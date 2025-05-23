# src/api/permissions.py
"""Custom Permission Classes"""

from rest_framework import permissions
from rest_framework.permissions import BasePermission
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
import logging

logger = logging.getLogger(__name__)


class IsOwnerOrReadOnly(BasePermission):
    """Permission to only allow owners to edit objects"""

    def has_object_permission(self, request, view, obj):
        # Read permissions for any request
        if request.method in permissions.SAFE_METHODS:
            return True

        # Write permissions only to owner
        return obj.user == request.user


class IsTeacherOrReadOnly(BasePermission):
    """Permission for teacher-specific actions"""

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False

        # Read access for authenticated users
        if request.method in permissions.SAFE_METHODS:
            return True

        # Write access only for teachers and admins
        return request.user.is_teacher or request.user.is_admin


class IsParentOfStudent(BasePermission):
    """Permission for parents to access only their children's data"""

    def has_object_permission(self, request, view, obj):
        if not request.user.is_authenticated:
            return False

        if request.user.is_admin or request.user.is_teacher:
            return True

        # For parents, check if they're related to the student
        if hasattr(obj, "student"):
            return obj.student.parents.filter(user=request.user).exists()
        elif hasattr(obj, "students"):
            return obj.students.filter(parents__user=request.user).exists()

        return False


class IsAdminOrReadOnly(BasePermission):
    """Permission for admin-only write operations"""

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False

        # Read access for authenticated users
        if request.method in permissions.SAFE_METHODS:
            return True

        # Write access only for admins
        return request.user.is_admin


class HasModulePermission(BasePermission):
    """Check if user has permission for specific module"""

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False

        required_permission = getattr(view, "required_permission", None)
        if not required_permission:
            return True

        return self._user_has_permission(request.user, required_permission)

    def _user_has_permission(self, user, permission):
        """Check user permission with caching"""
        cache_key = f"user_perm_{user.id}_{permission}"
        has_perm = cache.get(cache_key)

        if has_perm is None:
            has_perm = user.has_perm(permission)
            cache.set(cache_key, has_perm, 300)  # Cache for 5 minutes

        return has_perm


class RoleBasedPermission(BasePermission):
    """Dynamic permission based on user roles"""

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False

        allowed_roles = getattr(view, "allowed_roles", [])
        if not allowed_roles:
            return True

        user_roles = self._get_user_roles(request.user)
        return any(role in allowed_roles for role in user_roles)

    def _get_user_roles(self, user):
        """Get user roles with caching"""
        cache_key = f"user_roles_{user.id}"
        roles = cache.get(cache_key)

        if roles is None:
            roles = list(user.roles.values_list("name", flat=True))
            cache.set(cache_key, roles, 300)  # Cache for 5 minutes

        return roles


class TermBasedPermission(BasePermission):
    """Permission that respects academic term restrictions"""

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False

        # Admin users bypass term restrictions
        if request.user.is_admin:
            return True

        # Check if current term allows the operation
        return self._is_operation_allowed_in_current_term(request, view)

    def _is_operation_allowed_in_current_term(self, request, view):
        """Check if operation is allowed in current academic term"""
        # Implementation based on your term rules
        # This is a placeholder - customize based on your academic calendar rules
        return True
