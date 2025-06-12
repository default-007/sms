# core/api/serializers.py
from rest_framework import serializers
from django.contrib.auth import get_user_model
from src.finance.models import FinancialAnalytics
from ..models import (
    SystemSetting,
    AuditLog,
    StudentPerformanceAnalytics,
    ClassPerformanceAnalytics,
    AttendanceAnalytics,
    TeacherPerformanceAnalytics,
    SystemHealthMetrics,
)

User = get_user_model()


class SystemSettingSerializer(serializers.ModelSerializer):
    """Serializer for SystemSetting model"""

    typed_value = serializers.SerializerMethodField()
    updated_by_name = serializers.SerializerMethodField()

    class Meta:
        model = SystemSetting
        fields = [
            "id",
            "setting_key",
            "setting_value",
            "typed_value",
            "data_type",
            "category",
            "description",
            "is_editable",
            "created_at",
            "updated_at",
            "updated_by",
            "updated_by_name",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "updated_by"]

    def get_typed_value(self, obj):
        """Get the typed value of the setting"""
        return obj.get_typed_value()

    def get_updated_by_name(self, obj):
        """Get the name of the user who last updated the setting"""
        if obj.updated_by:
            return obj.updated_by.get_full_name() or obj.updated_by.username
        return None


class UserBasicSerializer(serializers.ModelSerializer):
    """Basic user serializer for related fields"""

    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "username", "first_name", "last_name", "full_name", "email"]

    def get_full_name(self, obj):
        return obj.get_full_name() or obj.username


