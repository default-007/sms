from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied
from django.utils.translation import gettext_lazy as _
from rest_framework import permissions

from .models import Subject, SubjectAssignment, Syllabus, TopicProgress


class SubjectPermissions:
    """
    Custom permissions for subjects module.
    """

    # Permission codenames
    CAN_MANAGE_CURRICULUM = "can_manage_curriculum"
    CAN_VIEW_ALL_SYLLABI = "can_view_all_syllabi"
    CAN_EDIT_ANY_SYLLABUS = "can_edit_any_syllabus"
    CAN_ASSIGN_TEACHERS = "can_assign_teachers"
    CAN_VIEW_ANALYTICS = "can_view_analytics"
    CAN_BULK_IMPORT = "can_bulk_import"
    CAN_MANAGE_PREREQUISITES = "can_manage_prerequisites"

    @classmethod
    def create_custom_permissions(cls):
        """
        Create custom permissions for the subjects module.
        This should be called during app initialization.
        """
        permissions_to_create = [
            (cls.CAN_MANAGE_CURRICULUM, _("Can manage curriculum structure")),
            (cls.CAN_VIEW_ALL_SYLLABI, _("Can view all syllabi across departments")),
            (
                cls.CAN_EDIT_ANY_SYLLABUS,
                _("Can edit any syllabus regardless of assignment"),
            ),
            (cls.CAN_ASSIGN_TEACHERS, _("Can assign teachers to subjects")),
            (cls.CAN_VIEW_ANALYTICS, _("Can view curriculum analytics and reports")),
            (cls.CAN_BULK_IMPORT, _("Can bulk import subjects and syllabi")),
            (cls.CAN_MANAGE_PREREQUISITES, _("Can manage subject prerequisites")),
        ]

        # Get content types
        subject_ct = ContentType.objects.get_for_model(Subject)
        syllabus_ct = ContentType.objects.get_for_model(Syllabus)

        for codename, name in permissions_to_create:
            # Create permission for Subject model (as the main model)
            Permission.objects.get_or_create(
                codename=codename, content_type=subject_ct, defaults={"name": name}
            )


class IsTeacherOrReadOnly(permissions.BasePermission):
    """
    Permission that allows teachers to edit their own syllabi and assignments,
    but only read access for others.
    """

    def has_permission(self, request, view):
        """Check if user has basic permission to access the view."""
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        """Check object-level permissions."""
        # Read permissions for authenticated users
        if request.method in permissions.SAFE_METHODS:
            return True

        # Check if user is a teacher
        if not hasattr(request.user, "teacher_profile"):
            return False

        teacher = request.user.teacher_profile

        # Check permissions based on object type
        if isinstance(obj, Syllabus):
            return self._can_edit_syllabus(teacher, obj)
        elif isinstance(obj, SubjectAssignment):
            return self._can_edit_assignment(teacher, obj)
        elif isinstance(obj, TopicProgress):
            return self._can_edit_topic_progress(teacher, obj)
        elif isinstance(obj, Subject):
            # Only curriculum managers can edit subjects
            return request.user.has_perm("subjects.can_manage_curriculum")

        return False

    def _can_edit_syllabus(self, teacher, syllabus):
        """Check if teacher can edit this syllabus."""
        # Teacher can edit if they are assigned to teach this subject
        return SubjectAssignment.objects.filter(
            teacher=teacher,
            subject=syllabus.subject,
            class_assigned__grade=syllabus.grade,
            academic_year=syllabus.academic_year,
            term=syllabus.term,
            is_active=True,
        ).exists()

    def _can_edit_assignment(self, teacher, assignment):
        """Check if teacher can edit this assignment."""
        # Only the assigned teacher or curriculum managers can edit
        return assignment.teacher == teacher

    def _can_edit_topic_progress(self, teacher, topic_progress):
        """Check if teacher can edit this topic progress."""
        # Teacher can edit if they can edit the related syllabus
        return self._can_edit_syllabus(teacher, topic_progress.syllabus)


class IsCurriculumManager(permissions.BasePermission):
    """
    Permission for curriculum managers who can manage all curriculum-related data.
    """

    def has_permission(self, request, view):
        """Check if user is a curriculum manager."""
        return (
            request.user
            and request.user.is_authenticated
            and request.user.has_perm("subjects.can_manage_curriculum")
        )


class CanViewAllSyllabi(permissions.BasePermission):
    """
    Permission for users who can view all syllabi across departments.
    """

    def has_permission(self, request, view):
        """Check if user can view all syllabi."""
        if request.method in permissions.SAFE_METHODS:
            return (
                request.user
                and request.user.is_authenticated
                and request.user.has_perm("subjects.can_view_all_syllabi")
            )
        return False


