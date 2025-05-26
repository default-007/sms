from decimal import Decimal
from django.db import transaction, models
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db.models import Q, Sum, F
from typing import List, Dict, Optional

from ..models import Invoice, InvoiceItem, Payment, FeeWaiver
from .fee_service import FeeService


class InvoiceService:
    """Service for invoice generation and management."""

    @classmethod
    @transaction.atomic
    def generate_invoice(cls, student, academic_year, term, created_by=None) -> Invoice:
        """Generate invoice for a student for a specific term."""

        # Check if invoice already exists
        existing_invoice = Invoice.objects.filter(
            student=student, academic_year=academic_year, term=term
        ).first()

        if existing_invoice:
            raise ValidationError(f"Invoice already exists for {student} in {term}")

        # Calculate fees
        fee_breakdown = FeeService.calculate_student_fees(student, academic_year, term)

        # Create invoice
        invoice = Invoice.objects.create(
            student=student,
            academic_year=academic_year,
            term=term,
            due_date=cls._calculate_due_date(fee_breakdown),
            total_amount=fee_breakdown["total_amount"],
            discount_amount=fee_breakdown["discount_amount"],
            net_amount=fee_breakdown["net_amount"],
            created_by=created_by,
        )

        # Create invoice items for base fees
        for fee in fee_breakdown["base_fees"]:
            InvoiceItem.objects.create(
                invoice=invoice,
                fee_structure_id=fee.get("fee_structure_id"),
                description=f"{fee['category']} ({fee['type'].title()})",
                amount=fee["amount"],
                discount_amount=Decimal("0.00"),
                net_amount=fee["amount"],
            )

        # Create invoice items for special fees
        for fee in fee_breakdown["special_fees"]:
            InvoiceItem.objects.create(
                invoice=invoice,
                special_fee_id=fee.get("special_fee_id"),
                description=f"{fee['name']} - {fee['category']}",
                amount=fee["amount"],
                discount_amount=Decimal("0.00"),
                net_amount=fee["amount"],
            )

        # Apply scholarship discounts to invoice items
        if fee_breakdown["discount_amount"] > 0:
            cls._apply_scholarship_discounts(
                invoice, fee_breakdown["scholarships_applied"]
            )

        return invoice

    @classmethod
    def _calculate_due_date(cls, fee_breakdown):
        """Calculate due date based on earliest fee due date."""
        due_dates = []

        for fee in fee_breakdown["base_fees"]:
            if fee.get("due_date"):
                due_dates.append(fee["due_date"])

        for fee in fee_breakdown["special_fees"]:
            if fee.get("due_date"):
                due_dates.append(fee["due_date"])

        return min(due_dates) if due_dates else timezone.now().date()

    @classmethod
    def _apply_scholarship_discounts(cls, invoice, scholarships):
        """Apply scholarship discounts to invoice items."""
        items = invoice.items.all()
        total_discount = invoice.discount_amount

        # Distribute discount proportionally among items
        if total_discount > 0 and items.exists():
            for item in items:
                item_proportion = item.amount / invoice.total_amount
                item_discount = total_discount * item_proportion
                item.discount_amount = item_discount
                item.save()

    @classmethod
    def bulk_generate_invoices(
        cls, students_list, academic_year, term, created_by=None
    ) -> Dict:
        """Generate invoices for multiple students."""
        results = {"created": [], "skipped": [], "errors": []}

        for student in students_list:
            try:
                invoice = cls.generate_invoice(student, academic_year, term, created_by)
                results["created"].append({"student": student, "invoice": invoice})
            except ValidationError as e:
                results["skipped"].append({"student": student, "reason": str(e)})
            except Exception as e:
                results["errors"].append({"student": student, "error": str(e)})

        return results

    @classmethod
    def update_invoice_status(cls, invoice):
        """Update invoice status based on payments."""
        if invoice.paid_amount >= invoice.net_amount:
            invoice.status = "paid"
        elif invoice.paid_amount > 0:
            invoice.status = "partially_paid"
        elif invoice.is_overdue:
            invoice.status = "overdue"
        else:
            invoice.status = "unpaid"

        invoice.save()

    @classmethod
    @transaction.atomic
    def process_payment(
        cls, invoice, amount, payment_method, received_by=None, **kwargs
    ) -> Payment:
        """Process payment for an invoice."""

        if amount <= 0:
            raise ValidationError("Payment amount must be positive")

        if invoice.outstanding_amount <= 0:
            raise ValidationError("Invoice is already fully paid")

        if amount > invoice.outstanding_amount:
            raise ValidationError("Payment amount exceeds outstanding balance")

        # Create payment record
        payment = Payment.objects.create(
            invoice=invoice,
            amount=amount,
            payment_method=payment_method,
            received_by=received_by,
            transaction_id=kwargs.get("transaction_id", ""),
            reference_number=kwargs.get("reference_number", ""),
            remarks=kwargs.get("remarks", ""),
            status="completed",
        )

        # Update invoice paid amount
        invoice.paid_amount = F("paid_amount") + amount
        invoice.save()
        invoice.refresh_from_db()

        # Update invoice status
        cls.update_invoice_status(invoice)

        return payment

    @classmethod
    def get_overdue_invoices(cls, days_overdue=None) -> List[Invoice]:
        """Get overdue invoices."""
        today = timezone.now().date()

        queryset = Invoice.objects.filter(
            due_date__lt=today, status__in=["unpaid", "partially_paid"]
        ).select_related("student", "academic_year", "term")

        if days_overdue:
            cutoff_date = today - timezone.timedelta(days=days_overdue)
            queryset = queryset.filter(due_date__lt=cutoff_date)

        return list(queryset)

    @classmethod
    def get_payment_history(
        cls, student=None, academic_year=None, term=None
    ) -> List[Payment]:
        """Get payment history with filters."""
        queryset = Payment.objects.select_related("invoice__student", "received_by")

        if student:
            queryset = queryset.filter(invoice__student=student)

        if academic_year:
            queryset = queryset.filter(invoice__academic_year=academic_year)

        if term:
            queryset = queryset.filter(invoice__term=term)

        return list(queryset.order_by("-payment_date"))

    @classmethod
    def calculate_collection_statistics(cls, academic_year, term=None) -> Dict:
        """Calculate collection statistics for a period."""
        queryset = Invoice.objects.filter(academic_year=academic_year)

        if term:
            queryset = queryset.filter(term=term)

        stats = queryset.aggregate(
            total_invoices=models.Count("id"),
            total_amount_due=models.Sum("net_amount"),
            total_amount_paid=models.Sum("paid_amount"),
            total_outstanding=models.Sum("net_amount") - models.Sum("paid_amount"),
        )

        # Calculate collection rate
        if stats["total_amount_due"]:
            collection_rate = (
                stats["total_amount_paid"] / stats["total_amount_due"]
            ) * 100
        else:
            collection_rate = 0

        # Count status breakdown
        status_breakdown = (
            queryset.values("status")
            .annotate(count=models.Count("id"))
            .order_by("status")
        )

        return {
            "total_invoices": stats["total_invoices"] or 0,
            "total_amount_due": stats["total_amount_due"] or Decimal("0.00"),
            "total_amount_paid": stats["total_amount_paid"] or Decimal("0.00"),
            "total_outstanding": stats["total_outstanding"] or Decimal("0.00"),
            "collection_rate": round(collection_rate, 2),
            "status_breakdown": list(status_breakdown),
        }

    @classmethod
    @transaction.atomic
    def apply_fee_waiver(
        cls, invoice, amount, reason, requested_by, waiver_type="partial"
    ):
        """Apply fee waiver to an invoice."""

        if amount <= 0:
            raise ValidationError("Waiver amount must be positive")

        if amount > invoice.outstanding_amount:
            raise ValidationError("Waiver amount exceeds outstanding balance")

        # Create waiver record
        waiver = FeeWaiver.objects.create(
            student=invoice.student,
            invoice=invoice,
            waiver_type=waiver_type,
            amount=amount,
            reason=reason,
            requested_by=requested_by,
            status="pending",
        )

        return waiver

    @classmethod
    @transaction.atomic
    def approve_fee_waiver(cls, waiver, approved_by):
        """Approve a fee waiver and apply it to the invoice."""

        if waiver.status != "pending":
            raise ValidationError("Only pending waivers can be approved")

        # Update waiver
        waiver.status = "approved"
        waiver.approved_by = approved_by
        waiver.save()

        # Apply waiver to invoice as a negative payment
        invoice = waiver.invoice
        payment = Payment.objects.create(
            invoice=invoice,
            amount=waiver.amount,
            payment_method="waiver",
            received_by=approved_by,
            remarks=f"Fee waiver approved: {waiver.reason}",
            status="completed",
        )

        # Update invoice
        invoice.paid_amount = F("paid_amount") + waiver.amount
        invoice.save()
        invoice.refresh_from_db()

        cls.update_invoice_status(invoice)

        return payment

    @classmethod
    def generate_invoice_pdf(cls, invoice):
        """Generate PDF for invoice (placeholder for PDF generation logic)."""
        # This would integrate with a PDF generation library like reportlab
        # For now, return a dictionary with invoice data
        return {
            "invoice_number": invoice.invoice_number,
            "student": str(invoice.student),
            "total_amount": invoice.total_amount,
            "net_amount": invoice.net_amount,
            "outstanding_amount": invoice.outstanding_amount,
            "items": [
                {
                    "description": item.description,
                    "amount": item.amount,
                    "discount": item.discount_amount,
                    "net_amount": item.net_amount,
                }
                for item in invoice.items.all()
            ],
            "payments": [
                {
                    "date": payment.payment_date,
                    "amount": payment.amount,
                    "method": payment.payment_method,
                    "receipt_number": payment.receipt_number,
                }
                for payment in invoice.payments.all()
            ],
        }

    @classmethod
    def send_payment_reminder(cls, invoice):
        """Send payment reminder for overdue invoice."""
        # This would integrate with the communications module
        # For now, return reminder data
        return {
            "recipient": invoice.student.user.email,
            "subject": f"Payment Reminder - Invoice {invoice.invoice_number}",
            "message": f"Your payment of {invoice.outstanding_amount} is overdue.",
            "due_date": invoice.due_date,
            "invoice_url": f"/finance/invoices/{invoice.id}/",
        }

    @classmethod
    def get_defaulter_report(
        cls, academic_year, term=None, days_overdue=30
    ) -> List[Dict]:
        """Get list of students with overdue payments."""
        today = timezone.now().date()
        cutoff_date = today - timezone.timedelta(days=days_overdue)

        queryset = Invoice.objects.filter(
            academic_year=academic_year,
            due_date__lt=cutoff_date,
            status__in=["unpaid", "partially_paid"],
        ).select_related("student", "student__user")

        if term:
            queryset = queryset.filter(term=term)

        defaulters = []
        for invoice in queryset:
            days_overdue_count = (today - invoice.due_date).days
            defaulters.append(
                {
                    "student": invoice.student,
                    "invoice_number": invoice.invoice_number,
                    "outstanding_amount": invoice.outstanding_amount,
                    "due_date": invoice.due_date,
                    "days_overdue": days_overdue_count,
                    "contact_email": invoice.student.user.email,
                    "contact_phone": invoice.student.user.phone_number,
                }
            )

        return sorted(defaulters, key=lambda x: x["days_overdue"], reverse=True)
