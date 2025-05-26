import json
from datetime import datetime, time

from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Q

from academics.models import Class, Grade, Term
from subjects.models import Subject
from teachers.models import Teacher

from .models import (
    Room,
    SchedulingConstraint,
    SubstituteTeacher,
    TimeSlot,
    Timetable,
    TimetableGeneration,
    TimetableTemplate,
)


class TimeSlotForm(forms.ModelForm):
    """Form for creating/editing time slots"""

    class Meta:
        model = TimeSlot
        fields = [
            "day_of_week",
            "start_time",
            "end_time",
            "duration_minutes",
            "period_number",
            "name",
            "is_break",
            "is_active",
        ]
        widgets = {
            "start_time": forms.TimeInput(attrs={"type": "time"}),
            "end_time": forms.TimeInput(attrs={"type": "time"}),
            "duration_minutes": forms.NumberInput(attrs={"min": 15, "max": 180}),
            "period_number": forms.NumberInput(attrs={"min": 1, "max": 12}),
            "name": forms.TextInput(
                attrs={"placeholder": "e.g., Period 1, Lunch Break"}
            ),
        }

    def clean(self):
        cleaned_data = super().clean()
        start_time = cleaned_data.get("start_time")
        end_time = cleaned_data.get("end_time")
        duration_minutes = cleaned_data.get("duration_minutes")
        day_of_week = cleaned_data.get("day_of_week")
        period_number = cleaned_data.get("period_number")

        # Validate time range
        if start_time and end_time:
            if start_time >= end_time:
                raise ValidationError("Start time must be before end time")

            # Calculate expected duration
            start_datetime = datetime.combine(datetime.today(), start_time)
            end_datetime = datetime.combine(datetime.today(), end_time)
            calculated_duration = int(
                (end_datetime - start_datetime).total_seconds() / 60
            )

            if duration_minutes and abs(duration_minutes - calculated_duration) > 1:
                raise ValidationError("Duration doesn't match start and end times")

        # Check for overlapping time slots
        if day_of_week is not None and start_time and end_time:
            overlapping = TimeSlot.objects.filter(
                day_of_week=day_of_week,
                start_time__lt=end_time,
                end_time__gt=start_time,
                is_active=True,
            )

            if self.instance.pk:
                overlapping = overlapping.exclude(pk=self.instance.pk)

            if overlapping.exists():
                raise ValidationError(
                    "This time slot overlaps with existing time slots"
                )

        # Check for duplicate period numbers on same day
        if day_of_week is not None and period_number:
            duplicate_period = TimeSlot.objects.filter(
                day_of_week=day_of_week, period_number=period_number, is_active=True
            )

            if self.instance.pk:
                duplicate_period = duplicate_period.exclude(pk=self.instance.pk)

            if duplicate_period.exists():
                raise ValidationError("Period number already exists for this day")

        return cleaned_data


class RoomForm(forms.ModelForm):
    """Form for creating/editing rooms"""

    equipment_choices = [
        ("projector", "Projector"),
        ("computer", "Computer"),
        ("whiteboard", "Whiteboard"),
        ("blackboard", "Blackboard"),
        ("smart_board", "Smart Board"),
        ("speakers", "Speakers"),
        ("microphone", "Microphone"),
        ("air_conditioning", "Air Conditioning"),
        ("laboratory_equipment", "Laboratory Equipment"),
        ("sports_equipment", "Sports Equipment"),
    ]

    equipment = forms.MultipleChoiceField(
        choices=equipment_choices,
        widget=forms.CheckboxSelectMultiple,
        required=False,
        help_text="Select available equipment in this room",
    )

    class Meta:
        model = Room
        fields = [
            "number",
            "name",
            "room_type",
            "building",
            "floor",
            "capacity",
            "equipment",
            "is_available",
            "maintenance_notes",
        ]
        widgets = {
            "number": forms.TextInput(attrs={"placeholder": "e.g., 101, A-201"}),
            "name": forms.TextInput(
                attrs={"placeholder": "e.g., Physics Lab, Main Hall"}
            ),
            "capacity": forms.NumberInput(attrs={"min": 1, "max": 500}),
            "maintenance_notes": forms.Textarea(attrs={"rows": 3}),
        }

    def clean_number(self):
        number = self.cleaned_data["number"]

        # Check for duplicate room numbers
        duplicate = Room.objects.filter(number=number)
        if self.instance.pk:
            duplicate = duplicate.exclude(pk=self.instance.pk)

        if duplicate.exists():
            raise ValidationError("Room number already exists")

        return number


