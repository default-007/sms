from django import forms
from django.contrib.auth import get_user_model
from .models import Teacher, TeacherClassAssignment, TeacherEvaluation

User = get_user_model()


class TeacherForm(forms.ModelForm):
    first_name = forms.CharField(max_length=100)
    last_name = forms.CharField(max_length=100)
    email = forms.EmailField()
    phone_number = forms.CharField(max_length=20)

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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # If teacher is preselected, make it readonly
        teacher_id = kwargs.get("initial", {}).get("teacher")
        if teacher_id:
            self.fields["teacher"].widget.attrs["readonly"] = True


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
            "criteria": forms.Textarea(attrs={"rows": 4}),
            "remarks": forms.Textarea(attrs={"rows": 4}),
            "followup_actions": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # If teacher is preselected, make it readonly
        teacher_id = kwargs.get("initial", {}).get("teacher")
        if teacher_id:
            self.fields["teacher"].widget.attrs["readonly"] = True

        # Default criteria structure if empty
        if not self.instance.pk:
            self.fields["criteria"].initial = {
                "teaching_methodology": {"score": 0, "max_score": 10, "comments": ""},
                "subject_knowledge": {"score": 0, "max_score": 10, "comments": ""},
                "classroom_management": {"score": 0, "max_score": 10, "comments": ""},
                "student_engagement": {"score": 0, "max_score": 10, "comments": ""},
                "professional_conduct": {"score": 0, "max_score": 10, "comments": ""},
            }
