# src/accounts/cache_utils.py

import hashlib
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import Count, Q
from django.utils import timezone

from .models import UserRole, UserRoleAssignment, UserAuditLog

logger = logging.getLogger(__name__)
User = get_user_model()


class CacheManager:
    """Advanced caching utilities for accounts module."""

    # Cache timeouts (in seconds)
    USER_PERMISSIONS_TIMEOUT = getattr(
        settings, "USER_PERMISSIONS_CACHE_TIMEOUT", 3600
    )  # 1 hour
    USER_ROLES_TIMEOUT = getattr(settings, "USER_ROLES_CACHE_TIMEOUT", 3600)  # 1 hour
    USER_STATS_TIMEOUT = getattr(settings, "USER_STATS_CACHE_TIMEOUT", 300)  # 5 minutes
    ANALYTICS_TIMEOUT = getattr(settings, "ANALYTICS_CACHE_TIMEOUT", 900)  # 15 minutes
    SESSION_DATA_TIMEOUT = getattr(
        settings, "SESSION_DATA_CACHE_TIMEOUT", 1800
    )  # 30 minutes

    # Cache key prefixes
    USER_PERMISSIONS_PREFIX = "user_permissions"
    USER_ROLES_PREFIX = "user_roles"
    USER_STATS_PREFIX = "user_stats"
    ROLE_STATS_PREFIX = "role_stats"
    ANALYTICS_PREFIX = "analytics"
    SESSION_PREFIX = "session_data"
    SECURITY_PREFIX = "security"

    @staticmethod
    def _make_key(*parts) -> str:
        """Generate cache key from parts."""
        key = ":".join(str(part) for part in parts)
        # Ensure key length doesn't exceed memcached limit
        if len(key) > 200:
            key_hash = hashlib.md5(key.encode()).hexdigest()
            return f"hash:{key_hash}"
        return key

    @staticmethod
    def _serialize_data(data: Any) -> str:
        """Serialize data for caching."""
        return json.dumps(data, cls=DjangoJSONEncoder)

    @staticmethod
    def _deserialize_data(data: str) -> Any:
        """Deserialize cached data."""
        try:
            return json.loads(data)
        except (json.JSONDecodeError, TypeError):
            return None

    # User permissions caching
    @staticmethod
    def get_user_permissions(user_id: int) -> Optional[Dict[str, List[str]]]:
        """Get cached user permissions."""
        cache_key = CacheManager._make_key(
            CacheManager.USER_PERMISSIONS_PREFIX, user_id
        )
        return cache.get(cache_key)

    @staticmethod
    def set_user_permissions(user_id: int, permissions: Dict[str, List[str]]):
        """Cache user permissions."""
        cache_key = CacheManager._make_key(
            CacheManager.USER_PERMISSIONS_PREFIX, user_id
        )
        cache.set(cache_key, permissions, CacheManager.USER_PERMISSIONS_TIMEOUT)

    @staticmethod
    def clear_user_permissions(user_id: int):
        """Clear cached user permissions."""
        cache_key = CacheManager._make_key(
            CacheManager.USER_PERMISSIONS_PREFIX, user_id
        )
        cache.delete(cache_key)

    # User roles caching
    @staticmethod
    def get_user_roles(user_id: int) -> Optional[List[Dict[str, Any]]]:
        """Get cached user roles."""
        cache_key = CacheManager._make_key(CacheManager.USER_ROLES_PREFIX, user_id)
        return cache.get(cache_key)

    @staticmethod
    def set_user_roles(user_id: int, roles: List[Dict[str, Any]]):
        """Cache user roles."""
        cache_key = CacheManager._make_key(CacheManager.USER_ROLES_PREFIX, user_id)
        cache.set(cache_key, roles, CacheManager.USER_ROLES_TIMEOUT)

    @staticmethod
    def clear_user_roles(user_id: int):
        """Clear cached user roles."""
        cache_key = CacheManager._make_key(CacheManager.USER_ROLES_PREFIX, user_id)
        cache.delete(cache_key)

    @staticmethod
    def clear_user_cache(user_id: int):
        """Clear all cached data for a user."""
        CacheManager.clear_user_permissions(user_id)
        CacheManager.clear_user_roles(user_id)

        # Clear additional user-specific caches
        cache_keys = [
            CacheManager._make_key(CacheManager.USER_STATS_PREFIX, user_id),
            CacheManager._make_key(CacheManager.SESSION_PREFIX, user_id),
            CacheManager._make_key(CacheManager.SECURITY_PREFIX, user_id),
        ]
        cache.delete_many(cache_keys)

    # Role-based cache invalidation
    @staticmethod
    def clear_role_cache(role_id: int):
        """Clear cache for all users with a specific role."""
        try:
            # Get all users with this role
            user_ids = UserRoleAssignment.objects.filter(
                role_id=role_id, is_active=True
            ).values_list("user_id", flat=True)

            # Clear cache for each user
            for user_id in user_ids:
                CacheManager.clear_user_cache(user_id)

            # Clear role statistics
            cache_key = CacheManager._make_key(CacheManager.ROLE_STATS_PREFIX, role_id)
            cache.delete(cache_key)

            logger.info(
                f"Cleared cache for {len(user_ids)} users affected by role {role_id}"
            )

        except Exception as e:
            logger.error(f"Error clearing role cache: {e}")

    # Statistics caching
    @staticmethod
    def get_user_statistics() -> Optional[Dict[str, Any]]:
        """Get cached user statistics."""
        cache_key = CacheManager._make_key(CacheManager.USER_STATS_PREFIX, "global")
        return cache.get(cache_key)

    @staticmethod
    def set_user_statistics(stats: Dict[str, Any]):
        """Cache user statistics."""
        cache_key = CacheManager._make_key(CacheManager.USER_STATS_PREFIX, "global")
        cache.set(cache_key, stats, CacheManager.USER_STATS_TIMEOUT)

    @staticmethod
    def get_role_statistics() -> Optional[Dict[str, Any]]:
        """Get cached role statistics."""
        cache_key = CacheManager._make_key(CacheManager.ROLE_STATS_PREFIX, "global")
        return cache.get(cache_key)

    @staticmethod
    def set_role_statistics(stats: Dict[str, Any]):
        """Cache role statistics."""
        cache_key = CacheManager._make_key(CacheManager.ROLE_STATS_PREFIX, "global")
        cache.set(cache_key, stats, CacheManager.USER_STATS_TIMEOUT)

    # Analytics caching
    @staticmethod
    def get_analytics_data(
        report_type: str, params_hash: str
    ) -> Optional[Dict[str, Any]]:
        """Get cached analytics data."""
        cache_key = CacheManager._make_key(
            CacheManager.ANALYTICS_PREFIX, report_type, params_hash
        )
        return cache.get(cache_key)

    @staticmethod
    def set_analytics_data(report_type: str, params_hash: str, data: Dict[str, Any]):
        """Cache analytics data."""
        cache_key = CacheManager._make_key(
            CacheManager.ANALYTICS_PREFIX, report_type, params_hash
        )
        cache.set(cache_key, data, CacheManager.ANALYTICS_TIMEOUT)

    @staticmethod
    def generate_params_hash(params: Dict[str, Any]) -> str:
        """Generate hash for parameters to use as cache key."""
        params_str = json.dumps(params, sort_keys=True)
        return hashlib.md5(params_str.encode()).hexdigest()

    # Session data caching
    @staticmethod
    def get_session_data(user_id: int, data_type: str) -> Optional[Any]:
        """Get cached session data."""
        cache_key = CacheManager._make_key(
            CacheManager.SESSION_PREFIX, user_id, data_type
        )
        return cache.get(cache_key)

    @staticmethod
    def set_session_data(user_id: int, data_type: str, data: Any, timeout: int = None):
        """Cache session data."""
        cache_key = CacheManager._make_key(
            CacheManager.SESSION_PREFIX, user_id, data_type
        )
        timeout = timeout or CacheManager.SESSION_DATA_TIMEOUT
        cache.set(cache_key, data, timeout)

    # Security-related caching
    @staticmethod
    def get_security_data(identifier: str, data_type: str) -> Optional[Any]:
        """Get cached security data."""
        cache_key = CacheManager._make_key(
            CacheManager.SECURITY_PREFIX, data_type, identifier
        )
        return cache.get(cache_key)

    @staticmethod
    def set_security_data(
        identifier: str, data_type: str, data: Any, timeout: int = 300
    ):
        """Cache security data with short timeout."""
        cache_key = CacheManager._make_key(
            CacheManager.SECURITY_PREFIX, data_type, identifier
        )
        cache.set(cache_key, data, timeout)

    # Rate limiting cache
    @staticmethod
    def is_rate_limited(identifier: str, action: str, limit: int, window: int) -> bool:
        """Check if action is rate limited."""
        cache_key = CacheManager._make_key("rate_limit", action, identifier)

        current_count = cache.get(cache_key, 0)
        if current_count >= limit:
            return True

        # Increment counter
        try:
            cache.set(cache_key, current_count + 1, window)
        except:
            # If cache set fails, allow the action
            pass

        return False

    @staticmethod
    def get_rate_limit_remaining(identifier: str, action: str, limit: int) -> int:
        """Get remaining rate limit attempts."""
        cache_key = CacheManager._make_key("rate_limit", action, identifier)
        current_count = cache.get(cache_key, 0)
        return max(0, limit - current_count)

    # Bulk cache operations
    @staticmethod
    def warm_user_cache(user_ids: List[int]):
        """Pre-warm cache for multiple users."""
        from .services import RoleService

        try:
            users = User.objects.filter(id__in=user_ids).prefetch_related(
                "role_assignments__role"
            )

            for user in users:
                # Cache permissions
                permissions = RoleService.get_user_permissions(user)
                CacheManager.set_user_permissions(user.id, permissions)

                # Cache roles
                roles = [
                    {
                        "id": role.id,
                        "name": role.name,
                        "description": role.description,
                        "is_system_role": role.is_system_role,
                    }
                    for role in user.get_assigned_roles()
                ]
                CacheManager.set_user_roles(user.id, roles)

            logger.info(f"Warmed cache for {len(users)} users")

        except Exception as e:
            logger.error(f"Error warming user cache: {e}")

    @staticmethod
    def clear_all_user_caches():
        """Clear all user-related caches (use with caution)."""
        try:
            # This is a brute force approach - in production, you might want
            # to maintain a list of cached user IDs
            cache_patterns = [
                f"{CacheManager.USER_PERMISSIONS_PREFIX}:*",
                f"{CacheManager.USER_ROLES_PREFIX}:*",
                f"{CacheManager.USER_STATS_PREFIX}:*",
                f"{CacheManager.SESSION_PREFIX}:*",
            ]

            # Note: This method depends on cache backend supporting pattern deletion
            # For Redis: cache.delete_pattern()
            # For Memcached: Not directly supported

            logger.warning("Clearing all user caches")

        except Exception as e:
            logger.error(f"Error clearing all user caches: {e}")

    # Cache statistics and monitoring
    @staticmethod
    def get_cache_statistics() -> Dict[str, Any]:
        """Get cache usage statistics."""
        try:
            # These statistics depend on your cache backend
            # This is a basic implementation

            # Sample some cache keys to check hit rates
            sample_users = User.objects.values_list("id", flat=True)[:100]

            permissions_hits = 0
            roles_hits = 0

            for user_id in sample_users:
                if CacheManager.get_user_permissions(user_id) is not None:
                    permissions_hits += 1

                if CacheManager.get_user_roles(user_id) is not None:
                    roles_hits += 1

            total_sample = len(sample_users)

            return {
                "sample_size": total_sample,
                "permissions_hit_rate": (
                    (permissions_hits / total_sample * 100) if total_sample > 0 else 0
                ),
                "roles_hit_rate": (
                    (roles_hits / total_sample * 100) if total_sample > 0 else 0
                ),
                "cache_backend": settings.CACHES["default"]["BACKEND"],
                "timestamp": timezone.now().isoformat(),
            }

        except Exception as e:
            logger.error(f"Error getting cache statistics: {e}")
            return {}

    # Background cache maintenance
    @staticmethod
    def cleanup_expired_cache():
        """Clean up expired cache entries (if backend doesn't auto-expire)."""
        try:
            # This depends on your cache backend
            # For backends that don't auto-expire, you might need custom cleanup
            logger.info("Cache cleanup completed")

        except Exception as e:
            logger.error(f"Error during cache cleanup: {e}")

    @staticmethod
    def invalidate_user_on_update(user_id: int, fields_updated: List[str]):
        """Intelligently invalidate cache based on what was updated."""

        # Always clear basic user cache
        CacheManager.clear_user_cache(user_id)

        # If role-related fields changed, clear role statistics
        role_related_fields = ["is_active", "is_staff", "is_superuser"]
        if any(field in role_related_fields for field in fields_updated):
            # Clear global statistics that might be affected
            cache.delete(
                CacheManager._make_key(CacheManager.USER_STATS_PREFIX, "global")
            )
            cache.delete(
                CacheManager._make_key(CacheManager.ROLE_STATS_PREFIX, "global")
            )

        # If security-related fields changed, clear security cache
        security_related_fields = [
            "failed_login_attempts",
            "password",
            "email_verified",
            "phone_verified",
            "two_factor_enabled",
        ]
        if any(field in security_related_fields for field in fields_updated):
            cache.delete(CacheManager._make_key(CacheManager.SECURITY_PREFIX, user_id))


