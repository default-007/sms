"""
School Management System - Exam Forms
File: src/exams/forms.py
"""

import json
from datetime import date, time

from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

from academics.models import AcademicYear, Class, Term
from subjects.models import Subject
from teachers.models import Teacher

from .models import (
    Exam,
    ExamQuestion,
    ExamSchedule,
    ExamType,
    OnlineExam,
    StudentExamResult,
)


class ExamForm(forms.ModelForm):
    """Form for creating/editing exams"""

    class Meta:
        model = Exam
        fields = [
            "name",
            "exam_type",
            "academic_year",
            "term",
            "start_date",
            "end_date",
            "description",
            "instructions",
            "grading_system",
            "passing_percentage",
        ]
        widgets = {
            "start_date": forms.DateInput(
                attrs={"type": "date", "class": "form-control"}
            ),
            "end_date": forms.DateInput(
                attrs={"type": "date", "class": "form-control"}
            ),
            "description": forms.Textarea(attrs={"rows": 3, "class": "form-control"}),
            "instructions": forms.Textarea(attrs={"rows": 4, "class": "form-control"}),
            "passing_percentage": forms.NumberInput(
                attrs={"min": 0, "max": 100, "step": 0.01}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Set default academic year and term
        current_year = AcademicYear.objects.filter(is_current=True).first()
        if current_year:
            self.fields["academic_year"].initial = current_year

            current_term = current_year.terms.filter(is_current=True).first()
            if current_term:
                self.fields["term"].initial = current_term

        # Style form fields
        for field_name, field in self.fields.items():
            if not field.widget.attrs.get("class"):
                field.widget.attrs["class"] = "form-control"

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get("start_date")
        end_date = cleaned_data.get("end_date")
        term = cleaned_data.get("term")

        if start_date and end_date:
            if start_date > end_date:
                raise ValidationError("Start date cannot be after end date.")

            if start_date < date.today():
                raise ValidationError("Start date cannot be in the past.")

        if term and start_date and end_date:
            if start_date < term.start_date or end_date > term.end_date:
                raise ValidationError("Exam dates must be within the selected term.")

        return cleaned_data


class ExamScheduleForm(forms.ModelForm):
    """Form for creating/editing exam schedules"""

    class Meta:
        model = ExamSchedule
        fields = [
            "class_obj",
            "subject",
            "date",
            "start_time",
            "end_time",
            "duration_minutes",
            "room",
            "supervisor",
            "additional_supervisors",
            "total_marks",
            "passing_marks",
            "special_instructions",
            "materials_allowed",
        ]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "start_time": forms.TimeInput(
                attrs={"type": "time", "class": "form-control"}
            ),
            "end_time": forms.TimeInput(
                attrs={"type": "time", "class": "form-control"}
            ),
            "special_instructions": forms.Textarea(
                attrs={"rows": 3, "class": "form-control"}
            ),
            "materials_allowed": forms.Textarea(
                attrs={"rows": 2, "class": "form-control"}
            ),
            "additional_supervisors": forms.CheckboxSelectMultiple(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Style form fields
        for field_name, field in self.fields.items():
            if field_name != "additional_supervisors" and not field.widget.attrs.get(
                "class"
            ):
                field.widget.attrs["class"] = "form-control"

        # Filter supervisors to only teachers
        self.fields["supervisor"].queryset = Teacher.objects.filter(status="ACTIVE")
        self.fields["additional_supervisors"].queryset = Teacher.objects.filter(
            status="ACTIVE"
        )

    def clean(self):
        cleaned_data = super().clean()
        start_time = cleaned_data.get("start_time")
        end_time = cleaned_data.get("end_time")
        duration_minutes = cleaned_data.get("duration_minutes")
        total_marks = cleaned_data.get("total_marks")
        passing_marks = cleaned_data.get("passing_marks")
        exam_date = cleaned_data.get("date")

        if start_time and end_time:
            if start_time >= end_time:
                raise ValidationError("Start time must be before end time.")

            # Calculate duration
            start_datetime = timezone.datetime.combine(date.today(), start_time)
            end_datetime = timezone.datetime.combine(date.today(), end_time)
            calculated_duration = int(
                (end_datetime - start_datetime).total_seconds() / 60
            )

            if duration_minutes and abs(duration_minutes - calculated_duration) > 5:
                raise ValidationError(
                    "Duration minutes should match the time difference."
                )

        if total_marks and passing_marks:
            if passing_marks > total_marks:
                raise ValidationError("Passing marks cannot exceed total marks.")

        if exam_date and exam_date < date.today():
            raise ValidationError("Exam date cannot be in the past.")

        return cleaned_data


class ResultEntryForm(forms.ModelForm):
    """Form for entering individual exam results"""

    class Meta:
        model = StudentExamResult
        fields = [
            "marks_obtained",
            "is_absent",
            "is_exempted",
            "remarks",
            "teacher_comments",
        ]
        widgets = {
            "remarks": forms.Textarea(attrs={"rows": 2, "class": "form-control"}),
            "teacher_comments": forms.Textarea(
                attrs={"rows": 3, "class": "form-control"}
            ),
        }

    def __init__(self, *args, **kwargs):
        self.exam_schedule = kwargs.pop("exam_schedule", None)
        super().__init__(*args, **kwargs)

        if self.exam_schedule:
            self.fields["marks_obtained"].widget.attrs.update(
                {"max": self.exam_schedule.total_marks, "min": 0, "step": 0.1}
            )

        # Style form fields
        for field_name, field in self.fields.items():
            if field_name not in ["is_absent", "is_exempted"]:
                field.widget.attrs["class"] = "form-control"

    def clean_marks_obtained(self):
        marks = self.cleaned_data.get("marks_obtained")
        is_absent = self.cleaned_data.get("is_absent")

        if not is_absent and marks is None:
            raise ValidationError("Marks are required for non-absent students.")

        if marks and self.exam_schedule:
            if marks < 0 or marks > self.exam_schedule.total_marks:
                raise ValidationError(
                    f"Marks must be between 0 and {self.exam_schedule.total_marks}."
                )

        return marks


class ExamQuestionForm(forms.ModelForm):
    """Form for creating/editing exam questions"""

    options_text = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 4, "class": "form-control"}),
        required=False,
        help_text="For MCQ questions, enter each option on a new line",
    )

    class Meta:
        model = ExamQuestion
        fields = [
            "subject",
            "grade",
            "question_text",
            "question_type",
            "difficulty_level",
            "marks",
            "correct_answer",
            "explanation",
            "topic",
            "learning_objective",
        ]
        widgets = {
            "question_text": forms.Textarea(attrs={"rows": 4, "class": "form-control"}),
            "correct_answer": forms.Textarea(
                attrs={"rows": 2, "class": "form-control"}
            ),
            "explanation": forms.Textarea(attrs={"rows": 3, "class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Style form fields
        for field_name, field in self.fields.items():
            if not field.widget.attrs.get("class"):
                field.widget.attrs["class"] = "form-control"

        # Populate options text for existing MCQ questions
        if self.instance and self.instance.pk and self.instance.options:
            self.fields["options_text"].initial = "\n".join(self.instance.options)

    def clean(self):
        cleaned_data = super().clean()
        question_type = cleaned_data.get("question_type")
        options_text = cleaned_data.get("options_text")
        correct_answer = cleaned_data.get("correct_answer")

        if question_type == "MCQ":
            if not options_text:
                raise ValidationError("Options are required for MCQ questions.")

            options = [opt.strip() for opt in options_text.split("\n") if opt.strip()]
            if len(options) < 2:
                raise ValidationError("MCQ questions must have at least 2 options.")

            # Store options in cleaned_data for saving
            cleaned_data["options"] = options

            if correct_answer and correct_answer not in options:
                raise ValidationError(
                    "Correct answer must be one of the provided options."
                )

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)

        # Handle MCQ options
        if self.cleaned_data.get("question_type") == "MCQ":
            instance.options = self.cleaned_data.get("options", [])

        if commit:
            instance.save()

        return instance


class OnlineExamConfigForm(forms.ModelForm):
    """Form for configuring online exams"""

    class Meta:
        model = OnlineExam
        fields = [
            "time_limit_minutes",
            "max_attempts",
            "shuffle_questions",
            "shuffle_options",
            "show_results_immediately",
            "enable_proctoring",
            "webcam_required",
            "fullscreen_required",
            "access_code",
            "ip_restrictions",
        ]
        widgets = {
            "ip_restrictions": forms.Textarea(
                attrs={"rows": 3, "class": "form-control"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Style form fields
        for field_name, field in self.fields.items():
            if field_name not in [
                "shuffle_questions",
                "shuffle_options",
                "show_results_immediately",
                "enable_proctoring",
                "webcam_required",
                "fullscreen_required",
            ]:
                field.widget.attrs["class"] = "form-control"

    def clean_time_limit_minutes(self):
        time_limit = self.cleaned_data.get("time_limit_minutes")
        if time_limit and (time_limit < 5 or time_limit > 480):  # 5 minutes to 8 hours
            raise ValidationError("Time limit must be between 5 and 480 minutes.")
        return time_limit

    def clean_max_attempts(self):
        max_attempts = self.cleaned_data.get("max_attempts")
        if max_attempts and (max_attempts < 1 or max_attempts > 10):
            raise ValidationError("Max attempts must be between 1 and 10.")
        return max_attempts

    def clean_ip_restrictions(self):
        ip_restrictions = self.cleaned_data.get("ip_restrictions")
        if ip_restrictions:
            # Basic IP validation
            ips = [ip.strip() for ip in ip_restrictions.split(",") if ip.strip()]
            for ip in ips:
                parts = ip.split(".")
                if len(parts) != 4:
                    raise ValidationError(f"Invalid IP address format: {ip}")
                try:
                    for part in parts:
                        if not 0 <= int(part) <= 255:
                            raise ValidationError(f"Invalid IP address: {ip}")
                except ValueError:
                    raise ValidationError(f"Invalid IP address: {ip}")
        return ip_restrictions


class BulkResultUploadForm(forms.Form):
    """Form for bulk result upload via CSV"""

    csv_file = forms.FileField(
        widget=forms.FileInput(attrs={"accept": ".csv", "class": "form-control"}),
        help_text="Upload CSV file with columns: student_admission_number, marks_obtained, remarks",
    )

    def clean_csv_file(self):
        csv_file = self.cleaned_data.get("csv_file")
        if csv_file:
            if not csv_file.name.endswith(".csv"):
                raise ValidationError("Only CSV files are allowed.")

            if csv_file.size > 5 * 1024 * 1024:  # 5MB limit
                raise ValidationError("File size cannot exceed 5MB.")

        return csv_file


class ExamFilterForm(forms.Form):
    """Form for filtering exams"""

    academic_year = forms.ModelChoiceField(
        queryset=AcademicYear.objects.all(),
        required=False,
        empty_label="All Academic Years",
        widget=forms.Select(attrs={"class": "form-control"}),
    )

    term = forms.ModelChoiceField(
        queryset=Term.objects.all(),
        required=False,
        empty_label="All Terms",
        widget=forms.Select(attrs={"class": "form-control"}),
    )

    exam_type = forms.ModelChoiceField(
        queryset=ExamType.objects.all(),
        required=False,
        empty_label="All Exam Types",
        widget=forms.Select(attrs={"class": "form-control"}),
    )

    status = forms.ChoiceField(
        choices=[("", "All Statuses")] + Exam._meta.get_field("status").choices,
        required=False,
        widget=forms.Select(attrs={"class": "form-control"}),
    )

    search = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Search exams..."}
        ),
    )


class QuestionFilterForm(forms.Form):
    """Form for filtering questions"""

    subject = forms.ModelChoiceField(
        queryset=Subject.objects.all(),
        required=False,
        empty_label="All Subjects",
        widget=forms.Select(attrs={"class": "form-control"}),
    )

    question_type = forms.ChoiceField(
        choices=[("", "All Types")] + ExamQuestion.QUESTION_TYPES,
        required=False,
        widget=forms.Select(attrs={"class": "form-control"}),
    )

    difficulty_level = forms.ChoiceField(
        choices=[("", "All Difficulties")] + ExamQuestion.DIFFICULTY_LEVELS,
        required=False,
        widget=forms.Select(attrs={"class": "form-control"}),
    )

    search = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Search questions..."}
        ),
    )
