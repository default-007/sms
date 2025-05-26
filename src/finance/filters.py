import django_filters
from django.db import models
from django.db.models import Q
from django.utils import timezone
from datetime import datetime, timedelta

from .models import (
    FeeCategory,
    FeeStructure,
    SpecialFee,
    Scholarship,
    StudentScholarship,
    Invoice,
    Payment,
    FinancialAnalytics,
    FeeWaiver,
)
from academics.models import AcademicYear, Term, Section, Grade, Class
from students.models import Student


class FeeCategoryFilter(django_filters.FilterSet):
    """Filter for fee categories."""

    name = django_filters.CharFilter(lookup_expr="icontains")
    is_mandatory = django_filters.BooleanFilter()
    is_recurring = django_filters.BooleanFilter()
    frequency = django_filters.ChoiceFilter(choices=FeeCategory.FREQUENCY_CHOICES)

    class Meta:
        model = FeeCategory
        fields = ["name", "is_mandatory", "is_recurring", "frequency"]


class FeeStructureFilter(django_filters.FilterSet):
    """Filter for fee structures."""

    academic_year = django_filters.ModelChoiceFilter(
        queryset=AcademicYear.objects.all()
    )
    term = django_filters.ModelChoiceFilter(queryset=Term.objects.all())
    section = django_filters.ModelChoiceFilter(queryset=Section.objects.all())
    grade = django_filters.ModelChoiceFilter(queryset=Grade.objects.all())
    fee_category = django_filters.ModelChoiceFilter(queryset=FeeCategory.objects.all())

    amount_min = django_filters.NumberFilter(field_name="amount", lookup_expr="gte")
    amount_max = django_filters.NumberFilter(field_name="amount", lookup_expr="lte")

    due_date_from = django_filters.DateFilter(field_name="due_date", lookup_expr="gte")
    due_date_to = django_filters.DateFilter(field_name="due_date", lookup_expr="lte")

    is_active = django_filters.BooleanFilter()

    class Meta:
        model = FeeStructure
        fields = [
            "academic_year",
            "term",
            "section",
            "grade",
            "fee_category",
            "amount_min",
            "amount_max",
            "due_date_from",
            "due_date_to",
            "is_active",
        ]


class SpecialFeeFilter(django_filters.FilterSet):
    """Filter for special fees."""

    name = django_filters.CharFilter(lookup_expr="icontains")
    fee_category = django_filters.ModelChoiceFilter(queryset=FeeCategory.objects.all())
    fee_type = django_filters.ChoiceFilter(choices=SpecialFee.FEE_TYPE_CHOICES)
    term = django_filters.ModelChoiceFilter(queryset=Term.objects.all())

    amount_min = django_filters.NumberFilter(field_name="amount", lookup_expr="gte")
    amount_max = django_filters.NumberFilter(field_name="amount", lookup_expr="lte")

    due_date_from = django_filters.DateFilter(field_name="due_date", lookup_expr="gte")
    due_date_to = django_filters.DateFilter(field_name="due_date", lookup_expr="lte")

    is_active = django_filters.BooleanFilter()

    # Student and class filters
    student = django_filters.ModelChoiceFilter(queryset=Student.objects.all())
    class_obj = django_filters.ModelChoiceFilter(
        field_name="class_obj", queryset=Class.objects.all()
    )

    class Meta:
        model = SpecialFee
        fields = [
            "name",
            "fee_category",
            "fee_type",
            "term",
            "amount_min",
            "amount_max",
            "due_date_from",
            "due_date_to",
            "is_active",
            "student",
            "class_obj",
        ]


class ScholarshipFilter(django_filters.FilterSet):
    """Filter for scholarships."""

    name = django_filters.CharFilter(lookup_expr="icontains")
    academic_year = django_filters.ModelChoiceFilter(
        queryset=AcademicYear.objects.all()
    )
    criteria = django_filters.ChoiceFilter(choices=Scholarship.CRITERIA_CHOICES)
    discount_type = django_filters.ChoiceFilter(
        choices=Scholarship.DISCOUNT_TYPE_CHOICES
    )

    discount_value_min = django_filters.NumberFilter(
        field_name="discount_value", lookup_expr="gte"
    )
    discount_value_max = django_filters.NumberFilter(
        field_name="discount_value", lookup_expr="lte"
    )

    is_active = django_filters.BooleanFilter()
    has_available_slots = django_filters.BooleanFilter(method="filter_available_slots")

    class Meta:
        model = Scholarship
        fields = [
            "name",
            "academic_year",
            "criteria",
            "discount_type",
            "discount_value_min",
            "discount_value_max",
            "is_active",
            "has_available_slots",
        ]

    def filter_available_slots(self, queryset, name, value):
        """Filter scholarships with available slots."""
        if value:
            return queryset.filter(
                Q(max_recipients__isnull=True)
                | Q(current_recipients__lt=models.F("max_recipients"))
            )
        else:
            return queryset.filter(current_recipients__gte=models.F("max_recipients"))


