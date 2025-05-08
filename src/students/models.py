# students/models.py
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.validators import RegexValidator
from src.courses.models import Class, AcademicYear
from src.core.utils import generate_unique_id


class StudentQuerySet(models.QuerySet):
    def active(self):
        return self.filter(status="Active")

    def inactive(self):
        return self.filter(status__in=["Inactive", "Suspended", "Expelled"])

    def graduated(self):
        return self.filter(status="Graduated")

    def by_class(self, class_id):
        return self.filter(current_class_id=class_id)

    def by_admission_year(self, year):
        return self.filter(admission_date__year=year)

    def by_blood_group(self, blood_group):
        return self.filter(blood_group=blood_group)


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
        ("Unknown", "Unknown"),
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
        max_length=10, choices=BLOOD_GROUP_CHOICES, default="Unknown"
    )
    medical_conditions = models.TextField(blank=True, null=True)
    emergency_contact_name = models.CharField(max_length=100)
    emergency_contact_number = models.CharField(
        max_length=20,
        validators=[
            RegexValidator(
                regex=r"^\+?1?\d{9,15}$",
                message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed.",
            )
        ],
    )
    previous_school = models.CharField(max_length=200, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="Active")
    registration_number = models.CharField(
        max_length=30, blank=True, null=True, unique=True
    )
    nationality = models.CharField(max_length=50, blank=True, null=True)
    religion = models.CharField(max_length=50, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    state = models.CharField(max_length=100, blank=True, null=True)
    postal_code = models.CharField(max_length=20, blank=True, null=True)
    country = models.CharField(max_length=100, blank=True, null=True)
    photo = models.ImageField(upload_to="student_photos/", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = StudentQuerySet.as_manager()

    class Meta:
        ordering = ["admission_number"]
        permissions = [
            ("view_student_details", "Can view detailed student information"),
            ("export_student_data", "Can export student data"),
            ("promote_student", "Can promote student to next class"),
            ("graduate_student", "Can mark student as graduated"),
            ("generate_student_id", "Can generate student ID card"),
        ]

    def __str__(self):
        return f"{self.user.first_name} {self.user.last_name} ({self.admission_number})"

    def save(self, *args, **kwargs):
        # Generate registration number if not provided
        if not self.registration_number:
            admission_year = self.admission_date.year
            self.registration_number = (
                f"STU-{admission_year}-{generate_unique_id(length=6)}"
            )

        super().save(*args, **kwargs)

    def is_active(self):
        return self.status == "Active"

    def get_full_name(self):
        return f"{self.user.first_name} {self.user.last_name}"

    def get_full_address(self):
        """Return the complete address with city, state, and country"""
        address_parts = [
            part
            for part in [
                self.address,
                self.city,
                self.state,
                self.postal_code,
                self.country,
            ]
            if part
        ]

        return ", ".join(address_parts) if address_parts else "No address provided"

    def get_parents(self):
        """Get all parents of the student"""
        return [relation.parent for relation in self.student_parent_relations.all()]

    def get_primary_parent(self):
        """Get the primary parent of the student"""
        primary_relation = self.student_parent_relations.filter(
            is_primary_contact=True
        ).first()
        return primary_relation.parent if primary_relation else None

    def get_siblings(self):
        """Get all siblings of the student"""
        # Get parents of the student
        parents = self.get_parents()
        if not parents:
            return []

        # Get all students related to these parents except self
        siblings = set()
        for parent in parents:
            for relation in parent.parent_student_relations.all():
                if relation.student.id != self.id:
                    siblings.add(relation.student)

        return list(siblings)

    def get_attendance_percentage(self, academic_year=None, month=None):
        """Get the attendance percentage for a specific period"""
        from src.attendance.models import Attendance

        # Base query for student's attendance
        query = Attendance.objects.filter(student=self)

        # Filter by academic year if provided
        if academic_year:
            query = query.filter(academic_year=academic_year)
        else:
            # Get current academic year
            current_year = AcademicYear.objects.filter(is_current=True).first()
            if current_year:
                query = query.filter(academic_year=current_year)

        # Filter by month if provided
        if month:
            query = query.filter(date__month=month)

        # Count total and present days
        total_days = query.count()
        present_days = query.filter(status="Present").count()

        if total_days == 0:
            return 0

        return round((present_days / total_days) * 100, 2)

    def promote_to_next_class(self, new_class):
        """Promote student to next class"""
        old_class = self.current_class
        self.current_class = new_class
        self.save()

        # Log the promotion
        from src.core.models import AuditLog

        AuditLog.objects.create(
            user=None,  # Can be set to the user performing the action
            action="update",
            entity_type="student",
            entity_id=self.id,
            data_before={"current_class": old_class.id if old_class else None},
            data_after={"current_class": new_class.id},
        )

        return True

    def mark_as_graduated(self):
        """Mark student as graduated"""
        old_status = self.status
        self.status = "Graduated"
        self.save()

        # Log the graduation
        from src.core.models import AuditLog

        AuditLog.objects.create(
            user=None,  # Can be set to the user performing the action
            action="update",
            entity_type="student",
            entity_id=self.id,
            data_before={"status": old_status},
            data_after={"status": "Graduated"},
        )

        return True


class Parent(models.Model):
    RELATION_CHOICES = (
        ("Father", "Father"),
        ("Mother", "Mother"),
        ("Guardian", "Guardian"),
        ("Grandparent", "Grandparent"),
        ("Other", "Other"),
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
    workplace = models.CharField(max_length=200, blank=True, null=True)
    work_address = models.TextField(blank=True, null=True)
    work_phone = models.CharField(max_length=20, blank=True, null=True)
    emergency_contact = models.BooleanField(default=True)
    photo = models.ImageField(upload_to="parent_photos/", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["user__first_name", "user__last_name"]
        permissions = [
            ("view_parent_details", "Can view detailed parent information"),
        ]

    def __str__(self):
        return f"{self.user.first_name} {self.user.last_name} ({self.relation_with_student})"

    def get_full_name(self):
        return f"{self.user.first_name} {self.user.last_name}"

    def get_students(self):
        """Get all students related to this parent"""
        return [relation.student for relation in self.parent_student_relations.all()]


class StudentParentRelation(models.Model):
    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="student_parent_relations"
    )
    parent = models.ForeignKey(
        Parent, on_delete=models.CASCADE, related_name="parent_student_relations"
    )
    is_primary_contact = models.BooleanField(default=False)
    can_pickup = models.BooleanField(default=True)
    emergency_contact_priority = models.PositiveSmallIntegerField(default=1)
    financial_responsibility = models.BooleanField(default=False)
    access_to_grades = models.BooleanField(default=True)
    access_to_attendance = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ["student", "parent"]
        ordering = ["emergency_contact_priority"]

    def __str__(self):
        return f"{self.student} - {self.parent}"

    def save(self, *args, **kwargs):
        # Ensure only one primary contact per student
        if self.is_primary_contact:
            StudentParentRelation.objects.filter(
                student=self.student, is_primary_contact=True
            ).update(is_primary_contact=False)

        super().save(*args, **kwargs)
