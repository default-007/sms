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
        self.lockout_duration = getattr(settings, "ACCOUNT_LOCKOUT_DURATION", 30)
        self.session_timeout = getattr(settings, "SESSION_TIMEOUT", 30)
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
        # Add security headers (but NOT CSP - that's handled by django-csp)
        response["X-Content-Type-Options"] = "nosniff"
        response["X-Frame-Options"] = "DENY"
        response["X-XSS-Protection"] = "1; mode=block"
        response["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # REMOVE/COMMENT OUT this line - CSP is now handled by django-csp
        # if not request.path.startswith("/api/"):
        #     response["Content-Security-Policy"] = self._get_csp_header()

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

    """ def _get_csp_header(self):
        # Generate Content Security Policy header.
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
        ) """


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
        active_sessions = UserSession.objects.concurrent_sessions(request.user)

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


class AuthenticationRateLimitMiddleware:
    """Rate limiting middleware for authentication endpoints."""

    def __init__(self, get_response):
        self.get_response = get_response

        # Get rate limiting settings
        rate_settings = getattr(settings, "RATE_LIMITING", {})
        login_settings = rate_settings.get("LOGIN_ATTEMPTS", {})

        self.max_attempts = self._parse_rate(login_settings.get("RATE", "10/hour"))
        self.window_seconds = self._parse_window(login_settings.get("RATE", "10/hour"))
        self.burst_allowance = login_settings.get("BURST", 3)

        # Protected endpoints
        self.protected_paths = [
            "/accounts/login/",
            "/accounts/api/login/",
            "/accounts/password-reset/",
        ]

    def __call__(self, request):
        # Check if this is a protected endpoint
        if any(request.path.startswith(path) for path in self.protected_paths):
            if request.method == "POST":
                if self._is_rate_limited(request):
                    return self._rate_limit_response(request)

                # Store the request for potential rate limiting
                response = self.get_response(request)

                # If authentication failed, increment counter
                if self._is_auth_failure(response):
                    self._increment_rate_limit(request)
                else:
                    # If successful, reset the counter
                    self._reset_rate_limit(request)

                return response

        return self.get_response(request)

    def _parse_rate(self, rate_string):
        """Parse rate string like '10/hour' to get max attempts."""
        try:
            return int(rate_string.split("/")[0])
        except (ValueError, IndexError):
            return 10  # Default

    def _parse_window(self, rate_string):
        """Parse rate string like '10/hour' to get window in seconds."""
        try:
            unit = rate_string.split("/")[1].lower()
            if unit == "minute":
                return 60
            elif unit == "hour":
                return 3600
            elif unit == "day":
                return 86400
            else:
                return 3600  # Default to hour
        except (ValueError, IndexError):
            return 3600

    def _get_client_key(self, request):
        """Get unique key for client identification."""
        client_info = get_client_info(request)
        ip_address = client_info.get("ip_address", "unknown")
        return f"auth_rate_limit:{ip_address}"

    def _is_rate_limited(self, request):
        """Check if client is rate limited."""
        key = self._get_client_key(request)
        current_attempts = cache.get(key, 0)
        return current_attempts >= self.max_attempts

    def _increment_rate_limit(self, request):
        """Increment rate limit counter for client."""
        key = self._get_client_key(request)
        current_attempts = cache.get(key, 0)
        cache.set(key, current_attempts + 1, timeout=self.window_seconds)

        # Log rate limiting
        if current_attempts + 1 >= self.max_attempts:
            logger.warning(f"Rate limit exceeded for key: {key}")

    def _reset_rate_limit(self, request):
        """Reset rate limit counter for successful authentication."""
        key = self._get_client_key(request)
        cache.delete(key)

    def _rate_limit_response(self, request):
        """Return rate limit exceeded response."""
        if request.content_type == "application/json" or request.path.startswith(
            "/api/"
        ):
            return JsonResponse(
                {
                    "error": "Rate limit exceeded",
                    "message": "Too many authentication attempts. Please try again later.",
                    "retry_after": self.window_seconds,
                },
                status=429,
            )
        else:
            return HttpResponseForbidden(
                "Too many authentication attempts. Please try again later."
            )

    def _is_auth_failure(self, response):
        """Check if response indicates authentication failure."""
        if response.status_code in [400, 401, 403]:
            return True

        # Check for form errors in HTML responses
        if hasattr(response, "content") and b"error" in response.content.lower():
            return True

        return False


class SessionSecurityMiddleware:
    """Middleware for session security and management."""

    def __init__(self, get_response):
        self.get_response = get_response

        # Get session settings
        self.session_timeout = (
            getattr(settings, "SESSION_TIMEOUT", 30) * 60
        )  # Convert to seconds
        self.max_concurrent_sessions = getattr(settings, "MAX_CONCURRENT_SESSIONS", 5)

    def __call__(self, request):
        if request.user.is_authenticated:
            # Check session timeout
            if self._is_session_expired(request):
                self._handle_expired_session(request)
                return self.get_response(request)

            # Update session activity
            self._update_session_activity(request)

            # Check concurrent sessions
            self._check_concurrent_sessions(request)

        response = self.get_response(request)
        return response

    def _is_session_expired(self, request):
        """Check if session has expired due to inactivity."""
        last_activity = request.session.get("last_activity")
        if not last_activity:
            return False

        last_activity_time = timezone.datetime.fromisoformat(last_activity)
        inactive_duration = timezone.now() - last_activity_time

        return inactive_duration.total_seconds() > self.session_timeout

    def _handle_expired_session(self, request):
        """Handle expired session."""
        logger.info(f"Session expired for user {request.user.id}")

        # Log session expiry
        UserAuditLog.objects.create(
            user=request.user,
            action="session_expired",
            description="Session expired due to inactivity",
            ip_address=get_client_info(request).get("ip_address"),
        )

        # Logout user
        logout(request)

    def _update_session_activity(self, request):
        """Update last activity timestamp."""
        request.session["last_activity"] = timezone.now().isoformat()

        # Update UserSession record if exists
        session_key = request.session.session_key
        if session_key:
            UserSession.objects.filter(
                user=request.user, session_key=session_key
            ).update(last_activity=timezone.now())

    def _check_concurrent_sessions(self, request):
        """Check and manage concurrent sessions."""
        user = request.user
        current_session_key = request.session.session_key

        # Get active sessions for user
        active_sessions = UserSession.objects.filter(
            user=user, is_active=True
        ).order_by("last_activity")

        # If too many sessions, deactivate oldest ones
        if active_sessions.count() > self.max_concurrent_sessions:
            sessions_to_deactivate = active_sessions[: -self.max_concurrent_sessions]

            for session in sessions_to_deactivate:
                session.is_active = False
                session.save()

                logger.info(
                    f"Deactivated old session for user {user.id}: {session.session_key}"
                )


class SuspiciousActivityMiddleware:
    """Middleware to detect and handle suspicious authentication activity."""

    def __init__(self, get_response):
        self.get_response = get_response

        # Suspicious activity thresholds
        self.suspicious_threshold = getattr(
            settings, "SUSPICIOUS_ACTIVITY_THRESHOLD", 10
        )
        self.check_window_hours = 1

    def __call__(self, request):
        response = self.get_response(request)

        # Check for suspicious activity after authentication attempts
        if self._is_auth_endpoint(request) and request.method == "POST":
            self._check_suspicious_activity(request, response)

        return response

    def _is_auth_endpoint(self, request):
        """Check if request is to an authentication endpoint."""
        auth_paths = ["/accounts/login/", "/accounts/api/login/"]
        return any(request.path.startswith(path) for path in auth_paths)

    def _check_suspicious_activity(self, request, response):
        """Check for suspicious activity patterns."""
        client_info = get_client_info(request)
        ip_address = client_info.get("ip_address")

        if not ip_address or ip_address == "unknown":
            return

        # Check recent activity from this IP
        since_time = timezone.now() - timedelta(hours=self.check_window_hours)

        recent_attempts = UserAuditLog.objects.filter(
            ip_address=ip_address, action="login", timestamp__gte=since_time
        ).count()

        if recent_attempts >= self.suspicious_threshold:
            self._handle_suspicious_activity(request, ip_address, recent_attempts)

    def _handle_suspicious_activity(self, request, ip_address, attempt_count):
        """Handle detected suspicious activity."""
        logger.warning(
            f"Suspicious activity detected from IP {ip_address}: "
            f"{attempt_count} login attempts in {self.check_window_hours} hour(s)"
        )

        # Log security event
        UserAuditLog.objects.create(
            action="suspicious_activity",
            description=f"Suspicious login activity: {attempt_count} attempts",
            ip_address=ip_address,
            user_agent=get_client_info(request).get("user_agent"),
            severity="high",
            extra_data={
                "attempt_count": attempt_count,
                "time_window_hours": self.check_window_hours,
                "threshold": self.suspicious_threshold,
            },
        )

        # Optional: Add IP to temporary blacklist
        if getattr(settings, "AUTO_BLACKLIST_SUSPICIOUS_IPS", False):
            self._temporary_blacklist_ip(ip_address)

    def _temporary_blacklist_ip(self, ip_address):
        """Add IP to temporary blacklist."""
        blacklist_key = f"blacklisted_ip:{ip_address}"
        blacklist_duration = 3600  # 1 hour

        cache.set(blacklist_key, True, timeout=blacklist_duration)

        logger.info(f"Temporarily blacklisted IP: {ip_address}")


class IPBlacklistMiddleware:
    """Middleware to block blacklisted IP addresses."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        client_info = get_client_info(request)
        ip_address = client_info.get("ip_address")

        if self._is_ip_blacklisted(ip_address):
            logger.warning(f"Blocked request from blacklisted IP: {ip_address}")

            return JsonResponse(
                {
                    "error": "Access denied",
                    "message": "Your IP address has been temporarily blocked due to suspicious activity.",
                },
                status=403,
            )

        return self.get_response(request)

    def _is_ip_blacklisted(self, ip_address):
        """Check if IP is blacklisted."""
        if not ip_address or ip_address == "unknown":
            return False

        # Check temporary blacklist (cache)
        temp_blacklist_key = f"blacklisted_ip:{ip_address}"
        if cache.get(temp_blacklist_key):
            return True

        # Check permanent blacklist (database)
        try:
            from .models import IpBlacklist

            blacklist_entry = IpBlacklist.objects.filter(
                ip_address=ip_address, is_active=True
            ).first()

            if blacklist_entry:
                # Check if blacklist entry has expired
                if (
                    blacklist_entry.expires_at
                    and blacklist_entry.expires_at <= timezone.now()
                ):
                    blacklist_entry.is_active = False
                    blacklist_entry.save()
                    return False

                return True

        except ImportError:
            # IpBlacklist model not available
            pass

        return False


class AuthenticationAuditMiddleware:
    """Middleware for comprehensive authentication auditing."""

    def __init__(self, get_response):
        self.get_response = get_response

        # Audit settings
        self.log_all_requests = getattr(settings, "LOG_ALL_AUTH_REQUESTS", False)
        self.log_successful_auth = getattr(settings, "LOG_SUCCESSFUL_AUTH", True)
        self.log_failed_auth = getattr(settings, "LOG_FAILED_AUTH", True)

    def __call__(self, request):
        start_time = time.time()

        # Process request
        response = self.get_response(request)

        # Log authentication requests
        if self._should_log_request(request):
            processing_time = time.time() - start_time
            self._log_auth_request(request, response, processing_time)

        return response

    def _should_log_request(self, request):
        """Determine if request should be logged."""
        if self.log_all_requests:
            return True

        # Log authentication-related requests
        auth_paths = ["/accounts/", "/api/auth/"]
        return any(request.path.startswith(path) for path in auth_paths)

    def _log_auth_request(self, request, response, processing_time):
        """Log authentication request details."""
        client_info = get_client_info(request)

        # Determine log level based on response
        if response.status_code >= 400:
            log_level = "warning"
        elif response.status_code >= 300:
            log_level = "info"
        else:
            log_level = "info"

        # Create audit log entry
        UserAuditLog.objects.create(
            user=request.user if request.user.is_authenticated else None,
            action="http_request",
            description=f"{request.method} {request.path}",
            ip_address=client_info.get("ip_address"),
            user_agent=client_info.get("user_agent"),
            extra_data={
                "status_code": response.status_code,
                "processing_time": round(processing_time, 3),
                "request_method": request.method,
                "request_path": request.path,
                "query_params": dict(request.GET),
                "content_type": request.content_type,
                "is_ajax": request.headers.get("X-Requested-With") == "XMLHttpRequest",
                "is_api": request.path.startswith("/api/"),
            },
            severity="low",
        )


class SecurityHeadersMiddleware:
    """Middleware to add security headers to authentication responses."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # Add security headers for authentication pages
        if self._is_auth_related(request):
            self._add_security_headers(response)

        return response

    def _is_auth_related(self, request):
        """Check if request is authentication-related."""
        auth_paths = ["/accounts/", "/api/auth/"]
        return any(request.path.startswith(path) for path in auth_paths)

    def _add_security_headers(self, response):
        """Add security headers to response."""
        # Prevent caching of authentication pages
        response["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response["Pragma"] = "no-cache"
        response["Expires"] = "0"

        # Content security policy for auth pages
        response["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "font-src 'self'; "
            "connect-src 'self'; "
            "frame-ancestors 'none';"
        )

        # Additional security headers
        response["X-Content-Type-Options"] = "nosniff"
        response["X-Frame-Options"] = "DENY"
        response["X-XSS-Protection"] = "1; mode=block"
        response["Referrer-Policy"] = "strict-origin-when-cross-origin"