class StudentScholarshipFilter(django_filters.FilterSet):
    """Filter for student scholarship assignments."""

    student = django_filters.ModelChoiceFilter(queryset=Student.objects.all())
    scholarship = django_filters.ModelChoiceFilter(queryset=Scholarship.objects.all())
    status = django_filters.ChoiceFilter(choices=StudentScholarship.STATUS_CHOICES)

    # Filter by student details
    student_name = django_filters.CharFilter(method="filter_student_name")
    admission_number = django_filters.CharFilter(
        field_name="student__admission_number", lookup_expr="icontains"
    )

    # Filter by scholarship details
    scholarship_name = django_filters.CharFilter(
        field_name="scholarship__name", lookup_expr="icontains"
    )
    academic_year = django_filters.ModelChoiceFilter(
        field_name="scholarship__academic_year", queryset=AcademicYear.objects.all()
    )

    # Date filters
    start_date_from = django_filters.DateFilter(
        field_name="start_date", lookup_expr="gte"
    )
    start_date_to = django_filters.DateFilter(
        field_name="start_date", lookup_expr="lte"
    )
    approval_date_from = django_filters.DateFilter(
        field_name="approval_date", lookup_expr="gte"
    )
    approval_date_to = django_filters.DateFilter(
        field_name="approval_date", lookup_expr="lte"
    )

    class Meta:
        model = StudentScholarship
        fields = [
            "student",
            "scholarship",
            "status",
            "student_name",
            "admission_number",
            "scholarship_name",
            "academic_year",
            "start_date_from",
            "start_date_to",
            "approval_date_from",
            "approval_date_to",
        ]

    def filter_student_name(self, queryset, name, value):
        """Filter by student name (first name or last name)."""
        return queryset.filter(
            Q(student__user__first_name__icontains=value)
            | Q(student__user__last_name__icontains=value)
        )


class InvoiceFilter(django_filters.FilterSet):
    """Filter for invoices."""

    student = django_filters.ModelChoiceFilter(queryset=Student.objects.all())
    academic_year = django_filters.ModelChoiceFilter(
        queryset=AcademicYear.objects.all()
    )
    term = django_filters.ModelChoiceFilter(queryset=Term.objects.all())
    status = django_filters.ChoiceFilter(choices=Invoice.STATUS_CHOICES)

    # Student details filters
    student_name = django_filters.CharFilter(method="filter_student_name")
    admission_number = django_filters.CharFilter(
        field_name="student__admission_number", lookup_expr="icontains"
    )
    student_class = django_filters.ModelChoiceFilter(
        field_name="student__current_class", queryset=Class.objects.all()
    )

    # Amount filters
    total_amount_min = django_filters.NumberFilter(
        field_name="total_amount", lookup_expr="gte"
    )
    total_amount_max = django_filters.NumberFilter(
        field_name="total_amount", lookup_expr="lte"
    )
    net_amount_min = django_filters.NumberFilter(
        field_name="net_amount", lookup_expr="gte"
    )
    net_amount_max = django_filters.NumberFilter(
        field_name="net_amount", lookup_expr="lte"
    )
    outstanding_min = django_filters.NumberFilter(method="filter_outstanding_min")
    outstanding_max = django_filters.NumberFilter(method="filter_outstanding_max")

    # Date filters
    issue_date_from = django_filters.DateFilter(
        field_name="issue_date", lookup_expr="gte"
    )
    issue_date_to = django_filters.DateFilter(
        field_name="issue_date", lookup_expr="lte"
    )
    due_date_from = django_filters.DateFilter(field_name="due_date", lookup_expr="gte")
    due_date_to = django_filters.DateFilter(field_name="due_date", lookup_expr="lte")

    # Special filters
    is_overdue = django_filters.BooleanFilter(method="filter_overdue")
    has_payments = django_filters.BooleanFilter(method="filter_has_payments")

    class Meta:
        model = Invoice
        fields = [
            "student",
            "academic_year",
            "term",
            "status",
            "student_name",
            "admission_number",
            "student_class",
            "total_amount_min",
            "total_amount_max",
            "net_amount_min",
            "net_amount_max",
            "outstanding_min",
            "outstanding_max",
            "issue_date_from",
            "issue_date_to",
            "due_date_from",
            "due_date_to",
            "is_overdue",
            "has_payments",
        ]

    def filter_student_name(self, queryset, name, value):
        """Filter by student name."""
        return queryset.filter(
            Q(student__user__first_name__icontains=value)
            | Q(student__user__last_name__icontains=value)
        )

    def filter_outstanding_min(self, queryset, name, value):
        """Filter by minimum outstanding amount."""
        return queryset.extra(
            where=["(net_amount - paid_amount) >= %s"], params=[value]
        )

    def filter_outstanding_max(self, queryset, name, value):
        """Filter by maximum outstanding amount."""
        return queryset.extra(
            where=["(net_amount - paid_amount) <= %s"], params=[value]
        )

    def filter_overdue(self, queryset, name, value):
        """Filter overdue invoices."""
        today = timezone.now().date()
        if value:
            return queryset.filter(
                due_date__lt=today, status__in=["unpaid", "partially_paid"]
            )
        else:
            return queryset.exclude(
                due_date__lt=today, status__in=["unpaid", "partially_paid"]
            )

    def filter_has_payments(self, queryset, name, value):
        """Filter invoices with/without payments."""
        if value:
            return queryset.filter(payments__isnull=False).distinct()
        else:
            return queryset.filter(payments__isnull=True)


