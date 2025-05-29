# src/accounts/signals.py

from datetime import timezone
import logging
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver

from .models import User, UserRole, UserRoleAssignment, UserProfile, UserAuditLog
from .services import RoleService
from .tasks import send_welcome_email, send_verification_email
from .utils import get_client_info

logger = logging.getLogger(__name__)
User = get_user_model()


@receiver(post_save, sender=User)
def handle_user_post_save(sender, instance, created, **kwargs):
    """
    Handle actions after a user is created or updated.
    """
    if created:
        # Create user profile
        UserProfile.objects.get_or_create(user=instance)

        # Create default roles if they don't exist
        try:
            RoleService.create_default_roles()
        except Exception as e:
            logger.error(f"Error creating default roles: {str(e)}")

        # Send welcome email (async)
        if instance.email and instance.is_active:
            send_welcome_email.delay(instance.id)

        # Send email verification (async)
        if instance.email and not instance.email_verified:
            send_verification_email.delay(instance.id, "email")

        # Log user creation
        UserAuditLog.objects.create(
            user=instance,
            action="create",
            description="User account created",
            severity="low",
            extra_data={
                "username": instance.username,
                "email": instance.email,
                "is_active": instance.is_active,
            },
        )

        logger.info(f"New user created: {instance.username} ({instance.email})")

    else:
        # Clear user cache on update
        cache.delete_many(
            [f"user_permissions_{instance.pk}", f"user_roles_{instance.pk}"]
        )

        # Check for important field changes
        if kwargs.get("update_fields"):
            updated_fields = kwargs["update_fields"]

            if "is_active" in updated_fields:
                action = "activate" if instance.is_active else "deactivate"
                UserAuditLog.objects.create(
                    user=instance,
                    action=action,
                    description=f"User account {'activated' if instance.is_active else 'deactivated'}",
                    severity="medium",
                    extra_data={"is_active": instance.is_active},
                )

            if "email" in updated_fields:
                # Reset email verification status
                instance.email_verified = False
                instance.save(update_fields=["email_verified"])

                # Send new verification email
                send_verification_email.delay(instance.id, "email")

                UserAuditLog.objects.create(
                    user=instance,
                    action="email_change",
                    description="Email address changed",
                    severity="medium",
                    extra_data={"new_email": instance.email},
                )


@receiver(pre_save, sender=User)
def handle_user_pre_save(sender, instance, **kwargs):
    """
    Handle actions before a user is saved.
    """
    if instance.pk:  # Existing user
        try:
            old_instance = User.objects.get(pk=instance.pk)

            # Check for password change
            if old_instance.password != instance.password:
                instance.password_changed_at = timezone.now()
                instance.requires_password_change = False

                # Log password change
                UserAuditLog.objects.create(
                    user=instance,
                    action="password_change",
                    description="Password changed",
                    severity="medium",
                )

        except User.DoesNotExist:
            pass


@receiver(post_save, sender=UserRole)
def handle_role_post_save(sender, instance, created, **kwargs):
    """
    Handle actions after a role is created or updated.
    """
    if created:
        logger.info(f"New role created: {instance.name}")

        # Log role creation
        UserAuditLog.objects.create(
            action="role_create",
            description=f"Role '{instance.name}' created",
            severity="low",
            extra_data={
                "role_name": instance.name,
                "role_id": instance.id,
                "is_system_role": instance.is_system_role,
            },
        )
    else:
        # Clear cache for all users with this role
        instance._clear_user_caches()

        logger.info(f"Role updated: {instance.name}")


@receiver(post_delete, sender=UserRole)
def handle_role_post_delete(sender, instance, **kwargs):
    """
    Handle actions after a role is deleted.
    """
    # Clear cache for all users who had this role
    instance._clear_user_caches()

    # Log role deletion
    UserAuditLog.objects.create(
        action="role_delete",
        description=f"Role '{instance.name}' deleted",
        severity="medium",
        extra_data={"role_name": instance.name, "role_id": instance.id},
    )

    logger.info(f"Role deleted: {instance.name}")


