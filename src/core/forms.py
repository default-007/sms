# core/forms.py
import json
from django import forms
from django.contrib.auth import get_user_model
from .models import SystemSetting

User = get_user_model()


class SystemSettingForm(forms.ModelForm):
    """Form for editing system settings"""

    class Meta:
        model = SystemSetting
        fields = ["setting_value", "description", "is_editable"]
        widgets = {
            "setting_value": forms.Textarea(attrs={"rows": 3, "class": "form-control"}),
            "description": forms.Textarea(attrs={"rows": 2, "class": "form-control"}),
            "is_editable": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.instance and self.instance.pk:
            # Customize widget based on data type
            if self.instance.data_type == "boolean":
                self.fields["setting_value"].widget = forms.Select(
                    choices=[("true", "True"), ("false", "False")],
                    attrs={"class": "form-select"},
                )
            elif self.instance.data_type == "integer":
                self.fields["setting_value"].widget = forms.NumberInput(
                    attrs={"class": "form-control"}
                )
            elif self.instance.data_type == "float":
                self.fields["setting_value"].widget = forms.NumberInput(
                    attrs={"step": "any", "class": "form-control"}
                )
            elif self.instance.data_type == "json":
                self.fields["setting_value"].widget = forms.Textarea(
                    attrs={"rows": 5, "class": "form-control", "data-json": "true"}
                )

        # Set initial value as typed value for display
        if self.instance and self.instance.pk:
            if self.instance.data_type == "json":
                try:
                    value = self.instance.get_typed_value()
                    self.fields["setting_value"].initial = json.dumps(value, indent=2)
                except:
                    pass
            elif self.instance.data_type == "boolean":
                self.fields["setting_value"].initial = (
                    "true" if self.instance.get_typed_value() else "false"
                )

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
                except json.JSONDecodeError as e:
                    raise forms.ValidationError(f"Value must be valid JSON: {str(e)}")

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

    department = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(
            attrs={
                "placeholder": "Department...",
                "class": "form-control",
            }
        ),
    )

    date_joined_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
    )

    date_joined_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
    )


class ReportGenerationForm(forms.Form):
    """Form for report generation parameters"""

    REPORT_TYPES = [
        ("student_performance", "Student Performance Report"),
        ("class_performance", "Class Performance Report"),
        ("attendance_summary", "Attendance Summary Report"),
        ("financial_summary", "Financial Summary Report"),
        ("teacher_performance", "Teacher Performance Report"),
        ("enrollment_report", "Enrollment Report"),
        ("fee_defaulters", "Fee Defaulters Report"),
        ("system_usage", "System Usage Report"),
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
        empty_label="Current Academic Year",
    )

    term = forms.ModelChoiceField(
        queryset=None,  # Will be set in __init__
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
        empty_label="Current Term",
    )

    section = forms.ModelChoiceField(
        queryset=None,  # Will be set in __init__
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
        empty_label="All Sections",
    )

    grade = forms.ModelChoiceField(
        queryset=None,  # Will be set in __init__
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
        empty_label="All Grades",
    )

    start_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
        help_text="Start date for date range reports",
    )

    end_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
        help_text="End date for date range reports",
    )

    include_inactive = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
        help_text="Include inactive students/teachers in the report",
    )

    detailed_report = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
        help_text="Generate detailed report with additional information",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Set querysets for model choice fields
        try:
            from src.academics.models import AcademicYear, Term, Section, Grade

            self.fields["academic_year"].queryset = AcademicYear.objects.all().order_by(
                "-start_date"
            )
            self.fields["term"].queryset = Term.objects.all().order_by("term_number")
            self.fields["section"].queryset = Section.objects.all().order_by("name")
            self.fields["grade"].queryset = Grade.objects.all().order_by(
                "order_sequence"
            )
        except ImportError:
            # If academics app is not available, hide these fields
            self.fields["academic_year"].widget = forms.HiddenInput()
            self.fields["term"].widget = forms.HiddenInput()
            self.fields["section"].widget = forms.HiddenInput()
            self.fields["grade"].widget = forms.HiddenInput()

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get("start_date")
        end_date = cleaned_data.get("end_date")

        # Validate date range
        if start_date and end_date and start_date > end_date:
            raise forms.ValidationError("Start date must be before end date.")

        return cleaned_data


