# middleware.py
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.http import JsonResponse
from django.core.cache import cache
from django.utils.deprecation import MiddlewareMixin
from django.conf import settings
from django.db import connection
import time
import logging

from .services import AuditService, ConfigurationService, SecurityService
from .models import SystemHealthMetrics

logger = logging.getLogger(__name__)
User = get_user_model()


class AuditMiddleware:
    """Middleware for automatic audit logging"""

    def __init__(self, get_response):
        self.get_response = get_response

        # Exclude these paths from audit logging
        self.excluded_paths = [
            "/admin/jsi18n/",
            "/static/",
            "/media/",
            "/favicon.ico",
        ]

        # Only log these HTTP methods
        self.logged_methods = ["POST", "PUT", "PATCH", "DELETE"]

    def __call__(self, request):
        start_time = time.time()

        # Process request
        response = self.get_response(request)

        # Calculate duration
        duration_ms = int((time.time() - start_time) * 1000)

        # Log audit trail if conditions are met
        if self._should_log_request(request, response):
            self._log_request(request, response, duration_ms)

        return response

    def _should_log_request(self, request, response):
        """Determine if request should be logged"""
        # Skip if path is excluded
        for excluded_path in self.excluded_paths:
            if request.path.startswith(excluded_path):
                return False

        # Only log certain HTTP methods
        if request.method not in self.logged_methods:
            return False

        # Only log authenticated users
        if not request.user.is_authenticated:
            return False

        # Only log successful requests (2xx and 3xx)
        if response.status_code >= 400:
            return False

        return True

    def _log_request(self, request, response, duration_ms):
        """Log the request to audit trail"""
        try:
            # Extract view information
            view_name = ""
            module_name = ""

            if hasattr(request, "resolver_match") and request.resolver_match:
                view_name = request.resolver_match.view_name or ""
                if request.resolver_match.func:
                    module_name = request.resolver_match.func.__module__.split(".")[0]

            # Determine action based on HTTP method
            action_map = {
                "POST": "create",
                "PUT": "update",
                "PATCH": "update",
                "DELETE": "delete",
            }
            action = action_map.get(request.method, "unknown")

            # Log the action
            AuditService.log_action(
                user=request.user,
                action=action,
                description=f"{request.method} {request.path}",
                ip_address=request.META.get("REMOTE_ADDR"),
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
                session_key=request.session.session_key,
                module_name=module_name,
                view_name=view_name,
                duration_ms=duration_ms,
            )
        except Exception as e:
            logger.error(f"Error logging audit trail: {str(e)}")


