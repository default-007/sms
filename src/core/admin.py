# core/admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from django.db.models import Q
import json

from .models import (
    SystemSetting,
    AuditLog,
    StudentPerformanceAnalytics,
    ClassPerformanceAnalytics,
    AttendanceAnalytics,
    # FinancialAnalytics,
    TeacherPerformanceAnalytics,
    SystemHealthMetrics,
)


@admin.register(SystemSetting)
class SystemSettingAdmin(admin.ModelAdmin):
    list_display = [
        "setting_key",
        "typed_value_display",
        "data_type",
        "category",
        "is_editable",
        "updated_at",
        "updated_by_display",
    ]
    list_filter = ["category", "data_type", "is_editable", "created_at"]
    search_fields = ["setting_key", "description"]
    readonly_fields = ["created_at", "updated_at", "updated_by"]

    fieldsets = (
        (
            "Basic Information",
            {"fields": ("setting_key", "setting_value", "data_type", "category")},
        ),
        ("Configuration", {"fields": ("description", "is_editable")}),
        (
            "Metadata",
            {
                "fields": ("created_at", "updated_at", "updated_by"),
                "classes": ("collapse",),
            },
        ),
    )

    def typed_value_display(self, obj):
        """Display the typed value"""
        value = obj.get_typed_value()
        if isinstance(value, dict) or isinstance(value, list):
            return format_html(
                "<code>{}</code>",
                (
                    json.dumps(value, indent=2)[:100] + "..."
                    if len(str(value)) > 100
                    else json.dumps(value, indent=2)
                ),
            )
        return str(value)

    typed_value_display.short_description = "Current Value"

    def updated_by_display(self, obj):
        """Display updated by user"""
        if obj.updated_by:
            return obj.updated_by.get_full_name() or obj.updated_by.username
        return "-"

    updated_by_display.short_description = "Updated By"

    def save_model(self, request, obj, form, change):
        """Set updated_by field"""
        if change:
            obj.updated_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = [
        "timestamp",
        "user_display",
        "action",
        "content_type",
        "object_representation",
        "module_name",
        "ip_address",
    ]
    list_filter = [
        "action",
        "content_type",
        "module_name",
        "timestamp",
        ("user", admin.RelatedOnlyFieldListFilter),
    ]
    search_fields = [
        "user__username",
        "user__first_name",
        "user__last_name",
        "description",
        "module_name",
        "view_name",
    ]
    readonly_fields = [
        "user",
        "action",
        "content_type",
        "object_id",
        "data_before",
        "data_after",
        "ip_address",
        "user_agent",
        "session_key",
        "description",
        "module_name",
        "view_name",
        "timestamp",
        "duration_ms",
    ]
    date_hierarchy = "timestamp"
    ordering = ["-timestamp"]

    # Disable add/delete permissions as audit logs should only be created programmatically
    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    def user_display(self, obj):
        """Display user information"""
        if obj.user:
            return obj.user.get_full_name() or obj.user.username
        return "System"

    user_display.short_description = "User"

    def object_representation(self, obj):
        """Display object representation"""
        if obj.content_object:
            return str(obj.content_object)[:50]
        return "-"

    object_representation.short_description = "Object"

    def get_queryset(self, request):
        """Optimize queryset"""
        return super().get_queryset(request).select_related("user", "content_type")


class AnalyticsAdminMixin:
    """Mixin for analytics admin classes"""

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