@receiver(post_save, sender=UserRoleAssignment)
def handle_role_assignment_post_save(sender, instance, created, **kwargs):
    """
    Handle actions after a role assignment is created or updated.
    """
    # Clear user cache
    instance._clear_user_cache()

    if created:
        # Log role assignment
        UserAuditLog.objects.create(
            user=instance.user,
            action="role_assign",
            description=f"Role '{instance.role.name}' assigned",
            performed_by=instance.assigned_by,
            severity="low",
            extra_data={
                "role_name": instance.role.name,
                "role_id": instance.role.id,
                "expires_at": (
                    instance.expires_at.isoformat() if instance.expires_at else None
                ),
            },
        )

        logger.info(
            f"Role '{instance.role.name}' assigned to user '{instance.user.username}'"
        )

    else:
        # Handle status changes
        if not instance.is_active:
            UserAuditLog.objects.create(
                user=instance.user,
                action="role_remove",
                description=f"Role '{instance.role.name}' removed/deactivated",
                severity="low",
                extra_data={
                    "role_name": instance.role.name,
                    "role_id": instance.role.id,
                },
            )


@receiver(post_delete, sender=UserRoleAssignment)
def handle_role_assignment_post_delete(sender, instance, **kwargs):
    """
    Handle actions after a role assignment is deleted.
    """
    # Clear user cache
    cache.delete_many(
        [f"user_permissions_{instance.user.pk}", f"user_roles_{instance.user.pk}"]
    )

    # Log role removal
    UserAuditLog.objects.create(
        user=instance.user,
        action="role_remove",
        description=f"Role '{instance.role.name}' assignment deleted",
        severity="low",
        extra_data={"role_name": instance.role.name, "role_id": instance.role.id},
    )

    logger.info(
        f"Role assignment deleted: '{instance.role.name}' from user '{instance.user.username}'"
    )


# src/accounts/validators.py

import re
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.contrib.auth import get_user_model

User = get_user_model()


def validate_username(username):
    """
    Validate username format and uniqueness.
    """
    # Check format
    if not re.match(r"^[a-zA-Z0-9_]+$", username):
        raise ValidationError(
            _("Username must contain only letters, numbers, and underscores.")
        )

    # Check length
    if len(username) < 3:
        raise ValidationError(_("Username must be at least 3 characters long."))

    if len(username) > 150:
        raise ValidationError(_("Username cannot be longer than 150 characters."))

    # Check for reserved usernames
    reserved_usernames = [
        "admin",
        "administrator",
        "root",
        "system",
        "api",
        "www",
        "mail",
        "email",
        "support",
        "help",
        "info",
        "contact",
        "security",
        "privacy",
        "legal",
        "terms",
        "about",
    ]

    if username.lower() in reserved_usernames:
        raise ValidationError(_("This username is reserved and cannot be used."))


def validate_email_domain(email):
    """
    Validate email domain against allowed/blocked lists.
    """
    domain = email.split("@")[1].lower()

    # Example blocked domains (you would configure this)
    blocked_domains = ["tempmail.com", "10minutemail.com", "guerrillamail.com"]

    if domain in blocked_domains:
        raise ValidationError(_("Email addresses from this domain are not allowed."))

    # You could also implement allowed domains list
    # allowed_domains = ['yourschool.edu', 'partnerschool.edu']
    # if allowed_domains and domain not in allowed_domains:
    #     raise ValidationError(
    #         _('Only email addresses from approved domains are allowed.')
    #     )


def validate_phone_format(phone_number):
    """
    Validate phone number format.
    """
    if not phone_number:
        return

    # Remove common formatting characters
    clean_phone = re.sub(r"[\s\-\(\)]", "", phone_number)

    # Check if it starts with + and contains only digits
    if not re.match(r"^\+?[\d]{10,15}$", clean_phone):
        raise ValidationError(
            _("Phone number must be 10-15 digits and may include country code.")
        )


