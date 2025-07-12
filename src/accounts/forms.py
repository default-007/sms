from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import (
    AuthenticationForm,
    PasswordChangeForm,
    PasswordResetForm,
    SetPasswordForm,
    UserCreationForm,
)
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.utils.translation import gettext_lazy as _

from .constants import PERMISSION_SCOPES
from .models import UserProfile, UserRole, UserRoleAssignment
from .utils import validate_password_strength

User = get_user_model()


class CustomAuthenticationForm(AuthenticationForm):
    """Custom login form with additional styling and validation."""

    username = forms.CharField(
        label=_("Username or Email"),
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Username or Email",
                "autofocus": True,
                "autocomplete": "username",
            }
        ),
    )
    password = forms.CharField(
        label=_("Password"),
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control",
                "placeholder": "Password",
                "autocomplete": "current-password",
            }
        ),
    )
    remember_me = forms.BooleanField(
        label=_("Remember me"),
        required=False,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )

    error_messages = {
        "invalid_login": _(
            "Please enter a correct %(username)s and password. Note that both "
            "fields may be case-sensitive."
        ),
        "inactive": _("This account is inactive."),
    }

    def clean_username(self):
        """Allow login with either username or email."""
        username = self.cleaned_data.get("username")
        if "@" in username:
            # If it looks like an email, validate it
            try:
                validate_email(username)
            except ValidationError:
                raise forms.ValidationError(_("Please enter a valid email address."))
        return username


