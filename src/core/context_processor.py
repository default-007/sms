from django.conf import settings
from .utils import get_system_setting


def global_settings(request):
    """Make settings available in all templates."""
    return {
        "SITE_NAME": get_system_setting("site_name", "School Management System"),
        "SCHOOL_ADDRESS": get_system_setting("school_address", ""),
        "SCHOOL_PHONE": get_system_setting("school_phone", ""),
        "SCHOOL_EMAIL": get_system_setting("school_email", ""),
        "CURRENT_ACADEMIC_YEAR": get_system_setting("current_academic_year", ""),
        "ENABLE_NOTIFICATIONS": get_system_setting("enable_notifications", True),
    }


def user_permissions(request):
    """Make user permissions available in all templates."""
    context = {
        "user_permissions": {},
        "user_modules": [],
    }

    if request.user.is_authenticated:
        # Superuser has all permissions
        if request.user.is_superuser:
            context["has_admin_access"] = True

            # Get all available modules
            context["user_modules"] = [
                "students",
                "teachers",
                "courses",
                "exams",
                "attendance",
                "finance",
                "library",
                "transport",
                "communications",
                "reports",
            ]
        else:
            # Get permissions from user roles
            context["has_admin_access"] = request.user.is_staff

            # Collect permissions from all roles
            permissions = {}
            modules = set()

            for role in request.user.roles.all():
                permissions.update(role.permissions)
                # Add module to available modules if user has any permission for it
                for key, value in role.permissions.items():
                    if value and key.split("_")[0] not in modules:
                        modules.add(key.split("_")[0])

            context["user_permissions"] = permissions
            context["user_modules"] = list(modules)

    return context


def notification_processor(request):
    """Make unread notifications available in all templates."""
    context = {
        "unread_notifications_count": 0,
        "recent_notifications": [],
    }

    if request.user.is_authenticated:
        # Import here to avoid circular imports
        from django.apps import apps

        try:
            Notification = apps.get_model("communications", "Notification")

            # Get unread notifications count
            context["unread_notifications_count"] = Notification.objects.filter(
                user=request.user, is_read=False
            ).count()

            # Get recent notifications
            context["recent_notifications"] = Notification.objects.filter(
                user=request.user
            ).order_by("-created_at")[:5]
        except:
            # Communications app might not be installed yet
            pass

    return context
