from django import forms
from django.core.exceptions import ValidationError

from src.courses.models import (
    AcademicYear,
    Assignment,
    AssignmentSubmission,
    Class,
    Department,
    Grade,
    Section,
    Subject,
    Syllabus,
    TimeSlot,
    Timetable,
)


class DepartmentForm(forms.ModelForm):
    class Meta:
        model = Department
        fields = ["name", "description", "head"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
        }


class AcademicYearForm(forms.ModelForm):
    class Meta:
        model = AcademicYear
        fields = ["name", "start_date", "end_date", "is_current"]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
        }

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get("start_date")
        end_date = cleaned_data.get("end_date")

        if start_date and end_date and start_date >= end_date:
            raise ValidationError("End date must be after start date.")

        return cleaned_data


class GradeForm(forms.ModelForm):
    class Meta:
        model = Grade
        fields = ["name", "description", "department"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
        }


class SectionForm(forms.ModelForm):
    class Meta:
        model = Section
        fields = ["name", "description"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
        }


class ClassForm(forms.ModelForm):
    class Meta:
        model = Class
        fields = [
            "grade",
            "section",
            "academic_year",
            "room_number",
            "capacity",
            "class_teacher",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["academic_year"].queryset = AcademicYear.objects.all().order_by(
            "-is_current", "-start_date"
        )


class SubjectForm(forms.ModelForm):
    class Meta:
        model = Subject
        fields = [
            "name",
            "code",
            "description",
            "department",
            "credit_hours",
            "is_elective",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
        }


class SyllabusForm(forms.ModelForm):
    class Meta:
        model = Syllabus
        fields = [
            "subject",
            "grade",
            "academic_year",
            "title",
            "description",
            "content",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "content": forms.Textarea(attrs={"rows": 10}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        self.fields["academic_year"].queryset = AcademicYear.objects.all().order_by(
            "-is_current", "-start_date"
        )

    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.user:
            if not instance.pk:  # New instance
                instance.created_by = self.user
            instance.last_updated_by = self.user

        if commit:
            instance.save()
        return instance


class TimeSlotForm(forms.ModelForm):
    class Meta:
        model = TimeSlot
        fields = ["day_of_week", "start_time", "end_time"]
        widgets = {
            "start_time": forms.TimeInput(attrs={"type": "time"}),
            "end_time": forms.TimeInput(attrs={"type": "time"}),
        }

    def clean(self):
        cleaned_data = super().clean()
        start_time = cleaned_data.get("start_time")
        end_time = cleaned_data.get("end_time")

        if start_time and end_time and start_time >= end_time:
            raise ValidationError("End time must be after start time.")

        return cleaned_data


class TimetableForm(forms.ModelForm):
    class Meta:
        model = Timetable
        fields = [
            "class_obj",
            "subject",
            "teacher",
            "time_slot",
            "room",
            "effective_from_date",
            "effective_to_date",
            "is_active",
        ]
        widgets = {
            "effective_from_date": forms.DateInput(attrs={"type": "date"}),
            "effective_to_date": forms.DateInput(attrs={"type": "date"}),
        }

    def clean(self):
        cleaned_data = super().clean()
        class_obj = cleaned_data.get("class_obj")
        time_slot = cleaned_data.get("time_slot")
        teacher = cleaned_data.get("teacher")

        # Skip validation if any of the required fields is missing
        if not class_obj or not time_slot or not teacher:
            return cleaned_data

        # Check for class timetable clash
        from src.courses.services.class_service import ClassService

        instance_id = self.instance.id if self.instance else None

        if ClassService.check_timetable_clash(
            class_obj, time_slot, exclude_id=instance_id
        ):
            raise ValidationError(
                "There is already a class scheduled in this time slot."
            )

        # Check for teacher availability
        from src.courses.services.timetable_service import TimetableService

        if not TimetableService.check_teacher_availability(
            teacher, time_slot, exclude_id=instance_id
        ):
            raise ValidationError(
                "The teacher is already assigned to another class in this time slot."
            )

        return cleaned_data


class AssignmentForm(forms.ModelForm):
    class Meta:
        model = Assignment
        fields = [
            "title",
            "description",
            "class_obj",
            "subject",
            "teacher",
            "due_date",
            "total_marks",
            "attachment",
            "submission_type",
            "status",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 5}),
            "due_date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

        # If it's a teacher, pre-select the teacher field
        if self.user and hasattr(self.user, "teacher"):
            self.fields["teacher"].initial = self.user.teacher
            self.fields["teacher"].widget.attrs["readonly"] = True

    def clean(self):
        cleaned_data = super().clean()

        # If it's a teacher, ensure they can only create assignments for classes they teach
        if self.user and hasattr(self.user, "teacher"):
            class_obj = cleaned_data.get("class_obj")
            subject = cleaned_data.get("subject")

            if class_obj and subject:
                # Check if the teacher teaches this subject in this class
                from src.courses.models import Timetable

                teaches_subject = Timetable.objects.filter(
                    class_obj=class_obj,
                    subject=subject,
                    teacher=self.user.teacher,
                    is_active=True,
                ).exists()

                if not teaches_subject and not self.user.is_staff:  # Allow admin users
                    raise ValidationError(
                        "You can only create assignments for subjects you teach."
                    )

        return cleaned_data


class AssignmentSubmissionForm(forms.ModelForm):
    class Meta:
        model = AssignmentSubmission
        fields = ["content", "file"]
        widgets = {
            "content": forms.Textarea(attrs={"rows": 5}),
        }

    def __init__(self, *args, **kwargs):
        self.assignment = kwargs.pop("assignment", None)
        self.student = kwargs.pop("student", None)
        super().__init__(*args, **kwargs)

    def save(self, commit=True):
        instance = super().save(commit=False)

        if self.assignment:
            instance.assignment = self.assignment

        if self.student:
            instance.student = self.student

        if commit:
            instance.save()

        return instance


class GradeSubmissionForm(forms.ModelForm):
    class Meta:
        model = AssignmentSubmission
        fields = ["marks_obtained", "remarks"]
        widgets = {
            "remarks": forms.Textarea(attrs={"rows": 3}),
        }
