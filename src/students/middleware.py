# students/middleware.py
import logging
import time

from django.conf import settings
from django.core.cache import cache
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger(__name__)


class StudentQueryOptimizationMiddleware(MiddlewareMixin):
    """Middleware to monitor and optimize student-related database queries"""

    def process_request(self, request):
        # Start timing
        request._query_start_time = time.time()

        # Store initial query count if in debug mode
        if settings.DEBUG:
            from django.db import connection

            request._initial_queries = len(connection.queries)

    def process_response(self, request, response):
        # Calculate total time
        if hasattr(request, "_query_start_time"):
            total_time = time.time() - request._query_start_time

            # Log slow requests
            if total_time > 1.0:  # Log requests taking more than 1 second
                logger.warning(f"Slow request: {request.path} took {total_time:.2f}s")

            # Log query count for student-related views
            if settings.DEBUG and "/students/" in request.path:
                from django.db import connection

                query_count = len(connection.queries) - getattr(
                    request, "_initial_queries", 0
                )

                if query_count > 10:  # Log if more than 10 queries
                    logger.warning(
                        f"High query count: {request.path} executed {query_count} queries"
                    )

        return response


class StudentCacheMiddleware(MiddlewareMixin):
    """Middleware to handle student-related caching"""

    def process_request(self, request):
        # Don't cache for authenticated admin users making changes
        if (
            request.user.is_authenticated
            and request.user.is_staff
            and request.method in ["POST", "PUT", "PATCH", "DELETE"]
        ):
            return None

        # Check for cached response for student list views
        if request.method == "GET" and "/students/" in request.path:
            cache_key = self._get_cache_key(request)
            cached_response = cache.get(cache_key)

            if cached_response:
                # Add cache hit header for debugging
                cached_response["X-Cache"] = "HIT"
                return cached_response

        return None

    def process_response(self, request, response):
        # Cache successful GET responses for student views
        if (
            request.method == "GET"
            and response.status_code == 200
            and "/students/" in request.path
            and not request.user.is_staff
        ):

            cache_key = self._get_cache_key(request)
            # Cache for 5 minutes
            cache.set(cache_key, response, 300)
            response["X-Cache"] = "MISS"

        return response

    def _get_cache_key(self, request):
        """Generate cache key based on request path and parameters"""
        path = request.path
        params = sorted(request.GET.items())
        params_str = "&".join([f"{k}={v}" for k, v in params])
        user_id = request.user.id if request.user.is_authenticated else "anonymous"

        return f"student_view_{user_id}_{path}_{params_str}"


class StudentPermissionMiddleware(MiddlewareMixin):
    """Middleware to handle student-specific permission checking"""

    def process_view(self, request, view_func, view_args, view_kwargs):
        # Check if this is a student-related view
        if not request.path.startswith("/students/"):
            return None

        # Skip for staff users
        if request.user.is_staff:
            return None

        # Check student-specific permissions
        if not request.user.is_authenticated:
            return None

        # Handle student detail views
        if "pk" in view_kwargs and request.path.endswith(f"/{view_kwargs['pk']}/"):
            try:
                from .models import Student

                student = Student.objects.get(pk=view_kwargs["pk"])

                # Check if user can access this student
                if not self._can_access_student(request.user, student):
                    from django.contrib.auth.views import redirect_to_login

                    return redirect_to_login(request.get_full_path())

            except Student.DoesNotExist:
                pass

        return None

    def _can_access_student(self, user, student):
        """Check if user can access the given student"""
        # User is the student themselves
        if hasattr(user, "student_profile") and user.student_profile.id == student.id:
            return True

        # User is a parent of the student
        if hasattr(user, "parent_profile"):
            from .models import StudentParentRelation

            return StudentParentRelation.objects.filter(
                parent=user.parent_profile, student=student
            ).exists()

        return False


class StudentActivityTrackingMiddleware(MiddlewareMixin):
    """Middleware to track student activity for analytics"""

    def process_response(self, request, response):
        # Only track for authenticated users
        if not request.user.is_authenticated:
            return response

        # Only track successful requests
        if response.status_code != 200:
            return response

        # Track student-related activities
        if "/students/" in request.path:
            self._track_activity(request, response)

        return response

    def _track_activity(self, request, response):
        """Track user activity in student module"""
        try:
            activity_data = {
                "user_id": request.user.id,
                "path": request.path,
                "method": request.method,
                "timestamp": time.time(),
                "user_agent": request.META.get("HTTP_USER_AGENT", ""),
                "ip_address": self._get_client_ip(request),
            }

            # Store in cache for later processing
            cache_key = f"student_activity_{request.user.id}_{int(time.time())}"
            cache.set(cache_key, activity_data, 3600)  # Store for 1 hour

        except Exception as e:
            logger.error(f"Failed to track activity: {str(e)}")

    def _get_client_ip(self, request):
        """Get client IP address"""
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            ip = x_forwarded_for.split(",")[0]
        else:
            ip = request.META.get("REMOTE_ADDR")
        return ip


class StudentDataValidationMiddleware(MiddlewareMixin):
    """Middleware to validate student data submissions"""

    def process_request(self, request):
        # Only validate POST requests to student forms
        if (
            request.method in ["POST", "PUT", "PATCH"]
            and "/students/" in request.path
            and "form" in request.path_info.lower()
        ):

            # Add custom validation
            self._validate_student_data(request)

        return None

    def _validate_student_data(self, request):
        """Add additional validation for student data"""
        if "admission_number" in request.POST:
            admission_number = request.POST.get("admission_number")

            # Validate admission number format
            if not self._is_valid_admission_number(admission_number):
                logger.warning(
                    f"Invalid admission number format: {admission_number} from IP: {self._get_client_ip(request)}"
                )

        if "email" in request.POST:
            email = request.POST.get("email")

            # Check for suspicious email patterns
            if self._is_suspicious_email(email):
                logger.warning(
                    f"Suspicious email submitted: {email} from IP: {self._get_client_ip(request)}"
                )

    def _is_valid_admission_number(self, admission_number):
        """Validate admission number format"""
        if not admission_number:
            return False

        # Add your specific validation rules here
        # Example: must be alphanumeric and 6-20 characters
        return admission_number.isalnum() and 6 <= len(admission_number) <= 20

    def _is_suspicious_email(self, email):
        """Check for suspicious email patterns"""
        if not email:
            return False

        # List of suspicious domains or patterns
        suspicious_patterns = ["10minutemail.com", "tempmail.org", "guerrillamail.com"]

        return any(pattern in email.lower() for pattern in suspicious_patterns)

    def _get_client_ip(self, request):
        """Get client IP address"""
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            ip = x_forwarded_for.split(",")[0]
        else:
            ip = request.META.get("REMOTE_ADDR")
        return ip
