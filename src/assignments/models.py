import os
from datetime import datetime, timedelta

from django.contrib.auth import get_user_model
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

User = get_user_model()


def assignment_attachment_path(instance, filename):
    """Generate upload path for assignment attachments"""
    return f"assignments/{instance.class_id.grade.section.name}/{instance.class_id.grade.name}/{instance.class_id.name}/{instance.subject.code}/{filename}"


def submission_attachment_path(instance, filename):
    """Generate upload path for submission attachments"""
    return f"submissions/{instance.assignment.class_id.grade.section.name}/{instance.assignment.class_id.grade.name}/{instance.assignment.class_id.name}/{instance.assignment.subject.code}/{instance.assignment.id}/{instance.student.user.username}/{filename}"


class Assignment(models.Model):
    """
    Assignment model for managing academic assignments
    """

    SUBMISSION_TYPE_CHOICES = [
        ("online", "Online"),
        ("physical", "Physical"),
        ("both", "Both Online and Physical"),
    ]

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("published", "Published"),
        ("closed", "Closed"),
        ("archived", "Archived"),
    ]

    DIFFICULTY_CHOICES = [
        ("easy", "Easy"),
        ("medium", "Medium"),
        ("hard", "Hard"),
    ]

    title = models.CharField(max_length=200)
    description = models.TextField()
    instructions = models.TextField(
        blank=True, help_text="Detailed instructions for students"
    )

    # Foreign Keys
    class_id = models.ForeignKey(
        "academics.Class", on_delete=models.CASCADE, related_name="assignments"
    )
    subject = models.ForeignKey(
        "subjects.Subject", on_delete=models.CASCADE, related_name="assignment_subject"
    )
    teacher = models.ForeignKey(
        "teachers.Teacher", on_delete=models.CASCADE, related_name="assignments_created"
    )
    term = models.ForeignKey(
        "academics.Term", on_delete=models.CASCADE, related_name="assignments"
    )

    # Assignment Details
    assigned_date = models.DateTimeField(default=timezone.now)
    due_date = models.DateTimeField()
    total_marks = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(1000)]
    )
    passing_marks = models.PositiveIntegerField(
        null=True, blank=True, help_text="Minimum marks required to pass"
    )

    # File and Submission Management
    attachment = models.FileField(
        upload_to=assignment_attachment_path,
        blank=True,
        null=True,
        help_text="Assignment file, questions, or reference material",
    )
    submission_type = models.CharField(
        max_length=10, choices=SUBMISSION_TYPE_CHOICES, default="online"
    )

    # Assignment Properties
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="draft")
    difficulty_level = models.CharField(
        max_length=10, choices=DIFFICULTY_CHOICES, default="medium"
    )

    # Settings
    allow_late_submission = models.BooleanField(default=True)
    late_penalty_percentage = models.PositiveIntegerField(
        default=10,
        validators=[MaxValueValidator(100)],
        help_text="Percentage deduction for late submissions",
    )
    max_file_size_mb = models.PositiveIntegerField(
        default=10, help_text="Maximum file size in MB for submissions"
    )
    allowed_file_types = models.CharField(
        max_length=200,
        default="pdf,doc,docx,txt",
        help_text="Comma-separated list of allowed file extensions",
    )

    # Analytics Fields
    estimated_duration_hours = models.PositiveIntegerField(
        null=True, blank=True, help_text="Estimated time to complete in hours"
    )
    learning_objectives = models.TextField(
        blank=True, help_text="Learning objectives this assignment addresses"
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    published_at = models.DateTimeField(null=True, blank=True)

    # Grading Settings
    auto_grade = models.BooleanField(
        default=False, help_text="Automatically grade based on rubric"
    )
    peer_review = models.BooleanField(
        default=False, help_text="Enable peer review for this assignment"
    )

    class Meta:
        db_table = "assignments_assignment"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["class_id", "subject", "status"]),
            models.Index(fields=["teacher", "status"]),
            models.Index(fields=["due_date"]),
            models.Index(fields=["term", "status"]),
        ]

    def __str__(self):
        return f"{self.title} - {self.class_id} ({self.subject.code})"

    @property
    def is_overdue(self):
        """Check if assignment is past due date"""
        return timezone.now() > self.due_date and self.status == "published"

    @property
    def days_until_due(self):
        """Calculate days until due date"""
        if self.due_date > timezone.now():
            return (self.due_date - timezone.now()).days
        return 0

    @property
    def submission_count(self):
        """Get total number of submissions"""
        return self.submissions.count()

    @property
    def graded_submission_count(self):
        """Get number of graded submissions"""
        return self.submissions.filter(status="graded").count()

    @property
    def average_score(self):
        """Calculate average score for graded submissions"""
        graded_submissions = self.submissions.filter(
            status="graded", marks_obtained__isnull=False
        )
        if graded_submissions.exists():
            return graded_submissions.aggregate(avg_score=models.Avg("marks_obtained"))[
                "avg_score"
            ]
        return None

    @property
    def completion_rate(self):
        """Calculate submission completion rate"""
        total_students = self.class_id.students.filter(status="active").count()
        if total_students > 0:
            return (self.submission_count / total_students) * 100
        return 0

    def save(self, *args, **kwargs):
        # Set published_at when status changes to published
        if self.status == "published" and not self.published_at:
            self.published_at = timezone.now()

        # Validate passing marks
        if self.passing_marks and self.passing_marks > self.total_marks:
            self.passing_marks = self.total_marks

        super().save(*args, **kwargs)

    def get_student_submission(self, student):
        """Get submission for a specific student"""
        try:
            return self.submissions.get(student=student)
        except AssignmentSubmission.DoesNotExist:
            return None

    def is_submitted_by_student(self, student):
        """Check if student has submitted the assignment"""
        return self.submissions.filter(student=student).exists()


