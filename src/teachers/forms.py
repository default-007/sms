from django import forms
from django.contrib.auth import get_user_model
from django.utils import timezone
from .models import Teacher, TeacherClassAssignment, TeacherEvaluation
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Column, Submit, Div, HTML

User = get_user_model()


class TeacherForm(forms.ModelForm):
    first_name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={"class": "form-control"}),
        required=True,
    )
    last_name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={"class": "form-control"}),
        required=True,
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={"class": "form-control"}), required=True
    )
    phone_number = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    profile_picture = forms.ImageField(
        required=False, widget=forms.FileInput(attrs={"class": "form-control"})
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
                attrs={"class": "form-control", "required": True}
            ),
            "joining_date": forms.DateInput(
                attrs={"class": "form-control", "type": "date", "required": True}
            ),
            "qualification": forms.TextInput(
                attrs={"class": "form-control", "required": True}
            ),
            "experience_years": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "step": "0.1",
                    "min": "0",
                    "required": True,
                }
            ),
            "specialization": forms.TextInput(
                attrs={"class": "form-control", "required": True}
            ),
            "department": forms.Select(attrs={"class": "form-select select2"}),
            "position": forms.TextInput(
                attrs={"class": "form-control", "required": True}
            ),
            "salary": forms.NumberInput(
                attrs={"class": "form-control", "min": "0", "required": True}
            ),
            "contract_type": forms.Select(
                attrs={"class": "form-select", "required": True}
            ),
            "status": forms.Select(attrs={"class": "form-select", "required": True}),
            "bio": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "emergency_contact": forms.TextInput(attrs={"class": "form-control"}),
            "emergency_phone": forms.TextInput(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields["first_name"].initial = self.instance.user.first_name
            self.fields["last_name"].initial = self.instance.user.last_name
            self.fields["email"].initial = self.instance.user.email
            self.fields["phone_number"].initial = self.instance.user.phone_number
            if hasattr(self.instance.user, "profile_picture"):
                self.fields["profile_picture"].initial = (
                    self.instance.user.profile_picture
                )

        # Setup crispy forms helper
        self.helper = FormHelper()
        self.helper.form_tag = True
        self.helper.form_class = "form-horizontal"
        self.helper.label_class = "col-md-3"
        self.helper.field_class = "col-md-9"
        self.helper.layout = Layout(
            HTML('<h5 class="mb-4">Personal Information</h5>'),
            Row(
                Column("first_name", css_class="form-group col-md-6 mb-3"),
                Column("last_name", css_class="form-group col-md-6 mb-3"),
                css_class="form-row",
            ),
            Row(
                Column("email", css_class="form-group col-md-6 mb-3"),
                Column("phone_number", css_class="form-group col-md-6 mb-3"),
                css_class="form-row",
            ),
            Row(
                Column("profile_picture", css_class="form-group col-md-6 mb-3"),
                css_class="form-row",
            ),
            HTML('<hr><h5 class="mb-4">Employment Information</h5>'),
            Row(
                Column("employee_id", css_class="form-group col-md-6 mb-3"),
                Column("joining_date", css_class="form-group col-md-6 mb-3"),
                css_class="form-row",
            ),
            Row(
                Column("department", css_class="form-group col-md-6 mb-3"),
                Column("position", css_class="form-group col-md-6 mb-3"),
                css_class="form-row",
            ),
            Row(
                Column("salary", css_class="form-group col-md-4 mb-3"),
                Column("contract_type", css_class="form-group col-md-4 mb-3"),
                Column("status", css_class="form-group col-md-4 mb-3"),
                css_class="form-row",
            ),
            HTML('<hr><h5 class="mb-4">Qualifications & Expertise</h5>'),
            Row(
                Column("qualification", css_class="form-group col-md-6 mb-3"),
                Column("experience_years", css_class="form-group col-md-6 mb-3"),
                css_class="form-row",
            ),
            Row(
                Column("specialization", css_class="form-group col-md-12 mb-3"),
                css_class="form-row",
            ),
            HTML('<hr><h5 class="mb-4">Additional Information</h5>'),
            Row(
                Column("bio", css_class="form-group col-md-12 mb-3"),
                css_class="form-row",
            ),
            Row(
                Column("emergency_contact", css_class="form-group col-md-6 mb-3"),
                Column("emergency_phone", css_class="form-group col-md-6 mb-3"),
                css_class="form-row",
            ),
            Div(
                Submit("submit", "Save", css_class="btn btn-primary"),
                HTML(
                    '<a href="{% url "teachers:teacher-list" %}" class="btn btn-secondary ms-2">Cancel</a>'
                ),
                css_class="text-end",
            ),
        )

    def clean_email(self):
        email = self.cleaned_data.get("email")
        user_id = self.instance.user.id if self.instance and self.instance.pk else None

        # Check if email already exists
        if User.objects.filter(email=email).exclude(id=user_id).exists():
            raise forms.ValidationError("This email is already in use by another user.")

        return email

    def clean_employee_id(self):
        employee_id = self.cleaned_data.get("employee_id")
        instance_id = self.instance.id if self.instance and self.instance.pk else None

        # Check if employee_id already exists
        if (
            Teacher.objects.filter(employee_id=employee_id)
            .exclude(id=instance_id)
            .exists()
        ):
            raise forms.ValidationError("This employee ID is already in use.")

        return employee_id

    def save(self, commit=True):
        teacher = super().save(commit=False)

        # Get or create user
        if teacher.pk:
            user = teacher.user
        else:
            user = User.objects.filter(email=self.cleaned_data["email"]).first()
            if not user:
                user = User(
                    username=self.cleaned_data["email"],
                    email=self.cleaned_data["email"],
                    is_active=True,
                )

        # Update user fields
        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data["last_name"]
        user.email = self.cleaned_data["email"]
        user.username = self.cleaned_data["email"]  # Ensure username matches email

        if hasattr(user, "phone_number"):  # Check if User model has phone_number field
            user.phone_number = self.cleaned_data.get("phone_number", "")

        # Handle profile picture if present
        if (
            "profile_picture" in self.cleaned_data
            and self.cleaned_data["profile_picture"]
        ):
            if hasattr(
                user, "profile_picture"
            ):  # Check if User model has profile_picture field
                user.profile_picture = self.cleaned_data["profile_picture"]

        if commit:
            user.save()
            teacher.user = user
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
            "notes",
        )
        widgets = {
            "teacher": forms.HiddenInput(),
            "class_instance": forms.Select(attrs={"class": "form-select select2"}),
            "subject": forms.Select(attrs={"class": "form-select select2"}),
            "academic_year": forms.Select(attrs={"class": "form-select"}),
            "is_class_teacher": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
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
        from src.courses.models import Department

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
