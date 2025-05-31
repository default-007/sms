# mixins.py
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import redirect
from django.contrib import messages
from django.views.generic.base import ContextMixin
from django.utils.decorators import method_decorator
from functools import wraps
import logging

from .services import AuditService, SecurityService

logger = logging.getLogger(__name__)


class ModulePermissionMixin(UserPassesTestMixin):
    """
    Base mixin for module-level permissions
    Provides flexible permission checking for different user roles
    """

    # Define required permissions for the view
    required_permissions = []
    required_roles = []
    required_groups = []

    # Module-specific settings
    module_name = None
    allow_staff = False
    allow_superuser = True

    def test_func(self):
        """Test if user has required permissions"""
        user = self.request.user

        # Check if user is authenticated
        if not user.is_authenticated:
            return False

        # Always allow superusers if enabled
        if self.allow_superuser and user.is_superuser:
            return True

        # Allow staff if enabled
        if self.allow_staff and user.is_staff:
            return True

        # Check specific permissions
        if self.required_permissions:
            if not all(user.has_perm(perm) for perm in self.required_permissions):
                return False

        # Check group memberships
        if self.required_groups:
            user_groups = user.groups.values_list("name", flat=True)
            if not any(group in user_groups for group in self.required_groups):
                return False

        # Check user roles (based on related models)
        if self.required_roles:
            if not self._check_user_roles(user):
                return False

        return True

    def _check_user_roles(self, user):
        """Check if user has any of the required roles"""
        user_roles = []

        # Check model-based roles
        if hasattr(user, "teacher") and user.teacher.status == "active":
            user_roles.append("teacher")

        if hasattr(user, "parent"):
            user_roles.append("parent")

        if hasattr(user, "student") and user.student.status == "active":
            user_roles.append("student")

        # Check group-based roles
        user_groups = user.groups.values_list("name", flat=True)
        if "System Administrators" in user_groups:
            user_roles.append("system_admin")
        if "School Administrators" in user_groups:
            user_roles.append("school_admin")

        return any(role in user_roles for role in self.required_roles)

    def handle_no_permission(self):
        """Handle permission denied cases"""
        user = self.request.user

        # Log security event
        SecurityService.log_security_event(
            "permission_denied",
            user=user if user.is_authenticated else None,
            ip_address=self.request.META.get("REMOTE_ADDR"),
            details={
                "view": self.__class__.__name__,
                "module": self.module_name,
                "required_permissions": self.required_permissions,
                "required_roles": self.required_roles,
                "required_groups": self.required_groups,
                "path": self.request.path,
            },
        )

        if not user.is_authenticated:
            # Redirect to login for unauthenticated users
            return redirect("accounts:login")

        # For AJAX requests, return JSON response
        if self.request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse(
                {
                    "error": "Permission denied",
                    "message": "You do not have permission to access this resource.",
                },
                status=403,
            )

        # For regular requests, show error page or redirect
        messages.error(self.request, "You do not have permission to access this page.")
        return HttpResponseForbidden("Permission denied")


class SystemAdminMixin(ModulePermissionMixin):
    """Mixin for views that require system administrator access"""

    required_groups = ["System Administrators"]
    module_name = "system"


class SchoolAdminMixin(ModulePermissionMixin):
    """Mixin for views that require school administrator access or higher"""

    required_groups = ["System Administrators", "School Administrators"]
    module_name = "admin"


class TeacherMixin(ModulePermissionMixin):
    """Mixin for views that require teacher access or higher"""

    required_roles = ["teacher"]
    required_groups = ["System Administrators", "School Administrators"]
    module_name = "academic"

    def test_func(self):
        """Override to allow admins and teachers"""
        user = self.request.user

        if not user.is_authenticated:
            return False

        # Allow superusers
        if user.is_superuser:
            return True

        # Allow admin groups
        user_groups = user.groups.values_list("name", flat=True)
        if any(group in user_groups for group in self.required_groups):
            return True

        # Allow active teachers
        if hasattr(user, "teacher") and user.teacher.status == "active":
            return True

        return False


class ParentMixin(ModulePermissionMixin):
    """Mixin for views that require parent access or higher"""

    required_roles = ["parent"]
    required_groups = ["System Administrators", "School Administrators"]
    module_name = "parent"

    def test_func(self):
        """Override to allow admins and parents"""
        user = self.request.user

        if not user.is_authenticated:
            return False

        # Allow superusers
        if user.is_superuser:
            return True

        # Allow admin groups
        user_groups = user.groups.values_list("name", flat=True)
        if any(group in user_groups for group in self.required_groups):
            return True

        # Allow parents
        if hasattr(user, "parent"):
            return True

        return False


