from django.db import models
from django.conf import settings
from django.db.models import Avg, Count, Sum
from django.utils import timezone
from src.courses.models import Department, Subject, Class


class TeacherQuerySet(models.QuerySet):
    def active(self):
        return self.filter(status="Active")

    def on_leave(self):
        return self.filter(status="On Leave")

    def by_department(self, department_id):
        return self.filter(department_id=department_id)

    def by_experience_range(self, min_years=None, max_years=None):
        queryset = self
        if min_years is not None:
            queryset = queryset.filter(experience_years__gte=min_years)
        if max_years is not None:
            queryset = queryset.filter(experience_years__lte=max_years)
        return queryset

    def with_evaluation_stats(self):
        return self.annotate(
            avg_evaluation_score=Avg("evaluations__score"),
            evaluation_count=Count("evaluations"),
        )

    def with_class_counts(self):
        return self.annotate(class_count=Count("class_assignments", distinct=True))


class Teacher(models.Model):
    STATUS_CHOICES = (
        ("Active", "Active"),
        ("On Leave", "On Leave"),
        ("Terminated", "Terminated"),
    )

    CONTRACT_TYPE_CHOICES = (
        ("Permanent", "Permanent"),
        ("Temporary", "Temporary"),
        ("Contract", "Contract"),
    )

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="teacher_profile",
    )
    employee_id = models.CharField(max_length=20, unique=True, db_index=True)
    joining_date = models.DateField()
    qualification = models.CharField(max_length=200)
    experience_years = models.DecimalField(
        max_digits=4, decimal_places=1, default=0, db_index=True
    )
    specialization = models.CharField(max_length=200)
    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        related_name="teachers",
        db_index=True,
    )
    position = models.CharField(max_length=100)
    salary = models.DecimalField(max_digits=12, decimal_places=2)
    contract_type = models.CharField(
        max_length=20, choices=CONTRACT_TYPE_CHOICES, db_index=True
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="Active", db_index=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    bio = models.TextField(blank=True, null=True)
    emergency_contact = models.CharField(max_length=100, blank=True, null=True)
    emergency_phone = models.CharField(max_length=20, blank=True, null=True)

    objects = TeacherQuerySet.as_manager()

    class Meta:
        ordering = ["employee_id"]
        permissions = [
            ("view_teacher_details", "Can view detailed teacher information"),
            ("assign_classes", "Can assign classes to teachers"),
            ("view_teacher_analytics", "Can view teacher analytics"),
            ("export_teacher_data", "Can export teacher data"),
        ]
        indexes = [
            models.Index(fields=["joining_date"]),
            models.Index(fields=["department", "status"]),
            models.Index(fields=["contract_type", "status"]),
        ]

    def __str__(self):
        return f"{self.user.first_name} {self.user.last_name} ({self.employee_id})"

    def is_active(self):
        return self.status == "Active"

    def get_full_name(self):
        return f"{self.user.first_name} {self.user.last_name}"

    def get_short_name(self):
        return f"{self.user.first_name} {self.user.last_name[0]}."

    def get_assigned_classes(self, academic_year=None):
        assignments = self.class_assignments.all().select_related(
            "class_instance", "subject"
        )
        if academic_year:
            assignments = assignments.filter(academic_year=academic_year)
        return [assignment.class_instance for assignment in assignments]

    def get_assigned_subjects(self, academic_year=None):
        assignments = self.class_assignments.all().select_related("subject")
        if academic_year:
            assignments = assignments.filter(academic_year=academic_year)
        return list(set([assignment.subject for assignment in assignments]))

    def get_average_evaluation_score(self):
        return self.evaluations.aggregate(avg_score=Avg("score"))["avg_score"]

    def get_latest_evaluation(self):
        return self.evaluations.order_by("-evaluation_date").first()

    def get_years_of_service(self):
        if not self.joining_date:
            return 0
        today = timezone.now().date()
        return (today - self.joining_date).days // 365

    def get_performance_trend(self, months=6):
        """Get performance trend over the last X months"""
        start_date = timezone.now().date() - timezone.timedelta(days=30 * months)
        evaluations = self.evaluations.filter(evaluation_date__gte=start_date).order_by(
            "evaluation_date"
        )

        return {
            "dates": [eval.evaluation_date.strftime("%b %Y") for eval in evaluations],
            "scores": [float(eval.score) for eval in evaluations],
        }


class TeacherClassAssignment(models.Model):
    teacher = models.ForeignKey(
        Teacher, on_delete=models.CASCADE, related_name="class_assignments"
    )
    class_instance = models.ForeignKey(
        Class, on_delete=models.CASCADE, related_name="teacher_assignments"
    )
    subject = models.ForeignKey(
        Subject, on_delete=models.CASCADE, related_name="teacher_assignments"
    )
    academic_year = models.ForeignKey("courses.AcademicYear", on_delete=models.CASCADE)
    is_class_teacher = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    notes = models.TextField(blank=True, null=True)

    class Meta:
        unique_together = ["teacher", "class_instance", "subject", "academic_year"]
        indexes = [
            models.Index(fields=["teacher", "academic_year"]),
            models.Index(fields=["class_instance", "academic_year"]),
            models.Index(fields=["is_class_teacher"]),
        ]

    def __str__(self):
        return f"{self.teacher} - {self.class_instance} - {self.subject}"


class TeacherEvaluation(models.Model):
    EVALUATION_CATEGORIES = [
        "teaching_methodology",
        "subject_knowledge",
        "classroom_management",
        "student_engagement",
        "professional_conduct",
    ]

    teacher = models.ForeignKey(
        Teacher, on_delete=models.CASCADE, related_name="evaluations"
    )
    evaluator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="teacher_evaluations",
    )
    evaluation_date = models.DateField(db_index=True)
    criteria = models.JSONField()  # Stores evaluation parameters and scores
    score = models.DecimalField(max_digits=5, decimal_places=2, db_index=True)
    remarks = models.TextField()
    followup_actions = models.TextField(blank=True, null=True)
    status = models.CharField(
        max_length=20,
        choices=[
            ("draft", "Draft"),
            ("submitted", "Submitted"),
            ("reviewed", "Reviewed"),
            ("closed", "Closed"),
        ],
        default="submitted",
        db_index=True,
    )
    followup_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-evaluation_date"]
        indexes = [
            models.Index(fields=["teacher", "evaluation_date"]),
            models.Index(fields=["teacher", "score"]),
        ]

    def __str__(self):
        return f"Evaluation of {self.teacher} on {self.evaluation_date}"

    def get_performance_level(self):
        if self.score >= 90:
            return "Excellent"
        elif self.score >= 80:
            return "Good"
        elif self.score >= 70:
            return "Satisfactory"
        elif self.score >= 60:
            return "Needs Improvement"
        else:
            return "Poor"

    def is_followup_required(self):
        return self.score < 70 and self.status != "closed"

    def is_followup_overdue(self):
        if not self.followup_date:
            return False
        return self.followup_date < timezone.now().date() and self.status != "closed"

    @staticmethod
    def get_default_criteria():
        return {
            "teaching_methodology": {"score": 0, "max_score": 10, "comments": ""},
            "subject_knowledge": {"score": 0, "max_score": 10, "comments": ""},
            "classroom_management": {"score": 0, "max_score": 10, "comments": ""},
            "student_engagement": {"score": 0, "max_score": 10, "comments": ""},
            "professional_conduct": {"score": 0, "max_score": 10, "comments": ""},
        }
