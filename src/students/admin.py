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
    user__first_name = fields.Field(column_name="first_name")
    user__last_name = fields.Field(column_name="last_name")
    user__email = fields.Field(column_name="email")
    user__phone_number = fields.Field(column_name="phone_number")
    current_class__name = fields.Field(column_name="class_name")

    class Meta:
        model = Student
        fields = (
            "admission_number",
            "user__first_name",
            "user__last_name",
            "user__email",
            "user__phone_number",
            "current_class__name",
            "roll_number",
            "blood_group",
            "status",
            "admission_date",
        )


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
        "get_username",  # Show username (admission number)
        "get_email",
        "current_class",
        "status_badge",
        "blood_group",
        "get_age",
        "get_parent_count",
    )
    list_filter = (
        "status",
        "blood_group",
        "current_class__grade",
        "admission_date",
        "created_at",
    )
    search_fields = (
        "admission_number",
        "user__username",  # Search by username (admission number)
        "user__first_name",
        "user__last_name",
        "user__email",
        "roll_number",
        "registration_number",
    )
    autocomplete_fields = ["user", "current_class", "created_by"]
    readonly_fields = (
        "id",
        "registration_number",
        "created_at",
        "updated_at",
        "get_username_display",
        "get_email_display",
    )
    inlines = [StudentParentRelationInline]
    date_hierarchy = "admission_date"
    list_per_page = 50
    list_select_related = ("user", "current_class__grade", "current_class__section")
    show_full_result_count = False

    fieldsets = (
        (
            "Basic Information",
            {
                "fields": (
                    "id",
                    "user",
                    "admission_number",
                    "registration_number",
                    "admission_date",
                    "current_class",
                    "roll_number",
                    "status",
                )
            },
        ),
        (
            "User Account Information",
            {
                "fields": (("get_username_display", "get_email_display"),),
                "description": "Student logs in using admission number as username. Email is optional.",
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
            {"fields": ("previous_school", "created_by", "created_at", "updated_at")},
        ),
    )

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("user", "current_class__grade", "current_class__section")
            .prefetch_related("student_parent_relations__parent__user")
        )

    def get_full_name(self, obj):
        return obj.get_full_name()

    get_full_name.short_description = "Name"
    get_full_name.admin_order_field = "user__first_name"

    def get_username(self, obj):
        """Display the username (should be admission number)"""
        return obj.user.username

    get_username.short_description = "Username"
    get_username.admin_order_field = "user__username"

    def get_username_display(self, obj):
        """Readonly field to display username"""
        return obj.user.username

    get_username_display.short_description = "Username (Login ID)"

    def get_email_display(self, obj):
        """Readonly field to display email status"""
        return obj.user.email or "No email provided"

    get_email_display.short_description = "Email"

    def get_email(self, obj):
        """Display email with note if empty"""
        return obj.user.email or "No email provided"

    get_email.short_description = "Email"
    get_email.admin_order_field = "user__email"

    def get_age(self, obj):
        return obj.age or "Not provided"

    get_age.short_description = "Age"

    def status_badge(self, obj):
        colors = {
            "Active": "success",
            "Inactive": "secondary",
            "Graduated": "info",
            "Suspended": "warning",
            "Expelled": "danger",
            "Withdrawn": "secondary",
        }
        color = colors.get(obj.status, "secondary")
        return format_html('<span class="badge bg-{}">{}</span>', color, obj.status)

    status_badge.short_description = "Status"

    def get_parent_count(self, obj):
        count = obj.student_parent_relations.count()
        if count > 0:
            url = (
                reverse("admin:students_studentparentrelation_changelist")
                + f"?student__id__exact={obj.id}"
            )
            return format_html('<a href="{}">{} parent(s)</a>', url, count)
        return "0 parents"

    get_parent_count.short_description = "Parents"

    def gender_filter(self, obj):
        return obj.user.gender if hasattr(obj.user, "gender") else "Not specified"

    gender_filter.short_description = "Gender"

    actions = [
        "mark_as_graduated",
        "mark_as_active",
        "export_selected",
        "reset_passwords",
    ]

    def mark_as_graduated(self, request, queryset):
        updated = queryset.update(status="Graduated")
        self.message_user(request, f"{updated} students marked as graduated.")

    mark_as_graduated.short_description = "Mark selected students as graduated"

    def mark_as_active(self, request, queryset):
        updated = queryset.update(status="Active")
        self.message_user(request, f"{updated} students marked as active.")

    mark_as_active.short_description = "Mark selected students as active"

    def reset_passwords(self, request, queryset):
        """Reset passwords for selected students"""
        updated = 0
        for student in queryset:
            new_password = User.objects.make_random_password()
            student.user.set_password(new_password)
            student.user.save()
            updated += 1

            # Send new password via email if available
            if student.user.email:
                try:
                    send_mail(
                        subject="Password Reset",
                        message=f"Your new password is: {new_password}\nUsername: {student.user.username}",
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[student.user.email],
                        fail_silently=True,
                    )
                except:
                    pass

        self.message_user(request, f"Reset passwords for {updated} students.")

    reset_passwords.short_description = "Reset passwords for selected students"


