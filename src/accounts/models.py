from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.core.validators import RegexValidator
from django.core.cache import cache
from PIL import Image
import os

from .managers import UserManager


class User(AbstractBaseUser, PermissionsMixin):
    """Enhanced Custom User model with optimizations."""

    username = models.CharField(
        _("username"),
        max_length=150,
        unique=True,
        validators=[
            RegexValidator(
                r"^[a-zA-Z0-9_]+$",
                _("Username must contain only letters, numbers, and underscores."),
            )
        ],
        help_text=_("150 characters or fewer. Letters, digits and underscore only."),
        error_messages={
            "unique": _("A user with that username already exists."),
        },
    )
    email = models.EmailField(_("email address"), unique=True)
    first_name = models.CharField(_("first name"), max_length=150, blank=True)
    last_name = models.CharField(_("last name"), max_length=150, blank=True)

    phone_number = models.CharField(
        _("phone number"),
        max_length=20,
        blank=True,
        validators=[
            RegexValidator(
                r"^\+?1?\d{9,15}$",
                _(
                    'Phone number must be entered in the format: "+999999999". Up to 15 digits allowed.'
                ),
            )
        ],
    )
    address = models.TextField(_("address"), blank=True)
    date_of_birth = models.DateField(_("date of birth"), null=True, blank=True)

    GENDER_CHOICES = (
        ("M", _("Male")),
        ("F", _("Female")),
        ("O", _("Other")),
        ("P", _("Prefer not to say")),
    )
    gender = models.CharField(
        _("gender"), max_length=1, choices=GENDER_CHOICES, blank=True
    )

    profile_picture = models.ImageField(
        _("profile picture"), upload_to="profile_pictures/%Y/%m/", null=True, blank=True
    )

    # Additional security fields
    failed_login_attempts = models.PositiveIntegerField(default=0)
    last_failed_login = models.DateTimeField(null=True, blank=True)
    password_changed_at = models.DateTimeField(default=timezone.now)
    requires_password_change = models.BooleanField(default=False)

    # System fields
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

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = "username"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS = ["email"]

    class Meta:
        verbose_name = _("user")
        verbose_name_plural = _("users")
        ordering = ["username"]
        indexes = [
            models.Index(fields=["username"]),
            models.Index(fields=["email"]),
            models.Index(fields=["is_active", "date_joined"]),
        ]

    def __str__(self):
        return f"{self.username} ({self.get_full_name()})"

    def save(self, *args, **kwargs):
        """Override save to handle profile picture resizing and cache invalidation."""
        # Clear cache when user is saved
        cache.delete(f"user_permissions_{self.pk}")
        cache.delete(f"user_roles_{self.pk}")

        super().save(*args, **kwargs)

        # Resize profile picture if it exists
        if self.profile_picture:
            self._resize_profile_picture()

    def _resize_profile_picture(self):
        """Resize profile picture to optimize storage."""
        if self.profile_picture and hasattr(self.profile_picture, "path"):
            try:
                with Image.open(self.profile_picture.path) as img:
                    if img.height > 300 or img.width > 300:
                        img.thumbnail((300, 300), Image.Resampling.LANCZOS)
                        img.save(self.profile_picture.path)
            except Exception:
                pass  # Silently handle image processing errors

    def get_full_name(self):
        """Return the first_name plus the last_name, with a space in between."""
        full_name = f"{self.first_name} {self.last_name}"
        return full_name.strip() or self.username

    def get_short_name(self):
        """Return the short name for the user."""
        return self.first_name or self.username

    def get_assigned_roles(self):
        """Return all roles assigned to this user with caching."""
        cache_key = f"user_roles_{self.pk}"
        roles = cache.get(cache_key)

        if roles is None:
            roles = [
                assignment.role
                for assignment in self.role_assignments.select_related("role").all()
            ]
            cache.set(cache_key, roles, 3600)  # Cache for 1 hour

        return roles

    def has_role(self, role_name):
        """Check if the user has a specific role with caching."""
        roles = self.get_assigned_roles()
        return any(role.name == role_name for role in roles)

    def get_initials(self):
        """Return the user's initials."""
        initials = ""
        if self.first_name:
            initials += self.first_name[0]
        if self.last_name:
            initials += self.last_name[0]
        return initials.upper() or self.username[0].upper()

    def get_age(self):
        """Return the user's age based on date of birth."""
        if not self.date_of_birth:
            return None

        from datetime import date

        today = date.today()
        return (
            today.year
            - self.date_of_birth.year
            - (
                (today.month, today.day)
                < (self.date_of_birth.month, self.date_of_birth.day)
            )
        )

    def is_admin(self):
        """Check if the user has admin role."""
        return self.is_superuser or self.has_role("Admin")

    def get_permissions(self):
        """Get all permissions from the user's roles with caching."""
        from .services import RoleService

        cache_key = f"user_permissions_{self.pk}"
        permissions = cache.get(cache_key)

        if permissions is None:
            permissions = RoleService.get_user_permissions(self)
            cache.set(cache_key, permissions, 3600)  # Cache for 1 hour

        return permissions

    def has_permission(self, resource, action):
        """Check if the user has a specific permission."""
        from .services import RoleService

        return RoleService.check_permission(self, resource, action)

    def is_account_locked(self):
        """Check if account is locked due to failed login attempts."""
        if self.failed_login_attempts >= 5:
            if self.last_failed_login:
                # Lock for 30 minutes after 5 failed attempts
                lockout_time = timezone.now() - timezone.timedelta(minutes=30)
                return self.last_failed_login > lockout_time
        return False

    def reset_failed_login_attempts(self):
        """Reset failed login attempts counter."""
        self.failed_login_attempts = 0
        self.last_failed_login = None
        self.save(update_fields=["failed_login_attempts", "last_failed_login"])

    def increment_failed_login_attempts(self):
        """Increment failed login attempts counter."""
        self.failed_login_attempts += 1
        self.last_failed_login = timezone.now()
        self.save(update_fields=["failed_login_attempts", "last_failed_login"])


