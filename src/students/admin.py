# students/admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from .models import Student, Parent, StudentParentRelation


class StudentParentRelationInline(admin.TabularInline):
    model = StudentParentRelation
    extra = 1
    autocomplete_fields = ["parent"]


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = (
        "admission_number",
        "get_full_name",
        "get_email",
        "current_class",
        "status",
        "blood_group",
    )
    list_filter = ("status", "blood_group", "current_class", "admission_date")
    search_fields = (
        "admission_number",
        "user__first_name",
        "user__last_name",
        "user__email",
        "roll_number",
    )
    autocomplete_fields = ["user", "current_class"]
    readonly_fields = ("created_at", "updated_at")
    inlines = [StudentParentRelationInline]
    date_hierarchy = "admission_date"

    fieldsets = (
        (
            "Basic Information",
            {
                "fields": (
                    "user",
                    "admission_number",
                    "admission_date",
                    "current_class",
                    "roll_number",
                    "status",
                    "registration_number",
                )
            },
        ),
        (
            "Personal Information",
            {
                "fields": (
                    "blood_group",
                    "medical_conditions",
                    "nationality",
                    "religion",
                    "photo",
                )
            },
        ),
        (
            "Contact Information",
            {
                "fields": (
                    "address",
                    "city",
                    "state",
                    "postal_code",
                    "country",
                    "emergency_contact_name",
                    "emergency_contact_number",
                )
            },
        ),
        (
            "Other Information",
            {"fields": ("previous_school", "created_at", "updated_at")},
        ),
    )

    def get_full_name(self, obj):
        return obj.get_full_name()

    get_full_name.short_description = "Name"
    get_full_name.admin_order_field = "user__first_name"

    def get_email(self, obj):
        return obj.user.email

    get_email.short_description = "Email"
    get_email.admin_order_field = "user__email"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("user", "current_class")


class StudentParentRelationInline(admin.TabularInline):
    model = StudentParentRelation
    extra = 1
    autocomplete_fields = ["student"]


@admin.register(Parent)
class ParentAdmin(admin.ModelAdmin):
    list_display = (
        "get_full_name",
        "get_email",
        "relation_with_student",
        "occupation",
        "emergency_contact",
        "student_count",
    )
    list_filter = ("relation_with_student", "emergency_contact")
    search_fields = ("user__first_name", "user__last_name", "user__email", "occupation")
    autocomplete_fields = ["user"]
    readonly_fields = ("created_at", "updated_at")
    inlines = [StudentParentRelationInline]

    fieldsets = (
        ("Basic Information", {"fields": ("user", "relation_with_student", "photo")}),
        (
            "Professional Information",
            {
                "fields": (
                    "occupation",
                    "annual_income",
                    "education",
                    "workplace",
                    "work_address",
                    "work_phone",
                )
            },
        ),
        ("Contact Preferences", {"fields": ("emergency_contact",)}),
        ("Other Information", {"fields": ("created_at", "updated_at")}),
    )

    def get_full_name(self, obj):
        return obj.get_full_name()

    get_full_name.short_description = "Name"
    get_full_name.admin_order_field = "user__first_name"

    def get_email(self, obj):
        return obj.user.email

    get_email.short_description = "Email"
    get_email.admin_order_field = "user__email"

    def student_count(self, obj):
        count = obj.parent_student_relations.count()
        if count > 0:
            url = (
                reverse("admin:students_student_changelist")
                + f'?id__in={",".join([str(s.student.id) for s in obj.parent_student_relations.all()])}'
            )
            return format_html('<a href="{}">{} students</a>', url, count)
        return "0 students"

    student_count.short_description = "Students"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("user")


@admin.register(StudentParentRelation)
class StudentParentRelationAdmin(admin.ModelAdmin):
    list_display = (
        "student",
        "parent",
        "is_primary_contact",
        "can_pickup",
        "emergency_contact_priority",
    )
    list_filter = ("is_primary_contact", "can_pickup", "financial_responsibility")
    search_fields = (
        "student__user__first_name",
        "student__user__last_name",
        "student__admission_number",
        "parent__user__first_name",
        "parent__user__last_name",
    )
    autocomplete_fields = ["student", "parent"]
    list_editable = ("is_primary_contact", "can_pickup", "emergency_contact_priority")
