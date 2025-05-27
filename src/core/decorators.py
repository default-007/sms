# decorators.py
from functools import wraps
from django.core.cache import cache
from django.http import JsonResponse, HttpResponseForbidden
from django.contrib.auth.decorators import user_passes_test
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.conf import settings
import time
import logging

from .services import SecurityService, AuditService

logger = logging.getLogger(__name__)


def audit_action(action: str = None, description: str = None, module_name: str = None):
    """Decorator to automatically log actions to audit trail"""

    def decorator(func):
        @wraps(func)
        def wrapper(request, *args, **kwargs):
            start_time = time.time()

            # Execute the function
            result = func(request, *args, **kwargs)

            # Calculate duration
            duration_ms = int((time.time() - start_time) * 1000)

            # Log the action
            try:
                AuditService.log_action(
                    user=(
                        request.user
                        if hasattr(request, "user") and request.user.is_authenticated
                        else None
                    ),
                    action=action or "view",
                    description=description or f"Executed {func.__name__}",
                    ip_address=(
                        request.META.get("REMOTE_ADDR")
                        if hasattr(request, "META")
                        else None
                    ),
                    user_agent=(
                        request.META.get("HTTP_USER_AGENT", "")
                        if hasattr(request, "META")
                        else ""
                    ),
                    module_name=module_name or func.__module__.split(".")[0],
                    view_name=func.__name__,
                    duration_ms=duration_ms,
                )
            except Exception as e:
                logger.error(f"Error logging audit action: {str(e)}")

            return result

        return wrapper

    return decorator


def rate_limit(max_attempts: int = 5, window_minutes: int = 15, identifier_func=None):
    """Decorator to apply rate limiting to views"""

    def decorator(func):
        @wraps(func)
        def wrapper(request, *args, **kwargs):
            # Get identifier for rate limiting
            if identifier_func:
                identifier = identifier_func(request)
            else:
                identifier = request.META.get("REMOTE_ADDR", "unknown")
                if hasattr(request, "user") and request.user.is_authenticated:
                    identifier = str(request.user.id)

            # Check rate limit
            action_name = f"{func.__module__}.{func.__name__}"
            if not SecurityService.check_rate_limit(
                identifier, action_name, max_attempts, window_minutes
            ):
                SecurityService.log_security_event(
                    "rate_limit_exceeded",
                    user=(
                        request.user
                        if hasattr(request, "user") and request.user.is_authenticated
                        else None
                    ),
                    ip_address=(
                        request.META.get("REMOTE_ADDR")
                        if hasattr(request, "META")
                        else None
                    ),
                    details={"function": action_name, "identifier": identifier},
                )

                if request.path.startswith("/api/"):
                    return JsonResponse(
                        {"error": "Rate limit exceeded. Please try again later."},
                        status=429,
                    )
                else:
                    return HttpResponseForbidden(
                        "Rate limit exceeded. Please try again later."
                    )

            return func(request, *args, **kwargs)

        return wrapper

    return decorator


def cache_result(timeout: int = 3600, key_func=None):
    """Decorator to cache function results"""

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                cache_key = (
                    f"{func.__module__}.{func.__name__}:{hash(str(args) + str(kwargs))}"
                )

            # Try to get from cache
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                return cached_result

            # Execute function and cache result
            result = func(*args, **kwargs)
            cache.set(cache_key, result, timeout)

            return result

        return wrapper

    return decorator


def require_role(*allowed_roles):
    """Decorator to require specific user roles"""

    def decorator(func):
        @wraps(func)
        def wrapper(request, *args, **kwargs):
            if not hasattr(request, "user") or not request.user.is_authenticated:
                if request.path.startswith("/api/"):
                    return JsonResponse(
                        {"error": "Authentication required"}, status=401
                    )
                else:
                    return HttpResponseForbidden("Authentication required")

            user = request.user
            user_roles = []

            # Check user roles
            if user.is_superuser:
                user_roles.append("superuser")

            if hasattr(user, "teacher") and user.teacher.status == "active":
                user_roles.append("teacher")

            if hasattr(user, "parent"):
                user_roles.append("parent")

            if hasattr(user, "student"):
                user_roles.append("student")

            # Check group memberships
            user_groups = user.groups.values_list("name", flat=True)
            if "System Administrators" in user_groups:
                user_roles.append("system_admin")
            if "School Administrators" in user_groups:
                user_roles.append("school_admin")

            # Check if user has any of the allowed roles
            if not any(role in user_roles for role in allowed_roles):
                SecurityService.log_security_event(
                    "unauthorized_access_attempt",
                    user=user,
                    ip_address=request.META.get("REMOTE_ADDR"),
                    details={"required_roles": allowed_roles, "user_roles": user_roles},
                )

                if request.path.startswith("/api/"):
                    return JsonResponse(
                        {"error": "Insufficient permissions"}, status=403
                    )
                else:
                    return HttpResponseForbidden("Insufficient permissions")

            return func(request, *args, **kwargs)

        return wrapper

    return decorator


def system_admin_required(func):
    """Decorator to require system admin role"""
    return require_role("superuser", "system_admin")(func)


def school_admin_required(func):
    """Decorator to require school admin role or higher"""
    return require_role("superuser", "system_admin", "school_admin")(func)


def teacher_required(func):
    """Decorator to require teacher role or higher"""
    return require_role("superuser", "system_admin", "school_admin", "teacher")(func)


def performance_monitor(threshold_ms: int = 1000):
    """Decorator to monitor function performance"""

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()

            result = func(*args, **kwargs)

            duration_ms = int((time.time() - start_time) * 1000)

            if duration_ms > threshold_ms:
                logger.warning(
                    f"Slow function execution: {func.__module__}.{func.__name__} "
                    f"took {duration_ms}ms (threshold: {threshold_ms}ms)"
                )

            return result

        return wrapper

    return decorator


def exception_handler(default_return=None, log_exception=True):
    """Decorator to handle exceptions gracefully"""

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if log_exception:
                    logger.error(
                        f"Exception in {func.__module__}.{func.__name__}: {str(e)}",
                        exc_info=True,
                    )

                if default_return is not None:
                    return default_return

                # Re-raise if no default return specified
                raise

        return wrapper

    return decorator


# Method decorators for class-based views
class MethodDecorator:
    """Class to create method decorators for class-based views"""

    @staticmethod
    def audit_action(
        action: str = None, description: str = None, module_name: str = None
    ):
        """Method decorator for audit logging"""
        return method_decorator(audit_action(action, description, module_name))

    @staticmethod
    def rate_limit(max_attempts: int = 5, window_minutes: int = 15):
        """Method decorator for rate limiting"""
        return method_decorator(rate_limit(max_attempts, window_minutes))

    @staticmethod
    def require_role(*allowed_roles):
        """Method decorator for role requirements"""
        return method_decorator(require_role(*allowed_roles))

    @staticmethod
    def cache_page(timeout: int = 3600):
        """Method decorator for page caching"""
        return method_decorator(cache_page(timeout))

    @staticmethod
    def performance_monitor(threshold_ms: int = 1000):
        """Method decorator for performance monitoring"""
        return method_decorator(performance_monitor(threshold_ms))
