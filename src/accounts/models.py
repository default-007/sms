# src/accounts/models.py

import os
import re
from datetime import timedelta

from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator, validate_email
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from PIL import Image

from .managers import (
    UserAuditLogManager,
    UserManager,
    UserRoleAssignmentManager,
    UserRoleManager,
    UserSessionManager,
)


def user_profile_picture_path(instance, filename):
    """Generate upload path for user profile pictures."""
    ext = filename.split(".")[-1].lower()
    filename = f"{instance.username}_{timezone.now().strftime('%Y%m%d_%H%M%S')}.{ext}"
    return f"profile_pictures/{instance.id or 'temp'}/{filename}"


class User(AbstractBaseUser, PermissionsMixin):
    """Enhanced Custom User model with email/phone login support."""

    # Core identification fields
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

    email = models.EmailField(
        _("email address"),
        unique=True,
        help_text=_("Required. Must be a valid email address."),
    )

    phone_number = models.CharField(
        _("phone number"),
        max_length=20,
        blank=True,
        unique=True,
        null=True,
        validators=[
            RegexValidator(
                r"^\+?1?\d{9,15}$",
                _(
                    'Phone number must be entered in the format: "+999999999". Up to 15 digits allowed.'
                ),
            )
        ],
        help_text=_("Optional. Include country code for international numbers."),
    )

    # Personal information
    first_name = models.CharField(_("first name"), max_length=150, blank=True)
    last_name = models.CharField(_("last name"), max_length=150, blank=True)
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
        _("profile picture"),
        upload_to=user_profile_picture_path,
        null=True,
        blank=True,
        help_text=_("Profile picture (max 2MB, JPEG/PNG only)"),
    )

    # Security and authentication fields
    failed_login_attempts = models.PositiveIntegerField(default=0)
    last_failed_login = models.DateTimeField(null=True, blank=True)
    password_changed_at = models.DateTimeField(default=timezone.now)
    requires_password_change = models.BooleanField(default=False)
    email_verified = models.BooleanField(default=False)
    phone_verified = models.BooleanField(default=False)
    two_factor_enabled = models.BooleanField(default=False)
    backup_codes = models.JSONField(default=list, blank=True)

    # Account status
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

    # Preferences
    timezone_preference = models.CharField(
        _("timezone"),
        max_length=50,
        default="UTC",
        help_text=_("User's preferred timezone"),
    )
    language_preference = models.CharField(
        _("language"),
        max_length=10,
        default="en",
        help_text=_("User's preferred language"),
    )
    email_notifications = models.BooleanField(
        _("email notifications"),
        default=True,
        help_text=_("Receive notifications via email"),
    )
    sms_notifications = models.BooleanField(
        _("SMS notifications"),
        default=False,
        help_text=_("Receive notifications via SMS"),
    )

    # Timestamps
    date_joined = models.DateTimeField(_("date joined"), default=timezone.now)
    last_login = models.DateTimeField(_("last login"), null=True, blank=True)
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
            models.Index(fields=["phone_number"]),
            models.Index(fields=["is_active", "date_joined"]),
            models.Index(fields=["failed_login_attempts", "last_failed_login"]),
            models.Index(fields=["email_verified", "phone_verified"]),
        ]

    def __str__(self):
        return f"{self.username} ({self.get_full_name()})"

    def clean(self):
        """Validate model fields."""
        super().clean()

        # Normalize email
        if self.email:
            self.email = self.email.lower().strip()
            try:
                validate_email(self.email)
            except ValidationError:
                raise ValidationError({"email": _("Enter a valid email address.")})

        # Normalize phone number
        if self.phone_number:
            # Remove all non-digit characters except +
            clean_phone = re.sub(r"[^\d+]", "", self.phone_number)
            if not clean_phone.startswith("+"):
                clean_phone = "+" + clean_phone
            self.phone_number = clean_phone

        # Validate date of birth
        if self.date_of_birth and self.date_of_birth > timezone.now().date():
            raise ValidationError(
                {"date_of_birth": _("Date of birth cannot be in the future.")}
            )

    def save(self, *args, **kwargs):
        """Override save to handle profile picture resizing and cache invalidation."""
        # Clean fields
        self.full_clean()

        # Clear cache when user is saved
        if self.pk:
            cache.delete_many([f"user_permissions_{self.pk}", f"user_roles_{self.pk}"])

        is_new = self.pk is None
        super().save(*args, **kwargs)

        # Resize profile picture if it exists and is new
        if self.profile_picture and (
            is_new or "profile_picture" in kwargs.get("update_fields", [])
        ):
            self._resize_profile_picture()

    def _resize_profile_picture(self):
        """Resize profile picture to optimize storage."""
        if not self.profile_picture or not hasattr(self.profile_picture, "path"):
            return

        try:
            with Image.open(self.profile_picture.path) as img:
                # Convert to RGB if necessary
                if img.mode in ("RGBA", "LA", "P"):
                    img = img.convert("RGB")

                if img.height > 300 or img.width > 300:
                    img.thumbnail((300, 300), Image.Resampling.LANCZOS)

                    # Save with optimization
                    img.save(
                        self.profile_picture.path, "JPEG", quality=85, optimize=True
                    )
        except Exception as e:
            import logging

            logger = logging.getLogger(__name__)
            logger.warning(
                f"Could not resize profile picture for user {self.username}: {e}"
            )

    def get_full_name(self):
        """Return the first_name plus the last_name, with a space in between."""
        full_name = f"{self.first_name} {self.last_name}"
        return full_name.strip() or self.username

    def get_short_name(self):
        """Return the short name for the user."""
        return self.first_name or self.username

    def get_display_name(self):
        """Return appropriate display name."""
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        elif self.first_name:
            return self.first_name
        return self.username

    def get_assigned_roles(self):
        """Return all roles assigned to this user with caching."""
        cache_key = f"user_roles_{self.pk}"
        roles = cache.get(cache_key)

        if roles is None:
            roles = list(
                self.role_assignments.filter(is_active=True)
                .select_related("role")
                .values_list("role", flat=True)
            )
            # Get the actual role objects
            from .models import UserRole

            roles = list(UserRole.objects.filter(id__in=roles))
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
            cache.set(cache_key, permissions, 3600)

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
                lockout_time = timezone.now() - timedelta(minutes=30)
                return self.last_failed_login > lockout_time
        return False

    def reset_failed_login_attempts(self):
        """Reset failed login attempts counter."""
        if self.failed_login_attempts > 0 or self.last_failed_login:
            self.failed_login_attempts = 0
            self.last_failed_login = None
            self.save(update_fields=["failed_login_attempts", "last_failed_login"])

    def increment_failed_login_attempts(self):
        """Increment failed login attempts counter."""
        self.failed_login_attempts += 1
        self.last_failed_login = timezone.now()
        self.save(update_fields=["failed_login_attempts", "last_failed_login"])

    def can_login_with_identifier(self, identifier):
        """Check if user can be identified by the given identifier."""
        identifier = identifier.strip().lower()

        # Check email
        if self.email.lower() == identifier:
            return True

        # Check phone number
        if self.phone_number:
            clean_phone = re.sub(r"[^\d+]", "", self.phone_number)
            clean_identifier = re.sub(r"[^\d+]", "", identifier)
            if clean_phone == clean_identifier:
                return True

        # Check username
        return self.username.lower() == identifier

    def get_contact_methods(self):
        """Get available contact methods for this user."""
        methods = []
        if self.email and self.email_verified:
            methods.append({"type": "email", "value": self.email, "verified": True})
        if self.phone_number and self.phone_verified:
            methods.append(
                {"type": "phone", "value": self.phone_number, "verified": True}
            )
        return methods

    def get_profile_completion_percentage(self):
        """Calculate profile completion percentage."""
        total_fields = 12
        completed_fields = 0

        fields_to_check = [
            self.first_name,
            self.last_name,
            self.email,
            self.phone_number,
            self.address,
            self.date_of_birth,
            self.gender,
            self.profile_picture,
            self.timezone_preference,
            self.language_preference,
        ]

        for field in fields_to_check:
            if field:
                completed_fields += 1

        # Email and phone verification
        if self.email_verified:
            completed_fields += 1
        if self.phone_verified:
            completed_fields += 1

        return int((completed_fields / total_fields) * 100)

    def get_security_score(self):
        """Calculate security score based on various factors."""
        score = 0
        max_score = 100

        # Password age (20 points)
        if self.password_changed_at:
            days_since_change = (timezone.now() - self.password_changed_at).days
            if days_since_change <= 30:
                score += 20
            elif days_since_change <= 90:
                score += 15
            elif days_since_change <= 180:
                score += 10
            else:
                score += 5

        # Email verification (20 points)
        if self.email_verified:
            score += 20

        # Phone verification (20 points)
        if self.phone_verified:
            score += 20

        # Two-factor authentication (30 points)
        if self.two_factor_enabled:
            score += 30

        # Failed login attempts (penalty)
        if self.failed_login_attempts > 0:
            score -= min(self.failed_login_attempts * 2, 10)

        return max(0, min(score, max_score))


