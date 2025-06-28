# src/accounts/forms.py

import re
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
from .services import AuthenticationService
from .utils import validate_password_strength

User = get_user_model()


class CustomAuthenticationForm(AuthenticationForm):
    """Enhanced login form supporting email, phone, or username."""

    identifier = forms.CharField(
        label=_("Email, Phone, Username, or Admission Number"),
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Email, phone, username, or admission number",
                "autofocus": True,
                "autocomplete": "username",
            }
        ),
        help_text=_(
            "You can log in using your email address, phone number, username, or admission number (for students)"
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
            "Please enter valid credentials. Note that fields may be case-sensitive."
        ),
        "inactive": _("This account is inactive."),
        "account_locked": _(
            "This account is locked due to multiple failed login attempts."
        ),
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Remove the username field from parent class
        if "username" in self.fields:
            del self.fields["username"]

    def clean_identifier(self):
        """Validate and normalize the identifier."""
        identifier = self.cleaned_data.get("identifier", "").strip()

        if not identifier:
            raise forms.ValidationError(_("This field is required."))

        # Basic format validation for email
        if "@" in identifier:
            try:
                validate_email(identifier)
            except ValidationError:
                raise forms.ValidationError(_("Please enter a valid email address."))

        # Basic format validation for phone
        elif (
            identifier.replace("+", "")
            .replace("-", "")
            .replace(" ", "")
            .replace("(", "")
            .replace(")", "")
            .isdigit()
        ):
            # Basic phone number validation
            clean_phone = re.sub(r"[^\d+]", "", identifier)
            if len(clean_phone) < 10:
                raise forms.ValidationError(_("Please enter a valid phone number."))

        # Basic format validation for admission number
        elif re.match(r"^[A-Z0-9]{6,20}$", identifier, re.IGNORECASE):
            # Admission numbers are typically alphanumeric
            pass

        return identifier

    def clean(self):
        """Authenticate using identifier and password."""
        identifier = self.cleaned_data.get("identifier")
        password = self.cleaned_data.get("password")

        if identifier and password:
            # Use our custom authentication service
            user, result = AuthenticationService.authenticate_user(
                identifier, password, self.request
            )

            if result == "success" and user:
                self.user_cache = user
                self.confirm_login_allowed(user)
            else:
                # Handle different authentication results
                error_messages = {
                    "user_not_found": _("No account found with this identifier."),
                    "account_locked": _(
                        "Account is locked due to multiple failed attempts."
                    ),
                    "account_inactive": _("This account is inactive."),
                    "invalid_credentials": _("Invalid credentials."),
                }

                error_message = error_messages.get(result, _("Authentication failed."))
                raise forms.ValidationError(error_message, code="invalid_login")

        return self.cleaned_data

    def confirm_login_allowed(self, user):
        """Additional checks for login permission."""
        if not user.is_active:
            raise ValidationError(
                self.error_messages["inactive"],
                code="inactive",
            )

        if user.is_account_locked():
            raise ValidationError(
                self.error_messages["account_locked"],
                code="account_locked",
            )


