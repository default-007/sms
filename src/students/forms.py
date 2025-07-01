import csv
from datetime import timezone
import io

from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.translation import gettext_lazy as _

from src.academics.models import AcademicYear, Class


from .models import Parent, Student, StudentParentRelation

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


# students/forms.py - Updated StudentForm with optional email/phone


class StudentForm(BaseModelForm):
    # User fields
    first_name = forms.CharField(
        max_length=100, required=True, help_text="Student's first name"
    )
    last_name = forms.CharField(
        max_length=100, required=True, help_text="Student's last name"
    )
    email = forms.EmailField(
        required=False, help_text="Student's email address (optional)"
    )  # CHANGED: Made optional
    phone_number = forms.CharField(
        max_length=20, required=False, help_text="Student's phone number (optional)"
    )  # CHANGED: Made optional
    date_of_birth = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
        help_text="Student's date of birth",
    )
    gender = forms.ChoiceField(
        choices=[("M", "Male"), ("F", "Female"), ("O", "Other")],
        required=False,
        help_text="Student's gender",
    )
    password = forms.CharField(
        widget=forms.PasswordInput(),
        required=False,
        help_text="Leave blank to auto-generate",
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(), required=False, help_text="Confirm the password"
    )

    # Address fields for better UX
    address_line = forms.CharField(
        max_length=200, required=False, help_text="Street address"
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
            "admission_date": forms.DateInput(attrs={"type": "date"}),
            "medical_conditions": forms.Textarea(attrs={"rows": 3}),
            "photo": forms.FileInput(attrs={"accept": "image/*"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # UPDATED: Simplified required fields list - removed email
        required_fields = [
            "first_name",
            "last_name",
            "admission_number",
            "admission_date",
            "emergency_contact_name",
            "emergency_contact_number",
        ]

        for field_name in required_fields:
            if field_name in self.fields:
                self.fields[field_name].required = True
                # Add visual indicator for required fields
                current_attrs = self.fields[field_name].widget.attrs
                current_attrs.update({"required": True})

        # Optional fields styling
        optional_fields = ["email", "phone_number", "date_of_birth", "gender"]
        for field_name in optional_fields:
            if field_name in self.fields:
                self.fields[field_name].required = False
                # Update help text to indicate optional
                if self.fields[field_name].help_text:
                    if "(optional)" not in self.fields[field_name].help_text:
                        self.fields[field_name].help_text += " (optional)"

    def clean_email(self):
        """Validate email only if provided"""
        email = self.cleaned_data.get("email", "").strip()

        if email:  # Only validate if email is provided
            # Check for existing email
            existing_user = User.objects.filter(email__iexact=email)
            if self.instance and self.instance.user:
                existing_user = existing_user.exclude(pk=self.instance.user.pk)

            if existing_user.exists():
                raise ValidationError(_("This email address is already in use."))

            return email.lower()

        return email  # Return empty string if not provided

    def clean_phone_number(self):
        """Validate phone number only if provided"""
        phone = self.cleaned_data.get("phone_number", "").strip()

        if phone:  # Only validate if phone is provided
            # Basic phone number validation
            import re

            clean_phone = re.sub(r"[^\d+]", "", phone)
            if not clean_phone.startswith("+"):
                clean_phone = "+" + clean_phone

            # Check for existing phone
            existing_user = User.objects.filter(phone_number=clean_phone)
            if self.instance and self.instance.user:
                existing_user = existing_user.exclude(pk=self.instance.user.pk)

            if existing_user.exists():
                raise ValidationError(_("This phone number is already in use."))

            return clean_phone

        return phone  # Return empty string if not provided

    def clean_admission_number(self):
        """Validate admission number uniqueness"""
        admission_number = self.cleaned_data["admission_number"]

        # Check if admission number exists as username
        existing_user = User.objects.filter(username=admission_number)
        if self.instance and self.instance.user:
            existing_user = existing_user.exclude(pk=self.instance.user.pk)

        if existing_user.exists():
            raise ValidationError(_("This admission number is already in use."))

        # Check if admission number exists for another student
        existing_student = Student.objects.filter(admission_number=admission_number)
        if self.instance.pk:
            existing_student = existing_student.exclude(pk=self.instance.pk)

        if existing_student.exists():
            raise ValidationError(
                _("This admission number is already assigned to another student.")
            )

        return admission_number

    def save(self, commit=True):
        """Enhanced save method for optional email/phone"""
        from .services.student_service import StudentService

        if not self.instance.pk:
            # Creating new student
            user_data = {
                "first_name": self.cleaned_data["first_name"],
                "last_name": self.cleaned_data["last_name"],
                "email": self.cleaned_data.get("email", ""),  # Optional
                "phone_number": self.cleaned_data.get("phone_number", ""),  # Optional
                "username": self.cleaned_data["admission_number"],
            }

            student_data = {
                k: v
                for k, v in self.cleaned_data.items()
                if k in [f.name for f in Student._meta.fields]
            }
            student_data["address"] = self.cleaned_data.get("address_line", "")

            # Create password if provided
            password = self.cleaned_data.get("password")
            if password:
                user_data["password"] = password

            return StudentService.create_student(student_data, user_data)
        else:
            # Updating existing student
            student = super().save(commit=False)

            if student.user:
                # Update user fields
                student.user.first_name = self.cleaned_data["first_name"]
                student.user.last_name = self.cleaned_data["last_name"]

                # Only update email/phone if provided
                email = self.cleaned_data.get("email", "").strip()
                if email:
                    student.user.email = email

                phone = self.cleaned_data.get("phone_number", "").strip()
                if phone:
                    student.user.phone_number = phone

                student.user.save()

            # Update address
            student.address = self.cleaned_data.get("address_line", "")

            if commit:
                student.save()

            return student


# Updated QuickStudentAddForm for quick student creation
class QuickStudentAddForm(forms.Form):
    """Simplified form for quick student addition"""

    first_name = forms.CharField(
        max_length=100,
        required=True,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "First Name"}
        ),
    )
    last_name = forms.CharField(
        max_length=100,
        required=True,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Last Name"}
        ),
    )
    admission_number = forms.CharField(
        max_length=20,
        required=True,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Admission Number"}
        ),
    )
    email = forms.EmailField(
        required=False,  # CHANGED: Made optional
        widget=forms.EmailInput(
            attrs={"class": "form-control", "placeholder": "Email (optional)"}
        ),
        help_text="Optional - for login and communication",
    )
    phone_number = forms.CharField(
        max_length=20,
        required=False,  # CHANGED: Made optional
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Phone Number (optional)"}
        ),
        help_text="Optional - for contact purposes",
    )
    current_class = forms.ModelChoiceField(
        queryset=None,
        required=False,
        empty_label="Select Class (optional)",
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    emergency_contact_name = forms.CharField(
        max_length=100,
        required=True,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Emergency Contact Name"}
        ),
    )
    emergency_contact_number = forms.CharField(
        max_length=20,
        required=True,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Emergency Contact Number"}
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Load available classes
        try:
            from academics.models import Class, AcademicYear

            current_year = AcademicYear.objects.filter(is_current=True).first()
            if current_year:
                self.fields["current_class"].queryset = (
                    Class.objects.filter(academic_year=current_year, is_active=True)
                    .select_related("grade__section")
                    .order_by(
                        "grade__section__order_sequence",
                        "grade__order_sequence",
                        "name",
                    )
                )
        except:
            self.fields["current_class"].widget = forms.HiddenInput()

    def clean_email(self):
        """Validate email only if provided"""
        email = self.cleaned_data.get("email", "").strip()

        if email:
            if User.objects.filter(email__iexact=email).exists():
                raise ValidationError(_("This email address is already in use."))
            return email.lower()

        return email

    def clean_phone_number(self):
        """Validate phone number only if provided"""
        phone = self.cleaned_data.get("phone_number", "").strip()

        if phone:
            import re

            clean_phone = re.sub(r"[^\d+]", "", phone)
            if not clean_phone.startswith("+"):
                clean_phone = "+" + clean_phone

            if User.objects.filter(phone_number=clean_phone).exists():
                raise ValidationError(_("This phone number is already in use."))

            return clean_phone

        return phone

    def clean_admission_number(self):
        """Validate admission number uniqueness"""
        admission_number = self.cleaned_data["admission_number"]

        if User.objects.filter(username=admission_number).exists():
            raise ValidationError(_("This admission number is already in use."))

        if Student.objects.filter(admission_number=admission_number).exists():
            raise ValidationError(
                _("This admission number is already assigned to another student.")
            )

        return admission_number

    def save(self):
        """Create student with minimal required fields"""
        from .services.student_service import StudentService

        user_data = {
            "first_name": self.cleaned_data["first_name"],
            "last_name": self.cleaned_data["last_name"],
            "email": self.cleaned_data.get("email", ""),  # Optional
            "phone_number": self.cleaned_data.get("phone_number", ""),  # Optional
            "username": self.cleaned_data["admission_number"],
        }

        student_data = {
            "admission_number": self.cleaned_data["admission_number"],
            "admission_date": timezone.now().date(),
            "current_class": self.cleaned_data.get("current_class"),
            "emergency_contact_name": self.cleaned_data["emergency_contact_name"],
            "emergency_contact_number": self.cleaned_data["emergency_contact_number"],
            "status": "Active",
        }

        return StudentService.create_student(student_data, user_data)


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


class StudentBulkImportForm(forms.Form):
    # Class selection for targeted imports
    target_class = forms.ModelChoiceField(
        queryset=Class.objects.none(),
        required=False,
        empty_label="Select a specific class (optional)",
        widget=forms.Select(attrs={"class": "form-select"}),
        help_text="Optional: Import all students to this specific class",
    )

    academic_year = forms.ModelChoiceField(
        queryset=AcademicYear.objects.filter(is_current=True),
        required=False,
        empty_label="Current Academic Year",
        widget=forms.Select(attrs={"class": "form-select"}),
        help_text="Academic year for the import",
    )

    csv_file = forms.FileField(
        widget=forms.FileInput(attrs={"accept": ".csv", "class": "form-control"}),
        help_text="CSV file containing student data. Download template below.",
    )

    # Simplified notification options
    send_email_notifications = forms.BooleanField(
        required=False,
        initial=False,  # Default to False since email is optional
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
        help_text="Send welcome emails (only to students with email addresses)",
    )

    update_existing = forms.BooleanField(
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
        help_text="Update existing students if admission number matches",
    )

    # New option for handling missing class assignments
    auto_assign_class = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
        help_text="Automatically assign students without class_id to the selected target class",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Load active classes for current academic year
        try:
            current_year = AcademicYear.objects.filter(is_current=True).first()
            if current_year:
                self.fields["target_class"].queryset = (
                    Class.objects.filter(academic_year=current_year, is_active=True)
                    .select_related("grade__section")
                    .order_by(
                        "grade__section__order_sequence",
                        "grade__order_sequence",
                        "name",
                    )
                )
                self.fields["academic_year"].initial = current_year
        except:
            pass

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

            # Updated required columns - removed email requirement
            required_columns = ["first_name", "last_name", "admission_number"]
            missing_columns = [
                col for col in required_columns if col not in csv_data.fieldnames
            ]

            if missing_columns:
                raise ValidationError(
                    _(f"Missing required columns: {', '.join(missing_columns)}")
                )

            # Validate data rows
            row_count = 0
            for row_num, row in enumerate(csv_data, start=2):
                row_count += 1

                # Check required fields have values
                for field in required_columns:
                    if not row.get(field, "").strip():
                        raise ValidationError(
                            _(
                                f"Row {row_num}: Missing value for required field '{field}'"
                            )
                        )

                # Validate admission number format (customize as needed)
                admission_number = row.get("admission_number", "").strip()
                if not admission_number:
                    raise ValidationError(
                        _(f"Row {row_num}: Admission number is required")
                    )

                # Optional: Validate admission number format
                if len(admission_number) < 3:
                    raise ValidationError(
                        _(
                            f"Row {row_num}: Admission number must be at least 3 characters long"
                        )
                    )

            if row_count == 0:
                raise ValidationError(_("CSV file contains no data rows."))

        except UnicodeDecodeError:
            raise ValidationError(
                _("Unable to decode file. Please ensure it's UTF-8 encoded.")
            )
        except Exception as e:
            if isinstance(e, ValidationError):
                raise
            raise ValidationError(_(f"Error parsing CSV file: {str(e)}"))

        return csv_file

    def clean(self):
        cleaned_data = super().clean()
        target_class = cleaned_data.get("target_class")
        auto_assign_class = cleaned_data.get("auto_assign_class")

        # If auto_assign_class is enabled, target_class should be selected
        if auto_assign_class and not target_class:
            raise ValidationError(
                "Please select a target class when auto-assign is enabled, or disable auto-assign to use class_id from CSV."
            )

        return cleaned_data


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


class StudentPromotionForm(forms.Form):
    source_class = forms.ModelChoiceField(
        queryset=Class.objects.none(),
        required=True,
        label="Current Class",
        help_text="Select the class to promote students from",
    )

    target_class = forms.ModelChoiceField(
        queryset=Class.objects.none(),
        required=True,
        label="Target Class",
        help_text="Select the class to promote students to",
    )

    students = forms.ModelMultipleChoiceField(
        queryset=Student.objects.none(),
        widget=forms.CheckboxSelectMultiple(),
        required=True,
        label="Students to Promote",
        help_text="Select students to promote",
    )

    send_notifications = forms.BooleanField(
        required=False,
        initial=True,
        help_text="Send notification emails to students and parents",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Add CSS classes
        for field_name, field in self.fields.items():
            if field_name != "students":
                field.widget.attrs.update({"class": "form-control"})

        # Get current and next academic year
        current_year = AcademicYear.objects.filter(is_current=True).first()

        if current_year:
            self.fields["source_class"].queryset = Class.objects.filter(
                academic_year=current_year
            ).select_related("grade", "section")

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
                self.fields["target_class"].queryset = Class.objects.filter(
                    academic_year=current_year
                ).select_related("grade", "section")

        # Add AJAX handling for student population
        if "source_class" in self.data:
            try:
                source_class_id = int(self.data.get("source_class"))
                self.fields["students"].queryset = Student.objects.filter(
                    current_class_id=source_class_id, status="Active"
                ).with_related()
            except (ValueError, TypeError):
                pass

    def clean(self):
        cleaned_data = super().clean()
        source_class = cleaned_data.get("source_class")
        target_class = cleaned_data.get("target_class")

        if source_class and target_class and source_class == target_class:
            raise ValidationError(_("Source and target classes cannot be the same."))

        return cleaned_data
