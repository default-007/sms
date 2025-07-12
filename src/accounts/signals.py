from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import UserRole, UserRoleAssignment
from .services import RoleService

User = get_user_model()


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """
    Signal to handle actions when a user is created.
    """
    if created:
        # Create default roles if they don't exist
        RoleService.create_default_roles()


@receiver(post_save, sender=UserRole)
def update_role_assignments(sender, instance, **kwargs):
    """
    Signal to handle actions when a role is updated.
    """
    # This could be used to update caches, permissions, etc.
    pass


@receiver(post_delete, sender=UserRole)
def handle_role_delete(sender, instance, **kwargs):
    """
    Signal to handle actions when a role is deleted.
    """
    # Clean up any related records or update caches
    pass


@receiver([post_save, post_delete], sender=User)
def clear_user_cache_on_change(sender, instance, **kwargs):
    """Clear user cache when user data changes."""
    try:
        instance.clear_user_cache()
    except Exception as e:
        logger.warning(f"Failed to clear cache for user {instance.id}: {e}")


@receiver([post_save, post_delete], sender=UserRoleAssignment)
def clear_user_cache_on_role_change(sender, instance, **kwargs):
    """Clear user cache when role assignments change."""
    try:
        instance.user.clear_user_cache()
    except Exception as e:
        logger.warning(f"Failed to clear cache after role change: {e}")