@admin.register(StudentPerformanceAnalytics)
class StudentPerformanceAnalyticsAdmin(AnalyticsAdminMixin, admin.ModelAdmin):
    list_display = [
        "student_name",
        "class_name",
        "term_name",
        "subject_name",
        "average_marks",
        "attendance_percentage",
        "ranking_in_class",
        "calculated_at",
    ]
    list_filter = [
        "academic_year",
        "term",
        "subject",
        "improvement_trend",
        "calculated_at",
    ]
    search_fields = [
        "student__user__first_name",
        "student__user__last_name",
        "student__admission_number",
    ]
    readonly_fields = [
        "student",
        "academic_year",
        "term",
        "subject",
        "average_marks",
        "highest_marks",
        "lowest_marks",
        "grade_point",
        "attendance_percentage",
        "assignment_completion_rate",
        "assignments_submitted",
        "assignments_on_time",
        "ranking_in_class",
        "ranking_in_grade",
        "ranking_in_section",
        "improvement_trend",
        "trend_percentage",
        "calculated_at",
    ]
    date_hierarchy = "calculated_at"
    ordering = ["-calculated_at", "student__user__last_name"]

    def student_name(self, obj):
        return obj.student.user.get_full_name()

    student_name.short_description = "Student"
    student_name.admin_order_field = "student__user__last_name"

    def class_name(self, obj):
        return str(obj.student.current_class)

    class_name.short_description = "Class"

    def term_name(self, obj):
        return str(obj.term)

    term_name.short_description = "Term"

    def subject_name(self, obj):
        return obj.subject.name if obj.subject else "Overall"

    subject_name.short_description = "Subject"

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related(
                "student__user",
                "student__current_class",
                "academic_year",
                "term",
                "subject",
            )
        )


@admin.register(ClassPerformanceAnalytics)
class ClassPerformanceAnalyticsAdmin(AnalyticsAdminMixin, admin.ModelAdmin):
    list_display = [
        "class_name",
        "grade_name",
        "section_name",
        "term_name",
        "class_average",
        "pass_rate",
        "total_students",
        "calculated_at",
    ]
    list_filter = [
        "academic_year",
        "term",
        "subject",
        "calculated_at",
        "class_instance__grade__section",
    ]
    search_fields = [
        "class_instance__name",
        "class_instance__grade__name",
        "class_instance__grade__section__name",
    ]
    readonly_fields = [
        "class_instance",
        "academic_year",
        "term",
        "subject",
        "class_average",
        "highest_score",
        "lowest_score",
        "median_score",
        "standard_deviation",
        "total_students",
        "students_above_average",
        "students_below_average",
        "students_at_risk",
        "pass_rate",
        "distinction_rate",
        "grade_ranking",
        "section_ranking",
        "calculated_at",
    ]
    date_hierarchy = "calculated_at"
    ordering = ["-calculated_at", "-class_average"]

    def class_name(self, obj):
        return obj.class_instance.name

    class_name.short_description = "Class"

    def grade_name(self, obj):
        return obj.class_instance.grade.name

    grade_name.short_description = "Grade"

    def section_name(self, obj):
        return obj.class_instance.grade.section.name

    section_name.short_description = "Section"

    def term_name(self, obj):
        return str(obj.term)

    term_name.short_description = "Term"

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related(
                "class_instance__grade__section", "academic_year", "term", "subject"
            )
        )


@admin.register(AttendanceAnalytics)
class AttendanceAnalyticsAdmin(AnalyticsAdminMixin, admin.ModelAdmin):
    list_display = [
        "entity_name",
        "entity_type",
        "term_name",
        "attendance_percentage",
        "total_days",
        "present_days",
        "absent_days",
        "calculated_at",
    ]
    list_filter = [
        "entity_type",
        "academic_year",
        "term",
        "attendance_trend",
        "calculated_at",
    ]
    search_fields = ["entity_name"]
    readonly_fields = [
        "entity_type",
        "entity_id",
        "entity_name",
        "academic_year",
        "term",
        "month",
        "year",
        "total_days",
        "present_days",
        "absent_days",
        "late_days",
        "excused_days",
        "attendance_percentage",
        "consecutive_absences",
        "frequent_late_arrivals",
        "attendance_trend",
        "calculated_at",
    ]
    date_hierarchy = "calculated_at"
    ordering = ["-calculated_at", "-attendance_percentage"]

    def term_name(self, obj):
        return str(obj.term) if obj.term else f"{obj.month}/{obj.year}"

    term_name.short_description = "Period"


