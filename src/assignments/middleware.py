from django.utils import timezone
from django.core.cache import cache
from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.deprecation import MiddlewareMixin
from datetime import datetime, timedelta
import logging

from .models import Assignment, AssignmentSubmission
from .services import DeadlineService
from .utils import CacheUtils

logger = logging.getLogger(__name__)


class AssignmentDeadlineNotificationMiddleware(MiddlewareMixin):
    """
    Middleware to show deadline notifications to users
    """

    def process_request(self, request):
        """
        Check for upcoming deadlines and add notifications
        """
        # Only process for authenticated users
        if not request.user.is_authenticated:
            return None

        # Skip for AJAX requests and API calls
        if request.headers.get(
            "X-Requested-With"
        ) == "XMLHttpRequest" or request.path.startswith("/api/"):
            return None

        try:
            # Check cache first to avoid database hits on every request
            cache_key = f"deadline_notifications_{request.user.id}"
            cached_notifications = cache.get(cache_key)

            if cached_notifications is None:
                notifications = self._get_deadline_notifications(request.user)
                # Cache for 15 minutes
                cache.set(cache_key, notifications, 900)
            else:
                notifications = cached_notifications

            # Add notifications to messages framework
            for notification in notifications:
                messages.add_message(
                    request,
                    notification["level"],
                    notification["message"],
                    extra_tags=notification.get("tags", ""),
                )

        except Exception as e:
            logger.error(f"Error in deadline notification middleware: {str(e)}")

        return None

    def _get_deadline_notifications(self, user):
        """
        Get deadline notifications for user
        """
        notifications = []

        try:
            if hasattr(user, "student"):
                notifications.extend(self._get_student_notifications(user.student))
            elif hasattr(user, "teacher"):
                notifications.extend(self._get_teacher_notifications(user.teacher))
        except Exception as e:
            logger.error(f"Error getting deadline notifications: {str(e)}")

        return notifications

    def _get_student_notifications(self, student):
        """
        Get notifications for students
        """
        notifications = []

        # Get upcoming deadlines (next 3 days)
        upcoming_assignments = Assignment.objects.filter(
            class_id=student.current_class_id,
            status="published",
            due_date__range=[timezone.now(), timezone.now() + timedelta(days=3)],
        ).exclude(submissions__student=student)

        for assignment in upcoming_assignments:
            days_until_due = assignment.days_until_due

            if days_until_due <= 1:
                # Urgent notification
                notifications.append(
                    {
                        "level": messages.WARNING,
                        "message": f'Assignment "{assignment.title}" is due soon! ({assignment.due_date.strftime("%b %d, %Y at %I:%M %p")})',
                        "tags": "assignment-deadline urgent",
                    }
                )
            elif days_until_due <= 3:
                # Regular reminder
                notifications.append(
                    {
                        "level": messages.INFO,
                        "message": f'Assignment "{assignment.title}" is due in {days_until_due} days',
                        "tags": "assignment-deadline",
                    }
                )

        # Check for new grades (last 7 days)
        new_grades = AssignmentSubmission.objects.filter(
            student=student,
            status="graded",
            graded_at__gte=timezone.now() - timedelta(days=7),
        ).count()

        if new_grades > 0:
            notifications.append(
                {
                    "level": messages.SUCCESS,
                    "message": f'You have {new_grades} new grade{"s" if new_grades > 1 else ""} available!',
                    "tags": "new-grades",
                }
            )

        return notifications

    def _get_teacher_notifications(self, teacher):
        """
        Get notifications for teachers
        """
        notifications = []

        # Get pending submissions for grading
        pending_count = AssignmentSubmission.objects.filter(
            assignment__teacher=teacher, status="submitted"
        ).count()

        if pending_count > 0:
            if pending_count > 10:
                level = messages.WARNING
                message = f"You have {pending_count} submissions pending grading!"
            else:
                level = messages.INFO
                message = f'You have {pending_count} submission{"s" if pending_count > 1 else ""} to grade'

            notifications.append(
                {"level": level, "message": message, "tags": "pending-grading"}
            )

        # Check for overdue assignments
        overdue_count = Assignment.objects.filter(
            teacher=teacher, status="published", due_date__lt=timezone.now()
        ).count()

        if overdue_count > 0:
            notifications.append(
                {
                    "level": messages.WARNING,
                    "message": f'You have {overdue_count} overdue assignment{"s" if overdue_count > 1 else ""}',
                    "tags": "overdue-assignments",
                }
            )

        return notifications