class StudentMixin(ModulePermissionMixin):
    """Mixin for views that require student access or higher"""

    required_roles = ["student"]
    required_groups = ["System Administrators", "School Administrators"]
    module_name = "student"

    def test_func(self):
        """Override to allow admins and students"""
        user = self.request.user

        if not user.is_authenticated:
            return False

        # Allow superusers
        if user.is_superuser:
            return True

        # Allow admin groups
        user_groups = user.groups.values_list("name", flat=True)
        if any(group in user_groups for group in self.required_groups):
            return True

        # Allow active students
        if hasattr(user, "student") and user.student.status == "active":
            return True

        return False


class TeacherOrAdminMixin(ModulePermissionMixin):
    """Mixin for views accessible by teachers and administrators"""

    module_name = "academic"

    def test_func(self):
        user = self.request.user

        if not user.is_authenticated:
            return False

        # Allow superusers
        if user.is_superuser:
            return True

        # Allow admin groups
        user_groups = user.groups.values_list("name", flat=True)
        if any(
            group in ["System Administrators", "School Administrators"]
            for group in user_groups
        ):
            return True

        # Allow active teachers
        if hasattr(user, "teacher") and user.teacher.status == "active":
            return True

        return False


class OwnershipMixin(ModulePermissionMixin):
    """
    Mixin for views that require object ownership or admin access
    Must be used with DetailView or similar views that have get_object()
    """

    ownership_field = "user"  # Field that determines ownership
    allow_admin_override = True

    def test_func(self):
        """Test ownership or admin access"""
        user = self.request.user

        if not user.is_authenticated:
            return False

        # Allow superusers
        if user.is_superuser:
            return True

        # Allow admins if override is enabled
        if self.allow_admin_override:
            user_groups = user.groups.values_list("name", flat=True)
            if any(
                group in ["System Administrators", "School Administrators"]
                for group in user_groups
            ):
                return True

        # Check ownership
        try:
            obj = self.get_object()
            owner = getattr(obj, self.ownership_field, None)

            if owner == user:
                return True

            # Check related ownership (e.g., parent accessing child's data)
            if hasattr(user, "parent") and hasattr(obj, "student"):
                from students.models import StudentParentRelation

                if StudentParentRelation.objects.filter(
                    parent=user.parent, student=obj.student
                ).exists():
                    return True

            # Check teacher-student relationship
            if hasattr(user, "teacher") and hasattr(obj, "student"):
                from teachers.models import TeacherClassAssignment

                if TeacherClassAssignment.objects.filter(
                    teacher=user.teacher, class_instance=obj.student.current_class
                ).exists():
                    return True

        except AttributeError:
            # If get_object() is not available, default to False
            pass

        return False


class AuditMixin(ContextMixin):
    """
    Mixin to automatically log view access for audit purposes
    Should be used with other mixins
    """

    audit_action = "view"
    audit_description = None

    def dispatch(self, request, *args, **kwargs):
        """Override dispatch to log audit trail"""
        response = super().dispatch(request, *args, **kwargs)

        # Log the view access
        if request.user.is_authenticated:
            description = (
                self.audit_description or f"Accessed {self.__class__.__name__}"
            )

            AuditService.log_action(
                user=request.user,
                action=self.audit_action,
                description=description,
                ip_address=request.META.get("REMOTE_ADDR"),
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
                module_name=getattr(self, "module_name", "unknown"),
                view_name=self.__class__.__name__,
            )

        return response


class RateLimitMixin:
    """
    Mixin to apply rate limiting to views
    """

    rate_limit_key = None
    rate_limit_max_attempts = 5
    rate_limit_window_minutes = 15

    def dispatch(self, request, *args, **kwargs):
        """Override dispatch to apply rate limiting"""
        # Generate rate limit key
        if self.rate_limit_key:
            key = self.rate_limit_key
        else:
            key = f"{self.__class__.__name__}:{request.user.id if request.user.is_authenticated else request.META.get('REMOTE_ADDR', 'unknown')}"

        # Check rate limit
        if not SecurityService.check_rate_limit(
            key,
            f"view_{self.__class__.__name__}",
            self.rate_limit_max_attempts,
            self.rate_limit_window_minutes,
        ):
            # Rate limit exceeded
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return JsonResponse(
                    {
                        "error": "Rate limit exceeded",
                        "message": "Too many requests. Please try again later.",
                    },
                    status=429,
                )

            messages.error(request, "Rate limit exceeded. Please try again later.")
            return HttpResponseForbidden("Rate limit exceeded")

        return super().dispatch(request, *args, **kwargs)


class CacheMixin:
    """
    Mixin to add caching capabilities to views
    """

    cache_timeout = 300  # 5 minutes default
    cache_key_prefix = None

    def get_cache_key(self):
        """Generate cache key for this view"""
        prefix = self.cache_key_prefix or self.__class__.__name__
        user_part = (
            f"user_{self.request.user.id}"
            if self.request.user.is_authenticated
            else "anonymous"
        )
        query_part = str(sorted(self.request.GET.items()))

        return f"{prefix}:{user_part}:{hash(query_part)}"

    def get_cached_context_data(self, **kwargs):
        """Get context data with caching"""
        from django.core.cache import cache

        cache_key = self.get_cache_key()
        cached_data = cache.get(cache_key)

        if cached_data is not None:
            return cached_data

        # Get fresh data
        context = super().get_context_data(**kwargs)

        # Cache the data
        cache.set(cache_key, context, self.cache_timeout)

        return context


