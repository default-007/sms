"""
Custom Permissions for Academics Module

This module defines custom permissions for the academics app,
including role-based access control and object-level permissions.
"""

from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied
from rest_framework import permissions

from .models import AcademicYear, Class, Department, Grade, Section, Term


class IsAcademicAdmin(permissions.BasePermission):
    """
    Permission for academic administrators
    """

    def has_permission(self, request, view):
        """Check if user is academic admin"""
        if not request.user or not request.user.is_authenticated:
            return False

        # Superusers have all permissions
        if request.user.is_superuser:
            return True

        # Check for academic admin role
        return request.user.groups.filter(name="Academic Admin").exists()


class IsAcademicStaff(permissions.BasePermission):
    """
    Permission for academic staff (teachers, coordinators, etc.)
    """

    def has_permission(self, request, view):
        """Check if user is academic staff"""
        if not request.user or not request.user.is_authenticated:
            return False

        # Superusers and academic admins have all permissions
        if (
            request.user.is_superuser
            or request.user.groups.filter(name="Academic Admin").exists()
        ):
            return True

        # Check for academic staff roles
        academic_roles = [
            "Teacher",
            "Academic Coordinator",
            "Department Head",
            "Principal",
        ]
        return request.user.groups.filter(name__in=academic_roles).exists()


class CanManageDepartment(permissions.BasePermission):
    """
    Permission to manage departments
    """

    def has_permission(self, request, view):
        """Check basic department management permission"""
        if not request.user or not request.user.is_authenticated:
            return False

        if request.user.is_superuser:
            return True

        # Read permissions for academic staff
        if request.method in permissions.SAFE_METHODS:
            return request.user.groups.filter(
                name__in=[
                    "Academic Admin",
                    "Teacher",
                    "Academic Coordinator",
                    "Principal",
                ]
            ).exists()

        # Write permissions for admins only
        return request.user.groups.filter(name="Academic Admin").exists()

    def has_object_permission(self, request, view, obj):
        """Check object-level department permissions"""
        if not request.user or not request.user.is_authenticated:
            return False

        if request.user.is_superuser:
            return True

        # Department heads can manage their own department
        if hasattr(request.user, "teacher_profile"):
            if obj.head and obj.head.user == request.user:
                return True

        # Read permissions for academic staff
        if request.method in permissions.SAFE_METHODS:
            return request.user.groups.filter(
                name__in=[
                    "Academic Admin",
                    "Teacher",
                    "Academic Coordinator",
                    "Principal",
                ]
            ).exists()

        # Write permissions for academic admins
        return request.user.groups.filter(name="Academic Admin").exists()


class CanManageAcademicStructure(permissions.BasePermission):
    """
    Permission to manage academic structure (sections, grades, classes)
    """

    def has_permission(self, request, view):
        """Check academic structure management permission"""
        if not request.user or not request.user.is_authenticated:
            return False

        if request.user.is_superuser:
            return True

        # Read permissions for academic staff
        if request.method in permissions.SAFE_METHODS:
            return request.user.groups.filter(
                name__in=[
                    "Academic Admin",
                    "Teacher",
                    "Academic Coordinator",
                    "Principal",
                ]
            ).exists()

        # Write permissions for admins and coordinators
        return request.user.groups.filter(
            name__in=["Academic Admin", "Academic Coordinator", "Principal"]
        ).exists()


class CanManageClass(permissions.BasePermission):
    """
    Permission to manage specific classes
    """

    def has_permission(self, request, view):
        """Check basic class management permission"""
        if not request.user or not request.user.is_authenticated:
            return False

        if request.user.is_superuser:
            return True

        # Academic staff can read class information
        if request.method in permissions.SAFE_METHODS:
            return request.user.groups.filter(
                name__in=[
                    "Academic Admin",
                    "Teacher",
                    "Academic Coordinator",
                    "Principal",
                ]
            ).exists()

        # Write permissions for admins and coordinators
        return request.user.groups.filter(
            name__in=["Academic Admin", "Academic Coordinator", "Principal"]
        ).exists()

    def has_object_permission(self, request, view, obj):
        """Check object-level class permissions"""
        if not request.user or not request.user.is_authenticated:
            return False

        if request.user.is_superuser:
            return True

        # Class teachers can manage their own classes (limited operations)
        if hasattr(request.user, "teacher_profile"):
            teacher = request.user.teacher_profile
            if obj.class_teacher == teacher:
                # Class teachers can update certain fields only
                if request.method in ["PUT", "PATCH"]:
                    # Define allowed fields for class teachers
                    allowed_fields = ["room_number"]  # Example
                    if hasattr(view, "get_serializer"):
                        serializer = view.get_serializer(
                            data=request.data, partial=True
                        )
                        if serializer.is_valid():
                            data_fields = set(serializer.validated_data.keys())
                            if data_fields.issubset(set(allowed_fields)):
                                return True

                # Read permissions for class teachers
                if request.method in permissions.SAFE_METHODS:
                    return True

        # Full permissions for academic admins and coordinators
        return request.user.groups.filter(
            name__in=["Academic Admin", "Academic Coordinator", "Principal"]
        ).exists()


