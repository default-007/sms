"""
Custom middleware for the scheduling module
"""

import json
import logging
import time
from datetime import datetime, timedelta

from django.conf import settings
from django.core.cache import cache
from django.http import JsonResponse
from django.urls import resolve
from django.utils import timezone
from django.utils.deprecation import MiddlewareMixin

from .exceptions import TimetableGenerationInProgressError
from .models import TimetableGeneration

logger = logging.getLogger("scheduling.middleware")


class SchedulingPerformanceMiddleware(MiddlewareMixin):
    """
    Middleware to monitor performance of scheduling operations
    """

    def process_request(self, request):
        """Start timing the request"""
        request._scheduling_start_time = time.time()
        return None

    def process_response(self, request, response):
        """Log performance metrics for scheduling requests"""

        if not hasattr(request, "_scheduling_start_time"):
            return response

        # Check if this is a scheduling-related request
        if not self._is_scheduling_request(request):
            return response

        execution_time = time.time() - request._scheduling_start_time

        # Log slow requests
        slow_threshold = getattr(settings, "SCHEDULING_SLOW_REQUEST_THRESHOLD", 2.0)
        if execution_time > slow_threshold:
            logger.warning(
                f"Slow scheduling request: {request.path} took {execution_time:.2f}s",
                extra={
                    "path": request.path,
                    "method": request.method,
                    "execution_time": execution_time,
                    "user": (
                        request.user.username
                        if request.user.is_authenticated
                        else "anonymous"
                    ),
                    "status_code": response.status_code,
                },
            )

        # Add performance headers
        response["X-Scheduling-Execution-Time"] = f"{execution_time:.3f}"

        # Cache performance metrics
        self._cache_performance_metrics(request, execution_time)

        return response

    def _is_scheduling_request(self, request):
        """Check if request is scheduling-related"""
        return (
            request.path.startswith("/scheduling/")
            or request.path.startswith("/api/scheduling/")
            or "scheduling" in getattr(request, "resolver_match", {}).namespace
            or ""
        )

    def _cache_performance_metrics(self, request, execution_time):
        """Cache performance metrics for analytics"""

        cache_key = "scheduling_performance_metrics"
        metrics = cache.get(cache_key, [])

        # Add current metric
        metrics.append(
            {
                "timestamp": timezone.now().isoformat(),
                "path": request.path,
                "method": request.method,
                "execution_time": execution_time,
                "user_id": request.user.id if request.user.is_authenticated else None,
            }
        )

        # Keep only last 1000 metrics
        metrics = metrics[-1000:]

        # Cache for 1 hour
        cache.set(cache_key, metrics, 3600)


class TimetableGenerationLockMiddleware(MiddlewareMixin):
    """
    Middleware to prevent concurrent timetable generation
    """

    def process_request(self, request):
        """Check for concurrent generation attempts"""

        if not self._is_generation_request(request):
            return None

        # Check for running generations
        running_generations = TimetableGeneration.objects.filter(
            status="running",
            started_at__gte=timezone.now() - timedelta(hours=2),  # 2 hour timeout
        )

        if running_generations.exists():
            generation = running_generations.first()

            # If this is an API request, return JSON error
            if request.path.startswith("/api/"):
                error_data = {
                    "error": True,
                    "code": "generation_in_progress",
                    "message": f"Timetable generation already in progress for {generation.term}",
                    "details": {
                        "generation_id": str(generation.id),
                        "started_at": generation.started_at.isoformat(),
                        "started_by": (
                            generation.started_by.username
                            if generation.started_by
                            else None
                        ),
                    },
                }
                return JsonResponse(error_data, status=423)  # 423 Locked

            # For web requests, let the view handle it
            request._scheduling_generation_lock = generation

        return None

    def _is_generation_request(self, request):
        """Check if request is for timetable generation"""
        generation_paths = [
            "/api/scheduling/generations/",
            "/scheduling/generate/",
            "/api/scheduling/timetables/generate/",
        ]

        return request.method == "POST" and any(
            request.path.startswith(path) for path in generation_paths
        )