class AuditLogFilterForm(forms.Form):
    """Form for filtering audit logs"""

    user = forms.ModelChoiceField(
        queryset=User.objects.all(),
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
        empty_label="All Users",
    )

    action = forms.ChoiceField(
        choices=[("", "All Actions")]
        + [
            (choice[0], choice[1])
            for choice in [
                ("create", "Create"),
                ("update", "Update"),
                ("delete", "Delete"),
                ("login", "Login"),
                ("logout", "Logout"),
                ("view", "View"),
                ("export", "Export"),
                ("import", "Import"),
                ("system_action", "System Action"),
            ]
        ],
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    module_name = forms.CharField(
        max_length=50,
        required=False,
        widget=forms.TextInput(
            attrs={
                "placeholder": "Module name...",
                "class": "form-control",
            }
        ),
    )

    start_date = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(
            attrs={"type": "datetime-local", "class": "form-control"}
        ),
    )

    end_date = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(
            attrs={"type": "datetime-local", "class": "form-control"}
        ),
    )

    ip_address = forms.GenericIPAddressField(
        required=False,
        widget=forms.TextInput(
            attrs={
                "placeholder": "IP Address...",
                "class": "form-control",
            }
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Limit user queryset to reduce load
        self.fields["user"].queryset = User.objects.filter(is_active=True).order_by(
            "first_name", "last_name", "username"
        )[:100]


class AnalyticsCalculationForm(forms.Form):
    """Form for triggering analytics calculations"""

    TYPE_CHOICES = [
        ("all", "All Analytics"),
        ("student", "Student Performance"),
        ("class", "Class Performance"),
        ("attendance", "Attendance Analytics"),
        ("financial", "Financial Analytics"),
        ("teacher", "Teacher Performance"),
    ]

    analytics_type = forms.ChoiceField(
        choices=TYPE_CHOICES,
        widget=forms.Select(attrs={"class": "form-select"}),
        initial="all",
    )

    force_recalculate = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
        help_text="Force recalculation even if analytics already exist",
    )

    academic_year = forms.ModelChoiceField(
        queryset=None,  # Will be set in __init__
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
        empty_label="Current Academic Year",
    )

    term = forms.ModelChoiceField(
        queryset=None,  # Will be set in __init__
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
        empty_label="Current Term",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        try:
            from src.academics.models import AcademicYear, Term

            self.fields["academic_year"].queryset = AcademicYear.objects.all().order_by(
                "-start_date"
            )
            self.fields["term"].queryset = Term.objects.all().order_by("term_number")
        except ImportError:
            self.fields["academic_year"].widget = forms.HiddenInput()
            self.fields["term"].widget = forms.HiddenInput()


class SystemHealthFilterForm(forms.Form):
    """Form for filtering system health metrics"""

    hours = forms.IntegerField(
        initial=24,
        min_value=1,
        max_value=168,  # 1 week
        widget=forms.NumberInput(
            attrs={
                "class": "form-control",
                "placeholder": "Hours to display",
            }
        ),
        help_text="Number of hours of history to display (max 168)",
    )

    metric_type = forms.ChoiceField(
        choices=[
            ("all", "All Metrics"),
            ("performance", "Performance Metrics"),
            ("database", "Database Metrics"),
            ("cache", "Cache Metrics"),
            ("storage", "Storage Metrics"),
        ],
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
        initial="all",
    )


class BulkUserActionForm(forms.Form):
    """Form for bulk user actions"""

    ACTION_CHOICES = [
        ("activate", "Activate Users"),
        ("deactivate", "Deactivate Users"),
        ("send_notification", "Send Notification"),
        ("export_data", "Export User Data"),
        ("password_reset", "Send Password Reset"),
    ]

    action = forms.ChoiceField(
        choices=ACTION_CHOICES,
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    user_ids = forms.CharField(
        widget=forms.HiddenInput(),
        help_text="Comma-separated list of user IDs",
    )

    message = forms.CharField(
        max_length=500,
        required=False,
        widget=forms.Textarea(
            attrs={
                "rows": 3,
                "class": "form-control",
                "placeholder": "Message for notification...",
            }
        ),
        help_text="Message to send (for notification action)",
    )

    def clean_user_ids(self):
        """Validate user IDs"""
        user_ids_str = self.cleaned_data["user_ids"]
        if not user_ids_str:
            raise forms.ValidationError("No users selected")

        try:
            user_ids = [int(id.strip()) for id in user_ids_str.split(",") if id.strip()]
            if not user_ids:
                raise forms.ValidationError("No valid user IDs provided")
            return user_ids
        except ValueError:
            raise forms.ValidationError("Invalid user ID format")

    def clean(self):
        cleaned_data = super().clean()
        action = cleaned_data.get("action")
        message = cleaned_data.get("message")

        if action == "send_notification" and not message:
            raise forms.ValidationError("Message is required for notification action")

        return cleaned_data
