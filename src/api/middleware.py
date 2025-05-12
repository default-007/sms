from django.utils.deprecation import MiddlewareMixin
import json
import time


class APIRequestLogMiddleware(MiddlewareMixin):
    """
    Middleware to log API requests for monitoring and debugging.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def process_request(self, request):
        # Only log API requests
        if request.path.startswith("/api/"):
            request.api_start_time = time.time()

        return None

    def process_response(self, request, response):
        # Only log API requests
        if not request.path.startswith("/api/") or not hasattr(
            request, "api_start_time"
        ):
            return response

        # Calculate request duration
        duration = time.time() - request.api_start_time

        # Log request details
        log_data = {
            "path": request.path,
            "method": request.method,
            "status_code": response.status_code,
            "duration_ms": round(duration * 1000, 2),
            "user_id": request.user.id if request.user.is_authenticated else None,
            "ip": request.META.get("REMOTE_ADDR"),
        }

        # Log to console in development
        from django.conf import settings

        if settings.DEBUG:
            print(f"API Request: {json.dumps(log_data)}")

        # Create audit log for write operations
        if (
            request.method in ["POST", "PUT", "PATCH", "DELETE"]
            and request.user.is_authenticated
        ):
            from src.core.utils import create_audit_log

            action_map = {
                "POST": "create",
                "PUT": "update",
                "PATCH": "update",
                "DELETE": "delete",
            }
            # Determine entity type from URL
            path_parts = request.path.strip("/").split("/")
            entity_type = path_parts[1] if len(path_parts) > 1 else "unknown"
            entity_id = path_parts[2] if len(path_parts) > 2 else None

            create_audit_log(
                user=request.user,
                action=action_map.get(request.method, "other"),
                entity_type=entity_type,
                entity_id=entity_id,
                request=request,
            )

        return response
