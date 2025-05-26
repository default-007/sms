"""
Custom decorators for the scheduling module
"""

import functools
import logging
import time
from datetime import datetime, timedelta

from django.contrib.auth.decorators import user_passes_test
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone

from .exceptions import (
    SchedulingException,
    TermNotActiveError,
    TimetableConflictError,
    TimetableGenerationInProgressError,
)
from .models import TimetableGeneration

logger = logging.getLogger("scheduling.decorators")


def scheduling_permission_required(permission):
    """
    Decorator to check scheduling-specific permissions

    Usage:
        @scheduling_permission_required('scheduling.generate_timetable')
        def my_view(request):
            pass
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                raise PermissionDenied("Authentication required")

            if not request.user.has_perm(permission):
                raise PermissionDenied(f"Permission required: {permission}")

            return func(request, *args, **kwargs)

        return wrapper

    return decorator


def require_active_term(func):
    """
    Decorator to ensure operations are performed on active terms only

    Usage:
        @require_active_term
        def my_view(request, term_id):
            pass
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # Extract term from arguments
        term = None

        # Check if term is passed as keyword argument
        if "term" in kwargs:
            term = kwargs["term"]
        elif "term_id" in kwargs:
            from academics.models import Term

            try:
                term = Term.objects.get(id=kwargs["term_id"])
            except Term.DoesNotExist:
                raise SchedulingException("Term not found", code="term_not_found")

        # Check for term in positional arguments (for service methods)
        if not term:
            for arg in args:
                if hasattr(arg, "is_current"):  # Duck typing for Term
                    term = arg
                    break

        if term and not term.is_current:
            raise TermNotActiveError(term, func.__name__)

        return func(*args, **kwargs)

    return wrapper


def cache_scheduling_result(cache_key_pattern, timeout=300):
    """
    Decorator to cache scheduling operation results

    Args:
        cache_key_pattern: Pattern for cache key with placeholders
        timeout: Cache timeout in seconds (default: 5 minutes)

    Usage:
        @cache_scheduling_result('timetable_{class_id}_{term_id}', timeout=600)
        def get_class_timetable(class_id, term_id):
            pass
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            cache_key = cache_key_pattern.format(**kwargs)

            # Try to get from cache
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                logger.debug(f"Cache hit for {func.__name__}: {cache_key}")
                return cached_result

            # Execute function
            result = func(*args, **kwargs)

            # Cache result
            cache.set(cache_key, result, timeout)
            logger.debug(f"Cached result for {func.__name__}: {cache_key}")

            return result

        return wrapper

    return decorator


def invalidate_cache_on_change(cache_patterns):
    """
    Decorator to invalidate caches when data changes

    Args:
        cache_patterns: List of cache key patterns to invalidate

    Usage:
        @invalidate_cache_on_change(['timetable_*', 'analytics_*'])
        def update_timetable():
            pass
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)

            # Invalidate caches
            for pattern in cache_patterns:
                # Note: This is a simplified implementation
                # Real implementation would depend on cache backend
                cache.delete_many(cache.keys(pattern))
                logger.debug(f"Invalidated cache pattern: {pattern}")

            return result

        return wrapper

    return decorator


def prevent_concurrent_generation(func):
    """
    Decorator to prevent concurrent timetable generation

    Usage:
        @prevent_concurrent_generation
        def start_timetable_generation(term):
            pass
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # Extract term from arguments
        term = None

        if "term" in kwargs:
            term = kwargs["term"]
        elif len(args) > 0 and hasattr(args[0], "start_date"):
            term = args[0]

        if term:
            # Check for running generations
            running_generation = TimetableGeneration.objects.filter(
                term=term,
                status="running",
                started_at__gte=timezone.now() - timedelta(hours=2),
            ).first()

            if running_generation:
                raise TimetableGenerationInProgressError(term, running_generation)

        return func(*args, **kwargs)

    return wrapper


def log_scheduling_operation(operation_type):
    """
    Decorator to log scheduling operations

    Args:
        operation_type: Type of operation being performed

    Usage:
        @log_scheduling_operation('timetable_creation')
        def create_timetable():
            pass
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()

            logger.info(f"Starting {operation_type}: {func.__name__}")

            try:
                result = func(*args, **kwargs)
                execution_time = time.time() - start_time

                logger.info(
                    f"Completed {operation_type}: {func.__name__} "
                    f"in {execution_time:.2f}s"
                )

                return result

            except Exception as e:
                execution_time = time.time() - start_time

                logger.error(
                    f"Failed {operation_type}: {func.__name__} "
                    f"after {execution_time:.2f}s - {str(e)}"
                )

                raise

        return wrapper

    return decorator


