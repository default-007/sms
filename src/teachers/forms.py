# src/teachers/forms.py
from django import forms
from django.contrib.auth import get_user_model
from .models import Teacher, TeacherClassAssignment, TeacherEvaluation

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
            "department": forms.Select(attrs={"class": "form-select select2-enable"}),
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
        )
        widgets = {
            "teacher": forms.HiddenInput(),
            "class_instance": forms.Select(attrs={"class": "form-select"}),
            "subject": forms.Select(attrs={"class": "form-select"}),
            "academic_year": forms.Select(attrs={"class": "form-select"}),
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
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

        # Default criteria structure if empty
        if not self.instance.pk:
            self.fields["criteria"].initial = {
                "teaching_methodology": {"score": 0, "max_score": 10, "comments": ""},
                "subject_knowledge": {"score": 0, "max_score": 10, "comments": ""},
                "classroom_management": {"score": 0, "max_score": 10, "comments": ""},
                "student_engagement": {"score": 0, "max_score": 10, "comments": ""},
                "professional_conduct": {"score": 0, "max_score": 10, "comments": ""},
            }
            self.fields["evaluation_date"].initial = timezone.now().date()

    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.user and not instance.evaluator_id:
            instance.evaluator = self.user
        if commit:
            instance.save()
        return instance
