# api/serializers.py
from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType

from ..models import (
    SystemSetting,
    AuditLog,
    StudentPerformanceAnalytics,
    ClassPerformanceAnalytics,
    AttendanceAnalytics,
    FinancialAnalytics,
    TeacherPerformanceAnalytics,
    SystemHealthMetrics,
)

User = get_user_model()


class SystemSettingSerializer(serializers.ModelSerializer):
    """Serializer for system settings"""

    typed_value = serializers.SerializerMethodField()
    category_display = serializers.CharField(
        source="get_category_display", read_only=True
    )
    data_type_display = serializers.CharField(
        source="get_data_type_display", read_only=True
    )
    updated_by_name = serializers.CharField(
        source="updated_by.get_full_name", read_only=True
    )

    class Meta:
        model = SystemSetting
        fields = [
            "id",
            "setting_key",
            "setting_value",
            "typed_value",
            "data_type",
            "data_type_display",
            "category",
            "category_display",
            "description",
            "is_editable",
            "created_at",
            "updated_at",
            "updated_by",
            "updated_by_name",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "updated_by"]

    def get_typed_value(self, obj):
        """Return the properly typed value"""
        return obj.get_typed_value()

    def validate_setting_key(self, value):
        """Validate setting key format"""
        if not value.replace("_", "").replace(".", "").replace("-", "").isalnum():
            raise serializers.ValidationError(
                "Setting key can only contain alphanumeric characters, dots, hyphens, and underscores"
            )
        return value

    def update(self, instance, validated_data):
        """Custom update to handle typed values"""
        # Set the typed value using the model's method
        if "setting_value" in validated_data:
            instance.set_typed_value(validated_data["setting_value"])
            validated_data.pop("setting_value")

        return super().update(instance, validated_data)


class SystemSettingUpdateSerializer(serializers.Serializer):
    """Serializer for updating system setting values"""

    value = serializers.JSONField()

    def validate_value(self, value):
        """Validate the value based on the setting's data type"""
        setting = self.context.get("setting")
        if not setting:
            return value

        if setting.data_type == "boolean" and not isinstance(value, bool):
            raise serializers.ValidationError("Value must be a boolean")
        elif setting.data_type == "integer" and not isinstance(value, int):
            raise serializers.ValidationError("Value must be an integer")
        elif setting.data_type == "float" and not isinstance(value, (int, float)):
            raise serializers.ValidationError("Value must be a number")
        elif setting.data_type == "string" and not isinstance(value, str):
            raise serializers.ValidationError("Value must be a string")
        elif setting.data_type == "json" and not isinstance(value, (dict, list)):
            raise serializers.ValidationError("Value must be a JSON object or array")

        return value


class AuditLogSerializer(serializers.ModelSerializer):
    """Serializer for audit logs"""

    user_name = serializers.CharField(source="user.get_full_name", read_only=True)
    user_username = serializers.CharField(source="user.username", read_only=True)
    action_display = serializers.CharField(source="get_action_display", read_only=True)
    content_type_name = serializers.CharField(
        source="content_type.name", read_only=True
    )
    object_representation = serializers.SerializerMethodField()
    duration_formatted = serializers.SerializerMethodField()

    class Meta:
        model = AuditLog
        fields = [
            "id",
            "user",
            "user_name",
            "user_username",
            "action",
            "action_display",
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
            "duration_formatted",
        ]
        read_only_fields = fields  # All fields are read-only for audit logs

    def get_object_representation(self, obj):
        """Get string representation of the content object"""
        if obj.content_object:
            return str(obj.content_object)
        return None

    def get_duration_formatted(self, obj):
        """Format duration in human-readable form"""
        if obj.duration_ms:
            if obj.duration_ms < 1000:
                return f"{obj.duration_ms}ms"
            else:
                return f"{obj.duration_ms / 1000:.2f}s"
        return None


