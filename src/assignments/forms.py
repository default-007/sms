import os
from datetime import datetime, timedelta

from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.forms import inlineformset_factory
from django.forms.widgets import DateTimeInput
from django.utils import timezone

from academics.models import Class, Term
from students.models import Student
from subjects.models import Subject
from teachers.models import Teacher

from .models import (
    Assignment,
    AssignmentComment,
    AssignmentRubric,
    AssignmentSubmission,
    SubmissionGrade,
)

User = get_user_model()


class AssignmentForm(forms.ModelForm):
    """
    Form for creating and editing assignments
    """

    class Meta:
        model = Assignment
        fields = [
            "title",
            "description",
            "instructions",
            "class_id",
            "subject",
            "term",
            "due_date",
            "total_marks",
            "passing_marks",
            "submission_type",
            "difficulty_level",
            "allow_late_submission",
            "late_penalty_percentage",
            "max_file_size_mb",
            "allowed_file_types",
            "estimated_duration_hours",
            "learning_objectives",
            "attachment",
            "auto_grade",
            "peer_review",
        ]

        widgets = {
            "title": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Enter assignment title"}
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 4,
                    "placeholder": "Brief description of the assignment",
                }
            ),
            "instructions": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 6,
                    "placeholder": "Detailed instructions for students",
                }
            ),
            "class_id": forms.Select(attrs={"class": "form-select"}),
            "subject": forms.Select(attrs={"class": "form-select"}),
            "term": forms.Select(attrs={"class": "form-select"}),
            "due_date": DateTimeInput(
                attrs={"type": "datetime-local", "class": "form-control"}
            ),
            "total_marks": forms.NumberInput(
                attrs={"class": "form-control", "min": "1", "max": "1000"}
            ),
            "passing_marks": forms.NumberInput(
                attrs={"class": "form-control", "min": "0"}
            ),
            "submission_type": forms.Select(attrs={"class": "form-select"}),
            "difficulty_level": forms.Select(attrs={"class": "form-select"}),
            "allow_late_submission": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),
            "late_penalty_percentage": forms.NumberInput(
                attrs={"class": "form-control", "min": "0", "max": "100"}
            ),
            "max_file_size_mb": forms.NumberInput(
                attrs={"class": "form-control", "min": "1", "max": "100"}
            ),
            "allowed_file_types": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "pdf,doc,docx,txt"}
            ),
            "estimated_duration_hours": forms.NumberInput(
                attrs={"class": "form-control", "min": "1", "max": "48"}
            ),
            "learning_objectives": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": "What students should learn from this assignment",
                }
            ),
            "attachment": forms.FileInput(attrs={"class": "form-control"}),
            "auto_grade": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "peer_review": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, **kwargs):
        self.teacher = kwargs.pop("teacher", None)
        super().__init__(*args, **kwargs)

        # Filter querysets based on teacher
        if self.teacher:
            # Only show classes where teacher is assigned
            teacher_classes = Class.objects.filter(
                teacherassignment__teacher=self.teacher
            ).distinct()
            self.fields["class_id"].queryset = teacher_classes

            # Only show subjects teacher can teach
            self.fields["subject"].queryset = self.teacher.subjects.all()

        # Only show current and future terms
        self.fields["term"].queryset = Term.objects.filter(
            end_date__gte=timezone.now().date()
        ).order_by("start_date")

        # Set initial values
        if not self.instance.pk:
            self.fields["due_date"].initial = timezone.now() + timedelta(days=7)
            self.fields["total_marks"].initial = 100
            self.fields["max_file_size_mb"].initial = 10
            self.fields["allowed_file_types"].initial = "pdf,doc,docx,txt"

    def clean_due_date(self):
        """Validate due date is in the future"""
        due_date = self.cleaned_data["due_date"]
        if due_date <= timezone.now():
            raise ValidationError("Due date must be in the future")
        return due_date

    def clean_passing_marks(self):
        """Validate passing marks don't exceed total marks"""
        passing_marks = self.cleaned_data.get("passing_marks")
        total_marks = self.cleaned_data.get("total_marks")

        if passing_marks and total_marks and passing_marks > total_marks:
            raise ValidationError("Passing marks cannot exceed total marks")

        return passing_marks

    def clean_allowed_file_types(self):
        """Validate file types format"""
        file_types = self.cleaned_data["allowed_file_types"]
        if file_types:
            # Check format (comma-separated, no spaces in extensions)
            types = [t.strip().lower() for t in file_types.split(",")]
            for file_type in types:
                if not file_type.isalnum():
                    raise ValidationError(
                        "File types must be alphanumeric (e.g., pdf,doc,txt)"
                    )
        return file_types

    def save(self, commit=True):
        """Save assignment with teacher"""
        assignment = super().save(commit=False)
        if self.teacher:
            assignment.teacher = self.teacher
        if commit:
            assignment.save()
        return assignment