# Decorator versions of mixins for function-based views
def require_role(*roles):
    """Decorator to require specific user roles"""

    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def wrapped_view(request, *args, **kwargs):
            user = request.user
            user_roles = []

            # Check model-based roles
            if hasattr(user, "teacher") and user.teacher.status == "active":
                user_roles.append("teacher")
            if hasattr(user, "parent"):
                user_roles.append("parent")
            if hasattr(user, "student") and user.student.status == "active":
                user_roles.append("student")

            # Check group-based roles
            user_groups = user.groups.values_list("name", flat=True)
            if "System Administrators" in user_groups:
                user_roles.append("system_admin")
            if "School Administrators" in user_groups:
                user_roles.append("school_admin")

            if user.is_superuser or any(role in user_roles for role in roles):
                return view_func(request, *args, **kwargs)

            # Log permission denied
            SecurityService.log_security_event(
                "permission_denied",
                user=user,
                ip_address=request.META.get("REMOTE_ADDR"),
                details={
                    "view": view_func.__name__,
                    "required_roles": roles,
                    "user_roles": user_roles,
                },
            )

            raise PermissionDenied

        return wrapped_view

    return decorator


def require_group(*groups):
    """Decorator to require specific user groups"""

    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def wrapped_view(request, *args, **kwargs):
            user = request.user

            if user.is_superuser:
                return view_func(request, *args, **kwargs)

            user_groups = user.groups.values_list("name", flat=True)
            if any(group in user_groups for group in groups):
                return view_func(request, *args, **kwargs)

            # Log permission denied
            SecurityService.log_security_event(
                "permission_denied",
                user=user,
                ip_address=request.META.get("REMOTE_ADDR"),
                details={
                    "view": view_func.__name__,
                    "required_groups": groups,
                    "user_groups": list(user_groups),
                },
            )

            raise PermissionDenied

        return wrapped_view

    return decorator


# Specific permission decorators
require_system_admin = require_group("System Administrators")
require_school_admin = require_group("System Administrators", "School Administrators")
require_teacher = require_role("teacher", "system_admin", "school_admin")
require_parent = require_role("parent", "system_admin", "school_admin")
require_student = require_role("student", "system_admin", "school_admin")


class PermissionHelperMixin:
    """
    Mixin to add permission helper methods to views
    """

    def get_user_role(self):
        """Get the primary role of the current user"""
        user = self.request.user

        if not user.is_authenticated:
            return "anonymous"

        if user.is_superuser:
            return "superuser"

        # Check groups first
        user_groups = user.groups.values_list("name", flat=True)
        if "System Administrators" in user_groups:
            return "system_admin"
        if "School Administrators" in user_groups:
            return "school_admin"

        # Check model-based roles
        if hasattr(user, "teacher") and user.teacher.status == "active":
            return "teacher"
        if hasattr(user, "parent"):
            return "parent"
        if hasattr(user, "student") and user.student.status == "active":
            return "student"

        return "user"

    def is_admin_user(self):
        """Check if user is an administrator"""
        user = self.request.user
        if not user.is_authenticated:
            return False

        if user.is_superuser:
            return True

        user_groups = user.groups.values_list("name", flat=True)
        return any(
            group in ["System Administrators", "School Administrators"]
            for group in user_groups
        )

    def can_edit_object(self, obj):
        """Check if user can edit the given object"""
        user = self.request.user

        if not user.is_authenticated:
            return False

        # Admins can edit everything
        if self.is_admin_user():
            return True

        # Check ownership
        if hasattr(obj, "user") and obj.user == user:
            return True

        # Teachers can edit their students' related objects
        if hasattr(user, "teacher") and hasattr(obj, "student"):
            from teachers.models import TeacherClassAssignment

            return TeacherClassAssignment.objects.filter(
                teacher=user.teacher, class_instance=obj.student.current_class
            ).exists()

        # Parents can edit their children's related objects
        if hasattr(user, "parent") and hasattr(obj, "student"):
            from students.models import StudentParentRelation

            return StudentParentRelation.objects.filter(
                parent=user.parent, student=obj.student
            ).exists()

        return False

    def get_context_data(self, **kwargs):
        """Add permission context to all views using this mixin"""
        context = super().get_context_data(**kwargs)

        context.update(
            {
                "user_role": self.get_user_role(),
                "is_admin_user": self.is_admin_user(),
                "is_system_admin": self.get_user_role() == "system_admin",
                "is_school_admin": self.get_user_role()
                in ["system_admin", "school_admin"],
                "is_teacher": self.get_user_role() == "teacher",
                "is_parent": self.get_user_role() == "parent",
                "is_student": self.get_user_role() == "student",
            }
        )

        return context
