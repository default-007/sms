from rest_framework import permissions


class IsAdminUser(permissions.BasePermission):
    """Permission to only allow admin users."""

    def has_permission(self, request, view):
        return bool(
            request.user and request.user.is_authenticated and request.user.is_staff
        )


class IsOwnerOrAdmin(permissions.BasePermission):
    """Permission to only allow owners of an object or admins."""

    def has_object_permission(self, request, view, obj):
        # Admin permissions
        if request.user.is_staff:
            return True

        # Check if obj has a user field directly
        if hasattr(obj, "user"):
            return obj.user == request.user

        # Check if obj has an owner field
        if hasattr(obj, "owner"):
            return obj.owner == request.user

        # Check if obj has a created_by field
        if hasattr(obj, "created_by"):
            return obj.created_by == request.user

        return False


class HasModulePermission(permissions.BasePermission):
    """Permission to check if user has access to a specific module."""

    def has_permission(self, request, view):
        module_name = getattr(view, "module_permission", None)

        if not module_name:
            return False

        if request.user.is_staff:
            return True

        # Check if the user's role has permission to this module
        user_roles = request.user.roles.all()

        for role in user_roles:
            if role.permissions.get(module_name, False):
                return True

        return False
