from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from src.courses.models import AcademicYear, Class, Subject


class ExamType(models.Model):
    """Model to define different types of examinations."""

    name = models.CharField(_("name"), max_length=100)
    description = models.TextField(_("description"), blank=True)
    contribution_percentage = models.DecimalField(
        _("contribution percentage"),
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text=_("How much this exam contributes to the final grade (percentage)"),
    )

    class Meta:
        verbose_name = _("exam type")
        verbose_name_plural = _("exam types")
        ordering = ["name"]

    def __str__(self):
        return self.name


class Exam(models.Model):
    """Model to represent an examination event."""

    STATUS_CHOICES = (
        ("scheduled", _("Scheduled")),
        ("ongoing", _("Ongoing")),
        ("completed", _("Completed")),
        ("cancelled", _("Cancelled")),
    )

    name = models.CharField(_("name"), max_length=200)
    exam_type = models.ForeignKey(
        ExamType,
        on_delete=models.CASCADE,
        related_name="exams",
        verbose_name=_("exam type"),
    )
    academic_year = models.ForeignKey(
        AcademicYear,
        on_delete=models.CASCADE,
        related_name="exams",
        verbose_name=_("academic year"),
    )
    start_date = models.DateField(_("start date"))
    end_date = models.DateField(_("end date"))
    description = models.TextField(_("description"), blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="created_exams",
        verbose_name=_("created by"),
    )
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)
    status = models.CharField(
        _("status"), max_length=20, choices=STATUS_CHOICES, default="scheduled"
    )

    class Meta:
        verbose_name = _("exam")
        verbose_name_plural = _("exams")
        ordering = ["-start_date"]

    def __str__(self):
        return f"{self.name} ({self.academic_year})"

    def is_active(self):
        """Check if the exam is currently active."""
        today = timezone.now().date()
        return self.start_date <= today <= self.end_date and self.status == "ongoing"

    def get_total_subjects(self):
        """Get total number of subjects in this exam."""
        return self.exam_schedules.count()

    def get_completed_subjects(self):
        """Get number of completed subjects in this exam."""
        return self.exam_schedules.filter(status="completed").count()


class ExamSchedule(models.Model):
    """Model to represent the schedule of each subject in an exam."""

    STATUS_CHOICES = (
        ("scheduled", _("Scheduled")),
        ("ongoing", _("Ongoing")),
        ("completed", _("Completed")),
        ("cancelled", _("Cancelled")),
    )

    exam = models.ForeignKey(
        Exam,
        on_delete=models.CASCADE,
        related_name="exam_schedules",
        verbose_name=_("exam"),
    )
    class_obj = models.ForeignKey(
        Class,
        on_delete=models.CASCADE,
        related_name="exam_schedules",
        verbose_name=_("class"),
    )
    subject = models.ForeignKey(
        Subject,
        on_delete=models.CASCADE,
        related_name="exam_schedules",
        verbose_name=_("subject"),
    )
    date = models.DateField(_("date"))
    start_time = models.TimeField(_("start time"))
    end_time = models.TimeField(_("end time"))
    room = models.CharField(_("room"), max_length=50)
    supervisor = models.ForeignKey(
        "teachers.Teacher",
        on_delete=models.SET_NULL,
        null=True,
        related_name="supervised_exams",
        verbose_name=_("supervisor"),
    )
    total_marks = models.PositiveIntegerField(_("total marks"))
    passing_marks = models.PositiveIntegerField(_("passing marks"))
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)
    status = models.CharField(
        _("status"), max_length=20, choices=STATUS_CHOICES, default="scheduled"
    )

    class Meta:
        verbose_name = _("exam schedule")
        verbose_name_plural = _("exam schedules")
        ordering = ["date", "start_time"]
        unique_together = ["exam", "class_obj", "subject"]

    def __str__(self):
        return f"{self.subject.name} - {self.class_obj} ({self.date})"

    def duration_minutes(self):
        """Calculate duration in minutes."""
        if not self.start_time or not self.end_time:
            return 0

        from datetime import datetime, timedelta

        start_dt = datetime.combine(datetime.today(), self.start_time)
        end_dt = datetime.combine(datetime.today(), self.end_time)

        if end_dt < start_dt:  # Handle case when end_time is on next day
            end_dt += timedelta(days=1)

        duration = end_dt - start_dt
        return int(duration.total_seconds() / 60)


