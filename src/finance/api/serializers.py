from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from src.academics.models import AcademicYear, Class, Grade, Section, Term
from src.students.models import Student

from ..models import (
    FeeCategory,
    FeeStructure,
    FeeWaiver,
    FinancialAnalytics,
    FinancialSummary,
    Invoice,
    InvoiceItem,
    Payment,
    Scholarship,
    SpecialFee,
    StudentScholarship,
)


class FeeCategorySerializer(serializers.ModelSerializer):
    """Serializer for fee categories."""

    class Meta:
        model = FeeCategory
        fields = [
            "id",
            "name",
            "description",
            "is_recurring",
            "frequency",
            "is_mandatory",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]


class FeeStructureSerializer(serializers.ModelSerializer):
    """Serializer for fee structures."""

    fee_category_name = serializers.CharField(
        source="fee_category.name", read_only=True
    )
    section_name = serializers.CharField(source="section.name", read_only=True)
    grade_name = serializers.CharField(source="grade.name", read_only=True)
    applicable_level = serializers.CharField(read_only=True)
    created_by_name = serializers.CharField(
        source="created_by.get_full_name", read_only=True
    )

    class Meta:
        model = FeeStructure
        fields = [
            "id",
            "academic_year",
            "term",
            "section",
            "grade",
            "fee_category",
            "amount",
            "due_date",
            "late_fee_percentage",
            "grace_period_days",
            "is_active",
            "created_at",
            "created_by",
            "fee_category_name",
            "section_name",
            "grade_name",
            "applicable_level",
            "created_by_name",
        ]
        read_only_fields = ["created_at", "created_by"]

    def validate(self, data):
        """Validate fee structure data."""
        if not data.get("section") and not data.get("grade"):
            raise serializers.ValidationError(
                "Either section or grade must be specified"
            )

        # Check for duplicate fee structures
        existing = FeeStructure.objects.filter(
            academic_year=data["academic_year"],
            term=data["term"],
            section=data.get("section"),
            grade=data.get("grade"),
            fee_category=data["fee_category"],
        )

        if self.instance:
            existing = existing.exclude(id=self.instance.id)

        if existing.exists():
            raise serializers.ValidationError(
                "Fee structure already exists for this combination"
            )

        return data

    def create(self, validated_data):
        validated_data["created_by"] = self.context["request"].user
        return super().create(validated_data)


class SpecialFeeSerializer(serializers.ModelSerializer):
    """Serializer for special fees."""

    fee_category_name = serializers.CharField(
        source="fee_category.name", read_only=True
    )
    class_name = serializers.CharField(source="class_obj.name", read_only=True)
    student_name = serializers.CharField(
        source="student.user.get_full_name", read_only=True
    )
    created_by_name = serializers.CharField(
        source="created_by.get_full_name", read_only=True
    )

    class Meta:
        model = SpecialFee
        fields = [
            "id",
            "name",
            "description",
            "fee_category",
            "amount",
            "fee_type",
            "class_obj",
            "student",
            "term",
            "due_date",
            "reason",
            "is_active",
            "created_at",
            "updated_at",
            "created_by",
            "fee_category_name",
            "class_name",
            "student_name",
            "created_by_name",
        ]
        read_only_fields = ["created_at", "updated_at", "created_by"]

    def validate(self, data):
        """Validate special fee data."""
        fee_type = data.get("fee_type")

        if fee_type == "class_based" and not data.get("class_obj"):
            raise serializers.ValidationError("Class is required for class-based fees")
        elif fee_type == "student_specific" and not data.get("student"):
            raise serializers.ValidationError(
                "Student is required for student-specific fees"
            )

        return data

    def create(self, validated_data):
        validated_data["created_by"] = self.context["request"].user
        return super().create(validated_data)


