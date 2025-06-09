# students/models.py
import uuid

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
        return self.select_related(
            "user", "current_class__grade", "current_class__section"
        )

    def with_parents(self):
        return self.prefetch_related("student_parent_relations__parent__user")

    def search(self, query):
        if not query:
            return self
        return self.filter(
            Q(admission_number__icontains=query)
            | Q(user__first_name__icontains=query)
            | Q(user__last_name__icontains=query)
            | Q(user__email__icontains=query)
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

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="student_profile",
    )
    admission_number = models.CharField(
        max_length=20, unique=True, validators=[MinLengthValidator(3)], db_index=True
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
    roll_number = models.CharField(max_length=20, blank=True, null=True, db_index=True)
    blood_group = models.CharField(
        max_length=10, choices=BLOOD_GROUP_CHOICES, default="Unknown", db_index=True
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
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="Active", db_index=True
    )
    registration_number = models.CharField(
        max_length=30, blank=True, null=True, unique=True, db_index=True
    )
    nationality = models.CharField(max_length=50, blank=True, null=True)
    religion = models.CharField(max_length=50, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    state = models.CharField(max_length=100, blank=True, null=True)
    postal_code = models.CharField(max_length=20, blank=True, null=True)
    country = models.CharField(max_length=100, blank=True, null=True, default="India")
    photo = models.ImageField(upload_to="student_photos/%Y/%m/", blank=True, null=True)

    # Metadata fields
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
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
            models.Index(fields=["user", "status"]),
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
        return f"{self.user.first_name} {self.user.last_name} ({self.admission_number})"

    def save(self, *args, **kwargs):
        # Set username as admission_number for the associated user
        if self.user and self.admission_number:
            self.user.username = self.admission_number
            self.user.save()

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
        return f"{self.user.first_name} {self.user.last_name}"

    @property
    def age(self):
        if self.user.date_of_birth:
            today = timezone.now().date()
            return (
                today.year
                - self.user.date_of_birth.year
                - (
                    (today.month, today.day)
                    < (self.user.date_of_birth.month, self.user.date_of_birth.day)
                )
            )
        return None

    def is_active(self):
        return self.status == "Active"

    def get_full_name(self):
        return self.full_name

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
        """Get all parents of the student - cached"""
        cache_key = f"student_parents_{self.id}"
        parents = cache.get(cache_key)

        if parents is None:
            parents = list(
                self.student_parent_relations.select_related(
                    "parent__user"
                ).values_list("parent", flat=True)
            )
            cache.set(cache_key, parents, 3600)  # Cache for 1 hour

        return Parent.objects.filter(id__in=parents)

    def get_primary_parent(self):
        """Get the primary parent of the student"""
        primary_relation = (
            self.student_parent_relations.filter(is_primary_contact=True)
            .select_related("parent__user")
            .first()
        )
        return primary_relation.parent if primary_relation else None

    def get_siblings(self):
        """Get all siblings of the student - cached"""
        cache_key = f"student_siblings_{self.id}"
        siblings = cache.get(cache_key)

        if siblings is None:
            parents = self.get_parents()
            if not parents:
                return Student.objects.none()

            sibling_ids = set()
            for parent in parents:
                for relation in parent.parent_student_relations.exclude(student=self):
                    sibling_ids.add(relation.student.id)

            siblings = list(sibling_ids)
            cache.set(cache_key, siblings, 3600)  # Cache for 1 hour

        return Student.objects.filter(id__in=siblings).with_related()

    def get_attendance_percentage(self, academic_year=None, month=None):
        """Get the attendance percentage for a specific period - cached"""
        cache_key = f"student_attendance_percentage_{self.id}_{academic_year}_{month}"
        percentage = cache.get(cache_key)

        if percentage is None:
            try:
                from attendance.models import Attendance

                query = Attendance.objects.filter(student=self)

                if academic_year:
                    query = query.filter(academic_year=academic_year)
                else:
                    current_year = AcademicYear.objects.filter(is_current=True).first()
                    if current_year:
                        query = query.filter(academic_year=current_year)

                if month:
                    query = query.filter(date__month=month)

                total_days = query.count()
                present_days = query.filter(status="Present").count()

                percentage = (
                    round((present_days / total_days) * 100, 2) if total_days > 0 else 0
                )
                cache.set(cache_key, percentage, 1800)  # Cache for 30 minutes
            except:
                percentage = 0

        return percentage

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
