# src/teachers/managers.py
"""
Custom managers and querysets for optimized database operations in the teachers module.
"""

from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Union

from django.contrib.auth import get_user_model
from django.db import models
from django.db.models import (
    Avg,
    BooleanField,
    Case,
    Count,
    DecimalField,
    Exists,
    F,
    FloatField,
    IntegerField,
    Max,
    Min,
    OuterRef,
    Prefetch,
    Q,
    Subquery,
    Sum,
    Value,
    When,
)
from django.utils import timezone

User = get_user_model()


class TeacherQuerySet(models.QuerySet):
    """Custom QuerySet for Teacher model with optimized queries."""

    def active(self):
        """Filter active teachers."""
        return self.filter(status="Active")

    def inactive(self):
        """Filter inactive teachers (on leave or terminated)."""
        return self.filter(status__in=["On Leave", "Terminated"])

    def on_leave(self):
        """Filter teachers on leave."""
        return self.filter(status="On Leave")

    def terminated(self):
        """Filter terminated teachers."""
        return self.filter(status="Terminated")

    def by_department(self, department_id):
        """Filter teachers by department."""
        return self.filter(department_id=department_id)

    def by_contract_type(self, contract_type):
        """Filter teachers by contract type."""
        return self.filter(contract_type=contract_type)

    def permanent(self):
        """Filter permanent teachers."""
        return self.filter(contract_type="Permanent")

    def temporary(self):
        """Filter temporary teachers."""
        return self.filter(contract_type="Temporary")

    def contract(self):
        """Filter contract teachers."""
        return self.filter(contract_type="Contract")

    def by_experience_range(self, min_years=None, max_years=None):
        """Filter teachers by experience range."""
        queryset = self
        if min_years is not None:
            queryset = queryset.filter(experience_years__gte=min_years)
        if max_years is not None:
            queryset = queryset.filter(experience_years__lte=max_years)
        return queryset

    def junior(self, max_years=2):
        """Filter junior teachers (less than specified years of experience)."""
        return self.filter(experience_years__lt=max_years)

    def senior(self, min_years=10):
        """Filter senior teachers (more than specified years of experience)."""
        return self.filter(experience_years__gte=min_years)

    def hired_in_period(self, start_date, end_date):
        """Filter teachers hired within a specific period."""
        return self.filter(joining_date__range=[start_date, end_date])

    def hired_this_year(self):
        """Filter teachers hired this year."""
        current_year = timezone.now().year
        return self.filter(joining_date__year=current_year)

    def recently_hired(self, days=90):
        """Filter recently hired teachers."""
        cutoff_date = timezone.now().date() - timedelta(days=days)
        return self.filter(joining_date__gte=cutoff_date)

    def by_salary_range(self, min_salary=None, max_salary=None):
        """Filter teachers by salary range."""
        queryset = self
        if min_salary is not None:
            queryset = queryset.filter(salary__gte=min_salary)
        if max_salary is not None:
            queryset = queryset.filter(salary__lte=max_salary)
        return queryset

    def high_earners(self, threshold=50000):
        """Filter high-earning teachers."""
        return self.filter(salary__gte=threshold)

    def with_basic_relations(self):
        """Prefetch basic related objects to reduce queries."""
        return self.select_related("user", "department").prefetch_related(
            "user__groups"
        )

    def with_evaluation_stats(self):
        """Annotate with evaluation statistics."""
        return self.annotate(
            evaluation_count=Count("evaluations"),
            avg_evaluation_score=Avg("evaluations__score"),
            latest_evaluation_score=Subquery(
                self.model.evaluations.through.objects.filter(teacher=OuterRef("pk"))
                .order_by("-evaluation_date")
                .values("score")[:1]
            ),
            latest_evaluation_date=Subquery(
                self.model.evaluations.through.objects.filter(teacher=OuterRef("pk"))
                .order_by("-evaluation_date")
                .values("evaluation_date")[:1]
            ),
            needs_evaluation=Case(
                When(
                    Q(evaluations__isnull=True)
                    | Q(
                        evaluations__evaluation_date__lt=timezone.now().date()
                        - timedelta(days=180)
                    ),
                    then=Value(True),
                ),
                default=Value(False),
                output_field=BooleanField(),
            ),
        )

    def with_workload_stats(self, academic_year=None):
        """Annotate with workload statistics."""
        from src.teachers.models import TeacherClassAssignment

        filter_kwargs = {}
        if academic_year:
            filter_kwargs["class_assignments__academic_year"] = academic_year

        return self.annotate(
            total_assignments=Count("class_assignments", filter=Q(**filter_kwargs)),
            unique_classes=Count(
                "class_assignments__class_instance",
                distinct=True,
                filter=Q(**filter_kwargs),
            ),
            unique_subjects=Count(
                "class_assignments__subject", distinct=True, filter=Q(**filter_kwargs)
            ),
            class_teacher_count=Count(
                "class_assignments",
                filter=Q(class_assignments__is_class_teacher=True, **filter_kwargs),
            ),
            workload_level=Case(
                When(total_assignments__gte=8, then=Value("Heavy")),
                When(total_assignments__gte=4, then=Value("Moderate")),
                When(total_assignments__gte=1, then=Value("Light")),
                default=Value("None"),
                output_field=models.CharField(),
            ),
        )

    def with_tenure_info(self):
        """Annotate with tenure information."""
        today = timezone.now().date()
        return self.annotate(
            tenure_days=today - F("joining_date"),
            tenure_years=Case(
                When(
                    joining_date__isnull=False,
                    then=(today - F("joining_date")) / 365.25,
                ),
                default=Value(0),
                output_field=FloatField(),
            ),
            is_new_hire=Case(
                When(joining_date__gte=today - timedelta(days=90), then=Value(True)),
                default=Value(False),
                output_field=BooleanField(),
            ),
        )

    def with_performance_indicators(self):
        """Annotate with performance indicators."""
        return self.annotate(
            has_recent_evaluation=Exists(
                self.model.evaluations.through.objects.filter(
                    teacher=OuterRef("pk"),
                    evaluation_date__gte=timezone.now().date() - timedelta(days=180),
                )
            ),
            is_high_performer=Case(
                When(
                    Q(evaluations__score__gte=85)
                    & Q(
                        evaluations__evaluation_date__gte=timezone.now().date()
                        - timedelta(days=365)
                    ),
                    then=Value(True),
                ),
                default=Value(False),
                output_field=BooleanField(),
            ),
            needs_improvement=Case(
                When(
                    Q(evaluations__score__lt=70)
                    & Q(
                        evaluations__evaluation_date__gte=timezone.now().date()
                        - timedelta(days=365)
                    ),
                    then=Value(True),
                ),
                default=Value(False),
                output_field=BooleanField(),
            ),
        )

    def department_heads(self):
        """Filter teachers who are department heads."""
        return self.filter(department__head=F("id"))

    def class_teachers(self, academic_year=None):
        """Filter teachers who are class teachers."""
        filter_kwargs = {"class_assignments__is_class_teacher": True}
        if academic_year:
            filter_kwargs["class_assignments__academic_year"] = academic_year
        return self.filter(**filter_kwargs).distinct()

    def available_for_assignment(self, academic_year=None, max_assignments=8):
        """Filter teachers available for new assignments."""
        return self.with_workload_stats(academic_year).filter(
            status="Active", total_assignments__lt=max_assignments
        )

    def overloaded(self, academic_year=None, threshold=8):
        """Filter overloaded teachers."""
        return self.with_workload_stats(academic_year).filter(
            total_assignments__gte=threshold
        )

    def underutilized(self, academic_year=None, threshold=3):
        """Filter underutilized teachers."""
        return self.with_workload_stats(academic_year).filter(
            status="Active", total_assignments__lt=threshold
        )

    def top_performers(self, limit=10, days=365):
        """Get top performing teachers based on recent evaluations."""
        cutoff_date = timezone.now().date() - timedelta(days=days)
        return (
            self.with_evaluation_stats()
            .filter(
                evaluations__evaluation_date__gte=cutoff_date,
                avg_evaluation_score__isnull=False,
            )
            .order_by("-avg_evaluation_score")[:limit]
        )

    def requiring_attention(self):
        """Filter teachers requiring management attention."""
        return (
            self.with_evaluation_stats()
            .with_performance_indicators()
            .filter(
                Q(needs_improvement=True)
                | Q(needs_evaluation=True)
                | Q(status="On Leave")
            )
        )

    def for_department_comparison(self):
        """Optimize queryset for department comparison analysis."""
        return (
            self.select_related("department")
            .with_evaluation_stats()
            .annotate(department_name=F("department__name"))
        )

    def search(self, query):
        """Full-text search across teacher fields."""
        if not query:
            return self

        return self.filter(
            Q(user__first_name__icontains=query)
            | Q(user__last_name__icontains=query)
            | Q(employee_id__icontains=query)
            | Q(user__email__icontains=query)
            | Q(position__icontains=query)
            | Q(specialization__icontains=query)
            | Q(qualification__icontains=query)
            | Q(department__name__icontains=query)
        ).distinct()


