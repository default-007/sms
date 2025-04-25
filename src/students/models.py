from django.db import models
from django.conf import settings
from src.courses.models import Class


class StudentQuerySet(models.QuerySet):
    def active(self):
        return self.filter(status="Active")

    def inactive(self):
        return self.filter(status="Inactive")

    def graduated(self):
        return self.filter(status="Graduated")

    def by_class(self, class_id):
        return self.filter(current_class_id=class_id)


class Student(models.Model):
    STATUS_CHOICES = (
        ("Active", "Active"),
        ("Inactive", "Inactive"),
        ("Graduated", "Graduated"),
        ("Suspended", "Suspended"),
        ("Expelled", "Expelled"),
    )

    BLOOD_GROUP_CHOICES = (
        ("A+", "A+"),
        ("A-", "A-"),
        ("B+", "B+"),
        ("B-", "B-"),
        ("AB+", "AB+"),
        ("AB-", "AB-"),
        ("O+", "O+"),
        ("O-", "O-"),
    )

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="student_profile",
    )
    admission_number = models.CharField(max_length=20, unique=True)
    admission_date = models.DateField()
    current_class = models.ForeignKey(
        Class, on_delete=models.SET_NULL, null=True, related_name="students"
    )
    roll_number = models.CharField(max_length=20, blank=True, null=True)
    blood_group = models.CharField(
        max_length=3, choices=BLOOD_GROUP_CHOICES, blank=True, null=True
    )
    medical_conditions = models.TextField(blank=True, null=True)
    emergency_contact_name = models.CharField(max_length=100)
    emergency_contact_number = models.CharField(max_length=20)
    previous_school = models.CharField(max_length=200, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="Active")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = StudentQuerySet.as_manager()

    class Meta:
        ordering = ["admission_number"]
        permissions = [
            ("view_student_details", "Can view detailed student information"),
            ("export_student_data", "Can export student data"),
        ]

    def __str__(self):
        return f"{self.user.first_name} {self.user.last_name} ({self.admission_number})"

    def is_active(self):
        return self.status == "Active"

    def get_full_name(self):
        return f"{self.user.first_name} {self.user.last_name}"

    def get_parents(self):
        return [
            relation.parent
            for relation in self.student_parent_relations.filter(
                is_primary_contact=True
            )
        ]

    def get_primary_parent(self):
        primary_relation = self.student_parent_relations.filter(
            is_primary_contact=True
        ).first()
        return primary_relation.parent if primary_relation else None


class Parent(models.Model):
    RELATION_CHOICES = (
        ("Father", "Father"),
        ("Mother", "Mother"),
        ("Guardian", "Guardian"),
    )

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="parent_profile",
    )
    occupation = models.CharField(max_length=100, blank=True, null=True)
    annual_income = models.DecimalField(
        max_digits=15, decimal_places=2, blank=True, null=True
    )
    education = models.CharField(max_length=100, blank=True, null=True)
    relation_with_student = models.CharField(max_length=20, choices=RELATION_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["user__first_name", "user__last_name"]

    def __str__(self):
        return f"{self.user.first_name} {self.user.last_name} ({self.relation_with_student})"

    def get_students(self):
        return [relation.student for relation in self.parent_student_relations.all()]


class StudentParentRelation(models.Model):
    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="student_parent_relations"
    )
    parent = models.ForeignKey(
        Parent, on_delete=models.CASCADE, related_name="parent_student_relations"
    )
    is_primary_contact = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ["student", "parent"]

    def __str__(self):
        return f"{self.student} - {self.parent}"
