from django import forms
from django.contrib.auth.forms import (
    AuthenticationForm,
    UserCreationForm,
    PasswordChangeForm,
    PasswordResetForm,
    SetPasswordForm,
)
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

from .models import UserRole

User = get_user_model()


class CustomAuthenticationForm(AuthenticationForm):
    """Custom login form with additional styling and validation."""

    username = forms.CharField(
        label=_("Username"),
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Username"}
        ),
    )
    password = forms.CharField(
        label=_("Password"),
        widget=forms.PasswordInput(
            attrs={"class": "form-control", "placeholder": "Password"}
        ),
    )

    error_messages = {
        "invalid_login": _(
            "Please enter a correct %(username)s and password. Note that both "
            "fields may be case-sensitive."
        ),
        "inactive": _("This account is inactive."),
    }


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
    )
    last_name = forms.CharField(
        label=_("Last Name"),
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Last Name"}
        ),
        required=True,
    )
    phone_number = forms.CharField(
        label=_("Phone Number"),
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Phone Number"}
        ),
        required=False,
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
        choices=User.GENDER_CHOICES,
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

    def clean_email(self):
        email = self.cleaned_data.get("email")
        if User.objects.filter(email=email).exists():
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
        }

    def clean_email(self):
        email = self.cleaned_data.get("email")
        if User.objects.filter(email=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError(_("This email address is already in use."))
        return email


class CustomPasswordChangeForm(PasswordChangeForm):
    """Custom password change form with improved styling."""

    old_password = forms.CharField(
        label=_("Current Password"),
        widget=forms.PasswordInput(
            attrs={"class": "form-control", "placeholder": "Current Password"}
        ),
    )
    new_password1 = forms.CharField(
        label=_("New Password"),
        widget=forms.PasswordInput(
            attrs={"class": "form-control", "placeholder": "New Password"}
        ),
    )
    new_password2 = forms.CharField(
        label=_("Confirm New Password"),
        widget=forms.PasswordInput(
            attrs={"class": "form-control", "placeholder": "Confirm New Password"}
        ),
    )


class CustomPasswordResetForm(PasswordResetForm):
    """Custom password reset form with improved styling."""

    email = forms.EmailField(
        label=_("Email"),
        widget=forms.EmailInput(
            attrs={"class": "form-control", "placeholder": "Email"}
        ),
        max_length=254,
    )


class CustomSetPasswordForm(SetPasswordForm):
    """Custom set password form with improved styling."""

    new_password1 = forms.CharField(
        label=_("New Password"),
        widget=forms.PasswordInput(
            attrs={"class": "form-control", "placeholder": "New Password"}
        ),
    )
    new_password2 = forms.CharField(
        label=_("Confirm New Password"),
        widget=forms.PasswordInput(
            attrs={"class": "form-control", "placeholder": "Confirm New Password"}
        ),
    )


class UserRoleForm(forms.ModelForm):
    """Form for creating and updating user roles."""

    class Meta:
        model = UserRole
        fields = ("name", "description")
        widgets = {
            "name": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Role Name"}
            ),
            "description": forms.Textarea(
                attrs={"class": "form-control", "placeholder": "Description", "rows": 3}
            ),
        }

    def clean_name(self):
        name = self.cleaned_data.get("name")
        if (
            UserRole.objects.filter(name=name)
            .exclude(pk=self.instance.pk if self.instance else None)
            .exists()
        ):
            raise forms.ValidationError(_("A role with this name already exists."))
        return name