class Quiz(models.Model):
    """Model to represent a quiz."""

    STATUS_CHOICES = (
        ("draft", _("Draft")),
        ("published", _("Published")),
        ("closed", _("Closed")),
    )

    title = models.CharField(_("title"), max_length=200)
    description = models.TextField(_("description"), blank=True)
    class_obj = models.ForeignKey(
        Class, on_delete=models.CASCADE, related_name="quizzes", verbose_name=_("class")
    )
    subject = models.ForeignKey(
        Subject,
        on_delete=models.CASCADE,
        related_name="quizzes",
        verbose_name=_("subject"),
    )
    teacher = models.ForeignKey(
        "teachers.Teacher",
        on_delete=models.CASCADE,
        related_name="quizzes",
        verbose_name=_("teacher"),
    )
    start_datetime = models.DateTimeField(_("start datetime"))
    end_datetime = models.DateTimeField(_("end datetime"))
    duration_minutes = models.PositiveIntegerField(_("duration minutes"))
    total_marks = models.PositiveIntegerField(_("total marks"))
    passing_marks = models.PositiveIntegerField(_("passing marks"))
    attempts_allowed = models.PositiveIntegerField(_("attempts allowed"), default=1)
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)
    status = models.CharField(
        _("status"), max_length=20, choices=STATUS_CHOICES, default="draft"
    )

    class Meta:
        verbose_name = _("quiz")
        verbose_name_plural = _("quizzes")
        ordering = ["-start_datetime"]

    def __str__(self):
        return self.title

    def is_active(self):
        """Check if the quiz is currently active."""
        now = timezone.now()
        return (
            self.start_datetime <= now <= self.end_datetime
            and self.status == "published"
        )

    def get_total_questions(self):
        """Get total number of questions in the quiz."""
        return self.questions.count()

    def get_total_marks(self):
        """Calculate total marks of the quiz based on questions."""
        return self.questions.aggregate(models.Sum("marks"))["marks__sum"] or 0


class Question(models.Model):
    """Model to represent a question in a quiz."""

    QUESTION_TYPE_CHOICES = (
        ("mcq", _("Multiple Choice")),
        ("true_false", _("True/False")),
        ("short_answer", _("Short Answer")),
        ("essay", _("Essay")),
    )

    DIFFICULTY_CHOICES = (
        ("easy", _("Easy")),
        ("medium", _("Medium")),
        ("hard", _("Hard")),
    )

    quiz = models.ForeignKey(
        Quiz, on_delete=models.CASCADE, related_name="questions", verbose_name=_("quiz")
    )
    question_text = models.TextField(_("question text"))
    question_type = models.CharField(
        _("question type"), max_length=20, choices=QUESTION_TYPE_CHOICES
    )
    options = models.JSONField(
        _("options"), default=list, blank=True, help_text=_("Options for MCQ questions")
    )
    correct_answer = models.TextField(_("correct answer"))
    explanation = models.TextField(_("explanation"), blank=True)
    marks = models.PositiveIntegerField(_("marks"))
    difficulty_level = models.CharField(
        _("difficulty level"),
        max_length=20,
        choices=DIFFICULTY_CHOICES,
        default="medium",
    )
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        verbose_name = _("question")
        verbose_name_plural = _("questions")
        ordering = ["id"]

    def __str__(self):
        return self.question_text[:50]