class CanViewAcademicAnalytics(permissions.BasePermission):
    """
    Permission to view academic analytics
    """

    def has_permission(self, request, view):
        """Check analytics viewing permission"""
        if not request.user or not request.user.is_authenticated:
            return False

        if request.user.is_superuser:
            return True

        # Academic staff can view analytics
        return request.user.groups.filter(
            name__in=[
                "Academic Admin",
                "Teacher",
                "Academic Coordinator",
                "Principal",
                "Management",
            ]
        ).exists()


class CanManageAcademicYear(permissions.BasePermission):
    """
    Permission to manage academic years and terms
    """

    def has_permission(self, request, view):
        """Check academic year management permission"""
        if not request.user or not request.user.is_authenticated:
            return False

        if request.user.is_superuser:
            return True

        # Read permissions for academic staff
        if request.method in permissions.SAFE_METHODS:
            return request.user.groups.filter(
                name__in=[
                    "Academic Admin",
                    "Teacher",
                    "Academic Coordinator",
                    "Principal",
                ]
            ).exists()

        # Write permissions for admins and principal only
        return request.user.groups.filter(
            name__in=["Academic Admin", "Principal"]
        ).exists()


class IsClassTeacher(permissions.BasePermission):
    """
    Permission for class teachers to access their class data
    """

    def has_permission(self, request, view):
        """Check if user is a teacher"""
        if not request.user or not request.user.is_authenticated:
            return False

        return hasattr(request.user, "teacher_profile")

    def has_object_permission(self, request, view, obj):
        """Check if teacher is assigned to this class"""
        if not request.user or not request.user.is_authenticated:
            return False

        if not hasattr(request.user, "teacher_profile"):
            return False

        teacher = request.user.teacher_profile

        # Check if teacher is class teacher for this class
        if isinstance(obj, Class):
            return obj.class_teacher == teacher

        # Check if teacher teaches in this grade/section
        if isinstance(obj, Grade):
            return obj.classes.filter(class_teacher=teacher).exists()

        if isinstance(obj, Section):
            return Class.objects.filter(section=obj, class_teacher=teacher).exists()

        return False


class IsDepartmentHead(permissions.BasePermission):
    """
    Permission for department heads to access their department data
    """

    def has_permission(self, request, view):
        """Check if user is a department head"""
        if not request.user or not request.user.is_authenticated:
            return False

        if not hasattr(request.user, "teacher_profile"):
            return False

        teacher = request.user.teacher_profile
        return Department.objects.filter(head=teacher, is_active=True).exists()

    def has_object_permission(self, request, view, obj):
        """Check if user is head of this department"""
        if not request.user or not request.user.is_authenticated:
            return False

        if not hasattr(request.user, "teacher_profile"):
            return False

        teacher = request.user.teacher_profile

        if isinstance(obj, Department):
            return obj.head == teacher

        # Check for related objects
        if hasattr(obj, "department") and obj.department:
            return obj.department.head == teacher

        return False


# Permission checking functions


def check_academic_permission(user, action, obj=None):
    """
    Check if user has permission for academic action

    Args:
        user: User instance
        action: Action string (e.g., 'view_class', 'edit_grade')
        obj: Optional object instance

    Returns:
        Boolean indicating permission
    """
    if not user or not user.is_authenticated:
        return False

    if user.is_superuser:
        return True

    # Map actions to permission classes
    permission_map = {
        "view_analytics": CanViewAcademicAnalytics,
        "manage_department": CanManageDepartment,
        "manage_structure": CanManageAcademicStructure,
        "manage_class": CanManageClass,
        "manage_academic_year": CanManageAcademicYear,
    }

    permission_class = permission_map.get(action)
    if not permission_class:
        return False

    permission = permission_class()

    # Create mock request object
    class MockRequest:
        def __init__(self, user):
            self.user = user
            self.method = "GET"  # Default to safe method

    mock_request = MockRequest(user)

    # Check permission
    if obj:
        return permission.has_permission(
            mock_request, None
        ) and permission.has_object_permission(mock_request, None, obj)
    else:
        return permission.has_permission(mock_request, None)


