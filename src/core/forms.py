# forms.py
import json
from django import forms
from .models import SystemSetting


class SystemSettingForm(forms.ModelForm):
    """Form for editing system settings"""

    class Meta:
        model = SystemSetting
        fields = ["setting_value", "description", "is_editable"]
        widgets = {
            "setting_value": forms.Textarea(attrs={"rows": 3}),
            "description": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.instance and self.instance.pk:
            # Customize widget based on data type
            if self.instance.data_type == "boolean":
                self.fields["setting_value"].widget = forms.Select(
                    choices=[("true", "True"), ("false", "False")]
                )
            elif self.instance.data_type == "integer":
                self.fields["setting_value"].widget = forms.NumberInput()
            elif self.instance.data_type == "float":
                self.fields["setting_value"].widget = forms.NumberInput(
                    attrs={"step": "any"}
                )
            elif self.instance.data_type == "json":
                self.fields["setting_value"].widget = forms.Textarea(attrs={"rows": 5})

    def clean_setting_value(self):
        """Validate setting value based on data type"""
        value = self.cleaned_data["setting_value"]

        if self.instance and self.instance.pk:
            data_type = self.instance.data_type

            if data_type == "boolean":
                if value.lower() not in ["true", "false"]:
                    raise forms.ValidationError("Value must be 'true' or 'false'")
            elif data_type == "integer":
                try:
                    int(value)
                except ValueError:
                    raise forms.ValidationError("Value must be a valid integer")
            elif data_type == "float":
                try:
                    float(value)
                except ValueError:
                    raise forms.ValidationError("Value must be a valid number")
            elif data_type == "json":
                try:
                    json.loads(value)
                except json.JSONDecodeError:
                    raise forms.ValidationError("Value must be valid JSON")

        return value


class UserSearchForm(forms.Form):
    """Form for searching users"""

    search = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(
            attrs={
                "placeholder": "Search by name, username, or email...",
                "class": "form-control",
            }
        ),
    )

    role = forms.ChoiceField(
        choices=[
            ("", "All Roles"),
            ("admin", "Administrators"),
            ("teacher", "Teachers"),
            ("parent", "Parents"),
            ("student", "Students"),
        ],
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    status = forms.ChoiceField(
        choices=[
            ("", "All Status"),
            ("active", "Active"),
            ("inactive", "Inactive"),
        ],
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )


class ReportGenerationForm(forms.Form):
    """Form for report generation parameters"""

    REPORT_TYPES = [
        ("student_performance", "Student Performance Report"),
        ("class_performance", "Class Performance Report"),
        ("attendance_summary", "Attendance Summary Report"),
        ("financial_summary", "Financial Summary Report"),
        ("teacher_performance", "Teacher Performance Report"),
    ]

    FORMAT_CHOICES = [
        ("pdf", "PDF"),
        ("excel", "Excel"),
        ("csv", "CSV"),
    ]

    report_type = forms.ChoiceField(
        choices=REPORT_TYPES, widget=forms.Select(attrs={"class": "form-select"})
    )

    format = forms.ChoiceField(
        choices=FORMAT_CHOICES,
        widget=forms.Select(attrs={"class": "form-select"}),
        initial="pdf",
    )

    academic_year = forms.ModelChoiceField(
        queryset=None,  # Will be set in __init__
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    term = forms.ModelChoiceField(
        queryset=None,  # Will be set in __init__
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    section = forms.ModelChoiceField(
        queryset=None,  # Will be set in __init__
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    grade = forms.ModelChoiceField(
        queryset=None,  # Will be set in __init__
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    start_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
    )

    end_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Set querysets for model choice fields
        from academics.models import AcademicYear, Term, Section, Grade

        self.fields["academic_year"].queryset = AcademicYear.objects.all().order_by(
            "-start_date"
        )
        self.fields["term"].queryset = Term.objects.all().order_by("term_number")
        self.fields["section"].queryset = Section.objects.all().order_by("name")
        self.fields["grade"].queryset = Grade.objects.all().order_by("order_sequence")