class StudentExamResult(models.Model):
    """Model to record a student's result for a specific exam subject."""

    student = models.ForeignKey(
        "students.Student",
        on_delete=models.CASCADE,
        related_name="exam_results",
        verbose_name=_("student"),
    )
    exam_schedule = models.ForeignKey(
        ExamSchedule,
        on_delete=models.CASCADE,
        related_name="student_results",
        verbose_name=_("exam schedule"),
    )
    marks_obtained = models.DecimalField(
        _("marks obtained"), max_digits=6, decimal_places=2
    )
    percentage = models.DecimalField(
        _("percentage"),
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    grade = models.CharField(_("grade"), max_length=10, blank=True)
    remarks = models.TextField(_("remarks"), blank=True)
    is_pass = models.BooleanField(_("is pass"), default=False)
    entered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="entered_results",
        verbose_name=_("entered by"),
    )
    entry_date = models.DateTimeField(_("entry date"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        verbose_name = _("student exam result")
        verbose_name_plural = _("student exam results")
        unique_together = ["student", "exam_schedule"]
        ordering = ["student__user__first_name", "student__user__last_name"]

    def __str__(self):
        return f"{self.student} - {self.exam_schedule.subject} - {self.marks_obtained}/{self.exam_schedule.total_marks}"

    def save(self, *args, **kwargs):
        """Calculate percentage and check if passed before saving."""
        if not self.percentage and self.exam_schedule and self.marks_obtained:
            self.percentage = (
                self.marks_obtained / self.exam_schedule.total_marks
            ) * 100

        if not self.is_pass and self.exam_schedule and self.marks_obtained:
            self.is_pass = self.marks_obtained >= self.exam_schedule.passing_marks

        super().save(*args, **kwargs)


class StudentQuizAttempt(models.Model):
    """Model to record a student's attempt at a quiz."""

    student = models.ForeignKey(
        "students.Student",
        on_delete=models.CASCADE,
        related_name="quiz_attempts",
        verbose_name=_("student"),
    )
    quiz = models.ForeignKey(
        Quiz,
        on_delete=models.CASCADE,
        related_name="student_attempts",
        verbose_name=_("quiz"),
    )
    start_time = models.DateTimeField(_("start time"))
    end_time = models.DateTimeField(_("end time"), null=True, blank=True)
    marks_obtained = models.DecimalField(
        _("marks obtained"), max_digits=6, decimal_places=2, null=True, blank=True
    )
    percentage = models.DecimalField(
        _("percentage"),
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        null=True,
        blank=True,
    )
    is_pass = models.BooleanField(_("is pass"), default=False)
    attempt_number = models.PositiveIntegerField(_("attempt number"), default=1)
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        verbose_name = _("student quiz attempt")
        verbose_name_plural = _("student quiz attempts")
        unique_together = ["student", "quiz", "attempt_number"]
        ordering = ["-start_time"]

    def __str__(self):
        return f"{self.student} - {self.quiz.title} (Attempt {self.attempt_number})"

    def is_completed(self):
        """Check if the attempt is completed."""
        return self.end_time is not None

    def calculate_results(self):
        """Calculate the results of this attempt."""
        if not self.is_completed():
            return False

        total_marks = sum([q.marks for q in self.quiz.questions.all()])
        if total_marks == 0:
            return False

        obtained_marks = sum(
            [
                resp.marks_obtained if resp.is_correct else 0
                for resp in self.responses.all()
            ]
        )

        self.marks_obtained = obtained_marks
        self.percentage = (obtained_marks / total_marks) * 100
        self.is_pass = obtained_marks >= self.quiz.passing_marks
        self.save()
        return True


class StudentQuizResponse(models.Model):
    """Model to record a student's response to a question."""

    student_quiz_attempt = models.ForeignKey(
        StudentQuizAttempt,
        on_delete=models.CASCADE,
        related_name="responses",
        verbose_name=_("student quiz attempt"),
    )
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name="student_responses",
        verbose_name=_("question"),
    )
    selected_option = models.IntegerField(
        _("selected option"),
        null=True,
        blank=True,
        help_text=_("Index of selected option for MCQ questions"),
    )
    answer_text = models.TextField(
        _("answer text"), blank=True, help_text=_("Text answer for non-MCQ questions")
    )
    is_correct = models.BooleanField(_("is correct"), default=False)
    marks_obtained = models.DecimalField(
        _("marks obtained"), max_digits=6, decimal_places=2, default=0
    )
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        verbose_name = _("student quiz response")
        verbose_name_plural = _("student quiz responses")
        unique_together = ["student_quiz_attempt", "question"]

    def __str__(self):
        return f"Response to {self.question}"

    def evaluate(self):
        """Evaluate the response and assign marks."""
        question = self.question

        if question.question_type == "mcq":
            if self.selected_option is not None:
                try:
                    correct_option = int(question.correct_answer)
                    self.is_correct = self.selected_option == correct_option
                    self.marks_obtained = question.marks if self.is_correct else 0
                except (ValueError, IndexError):
                    self.is_correct = False
                    self.marks_obtained = 0

        elif question.question_type == "true_false":
            correct_answer = question.correct_answer.lower()
            student_answer = self.answer_text.lower()

            self.is_correct = (
                correct_answer == "true"
                and student_answer in ["true", "t", "yes", "y", "1"]
            ) or (
                correct_answer == "false"
                and student_answer in ["false", "f", "no", "n", "0"]
            )
            self.marks_obtained = question.marks if self.is_correct else 0

        else:
            # For essay or short answer, manual grading needed
            pass

        self.save()
        return self.is_correct


class GradingSystem(models.Model):
    """Model to define the grading system."""

    academic_year = models.ForeignKey(
        AcademicYear,
        on_delete=models.CASCADE,
        related_name="grading_systems",
        verbose_name=_("academic year"),
    )
    grade_name = models.CharField(_("grade name"), max_length=10)
    min_percentage = models.DecimalField(
        _("minimum percentage"),
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    max_percentage = models.DecimalField(
        _("maximum percentage"),
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    grade_point = models.DecimalField(_("grade point"), max_digits=3, decimal_places=1)
    description = models.TextField(_("description"), blank=True)
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        verbose_name = _("grading system")
        verbose_name_plural = _("grading systems")
        ordering = ["-grade_point"]
        unique_together = ["academic_year", "grade_name"]

    def __str__(self):
        return f"{self.grade_name} ({self.min_percentage}% - {self.max_percentage}%)"


class ReportCard(models.Model):
    """Model to represent a student's report card."""

    TERM_CHOICES = (
        ("first", _("First")),
        ("second", _("Second")),
        ("final", _("Final")),
    )

    STATUS_CHOICES = (
        ("draft", _("Draft")),
        ("published", _("Published")),
        ("archived", _("Archived")),
    )

    student = models.ForeignKey(
        "students.Student",
        on_delete=models.CASCADE,
        related_name="report_cards",
        verbose_name=_("student"),
    )
    class_obj = models.ForeignKey(
        Class,
        on_delete=models.CASCADE,
        related_name="report_cards",
        verbose_name=_("class"),
    )
    academic_year = models.ForeignKey(
        AcademicYear,
        on_delete=models.CASCADE,
        related_name="report_cards",
        verbose_name=_("academic year"),
    )
    term = models.CharField(_("term"), max_length=10, choices=TERM_CHOICES)
    generation_date = models.DateField(_("generation date"), auto_now_add=True)
    total_marks = models.DecimalField(_("total marks"), max_digits=10, decimal_places=2)
    marks_obtained = models.DecimalField(
        _("marks obtained"), max_digits=10, decimal_places=2
    )
    percentage = models.DecimalField(
        _("percentage"),
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    grade = models.CharField(_("grade"), max_length=10)
    grade_point_average = models.DecimalField(
        _("grade point average"), max_digits=3, decimal_places=2
    )
    rank = models.PositiveIntegerField(_("rank"), null=True, blank=True)
    remarks = models.TextField(_("remarks"), blank=True)
    attendance_percentage = models.DecimalField(
        _("attendance percentage"),
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        null=True,
        blank=True,
    )
    class_teacher_remarks = models.TextField(_("class teacher remarks"), blank=True)
    principal_remarks = models.TextField(_("principal remarks"), blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="created_report_cards",
        verbose_name=_("created by"),
    )
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)
    status = models.CharField(
        _("status"), max_length=20, choices=STATUS_CHOICES, default="draft"
    )

    class Meta:
        verbose_name = _("report card")
        verbose_name_plural = _("report cards")
        unique_together = ["student", "class_obj", "academic_year", "term"]
        ordering = ["student__user__first_name", "student__user__last_name"]

    def __str__(self):
        return f"{self.student} - {self.class_obj} - {self.term} Term"