def get_user_accessible_classes(user):
    """
    Get classes accessible to a user based on their role

    Args:
        user: User instance

    Returns:
        QuerySet of accessible Class objects
    """
    if not user or not user.is_authenticated:
        return Class.objects.none()

    if user.is_superuser:
        return Class.objects.all()

    # Academic admins and coordinators see all classes
    if user.groups.filter(
        name__in=["Academic Admin", "Academic Coordinator", "Principal"]
    ).exists():
        return Class.objects.all()

    # Teachers see their assigned classes
    if hasattr(user, "teacher_profile"):
        teacher = user.teacher_profile
        return Class.objects.filter(class_teacher=teacher)

    # Parents see their children's classes
    if hasattr(user, "parent_profile"):
        parent = user.parent_profile
        return Class.objects.filter(students__parents=parent).distinct()

    # Students see their own class
    if hasattr(user, "student_profile"):
        student = user.student_profile
        if student.current_class:
            return Class.objects.filter(id=student.current_class.id)

    return Class.objects.none()


def get_user_accessible_sections(user):
    """
    Get sections accessible to a user based on their role

    Args:
        user: User instance

    Returns:
        QuerySet of accessible Section objects
    """
    if not user or not user.is_authenticated:
        return Section.objects.none()

    if user.is_superuser:
        return Section.objects.all()

    # Academic admins see all sections
    if user.groups.filter(name__in=["Academic Admin", "Principal"]).exists():
        return Section.objects.all()

    # Department heads see sections in their department
    if hasattr(user, "teacher_profile"):
        teacher = user.teacher_profile

        # If department head
        headed_departments = Department.objects.filter(head=teacher)
        if headed_departments.exists():
            return Section.objects.filter(department__in=headed_departments)

        # If teacher, see sections where they teach
        taught_classes = Class.objects.filter(class_teacher=teacher)
        sections = Section.objects.filter(
            id__in=taught_classes.values_list("section", flat=True)
        ).distinct()
        return sections

    return Section.objects.none()


# Permission decorators for views


def require_academic_permission(action):
    """
    Decorator to require specific academic permission

    Args:
        action: Required action permission

    Returns:
        Decorator function
    """

    def decorator(view_func):
        def wrapped_view(request, *args, **kwargs):
            if not check_academic_permission(request.user, action):
                raise PermissionDenied(f"Permission denied: {action}")
            return view_func(request, *args, **kwargs)

        return wrapped_view

    return decorator


def require_object_permission(action, get_object_func):
    """
    Decorator to require object-level permission

    Args:
        action: Required action permission
        get_object_func: Function to get the object from request

    Returns:
        Decorator function
    """

    def decorator(view_func):
        def wrapped_view(request, *args, **kwargs):
            obj = get_object_func(request, *args, **kwargs)
            if not check_academic_permission(request.user, action, obj):
                raise PermissionDenied(f"Permission denied: {action} on {obj}")
            return view_func(request, *args, **kwargs)

        return wrapped_view

    return decorator


# Custom permission classes for specific use cases


class ReadOnlyForTeachers(permissions.BasePermission):
    """
    Read-only permission for teachers, full access for admins
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        if request.user.is_superuser:
            return True

        # Admins have full access
        if request.user.groups.filter(
            name__in=["Academic Admin", "Principal"]
        ).exists():
            return True

        # Teachers have read-only access
        if request.method in permissions.SAFE_METHODS:
            return request.user.groups.filter(name="Teacher").exists()

        return False


class SectionBasedPermission(permissions.BasePermission):
    """
    Permission based on section access
    """

    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        # Get user's accessible sections
        accessible_sections = get_user_accessible_sections(request.user)

        # Check if object's section is accessible
        if hasattr(obj, "section"):
            return obj.section in accessible_sections
        elif hasattr(obj, "grade") and hasattr(obj.grade, "section"):
            return obj.grade.section in accessible_sections

        return False
