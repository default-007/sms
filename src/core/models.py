from django.db import models
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
import json

User = get_user_model()


class SystemSetting(models.Model):
    """System-wide configuration settings"""

    SETTING_CATEGORIES = [
        ("academic", "Academic"),
        ("financial", "Financial"),
        ("system", "System"),
        ("communication", "Communication"),
        ("security", "Security"),
        ("analytics", "Analytics"),
    ]

    DATA_TYPES = [
        ("string", "String"),
        ("integer", "Integer"),
        ("float", "Float"),
        ("boolean", "Boolean"),
        ("json", "JSON"),
        ("text", "Text"),
    ]

    setting_key = models.CharField(max_length=100, unique=True, db_index=True)
    setting_value = models.TextField()
    data_type = models.CharField(max_length=20, choices=DATA_TYPES, default="string")
    category = models.CharField(
        max_length=20, choices=SETTING_CATEGORIES, default="system"
    )
    description = models.TextField(blank=True)
    is_editable = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True
    )

    class Meta:
        ordering = ["category", "setting_key"]
        indexes = [
            models.Index(fields=["category"]),
            models.Index(fields=["setting_key"]),
        ]

    def __str__(self):
        return f"{self.setting_key}: {self.get_typed_value()}"

    def get_typed_value(self):
        """Return the setting value in its proper data type"""
        if self.data_type == "boolean":
            return self.setting_value.lower() in ("true", "1", "yes", "on")
        elif self.data_type == "integer":
            try:
                return int(self.setting_value)
            except (ValueError, TypeError):
                return 0
        elif self.data_type == "float":
            try:
                return float(self.setting_value)
            except (ValueError, TypeError):
                return 0.0
        elif self.data_type == "json":
            try:
                return json.loads(self.setting_value)
            except (json.JSONDecodeError, TypeError):
                return {}
        return self.setting_value

    def set_typed_value(self, value):
        """Set the setting value from a typed value"""
        if self.data_type == "json":
            self.setting_value = json.dumps(value)
        elif self.data_type == "boolean":
            self.setting_value = str(bool(value)).lower()
        else:
            self.setting_value = str(value)


class AuditLog(models.Model):
    """Comprehensive audit logging for all system activities"""

    ACTION_CHOICES = [
        ("create", "Create"),
        ("update", "Update"),
        ("delete", "Delete"),
        ("login", "Login"),
        ("logout", "Logout"),
        ("view", "View"),
        ("export", "Export"),
        ("import", "Import"),
        ("password_change", "Password Change"),
        ("permission_change", "Permission Change"),
        ("bulk_action", "Bulk Action"),
        ("system_action", "System Action"),
    ]

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    content_type = models.ForeignKey(
        ContentType, on_delete=models.CASCADE, null=True, blank=True
    )
    object_id = models.PositiveIntegerField(null=True, blank=True)
    content_object = GenericForeignKey("content_type", "object_id")

    # Data tracking
    data_before = models.JSONField(null=True, blank=True)
    data_after = models.JSONField(null=True, blank=True)

    # Session information
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    session_key = models.CharField(max_length=40, blank=True)

    # Additional context
    description = models.TextField(blank=True)
    module_name = models.CharField(max_length=50, blank=True)
    view_name = models.CharField(max_length=100, blank=True)

    # Metadata
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    duration_ms = models.PositiveIntegerField(null=True, blank=True)  # Request duration

    class Meta:
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["user", "-timestamp"]),
            models.Index(fields=["action", "-timestamp"]),
            models.Index(fields=["content_type", "-timestamp"]),
            models.Index(fields=["module_name", "-timestamp"]),
        ]

    def __str__(self):
        user_str = self.user.username if self.user else "System"
        object_str = str(self.content_object) if self.content_object else "N/A"
        return f"{user_str} {self.action} {object_str} at {self.timestamp}"


