"""
School Management System - Exams Models
File: src/exams/models.py
"""

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.contrib.auth import get_user_model
from django.utils import timezone
from decimal import Decimal
import uuid

User = get_user_model()


class ExamType(models.Model):
    """
    Types of examinations (Mid-term, Final, Quiz, Continuous Assessment)
    """

    FREQUENCY_CHOICES = [
        ("DAILY", "Daily"),
        ("WEEKLY", "Weekly"),
        ("MONTHLY", "Monthly"),
        ("TERMLY", "Termly"),
        ("YEARLY", "Yearly"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    contribution_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Percentage contribution to final grade",
    )
    is_term_based = models.BooleanField(default=True)
    frequency = models.CharField(
        max_length=20, choices=FREQUENCY_CHOICES, default="TERMLY"
    )
    max_attempts = models.PositiveIntegerField(default=1)
    is_online = models.BooleanField(default=False)
    duration_minutes = models.PositiveIntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "exam_types"
        ordering = ["contribution_percentage", "name"]

    def __str__(self):
        return f"{self.name} ({self.contribution_percentage}%)"


class Exam(models.Model):
    """
    Main exam instances (e.g., "Mid-term Exam March 2024")
    """

    STATUS_CHOICES = [
        ("DRAFT", "Draft"),
        ("SCHEDULED", "Scheduled"),
        ("ONGOING", "Ongoing"),
        ("COMPLETED", "Completed"),
        ("CANCELLED", "Cancelled"),
        ("POSTPONED", "Postponed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    exam_type = models.ForeignKey(
        ExamType, on_delete=models.CASCADE, related_name="exams"
    )
    academic_year = models.ForeignKey(
        "academics.AcademicYear", on_delete=models.CASCADE, related_name="exams"
    )
    term = models.ForeignKey(
        "academics.Term", on_delete=models.CASCADE, related_name="exams"
    )
    start_date = models.DateField()
    end_date = models.DateField()
    description = models.TextField(blank=True)
    instructions = models.TextField(
        blank=True, help_text="General instructions for students"
    )

    # Grading configuration
    grading_system = models.ForeignKey(
        "GradingSystem", on_delete=models.SET_NULL, null=True, blank=True
    )
    passing_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("40.00"),
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )

    # Meta information
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="created_exams"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="DRAFT")
    is_published = models.BooleanField(default=False)
    publish_results = models.BooleanField(default=False)

    # Analytics
    total_students = models.PositiveIntegerField(default=0)
    completed_count = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "exams"
        ordering = ["-start_date", "name"]
        unique_together = ["name", "academic_year", "term"]

    def __str__(self):
        return f"{self.name} - {self.term}"

    @property
    def completion_rate(self):
        if self.total_students == 0:
            return 0
        return (self.completed_count / self.total_students) * 100

    @property
    def is_active(self):
        today = timezone.now().date()
        return self.start_date <= today <= self.end_date

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValidationError("Start date cannot be after end date")