class UserRole(models.Model):
    """Enhanced Role model with optimizations."""

    name = models.CharField(_("role name"), max_length=100, unique=True)
    description = models.TextField(_("description"), blank=True)
    permissions = models.JSONField(_("permissions"), default=dict, blank=True)
    is_system_role = models.BooleanField(_("system role"), default=False)

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_roles",
        verbose_name=_("created by"),
    )

    class Meta:
        verbose_name = _("user role")
        verbose_name_plural = _("user roles")
        ordering = ["name"]
        indexes = [
            models.Index(fields=["name"]),
            models.Index(fields=["is_system_role"]),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        """Override save to clear cache."""
        super().save(*args, **kwargs)
        # Clear all user permissions cache when role is updated
        cache.delete_many(
            [
                f"user_permissions_{assignment.user.pk}"
                for assignment in self.user_assignments.all()
            ]
        )
        cache.delete_many(
            [
                f"user_roles_{assignment.user.pk}"
                for assignment in self.user_assignments.all()
            ]
        )

    def delete(self, *args, **kwargs):
        """Override delete to clear cache."""
        # Clear cache before deletion
        cache.delete_many(
            [
                f"user_permissions_{assignment.user.pk}"
                for assignment in self.user_assignments.all()
            ]
        )
        cache.delete_many(
            [
                f"user_roles_{assignment.user.pk}"
                for assignment in self.user_assignments.all()
            ]
        )
        super().delete(*args, **kwargs)

    def get_permission_count(self):
        """Get total number of permissions in this role."""
        count = 0
        for resource, actions in self.permissions.items():
            count += len(actions) if isinstance(actions, list) else 0
        return count

    def has_permission(self, resource, action):
        """Check if this role has a specific permission."""
        return resource in self.permissions and action in self.permissions.get(
            resource, []
        )


class UserRoleAssignment(models.Model):
    """Enhanced model to assign roles to users."""

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
    expires_at = models.DateTimeField(_("expires at"), null=True, blank=True)
    is_active = models.BooleanField(_("is active"), default=True)

    # Metadata
    notes = models.TextField(_("notes"), blank=True)

    class Meta:
        verbose_name = _("user role assignment")
        verbose_name_plural = _("user role assignments")
        unique_together = ("user", "role")
        ordering = ["-assigned_date"]
        indexes = [
            models.Index(fields=["user", "is_active"]),
            models.Index(fields=["role", "is_active"]),
            models.Index(fields=["assigned_date"]),
            models.Index(fields=["expires_at"]),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.role.name}"

    def save(self, *args, **kwargs):
        """Override save to clear user cache."""
        super().save(*args, **kwargs)
        # Clear user's cache when role assignment changes
        cache.delete(f"user_permissions_{self.user.pk}")
        cache.delete(f"user_roles_{self.user.pk}")

    def delete(self, *args, **kwargs):
        """Override delete to clear user cache."""
        user_pk = self.user.pk
        super().delete(*args, **kwargs)
        # Clear user's cache when role assignment is deleted
        cache.delete(f"user_permissions_{user_pk}")
        cache.delete(f"user_roles_{user_pk}")

    def is_expired(self):
        """Check if this role assignment has expired."""
        if self.expires_at:
            return timezone.now() > self.expires_at
        return False

    def days_until_expiry(self):
        """Return number of days until this assignment expires."""
        if self.expires_at:
            delta = self.expires_at - timezone.now()
            return delta.days
        return None


class UserProfile(models.Model):
    """Extended profile information for users."""

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="profile",
        verbose_name=_("user"),
    )
    bio = models.TextField(_("biography"), blank=True, max_length=500)
    website = models.URLField(_("website"), blank=True)
    location = models.CharField(_("location"), max_length=100, blank=True)
    birth_date = models.DateField(_("birth date"), null=True, blank=True)

    # Preferences
    language = models.CharField(_("language"), max_length=10, default="en")
    timezone = models.CharField(_("timezone"), max_length=50, default="UTC")
    email_notifications = models.BooleanField(_("email notifications"), default=True)
    sms_notifications = models.BooleanField(_("SMS notifications"), default=False)

    # Social media
    linkedin_url = models.URLField(_("LinkedIn URL"), blank=True)
    twitter_url = models.URLField(_("Twitter URL"), blank=True)
    facebook_url = models.URLField(_("Facebook URL"), blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("user profile")
        verbose_name_plural = _("user profiles")

    def __str__(self):
        return f"{self.user.username} Profile"


class UserSession(models.Model):
    """Track user sessions for security purposes."""

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="sessions",
        verbose_name=_("user"),
    )
    session_key = models.CharField(_("session key"), max_length=40, unique=True)
    ip_address = models.GenericIPAddressField(_("IP address"))
    user_agent = models.TextField(_("user agent"))
    created_at = models.DateTimeField(auto_now_add=True)
    last_activity = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = _("user session")
        verbose_name_plural = _("user sessions")
        ordering = ["-last_activity"]
        indexes = [
            models.Index(fields=["user", "is_active"]),
            models.Index(fields=["session_key"]),
            models.Index(fields=["last_activity"]),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.ip_address}"


