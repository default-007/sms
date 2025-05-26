"""
Custom Decorators for Academics Module

This module provides decorators for common functionality in the academics app,
including permission checking, caching, validation, and audit logging.
"""

import logging
import time
from functools import wraps
from typing import Any, Callable

from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.views.decorators.vary import vary_on_headers

from .constants import ANALYTICS_CACHE_TIMEOUT, CACHE_KEYS
from .permissions import check_academic_permission

logger = logging.getLogger(__name__)


def require_current_academic_year(func: Callable) -> Callable:
    """
    Decorator to ensure a current academic year exists

    Args:
        func: Function to decorate

    Returns:
        Decorated function
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        from .services import AcademicYearService

        current_year = AcademicYearService.get_current_academic_year()
        if not current_year:
            if hasattr(args[0], "__class__") and hasattr(args[0], "request"):
                # This is a view method
                request = args[0].request if hasattr(args[0], "request") else args[0]
                if request.content_type == "application/json":
                    return JsonResponse(
                        {"error": "No current academic year is set"}, status=400
                    )
            raise ValueError("No current academic year is set")

        # Add current_year to kwargs for easy access
        kwargs["current_academic_year"] = current_year
        return func(*args, **kwargs)

    return wrapper


def require_academic_permission(permission: str):
    """
    Decorator to check academic permissions

    Args:
        permission: Required permission string

    Returns:
        Decorator function
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(request, *args, **kwargs):
            if not check_academic_permission(request.user, permission):
                raise PermissionDenied(f"Permission denied: {permission}")
            return func(request, *args, **kwargs)

        return wrapper

    return decorator


def require_object_permission(permission: str, get_object_func: Callable):
    """
    Decorator for object-level permission checking

    Args:
        permission: Required permission string
        get_object_func: Function to get the object from request/args

    Returns:
        Decorator function
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(request, *args, **kwargs):
            obj = get_object_func(request, *args, **kwargs)
            if not check_academic_permission(request.user, permission, obj):
                raise PermissionDenied(f"Permission denied: {permission} on {obj}")
            return func(request, *args, **kwargs)

        return wrapper

    return decorator


def cache_academic_data(
    cache_key_template: str, timeout: int = ANALYTICS_CACHE_TIMEOUT
):
    """
    Decorator to cache academic data

    Args:
        cache_key_template: Cache key template with format placeholders
        timeout: Cache timeout in seconds

    Returns:
        Decorator function
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Build cache key from template and function arguments
            cache_key = cache_key_template.format(**kwargs)

            # Try to get from cache first
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                logger.debug(f"Cache hit for key: {cache_key}")
                return cached_result

            # Execute function and cache result
            result = func(*args, **kwargs)
            cache.set(cache_key, result, timeout)
            logger.debug(f"Cached result for key: {cache_key}")

            return result

        return wrapper

    return decorator


def invalidate_cache_on_change(cache_keys: list):
    """
    Decorator to invalidate cache when data changes

    Args:
        cache_keys: List of cache keys to invalidate

    Returns:
        Decorator function
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)

            # Invalidate specified cache keys
            for cache_key in cache_keys:
                # Support format placeholders in cache keys
                if hasattr(result, "id"):
                    cache_key = cache_key.format(id=result.id)
                cache.delete(cache_key)
                logger.debug(f"Invalidated cache key: {cache_key}")

            return result

        return wrapper

    return decorator


def log_academic_action(action: str, log_level: str = "INFO"):
    """
    Decorator to log academic actions

    Args:
        action: Action description
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)

    Returns:
        Decorator function
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()

            # Extract user information if available
            user_info = "Unknown"
            if args and hasattr(args[0], "user"):
                user = args[0].user
                user_info = f"{user.username} ({user.id})"
            elif "user" in kwargs:
                user = kwargs["user"]
                user_info = f"{user.username} ({user.id})"

            log_message = f"Academic Action: {action} - User: {user_info}"

            try:
                result = func(*args, **kwargs)
                execution_time = time.time() - start_time

                # Log successful execution
                getattr(logger, log_level.lower())(
                    f"{log_message} - Success - Time: {execution_time:.2f}s"
                )

                # Log to audit trail if available
                try:
                    from core.models import AuditLog

                    AuditLog.objects.create(
                        action=action,
                        entity_type="Academic",
                        user=kwargs.get("user")
                        or (args[0].user if hasattr(args[0], "user") else None),
                        metadata={"execution_time": execution_time},
                    )
                except ImportError:
                    pass  # Audit system not available

                return result

            except Exception as e:
                execution_time = time.time() - start_time
                logger.error(
                    f"{log_message} - Error: {str(e)} - Time: {execution_time:.2f}s"
                )
                raise

        return wrapper

    return decorator


