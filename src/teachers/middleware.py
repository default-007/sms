# src/teachers/middleware.py
"""
Middleware for the teachers module.
Handles logging, performance monitoring, security, and teacher-specific operations.
"""

import time
import logging
import json
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from django.utils.deprecation import MiddlewareMixin
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.core.cache import cache
from django.conf import settings
from django.utils import timezone
from django.contrib.auth.models import AnonymousUser
from django.urls import resolve, reverse
from django.db.models import Q

from src.teachers.models import Teacher, TeacherEvaluation
from src.teachers.exceptions import (
    TeacherModuleException,
    TeacherInactiveException,
    handle_teacher_exception,
)
from src.core.models import AuditLog

logger = logging.getLogger(__name__)


class TeacherAuditMiddleware(MiddlewareMixin):
    """Middleware for auditing teacher-related operations."""

    TEACHER_URLS = [
        "teachers:teacher-list",
        "teachers:teacher-detail",
        "teachers:teacher-create",
        "teachers:teacher-update",
        "teachers:teacher-delete",
        "teachers:teacher-evaluation-create",
        "teachers:teacher-assignment-create",
    ]

    SENSITIVE_OPERATIONS = [
        "teacher-delete",
        "teacher-update",
        "teacher-evaluation-create",
    ]

    def __init__(self, get_response):
        self.get_response = get_response
        super().__init__(get_response)

    def process_request(self, request):
        """Process incoming request for teacher operations."""
        # Store request start time for performance monitoring
        request._teacher_audit_start_time = time.time()

        # Check if this is a teacher-related request
        try:
            resolved = resolve(request.path_info)
            request._teacher_audit_url_name = resolved.url_name
            request._teacher_audit_namespace = resolved.namespace
        except:
            request._teacher_audit_url_name = None
            request._teacher_audit_namespace = None

        # Log sensitive operations
        if (
            request._teacher_audit_namespace == "teachers"
            and request._teacher_audit_url_name in self.SENSITIVE_OPERATIONS
        ):

            logger.info(
                f"Sensitive teacher operation initiated: {request._teacher_audit_url_name}",
                extra={
                    "user_id": (
                        request.user.id
                        if hasattr(request, "user") and request.user.is_authenticated
                        else None
                    ),
                    "ip_address": self._get_client_ip(request),
                    "user_agent": request.META.get("HTTP_USER_AGENT", ""),
                    "url": request.path,
                    "method": request.method,
                },
            )

    def process_response(self, request, response):
        """Process response for teacher operations."""
        # Calculate request duration
        if hasattr(request, "_teacher_audit_start_time"):
            duration = time.time() - request._teacher_audit_start_time

            # Log slow requests
            if duration > getattr(settings, "TEACHER_SLOW_REQUEST_THRESHOLD", 2.0):
                logger.warning(
                    f"Slow teacher operation detected: {duration:.2f}s",
                    extra={
                        "duration": duration,
                        "url": request.path,
                        "method": request.method,
                        "user_id": (
                            request.user.id
                            if hasattr(request, "user")
                            and request.user.is_authenticated
                            else None
                        ),
                    },
                )

        # Log completed operations
        if (
            hasattr(request, "_teacher_audit_namespace")
            and request._teacher_audit_namespace == "teachers"
            and hasattr(request, "_teacher_audit_url_name")
            and request._teacher_audit_url_name in self.SENSITIVE_OPERATIONS
        ):

            self._create_audit_log(request, response)

        return response

    def process_exception(self, request, exception):
        """Process exceptions in teacher operations."""
        if isinstance(exception, TeacherModuleException):
            error_info = handle_teacher_exception(exception)

            logger.error(
                f"Teacher module exception: {error_info['message']}",
                extra={
                    "error_code": error_info["code"],
                    "error_details": error_info["details"],
                    "user_id": (
                        request.user.id
                        if hasattr(request, "user") and request.user.is_authenticated
                        else None
                    ),
                    "url": request.path,
                    "method": request.method,
                },
            )

            # Return JSON error response for API requests
            if request.path.startswith("/api/"):
                return JsonResponse(error_info, status=400)

        return None

    def _get_client_ip(self, request):
        """Get client IP address."""
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            ip = x_forwarded_for.split(",")[0].strip()
        else:
            ip = request.META.get("REMOTE_ADDR")
        return ip

    def _create_audit_log(self, request, response):
        """Create audit log entry for teacher operations."""
        if not hasattr(request, "user") or not request.user.is_authenticated:
            return

        try:
            # Extract entity information from URL parameters
            entity_id = None
            entity_type = "Teacher"

            if "pk" in getattr(request, "resolver_match", {}).kwargs:
                entity_id = request.resolver_match.kwargs["pk"]
            elif "teacher_id" in getattr(request, "resolver_match", {}).kwargs:
                entity_id = request.resolver_match.kwargs["teacher_id"]

            # Determine action based on URL name and method
            action_map = {
                "teacher-create": "CREATE",
                "teacher-update": "UPDATE",
                "teacher-delete": "DELETE",
                "teacher-evaluation-create": "CREATE_EVALUATION",
                "teacher-assignment-create": "CREATE_ASSIGNMENT",
            }

            action = action_map.get(request._teacher_audit_url_name, "UNKNOWN")

            # Create audit log
            AuditLog.objects.create(
                user=request.user,
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                ip_address=self._get_client_ip(request),
                user_agent=request.META.get("HTTP_USER_AGENT", "")[:500],
                data_after={"response_status": response.status_code},
            )

        except Exception as e:
            logger.error(f"Failed to create audit log: {str(e)}")


