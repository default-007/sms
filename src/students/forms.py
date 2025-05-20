from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.db import transaction
import csv
import io

from .models import Student, Parent, StudentParentRelation
from src.courses.models import Class, AcademicYear

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


class StudentForm(BaseModelForm):
    # User fields
    first_name = forms.CharField(
        max_length=100, required=True, help_text="Student's first name"
    )
    last_name = forms.CharField(
        max_length=100, required=True, help_text="Student's last name"
    )
    email = forms.EmailField(required=True, help_text="Student's email address")
    phone_number = forms.CharField(
        max_length=20, required=False, help_text="Student's phone number"
    )
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

        # Make required fields more obvious
        required_fields = [
            "first_name",
            "last_name",
            "email",
            "admission_number",
            "admission_date",
            "emergency_contact_name",
            "emergency_contact_number",
        ]
        for field_name in required_fields:
            if field_name in self.fields:
                self.fields[field_name].required = True
                self.fields[field_name].widget.attrs["required"] = True

        # Populate user fields if instance exists with a related user
        if (
            self.instance
            and self.instance.pk
            and hasattr(self.instance, "user")
            and self.instance.user
        ):
            self.fields["first_name"].initial = self.instance.user.first_name
            self.fields["last_name"].initial = self.instance.user.last_name
            self.fields["email"].initial = self.instance.user.email
            self.fields["phone_number"].initial = self.instance.user.phone_number
            self.fields["date_of_birth"].initial = self.instance.user.date_of_birth
            if hasattr(self.instance.user, "gender"):
                self.fields["gender"].initial = self.instance.user.gender
            self.fields["address_line"].initial = self.instance.address

        # Filter classes to current academic year
        current_year = AcademicYear.objects.filter(is_current=True).first()
        if current_year:
            self.fields["current_class"].queryset = Class.objects.filter(
                academic_year=current_year
            ).select_related("grade", "section")

        # Add AJAX autocomplete for classes
        self.fields["current_class"].widget.attrs.update(
            {"data-autocomplete-url": "/api/courses/classes/autocomplete/"}
        )

    def clean_email(self):
        email = self.cleaned_data.get("email")
        if self.instance and self.instance.pk:
            existing_users = User.objects.filter(email=email).exclude(
                id=self.instance.user.id
            )
        else:
            existing_users = User.objects.filter(email=email)

        if existing_users.exists():
            raise ValidationError(_("This email address is already in use."))
        return email

    def clean_admission_number(self):
        admission_number = self.cleaned_data.get("admission_number")
        if self.instance and self.instance.pk:
            existing_students = Student.objects.filter(
                admission_number=admission_number
            ).exclude(id=self.instance.id)
        else:
            existing_students = Student.objects.filter(
                admission_number=admission_number
            )

        if existing_students.exists():
            raise ValidationError(_("This admission number is already in use."))
        return admission_number

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")

        if password and password != confirm_password:
            raise ValidationError(_("Passwords don't match."))

        return cleaned_data

    def save(self, commit=True):
        student = super().save(commit=False)

        if commit:
            with transaction.atomic():
                # Handle user creation/update
                if student.pk:
                    user = student.user
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
                    # Generate random password for new users
                    user.set_password(User.objects.make_random_password())

                user.save()
                student.user = user
                student.address = self.cleaned_data.get("address_line", "")
                student.save()

                # Assign student role
                from src.accounts.services import RoleService

                RoleService.assign_role_to_user(user, "Student")

        return student


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

        # Populate user fields if instance exists
        if self.instance and self.instance.pk:
            self.fields["first_name"].initial = self.instance.user.first_name
            self.fields["last_name"].initial = self.instance.user.last_name
            self.fields["email"].initial = self.instance.user.email
            self.fields["phone_number"].initial = self.instance.user.phone_number
            self.fields["date_of_birth"].initial = self.instance.user.date_of_birth
            if hasattr(self.instance.user, "gender"):
                self.fields["gender"].initial = self.instance.user.gender

    def clean_email(self):
        email = self.cleaned_data.get("email")
        if self.instance and self.instance.pk:
            existing_users = User.objects.filter(email=email).exclude(
                id=self.instance.user.id
            )
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
                    user = parent.user
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
    csv_file = forms.FileField(
        widget=forms.FileInput(attrs={"accept": ".csv"}),
        help_text="CSV file containing student data. Download template below.",
    )
    send_email_notifications = forms.BooleanField(
        required=False,
        initial=True,
        help_text="Send email notifications to created students and parents",
    )
    update_existing = forms.BooleanField(
        required=False,
        initial=False,
        help_text="Update existing students if admission number matches",
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

            required_columns = ["first_name", "last_name", "email", "admission_number"]
            missing_columns = [
                col for col in required_columns if col not in csv_data.fieldnames
            ]

            if missing_columns:
                raise ValidationError(
                    _(f"Missing required columns: {', '.join(missing_columns)}")
                )

        except UnicodeDecodeError:
            raise ValidationError(
                _("Unable to decode file. Please ensure it's UTF-8 encoded.")
            )
        except Exception as e:
            raise ValidationError(_(f"Error parsing CSV file: {str(e)}"))

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


class QuickStudentAddForm(forms.Form):
    """Simplified form for quick student addition"""

    first_name = forms.CharField(max_length=100)
    last_name = forms.CharField(max_length=100)
    email = forms.EmailField()
    admission_number = forms.CharField(max_length=20)
    current_class = forms.ModelChoiceField(
        queryset=Class.objects.none(), required=False
    )
    emergency_contact_name = forms.CharField(max_length=100)
    emergency_contact_number = forms.CharField(max_length=20)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Add CSS classes
        for field in self.fields.values():
            field.widget.attrs.update({"class": "form-control"})

        # Filter classes to current academic year
        current_year = AcademicYear.objects.filter(is_current=True).first()
        if current_year:
            self.fields["current_class"].queryset = Class.objects.filter(
                academic_year=current_year
            ).select_related("grade", "section")

    def save(self):
        """Create student with minimal required fields"""
        from .services.student_service import StudentService

        user_data = {
            "first_name": self.cleaned_data["first_name"],
            "last_name": self.cleaned_data["last_name"],
            "email": self.cleaned_data["email"],
            "username": self.cleaned_data["email"],
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