class AssignmentAccessControlMiddleware(MiddlewareMixin):
    """
    Middleware to control access to assignments based on user roles and permissions
    """

    def process_view(self, request, view_func, view_args, view_kwargs):
        """
        Check assignment access permissions
        """
        # Only check assignment-related views
        if (
            not request.resolver_match
            or "assignments" not in request.resolver_match.app_names
        ):
            return None

        # Skip for staff users
        if request.user.is_staff:
            return None

        # Check specific assignment access
        assignment_id = view_kwargs.get("pk") or view_kwargs.get("assignment_id")
        if assignment_id:
            try:
                assignment = Assignment.objects.get(id=assignment_id)

                if not self._has_assignment_access(request.user, assignment):
                    messages.error(
                        request, "You do not have permission to access this assignment."
                    )
                    return redirect("assignments:assignment_list")

            except Assignment.DoesNotExist:
                pass  # Let the view handle the 404

        # Check submission access
        submission_id = (
            view_kwargs.get("pk")
            if "submission" in request.resolver_match.url_name
            else None
        )
        if submission_id:
            try:
                submission = AssignmentSubmission.objects.get(id=submission_id)

                if not self._has_submission_access(request.user, submission):
                    messages.error(
                        request, "You do not have permission to access this submission."
                    )
                    return redirect("assignments:assignment_list")

            except AssignmentSubmission.DoesNotExist:
                pass  # Let the view handle the 404

        return None

    def _has_assignment_access(self, user, assignment):
        """
        Check if user has access to assignment
        """
        if hasattr(user, "teacher"):
            return assignment.teacher == user.teacher
        elif hasattr(user, "student"):
            return (
                assignment.class_id == user.student.current_class_id
                and assignment.status == "published"
            )
        elif hasattr(user, "parent"):
            children_classes = user.parent.children.values_list(
                "current_class_id", flat=True
            )
            return (
                assignment.class_id.id in children_classes
                and assignment.status == "published"
            )

        return False

    def _has_submission_access(self, user, submission):
        """
        Check if user has access to submission
        """
        if hasattr(user, "teacher"):
            return submission.assignment.teacher == user.teacher
        elif hasattr(user, "student"):
            return submission.student == user.student
        elif hasattr(user, "parent"):
            children = user.parent.children.all()
            return submission.student in children

        return False


class AssignmentActivityTrackingMiddleware(MiddlewareMixin):
    """
    Middleware to track user activity related to assignments
    """

    def process_response(self, request, response):
        """
        Track assignment-related activities
        """
        # Only track for authenticated users
        if not request.user.is_authenticated:
            return response

        # Only track successful requests
        if response.status_code != 200:
            return response

        try:
            # Track assignment views
            if (
                request.resolver_match
                and "assignments" in request.resolver_match.app_names
            ):
                self._track_activity(request)

        except Exception as e:
            logger.error(f"Error in activity tracking middleware: {str(e)}")

        return response

    def _track_activity(self, request):
        """
        Track specific assignment activity
        """
        view_name = request.resolver_match.url_name
        user = request.user

        # Define trackable activities
        activities = {
            "assignment_detail": "viewed_assignment",
            "submission_detail": "viewed_submission",
            "assignment_create": "created_assignment",
            "submission_create": "submitted_assignment",
            "submission_grade": "graded_submission",
        }

        activity_type = activities.get(view_name)
        if not activity_type:
            return

        # Get entity ID
        entity_id = request.resolver_match.kwargs.get(
            "pk"
        ) or request.resolver_match.kwargs.get("assignment_id")

        if entity_id:
            # Store activity in cache for later processing
            self._store_activity(user.id, activity_type, entity_id)

    def _store_activity(self, user_id, activity_type, entity_id):
        """
        Store activity data in cache for batch processing
        """
        cache_key = f"assignment_activities_{user_id}"
        activities = cache.get(cache_key, [])

        activities.append(
            {
                "type": activity_type,
                "entity_id": entity_id,
                "timestamp": timezone.now().isoformat(),
            }
        )

        # Keep only last 50 activities per user
        if len(activities) > 50:
            activities = activities[-50:]

        # Cache for 1 hour
        cache.set(cache_key, activities, 3600)


class AssignmentSubmissionValidationMiddleware(MiddlewareMixin):
    """
    Middleware to validate assignment submissions
    """

    def process_view(self, request, view_func, view_args, view_kwargs):
        """
        Validate submission attempts
        """
        # Only check submission creation views
        if (
            not request.resolver_match
            or request.resolver_match.url_name != "submission_create"
            or request.method != "POST"
        ):
            return None

        assignment_id = view_kwargs.get("assignment_id")
        if not assignment_id:
            return None

        try:
            assignment = Assignment.objects.get(id=assignment_id)

            # Check if assignment accepts submissions
            if assignment.status != "published":
                messages.error(
                    request, "This assignment is not available for submissions."
                )
                return redirect("assignments:assignment_detail", pk=assignment.id)

            # Check if student already submitted
            if hasattr(request.user, "student"):
                if assignment.is_submitted_by_student(request.user.student):
                    messages.info(
                        request, "You have already submitted this assignment."
                    )
                    return redirect("assignments:assignment_detail", pk=assignment.id)

                # Check if assignment is overdue and late submissions not allowed
                if assignment.is_overdue and not assignment.allow_late_submission:
                    messages.error(
                        request, "The deadline for this assignment has passed."
                    )
                    return redirect("assignments:assignment_detail", pk=assignment.id)

        except Assignment.DoesNotExist:
            pass  # Let the view handle the 404

        return None


