"""
Academic Management Models

This module contains models for managing the academic structure:
- Department: Subject/Activity-based departments
- AcademicYear: Academic year with start/end dates
- Term: Terms within academic years
- Section: Academic divisions (Lower Primary, Upper Primary, etc.)
- Grade: Grades within sections
- Class: Named classes within grades
"""

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

User = get_user_model()


class Department(models.Model):
    """
    Subject or activity-based departments (English, Math, Science, Sports, etc.)
    """

    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    head = models.OneToOneField(
        "teachers.Teacher",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="headed_department",
    )
    creation_date = models.DateField(default=timezone.now)
    is_active = models.BooleanField(default=True)

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "academics_department"
        verbose_name = "Department"
        verbose_name_plural = "Departments"
        ordering = ["name"]

    def __str__(self):
        return self.name

    def get_teachers_count(self):
        """Get count of teachers in this department"""
        return self.teachers.filter(status="Active").count()

    def get_subjects_count(self):
        """Get count of subjects in this department"""
        return self.subjects.filter(is_active=True).count()


class AcademicYear(models.Model):
    """
    Academic year with start and end dates
    """

    name = models.CharField(max_length=20, unique=True, help_text="e.g., '2023-2024'")
    start_date = models.DateField()
    end_date = models.DateField()
    is_current = models.BooleanField(
        default=False, help_text="Only one academic year can be current"
    )

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_academic_years",
    )

    class Meta:
        db_table = "academics_academic_year"
        verbose_name = "Academic Year"
        verbose_name_plural = "Academic Years"
        ordering = ["-start_date"]

    def __str__(self):
        return self.name

    def clean(self):
        """Validate academic year data"""
        if self.start_date and self.end_date:
            if self.start_date >= self.end_date:
                raise ValidationError("Start date must be before end date")

            # Check for overlapping academic years
            overlapping = AcademicYear.objects.filter(
                models.Q(start_date__lte=self.end_date)
                & models.Q(end_date__gte=self.start_date)
            ).exclude(pk=self.pk)

            if overlapping.exists():
                raise ValidationError(
                    "Academic year dates overlap with existing academic year"
                )

    def save(self, *args, **kwargs):
        self.full_clean()

        # Ensure only one current academic year
        if self.is_current:
            AcademicYear.objects.filter(is_current=True).update(is_current=False)

        super().save(*args, **kwargs)

    @property
    def is_active(self):
        """Check if academic year is currently active"""
        today = timezone.now().date()
        return self.start_date <= today <= self.end_date

    def get_terms(self):
        """Get all terms for this academic year"""
        return self.terms.all().order_by("term_number")

    def get_current_term(self):
        """Get the current term if any"""
        today = timezone.now().date()
        return self.terms.filter(start_date__lte=today, end_date__gte=today).first()


class Term(models.Model):
    """
    Terms within an academic year (typically 2-4 terms per year)
    """

    TERM_CHOICES = [
        (1, "First Term"),
        (2, "Second Term"),
        (3, "Third Term"),
        (4, "Fourth Term"),
    ]

    academic_year = models.ForeignKey(
        AcademicYear, on_delete=models.CASCADE, related_name="terms"
    )
    name = models.CharField(
        max_length=50, help_text="e.g., 'First Term', 'Fall Semester'"
    )
    term_number = models.PositiveIntegerField(
        choices=TERM_CHOICES, validators=[MinValueValidator(1), MaxValueValidator(4)]
    )
    start_date = models.DateField()
    end_date = models.DateField()
    is_current = models.BooleanField(default=False)

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "academics_term"
        verbose_name = "Term"
        verbose_name_plural = "Terms"
        unique_together = ["academic_year", "term_number"]
        ordering = ["academic_year", "term_number"]

    def __str__(self):
        return f"{self.academic_year.name} - {self.name}"

    def clean(self):
        """Validate term data"""
        if self.start_date and self.end_date:
            if self.start_date >= self.end_date:
                raise ValidationError("Start date must be before end date")

            # Ensure term dates are within academic year
            if self.academic_year:
                if (
                    self.start_date < self.academic_year.start_date
                    or self.end_date > self.academic_year.end_date
                ):
                    raise ValidationError(
                        "Term dates must be within academic year dates"
                    )

            # Check for overlapping terms in the same academic year
            overlapping = Term.objects.filter(
                academic_year=self.academic_year,
                start_date__lte=self.end_date,
                end_date__gte=self.start_date,
            ).exclude(pk=self.pk)

            if overlapping.exists():
                raise ValidationError(
                    "Term dates overlap with existing term in the same academic year"
                )

    def save(self, *args, **kwargs):
        self.full_clean()

        # Ensure only one current term per academic year
        if self.is_current:
            Term.objects.filter(
                academic_year=self.academic_year, is_current=True
            ).update(is_current=False)

        super().save(*args, **kwargs)

    @property
    def is_active(self):
        """Check if term is currently active"""
        today = timezone.now().date()
        return self.start_date <= today <= self.end_date

    def get_duration_days(self):
        """Get term duration in days"""
        return (self.end_date - self.start_date).days


