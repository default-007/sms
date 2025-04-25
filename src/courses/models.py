from django.db import models
from django.conf import settings


class Department(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    head = models.ForeignKey(
        "teachers.Teacher",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="headed_departments",
    )
    creation_date = models.DateField(auto_now_add=True)

    def __str__(self):
        return self.name


class AcademicYear(models.Model):
    name = models.CharField(max_length=50)
    start_date = models.DateField()
    end_date = models.DateField()
    is_current = models.BooleanField(default=False)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        # Ensure only one academic year is marked as current
        if self.is_current:
            AcademicYear.objects.filter(is_current=True).update(is_current=False)
        super().save(*args, **kwargs)


class Grade(models.Model):
    name = models.CharField(max_length=50)
    description = models.TextField(blank=True)
    department = models.ForeignKey(
        Department, on_delete=models.CASCADE, related_name="grades"
    )

    def __str__(self):
        return self.name


class Section(models.Model):
    name = models.CharField(max_length=20)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name


class Class(models.Model):
    grade = models.ForeignKey(Grade, on_delete=models.CASCADE, related_name="classes")
    section = models.ForeignKey(
        Section, on_delete=models.CASCADE, related_name="classes"
    )
    academic_year = models.ForeignKey(
        AcademicYear, on_delete=models.CASCADE, related_name="classes"
    )
    room_number = models.CharField(max_length=20, blank=True)
    capacity = models.PositiveIntegerField(default=30)
    class_teacher = models.ForeignKey(
        to="teachers.Teacher",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_classes",
    )

    class Meta:
        verbose_name_plural = "Classes"
        unique_together = ("grade", "section", "academic_year")

    def __str__(self):
        return f"{self.grade.name} - {self.section.name} ({self.academic_year.name})"


class Subject(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20, unique=True)
    description = models.TextField(blank=True)
    department = models.ForeignKey(
        Department, on_delete=models.CASCADE, related_name="subjects"
    )
    credit_hours = models.DecimalField(max_digits=3, decimal_places=1, default=1.0)
    is_elective = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.name} ({self.code})"


class Syllabus(models.Model):
    subject = models.ForeignKey(
        Subject, on_delete=models.CASCADE, related_name="syllabi"
    )
    grade = models.ForeignKey(Grade, on_delete=models.CASCADE, related_name="syllabi")
    academic_year = models.ForeignKey(
        AcademicYear, on_delete=models.CASCADE, related_name="syllabi"
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    content = models.JSONField(default=dict)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="created_syllabi",
    )
    last_updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="updated_syllabi",
    )
    last_updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Syllabi"
        unique_together = ("subject", "grade", "academic_year")

    def __str__(self):
        return f"Syllabus for {self.subject.name} - {self.grade.name} ({self.academic_year.name})"


class TimeSlot(models.Model):
    DAY_CHOICES = [
        (0, "Monday"),
        (1, "Tuesday"),
        (2, "Wednesday"),
        (3, "Thursday"),
        (4, "Friday"),
        (5, "Saturday"),
        (6, "Sunday"),
    ]

    day_of_week = models.IntegerField(choices=DAY_CHOICES)
    start_time = models.TimeField()
    end_time = models.TimeField()
    duration_minutes = models.PositiveIntegerField()

    def __str__(self):
        return f"{self.get_day_of_week_display()} {self.start_time} - {self.end_time}"

    def save(self, *args, **kwargs):
        # Calculate duration in minutes
        start_datetime = datetime.combine(date.today(), self.start_time)
        end_datetime = datetime.combine(date.today(), self.end_time)
        delta = end_datetime - start_datetime
        self.duration_minutes = delta.seconds // 60
        super().save(*args, **kwargs)


class Timetable(models.Model):
    class_obj = models.ForeignKey(
        Class, on_delete=models.CASCADE, related_name="timetable_entries"
    )
    subject = models.ForeignKey(
        Subject, on_delete=models.CASCADE, related_name="timetable_entries"
    )
    teacher = models.ForeignKey(
        "teachers.Teacher", on_delete=models.CASCADE, related_name="timetable_entries"
    )
    time_slot = models.ForeignKey(
        TimeSlot, on_delete=models.CASCADE, related_name="timetable_entries"
    )
    room = models.CharField(max_length=20, blank=True)
    effective_from_date = models.DateField()
    effective_to_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.class_obj} - {self.subject} - {self.time_slot}"


class Assignment(models.Model):
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("published", "Published"),
        ("closed", "Closed"),
    ]

    SUBMISSION_CHOICES = [
        ("online", "Online"),
        ("physical", "Physical"),
    ]

    title = models.CharField(max_length=200)
    description = models.TextField()
    class_obj = models.ForeignKey(
        Class, on_delete=models.CASCADE, related_name="assignments"
    )
    subject = models.ForeignKey(
        Subject, on_delete=models.CASCADE, related_name="assignments"
    )
    teacher = models.ForeignKey(
        "teachers.Teacher", on_delete=models.CASCADE, related_name="assignments"
    )
    assigned_date = models.DateField(auto_now_add=True)
    due_date = models.DateField()
    total_marks = models.PositiveIntegerField()
    attachment = models.FileField(upload_to="assignments/", null=True, blank=True)
    submission_type = models.CharField(
        max_length=10, choices=SUBMISSION_CHOICES, default="online"
    )
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="draft")

    def __str__(self):
        return self.title


class AssignmentSubmission(models.Model):
    STATUS_CHOICES = [
        ("submitted", "Submitted"),
        ("late", "Late"),
        ("graded", "Graded"),
    ]

    assignment = models.ForeignKey(
        Assignment, on_delete=models.CASCADE, related_name="submissions"
    )
    student = models.ForeignKey(
        "students.Student",
        on_delete=models.CASCADE,
        related_name="assignment_submissions",
    )
    submission_date = models.DateTimeField(auto_now_add=True)
    content = models.TextField(blank=True)
    file = models.FileField(upload_to="assignment_submissions/", null=True, blank=True)
    remarks = models.TextField(blank=True)
    marks_obtained = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    status = models.CharField(
        max_length=10, choices=STATUS_CHOICES, default="submitted"
    )
    graded_by = models.ForeignKey(
        "teachers.Teacher",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="graded_submissions",
    )
    graded_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.assignment.title} - {self.student}"

    def save(self, *args, **kwargs):
        # Check if submission is late
        if self.submission_date.date() > self.assignment.due_date:
            self.status = "late"
        super().save(*args, **kwargs)