class TeacherManager(models.Manager):
    """Custom Manager for Teacher model."""

    def get_queryset(self):
        """Return custom queryset."""
        return TeacherQuerySet(self.model, using=self._db)

    def active(self):
        return self.get_queryset().active()

    def inactive(self):
        return self.get_queryset().inactive()

    def by_department(self, department_id):
        return self.get_queryset().by_department(department_id)

    def with_basic_relations(self):
        return self.get_queryset().with_basic_relations()

    def with_evaluation_stats(self):
        return self.get_queryset().with_evaluation_stats()

    def with_workload_stats(self, academic_year=None):
        return self.get_queryset().with_workload_stats(academic_year)

    def get_performance_summary(self, department_id=None, academic_year=None):
        """Get performance summary statistics."""
        queryset = self.with_evaluation_stats()

        if department_id:
            queryset = queryset.filter(department_id=department_id)

        return queryset.aggregate(
            total_teachers=Count("id"),
            evaluated_teachers=Count("id", filter=Q(evaluation_count__gt=0)),
            avg_score=Avg("avg_evaluation_score"),
            high_performers=Count("id", filter=Q(avg_evaluation_score__gte=85)),
            needs_improvement=Count("id", filter=Q(avg_evaluation_score__lt=70)),
            never_evaluated=Count("id", filter=Q(evaluation_count=0)),
        )

    def get_workload_summary(self, academic_year=None):
        """Get workload distribution summary."""
        queryset = self.with_workload_stats(academic_year).filter(status="Active")

        return queryset.aggregate(
            total_active=Count("id"),
            overloaded=Count("id", filter=Q(total_assignments__gte=8)),
            balanced=Count(
                "id", filter=Q(total_assignments__gte=4, total_assignments__lt=8)
            ),
            underutilized=Count("id", filter=Q(total_assignments__lt=4)),
            class_teachers=Count("id", filter=Q(class_teacher_count__gt=0)),
            avg_assignments=Avg("total_assignments"),
        )

    def get_hiring_trends(self, years=5):
        """Get hiring trends over specified years."""
        current_year = timezone.now().year
        trends = []

        for year in range(current_year - years + 1, current_year + 1):
            year_stats = self.filter(joining_date__year=year).aggregate(
                total_hired=Count("id"),
                permanent_hired=Count("id", filter=Q(contract_type="Permanent")),
                temporary_hired=Count("id", filter=Q(contract_type="Temporary")),
                contract_hired=Count("id", filter=Q(contract_type="Contract")),
                avg_experience=Avg("experience_years"),
            )
            year_stats["year"] = year
            trends.append(year_stats)

        return trends

    def get_department_distribution(self):
        """Get teacher distribution by department."""
        return (
            self.values("department__name")
            .annotate(
                teacher_count=Count("id"),
                active_count=Count("id", filter=Q(status="Active")),
                avg_experience=Avg("experience_years"),
                avg_salary=Avg("salary"),
            )
            .order_by("-teacher_count")
        )


