from rest_framework import permissions
from src.accounts.services.role_service import RoleService


class HasAPIAccess(permissions.BasePermission):
    """
    Permission class to check if user has API access.
    """

    message = "You do not have permission to access the API."

    def has_permission(self, request, view):
        # Allow authenticated users only
        if not request.user or not request.user.is_authenticated:
            return False

        # Check if user has API access permission
        return RoleService.check_permission(request.user, "api", "access")


class HasResourcePermission(permissions.BasePermission):
    """
    Permission class to check if user has permission to access a specific resource.
    The resource and action are determined from the view attributes or method.
    """

    message = "You do not have permission to perform this action."

    def has_permission(self, request, view):
        # Allow authenticated users only
        if not request.user or not request.user.is_authenticated:
            return False

        # Admin users have all permissions
        if request.user.is_superuser or request.user.has_role("Admin"):
            return True

        # Get resource and action from view
        resource = getattr(view, "resource_name", None)

        if not resource:
            # Try to get resource from view name
            if hasattr(view, "get_queryset"):
                model = view.get_queryset().model
                resource = model._meta.model_name

        if not resource:
            return False

        # Map HTTP method to action
        method_action_map = {
            "GET": "view",
            "POST": "add",
            "PUT": "change",
            "PATCH": "change",
            "DELETE": "delete",
        }

        action = method_action_map.get(request.method, None)
        if not action:
            return False

        # Check if user has permission
        return RoleService.check_permission(request.user, resource, action)

    def has_object_permission(self, request, view, obj):
        # Check if user has permission first
        if not self.has_permission(request, view):
            return False

        # Admin users have all permissions
        if request.user.is_superuser or request.user.has_role("Admin"):
            return True

        # Get resource and action from view
        resource = getattr(view, "resource_name", None)

        if not resource:
            # Try to get resource from view name
            if hasattr(view, "get_queryset"):
                model = view.get_queryset().model
                resource = model._meta.model_name

        if not resource:
            return False

        # Map HTTP method to action
        method_action_map = {
            "GET": "view",
            "POST": "add",
            "PUT": "change",
            "PATCH": "change",
            "DELETE": "delete",
        }

        action = method_action_map.get(request.method, None)
        if not action:
            return False

        # Check if user is the owner (if applicable)
        # For user objects
        if hasattr(obj, "user") and obj.user == request.user:
            return True

        # For objects created by user
        if hasattr(obj, "created_by") and obj.created_by == request.user:
            return True

        # For class teacher (if applicable)
        if resource == "class" and hasattr(request.user, "teacher_profile"):
            if obj.class_teacher == request.user.teacher_profile:
                return True

        # For parent-student relationship
        if resource == "student" and hasattr(request.user, "parent_profile"):
            parent = request.user.parent_profile
            student_ids = [
                rel.student.id for rel in parent.parent_student_relations.all()
            ]
            if obj.id in student_ids:
                return True

        # Default to checking permissions
        return RoleService.check_permission(request.user, resource, action)