class StudentPerformanceAnalyticsSerializer(serializers.ModelSerializer):
    """Serializer for student performance analytics"""

    student_name = serializers.CharField(
        source="student.user.get_full_name", read_only=True
    )
    student_admission_number = serializers.CharField(
        source="student.admission_number", read_only=True
    )
    class_name = serializers.CharField(source="student.current_class", read_only=True)
    academic_year_name = serializers.CharField(
        source="academic_year.name", read_only=True
    )
    term_name = serializers.CharField(source="term.name", read_only=True)
    subject_name = serializers.CharField(source="subject.name", read_only=True)
    improvement_trend_display = serializers.CharField(
        source="get_improvement_trend_display", read_only=True
    )

    class Meta:
        model = StudentPerformanceAnalytics
        fields = [
            "id",
            "student",
            "student_name",
            "student_admission_number",
            "class_name",
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
            "improvement_trend_display",
            "trend_percentage",
            "calculated_at",
        ]
        read_only_fields = fields


class ClassPerformanceAnalyticsSerializer(serializers.ModelSerializer):
    """Serializer for class performance analytics"""

    class_name = serializers.CharField(source="class_instance", read_only=True)
    grade_name = serializers.CharField(
        source="class_instance.grade.name", read_only=True
    )
    section_name = serializers.CharField(
        source="class_instance.grade.section.name", read_only=True
    )
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
            "class_name",
            "grade_name",
            "section_name",
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
        read_only_fields = fields


class AttendanceAnalyticsSerializer(serializers.ModelSerializer):
    """Serializer for attendance analytics"""

    entity_type_display = serializers.CharField(
        source="get_entity_type_display", read_only=True
    )
    academic_year_name = serializers.CharField(
        source="academic_year.name", read_only=True
    )
    term_name = serializers.CharField(source="term.name", read_only=True)
    attendance_trend_display = serializers.CharField(
        source="get_attendance_trend_display", read_only=True
    )

    class Meta:
        model = AttendanceAnalytics
        fields = [
            "id",
            "entity_type",
            "entity_type_display",
            "entity_id",
            "entity_name",
            "academic_year",
            "academic_year_name",
            "term",
            "term_name",
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
            "attendance_trend_display",
            "calculated_at",
        ]
        read_only_fields = fields


class FinancialAnalyticsSerializer(serializers.ModelSerializer):
    """Serializer for financial analytics"""

    academic_year_name = serializers.CharField(
        source="academic_year.name", read_only=True
    )
    term_name = serializers.CharField(source="term.name", read_only=True)
    section_name = serializers.CharField(source="section.name", read_only=True)
    grade_name = serializers.CharField(source="grade.name", read_only=True)
    fee_category_name = serializers.CharField(
        source="fee_category.name", read_only=True
    )
    collection_trend_display = serializers.CharField(
        source="get_collection_trend_display", read_only=True
    )

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
            "collection_trend_display",
            "month",
            "year",
            "calculated_at",
        ]
        read_only_fields = fields


class TeacherPerformanceAnalyticsSerializer(serializers.ModelSerializer):
    """Serializer for teacher performance analytics"""

    teacher_name = serializers.CharField(
        source="teacher.user.get_full_name", read_only=True
    )
    teacher_employee_id = serializers.CharField(
        source="teacher.employee_id", read_only=True
    )
    academic_year_name = serializers.CharField(
        source="academic_year.name", read_only=True
    )
    term_name = serializers.CharField(source="term.name", read_only=True)

    class Meta:
        model = TeacherPerformanceAnalytics
        fields = [
            "id",
            "teacher",
            "teacher_name",
            "teacher_employee_id",
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
            "calculated_at",
        ]
        read_only_fields = fields


class SystemHealthMetricsSerializer(serializers.ModelSerializer):
    """Serializer for system health metrics"""

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
        ]
        read_only_fields = fields

    def get_storage_usage_percentage(self, obj):
        """Calculate storage usage percentage"""
        total_storage = obj.storage_used_gb + obj.storage_available_gb
        if total_storage > 0:
            return round((obj.storage_used_gb / total_storage) * 100, 2)
        return 0