class TeacherEvaluationQuerySet(models.QuerySet):
    """Custom QuerySet for TeacherEvaluation model."""

    def for_teacher(self, teacher_id):
        """Filter evaluations for a specific teacher."""
        return self.filter(teacher_id=teacher_id)

    def by_evaluator(self, evaluator_id):
        """Filter evaluations by evaluator."""
        return self.filter(evaluator_id=evaluator_id)

    def by_status(self, status):
        """Filter evaluations by status."""
        return self.filter(status=status)

    def pending(self):
        """Filter pending evaluations."""
        return self.filter(status__in=["draft", "submitted"])

    def completed(self):
        """Filter completed evaluations."""
        return self.filter(status__in=["reviewed", "closed"])

    def in_period(self, start_date, end_date):
        """Filter evaluations in a specific period."""
        return self.filter(evaluation_date__range=[start_date, end_date])

    def this_year(self):
        """Filter evaluations from current year."""
        current_year = timezone.now().year
        return self.filter(evaluation_date__year=current_year)

    def recent(self, days=90):
        """Filter recent evaluations."""
        cutoff_date = timezone.now().date() - timedelta(days=days)
        return self.filter(evaluation_date__gte=cutoff_date)

    def by_score_range(self, min_score=None, max_score=None):
        """Filter evaluations by score range."""
        queryset = self
        if min_score is not None:
            queryset = queryset.filter(score__gte=min_score)
        if max_score is not None:
            queryset = queryset.filter(score__lte=max_score)
        return queryset

    def high_performing(self, threshold=85):
        """Filter high-performing evaluations."""
        return self.filter(score__gte=threshold)

    def low_performing(self, threshold=70):
        """Filter low-performing evaluations."""
        return self.filter(score__lt=threshold)

    def excellent(self):
        """Filter excellent evaluations (90%+)."""
        return self.filter(score__gte=90)

    def needs_improvement(self):
        """Filter evaluations indicating need for improvement."""
        return self.filter(score__lt=70)

    def requiring_followup(self):
        """Filter evaluations requiring followup."""
        return self.filter(score__lt=70, status__in=["submitted", "reviewed"])

    def overdue_followup(self):
        """Filter evaluations with overdue followup."""
        return self.filter(
            followup_date__lt=timezone.now().date(),
            status__in=["submitted", "reviewed"],
        )

    def by_department(self, department_id):
        """Filter evaluations by teacher's department."""
        return self.filter(teacher__department_id=department_id)

    def with_teacher_info(self):
        """Prefetch teacher and user information."""
        return self.select_related(
            "teacher", "teacher__user", "teacher__department", "evaluator"
        )

    def with_criteria_analysis(self):
        """Annotate with criteria analysis."""
        # This would require custom database functions for JSON analysis
        # For now, we'll keep it simple
        return self.select_related("teacher", "evaluator")

    def latest_for_each_teacher(self):
        """Get latest evaluation for each teacher."""
        return self.filter(
            id__in=Subquery(
                self.values("teacher").annotate(latest_id=Max("id")).values("latest_id")
            )
        )

    def trend_analysis(self, teacher_id, months=12):
        """Get evaluation trend for a specific teacher."""
        cutoff_date = timezone.now().date() - timedelta(days=30 * months)
        return self.filter(
            teacher_id=teacher_id, evaluation_date__gte=cutoff_date
        ).order_by("evaluation_date")