def validate_timetable_conflicts(func):
    """
    Decorator to automatically validate timetable conflicts

    Usage:
        @validate_timetable_conflicts
        def create_timetable_entry(class_obj, teacher, time_slot, term):
            pass
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # Extract scheduling parameters
        teacher = kwargs.get("teacher") or (args[1] if len(args) > 1 else None)
        time_slot = kwargs.get("time_slot") or (args[2] if len(args) > 2 else None)
        term = kwargs.get("term") or (args[3] if len(args) > 3 else None)
        room = kwargs.get("room")
        class_obj = kwargs.get("class_assigned") or (args[0] if len(args) > 0 else None)

        # Validate conflicts before execution
        if all([teacher, time_slot, term]):
            from .services.timetable_service import TimetableService

            conflicts = TimetableService.check_conflicts(
                teacher=teacher,
                room=room,
                class_obj=class_obj,
                time_slot=time_slot,
                date_range=(term.start_date, term.end_date),
            )

            if conflicts:
                raise TimetableConflictError(conflicts)

        return func(*args, **kwargs)

    return wrapper


def atomic_scheduling_operation(func):
    """
    Decorator to wrap scheduling operations in database transactions

    Usage:
        @atomic_scheduling_operation
        def bulk_create_timetables():
            pass
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        with transaction.atomic():
            return func(*args, **kwargs)

    return wrapper


def rate_limit(max_calls=10, time_window=3600):
    """
    Decorator to rate limit function calls per user

    Args:
        max_calls: Maximum number of calls allowed
        time_window: Time window in seconds (default: 1 hour)

    Usage:
        @rate_limit(max_calls=5, time_window=3600)
        def expensive_operation(request):
            pass
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Extract request and user
            request = None
            for arg in args:
                if hasattr(arg, "user"):
                    request = arg
                    break

            if not request or not request.user.is_authenticated:
                return func(*args, **kwargs)

            # Check rate limit
            cache_key = f"rate_limit:{func.__name__}:{request.user.id}"
            current_calls = cache.get(cache_key, 0)

            if current_calls >= max_calls:
                raise SchedulingException(
                    f"Rate limit exceeded for {func.__name__}. "
                    f"Maximum {max_calls} calls per {time_window} seconds.",
                    code="rate_limit_exceeded",
                )

            # Increment counter
            cache.set(cache_key, current_calls + 1, time_window)

            return func(*args, **kwargs)

        return wrapper

    return decorator


def measure_performance(func):
    """
    Decorator to measure and log function performance

    Usage:
        @measure_performance
        def slow_operation():
            pass
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        start_memory = None

        try:
            import psutil

            process = psutil.Process()
            start_memory = process.memory_info().rss
        except ImportError:
            pass

        result = func(*args, **kwargs)

        execution_time = time.time() - start_time

        # Calculate memory usage if available
        memory_used = None
        if start_memory:
            try:
                end_memory = process.memory_info().rss
                memory_used = (end_memory - start_memory) / 1024 / 1024  # MB
            except:
                pass

        # Log performance metrics
        performance_data = {
            "function": func.__name__,
            "execution_time": execution_time,
            "memory_used_mb": memory_used,
        }

        logger.info(
            f"Performance: {func.__name__} - "
            f"Time: {execution_time:.3f}s"
            f"{f', Memory: {memory_used:.1f}MB' if memory_used else ''}"
        )

        # Cache performance metrics
        cache_key = "scheduling_performance_history"
        history = cache.get(cache_key, [])
        history.append({**performance_data, "timestamp": timezone.now().isoformat()})

        # Keep only last 100 entries
        history = history[-100:]
        cache.set(cache_key, history, 3600)  # 1 hour

        return result

    return wrapper


