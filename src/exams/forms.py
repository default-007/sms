from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.utils import timezone

from .models import (
    ExamType,
    Exam,
    ExamSchedule,
    Quiz,
    Question,
    StudentExamResult,
    StudentQuizAttempt,
    GradingSystem,
    ReportCard,
)


class ExamTypeForm(forms.ModelForm):
    class Meta:
        model = ExamType
        fields = ["name", "description", "contribution_percentage"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
        }


class ExamForm(forms.ModelForm):
    class Meta:
        model = Exam
        fields = [
            "name",
            "exam_type",
            "academic_year",
            "start_date",
            "end_date",
            "description",
            "status",
        ]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
            "description": forms.Textarea(attrs={"rows": 3}),
        }

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get("start_date")
        end_date = cleaned_data.get("end_date")

        if start_date and end_date and start_date > end_date:
            raise ValidationError(_("End date must be after start date."))

        return cleaned_data


class ExamScheduleForm(forms.ModelForm):
    class Meta:
        model = ExamSchedule
        fields = [
            "exam",
            "class_obj",
            "subject",
            "date",
            "start_time",
            "end_time",
            "room",
            "supervisor",
            "total_marks",
            "passing_marks",
            "status",
        ]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
            "start_time": forms.TimeInput(attrs={"type": "time"}),
            "end_time": forms.TimeInput(attrs={"type": "time"}),
        }

    def __init__(self, *args, **kwargs):
        exam = kwargs.pop("exam", None)
        super().__init__(*args, **kwargs)

        if exam:
            self.fields["exam"].initial = exam
            self.fields["exam"].widget.attrs["readonly"] = True

            # Filter class and subject based on the exam's academic year
            self.fields["class_obj"].queryset = self.fields[
                "class_obj"
            ].queryset.filter(academic_year=exam.academic_year)

    def clean(self):
        cleaned_data = super().clean()
        start_time = cleaned_data.get("start_time")
        end_time = cleaned_data.get("end_time")
        exam = cleaned_data.get("exam")
        date = cleaned_data.get("date")

        if start_time and end_time and start_time > end_time:
            raise ValidationError(_("End time must be after start time."))

        if date and exam:
            if date < exam.start_date or date > exam.end_date:
                raise ValidationError(
                    _("Exam schedule date must be within the exam period.")
                )

        return cleaned_data