class TeacherEvaluationManager(models.Manager):
    """Custom Manager for TeacherEvaluation model."""

    def get_queryset(self):
        return TeacherEvaluationQuerySet(self.model, using=self._db)

    def for_teacher(self, teacher_id):
        return self.get_queryset().for_teacher(teacher_id)

    def requiring_followup(self):
        return self.get_queryset().requiring_followup()

    def overdue_followup(self):
        return self.get_queryset().overdue_followup()

    def with_teacher_info(self):
        return self.get_queryset().with_teacher_info()

    def get_performance_distribution(self, department_id=None, year=None):
        """Get performance score distribution."""
        queryset = self.get_queryset()

        if department_id:
            queryset = queryset.filter(teacher__department_id=department_id)

        if year:
            queryset = queryset.filter(evaluation_date__year=year)

        return queryset.aggregate(
            total_evaluations=Count("id"),
            avg_score=Avg("score"),
            min_score=Min("score"),
            max_score=Max("score"),
            excellent=Count("id", filter=Q(score__gte=90)),
            good=Count("id", filter=Q(score__gte=80, score__lt=90)),
            satisfactory=Count("id", filter=Q(score__gte=70, score__lt=80)),
            needs_improvement=Count("id", filter=Q(score__gte=60, score__lt=70)),
            poor=Count("id", filter=Q(score__lt=60)),
        )

    def get_evaluator_stats(self, evaluator_id):
        """Get statistics for a specific evaluator."""
        return self.filter(evaluator_id=evaluator_id).aggregate(
            total_evaluations=Count("id"),
            avg_score_given=Avg("score"),
            evaluations_this_year=Count(
                "id", filter=Q(evaluation_date__year=timezone.now().year)
            ),
            strict_evaluator=Case(
                When(avg_score_given__lt=75, then=Value(True)),
                default=Value(False),
                output_field=BooleanField(),
            ),
        )