class AssignmentSubmission(models.Model):
    """
    Assignment submission model for tracking student submissions
    """

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("submitted", "Submitted"),
        ("late", "Late Submission"),
        ("graded", "Graded"),
        ("returned", "Returned for Revision"),
    ]

    SUBMISSION_METHOD_CHOICES = [
        ("online", "Online Upload"),
        ("physical", "Physical Handover"),
        ("email", "Email Submission"),
    ]

    # Core Relations
    assignment = models.ForeignKey(
        Assignment, on_delete=models.CASCADE, related_name="submissions"
    )
    student = models.ForeignKey(
        "students.Student",
        on_delete=models.CASCADE,
        related_name="assignment_submissions",
    )

    # Submission Content
    content = models.TextField(blank=True, help_text="Text submission or notes")
    attachment = models.FileField(
        upload_to=submission_attachment_path,
        blank=True,
        null=True,
        help_text="Submitted file",
    )

    # Submission Details
    submission_date = models.DateTimeField(auto_now_add=True)
    submission_method = models.CharField(
        max_length=10, choices=SUBMISSION_METHOD_CHOICES, default="online"
    )
    student_remarks = models.TextField(
        blank=True, help_text="Student's notes or comments about the submission"
    )

    # Grading Information
    marks_obtained = models.PositiveIntegerField(
        null=True, blank=True, help_text="Marks awarded for this submission"
    )
    percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Percentage score calculated automatically",
    )
    grade = models.CharField(
        max_length=5, blank=True, help_text="Letter grade (A, B, C, etc.)"
    )

    # Teacher Feedback
    teacher_remarks = models.TextField(
        blank=True, help_text="Teacher's feedback and comments"
    )
    strengths = models.TextField(blank=True, help_text="What the student did well")
    improvements = models.TextField(blank=True, help_text="Areas for improvement")

    # Grading Details
    graded_by = models.ForeignKey(
        "teachers.Teacher",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="graded_submissions",
    )
    graded_at = models.DateTimeField(null=True, blank=True)

    # Status and Tracking
    status = models.CharField(
        max_length=10, choices=STATUS_CHOICES, default="submitted"
    )

    # Late Submission Handling
    is_late = models.BooleanField(default=False)
    late_penalty_applied = models.BooleanField(default=False)
    original_marks = models.PositiveIntegerField(
        null=True, blank=True, help_text="Marks before late penalty"
    )

    # Plagiarism Detection
    plagiarism_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Plagiarism percentage (0-100)",
    )
    plagiarism_checked = models.BooleanField(default=False)
    plagiarism_report = models.JSONField(
        null=True, blank=True, help_text="Detailed plagiarism analysis"
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Revision Tracking
    revision_count = models.PositiveIntegerField(default=0)
    previous_submission = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="revisions",
    )

    class Meta:
        db_table = "assignments_submission"
        unique_together = [["assignment", "student"]]
        ordering = ["-submission_date"]
        indexes = [
            models.Index(fields=["assignment", "status"]),
            models.Index(fields=["student", "status"]),
            models.Index(fields=["graded_by", "status"]),
            models.Index(fields=["submission_date"]),
        ]

    def __str__(self):
        return f"{self.assignment.title} - {self.student.user.get_full_name()} ({self.status})"

    def save(self, *args, **kwargs):
        # Check if submission is late
        if self.submission_date and self.assignment.due_date:
            self.is_late = self.submission_date > self.assignment.due_date

        # Calculate percentage if marks are provided
        if self.marks_obtained is not None and self.assignment.total_marks:
            self.percentage = (self.marks_obtained / self.assignment.total_marks) * 100

        # Apply late penalty if applicable
        if (
            self.is_late
            and self.assignment.allow_late_submission
            and self.marks_obtained
            and not self.late_penalty_applied
        ):
            self.original_marks = self.marks_obtained
            penalty = (
                self.assignment.late_penalty_percentage / 100
            ) * self.marks_obtained
            self.marks_obtained = max(0, self.marks_obtained - penalty)
            self.late_penalty_applied = True

        # Set graded timestamp
        if self.status == "graded" and not self.graded_at:
            self.graded_at = timezone.now()

        super().save(*args, **kwargs)

    @property
    def days_late(self):
        """Calculate how many days late the submission was"""
        if self.is_late and self.submission_date and self.assignment.due_date:
            return (self.submission_date - self.assignment.due_date).days
        return 0

    @property
    def is_passed(self):
        """Check if submission passed based on passing marks"""
        if self.marks_obtained and self.assignment.passing_marks:
            return self.marks_obtained >= self.assignment.passing_marks
        return None

    @property
    def file_size_mb(self):
        """Get file size in MB"""
        if self.attachment:
            return round(self.attachment.size / (1024 * 1024), 2)
        return 0

    def calculate_grade(self):
        """Calculate letter grade based on percentage"""
        if self.percentage is None:
            return ""

        if self.percentage >= 90:
            return "A+"
        elif self.percentage >= 85:
            return "A"
        elif self.percentage >= 80:
            return "A-"
        elif self.percentage >= 75:
            return "B+"
        elif self.percentage >= 70:
            return "B"
        elif self.percentage >= 65:
            return "B-"
        elif self.percentage >= 60:
            return "C+"
        elif self.percentage >= 55:
            return "C"
        elif self.percentage >= 50:
            return "C-"
        elif self.percentage >= 45:
            return "D"
        else:
            return "F"


