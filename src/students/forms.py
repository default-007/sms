import csv
from datetime import timezone
import io

from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from src.academics.models import AcademicYear, Class

from .models import Parent, Student, StudentParentRelation
from .utils import StudentUtils

User = get_user_model()


class BaseModelForm(forms.ModelForm):
    """Base form with common styling"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if isinstance(
                field.widget,
                (
                    forms.TextInput,
                    forms.EmailInput,
                    forms.NumberInput,
                    forms.Select,
                    forms.Textarea,
                    forms.DateInput,
                ),
            ):
                field.widget.attrs.update({"class": "form-control"})
            elif isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.update({"class": "form-check-input"})
            elif isinstance(field.widget, forms.FileInput):
                field.widget.attrs.update({"class": "form-control"})


class StudentForm(forms.ModelForm):
    """Form for creating and updating students with direct fields"""

    class Meta:
        model = Student
        fields = [
            # Personal Information
            "first_name",
            "last_name",
            "email",
            "phone_number",
            "date_of_birth",
            "gender",
            "address",
            "profile_picture",
            # Academic Information
            "admission_number",
            "admission_date",
            "current_class",
            "roll_number",
            # Health and Emergency
            "blood_group",
            "medical_conditions",
            "emergency_contact_name",
            "emergency_contact_number",
            "emergency_contact_relationship",
            # Previous Education
            "previous_school",
            "transfer_certificate_number",
            # Status
            "status",
        ]
        widgets = {
            "first_name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Enter first name",
                    "required": True,
                }
            ),
            "last_name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Enter last name",
                    "required": True,
                }
            ),
            "email": forms.EmailInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Enter email address (optional)",
                }
            ),
            "phone_number": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "+1234567890",
                }
            ),
            "date_of_birth": forms.DateInput(
                attrs={
                    "class": "form-control",
                    "type": "date",
                }
            ),
            "gender": forms.Select(attrs={"class": "form-control"}),
            "address": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": "Enter full address",
                }
            ),
            "admission_number": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "STU-2024-ABC123",
                    "required": True,
                }
            ),
            "admission_date": forms.DateInput(
                attrs={
                    "class": "form-control",
                    "type": "date",
                    "required": True,
                }
            ),
            "current_class": forms.Select(
                attrs={
                    "class": "form-control",
                }
            ),
            "roll_number": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Roll number in class",
                }
            ),
            "blood_group": forms.Select(attrs={"class": "form-control"}),
            "medical_conditions": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": "Enter any medical conditions or allergies",
                }
            ),
            "emergency_contact_name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Emergency contact person name",
                    "required": True,
                }
            ),
            "emergency_contact_number": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "+1234567890",
                    "required": True,
                }
            ),
            "emergency_contact_relationship": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Relationship to student",
                }
            ),
            "previous_school": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Previous school name",
                }
            ),
            "transfer_certificate_number": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "TC number if transferred",
                }
            ),
            "status": forms.Select(attrs={"class": "form-control"}),
            "profile_picture": forms.FileInput(
                attrs={
                    "class": "form-control",
                    "accept": "image/*",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Set default admission date
        if not self.instance.pk:
            self.fields["admission_date"].initial = timezone.now().date()

        # Make certain fields required
        self.fields["first_name"].required = True
        self.fields["last_name"].required = True
        self.fields["admission_number"].required = True
        self.fields["admission_date"].required = True
        self.fields["emergency_contact_name"].required = True
        self.fields["emergency_contact_number"].required = True

        # Email is optional now
        self.fields["email"].required = False

    def clean_admission_number(self):
        admission_number = self.cleaned_data.get("admission_number", "").strip().upper()

        if not admission_number:
            raise ValidationError(_("Admission number is required."))

        # Validate format
        if not StudentUtils.validate_admission_number(admission_number):
            raise ValidationError(
                _("Invalid admission number format. Use format like STU-2024-ABC123")
            )

        # Check uniqueness
        if self.instance and self.instance.pk:
            # Updating existing student
            existing_students = Student.objects.filter(
                admission_number=admission_number
            ).exclude(id=self.instance.id)
        else:
            # Creating new student
            existing_students = Student.objects.filter(
                admission_number=admission_number
            )

        if existing_students.exists():
            raise ValidationError(_("This admission number is already in use."))

        return admission_number

    def clean_email(self):
        email = self.cleaned_data.get("email")
        if not email:  # Email is optional
            return email

        # Check uniqueness among students only (since parents can have same email)
        if self.instance and self.instance.pk:
            existing_students = Student.objects.filter(email=email).exclude(
                id=self.instance.id
            )
        else:
            existing_students = Student.objects.filter(email=email)

        if existing_students.exists():
            raise ValidationError(
                _("This email address is already used by another student.")
            )

        return email

    def clean_date_of_birth(self):
        date_of_birth = self.cleaned_data.get("date_of_birth")

        if date_of_birth:
            # Check if date is not in the future
            if date_of_birth > timezone.now().date():
                raise ValidationError(_("Date of birth cannot be in the future."))

            # Check if age is reasonable (between 3 and 25 years)
            age = timezone.now().date().year - date_of_birth.year
            if age < 3 or age > 25:
                raise ValidationError(_("Please enter a valid date of birth."))

        return date_of_birth

    def clean_admission_date(self):
        admission_date = self.cleaned_data.get("admission_date")

        if admission_date:
            # Check if admission date is not in the future
            if admission_date > timezone.now().date():
                raise ValidationError(_("Admission date cannot be in the future."))

        return admission_date

    def save(self, commit=True):
        student = super().save(commit=commit)

        if commit:
            # Ensure is_active is True for new students
            if not student.pk:
                student.is_active = True
                student.save()

        return student


class QuickStudentForm(forms.ModelForm):
    """Simplified form for quick student creation"""

    class Meta:
        model = Student
        fields = [
            "first_name",
            "last_name",
            "admission_number",
            "current_class",
            "emergency_contact_name",
            "emergency_contact_number",
        ]
        widgets = {
            "first_name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "First name",
                    "required": True,
                }
            ),
            "last_name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Last name",
                    "required": True,
                }
            ),
            "admission_number": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "STU-2024-ABC123",
                    "required": True,
                }
            ),
            "current_class": forms.Select(attrs={"class": "form-control"}),
            "emergency_contact_name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Emergency contact name",
                    "required": True,
                }
            ),
            "emergency_contact_number": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "+1234567890",
                    "required": True,
                }
            ),
        }

    def save(self):
        """Create student with minimal required fields"""
        from .services.student_service import StudentService

        student_data = {
            "first_name": self.cleaned_data["first_name"],
            "last_name": self.cleaned_data["last_name"],
            "admission_number": self.cleaned_data["admission_number"],
            "admission_date": timezone.now().date(),
            "current_class": self.cleaned_data.get("current_class"),
            "emergency_contact_name": self.cleaned_data["emergency_contact_name"],
            "emergency_contact_number": self.cleaned_data["emergency_contact_number"],
            "status": "Active",
            "is_active": True,
        }

        return StudentService.create_student(student_data)


class StudentPromotionForm(forms.Form):
    """Form for bulk student promotion"""

    students = forms.ModelMultipleChoiceField(
        queryset=Student.objects.none(),
        widget=forms.CheckboxSelectMultiple(attrs={"class": "form-check-input"}),
        required=True,
    )
    target_class = forms.ModelChoiceField(
        queryset=Class.objects.all(),
        widget=forms.Select(attrs={"class": "form-control"}),
        required=True,
    )
    send_notifications = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )

    def __init__(self, *args, **kwargs):
        current_class = kwargs.pop("current_class", None)
        super().__init__(*args, **kwargs)

        if current_class:
            self.fields["students"].queryset = Student.objects.filter(
                current_class=current_class, status="Active"
            )
        else:
            self.fields["students"].queryset = Student.objects.filter(status="Active")


class StudentSearchForm(forms.Form):
    """Form for searching students"""

    query = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Search by name, admission number, email, or roll number",
            }
        ),
    )
    class_filter = forms.ModelChoiceField(
        queryset=Class.objects.all(),
        required=False,
        empty_label="All Classes",
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    status_filter = forms.ChoiceField(
        choices=[("", "All Status")] + Student.STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    blood_group_filter = forms.ChoiceField(
        choices=[("", "All Blood Groups")] + Student.BLOOD_GROUP_CHOICES,
        required=False,
        widget=forms.Select(attrs={"class": "form-control"}),
    )


class ParentForm(BaseModelForm):
    # User fields
    first_name = forms.CharField(max_length=100, required=True)
    last_name = forms.CharField(max_length=100, required=True)
    email = forms.EmailField(required=True)
    phone_number = forms.CharField(max_length=20, required=True)
    date_of_birth = forms.DateField(
        required=False, widget=forms.DateInput(attrs={"type": "date"})
    )
    gender = forms.ChoiceField(
        choices=[("M", "Male"), ("F", "Female"), ("O", "Other")], required=False
    )
    password = forms.CharField(
        widget=forms.PasswordInput(),
        required=False,
        help_text="Leave blank to auto-generate",
    )
    confirm_password = forms.CharField(widget=forms.PasswordInput(), required=False)

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
            "work_address": forms.Textarea(attrs={"rows": 3}),
            "photo": forms.FileInput(attrs={"accept": "image/*"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Populate user fields if instance exists with a related user
        if self.instance and self.instance.pk and hasattr(self.instance, "user"):
            try:
                # Try to access the user, but handle the case where it might not exist
                user = self.instance.user
                self.fields["first_name"].initial = user.first_name
                self.fields["last_name"].initial = user.last_name
                self.fields["email"].initial = user.email
                self.fields["phone_number"].initial = user.phone_number
                self.fields["date_of_birth"].initial = user.date_of_birth
                if hasattr(user, "gender"):
                    self.fields["gender"].initial = user.gender
            except Parent.user.RelatedObjectDoesNotExist:
                # User doesn't exist yet, which is fine for new instances
                pass

    def clean_email(self):
        email = self.cleaned_data.get("email")
        if self.instance and self.instance.pk:
            try:
                existing_users = User.objects.filter(email=email).exclude(
                    id=self.instance.user.id
                )
            except Parent.user.RelatedObjectDoesNotExist:
                existing_users = User.objects.filter(email=email)
        else:
            existing_users = User.objects.filter(email=email)

        if existing_users.exists():
            raise ValidationError(_("This email address is already in use."))
        return email

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")

        if password and password != confirm_password:
            raise ValidationError(_("Passwords don't match."))

        return cleaned_data

    def save(self, commit=True):
        parent = super().save(commit=False)

        if commit:
            with transaction.atomic():
                # Handle user creation/update
                if parent.pk:
                    try:
                        user = parent.user
                    except Parent.user.RelatedObjectDoesNotExist:
                        # Create new user if it doesn't exist
                        email = self.cleaned_data["email"]
                        username = self.cleaned_data["email"]
                        user = User(username=username, email=email)
                else:
                    email = self.cleaned_data["email"]
                    try:
                        user = User.objects.get(email=email)
                    except User.DoesNotExist:
                        username = self.cleaned_data["email"]
                        user = User(username=username, email=email)

                # Update user fields
                for field in [
                    "first_name",
                    "last_name",
                    "email",
                    "phone_number",
                    "date_of_birth",
                ]:
                    if field in self.cleaned_data:
                        setattr(user, field, self.cleaned_data[field])

                if "gender" in self.cleaned_data and hasattr(user, "gender"):
                    user.gender = self.cleaned_data["gender"]

                # Set password if provided
                password = self.cleaned_data.get("password")
                if password:
                    user.set_password(password)
                elif not user.pk:
                    user.set_password(User.objects.make_random_password())

                user.save()
                parent.user = user
                parent.save()

                # Assign parent role
                from src.accounts.services import RoleService

                RoleService.assign_role_to_user(user, "Parent")

        return parent


class StudentParentRelationForm(BaseModelForm):
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
            "access_to_financial_info",
            "receive_sms",
            "receive_email",
            "receive_push_notifications",
        )

    def __init__(self, *args, **kwargs):
        student = kwargs.pop("student", None)
        parent = kwargs.pop("parent", None)
        super().__init__(*args, **kwargs)

        # Prefill and disable fields if provided
        if student:
            self.fields["student"].initial = student
            self.fields["student"].widget.attrs["readonly"] = True

        if parent:
            self.fields["parent"].initial = parent
            self.fields["parent"].widget.attrs["readonly"] = True

        # Use select_related to optimize queries
        self.fields["student"].queryset = Student.objects.with_related()
        self.fields["parent"].queryset = Parent.objects.with_related()

        # Add AJAX autocomplete
        self.fields["student"].widget.attrs.update(
            {"data-autocomplete-url": "/api/students/autocomplete/"}
        )
        self.fields["parent"].widget.attrs.update(
            {"data-autocomplete-url": "/api/parents/autocomplete/"}
        )


class StudentParentRelationForm(forms.ModelForm):
    """Form for managing student-parent relationships"""

    class Meta:
        model = StudentParentRelation
        fields = [
            "parent",
            "is_primary_contact",
            "can_pickup",
            "emergency_contact_priority",
            "financial_responsibility",
            "access_to_grades",
            "access_to_attendance",
            "access_to_financial_info",
            "receive_sms",
            "receive_email",
            "receive_push_notifications",
        ]
        widgets = {
            "parent": forms.Select(attrs={"class": "form-control"}),
            "emergency_contact_priority": forms.NumberInput(
                attrs={"class": "form-control", "min": 1, "max": 10}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only show active parents
        self.fields["parent"].queryset = Parent.objects.filter(
            user__is_active=True
        ).select_related("user")


class BulkStudentImportForm(forms.Form):
    """Form for bulk importing students from CSV"""

    csv_file = forms.FileField(
        widget=forms.FileInput(
            attrs={
                "class": "form-control",
                "accept": ".csv",
            }
        ),
        help_text="Upload a CSV file with student data",
    )
    default_class = forms.ModelChoiceField(
        queryset=Class.objects.all(),
        required=False,
        widget=forms.Select(attrs={"class": "form-control"}),
        help_text="Default class for students without class specified",
    )
    send_welcome_emails = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
        help_text="Send welcome emails to students with email addresses",
    )

    def clean_csv_file(self):
        csv_file = self.cleaned_data.get("csv_file")

        if csv_file:
            if not csv_file.name.endswith(".csv"):
                raise ValidationError("File must be a CSV file")

            if csv_file.size > 5 * 1024 * 1024:  # 5MB limit
                raise ValidationError("File size must be less than 5MB")

        return csv_file


class ParentBulkImportForm(forms.Form):
    csv_file = forms.FileField(
        widget=forms.FileInput(attrs={"accept": ".csv"}),
        help_text="CSV file containing parent data. Download template below.",
    )
    send_email_notifications = forms.BooleanField(
        required=False,
        initial=True,
        help_text="Send email notifications to created parents",
    )
    update_existing = forms.BooleanField(
        required=False,
        initial=False,
        help_text="Update existing parents if email matches",
    )

    def clean_csv_file(self):
        csv_file = self.cleaned_data.get("csv_file")

        if not csv_file:
            return None

        if not csv_file.name.endswith(".csv"):
            raise ValidationError(_("File must be a CSV file."))

        if csv_file.size > 5 * 1024 * 1024:  # 5MB limit
            raise ValidationError(_("File size must be less than 5MB."))

        try:
            decoded_file = csv_file.read().decode("utf-8")
            csv_file.seek(0)

            csv_data = csv.DictReader(io.StringIO(decoded_file))

            if not csv_data.fieldnames:
                raise ValidationError(_("CSV file is empty or improperly formatted."))

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
