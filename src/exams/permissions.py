"""
School Management System - Exam Permissions
File: src/exams/permissions.py
"""

from rest_framework import permissions
from django.core.exceptions import PermissionDenied


class CanManageExams(permissions.BasePermission):
    """Permission for managing exams (Admin, Principal, Academic Coordinator)"""

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False

        # Allow admin users
        if request.user.role == "ADMIN":
            return True

        # Allow specific staff roles
        if request.user.role in ["PRINCIPAL", "ACADEMIC_COORDINATOR"]:
            return True

        # Teachers can view and enter results
        if request.user.role == "TEACHER" and view.action in [
            "list",
            "retrieve",
            "bulk_results",
            "results",
        ]:
            return True

        return False


class CanEnterResults(permissions.BasePermission):
    """Permission for entering exam results"""

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False

        return request.user.role in ["ADMIN", "TEACHER", "PRINCIPAL"]

    def has_object_permission(self, request, view, obj):
        # Teachers can only enter results for their supervised exams
        if request.user.role == "TEACHER":
            if hasattr(obj, "supervisor"):
                return obj.supervisor.user == request.user
            elif hasattr(obj, "exam_schedule"):
                return obj.exam_schedule.supervisor.user == request.user

        return True


class CanViewReportCards(permissions.BasePermission):
    """Permission for viewing report cards"""

    def has_permission(self, request, view):
        return request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        user = request.user

        # Admin can view all
        if user.role == "ADMIN":
            return True

        # Students can view their own report cards
        if user.role == "STUDENT":
            return obj.student.user == user

        # Parents can view their children's report cards
        if user.role == "PARENT":
            return obj.student in user.parent.students.all()

        # Teachers can view report cards of their students
        if user.role == "TEACHER":
            return obj.class_obj.class_teacher.user == user

        return False


class CanManageQuestions(permissions.BasePermission):
    """Permission for managing exam questions"""

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False

        return request.user.role in ["ADMIN", "TEACHER", "PRINCIPAL"]

    def has_object_permission(self, request, view, obj):
        # Teachers can only edit their own questions
        if request.user.role == "TEACHER":
            return obj.created_by == request.user

        return True
