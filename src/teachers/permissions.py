# src/teachers/permissions.py
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied
from rest_framework import permissions

from src.teachers.models import Teacher, TeacherClassAssignment, TeacherEvaluation


class TeacherModulePermissions(permissions.BasePermission):
    """Base permission class for teacher module operations."""

    def has_permission(self, request, view):
        """Check if user has permission to access teacher module."""
        if not request.user or not request.user.is_authenticated:
            return False

        # Superusers have full access
        if request.user.is_superuser:
            return True

        # Check if user has specific teacher module permissions
        user_groups = request.user.groups.values_list("name", flat=True)

        # Define which groups can access teacher module
        allowed_groups = [
            "Admin",
            "Principal",
            "Teacher",
            "HR Manager",
            "Academic Coordinator",
        ]

        # Check if user belongs to any allowed group
        if any(group in user_groups for group in allowed_groups):
            return True

        # Check specific permissions
        teacher_permissions = [
            "teachers.view_teacher",
            "teachers.add_teacher",
            "teachers.change_teacher",
            "teachers.delete_teacher",
        ]

        return any(request.user.has_perm(perm) for perm in teacher_permissions)

    def has_object_permission(self, request, view, obj):
        """Check object-level permissions."""
        if not request.user or not request.user.is_authenticated:
            return False

        # Superusers have full access
        if request.user.is_superuser:
            return True

        # If user is the teacher themselves (for profile access)
        if isinstance(obj, Teacher) and hasattr(request.user, "teacher_profile"):
            if request.user.teacher_profile == obj:
                # Teachers can view/update their own profile with restrictions
                if request.method in permissions.SAFE_METHODS:
                    return True
                # Teachers can only update specific fields
                return view.action in [
                    "partial_update"
                ] and self._can_teacher_update_profile(request)

        # Admin and Principal have full access
        user_groups = request.user.groups.values_list("name", flat=True)
        if "Admin" in user_groups or "Principal" in user_groups:
            return True

        # Department heads can manage teachers in their department
        if "Department Head" in user_groups:
            if isinstance(obj, Teacher):
                return self._is_department_head_of_teacher(request.user, obj)
            elif isinstance(obj, TeacherEvaluation):
                return self._is_department_head_of_teacher(request.user, obj.teacher)
            elif isinstance(obj, TeacherClassAssignment):
                return self._is_department_head_of_teacher(request.user, obj.teacher)

        # HR Managers can view and manage teacher employment data
        if "HR Manager" in user_groups:
            if request.method in permissions.SAFE_METHODS:
                return True
            # HR can update employment-related fields only
            return self._can_hr_update_teacher(request, obj)

        # Academic Coordinators can view teachers and manage assignments
        if "Academic Coordinator" in user_groups:
            if isinstance(obj, Teacher):
                return request.method in permissions.SAFE_METHODS
            elif isinstance(obj, TeacherClassAssignment):
                return True  # Can manage all assignments
            elif isinstance(obj, TeacherEvaluation):
                return request.method in permissions.SAFE_METHODS

        # Default: check specific permissions
        return self._check_specific_permissions(request, obj)

    def _can_teacher_update_profile(self, request):
        """Check if teacher can update their own profile."""
        allowed_fields = ["bio", "emergency_contact", "emergency_phone"]
        if hasattr(request, "data"):
            return all(field in allowed_fields for field in request.data.keys())
        return True

    def _is_department_head_of_teacher(self, user, teacher):
        """Check if user is department head of the teacher's department."""
        if hasattr(user, "teacher_profile"):
            user_teacher = user.teacher_profile
            if (
                teacher.department
                and teacher.department.head
                and teacher.department.head == user_teacher
            ):
                return True
        return False

    def _can_hr_update_teacher(self, request, obj):
        """Check if HR can update teacher data."""
        if not isinstance(obj, Teacher):
            return False

        hr_allowed_fields = [
            "salary",
            "contract_type",
            "status",
            "position",
            "joining_date",
            "employee_id",
        ]

        if hasattr(request, "data"):
            return all(field in hr_allowed_fields for field in request.data.keys())
        return True

    def _check_specific_permissions(self, request, obj):
        """Check specific Django permissions."""
        if isinstance(obj, Teacher):
            if request.method in permissions.SAFE_METHODS:
                return request.user.has_perm("teachers.view_teacher")
            elif request.method == "POST":
                return request.user.has_perm("teachers.add_teacher")
            elif request.method in ["PUT", "PATCH"]:
                return request.user.has_perm("teachers.change_teacher")
            elif request.method == "DELETE":
                return request.user.has_perm("teachers.delete_teacher")

        return False


