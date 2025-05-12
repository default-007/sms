# src/teachers/services/teacher_service.py

from src.teachers.models import Teacher, TeacherClassAssignment, TeacherEvaluation
from datetime import date


class TeacherService:
    """Service class for teacher-related operations."""

    @staticmethod
    def get_teacher_by_id(teacher_id):
        """Get a teacher by ID."""
        try:
            return Teacher.objects.get(id=teacher_id)
        except Teacher.DoesNotExist:
            return None

    @staticmethod
    def get_teacher_by_employee_id(employee_id):
        """Get a teacher by employee ID."""
        try:
            return Teacher.objects.get(employee_id=employee_id)
        except Teacher.DoesNotExist:
            return None

    @staticmethod
    def get_active_teachers():
        """Get all active teachers."""
        return Teacher.objects.active()

    @staticmethod
    def get_teachers_by_department(department_id):
        """Get teachers by department."""
        return Teacher.objects.filter(department_id=department_id)

    @staticmethod
    def get_class_teacher(class_id):
        """Get the class teacher for a specific class."""
        from src.courses.models import Class

        try:
            class_obj = Class.objects.get(id=class_id)
            return class_obj.class_teacher
        except Class.DoesNotExist:
            return None

    @staticmethod
    def get_teacher_timetable(teacher, academic_year=None):
        """Get the timetable for a specific teacher."""
        from src.courses.services.timetable_service import TimetableService

        return TimetableService.get_teacher_timetable(
            teacher, academic_year=academic_year
        )

    @staticmethod
    def calculate_teacher_performance(teacher, year=None):
        """Calculate teacher performance based on evaluations."""
        if not year:
            year = date.today().year

        evaluations = TeacherEvaluation.objects.filter(
            teacher=teacher, evaluation_date__year=year
        )

        if not evaluations.exists():
            return None

        avg_score = evaluations.aggregate(models.Avg("score"))["score__avg"]
        return {
            "average_score": avg_score,
            "evaluation_count": evaluations.count(),
            "latest_evaluation": evaluations.order_by("-evaluation_date").first(),
        }
