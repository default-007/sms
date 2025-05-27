# signals.py
from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.cache import cache

from .models import SystemSetting
from .services import AuditService

User = get_user_model()


@receiver(post_save, sender=SystemSetting)
def clear_setting_cache(sender, instance, **kwargs):
    """Clear cache when system setting is updated"""
    from .services import ConfigurationService

    cache_key = f"{ConfigurationService.CACHE_PREFIX}{instance.setting_key}"
    cache.delete(cache_key)

    logger.info(f"Cleared cache for system setting: {instance.setting_key}")


@receiver(post_save, sender=User)
def log_user_creation(sender, instance, created, **kwargs):
    """Log user creation"""
    if created:
        AuditService.log_action(
            action="create",
            content_object=instance,
            description=f"User account created: {instance.username}",
            module_name="accounts",
        )


@receiver(post_delete, sender=User)
def log_user_deletion(sender, instance, **kwargs):
    """Log user deletion"""
    AuditService.log_action(
        action="delete",
        description=f"User account deleted: {instance.username}",
        data_before={
            "username": instance.username,
            "email": instance.email,
            "first_name": instance.first_name,
            "last_name": instance.last_name,
        },
        module_name="accounts",
    )


@receiver(pre_save, sender=User)
def track_user_changes(sender, instance, **kwargs):
    """Track changes to user accounts"""
    if instance.pk:  # Only for existing users
        try:
            old_instance = User.objects.get(pk=instance.pk)
            changes = {}

            # Track important field changes
            tracked_fields = [
                "username",
                "email",
                "first_name",
                "last_name",
                "is_active",
                "is_staff",
                "is_superuser",
            ]

            for field in tracked_fields:
                old_value = getattr(old_instance, field, None)
                new_value = getattr(instance, field, None)

                if old_value != new_value:
                    changes[field] = {"old": old_value, "new": new_value}

            if changes:
                # Store changes in instance for post_save signal
                instance._tracked_changes = changes

        except User.DoesNotExist:
            pass


@receiver(post_save, sender=User)
def log_user_changes(sender, instance, created, **kwargs):
    """Log user changes (from pre_save tracking)"""
    if not created and hasattr(instance, "_tracked_changes"):
        changes = instance._tracked_changes

        AuditService.log_action(
            action="update",
            content_object=instance,
            description=f"User account updated: {instance.username}",
            data_after=changes,
            module_name="accounts",
        )

        # Clean up temporary attribute
        delattr(instance, "_tracked_changes")


# Auto-create user groups if they don't exist
@receiver(post_save, sender=User)
def create_default_groups(sender, instance, created, **kwargs):
    """Create default user groups if they don't exist"""
    if created and instance.is_superuser:
        default_groups = [
            "System Administrators",
            "School Administrators",
            "Teachers",
            "Parents",
            "Students",
            "Staff",
        ]

        for group_name in default_groups:
            Group.objects.get_or_create(name=group_name)