class SchedulingCacheMiddleware(MiddlewareMixin):
    """
    Middleware to handle scheduling-specific caching
    """

    def process_request(self, request):
        """Check cache for frequently requested data"""

        if request.method != "GET":
            return None

        # Check for cacheable scheduling requests
        cache_key = self._get_cache_key(request)
        if not cache_key:
            return None

        cached_response = cache.get(cache_key)
        if cached_response:
            logger.debug(f"Cache hit for {request.path}")
            response = JsonResponse(cached_response)
            response["X-Scheduling-Cache"] = "HIT"
            return response

        # Mark request for caching
        request._scheduling_cache_key = cache_key
        return None

    def process_response(self, request, response):
        """Cache successful responses"""

        if not hasattr(request, "_scheduling_cache_key"):
            return response

        if response.status_code == 200 and response.get("Content-Type", "").startswith(
            "application/json"
        ):

            try:
                response_data = json.loads(response.content)

                # Cache for different durations based on data type
                cache_duration = self._get_cache_duration(request.path)
                cache.set(request._scheduling_cache_key, response_data, cache_duration)

                response["X-Scheduling-Cache"] = "MISS"
                logger.debug(
                    f"Cached response for {request.path} (duration: {cache_duration}s)"
                )

            except (json.JSONDecodeError, ValueError):
                pass  # Don't cache invalid JSON

        return response

    def _get_cache_key(self, request):
        """Generate cache key for request"""

        cacheable_patterns = [
            "/api/scheduling/analytics/",
            "/api/scheduling/rooms/",
            "/api/scheduling/time-slots/",
            "/api/scheduling/timetables/class/",
            "/api/scheduling/timetables/teacher/",
        ]

        if not any(request.path.startswith(pattern) for pattern in cacheable_patterns):
            return None

        # Include query parameters and user in cache key
        query_string = request.GET.urlencode()
        user_id = request.user.id if request.user.is_authenticated else "anonymous"

        cache_key = f"scheduling:{request.path}:{query_string}:{user_id}"
        return cache_key

    def _get_cache_duration(self, path):
        """Get cache duration based on path"""

        cache_durations = {
            "/api/scheduling/analytics/": 900,  # 15 minutes
            "/api/scheduling/rooms/": 3600,  # 1 hour
            "/api/scheduling/time-slots/": 7200,  # 2 hours
            "/api/scheduling/timetables/": 1800,  # 30 minutes
        }

        for pattern, duration in cache_durations.items():
            if path.startswith(pattern):
                return duration

        return 300  # Default 5 minutes


class SchedulingAuditMiddleware(MiddlewareMixin):
    """
    Middleware to audit scheduling operations
    """

    def process_request(self, request):
        """Log request details for auditing"""

        if not self._should_audit(request):
            return None

        audit_data = {
            "timestamp": timezone.now().isoformat(),
            "user": (
                request.user.username if request.user.is_authenticated else "anonymous"
            ),
            "user_id": request.user.id if request.user.is_authenticated else None,
            "ip_address": self._get_client_ip(request),
            "user_agent": request.META.get("HTTP_USER_AGENT", ""),
            "method": request.method,
            "path": request.path,
            "query_params": dict(request.GET),
        }

        # Store for process_response
        request._scheduling_audit_data = audit_data

        return None

    def process_response(self, request, response):
        """Complete audit log with response details"""

        if not hasattr(request, "_scheduling_audit_data"):
            return response

        audit_data = request._scheduling_audit_data
        audit_data.update(
            {
                "status_code": response.status_code,
                "response_size": (
                    len(response.content) if hasattr(response, "content") else 0
                ),
            }
        )

        # Log based on operation type
        if self._is_sensitive_operation(request):
            logger.info(
                f"Scheduling operation: {request.method} {request.path}",
                extra={"audit_data": audit_data},
            )

        return response

    def _should_audit(self, request):
        """Determine if request should be audited"""

        audit_patterns = [
            "/api/scheduling/timetables/",
            "/api/scheduling/generations/",
            "/api/scheduling/substitutes/",
            "/scheduling/timetables/",
            "/scheduling/generate/",
        ]

        return any(request.path.startswith(pattern) for pattern in audit_patterns)

    def _is_sensitive_operation(self, request):
        """Check if operation is sensitive and needs detailed logging"""

        sensitive_operations = [
            ("POST", "/api/scheduling/timetables/"),
            ("PUT", "/api/scheduling/timetables/"),
            ("DELETE", "/api/scheduling/timetables/"),
            ("POST", "/api/scheduling/generations/"),
            ("POST", "/api/scheduling/timetables/bulk-create/"),
        ]

        return (
            (request.method, request.path) in sensitive_operations
            or request.path.endswith("/delete/")
            or "bulk" in request.path
        )

    def _get_client_ip(self, request):
        """Get client IP address"""

        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            ip = x_forwarded_for.split(",")[0]
        else:
            ip = request.META.get("REMOTE_ADDR")

        return ip


