# middleware.py
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.http import JsonResponse
from django.core.cache import cache
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