class TeacherClassAssignmentQuerySet(models.QuerySet):
    """Custom QuerySet for TeacherClassAssignment model."""

    def for_teacher(self, teacher_id):
        """Filter assignments for a specific teacher."""
        return self.filter(teacher_id=teacher_id)

    def for_class(self, class_id):
        """Filter assignments for a specific class."""
        return self.filter(class_instance_id=class_id)

    def for_subject(self, subject_id):
        """Filter assignments for a specific subject."""
        return self.filter(subject_id=subject_id)

    def for_academic_year(self, academic_year):
        """Filter assignments for a specific academic year."""
        return self.filter(academic_year=academic_year)

    def current_year(self):
        """Filter assignments for current academic year."""
        from src.courses.models import AcademicYear

        current_year = AcademicYear.objects.filter(is_current=True).first()
        if current_year:
            return self.filter(academic_year=current_year)
        return self.none()

    def class_teachers_only(self):
        """Filter only class teacher assignments."""
        return self.filter(is_class_teacher=True)

    def subject_teachers_only(self):
        """Filter only subject teacher assignments."""
        return self.filter(is_class_teacher=False)

    def by_department(self, department_id):
        """Filter assignments by teacher's department."""
        return self.filter(teacher__department_id=department_id)

    def active_teachers_only(self):
        """Filter assignments for active teachers only."""
        return self.filter(teacher__status="Active")

    def with_full_info(self):
        """Prefetch all related information."""
        return self.select_related(
            "teacher",
            "teacher__user",
            "teacher__department",
            "class_instance",
            "class_instance__grade",
            "class_instance__grade__section",
            "subject",
            "academic_year",
        )

    def workload_analysis(self):
        """Annotate with workload analysis."""
        return self.values("teacher").annotate(
            total_assignments=Count("id"),
            unique_classes=Count("class_instance", distinct=True),
            unique_subjects=Count("subject", distinct=True),
            class_teacher_duties=Count("id", filter=Q(is_class_teacher=True)),
        )

    def conflicts(self):
        """Find potential scheduling conflicts."""
        # This would require timetable integration
        # For now, return basic duplicate detection
        return (
            self.values("teacher", "class_instance", "subject", "academic_year")
            .annotate(assignment_count=Count("id"))
            .filter(assignment_count__gt=1)
        )


