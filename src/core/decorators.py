from functools import wraps
from django.http import HttpResponseForbidden
from django.shortcuts import redirect
from django.urls import reverse
from django.contrib import messages
from .utils import create_audit_log


def role_required(role_name):
    """Decorator to check if a user has a specific role."""

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect(reverse("accounts:login"))

            # Check if user has the required role
            has_role = request.user.roles.filter(name=role_name).exists()

            if not has_role and not request.user.is_superuser:
                messages.error(
                    request, f"You need {role_name} privileges to access this page."
                )
                return redirect(reverse("core:dashboard"))

            return view_func(request, *args, **kwargs)

        return _wrapped_view

    return decorator


def module_access_required(module_name):
    """Decorator to check if a user has access to a specific module."""

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect(reverse("accounts:login"))

            # Superuser has all permissions
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)

            # Check user roles for the module permission
            has_access = any(
                role.permissions.get(module_name, False)
                for role in request.user.roles.all()
            )

            if not has_access:
                messages.error(
                    request,
                    f"You don't have permission to access the {module_name} module.",
                )
                return redirect(reverse("core:dashboard"))

            return view_func(request, *args, **kwargs)

        return _wrapped_view

    return decorator


def audit_log(action, entity_type):
    """Decorator to create an audit log entry for view functions."""

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            response = view_func(request, *args, **kwargs)

            # Only create audit logs for authenticated users
            if request.user.is_authenticated:
                # Get entity_id from kwargs if available
                entity_id = kwargs.get("pk") or kwargs.get("id")

                create_audit_log(
                    user=request.user,
                    action=action,
                    entity_type=entity_type,
                    entity_id=entity_id,
                    request=request,
                )

            return response

        return _wrapped_view

    return decorator