class EnhancedUserCreationForm(UserCreationForm):
    """Enhanced user creation form with additional fields and validation."""

    email = forms.EmailField(
        label=_("Email"),
        widget=forms.EmailInput(
            attrs={"class": "form-control", "placeholder": "Email"}
        ),
        required=True,
        help_text=_("Required. Must be a valid email address."),
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
            attrs={"class": "form-control", "placeholder": "+1234567890"}
        ),
        required=False,
        max_length=20,
        help_text=_("Optional. Include country code for international numbers."),
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
        help_text=_("Max 2MB, JPEG/PNG only"),
    )
    roles = forms.ModelMultipleChoiceField(
        queryset=UserRole.objects.filter(is_system_role=False, is_active=True),
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
    requires_password_change = forms.BooleanField(
        label=_("Require password change on first login"),
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
        self.fields["username"].help_text = _(
            "Optional. If not provided, one will be generated automatically."
        )
        self.fields["username"].required = False

    def clean_email(self):
        """Validate email uniqueness."""
        email = self.cleaned_data.get("email")
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError(_("This email address is already in use."))
        return email.lower()

    def clean_username(self):
        """Validate username or generate one if not provided."""
        username = self.cleaned_data.get("username", "").strip()

        if username:
            if User.objects.filter(username=username).exists():
                raise forms.ValidationError(_("This username is already taken."))
            if len(username) < 3:
                raise forms.ValidationError(
                    _("Username must be at least 3 characters long.")
                )
        else:
            # Generate username from email or names
            email = self.cleaned_data.get("email", "")
            first_name = self.cleaned_data.get("first_name", "")
            last_name = self.cleaned_data.get("last_name", "")

            username = self._generate_username(first_name, last_name, email)

        return username

    def clean_phone_number(self):
        """Validate and normalize phone number."""
        phone = self.cleaned_data.get("phone_number", "").strip()

        if phone:
            # Normalize phone number
            clean_phone = re.sub(r"[^\d+]", "", phone)
            if not clean_phone.startswith("+"):
                clean_phone = "+" + clean_phone

            # Check uniqueness
            if User.objects.filter(phone_number=clean_phone).exists():
                raise forms.ValidationError(_("This phone number is already in use."))

            return clean_phone
        return phone

    def clean_password1(self):
        """Validate password strength."""
        password = self.cleaned_data.get("password1")
        if password:
            validation = validate_password_strength(password)
            if not validation["is_valid"]:
                raise forms.ValidationError(validation["feedback"])
        return password

    def clean_profile_picture(self):
        """Validate profile picture."""
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

    def _generate_username(self, first_name, last_name, email):
        """Generate a unique username."""
        base_username = ""

        if first_name and last_name:
            base_username = f"{first_name.lower()}.{last_name.lower()}"
        elif email:
            base_username = email.split("@")[0].lower()
        else:
            base_username = "user"

        # Clean username
        base_username = re.sub(r"[^a-zA-Z0-9_]", "", base_username)

        # Ensure uniqueness
        username = base_username
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{base_username}{counter}"
            counter += 1

        return username

    def get_identifier_type_display(self):
        """Get display name for identifier type."""
        return "credentials"

    def _detect_identifier_type(self, identifier):
        """Detect the type of identifier being used."""
        if not identifier:
            return "unknown"

        if "@" in identifier:
            return "email"
        elif (
            identifier.replace("+", "")
            .replace("-", "")
            .replace(" ", "")
            .replace("(", "")
            .replace(")", "")
            .isdigit()
        ):
            return "phone"
        else:
            return "username"

    def save(self, commit=True):
        """Save user with additional processing."""
        user = super().save(commit=False)

        # Set additional fields
        user.requires_password_change = self.cleaned_data.get(
            "requires_password_change", True
        )

        if commit:
            user.save()

            # Assign roles
            roles = self.cleaned_data.get("roles", [])
            for role in roles:
                UserRoleAssignment.objects.create(
                    user=user, role=role, assigned_by=getattr(self, "created_by", None)
                )

            # Send welcome email if requested
            if self.cleaned_data.get("send_welcome_email", True):
                # This would be handled by a signal or service
                pass

        return user


class UserUpdateForm(forms.ModelForm):
    """Enhanced form for updating existing users."""

    roles = forms.ModelMultipleChoiceField(
        queryset=UserRole.objects.filter(is_active=True),
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
            "email_notifications",
            "sms_notifications",
            "timezone_preference",
            "language_preference",
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
            "email_notifications": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),
            "sms_notifications": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),
            "timezone_preference": forms.Select(attrs={"class": "form-control"}),
            "language_preference": forms.Select(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            # Pre-select current roles
            self.fields["roles"].initial = self.instance.role_assignments.filter(
                is_active=True
            ).values_list("role", flat=True)

    def clean_email(self):
        """Validate email uniqueness."""
        email = self.cleaned_data.get("email")
        if User.objects.filter(email=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError(_("This email address is already in use."))
        return email.lower()

    def clean_phone_number(self):
        """Validate phone number uniqueness."""
        phone = self.cleaned_data.get("phone_number", "").strip()

        if phone:
            # Normalize phone number
            clean_phone = re.sub(r"[^\d+]", "", phone)
            if not clean_phone.startswith("+"):
                clean_phone = "+" + clean_phone

            # Check uniqueness
            if (
                User.objects.filter(phone_number=clean_phone)
                .exclude(pk=self.instance.pk)
                .exists()
            ):
                raise forms.ValidationError(_("This phone number is already in use."))

            return clean_phone
        return phone


class ProfileForm(forms.ModelForm):
    """Form for user profile self-management."""

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
            "email_notifications",
            "sms_notifications",
            "timezone_preference",
            "language_preference",
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
            "email_notifications": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),
            "sms_notifications": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),
            "timezone_preference": forms.Select(attrs={"class": "form-control"}),
            "language_preference": forms.Select(attrs={"class": "form-control"}),
        }

    def clean_email(self):
        """Validate email uniqueness."""
        email = self.cleaned_data.get("email")
        if User.objects.filter(email=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError(_("This email address is already in use."))
        return email.lower()

    def clean_phone_number(self):
        """Validate phone number."""
        phone = self.cleaned_data.get("phone_number", "").strip()

        if phone:
            # Normalize phone number
            clean_phone = re.sub(r"[^\d+]", "", phone)
            if not clean_phone.startswith("+"):
                clean_phone = "+" + clean_phone

            # Check uniqueness
            if (
                User.objects.filter(phone_number=clean_phone)
                .exclude(pk=self.instance.pk)
                .exists()
            ):
                raise forms.ValidationError(_("This phone number is already in use."))

            return clean_phone
        return phone

    def clean_profile_picture(self):
        """Validate profile picture."""
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


class ExtendedProfileForm(forms.ModelForm):
    """Form for extended profile information."""

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

    class Meta:
        model = UserProfile
        fields = [
            "bio",
            "website",
            "location",
            "education_level",
            "institution",
            "occupation",
            "department",
            "employee_id",
            "emergency_contact_name",
            "emergency_contact_phone",
            "emergency_contact_relationship",
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
            "education_level": forms.Select(attrs={"class": "form-control"}),
            "institution": forms.TextInput(attrs={"class": "form-control"}),
            "occupation": forms.TextInput(attrs={"class": "form-control"}),
            "department": forms.TextInput(attrs={"class": "form-control"}),
            "employee_id": forms.TextInput(attrs={"class": "form-control"}),
            "emergency_contact_name": forms.TextInput(attrs={"class": "form-control"}),
            "emergency_contact_phone": forms.TextInput(attrs={"class": "form-control"}),
            "emergency_contact_relationship": forms.TextInput(
                attrs={"class": "form-control"}
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

    def clean_employee_id(self):
        """Validate employee ID uniqueness."""
        employee_id = self.cleaned_data.get("employee_id")
        if employee_id:
            existing = UserProfile.objects.filter(employee_id=employee_id)
            if self.instance:
                existing = existing.exclude(pk=self.instance.pk)
            if existing.exists():
                raise forms.ValidationError(_("This employee ID is already in use."))
        return employee_id

    def save(self, commit=True):
        """Save profile and update user fields."""
        profile = super().save(commit=False)

        if self.user:
            # Update user fields
            self.user.first_name = self.cleaned_data["first_name"]
            self.user.last_name = self.cleaned_data["last_name"]
            self.user.email = self.cleaned_data["email"]
            self.user.phone_number = self.cleaned_data["phone_number"]

            if commit:
                self.user.save()

            profile.user = self.user

        if commit:
            profile.save()

        return profile


class CustomPasswordChangeForm(PasswordChangeForm):
    """Enhanced password change form with strength validation."""

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
        help_text=_(
            "Password must be at least 8 characters with uppercase, lowercase, numbers, and special characters."
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
        """Validate password strength."""
        password = self.cleaned_data.get("new_password1")
        if password:
            validation = validate_password_strength(password)
            if not validation["is_valid"]:
                raise forms.ValidationError(validation["feedback"])
        return password


class CustomPasswordResetForm(PasswordResetForm):
    """Enhanced password reset form with identifier support."""

    identifier = forms.CharField(
        label=_("Email, Username, or Admission Number"),
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Email, username, or admission number",
                "autocomplete": "email",
            }
        ),
        max_length=254,
        help_text=_(
            "Enter your email address, username, or admission number (for students) to reset your password."
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Remove the email field from parent class
        if "email" in self.fields:
            del self.fields["email"]

    def clean_identifier(self):
        """Find user by identifier and return email."""
        identifier = self.cleaned_data.get("identifier", "").strip()

        # Try to find user by email, username, or admission number
        user = None
        if "@" in identifier:
            try:
                validate_email(identifier)
                user = User.objects.filter(email=identifier, is_active=True).first()
            except ValidationError:
                pass

        if not user:
            user = User.objects.filter(username=identifier, is_active=True).first()

        # Try admission number if still not found
        if not user and re.match(r"^[A-Z0-9]{6,20}$", identifier, re.IGNORECASE):
            from .validators import find_user_by_admission_number

            user = find_user_by_admission_number(identifier)

        if not user:
            raise forms.ValidationError(
                _("No active account found with this identifier.")
            )

        # Return the email for the reset process
        self.cleaned_data["email"] = user.email
        return identifier

    def get_users(self, email):
        """Return matching user(s) who should receive a reset."""
        active_users = User.objects.filter(
            email__iexact=email,
            is_active=True,
        )
        return (u for u in active_users if u.has_usable_password())


class CustomSetPasswordForm(SetPasswordForm):
    """Enhanced set password form with strength validation."""

    new_password1 = forms.CharField(
        label=_("New Password"),
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control",
                "placeholder": "New Password",
                "autocomplete": "new-password",
            }
        ),
        help_text=_(
            "Password must be at least 8 characters with uppercase, lowercase, numbers, and special characters."
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
        """Validate password strength."""
        password = self.cleaned_data.get("new_password1")
        if password:
            validation = validate_password_strength(password)
            if not validation["is_valid"]:
                raise forms.ValidationError(validation["feedback"])
        return password


class UserRoleForm(forms.ModelForm):
    """Enhanced form for creating and updating user roles."""

    class Meta:
        model = UserRole
        fields = ("name", "description", "color_code", "parent_role")
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "color_code": forms.TextInput(
                attrs={"class": "form-control", "type": "color"}
            ),
            "parent_role": forms.Select(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Exclude self from parent role choices to prevent circular references
        if self.instance and self.instance.pk:
            self.fields["parent_role"].queryset = UserRole.objects.exclude(
                pk=self.instance.pk
            ).filter(is_active=True)

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
                label=resource.title().replace("_", " ") + " Permissions",
            )

            # Set initial values if editing existing role
            if self.instance and self.instance.pk and self.instance.permissions:
                initial_perms = self.instance.permissions.get(resource, [])
                self.fields[field_name].initial = initial_perms

    def clean_name(self):
        """Validate role name."""
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

    def clean_parent_role(self):
        """Validate parent role to prevent circular references."""
        parent_role = self.cleaned_data.get("parent_role")

        if parent_role and self.instance:
            # Check for circular reference
            current_role = parent_role
            while current_role:
                if current_role == self.instance:
                    raise forms.ValidationError(
                        _("Cannot create circular role inheritance.")
                    )
                current_role = current_role.parent_role

        return parent_role

    def save(self, commit=True):
        """Save role with permissions."""
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
    """Enhanced form for bulk user import via CSV."""

    csv_file = forms.FileField(
        label=_("CSV File"),
        widget=forms.FileInput(attrs={"class": "form-control", "accept": ".csv"}),
        help_text=_(
            "Upload a CSV file with user data. Required columns: email, first_name, last_name. "
            "Optional: username, phone_number, address, gender"
        ),
    )
    default_password = forms.CharField(
        label=_("Default Password"),
        widget=forms.PasswordInput(attrs={"class": "form-control"}),
        initial="TempPass123!",
        help_text=_(
            "Default password for all imported users (they will be required to change it)"
        ),
    )
    default_roles = forms.ModelMultipleChoiceField(
        queryset=UserRole.objects.filter(is_system_role=False, is_active=True),
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
        help_text=_("Update existing users if email matches"),
    )
    dry_run = forms.BooleanField(
        label=_("Dry run (preview only)"),
        initial=False,
        required=False,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
        help_text=_("Preview import without actually creating users"),
    )

    def clean_csv_file(self):
        """Validate CSV file."""
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
                required_columns = ["email", "first_name", "last_name"]
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

    def clean_default_password(self):
        """Validate default password strength."""
        password = self.cleaned_data.get("default_password")
        if password:
            validation = validate_password_strength(password)
            if not validation["is_valid"]:
                raise forms.ValidationError(
                    _("Default password is too weak: {}").format(
                        ", ".join(validation["feedback"])
                    )
                )
        return password


class UserFilterForm(forms.Form):
    """Enhanced form for filtering users in list view."""

    search = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Search users by name, email, username, or phone...",
                "data-filter": "search",
            }
        ),
    )
    role = forms.ModelChoiceField(
        queryset=UserRole.objects.filter(is_active=True),
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
            ("email_unverified", "Email Unverified"),
            ("phone_unverified", "Phone Unverified"),
        ],
        required=False,
        widget=forms.Select(attrs={"class": "form-control", "data-filter": "status"}),
    )
    date_joined_from = forms.DateField(
        required=False,
        widget=forms.DateInput(
            attrs={"class": "form-control", "type": "date", "data-filter": "date_from"}
        ),
        label=_("Joined From"),
    )
    date_joined_to = forms.DateField(
        required=False,
        widget=forms.DateInput(
            attrs={"class": "form-control", "type": "date", "data-filter": "date_to"}
        ),
        label=_("Joined To"),
    )
    last_login_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
        label=_("Last Login From"),
    )
    last_login_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
        label=_("Last Login To"),
    )


