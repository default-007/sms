# students/admin.py
from django.conf import settings
from django.contrib import admin
from django.db.models import Count, Q
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from import_export import fields, resources
from import_export.admin import ImportExportModelAdmin

from .models import Parent, Student, StudentParentRelation


class StudentResource(resources.ModelResource):
    """Resource for importing/exporting students"""

    current_class_name = fields.Field(column_name="class_name")

    class Meta:
        model = Student
        fields = (
            "admission_number",
            "first_name",
            "last_name",
            "email",
            "phone_number",
            "current_class_name",
            "roll_number",
            "blood_group",
            "status",
            "admission_date",
            "date_of_birth",
            "gender",
            "emergency_contact_name",
            "emergency_contact_number",
        )

    def dehydrate_current_class_name(self, student):
        return str(student.current_class) if student.current_class else ""


class StudentParentRelationInline(admin.TabularInline):
    model = StudentParentRelation
    extra = 0
    min_num = 1
    autocomplete_fields = ["parent"]
    fields = (
        "parent",
        "is_primary_contact",
        "can_pickup",
        "emergency_contact_priority",
        "financial_responsibility",
    )
    readonly_fields = ("created_at", "updated_at")


@admin.register(Student)
class StudentAdmin(ImportExportModelAdmin):
    resource_class = StudentResource
    list_display = (
        "admission_number",
        "get_full_name",
        "get_email",
        "get_phone",
        "current_class",
        "status_badge",
        "blood_group",
        "get_age",
        "get_parent_count",
        "is_active",
    )
    list_filter = (
        "status",
        "is_active",
        "blood_group",
        "gender",
        "current_class__grade",
        "admission_date",
        "date_joined",
    )
    search_fields = (
        "admission_number",
        "first_name",
        "last_name",
        "email",
        "phone_number",
        "roll_number",
        "registration_number",
        "emergency_contact_name",
        "emergency_contact_number",
    )
    autocomplete_fields = ["current_class", "created_by"]
    readonly_fields = (
        "id",
        "registration_number",
        "date_joined",
        "last_updated",
        "get_age",
        "get_full_name",
        "get_parents_display",
        "get_siblings_count",
        "created_by",
    )
    fieldsets = (
        (
            "Personal Information",
            {
                "fields": (
                    ("first_name", "last_name"),
                    ("email", "phone_number"),
                    ("date_of_birth", "gender"),
                    "address",
                    "profile_picture",
                )
            },
        ),
        (
            "Academic Information",
            {
                "fields": (
                    ("admission_number", "registration_number"),
                    ("admission_date", "current_class"),
                    "roll_number",
                    "previous_school",
                    "transfer_certificate_number",
                )
            },
        ),
        (
            "Health & Emergency",
            {
                "fields": (
                    "blood_group",
                    "medical_conditions",
                    ("emergency_contact_name", "emergency_contact_number"),
                    "emergency_contact_relationship",
                )
            },
        ),
        (
            "Status & Metadata",
            {
                "fields": (
                    ("status", "is_active"),
                    ("date_joined", "last_updated"),
                    "created_by",
                )
            },
        ),
        (
            "Computed Fields",
            {
                "fields": (
                    "get_full_name",
                    "get_age",
                    "get_parents_display",
                    "get_siblings_count",
                ),
                "classes": ("collapse",),
            },
        ),
    )
    inlines = [StudentParentRelationInline]

    # List settings
    list_per_page = 50
    list_max_show_all = 200
    preserve_filters = True

    # Actions
    actions = [
        "activate_students",
        "deactivate_students",
        "mark_graduated",
        "export_selected_students",
    ]

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related(
                "current_class__grade", "current_class__section", "created_by"
            )
            .prefetch_related("student_parent_relations__parent__user")
        )

    def get_full_name(self, obj):
        """Get student's full name"""
        return obj.full_name

    get_full_name.short_description = "Full Name"
    get_full_name.admin_order_field = "first_name"

    def get_email(self, obj):
        """Get student's email with link"""
        if obj.email:
            return format_html('<a href="mailto:{}">{}</a>', obj.email, obj.email)
        return "-"

    get_email.short_description = "Email"
    get_email.admin_order_field = "email"

    def get_phone(self, obj):
        """Get student's phone number"""
        return obj.phone_number or "-"

    get_phone.short_description = "Phone"
    get_phone.admin_order_field = "phone_number"

    def status_badge(self, obj):
        """Display status as colored badge"""
        colors = {
            "Active": "success",
            "Inactive": "secondary",
            "Graduated": "primary",
            "Suspended": "warning",
            "Expelled": "danger",
            "Withdrawn": "info",
        }
        color = colors.get(obj.status, "secondary")
        return format_html('<span class="badge badge-{}">{}</span>', color, obj.status)

    status_badge.short_description = "Status"
    status_badge.admin_order_field = "status"

    def get_age(self, obj):
        """Get student's age"""
        return f"{obj.age} years" if obj.age else "-"

    get_age.short_description = "Age"

    def get_parent_count(self, obj):
        """Get number of parents"""
        count = obj.student_parent_relations.count()
        if count == 0:
            return format_html('<span class="text-danger">No parents</span>')
        return f"{count} parent{'s' if count != 1 else ''}"

    get_parent_count.short_description = "Parents"

    def get_parents_display(self, obj):
        """Display parents with links"""
        parents = obj.get_parents()
        if not parents:
            return "No parents assigned"

        parent_links = []
        for parent in parents:
            url = reverse("admin:students_parent_change", args=[parent.pk])
            parent_links.append(
                format_html('<a href="{}">{}</a>', url, parent.full_name)
            )

        return format_html(", ".join(parent_links))

    get_parents_display.short_description = "Parents"

    def get_siblings_count(self, obj):
        """Get number of siblings"""
        siblings = obj.get_siblings()
        return f"{len(siblings)} sibling{'s' if len(siblings) != 1 else ''}"

    get_siblings_count.short_description = "Siblings"

    # Custom actions
    def activate_students(self, request, queryset):
        """Activate selected students"""
        count = queryset.update(is_active=True, status="Active")
        self.message_user(request, f"Activated {count} students.")

    activate_students.short_description = "Activate selected students"

    def deactivate_students(self, request, queryset):
        """Deactivate selected students"""
        count = queryset.update(is_active=False, status="Inactive")
        self.message_user(request, f"Deactivated {count} students.")

    deactivate_students.short_description = "Deactivate selected students"

    def mark_graduated(self, request, queryset):
        """Mark selected students as graduated"""
        count = queryset.update(status="Graduated")
        self.message_user(request, f"Marked {count} students as graduated.")

    mark_graduated.short_description = "Mark as graduated"

    def export_selected_students(self, request, queryset):
        """Export selected students"""
        # This would integrate with the export functionality
        self.message_user(request, f"Exporting {queryset.count()} students...")

    export_selected_students.short_description = "Export selected students"