class ScholarshipSerializer(serializers.ModelSerializer):
    """Serializer for scholarships."""

    applicable_categories = FeeCategorySerializer(many=True, read_only=True)
    applicable_category_ids = serializers.ListField(
        child=serializers.IntegerField(), write_only=True, required=False
    )
    current_recipients_count = serializers.IntegerField(
        source="current_recipients", read_only=True
    )
    has_available_slots = serializers.BooleanField(read_only=True)
    created_by_name = serializers.CharField(
        source="created_by.get_full_name", read_only=True
    )

    class Meta:
        model = Scholarship
        fields = [
            "id",
            "name",
            "description",
            "discount_type",
            "discount_value",
            "criteria",
            "academic_year",
            "applicable_terms",
            "max_recipients",
            "current_recipients_count",
            "is_active",
            "created_at",
            "created_by",
            "applicable_categories",
            "applicable_category_ids",
            "has_available_slots",
            "created_by_name",
        ]
        read_only_fields = ["created_at", "created_by", "current_recipients"]

    def validate_discount_value(self, value):
        """Validate discount value."""
        if value <= 0:
            raise serializers.ValidationError("Discount value must be positive")
        return value

    def validate(self, data):
        """Validate scholarship data."""
        if (
            data.get("discount_type") == "percentage"
            and data.get("discount_value", 0) > 100
        ):
            raise serializers.ValidationError("Percentage discount cannot exceed 100%")
        return data

    def create(self, validated_data):
        applicable_category_ids = validated_data.pop("applicable_category_ids", [])
        validated_data["created_by"] = self.context["request"].user

        scholarship = super().create(validated_data)

        if applicable_category_ids:
            categories = FeeCategory.objects.filter(id__in=applicable_category_ids)
            scholarship.applicable_categories.set(categories)

        return scholarship

    def update(self, instance, validated_data):
        applicable_category_ids = validated_data.pop("applicable_category_ids", None)

        scholarship = super().update(instance, validated_data)

        if applicable_category_ids is not None:
            categories = FeeCategory.objects.filter(id__in=applicable_category_ids)
            scholarship.applicable_categories.set(categories)

        return scholarship


class StudentScholarshipSerializer(serializers.ModelSerializer):
    """Serializer for student scholarship assignments."""

    student_name = serializers.CharField(
        source="student.user.get_full_name", read_only=True
    )
    student_admission_number = serializers.CharField(
        source="student.admission_number", read_only=True
    )
    scholarship_name = serializers.CharField(source="scholarship.name", read_only=True)
    scholarship_amount = serializers.DecimalField(
        source="scholarship.discount_value",
        max_digits=10,
        decimal_places=2,
        read_only=True,
    )
    approved_by_name = serializers.CharField(
        source="approved_by.get_full_name", read_only=True
    )

    class Meta:
        model = StudentScholarship
        fields = [
            "id",
            "student",
            "scholarship",
            "approved_by",
            "approval_date",
            "start_date",
            "end_date",
            "remarks",
            "status",
            "created_at",
            "updated_at",
            "student_name",
            "student_admission_number",
            "scholarship_name",
            "scholarship_amount",
            "approved_by_name",
        ]
        read_only_fields = ["created_at", "updated_at", "approval_date"]

    def validate(self, data):
        """Validate student scholarship assignment."""
        student = data.get("student")
        scholarship = data.get("scholarship")

        if student and scholarship:
            # Check if student already has this scholarship
            existing = StudentScholarship.objects.filter(
                student=student,
                scholarship=scholarship,
                status__in=["approved", "pending"],
            )

            if self.instance:
                existing = existing.exclude(id=self.instance.id)

            if existing.exists():
                raise serializers.ValidationError(
                    "Student already has this scholarship"
                )

        return data


class InvoiceItemSerializer(serializers.ModelSerializer):
    """Serializer for invoice items."""

    fee_category_name = serializers.SerializerMethodField()

    class Meta:
        model = InvoiceItem
        fields = [
            "id",
            "fee_structure",
            "special_fee",
            "description",
            "amount",
            "discount_amount",
            "net_amount",
            "created_at",
            "fee_category_name",
        ]
        read_only_fields = ["created_at", "net_amount"]

    def get_fee_category_name(self, obj):
        """Get fee category name from fee structure or special fee."""
        if obj.fee_structure:
            return obj.fee_structure.fee_category.name
        elif obj.special_fee:
            return obj.special_fee.fee_category.name
        return None


class PaymentSerializer(serializers.ModelSerializer):
    """Serializer for payments."""

    invoice_number = serializers.CharField(
        source="invoice.invoice_number", read_only=True
    )
    student_name = serializers.CharField(
        source="invoice.student.user.get_full_name", read_only=True
    )
    received_by_name = serializers.CharField(
        source="received_by.get_full_name", read_only=True
    )
    payment_method_display = serializers.CharField(
        source="get_payment_method_display", read_only=True
    )

    class Meta:
        model = Payment
        fields = [
            "id",
            "invoice",
            "payment_date",
            "amount",
            "payment_method",
            "transaction_id",
            "reference_number",
            "received_by",
            "receipt_number",
            "remarks",
            "status",
            "created_at",
            "updated_at",
            "invoice_number",
            "student_name",
            "received_by_name",
            "payment_method_display",
        ]
        read_only_fields = [
            "created_at",
            "updated_at",
            "receipt_number",
            "payment_date",
        ]

    def validate_amount(self, value):
        """Validate payment amount."""
        if value <= 0:
            raise serializers.ValidationError("Payment amount must be positive")
        return value

    def create(self, validated_data):
        validated_data["received_by"] = self.context["request"].user
        return super().create(validated_data)


