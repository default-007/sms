# src/teachers/services/analytics_service.py
import json
from datetime import date, datetime, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db.models import (
    Avg,
    Case,
    Count,
    DateField,
    F,
    FloatField,
    IntegerField,
    Max,
    Min,
    OuterRef,
    Q,
    StdDev,
    Subquery,
    Sum,
    Value,
    When,
)
from django.db.models.functions import (
    Coalesce,
    Extract,
    ExtractMonth,
    ExtractYear,
    TruncMonth,
    TruncQuarter,
    TruncWeek,
    TruncYear,
)
from django.utils import timezone

from src.academics.models import AcademicYear, Department
from src.students.models import Student
from src.teachers.models import Teacher, TeacherClassAssignment, TeacherEvaluation

User = get_user_model()


class TeacherAnalyticsService:
    """Comprehensive analytics service for teacher performance and metrics."""

    @staticmethod
    def get_performance_overview(academic_year=None, department_id=None):
        """Get comprehensive performance overview for teachers."""
        if not academic_year:
            academic_year = AcademicYear.objects.filter(is_current=True).first()

        queryset = Teacher.objects.active()

        if department_id:
            queryset = queryset.filter(department_id=department_id)

        # Base performance metrics
        base_stats = queryset.aggregate(
            total_teachers=Count("id"),
            avg_experience=Avg("experience_years"),
            avg_evaluation_score=Avg("evaluations__score"),
            total_evaluations=Count("evaluations"),
            high_performers=Count("id", filter=Q(evaluations__score__gte=85)),
            needs_improvement=Count("id", filter=Q(evaluations__score__lt=70)),
        )

        # Performance distribution
        performance_distribution = [
            {
                "range": "Excellent (90-100%)",
                "count": queryset.filter(evaluations__score__gte=90).distinct().count(),
                "percentage": 0,
            },
            {
                "range": "Good (80-89%)",
                "count": queryset.filter(
                    evaluations__score__gte=80, evaluations__score__lt=90
                )
                .distinct()
                .count(),
                "percentage": 0,
            },
            {
                "range": "Satisfactory (70-79%)",
                "count": queryset.filter(
                    evaluations__score__gte=70, evaluations__score__lt=80
                )
                .distinct()
                .count(),
                "percentage": 0,
            },
            {
                "range": "Needs Improvement (60-69%)",
                "count": queryset.filter(
                    evaluations__score__gte=60, evaluations__score__lt=70
                )
                .distinct()
                .count(),
                "percentage": 0,
            },
            {
                "range": "Poor (Below 60%)",
                "count": queryset.filter(evaluations__score__lt=60).distinct().count(),
                "percentage": 0,
            },
        ]

        # Calculate percentages
        total_evaluated = sum(item["count"] for item in performance_distribution)
        if total_evaluated > 0:
            for item in performance_distribution:
                item["percentage"] = round((item["count"] / total_evaluated) * 100, 1)

        return {
            "base_stats": base_stats,
            "performance_distribution": performance_distribution,
            "academic_year": academic_year,
        }

    @staticmethod
    def get_workload_analysis(academic_year=None):
        """Analyze teacher workload distribution."""
        if not academic_year:
            academic_year = AcademicYear.objects.filter(is_current=True).first()

        workload_data = (
            Teacher.objects.active()
            .annotate(
                total_classes=Count(
                    "class_assignments__class_instance",
                    filter=Q(class_assignments__academic_year=academic_year),
                    distinct=True,
                ),
                total_subjects=Count(
                    "class_assignments__subject",
                    filter=Q(class_assignments__academic_year=academic_year),
                    distinct=True,
                ),
                total_students=Sum(
                    "class_assignments__class_instance__capacity",
                    filter=Q(class_assignments__academic_year=academic_year),
                ),
                class_teacher_count=Count(
                    "class_assignments",
                    filter=Q(
                        class_assignments__academic_year=academic_year,
                        class_assignments__is_class_teacher=True,
                    ),
                ),
            )
            .values(
                "id",
                "user__first_name",
                "user__last_name",
                "employee_id",
                "department__name",
                "total_classes",
                "total_subjects",
                "total_students",
                "class_teacher_count",
            )
            .order_by("-total_classes")
        )

        # Workload distribution analysis
        workload_stats = {
            "overloaded": workload_data.filter(total_classes__gte=8).count(),
            "balanced": workload_data.filter(
                total_classes__gte=4, total_classes__lt=8
            ).count(),
            "underutilized": workload_data.filter(total_classes__lt=4).count(),
        }

        return {
            "workload_data": list(workload_data),
            "workload_stats": workload_stats,
            "academic_year": academic_year,
        }

    @staticmethod
    def get_evaluation_trends(months=12, department_id=None):
        """Get evaluation trends over time."""
        start_date = timezone.now().date() - timedelta(days=30 * months)

        queryset = TeacherEvaluation.objects.filter(evaluation_date__gte=start_date)

        if department_id:
            queryset = queryset.filter(teacher__department_id=department_id)

        # Monthly trends
        monthly_trends = (
            queryset.annotate(month=TruncMonth("evaluation_date"))
            .values("month")
            .annotate(
                avg_score=Avg("score"),
                total_evaluations=Count("id"),
                high_scores=Count("id", filter=Q(score__gte=85)),
                low_scores=Count("id", filter=Q(score__lt=70)),
                avg_teaching_methodology=Avg(
                    Case(
                        When(
                            criteria__teaching_methodology__score__isnull=False,
                            then=F("criteria__teaching_methodology__score"),
                        ),
                        default=Value(0),
                        output_field=FloatField(),
                    )
                ),
                avg_subject_knowledge=Avg(
                    Case(
                        When(
                            criteria__subject_knowledge__score__isnull=False,
                            then=F("criteria__subject_knowledge__score"),
                        ),
                        default=Value(0),
                        output_field=FloatField(),
                    )
                ),
                avg_classroom_management=Avg(
                    Case(
                        When(
                            criteria__classroom_management__score__isnull=False,
                            then=F("criteria__classroom_management__score"),
                        ),
                        default=Value(0),
                        output_field=FloatField(),
                    )
                ),
            )
            .order_by("month")
        )

        # Quarterly comparison
        quarterly_trends = (
            queryset.annotate(quarter=TruncQuarter("evaluation_date"))
            .values("quarter")
            .annotate(avg_score=Avg("score"), total_evaluations=Count("id"))
            .order_by("quarter")
        )

        return {
            "monthly_trends": list(monthly_trends),
            "quarterly_trends": list(quarterly_trends),
        }

    @staticmethod
    def get_departmental_comparison():
        """Compare performance across departments."""
        departments = (
            Department.objects.annotate(
                teacher_count=Count("teachers", filter=Q(teachers__status="Active")),
                avg_experience=Avg("teachers__experience_years"),
                avg_evaluation_score=Avg("teachers__evaluations__score"),
                total_evaluations=Count("teachers__evaluations"),
                latest_evaluation_avg=Avg(
                    "teachers__evaluations__score",
                    filter=Q(
                        teachers__evaluations__evaluation_date__gte=timezone.now().date()
                        - timedelta(days=365)
                    ),
                ),
                high_performers=Count(
                    "teachers",
                    filter=Q(teachers__evaluations__score__gte=85),
                    distinct=True,
                ),
                needs_improvement=Count(
                    "teachers",
                    filter=Q(teachers__evaluations__score__lt=70),
                    distinct=True,
                ),
                avg_workload=Avg(
                    Subquery(
                        TeacherClassAssignment.objects.filter(
                            teacher__department=OuterRef("pk"),
                            academic_year__is_current=True,
                        )
                        .values("teacher")
                        .annotate(class_count=Count("class_instance", distinct=True))
                        .values("class_count")[:1]
                    )
                ),
            )
            .filter(teacher_count__gt=0)
            .order_by("-avg_evaluation_score")
        )

        return list(
            departments.values(
                "id",
                "name",
                "teacher_count",
                "avg_experience",
                "avg_evaluation_score",
                "total_evaluations",
                "latest_evaluation_avg",
                "high_performers",
                "needs_improvement",
                "avg_workload",
            )
        )

    @staticmethod
    def get_teacher_growth_analysis(teacher_id, months=24):
        """Analyze individual teacher growth over time."""
        try:
            teacher = Teacher.objects.get(id=teacher_id)
        except Teacher.DoesNotExist:
            return None

        start_date = timezone.now().date() - timedelta(days=30 * months)

        # Evaluation progression
        evaluations = TeacherEvaluation.objects.filter(
            teacher=teacher, evaluation_date__gte=start_date
        ).order_by("evaluation_date")

        if not evaluations.exists():
            return {"teacher": teacher, "evaluations": [], "growth_metrics": {}}

        # Calculate growth metrics
        first_score = evaluations.first().score
        latest_score = evaluations.last().score
        growth_rate = (
            ((latest_score - first_score) / first_score * 100) if first_score > 0 else 0
        )

        # Criteria improvement analysis
        criteria_analysis = {}
        for eval in evaluations:
            for criterion, data in eval.criteria.items():
                if criterion not in criteria_analysis:
                    criteria_analysis[criterion] = []
                if isinstance(data, dict) and "score" in data:
                    criteria_analysis[criterion].append(
                        {
                            "date": eval.evaluation_date,
                            "score": data["score"],
                            "max_score": data.get("max_score", 10),
                        }
                    )

        # Performance consistency
        scores = [float(e.score) for e in evaluations]
        consistency_score = 100 - (
            (max(scores) - min(scores)) / max(scores) * 100 if scores else 0
        )

        growth_metrics = {
            "total_evaluations": evaluations.count(),
            "first_score": float(first_score),
            "latest_score": float(latest_score),
            "growth_rate": round(growth_rate, 2),
            "average_score": round(sum(scores) / len(scores), 2) if scores else 0,
            "consistency_score": round(consistency_score, 2),
            "improvement_trend": (
                "Improving"
                if growth_rate > 5
                else "Stable" if growth_rate > -5 else "Declining"
            ),
        }

        return {
            "teacher": teacher,
            "evaluations": list(evaluations.values()),
            "criteria_analysis": criteria_analysis,
            "growth_metrics": growth_metrics,
        }

    @staticmethod
    def get_student_performance_correlation(academic_year=None):
        """Analyze correlation between teacher performance and student outcomes."""
        if not academic_year:
            academic_year = AcademicYear.objects.filter(is_current=True).first()

        # Get teacher assignments with student performance data
        correlations = []

        assignments = TeacherClassAssignment.objects.filter(
            academic_year=academic_year
        ).select_related("teacher", "class_instance", "subject")

        for assignment in assignments:
            # Get teacher's evaluation score
            teacher_eval = TeacherEvaluation.objects.filter(
                teacher=assignment.teacher,
                evaluation_date__year=academic_year.start_date.year,
            ).aggregate(avg_score=Avg("score"))["avg_score"]

            if not teacher_eval:
                continue

            # Get student performance in this class/subject
            # This would depend on your exam/grade models
            # For now, using a placeholder calculation
            student_performance = {
                "avg_attendance": 85.0,  # Placeholder
                "avg_grade": 78.5,  # Placeholder
                "pass_rate": 92.0,  # Placeholder
            }

            correlations.append(
                {
                    "teacher": assignment.teacher.get_full_name(),
                    "teacher_id": assignment.teacher.id,
                    "class": str(assignment.class_instance),
                    "subject": assignment.subject.name,
                    "teacher_score": float(teacher_eval),
                    "student_avg_attendance": student_performance["avg_attendance"],
                    "student_avg_grade": student_performance["avg_grade"],
                    "student_pass_rate": student_performance["pass_rate"],
                }
            )

        return correlations

    @staticmethod
    def get_evaluation_criteria_analysis(department_id=None, year=None):
        """Detailed analysis of evaluation criteria performance."""
        if not year:
            year = timezone.now().year

        queryset = TeacherEvaluation.objects.filter(evaluation_date__year=year)

        if department_id:
            queryset = queryset.filter(teacher__department_id=department_id)

        criteria_stats = {}

        for evaluation in queryset:
            for criterion, data in evaluation.criteria.items():
                if criterion not in criteria_stats:
                    criteria_stats[criterion] = {
                        "scores": [],
                        "max_scores": [],
                        "percentages": [],
                    }

                if isinstance(data, dict) and "score" in data:
                    score = data["score"]
                    max_score = data.get("max_score", 10)
                    percentage = (score / max_score * 100) if max_score > 0 else 0

                    criteria_stats[criterion]["scores"].append(score)
                    criteria_stats[criterion]["max_scores"].append(max_score)
                    criteria_stats[criterion]["percentages"].append(percentage)

        # Calculate statistics for each criterion
        analysis = {}
        for criterion, data in criteria_stats.items():
            if data["scores"]:
                analysis[criterion] = {
                    "average_score": round(
                        sum(data["scores"]) / len(data["scores"]), 2
                    ),
                    "average_percentage": round(
                        sum(data["percentages"]) / len(data["percentages"]), 2
                    ),
                    "min_score": min(data["scores"]),
                    "max_score": max(data["scores"]),
                    "std_deviation": (
                        round(
                            (
                                sum(
                                    (x - sum(data["scores"]) / len(data["scores"])) ** 2
                                    for x in data["scores"]
                                )
                                / len(data["scores"])
                            )
                            ** 0.5,
                            2,
                        )
                        if len(data["scores"]) > 1
                        else 0
                    ),
                    "evaluation_count": len(data["scores"]),
                    "performance_level": TeacherAnalyticsService._get_performance_level(
                        sum(data["percentages"]) / len(data["percentages"])
                    ),
                }

        return analysis

    @staticmethod
    def get_retention_analysis():
        """Analyze teacher retention patterns."""
        current_year = timezone.now().year

        # Yearly retention rates
        retention_data = []
        for year in range(current_year - 5, current_year + 1):
            year_start = date(year, 1, 1)
            year_end = date(year, 12, 31)

            teachers_start = Teacher.objects.filter(
                Q(joining_date__lte=year_start)
                & (Q(status="Terminated") | Q(updated_at__gt=year_end))
            ).count()

            teachers_left = Teacher.objects.filter(
                status="Terminated", updated_at__year=year
            ).count()

            retention_rate = (
                ((teachers_start - teachers_left) / teachers_start * 100)
                if teachers_start > 0
                else 0
            )

            retention_data.append(
                {
                    "year": year,
                    "teachers_start": teachers_start,
                    "teachers_left": teachers_left,
                    "retention_rate": round(retention_rate, 2),
                }
            )

        # Reasons for leaving analysis (based on status changes)
        termination_analysis = (
            Teacher.objects.filter(
                status="Terminated", updated_at__year__gte=current_year - 2
            )
            .values("contract_type")
            .annotate(count=Count("id"))
        )

        return {
            "retention_trends": retention_data,
            "termination_by_contract": list(termination_analysis),
        }

    @staticmethod
    def get_hiring_analysis():
        """Analyze hiring patterns and trends."""
        current_year = timezone.now().year

        # Hiring trends by year
        hiring_trends = []
        for year in range(current_year - 5, current_year + 1):
            year_hires = Teacher.objects.filter(joining_date__year=year)

            hiring_trends.append(
                {
                    "year": year,
                    "total_hires": year_hires.count(),
                    "permanent_hires": year_hires.filter(
                        contract_type="Permanent"
                    ).count(),
                    "temporary_hires": year_hires.filter(
                        contract_type="Temporary"
                    ).count(),
                    "contract_hires": year_hires.filter(
                        contract_type="Contract"
                    ).count(),
                    "avg_experience": year_hires.aggregate(avg=Avg("experience_years"))[
                        "avg"
                    ]
                    or 0,
                }
            )

        # Seasonal hiring patterns
        monthly_hiring = (
            Teacher.objects.filter(joining_date__year__gte=current_year - 2)
            .annotate(month=ExtractMonth("joining_date"))
            .values("month")
            .annotate(count=Count("id"))
            .order_by("month")
        )

        return {
            "hiring_trends": hiring_trends,
            "monthly_patterns": list(monthly_hiring),
        }

    @staticmethod
    def get_performance_predictors():
        """Identify factors that predict teacher performance."""
        teachers_with_evaluations = (
            Teacher.objects.filter(evaluations__isnull=False)
            .annotate(
                avg_score=Avg("evaluations__score"),
                evaluation_count=Count("evaluations"),
            )
            .filter(evaluation_count__gte=2)
        )

        # Analyze correlation between various factors and performance
        predictors = []

        for teacher in teachers_with_evaluations:
            predictors.append(
                {
                    "teacher_id": teacher.id,
                    "avg_score": float(teacher.avg_score),
                    "experience_years": float(teacher.experience_years),
                    "tenure_years": (timezone.now().date() - teacher.joining_date).days
                    / 365.25,
                    "contract_type": teacher.contract_type,
                    "department": (
                        teacher.department.name if teacher.department else "None"
                    ),
                    "evaluation_count": teacher.evaluation_count,
                }
            )

        return predictors

    @staticmethod
    def _get_performance_level(percentage):
        """Get performance level based on percentage."""
        if percentage >= 90:
            return "Excellent"
        elif percentage >= 80:
            return "Good"
        elif percentage >= 70:
            return "Satisfactory"
        elif percentage >= 60:
            return "Needs Improvement"
        else:
            return "Poor"

    @staticmethod
    def get_dashboard_metrics(academic_year=None, department_id=None):
        """Get key metrics for dashboard display."""
        if not academic_year:
            academic_year = AcademicYear.objects.filter(is_current=True).first()

        base_queryset = Teacher.objects.active()
        if department_id:
            base_queryset = base_queryset.filter(department_id=department_id)

        # Current period metrics
        current_metrics = {
            "total_teachers": base_queryset.count(),
            "avg_experience": base_queryset.aggregate(avg=Avg("experience_years"))[
                "avg"
            ]
            or 0,
            "evaluations_pending": TeacherEvaluation.objects.filter(
                status="draft", teacher__in=base_queryset
            ).count(),
            "high_performers": base_queryset.filter(
                evaluations__score__gte=85,
                evaluations__evaluation_date__year=timezone.now().year,
            )
            .distinct()
            .count(),
            "needs_attention": base_queryset.filter(
                evaluations__score__lt=70,
                evaluations__evaluation_date__year=timezone.now().year,
            )
            .distinct()
            .count(),
        }

        # Recent trends (last 30 days)
        thirty_days_ago = timezone.now().date() - timedelta(days=30)
        recent_metrics = {
            "new_hires": base_queryset.filter(
                joining_date__gte=thirty_days_ago
            ).count(),
            "recent_evaluations": TeacherEvaluation.objects.filter(
                teacher__in=base_queryset, evaluation_date__gte=thirty_days_ago
            ).count(),
            "avg_recent_score": TeacherEvaluation.objects.filter(
                teacher__in=base_queryset, evaluation_date__gte=thirty_days_ago
            ).aggregate(avg=Avg("score"))["avg"]
            or 0,
        }

        return {
            "current_metrics": current_metrics,
            "recent_metrics": recent_metrics,
            "academic_year": academic_year,
        }
