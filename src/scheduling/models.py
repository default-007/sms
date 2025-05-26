from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import datetime, time, timedelta
import uuid


class TimeSlot(models.Model):
    """Time slots for scheduling periods"""

    DAY_CHOICES = [
        (0, "Monday"),
        (1, "Tuesday"),
        (2, "Wednesday"),
        (3, "Thursday"),
        (4, "Friday"),
        (5, "Saturday"),
        (6, "Sunday"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    day_of_week = models.IntegerField(choices=DAY_CHOICES)
    start_time = models.TimeField()
    end_time = models.TimeField()
    duration_minutes = models.PositiveIntegerField(
        validators=[MinValueValidator(15), MaxValueValidator(180)]
    )
    period_number = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(12)]
    )
    name = models.CharField(
        max_length=50, blank=True
    )  # e.g., "Period 1", "Lunch", "Assembly"
    is_break = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "scheduling_timeslot"
        unique_together = ["day_of_week", "period_number", "start_time"]
        ordering = ["day_of_week", "period_number", "start_time"]
        indexes = [
            models.Index(fields=["day_of_week", "start_time"]),
            models.Index(fields=["period_number"]),
        ]

    def clean(self):
        if self.start_time >= self.end_time:
            raise ValidationError("Start time must be before end time")

        # Calculate duration
        start_datetime = datetime.combine(datetime.today(), self.start_time)
        end_datetime = datetime.combine(datetime.today(), self.end_time)
        calculated_duration = int((end_datetime - start_datetime).total_seconds() / 60)

        if abs(self.duration_minutes - calculated_duration) > 1:
            raise ValidationError("Duration doesn't match start and end times")

    def save(self, *args, **kwargs):
        self.full_clean()
        if not self.name:
            if self.is_break:
                self.name = f"Break {self.period_number}"
            else:
                self.name = f"Period {self.period_number}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.get_day_of_week_display()} - {self.name} ({self.start_time}-{self.end_time})"


class Room(models.Model):
    """Rooms/Classrooms for scheduling"""

    ROOM_TYPES = [
        ("classroom", "Regular Classroom"),
        ("laboratory", "Laboratory"),
        ("library", "Library"),
        ("auditorium", "Auditorium"),
        ("gymnasium", "Gymnasium"),
        ("computer_lab", "Computer Lab"),
        ("music_room", "Music Room"),
        ("art_room", "Art Room"),
        ("conference", "Conference Room"),
        ("outdoor", "Outdoor Area"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    number = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=100)
    room_type = models.CharField(max_length=20, choices=ROOM_TYPES, default="classroom")
    building = models.CharField(max_length=50, blank=True)
    floor = models.CharField(max_length=10, blank=True)
    capacity = models.PositiveIntegerField(default=30)
    equipment = models.JSONField(
        default=list, blank=True
    )  # ['projector', 'computer', 'whiteboard']
    is_available = models.BooleanField(default=True)
    maintenance_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "scheduling_room"
        ordering = ["building", "floor", "number"]
        indexes = [
            models.Index(fields=["room_type"]),
            models.Index(fields=["is_available"]),
        ]

    def __str__(self):
        return f"{self.number} - {self.name}"


class Timetable(models.Model):
    """Main timetable entries"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    class_assigned = models.ForeignKey(
        "academics.Class", on_delete=models.CASCADE, related_name="timetable_entries"
    )
    subject = models.ForeignKey(
        "subjects.Subject", on_delete=models.CASCADE, related_name="timetable_entries"
    )
    teacher = models.ForeignKey(
        "teachers.Teacher", on_delete=models.CASCADE, related_name="timetable_entries"
    )
    time_slot = models.ForeignKey(
        TimeSlot, on_delete=models.CASCADE, related_name="timetable_entries"
    )
    room = models.ForeignKey(
        Room,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="timetable_entries",
    )
    term = models.ForeignKey(
        "academics.Term", on_delete=models.CASCADE, related_name="timetable_entries"
    )
    effective_from_date = models.DateField()
    effective_to_date = models.DateField()
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_timetables",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "scheduling_timetable"
        unique_together = [
            ["class_assigned", "time_slot", "effective_from_date", "effective_to_date"],
            ["teacher", "time_slot", "effective_from_date", "effective_to_date"],
            ["room", "time_slot", "effective_from_date", "effective_to_date"],
        ]
        indexes = [
            models.Index(fields=["class_assigned", "term"]),
            models.Index(fields=["teacher", "term"]),
            models.Index(fields=["time_slot", "effective_from_date"]),
            models.Index(fields=["is_active"]),
        ]

    def clean(self):
        if self.effective_from_date > self.effective_to_date:
            raise ValidationError("From date must be before to date")

        # Check for conflicts
        conflicts = self._check_conflicts()
        if conflicts:
            raise ValidationError(f"Scheduling conflicts found: {conflicts}")

    def _check_conflicts(self):
        """Check for scheduling conflicts"""
        conflicts = []

        # Teacher conflict
        teacher_conflicts = Timetable.objects.filter(
            teacher=self.teacher,
            time_slot=self.time_slot,
            effective_from_date__lte=self.effective_to_date,
            effective_to_date__gte=self.effective_from_date,
            is_active=True,
        ).exclude(pk=self.pk)

        if teacher_conflicts.exists():
            conflicts.append("Teacher already scheduled")

        # Room conflict
        if self.room:
            room_conflicts = Timetable.objects.filter(
                room=self.room,
                time_slot=self.time_slot,
                effective_from_date__lte=self.effective_to_date,
                effective_to_date__gte=self.effective_from_date,
                is_active=True,
            ).exclude(pk=self.pk)

            if room_conflicts.exists():
                conflicts.append("Room already booked")

        # Class conflict
        class_conflicts = Timetable.objects.filter(
            class_assigned=self.class_assigned,
            time_slot=self.time_slot,
            effective_from_date__lte=self.effective_to_date,
            effective_to_date__gte=self.effective_from_date,
            is_active=True,
        ).exclude(pk=self.pk)

        if class_conflicts.exists():
            conflicts.append("Class already has a subject scheduled")

        return conflicts

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.class_assigned} - {self.subject} - {self.time_slot}"


class TimetableTemplate(models.Model):
    """Reusable timetable templates"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    grade = models.ForeignKey(
        "academics.Grade", on_delete=models.CASCADE, related_name="timetable_templates"
    )
    is_default = models.BooleanField(default=False)
    configuration = models.JSONField(default=dict)  # Template configuration
    created_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_templates",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "scheduling_timetable_template"
        ordering = ["grade", "name"]

    def __str__(self):
        return f"{self.name} - {self.grade}"


