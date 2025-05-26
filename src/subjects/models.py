from datetime import timezone
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
import json

User = get_user_model()


class Subject(models.Model):
    """
    Subject model representing academic subjects in the school.
    Subjects can be assigned to specific grades and departments.
    """

    name = models.CharField(max_length=200, verbose_name=_("Subject Name"))
    code = models.CharField(
        max_length=20,
        unique=True,
        verbose_name=_("Subject Code"),
        help_text=_("Unique identifier for the subject (e.g., MATH101, ENG201)"),
    )
    description = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Description"),
        help_text=_("Detailed description of the subject"),
    )
    department = models.ForeignKey(
        "academics.Department",
        on_delete=models.CASCADE,
        related_name="subjects",
        verbose_name=_("Department"),
    )
    credit_hours = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        verbose_name=_("Credit Hours"),
        help_text=_("Number of credit hours for this subject"),
    )
    is_elective = models.BooleanField(
        default=False,
        verbose_name=_("Is Elective"),
        help_text=_("Whether this subject is elective or mandatory"),
    )
    grade_level = models.JSONField(
        default=list,
        verbose_name=_("Grade Levels"),
        help_text=_("List of grade IDs that can take this subject"),
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_("Is Active"),
        help_text=_("Whether this subject is currently active"),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Subject")
        verbose_name_plural = _("Subjects")
        ordering = ["department__name", "name"]
        indexes = [
            models.Index(fields=["department", "is_active"]),
            models.Index(fields=["code"]),
            models.Index(fields=["is_elective"]),
        ]

    def __str__(self):
        return f"{self.code} - {self.name}"

    def clean(self):
        """Validate model data"""
        if self.grade_level and not isinstance(self.grade_level, list):
            raise ValidationError(_("Grade level must be a list of grade IDs"))

    def get_applicable_grades(self):
        """Get Grade objects that this subject applies to"""
        from academics.models import Grade

        if not self.grade_level:
            return Grade.objects.none()
        return Grade.objects.filter(id__in=self.grade_level)

    def is_applicable_for_grade(self, grade_id):
        """Check if subject is applicable for a specific grade"""
        return not self.grade_level or grade_id in self.grade_level

    @property
    def total_syllabus_items(self):
        """Count total syllabus items across all terms"""
        return self.syllabi.count()

    @property
    def completion_percentage(self):
        """Calculate average completion percentage across all syllabi"""
        syllabi = self.syllabi.all()
        if not syllabi:
            return 0
        total_completion = sum(s.completion_percentage for s in syllabi)
        return total_completion / len(syllabi)


class Syllabus(models.Model):
    """
    Syllabus model representing curriculum content for a subject in a specific term.
    Contains detailed course content, learning objectives, and progress tracking.
    """

    subject = models.ForeignKey(
        Subject,
        on_delete=models.CASCADE,
        related_name="syllabi",
        verbose_name=_("Subject"),
    )
    grade = models.ForeignKey(
        "academics.Grade",
        on_delete=models.CASCADE,
        related_name="syllabi",
        verbose_name=_("Grade"),
    )
    academic_year = models.ForeignKey(
        "academics.AcademicYear",
        on_delete=models.CASCADE,
        related_name="syllabi",
        verbose_name=_("Academic Year"),
    )
    term = models.ForeignKey(
        "academics.Term",
        on_delete=models.CASCADE,
        related_name="syllabi",
        verbose_name=_("Term"),
    )
    title = models.CharField(
        max_length=300,
        verbose_name=_("Syllabus Title"),
        help_text=_("Title for this term's syllabus"),
    )
    description = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Description"),
        help_text=_("Overview of the syllabus content"),
    )
    content = models.JSONField(
        default=dict,
        verbose_name=_("Syllabus Content"),
        help_text=_("Structured content including topics, subtopics, and materials"),
    )
    learning_objectives = models.JSONField(
        default=list,
        verbose_name=_("Learning Objectives"),
        help_text=_("List of learning objectives for this syllabus"),
    )
    completion_percentage = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(100.0)],
        verbose_name=_("Completion Percentage"),
        help_text=_("Percentage of syllabus completed"),
    )
    estimated_duration_hours = models.PositiveIntegerField(
        default=0,
        verbose_name=_("Estimated Duration (Hours)"),
        help_text=_("Estimated time to complete this syllabus"),
    )
    difficulty_level = models.CharField(
        max_length=20,
        choices=[
            ("beginner", _("Beginner")),
            ("intermediate", _("Intermediate")),
            ("advanced", _("Advanced")),
            ("expert", _("Expert")),
        ],
        default="intermediate",
        verbose_name=_("Difficulty Level"),
    )
    prerequisites = models.JSONField(
        default=list,
        verbose_name=_("Prerequisites"),
        help_text=_("List of prerequisite subjects or topics"),
    )
    assessment_methods = models.JSONField(
        default=list,
        verbose_name=_("Assessment Methods"),
        help_text=_("Methods used to assess student understanding"),
    )
    resources = models.JSONField(
        default=dict,
        verbose_name=_("Resources"),
        help_text=_("Books, materials, and other resources"),
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_syllabi",
        verbose_name=_("Created By"),
    )
    last_updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="updated_syllabi",
        verbose_name=_("Last Updated By"),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    last_updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True, verbose_name=_("Is Active"))

    class Meta:
        verbose_name = _("Syllabus")
        verbose_name_plural = _("Syllabi")
        unique_together = [["subject", "grade", "academic_year", "term"]]
        ordering = ["academic_year", "term", "subject__name"]
        indexes = [
            models.Index(fields=["subject", "grade", "academic_year", "term"]),
            models.Index(fields=["academic_year", "term"]),
            models.Index(fields=["completion_percentage"]),
            models.Index(fields=["is_active"]),
        ]

    def __str__(self):
        return f"{self.subject.name} - {self.grade.name} - {self.term.name}"

    def clean(self):
        """Validate model data"""
        # Ensure subject is applicable for the grade
        if not self.subject.is_applicable_for_grade(self.grade.id):
            raise ValidationError(
                _("Subject '{}' is not applicable for grade '{}'").format(
                    self.subject.name, self.grade.name
                )
            )

        # Validate term belongs to academic year
        if self.term.academic_year != self.academic_year:
            raise ValidationError(
                _("Term '{}' does not belong to academic year '{}'").format(
                    self.term.name, self.academic_year.name
                )
            )

    def get_total_topics(self):
        """Count total topics in the syllabus content"""
        if not isinstance(self.content, dict) or "topics" not in self.content:
            return 0
        return len(self.content.get("topics", []))

    def get_completed_topics(self):
        """Count completed topics"""
        if not isinstance(self.content, dict) or "topics" not in self.content:
            return 0
        return len(
            [
                topic
                for topic in self.content.get("topics", [])
                if topic.get("completed", False)
            ]
        )

    def update_completion_percentage(self):
        """Recalculate and update completion percentage based on topics"""
        total_topics = self.get_total_topics()
        if total_topics == 0:
            self.completion_percentage = 0.0
        else:
            completed_topics = self.get_completed_topics()
            self.completion_percentage = (completed_topics / total_topics) * 100
        self.save(update_fields=["completion_percentage"])

    def get_learning_outcomes(self):
        """Get formatted learning outcomes"""
        return self.learning_objectives or []

    def add_topic(self, topic_data):
        """Add a new topic to the syllabus content"""
        if not isinstance(self.content, dict):
            self.content = {}
        if "topics" not in self.content:
            self.content["topics"] = []

        topic_data.setdefault("completed", False)
        topic_data.setdefault("created_at", str(timezone.now()))
        self.content["topics"].append(topic_data)
        self.save()

    def mark_topic_completed(self, topic_index):
        """Mark a specific topic as completed"""
        if (
            isinstance(self.content, dict)
            and "topics" in self.content
            and 0 <= topic_index < len(self.content["topics"])
        ):

            self.content["topics"][topic_index]["completed"] = True
            self.save()
            self.update_completion_percentage()

    @property
    def progress_status(self):
        """Get progress status based on completion percentage"""
        if self.completion_percentage == 0:
            return "not_started"
        elif self.completion_percentage < 50:
            return "in_progress"
        elif self.completion_percentage < 100:
            return "nearing_completion"
        else:
            return "completed"


