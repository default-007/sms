# students/forms.py
from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
import csv
import io

from .models import Student, Parent, StudentParentRelation
from src.courses.models import Class, AcademicYear

User = get_user_model()


class StudentForm(forms.ModelForm):
    # User fields
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
        widget=forms.TextInput(attrs={"class": "form-control"}),
        required=False,
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={"class": "form-control"}),
        required=False,
        help_text="Leave blank if not changing password.",
    )

    # Additional student fields for easier form organization
    address_line = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={"class": "form-control"}),
        required=False,
    )

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
            "nationality",
            "religion",
            "city",
            "state",
            "postal_code",
            "country",
            "photo",
        )
        widgets = {
            "admission_number": forms.TextInput(attrs={"class": "form-control"}),
            "admission_date": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}
            ),
            "current_class": forms.Select(attrs={"class": "form-control"}),
            "roll_number": forms.TextInput(attrs={"class": "form-control"}),
            "blood_group": forms.Select(attrs={"class": "form-control"}),
            "medical_conditions": forms.Textarea(
                attrs={"class": "form-control", "rows": 3}
            ),
            "emergency_contact_name": forms.TextInput(attrs={"class": "form-control"}),
            "emergency_contact_number": forms.TextInput(
                attrs={"class": "form-control"}
            ),
            "previous_school": forms.TextInput(attrs={"class": "form-control"}),
            "status": forms.Select(attrs={"class": "form-control"}),
            "nationality": forms.TextInput(attrs={"class": "form-control"}),
            "religion": forms.TextInput(attrs={"class": "form-control"}),
            "city": forms.TextInput(attrs={"class": "form-control"}),
            "state": forms.TextInput(attrs={"class": "form-control"}),
            "postal_code": forms.TextInput(attrs={"class": "form-control"}),
            "country": forms.TextInput(attrs={"class": "form-control"}),
            "photo": forms.FileInput(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Make certain fields required
        self.fields["emergency_contact_name"].required = True
        self.fields["emergency_contact_number"].required = True

        # Populate user fields if instance exists
        if self.instance and self.instance.pk:
            self.fields["first_name"].initial = self.instance.user.first_name
            self.fields["last_name"].initial = self.instance.user.last_name
            self.fields["email"].initial = self.instance.user.email
            self.fields["phone_number"].initial = self.instance.user.phone_number

            # Populate address field
            self.fields["address_line"].initial = self.instance.address

        # Filter current_class choices to show only classes from the current academic year
        current_year = AcademicYear.objects.filter(is_current=True).first()
        if current_year:
            self.fields["current_class"].queryset = Class.objects.filter(
                academic_year=current_year
            ).select_related("grade", "section")

    def clean_email(self):
        email = self.cleaned_data.get("email")

        # Check if email is already in use
        if self.instance and self.instance.pk:
            # Existing student - check if email is used by someone else
            existing_users = User.objects.filter(email=email).exclude(
                id=self.instance.user.id
            )
        else:
            # New student - check if email is already in use
            existing_users = User.objects.filter(email=email)

        if existing_users.exists():
            raise ValidationError(_("This email address is already in use."))

        return email

    def clean_admission_number(self):
        admission_number = self.cleaned_data.get("admission_number")

        # Check if admission number is already in use
        if self.instance and self.instance.pk:
            # Existing student - check if admission number is used by someone else
            existing_students = Student.objects.filter(
                admission_number=admission_number
            ).exclude(id=self.instance.id)
        else:
            # New student - check if admission number is already in use
            existing_students = Student.objects.filter(
                admission_number=admission_number
            )

        if existing_students.exists():
            raise ValidationError(_("This admission number is already in use."))

        return admission_number

    def save(self, commit=True):
        student = super().save(commit=False)

        # Get or create user
        if student.pk:
            user = student.user
        else:
            # Check if user with this email already exists
            email = self.cleaned_data["email"]
            try:
                user = User.objects.get(email=email)
            except User.DoesNotExist:
                # Create new user
                username = self.cleaned_data["email"]
                user = User(username=username, email=email)

        # Update user fields
        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data["last_name"]
        user.email = self.cleaned_data["email"]
        user.phone_number = self.cleaned_data["phone_number"]

        # Set password if provided
        password = self.cleaned_data.get("password")
        if password:
            user.set_password(password)

        # Save user
        if commit:
            user.save()
            student.user = user

            # Set address from address_line field
            student.address = self.cleaned_data.get("address_line") or ""

            student.save()

            # Ensure student has Student role
            from src.accounts.services import RoleService

            RoleService.assign_role_to_user(user, "Student")

        return student


class ParentForm(forms.ModelForm):
    # User fields
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
        widget=forms.TextInput(attrs={"class": "form-control"}),
        required=True,
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={"class": "form-control"}),
        required=False,
        help_text="Leave blank if not changing password.",
    )

    class Meta:
        model = Parent
        fields = (
            "occupation",
            "annual_income",
            "education",
            "relation_with_student",
            "workplace",
            "work_address",
            "work_phone",
            "emergency_contact",
            "photo",
        )
        widgets = {
            "occupation": forms.TextInput(attrs={"class": "form-control"}),
            "annual_income": forms.NumberInput(attrs={"class": "form-control"}),
            "education": forms.TextInput(attrs={"class": "form-control"}),
            "relation_with_student": forms.Select(attrs={"class": "form-control"}),
            "workplace": forms.TextInput(attrs={"class": "form-control"}),
            "work_address": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "work_phone": forms.TextInput(attrs={"class": "form-control"}),
            "emergency_contact": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),
            "photo": forms.FileInput(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Populate user fields if instance exists
        if self.instance and self.instance.pk:
            self.fields["first_name"].initial = self.instance.user.first_name
            self.fields["last_name"].initial = self.instance.user.last_name
            self.fields["email"].initial = self.instance.user.email
            self.fields["phone_number"].initial = self.instance.user.phone_number

    def clean_email(self):
        email = self.cleaned_data.get("email")

        # Check if email is already in use
        if self.instance and self.instance.pk:
            # Existing parent - check if email is used by someone else
            existing_users = User.objects.filter(email=email).exclude(
                id=self.instance.user.id
            )
        else:
            # New parent - check if email is already in use
            existing_users = User.objects.filter(email=email)

        if existing_users.exists():
            raise ValidationError(_("This email address is already in use."))

        return email

    def save(self, commit=True):
        parent = super().save(commit=False)

        # Get or create user
        if parent.pk:
            user = parent.user
        else:
            # Check if user with this email already exists
            email = self.cleaned_data["email"]
            try:
                user = User.objects.get(email=email)
            except User.DoesNotExist:
                # Create new user
                username = self.cleaned_data["email"]
                user = User(username=username, email=email)

        # Update user fields
        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data["last_name"]
        user.email = self.cleaned_data["email"]
        user.phone_number = self.cleaned_data["phone_number"]

        # Set password if provided
        password = self.cleaned_data.get("password")
        if password:
            user.set_password(password)

        # Save user
        if commit:
            user.save()
            parent.user = user
            parent.save()

            # Ensure parent has Parent role
            from src.accounts.services import RoleService

            RoleService.assign_role_to_user(user, "Parent")

        return parent


class StudentParentRelationForm(forms.ModelForm):
    class Meta:
        model = StudentParentRelation
        fields = (
            "student",
            "parent",
            "is_primary_contact",
            "can_pickup",
            "emergency_contact_priority",
            "financial_responsibility",
            "access_to_grades",
            "access_to_attendance",
        )
        widgets = {
            "student": forms.Select(attrs={"class": "form-control"}),
            "parent": forms.Select(attrs={"class": "form-control"}),
            "is_primary_contact": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),
            "can_pickup": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "emergency_contact_priority": forms.NumberInput(
                attrs={"class": "form-control", "min": 1}
            ),
            "financial_responsibility": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),
            "access_to_grades": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),
            "access_to_attendance": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),
        }

    def __init__(self, *args, **kwargs):
        student = kwargs.pop("student", None)
        parent = kwargs.pop("parent", None)
        super().__init__(*args, **kwargs)

        # Prefill student and parent if provided
        if student:
            self.fields["student"].initial = student
            self.fields["student"].widget.attrs["readonly"] = True

        if parent:
            self.fields["parent"].initial = parent
            self.fields["parent"].widget.attrs["readonly"] = True

        # Use select_related to optimize queries
        self.fields["student"].queryset = Student.objects.select_related(
            "user", "current_class"
        )
        self.fields["parent"].queryset = Parent.objects.select_related("user")