class TeacherEvaluationPermissions(permissions.BasePermission):
    """Permissions for teacher evaluation operations."""

    def has_permission(self, request, view):
        """Check if user can access evaluations."""
        if not request.user or not request.user.is_authenticated:
            return False

        # Superusers have full access
        if request.user.is_superuser:
            return True

        user_groups = request.user.groups.values_list("name", flat=True)

        # Only specific roles can access evaluations
        evaluation_roles = [
            "Admin",
            "Principal",
            "Department Head",
            "Academic Coordinator",
        ]

        if any(role in user_groups for role in evaluation_roles):
            return True

        # Teachers can only view their own evaluations
        if "Teacher" in user_groups:
            return request.method in permissions.SAFE_METHODS

        # Check specific permissions
        return request.user.has_perm("teachers.view_teacherevaluation")

    def has_object_permission(self, request, view, obj):
        """Check object-level permissions for evaluations."""
        if not request.user or not request.user.is_authenticated:
            return False

        # Superusers have full access
        if request.user.is_superuser:
            return True

        user_groups = request.user.groups.values_list("name", flat=True)

        # Admin and Principal have full access
        if "Admin" in user_groups or "Principal" in user_groups:
            return True

        # Department heads can manage evaluations in their department
        if "Department Head" in user_groups:
            return self._is_department_head_of_teacher(request.user, obj.teacher)

        # Academic Coordinators can view and create evaluations
        if "Academic Coordinator" in user_groups:
            if request.method in permissions.SAFE_METHODS or request.method == "POST":
                return True

        # Teachers can only view their own evaluations
        if "Teacher" in user_groups and hasattr(request.user, "teacher_profile"):
            if obj.teacher == request.user.teacher_profile:
                return request.method in permissions.SAFE_METHODS

        # Evaluators can view evaluations they created
        if obj.evaluator == request.user:
            return True

        return False

    def _is_department_head_of_teacher(self, user, teacher):
        """Check if user is department head of the teacher's department."""
        if hasattr(user, "teacher_profile"):
            user_teacher = user.teacher_profile
            if (
                teacher.department
                and teacher.department.head
                and teacher.department.head == user_teacher
            ):
                return True
        return False