class SubjectAssignment(models.Model):
    """
    Model to track which teachers are assigned to teach specific subjects
    for specific classes in a given term.
    """

    subject = models.ForeignKey(
        Subject,
        on_delete=models.CASCADE,
        related_name="assignments",
        verbose_name=_("Subject"),
    )
    teacher = models.ForeignKey(
        "teachers.Teacher",
        on_delete=models.CASCADE,
        related_name="subject_assignments",
        verbose_name=_("Teacher"),
    )
    class_assigned = models.ForeignKey(
        "academics.Class",
        on_delete=models.CASCADE,
        related_name="subject_assignments",
        verbose_name=_("Class"),
    )
    academic_year = models.ForeignKey(
        "academics.AcademicYear",
        on_delete=models.CASCADE,
        related_name="subject_assignments",
        verbose_name=_("Academic Year"),
    )
    term = models.ForeignKey(
        "academics.Term",
        on_delete=models.CASCADE,
        related_name="subject_assignments",
        verbose_name=_("Term"),
    )
    is_primary_teacher = models.BooleanField(
        default=True,
        verbose_name=_("Is Primary Teacher"),
        help_text=_("Whether this teacher is the primary instructor for this subject"),
    )
    assigned_date = models.DateField(auto_now_add=True)
    assigned_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="subject_assignments_made",
        verbose_name=_("Assigned By"),
    )
    is_active = models.BooleanField(default=True, verbose_name=_("Is Active"))

    class Meta:
        verbose_name = _("Subject Assignment")
        verbose_name_plural = _("Subject Assignments")
        unique_together = [["subject", "class_assigned", "academic_year", "term"]]
        ordering = ["academic_year", "term", "class_assigned", "subject"]
        indexes = [
            models.Index(fields=["teacher", "academic_year", "term"]),
            models.Index(fields=["class_assigned", "academic_year", "term"]),
            models.Index(fields=["subject", "academic_year", "term"]),
        ]

    def __str__(self):
        return f"{self.teacher.user.get_full_name()} - {self.subject.name} - {self.class_assigned}"

    def clean(self):
        """Validate assignment data"""
        # Check if subject is applicable for the class's grade
        if not self.subject.is_applicable_for_grade(self.class_assigned.grade.id):
            raise ValidationError(
                _("Subject '{}' is not applicable for grade '{}'").format(
                    self.subject.name, self.class_assigned.grade.name
                )
            )


