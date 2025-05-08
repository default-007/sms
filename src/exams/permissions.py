from rest_framework import permissions
from django.utils.translation import gettext_lazy as _


class IsExamAdmin(permissions.BasePermission):
    """
    Permission to only allow exam administrators to access the view.
    """

    message = _("Only exam administrators can perform this action.")

    def has_permission(self, request, view):
        return request.user.is_authenticated and (
            request.user.is_staff or request.user.has_perm("exams.admin_exams")
        )


class CanManageExams(permissions.BasePermission):
    """
    Permission to allow users with proper role permissions to manage exams.
    """

    message = _("You do not have permission to manage exams.")

    def has_permission(self, request, view):
        # Admin can do anything
        if request.user.is_staff:
            return True

        # Check if the user has appropriate permissions based on their roles
        for role_assignment in request.user.role_assignments.all():
            role_permissions = role_assignment.role.permissions

            # Check for exams management permission
            if "exams" in role_permissions:
                actions_map = {
                    "GET": "view",
                    "POST": "add",
                    "PUT": "change",
                    "PATCH": "change",
                    "DELETE": "delete",
                }

                required_action = actions_map.get(request.method)
                if required_action and required_action in role_permissions["exams"]:
                    return True

        return False


class IsTeacherForClass(permissions.BasePermission):
    """
    Permission to only allow teachers to manage exams for their classes.
    """

    message = _("You can only manage exams for classes you teach.")

    def has_permission(self, request, view):
        # Admin can do anything
        if request.user.is_staff:
            return True

        # If not a teacher, deny permission
        if not hasattr(request.user, "teacher_profile"):
            return False

        # For list views, allow access (filtering happens in queryset)
        if request.method == "GET" and not view.kwargs.get("pk"):
            return True

        return True  # Further checks happen in has_object_permission

    def has_object_permission(self, request, view, obj):
        # Admin can do anything
        if request.user.is_staff:
            return True

        # If not a teacher, deny permission
        if not hasattr(request.user, "teacher_profile"):
            return False

        teacher = request.user.teacher_profile

        # Check if this is an exam or related object
        if hasattr(obj, "teacher_id"):
            # Direct teacher association (Quiz)
            return obj.teacher_id == teacher.id
        elif hasattr(obj, "exam_schedule"):
            # Result - check through exam schedule
            return obj.exam_schedule.supervisor_id == teacher.id
        elif hasattr(obj, "exam"):
            # Schedule - check for class teacher or subject teacher
            if obj.supervisor_id == teacher.id:
                return True

            # Check if teacher is assigned to this class+subject
            from src.teachers.models import TeacherClassAssignment

            return TeacherClassAssignment.objects.filter(
                teacher=teacher,
                class_instance=obj.class_obj,
                subject=obj.subject,
                academic_year=obj.exam.academic_year,
            ).exists()

        return False


class IsExamStudent(permissions.BasePermission):
    """
    Permission for student-specific exam actions.
    """

    message = _("Students can only view their own exams and results.")

    def has_permission(self, request, view):
        # Only allow GET requests for students
        if not request.user.is_authenticated or not hasattr(
            request.user, "student_profile"
        ):
            return False

        return request.method == "GET" or request.method == "POST"

    def has_object_permission(self, request, view, obj):
        # If not a student, deny permission
        if not request.user.is_authenticated or not hasattr(
            request.user, "student_profile"
        ):
            return False

        student = request.user.student_profile

        # Check if this is a student's own record
        if hasattr(obj, "student_id"):
            return obj.student_id == student.id
        elif hasattr(obj, "class_obj"):
            # For exams/quizzes, check if student is in the class
            return obj.class_obj == student.current_class

        return False