class AssignmentRubric(models.Model):
    """
    Rubric model for structured assignment grading
    """

    assignment = models.ForeignKey(
        Assignment, on_delete=models.CASCADE, related_name="rubrics"
    )
    criteria_name = models.CharField(max_length=100)
    description = models.TextField()
    max_points = models.PositiveIntegerField()
    weight_percentage = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(100)]
    )

    # Performance Levels
    excellent_description = models.TextField(help_text="90-100% performance")
    good_description = models.TextField(help_text="70-89% performance")
    satisfactory_description = models.TextField(help_text="50-69% performance")
    needs_improvement_description = models.TextField(help_text="Below 50% performance")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "assignments_rubric"
        unique_together = [["assignment", "criteria_name"]]

    def __str__(self):
        return f"{self.assignment.title} - {self.criteria_name}"


class SubmissionGrade(models.Model):
    """
    Individual rubric grading for submissions
    """

    submission = models.ForeignKey(
        AssignmentSubmission, on_delete=models.CASCADE, related_name="rubric_grades"
    )
    rubric = models.ForeignKey(
        AssignmentRubric, on_delete=models.CASCADE, related_name="grades"
    )
    points_earned = models.PositiveIntegerField()
    feedback = models.TextField(blank=True)

    class Meta:
        db_table = "assignments_submission_grade"
        unique_together = [["submission", "rubric"]]

    def __str__(self):
        return f"{self.submission} - {self.rubric.criteria_name}: {self.points_earned}/{self.rubric.max_points}"


class AssignmentComment(models.Model):
    """
    Comments on assignments for discussion and clarification
    """

    assignment = models.ForeignKey(
        Assignment, on_delete=models.CASCADE, related_name="comments"
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    parent_comment = models.ForeignKey(
        "self", on_delete=models.CASCADE, null=True, blank=True, related_name="replies"
    )
    content = models.TextField()
    is_private = models.BooleanField(
        default=False, help_text="Only visible to teachers"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "assignments_comment"
        ordering = ["created_at"]

    def __str__(self):
        return f"Comment on {self.assignment.title} by {self.user.get_full_name()}"
