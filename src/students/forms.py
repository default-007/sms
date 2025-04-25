from django import forms
from django.contrib.auth import get_user_model
from .models import Student, Parent, StudentParentRelation

User = get_user_model()


class StudentForm(forms.ModelForm):
    first_name = forms.CharField(max_length=100)
    last_name = forms.CharField(max_length=100)
    email = forms.EmailField()
    phone_number = forms.CharField(max_length=20)

    class Meta:
        model = Student
        fields = (
            "admission_number",
            "admission_date",
            "current_class",
            "roll_number",
            "blood_group",
            "medical_conditions",
            "emergency_contact_name",
            "emergency_contact_number",
            "previous_school",
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
        student = super().save(commit=False)

        # Get or create user
        if student.pk:
            user = student.user
        else:
            user = User(username=self.cleaned_data["email"])

        # Update user fields
        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data["last_name"]
        user.email = self.cleaned_data["email"]
        user.phone_number = self.cleaned_data["phone_number"]

        if commit:
            user.save()
            student.user = user
            student.save()

        return student


class ParentForm(forms.ModelForm):
    first_name = forms.CharField(max_length=100)
    last_name = forms.CharField(max_length=100)
    email = forms.EmailField()
    phone_number = forms.CharField(max_length=20)

    class Meta:
        model = Parent
        fields = ("occupation", "annual_income", "education", "relation_with_student")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields["first_name"].initial = self.instance.user.first_name
            self.fields["last_name"].initial = self.instance.user.last_name
            self.fields["email"].initial = self.instance.user.email
            self.fields["phone_number"].initial = self.instance.user.phone_number

    def save(self, commit=True):
        parent = super().save(commit=False)

        # Get or create user
        if parent.pk:
            user = parent.user
        else:
            user = User(username=self.cleaned_data["email"])

        # Update user fields
        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data["last_name"]
        user.email = self.cleaned_data["email"]
        user.phone_number = self.cleaned_data["phone_number"]

        if commit:
            user.save()
            parent.user = user
            parent.save()

        return parent


class StudentParentRelationForm(forms.ModelForm):
    class Meta:
        model = StudentParentRelation
        fields = ("student", "parent", "is_primary_contact")