class TeacherPerformanceMiddleware(MiddlewareMixin):
    """Middleware for monitoring teacher module performance."""

    def __init__(self, get_response):
        self.get_response = get_response
        super().__init__(get_response)

    def process_request(self, request):
        """Start performance monitoring."""
        if self._is_teacher_request(request):
            request._perf_start_time = time.time()
            request._perf_start_queries = self._get_query_count()

    def process_response(self, request, response):
        """End performance monitoring and log metrics."""
        if self._is_teacher_request(request) and hasattr(request, "_perf_start_time"):

            duration = time.time() - request._perf_start_time
            query_count = self._get_query_count() - getattr(
                request, "_perf_start_queries", 0
            )

            # Store metrics in cache for analysis
            self._store_performance_metrics(
                request, duration, query_count, response.status_code
            )

            # Log performance warnings
            if duration > 3.0:  # Slow request threshold
                logger.warning(
                    f"Slow teacher request: {request.path} took {duration:.2f}s with {query_count} queries"
                )

            if query_count > 50:  # High query count threshold
                logger.warning(
                    f"High query count in teacher request: {request.path} used {query_count} queries"
                )

        return response

    def _is_teacher_request(self, request):
        """Check if request is teacher-related."""
        return request.path.startswith("/teachers/") or request.path.startswith(
            "/api/teachers/"
        )

    def _get_query_count(self):
        """Get current database query count."""
        try:
            from django.db import connection

            return len(connection.queries)
        except:
            return 0

    def _store_performance_metrics(self, request, duration, query_count, status_code):
        """Store performance metrics in cache."""
        try:
            cache_key = f"teacher_perf_metrics_{datetime.now().strftime('%Y%m%d%H')}"
            metrics = cache.get(cache_key, [])

            metric = {
                "timestamp": timezone.now().isoformat(),
                "path": request.path,
                "method": request.method,
                "duration": round(duration, 3),
                "query_count": query_count,
                "status_code": status_code,
                "user_id": (
                    request.user.id
                    if hasattr(request, "user") and request.user.is_authenticated
                    else None
                ),
            }

            metrics.append(metric)

            # Keep only last 1000 metrics per hour
            if len(metrics) > 1000:
                metrics = metrics[-1000:]

            cache.set(cache_key, metrics, 3600)  # 1 hour

        except Exception as e:
            logger.error(f"Failed to store performance metrics: {str(e)}")


