import re
from crispy_forms.helper import FormHelper
from crispy_forms.layout import HTML, Column, Div, Layout, Row, Submit
from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.db import transaction
from src.accounts.services.authentication_service import AuthenticationService
from src.accounts.services.role_service import RoleService
from .models import Teacher, TeacherClassAssignment, TeacherEvaluation

User = get_user_model()


class TeacherForm(forms.ModelForm):
    # User account fields
    first_name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={"class": "form-control"}),
        required=True,
        help_text="Teacher's first name",
    )
    last_name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={"class": "form-control"}),
        required=True,
        help_text="Teacher's last name",
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={"class": "form-control"}),
        required=True,
        help_text="Valid email address for account access",
    )
    phone_number = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control"}),
        help_text="Contact phone number",
    )
    profile_picture = forms.ImageField(
        required=False,
        widget=forms.FileInput(attrs={"class": "form-control"}),
        help_text="Optional profile picture",
    )

    # Optional credential fields for manual entry
    username = forms.CharField(
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control"}),
        help_text="Auto-generated from name if left blank",
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={"class": "form-control"}),
        required=False,
        help_text="Auto-generated secure password if left blank",
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={"class": "form-control"}),
        required=False,
        help_text="Confirm the password if you set one manually",
    )

    # Email notification option
    send_welcome_email = forms.BooleanField(
        initial=True,
        required=False,
        help_text="Send welcome email with login credentials to the teacher",
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
        label="Send welcome email with login credentials",
    )

    class Meta:
        model = Teacher
        fields = (
            "employee_id",
            "joining_date",
            "qualification",
            "experience_years",
            "specialization",
            "department",
            "position",
            "salary",
            "contract_type",
            "status",
            "bio",
            "emergency_contact",
            "emergency_phone",
        )
        widgets = {
            "employee_id": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Auto-generated if left blank",
                }
            ),
            "joining_date": forms.DateInput(
                attrs={"class": "form-control", "type": "date", "required": True}
            ),
            "qualification": forms.TextInput(attrs={"class": "form-control"}),
            "experience_years": forms.NumberInput(
                attrs={"class": "form-control", "min": "0", "max": "50"}
            ),
            "specialization": forms.Textarea(
                attrs={"class": "form-control", "rows": 3}
            ),
            "department": forms.Select(attrs={"class": "form-control"}),
            "position": forms.Select(attrs={"class": "form-control"}),
            "salary": forms.NumberInput(
                attrs={"class": "form-control", "min": "0", "step": "0.01"}
            ),
            "contract_type": forms.Select(attrs={"class": "form-control"}),
            "status": forms.Select(attrs={"class": "form-control"}),
            "bio": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
            "emergency_contact": forms.TextInput(attrs={"class": "form-control"}),
            "emergency_phone": forms.TextInput(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        # Extract created_by from kwargs if available
        self.created_by = kwargs.pop("created_by", None)
        super().__init__(*args, **kwargs)

        # If editing existing teacher, populate user fields and hide credential fields
        if self.instance and self.instance.pk and self.instance.user:
            user = self.instance.user
            self.fields["first_name"].initial = user.first_name
            self.fields["last_name"].initial = user.last_name
            self.fields["email"].initial = user.email
            if hasattr(user, "phone_number"):
                self.fields["phone_number"].initial = user.phone_number

            # Hide credential fields for existing teachers
            del self.fields["username"]
            del self.fields["password"]
            del self.fields["confirm_password"]
            del self.fields["send_welcome_email"]

        # Set default joining date if creating new teacher
        if not self.instance.pk:
            self.fields["joining_date"].initial = timezone.now().date()

    def clean_email(self):
        email = self.cleaned_data.get("email")
        instance_id = self.instance.id if self.instance and self.instance.pk else None

        # Check if email already exists for a different teacher
        existing_user = User.objects.filter(email=email).first()
        if existing_user:
            # If this is an update and the email belongs to the same teacher, it's OK
            if (
                instance_id
                and hasattr(existing_user, "teacher")
                and existing_user.teacher.id == instance_id
            ):
                pass  # Same teacher, email is OK
            else:
                raise forms.ValidationError(
                    "This email is already in use by another user."
                )

        return email

    def clean_employee_id(self):
        employee_id = self.cleaned_data.get("employee_id")
        instance_id = self.instance.id if self.instance and self.instance.pk else None

        # Auto-generate employee ID if not provided for new teachers
        if not employee_id and not instance_id:
            employee_id = self._generate_employee_id()

        # Check if employee_id already exists
        if (
            employee_id
            and Teacher.objects.filter(employee_id=employee_id)
            .exclude(id=instance_id)
            .exists()
        ):
            # If auto-generated ID conflicts, try again
            if not self.cleaned_data.get("employee_id"):
                employee_id = self._generate_employee_id()
                # Double-check the new ID
                if (
                    Teacher.objects.filter(employee_id=employee_id)
                    .exclude(id=instance_id)
                    .exists()
                ):
                    raise forms.ValidationError(
                        "Unable to generate unique employee ID. Please provide one manually."
                    )
            else:
                raise forms.ValidationError("This employee ID is already in use.")

        return employee_id

    def clean_username(self):
        username = self.cleaned_data.get("username")

        # Only validate username for new teachers
        if self.instance and self.instance.pk:
            return username

        # If username provided, validate it
        if username:
            # Check for valid characters
            if not re.match(r"^[a-zA-Z0-9._]+$", username):
                raise forms.ValidationError(
                    "Username can only contain letters, numbers, periods, and underscores."
                )

            # Check uniqueness
            if User.objects.filter(username=username).exists():
                raise forms.ValidationError("This username is already taken.")

        return username

    def clean(self):
        cleaned_data = super().clean()

        # Only validate passwords for new teachers
        if self.instance and self.instance.pk:
            return cleaned_data

        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")

        # If password is provided, confirm password must match
        if password and password != confirm_password:
            raise forms.ValidationError({"confirm_password": "Passwords do not match."})

        return cleaned_data

    def _generate_employee_id(self):
        """Generate a unique employee ID in format TCH{YEAR}{NNNN}"""
        current_year = timezone.now().year
        prefix = f"TCH{current_year}"

        # Find the last employee ID with this prefix
        last_teacher = (
            Teacher.objects.filter(employee_id__startswith=prefix)
            .order_by("employee_id")
            .last()
        )

        if last_teacher:
            try:
                # Extract the number part and increment
                last_number = int(last_teacher.employee_id.replace(prefix, ""))
                new_number = last_number + 1
            except ValueError:
                new_number = 1
        else:
            new_number = 1

        return f"{prefix}{new_number:04d}"

    @transaction.atomic
    def save(self, commit=True):
        teacher = super().save(commit=False)

        if teacher.pk:
            # Updating existing teacher - only update user fields
            user = teacher.user
            user.first_name = self.cleaned_data["first_name"]
            user.last_name = self.cleaned_data["last_name"]
            user.email = self.cleaned_data["email"]

            if hasattr(user, "phone_number"):
                user.phone_number = self.cleaned_data.get("phone_number", "")

            # Handle profile picture if present
            if self.cleaned_data.get("profile_picture"):
                if hasattr(user, "profile_picture"):
                    user.profile_picture = self.cleaned_data["profile_picture"]

            if commit:
                user.save()
        else:
            # Creating new teacher - use AuthenticationService
            user_data = {
                "first_name": self.cleaned_data["first_name"],
                "last_name": self.cleaned_data["last_name"],
                "email": self.cleaned_data["email"],
                "is_active": True,
            }

            # Add optional fields
            if self.cleaned_data.get("phone_number"):
                user_data["phone_number"] = self.cleaned_data["phone_number"]

            # Add username if provided, otherwise let service generate it
            if self.cleaned_data.get("username"):
                user_data["username"] = self.cleaned_data["username"]

            # Add password if provided, otherwise let service generate it
            if self.cleaned_data.get("password"):
                user_data["password"] = self.cleaned_data["password"]

            try:
                # Use AuthenticationService to create user with proper setup
                user = AuthenticationService.register_user(
                    user_data=user_data,
                    role_names=["Teacher"],  # Assign Teacher role
                    created_by=self.created_by,
                    send_email=self.cleaned_data.get("send_welcome_email", True),
                )

                # Handle profile picture if present
                if self.cleaned_data.get("profile_picture"):
                    if hasattr(user, "profile_picture"):
                        user.profile_picture = self.cleaned_data["profile_picture"]
                        user.save()

            except Exception as e:
                raise forms.ValidationError(f"Error creating user account: {str(e)}")

        if commit:
            teacher.user = user
            # Ensure employee_id is set
            if not teacher.employee_id:
                teacher.employee_id = (
                    self.cleaned_data.get("employee_id") or self._generate_employee_id()
                )
            teacher.save()

        return teacher


class TeacherClassAssignmentForm(forms.ModelForm):
    class Meta:
        model = TeacherClassAssignment
        fields = (
            "teacher",
            "class_instance",
            "subject",
            "academic_year",
            "is_class_teacher",
        )
        widgets = {
            "teacher": forms.Select(attrs={"class": "form-control"}),
            "class_instance": forms.Select(attrs={"class": "form-control"}),
            "subject": forms.Select(attrs={"class": "form-control"}),
            "academic_year": forms.Select(attrs={"class": "form-control"}),
            "is_class_teacher": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # If teacher is preselected, make it readonly
        teacher_id = kwargs.get("initial", {}).get("teacher")
        if teacher_id:
            self.fields["teacher"].widget = forms.HiddenInput()

        # Setup crispy forms helper
        self.helper = FormHelper()
        self.helper.form_tag = True
        self.helper.layout = Layout(
            "teacher",
            Row(
                Column("academic_year", css_class="form-group col-md-12 mb-3"),
                css_class="form-row",
            ),
            Row(
                Column("class_instance", css_class="form-group col-md-6 mb-3"),
                Column("subject", css_class="form-group col-md-6 mb-3"),
                css_class="form-row",
            ),
            Row(
                Column("is_class_teacher", css_class="form-group col-md-12 mb-3"),
                css_class="form-row",
            ),
            Row(
                Column("notes", css_class="form-group col-md-12 mb-3"),
                css_class="form-row",
            ),
            Div(
                Submit("submit", "Save", css_class="btn btn-primary"),
                HTML(
                    '<a href="#" onclick="history.back(); return false;" class="btn btn-secondary ms-2">Cancel</a>'
                ),
                css_class="text-end",
            ),
        )

    def clean(self):
        cleaned_data = super().clean()
        teacher = cleaned_data.get("teacher")
        class_instance = cleaned_data.get("class_instance")
        subject = cleaned_data.get("subject")
        academic_year = cleaned_data.get("academic_year")
        is_class_teacher = cleaned_data.get("is_class_teacher")

        # Check if this teacher is already assigned to this class and subject
        if teacher and class_instance and subject and academic_year:
            if (
                TeacherClassAssignment.objects.filter(
                    teacher=teacher,
                    class_instance=class_instance,
                    subject=subject,
                    academic_year=academic_year,
                )
                .exclude(id=self.instance.id if self.instance.id else None)
                .exists()
            ):
                raise forms.ValidationError(
                    "This teacher is already assigned to this class and subject for the selected academic year."
                )

        # Check if another teacher is already the class teacher
        if is_class_teacher and class_instance and academic_year:
            existing_class_teacher = (
                TeacherClassAssignment.objects.filter(
                    class_instance=class_instance,
                    academic_year=academic_year,
                    is_class_teacher=True,
                )
                .exclude(id=self.instance.id if self.instance.id else None)
                .first()
            )

            if existing_class_teacher:
                raise forms.ValidationError(
                    f"{existing_class_teacher.teacher.get_full_name()} is already assigned as the class teacher for this class."
                )

        return cleaned_data


class TeacherEvaluationForm(forms.ModelForm):
    class Meta:
        model = TeacherEvaluation
        fields = (
            "teacher",
            "evaluation_date",
            "criteria",
            "score",
            "remarks",
            "followup_actions",
            "status",
            "followup_date",
        )
        widgets = {
            "teacher": forms.HiddenInput(),
            "evaluation_date": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}
            ),
            "criteria": forms.HiddenInput(),
            "score": forms.HiddenInput(),
            "remarks": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
            "followup_actions": forms.Textarea(
                attrs={"class": "form-control", "rows": 4}
            ),
            "status": forms.Select(attrs={"class": "form-select"}),
            "followup_date": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}
            ),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

        # Default criteria structure if empty
        if not self.instance.pk:
            self.fields["criteria"].initial = TeacherEvaluation.get_default_criteria()
            self.fields["evaluation_date"].initial = timezone.now().date()

        # Make followup_date conditional based on score
        self.fields["followup_date"].required = False

        # Setup crispy forms helper
        self.helper = FormHelper()
        self.helper.form_tag = True
        self.helper.layout = Layout(
            "teacher",
            "criteria",
            "score",
            Row(
                Column("evaluation_date", css_class="form-group col-md-6 mb-3"),
                Column("status", css_class="form-group col-md-6 mb-3"),
                css_class="form-row",
            ),
            HTML('<div id="criteria-container" class="mb-4"></div>'),
            Row(
                Column("remarks", css_class="form-group col-md-12 mb-3"),
                css_class="form-row",
            ),
            Row(
                Column("followup_actions", css_class="form-group col-md-6 mb-3"),
                Column("followup_date", css_class="form-group col-md-6 mb-3"),
                css_class="form-row",
                id="followup-row",
            ),
            Div(
                Submit("submit", "Save", css_class="btn btn-primary"),
                HTML(
                    '<a href="#" onclick="history.back(); return false;" class="btn btn-secondary ms-2">Cancel</a>'
                ),
                css_class="text-end",
            ),
        )

    def clean(self):
        cleaned_data = super().clean()
        score = cleaned_data.get("score")
        status = cleaned_data.get("status")
        followup_date = cleaned_data.get("followup_date")
        followup_actions = cleaned_data.get("followup_actions")

        # If score is low, require followup information
        if score and float(score) < 70 and status != "closed":
            if not followup_actions:
                self.add_error(
                    "followup_actions",
                    "Follow-up actions are required for low performance evaluations.",
                )
            if not followup_date:
                self.add_error(
                    "followup_date",
                    "Follow-up date is required for low performance evaluations.",
                )

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.user and not instance.evaluator_id:
            instance.evaluator = self.user
        if commit:
            instance.save()
        return instance