class TeacherClassAssignmentManager(models.Manager):
    """Custom Manager for TeacherClassAssignment model."""

    def get_queryset(self):
        return TeacherClassAssignmentQuerySet(self.model, using=self._db)

    def current_year(self):
        return self.get_queryset().current_year()

    def for_teacher(self, teacher_id):
        return self.get_queryset().for_teacher(teacher_id)

    def with_full_info(self):
        return self.get_queryset().with_full_info()

    def get_workload_distribution(self, academic_year=None):
        """Get workload distribution across teachers."""
        queryset = self.get_queryset()
        if academic_year:
            queryset = queryset.filter(academic_year=academic_year)

        return queryset.workload_analysis().aggregate(
            total_teachers_assigned=Count("teacher", distinct=True),
            avg_assignments_per_teacher=Avg("total_assignments"),
            max_assignments=Max("total_assignments"),
            min_assignments=Min("total_assignments"),
            total_class_teacher_roles=Sum("class_teacher_duties"),
        )

    def get_subject_distribution(self, academic_year=None):
        """Get distribution of subject assignments."""
        queryset = self.get_queryset()
        if academic_year:
            queryset = queryset.filter(academic_year=academic_year)

        return (
            queryset.values("subject__name")
            .annotate(
                teacher_count=Count("teacher", distinct=True),
                class_count=Count("class_instance", distinct=True),
                total_assignments=Count("id"),
            )
            .order_by("-total_assignments")
        )

    def get_class_coverage(self, academic_year=None):
        """Get class coverage statistics."""
        queryset = self.get_queryset()
        if academic_year:
            queryset = queryset.filter(academic_year=academic_year)

        return queryset.values("class_instance").annotate(
            teacher_count=Count("teacher", distinct=True),
            subject_count=Count("subject", distinct=True),
            has_class_teacher=Exists(
                queryset.filter(
                    class_instance=OuterRef("class_instance"), is_class_teacher=True
                )
            ),
        )


# Specialized managers for analytics and reporting