class AssignmentCacheMiddleware(MiddlewareMixin):
    """
    Middleware to manage assignment-related caching
    """

    def process_request(self, request):
        """
        Set cache headers for assignment pages
        """
        # Set cache headers for static assignment content
        if (
            request.resolver_match
            and "assignments" in request.resolver_match.app_names
            and request.method == "GET"
        ):

            view_name = request.resolver_match.url_name

            # Different cache strategies for different views
            if view_name in ["assignment_list", "assignment_search"]:
                # Short cache for dynamic lists
                request.cache_timeout = 300  # 5 minutes
            elif view_name == "assignment_detail":
                # Medium cache for assignment details
                request.cache_timeout = 900  # 15 minutes
            elif view_name == "analytics_dashboard":
                # Longer cache for analytics
                request.cache_timeout = 1800  # 30 minutes

        return None

    def process_response(self, request, response):
        """
        Apply cache headers to response
        """
        if hasattr(request, "cache_timeout") and response.status_code == 200:
            cache_timeout = request.cache_timeout

            response["Cache-Control"] = f"public, max-age={cache_timeout}"
            response["Expires"] = (
                timezone.now() + timedelta(seconds=cache_timeout)
            ).strftime("%a, %d %b %Y %H:%M:%S GMT")

        return response


class AssignmentMaintenanceMiddleware(MiddlewareMixin):
    """
    Middleware for assignment system maintenance and cleanup
    """

    def process_request(self, request):
        """
        Perform periodic maintenance tasks
        """
        # Only run maintenance occasionally to avoid performance impact
        if not self._should_run_maintenance():
            return None

        try:
            self._run_maintenance_tasks()
        except Exception as e:
            logger.error(f"Error in maintenance middleware: {str(e)}")

        return None

    def _should_run_maintenance(self):
        """
        Check if maintenance should run (e.g., once per hour)
        """
        cache_key = "assignment_maintenance_last_run"
        last_run = cache.get(cache_key)

        if not last_run:
            cache.set(cache_key, timezone.now(), 3600)  # 1 hour
            return True

        return (timezone.now() - last_run).total_seconds() > 3600

    def _run_maintenance_tasks(self):
        """
        Run periodic maintenance tasks
        """
        # Clean up expired cache entries
        self._cleanup_expired_cache()

        # Update assignment status for overdue assignments
        self._update_overdue_assignments()

        # Clean up orphaned files (would need proper implementation)
        # self._cleanup_orphaned_files()

    def _cleanup_expired_cache(self):
        """
        Clean up expired cache entries
        """
        # This would need to be implemented based on your cache backend
        pass

    def _update_overdue_assignments(self):
        """
        Update status for overdue assignments
        """
        overdue_assignments = Assignment.objects.filter(
            status="published", due_date__lt=timezone.now()
        )

        # You could add logic here to automatically close overdue assignments
        # or send notifications to teachers

        for assignment in overdue_assignments[
            :10
        ]:  # Limit to prevent long-running tasks
            # Log overdue assignments
            logger.info(f"Assignment {assignment.id} is overdue: {assignment.title}")


class AssignmentSecurityMiddleware(MiddlewareMixin):
    """
    Middleware for assignment-related security
    """

    def process_request(self, request):
        """
        Check for security issues in assignment requests
        """
        # Check for suspicious file upload attempts
        if request.method == "POST" and request.FILES:
            for file_field, uploaded_file in request.FILES.items():
                if not self._is_safe_file(uploaded_file):
                    messages.error(request, "File upload blocked for security reasons.")
                    return redirect("assignments:assignment_list")

        return None

    def _is_safe_file(self, uploaded_file):
        """
        Check if uploaded file is safe
        """
        # Check file extension
        dangerous_extensions = [
            "exe",
            "bat",
            "cmd",
            "scr",
            "vbs",
            "js",
            "jar",
            "com",
            "pif",
            "application",
            "gadget",
            "msi",
            "msp",
            "hta",
            "cpl",
            "msc",
            "dll",
            "scf",
            "lnk",
            "inf",
            "reg",
        ]

        file_extension = uploaded_file.name.split(".")[-1].lower()
        if file_extension in dangerous_extensions:
            return False

        # Check file size (prevent huge uploads)
        max_file_size = 100 * 1024 * 1024  # 100MB
        if uploaded_file.size > max_file_size:
            return False

        # Additional MIME type checking could be added here

        return True
