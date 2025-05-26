from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import AuditLog, SystemSetting
from .services import SystemSettingService


# Initialize default settings when the app is ready
@receiver(post_save, sender=SystemSetting)
def initialize_settings(sender, **kwargs):
    """Initialize default settings when the first setting is created."""
    if kwargs.get("created", False):
        transaction.on_commit(SystemSettingService.initialize_default_settings)


# Create audit logs for user model changes
User = get_user_model()


@receiver(post_save, sender=User)
def log_user_changes(sender, instance, created, **kwargs):
    """Log when a user is created or updated."""
    if not getattr(instance, "_skip_audit_log", False):
        AuditLog.objects.create(
            user=instance,
            action="create" if created else "update",
            entity_type="user",
            entity_id=instance.id,
            # Don't store sensitive user data in logs
            data_after={"username": instance.username, "is_active": instance.is_active},
        )


@receiver(post_delete, sender=User)
def log_user_deletion(sender, instance, **kwargs):
    """Log when a user is deleted."""
    if not getattr(instance, "_skip_audit_log", False):
        AuditLog.objects.create(
            user=None,  # User is being deleted
            action="delete",
            entity_type="user",
            entity_id=instance.id,
            data_before={"username": instance.username, "email": instance.email},
        )


# Signal handler to sync settings with cache
@receiver(post_save, sender=SystemSetting)
def update_settings_cache(sender, instance, **kwargs):
    """Update settings cache when a setting is changed."""
    # This could be implemented with caching if needed
    pass