class TeacherFilterForm(forms.Form):
    name = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Search by name"}
        ),
    )
    department = forms.ModelChoiceField(
        queryset=None,
        required=False,
        empty_label="All Departments",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    status = forms.ChoiceField(
        choices=[("", "All Statuses")] + list(Teacher.STATUS_CHOICES),
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    contract_type = forms.ChoiceField(
        choices=[("", "All Contract Types")] + list(Teacher.CONTRACT_TYPE_CHOICES),
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    experience_min = forms.DecimalField(
        required=False,
        min_value=0,
        widget=forms.NumberInput(attrs={"class": "form-control", "placeholder": "Min"}),
    )
    experience_max = forms.DecimalField(
        required=False,
        min_value=0,
        widget=forms.NumberInput(attrs={"class": "form-control", "placeholder": "Max"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from src.academics.models import Department

        self.fields["department"].queryset = Department.objects.all()

        # Setup crispy forms helper
        self.helper = FormHelper()
        self.helper.form_method = "get"
        self.helper.form_class = "row align-items-end"
        self.helper.layout = Layout(
            Column("name", css_class="form-group col-md-3 mb-0"),
            Column("department", css_class="form-group col-md-2 mb-0"),
            Column("status", css_class="form-group col-md-2 mb-0"),
            Column("contract_type", css_class="form-group col-md-2 mb-0"),
            Column(
                Div(
                    Div("experience_min", css_class="col-6 pe-1"),
                    Div("experience_max", css_class="col-6 ps-1"),
                    css_class="row",
                ),
                css_class="form-group col-md-2 mb-0",
                title="Experience Range (Years)",
            ),
            Column(
                Submit("submit", "Filter", css_class="btn btn-primary w-100"),
                css_class="form-group col-md-1 mb-0",
            ),
        )