class CanAssignTeachers(permissions.BasePermission):
    """
    Permission for users who can assign teachers to subjects.
    """

    def has_permission(self, request, view):
        """Check if user can assign teachers."""
        return (
            request.user
            and request.user.is_authenticated
            and request.user.has_perm("subjects.can_assign_teachers")
        )


class CanViewAnalytics(permissions.BasePermission):
    """
    Permission for users who can view curriculum analytics.
    """

    def has_permission(self, request, view):
        """Check if user can view analytics."""
        return (
            request.user
            and request.user.is_authenticated
            and request.user.has_perm("subjects.can_view_analytics")
        )


class CanBulkImport(permissions.BasePermission):
    """
    Permission for users who can perform bulk import operations.
    """

    def has_permission(self, request, view):
        """Check if user can perform bulk imports."""
        return (
            request.user
            and request.user.is_authenticated
            and request.user.has_perm("subjects.can_bulk_import")
        )


class DepartmentBasedPermission(permissions.BasePermission):
    """
    Permission that restricts access based on user's department.
    """

    def has_permission(self, request, view):
        """Check if user has basic permission."""
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        """Check object-level permissions based on department."""
        # Superusers and curriculum managers can access everything
        if request.user.is_superuser or request.user.has_perm(
            "subjects.can_manage_curriculum"
        ):
            return True

        # Get user's department
        user_department = self._get_user_department(request.user)
        if not user_department:
            return False

        # Get object's department
        obj_department = self._get_object_department(obj)
        if not obj_department:
            return True  # Allow access if no department restriction

        # Check if departments match
        return user_department == obj_department

    def _get_user_department(self, user):
        """Get user's department."""
        if hasattr(user, "teacher_profile") and user.teacher_profile.department:
            return user.teacher_profile.department
        elif hasattr(user, "staff_profile") and user.staff_profile.department:
            return user.staff_profile.department
        return None

    def _get_object_department(self, obj):
        """Get object's department."""
        if isinstance(obj, Subject):
            return obj.department
        elif isinstance(obj, Syllabus):
            return obj.subject.department
        elif isinstance(obj, SubjectAssignment):
            return obj.subject.department
        elif isinstance(obj, TopicProgress):
            return obj.syllabus.subject.department
        return None


class SyllabusTeacherPermission(permissions.BasePermission):
    """
    Permission that allows teachers to only access syllabi they are assigned to teach.
    """

    def has_permission(self, request, view):
        """Check if user has basic permission."""
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        """Check if teacher can access this syllabus."""
        # Superusers and curriculum managers can access everything
        if request.user.is_superuser or request.user.has_perm(
            "subjects.can_view_all_syllabi"
        ):
            return True

        # Check if user is a teacher
        if not hasattr(request.user, "teacher_profile"):
            return False

        teacher = request.user.teacher_profile

        # For syllabus objects
        if isinstance(obj, Syllabus):
            return SubjectAssignment.objects.filter(
                teacher=teacher,
                subject=obj.subject,
                class_assigned__grade=obj.grade,
                academic_year=obj.academic_year,
                term=obj.term,
                is_active=True,
            ).exists()

        return False


class ReadOnlyOrCurriculumManager(permissions.BasePermission):
    """
    Permission that allows read-only access to all users and write access to curriculum managers.
    """

    def has_permission(self, request, view):
        """Check permissions based on request method."""
        if request.method in permissions.SAFE_METHODS:
            return request.user and request.user.is_authenticated

        return (
            request.user
            and request.user.is_authenticated
            and request.user.has_perm("subjects.can_manage_curriculum")
        )


class TeacherSelfOrCurriculumManager(permissions.BasePermission):
    """
    Permission that allows teachers to access their own data and curriculum managers to access all.
    """

    def has_permission(self, request, view):
        """Check if user has basic permission."""
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        """Check object-level permissions."""
        # Curriculum managers can access everything
        if request.user.has_perm("subjects.can_manage_curriculum"):
            return True

        # Teachers can only access their own assignments
        if hasattr(request.user, "teacher_profile"):
            teacher = request.user.teacher_profile

            if isinstance(obj, SubjectAssignment):
                return obj.teacher == teacher
            elif isinstance(obj, Syllabus):
                return SubjectAssignment.objects.filter(
                    teacher=teacher,
                    subject=obj.subject,
                    class_assigned__grade=obj.grade,
                    academic_year=obj.academic_year,
                    term=obj.term,
                    is_active=True,
                ).exists()

        return False