class UserRole(models.Model):
    """Enhanced Role model with permission management."""

    name = models.CharField(_("role name"), max_length=100, unique=True)
    description = models.TextField(_("description"), blank=True)
    permissions = models.JSONField(_("permissions"), default=dict, blank=True)
    is_system_role = models.BooleanField(_("system role"), default=False)
    is_active = models.BooleanField(_("active"), default=True)

    # Hierarchy and inheritance
    parent_role = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="child_roles",
        verbose_name=_("parent role"),
        help_text=_("Role to inherit permissions from"),
    )

    # Color coding for UI
    color_code = models.CharField(
        _("color code"),
        max_length=7,
        default="#007bff",
        help_text=_("Hex color code for UI display"),
    )

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

    objects = UserRoleManager()

    class Meta:
        verbose_name = _("user role")
        verbose_name_plural = _("user roles")
        ordering = ["name"]
        indexes = [
            models.Index(fields=["name"]),
            models.Index(fields=["is_system_role"]),
            models.Index(fields=["is_active"]),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        """Override save to clear cache and handle inheritance."""
        super().save(*args, **kwargs)
        # Clear all related user permissions cache
        self._clear_user_caches()

    def delete(self, *args, **kwargs):
        """Override delete to clear cache."""
        self._clear_user_caches()
        super().delete(*args, **kwargs)

    def _clear_user_caches(self):
        """Clear cache for all users with this role."""
        user_ids = self.user_assignments.values_list("user_id", flat=True)
        cache_keys = []
        for user_id in user_ids:
            cache_keys.extend([f"user_permissions_{user_id}", f"user_roles_{user_id}"])
        if cache_keys:
            cache.delete_many(cache_keys)

    def get_permission_count(self):
        """Get total number of permissions in this role."""
        count = 0
        for resource, actions in self.permissions.items():
            count += len(actions) if isinstance(actions, list) else 0
        return count

    def has_permission(self, resource, action):
        """Check if this role has a specific permission."""
        # Check direct permissions
        if resource in self.permissions and action in self.permissions.get(
            resource, []
        ):
            return True

        # Check inherited permissions from parent role
        if self.parent_role:
            return self.parent_role.has_permission(resource, action)

        return False

    def get_all_permissions(self):
        """Get all permissions including inherited ones."""
        all_permissions = self.permissions.copy()

        # Inherit from parent role
        if self.parent_role:
            parent_permissions = self.parent_role.get_all_permissions()
            for resource, actions in parent_permissions.items():
                if resource not in all_permissions:
                    all_permissions[resource] = []
                # Merge actions without duplicates
                all_permissions[resource] = list(
                    set(all_permissions[resource] + actions)
                )

        return all_permissions

    def get_inherited_permissions(self):
        """Get only the permissions inherited from parent roles."""
        if not self.parent_role:
            return {}
        return self.parent_role.get_all_permissions()


class UserRoleAssignment(models.Model):
    """Enhanced model to assign roles to users with advanced features."""

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

    # Additional context
    notes = models.TextField(_("notes"), blank=True)
    assignment_reason = models.CharField(
        _("assignment reason"),
        max_length=200,
        blank=True,
        help_text=_("Reason for role assignment"),
    )

    # Approval workflow
    requires_approval = models.BooleanField(_("requires approval"), default=False)
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="role_assignments_approved",
        verbose_name=_("approved by"),
    )
    approved_at = models.DateTimeField(_("approved at"), null=True, blank=True)

    objects = UserRoleAssignmentManager()

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
            models.Index(fields=["requires_approval", "approved_at"]),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.role.name}"

    def save(self, *args, **kwargs):
        """Override save to clear user cache."""
        super().save(*args, **kwargs)
        self._clear_user_cache()

    def delete(self, *args, **kwargs):
        """Override delete to clear user cache."""
        user_pk = self.user.pk
        super().delete(*args, **kwargs)
        cache.delete_many([f"user_permissions_{user_pk}", f"user_roles_{user_pk}"])

    def _clear_user_cache(self):
        """Clear user's cache when role assignment changes."""
        cache.delete_many(
            [f"user_permissions_{self.user.pk}", f"user_roles_{self.user.pk}"]
        )

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

    def is_pending_approval(self):
        """Check if assignment is pending approval."""
        return self.requires_approval and not self.approved_at

    def approve(self, approved_by):
        """Approve the role assignment."""
        self.approved_by = approved_by
        self.approved_at = timezone.now()
        self.is_active = True
        self.save()