class TeacherAnalyticsManager:
    """Manager for teacher analytics operations."""

    def __init__(self):
        from src.teachers.models import (
            Teacher,
            TeacherClassAssignment,
            TeacherEvaluation,
        )

        self.teacher_model = Teacher
        self.evaluation_model = TeacherEvaluation
        self.assignment_model = TeacherClassAssignment

    def get_performance_trends(self, department_id=None, months=12):
        """Get performance trends over time."""
        cutoff_date = timezone.now().date() - timedelta(days=30 * months)

        queryset = self.evaluation_model.objects.filter(
            evaluation_date__gte=cutoff_date
        )

        if department_id:
            queryset = queryset.filter(teacher__department_id=department_id)

        # Group by month and calculate averages
        trends = (
            queryset.extra(select={"month": "DATE_TRUNC('month', evaluation_date)"})
            .values("month")
            .annotate(
                avg_score=Avg("score"),
                evaluation_count=Count("id"),
                teacher_count=Count("teacher", distinct=True),
            )
            .order_by("month")
        )

        return list(trends)

    def get_correlation_analysis(self, academic_year=None):
        """Analyze correlations between teacher attributes and performance."""
        queryset = self.teacher_model.objects.with_evaluation_stats()

        if academic_year:
            # Filter evaluations to specific academic year
            year_start = academic_year.start_date
            year_end = academic_year.end_date
            queryset = queryset.filter(
                evaluations__evaluation_date__range=[year_start, year_end]
            )

        # Calculate correlations (simplified)
        return queryset.filter(avg_evaluation_score__isnull=False).aggregate(
            experience_high_performers=Count(
                "id", filter=Q(experience_years__gte=5, avg_evaluation_score__gte=85)
            ),
            experience_low_performers=Count(
                "id", filter=Q(experience_years__gte=5, avg_evaluation_score__lt=70)
            ),
            junior_high_performers=Count(
                "id", filter=Q(experience_years__lt=5, avg_evaluation_score__gte=85)
            ),
            junior_low_performers=Count(
                "id", filter=Q(experience_years__lt=5, avg_evaluation_score__lt=70)
            ),
            permanent_high_performers=Count(
                "id", filter=Q(contract_type="Permanent", avg_evaluation_score__gte=85)
            ),
            temporary_high_performers=Count(
                "id", filter=Q(contract_type="Temporary", avg_evaluation_score__gte=85)
            ),
        )

    def get_department_benchmarks(self):
        """Get performance benchmarks by department."""
        return (
            self.teacher_model.objects.values("department__name")
            .annotate(
                teacher_count=Count("id"),
                avg_experience=Avg("experience_years"),
                avg_performance=Avg("evaluations__score"),
                high_performer_rate=Count("id", filter=Q(evaluations__score__gte=85))
                * 100.0
                / Count("id"),
                evaluation_coverage=Count("id", filter=Q(evaluations__isnull=False))
                * 100.0
                / Count("id"),
            )
            .filter(teacher_count__gt=0)
            .order_by("-avg_performance")
        )

    def get_retention_metrics(self, years=5):
        """Calculate teacher retention metrics."""
        current_date = timezone.now().date()
        metrics = {}

        for year in range(years):
            year_start = current_date - timedelta(days=365 * (year + 1))
            year_end = current_date - timedelta(days=365 * year)

            teachers_at_start = self.teacher_model.objects.filter(
                Q(joining_date__lte=year_start)
                & (Q(status="Active") | Q(updated_at__gt=year_end))
            ).count()

            teachers_left = self.teacher_model.objects.filter(
                status="Terminated", updated_at__range=[year_start, year_end]
            ).count()

            retention_rate = (
                (teachers_at_start - teachers_left) / teachers_at_start * 100
                if teachers_at_start > 0
                else 0
            )

            metrics[year] = {
                "year_start": year_start,
                "year_end": year_end,
                "teachers_at_start": teachers_at_start,
                "teachers_left": teachers_left,
                "retention_rate": round(retention_rate, 2),
            }

        return metrics


# Factory function to create optimized querysets


def create_teacher_summary_queryset(department_id=None, academic_year=None):
    """Create an optimized queryset for teacher summary display."""
    from src.teachers.models import Teacher

    queryset = Teacher.objects.with_basic_relations().with_evaluation_stats()

    if academic_year:
        queryset = queryset.with_workload_stats(academic_year)

    if department_id:
        queryset = queryset.filter(department_id=department_id)

    return queryset.select_related("department").prefetch_related(
        Prefetch(
            "evaluations",
            queryset=Teacher.evaluations.through.objects.select_related(
                "evaluator"
            ).order_by("-evaluation_date")[:3],
        )
    )


def create_performance_analysis_queryset(filters=None):
    """Create optimized queryset for performance analysis."""
    from src.teachers.models import TeacherEvaluation

    queryset = TeacherEvaluation.objects.with_teacher_info()

    if filters:
        if "department_id" in filters:
            queryset = queryset.filter(teacher__department_id=filters["department_id"])

        if "date_range" in filters:
            start_date, end_date = filters["date_range"]
            queryset = queryset.filter(evaluation_date__range=[start_date, end_date])

        if "score_range" in filters:
            min_score, max_score = filters["score_range"]
            queryset = queryset.filter(score__range=[min_score, max_score])

    return queryset.order_by("-evaluation_date")