class TopicProgress(models.Model):
    """
    Model to track individual topic progress within a syllabus.
    Allows detailed tracking of curriculum coverage.
    """

    syllabus = models.ForeignKey(
        Syllabus,
        on_delete=models.CASCADE,
        related_name="topic_progress",
        verbose_name=_("Syllabus"),
    )
    topic_name = models.CharField(max_length=300, verbose_name=_("Topic Name"))
    topic_index = models.PositiveIntegerField(
        verbose_name=_("Topic Index"), help_text=_("Position of topic in the syllabus")
    )
    is_completed = models.BooleanField(default=False, verbose_name=_("Is Completed"))
    completion_date = models.DateField(
        null=True, blank=True, verbose_name=_("Completion Date")
    )
    hours_taught = models.FloatField(
        default=0.0, validators=[MinValueValidator(0.0)], verbose_name=_("Hours Taught")
    )
    teaching_method = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_("Teaching Method"),
        help_text=_("Method used to teach this topic"),
    )
    notes = models.TextField(
        blank=True,
        verbose_name=_("Notes"),
        help_text=_("Additional notes about teaching this topic"),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Topic Progress")
        verbose_name_plural = _("Topic Progress")
        unique_together = [["syllabus", "topic_index"]]
        ordering = ["syllabus", "topic_index"]
        indexes = [
            models.Index(fields=["syllabus", "is_completed"]),
            models.Index(fields=["completion_date"]),
        ]

    def __str__(self):
        return f"{self.syllabus} - {self.topic_name}"

    def mark_completed(self):
        """Mark topic as completed and set completion date"""
        self.is_completed = True
        self.completion_date = timezone.now().date()
        self.save()

        # Update syllabus completion percentage
        self.syllabus.update_completion_percentage()