class InvoiceSerializer(serializers.ModelSerializer):
    """Serializer for invoices."""

    items = InvoiceItemSerializer(many=True, read_only=True)
    payments = PaymentSerializer(many=True, read_only=True)
    student_name = serializers.CharField(
        source="student.user.get_full_name", read_only=True
    )
    student_admission_number = serializers.CharField(
        source="student.admission_number", read_only=True
    )
    student_class = serializers.CharField(
        source="student.current_class", read_only=True
    )
    academic_year_name = serializers.CharField(
        source="academic_year.name", read_only=True
    )
    term_name = serializers.CharField(source="term.name", read_only=True)
    outstanding_amount = serializers.DecimalField(
        max_digits=10, decimal_places=2, read_only=True
    )
    is_overdue = serializers.BooleanField(read_only=True)
    created_by_name = serializers.CharField(
        source="created_by.get_full_name", read_only=True
    )

    class Meta:
        model = Invoice
        fields = [
            "id",
            "student",
            "academic_year",
            "term",
            "invoice_number",
            "issue_date",
            "due_date",
            "total_amount",
            "discount_amount",
            "net_amount",
            "paid_amount",
            "status",
            "remarks",
            "created_by",
            "created_at",
            "updated_at",
            "items",
            "payments",
            "student_name",
            "student_admission_number",
            "student_class",
            "academic_year_name",
            "term_name",
            "outstanding_amount",
            "is_overdue",
            "created_by_name",
        ]
        read_only_fields = [
            "created_at",
            "updated_at",
            "invoice_number",
            "issue_date",
            "paid_amount",
            "created_by",
        ]

    def validate(self, data):
        """Validate invoice data."""
        student = data.get("student")
        academic_year = data.get("academic_year")
        term = data.get("term")

        if student and academic_year and term:
            # Check if invoice already exists for this combination
            existing = Invoice.objects.filter(
                student=student, academic_year=academic_year, term=term
            )

            if self.instance:
                existing = existing.exclude(id=self.instance.id)

            if existing.exists():
                raise serializers.ValidationError(
                    "Invoice already exists for this student in this term"
                )

        return data


class FeeCalculationSerializer(serializers.Serializer):
    """Serializer for fee calculation requests."""

    student_id = serializers.IntegerField()
    academic_year_id = serializers.IntegerField()
    term_id = serializers.IntegerField()

    def validate_student_id(self, value):
        """Validate student exists."""
        try:
            Student.objects.get(id=value)
        except Student.DoesNotExist:
            raise serializers.ValidationError("Student not found")
        return value

    def validate_academic_year_id(self, value):
        """Validate academic year exists."""
        try:
            AcademicYear.objects.get(id=value)
        except AcademicYear.DoesNotExist:
            raise serializers.ValidationError("Academic year not found")
        return value

    def validate_term_id(self, value):
        """Validate term exists."""
        try:
            Term.objects.get(id=value)
        except Term.DoesNotExist:
            raise serializers.ValidationError("Term not found")
        return value


class BulkInvoiceGenerationSerializer(serializers.Serializer):
    """Serializer for bulk invoice generation."""

    student_ids = serializers.ListField(child=serializers.IntegerField())
    academic_year_id = serializers.IntegerField()
    term_id = serializers.IntegerField()

    def validate_student_ids(self, value):
        """Validate all students exist."""
        if not value:
            raise serializers.ValidationError("At least one student ID is required")

        existing_students = Student.objects.filter(id__in=value).values_list(
            "id", flat=True
        )
        missing_students = set(value) - set(existing_students)

        if missing_students:
            raise serializers.ValidationError(
                f"Students not found: {list(missing_students)}"
            )

        return value


class PaymentProcessingSerializer(serializers.Serializer):
    """Serializer for payment processing."""

    invoice_id = serializers.IntegerField()
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=0.01)
    payment_method = serializers.ChoiceField(choices=Payment.PAYMENT_METHOD_CHOICES)
    transaction_id = serializers.CharField(
        max_length=100, required=False, allow_blank=True
    )
    reference_number = serializers.CharField(
        max_length=100, required=False, allow_blank=True
    )
    remarks = serializers.CharField(max_length=500, required=False, allow_blank=True)

    def validate_invoice_id(self, value):
        """Validate invoice exists."""
        try:
            Invoice.objects.get(id=value)
        except Invoice.DoesNotExist:
            raise serializers.ValidationError("Invoice not found")
        return value