class AnalyticsSummarySerializer(serializers.Serializer):
    """Serializer for analytics summary data"""

    academic_year = serializers.CharField()
    term = serializers.CharField()

    # Student metrics
    total_students = serializers.IntegerField()
    active_students = serializers.IntegerField()
    average_performance = serializers.DecimalField(max_digits=5, decimal_places=2)
    attendance_rate = serializers.DecimalField(max_digits=5, decimal_places=2)

    # Class metrics
    total_classes = serializers.IntegerField()
    best_performing_class = serializers.CharField()
    lowest_performing_class = serializers.CharField()

    # Financial metrics
    total_revenue_expected = serializers.DecimalField(max_digits=12, decimal_places=2)
    total_revenue_collected = serializers.DecimalField(max_digits=12, decimal_places=2)
    collection_rate = serializers.DecimalField(max_digits=5, decimal_places=2)
    outstanding_amount = serializers.DecimalField(max_digits=12, decimal_places=2)

    # Teacher metrics
    total_teachers = serializers.IntegerField()
    average_teacher_performance = serializers.DecimalField(
        max_digits=4, decimal_places=2
    )


class ContentTypeSerializer(serializers.ModelSerializer):
    """Serializer for content types (for audit log filtering)"""

    class Meta:
        model = ContentType
        fields = ["id", "app_label", "model", "name"]
        read_only_fields = fields


class UserActivitySummarySerializer(serializers.Serializer):
    """Serializer for user activity summary"""

    user_id = serializers.IntegerField()
    username = serializers.CharField()
    full_name = serializers.CharField()
    total_actions = serializers.IntegerField()
    last_login = serializers.DateTimeField()
    most_common_action = serializers.CharField()
    modules_accessed = serializers.ListField(child=serializers.CharField())
    actions_by_day = serializers.DictField()


class SystemMetricsSummarySerializer(serializers.Serializer):
    """Serializer for system metrics summary"""

    current_users = serializers.IntegerField()
    total_users = serializers.IntegerField()
    database_size_mb = serializers.DecimalField(max_digits=10, decimal_places=2)
    average_response_time = serializers.DecimalField(max_digits=8, decimal_places=2)
    error_rate = serializers.DecimalField(max_digits=5, decimal_places=2)
    uptime_percentage = serializers.DecimalField(max_digits=5, decimal_places=2)
    last_backup = serializers.DateTimeField()
    pending_tasks = serializers.IntegerField()


class BulkAnalyticsCalculationSerializer(serializers.Serializer):
    """Serializer for bulk analytics calculation requests"""

    ANALYTICS_TYPES = [
        ("student", "Student Performance"),
        ("class", "Class Performance"),
        ("attendance", "Attendance"),
        ("financial", "Financial"),
        ("teacher", "Teacher Performance"),
        ("all", "All Analytics"),
    ]

    analytics_type = serializers.ChoiceField(choices=ANALYTICS_TYPES, default="all")
    academic_year_id = serializers.IntegerField(required=False)
    term_id = serializers.IntegerField(required=False)
    force_recalculate = serializers.BooleanField(default=False)

    def validate(self, data):
        """Validate the analytics calculation request"""
        if data.get("academic_year_id"):
            from academics.models import AcademicYear

            try:
                AcademicYear.objects.get(id=data["academic_year_id"])
            except AcademicYear.DoesNotExist:
                raise serializers.ValidationError("Invalid academic year ID")

        if data.get("term_id"):
            from academics.models import Term

            try:
                term = Term.objects.get(id=data["term_id"])
                if (
                    data.get("academic_year_id")
                    and term.academic_year_id != data["academic_year_id"]
                ):
                    raise serializers.ValidationError(
                        "Term does not belong to the specified academic year"
                    )
            except Term.DoesNotExist:
                raise serializers.ValidationError("Invalid term ID")

        return data