# Decorators for caching
def cache_user_data(timeout: int = None, key_suffix: str = ""):
    """Decorator to cache user-specific data."""

    def decorator(func):
        def wrapper(user, *args, **kwargs):
            if not user or not user.is_authenticated:
                return func(user, *args, **kwargs)

            # Generate cache key
            func_name = func.__name__
            cache_key = CacheManager._make_key("func", func_name, user.id, key_suffix)

            # Try to get from cache
            result = cache.get(cache_key)
            if result is not None:
                return result

            # Execute function and cache result
            result = func(user, *args, **kwargs)
            cache_timeout = timeout or CacheManager.USER_STATS_TIMEOUT
            cache.set(cache_key, result, cache_timeout)

            return result

        return wrapper

    return decorator


def cache_analytics_data(timeout: int = None):
    """Decorator to cache analytics data."""

    def decorator(func):
        def wrapper(*args, **kwargs):
            # Generate cache key from function name and arguments
            func_name = func.__name__
            params_hash = CacheManager.generate_params_hash(
                {"args": args, "kwargs": kwargs}
            )

            cache_key = CacheManager._make_key("analytics_func", func_name, params_hash)

            # Try to get from cache
            result = cache.get(cache_key)
            if result is not None:
                return result

            # Execute function and cache result
            result = func(*args, **kwargs)
            cache_timeout = timeout or CacheManager.ANALYTICS_TIMEOUT
            cache.set(cache_key, result, cache_timeout)

            return result

        return wrapper

    return decorator