def check_syllabus_edit_permission(user, syllabus):
    """
    Helper function to check if user can edit a specific syllabus.
    """
    # Superusers can edit everything
    if user.is_superuser:
        return True

    # Curriculum managers can edit everything
    if user.has_perm("subjects.can_edit_any_syllabus"):
        return True

    # Teachers can edit syllabi they are assigned to
    if hasattr(user, "teacher_profile"):
        teacher = user.teacher_profile
        return SubjectAssignment.objects.filter(
            teacher=teacher,
            subject=syllabus.subject,
            class_assigned__grade=syllabus.grade,
            academic_year=syllabus.academic_year,
            term=syllabus.term,
            is_active=True,
        ).exists()

    return False


def check_subject_view_permission(user, subject):
    """
    Helper function to check if user can view a specific subject.
    """
    # Everyone can view subjects (basic curriculum info)
    if user.is_authenticated:
        return True

    return False


def check_analytics_permission(user, analytics_type=None):
    """
    Helper function to check if user can view specific analytics.
    """
    if not user.is_authenticated:
        return False

    # Basic analytics permission
    if not user.has_perm("subjects.can_view_analytics"):
        return False

    # Check specific analytics types if needed
    if analytics_type == "teacher_performance":
        # Teachers can view their own performance, managers can view all
        return hasattr(user, "teacher_profile") or user.has_perm(
            "subjects.can_manage_curriculum"
        )

    return True


def check_bulk_operation_permission(user, operation_type):
    """
    Helper function to check if user can perform bulk operations.
    """
    if not user.is_authenticated:
        return False

    # Basic bulk import permission
    if not user.has_perm("subjects.can_bulk_import"):
        return False

    # Additional checks for specific operations
    if operation_type == "subject_import":
        return user.has_perm("subjects.can_manage_curriculum")
    elif operation_type == "syllabus_creation":
        return user.has_perm("subjects.can_manage_curriculum")

    return True


class CustomPermissionMixin:
    """
    Mixin to add custom permission checks to views.
    """

    def check_custom_permission(self, permission_name, obj=None):
        """
        Check custom permission and raise PermissionDenied if not allowed.
        """
        user = self.request.user

        if permission_name == "edit_syllabus" and obj:
            if not check_syllabus_edit_permission(user, obj):
                raise PermissionDenied(
                    _("You don't have permission to edit this syllabus.")
                )

        elif permission_name == "view_analytics":
            if not check_analytics_permission(user):
                raise PermissionDenied(
                    _("You don't have permission to view analytics.")
                )

        elif permission_name == "bulk_import":
            if not check_bulk_operation_permission(user, "subject_import"):
                raise PermissionDenied(
                    _("You don't have permission to perform bulk imports.")
                )

        # Add more custom permission checks as needed

    def has_department_access(self, department):
        """
        Check if user has access to specific department.
        """
        user = self.request.user

        if user.is_superuser or user.has_perm("subjects.can_manage_curriculum"):
            return True

        user_department = None
        if hasattr(user, "teacher_profile"):
            user_department = user.teacher_profile.department
        elif hasattr(user, "staff_profile"):
            user_department = user.staff_profile.department

        return user_department == department


# Permission classes for API views
class SubjectPermission(permissions.BasePermission):
    """
    Custom permission for Subject API views.
    """

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return request.user and request.user.is_authenticated

        return (
            request.user
            and request.user.is_authenticated
            and (
                request.user.has_perm("subjects.add_subject")
                or request.user.has_perm("subjects.can_manage_curriculum")
            )
        )

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True

        return request.user.has_perm(
            "subjects.change_subject"
        ) or request.user.has_perm("subjects.can_manage_curriculum")


class SyllabusPermission(permissions.BasePermission):
    """
    Custom permission for Syllabus API views.
    """

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return request.user and request.user.is_authenticated

        return (
            request.user
            and request.user.is_authenticated
            and (
                request.user.has_perm("subjects.add_syllabus")
                or hasattr(request.user, "teacher_profile")
            )
        )

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            # Check if user can view this syllabus
            if request.user.has_perm("subjects.can_view_all_syllabi"):
                return True

            # Teachers can view syllabi they are assigned to
            if hasattr(request.user, "teacher_profile"):
                teacher = request.user.teacher_profile
                return SubjectAssignment.objects.filter(
                    teacher=teacher,
                    subject=obj.subject,
                    class_assigned__grade=obj.grade,
                    academic_year=obj.academic_year,
                    term=obj.term,
                    is_active=True,
                ).exists()

            return False

        # Write permissions
        return check_syllabus_edit_permission(request.user, obj)
