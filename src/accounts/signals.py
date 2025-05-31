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
