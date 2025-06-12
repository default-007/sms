# core/admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from django.db.models import Q
from django.utils.safestring import mark_safe
import json

from .models import (
    SystemSetting,
    AuditLog,
    StudentPerformanceAnalytics,
    ClassPerformanceAnalytics,
    AttendanceAnalytics,
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
    list_per_page = 25

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
            json_str = json.dumps(value, indent=2)
            if len(json_str) > 100:
                json_str = json_str[:100] + "..."
            return format_html(
                "<code style='white-space: pre-wrap;'>{}</code>", json_str
            )
        elif isinstance(value, bool):
            icon = "✓" if value else "✗"
            color = "green" if value else "red"
            return format_html('<span style="color: {};">{}</span>', color, icon)
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

    def get_queryset(self, request):
        """Optimize queryset"""
        return super().get_queryset(request).select_related("updated_by")


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = [
        "timestamp",
        "user_display",
        "action",
        "content_type_display",
        "object_representation",
        "module_name",
        "ip_address",
        "duration_display",
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
        "ip_address",
    ]
    readonly_fields = [
        "user",
        "action",
        "content_type",
        "object_id",
        "data_before_display",
        "data_after_display",
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
    list_per_page = 50

    fieldsets = (
        (
            "Basic Information",
            {
                "fields": (
                    "timestamp",
                    "user",
                    "action",
                    "description",
                    "duration_ms",
                )
            },
        ),
        (
            "Content Object",
            {
                "fields": ("content_type", "object_id"),
                "classes": ("collapse",),
            },
        ),
        (
            "Data Changes",
            {
                "fields": ("data_before_display", "data_after_display"),
                "classes": ("collapse",),
            },
        ),
        (
            "Session Information",
            {
                "fields": ("ip_address", "user_agent", "session_key"),
                "classes": ("collapse",),
            },
        ),
        (
            "System Information",
            {
                "fields": ("module_name", "view_name"),
                "classes": ("collapse",),
            },
        ),
    )

    # Disable add/delete permissions as audit logs should only be created programmatically
    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return False

    def user_display(self, obj):
        """Display user information"""
        if obj.user:
            name = obj.user.get_full_name() or obj.user.username
            return format_html(
                '<a href="{}">{}</a>',
                reverse("admin:accounts_user_change", args=[obj.user.pk]),
                name,
            )
        return "System"

    user_display.short_description = "User"

    def content_type_display(self, obj):
        """Display content type"""
        if obj.content_type:
            return f"{obj.content_type.app_label}.{obj.content_type.model}"
        return "-"

    content_type_display.short_description = "Content Type"

    def object_representation(self, obj):
        """Display object representation"""
        if obj.content_object:
            return str(obj.content_object)[:50]
        return "-"

    object_representation.short_description = "Object"

    def duration_display(self, obj):
        """Display duration with color coding"""
        if obj.duration_ms:
            if obj.duration_ms < 100:
                color = "green"
            elif obj.duration_ms < 500:
                color = "orange"
            else:
                color = "red"
            return format_html(
                '<span style="color: {};">{} ms</span>', color, obj.duration_ms
            )
        return "-"

    duration_display.short_description = "Duration"

    def data_before_display(self, obj):
        """Display formatted data_before"""
        if obj.data_before:
            json_str = json.dumps(obj.data_before, indent=2)
            return format_html("<pre>{}</pre>", json_str)
        return "-"

    data_before_display.short_description = "Data Before"

    def data_after_display(self, obj):
        """Display formatted data_after"""
        if obj.data_after:
            json_str = json.dumps(obj.data_after, indent=2)
            return format_html("<pre>{}</pre>", json_str)
        return "-"

    data_after_display.short_description = "Data After"

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

    def get_readonly_fields(self, request, obj=None):
        """Make all fields readonly"""
        return [field.name for field in self.model._meta.fields]


@admin.register(StudentPerformanceAnalytics)
class StudentPerformanceAnalyticsAdmin(AnalyticsAdminMixin, admin.ModelAdmin):
    list_display = [
        "student_name",
        "class_name",
        "term_name",
        "subject_name",
        "average_marks_display",
        "attendance_percentage_display",
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
    date_hierarchy = "calculated_at"
    ordering = ["-calculated_at", "student__user__last_name"]
    list_per_page = 25

    def student_name(self, obj):
        name = obj.student.user.get_full_name()
        return format_html(
            '<a href="{}">{}</a>',
            reverse("admin:students_student_change", args=[obj.student.pk]),
            name,
        )

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

    def average_marks_display(self, obj):
        """Display average marks with color coding"""
        if obj.average_marks:
            marks = float(obj.average_marks)
            if marks >= 80:
                color = "green"
            elif marks >= 60:
                color = "orange"
            else:
                color = "red"
            return format_html(
                '<span style="color: {}; font-weight: bold;">{:.1f}</span>',
                color,
                marks,
            )
        return "-"

    average_marks_display.short_description = "Avg Marks"

    def attendance_percentage_display(self, obj):
        """Display attendance with color coding"""
        if obj.attendance_percentage:
            attendance = float(obj.attendance_percentage)
            if attendance >= 90:
                color = "green"
            elif attendance >= 75:
                color = "orange"
            else:
                color = "red"
            return format_html(
                '<span style="color: {}; font-weight: bold;">{:.1f}%</span>',
                color,
                attendance,
            )
        return "-"

    attendance_percentage_display.short_description = "Attendance"

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
        "class_average_display",
        "pass_rate_display",
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
    date_hierarchy = "calculated_at"
    ordering = ["-calculated_at", "-class_average"]
    list_per_page = 25

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

    def class_average_display(self, obj):
        """Display class average with color coding"""
        if obj.class_average:
            avg = float(obj.class_average)
            if avg >= 80:
                color = "green"
            elif avg >= 60:
                color = "orange"
            else:
                color = "red"
            return format_html(
                '<span style="color: {}; font-weight: bold;">{:.1f}</span>', color, avg
            )
        return "-"

    class_average_display.short_description = "Class Average"

    def pass_rate_display(self, obj):
        """Display pass rate with color coding"""
        if obj.pass_rate:
            rate = float(obj.pass_rate)
            if rate >= 90:
                color = "green"
            elif rate >= 70:
                color = "orange"
            else:
                color = "red"
            return format_html(
                '<span style="color: {}; font-weight: bold;">{:.1f}%</span>',
                color,
                rate,
            )
        return "-"

    pass_rate_display.short_description = "Pass Rate"

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
        "attendance_percentage_display",
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
    date_hierarchy = "calculated_at"
    ordering = ["-calculated_at", "attendance_percentage"]
    list_per_page = 25

    def term_name(self, obj):
        return str(obj.term) if obj.term else f"{obj.month}/{obj.year}"

    term_name.short_description = "Period"

    def attendance_percentage_display(self, obj):
        """Display attendance percentage with color coding"""
        percentage = float(obj.attendance_percentage)
        if percentage >= 90:
            color = "green"
        elif percentage >= 75:
            color = "orange"
        else:
            color = "red"
        return format_html(
            '<span style="color: {}; font-weight: bold;">{:.1f}%</span>',
            color,
            percentage,
        )

    attendance_percentage_display.short_description = "Attendance %"


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
        "collection_rate_display",
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
    date_hierarchy = "calculated_at"
    ordering = ["-calculated_at", "-total_expected_revenue"]
    list_per_page = 25

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

    def collection_rate_display(self, obj):
        # Display collection rate with color coding
        rate = float(obj.collection_rate)
        if rate >= 90:
            color = "green"
        elif rate >= 70:
            color = "orange"
        else:
            color = "red"
        return format_html(
            '<span style="color: {}; font-weight: bold;">{:.1f}%</span>', color, rate
        )

    collection_rate_display.short_description = "Collection Rate"
 """


@admin.register(TeacherPerformanceAnalytics)
class TeacherPerformanceAnalyticsAdmin(AnalyticsAdminMixin, admin.ModelAdmin):
    list_display = [
        "teacher_name",
        "term_name",
        "classes_taught",
        "total_students",
        "average_class_performance_display",
        "overall_performance_score_display",
        "calculated_at",
    ]
    list_filter = ["academic_year", "term", "calculated_at"]
    search_fields = [
        "teacher__user__first_name",
        "teacher__user__last_name",
        "teacher__employee_id",
    ]
    date_hierarchy = "calculated_at"
    ordering = ["-calculated_at", "-overall_performance_score"]
    list_per_page = 25

    def teacher_name(self, obj):
        name = obj.teacher.user.get_full_name()
        return format_html(
            '<a href="{}">{}</a>',
            reverse("admin:teachers_teacher_change", args=[obj.teacher.pk]),
            name,
        )

    teacher_name.short_description = "Teacher"
    teacher_name.admin_order_field = "teacher__user__last_name"

    def term_name(self, obj):
        return str(obj.term)

    term_name.short_description = "Term"

    def average_class_performance_display(self, obj):
        """Display average class performance with color coding"""
        if obj.average_class_performance:
            perf = float(obj.average_class_performance)
            if perf >= 80:
                color = "green"
            elif perf >= 60:
                color = "orange"
            else:
                color = "red"
            return format_html(
                '<span style="color: {}; font-weight: bold;">{:.1f}</span>', color, perf
            )
        return "-"

    average_class_performance_display.short_description = "Class Performance"

    def overall_performance_score_display(self, obj):
        """Display overall performance score with color coding"""
        if obj.overall_performance_score:
            score = float(obj.overall_performance_score)
            if score >= 4.0:
                color = "green"
            elif score >= 3.0:
                color = "orange"
            else:
                color = "red"
            return format_html(
                '<span style="color: {}; font-weight: bold;">{:.1f}/5.0</span>',
                color,
                score,
            )
        return "-"

    overall_performance_score_display.short_description = "Overall Score"

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
        "avg_response_time_display",
        "error_rate_display",
        "cache_hit_rate_display",
        "storage_used_display",
        "pending_tasks",
    ]
    list_filter = ["timestamp"]
    date_hierarchy = "timestamp"
    ordering = ["-timestamp"]
    list_per_page = 50

    def avg_response_time_display(self, obj):
        """Display response time with color coding"""
        time_ms = float(obj.avg_response_time_ms)
        if time_ms < 300:
            color = "green"
        elif time_ms < 1000:
            color = "orange"
        else:
            color = "red"
        return format_html('<span style="color: {};">{:.1f} ms</span>', color, time_ms)

    avg_response_time_display.short_description = "Avg Response Time"

    def error_rate_display(self, obj):
        """Display error rate with color coding"""
        rate = float(obj.error_rate)
        if rate < 1:
            color = "green"
        elif rate < 5:
            color = "orange"
        else:
            color = "red"
        return format_html('<span style="color: {};">{:.1f}%</span>', color, rate)

    error_rate_display.short_description = "Error Rate"

    def cache_hit_rate_display(self, obj):
        """Display cache hit rate with color coding"""
        rate = float(obj.cache_hit_rate)
        if rate > 80:
            color = "green"
        elif rate > 60:
            color = "orange"
        else:
            color = "red"
        return format_html('<span style="color: {};">{:.1f}%</span>', color, rate)

    cache_hit_rate_display.short_description = "Cache Hit Rate"

    def storage_used_display(self, obj):
        """Display storage usage with color coding"""
        total_storage = obj.storage_used_gb + obj.storage_available_gb
        if total_storage > 0:
            usage_percentage = (obj.storage_used_gb / total_storage) * 100
            if usage_percentage < 70:
                color = "green"
            elif usage_percentage < 85:
                color = "orange"
            else:
                color = "red"
            return format_html(
                '<span style="color: {};">{:.1f} GB ({:.1f}%)</span>',
                color,
                obj.storage_used_gb,
                usage_percentage,
            )
        return f"{obj.storage_used_gb:.1f} GB"

    storage_used_display.short_description = "Storage Used"

    def get_queryset(self, request):
        # Only show recent metrics (last 30 days) for performance
        cutoff_date = timezone.now() - timezone.timedelta(days=30)
        return super().get_queryset(request).filter(timestamp__gte=cutoff_date)


# Customize admin site header and title
admin.site.site_header = "School Management System Administration"
admin.site.site_title = "SMS Admin"
admin.site.index_title = "Administration Dashboard"