def retry_on_conflict(max_retries=3, delay=1.0):
    """
    Decorator to retry operations on conflict errors

    Args:
        max_retries: Maximum number of retry attempts
        delay: Delay between retries in seconds

    Usage:
        @retry_on_conflict(max_retries=3, delay=0.5)
        def create_timetable_with_retry():
            pass
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)

                except TimetableConflictError as e:
                    last_exception = e

                    if attempt < max_retries:
                        logger.warning(
                            f"Conflict in {func.__name__}, attempt {attempt + 1}/{max_retries + 1}. "
                            f"Retrying in {delay}s..."
                        )
                        time.sleep(delay)
                        continue
                    else:
                        logger.error(
                            f"Failed {func.__name__} after {max_retries + 1} attempts due to conflicts"
                        )
                        raise

                except Exception as e:
                    # Don't retry for non-conflict errors
                    raise

            # This should never be reached, but just in case
            raise last_exception

        return wrapper

    return decorator


def validate_scheduling_data(validation_rules):
    """
    Decorator to validate input data for scheduling functions

    Args:
        validation_rules: Dictionary of validation rules

    Usage:
        @validate_scheduling_data({
            'term': 'required',
            'class_obj': 'required',
            'teacher': 'required'
        })
        def create_timetable(term, class_obj, teacher):
            pass
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Validate required parameters
            for param, rule in validation_rules.items():
                if rule == "required":
                    if param not in kwargs or kwargs[param] is None:
                        raise SchedulingException(
                            f"Required parameter '{param}' is missing",
                            code="missing_parameter",
                        )

            return func(*args, **kwargs)

        return wrapper

    return decorator


def scheduling_api_response(func):
    """
    Decorator to standardize API responses for scheduling endpoints

    Usage:
        @scheduling_api_response
        def my_api_view(request):
            return {'data': 'some data'}
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            result = func(*args, **kwargs)

            # If result is already a Response, return as-is
            if hasattr(result, "status_code"):
                return result

            # Wrap in standard response format
            response_data = {
                "success": True,
                "data": result,
                "timestamp": timezone.now().isoformat(),
            }

            return JsonResponse(response_data)

        except SchedulingException as e:
            error_response = {
                "success": False,
                "error": {"code": e.code, "message": e.message, "details": e.details},
                "timestamp": timezone.now().isoformat(),
            }

            # Determine status code based on exception type
            status_code = 400  # Default bad request
            if isinstance(e, TimetableConflictError):
                status_code = 409  # Conflict
            elif isinstance(e, TimetableGenerationInProgressError):
                status_code = 423  # Locked

            return JsonResponse(error_response, status=status_code)

        except Exception as e:
            logger.error(f"Unexpected error in {func.__name__}: {str(e)}")

            error_response = {
                "success": False,
                "error": {
                    "code": "internal_error",
                    "message": "An internal error occurred",
                    "details": {},
                },
                "timestamp": timezone.now().isoformat(),
            }

            return JsonResponse(error_response, status=500)

    return wrapper


# Class-based decorator for view methods
class SchedulingViewMixin:
    """
    Mixin class to add scheduling-specific functionality to views
    """

    def dispatch(self, request, *args, **kwargs):
        """Add scheduling-specific dispatch logic"""

        # Check scheduling module permissions
        if hasattr(self, "scheduling_permission_required"):
            if not request.user.has_perm(self.scheduling_permission_required):
                raise PermissionDenied(
                    f"Permission required: {self.scheduling_permission_required}"
                )

        # Check for maintenance mode
        if cache.get("scheduling_maintenance_mode", False):
            if request.method not in ["GET", "HEAD", "OPTIONS"]:
                return JsonResponse(
                    {
                        "error": True,
                        "code": "maintenance_mode",
                        "message": "Scheduling system is under maintenance",
                    },
                    status=503,
                )

        return super().dispatch(request, *args, **kwargs)


# Utility decorator for debugging
def debug_scheduling_operation(func):
    """
    Decorator to add debug information to scheduling operations
    Only active when DEBUG=True

    Usage:
        @debug_scheduling_operation
        def complex_operation():
            pass
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        from django.conf import settings

        if not settings.DEBUG:
            return func(*args, **kwargs)

        start_time = time.time()

        logger.debug(f"DEBUG: Starting {func.__name__}")
        logger.debug(f"DEBUG: Args: {args}")
        logger.debug(f"DEBUG: Kwargs: {kwargs}")

        try:
            result = func(*args, **kwargs)
            execution_time = time.time() - start_time

            logger.debug(f"DEBUG: Completed {func.__name__} in {execution_time:.3f}s")
            logger.debug(f"DEBUG: Result type: {type(result)}")

            return result

        except Exception as e:
            execution_time = time.time() - start_time

            logger.debug(f"DEBUG: Failed {func.__name__} after {execution_time:.3f}s")
            logger.debug(f"DEBUG: Exception: {type(e).__name__}: {str(e)}")

            raise

    return wrapper
