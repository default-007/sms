# students/models.py
import uuid
import logging

from django.conf import settings
from django.core.cache import cache
from django.core.validators import MinLengthValidator, RegexValidator
from django.db import models
from django.db.models import Count, Q
from django.utils import timezone

from src.academics.models import AcademicYear, Class
from src.core.utils import generate_unique_id, generate_unique_id_with_db_check


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

    def with_related(self):
        return self.select_related("current_class__grade", "current_class__section")

    def with_parents(self):
        return self.prefetch_related("student_parent_relations__parent__user")

    def search(self, query):
        if not query:
            return self
        return self.filter(
            Q(admission_number__icontains=query)
            | Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
            | Q(email__icontains=query)
            | Q(roll_number__icontains=query)
        )


class Student(models.Model):
    STATUS_CHOICES = (
        ("Active", "Active"),
        ("Inactive", "Inactive"),
        ("Graduated", "Graduated"),
        ("Suspended", "Suspended"),
        ("Expelled", "Expelled"),
        ("Withdrawn", "Withdrawn"),
    )
    GENDER_CHOICES = (
        ("MALE", "MALE"),
        ("FEMALE", "FEMALE"),
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

    # Use UUID as primary key for better security
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Personal Information (previously from User model)
    first_name = models.CharField(max_length=50, db_index=True)
    last_name = models.CharField(max_length=50, db_index=True)
    email = models.EmailField(blank=True, null=True, db_index=True)
    phone_number = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        validators=[
            RegexValidator(
                regex=r"^\+?1?\d{9,15}$",
                message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed.",
            )
        ],
    )
    date_of_birth = models.DateField(blank=True, null=True, db_index=True)
    gender = models.CharField(choices=GENDER_CHOICES, blank=True)
    address = models.TextField(blank=True)
    profile_picture = models.ImageField(
        upload_to="student_photos/%Y/%m/", blank=True, null=True
    )

    # Academic Information
    admission_number = models.CharField(
        max_length=20,
        unique=True,
        db_index=True,
        validators=[
            MinLengthValidator(3),
            RegexValidator(
                regex=r"^[A-Z0-9\-/]+$",
                message="Admission number must contain only uppercase letters, numbers, hyphens, and slashes.",
            ),
        ],
    )
    registration_number = models.CharField(
        max_length=50, unique=True, blank=True, null=True, db_index=True
    )
    admission_date = models.DateField(db_index=True)
    current_class = models.ForeignKey(
        Class,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="students",
        db_index=True,
    )
    roll_number = models.CharField(max_length=10, blank=True, db_index=True)

    # Health and Emergency Information
    blood_group = models.CharField(
        max_length=10, choices=BLOOD_GROUP_CHOICES, default="Unknown", db_index=True
    )
    medical_conditions = models.TextField(blank=True)
    emergency_contact_name = models.CharField(max_length=100)
    emergency_contact_number = models.CharField(
        max_length=20,
        validators=[
            RegexValidator(
                regex=r"^\+?1?\d{9,15}$",
                message="Emergency contact number must be entered in the format: '+999999999'. Up to 15 digits allowed.",
            )
        ],
    )
    emergency_contact_relationship = models.CharField(max_length=50, blank=True)

    # Academic History
    previous_school = models.CharField(max_length=200, blank=True)
    transfer_certificate_number = models.CharField(max_length=100, blank=True)

    # Status and Metadata
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="Active", db_index=True
    )
    is_active = models.BooleanField(default=True, db_index=True)
    date_joined = models.DateTimeField(auto_now_add=True, db_index=True)
    last_updated = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_students",
    )

    objects = StudentQuerySet.as_manager()

    class Meta:
        ordering = ["admission_number"]
        indexes = [
            models.Index(fields=["admission_date", "status"]),
            models.Index(fields=["current_class", "status"]),
            models.Index(fields=["first_name", "last_name"]),
            models.Index(fields=["email"]),
        ]
        permissions = [
            ("view_student_details", "Can view detailed student information"),
            ("export_student_data", "Can export student data"),
            ("promote_student", "Can promote student to next class"),
            ("graduate_student", "Can mark student as graduated"),
            ("generate_student_id", "Can generate student ID card"),
            ("bulk_import_students", "Can bulk import students"),
        ]

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.admission_number})"

    def save(self, *args, **kwargs):
        if not self.registration_number:
            admission_year = self.admission_date.year
            self.registration_number = f"STU-{admission_year}-{generate_unique_id(6)}"

        if self.pk:  # Only clear cache for existing objects
            cache.delete_many(
                [
                    f"student_attendance_percentage_{self.id}",
                    f"student_siblings_{self.id}",
                    f"student_parents_{self.id}",
                ]
            )

        super().save(*args, **kwargs)

    def clean(self):
        from django.core.exceptions import ValidationError

        # Validate admission date
        if self.admission_date and self.admission_date > timezone.now().date():
            raise ValidationError("Admission date cannot be in the future.")

        # Validate emergency contact
        if not self.emergency_contact_name or not self.emergency_contact_number:
            raise ValidationError("Emergency contact information is required.")

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def age(self):
        """Calculate age from date of birth"""
        if not self.date_of_birth:
            return None
        today = timezone.now().date()
        return (
            today.year
            - self.date_of_birth.year
            - (
                (today.month, today.day)
                < (self.date_of_birth.month, self.date_of_birth.day)
            )
        )

    def get_parents(self):
        """Get all parents related to this student"""
        return Parent.objects.filter(
            parent_student_relations__student=self
        ).select_related("user")

    def get_primary_parent(self):
        """Get the primary contact parent"""
        try:
            relation = (
                self.student_parent_relations.filter(is_primary_contact=True)
                .select_related("parent__user")
                .first()
            )
            return relation.parent if relation else None
        except Exception:
            return None

    def get_siblings(self):
        """Get siblings through shared parents"""
        cache_key = f"student_siblings_{self.id}"
        siblings = cache.get(cache_key)

        if siblings is None:
            parent_ids = self.student_parent_relations.values_list(
                "parent_id", flat=True
            )
            if parent_ids:
                siblings = (
                    Student.objects.filter(
                        student_parent_relations__parent_id__in=parent_ids
                    )
                    .exclude(id=self.id)
                    .distinct()
                    .select_related("current_class")
                )
                siblings = list(siblings)  # Convert to list for caching
            else:
                siblings = []

            cache.set(cache_key, siblings, 3600)  # Cache for 1 hour

        return siblings

    def get_attendance_percentage(self, academic_year=None, term=None):
        """Calculate attendance percentage"""
        cache_key = f"student_attendance_percentage_{self.id}_{academic_year}_{term}"
        percentage = cache.get(cache_key)

        if percentage is None:
            from src.attendance.models import StudentAttendance

            attendance_qs = StudentAttendance.objects.filter(student=self)

            if academic_year:
                attendance_qs = attendance_qs.filter(date__year=academic_year)
            if term:
                attendance_qs = attendance_qs.filter(term=term)

            total_days = attendance_qs.count()
            present_days = attendance_qs.filter(status="present").count()

            percentage = (present_days / total_days * 100) if total_days > 0 else 0
            cache.set(cache_key, percentage, 1800)  # Cache for 30 minutes

        return round(percentage, 2)

    def get_current_academic_year(self):
        """Get current academic year"""
        return AcademicYear.objects.filter(is_current=True).first()

    def is_eligible_for_promotion(self):
        """Check if student is eligible for promotion"""
        return self.status == "Active" and self.current_class is not None

    def promote_to_next_class(self, new_class):
        """Promote student to next class"""
        old_class = self.current_class
        self.current_class = new_class
        self.save()

        # Clear cache
        cache.delete(f"student_attendance_percentage_{self.id}")

        # Log the promotion
        from core.models import AuditLog

        AuditLog.objects.create(
            user=None,
            action="promote",
            entity_type="student",
            entity_id=str(self.id),
            data_before={"current_class": str(old_class.id) if old_class else None},
            data_after={"current_class": str(new_class.id)},
        )

        return True

    def mark_as_graduated(self):
        """Mark student as graduated"""
        old_status = self.status
        self.status = "Graduated"
        self.save()

        # Log the graduation
        from core.models import AuditLog

        AuditLog.objects.create(
            user=None,
            action="graduate",
            entity_type="student",
            entity_id=str(self.id),
            data_before={"status": old_status},
            data_after={"status": "Graduated"},
        )

        return True

    def mark_as_withdrawn(self, reason=""):
        """Mark student as withdrawn"""
        old_status = self.status
        self.status = "Withdrawn"
        self.save()

        # Log the withdrawal
        from core.models import AuditLog

        AuditLog.objects.create(
            user=None,
            action="withdraw",
            entity_type="student",
            entity_id=str(self.id),
            data_before={"status": old_status},
            data_after={"status": "Withdrawn", "reason": reason},
        )

        return True


