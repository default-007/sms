from django.contrib import admin
from .models import (
    FeeCategory,
    FeeStructure,
    Scholarship,
    StudentScholarship,
    Invoice,
    InvoiceItem,
    Payment,
    Expense,
)


class FeeCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "is_recurring", "frequency")
    list_filter = ("is_recurring",)
    search_fields = ("name", "description")


class FeeStructureAdmin(admin.ModelAdmin):
    list_display = ("fee_category", "grade", "academic_year", "amount")
    list_filter = ("academic_year", "grade", "fee_category")
    search_fields = ("fee_category__name", "grade__name")


class ScholarshipAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "discount_type",
        "discount_value",
        "criteria",
        "academic_year",
    )
    list_filter = ("discount_type", "criteria", "academic_year")
    search_fields = ("name", "description")


class StudentScholarshipAdmin(admin.ModelAdmin):
    list_display = ("student", "scholarship", "status", "start_date", "end_date")
    list_filter = ("status", "scholarship", "start_date")
    search_fields = (
        "student__user__first_name",
        "student__user__last_name",
        "scholarship__name",
    )
    raw_id_fields = ("student", "scholarship", "approved_by")


class InvoiceItemInline(admin.TabularInline):
    model = InvoiceItem
    extra = 1


class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0
    readonly_fields = ("receipt_number",)


class InvoiceAdmin(admin.ModelAdmin):
    list_display = (
        "invoice_number",
        "student",
        "issue_date",
        "due_date",
        "total_amount",
        "status",
    )
    list_filter = ("status", "issue_date", "due_date", "academic_year")
    search_fields = (
        "invoice_number",
        "student__user__first_name",
        "student__user__last_name",
        "student__admission_number",
    )
    raw_id_fields = ("student", "created_by")
    readonly_fields = ("invoice_number",)
    inlines = [InvoiceItemInline, PaymentInline]


class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        "receipt_number",
        "invoice",
        "payment_date",
        "amount",
        "payment_method",
        "status",
    )
    list_filter = ("status", "payment_method", "payment_date")
    search_fields = (
        "receipt_number",
        "invoice__invoice_number",
        "invoice__student__user__first_name",
        "invoice__student__user__last_name",
    )
    raw_id_fields = ("invoice", "received_by")
    readonly_fields = ("receipt_number",)


class ExpenseAdmin(admin.ModelAdmin):
    list_display = ("expense_category", "amount", "expense_date", "paid_to")
    list_filter = ("expense_category", "expense_date")
    search_fields = ("description", "paid_to")
    raw_id_fields = ("approved_by",)


admin.site.register(FeeCategory, FeeCategoryAdmin)
admin.site.register(FeeStructure, FeeStructureAdmin)
admin.site.register(Scholarship, ScholarshipAdmin)
admin.site.register(StudentScholarship, StudentScholarshipAdmin)
admin.site.register(Invoice, InvoiceAdmin)
admin.site.register(Payment, PaymentAdmin)
admin.site.register(Expense, ExpenseAdmin)