class Section(models.Model):
    """
    Academic sections (Lower Primary, Upper Primary, Secondary, etc.)
    """

    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sections",
    )
    order_sequence = models.PositiveIntegerField(
        default=1, help_text="Order of display (1=first, 2=second, etc.)"
    )
    is_active = models.BooleanField(default=True)

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "academics_section"
        verbose_name = "Section"
        verbose_name_plural = "Sections"
        ordering = ["order_sequence", "name"]

    def __str__(self):
        return self.name

    def get_grades(self):
        """Get all grades in this section"""
        return self.grades.filter(is_active=True).order_by("order_sequence")

    def get_grades_count(self):
        """Get count of active grades in this section"""
        return self.grades.filter(is_active=True).count()

    def get_total_students(self):
        """Get total students across all grades in this section"""
        return sum(grade.get_total_students() for grade in self.get_grades())


class Grade(models.Model):
    """
    Grades within sections (Grade 1, Grade 2, etc.)
    """

    name = models.CharField(max_length=50)
    description = models.TextField(blank=True)
    section = models.ForeignKey(
        Section, on_delete=models.CASCADE, related_name="grades"
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="grades",
    )
    order_sequence = models.PositiveIntegerField(
        default=1,
        help_text="Order within section (1=first grade, 2=second grade, etc.)",
    )
    is_active = models.BooleanField(default=True)

    # Academic properties
    minimum_age = models.PositiveIntegerField(
        null=True, blank=True, help_text="Minimum age for admission"
    )
    maximum_age = models.PositiveIntegerField(
        null=True, blank=True, help_text="Maximum age for admission"
    )

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "academics_grade"
        verbose_name = "Grade"
        verbose_name_plural = "Grades"
        unique_together = ["section", "name"]
        ordering = ["section", "order_sequence"]

    def __str__(self):
        return f"{self.section.name} - {self.name}"

    def clean(self):
        """Validate grade data"""
        if self.minimum_age and self.maximum_age:
            if self.minimum_age >= self.maximum_age:
                raise ValidationError("Minimum age must be less than maximum age")

    def get_classes(self, academic_year=None):
        """Get all classes for this grade"""
        classes = self.classes.filter(is_active=True)
        if academic_year:
            classes = classes.filter(academic_year=academic_year)
        return classes.order_by("name")

    def get_classes_count(self, academic_year=None):
        """Get count of classes for this grade"""
        return self.get_classes(academic_year).count()

    def get_total_students(self, academic_year=None):
        """Get total students across all classes in this grade"""
        classes = self.get_classes(academic_year)
        return sum(cls.get_students_count() for cls in classes)

    @property
    def display_name(self):
        """Get display name including section"""
        return f"{self.section.name} - {self.name}"


class Class(models.Model):
    """
    Named classes within grades (North, South, Blue, Red, etc.)
    """

    name = models.CharField(
        max_length=50, help_text="Class name (e.g., North, Blue, Alpha)"
    )
    grade = models.ForeignKey(Grade, on_delete=models.CASCADE, related_name="classes")
    section = models.ForeignKey(
        Section, on_delete=models.CASCADE, related_name="classes"
    )
    academic_year = models.ForeignKey(
        AcademicYear, on_delete=models.CASCADE, related_name="classes"
    )
    room_number = models.CharField(max_length=20, blank=True)
    capacity = models.PositiveIntegerField(
        default=30, validators=[MinValueValidator(1), MaxValueValidator(100)]
    )
    class_teacher = models.ForeignKey(
        "teachers.Teacher",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_classes",
    )
    is_active = models.BooleanField(default=True)

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "academics_class"
        verbose_name = "Class"
        verbose_name_plural = "Classes"
        unique_together = ["grade", "name", "academic_year"]
        ordering = ["grade", "name"]

    def __str__(self):
        return self.display_name

    def clean(self):
        """Validate class data"""
        # Auto-set section from grade
        if self.grade and not self.section:
            self.section = self.grade.section

        # Validate section matches grade's section
        if self.grade and self.section and self.grade.section != self.section:
            raise ValidationError("Section must match the grade's section")

    def save(self, *args, **kwargs):
        # Auto-set section from grade if not provided
        if self.grade and not self.section:
            self.section = self.grade.section

        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def display_name(self):
        """Get full display name (e.g., 'Grade 3 North')"""
        return f"{self.grade.name} {self.name}"

    @property
    def full_name(self):
        """Get complete name including section (e.g., 'Lower Primary - Grade 3 North')"""
        return f"{self.section.name} - {self.display_name}"

    def get_students(self):
        """Get all active students in this class"""
        return self.students.filter(status="Active")

    def get_students_count(self):
        """Get count of active students in this class"""
        return self.get_students().count()

    def get_available_capacity(self):
        """Get remaining capacity"""
        return self.capacity - self.get_students_count()

    def is_full(self):
        """Check if class is at capacity"""
        return self.get_students_count() >= self.capacity

    def get_subjects(self, term=None):
        """Get subjects taught in this class"""
        assignments = self.teacher_assignments.filter(is_active=True)
        if term:
            assignments = assignments.filter(term=term)
        return assignments.values_list("subject", flat=True).distinct()

    def get_timetable(self, term=None):
        """Get class timetable"""
        timetable = self.timetable_entries.filter(is_active=True)
        if term:
            timetable = timetable.filter(term=term)
        return timetable.order_by("time_slot__day_of_week", "time_slot__start_time")