class SchedulingSecurityMiddleware(MiddlewareMixin):
    """
    Middleware to handle scheduling-specific security
    """

    def process_request(self, request):
        """Apply security checks for scheduling requests"""

        if not self._is_scheduling_request(request):
            return None

        # Rate limiting for optimization requests
        if self._is_optimization_request(request):
            if not self._check_optimization_rate_limit(request):
                return JsonResponse(
                    {
                        "error": True,
                        "code": "rate_limit_exceeded",
                        "message": "Too many optimization requests. Please try again later.",
                    },
                    status=429,
                )

        # Check user permissions
        if not self._has_scheduling_permission(request):
            return JsonResponse(
                {
                    "error": True,
                    "code": "permission_denied",
                    "message": "Insufficient permissions for scheduling operations.",
                },
                status=403,
            )

        return None

    def _is_scheduling_request(self, request):
        """Check if request is scheduling-related"""
        return request.path.startswith("/scheduling/") or request.path.startswith(
            "/api/scheduling/"
        )

    def _is_optimization_request(self, request):
        """Check if request is for optimization"""
        optimization_paths = [
            "/api/scheduling/generations/",
            "/scheduling/generate/",
            "/scheduling/optimize/",
        ]

        return any(request.path.startswith(path) for path in optimization_paths)

    def _check_optimization_rate_limit(self, request):
        """Check rate limit for optimization requests"""

        if not request.user.is_authenticated:
            return False

        cache_key = f"scheduling_optimization_rate_limit:{request.user.id}"
        current_count = cache.get(cache_key, 0)

        # Allow 5 optimization requests per hour
        max_requests = getattr(settings, "SCHEDULING_OPTIMIZATION_RATE_LIMIT", 5)

        if current_count >= max_requests:
            return False

        # Increment counter
        cache.set(cache_key, current_count + 1, 3600)  # 1 hour
        return True

    def _has_scheduling_permission(self, request):
        """Check if user has required permissions"""

        if not request.user.is_authenticated:
            return False

        # Admin users have all permissions
        if request.user.is_superuser:
            return True

        # Check specific permissions based on request type
        required_permissions = self._get_required_permissions(request)

        if required_permissions:
            return request.user.has_perms(required_permissions)

        return True  # No specific permissions required

    def _get_required_permissions(self, request):
        """Get required permissions for request"""

        permission_map = {
            ("POST", "/api/scheduling/generations/"): ["scheduling.generate_timetable"],
            ("POST", "/api/scheduling/timetables/bulk-create/"): [
                "scheduling.bulk_edit_timetable"
            ],
            ("DELETE", "/api/scheduling/timetables/"): ["scheduling.delete_timetable"],
            ("GET", "/api/scheduling/analytics/"): [
                "scheduling.view_timetable_analytics"
            ],
        }

        key = (request.method, request.path)
        return permission_map.get(key, [])


class SchedulingMaintenanceMiddleware(MiddlewareMixin):
    """
    Middleware to handle maintenance mode for scheduling
    """

    def process_request(self, request):
        """Check if scheduling is in maintenance mode"""

        if not self._is_scheduling_request(request):
            return None

        # Check maintenance mode
        maintenance_mode = cache.get("scheduling_maintenance_mode", False)

        if maintenance_mode:
            # Allow read operations during maintenance
            if request.method in ["GET", "HEAD", "OPTIONS"]:
                response = self._get_response(request)
                response["X-Scheduling-Maintenance"] = "true"
                return response

            # Block write operations
            maintenance_message = cache.get(
                "scheduling_maintenance_message",
                "Scheduling system is currently under maintenance. Please try again later.",
            )

            if request.path.startswith("/api/"):
                return JsonResponse(
                    {
                        "error": True,
                        "code": "maintenance_mode",
                        "message": maintenance_message,
                    },
                    status=503,
                )

            # For web requests, redirect to maintenance page
            from django.shortcuts import render

            return render(
                request,
                "scheduling/maintenance.html",
                {"message": maintenance_message},
                status=503,
            )

        return None

    def _is_scheduling_request(self, request):
        """Check if request is scheduling-related"""
        return request.path.startswith("/scheduling/") or request.path.startswith(
            "/api/scheduling/"
        )


