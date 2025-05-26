from decimal import Decimal
from typing import Dict, List, Optional

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F, Q, Sum
from django.utils import timezone

from ..models import FinancialSummary, Invoice, Payment


class PaymentService:
    """Service for payment processing and management."""

    @classmethod
    @transaction.atomic
    def process_single_payment(
        cls,
        invoice_id: int,
        amount: Decimal,
        payment_method: str,
        received_by=None,
        **kwargs,
    ) -> Payment:
        """Process a single payment for an invoice."""

        try:
            invoice = Invoice.objects.select_for_update().get(id=invoice_id)
        except Invoice.DoesNotExist:
            raise ValidationError("Invoice not found")

        # Validate payment amount
        if amount <= 0:
            raise ValidationError("Payment amount must be positive")

        outstanding = invoice.outstanding_amount
        if outstanding <= 0:
            raise ValidationError("Invoice is already fully paid")

        # Allow overpayment (will be treated as advance payment)
        payment = Payment.objects.create(
            invoice=invoice,
            amount=amount,
            payment_method=payment_method,
            received_by=received_by,
            transaction_id=kwargs.get("transaction_id", ""),
            reference_number=kwargs.get("reference_number", ""),
            remarks=kwargs.get("remarks", ""),
            status=kwargs.get("status", "completed"),
        )

        # Update invoice paid amount
        invoice.paid_amount = F("paid_amount") + amount
        invoice.save()
        invoice.refresh_from_db()

        # Update invoice status
        cls._update_invoice_status(invoice)

        return payment

    @classmethod
    @transaction.atomic
    def process_bulk_payment(
        cls, student_payments: List[Dict], received_by=None
    ) -> Dict:
        """Process multiple payments in bulk."""

        results = {"successful": [], "failed": [], "total_processed": Decimal("0.00")}

        for payment_data in student_payments:
            try:
                payment = cls.process_single_payment(
                    invoice_id=payment_data["invoice_id"],
                    amount=payment_data["amount"],
                    payment_method=payment_data.get("payment_method", "cash"),
                    received_by=received_by,
                    **payment_data.get("additional_data", {}),
                )

                results["successful"].append(
                    {
                        "payment": payment,
                        "invoice_id": payment_data["invoice_id"],
                        "amount": payment_data["amount"],
                    }
                )
                results["total_processed"] += payment_data["amount"]

            except Exception as e:
                results["failed"].append(
                    {
                        "invoice_id": payment_data["invoice_id"],
                        "amount": payment_data["amount"],
                        "error": str(e),
                    }
                )

        return results

    @classmethod
    def allocate_advance_payment(
        cls,
        student,
        amount: Decimal,
        academic_year,
        payment_method: str,
        received_by=None,
    ) -> List[Payment]:
        """Allocate advance payment across unpaid invoices for a student."""

        # Get unpaid invoices for the student in chronological order
        unpaid_invoices = Invoice.objects.filter(
            student=student,
            academic_year=academic_year,
            status__in=["unpaid", "partially_paid"],
        ).order_by("due_date", "created_at")

        remaining_amount = amount
        payments_created = []

        for invoice in unpaid_invoices:
            if remaining_amount <= 0:
                break

            outstanding = invoice.outstanding_amount
            if outstanding <= 0:
                continue

            # Allocate payment (partial or full)
            payment_amount = min(remaining_amount, outstanding)

            payment = cls.process_single_payment(
                invoice_id=invoice.id,
                amount=payment_amount,
                payment_method=payment_method,
                received_by=received_by,
                remarks=f"Allocated from advance payment of {amount}",
            )

            payments_created.append(payment)
            remaining_amount -= payment_amount

        return payments_created

    @classmethod
    def process_refund(
        cls, payment_id: int, refund_amount: Decimal, reason: str, processed_by=None
    ) -> Payment:
        """Process refund for a payment."""

        try:
            original_payment = Payment.objects.get(id=payment_id)
        except Payment.DoesNotExist:
            raise ValidationError("Original payment not found")

        if original_payment.status == "refunded":
            raise ValidationError("Payment already refunded")

        if refund_amount > original_payment.amount:
            raise ValidationError("Refund amount exceeds original payment")

        # Create refund payment (negative amount)
        refund_payment = Payment.objects.create(
            invoice=original_payment.invoice,
            amount=-refund_amount,
            payment_method=original_payment.payment_method,
            received_by=processed_by,
            transaction_id=f"REFUND-{original_payment.transaction_id}",
            remarks=f"Refund: {reason}",
            status="completed",
        )

        # Update original payment status
        if refund_amount == original_payment.amount:
            original_payment.status = "refunded"
            original_payment.save()

        # Update invoice paid amount
        invoice = original_payment.invoice
        invoice.paid_amount = F("paid_amount") - refund_amount
        invoice.save()
        invoice.refresh_from_db()

        cls._update_invoice_status(invoice)

        return refund_payment

    @classmethod
    def get_payment_analytics(
        cls, academic_year, term=None, section=None, grade=None
    ) -> Dict:
        """Get payment analytics for specified filters."""

        # Base queryset
        payments = Payment.objects.filter(
            invoice__academic_year=academic_year, status="completed"
        )

        if term:
            payments = payments.filter(invoice__term=term)

        if section:
            payments = payments.filter(
                invoice__student__current_class__grade__section=section
            )
        elif grade:
            payments = payments.filter(invoice__student__current_class__grade=grade)

        # Calculate analytics
        total_payments = payments.aggregate(
            total_amount=Sum("amount"), payment_count=models.Count("id")
        )

        # Payment method breakdown
        method_breakdown = (
            payments.values("payment_method")
            .annotate(count=models.Count("id"), total=Sum("amount"))
            .order_by("-total")
        )

        # Daily collection trend (last 30 days)
        from datetime import timedelta

        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=30)

        daily_collections = (
            payments.filter(payment_date__date__range=[start_date, end_date])
            .extra(select={"day": "date(payment_date)"})
            .values("day")
            .annotate(daily_total=Sum("amount"), daily_count=models.Count("id"))
            .order_by("day")
        )

        return {
            "total_amount": total_payments["total_amount"] or Decimal("0.00"),
            "payment_count": total_payments["payment_count"] or 0,
            "method_breakdown": list(method_breakdown),
            "daily_collections": list(daily_collections),
            "average_payment": (
                total_payments["total_amount"] / total_payments["payment_count"]
                if total_payments["payment_count"] > 0
                else Decimal("0.00")
            ),
        }

    @classmethod
    def generate_receipt_data(cls, payment_id: int) -> Dict:
        """Generate receipt data for a payment."""

        try:
            payment = Payment.objects.select_related(
                "invoice__student__user",
                "invoice__academic_year",
                "invoice__term",
                "received_by",
            ).get(id=payment_id)
        except Payment.DoesNotExist:
            raise ValidationError("Payment not found")

        return {
            "receipt_number": payment.receipt_number,
            "payment_date": payment.payment_date,
            "amount": payment.amount,
            "payment_method": payment.get_payment_method_display(),
            "transaction_id": payment.transaction_id,
            "reference_number": payment.reference_number,
            "student": {
                "name": payment.invoice.student.user.get_full_name(),
                "admission_number": payment.invoice.student.admission_number,
                "class": str(payment.invoice.student.current_class),
            },
            "invoice": {
                "number": payment.invoice.invoice_number,
                "total_amount": payment.invoice.total_amount,
                "net_amount": payment.invoice.net_amount,
                "paid_amount": payment.invoice.paid_amount,
                "outstanding": payment.invoice.outstanding_amount,
            },
            "academic_details": {
                "year": str(payment.invoice.academic_year),
                "term": str(payment.invoice.term),
            },
            "received_by": (
                payment.received_by.get_full_name() if payment.received_by else ""
            ),
            "remarks": payment.remarks,
        }

    @classmethod
    def get_collection_summary(cls, date_from, date_to, group_by="day") -> List[Dict]:
        """Get collection summary for a date range."""

        payments = Payment.objects.filter(
            payment_date__date__range=[date_from, date_to], status="completed"
        )

        if group_by == "day":
            collections = (
                payments.extra(select={"period": "date(payment_date)"})
                .values("period")
                .annotate(
                    total_amount=Sum("amount"),
                    payment_count=models.Count("id"),
                    unique_students=models.Count("invoice__student", distinct=True),
                )
                .order_by("period")
            )

        elif group_by == "month":
            collections = (
                payments.extra(select={"period": "to_char(payment_date, 'YYYY-MM')"})
                .values("period")
                .annotate(
                    total_amount=Sum("amount"),
                    payment_count=models.Count("id"),
                    unique_students=models.Count("invoice__student", distinct=True),
                )
                .order_by("period")
            )

        elif group_by == "method":
            collections = (
                payments.values("payment_method")
                .annotate(
                    total_amount=Sum("amount"),
                    payment_count=models.Count("id"),
                    unique_students=models.Count("invoice__student", distinct=True),
                )
                .order_by("-total_amount")
            )

        return list(collections)

    @classmethod
    def reconcile_payments(cls, date, expected_cash_amount=None) -> Dict:
        """Reconcile payments for a specific date."""

        payments_today = Payment.objects.filter(
            payment_date__date=date, status="completed"
        )

        # Group by payment method
        method_totals = payments_today.values("payment_method").annotate(
            total=Sum("amount"), count=models.Count("id")
        )

        # Calculate cash total
        cash_total = payments_today.filter(payment_method="cash").aggregate(
            total=Sum("amount")
        )["total"] or Decimal("0.00")

        reconciliation = {
            "date": date,
            "total_collections": payments_today.aggregate(Sum("amount"))["amount__sum"]
            or Decimal("0.00"),
            "total_payments": payments_today.count(),
            "method_breakdown": list(method_totals),
            "cash_collected": cash_total,
            "cash_expected": expected_cash_amount,
            "cash_variance": (
                cash_total - expected_cash_amount if expected_cash_amount else None
            ),
        }

        return reconciliation

    @classmethod
    def _update_invoice_status(cls, invoice):
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
    def validate_payment_method(
        cls, payment_method: str, additional_data: Dict
    ) -> bool:
        """Validate payment method and required additional data."""

        required_fields = {
            "credit_card": ["transaction_id"],
            "debit_card": ["transaction_id"],
            "bank_transfer": ["reference_number"],
            "cheque": ["reference_number"],
            "online": ["transaction_id"],
            "mobile_payment": ["transaction_id"],
        }

        if payment_method in required_fields:
            for field in required_fields[payment_method]:
                if not additional_data.get(field):
                    raise ValidationError(
                        f"{field} is required for {payment_method} payments"
                    )

        return True

    @classmethod
    def get_outstanding_by_student(cls, academic_year, term=None) -> List[Dict]:
        """Get outstanding amounts grouped by student."""

        queryset = Invoice.objects.filter(
            academic_year=academic_year, status__in=["unpaid", "partially_paid"]
        ).select_related("student__user", "student__current_class")

        if term:
            queryset = queryset.filter(term=term)

        student_outstanding = {}

        for invoice in queryset:
            student_id = invoice.student.id
            if student_id not in student_outstanding:
                student_outstanding[student_id] = {
                    "student": invoice.student,
                    "total_outstanding": Decimal("0.00"),
                    "invoice_count": 0,
                    "oldest_due_date": invoice.due_date,
                }

            student_outstanding[student_id][
                "total_outstanding"
            ] += invoice.outstanding_amount
            student_outstanding[student_id]["invoice_count"] += 1

            if invoice.due_date < student_outstanding[student_id]["oldest_due_date"]:
                student_outstanding[student_id]["oldest_due_date"] = invoice.due_date

        return sorted(
            student_outstanding.values(),
            key=lambda x: x["total_outstanding"],
            reverse=True,
        )
