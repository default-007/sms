from functools import wraps

from django.contrib import messages
from django.shortcuts import redirect
from django.utils.translation import gettext_lazy as _

from .services import RoleService


def admin_required(view_func):
    """
    Decorator for views that checks if the user is an admin.
    """

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.error(request, _("You need to login to access this page."))
            return redirect("login")

        if not request.user.has_role("Admin"):
            messages.error(
                request, _("You need administrative privileges to access this page.")
            )
            return redirect("dashboard")

        return view_func(request, *args, **kwargs)

    return wrapper


def permission_required(resource, action):
    """
    Decorator for views that checks if the user has a specific permission.

    Args:
        resource: Resource name (e.g., 'users', 'students')
        action: Action name (e.g., 'view', 'add', 'change', 'delete')
    """

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                messages.error(request, _("You need to login to access this page."))
                return redirect("login")

            if not RoleService.check_permission(request.user, resource, action):
                messages.error(
                    request, _("You do not have permission to access this page.")
                )
                return redirect("dashboard")

            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator
