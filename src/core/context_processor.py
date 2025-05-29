# context_processors.py
from django.conf import settings
from .services import ConfigurationService


def system_settings(request):
    """Add system settings to template context"""
    return {
        "SCHOOL_NAME": ConfigurationService.get_setting(
            "system.school_name", "School Management System"
        ),
        "SCHOOL_LOGO": ConfigurationService.get_setting("system.school_logo", ""),
        "ACADEMIC_YEAR": ConfigurationService.get_setting("academic.current_year", ""),
        "CURRENT_TERM": ConfigurationService.get_setting("academic.current_term", ""),
        "MAINTENANCE_MODE": ConfigurationService.get_setting(
            "system.maintenance_mode", False
        ),
        "SYSTEM_VERSION": getattr(settings, "VERSION", "1.0.0"),
    }


def user_permissions(request):
    """Add user role information to template context"""
    context = {
        "is_system_admin": False,
        "is_school_admin": False,
        "is_teacher": False,
        "is_parent": False,
        "is_student": False,
        "user_role": "anonymous",
    }

    if request.user.is_authenticated:
        context["is_system_admin"] = (
            request.user.is_superuser
            or request.user.groups.filter(name="System Administrators").exists()
        )

        context["is_school_admin"] = (
            context["is_system_admin"]
            or request.user.groups.filter(name="School Administrators").exists()
        )

        context["is_teacher"] = (
            hasattr(request.user, "teacher") and request.user.teacher.status == "active"
        )

        context["is_parent"] = hasattr(request.user, "parent")
        context["is_student"] = hasattr(request.user, "student")

        # Determine primary role
        if context["is_system_admin"]:
            context["user_role"] = "system_admin"
        elif context["is_school_admin"]:
            context["user_role"] = "school_admin"
        elif context["is_teacher"]:
            context["user_role"] = "teacher"
        elif context["is_parent"]:
            context["user_role"] = "parent"
        elif context["is_student"]:
            context["user_role"] = "student"
        else:
            context["user_role"] = "user"

    return context


def navigation_context(request):
    """Add navigation context for templates"""
    return {
        "current_path": request.path,
        "current_app": (
            request.resolver_match.app_name if request.resolver_match else ""
        ),
        "current_view": (
            request.resolver_match.view_name if request.resolver_match else ""
        ),
    }