""" 
@admin.register(FinancialAnalytics)
class FinancialAnalyticsAdmin(AnalyticsAdminMixin, admin.ModelAdmin):
    list_display = [
        "academic_year_name",
        "term_name",
        "section_name",
        "grade_name",
        "total_expected_revenue",
        "total_collected_revenue",
        "collection_rate",
        "calculated_at",
    ]
    list_filter = [
        "academic_year",
        "term",
        "section",
        "grade",
        "fee_category",
        "collection_trend",
        "calculated_at",
    ]
    search_fields = ["section__name", "grade__name", "fee_category__name"]
    readonly_fields = [
        "academic_year",
        "term",
        "section",
        "grade",
        "fee_category",
        "total_expected_revenue",
        "total_collected_revenue",
        "total_outstanding",
        "total_advance_payments",
        "collection_rate",
        "on_time_collection_rate",
        "total_students",
        "students_paid_full",
        "students_paid_partial",
        "students_with_outstanding",
        "students_with_overdue",
        "total_scholarships_awarded",
        "scholarship_percentage",
        "revenue_growth",
        "collection_trend",
        "month",
        "year",
        "calculated_at",
    ]
    date_hierarchy = "calculated_at"
    ordering = ["-calculated_at", "-total_expected_revenue"]

    def academic_year_name(self, obj):
        return obj.academic_year.name

    academic_year_name.short_description = "Academic Year"

    def term_name(self, obj):
        return obj.term.name if obj.term else f"{obj.month}/{obj.year}"

    term_name.short_description = "Period"

    def section_name(self, obj):
        return obj.section.name if obj.section else "All Sections"

    section_name.short_description = "Section"

    def grade_name(self, obj):
        return obj.grade.name if obj.grade else "All Grades"

    grade_name.short_description = "Grade"
 """


@admin.register(TeacherPerformanceAnalytics)
class TeacherPerformanceAnalyticsAdmin(AnalyticsAdminMixin, admin.ModelAdmin):
    list_display = [
        "teacher_name",
        "term_name",
        "classes_taught",
        "total_students",
        "average_class_performance",
        "overall_performance_score",
        "calculated_at",
    ]
    list_filter = ["academic_year", "term", "calculated_at"]
    search_fields = [
        "teacher__user__first_name",
        "teacher__user__last_name",
        "teacher__employee_id",
    ]
    readonly_fields = [
        "teacher",
        "academic_year",
        "term",
        "classes_taught",
        "subjects_taught",
        "total_students",
        "teaching_hours_per_week",
        "average_class_performance",
        "students_above_average",
        "students_below_average",
        "improvement_rate",
        "attendance_rate",
        "punctuality_rate",
        "assignments_given",
        "assignments_graded",
        "assignments_graded_on_time",
        "average_grading_time_days",
        "training_hours_completed",
        "certifications_earned",
        "peer_evaluation_score",
        "student_feedback_score",
        "parent_feedback_score",
        "overall_performance_score",
        "calculated_at",
    ]
    date_hierarchy = "calculated_at"
    ordering = ["-calculated_at", "-overall_performance_score"]

    def teacher_name(self, obj):
        return obj.teacher.user.get_full_name()

    teacher_name.short_description = "Teacher"
    teacher_name.admin_order_field = "teacher__user__last_name"

    def term_name(self, obj):
        return str(obj.term)

    term_name.short_description = "Term"

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("teacher__user", "academic_year", "term")
        )


@admin.register(SystemHealthMetrics)
class SystemHealthMetricsAdmin(AnalyticsAdminMixin, admin.ModelAdmin):
    list_display = [
        "timestamp",
        "active_users",
        "avg_response_time_ms",
        "error_rate",
        "cache_hit_rate",
        "storage_used_gb",
        "pending_tasks",
    ]
    list_filter = ["timestamp"]
    readonly_fields = [
        "timestamp",
        "db_connection_count",
        "db_query_count",
        "avg_query_time_ms",
        "cache_hit_rate",
        "cache_memory_usage_mb",
        "active_users",
        "requests_per_minute",
        "avg_response_time_ms",
        "error_rate",
        "pending_tasks",
        "failed_tasks",
        "completed_tasks",
        "storage_used_gb",
        "storage_available_gb",
    ]
    date_hierarchy = "timestamp"
    ordering = ["-timestamp"]

    def get_queryset(self, request):
        # Only show recent metrics (last 30 days) for performance
        cutoff_date = timezone.now() - timezone.timedelta(days=30)
        return super().get_queryset(request).filter(timestamp__gte=cutoff_date)


# Customize admin site header and title
admin.site.site_header = "School Management System Administration"
admin.site.site_title = "SMS Admin"
admin.site.index_title = "Administration Dashboard"