class TeacherAssignmentPermissions(permissions.BasePermission):
    """Permissions for teacher class assignments."""

    def has_permission(self, request, view):
        """Check if user can manage assignments."""
        if not request.user or not request.user.is_authenticated:
            return False

        # Superusers have full access
        if request.user.is_superuser:
            return True

        user_groups = request.user.groups.values_list("name", flat=True)

        # Roles that can manage assignments
        assignment_roles = [
            "Admin",
            "Principal",
            "Academic Coordinator",
            "Department Head",
        ]

        if any(role in user_groups for role in assignment_roles):
            return True

        # Teachers can view their own assignments
        if "Teacher" in user_groups:
            return request.method in permissions.SAFE_METHODS

        return request.user.has_perm("teachers.assign_classes")

    def has_object_permission(self, request, view, obj):
        """Check object-level permissions for assignments."""
        if not request.user or not request.user.is_authenticated:
            return False

        # Superusers have full access
        if request.user.is_superuser:
            return True

        user_groups = request.user.groups.values_list("name", flat=True)

        # Admin and Principal have full access
        if "Admin" in user_groups or "Principal" in user_groups:
            return True

        # Academic Coordinators can manage all assignments
        if "Academic Coordinator" in user_groups:
            return True

        # Department heads can manage assignments in their department
        if "Department Head" in user_groups:
            return self._is_department_head_of_teacher(request.user, obj.teacher)

        # Teachers can only view their own assignments
        if "Teacher" in user_groups and hasattr(request.user, "teacher_profile"):
            if obj.teacher == request.user.teacher_profile:
                return request.method in permissions.SAFE_METHODS

        return False

    def _is_department_head_of_teacher(self, user, teacher):
        """Check if user is department head of the teacher's department."""
        if hasattr(user, "teacher_profile"):
            user_teacher = user.teacher_profile
            if (
                teacher.department
                and teacher.department.head
                and teacher.department.head == user_teacher
            ):
                return True
        return False


class TeacherAnalyticsPermissions(permissions.BasePermission):
    """Permissions for teacher analytics and reports."""

    def has_permission(self, request, view):
        """Check if user can access analytics."""
        if not request.user or not request.user.is_authenticated:
            return False

        # Superusers have full access
        if request.user.is_superuser:
            return True

        user_groups = request.user.groups.values_list("name", flat=True)

        # Roles that can access analytics
        analytics_roles = [
            "Admin",
            "Principal",
            "Department Head",
            "Academic Coordinator",
            "HR Manager",
        ]

        if any(role in user_groups for role in analytics_roles):
            return True

        # Check specific permission
        return request.user.has_perm("teachers.view_teacher_analytics")


class TeacherProfilePermissions(permissions.BasePermission):
    """Permissions for teacher profile management."""

    def has_permission(self, request, view):
        """Check if user can access profiles."""
        if not request.user or not request.user.is_authenticated:
            return False

        # Teachers can access their own profile
        if hasattr(request.user, "teacher_profile"):
            return True

        # Other roles need general teacher permissions
        return TeacherModulePermissions().has_permission(request, view)

    def has_object_permission(self, request, view, obj):
        """Check object-level permissions for profiles."""
        if not request.user or not request.user.is_authenticated:
            return False

        # Teachers can only access their own profile
        if hasattr(request.user, "teacher_profile"):
            if obj == request.user.teacher_profile:
                # Teachers have limited update permissions
                if request.method in permissions.SAFE_METHODS:
                    return True
                elif request.method in ["PUT", "PATCH"]:
                    return self._can_teacher_update_own_profile(request)

        # Other roles use general teacher permissions
        return TeacherModulePermissions().has_object_permission(request, view, obj)

    def _can_teacher_update_own_profile(self, request):
        """Check if teacher can update their own profile."""
        allowed_fields = [
            "bio",
            "emergency_contact",
            "emergency_phone",
            "user.phone_number",  # Allow updating phone number
        ]

        if hasattr(request, "data"):
            # Check if only allowed fields are being updated
            return all(
                field in allowed_fields or field.startswith("user.")
                for field in request.data.keys()
            )
        return True


class DepartmentHeadPermissions(permissions.BasePermission):
    """Special permissions for department heads."""

    def has_permission(self, request, view):
        """Check if user is a department head."""
        if not request.user or not request.user.is_authenticated:
            return False

        # Check if user is a department head
        if hasattr(request.user, "teacher_profile"):
            teacher = request.user.teacher_profile
            if teacher.department and teacher.department.head == teacher:
                return True

        # Also check for Department Head role
        user_groups = request.user.groups.values_list("name", flat=True)
        return "Department Head" in user_groups

    def has_object_permission(self, request, view, obj):
        """Check if department head can access specific objects."""
        if not self.has_permission(request, view):
            return False

        # Department heads can manage teachers in their department
        if isinstance(obj, Teacher):
            return self._is_in_same_department(request.user, obj)
        elif isinstance(obj, TeacherEvaluation):
            return self._is_in_same_department(request.user, obj.teacher)
        elif isinstance(obj, TeacherClassAssignment):
            return self._is_in_same_department(request.user, obj.teacher)

        return False

    def _is_in_same_department(self, user, teacher):
        """Check if user and teacher are in the same department."""
        if hasattr(user, "teacher_profile"):
            user_teacher = user.teacher_profile
            return (
                user_teacher.department
                and teacher.department
                and user_teacher.department == teacher.department
            )
        return False