class OptimizedUserSessionMiddleware(MiddlewareMixin):
    """
    Middleware to reduce unnecessary session updates and user queries
    """

    def __init__(self, get_response):
        self.get_response = get_response
        super().__init__(get_response)

        # Paths that don't need session updates
        self.skip_session_paths = [
            "/static/",
            "/media/",
            "/favicon.ico",
            ".css",
            ".js",
            ".png",
            ".jpg",
            ".jpeg",
            ".gif",
            ".svg",
            ".ico",
            ".woff",
            ".woff2",
            ".ttf",
            ".eot",
        ]

        # Cache timeout for user data
        self.user_cache_timeout = getattr(settings, "USER_CACHE_TIMEOUT", 300)

    def process_request(self, request):
        """Process the request before it reaches the view"""

        # Skip processing for static files and assets
        if self._should_skip_processing(request):
            return None

        # Cache user data to avoid repeated queries
        self._cache_user_data(request)

        # Optimize session handling
        self._optimize_session(request)

        return None

    def process_response(self, request, response):
        """Process the response before sending to client"""

        # Skip session updates for static files
        if self._should_skip_processing(request):
            return response

        # Only update session activity if it's been more than 60 seconds
        if hasattr(request, "user") and request.user.is_authenticated:
            self._conditional_session_update(request)

        return response

    def _should_skip_processing(self, request):
        """Check if we should skip processing for this request"""
        path = request.path_info.lower()

        # Skip static files and assets
        for skip_path in self.skip_session_paths:
            if skip_path in path:
                return True

        return False

    def _cache_user_data(self, request):
        """Cache user data to avoid repeated database queries"""
        if hasattr(request, "user") and request.user.is_authenticated:
            cache_key = f"user_data_{request.user.id}"
            cached_user = cache.get(cache_key)

            if not cached_user:
                # Cache basic user data
                user_data = {
                    "id": request.user.id,
                    "username": request.user.username,
                    "email": request.user.email,
                    "first_name": request.user.first_name,
                    "last_name": request.user.last_name,
                    "is_staff": request.user.is_staff,
                    "is_superuser": request.user.is_superuser,
                }
                cache.set(cache_key, user_data, self.user_cache_timeout)

    def _optimize_session(self, request):
        """Optimize session handling"""
        if hasattr(request, "session"):
            # Mark when we last updated session activity
            last_activity_update = request.session.get("_last_activity_update", 0)
            current_time = time.time()

            # Only update if it's been more than 60 seconds
            if current_time - last_activity_update > 60:
                request.session["_last_activity_update"] = current_time
                request.session.modified = True

    def _conditional_session_update(self, request):
        """Conditionally update session activity"""
        try:
            if hasattr(request.user, "usersession_set"):
                # Only update if session needs it
                last_update = getattr(request, "_session_last_updated", 0)
                current_time = time.time()

                if current_time - last_update > 60:  # 1 minute threshold
                    # Update session activity (but limit frequency)
                    from accounts.models import UserSession
                    from django.utils import timezone

                    UserSession.objects.filter(
                        user=request.user, session_key=request.session.session_key
                    ).update(last_activity=timezone.now())

                    request._session_last_updated = current_time

        except Exception as e:
            # Don't let session update errors break the request
            logger.warning(f"Session update error: {e}")


class AnalyticsOptimizationMiddleware(MiddlewareMixin):
    """
    Middleware to cache analytics settings and reduce DB queries
    """

    def __init__(self, get_response):
        self.get_response = get_response
        super().__init__(get_response)

        # Cache timeout for settings
        self.settings_cache_timeout = getattr(settings, "ANALYTICS_CACHE_TIMEOUT", 300)

    def process_request(self, request):
        """Cache analytics settings to avoid repeated DB queries"""

        # Cache analytics auto-calculation setting
        cache_key = "analytics_auto_calculation_enabled"
        setting_value = cache.get(cache_key)

        if setting_value is None:
            try:
                from core.models import SystemSetting

                setting = SystemSetting.objects.filter(
                    setting_key="analytics.auto_calculation_enabled"
                ).first()

                setting_value = setting.setting_value if setting else "true"
                cache.set(cache_key, setting_value, self.settings_cache_timeout)

            except Exception:
                setting_value = "true"  # Default value
                cache.set(cache_key, setting_value, 60)  # Short cache on error

        # Add to request for easy access
        request.analytics_auto_calculation = setting_value.lower() == "true"

        return None


class StaticFileOptimizationMiddleware(MiddlewareMixin):
    """
    Middleware to handle static file requests more efficiently
    """

    def process_request(self, request):
        """Skip unnecessary processing for static files"""
        path = request.path_info.lower()

        static_extensions = [
            ".css",
            ".js",
            ".png",
            ".jpg",
            ".jpeg",
            ".gif",
            ".svg",
            ".ico",
            ".woff",
            ".woff2",
            ".ttf",
            ".eot",
        ]

        # If this is a static file request
        if any(path.endswith(ext) for ext in static_extensions) or "/static/" in path:
            # Skip authentication and session middleware for static files
            request._skip_auth = True

        return None

    def process_response(self, request, response):
        """Add caching headers for static files"""
        path = request.path_info.lower()

        if "/static/" in path or any(
            path.endswith(ext) for ext in [".css", ".js", ".png", ".jpg"]
        ):
            # Add cache headers for static files
            response["Cache-Control"] = "public, max-age=31536000"  # 1 year

        return response