class ExamSchedule(models.Model):
    """
    Individual subject exam schedules within an exam
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name="schedules")
    class_obj = models.ForeignKey(
        "academics.Class", on_delete=models.CASCADE, related_name="exam_schedules"
    )
    subject = models.ForeignKey(
        "subjects.Subject", on_delete=models.CASCADE, related_name="exam_schedules"
    )

    # Scheduling details
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    duration_minutes = models.PositiveIntegerField()
    room = models.CharField(max_length=100, blank=True)

    # Supervision
    supervisor = models.ForeignKey(
        "teachers.Teacher",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="supervised_exams",
    )
    additional_supervisors = models.ManyToManyField(
        "teachers.Teacher", blank=True, related_name="additional_supervised_exams"
    )

    # Marking scheme
    total_marks = models.PositiveIntegerField()
    passing_marks = models.PositiveIntegerField()

    # Instructions
    special_instructions = models.TextField(blank=True)
    materials_allowed = models.TextField(
        blank=True, help_text="Calculator, formula sheet, etc."
    )

    # Status
    is_active = models.BooleanField(default=True)
    is_completed = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "exam_schedules"
        ordering = ["date", "start_time"]
        unique_together = ["exam", "class_obj", "subject"]

    def __str__(self):
        return f"{self.exam.name} - {self.subject.name} - {self.class_obj}"

    @property
    def duration_hours(self):
        return self.duration_minutes / 60

    @property
    def passing_percentage(self):
        return (self.passing_marks / self.total_marks) * 100

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.start_time and self.end_time and self.start_time >= self.end_time:
            raise ValidationError("Start time must be before end time")
        if (
            self.passing_marks
            and self.total_marks
            and self.passing_marks > self.total_marks
        ):
            raise ValidationError("Passing marks cannot exceed total marks")


class StudentExamResult(models.Model):
    """
    Individual student results for exam schedules
    """

    GRADE_CHOICES = [
        ("A+", "A+ (90-100)"),
        ("A", "A (80-89)"),
        ("B+", "B+ (70-79)"),
        ("B", "B (60-69)"),
        ("C+", "C+ (50-59)"),
        ("C", "C (40-49)"),
        ("D", "D (30-39)"),
        ("F", "F (0-29)"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey(
        "students.Student", on_delete=models.CASCADE, related_name="exam_results"
    )
    exam_schedule = models.ForeignKey(
        ExamSchedule, on_delete=models.CASCADE, related_name="student_results"
    )
    term = models.ForeignKey(
        "academics.Term", on_delete=models.CASCADE, related_name="exam_results"
    )

    # Scores
    marks_obtained = models.DecimalField(
        max_digits=6, decimal_places=2, validators=[MinValueValidator(0)]
    )
    percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    grade = models.CharField(max_length=2, choices=GRADE_CHOICES)
    grade_point = models.DecimalField(
        max_digits=3, decimal_places=2, null=True, blank=True
    )

    # Status
    is_pass = models.BooleanField()
    is_absent = models.BooleanField(default=False)
    is_exempted = models.BooleanField(default=False)

    # Comments
    remarks = models.TextField(blank=True)
    teacher_comments = models.TextField(blank=True)

    # Ranking
    class_rank = models.PositiveIntegerField(null=True, blank=True)
    grade_rank = models.PositiveIntegerField(null=True, blank=True)

    # Meta
    entered_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="entered_results"
    )
    entry_date = models.DateTimeField(auto_now_add=True)
    last_modified_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="modified_results"
    )
    last_modified_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "student_exam_results"
        ordering = ["-percentage", "student__last_name"]
        unique_together = ["student", "exam_schedule"]

    def __str__(self):
        return f"{self.student} - {self.exam_schedule.subject.name} - {self.marks_obtained}/{self.exam_schedule.total_marks}"

    def save(self, *args, **kwargs):
        # Auto-calculate percentage
        if self.marks_obtained is not None and self.exam_schedule:
            self.percentage = (
                self.marks_obtained / self.exam_schedule.total_marks
            ) * 100

        # Auto-determine pass/fail
        if self.exam_schedule:
            self.is_pass = (
                self.marks_obtained >= self.exam_schedule.passing_marks
                and not self.is_absent
            )

        # Auto-assign grade based on percentage
        self.grade = self._calculate_grade()

        super().save(*args, **kwargs)

    def _calculate_grade(self):
        """Calculate letter grade based on percentage"""
        if self.is_absent or self.is_exempted:
            return "F"

        percentage = float(self.percentage)
        if percentage >= 90:
            return "A+"
        elif percentage >= 80:
            return "A"
        elif percentage >= 70:
            return "B+"
        elif percentage >= 60:
            return "B"
        elif percentage >= 50:
            return "C+"
        elif percentage >= 40:
            return "C"
        elif percentage >= 30:
            return "D"
        else:
            return "F"


class GradingSystem(models.Model):
    """
    Configurable grading systems for different academic years
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    academic_year = models.ForeignKey(
        "academics.AcademicYear",
        on_delete=models.CASCADE,
        related_name="grading_systems",
    )
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "grading_systems"
        unique_together = ["academic_year", "name"]

    def __str__(self):
        return f"{self.name} - {self.academic_year}"


