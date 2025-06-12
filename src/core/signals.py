# core/signals.py
from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.cache import cache
import logging

from .models import SystemSetting
from .services import AuditService

User = get_user_model()
logger = logging.getLogger(__name__)


@receiver(post_save, sender=SystemSetting)
def clear_setting_cache(sender, instance, **kwargs):
    """Clear cache when system setting is updated"""
    from .services import ConfigurationService

    cache_key = f"{ConfigurationService.CACHE_PREFIX}{instance.setting_key}"
    try:
        cache.delete(cache_key)
        logger.info(f"Cleared cache for system setting: {instance.setting_key}")
    except Exception as e:
        logger.warning(f"Failed to clear cache for setting {instance.setting_key}: {e}")


@receiver(post_save, sender=User)
def log_user_creation(sender, instance, created, **kwargs):
    """Log user creation"""
    if created:
        try:
            AuditService.log_action(
                action="create",
                content_object=instance,
                description=f"User account created: {instance.username}",
                module_name="accounts",
            )
        except Exception as e:
            logger.error(f"Failed to log user creation: {e}")


@receiver(post_delete, sender=User)
def log_user_deletion(sender, instance, **kwargs):
    """Log user deletion"""
    try:
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
    except Exception as e:
        logger.error(f"Failed to log user deletion: {e}")


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
        except Exception as e:
            logger.error(f"Error tracking user changes: {e}")


@receiver(post_save, sender=User)
def log_user_changes(sender, instance, created, **kwargs):
    """Log user changes (from pre_save tracking)"""
    if not created and hasattr(instance, "_tracked_changes"):
        try:
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
        except Exception as e:
            logger.error(f"Failed to log user changes: {e}")


@receiver(post_save, sender=User)
def create_default_groups(sender, instance, created, **kwargs):
    """Create default user groups if they don't exist"""
    if created and instance.is_superuser:
        try:
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

            logger.info("Default user groups created/verified")
        except Exception as e:
            logger.error(f"Error creating default groups: {e}")


@receiver(post_save, sender=User)
def handle_user_activation_changes(sender, instance, created, **kwargs):
    """Handle user activation/deactivation"""
    if not created and hasattr(instance, "_tracked_changes"):
        changes = instance._tracked_changes

        if "is_active" in changes:
            old_active = changes["is_active"]["old"]
            new_active = changes["is_active"]["new"]

            if old_active and not new_active:
                # User was deactivated
                try:
                    AuditService.log_action(
                        action="system_action",
                        content_object=instance,
                        description=f"User account deactivated: {instance.username}",
                        module_name="accounts",
                    )
                    # Additional cleanup if needed (e.g., close sessions)
                except Exception as e:
                    logger.error(f"Error handling user deactivation: {e}")

            elif not old_active and new_active:
                # User was activated
                try:
                    AuditService.log_action(
                        action="system_action",
                        content_object=instance,
                        description=f"User account activated: {instance.username}",
                        module_name="accounts",
                    )
                except Exception as e:
                    logger.error(f"Error handling user activation: {e}")


# Signal for cleaning up related data when models are deleted
@receiver(post_delete)
def log_model_deletion(sender, instance, **kwargs):
    """Log deletion of important models"""
    # Only log for specific important models
    important_models = [
        "Student",
        "Teacher",
        "Parent",
        "Class",
        "Grade",
        "Section",
        "AcademicYear",
        "Term",
        "Subject",
        "Exam",
        "Assignment",
    ]

    model_name = sender.__name__
    if model_name in important_models:
        try:
            AuditService.log_action(
                action="delete",
                description=f"{model_name} deleted: {str(instance)}",
                data_before={
                    "model": model_name,
                    "id": instance.pk,
                    "representation": str(instance),
                },
                module_name=sender._meta.app_label,
            )
        except Exception as e:
            logger.error(f"Error logging model deletion: {e}")


# Signal for system setting validation
@receiver(pre_save, sender=SystemSetting)
def validate_system_setting(sender, instance, **kwargs):
    """Validate system settings before saving"""
    try:
        # Validate critical settings
        if instance.setting_key == "system.maintenance_mode":
            # Ensure maintenance mode is boolean
            value = instance.get_typed_value()
            if not isinstance(value, bool):
                logger.warning(f"Invalid maintenance mode value: {value}")

        elif instance.setting_key.startswith("academic."):
            # Validate academic settings
            if "percentage" in instance.setting_key:
                value = instance.get_typed_value()
                if not (0 <= value <= 100):
                    logger.warning(
                        f"Invalid percentage value for {instance.setting_key}: {value}"
                    )

        elif instance.setting_key.startswith("finance."):
            # Validate financial settings
            if "percentage" in instance.setting_key or "fee" in instance.setting_key:
                value = instance.get_typed_value()
                if value < 0:
                    logger.warning(
                        f"Negative value for financial setting {instance.setting_key}: {value}"
                    )

    except Exception as e:
        logger.error(f"Error validating system setting: {e}")


