# permissions.py
from rest_framework import permissions
from django.contrib.auth.models import Permission


class IsSystemAdmin(permissions.BasePermission):
    """Permission class for system administrators"""

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and (
                request.user.is_superuser
                or request.user.groups.filter(name="System Administrators").exists()
            )
        )


class IsSchoolAdmin(permissions.BasePermission):
    """Permission class for school administrators"""

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and (
                request.user.is_superuser
                or request.user.groups.filter(
                    name__in=["System Administrators", "School Administrators"]
                ).exists()
            )
        )


class IsTeacherOrAdmin(permissions.BasePermission):
    """Permission class for teachers and administrators"""

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False

        # Allow superusers and admins
        if (
            request.user.is_superuser
            or request.user.groups.filter(
                name__in=["System Administrators", "School Administrators"]
            ).exists()
        ):
            return True

        # Allow teachers
        if hasattr(request.user, "teacher") and request.user.teacher.status == "active":
            return True

        return False


class IsParentOrAdmin(permissions.BasePermission):
    """Permission class for parents and administrators"""

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False

        # Allow superusers and admins
        if (
            request.user.is_superuser
            or request.user.groups.filter(
                name__in=["System Administrators", "School Administrators"]
            ).exists()
        ):
            return True

        # Allow parents
        if hasattr(request.user, "parent"):
            return True

        return False


class IsOwnerOrAdmin(permissions.BasePermission):
    """Permission class for object owners and administrators"""

    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        # Allow superusers and admins
        if (
            request.user.is_superuser
            or request.user.groups.filter(
                name__in=["System Administrators", "School Administrators"]
            ).exists()
        ):
            return True

        # Check if user owns the object
        if hasattr(obj, "user") and obj.user == request.user:
            return True

        # Check if user is related to the object
        if (
            hasattr(obj, "student")
            and hasattr(request.user, "student")
            and obj.student == request.user.student
        ):
            return True

        return False


class IsReadOnlyOrAdmin(permissions.BasePermission):
    """Permission class that allows read-only access or admin write access"""

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False

        # Allow all authenticated users to read
        if request.method in permissions.SAFE_METHODS:
            return True

        # Only allow admins to write
        return (
            request.user.is_superuser
            or request.user.groups.filter(
                name__in=["System Administrators", "School Administrators"]
            ).exists()
        )