class AssignmentSubmissionForm(forms.ModelForm):
    """
    Form for student assignment submissions
    """

    class Meta:
        model = AssignmentSubmission
        fields = ["content", "attachment", "submission_method", "student_remarks"]

        widgets = {
            "content": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 8,
                    "placeholder": "Enter your submission text here (if applicable)",
                }
            ),
            "attachment": forms.FileInput(
                attrs={
                    "class": "form-control",
                    "accept": ".pdf,.doc,.docx,.txt,.jpg,.jpeg,.png",
                }
            ),
            "submission_method": forms.Select(attrs={"class": "form-select"}),
            "student_remarks": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": "Any additional comments or notes (optional)",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        self.assignment = kwargs.pop("assignment", None)
        self.student = kwargs.pop("student", None)
        super().__init__(*args, **kwargs)

        # Set file upload constraints based on assignment
        if self.assignment:
            max_size_mb = self.assignment.max_file_size_mb
            allowed_types = self.assignment.allowed_file_types

            self.fields["attachment"].help_text = (
                f"Maximum file size: {max_size_mb}MB. "
                f"Allowed types: {allowed_types}"
            )

            # Update accept attribute
            if allowed_types:
                extensions = [f".{ext.strip()}" for ext in allowed_types.split(",")]
                self.fields["attachment"].widget.attrs["accept"] = ",".join(extensions)

            # Hide submission method if assignment has specific requirement
            if self.assignment.submission_type != "both":
                self.fields["submission_method"].initial = (
                    self.assignment.submission_type
                )
                self.fields["submission_method"].widget = forms.HiddenInput()

    def clean_attachment(self):
        """Validate attachment file"""
        attachment = self.cleaned_data.get("attachment")

        if attachment and self.assignment:
            # Check file size
            max_size_bytes = self.assignment.max_file_size_mb * 1024 * 1024
            if attachment.size > max_size_bytes:
                raise ValidationError(
                    f"File size exceeds {self.assignment.max_file_size_mb}MB limit"
                )

            # Check file type
            allowed_types = [
                ext.strip().lower()
                for ext in self.assignment.allowed_file_types.split(",")
            ]
            file_ext = os.path.splitext(attachment.name)[1][1:].lower()

            if file_ext not in allowed_types:
                raise ValidationError(
                    f"File type '{file_ext}' not allowed. "
                    f"Allowed types: {', '.join(allowed_types)}"
                )

        return attachment

    def clean(self):
        """Validate submission has content or attachment"""
        cleaned_data = super().clean()
        content = cleaned_data.get("content")
        attachment = cleaned_data.get("attachment")

        if not content and not attachment:
            raise ValidationError("Please provide either text content or attach a file")

        return cleaned_data


class SubmissionGradingForm(forms.ModelForm):
    """
    Form for grading student submissions
    """

    class Meta:
        model = AssignmentSubmission
        fields = ["marks_obtained", "teacher_remarks", "strengths", "improvements"]

        widgets = {
            "marks_obtained": forms.NumberInput(
                attrs={"class": "form-control", "min": "0", "step": "0.1"}
            ),
            "teacher_remarks": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 4,
                    "placeholder": "Overall feedback and comments",
                }
            ),
            "strengths": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": "What the student did well",
                }
            ),
            "improvements": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": "Areas for improvement",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.instance and self.instance.assignment:
            total_marks = self.instance.assignment.total_marks
            self.fields["marks_obtained"].widget.attrs["max"] = str(total_marks)
            self.fields["marks_obtained"].help_text = f"Maximum marks: {total_marks}"

    def clean_marks_obtained(self):
        """Validate marks are within range"""
        marks = self.cleaned_data["marks_obtained"]

        if marks is not None and self.instance:
            total_marks = self.instance.assignment.total_marks
            if marks < 0:
                raise ValidationError("Marks cannot be negative")
            if marks > total_marks:
                raise ValidationError(f"Marks cannot exceed {total_marks}")

        return marks