class AuditLogSerializer(serializers.ModelSerializer):
    """Serializer for AuditLog model"""

    user_detail = UserBasicSerializer(source="user", read_only=True)
    content_type_name = serializers.SerializerMethodField()
    object_representation = serializers.SerializerMethodField()

    class Meta:
        model = AuditLog
        fields = [
            "id",
            "user",
            "user_detail",
            "action",
            "content_type",
            "content_type_name",
            "object_id",
            "object_representation",
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

    def get_content_type_name(self, obj):
        """Get human-readable content type name"""
        if obj.content_type:
            return f"{obj.content_type.app_label}.{obj.content_type.model}"
        return None

    def get_object_representation(self, obj):
        """Get string representation of the content object"""
        if obj.content_object:
            return str(obj.content_object)[:100]
        return None


class StudentBasicSerializer(serializers.Serializer):
    """Basic student serializer for analytics"""

    id = serializers.IntegerField()
    user_id = serializers.IntegerField(source="user.id")
    full_name = serializers.CharField(source="user.get_full_name")
    admission_number = serializers.CharField()


class StudentPerformanceAnalyticsSerializer(serializers.ModelSerializer):
    """Serializer for StudentPerformanceAnalytics model"""

    student_detail = StudentBasicSerializer(source="student", read_only=True)
    academic_year_name = serializers.CharField(
        source="academic_year.name", read_only=True
    )
    term_name = serializers.CharField(source="term.name", read_only=True)
    subject_name = serializers.CharField(source="subject.name", read_only=True)

    class Meta:
        model = StudentPerformanceAnalytics
        fields = [
            "id",
            "student",
            "student_detail",
            "academic_year",
            "academic_year_name",
            "term",
            "term_name",
            "subject",
            "subject_name",
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


class ClassBasicSerializer(serializers.Serializer):
    """Basic class serializer for analytics"""

    id = serializers.IntegerField()
    name = serializers.CharField()
    display_name = serializers.SerializerMethodField()
    grade_name = serializers.CharField(source="grade.name")
    section_name = serializers.CharField(source="grade.section.name")

    def get_display_name(self, obj):
        return f"{obj.grade.name} {obj.name}"


class ClassPerformanceAnalyticsSerializer(serializers.ModelSerializer):
    """Serializer for ClassPerformanceAnalytics model"""

    class_detail = ClassBasicSerializer(source="class_instance", read_only=True)
    academic_year_name = serializers.CharField(
        source="academic_year.name", read_only=True
    )
    term_name = serializers.CharField(source="term.name", read_only=True)
    subject_name = serializers.CharField(source="subject.name", read_only=True)

    class Meta:
        model = ClassPerformanceAnalytics
        fields = [
            "id",
            "class_instance",
            "class_detail",
            "academic_year",
            "academic_year_name",
            "term",
            "term_name",
            "subject",
            "subject_name",
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


class AttendanceAnalyticsSerializer(serializers.ModelSerializer):
    """Serializer for AttendanceAnalytics model"""

    academic_year_name = serializers.CharField(
        source="academic_year.name", read_only=True
    )
    term_name = serializers.CharField(source="term.name", read_only=True)
    period_display = serializers.SerializerMethodField()

    class Meta:
        model = AttendanceAnalytics
        fields = [
            "id",
            "entity_type",
            "entity_id",
            "entity_name",
            "academic_year",
            "academic_year_name",
            "term",
            "term_name",
            "month",
            "year",
            "period_display",
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

    def get_period_display(self, obj):
        """Get human-readable period display"""
        if obj.term:
            return str(obj.term)
        elif obj.month and obj.year:
            return f"{obj.month}/{obj.year}"
        return "Unknown"


class FinancialAnalyticsSerializer(serializers.ModelSerializer):
    """Serializer for FinancialAnalytics model"""

    academic_year_name = serializers.CharField(
        source="academic_year.name", read_only=True
    )
    term_name = serializers.CharField(source="term.name", read_only=True)
    section_name = serializers.CharField(source="section.name", read_only=True)
    grade_name = serializers.CharField(source="grade.name", read_only=True)
    fee_category_name = serializers.CharField(
        source="fee_category.name", read_only=True
    )
    collection_efficiency = serializers.SerializerMethodField()

    class Meta:
        model = FinancialAnalytics
        fields = [
            "id",
            "academic_year",
            "academic_year_name",
            "term",
            "term_name",
            "section",
            "section_name",
            "grade",
            "grade_name",
            "fee_category",
            "fee_category_name",
            "total_expected_revenue",
            "total_collected_revenue",
            "total_outstanding",
            "total_advance_payments",
            "collection_rate",
            "collection_efficiency",
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

    def get_collection_efficiency(self, obj):
        """Calculate collection efficiency percentage"""
        if obj.total_expected_revenue and obj.total_expected_revenue > 0:
            return round(
                float(obj.total_collected_revenue / obj.total_expected_revenue * 100), 2
            )
        return 0


class TeacherBasicSerializer(serializers.Serializer):
    """Basic teacher serializer for analytics"""

    id = serializers.IntegerField()
    user_id = serializers.IntegerField(source="user.id")
    full_name = serializers.CharField(source="user.get_full_name")
    employee_id = serializers.CharField()


class TeacherPerformanceAnalyticsSerializer(serializers.ModelSerializer):
    """Serializer for TeacherPerformanceAnalytics model"""

    teacher_detail = TeacherBasicSerializer(source="teacher", read_only=True)
    academic_year_name = serializers.CharField(
        source="academic_year.name", read_only=True
    )
    term_name = serializers.CharField(source="term.name", read_only=True)
    performance_level = serializers.SerializerMethodField()

    class Meta:
        model = TeacherPerformanceAnalytics
        fields = [
            "id",
            "teacher",
            "teacher_detail",
            "academic_year",
            "academic_year_name",
            "term",
            "term_name",
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
            "performance_level",
            "calculated_at",
        ]

    def get_performance_level(self, obj):
        """Get performance level based on overall score"""
        if obj.overall_performance_score:
            score = float(obj.overall_performance_score)
            if score >= 4.5:
                return "Excellent"
            elif score >= 4.0:
                return "Very Good"
            elif score >= 3.5:
                return "Good"
            elif score >= 3.0:
                return "Satisfactory"
            else:
                return "Needs Improvement"
        return "Not Evaluated"


class SystemHealthMetricsSerializer(serializers.ModelSerializer):
    """Serializer for SystemHealthMetrics model"""

    overall_status = serializers.SerializerMethodField()
    storage_usage_percentage = serializers.SerializerMethodField()

    class Meta:
        model = SystemHealthMetrics
        fields = [
            "id",
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
            "storage_usage_percentage",
            "overall_status",
        ]

    def get_overall_status(self, obj):
        """Determine overall system status"""
        if (
            obj.avg_response_time_ms < 500
            and obj.error_rate < 1
            and obj.cache_hit_rate > 80
        ):
            return "healthy"
        elif obj.error_rate > 5 or obj.avg_response_time_ms > 2000:
            return "critical"
        else:
            return "warning"

    def get_storage_usage_percentage(self, obj):
        """Calculate storage usage percentage"""
        total_storage = obj.storage_used_gb + obj.storage_available_gb
        if total_storage > 0:
            return round(float(obj.storage_used_gb / total_storage * 100), 2)
        return 0


class AnalyticsCalculationSerializer(serializers.Serializer):
    """Serializer for analytics calculation requests"""

    TYPE_CHOICES = [
        ("all", "All Analytics"),
        ("student", "Student Performance"),
        ("class", "Class Performance"),
        ("attendance", "Attendance"),
        ("financial", "Financial"),
        ("teacher", "Teacher Performance"),
    ]

    type = serializers.ChoiceField(choices=TYPE_CHOICES, default="all")
    force = serializers.BooleanField(default=False)
    academic_year_id = serializers.IntegerField(required=False)
    term_id = serializers.IntegerField(required=False)


class DashboardDataSerializer(serializers.Serializer):
    """Serializer for dashboard data"""

    user_role = serializers.CharField()
    current_time = serializers.DateTimeField()
    current_academic_year = serializers.CharField(allow_null=True)
    current_term = serializers.CharField(allow_null=True)
    total_students = serializers.IntegerField()
    total_teachers = serializers.IntegerField()
    total_classes = serializers.IntegerField()

    # Role-specific fields
    financial_summary = serializers.DictField(required=False)
    performance_summary = serializers.DictField(required=False)
    system_health = serializers.DictField(required=False)
    classes_taught = serializers.IntegerField(required=False)
    subjects_taught = serializers.IntegerField(required=False)
    children_count = serializers.IntegerField(required=False)
    current_class = serializers.CharField(required=False, allow_null=True)
    latest_performance = serializers.DictField(required=False, allow_null=True)