class UserProfile(models.Model):
    """Extended profile information for users."""

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="profile",
        verbose_name=_("user"),
    )

    # Professional information
    bio = models.TextField(_("biography"), blank=True, max_length=500)
    website = models.URLField(_("website"), blank=True)
    location = models.CharField(_("location"), max_length=100, blank=True)

    # Educational background
    education_level = models.CharField(
        _("education level"),
        max_length=50,
        blank=True,
        choices=[
            ("high_school", _("High School")),
            ("bachelor", _("Bachelor's Degree")),
            ("master", _("Master's Degree")),
            ("phd", _("PhD")),
            ("other", _("Other")),
        ],
    )
    institution = models.CharField(
        _("institution"),
        max_length=200,
        blank=True,
        help_text=_("Current or most recent educational institution"),
    )

    # Professional details
    occupation = models.CharField(_("occupation"), max_length=100, blank=True)
    department = models.CharField(_("department"), max_length=100, blank=True)
    employee_id = models.CharField(
        _("employee ID"), max_length=50, blank=True, unique=True, null=True
    )

    # Emergency contact
    emergency_contact_name = models.CharField(
        _("emergency contact name"), max_length=100, blank=True
    )
    emergency_contact_phone = models.CharField(
        _("emergency contact phone"), max_length=20, blank=True
    )
    emergency_contact_relationship = models.CharField(
        _("emergency contact relationship"), max_length=50, blank=True
    )

    # Social media
    linkedin_url = models.URLField(_("LinkedIn URL"), blank=True)
    twitter_url = models.URLField(_("Twitter URL"), blank=True)
    facebook_url = models.URLField(_("Facebook URL"), blank=True)

    # System tracking
    profile_views = models.PositiveIntegerField(_("profile views"), default=0)
    last_profile_update = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("user profile")
        verbose_name_plural = _("user profiles")

    def __str__(self):
        return f"{self.user.username} Profile"

    def increment_views(self):
        """Increment profile view count."""
        self.profile_views += 1
        self.save(update_fields=["profile_views"])