class AssignmentRubricForm(forms.ModelForm):
    """
    Form for creating assignment rubrics
    """

    class Meta:
        model = AssignmentRubric
        fields = [
            "criteria_name",
            "description",
            "max_points",
            "weight_percentage",
            "excellent_description",
            "good_description",
            "satisfactory_description",
            "needs_improvement_description",
        ]

        widgets = {
            "criteria_name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "e.g., Content Quality, Grammar, Creativity",
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 2,
                    "placeholder": "Brief description of this criterion",
                }
            ),
            "max_points": forms.NumberInput(
                attrs={"class": "form-control", "min": "1", "max": "100"}
            ),
            "weight_percentage": forms.NumberInput(
                attrs={"class": "form-control", "min": "1", "max": "100"}
            ),
            "excellent_description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 2,
                    "placeholder": "Description for excellent performance (90-100%)",
                }
            ),
            "good_description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 2,
                    "placeholder": "Description for good performance (70-89%)",
                }
            ),
            "satisfactory_description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 2,
                    "placeholder": "Description for satisfactory performance (50-69%)",
                }
            ),
            "needs_improvement_description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 2,
                    "placeholder": "Description for needs improvement (below 50%)",
                }
            ),
        }


# Create formset for managing multiple rubrics
RubricFormSet = inlineformset_factory(
    Assignment,
    AssignmentRubric,
    form=AssignmentRubricForm,
    extra=3,
    can_delete=True,
    min_num=1,
    validate_min=True,
)


class SubmissionGradeForm(forms.ModelForm):
    """
    Form for rubric-based grading
    """

    class Meta:
        model = SubmissionGrade
        fields = ["points_earned", "feedback"]

        widgets = {
            "points_earned": forms.NumberInput(
                attrs={"class": "form-control", "min": "0"}
            ),
            "feedback": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 2,
                    "placeholder": "Specific feedback for this criterion",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        self.rubric = kwargs.pop("rubric", None)
        super().__init__(*args, **kwargs)

        if self.rubric:
            self.fields["points_earned"].widget.attrs["max"] = str(
                self.rubric.max_points
            )
            self.fields["points_earned"].label = (
                f"{self.rubric.criteria_name} (max: {self.rubric.max_points})"
            )


class AssignmentCommentForm(forms.ModelForm):
    """
    Form for assignment comments and discussions
    """

    class Meta:
        model = AssignmentComment
        fields = ["content", "is_private"]

        widgets = {
            "content": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": "Add your comment or question...",
                }
            ),
            "is_private": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

        # Only teachers can make private comments
        if not (self.user and hasattr(self.user, "teacher")):
            del self.fields["is_private"]