class QuizForm(forms.ModelForm):
    class Meta:
        model = Quiz
        fields = [
            "title",
            "description",
            "class_obj",
            "subject",
            "teacher",
            "start_datetime",
            "end_datetime",
            "duration_minutes",
            "total_marks",
            "passing_marks",
            "attempts_allowed",
            "status",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "start_datetime": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "end_datetime": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

        # If user is a teacher, pre-select the teacher field
        if self.user and hasattr(self.user, "teacher_profile"):
            self.fields["teacher"].initial = self.user.teacher_profile
            self.fields["teacher"].widget.attrs["readonly"] = True

    def clean(self):
        cleaned_data = super().clean()
        start_datetime = cleaned_data.get("start_datetime")
        end_datetime = cleaned_data.get("end_datetime")
        duration_minutes = cleaned_data.get("duration_minutes")

        if start_datetime and end_datetime and start_datetime > end_datetime:
            raise ValidationError(_("End time must be after start time."))

        if start_datetime and end_datetime and duration_minutes:
            time_diff = end_datetime - start_datetime
            minutes_diff = time_diff.total_seconds() / 60

            if minutes_diff < duration_minutes:
                raise ValidationError(
                    _(
                        "The time window between start and end time must be at least as long as the quiz duration."
                    )
                )

        return cleaned_data


class QuestionForm(forms.ModelForm):
    class Meta:
        model = Question
        fields = [
            "quiz",
            "question_text",
            "question_type",
            "options",
            "correct_answer",
            "explanation",
            "marks",
            "difficulty_level",
        ]
        widgets = {
            "question_text": forms.Textarea(attrs={"rows": 3}),
            "explanation": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        quiz = kwargs.pop("quiz", None)
        super().__init__(*args, **kwargs)

        if quiz:
            self.fields["quiz"].initial = quiz
            self.fields["quiz"].widget.attrs["readonly"] = True

    def clean(self):
        cleaned_data = super().clean()
        question_type = cleaned_data.get("question_type")
        options = cleaned_data.get("options")
        correct_answer = cleaned_data.get("correct_answer")

        # Validate options for MCQ
        if question_type == "mcq":
            if not options or not isinstance(options, list) or len(options) < 2:
                raise ValidationError(
                    _("Multiple choice questions must have at least 2 options.")
                )

            try:
                correct_option = int(correct_answer)
                if correct_option < 0 or correct_option >= len(options):
                    raise ValidationError(
                        _("Correct answer must be a valid option index.")
                    )
            except ValueError:
                raise ValidationError(
                    _("Correct answer for MCQ must be a valid option index.")
                )

        # Validate true/false answer
        elif question_type == "true_false":
            if correct_answer.lower() not in ["true", "false"]:
                raise ValidationError(
                    _(
                        'Correct answer for True/False questions must be "true" or "false".'
                    )
                )

        return cleaned_data


class StudentExamResultForm(forms.ModelForm):
    class Meta:
        model = StudentExamResult
        fields = ["marks_obtained", "remarks"]
        widgets = {
            "remarks": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        self.exam_schedule = kwargs.pop("exam_schedule", None)
        self.student = kwargs.pop("student", None)
        super().__init__(*args, **kwargs)

        if self.exam_schedule:
            self.max_marks = self.exam_schedule.total_marks
            self.fields["marks_obtained"].label = (
                f"Marks Obtained (out of {self.max_marks})"
            )

    def clean_marks_obtained(self):
        marks = self.cleaned_data.get("marks_obtained")
        if self.exam_schedule and marks > self.exam_schedule.total_marks:
            raise ValidationError(
                _(
                    "Marks cannot exceed the maximum marks for this exam (%(max_marks)s)."
                ),
                params={"max_marks": self.exam_schedule.total_marks},
            )
        return marks


class BulkResultEntryForm(forms.Form):
    exam_schedule = forms.ModelChoiceField(
        queryset=ExamSchedule.objects.all(), label=_("Exam Schedule")
    )

    def __init__(self, *args, **kwargs):
        exam = kwargs.pop("exam", None)
        super().__init__(*args, **kwargs)

        if exam:
            self.fields["exam_schedule"].queryset = ExamSchedule.objects.filter(
                exam=exam
            )


class QuizAttemptForm(forms.ModelForm):
    class Meta:
        model = StudentQuizAttempt
        fields = []  # No fields needed as we'll create it programmatically


class QuizResponseForm(forms.Form):
    def __init__(self, *args, **kwargs):
        self.question = kwargs.pop("question", None)
        super().__init__(*args, **kwargs)

        if not self.question:
            return

        if self.question.question_type == "mcq":
            choices = [(i, option) for i, option in enumerate(self.question.options)]
            self.fields["answer"] = forms.ChoiceField(
                choices=choices,
                widget=forms.RadioSelect,
                label=self.question.question_text,
            )
        elif self.question.question_type == "true_false":
            self.fields["answer"] = forms.ChoiceField(
                choices=[("true", "True"), ("false", "False")],
                widget=forms.RadioSelect,
                label=self.question.question_text,
            )
        else:
            self.fields["answer"] = forms.CharField(
                widget=forms.Textarea(attrs={"rows": 3}),
                label=self.question.question_text,
            )


class GradingSystemForm(forms.ModelForm):
    class Meta:
        model = GradingSystem
        fields = [
            "academic_year",
            "grade_name",
            "min_percentage",
            "max_percentage",
            "grade_point",
            "description",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 2}),
        }

    def clean(self):
        cleaned_data = super().clean()
        min_percentage = cleaned_data.get("min_percentage")
        max_percentage = cleaned_data.get("max_percentage")

        if min_percentage and max_percentage and min_percentage >= max_percentage:
            raise ValidationError(
                _("Maximum percentage must be greater than minimum percentage.")
            )

        return cleaned_data


class ReportCardForm(forms.ModelForm):
    class Meta:
        model = ReportCard
        fields = [
            "student",
            "class_obj",
            "academic_year",
            "term",
            "remarks",
            "class_teacher_remarks",
            "principal_remarks",
            "status",
        ]
        widgets = {
            "remarks": forms.Textarea(attrs={"rows": 2}),
            "class_teacher_remarks": forms.Textarea(attrs={"rows": 2}),
            "principal_remarks": forms.Textarea(attrs={"rows": 2}),
        }