# Utility functions for middleware management


def enable_scheduling_maintenance(message=None, duration_hours=1):
    """
    Enable maintenance mode for scheduling

    Args:
        message: Custom maintenance message
        duration_hours: Duration in hours (default: 1)
    """

    cache.set("scheduling_maintenance_mode", True, duration_hours * 3600)

    if message:
        cache.set("scheduling_maintenance_message", message, duration_hours * 3600)

    logger.info(f"Scheduling maintenance mode enabled for {duration_hours} hours")


def disable_scheduling_maintenance():
    """Disable maintenance mode for scheduling"""

    cache.delete("scheduling_maintenance_mode")
    cache.delete("scheduling_maintenance_message")

    logger.info("Scheduling maintenance mode disabled")


def get_scheduling_performance_metrics():
    """Get cached performance metrics"""

    metrics = cache.get("scheduling_performance_metrics", [])

    if not metrics:
        return {
            "average_response_time": 0,
            "total_requests": 0,
            "slow_requests": 0,
            "requests_by_endpoint": {},
        }

    # Calculate statistics
    response_times = [m["execution_time"] for m in metrics]
    slow_threshold = getattr(settings, "SCHEDULING_SLOW_REQUEST_THRESHOLD", 2.0)

    # Group by endpoint
    endpoint_stats = {}
    for metric in metrics:
        endpoint = metric["path"]
        if endpoint not in endpoint_stats:
            endpoint_stats[endpoint] = {"count": 0, "total_time": 0, "slow_count": 0}

        endpoint_stats[endpoint]["count"] += 1
        endpoint_stats[endpoint]["total_time"] += metric["execution_time"]

        if metric["execution_time"] > slow_threshold:
            endpoint_stats[endpoint]["slow_count"] += 1

    # Calculate averages
    for endpoint, stats in endpoint_stats.items():
        stats["average_time"] = stats["total_time"] / stats["count"]

    return {
        "average_response_time": sum(response_times) / len(response_times),
        "total_requests": len(metrics),
        "slow_requests": len([t for t in response_times if t > slow_threshold]),
        "requests_by_endpoint": endpoint_stats,
    }


def clear_scheduling_cache(pattern=None):
    """
    Clear scheduling-related cache entries

    Args:
        pattern: Optional pattern to match cache keys
    """

    # This is a simplified implementation
    # In production, you'd want to use a more sophisticated cache clearing mechanism

    cache_patterns = [
        "scheduling:*",
        "scheduling_analytics_*",
        "scheduling_performance_metrics",
    ]

    if pattern:
        cache_patterns.append(pattern)

    # Note: This is pseudo-code, actual implementation depends on cache backend
    logger.info(f"Cleared scheduling cache patterns: {cache_patterns}")


# Configuration class for middleware settings
class SchedulingMiddlewareConfig:
    """Configuration class for scheduling middleware"""

    # Performance monitoring
    SLOW_REQUEST_THRESHOLD = 2.0  # seconds
    PERFORMANCE_METRICS_RETENTION = 1000  # number of metrics to keep

    # Caching
    DEFAULT_CACHE_DURATION = 300  # 5 minutes
    ANALYTICS_CACHE_DURATION = 900  # 15 minutes

    # Rate limiting
    OPTIMIZATION_RATE_LIMIT = 5  # requests per hour

    # Security
    AUDIT_SENSITIVE_OPERATIONS = True
    LOG_ALL_REQUESTS = False

    @classmethod
    def update_from_settings(cls):
        """Update configuration from Django settings"""

        if hasattr(settings, "SCHEDULING_MIDDLEWARE"):
            config = settings.SCHEDULING_MIDDLEWARE

            for key, value in config.items():
                if hasattr(cls, key):
                    setattr(cls, key, value)