class CustomUserCreationForm(UserCreationForm):
    """Custom user creation form with additional fields."""

    email = forms.EmailField(
        label=_("Email"),
        widget=forms.EmailInput(
            attrs={"class": "form-control", "placeholder": "Email"}
        ),
        required=True,
    )
    first_name = forms.CharField(
        label=_("First Name"),
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "First Name"}
        ),
        required=True,
        max_length=150,
    )
    last_name = forms.CharField(
        label=_("Last Name"),
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Last Name"}
        ),
        required=True,
        max_length=150,
    )
    phone_number = forms.CharField(
        label=_("Phone Number"),
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Phone Number"}
        ),
        required=False,
        max_length=20,
    )
    address = forms.CharField(
        label=_("Address"),
        widget=forms.Textarea(
            attrs={"class": "form-control", "placeholder": "Address", "rows": 3}
        ),
        required=False,
    )
    date_of_birth = forms.DateField(
        label=_("Date of Birth"),
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
        required=False,
    )
    gender = forms.ChoiceField(
        label=_("Gender"),
        choices=[("", "-- Select Gender --")] + list(User.GENDER_CHOICES),
        widget=forms.Select(attrs={"class": "form-control"}),
        required=False,
    )
    profile_picture = forms.ImageField(
        label=_("Profile Picture"),
        widget=forms.FileInput(attrs={"class": "form-control"}),
        required=False,
    )
    roles = forms.ModelMultipleChoiceField(
        queryset=UserRole.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label=_("User Roles"),
    )
    send_welcome_email = forms.BooleanField(
        label=_("Send welcome email"),
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )

    class Meta:
        model = User
        fields = (
            "username",
            "email",
            "first_name",
            "last_name",
            "phone_number",
            "address",
            "date_of_birth",
            "gender",
            "profile_picture",
            "password1",
            "password2",
        )
        widgets = {
            "username": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Username"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only show non-system roles for assignment
        self.fields["roles"].queryset = UserRole.objects.filter(is_system_role=False)

    def clean_email(self):
        email = self.cleaned_data.get("email")
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError(_("This email address is already in use."))
        return email

    def clean_username(self):
        username = self.cleaned_data.get("username")
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError(_("This username is already taken."))
        # Add custom username validation
        if len(username) < 3:
            raise forms.ValidationError(
                _("Username must be at least 3 characters long.")
            )
        return username

    def clean_password1(self):
        password = self.cleaned_data.get("password1")
        if password:
            validation = validate_password_strength(password)
            if not validation["is_valid"]:
                raise forms.ValidationError(validation["feedback"])
        return password

    def clean_profile_picture(self):
        picture = self.cleaned_data.get("profile_picture")
        if picture:
            # Validate file size (2MB max)
            if picture.size > 2 * 1024 * 1024:
                raise forms.ValidationError(_("Profile picture must be less than 2MB."))

            # Validate file type
            allowed_types = ["image/jpeg", "image/png", "image/jpg"]
            if picture.content_type not in allowed_types:
                raise forms.ValidationError(_("Only JPEG and PNG images are allowed."))

        return picture


class UserUpdateForm(forms.ModelForm):
    """Form for updating existing users."""

    roles = forms.ModelMultipleChoiceField(
        queryset=UserRole.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label=_("User Roles"),
    )

    class Meta:
        model = User
        fields = (
            "first_name",
            "last_name",
            "email",
            "phone_number",
            "address",
            "date_of_birth",
            "gender",
            "profile_picture",
            "is_active",
            "requires_password_change",
        )
        widgets = {
            "first_name": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "First Name"}
            ),
            "last_name": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Last Name"}
            ),
            "email": forms.EmailInput(
                attrs={"class": "form-control", "placeholder": "Email"}
            ),
            "phone_number": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Phone Number"}
            ),
            "address": forms.Textarea(
                attrs={"class": "form-control", "placeholder": "Address", "rows": 3}
            ),
            "date_of_birth": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}
            ),
            "gender": forms.Select(attrs={"class": "form-control"}),
            "profile_picture": forms.FileInput(attrs={"class": "form-control"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "requires_password_change": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            # Pre-select current roles
            self.fields["roles"].initial = self.instance.role_assignments.filter(
                is_active=True
            ).values_list("role", flat=True)

    def clean_email(self):
        email = self.cleaned_data.get("email")
        if User.objects.filter(email=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError(_("This email address is already in use."))
        return email


class UserProfileForm(forms.ModelForm):
    """Form for updating user profile information."""

    class Meta:
        model = User
        fields = (
            "first_name",
            "last_name",
            "email",
            "phone_number",
            "address",
            "date_of_birth",
            "gender",
            "profile_picture",
        )
        widgets = {
            "first_name": forms.TextInput(attrs={"class": "form-control"}),
            "last_name": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "phone_number": forms.TextInput(attrs={"class": "form-control"}),
            "address": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "date_of_birth": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}
            ),
            "gender": forms.Select(attrs={"class": "form-control"}),
            "profile_picture": forms.FileInput(attrs={"class": "form-control"}),
        }

    def clean_email(self):
        email = self.cleaned_data.get("email")
        if User.objects.filter(email=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError(_("This email address is already in use."))
        return email

    def clean_profile_picture(self):
        picture = self.cleaned_data.get("profile_picture")
        if picture:
            # Validate file size (2MB max)
            if picture.size > 2 * 1024 * 1024:
                raise forms.ValidationError(_("Profile picture must be less than 2MB."))

            # Validate file type
            allowed_types = ["image/jpeg", "image/png", "image/jpg"]
            if picture.content_type not in allowed_types:
                raise forms.ValidationError(_("Only JPEG and PNG images are allowed."))

        return picture


class UserProfileExtendedForm(forms.ModelForm):
    """Extended profile form including UserProfile fields."""

    # User fields
    first_name = forms.CharField(
        max_length=150, widget=forms.TextInput(attrs={"class": "form-control"})
    )
    last_name = forms.CharField(
        max_length=150, widget=forms.TextInput(attrs={"class": "form-control"})
    )
    email = forms.EmailField(widget=forms.EmailInput(attrs={"class": "form-control"}))
    phone_number = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    address = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3}),
    )
    date_of_birth = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
    )
    gender = forms.ChoiceField(
        choices=[("", "-- Select Gender --")] + list(User.GENDER_CHOICES),
        required=False,
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    profile_picture = forms.ImageField(
        required=False, widget=forms.FileInput(attrs={"class": "form-control"})
    )

    class Meta:
        model = UserProfile
        fields = [
            "bio",
            "website",
            "location",
            "language",
            "timezone",
            "email_notifications",
            "sms_notifications",
            "linkedin_url",
            "twitter_url",
            "facebook_url",
        ]
        widgets = {
            "bio": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 4,
                    "placeholder": "Tell us about yourself...",
                }
            ),
            "website": forms.URLInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "https://yourwebsite.com",
                }
            ),
            "location": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "City, Country"}
            ),
            "language": forms.Select(attrs={"class": "form-control"}),
            "timezone": forms.Select(attrs={"class": "form-control"}),
            "email_notifications": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),
            "sms_notifications": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),
            "linkedin_url": forms.URLInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "https://linkedin.com/in/yourprofile",
                }
            ),
            "twitter_url": forms.URLInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "https://twitter.com/yourusername",
                }
            ),
            "facebook_url": forms.URLInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "https://facebook.com/yourprofile",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

        if self.user:
            # Populate user fields
            self.fields["first_name"].initial = self.user.first_name
            self.fields["last_name"].initial = self.user.last_name
            self.fields["email"].initial = self.user.email
            self.fields["phone_number"].initial = self.user.phone_number
            self.fields["address"].initial = self.user.address
            self.fields["date_of_birth"].initial = self.user.date_of_birth
            self.fields["gender"].initial = self.user.gender
            self.fields["profile_picture"].initial = self.user.profile_picture

    def save(self, commit=True):
        profile = super().save(commit=False)

        if self.user:
            # Update user fields
            self.user.first_name = self.cleaned_data["first_name"]
            self.user.last_name = self.cleaned_data["last_name"]
            self.user.email = self.cleaned_data["email"]
            self.user.phone_number = self.cleaned_data["phone_number"]
            self.user.address = self.cleaned_data["address"]
            self.user.date_of_birth = self.cleaned_data["date_of_birth"]
            self.user.gender = self.cleaned_data["gender"]

            if (
                "profile_picture" in self.cleaned_data
                and self.cleaned_data["profile_picture"]
            ):
                self.user.profile_picture = self.cleaned_data["profile_picture"]

            if commit:
                self.user.save()

            profile.user = self.user

        if commit:
            profile.save()

        return profile


