# core/permissions.py
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


class IsStudentOwnerOrAdmin(permissions.BasePermission):
    """Permission class for student data access"""

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

        # Allow student to access their own data
        if hasattr(request.user, "student") and obj == request.user.student:
            return True

        # Allow parent to access their child's data
        if hasattr(request.user, "parent"):
            try:
                from src.students.models import StudentParentRelation

                if StudentParentRelation.objects.filter(
                    parent=request.user.parent, student=obj
                ).exists():
                    return True
            except ImportError:
                pass

        # Allow teacher to access their students' data
        if hasattr(request.user, "teacher"):
            try:
                from src.teachers.models import TeacherClassAssignment

                if TeacherClassAssignment.objects.filter(
                    teacher=request.user.teacher, class_instance=obj.current_class
                ).exists():
                    return True
            except ImportError:
                pass

        return False


class IsTeacherOwnerOrAdmin(permissions.BasePermission):
    """Permission class for teacher data access"""

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

        # Allow teacher to access their own data
        if hasattr(request.user, "teacher") and obj == request.user.teacher:
            return True

        return False


class IsClassMemberOrAdmin(permissions.BasePermission):
    """Permission class for class-related data access"""

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

        # Allow class teacher
        if hasattr(request.user, "teacher"):
            try:
                from src.teachers.models import TeacherClassAssignment

                if TeacherClassAssignment.objects.filter(
                    teacher=request.user.teacher,
                    class_instance=obj,
                    is_class_teacher=True,
                ).exists():
                    return True
            except ImportError:
                pass

        # Allow students in the class
        if (
            hasattr(request.user, "student")
            and request.user.student.current_class == obj
        ):
            return True

        # Allow parents of students in the class
        if hasattr(request.user, "parent"):
            try:
                from src.students.models import StudentParentRelation

                if StudentParentRelation.objects.filter(
                    parent=request.user.parent, student__current_class=obj
                ).exists():
                    return True
            except ImportError:
                pass

        return False


class IsFinanceStaffOrAdmin(permissions.BasePermission):
    """Permission class for finance-related operations"""

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

        # Allow finance staff (check for specific group or permission)
        if request.user.groups.filter(name="Finance Staff").exists():
            return True

        # Check for specific permission
        if request.user.has_perm("finance.view_financialdata"):
            return True

        return False


class IsLibrarianOrAdmin(permissions.BasePermission):
    """Permission class for library operations"""

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

        # Allow librarians
        if request.user.groups.filter(name="Librarians").exists():
            return True

        # For read operations, allow teachers and students
        if request.method in permissions.SAFE_METHODS:
            if hasattr(request.user, "teacher") or hasattr(request.user, "student"):
                return True

        return False


class CanViewAnalytics(permissions.BasePermission):
    """Permission class for viewing analytics"""

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

        # Allow teachers to view class analytics
        if hasattr(request.user, "teacher"):
            return True

        # Allow parents to view their children's analytics
        if hasattr(request.user, "parent"):
            return True

        return False


class CanManageUsers(permissions.BasePermission):
    """Permission class for user management operations"""

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False

        # Allow superusers
        if request.user.is_superuser:
            return True

        # Allow system administrators
        if request.user.groups.filter(name="System Administrators").exists():
            return True

        # Allow school administrators for read operations
        if (
            request.method in permissions.SAFE_METHODS
            and request.user.groups.filter(name="School Administrators").exists()
        ):
            return True

        return False


class CanAccessSystemLogs(permissions.BasePermission):
    """Permission class for accessing system logs and audit trails"""

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False

        # Allow superusers and system admins
        return (
            request.user.is_superuser
            or request.user.groups.filter(name="System Administrators").exists()
        )


class CanConfigureSystem(permissions.BasePermission):
    """Permission class for system configuration"""

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False

        # Only allow superusers and system administrators
        return (
            request.user.is_superuser
            or request.user.groups.filter(name="System Administrators").exists()
        )


class IsOwnerOrTeacherOrAdmin(permissions.BasePermission):
    """Permission class that allows owners, teachers, or admins"""

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

        # Allow owner
        if hasattr(obj, "user") and obj.user == request.user:
            return True

        # Allow teacher if object is related to their class/subject
        if hasattr(request.user, "teacher"):
            # Check if teacher teaches the class/subject related to this object
            try:
                from src.teachers.models import TeacherClassAssignment

                if hasattr(obj, "class_instance"):
                    if TeacherClassAssignment.objects.filter(
                        teacher=request.user.teacher, class_instance=obj.class_instance
                    ).exists():
                        return True

                if hasattr(obj, "subject"):
                    if TeacherClassAssignment.objects.filter(
                        teacher=request.user.teacher, subject=obj.subject
                    ).exists():
                        return True

            except ImportError:
                pass

        return False