# Signal for cache invalidation on related model changes
@receiver(post_save)
def invalidate_related_cache(sender, instance, **kwargs):
    """Invalidate cache for related data when models change"""
    try:
        # Clear dashboard cache when important models change
        important_models = ["Student", "Teacher", "Class", "Grade", "Section"]

        if sender.__name__ in important_models:
            # Clear dashboard cache
            cache_patterns = ["dashboard_*", "analytics_*", "system_stats_*"]

            for pattern in cache_patterns:
                try:
                    if hasattr(cache, "delete_pattern"):
                        cache.delete_pattern(pattern)
                    else:
                        # Fallback: clear all cache if delete_pattern not available
                        cache.clear()
                        break
                except Exception as e:
                    logger.warning(f"Failed to clear cache pattern {pattern}: {e}")

    except Exception as e:
        logger.error(f"Error invalidating cache: {e}")


# Signal for automatic analytics calculation triggers
@receiver(post_save)
def trigger_analytics_calculation(sender, instance, created, **kwargs):
    """Trigger analytics calculation when relevant data changes"""
    try:
        from .services import ConfigurationService

        # Only trigger if auto-calculation is enabled
        auto_calc_enabled = ConfigurationService.get_setting(
            "analytics.auto_calculation_enabled", True
        )

        if not auto_calc_enabled:
            return

        # Models that should trigger analytics recalculation
        analytics_trigger_models = [
            "StudentExamResult",
            "AssignmentSubmission",
            "Attendance",
            "Invoice",
            "Payment",
        ]

        if sender.__name__ in analytics_trigger_models:
            # Queue analytics calculation (would typically use Celery)
            logger.info(f"Analytics calculation triggered by {sender.__name__} change")

            # Here you would typically queue a Celery task:
            # from .tasks import calculate_analytics
            # calculate_analytics.delay(force_recalculate=False)

    except Exception as e:
        logger.error(f"Error triggering analytics calculation: {e}")


# Signal for system health monitoring
@receiver(post_save, sender=User)
def update_user_activity_metrics(sender, instance, **kwargs):
    """Update user activity metrics when users are created or modified"""
    try:
        # Update active user count in cache
        active_users_count = User.objects.filter(is_active=True).count()
        cache.set("active_users_count", active_users_count, timeout=300)  # 5 minutes

    except Exception as e:
        logger.error(f"Error updating user activity metrics: {e}")


# Signal for email notifications on critical system events
@receiver(post_save, sender=SystemSetting)
def notify_critical_setting_changes(sender, instance, **kwargs):
    """Send notifications for critical system setting changes"""
    try:
        critical_settings = [
            "system.maintenance_mode",
            "system.auto_backup_enabled",
            "security.max_login_attempts",
            "academic.passing_grade_percentage",
        ]

        if instance.setting_key in critical_settings:
            logger.warning(
                f"Critical system setting changed: {instance.setting_key} = {instance.get_typed_value()}"
            )

            # Here you would typically send email notifications to administrators
            # from .tasks import send_admin_notification
            # send_admin_notification.delay(
            #     subject=f"Critical Setting Changed: {instance.setting_key}",
            #     message=f"Setting {instance.setting_key} was changed to {instance.get_typed_value()}"
            # )

    except Exception as e:
        logger.error(f"Error sending critical setting notification: {e}")


# Signal for cleanup when users are deleted
@receiver(post_delete, sender=User)
def cleanup_user_data(sender, instance, **kwargs):
    """Clean up user-related data when user is deleted"""
    try:
        # Clear any cached data for this user
        user_cache_keys = [
            f"user_dashboard_{instance.id}",
            f"user_permissions_{instance.id}",
            f"user_activity_{instance.id}",
        ]

        for key in user_cache_keys:
            try:
                cache.delete(key)
            except Exception as e:
                logger.warning(f"Failed to clear cache key {key}: {e}")

        logger.info(f"Cleaned up data for deleted user: {instance.username}")

    except Exception as e:
        logger.error(f"Error cleaning up user data: {e}")
