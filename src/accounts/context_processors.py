# Fix for src/accounts/context_processors.py

from django.core.cache import cache
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


def user_roles(request):
    """Context processor for user roles with safe cache handling."""
    if not request.user.is_authenticated:
        return {"user_roles": []}

    try:
        # Use safe cache method
        roles = get_user_roles_safe(request.user)
        return {"user_roles": roles}
    except Exception as e:
        logger.warning(f"Error getting user roles: {e}")
        return {"user_roles": []}


def get_user_roles_safe(user):
    """Safely get user roles with cache fallback."""
    cache_key = f"user_roles_{user.id}"
    timeout = getattr(settings, "CACHE_TIMEOUTS", {}).get("user_roles", 3600)

    try:
        # Try to get from cache
        roles = cache.get(cache_key)
        if roles is not None:
            return roles
    except Exception as e:
        logger.warning(f"Cache get failed for user roles: {e}")

    # Fallback to database
    try:
        if hasattr(user, "get_assigned_roles"):
            roles = user.get_assigned_roles_safe()  # Use safe method
        else:
            roles = []

        # Try to cache the result
        try:
            cache.set(cache_key, roles, timeout)
        except Exception as e:
            logger.warning(f"Cache set failed for user roles: {e}")

        return roles
    except Exception as e:
        logger.error(f"Error fetching user roles from database: {e}")
        return []


def user_permissions(request):
    """Context processor for user permissions with safe cache handling."""
    if not request.user.is_authenticated:
        return {"user_permissions": []}

    try:
        permissions = get_user_permissions_safe(request.user)
        return {"user_permissions": permissions}
    except Exception as e:
        logger.warning(f"Error getting user permissions: {e}")
        return {"user_permissions": []}


def get_user_permissions_safe(user):
    """Safely get user permissions with cache fallback."""
    cache_key = f"user_permissions_{user.id}"
    timeout = getattr(settings, "CACHE_TIMEOUTS", {}).get("user_permissions", 3600)

    try:
        permissions = cache.get(cache_key)
        if permissions is not None:
            return permissions
    except Exception as e:
        logger.warning(f"Cache get failed for user permissions: {e}")

    # Fallback to database
    try:
        permissions = list(user.get_all_permissions())

        try:
            cache.set(cache_key, permissions, timeout)
        except Exception as e:
            logger.warning(f"Cache set failed for user permissions: {e}")

        return permissions
    except Exception as e:
        logger.error(f"Error fetching user permissions: {e}")
        return []