class TeacherSecurityMiddleware(MiddlewareMixin):
    """Middleware for teacher module security checks."""

    def __init__(self, get_response):
        self.get_response = get_response
        self.rate_limit_cache_prefix = "teacher_rate_limit"
        self.max_requests_per_minute = getattr(
            settings, "TEACHER_MAX_REQUESTS_PER_MINUTE", 60
        )
        super().__init__(get_response)

    def process_request(self, request):
        """Apply security checks to teacher requests."""
        if not self._is_teacher_request(request):
            return None

        # Rate limiting
        if self._is_rate_limited(request):
            logger.warning(
                f"Rate limit exceeded for teacher requests",
                extra={
                    "ip_address": self._get_client_ip(request),
                    "user_id": (
                        request.user.id
                        if hasattr(request, "user") and request.user.is_authenticated
                        else None
                    ),
                    "path": request.path,
                },
            )
            return JsonResponse({"error": "Rate limit exceeded"}, status=429)

        # Check for suspicious activity
        if self._detect_suspicious_activity(request):
            logger.warning(
                f"Suspicious activity detected in teacher module",
                extra={
                    "ip_address": self._get_client_ip(request),
                    "user_id": (
                        request.user.id
                        if hasattr(request, "user") and request.user.is_authenticated
                        else None
                    ),
                    "path": request.path,
                    "user_agent": request.META.get("HTTP_USER_AGENT", ""),
                },
            )

        # Validate teacher access permissions
        if hasattr(request, "user") and request.user.is_authenticated:
            return self._validate_teacher_access(request)

        return None

    def _is_teacher_request(self, request):
        """Check if request is teacher-related."""
        return request.path.startswith("/teachers/") or request.path.startswith(
            "/api/teachers/"
        )

    def _is_rate_limited(self, request):
        """Check if request should be rate limited."""
        ip_address = self._get_client_ip(request)
        cache_key = f"{self.rate_limit_cache_prefix}:{ip_address}"

        current_minute = datetime.now().strftime("%Y%m%d%H%M")
        full_cache_key = f"{cache_key}:{current_minute}"

        request_count = cache.get(full_cache_key, 0)

        if request_count >= self.max_requests_per_minute:
            return True

        cache.set(full_cache_key, request_count + 1, 60)  # 60 seconds
        return False

    def _detect_suspicious_activity(self, request):
        """Detect potentially suspicious activity."""
        # Check for rapid successive requests
        ip_address = self._get_client_ip(request)
        cache_key = f"teacher_activity:{ip_address}"

        recent_requests = cache.get(cache_key, [])
        now = time.time()

        # Remove requests older than 10 seconds
        recent_requests = [
            req_time for req_time in recent_requests if now - req_time < 10
        ]

        # Add current request
        recent_requests.append(now)
        cache.set(cache_key, recent_requests, 60)

        # Flag as suspicious if more than 20 requests in 10 seconds
        if len(recent_requests) > 20:
            return True

        # Check for unusual user agent patterns
        user_agent = request.META.get("HTTP_USER_AGENT", "").lower()
        suspicious_patterns = ["bot", "crawler", "spider", "scraper"]

        if any(pattern in user_agent for pattern in suspicious_patterns):
            return True

        return False

    def _validate_teacher_access(self, request):
        """Validate teacher-specific access permissions."""
        # Check if teacher user is trying to access only their own data
        if hasattr(request.user, "teacher_profile"):
            teacher = request.user.teacher_profile

            # Check teacher status for certain operations
            if request.method in ["POST", "PUT", "PATCH", "DELETE"]:
                if teacher.status != "Active":
                    logger.warning(
                        f"Inactive teacher {teacher.id} attempting write operation",
                        extra={
                            "teacher_id": teacher.id,
                            "teacher_status": teacher.status,
                            "operation": request.method,
                            "path": request.path,
                        },
                    )
                    return JsonResponse(
                        {"error": "Account is not active for this operation"},
                        status=403,
                    )

        return None

    def _get_client_ip(self, request):
        """Get client IP address."""
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            ip = x_forwarded_for.split(",")[0].strip()
        else:
            ip = request.META.get("REMOTE_ADDR")
        return ip


class TeacherSessionMiddleware(MiddlewareMixin):
    """Middleware for managing teacher-specific session data."""

    def __init__(self, get_response):
        self.get_response = get_response
        super().__init__(get_response)

    def process_request(self, request):
        """Process teacher session data."""
        if (
            hasattr(request, "user")
            and request.user.is_authenticated
            and hasattr(request.user, "teacher_profile")
        ):

            # Store teacher context in session
            teacher = request.user.teacher_profile

            # Update last activity
            teacher.user.last_login = timezone.now()
            teacher.user.save(update_fields=["last_login"])

            # Store teacher info in session for quick access
            request.session["teacher_context"] = {
                "teacher_id": teacher.id,
                "employee_id": teacher.employee_id,
                "department_id": teacher.department.id if teacher.department else None,
                "department_name": (
                    teacher.department.name if teacher.department else None
                ),
                "is_department_head": (
                    (teacher.department and teacher.department.head == teacher)
                    if teacher.department
                    else False
                ),
                "status": teacher.status,
                "last_updated": timezone.now().isoformat(),
            }

            # Check for pending evaluations or important notifications
            self._check_teacher_alerts(request, teacher)

    def _check_teacher_alerts(self, request, teacher):
        """Check for important alerts for the teacher."""
        alerts = []

        # Check for overdue evaluations that require followup
        if teacher.department and teacher.department.head == teacher:
            overdue_evaluations = TeacherEvaluation.objects.filter(
                teacher__department=teacher.department,
                followup_date__lt=timezone.now().date(),
                status__in=["submitted", "reviewed"],
            ).count()

            if overdue_evaluations > 0:
                alerts.append(
                    {
                        "type": "warning",
                        "message": f"{overdue_evaluations} evaluations require followup",
                    }
                )

        # Check if teacher's own evaluation is due
        last_evaluation = teacher.get_latest_evaluation()
        if (
            not last_evaluation
            or (timezone.now().date() - last_evaluation.evaluation_date).days > 180
        ):  # 6 months
            alerts.append(
                {"type": "info", "message": "Your performance evaluation is due"}
            )

        # Store alerts in session
        if alerts:
            request.session["teacher_alerts"] = alerts