class CustomPasswordChangeForm(PasswordChangeForm):
    """Custom password change form with improved styling and validation."""

    old_password = forms.CharField(
        label=_("Current Password"),
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control",
                "placeholder": "Current Password",
                "autocomplete": "current-password",
            }
        ),
    )
    new_password1 = forms.CharField(
        label=_("New Password"),
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control",
                "placeholder": "New Password",
                "autocomplete": "new-password",
            }
        ),
    )
    new_password2 = forms.CharField(
        label=_("Confirm New Password"),
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control",
                "placeholder": "Confirm New Password",
                "autocomplete": "new-password",
            }
        ),
    )

    def clean_new_password1(self):
        password = self.cleaned_data.get("new_password1")
        if password:
            validation = validate_password_strength(password)
            if not validation["is_valid"]:
                raise forms.ValidationError(validation["feedback"])
        return password


class CustomPasswordResetForm(PasswordResetForm):
    """Custom password reset form with improved styling."""

    email = forms.EmailField(
        label=_("Email"),
        widget=forms.EmailInput(
            attrs={
                "class": "form-control",
                "placeholder": "Email",
                "autocomplete": "email",
            }
        ),
        max_length=254,
    )

    def clean_email(self):
        email = self.cleaned_data.get("email")
        if not User.objects.filter(email=email, is_active=True).exists():
            raise forms.ValidationError(
                _("No active account with this email address exists.")
            )
        return email


class CustomSetPasswordForm(SetPasswordForm):
    """Custom set password form with improved styling."""

    new_password1 = forms.CharField(
        label=_("New Password"),
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control",
                "placeholder": "New Password",
                "autocomplete": "new-password",
            }
        ),
    )
    new_password2 = forms.CharField(
        label=_("Confirm New Password"),
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control",
                "placeholder": "Confirm New Password",
                "autocomplete": "new-password",
            }
        ),
    )

    def clean_new_password1(self):
        password = self.cleaned_data.get("new_password1")
        if password:
            validation = validate_password_strength(password)
            if not validation["is_valid"]:
                raise forms.ValidationError(validation["feedback"])
        return password