class StudentBulkImportForm(forms.Form):
    csv_file = forms.FileField(
        widget=forms.FileInput(attrs={"class": "form-control"}),
        label="CSV File",
        help_text="CSV file containing student data.",
    )

    def clean_csv_file(self):
        csv_file = self.cleaned_data.get("csv_file")

        if not csv_file:
            return None

        # Check file extension
        if not csv_file.name.endswith(".csv"):
            raise ValidationError(_("File must be a CSV file."))

        # Validate CSV format
        try:
            decoded_file = csv_file.read().decode("utf-8")
            csv_file.seek(0)  # Reset file pointer for later use

            # Parse CSV and check required columns
            csv_data = csv.DictReader(io.StringIO(decoded_file))

            # Check if there's at least one row
            if not csv_data.fieldnames:
                raise ValidationError(_("CSV file is empty or improperly formatted."))

            # Check required columns
            required_columns = ["first_name", "last_name", "email", "admission_number"]
            missing_columns = [
                col for col in required_columns if col not in csv_data.fieldnames
            ]

            if missing_columns:
                raise ValidationError(
                    _(f"Missing required columns: {', '.join(missing_columns)}")
                )

        except Exception as e:
            raise ValidationError(_(f"Error parsing CSV file: {str(e)}"))

        return csv_file