class QueryOptimizationMiddleware(MiddlewareMixin):
    """
    Middleware to optimize database queries
    """

    def process_request(self, request):
        """Initialize query optimization"""
        request._query_count_start = len(connection.queries) if settings.DEBUG else 0
        return None

    def process_response(self, request, response):
        """Log excessive queries in development"""
        if settings.DEBUG:
            from django.db import connection

            query_count = len(connection.queries) - getattr(
                request, "_query_count_start", 0
            )

            # Log if too many queries
            if query_count > 20:
                logger.warning(
                    f"High query count: {query_count} queries for {request.path}"
                )

        return response


class MaintenanceModeMiddleware:
    """Middleware to handle maintenance mode"""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Check if maintenance mode is enabled
        maintenance_mode = ConfigurationService.get_setting(
            "system.maintenance_mode", False
        )

        if maintenance_mode:
            # Allow superusers and staff to access during maintenance
            if request.user.is_authenticated and (
                request.user.is_superuser or request.user.is_staff
            ):
                response = self.get_response(request)
                return response

            # Allow access to admin and API authentication endpoints
            allowed_paths = ["/admin/", "/api/auth/"]
            if any(request.path.startswith(path) for path in allowed_paths):
                response = self.get_response(request)
                return response

            # Return maintenance response
            if request.path.startswith("/api/"):
                return JsonResponse(
                    {
                        "error": "System is currently under maintenance. Please try again later.",
                        "maintenance_mode": True,
                    },
                    status=503,
                )
            else:
                # For non-API requests, you would render a maintenance template
                from django.shortcuts import render

                return render(request, "core/maintenance.html", status=503)

        response = self.get_response(request)
        return response


class SecurityMiddleware:
    """Middleware for security enhancements"""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Rate limiting for sensitive endpoints
        if self._is_sensitive_endpoint(request):
            user_identifier = request.META.get("REMOTE_ADDR", "unknown")
            if request.user.is_authenticated:
                user_identifier = str(request.user.id)

            if not SecurityService.check_rate_limit(
                user_identifier, "sensitive_action", 10, 15
            ):
                SecurityService.log_security_event(
                    "rate_limit_exceeded",
                    user=request.user if request.user.is_authenticated else None,
                    ip_address=request.META.get("REMOTE_ADDR"),
                    details={"path": request.path, "method": request.method},
                )

                if request.path.startswith("/api/"):
                    return JsonResponse(
                        {"error": "Rate limit exceeded. Please try again later."},
                        status=429,
                    )

        response = self.get_response(request)

        # Add security headers
        response["X-Content-Type-Options"] = "nosniff"
        response["X-Frame-Options"] = "DENY"
        response["X-XSS-Protection"] = "1; mode=block"

        return response

    def _is_sensitive_endpoint(self, request):
        """Check if the endpoint is sensitive and requires rate limiting"""
        sensitive_patterns = [
            "/api/auth/",
            "/admin/login/",
            "/api/core/settings/",
            "/api/core/analytics/calculate/",
        ]

        return any(request.path.startswith(pattern) for pattern in sensitive_patterns)


class PerformanceMiddleware:
    """Middleware for performance monitoring"""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start_time = time.time()

        response = self.get_response(request)

        # Calculate request duration
        duration_ms = int((time.time() - start_time) * 1000)

        # Log slow requests
        slow_threshold = ConfigurationService.get_setting(
            "system.slow_request_threshold_ms", 1000
        )
        if duration_ms > slow_threshold:
            logger.warning(
                f"Slow request: {request.method} {request.path} took {duration_ms}ms"
            )

        # Add performance headers for debugging
        if ConfigurationService.get_setting("system.debug_performance_headers", False):
            response["X-Response-Time"] = f"{duration_ms}ms"

        return response