class ParentResource(resources.ModelResource):
    """Resource for importing/exporting parents"""

    user_first_name = fields.Field(column_name="first_name")
    user_last_name = fields.Field(column_name="last_name")
    user_email = fields.Field(column_name="email")
    user_phone_number = fields.Field(column_name="phone_number")

    class Meta:
        model = Parent
        fields = (
            "user_first_name",
            "user_last_name",
            "user_email",
            "user_phone_number",
            "relation_with_student",
            "occupation",
            "annual_income",
            "education",
            "emergency_contact",
        )

    def dehydrate_user_first_name(self, parent):
        return parent.user.first_name

    def dehydrate_user_last_name(self, parent):
        return parent.user.last_name

    def dehydrate_user_email(self, parent):
        return parent.user.email

    def dehydrate_user_phone_number(self, parent):
        return parent.user.phone_number


@admin.register(Parent)
class ParentAdmin(ImportExportModelAdmin):
    resource_class = ParentResource
    list_display = (
        "get_full_name",
        "get_email",
        "get_phone",
        "relation_with_student",
        "occupation",
        "emergency_contact",
        "get_children_count",
        "get_user_status",
    )
    list_filter = (
        "relation_with_student",
        "emergency_contact",
        "user__is_active",
        "created_at",
    )
    search_fields = (
        "user__first_name",
        "user__last_name",
        "user__email",
        "user__phone_number",
        "occupation",
        "company_name",
    )
    autocomplete_fields = ["user", "created_by"]
    readonly_fields = (
        "id",
        "created_at",
        "updated_at",
        "get_full_name",
        "get_children_display",
        "created_by",
    )
    fieldsets = (
        (
            "Basic Information",
            {
                "fields": (
                    "user",
                    "relation_with_student",
                    "emergency_contact",
                    "photo",
                )
            },
        ),
        (
            "Professional Information",
            {
                "fields": (
                    "occupation",
                    "company_name",
                    "office_address",
                    ("office_phone", "annual_income"),
                    "education",
                )
            },
        ),
        (
            "Metadata",
            {
                "fields": (
                    ("created_at", "updated_at"),
                    "created_by",
                )
            },
        ),
        (
            "Related Information",
            {
                "fields": (
                    "get_full_name",
                    "get_children_display",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("user", "created_by")
            .prefetch_related("parent_student_relations__student")
        )

    def get_full_name(self, obj):
        """Get parent's full name"""
        return obj.full_name

    get_full_name.short_description = "Full Name"
    get_full_name.admin_order_field = "user__first_name"

    def get_email(self, obj):
        """Get parent's email with link"""
        if obj.user.email:
            return format_html(
                '<a href="mailto:{}">{}</a>', obj.user.email, obj.user.email
            )
        return "-"

    get_email.short_description = "Email"
    get_email.admin_order_field = "user__email"

    def get_phone(self, obj):
        """Get parent's phone number"""
        return obj.user.phone_number or "-"

    get_phone.short_description = "Phone"
    get_phone.admin_order_field = "user__phone_number"

    def get_user_status(self, obj):
        """Get user account status"""
        if obj.user.is_active:
            return format_html('<span class="badge badge-success">Active</span>')
        return format_html('<span class="badge badge-danger">Inactive</span>')

    get_user_status.short_description = "Account Status"
    get_user_status.admin_order_field = "user__is_active"

    def get_children_count(self, obj):
        """Get number of children"""
        count = obj.parent_student_relations.count()
        if count == 0:
            return format_html('<span class="text-danger">No children</span>')
        return f"{count} child{'ren' if count != 1 else ''}"

    get_children_count.short_description = "Children"

    def get_children_display(self, obj):
        """Display children with links"""
        students = obj.get_students()
        if not students:
            return "No children assigned"

        student_links = []
        for student in students:
            url = reverse("admin:students_student_change", args=[student.pk])
            student_links.append(
                format_html('<a href="{}">{}</a>', url, student.full_name)
            )

        return format_html(", ".join(student_links))

    get_children_display.short_description = "Children"


@admin.register(StudentParentRelation)
class StudentParentRelationAdmin(admin.ModelAdmin):
    list_display = (
        "get_student_name",
        "get_parent_name",
        "get_relation_type",
        "is_primary_contact",
        "emergency_contact_priority",
        "financial_responsibility",
    )
    list_filter = (
        "is_primary_contact",
        "financial_responsibility",
        "emergency_contact_priority",
        "parent__relation_with_student",
        "created_at",
    )
    search_fields = (
        "student__first_name",
        "student__last_name",
        "student__admission_number",
        "parent__user__first_name",
        "parent__user__last_name",
    )
    autocomplete_fields = ["student", "parent"]
    readonly_fields = ("created_at", "updated_at")
    list_per_page = 50

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("student", "parent__user")

    def get_student_name(self, obj):
        """Get student name with link"""
        url = reverse("admin:students_student_change", args=[obj.student.pk])
        return format_html('<a href="{}">{}</a>', url, obj.student.full_name)

    get_student_name.short_description = "Student"
    get_student_name.admin_order_field = "student__first_name"

    def get_parent_name(self, obj):
        """Get parent name with link"""
        url = reverse("admin:students_parent_change", args=[obj.parent.pk])
        return format_html('<a href="{}">{}</a>', url, obj.parent.full_name)

    get_parent_name.short_description = "Parent"
    get_parent_name.admin_order_field = "parent__user__first_name"

    def get_relation_type(self, obj):
        """Get relation type"""
        return obj.parent.relation_with_student

    get_relation_type.short_description = "Relation"
    get_relation_type.admin_order_field = "parent__relation_with_student"
