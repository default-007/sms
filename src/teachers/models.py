from django.db import models
from django.conf import settings
from src.courses.models import Department, Subject, Class


class TeacherQuerySet(models.QuerySet):
    def active(self):
        return self.filter(status="Active")

    def on_leave(self):
        return self.filter(status="On Leave")

    def by_department(self, department_id):
        return self.filter(department_id=department_id)


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
    employee_id = models.CharField(max_length=20, unique=True)
    joining_date = models.DateField()
    qualification = models.CharField(max_length=200)
    experience_years = models.DecimalField(max_digits=4, decimal_places=1, default=0)
    specialization = models.CharField(max_length=200)
    department = models.ForeignKey(
        Department, on_delete=models.SET_NULL, null=True, related_name="teachers"
    )
    position = models.CharField(max_length=100)
    salary = models.DecimalField(max_digits=12, decimal_places=2)
    contract_type = models.CharField(max_length=20, choices=CONTRACT_TYPE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="Active")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = TeacherQuerySet.as_manager()

    class Meta:
        ordering = ["employee_id"]
        permissions = [
            ("view_teacher_details", "Can view detailed teacher information"),
            ("assign_classes", "Can assign classes to teachers"),
        ]

    def __str__(self):
        return f"{self.user.first_name} {self.user.last_name} ({self.employee_id})"

    def is_active(self):
        return self.status == "Active"

    def get_full_name(self):
        return f"{self.user.first_name} {self.user.last_name}"

    def get_assigned_classes(self, academic_year=None):
        assignments = self.class_assignments.all()
        if academic_year:
            assignments = assignments.filter(academic_year=academic_year)
        return [assignment.class_instance for assignment in assignments]

    def get_assigned_subjects(self, academic_year=None):
        assignments = self.class_assignments.all()
        if academic_year:
            assignments = assignments.filter(academic_year=academic_year)
        return list(set([assignment.subject for assignment in assignments]))


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

    class Meta:
        unique_together = ["teacher", "class_instance", "subject", "academic_year"]

    def __str__(self):
        return f"{self.teacher} - {self.class_instance} - {self.subject}"


class TeacherEvaluation(models.Model):
    teacher = models.ForeignKey(
        Teacher, on_delete=models.CASCADE, related_name="evaluations"
    )
    evaluator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="teacher_evaluations",
    )
    evaluation_date = models.DateField()
    criteria = models.JSONField()  # Stores evaluation parameters and scores
    score = models.DecimalField(max_digits=5, decimal_places=2)
    remarks = models.TextField()
    followup_actions = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-evaluation_date"]

    def __str__(self):
        return f"Evaluation of {self.teacher} on {self.evaluation_date}"
