# Create this file: src/core/utils/cache_utils.py

import logging
from django.core.cache import cache
from django.conf import settings

logger = logging.getLogger(__name__)


def safe_cache_get(key, default=None):
    """
    Safely get value from cache with fallback.
    """
    try:
        return cache.get(key, default)
    except Exception as e:
        logger.warning(f"Cache get failed for key {key}: {e}")
        return default


def safe_cache_set(key, value, timeout=None):
    """
    Safely set value in cache with error handling.
    """
    try:
        cache.set(key, value, timeout)
        return True
    except Exception as e:
        logger.warning(f"Cache set failed for key {key}: {e}")
        return False


def safe_cache_delete(key):
    """
    Safely delete value from cache.
    """
    try:
        cache.delete(key)
        return True
    except Exception as e:
        logger.warning(f"Cache delete failed for key {key}: {e}")
        return False


def safe_delete_pattern(pattern):
    """
    Safely delete cache keys matching pattern.
    Works with both django-redis and fallback options.
    """
    try:
        # Try django-redis method first
        from django_redis import get_redis_connection

        redis_conn = get_redis_connection("default")
        keys = redis_conn.keys(pattern)
        if keys:
            redis_conn.delete(*keys)
            logger.info(f"Deleted {len(keys)} cache keys matching pattern: {pattern}")
            return len(keys)
    except ImportError:
        logger.warning("django-redis not available, skipping pattern deletion")
    except Exception as e:
        logger.warning(f"Pattern deletion failed for {pattern}: {e}")

    return 0


def clear_user_cache(user_id):
    """
    Clear all cache entries for a specific user.
    """
    patterns = [
        f"user_roles_{user_id}",
        f"user_permissions_{user_id}",
        f"user_profile_{user_id}",
        f"user_sessions_{user_id}",
    ]

    for pattern in patterns:
        safe_cache_delete(pattern)


def is_redis_available():
    """
    Check if Redis is available.
    """
    try:
        from django_redis import get_redis_connection

        redis_conn = get_redis_connection("default")
        redis_conn.ping()
        return True
    except Exception:
        return False


class CacheManager:
    """
    Centralized cache management with fallback handling.
    """

    @staticmethod
    def get_or_set(key, callable_func, timeout=300):
        """
        Get from cache or set using callable function.
        """
        try:
            value = cache.get(key)
            if value is None:
                value = callable_func()
                cache.set(key, value, timeout)
            return value
        except Exception as e:
            logger.warning(f"Cache operation failed for {key}: {e}")
            return callable_func()

    @staticmethod
    def invalidate_user_cache(user_id):
        """
        Invalidate all cache entries for a user.
        """
        clear_user_cache(user_id)

    @staticmethod
    def get_user_roles(user_id, fetch_func):
        """
        Get user roles from cache or database.
        """
        cache_key = f"user_roles_{user_id}"
        return CacheManager.get_or_set(
            cache_key,
            fetch_func,
            timeout=getattr(settings, "CACHE_TIMEOUTS", {}).get("user_roles", 3600),
        )