class TimetableForm(forms.ModelForm):
    """Form for creating/editing timetable entries"""

    class Meta:
        model = Timetable
        fields = [
            "class_assigned",
            "subject",
            "teacher",
            "time_slot",
            "room",
            "term",
            "effective_from_date",
            "effective_to_date",
            "notes",
        ]
        widgets = {
            "effective_from_date": forms.DateInput(attrs={"type": "date"}),
            "effective_to_date": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Filter teachers based on subject assignment
        if "subject" in self.data:
            try:
                subject_id = int(self.data.get("subject"))
                self.fields["teacher"].queryset = Teacher.objects.filter(
                    teacher_assignments__subject_id=subject_id, status="active"
                ).distinct()
            except (ValueError, TypeError):
                self.fields["teacher"].queryset = Teacher.objects.none()
        elif self.instance.pk:
            self.fields["teacher"].queryset = Teacher.objects.filter(
                teacher_assignments__subject=self.instance.subject, status="active"
            ).distinct()
        else:
            self.fields["teacher"].queryset = Teacher.objects.none()

    def clean(self):
        cleaned_data = super().clean()
        class_assigned = cleaned_data.get("class_assigned")
        subject = cleaned_data.get("subject")
        teacher = cleaned_data.get("teacher")
        time_slot = cleaned_data.get("time_slot")
        room = cleaned_data.get("room")
        term = cleaned_data.get("term")
        effective_from = cleaned_data.get("effective_from_date")
        effective_to = cleaned_data.get("effective_to_date")

        # Validate date range
        if effective_from and effective_to:
            if effective_from > effective_to:
                raise ValidationError("From date must be before to date")

        # Validate term dates
        if term and effective_from and effective_to:
            if effective_from < term.start_date or effective_to > term.end_date:
                raise ValidationError("Timetable dates must be within term dates")

        # Check for conflicts
        if all([teacher, time_slot, effective_from, effective_to]):
            # Teacher conflicts
            teacher_conflicts = Timetable.objects.filter(
                teacher=teacher,
                time_slot=time_slot,
                effective_from_date__lte=effective_to,
                effective_to_date__gte=effective_from,
                is_active=True,
            )

            if self.instance.pk:
                teacher_conflicts = teacher_conflicts.exclude(pk=self.instance.pk)

            if teacher_conflicts.exists():
                raise ValidationError("Teacher is already scheduled at this time")

        # Room conflicts
        if all([room, time_slot, effective_from, effective_to]):
            room_conflicts = Timetable.objects.filter(
                room=room,
                time_slot=time_slot,
                effective_from_date__lte=effective_to,
                effective_to_date__gte=effective_from,
                is_active=True,
            )

            if self.instance.pk:
                room_conflicts = room_conflicts.exclude(pk=self.instance.pk)

            if room_conflicts.exists():
                raise ValidationError("Room is already booked at this time")

        # Class conflicts
        if all([class_assigned, time_slot, effective_from, effective_to]):
            class_conflicts = Timetable.objects.filter(
                class_assigned=class_assigned,
                time_slot=time_slot,
                effective_from_date__lte=effective_to,
                effective_to_date__gte=effective_from,
                is_active=True,
            )

            if self.instance.pk:
                class_conflicts = class_conflicts.exclude(pk=self.instance.pk)

            if class_conflicts.exists():
                raise ValidationError(
                    "Class already has a subject scheduled at this time"
                )

        return cleaned_data


class BulkTimetableForm(forms.Form):
    """Form for bulk timetable creation"""

    term = forms.ModelChoiceField(
        queryset=Term.objects.all(), empty_label="Select Term"
    )
    grades = forms.ModelMultipleChoiceField(
        queryset=Grade.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        help_text="Select grades to create timetables for",
    )
    copy_from_term = forms.ModelChoiceField(
        queryset=Term.objects.all(),
        required=False,
        empty_label="Don't copy (create new)",
        help_text="Optionally copy timetable from another term",
    )

    def clean(self):
        cleaned_data = super().clean()
        term = cleaned_data.get("term")
        copy_from_term = cleaned_data.get("copy_from_term")

        if copy_from_term and copy_from_term == term:
            raise ValidationError("Cannot copy from the same term")

        return cleaned_data


class SubstituteTeacherForm(forms.ModelForm):
    """Form for creating substitute teacher assignments"""

    class Meta:
        model = SubstituteTeacher
        fields = ["original_timetable", "substitute_teacher", "date", "reason", "notes"]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
            "reason": forms.TextInput(
                attrs={"placeholder": "e.g., Sick leave, Emergency"}
            ),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Filter substitute teachers to exclude the original teacher
        if "original_timetable" in self.data:
            try:
                timetable_id = self.data.get("original_timetable")
                original_timetable = Timetable.objects.get(id=timetable_id)
                self.fields["substitute_teacher"].queryset = Teacher.objects.filter(
                    status="active"
                ).exclude(id=original_timetable.teacher.id)
            except (ValueError, TypeError, Timetable.DoesNotExist):
                self.fields["substitute_teacher"].queryset = Teacher.objects.filter(
                    status="active"
                )
        elif self.instance.pk:
            self.fields["substitute_teacher"].queryset = Teacher.objects.filter(
                status="active"
            ).exclude(id=self.instance.original_timetable.teacher.id)
        else:
            self.fields["substitute_teacher"].queryset = Teacher.objects.filter(
                status="active"
            )

    def clean(self):
        cleaned_data = super().clean()
        original_timetable = cleaned_data.get("original_timetable")
        substitute_teacher = cleaned_data.get("substitute_teacher")
        date = cleaned_data.get("date")

        # Check if substitute teacher is available
        if all([substitute_teacher, original_timetable, date]):
            conflicts = Timetable.objects.filter(
                teacher=substitute_teacher,
                time_slot=original_timetable.time_slot,
                effective_from_date__lte=date,
                effective_to_date__gte=date,
                is_active=True,
            )

            if conflicts.exists():
                raise ValidationError(
                    "Substitute teacher is not available at this time"
                )

            # Check for existing substitute assignment
            existing_substitute = SubstituteTeacher.objects.filter(
                original_timetable=original_timetable, date=date
            )

            if self.instance.pk:
                existing_substitute = existing_substitute.exclude(pk=self.instance.pk)

            if existing_substitute.exists():
                raise ValidationError(
                    "Substitute already assigned for this timetable and date"
                )

        return cleaned_data


class TimetableGenerationForm(forms.ModelForm):
    """Form for timetable generation"""

    ALGORITHM_CHOICES = [
        ("genetic", "Genetic Algorithm"),
        ("greedy", "Greedy Algorithm"),
    ]

    algorithm_used = forms.ChoiceField(
        choices=ALGORITHM_CHOICES,
        initial="genetic",
        help_text="Select optimization algorithm",
    )

    population_size = forms.IntegerField(
        initial=50,
        min_value=10,
        max_value=200,
        help_text="Population size for genetic algorithm",
    )

    generations = forms.IntegerField(
        initial=100,
        min_value=10,
        max_value=500,
        help_text="Number of generations to run",
    )

    mutation_rate = forms.FloatField(
        initial=0.1,
        min_value=0.01,
        max_value=0.5,
        help_text="Mutation rate (0.1 = 10%)",
    )

    class Meta:
        model = TimetableGeneration
        fields = ["term", "algorithm_used"]
        widgets = {
            "term": forms.Select(attrs={"required": True}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["grades"] = forms.ModelMultipleChoiceField(
            queryset=Grade.objects.all(),
            widget=forms.CheckboxSelectMultiple,
            help_text="Select grades to generate timetables for",
        )

    def save(self, commit=True):
        instance = super().save(commit=False)

        # Set parameters
        instance.parameters = {
            "population_size": self.cleaned_data.get("population_size", 50),
            "generations": self.cleaned_data.get("generations", 100),
            "mutation_rate": self.cleaned_data.get("mutation_rate", 0.1),
        }

        if commit:
            instance.save()
            # Handle grades relationship
            grades = self.cleaned_data.get("grades", [])
            instance.grades.set(grades)

        return instance


class SchedulingConstraintForm(forms.ModelForm):
    """Form for scheduling constraints"""

    class Meta:
        model = SchedulingConstraint
        fields = [
            "name",
            "constraint_type",
            "parameters",
            "priority",
            "is_hard_constraint",
            "is_active",
        ]
        widgets = {
            "parameters": forms.Textarea(
                attrs={"rows": 5, "placeholder": "Enter constraint parameters as JSON"}
            ),
            "priority": forms.NumberInput(attrs={"min": 1, "max": 10}),
        }

    def clean_parameters(self):
        parameters = self.cleaned_data["parameters"]

        if parameters:
            try:
                json.loads(parameters)
            except json.JSONDecodeError:
                raise ValidationError("Parameters must be valid JSON")

        return parameters


class TimetableTemplateForm(forms.ModelForm):
    """Form for timetable templates"""

    class Meta:
        model = TimetableTemplate
        fields = ["name", "description", "grade", "is_default", "configuration"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "configuration": forms.Textarea(
                attrs={
                    "rows": 10,
                    "placeholder": "Enter template configuration as JSON",
                }
            ),
        }

    def clean_configuration(self):
        configuration = self.cleaned_data["configuration"]

        if configuration:
            try:
                json.loads(configuration)
            except json.JSONDecodeError:
                raise ValidationError("Configuration must be valid JSON")

        return configuration

    def clean(self):
        cleaned_data = super().clean()
        grade = cleaned_data.get("grade")
        is_default = cleaned_data.get("is_default")

        # Ensure only one default template per grade
        if is_default and grade:
            existing_default = TimetableTemplate.objects.filter(
                grade=grade, is_default=True
            )

            if self.instance.pk:
                existing_default = existing_default.exclude(pk=self.instance.pk)

            if existing_default.exists():
                raise ValidationError(
                    "A default template already exists for this grade"
                )

        return cleaned_data


# Filter Forms
class TimetableFilterForm(forms.Form):
    """Form for filtering timetables"""

    term = forms.ModelChoiceField(
        queryset=Term.objects.all(), required=False, empty_label="All Terms"
    )
    grade = forms.ModelChoiceField(
        queryset=Grade.objects.all(), required=False, empty_label="All Grades"
    )
    class_assigned = forms.ModelChoiceField(
        queryset=Class.objects.all(), required=False, empty_label="All Classes"
    )
    teacher = forms.ModelChoiceField(
        queryset=Teacher.objects.filter(status="active"),
        required=False,
        empty_label="All Teachers",
    )
    subject = forms.ModelChoiceField(
        queryset=Subject.objects.all(), required=False, empty_label="All Subjects"
    )
    day_of_week = forms.ChoiceField(
        choices=[("", "All Days")] + TimeSlot.DAY_CHOICES, required=False
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Dynamic filtering based on selections
        if "grade" in self.data and self.data["grade"]:
            try:
                grade_id = int(self.data["grade"])
                self.fields["class_assigned"].queryset = Class.objects.filter(
                    grade_id=grade_id
                )
            except (ValueError, TypeError):
                pass


class ConflictAnalysisForm(forms.Form):
    """Form for conflict analysis"""

    term = forms.ModelChoiceField(
        queryset=Term.objects.all(), help_text="Select term to analyze"
    )
    include_teacher_conflicts = forms.BooleanField(
        initial=True,
        required=False,
        help_text="Include teacher double-booking conflicts",
    )
    include_room_conflicts = forms.BooleanField(
        initial=True, required=False, help_text="Include room double-booking conflicts"
    )
    include_unassigned_rooms = forms.BooleanField(
        initial=True, required=False, help_text="Include classes without assigned rooms"
    )