class TwoFactorSetupForm(forms.Form):
    """Form for setting up two-factor authentication."""

    verification_code = forms.CharField(
        label=_("Verification Code"),
        max_length=6,
        min_length=6,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "123456",
                "autocomplete": "one-time-code",
            }
        ),
        help_text=_("Enter the 6-digit code from your authenticator app"),
    )

    def clean_verification_code(self):
        """Validate verification code format."""
        code = self.cleaned_data.get("verification_code")
        if code and not code.isdigit():
            raise forms.ValidationError(
                _("Verification code must contain only digits.")
            )
        return code


class EmailVerificationForm(forms.Form):
    """Form for email verification."""

    verification_code = forms.CharField(
        label=_("Verification Code"),
        max_length=6,
        min_length=6,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "123456",
                "autocomplete": "one-time-code",
            }
        ),
        help_text=_("Enter the 6-digit code sent to your email"),
    )

    def clean_verification_code(self):
        """Validate verification code format."""
        code = self.cleaned_data.get("verification_code")
        if code and not code.isdigit():
            raise forms.ValidationError(
                _("Verification code must contain only digits.")
            )
        return code


class PhoneVerificationForm(forms.Form):
    """Form for phone number verification."""

    verification_code = forms.CharField(
        label=_("Verification Code"),
        max_length=6,
        min_length=6,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "123456",
                "autocomplete": "one-time-code",
            }
        ),
        help_text=_("Enter the 6-digit code sent to your phone"),
    )

    def clean_verification_code(self):
        """Validate verification code format."""
        code = self.cleaned_data.get("verification_code")
        if code and not code.isdigit():
            raise forms.ValidationError(
                _("Verification code must contain only digits.")
            )
        return code