class ParentQuerySet(models.QuerySet):
    def with_related(self):
        return self.select_related("user")

    def with_students(self):
        return self.prefetch_related("parent_student_relations__student__user")

    def search(self, query):
        if not query:
            return self
        return self.filter(
            Q(user__first_name__icontains=query)
            | Q(user__last_name__icontains=query)
            | Q(user__email__icontains=query)
            | Q(user__phone_number__icontains=query)
            | Q(occupation__icontains=query)
        )


class Parent(models.Model):
    RELATION_CHOICES = (
        ("Father", "Father"),
        ("Mother", "Mother"),
        ("Guardian", "Guardian"),
        ("Grandparent", "Grandparent"),
        ("Uncle", "Uncle"),
        ("Aunt", "Aunt"),
        ("Other", "Other"),
    )

    # Use UUID as primary key for better security
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

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
    relation_with_student = models.CharField(
        max_length=20, choices=RELATION_CHOICES, db_index=True
    )
    workplace = models.CharField(max_length=200, blank=True, null=True)
    work_address = models.TextField(blank=True, null=True)
    work_phone = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        validators=[
            RegexValidator(
                regex=r"^\+?1?\d{9,15}$",
                message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed.",
            )
        ],
    )
    emergency_contact = models.BooleanField(default=True, db_index=True)
    photo = models.ImageField(upload_to="parent_photos/%Y/%m/", blank=True, null=True)

    # Metadata fields
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_parents",
    )

    objects = ParentQuerySet.as_manager()

    class Meta:
        ordering = ["user__first_name", "user__last_name"]
        indexes = [
            models.Index(fields=["relation_with_student", "emergency_contact"]),
            models.Index(fields=["user", "relation_with_student"]),
        ]
        permissions = [
            ("view_parent_details", "Can view detailed parent information"),
            ("export_parent_data", "Can export parent data"),
            ("bulk_import_parents", "Can bulk import parents"),
        ]

    def __str__(self):
        return f"{self.user.first_name} {self.user.last_name} ({self.relation_with_student})"

    @property
    def full_name(self):
        return f"{self.user.first_name} {self.user.last_name}"

    def get_full_name(self):
        return self.full_name

    def get_students(self):
        """Get all students related to this parent"""
        return Student.objects.filter(
            student_parent_relations__parent=self
        ).with_related()

    def get_primary_students(self):
        """Get students for which this parent is the primary contact"""
        return Student.objects.filter(
            student_parent_relations__parent=self,
            student_parent_relations__is_primary_contact=True,
        ).with_related()