def validate_academic_structure(func: Callable) -> Callable:
    """
    Decorator to validate academic structure before performing operations

    Args:
        func: Function to decorate

    Returns:
        Decorated function
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        from .utils import validate_academic_structure_integrity

        # Perform structure validation
        validation_result = validate_academic_structure_integrity()

        if not validation_result["is_valid"]:
            error_message = f"Academic structure integrity check failed: {'; '.join(validation_result['issues'])}"
            logger.error(error_message)
            raise ValueError(error_message)

        if validation_result["warnings"]:
            logger.warning(
                f"Academic structure warnings: {'; '.join(validation_result['warnings'])}"
            )

        return func(*args, **kwargs)

    return wrapper


def atomic_academic_operation(func: Callable) -> Callable:
    """
    Decorator to wrap academic operations in database transactions

    Args:
        func: Function to decorate

    Returns:
        Decorated function
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        with transaction.atomic():
            return func(*args, **kwargs)

    return wrapper


def rate_limit_analytics(max_calls: int = 10, time_window: int = 60):
    """
    Decorator to rate limit analytics operations

    Args:
        max_calls: Maximum number of calls allowed
        time_window: Time window in seconds

    Returns:
        Decorator function
    """

    def decorator(func: Callable) -> Callable:
        call_times = {}

        @wraps(func)
        def wrapper(*args, **kwargs):
            current_time = time.time()

            # Extract user identifier
            user_id = None
            if args and hasattr(args[0], "user"):
                user_id = args[0].user.id
            elif "user" in kwargs:
                user_id = kwargs["user"].id

            if user_id is None:
                # No user identified, allow operation
                return func(*args, **kwargs)

            # Clean old entries
            if user_id in call_times:
                call_times[user_id] = [
                    call_time
                    for call_time in call_times[user_id]
                    if current_time - call_time < time_window
                ]
            else:
                call_times[user_id] = []

            # Check rate limit
            if len(call_times[user_id]) >= max_calls:
                raise PermissionDenied(
                    f"Rate limit exceeded: {max_calls} calls per {time_window} seconds"
                )

            # Record this call
            call_times[user_id].append(current_time)

            return func(*args, **kwargs)

        return wrapper

    return decorator


def handle_academic_errors(default_return: Any = None):
    """
    Decorator to handle common academic errors gracefully

    Args:
        default_return: Default return value on error

    Returns:
        Decorator function
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except ValueError as e:
                logger.error(f"Academic validation error in {func.__name__}: {str(e)}")
                if "request" in kwargs or (args and hasattr(args[0], "request")):
                    return JsonResponse({"error": str(e)}, status=400)
                return default_return
            except PermissionDenied as e:
                logger.warning(f"Permission denied in {func.__name__}: {str(e)}")
                if "request" in kwargs or (args and hasattr(args[0], "request")):
                    return JsonResponse({"error": "Permission denied"}, status=403)
                return default_return
            except Exception as e:
                logger.error(f"Unexpected error in {func.__name__}: {str(e)}")
                if "request" in kwargs or (args and hasattr(args[0], "request")):
                    return JsonResponse({"error": "Internal server error"}, status=500)
                return default_return

        return wrapper

    return decorator


def ensure_class_capacity(func: Callable) -> Callable:
    """
    Decorator to ensure class capacity is not exceeded

    Args:
        func: Function to decorate

    Returns:
        Decorated function
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        # This decorator would be used on functions that add students to classes
        result = func(*args, **kwargs)

        # Check if we need to validate capacity
        if hasattr(result, "current_class") and result.current_class:
            cls = result.current_class
            if cls.get_students_count() > cls.capacity:
                logger.warning(f"Class {cls.display_name} is over capacity")

                # Trigger capacity warning if tasks are available
                try:
                    from .tasks import send_capacity_warning

                    send_capacity_warning.delay(cls.id, "over_capacity")
                except ImportError:
                    pass

        return result

    return wrapper


