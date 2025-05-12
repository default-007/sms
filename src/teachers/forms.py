# src/teachers/forms.py
from django import forms
from django.contrib.auth import get_user_model
from .models import Teacher, TeacherClassAssignment, TeacherEvaluation

User = get_user_model()


class TeacherForm(forms.ModelForm):
    first_name = forms.CharField(
        max_length=100, widget=forms.TextInput(attrs={"class": "form-control"})
    )
    last_name = forms.CharField(
        max_length=100, widget=forms.TextInput(attrs={"class": "form-control"})
    )
    email = forms.EmailField(widget=forms.EmailInput(attrs={"class": "form-control"}))
    phone_number = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control"}),
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
            "employee_id": forms.TextInput(attrs={"class": "form-control"}),
            "joining_date": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}
            ),
            "qualification": forms.TextInput(attrs={"class": "form-control"}),
            "experience_years": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.1"}
            ),
            "specialization": forms.TextInput(attrs={"class": "form-control"}),
            "department": forms.Select(attrs={"class": "form-select"}),
            "position": forms.TextInput(attrs={"class": "form-control"}),
            "salary": forms.NumberInput(attrs={"class": "form-control"}),
            "contract_type": forms.Select(attrs={"class": "form-select"}),
            "status": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields["first_name"].initial = self.instance.user.first_name
            self.fields["last_name"].initial = self.instance.user.last_name
            self.fields["email"].initial = self.instance.user.email
            self.fields["phone_number"].initial = self.instance.user.phone_number

    def save(self, commit=True):
        teacher = super().save(commit=False)

        # Get or create user
        if teacher.pk:
            user = teacher.user
        else:
            user = User(username=self.cleaned_data["email"])

        # Update user fields
        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data["last_name"]
        user.email = self.cleaned_data["email"]
        user.phone_number = self.cleaned_data["phone_number"]

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