class PaymentFilter(django_filters.FilterSet):
    """Filter for payments."""

    invoice = django_filters.ModelChoiceFilter(queryset=Invoice.objects.all())
    payment_method = django_filters.ChoiceFilter(choices=Payment.PAYMENT_METHOD_CHOICES)
    status = django_filters.ChoiceFilter(choices=Payment.STATUS_CHOICES)
    received_by = django_filters.ModelChoiceFilter(
        queryset=lambda request: (
            User.objects.filter(is_staff=True) if request else User.objects.none()
        )
    )

    # Student filters (through invoice)
    student = django_filters.ModelChoiceFilter(
        field_name="invoice__student", queryset=Student.objects.all()
    )
    student_name = django_filters.CharFilter(method="filter_student_name")

    # Amount filters
    amount_min = django_filters.NumberFilter(field_name="amount", lookup_expr="gte")
    amount_max = django_filters.NumberFilter(field_name="amount", lookup_expr="lte")

    # Date filters
    payment_date_from = django_filters.DateFilter(
        field_name="payment_date", lookup_expr="gte"
    )
    payment_date_to = django_filters.DateFilter(
        field_name="payment_date", lookup_expr="lte"
    )

    # Recent payments filter
    recent_days = django_filters.NumberFilter(method="filter_recent_days")

    # Transaction details
    transaction_id = django_filters.CharFilter(lookup_expr="icontains")
    reference_number = django_filters.CharFilter(lookup_expr="icontains")

    class Meta:
        model = Payment
        fields = [
            "invoice",
            "payment_method",
            "status",
            "received_by",
            "student",
            "student_name",
            "amount_min",
            "amount_max",
            "payment_date_from",
            "payment_date_to",
            "recent_days",
            "transaction_id",
            "reference_number",
        ]

    def filter_student_name(self, queryset, name, value):
        """Filter by student name through invoice."""
        return queryset.filter(
            Q(invoice__student__user__first_name__icontains=value)
            | Q(invoice__student__user__last_name__icontains=value)
        )

    def filter_recent_days(self, queryset, name, value):
        """Filter payments from recent days."""
        if value:
            cutoff_date = timezone.now().date() - timedelta(days=value)
            return queryset.filter(payment_date__date__gte=cutoff_date)
        return queryset


class FinancialAnalyticsFilter(django_filters.FilterSet):
    """Filter for financial analytics."""

    academic_year = django_filters.ModelChoiceFilter(
        queryset=AcademicYear.objects.all()
    )
    term = django_filters.ModelChoiceFilter(queryset=Term.objects.all())
    section = django_filters.ModelChoiceFilter(queryset=Section.objects.all())
    grade = django_filters.ModelChoiceFilter(queryset=Grade.objects.all())
    fee_category = django_filters.ModelChoiceFilter(queryset=FeeCategory.objects.all())

    # Collection rate filters
    collection_rate_min = django_filters.NumberFilter(
        field_name="collection_rate", lookup_expr="gte"
    )
    collection_rate_max = django_filters.NumberFilter(
        field_name="collection_rate", lookup_expr="lte"
    )

    # Revenue filters
    expected_revenue_min = django_filters.NumberFilter(
        field_name="total_expected_revenue", lookup_expr="gte"
    )
    expected_revenue_max = django_filters.NumberFilter(
        field_name="total_expected_revenue", lookup_expr="lte"
    )

    # Date filters
    calculated_from = django_filters.DateTimeFilter(
        field_name="calculated_at", lookup_expr="gte"
    )
    calculated_to = django_filters.DateTimeFilter(
        field_name="calculated_at", lookup_expr="lte"
    )

    class Meta:
        model = FinancialAnalytics
        fields = [
            "academic_year",
            "term",
            "section",
            "grade",
            "fee_category",
            "collection_rate_min",
            "collection_rate_max",
            "expected_revenue_min",
            "expected_revenue_max",
            "calculated_from",
            "calculated_to",
        ]