def academic_cache_key(key_template: str):
    """
    Decorator to generate academic cache keys

    Args:
        key_template: Template for cache key generation

    Returns:
        Decorator function
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key based on function arguments
            cache_key = key_template.format(**kwargs)

            # Add cache key to function result if it's a dict
            result = func(*args, **kwargs)
            if isinstance(result, dict):
                result["_cache_key"] = cache_key

            return result

        return wrapper

    return decorator


def track_academic_metrics(metric_name: str):
    """
    Decorator to track academic metrics

    Args:
        metric_name: Name of the metric to track

    Returns:
        Decorator function
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()

            try:
                result = func(*args, **kwargs)
                execution_time = time.time() - start_time

                # Track successful metric
                logger.info(
                    f"Academic Metric: {metric_name} - Success - Time: {execution_time:.2f}s"
                )

                # Store metric if analytics module is available
                try:
                    from analytics.services import MetricsService

                    MetricsService.track_metric(
                        name=metric_name, value=execution_time, status="success"
                    )
                except ImportError:
                    pass

                return result

            except Exception as e:
                execution_time = time.time() - start_time

                # Track failed metric
                logger.error(
                    f"Academic Metric: {metric_name} - Error: {str(e)} - Time: {execution_time:.2f}s"
                )

                try:
                    from analytics.services import MetricsService

                    MetricsService.track_metric(
                        name=metric_name,
                        value=execution_time,
                        status="error",
                        error=str(e),
                    )
                except ImportError:
                    pass

                raise

        return wrapper

    return decorator


# Class decorators for views


def academic_admin_required(view_class):
    """
    Class decorator to require academic admin permissions

    Args:
        view_class: View class to decorate

    Returns:
        Decorated view class
    """
    original_dispatch = view_class.dispatch

    def dispatch(self, request, *args, **kwargs):
        if not check_academic_permission(request.user, "manage_structure"):
            raise PermissionDenied("Academic admin permissions required")
        return original_dispatch(self, request, *args, **kwargs)

    view_class.dispatch = dispatch
    return view_class


def cache_academic_view(timeout: int = ANALYTICS_CACHE_TIMEOUT):
    """
    Class decorator to cache academic views

    Args:
        timeout: Cache timeout in seconds

    Returns:
        Decorator function
    """

    def decorator(view_class):
        view_class = method_decorator(cache_page(timeout))(view_class)
        view_class = method_decorator(vary_on_headers("User-Agent"))(view_class)
        return view_class

    return decorator


def require_login_and_academic_permission(permission: str):
    """
    Combined decorator for login and academic permission requirements

    Args:
        permission: Required academic permission

    Returns:
        Decorator function
    """

    def decorator(func: Callable) -> Callable:
        @login_required
        @require_academic_permission(permission)
        @wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        return wrapper

    return decorator


# Utility decorators


def retry_on_academic_error(max_retries: int = 3, delay: float = 1.0):
    """
    Decorator to retry operations on academic errors

    Args:
        max_retries: Maximum number of retries
        delay: Delay between retries in seconds

    Returns:
        Decorator function
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except (ValueError, PermissionDenied) as e:
                    # Don't retry validation or permission errors
                    raise
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries:
                        logger.warning(
                            f"Academic operation failed (attempt {attempt + 1}/{max_retries + 1}): {str(e)}"
                        )
                        time.sleep(delay * (2**attempt))  # Exponential backoff
                    else:
                        logger.error(
                            f"Academic operation failed after {max_retries + 1} attempts: {str(e)}"
                        )

            raise last_exception

        return wrapper

    return decorator


def academic_feature_flag(feature_name: str):
    """
    Decorator to check if an academic feature is enabled

    Args:
        feature_name: Name of the feature to check

    Returns:
        Decorator function
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            from .constants import FEATURES

            if not FEATURES.get(feature_name, False):
                raise PermissionDenied(f"Feature '{feature_name}' is not enabled")

            return func(*args, **kwargs)

        return wrapper

    return decorator