class SubstituteTeacher(models.Model):
    """Substitute teacher assignments"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    original_timetable = models.ForeignKey(
        Timetable, on_delete=models.CASCADE, related_name="substitutions"
    )
    substitute_teacher = models.ForeignKey(
        "teachers.Teacher",
        on_delete=models.CASCADE,
        related_name="substitute_assignments",
    )
    date = models.DateField()
    reason = models.CharField(max_length=200)
    notes = models.TextField(blank=True)
    approved_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        related_name="approved_substitutions",
    )
    created_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_substitutions",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "scheduling_substitute_teacher"
        unique_together = ["original_timetable", "date"]
        indexes = [
            models.Index(fields=["date"]),
            models.Index(fields=["substitute_teacher", "date"]),
        ]

    def clean(self):
        # Check if substitute teacher is available
        substitute_conflicts = Timetable.objects.filter(
            teacher=self.substitute_teacher,
            time_slot=self.original_timetable.time_slot,
            effective_from_date__lte=self.date,
            effective_to_date__gte=self.date,
            is_active=True,
        )

        if substitute_conflicts.exists():
            raise ValidationError("Substitute teacher is not available at this time")

    def __str__(self):
        return f"Substitute: {self.substitute_teacher} for {self.original_timetable} on {self.date}"


class SchedulingConstraint(models.Model):
    """Constraints for timetable generation"""

    CONSTRAINT_TYPES = [
        ("teacher_availability", "Teacher Availability"),
        ("room_requirement", "Room Requirement"),
        ("subject_priority", "Subject Priority"),
        ("consecutive_periods", "Consecutive Periods"),
        ("daily_limit", "Daily Subject Limit"),
        ("time_preference", "Time Preference"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    constraint_type = models.CharField(max_length=30, choices=CONSTRAINT_TYPES)
    parameters = models.JSONField(default=dict)
    priority = models.IntegerField(
        default=5, validators=[MinValueValidator(1), MaxValueValidator(10)]
    )
    is_hard_constraint = models.BooleanField(
        default=True
    )  # True = must satisfy, False = prefer
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "scheduling_constraint"
        ordering = ["-priority", "name"]

    def __str__(self):
        return f"{self.name} ({self.get_constraint_type_display()})"


class TimetableGeneration(models.Model):
    """Track timetable generation sessions"""

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("running", "Running"),
        ("completed", "Completed"),
        ("failed", "Failed"),
        ("cancelled", "Cancelled"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    term = models.ForeignKey(
        "academics.Term", on_delete=models.CASCADE, related_name="timetable_generations"
    )
    grades = models.ManyToManyField(
        "academics.Grade", related_name="timetable_generations"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    algorithm_used = models.CharField(max_length=50, default="genetic_algorithm")
    parameters = models.JSONField(default=dict)
    result_summary = models.JSONField(default=dict)
    conflicts_resolved = models.IntegerField(default=0)
    optimization_score = models.FloatField(null=True, blank=True)
    execution_time_seconds = models.FloatField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    started_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        related_name="started_generations",
    )
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "scheduling_timetable_generation"
        ordering = ["-started_at"]

    def __str__(self):
        return f"Generation for {self.term} - {self.status}"