# Analytics Models
class StudentPerformanceAnalytics(models.Model):
    """Aggregated student performance analytics"""

    IMPROVEMENT_TRENDS = [
        ("improving", "Improving"),
        ("declining", "Declining"),
        ("stable", "Stable"),
        ("fluctuating", "Fluctuating"),
    ]

    student = models.ForeignKey("students.Student", on_delete=models.CASCADE)
    academic_year = models.ForeignKey(
        "academics.AcademicYear", on_delete=models.CASCADE
    )
    term = models.ForeignKey("academics.Term", on_delete=models.CASCADE)
    subject = models.ForeignKey(
        "subjects.Subject", on_delete=models.CASCADE, null=True, blank=True
    )

    # Performance metrics
    average_marks = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    highest_marks = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    lowest_marks = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    grade_point = models.DecimalField(
        max_digits=4, decimal_places=2, null=True, blank=True
    )

    # Attendance metrics
    attendance_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        null=True,
        blank=True,
    )

    # Assignment metrics
    assignment_completion_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        null=True,
        blank=True,
    )
    assignments_submitted = models.PositiveIntegerField(default=0)
    assignments_on_time = models.PositiveIntegerField(default=0)

    # Rankings
    ranking_in_class = models.PositiveIntegerField(null=True, blank=True)
    ranking_in_grade = models.PositiveIntegerField(null=True, blank=True)
    ranking_in_section = models.PositiveIntegerField(null=True, blank=True)

    # Trends
    improvement_trend = models.CharField(
        max_length=20, choices=IMPROVEMENT_TRENDS, null=True, blank=True
    )
    trend_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )

    # Metadata
    calculated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ["student", "academic_year", "term", "subject"]
        ordering = ["-academic_year", "-term", "student"]
        indexes = [
            models.Index(fields=["student", "academic_year", "term"]),
            models.Index(fields=["academic_year", "term", "subject"]),
            models.Index(fields=["calculated_at"]),
        ]

    def __str__(self):
        subject_str = f" - {self.subject.name}" if self.subject else ""
        return f"{self.student} - {self.term}{subject_str}"


class ClassPerformanceAnalytics(models.Model):
    """Aggregated class performance analytics"""

    class_instance = models.ForeignKey("academics.Class", on_delete=models.CASCADE)
    academic_year = models.ForeignKey(
        "academics.AcademicYear", on_delete=models.CASCADE
    )
    term = models.ForeignKey("academics.Term", on_delete=models.CASCADE)
    subject = models.ForeignKey(
        "subjects.Subject", on_delete=models.CASCADE, null=True, blank=True
    )

    # Performance metrics
    class_average = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    highest_score = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    lowest_score = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    median_score = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    standard_deviation = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )

    # Student distribution
    total_students = models.PositiveIntegerField(default=0)
    students_above_average = models.PositiveIntegerField(default=0)
    students_below_average = models.PositiveIntegerField(default=0)
    students_at_risk = models.PositiveIntegerField(default=0)  # Below 40%

    # Pass/Fail metrics
    pass_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        null=True,
        blank=True,
    )
    distinction_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        null=True,
        blank=True,
    )

    # Comparison metrics
    grade_ranking = models.PositiveIntegerField(
        null=True, blank=True
    )  # Rank within grade
    section_ranking = models.PositiveIntegerField(
        null=True, blank=True
    )  # Rank within section

    # Metadata
    calculated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ["class_instance", "academic_year", "term", "subject"]
        ordering = ["-academic_year", "-term", "class_instance"]
        indexes = [
            models.Index(fields=["class_instance", "academic_year", "term"]),
            models.Index(fields=["academic_year", "term", "subject"]),
            models.Index(fields=["calculated_at"]),
        ]

    def __str__(self):
        subject_str = f" - {self.subject.name}" if self.subject else ""
        return f"{self.class_instance} - {self.term}{subject_str}"