class FinancialAnalyticsSerializer(serializers.ModelSerializer):
    """Serializer for financial analytics."""

    academic_year_name = serializers.CharField(
        source="academic_year.name", read_only=True
    )
    term_name = serializers.CharField(source="term.name", read_only=True)
    section_name = serializers.CharField(source="section.name", read_only=True)
    grade_name = serializers.CharField(source="grade.name", read_only=True)
    fee_category_name = serializers.CharField(
        source="fee_category.name", read_only=True
    )

    class Meta:
        model = FinancialAnalytics
        fields = [
            "id",
            "academic_year",
            "term",
            "section",
            "grade",
            "fee_category",
            "total_expected_revenue",
            "total_collected_revenue",
            "collection_rate",
            "total_outstanding",
            "number_of_defaulters",
            "calculated_at",
            "academic_year_name",
            "term_name",
            "section_name",
            "grade_name",
            "fee_category_name",
        ]
        read_only_fields = ["calculated_at"]


class FeeWaiverSerializer(serializers.ModelSerializer):
    """Serializer for fee waivers."""

    student_name = serializers.CharField(
        source="student.user.get_full_name", read_only=True
    )
    invoice_number = serializers.CharField(
        source="invoice.invoice_number", read_only=True
    )
    requested_by_name = serializers.CharField(
        source="requested_by.get_full_name", read_only=True
    )
    approved_by_name = serializers.CharField(
        source="approved_by.get_full_name", read_only=True
    )

    class Meta:
        model = FeeWaiver
        fields = [
            "id",
            "student",
            "invoice",
            "waiver_type",
            "amount",
            "reason",
            "requested_by",
            "approved_by",
            "status",
            "remarks",
            "created_at",
            "updated_at",
            "student_name",
            "invoice_number",
            "requested_by_name",
            "approved_by_name",
        ]
        read_only_fields = ["created_at", "updated_at", "requested_by"]

    def create(self, validated_data):
        validated_data["requested_by"] = self.context["request"].user
        return super().create(validated_data)


class FinancialSummarySerializer(serializers.ModelSerializer):
    """Serializer for financial summaries."""

    academic_year_name = serializers.CharField(
        source="academic_year.name", read_only=True
    )
    term_name = serializers.CharField(source="term.name", read_only=True)
    collection_rate = serializers.SerializerMethodField()

    class Meta:
        model = FinancialSummary
        fields = [
            "id",
            "academic_year",
            "term",
            "month",
            "year",
            "total_fees_due",
            "total_fees_collected",
            "total_outstanding",
            "total_scholarships_given",
            "total_expenses",
            "net_income",
            "generated_at",
            "academic_year_name",
            "term_name",
            "collection_rate",
        ]
        read_only_fields = ["generated_at"]

    def get_collection_rate(self, obj):
        """Calculate collection rate percentage."""
        if obj.total_fees_due > 0:
            return round((obj.total_fees_collected / obj.total_fees_due) * 100, 2)
        return 0


# Analytics-specific serializers
class CollectionMetricsSerializer(serializers.Serializer):
    """Serializer for collection metrics response."""

    period = serializers.DictField()
    collection_summary = serializers.DictField()
    status_breakdown = serializers.ListField()
    overdue_analysis = serializers.DictField()


class PaymentTrendsSerializer(serializers.Serializer):
    """Serializer for payment trends response."""

    period = serializers.CharField()
    daily_trends = serializers.ListField()
    payment_methods = serializers.ListField()
    peak_times = serializers.ListField()
    summary = serializers.DictField()


class DefaulterAnalysisSerializer(serializers.Serializer):
    """Serializer for defaulter analysis response."""

    analysis_period = serializers.CharField()
    total_defaulters = serializers.IntegerField()
    total_overdue_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    risk_by_level = serializers.ListField()
    amount_distribution = serializers.DictField()
    chronic_defaulters = serializers.ListField()
    recommendations = serializers.ListField()


class ScholarshipImpactSerializer(serializers.Serializer):
    """Serializer for scholarship impact analysis."""

    academic_year = serializers.CharField()
    term = serializers.CharField()
    total_scholarships = serializers.IntegerField()
    total_beneficiaries = serializers.IntegerField()
    total_discount_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    discount_by_type = serializers.DictField()
    criteria_distribution = serializers.ListField()
    average_discount_per_student = serializers.DecimalField(
        max_digits=10, decimal_places=2
    )
