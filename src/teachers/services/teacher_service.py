from django.db.models import Avg, Count, Sum, Max, F, Q, Case, When, Value, IntegerField
from django.utils import timezone
from datetime import datetime, timedelta
from django.db.models.functions import TruncMonth, ExtractYear, ExtractMonth

from src.teachers.models import Teacher, TeacherClassAssignment, TeacherEvaluation
from src.courses.models import Department, Class, Subject, AcademicYear


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
        return Teacher.objects.active().select_related("user", "department")

    @staticmethod
    def get_teachers_by_department(department_id):
        """Get teachers by department."""
        return Teacher.objects.filter(department_id=department_id).select_related(
            "user", "department"
        )

    @staticmethod
    def get_class_teacher(class_id):
        """Get the class teacher for a specific class."""
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
            year = timezone.now().year

        evaluations = TeacherEvaluation.objects.filter(
            teacher=teacher, evaluation_date__year=year
        )

        if not evaluations.exists():
            return None

        avg_score = evaluations.aggregate(Avg("score"))["score__avg"]
        return {
            "average_score": avg_score,
            "evaluation_count": evaluations.count(),
            "latest_evaluation": evaluations.order_by("-evaluation_date").first(),
            "trend": [
                {"date": e.evaluation_date, "score": float(e.score)}
                for e in evaluations.order_by("evaluation_date")
            ],
        }

    @staticmethod
    def get_top_performing_teachers(limit=10):
        """Get top performing teachers based on evaluation scores."""
        return (
            Teacher.objects.active()
            .with_evaluation_stats()
            .filter(avg_evaluation_score__isnull=False)
            .order_by("-avg_evaluation_score")[:limit]
        )

    @staticmethod
    def get_teacher_workload(academic_year=None):
        """Get teacher workload distribution."""
        if not academic_year:
            academic_year = AcademicYear.objects.filter(is_current=True).first()

        return (
            Teacher.objects.active()
            .annotate(
                class_count=Count(
                    "class_assignments",
                    filter=Q(class_assignments__academic_year=academic_year),
                    distinct=True,
                ),
                subject_count=Count(
                    "class_assignments__subject",
                    filter=Q(class_assignments__academic_year=academic_year),
                    distinct=True,
                ),
            )
            .order_by("-class_count")
        )

    @staticmethod
    def get_departmental_performance():
        """Get performance metrics by department."""
        return Department.objects.annotate(
            teacher_count=Count("teachers", filter=Q(teachers__status="Active")),
            avg_score=Avg("teachers__evaluations__score"),
            avg_experience=Avg("teachers__experience_years"),
        ).filter(teacher_count__gt=0)

    @staticmethod
    def get_performance_by_experience():
        """Get performance correlation with experience."""
        return [
            {
                "range": "0-2 years",
                "avg_score": TeacherEvaluation.objects.filter(
                    teacher__experience_years__lt=2
                ).aggregate(avg_score=Avg("score"))["avg_score"]
                or 0,
                "count": Teacher.objects.filter(experience_years__lt=2).count(),
            },
            {
                "range": "2-5 years",
                "avg_score": TeacherEvaluation.objects.filter(
                    teacher__experience_years__gte=2, teacher__experience_years__lt=5
                ).aggregate(avg_score=Avg("score"))["avg_score"]
                or 0,
                "count": Teacher.objects.filter(
                    experience_years__gte=2, experience_years__lt=5
                ).count(),
            },
            {
                "range": "5-10 years",
                "avg_score": TeacherEvaluation.objects.filter(
                    teacher__experience_years__gte=5, teacher__experience_years__lt=10
                ).aggregate(avg_score=Avg("score"))["avg_score"]
                or 0,
                "count": Teacher.objects.filter(
                    experience_years__gte=5, experience_years__lt=10
                ).count(),
            },
            {
                "range": "10+ years",
                "avg_score": TeacherEvaluation.objects.filter(
                    teacher__experience_years__gte=10
                ).aggregate(avg_score=Avg("score"))["avg_score"]
                or 0,
                "count": Teacher.objects.filter(experience_years__gte=10).count(),
            },
        ]

    @staticmethod
    def get_teacher_performance_trend(months=12):
        """Get performance trend over time."""
        start_date = timezone.now().date() - timedelta(days=30 * months)

        evaluations = (
            TeacherEvaluation.objects.filter(evaluation_date__gte=start_date)
            .annotate(month=TruncMonth("evaluation_date"))
            .values("month")
            .annotate(avg_score=Avg("score"), count=Count("id"))
            .order_by("month")
        )

        return {
            "months": [e["month"].strftime("%b %Y") for e in evaluations],
            "scores": [float(e["avg_score"]) for e in evaluations],
            "counts": [e["count"] for e in evaluations],
        }

    @staticmethod
    def get_teacher_statistics():
        """Get comprehensive teacher statistics."""
        total_teachers = Teacher.objects.count()
        active_teachers = Teacher.objects.filter(status="Active").count()
        on_leave_teachers = Teacher.objects.filter(status="On Leave").count()
        terminated_teachers = Teacher.objects.filter(status="Terminated").count()

        avg_experience = (
            Teacher.objects.aggregate(avg=Avg("experience_years"))["avg"] or 0
        )
        avg_salary = Teacher.objects.aggregate(avg=Avg("salary"))["avg"] or 0

        contract_distribution = (
            Teacher.objects.values("contract_type")
            .annotate(count=Count("id"))
            .order_by("contract_type")
        )

        recent_hires = Teacher.objects.filter(
            joining_date__gte=timezone.now().date() - timedelta(days=365)
        ).count()

        tenure_distribution = [
            {
                "range": "<1 year",
                "count": Teacher.objects.filter(
                    joining_date__gte=timezone.now().date() - timedelta(days=365)
                ).count(),
            },
            {
                "range": "1-3 years",
                "count": Teacher.objects.filter(
                    joining_date__lt=timezone.now().date() - timedelta(days=365),
                    joining_date__gte=timezone.now().date() - timedelta(days=3 * 365),
                ).count(),
            },
            {
                "range": "3-5 years",
                "count": Teacher.objects.filter(
                    joining_date__lt=timezone.now().date() - timedelta(days=3 * 365),
                    joining_date__gte=timezone.now().date() - timedelta(days=5 * 365),
                ).count(),
            },
            {
                "range": "5+ years",
                "count": Teacher.objects.filter(
                    joining_date__lt=timezone.now().date() - timedelta(days=5 * 365)
                ).count(),
            },
        ]

        return {
            "total_teachers": total_teachers,
            "active_teachers": active_teachers,
            "on_leave_teachers": on_leave_teachers,
            "terminated_teachers": terminated_teachers,
            "avg_experience": avg_experience,
            "avg_salary": avg_salary,
            "contract_distribution": contract_distribution,
            "recent_hires": recent_hires,
            "tenure_distribution": tenure_distribution,
        }

    @staticmethod
    def get_teacher_export_data(filters=None):
        """Get teacher data for export with optional filters."""
        queryset = Teacher.objects.select_related("user", "department")

        if filters:
            if "status" in filters and filters["status"]:
                queryset = queryset.filter(status=filters["status"])
            if "department" in filters and filters["department"]:
                queryset = queryset.filter(department_id=filters["department"])
            if "contract_type" in filters and filters["contract_type"]:
                queryset = queryset.filter(contract_type=filters["contract_type"])

        return queryset
