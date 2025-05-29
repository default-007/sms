# src/api/signals.py
"""API Signals"""

import logging

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

User = get_user_model()
logger = logging.getLogger(__name__)


@receiver(post_save)
def clear_model_cache(sender, instance, **kwargs):
    """Clear related cache when model is saved"""
    try:
        model_name = sender.__name__.lower()
        cache_patterns = [
            f"{model_name}_list_*",
            f"{model_name}_detail_{instance.pk}",
            f"user_perm_{instance.user.pk}_*" if hasattr(instance, "user") else None,
        ]

        for pattern in cache_patterns:
            if pattern:
                # This is a simplified approach
                # In production, consider using cache versioning or more sophisticated cache invalidation
                cache.delete_pattern(pattern)

    except Exception as e:
        logger.warning(f"Failed to clear cache for {sender.__name__}: {e}")


@receiver(post_delete)
def clear_model_cache_on_delete(sender, instance, **kwargs):
    """Clear related cache when model is deleted"""
    clear_model_cache(sender, instance, **kwargs)
