# src/api/middleware.py
"""Custom API Middleware"""

import time
import json
import logging
from django.utils.deprecation import MiddlewareMixin
from django.http import JsonResponse
from django.core.cache import cache
from django.conf import settings
from django.utils import timezone
import uuid

logger = logging.getLogger(__name__)


class APIRequestMiddleware(MiddlewareMixin):
    """Middleware for API request processing and logging"""

    def process_request(self, request):
        """Process incoming API requests"""

        # Skip non-API requests
        if not request.path.startswith("/api/"):
            return None

        # Add request start time
        request.start_time = time.time()

        # Generate request ID
        request.id = str(uuid.uuid4())

        # Add request ID to response headers
        request.META["HTTP_X_REQUEST_ID"] = request.id
        request.META["HTTP_X_REQUEST_TIME"] = str(int(time.time()))

        # Log request
        self._log_request(request)

        return None

    def process_response(self, request, response):
        """Process API responses"""

        # Skip non-API requests
        if not request.path.startswith("/api/"):
            return response

        # Add request ID to response headers
        response["X-Request-ID"] = getattr(request, "id", "unknown")

        # Add processing time
        if hasattr(request, "start_time"):
            processing_time = time.time() - request.start_time
            response["X-Processing-Time"] = f"{processing_time:.3f}s"

            # Log slow requests
            if processing_time > getattr(settings, "SLOW_REQUEST_THRESHOLD", 2.0):
                logger.warning(
                    f"Slow request: {request.path} took {processing_time:.3f}s"
                )

        # Add API version
        response["X-API-Version"] = getattr(settings, "API_VERSION", "2.0")

        # Log response
        self._log_response(request, response)

        return response

    def _log_request(self, request):
        """Log API request details"""
        try:
            log_data = {
                "request_id": getattr(request, "id", "unknown"),
                "method": request.method,
                "path": request.path,
                "user": (
                    str(request.user) if request.user.is_authenticated else "anonymous"
                ),
                "ip": self._get_client_ip(request),
                "user_agent": request.META.get("HTTP_USER_AGENT", ""),
                "timestamp": timezone.now().isoformat(),
            }

            logger.info(f"API Request: {json.dumps(log_data)}")
        except Exception as e:
            logger.error(f"Failed to log request: {e}")

    def _log_response(self, request, response):
        """Log API response details"""
        try:
            processing_time = 0
            if hasattr(request, "start_time"):
                processing_time = time.time() - request.start_time

            log_data = {
                "request_id": getattr(request, "id", "unknown"),
                "status_code": response.status_code,
                "processing_time": f"{processing_time:.3f}s",
                "content_length": len(response.content) if response.content else 0,
                "timestamp": timezone.now().isoformat(),
            }

            logger.info(f"API Response: {json.dumps(log_data)}")
        except Exception as e:
            logger.error(f"Failed to log response: {e}")

    def _get_client_ip(self, request):
        """Get client IP address"""
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            ip = x_forwarded_for.split(",")[0]
        else:
            ip = request.META.get("REMOTE_ADDR")
        return ip


class CORSMiddleware(MiddlewareMixin):
    """Custom CORS middleware for API"""

    def process_response(self, request, response):
        """Add CORS headers to API responses"""

        if request.path.startswith("/api/"):
            # Allow origins
            allowed_origins = getattr(settings, "CORS_ALLOWED_ORIGINS", ["*"])
            origin = request.META.get("HTTP_ORIGIN")

            if "*" in allowed_origins or origin in allowed_origins:
                response["Access-Control-Allow-Origin"] = origin or "*"

            # Allow methods
            response["Access-Control-Allow-Methods"] = (
                "GET, POST, PUT, PATCH, DELETE, OPTIONS"
            )

            # Allow headers
            response["Access-Control-Allow-Headers"] = (
                "Accept, Accept-Language, Content-Language, Content-Type, "
                "Authorization, X-API-Key, X-Requested-With"
            )

            # Allow credentials
            response["Access-Control-Allow-Credentials"] = "true"

            # Max age
            response["Access-Control-Max-Age"] = "86400"

        return response


class RateLimitMiddleware(MiddlewareMixin):
    """Custom rate limiting middleware"""

    def process_request(self, request):
        """Check rate limits before processing request"""

        if not request.path.startswith("/api/"):
            return None

        # Skip rate limiting for certain paths
        exempt_paths = getattr(settings, "RATE_LIMIT_EXEMPT_PATHS", [])
        if any(request.path.startswith(path) for path in exempt_paths):
            return None

        # Check rate limit
        if not self._check_rate_limit(request):
            return JsonResponse(
                {
                    "success": False,
                    "error": {
                        "code": "rate_limit_exceeded",
                        "message": "Rate limit exceeded. Please try again later.",
                        "details": None,
                    },
                },
                status=429,
            )

        return None

    def _check_rate_limit(self, request):
        """Check if request is within rate limits"""
        try:
            # Get client identifier
            if request.user.is_authenticated:
                client_id = f"user_{request.user.id}"
            else:
                client_id = f"ip_{self._get_client_ip(request)}"

            # Get rate limit settings
            rate_limit = getattr(settings, "API_RATE_LIMIT", "1000/hour")
            limit, period = self._parse_rate_limit(rate_limit)

            # Check cache
            cache_key = f"rate_limit_{client_id}"
            current_requests = cache.get(cache_key, 0)

            if current_requests >= limit:
                return False

            # Increment counter
            cache.set(cache_key, current_requests + 1, period)
            return True

        except Exception as e:
            logger.error(f"Rate limit check failed: {e}")
            return True  # Allow request if rate limiting fails

    def _parse_rate_limit(self, rate_limit):
        """Parse rate limit string (e.g., '1000/hour')"""
        try:
            limit, period_str = rate_limit.split("/")
            limit = int(limit)

            period_map = {"second": 1, "minute": 60, "hour": 3600, "day": 86400}

            period = period_map.get(period_str, 3600)
            return limit, period
        except Exception:
            return 1000, 3600  # Default: 1000/hour

    def _get_client_ip(self, request):
        """Get client IP address"""
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            ip = x_forwarded_for.split(",")[0]
        else:
            ip = request.META.get("REMOTE_ADDR")
        return ip


class SecurityHeadersMiddleware(MiddlewareMixin):
    """Add security headers to API responses"""

    def process_response(self, request, response):
        """Add security headers"""

        if request.path.startswith("/api/"):
            # Security headers
            response["X-Content-Type-Options"] = "nosniff"
            response["X-Frame-Options"] = "DENY"
            response["X-XSS-Protection"] = "1; mode=block"
            response["Referrer-Policy"] = "strict-origin-when-cross-origin"

            # Content Security Policy for API
            response["Content-Security-Policy"] = (
                "default-src 'none'; frame-ancestors 'none';"
            )

            # HSTS (only for HTTPS)
            if request.is_secure():
                response["Strict-Transport-Security"] = (
                    "max-age=31536000; includeSubDomains"
                )

        return response