class TeacherDataConsistencyMiddleware(MiddlewareMixin):
    """Middleware to ensure data consistency in teacher operations."""

    def __init__(self, get_response):
        self.get_response = get_response
        super().__init__(get_response)

    def process_request(self, request):
        """Check data consistency before processing teacher requests."""
        if (
            self._is_teacher_modification_request(request)
            and hasattr(request, "user")
            and request.user.is_authenticated
        ):

            return self._validate_data_consistency(request)

        return None

    def _is_teacher_modification_request(self, request):
        """Check if this is a teacher data modification request."""
        return request.method in ["POST", "PUT", "PATCH", "DELETE"] and (
            request.path.startswith("/teachers/")
            or request.path.startswith("/api/teachers/")
        )

    def _validate_data_consistency(self, request):
        """Validate data consistency for teacher operations."""
        try:
            # Check for orphaned records
            self._check_orphaned_evaluations()
            self._check_orphaned_assignments()

            # Check for data integrity issues
            self._check_evaluation_integrity()
            self._check_assignment_integrity()

        except Exception as e:
            logger.error(f"Data consistency check failed: {str(e)}")
            # Don't block the request, just log the error

        return None

    def _check_orphaned_evaluations(self):
        """Check for evaluations without valid teachers."""
        orphaned_count = TeacherEvaluation.objects.filter(teacher__isnull=True).count()

        if orphaned_count > 0:
            logger.warning(f"Found {orphaned_count} orphaned evaluations")

    def _check_orphaned_assignments(self):
        """Check for assignments without valid teachers or classes."""
        from src.teachers.models import TeacherClassAssignment

        orphaned_teacher_count = TeacherClassAssignment.objects.filter(
            teacher__isnull=True
        ).count()

        orphaned_class_count = TeacherClassAssignment.objects.filter(
            class_instance__isnull=True
        ).count()

        if orphaned_teacher_count > 0:
            logger.warning(
                f"Found {orphaned_teacher_count} assignments without teachers"
            )

        if orphaned_class_count > 0:
            logger.warning(f"Found {orphaned_class_count} assignments without classes")

    def _check_evaluation_integrity(self):
        """Check evaluation data integrity."""
        # Check for evaluations with invalid scores
        invalid_scores = TeacherEvaluation.objects.filter(
            Q(score__lt=0) | Q(score__gt=100)
        ).count()

        if invalid_scores > 0:
            logger.warning(f"Found {invalid_scores} evaluations with invalid scores")

    def _check_assignment_integrity(self):
        """Check assignment data integrity."""
        from src.teachers.models import TeacherClassAssignment

        # Check for duplicate assignments
        duplicates = (
            TeacherClassAssignment.objects.values(
                "teacher", "class_instance", "subject", "academic_year"
            )
            .annotate(count=models.Count("id"))
            .filter(count__gt=1)
        )

        if duplicates.exists():
            logger.warning(f"Found {duplicates.count()} duplicate assignments")


# Utility functions for middleware


def get_teacher_performance_metrics(hours=24):
    """Get performance metrics for the last N hours."""
    metrics = []

    for hour in range(hours):
        cache_key = f"teacher_perf_metrics_{(datetime.now() - timedelta(hours=hour)).strftime('%Y%m%d%H')}"
        hour_metrics = cache.get(cache_key, [])
        metrics.extend(hour_metrics)

    if not metrics:
        return {}

    # Calculate aggregated metrics
    total_requests = len(metrics)
    avg_duration = sum(m["duration"] for m in metrics) / total_requests
    avg_queries = sum(m["query_count"] for m in metrics) / total_requests

    status_codes = {}
    for metric in metrics:
        status = metric["status_code"]
        status_codes[status] = status_codes.get(status, 0) + 1

    return {
        "total_requests": total_requests,
        "avg_duration": round(avg_duration, 3),
        "avg_queries": round(avg_queries, 1),
        "status_codes": status_codes,
        "time_period_hours": hours,
    }


def clear_teacher_performance_cache():
    """Clear all teacher performance metrics from cache."""
    from django.core.cache import cache

    # Clear metrics for the last 48 hours
    for hour in range(48):
        cache_key = f"teacher_perf_metrics_{(datetime.now() - timedelta(hours=hour)).strftime('%Y%m%d%H')}"
        cache.delete(cache_key)


def get_teacher_security_stats(hours=24):
    """Get security statistics for teacher module."""
    # This would typically query logs or security events
    # For now, return a placeholder structure
    return {
        "rate_limited_requests": 0,
        "suspicious_activities": 0,
        "blocked_requests": 0,
        "failed_authentications": 0,
        "time_period_hours": hours,
    }