class UserRoleForm(forms.ModelForm):
    """Form for creating and updating user roles."""

    class Meta:
        model = UserRole
        fields = ("name", "description")
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Dynamically create permission fields
        for resource, actions in PERMISSION_SCOPES.items():
            field_name = f"{resource}_permissions"
            choices = [
                (action, description.title()) for action, description in actions.items()
            ]

            self.fields[field_name] = forms.MultipleChoiceField(
                choices=choices,
                widget=forms.CheckboxSelectMultiple(
                    attrs={"class": "form-check-input"}
                ),
                required=False,
                label=resource.title().replace("_", " ") + " Management",
            )

            # Set initial values if editing existing role
            if self.instance and self.instance.pk and self.instance.permissions:
                initial_perms = self.instance.permissions.get(resource, [])
                self.fields[field_name].initial = initial_perms

    def clean_name(self):
        name = self.cleaned_data.get("name")
        # Check if it's a system role and prevent editing
        if self.instance and self.instance.pk and self.instance.is_system_role:
            if name != self.instance.name:
                raise forms.ValidationError(
                    _("Cannot change the name of a system role.")
                )

        # Check for uniqueness
        if (
            UserRole.objects.filter(name=name)
            .exclude(pk=self.instance.pk if self.instance else None)
            .exists()
        ):
            raise forms.ValidationError(_("A role with this name already exists."))
        return name

    def save(self, commit=True):
        role = super().save(commit=False)

        # Build permissions from form data
        permissions = {}
        for resource in PERMISSION_SCOPES.keys():
            field_name = f"{resource}_permissions"
            if field_name in self.cleaned_data:
                selected_perms = self.cleaned_data[field_name]
                if selected_perms:
                    permissions[resource] = selected_perms

        role.permissions = permissions

        if commit:
            role.save()
        return role


class BulkUserImportForm(forms.Form):
    """Form for bulk user import via CSV."""

    csv_file = forms.FileField(
        label=_("CSV File"),
        widget=forms.FileInput(attrs={"class": "form-control", "accept": ".csv"}),
        help_text=_(
            "Upload a CSV file with user data. Required columns: username, email, first_name, last_name"
        ),
    )
    default_password = forms.CharField(
        label=_("Default Password"),
        widget=forms.PasswordInput(attrs={"class": "form-control"}),
        initial="changeme123",
        help_text=_(
            "Default password for all imported users (they will be required to change it)"
        ),
    )
    default_roles = forms.ModelMultipleChoiceField(
        queryset=UserRole.objects.filter(is_system_role=False),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label=_("Default Roles"),
        help_text=_("Roles to assign to all imported users"),
    )
    send_welcome_emails = forms.BooleanField(
        label=_("Send welcome emails"),
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
        help_text=_("Send welcome emails with login credentials to imported users"),
    )
    update_existing = forms.BooleanField(
        label=_("Update existing users"),
        initial=False,
        required=False,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
        help_text=_("Update existing users if username or email matches"),
    )

    def clean_csv_file(self):
        csv_file = self.cleaned_data.get("csv_file")
        if csv_file:
            # Validate file type
            if not csv_file.name.endswith(".csv"):
                raise forms.ValidationError(_("Please upload a CSV file."))

            # Validate file size (5MB max)
            if csv_file.size > 5 * 1024 * 1024:
                raise forms.ValidationError(_("CSV file must be less than 5MB."))

            # Basic CSV validation
            try:
                import csv
                from io import StringIO

                csv_file.seek(0)
                content = csv_file.read().decode("utf-8")
                csv_reader = csv.DictReader(StringIO(content))

                # Check required columns
                required_columns = ["username", "email", "first_name", "last_name"]
                if not all(col in csv_reader.fieldnames for col in required_columns):
                    raise forms.ValidationError(
                        _("CSV must contain columns: {}").format(
                            ", ".join(required_columns)
                        )
                    )

                # Reset file pointer
                csv_file.seek(0)

            except Exception as e:
                raise forms.ValidationError(_("Invalid CSV file: {}").format(str(e)))

        return csv_file


class UserFilterForm(forms.Form):
    """Form for filtering users in list view."""

    search = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Search users...",
                "data-filter": "search",
            }
        ),
    )
    role = forms.ModelChoiceField(
        queryset=UserRole.objects.all(),
        required=False,
        empty_label="All Roles",
        widget=forms.Select(attrs={"class": "form-control", "data-filter": "role"}),
    )
    status = forms.ChoiceField(
        choices=[
            ("", "All Status"),
            ("active", "Active"),
            ("inactive", "Inactive"),
            ("locked", "Locked"),
            ("password_change", "Requires Password Change"),
        ],
        required=False,
        widget=forms.Select(attrs={"class": "form-control", "data-filter": "status"}),
    )
    date_joined_from = forms.DateField(
        required=False,
        widget=forms.DateInput(
            attrs={"class": "form-control", "type": "date", "data-filter": "date_from"}
        ),
    )
    date_joined_to = forms.DateField(
        required=False,
        widget=forms.DateInput(
            attrs={"class": "form-control", "type": "date", "data-filter": "date_to"}
        ),
    )