class ParentResource(resources.ModelResource):
    user__first_name = fields.Field(column_name="first_name")
    user__last_name = fields.Field(column_name="last_name")
    user__email = fields.Field(column_name="email")
    user__phone_number = fields.Field(column_name="phone_number")
    student_count = fields.Field(column_name="student_count")

    class Meta:
        model = Parent
        fields = (
            "user__first_name",
            "user__last_name",
            "user__email",
            "user__phone_number",
            "relation_with_student",
            "occupation",
            "workplace",
            "work_phone",
            "emergency_contact",
            "student_count",
        )


class StudentParentRelationInlineForParent(admin.TabularInline):
    model = StudentParentRelation
    extra = 0
    autocomplete_fields = ["student"]
    fields = (
        "student",
        "is_primary_contact",
        "can_pickup",
        "emergency_contact_priority",
        "financial_responsibility",
    )


@admin.register(Parent)
class ParentAdmin(ImportExportModelAdmin):
    resource_class = ParentResource
    list_display = (
        "get_full_name",
        "get_email",
        "get_phone",
        "relation_with_student",
        "occupation",
        "emergency_contact_badge",
        "get_student_count",
    )
    list_filter = (
        "relation_with_student",
        "emergency_contact",
        "created_at",
    )
    search_fields = ("user__first_name", "user__last_name", "user__email", "occupation")
    autocomplete_fields = ["user", "created_by"]
    readonly_fields = ("id", "created_at", "updated_at")
    inlines = [StudentParentRelationInlineForParent]
    list_per_page = 50
    list_select_related = ("user",)
    show_full_result_count = False

    fieldsets = (
        (
            "Basic Information",
            {"fields": ("id", "user", "relation_with_student", "photo")},
        ),
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
        (
            "Metadata",
            {
                "fields": ("created_by", "created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("user")
            .annotate(student_count=Count("parent_student_relations"))
        )

    def get_full_name(self, obj):
        return obj.get_full_name()

    get_full_name.short_description = "Name"
    get_full_name.admin_order_field = "user__first_name"

    def get_email(self, obj):
        return obj.user.email

    get_email.short_description = "Email"
    get_email.admin_order_field = "user__email"

    def get_phone(self, obj):
        return obj.user.phone_number or "Not provided"

    get_phone.short_description = "Phone"

    def emergency_contact_badge(self, obj):
        if obj.emergency_contact:
            return format_html('<span class="badge bg-success">Yes</span>')
        return format_html('<span class="badge bg-secondary">No</span>')

    emergency_contact_badge.short_description = "Emergency Contact"

    def get_student_count(self, obj):
        count = getattr(obj, "student_count", 0)
        if count > 0:
            url = (
                reverse("admin:students_student_changelist")
                + f"?student_parent_relations__parent__id__exact={obj.id}"
            )
            return format_html('<a href="{}">{} student(s)</a>', url, count)
        return "0 students"

    get_student_count.short_description = "Students"


@admin.register(StudentParentRelation)
class StudentParentRelationAdmin(admin.ModelAdmin):
    list_display = (
        "student",
        "parent",
        "relation_type",
        "primary_contact_badge",
        "pickup_permission_badge",
        "emergency_contact_priority",
        "financial_responsibility_badge",
    )
    list_filter = (
        "is_primary_contact",
        "can_pickup",
        "financial_responsibility",
        "parent__relation_with_student",
        "created_at",
    )
    search_fields = (
        "student__user__first_name",
        "student__user__last_name",
        "student__admission_number",
        "parent__user__first_name",
        "parent__user__last_name",
    )
    autocomplete_fields = ["student", "parent", "created_by"]
    list_editable = ("emergency_contact_priority",)
    readonly_fields = ("id", "created_at", "updated_at")
    list_per_page = 50
    list_select_related = ("student__user", "parent__user")

    fieldsets = (
        (
            "Basic Information",
            {
                "fields": (
                    "id",
                    "student",
                    "parent",
                )
            },
        ),
        (
            "Permissions",
            {
                "fields": (
                    "is_primary_contact",
                    "can_pickup",
                    "emergency_contact_priority",
                    "financial_responsibility",
                )
            },
        ),
        (
            "Access Rights",
            {
                "fields": (
                    "access_to_grades",
                    "access_to_attendance",
                    "access_to_financial_info",
                )
            },
        ),
        (
            "Communication Preferences",
            {
                "fields": (
                    "receive_sms",
                    "receive_email",
                    "receive_push_notifications",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Metadata",
            {
                "fields": (
                    "created_by",
                    "created_at",
                    "updated_at",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    def relation_type(self, obj):
        return obj.parent.relation_with_student

    relation_type.short_description = "Relation"

    def primary_contact_badge(self, obj):
        if obj.is_primary_contact:
            return format_html('<span class="badge bg-primary">Primary</span>')
        return format_html('<span class="badge bg-secondary">Secondary</span>')

    primary_contact_badge.short_description = "Contact Type"

    def pickup_permission_badge(self, obj):
        if obj.can_pickup:
            return format_html('<span class="badge bg-success">Allowed</span>')
        return format_html('<span class="badge bg-danger">Not Allowed</span>')

    pickup_permission_badge.short_description = "Pickup Permission"

    def emergency_priority(self, obj):
        return f"Priority {obj.emergency_contact_priority}"

    emergency_priority.short_description = "Emergency Priority"

    def financial_responsibility_badge(self, obj):
        if obj.financial_responsibility:
            return format_html('<span class="badge bg-info">Responsible</span>')
        return format_html('<span class="badge bg-secondary">Not Responsible</span>')

    financial_responsibility_badge.short_description = "Financial Responsibility"