class UserSession(models.Model):
    """Enhanced model to track user sessions for security purposes."""

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="sessions",
        verbose_name=_("user"),
    )
    session_key = models.CharField(_("session key"), max_length=40, unique=True)
    ip_address = models.GenericIPAddressField(_("IP address"))
    user_agent = models.TextField(_("user agent"))

    # Geographic and device information
    country = models.CharField(_("country"), max_length=100, blank=True)
    city = models.CharField(_("city"), max_length=100, blank=True)
    device_type = models.CharField(
        _("device type"),
        max_length=20,
        choices=[
            ("desktop", _("Desktop")),
            ("mobile", _("Mobile")),
            ("tablet", _("Tablet")),
            ("unknown", _("Unknown")),
        ],
        default="unknown",
    )
    browser = models.CharField(_("browser"), max_length=50, blank=True)
    os = models.CharField(_("operating system"), max_length=50, blank=True)

    # Session tracking
    created_at = models.DateTimeField(auto_now_add=True)
    last_activity = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    logout_reason = models.CharField(
        _("logout reason"),
        max_length=50,
        blank=True,
        choices=[
            ("user", _("User Logout")),
            ("timeout", _("Session Timeout")),
            ("security", _("Security Logout")),
            ("admin", _("Admin Logout")),
        ],
    )

    objects = UserSessionManager()

    class Meta:
        verbose_name = _("user session")
        verbose_name_plural = _("user sessions")
        ordering = ["-last_activity"]
        indexes = [
            models.Index(fields=["user", "is_active"]),
            models.Index(fields=["session_key"]),
            models.Index(fields=["last_activity"]),
            models.Index(fields=["ip_address"]),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.ip_address}"

    def get_session_duration(self):
        """Get session duration in minutes."""
        if self.is_active:
            duration = timezone.now() - self.created_at
        else:
            duration = self.last_activity - self.created_at
        return int(duration.total_seconds() / 60)

    def is_current_session(self, request):
        """Check if this is the current session."""
        return (
            hasattr(request, "session")
            and request.session.session_key == self.session_key
        )


