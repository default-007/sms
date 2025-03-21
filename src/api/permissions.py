from rest_framework import permissions


class IsOwnerOrAdmin(permissions.BasePermission):
    """
    Permission to only allow owners of an object or admins to access it.
    """

    def has_object_permission(self, request, view, obj):
        # Admin can do anything
        if request.user.has_role("Admin"):
            return True

        # Users can only access their own objects
        return obj.user == request.user


class ReadOnly(permissions.BasePermission):
    """
    Permission to only allow read-only access.
    """

    def has_permission(self, request, view):
        return request.method in permissions.SAFE_METHODS