def validate_password_not_email(password, email=None):
    """
    Ensure password is not similar to email.
    """
    if email and password:
        email_local = email.split("@")[0].lower()
        if password.lower() in email_local or email_local in password.lower():
            raise ValidationError(
                _("Password cannot be similar to your email address.")
            )


def validate_password_not_name(password, first_name=None, last_name=None):
    """
    Ensure password is not similar to user's name.
    """
    if password:
        password_lower = password.lower()

        if first_name and first_name.lower() in password_lower:
            raise ValidationError(_("Password cannot contain your first name."))

        if last_name and last_name.lower() in password_lower:
            raise ValidationError(_("Password cannot contain your last name."))


def validate_password_not_username(password, username=None):
    """
    Ensure password is not similar to username.
    """
    if password and username:
        if password.lower() in username.lower() or username.lower() in password.lower():
            raise ValidationError(_("Password cannot be similar to your username."))


def validate_role_permissions(permissions):
    """
    Validate role permissions structure.
    """
    from .constants import PERMISSION_SCOPES

    if not isinstance(permissions, dict):
        raise ValidationError(_("Permissions must be a dictionary."))

    for resource, actions in permissions.items():
        if resource not in PERMISSION_SCOPES:
            raise ValidationError(_(f"Invalid resource: {resource}"))

        if not isinstance(actions, list):
            raise ValidationError(_(f"Actions for {resource} must be a list."))

        valid_actions = list(PERMISSION_SCOPES[resource].keys())
        for action in actions:
            if action not in valid_actions:
                raise ValidationError(
                    _(f'Invalid action "{action}" for resource "{resource}".')
                )


def validate_image_file(file):
    """
    Validate image file upload.
    """
    if not file:
        return

    # Check file size (2MB max)
    max_size = 2 * 1024 * 1024  # 2MB
    if file.size > max_size:
        raise ValidationError(_("Image file size cannot exceed 2MB."))

    # Check file type
    allowed_types = ["image/jpeg", "image/png", "image/jpg", "image/gif"]
    if hasattr(file, "content_type") and file.content_type not in allowed_types:
        raise ValidationError(_("Only JPEG, PNG, and GIF image files are allowed."))

    # Check file extension
    if hasattr(file, "name"):
        ext = file.name.split(".")[-1].lower() if "." in file.name else ""
        allowed_extensions = ["jpg", "jpeg", "png", "gif"]
        if ext not in allowed_extensions:
            raise ValidationError(
                _("File must have a valid image extension (.jpg, .png, .gif).")
            )


def validate_csv_file(file):
    """
    Validate CSV file upload.
    """
    if not file:
        return

    # Check file size (5MB max for CSV)
    max_size = 5 * 1024 * 1024  # 5MB
    if file.size > max_size:
        raise ValidationError(_("CSV file size cannot exceed 5MB."))

    # Check file extension
    if hasattr(file, "name"):
        if not file.name.lower().endswith(".csv"):
            raise ValidationError(_("File must be a CSV file with .csv extension."))

    # Check content type
    if hasattr(file, "content_type"):
        allowed_types = ["text/csv", "application/csv", "text/plain"]
        if file.content_type not in allowed_types:
            raise ValidationError(
                _("Invalid file type. Please upload a valid CSV file.")
            )


def validate_date_not_future(date_value):
    """
    Validate that date is not in the future.
    """
    if date_value:
        from django.utils import timezone

        if date_value > timezone.now().date():
            raise ValidationError(_("Date cannot be in the future."))


def validate_date_not_too_old(date_value, max_years=150):
    """
    Validate that date is not too far in the past.
    """
    if date_value:
        from django.utils import timezone
        from datetime import timedelta

        max_age = timezone.now().date() - timedelta(days=max_years * 365)
        if date_value < max_age:
            raise ValidationError(_(f"Date cannot be more than {max_years} years ago."))


