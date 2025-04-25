from rest_framework import permissions


class IsSchoolAdmin(permissions.BasePermission):
    """
    Permission to allow only school administrators.
    """

    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and request.user.groups.filter(name="School Admin").exists()
        )


class IsTeacher(permissions.BasePermission):
    """
    Permission to allow only teachers.
    """

    def has_permission(self, request, view):
        return request.user.is_authenticated and hasattr(
            request.user, "teacher_profile"
        )

    def has_object_permission(self, request, view, obj):
        # Teachers can only view, not modify student records
        if request.method in permissions.SAFE_METHODS:
            return True
        return False


class IsParent(permissions.BasePermission):
    """
    Permission to allow only parents.
    """

    def has_permission(self, request, view):
        return request.user.is_authenticated and hasattr(request.user, "parent_profile")

    def has_object_permission(self, request, view, obj):
        # Parents can only view their children's records
        if hasattr(obj, "student"):
            # For StudentParentRelation objects
            return obj.parent.user == request.user
        elif hasattr(obj, "user"):
            # For Student objects
            parent = request.user.parent_profile
            student_ids = [
                relation.student.id
                for relation in parent.parent_student_relations.all()
            ]
            return obj.id in student_ids
        return False