class AssignmentSearchForm(forms.Form):
    """
    Form for searching assignments
    """

    query = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Search assignments, subjects, or teachers...",
            }
        ),
    )

    status = forms.MultipleChoiceField(
        choices=Assignment.STATUS_CHOICES,
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={"class": "form-check-input"}),
    )

    subject = forms.ModelChoiceField(
        queryset=Subject.objects.all(),
        required=False,
        empty_label="All Subjects",
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    difficulty = forms.ChoiceField(
        choices=[("", "All Difficulties")] + Assignment.DIFFICULTY_CHOICES,
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    due_from = forms.DateTimeField(
        required=False,
        widget=DateTimeInput(attrs={"type": "datetime-local", "class": "form-control"}),
    )

    due_to = forms.DateTimeField(
        required=False,
        widget=DateTimeInput(attrs={"type": "datetime-local", "class": "form-control"}),
    )

    overdue_only = forms.BooleanField(
        required=False, widget=forms.CheckboxInput(attrs={"class": "form-check-input"})
    )


class BulkGradeForm(forms.Form):
    """
    Form for bulk grading operations
    """

    csv_file = forms.FileField(
        widget=forms.FileInput(attrs={"class": "form-control", "accept": ".csv"}),
        help_text="Upload CSV file with columns: submission_id, marks_obtained, teacher_remarks",
    )

    apply_late_penalty = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
        help_text="Apply late penalty to late submissions",
    )

    def clean_csv_file(self):
        """Validate CSV file format"""
        csv_file = self.cleaned_data["csv_file"]

        if not csv_file.name.endswith(".csv"):
            raise ValidationError("Please upload a CSV file")

        if csv_file.size > 5 * 1024 * 1024:  # 5MB limit
            raise ValidationError("File size must be less than 5MB")

        return csv_file


class AssignmentFilterForm(forms.Form):
    """
    Form for filtering assignments
    """

    teacher = forms.ModelChoiceField(
        queryset=Teacher.objects.all(),
        required=False,
        empty_label="All Teachers",
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    class_id = forms.ModelChoiceField(
        queryset=Class.objects.all(),
        required=False,
        empty_label="All Classes",
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    term = forms.ModelChoiceField(
        queryset=Term.objects.all(),
        required=False,
        empty_label="All Terms",
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    date_range = forms.ChoiceField(
        choices=[
            ("", "All Time"),
            ("today", "Today"),
            ("week", "This Week"),
            ("month", "This Month"),
            ("term", "Current Term"),
        ],
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )


class DeadlineExtensionForm(forms.Form):
    """
    Form for extending assignment deadlines
    """

    new_due_date = forms.DateTimeField(
        widget=DateTimeInput(attrs={"type": "datetime-local", "class": "form-control"})
    )

    reason = forms.CharField(
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 3,
                "placeholder": "Reason for deadline extension",
            }
        )
    )

    notify_students = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
        help_text="Send notification to students about the deadline change",
    )

    def clean_new_due_date(self):
        """Validate new due date is in the future"""
        new_due_date = self.cleaned_data["new_due_date"]
        if new_due_date <= timezone.now():
            raise ValidationError("New due date must be in the future")
        return new_due_date


class NotificationSettingsForm(forms.Form):
    """
    Form for assignment notification preferences
    """

    assignment_published = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
        label="New assignment published",
    )

    deadline_reminder = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
        label="Deadline reminders",
    )

    submission_received = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
        label="Submission received (for teachers)",
    )

    grade_available = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
        label="Grade available",
    )

    plagiarism_detected = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
        label="Plagiarism detected (for teachers)",
    )

    email_notifications = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
        label="Email notifications",
    )

    sms_notifications = forms.BooleanField(
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
        label="SMS notifications",
    )

    reminder_days = forms.IntegerField(
        initial=2,
        min_value=1,
        max_value=14,
        widget=forms.NumberInput(
            attrs={"class": "form-control", "min": "1", "max": "14"}
        ),
        help_text="Send deadline reminders this many days before due date",
    )


class AssignmentTemplateForm(forms.ModelForm):
    """
    Form for saving assignments as templates
    """

    template_name = forms.CharField(
        max_length=200,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Enter template name"}
        ),
    )

    template_description = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 3,
                "placeholder": "Brief description of this template",
            }
        ),
    )

    is_public = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
        help_text="Allow other teachers to use this template",
    )

    class Meta:
        model = Assignment
        fields = [
            "title",
            "description",
            "instructions",
            "submission_type",
            "difficulty_level",
            "total_marks",
            "estimated_duration_hours",
            "learning_objectives",
            "allowed_file_types",
            "max_file_size_mb",
        ]


class PlagiarismThresholdForm(forms.Form):
    """
    Form for setting plagiarism detection thresholds
    """

    threshold_percentage = forms.IntegerField(
        initial=30,
        min_value=10,
        max_value=90,
        widget=forms.NumberInput(
            attrs={"class": "form-control", "min": "10", "max": "90"}
        ),
        help_text="Submissions above this similarity percentage will be flagged",
    )

    check_against = forms.MultipleChoiceField(
        choices=[
            ("current_assignment", "Other submissions in this assignment"),
            ("all_assignments", "All assignments in the system"),
            ("external_sources", "External sources (if available)"),
        ],
        widget=forms.CheckboxSelectMultiple(attrs={"class": "form-check-input"}),
        initial=["current_assignment"],
    )

    auto_flag = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
        help_text="Automatically flag suspicious submissions",
    )


class QuickGradeForm(forms.Form):
    """
    Quick grading form for simple pass/fail or percentage grading
    """

    grading_method = forms.ChoiceField(
        choices=[
            ("percentage", "Percentage"),
            ("pass_fail", "Pass/Fail"),
            ("letter_grade", "Letter Grade"),
        ],
        widget=forms.RadioSelect(attrs={"class": "form-check-input"}),
    )

    default_feedback = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 2,
                "placeholder": "Default feedback for all submissions",
            }
        ),
    )

    apply_to_all = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
        help_text="Apply the same grade and feedback to all selected submissions",
    )