class AttendanceAnalytics(models.Model):
    """Attendance analytics for different entities"""

    ENTITY_TYPES = [
        ("student", "Student"),
        ("class", "Class"),
        ("grade", "Grade"),
        ("section", "Section"),
        ("teacher", "Teacher"),
    ]

    entity_type = models.CharField(max_length=20, choices=ENTITY_TYPES)
    entity_id = models.PositiveIntegerField()
    entity_name = models.CharField(max_length=200)  # Denormalized for performance

    academic_year = models.ForeignKey(
        "academics.AcademicYear", on_delete=models.CASCADE
    )
    term = models.ForeignKey(
        "academics.Term", on_delete=models.CASCADE, null=True, blank=True
    )
    month = models.PositiveIntegerField(
        null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(12)]
    )
    year = models.PositiveIntegerField(null=True, blank=True)

    # Attendance metrics
    total_days = models.PositiveIntegerField(default=0)
    present_days = models.PositiveIntegerField(default=0)
    absent_days = models.PositiveIntegerField(default=0)
    late_days = models.PositiveIntegerField(default=0)
    excused_days = models.PositiveIntegerField(default=0)

    attendance_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        default=0,
    )

    # Patterns
    consecutive_absences = models.PositiveIntegerField(default=0)
    frequent_late_arrivals = models.BooleanField(default=False)
    attendance_trend = models.CharField(
        max_length=20,
        choices=[
            ("improving", "Improving"),
            ("declining", "Declining"),
            ("stable", "Stable"),
        ],
        null=True,
        blank=True,
    )

    # Metadata
    calculated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [
            "entity_type",
            "entity_id",
            "academic_year",
            "term",
            "month",
            "year",
        ]
        ordering = ["-academic_year", "-term", "entity_type", "entity_name"]
        indexes = [
            models.Index(fields=["entity_type", "entity_id"]),
            models.Index(fields=["academic_year", "term"]),
            models.Index(fields=["attendance_percentage"]),
            models.Index(fields=["calculated_at"]),
        ]

    def __str__(self):
        period = f"{self.term}" if self.term else f"{self.month}/{self.year}"
        return f"{self.entity_name} ({self.entity_type}) - {period}: {self.attendance_percentage}%"


class FinancialAnalytics(models.Model):

    academic_year = models.ForeignKey(
        "academics.AcademicYear", on_delete=models.CASCADE
    )
    term = models.ForeignKey(
        "academics.Term", on_delete=models.CASCADE, null=True, blank=True
    )
    section = models.ForeignKey(
        "academics.Section", on_delete=models.CASCADE, null=True, blank=True
    )
    grade = models.ForeignKey(
        "academics.Grade", on_delete=models.CASCADE, null=True, blank=True
    )
    # fee_category = models.ForeignKey("finance.FeeCategory", on_delete=models.CASCADE, null=True, blank=True)

    # Revenue metrics
    total_expected_revenue = models.DecimalField(
        max_digits=12, decimal_places=2, default=0
    )
    total_collected_revenue = models.DecimalField(
        max_digits=12, decimal_places=2, default=0
    )
    total_outstanding = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_advance_payments = models.DecimalField(
        max_digits=12, decimal_places=2, default=0
    )

    # Collection metrics
    collection_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        default=0,
    )
    on_time_collection_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        default=0,
    )

    # Student metrics
    total_students = models.PositiveIntegerField(default=0)
    students_paid_full = models.PositiveIntegerField(default=0)
    students_paid_partial = models.PositiveIntegerField(default=0)
    students_with_outstanding = models.PositiveIntegerField(default=0)
    students_with_overdue = models.PositiveIntegerField(default=0)

    # Scholarship metrics
    total_scholarships_awarded = models.DecimalField(
        max_digits=12, decimal_places=2, default=0
    )
    scholarship_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        default=0,
    )

    # Trends
    revenue_growth = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    collection_trend = models.CharField(
        max_length=20,
        choices=[
            ("improving", "Improving"),
            ("declining", "Declining"),
            ("stable", "Stable"),
        ],
        null=True,
        blank=True,
    )

    # Metadata
    month = models.PositiveIntegerField(
        null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(12)]
    )
    year = models.PositiveIntegerField(null=True, blank=True)
    calculated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [
            "academic_year",
            "term",
            "section",
            "grade",
            "fee_category",
            "month",
            "year",
        ]
        ordering = ["-academic_year", "-term", "section", "grade"]
        indexes = [
            models.Index(fields=["academic_year", "term"]),
            models.Index(fields=["section", "grade"]),
            models.Index(fields=["collection_rate"]),
            models.Index(fields=["calculated_at"]),
        ]

    def __str__(self):
        filters = []
        if self.section:
            filters.append(str(self.section))
        if self.grade:
            filters.append(str(self.grade))
        if self.fee_category:
            filters.append(str(self.fee_category))
        filter_str = " - " + " | ".join(filters) if filters else ""

        return f"Financial Analytics {self.academic_year} {self.term}{filter_str}"