def validate_age_range(birth_date, min_age=13, max_age=120):
    """
    Validate age is within acceptable range.
    """
    if birth_date:
        from django.utils import timezone
        from datetime import date

        today = date.today()
        age = (
            today.year
            - birth_date.year
            - ((today.month, today.day) < (birth_date.month, birth_date.day))
        )

        if age < min_age:
            raise ValidationError(_(f"User must be at least {min_age} years old."))

        if age > max_age:
            raise ValidationError(_(f"Please enter a valid birth date."))


def validate_unique_email(email, exclude_user=None):
    """
    Validate email uniqueness.
    """
    queryset = User.objects.filter(email__iexact=email)

    if exclude_user:
        queryset = queryset.exclude(pk=exclude_user.pk)

    if queryset.exists():
        raise ValidationError(_("A user with this email address already exists."))


def validate_unique_phone(phone_number, exclude_user=None):
    """
    Validate phone number uniqueness.
    """
    if not phone_number:
        return

    # Normalize phone number
    clean_phone = re.sub(r"[\s\-\(\)]", "", phone_number)

    queryset = User.objects.filter(phone_number__icontains=clean_phone)

    if exclude_user:
        queryset = queryset.exclude(pk=exclude_user.pk)

    if queryset.exists():
        raise ValidationError(_("A user with this phone number already exists."))


def validate_role_assignment_dates(assigned_date, expires_at):
    """
    Validate role assignment dates.
    """
    if assigned_date and expires_at:
        if expires_at <= assigned_date:
            raise ValidationError(_("Expiry date must be after assignment date."))

    if expires_at:
        from django.utils import timezone

        if expires_at <= timezone.now():
            raise ValidationError(_("Expiry date must be in the future."))


def validate_json_structure(value, required_keys=None):
    """
    Validate JSON field structure.
    """
    if not isinstance(value, dict):
        raise ValidationError(_("Value must be a valid JSON object."))

    if required_keys:
        missing_keys = set(required_keys) - set(value.keys())
        if missing_keys:
            raise ValidationError(
                _(f'Missing required keys: {", ".join(missing_keys)}')
            )


class PasswordValidator:
    """
    Enhanced password validator.
    """

    def __init__(
        self,
        min_length=8,
        require_uppercase=True,
        require_lowercase=True,
        require_digits=True,
        require_symbols=True,
    ):
        self.min_length = min_length
        self.require_uppercase = require_uppercase
        self.require_lowercase = require_lowercase
        self.require_digits = require_digits
        self.require_symbols = require_symbols

    def validate(self, password, user=None):
        """Validate password according to policy."""
        errors = []

        # Length check
        if len(password) < self.min_length:
            errors.append(
                _(f"Password must be at least {self.min_length} characters long.")
            )

        # Character requirements
        if self.require_uppercase and not any(c.isupper() for c in password):
            errors.append(_("Password must contain at least one uppercase letter."))

        if self.require_lowercase and not any(c.islower() for c in password):
            errors.append(_("Password must contain at least one lowercase letter."))

        if self.require_digits and not any(c.isdigit() for c in password):
            errors.append(_("Password must contain at least one digit."))

        if self.require_symbols and not any(
            c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password
        ):
            errors.append(_("Password must contain at least one special character."))

        # User-specific checks
        if user:
            if user.email:
                validate_password_not_email(password, user.email)

            if user.username:
                validate_password_not_username(password, user.username)

            if user.first_name:
                validate_password_not_name(password, user.first_name, user.last_name)

        if errors:
            raise ValidationError(errors)

    def get_help_text(self):
        """Return help text for password requirements."""
        requirements = [f"Password must be at least {self.min_length} characters long"]

        if self.require_uppercase:
            requirements.append("contain at least one uppercase letter")

        if self.require_lowercase:
            requirements.append("contain at least one lowercase letter")

        if self.require_digits:
            requirements.append("contain at least one digit")

        if self.require_symbols:
            requirements.append("contain at least one special character")

        return _("Password requirements: ") + ", ".join(requirements) + "."
