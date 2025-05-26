from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from django.db.models import Sum, Count
from decimal import Decimal

from .models import (
    FeeCategory,
    FeeStructure,
    SpecialFee,
    Scholarship,
    StudentScholarship,
    Invoice,
    InvoiceItem,
    Payment,
    FinancialSummary,
    FinancialAnalytics,
    FeeWaiver,
)


@admin.register(FeeCategory)
class FeeCategoryAdmin(admin.ModelAdmin):
    """Admin for fee categories."""

    list_display = [
        "name",
        "is_mandatory",
        "is_recurring",
        "frequency",
        "created_at",
        "fee_structures_count",
    ]
    list_filter = ["is_mandatory", "is_recurring", "frequency"]
    search_fields = ["name", "description"]
    ordering = ["name"]
    readonly_fields = ["created_at", "updated_at"]

    fieldsets = (
        (None, {"fields": ("name", "description")}),
        ("Settings", {"fields": ("is_mandatory", "is_recurring", "frequency")}),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    def fee_structures_count(self, obj):
        """Count of fee structures using this category."""
        return obj.feestructure_set.count()

    fee_structures_count.short_description = "Fee Structures"


@admin.register(FeeStructure)
class FeeStructureAdmin(admin.ModelAdmin):
    """Admin for fee structures."""

    list_display = [
        "fee_category",
        "applicable_level",
        "amount",
        "due_date",
        "academic_year",
        "term",
        "is_active",
        "created_by",
    ]
    list_filter = [
        "academic_year",
        "term",
        "fee_category",
        "is_active",
        "section",
        "grade",
    ]
    search_fields = ["fee_category__name"]
    ordering = ["-created_at"]
    readonly_fields = ["created_at", "created_by"]

    fieldsets = (
        ("Basic Information", {"fields": ("fee_category", "amount", "due_date")}),
        ("Academic Context", {"fields": ("academic_year", "term", "section", "grade")}),
        ("Payment Terms", {"fields": ("late_fee_percentage", "grace_period_days")}),
        ("Status", {"fields": ("is_active",)}),
        (
            "Metadata",
            {"fields": ("created_at", "created_by"), "classes": ("collapse",)},
        ),
    )

    def applicable_level(self, obj):
        """Show the applicable level (grade or section)."""
        return str(obj.applicable_level)

    applicable_level.short_description = "Applicable Level"

    def save_model(self, request, obj, form, change):
        """Set created_by when creating new fee structure."""
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(SpecialFee)
class SpecialFeeAdmin(admin.ModelAdmin):
    """Admin for special fees."""

    list_display = [
        "name",
        "fee_type",
        "target",
        "amount",
        "due_date",
        "term",
        "is_active",
        "created_by",
    ]
    list_filter = ["fee_type", "fee_category", "term", "is_active"]
    search_fields = ["name", "description", "reason"]
    ordering = ["-created_at"]
    readonly_fields = ["created_at", "updated_at", "created_by"]

    fieldsets = (
        ("Basic Information", {"fields": ("name", "description", "fee_category")}),
        ("Fee Details", {"fields": ("amount", "fee_type", "due_date", "reason")}),
        (
            "Target Assignment",
            {
                "fields": ("class_obj", "student"),
                "description": "Select either class or student based on fee type",
            },
        ),
        ("Academic Context", {"fields": ("term",)}),
        ("Status", {"fields": ("is_active",)}),
        (
            "Metadata",
            {
                "fields": ("created_at", "updated_at", "created_by"),
                "classes": ("collapse",),
            },
        ),
    )

    def target(self, obj):
        """Show the target (class or student)."""
        return obj.class_obj or obj.student

    target.short_description = "Target"

    def save_model(self, request, obj, form, change):
        """Set created_by when creating new special fee."""
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(Scholarship)
class ScholarshipAdmin(admin.ModelAdmin):
    """Admin for scholarships."""

    list_display = [
        "name",
        "criteria",
        "discount_display",
        "current_recipients",
        "max_recipients",
        "academic_year",
        "is_active",
    ]
    list_filter = ["criteria", "discount_type", "academic_year", "is_active"]
    search_fields = ["name", "description"]
    ordering = ["-created_at"]
    readonly_fields = ["created_at", "created_by", "current_recipients"]
    filter_horizontal = ["applicable_categories"]

    fieldsets = (
        ("Basic Information", {"fields": ("name", "description", "criteria")}),
        ("Discount Details", {"fields": ("discount_type", "discount_value")}),
        (
            "Scope",
            {"fields": ("academic_year", "applicable_terms", "applicable_categories")},
        ),
        ("Limits", {"fields": ("max_recipients", "current_recipients")}),
        ("Status", {"fields": ("is_active",)}),
        (
            "Metadata",
            {"fields": ("created_at", "created_by"), "classes": ("collapse",)},
        ),
    )

    def discount_display(self, obj):
        """Display discount value with type."""
        if obj.discount_type == "percentage":
            return f"{obj.discount_value}%"
        else:
            return f"${obj.discount_value}"

    discount_display.short_description = "Discount"

    def save_model(self, request, obj, form, change):
        """Set created_by when creating new scholarship."""
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(StudentScholarship)
class StudentScholarshipAdmin(admin.ModelAdmin):
    """Admin for student scholarship assignments."""

    list_display = [
        "student",
        "scholarship",
        "status",
        "start_date",
        "end_date",
        "approved_by",
        "approval_date",
    ]
    list_filter = ["status", "scholarship", "scholarship__academic_year"]
    search_fields = [
        "student__user__first_name",
        "student__user__last_name",
        "scholarship__name",
    ]
    ordering = ["-approval_date"]
    readonly_fields = ["approval_date", "created_at", "updated_at"]

    fieldsets = (
        ("Assignment", {"fields": ("student", "scholarship")}),
        ("Approval", {"fields": ("approved_by", "approval_date", "status")}),
        ("Duration", {"fields": ("start_date", "end_date")}),
        ("Notes", {"fields": ("remarks",)}),
        (
            "Metadata",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )


class InvoiceItemInline(admin.TabularInline):
    """Inline admin for invoice items."""

    model = InvoiceItem
    extra = 0
    readonly_fields = ["net_amount", "created_at"]
    fields = [
        "description",
        "amount",
        "discount_amount",
        "net_amount",
        "fee_structure",
        "special_fee",
    ]


class PaymentInline(admin.TabularInline):
    """Inline admin for payments."""

    model = Payment
    extra = 0
    readonly_fields = ["receipt_number", "payment_date", "created_at"]
    fields = [
        "payment_date",
        "amount",
        "payment_method",
        "receipt_number",
        "transaction_id",
        "status",
        "received_by",
    ]


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    """Admin for invoices."""

    list_display = [
        "invoice_number",
        "student",
        "academic_year",
        "term",
        "net_amount",
        "paid_amount",
        "outstanding_display",
        "status",
        "due_date",
        "is_overdue",
    ]
    list_filter = ["status", "academic_year", "term", "issue_date", "due_date"]
    search_fields = [
        "invoice_number",
        "student__user__first_name",
        "student__user__last_name",
        "student__admission_number",
    ]
    ordering = ["-created_at"]
    readonly_fields = [
        "invoice_number",
        "issue_date",
        "outstanding_amount",
        "is_overdue",
        "created_at",
        "updated_at",
        "created_by",
    ]
    inlines = [InvoiceItemInline, PaymentInline]

    fieldsets = (
        (
            "Invoice Details",
            {"fields": ("invoice_number", "student", "issue_date", "due_date")},
        ),
        ("Academic Context", {"fields": ("academic_year", "term")}),
        (
            "Financial Summary",
            {
                "fields": (
                    "total_amount",
                    "discount_amount",
                    "net_amount",
                    "paid_amount",
                    "outstanding_amount",
                )
            },
        ),
        ("Status", {"fields": ("status", "is_overdue")}),
        ("Notes", {"fields": ("remarks",)}),
        (
            "Metadata",
            {
                "fields": ("created_at", "updated_at", "created_by"),
                "classes": ("collapse",),
            },
        ),
    )

    def outstanding_display(self, obj):
        """Display outstanding amount with color coding."""
        outstanding = obj.outstanding_amount
        if outstanding > 0:
            return format_html(
                '<span style="color: red; font-weight: bold;">${}</span>', outstanding
            )
        return format_html('<span style="color: green;">$0.00</span>')

    outstanding_display.short_description = "Outstanding"

    def save_model(self, request, obj, form, change):
        """Set created_by when creating new invoice."""
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    """Admin for payments."""

    list_display = [
        "receipt_number",
        "invoice",
        "student_name",
        "amount",
        "payment_method",
        "payment_date",
        "status",
        "received_by",
    ]
    list_filter = ["payment_method", "status", "payment_date"]
    search_fields = [
        "receipt_number",
        "transaction_id",
        "invoice__invoice_number",
        "invoice__student__user__first_name",
        "invoice__student__user__last_name",
    ]
    ordering = ["-payment_date"]
    readonly_fields = ["receipt_number", "payment_date", "created_at", "updated_at"]

    fieldsets = (
        (
            "Payment Details",
            {"fields": ("invoice", "amount", "payment_method", "payment_date")},
        ),
        (
            "Transaction Info",
            {"fields": ("transaction_id", "reference_number", "receipt_number")},
        ),
        ("Processing", {"fields": ("received_by", "status")}),
        ("Notes", {"fields": ("remarks",)}),
        (
            "Metadata",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    def student_name(self, obj):
        """Get student name from invoice."""
        return obj.invoice.student.user.get_full_name()

    student_name.short_description = "Student"


@admin.register(FeeWaiver)
class FeeWaiverAdmin(admin.ModelAdmin):
    """Admin for fee waivers."""

    list_display = [
        "student",
        "invoice",
        "waiver_type",
        "amount",
        "status",
        "requested_by",
        "approved_by",
        "created_at",
    ]
    list_filter = ["waiver_type", "status"]
    search_fields = [
        "student__user__first_name",
        "student__user__last_name",
        "invoice__invoice_number",
        "reason",
    ]
    ordering = ["-created_at"]
    readonly_fields = ["created_at", "updated_at"]

    fieldsets = (
        ("Waiver Details", {"fields": ("student", "invoice", "waiver_type", "amount")}),
        ("Justification", {"fields": ("reason",)}),
        ("Approval", {"fields": ("status", "requested_by", "approved_by")}),
        ("Notes", {"fields": ("remarks",)}),
        (
            "Metadata",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )


@admin.register(FinancialSummary)
class FinancialSummaryAdmin(admin.ModelAdmin):
    """Admin for financial summaries."""

    list_display = [
        "period_display",
        "total_fees_due",
        "total_fees_collected",
        "collection_rate_display",
        "total_outstanding",
        "generated_at",
    ]
    list_filter = ["academic_year", "term", "year", "month"]
    ordering = ["-year", "-month"]
    readonly_fields = ["generated_at"]

    fieldsets = (
        ("Period", {"fields": ("academic_year", "term", "month", "year")}),
        (
            "Revenue",
            {"fields": ("total_fees_due", "total_fees_collected", "total_outstanding")},
        ),
        (
            "Expenses & Scholarships",
            {"fields": ("total_scholarships_given", "total_expenses")},
        ),
        ("Net Result", {"fields": ("net_income",)}),
        ("Metadata", {"fields": ("generated_at",), "classes": ("collapse",)}),
    )

    def period_display(self, obj):
        """Display the period in a readable format."""
        if obj.term:
            return f"{obj.term} ({obj.academic_year})"
        return f"{obj.month}/{obj.year}"

    period_display.short_description = "Period"

    def collection_rate_display(self, obj):
        """Display collection rate as percentage."""
        if obj.total_fees_due > 0:
            rate = (obj.total_fees_collected / obj.total_fees_due) * 100
            return f"{rate:.1f}%"
        return "0%"

    collection_rate_display.short_description = "Collection Rate"


@admin.register(FinancialAnalytics)
class FinancialAnalyticsAdmin(admin.ModelAdmin):
    """Admin for financial analytics."""

    list_display = [
        "level_display",
        "academic_year",
        "term",
        "collection_rate",
        "total_expected_revenue",
        "total_collected_revenue",
        "number_of_defaulters",
        "calculated_at",
    ]
    list_filter = ["academic_year", "term", "section", "grade", "fee_category"]
    ordering = ["-calculated_at"]
    readonly_fields = ["calculated_at"]

    fieldsets = (
        (
            "Scope",
            {"fields": ("academic_year", "term", "section", "grade", "fee_category")},
        ),
        (
            "Financial Metrics",
            {
                "fields": (
                    "total_expected_revenue",
                    "total_collected_revenue",
                    "collection_rate",
                    "total_outstanding",
                )
            },
        ),
        ("Risk Metrics", {"fields": ("number_of_defaulters",)}),
        ("Metadata", {"fields": ("calculated_at",), "classes": ("collapse",)}),
    )

    def level_display(self, obj):
        """Display the level being analyzed."""
        if obj.fee_category:
            return f"{obj.fee_category.name}"
        elif obj.grade:
            return f"{obj.grade}"
        elif obj.section:
            return f"{obj.section}"
        return "Overall"

    level_display.short_description = "Level"


# Admin site customizations
admin.site.site_header = "School Finance Management"
admin.site.site_title = "Finance Admin"
admin.site.index_title = "Financial Administration"
