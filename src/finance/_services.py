from django.db import transaction
from django.db.models import F, Sum
from django.utils import timezone

from .models import (
    Expense,
    FeeCategory,
    FeeStructure,
    Invoice,
    InvoiceItem,
    Payment,
    Scholarship,
    StudentScholarship,
)


class FinanceService:
    """Service class for finance-related operations."""

    @staticmethod
    def generate_invoice(
        student, fee_structures, issue_date=None, due_date=None, created_by=None
    ):
        """
        Generate an invoice for a student based on provided fee structures.

        Args:
            student: Student model instance
            fee_structures: List of FeeStructure instances
            issue_date: Issue date (defaults to current date)
            due_date: Due date (defaults to 15 days from issue date)
            created_by: User who created the invoice

        Returns:
            Generated Invoice instance
        """
        if not issue_date:
            issue_date = timezone.now().date()

        if not due_date:
            due_date = issue_date + timezone.timedelta(days=15)

        # Calculate totals
        total_amount = sum(fs.amount for fs in fee_structures)

        # Calculate applicable discounts based on student's scholarships
        discount_amount = 0
        active_scholarships = StudentScholarship.objects.filter(
            student=student,
            status="approved",
            start_date__lte=issue_date,
            scholarship__academic_year=fee_structures[0].academic_year,
        ).select_related("scholarship")

        # A more sophisticated discount calculation would be implemented here
        # This is a simplified version
        for student_scholarship in active_scholarships:
            scholarship = student_scholarship.scholarship
            if scholarship.discount_type == "percentage":
                discount_amount += total_amount * scholarship.discount_value / 100
            else:  # fixed amount
                discount_amount += scholarship.discount_value

        # Ensure discount doesn't exceed total
        discount_amount = min(discount_amount, total_amount)

        with transaction.atomic():
            # Create invoice
            invoice = Invoice.objects.create(
                student=student,
                academic_year=fee_structures[0].academic_year,
                issue_date=issue_date,
                due_date=due_date,
                total_amount=total_amount,
                discount_amount=discount_amount,
                net_amount=total_amount - discount_amount,
                created_by=created_by,
            )

            # Create invoice items
            for fee_structure in fee_structures:
                # For simplicity, we're not calculating per-item discounts
                # In a real system, you might want to apply discounts to specific items
                InvoiceItem.objects.create(
                    invoice=invoice,
                    fee_structure=fee_structure,
                    description=f"{fee_structure.fee_category.name} - {fee_structure.grade.name}",
                    amount=fee_structure.amount,
                    discount_amount=0,
                    net_amount=fee_structure.amount,
                )

            return invoice

    @staticmethod
    def generate_bulk_invoices(
        academic_year,
        fee_category,
        grade=None,
        issue_date=None,
        due_date=None,
        created_by=None,
    ):
        """
        Generate invoices in bulk for multiple students.

        Args:
            academic_year: AcademicYear instance
            fee_category: FeeCategory instance
            grade: Grade instance (optional, if None, generate for all grades)
            issue_date: Issue date
            due_date: Due date
            created_by: User who created the invoices

        Returns:
            List of generated Invoice instances
        """
        from src.students.models import Student

        # Get fee structures
        query = FeeStructure.objects.filter(
            academic_year=academic_year, fee_category=fee_category
        )

        if grade:
            query = query.filter(grade=grade)
            students = Student.objects.filter(
                current_class__grade=grade, status="Active"
            )
        else:
            students = Student.objects.filter(status="Active")

        fee_structures_by_grade = {}
        for fs in query:
            if fs.grade_id not in fee_structures_by_grade:
                fee_structures_by_grade[fs.grade_id] = []
            fee_structures_by_grade[fs.grade_id].append(fs)

        # Generate invoices
        invoices = []
        for student in students:
            # Skip if student's grade has no fee structure
            student_grade_id = getattr(student.current_class.grade, "id", None)
            if not student_grade_id or student_grade_id not in fee_structures_by_grade:
                continue

            # Skip if invoice already exists for this student, fee category and academic year
            if Invoice.objects.filter(
                student=student,
                academic_year=academic_year,
                items__fee_structure__fee_category=fee_category,
            ).exists():
                continue

            invoice = FinanceService.generate_invoice(
                student=student,
                fee_structures=fee_structures_by_grade[student_grade_id],
                issue_date=issue_date,
                due_date=due_date,
                created_by=created_by,
            )
            invoices.append(invoice)

        return invoices

    @staticmethod
    def record_payment(
        invoice,
        amount,
        payment_method,
        payment_date=None,
        transaction_id=None,
        remarks=None,
        received_by=None,
    ):
        """
        Record a payment for an invoice.

        Args:
            invoice: Invoice instance
            amount: Payment amount
            payment_method: Payment method
            payment_date: Date of payment
            transaction_id: Transaction ID for reference
            remarks: Additional notes
            received_by: User who received the payment

        Returns:
            Created Payment instance
        """
        if not payment_date:
            payment_date = timezone.now().date()

        # Ensure payment doesn't exceed due amount
        due_amount = invoice.get_due_amount()
        if amount > due_amount:
            amount = due_amount

        # Create payment
        payment = Payment.objects.create(
            invoice=invoice,
            payment_date=payment_date,
            amount=amount,
            payment_method=payment_method,
            transaction_id=transaction_id or "",
            remarks=remarks or "",
            received_by=received_by,
        )

        # Update invoice status
        invoice.update_status()

        return payment

    @staticmethod
    def get_financial_summary(start_date=None, end_date=None):
        """
        Get financial summary for a date range.

        Args:
            start_date: Start date for summary
            end_date: End date for summary

        Returns:
            Dictionary with financial summary
        """
        # Default to current month if dates not provided
        if not start_date:
            today = timezone.now().date()
            start_date = today.replace(day=1)

        if not end_date:
            import calendar

            today = timezone.now().date()
            _, last_day = calendar.monthrange(today.year, today.month)
            end_date = today.replace(day=last_day)

        # Calculate income (payments received)
        payments = Payment.objects.filter(
            payment_date__gte=start_date, payment_date__lte=end_date, status="completed"
        )
        total_income = payments.aggregate(Sum("amount"))["amount__sum"] or 0

        # Calculate expenses
        expenses = Expense.objects.filter(
            expense_date__gte=start_date, expense_date__lte=end_date
        )
        total_expenses = expenses.aggregate(Sum("amount"))["amount__sum"] or 0

        # Calculate outstanding fees
        outstanding_invoices = Invoice.objects.filter(
            due_date__lte=end_date, status__in=["unpaid", "partially_paid", "overdue"]
        )
        total_outstanding = sum(
            invoice.get_due_amount() for invoice in outstanding_invoices
        )

        # Get expense breakdown by category
        expense_by_category = (
            expenses.values("expense_category")
            .annotate(total=Sum("amount"))
            .order_by("-total")
        )

        # Get income breakdown by fee category
        income_by_category = Payment.objects.filter(
            payment_date__gte=start_date, payment_date__lte=end_date, status="completed"
        ).select_related("invoice__items__fee_structure__fee_category")

        # This is a simplified calculation - in a real system,
        # you would need a more sophisticated approach to allocate payments
        # to specific fee categories, especially for partial payments
        income_categories = {}
        for payment in income_by_category:
            for item in payment.invoice.items.all():
                category_name = item.fee_structure.fee_category.name
                if category_name not in income_categories:
                    income_categories[category_name] = 0

                # Allocate payment proportionally
                item_ratio = item.net_amount / payment.invoice.net_amount
                income_categories[category_name] += payment.amount * item_ratio

        income_by_category_list = [
            {"category": k, "total": v} for k, v in income_categories.items()
        ]

        return {
            "period": {"start_date": start_date, "end_date": end_date},
            "summary": {
                "total_income": total_income,
                "total_expenses": total_expenses,
                "net_profit": total_income - total_expenses,
                "total_outstanding": total_outstanding,
            },
            "expense_breakdown": list(expense_by_category),
            "income_breakdown": income_by_category_list,
        }