# Audit Trail Model
class UserAuditLog(models.Model):
    """Audit trail for user-related actions."""

    ACTION_CHOICES = (
        ("create", _("Create")),
        ("update", _("Update")),
        ("delete", _("Delete")),
        ("login", _("Login")),
        ("logout", _("Logout")),
        ("password_change", _("Password Change")),
        ("role_assign", _("Role Assigned")),
        ("role_remove", _("Role Removed")),
        ("account_lock", _("Account Locked")),
        ("account_unlock", _("Account Unlocked")),
    )

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="audit_logs",
        verbose_name=_("user"),
    )
    action = models.CharField(_("action"), max_length=20, choices=ACTION_CHOICES)
    description = models.TextField(_("description"))
    ip_address = models.GenericIPAddressField(_("IP address"), null=True, blank=True)
    user_agent = models.TextField(_("user agent"), blank=True)
    performed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs_performed",
        verbose_name=_("performed by"),
    )
    timestamp = models.DateTimeField(auto_now_add=True)

    # Store additional context data
    extra_data = models.JSONField(_("extra data"), default=dict, blank=True)

    class Meta:
        verbose_name = _("user audit log")
        verbose_name_plural = _("user audit logs")
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["user", "timestamp"]),
            models.Index(fields=["action", "timestamp"]),
            models.Index(fields=["performed_by", "timestamp"]),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.get_action_display()} - {self.timestamp}"