# Context manager for cache operations
class CacheTransaction:
    """Context manager for batched cache operations."""

    def __init__(self):
        self.operations = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            # Execute all operations if no exception
            self._execute_operations()

    def set(self, key: str, value: Any, timeout: int = None):
        """Queue a cache set operation."""
        self.operations.append(("set", key, value, timeout))

    def delete(self, key: str):
        """Queue a cache delete operation."""
        self.operations.append(("delete", key))

    def _execute_operations(self):
        """Execute all queued operations."""
        try:
            for operation in self.operations:
                if operation[0] == "set":
                    _, key, value, timeout = operation
                    cache.set(key, value, timeout)
                elif operation[0] == "delete":
                    _, key = operation
                    cache.delete(key)

            logger.debug(f"Executed {len(self.operations)} cache operations")

        except Exception as e:
            logger.error(f"Error executing cache operations: {e}")


# Utility functions
def get_cached_or_compute(
    cache_key: str, compute_func, timeout: int = 300, *args, **kwargs
):
    """Get value from cache or compute and cache it."""
    result = cache.get(cache_key)
    if result is None:
        result = compute_func(*args, **kwargs)
        cache.set(cache_key, result, timeout)
    return result


def invalidate_pattern(pattern: str):
    """Invalidate cache keys matching pattern (Redis only)."""
    try:
        from django_redis import get_redis_connection

        redis_conn = get_redis_connection("default")
        keys = redis_conn.keys(pattern)
        if keys:
            redis_conn.delete(*keys)
            logger.info(
                f"Invalidated {len(keys)} cache keys matching pattern: {pattern}"
            )

    except ImportError:
        logger.warning("django-redis not available, cannot invalidate by pattern")
    except Exception as e:
        logger.error(f"Error invalidating cache pattern {pattern}: {e}")


def warm_frequently_accessed_data():
    """Pre-warm cache with frequently accessed data."""
    try:
        # Warm user statistics
        from .services import UserAnalyticsService

        stats = User.objects.get_statistics()
        CacheManager.set_user_statistics(stats)

        # Warm role statistics
        role_stats = UserRole.objects.with_user_counts().values(
            "id", "name", "user_count", "is_system_role"
        )
        CacheManager.set_role_statistics(list(role_stats))

        # Warm most active users
        active_users = User.objects.filter(
            last_login__gte=timezone.now() - timedelta(days=7)
        ).values_list("id", flat=True)[:50]

        CacheManager.warm_user_cache(list(active_users))

        logger.info("Cache warming completed successfully")

    except Exception as e:
        logger.error(f"Error during cache warming: {e}")