class StudentParentRelation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="student_parent_relations"
    )
    parent = models.ForeignKey(
        Parent, on_delete=models.CASCADE, related_name="parent_student_relations"
    )
    is_primary_contact = models.BooleanField(default=False, db_index=True)
    can_pickup = models.BooleanField(default=True)
    emergency_contact_priority = models.PositiveSmallIntegerField(default=1)
    financial_responsibility = models.BooleanField(default=False)
    access_to_grades = models.BooleanField(default=True)
    access_to_attendance = models.BooleanField(default=True)
    access_to_financial_info = models.BooleanField(default=False)

    # Communication preferences
    receive_sms = models.BooleanField(default=True)
    receive_email = models.BooleanField(default=True)
    receive_push_notifications = models.BooleanField(default=True)

    # Metadata fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_relations",
    )

    class Meta:
        unique_together = ["student", "parent"]
        ordering = ["emergency_contact_priority"]
        indexes = [
            models.Index(fields=["student", "is_primary_contact"]),
            models.Index(fields=["parent", "is_primary_contact"]),
        ]

    def __str__(self):
        return f"{self.student} - {self.parent}"

    def save(self, *args, **kwargs):
        # Ensure only one primary contact per student
        if self.is_primary_contact:
            StudentParentRelation.objects.filter(
                student=self.student, is_primary_contact=True
            ).exclude(id=self.id).update(is_primary_contact=False)

        # Clear related cache
        cache.delete(f"student_parents_{self.student.id}")
        cache.delete(f"student_siblings_{self.student.id}")

        super().save(*args, **kwargs)

    def clean(self):
        from django.core.exceptions import ValidationError

        # Validate emergency contact priority
        if self.emergency_contact_priority < 1:
            raise ValidationError("Emergency contact priority must be at least 1.")