class UserAuditLog(models.Model):
    """Enhanced audit trail for user-related actions."""

    ACTION_CHOICES = (
        ("create", _("Create")),
        ("update", _("Update")),
        ("delete", _("Delete")),
        ("login", _("Login")),
        ("logout", _("Logout")),
        ("password_change", _("Password Change")),
        ("password_reset", _("Password Reset")),
        ("role_assign", _("Role Assigned")),
        ("role_remove", _("Role Removed")),
        ("account_lock", _("Account Locked")),
        ("account_unlock", _("Account Unlocked")),
        ("email_verify", _("Email Verified")),
        ("phone_verify", _("Phone Verified")),
        ("2fa_enable", _("2FA Enabled")),
        ("2fa_disable", _("2FA Disabled")),
        ("profile_view", _("Profile Viewed")),
        ("export", _("Data Export")),
        ("import", _("Data Import")),
    )

    SEVERITY_CHOICES = (
        ("low", _("Low")),
        ("medium", _("Medium")),
        ("high", _("High")),
        ("critical", _("Critical")),
    )

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="audit_logs",
        verbose_name=_("user"),
        null=True,  # Allow null for system actions
    )
    action = models.CharField(_("action"), max_length=20, choices=ACTION_CHOICES)
    description = models.TextField(_("description"))
    severity = models.CharField(
        _("severity"), max_length=10, choices=SEVERITY_CHOICES, default="low"
    )

    # Context information
    ip_address = models.GenericIPAddressField(_("IP address"), null=True, blank=True)
    user_agent = models.TextField(_("user agent"), blank=True)
    session_key = models.CharField(_("session key"), max_length=40, blank=True)

    # Who performed the action
    performed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs_performed",
        verbose_name=_("performed by"),
    )

    # Additional data
    timestamp = models.DateTimeField(auto_now_add=True)
    extra_data = models.JSONField(_("extra data"), default=dict, blank=True)

    # Tags for categorization
    tags = models.JSONField(_("tags"), default=list, blank=True)

    objects = UserAuditLogManager()

    class Meta:
        verbose_name = _("user audit log")
        verbose_name_plural = _("user audit logs")
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["user", "timestamp"]),
            models.Index(fields=["action", "timestamp"]),
            models.Index(fields=["performed_by", "timestamp"]),
            models.Index(fields=["timestamp"]),
            models.Index(fields=["severity", "timestamp"]),
            models.Index(fields=["ip_address", "timestamp"]),
        ]

    def __str__(self):
        user_name = self.user.username if self.user else "System"
        return f"{user_name} - {self.get_action_display()} - {self.timestamp}"

    def get_formatted_timestamp(self):
        """Get formatted timestamp for display."""
        return self.timestamp.strftime("%Y-%m-%d %H:%M:%S")

    def add_tag(self, tag):
        """Add a tag to the audit log."""
        if tag not in self.tags:
            self.tags.append(tag)
            self.save(update_fields=["tags"])

    def remove_tag(self, tag):
        """Remove a tag from the audit log."""
        if tag in self.tags:
            self.tags.remove(tag)
            self.save(update_fields=["tags"])