class ParentBulkImportForm(forms.Form):
    csv_file = forms.FileField(
        widget=forms.FileInput(attrs={"class": "form-control"}),
        label="CSV File",
        help_text="CSV file containing parent data.",
    )

    def clean_csv_file(self):
        csv_file = self.cleaned_data.get("csv_file")

        if not csv_file:
            return None

        # Check file extension
        if not csv_file.name.endswith(".csv"):
            raise ValidationError(_("File must be a CSV file."))

        # Validate CSV format
        try:
            decoded_file = csv_file.read().decode("utf-8")
            csv_file.seek(0)  # Reset file pointer for later use

            # Parse CSV and check required columns
            csv_data = csv.DictReader(io.StringIO(decoded_file))

            # Check if there's at least one row
            if not csv_data.fieldnames:
                raise ValidationError(_("CSV file is empty or improperly formatted."))

            # Check required columns
            required_columns = [
                "first_name",
                "last_name",
                "email",
                "relation_with_student",
            ]
            missing_columns = [
                col for col in required_columns if col not in csv_data.fieldnames
            ]

            if missing_columns:
                raise ValidationError(
                    _(f"Missing required columns: {', '.join(missing_columns)}")
                )

        except Exception as e:
            raise ValidationError(_(f"Error parsing CSV file: {str(e)}"))

        return csv_file


class StudentPromotionForm(forms.Form):
    source_class = forms.ModelChoiceField(
        queryset=Class.objects.none(),
        widget=forms.Select(attrs={"class": "form-control"}),
        required=True,
        label="Current Class",
    )

    target_class = forms.ModelChoiceField(
        queryset=Class.objects.none(),
        widget=forms.Select(attrs={"class": "form-control"}),
        required=True,
        label="New Class",
    )

    students = forms.ModelMultipleChoiceField(
        queryset=Student.objects.none(),
        widget=forms.SelectMultiple(attrs={"class": "form-control", "size": 10}),
        required=True,
        label="Students to Promote",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Get current academic year
        current_year = AcademicYear.objects.filter(is_current=True).first()

        if current_year:
            # Populate source class choices with classes from current academic year
            self.fields["source_class"].queryset = Class.objects.filter(
                academic_year=current_year
            ).select_related("grade", "section")

            # For target class, get classes from next academic year if it exists
            next_year = (
                AcademicYear.objects.filter(start_date__gt=current_year.start_date)
                .order_by("start_date")
                .first()
            )

            if next_year:
                self.fields["target_class"].queryset = Class.objects.filter(
                    academic_year=next_year
                ).select_related("grade", "section")
            else:
                # If no next year exists, use current year classes
                self.fields["target_class"].queryset = Class.objects.filter(
                    academic_year=current_year
                ).select_related("grade", "section")
        else:
            # If no current year, use all classes
            all_classes = Class.objects.all().select_related("grade", "section")
            self.fields["source_class"].queryset = all_classes
            self.fields["target_class"].queryset = all_classes

        # If source class is selected, filter students
        if "source_class" in self.data:
            try:
                source_class_id = int(self.data.get("source_class"))
                self.fields["students"].queryset = Student.objects.filter(
                    current_class_id=source_class_id, status="Active"
                ).select_related("user")
            except (ValueError, TypeError):
                pass
        else:
            self.fields["students"].queryset = Student.objects.none()