class GradeScale(models.Model):
    """
    Individual grade definitions within a grading system
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    grading_system = models.ForeignKey(
        GradingSystem, on_delete=models.CASCADE, related_name="grade_scales"
    )
    grade_name = models.CharField(max_length=5)  # A+, A, B+, etc.
    min_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    max_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    grade_point = models.DecimalField(max_digits=3, decimal_places=2)
    description = models.CharField(max_length=100, blank=True)
    color_code = models.CharField(
        max_length=7, blank=True, help_text="Hex color code for UI"
    )

    class Meta:
        db_table = "grade_scales"
        ordering = ["-min_percentage"]
        unique_together = ["grading_system", "grade_name"]

    def __str__(self):
        return f"{self.grade_name} ({self.min_percentage}-{self.max_percentage}%)"


class ReportCard(models.Model):
    """
    Consolidated report cards for students per term
    """

    STATUS_CHOICES = [
        ("DRAFT", "Draft"),
        ("PUBLISHED", "Published"),
        ("ARCHIVED", "Archived"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey(
        "students.Student", on_delete=models.CASCADE, related_name="report_cards"
    )
    class_obj = models.ForeignKey(
        "academics.Class", on_delete=models.CASCADE, related_name="report_cards"
    )
    academic_year = models.ForeignKey(
        "academics.AcademicYear", on_delete=models.CASCADE, related_name="report_cards"
    )
    term = models.ForeignKey(
        "academics.Term", on_delete=models.CASCADE, related_name="report_cards"
    )

    # Aggregate scores
    total_marks = models.PositiveIntegerField()
    marks_obtained = models.DecimalField(max_digits=8, decimal_places=2)
    percentage = models.DecimalField(max_digits=5, decimal_places=2)
    grade = models.CharField(max_length=2)
    grade_point_average = models.DecimalField(max_digits=4, decimal_places=2)

    # Rankings
    class_rank = models.PositiveIntegerField()
    class_size = models.PositiveIntegerField()
    grade_rank = models.PositiveIntegerField(null=True, blank=True)
    grade_size = models.PositiveIntegerField(null=True, blank=True)

    # Attendance
    attendance_percentage = models.DecimalField(max_digits=5, decimal_places=2)
    days_present = models.PositiveIntegerField()
    days_absent = models.PositiveIntegerField()
    total_days = models.PositiveIntegerField()

    # Comments
    class_teacher_remarks = models.TextField(blank=True)
    principal_remarks = models.TextField(blank=True)
    achievements = models.TextField(blank=True)
    areas_for_improvement = models.TextField(blank=True)

    # Status
    generation_date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="DRAFT")
    published_date = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "report_cards"
        ordering = ["-academic_year__start_date", "-term__term_number", "class_rank"]
        unique_together = ["student", "academic_year", "term"]

    def __str__(self):
        return f"{self.student} - {self.term} - Rank {self.class_rank}"

    @property
    def rank_suffix(self):
        """Return rank with appropriate suffix (1st, 2nd, 3rd, etc.)"""
        rank = self.class_rank
        if 10 <= rank % 100 <= 20:
            suffix = "th"
        else:
            suffix = {1: "st", 2: "nd", 3: "rd"}.get(rank % 10, "th")
        return f"{rank}{suffix}"


class ExamQuestion(models.Model):
    """
    Question bank for online exams
    """

    QUESTION_TYPES = [
        ("MCQ", "Multiple Choice"),
        ("TF", "True/False"),
        ("SA", "Short Answer"),
        ("LA", "Long Answer"),
        ("FB", "Fill in the Blanks"),
        ("ESSAY", "Essay"),
    ]

    DIFFICULTY_LEVELS = [
        ("EASY", "Easy"),
        ("MEDIUM", "Medium"),
        ("HARD", "Hard"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    subject = models.ForeignKey(
        "subjects.Subject", on_delete=models.CASCADE, related_name="exam_questions"
    )
    grade = models.ForeignKey(
        "academics.Grade", on_delete=models.CASCADE, related_name="exam_questions"
    )

    question_text = models.TextField()
    question_type = models.CharField(max_length=10, choices=QUESTION_TYPES)
    difficulty_level = models.CharField(max_length=10, choices=DIFFICULTY_LEVELS)
    marks = models.PositiveIntegerField(default=1)

    # For MCQ questions
    options = models.JSONField(
        blank=True, null=True, help_text="Array of options for MCQ"
    )
    correct_answer = models.TextField(help_text="Correct answer or answer key")
    explanation = models.TextField(blank=True)

    # Categorization
    topic = models.CharField(max_length=200, blank=True)
    learning_objective = models.CharField(max_length=200, blank=True)

    # Meta
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="created_questions"
    )
    is_active = models.BooleanField(default=True)
    usage_count = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "exam_questions"
        ordering = ["subject", "difficulty_level", "topic"]

    def __str__(self):
        return f"{self.subject.name} - {self.question_type} - {self.difficulty_level}"


class OnlineExam(models.Model):
    """
    Online exam instances with question assignments
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    exam_schedule = models.OneToOneField(
        ExamSchedule, on_delete=models.CASCADE, related_name="online_exam"
    )
    questions = models.ManyToManyField(ExamQuestion, through="OnlineExamQuestion")

    # Configuration
    time_limit_minutes = models.PositiveIntegerField()
    max_attempts = models.PositiveIntegerField(default=1)
    shuffle_questions = models.BooleanField(default=True)
    shuffle_options = models.BooleanField(default=True)
    show_results_immediately = models.BooleanField(default=False)

    # Proctoring
    enable_proctoring = models.BooleanField(default=False)
    webcam_required = models.BooleanField(default=False)
    fullscreen_required = models.BooleanField(default=True)

    # Access control
    access_code = models.CharField(max_length=20, blank=True)
    ip_restrictions = models.TextField(
        blank=True, help_text="Comma-separated IP addresses"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "online_exams"

    def __str__(self):
        return f"Online: {self.exam_schedule}"


class OnlineExamQuestion(models.Model):
    """
    Junction table for online exam questions with ordering
    """

    online_exam = models.ForeignKey(OnlineExam, on_delete=models.CASCADE)
    question = models.ForeignKey(ExamQuestion, on_delete=models.CASCADE)
    order = models.PositiveIntegerField()
    marks = models.PositiveIntegerField()  # Can override question default marks

    class Meta:
        db_table = "online_exam_questions"
        ordering = ["order"]
        unique_together = ["online_exam", "question"]


class StudentOnlineExamAttempt(models.Model):
    """
    Student attempts at online exams
    """

    STATUS_CHOICES = [
        ("STARTED", "Started"),
        ("IN_PROGRESS", "In Progress"),
        ("SUBMITTED", "Submitted"),
        ("TIMED_OUT", "Timed Out"),
        ("CANCELLED", "Cancelled"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey(
        "students.Student",
        on_delete=models.CASCADE,
        related_name="online_exam_attempts",
    )
    online_exam = models.ForeignKey(
        OnlineExam, on_delete=models.CASCADE, related_name="student_attempts"
    )
    attempt_number = models.PositiveIntegerField()

    # Timing
    start_time = models.DateTimeField(auto_now_add=True)
    submit_time = models.DateTimeField(null=True, blank=True)
    time_remaining_seconds = models.PositiveIntegerField(null=True, blank=True)

    # Responses
    responses = models.JSONField(
        default=dict, help_text="Question ID to answer mapping"
    )

    # Scoring
    total_marks = models.PositiveIntegerField(default=0)
    marks_obtained = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    auto_graded_marks = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    manual_graded_marks = models.DecimalField(max_digits=6, decimal_places=2, default=0)

    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="STARTED")
    is_graded = models.BooleanField(default=False)

    # Proctoring data
    proctoring_data = models.JSONField(null=True, blank=True)
    violation_count = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "student_online_exam_attempts"
        ordering = ["-start_time"]
        unique_together = ["student", "online_exam", "attempt_number"]

    def __str__(self):
        return f"{self.student} - {self.online_exam} - Attempt {self.attempt_number}"
