from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .managers import UserManager


class User(AbstractBaseUser, PermissionsMixin):
    """Custom User model for authentication and user management."""

    username = models.CharField(_("username"), max_length=150, unique=True)
    email = models.EmailField(_("email address"), unique=True)
    first_name = models.CharField(_("first name"), max_length=150, blank=True)
    last_name = models.CharField(_("last name"), max_length=150, blank=True)
    phone_number = models.CharField(_("phone number"), max_length=20, blank=True)
    address = models.TextField(_("address"), blank=True)
    date_of_birth = models.DateField(_("date of birth"), null=True, blank=True)
    GENDER_CHOICES = (
        ("M", _("Male")),
        ("F", _("Female")),
        ("O", _("Other")),
    )
    gender = models.CharField(
        _("gender"), max_length=1, choices=GENDER_CHOICES, blank=True
    )
    profile_picture = models.ImageField(
        _("profile picture"), upload_to="profile_pictures/", null=True, blank=True
    )

    is_staff = models.BooleanField(
        _("staff status"),
        default=False,
        help_text=_("Designates whether the user can log into the admin site."),
    )
    is_active = models.BooleanField(
        _("active"),
        default=True,
        help_text=_(
            "Designates whether this user should be treated as active. "
            "Unselect this instead of deleting accounts."
        ),
    )
    date_joined = models.DateTimeField(_("date joined"), default=timezone.now)
    last_login = models.DateTimeField(_("last login"), null=True, blank=True)

    objects = UserManager()

    USERNAME_FIELD = "username"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS = ["email"]

    class Meta:
        verbose_name = _("user")
        verbose_name_plural = _("users")
        ordering = ["username"]

    def __str__(self):
        return self.username

    def get_full_name(self):
        """Return the first_name plus the last_name, with a space in between."""
        full_name = f"{self.first_name} {self.last_name}"
        return full_name.strip()

    def get_short_name(self):
        """Return the short name for the user."""
        return self.first_name

    def get_assigned_roles(self):
        """Return all roles assigned to this user."""
        return [assignment.role for assignment in self.role_assignments.all()]

    def has_role(self, role_name):
        """Check if the user has a specific role."""
        return self.role_assignments.filter(role__name=role_name).exists()


class UserRole(models.Model):
    """Role model for role-based access control."""

    name = models.CharField(_("role name"), max_length=100, unique=True)
    description = models.TextField(_("description"), blank=True)
    permissions = models.JSONField(_("permissions"), default=dict, blank=True)

    class Meta:
        verbose_name = _("user role")
        verbose_name_plural = _("user roles")
        ordering = ["name"]

    def __str__(self):
        return self.name


class UserRoleAssignment(models.Model):
    """Model to assign roles to users."""

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="role_assignments",
        verbose_name=_("user"),
    )
    role = models.ForeignKey(
        UserRole,
        on_delete=models.CASCADE,
        related_name="user_assignments",
        verbose_name=_("role"),
    )
    assigned_date = models.DateTimeField(_("assigned date"), default=timezone.now)
    assigned_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="role_assignments_made",
        verbose_name=_("assigned by"),
    )

    class Meta:
        verbose_name = _("user role assignment")
        verbose_name_plural = _("user role assignments")
        unique_together = ("user", "role")
        ordering = ["-assigned_date"]

    def __str__(self):
        return f"{self.user.username} - {self.role.name}"
