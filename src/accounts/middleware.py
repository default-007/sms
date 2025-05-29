import logging

from django.conf import settings
from django.contrib.auth import get_user_model, logout
from django.core.cache import cache
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.deprecation import MiddlewareMixin

from .models import UserAuditLog, UserSession

logger = logging.getLogger(__name__)
User = get_user_model()


class SecurityMiddleware(MiddlewareMixin):
    """Enhanced security middleware for user authentication and session management."""

    def __init__(self, get_response):
        self.get_response = get_response
        self.max_failed_attempts = getattr(settings, "MAX_FAILED_LOGIN_ATTEMPTS", 5)
        self.lockout_duration = getattr(
            settings, "ACCOUNT_LOCKOUT_DURATION", 30
        )  # minutes
        self.session_timeout = getattr(settings, "SESSION_TIMEOUT", 30)  # minutes
        self.max_concurrent_sessions = getattr(settings, "MAX_CONCURRENT_SESSIONS", 5)
        super().__init__(get_response)

    def process_request(self, request):
        """Process request for security checks."""
        if request.user.is_authenticated:
            # Check for account lockout
            if request.user.is_account_locked():
                logout(request)
                if request.path.startswith("/api/"):
                    return JsonResponse(
                        {
                            "error": "Account is locked due to multiple failed login attempts."
                        },
                        status=423,
                    )
                else:
                    return redirect(reverse("accounts:login") + "?locked=1")

            # Check for required password change
            if (
                request.user.requires_password_change
                and not request.path.startswith("/accounts/password-change/")
                and not request.path.startswith("/api/")
                and not request.path.startswith("/accounts/logout/")
            ):
                return redirect("accounts:password_change")

            # Update session activity
            self._update_session_activity(request)

            # Check session timeout
            if self._is_session_expired(request):
                logout(request)
                if request.path.startswith("/api/"):
                    return JsonResponse({"error": "Session expired."}, status=401)
                else:
                    return redirect(reverse("accounts:login") + "?expired=1")

    def process_response(self, request, response):
        """Process response for additional security measures."""
        # Add security headers
        response["X-Content-Type-Options"] = "nosniff"
        response["X-Frame-Options"] = "DENY"
        response["X-XSS-Protection"] = "1; mode=block"
        response["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Add CSP header for non-API responses
        if not request.path.startswith("/api/"):
            response["Content-Security-Policy"] = self._get_csp_header()

        return response

    def _update_session_activity(self, request):
        """Update session activity timestamp."""
        if hasattr(request, "session") and request.session.session_key:
            session_key = request.session.session_key
            ip_address = self._get_client_ip(request)
            user_agent = request.META.get("HTTP_USER_AGENT", "")

            # Update or create session record
            session_obj, created = UserSession.objects.get_or_create(
                session_key=session_key,
                defaults={
                    "user": request.user,
                    "ip_address": ip_address,
                    "user_agent": user_agent,
                    "is_active": True,
                },
            )

            if not created:
                session_obj.last_activity = timezone.now()
                session_obj.save(update_fields=["last_activity"])

    def _is_session_expired(self, request):
        """Check if the session has expired."""
        if not hasattr(request, "session") or not request.session.session_key:
            return False

        try:
            session_obj = UserSession.objects.get(
                session_key=request.session.session_key, is_active=True
            )

            last_activity = session_obj.last_activity
            timeout_delta = timezone.timedelta(minutes=self.session_timeout)

            return timezone.now() - last_activity > timeout_delta
        except UserSession.DoesNotExist:
            return True

    def _get_client_ip(self, request):
        """Get the client's IP address."""
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            ip = x_forwarded_for.split(",")[0]
        else:
            ip = request.META.get("REMOTE_ADDR")
        return ip

    def _get_csp_header(self):
        """Generate Content Security Policy header."""
        return (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' cdn.jsdelivr.net; "
            "img-src 'self' data: blob:; "
            "font-src 'self' cdn.jsdelivr.net; "
            "connect-src 'self'; "
            "media-src 'self'; "
            "object-src 'none'; "
            "base-uri 'self'; "
            "form-action 'self'"
        )


class RateLimitMiddleware(MiddlewareMixin):
    """Rate limiting middleware to prevent abuse."""

    def __init__(self, get_response):
        self.get_response = get_response
        self.rate_limits = getattr(
            settings,
            "RATE_LIMITS",
            {
                "login": {"requests": 5, "window": 300},  # 5 attempts per 5 minutes
                "api": {"requests": 100, "window": 3600},  # 100 requests per hour
                "password_reset": {
                    "requests": 3,
                    "window": 900,
                },  # 3 attempts per 15 minutes
            },
        )
        super().__init__(get_response)

    def process_request(self, request):
        """Check rate limits for specific endpoints."""
        # Skip rate limiting for superusers
        if request.user.is_authenticated and request.user.is_superuser:
            return None

        # Determine rate limit type based on request path
        limit_type = self._get_limit_type(request.path)
        if not limit_type:
            return None

        # Get rate limit configuration
        rate_config = self.rate_limits.get(limit_type)
        if not rate_config:
            return None

        # Check rate limit
        if self._is_rate_limited(request, limit_type, rate_config):
            if request.path.startswith("/api/"):
                return JsonResponse(
                    {"error": "Rate limit exceeded. Please try again later."},
                    status=429,
                )
            else:
                # You could redirect to a rate limit page or show an error
                return JsonResponse({"error": "Too many requests."}, status=429)

        return None

    def _get_limit_type(self, path):
        """Determine rate limit type based on request path."""
        if path.startswith("/accounts/login/"):
            return "login"
        elif path.startswith("/accounts/password-reset/"):
            return "password_reset"
        elif path.startswith("/api/"):
            return "api"
        return None

    def _is_rate_limited(self, request, limit_type, rate_config):
        """Check if request exceeds rate limit."""
        ip_address = self._get_client_ip(request)
        cache_key = f"rate_limit:{limit_type}:{ip_address}"

        # Get current request count
        request_count = cache.get(cache_key, 0)

        # Check if limit exceeded
        if request_count >= rate_config["requests"]:
            return True

        # Increment counter
        cache.set(cache_key, request_count + 1, rate_config["window"])
        return False

    def _get_client_ip(self, request):
        """Get the client's IP address."""
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            ip = x_forwarded_for.split(",")[0]
        else:
            ip = request.META.get("REMOTE_ADDR")
        return ip


class AuditMiddleware(MiddlewareMixin):
    """Middleware for auditing user actions."""

    def __init__(self, get_response):
        self.get_response = get_response
        self.audit_paths = getattr(
            settings,
            "AUDIT_PATHS",
            [
                "/accounts/",
                "/api/",
            ],
        )
        self.exclude_paths = getattr(
            settings,
            "AUDIT_EXCLUDE_PATHS",
            [
                "/accounts/login/",
                "/api/auth/login/",
                "/static/",
                "/media/",
            ],
        )
        super().__init__(get_response)

    def process_request(self, request):
        """Store request information for potential audit logging."""
        if self._should_audit(request):
            request._audit_start_time = timezone.now()
            request._audit_ip = self._get_client_ip(request)
            request._audit_user_agent = request.META.get("HTTP_USER_AGENT", "")

    def process_response(self, request, response):
        """Log the request if it meets audit criteria."""
        if hasattr(request, "_audit_start_time") and self._should_log_response(
            request, response
        ):

            self._create_audit_log(request, response)

        return response

    def _should_audit(self, request):
        """Determine if request should be audited."""
        path = request.path

        # Check if path should be audited
        if not any(path.startswith(audit_path) for audit_path in self.audit_paths):
            return False

        # Check exclusions
        if any(path.startswith(exclude_path) for exclude_path in self.exclude_paths):
            return False

        return True

    def _should_log_response(self, request, response):
        """Determine if response should be logged."""
        # Log all POST, PUT, PATCH, DELETE requests
        if request.method in ["POST", "PUT", "PATCH", "DELETE"]:
            return True

        # Log failed authentications
        if response.status_code in [401, 403]:
            return True

        # Log server errors
        if response.status_code >= 500:
            return True

        return False

    def _create_audit_log(self, request, response):
        """Create an audit log entry."""
        try:
            # Determine action based on method and path
            action = self._determine_action(request, response)

            # Create description
            description = f"{request.method} {request.path} - {response.status_code}"

            # Extra data
            extra_data = {
                "method": request.method,
                "path": request.path,
                "status_code": response.status_code,
                "user_agent": getattr(request, "_audit_user_agent", ""),
            }

            # Add query parameters if present
            if request.GET:
                extra_data["query_params"] = dict(request.GET)

            UserAuditLog.objects.create(
                user=request.user if request.user.is_authenticated else None,
                action=action,
                description=description,
                ip_address=getattr(request, "_audit_ip", None),
                user_agent=getattr(request, "_audit_user_agent", ""),
                extra_data=extra_data,
            )
        except Exception as e:
            logger.error(f"Failed to create audit log: {str(e)}")

    def _determine_action(self, request, response):
        """Determine the action type for the audit log."""
        path = request.path.lower()
        method = request.method

        # Authentication actions
        if "login" in path:
            return "login" if response.status_code < 400 else "login_failed"
        elif "logout" in path:
            return "logout"
        elif "password" in path:
            return "password_change"

        # CRUD actions
        if method == "POST":
            return "create"
        elif method in ["PUT", "PATCH"]:
            return "update"
        elif method == "DELETE":
            return "delete"
        elif method == "GET":
            return "view"

        return "unknown"

    def _get_client_ip(self, request):
        """Get the client's IP address."""
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            ip = x_forwarded_for.split(",")[0]
        else:
            ip = request.META.get("REMOTE_ADDR")
        return ip


class SessionSecurityMiddleware(MiddlewareMixin):
    """Middleware for enhanced session security."""

    def __init__(self, get_response):
        self.get_response = get_response
        self.max_concurrent_sessions = getattr(settings, "MAX_CONCURRENT_SESSIONS", 5)
        super().__init__(get_response)

    def process_request(self, request):
        """Handle session security checks."""
        if request.user.is_authenticated:
            # Check concurrent sessions
            self._check_concurrent_sessions(request)

            # Session hijacking protection
            if self._detect_session_hijacking(request):
                logger.warning(
                    f"Potential session hijacking detected for user {request.user.username}"
                )
                logout(request)

                # Create audit log
                UserAuditLog.objects.create(
                    user=request.user,
                    action="account_lock",
                    description="Potential session hijacking detected",
                    ip_address=self._get_client_ip(request),
                    user_agent=request.META.get("HTTP_USER_AGENT", ""),
                )

                if request.path.startswith("/api/"):
                    return JsonResponse(
                        {"error": "Session security violation detected."}, status=401
                    )
                else:
                    return redirect(reverse("accounts:login") + "?security=1")

    def _check_concurrent_sessions(self, request):
        """Check and limit concurrent sessions."""
        if not self.max_concurrent_sessions:
            return

        # Count active sessions for the user
        active_sessions = UserSession.objects.get_concurrent_sessions(request.user)

        if active_sessions >= self.max_concurrent_sessions:
            # Terminate oldest sessions
            UserSession.objects.terminate_user_sessions(
                request.user, exclude_session=request.session.session_key
            )

    def _detect_session_hijacking(self, request):
        """Detect potential session hijacking."""
        if not hasattr(request, "session") or not request.session.session_key:
            return False

        try:
            session_obj = UserSession.objects.get(
                session_key=request.session.session_key, is_active=True
            )

            # Check for IP address changes
            current_ip = self._get_client_ip(request)
            if session_obj.ip_address != current_ip:
                # Allow IP changes for mobile users or proxies, but log them
                logger.info(
                    f"IP change detected for user {request.user.username}: {session_obj.ip_address} -> {current_ip}"
                )
                # Update IP address
                session_obj.ip_address = current_ip
                session_obj.save(update_fields=["ip_address"])

            # Check for User-Agent changes (more suspicious)
            current_user_agent = request.META.get("HTTP_USER_AGENT", "")
            if session_obj.user_agent != current_user_agent:
                # This is more suspicious, but browsers can update
                logger.warning(
                    f"User-Agent change detected for user {request.user.username}"
                )
                return True

            return False
        except UserSession.DoesNotExist:
            # Session not found in our records - could be suspicious
            return True

    def _get_client_ip(self, request):
        """Get the client's IP address."""
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            ip = x_forwarded_for.split(",")[0]
        else:
            ip = request.META.get("REMOTE_ADDR")
        return ip
