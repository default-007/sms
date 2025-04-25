import time
import json
from django.utils.deprecation import MiddlewareMixin
from django.urls import resolve
from django.conf import settings
from .models import AuditLog


class RequestAuditMiddleware(MiddlewareMixin):
    """Middleware to log all requests for audit purposes."""

    def __init__(self, get_response):
        self.get_response = get_response
        # Paths that should not be logged
        self.exclude_paths = [
            "/static/",
            "/media/",
            "/admin/jsi18n/",
            "/favicon.ico",
        ]

    def is_excluded_path(self, path):
        """Check if the path should be excluded from logging."""
        return any(path.startswith(excluded) for excluded in self.exclude_paths)

    def process_request(self, request):
        if not self.is_excluded_path(request.path):
            # Store the start time
            request.start_time = time.time()
        return None

    def process_response(self, request, response):
        if hasattr(request, "start_time") and request.user.is_authenticated:
            # Calculate request duration
            duration = time.time() - request.start_time

            # Create audit log for sensitive operations
            if request.method in ["POST", "PUT", "PATCH", "DELETE"]:
                # Resolve the URL to get view name
                view_func, args, kwargs = resolve(request.path)
                view_name = view_func.__name__

                # Determine action type
                if request.method == "POST":
                    action = "create"
                elif request.method in ["PUT", "PATCH"]:
                    action = "update"
                elif request.method == "DELETE":
                    action = "delete"
                else:
                    action = "other"

                # Determine entity type from URL
                url_parts = request.path.strip("/").split("/")
                entity_type = url_parts[0] if url_parts else "unknown"

                # Get entity ID if available
                entity_id = kwargs.get("pk") or kwargs.get("id")

                # Log sensitive data before/after for admin users only
                data_before = None
                data_after = None

                if settings.DEBUG and request.user.is_staff:
                    # For POST requests, log the submitted data
                    if request.method == "POST":
                        try:
                            if request.content_type == "application/json":
                                data_after = json.loads(request.body)
                            else:
                                data_after = dict(request.POST)
                        except:
                            pass

                AuditLog.objects.create(
                    user=request.user,
                    action=action,
                    entity_type=entity_type,
                    entity_id=entity_id,
                    data_before=data_before,
                    data_after=data_after,
                    ip_address=request.META.get("REMOTE_ADDR"),
                    user_agent=request.META.get("HTTP_USER_AGENT"),
                )

        return response


class MaintenanceModeMiddleware(MiddlewareMixin):
    """Middleware to handle site maintenance mode."""

    def process_request(self, request):
        from .utils import get_system_setting
        from django.http import HttpResponse
        from django.template.loader import render_to_string

        # Check if maintenance mode is enabled
        maintenance_mode = get_system_setting("maintenance_mode", False)

        if maintenance_mode:
            # Allow superusers to access the site during maintenance
            if request.user.is_authenticated and request.user.is_superuser:
                return None

            # Render maintenance page
            content = render_to_string("core/maintenance.html")
            return HttpResponse(content, status=503)

        return None