class TeacherPerformanceAnalytics(models.Model):
    """Teacher performance analytics"""

    teacher = models.ForeignKey("teachers.Teacher", on_delete=models.CASCADE)
    academic_year = models.ForeignKey(
        "academics.AcademicYear", on_delete=models.CASCADE
    )
    term = models.ForeignKey("academics.Term", on_delete=models.CASCADE)

    # Teaching load
    classes_taught = models.PositiveIntegerField(default=0)
    subjects_taught = models.PositiveIntegerField(default=0)
    total_students = models.PositiveIntegerField(default=0)
    teaching_hours_per_week = models.DecimalField(
        max_digits=5, decimal_places=2, default=0
    )

    # Student performance correlation
    average_class_performance = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    students_above_average = models.PositiveIntegerField(default=0)
    students_below_average = models.PositiveIntegerField(default=0)
    improvement_rate = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )

    # Attendance and punctuality
    attendance_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        default=100,
    )
    punctuality_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        default=100,
    )

    # Assignment and assessment
    assignments_given = models.PositiveIntegerField(default=0)
    assignments_graded = models.PositiveIntegerField(default=0)
    assignments_graded_on_time = models.PositiveIntegerField(default=0)
    average_grading_time_days = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )

    # Professional development
    training_hours_completed = models.DecimalField(
        max_digits=5, decimal_places=2, default=0
    )
    certifications_earned = models.PositiveIntegerField(default=0)

    # Evaluation scores
    peer_evaluation_score = models.DecimalField(
        max_digits=4, decimal_places=2, null=True, blank=True
    )
    student_feedback_score = models.DecimalField(
        max_digits=4, decimal_places=2, null=True, blank=True
    )
    parent_feedback_score = models.DecimalField(
        max_digits=4, decimal_places=2, null=True, blank=True
    )
    overall_performance_score = models.DecimalField(
        max_digits=4, decimal_places=2, null=True, blank=True
    )

    # Metadata
    calculated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ["teacher", "academic_year", "term"]
        ordering = ["-academic_year", "-term", "teacher"]
        indexes = [
            models.Index(fields=["teacher", "academic_year", "term"]),
            models.Index(fields=["academic_year", "term"]),
            models.Index(fields=["overall_performance_score"]),
            models.Index(fields=["calculated_at"]),
        ]

    def __str__(self):
        return f"{self.teacher} - {self.term} Performance"


class SystemHealthMetrics(models.Model):
    """System health and performance metrics"""

    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    # Database metrics
    db_connection_count = models.PositiveIntegerField(default=0)
    db_query_count = models.PositiveIntegerField(default=0)
    avg_query_time_ms = models.DecimalField(max_digits=8, decimal_places=2, default=0)

    # Cache metrics
    cache_hit_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    cache_memory_usage_mb = models.DecimalField(
        max_digits=10, decimal_places=2, default=0
    )

    # Application metrics
    active_users = models.PositiveIntegerField(default=0)
    requests_per_minute = models.PositiveIntegerField(default=0)
    avg_response_time_ms = models.DecimalField(
        max_digits=8, decimal_places=2, default=0
    )
    error_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    # Background task metrics
    pending_tasks = models.PositiveIntegerField(default=0)
    failed_tasks = models.PositiveIntegerField(default=0)
    completed_tasks = models.PositiveIntegerField(default=0)

    # Storage metrics
    storage_used_gb = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    storage_available_gb = models.DecimalField(
        max_digits=10, decimal_places=2, default=0
    )

    class Meta:
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["-timestamp"]),
        ]

    def __str__(self):
        return f"System Health - {self.timestamp.strftime('%Y-%m-%d %H:%M')}"