class FeeWaiverFilter(django_filters.FilterSet):
    """Filter for fee waivers."""

    student = django_filters.ModelChoiceFilter(queryset=Student.objects.all())
    invoice = django_filters.ModelChoiceFilter(queryset=Invoice.objects.all())
    waiver_type = django_filters.ChoiceFilter(choices=FeeWaiver.WAIVER_TYPE_CHOICES)
    status = django_filters.ChoiceFilter(choices=FeeWaiver.STATUS_CHOICES)

    # Student details
    student_name = django_filters.CharFilter(method="filter_student_name")

    # Amount filters
    amount_min = django_filters.NumberFilter(field_name="amount", lookup_expr="gte")
    amount_max = django_filters.NumberFilter(field_name="amount", lookup_expr="lte")

    # Date filters
    created_from = django_filters.DateFilter(field_name="created_at", lookup_expr="gte")
    created_to = django_filters.DateFilter(field_name="created_at", lookup_expr="lte")

    # Staff filters
    requested_by = django_filters.ModelChoiceFilter(
        queryset=lambda request: (
            User.objects.filter(is_staff=True) if request else User.objects.none()
        )
    )
    approved_by = django_filters.ModelChoiceFilter(
        queryset=lambda request: (
            User.objects.filter(is_staff=True) if request else User.objects.none()
        )
    )

    class Meta:
        model = FeeWaiver
        fields = [
            "student",
            "invoice",
            "waiver_type",
            "status",
            "student_name",
            "amount_min",
            "amount_max",
            "created_from",
            "created_to",
            "requested_by",
            "approved_by",
        ]

    def filter_student_name(self, queryset, name, value):
        """Filter by student name."""
        return queryset.filter(
            Q(student__user__first_name__icontains=value)
            | Q(student__user__last_name__icontains=value)
        )


# Custom filter for date ranges
class DateRangeFilter(django_filters.FilterSet):
    """Reusable date range filter."""

    date_from = django_filters.DateFilter(method="filter_date_from")
    date_to = django_filters.DateFilter(method="filter_date_to")

    def filter_date_from(self, queryset, name, value):
        """Override in subclass to specify field."""
        return queryset

    def filter_date_to(self, queryset, name, value):
        """Override in subclass to specify field."""
        return queryset


# Advanced search filters
class AdvancedInvoiceFilter(InvoiceFilter):
    """Advanced invoice filter with complex queries."""

    # Multi-status filter
    status_in = django_filters.CharFilter(method="filter_status_in")

    # Payment status combinations
    fully_paid = django_filters.BooleanFilter(method="filter_fully_paid")
    no_payments = django_filters.BooleanFilter(method="filter_no_payments")

    # Academic filters
    section_name = django_filters.CharFilter(
        field_name="student__current_class__grade__section__name",
        lookup_expr="icontains",
    )
    grade_name = django_filters.CharFilter(
        field_name="student__current_class__grade__name", lookup_expr="icontains"
    )

    class Meta(InvoiceFilter.Meta):
        fields = InvoiceFilter.Meta.fields + [
            "status_in",
            "fully_paid",
            "no_payments",
            "section_name",
            "grade_name",
        ]

    def filter_status_in(self, queryset, name, value):
        """Filter by multiple statuses (comma-separated)."""
        if value:
            statuses = [status.strip() for status in value.split(",")]
            return queryset.filter(status__in=statuses)
        return queryset

    def filter_fully_paid(self, queryset, name, value):
        """Filter fully paid invoices."""
        if value:
            return queryset.filter(status="paid")
        return queryset

    def filter_no_payments(self, queryset, name, value):
        """Filter invoices with no payments."""
        if value:
            return queryset.filter(paid_amount=0)
        return queryset
