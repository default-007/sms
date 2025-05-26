from django.utils.translation import gettext_lazy as _
from rest_framework import permissions


class IsAdmin(permissions.BasePermission):
    """
    Permission to only allow administrators to access the view.
    """

    message = _("Only administrators are authorized to perform this action.")

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.has_role("Admin")
        )


class CanManageUsers(permissions.BasePermission):
    """
    Permission to allow users with proper role permissions to manage users.
    """

    message = _("You do not have permission to manage users.")

    def has_permission(self, request, view):
        # Admin can do anything
        if request.user.has_role("Admin"):
            return True

        # Check if the user has appropriate permissions based on their roles
        for role_assignment in request.user.role_assignments.all():
            role_permissions = role_assignment.role.permissions

            # Check for users management permission
            if "users" in role_permissions:
                actions_map = {
                    "GET": "view",
                    "POST": "add",
                    "PUT": "change",
                    "PATCH": "change",
                    "DELETE": "delete",
                }

                required_action = actions_map.get(request.method)
                if required_action and required_action in role_permissions["users"]:
                    return True

        return False

    def has_object_permission(self, request, view, obj):
        # Admin can do anything
        if request.user.has_role("Admin"):
            return True

        # Users can view and edit their own profile
        if obj == request.user:
            return True

        # Check role-based permissions for the specific object
        for role_assignment in request.user.role_assignments.all():
            role_permissions = role_assignment.role.permissions

            # Check for users management permission
            if "users" in role_permissions:
                actions_map = {
                    "GET": "view",
                    "PUT": "change",
                    "PATCH": "change",
                    "DELETE": "delete",
                }

                required_action = actions_map.get(request.method)
                if required_action and required_action in role_permissions["users"]:
                    # Additional checks could be added here
                    # For example, teachers might only manage students in their classes
                    return True

        return False