class TeacherTimetablePermissions(permissions.BasePermission):
    """Permissions for teacher timetable access."""

    def has_permission(self, request, view):
        """Check if user can access timetables."""
        if not request.user or not request.user.is_authenticated:
            return False

        # Most roles can view timetables
        user_groups = request.user.groups.values_list("name", flat=True)
        allowed_roles = [
            "Admin",
            "Principal",
            "Teacher",
            "Academic Coordinator",
            "Department Head",
            "Student",
            "Parent",
        ]

        return any(role in user_groups for role in allowed_roles)

    def has_object_permission(self, request, view, obj):
        """Check object-level permissions for timetables."""
        if not request.user or not request.user.is_authenticated:
            return False

        # Superusers and admin roles have full access
        if request.user.is_superuser:
            return True

        user_groups = request.user.groups.values_list("name", flat=True)

        if any(
            role in user_groups
            for role in ["Admin", "Principal", "Academic Coordinator"]
        ):
            return True

        # Teachers can view their own timetable
        if "Teacher" in user_groups and hasattr(request.user, "teacher_profile"):
            if isinstance(obj, Teacher) and obj == request.user.teacher_profile:
                return True

        # Department heads can view timetables of their department
        if "Department Head" in user_groups:
            return self._is_in_same_department(request.user, obj)

        # Students and parents can view teacher timetables (read-only)
        if any(role in user_groups for role in ["Student", "Parent"]):
            return request.method in permissions.SAFE_METHODS

        return False

    def _is_in_same_department(self, user, teacher):
        """Check if user and teacher are in the same department."""
        if hasattr(user, "teacher_profile"):
            user_teacher = user.teacher_profile
            return (
                user_teacher.department
                and teacher.department
                and user_teacher.department == teacher.department
            )
        return False


# Utility functions for permission checking
def check_teacher_module_permission(user, action, obj=None):
    """Utility function to check teacher module permissions."""
    permission_class = TeacherModulePermissions()

    # Create a mock request object
    class MockRequest:
        def __init__(self, user, method):
            self.user = user
            self.method = method

    request = MockRequest(user, action)

    if obj:
        return permission_class.has_object_permission(request, None, obj)
    else:
        return permission_class.has_permission(request, None)


def check_evaluation_permission(user, action, evaluation=None):
    """Utility function to check evaluation permissions."""
    permission_class = TeacherEvaluationPermissions()

    class MockRequest:
        def __init__(self, user, method):
            self.user = user
            self.method = method

    request = MockRequest(user, action)

    if evaluation:
        return permission_class.has_object_permission(request, None, evaluation)
    else:
        return permission_class.has_permission(request, None)


def is_department_head(user, department=None):
    """Check if user is a department head."""
    if not hasattr(user, "teacher_profile"):
        return False

    teacher = user.teacher_profile

    if department:
        return teacher.department == department and department.head == teacher
    else:
        return teacher.department and teacher.department.head == teacher


def can_access_teacher_analytics(user):
    """Check if user can access teacher analytics."""
    permission_class = TeacherAnalyticsPermissions()

    class MockRequest:
        def __init__(self, user):
            self.user = user
            self.method = "GET"

    request = MockRequest(user)
    return permission_class.has_permission(request, None)
