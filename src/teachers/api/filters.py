# src/teachers/api/filters.py
from datetime import timedelta

import django_filters
from django.db.models import Avg, Count, Q
from django.utils import timezone

from src.courses.models import AcademicYear, Department, Subject
from src.teachers.models import Teacher, TeacherClassAssignment, TeacherEvaluation


class TeacherFilter(django_filters.FilterSet):
    """Advanced filtering for Teacher model."""

    # Text search across multiple fields
    search = django_filters.CharFilter(method="filter_search", label="Search")

    # Status filtering
    status = django_filters.ChoiceFilter(
        choices=Teacher.STATUS_CHOICES, label="Employment Status"
    )

    # Department filtering
    department = django_filters.ModelChoiceFilter(
        queryset=Department.objects.all(), label="Department"
    )

    # Contract type filtering
    contract_type = django_filters.ChoiceFilter(
        choices=Teacher.CONTRACT_TYPE_CHOICES, label="Contract Type"
    )

    # Experience range filtering
    experience_min = django_filters.NumberFilter(
        field_name="experience_years",
        lookup_expr="gte",
        label="Minimum Experience (years)",
    )
    experience_max = django_filters.NumberFilter(
        field_name="experience_years",
        lookup_expr="lte",
        label="Maximum Experience (years)",
    )

    # Joining date range
    joined_after = django_filters.DateFilter(
        field_name="joining_date", lookup_expr="gte", label="Joined After"
    )
    joined_before = django_filters.DateFilter(
        field_name="joining_date", lookup_expr="lte", label="Joined Before"
    )

    # Salary range filtering
    salary_min = django_filters.NumberFilter(
        field_name="salary", lookup_expr="gte", label="Minimum Salary"
    )
    salary_max = django_filters.NumberFilter(
        field_name="salary", lookup_expr="lte", label="Maximum Salary"
    )

    # Performance-based filters
    has_evaluations = django_filters.BooleanFilter(
        method="filter_has_evaluations", label="Has Evaluations"
    )

    avg_score_min = django_filters.NumberFilter(
        method="filter_avg_score_min", label="Minimum Average Score"
    )
    avg_score_max = django_filters.NumberFilter(
        method="filter_avg_score_max", label="Maximum Average Score"
    )

    performance_level = django_filters.ChoiceFilter(
        method="filter_performance_level",
        choices=[
            ("excellent", "Excellent (90%+)"),
            ("good", "Good (80-89%)"),
            ("satisfactory", "Satisfactory (70-79%)"),
            ("needs_improvement", "Needs Improvement (60-69%)"),
            ("poor", "Poor (<60%)"),
        ],
        label="Performance Level",
    )

    # Assignment-based filters
    teaches_subject = django_filters.ModelChoiceFilter(
        queryset=Subject.objects.all(),
        method="filter_teaches_subject",
        label="Teaches Subject",
    )

    is_class_teacher = django_filters.BooleanFilter(
        method="filter_is_class_teacher", label="Is Class Teacher"
    )

    # Time-based filters
    recently_hired = django_filters.NumberFilter(
        method="filter_recently_hired", label="Hired in last N days"
    )

    tenure_years_min = django_filters.NumberFilter(
        method="filter_tenure_min", label="Minimum Tenure (years)"
    )
    tenure_years_max = django_filters.NumberFilter(
        method="filter_tenure_max", label="Maximum Tenure (years)"
    )

    class Meta:
        model = Teacher
        fields = {
            "employee_id": ["exact", "icontains"],
            "position": ["exact", "icontains"],
            "specialization": ["exact", "icontains"],
            "qualification": ["icontains"],
        }

    def filter_search(self, queryset, name, value):
        """Search across multiple fields."""
        if not value:
            return queryset

        return queryset.filter(
            Q(user__first_name__icontains=value)
            | Q(user__last_name__icontains=value)
            | Q(employee_id__icontains=value)
            | Q(user__email__icontains=value)
            | Q(position__icontains=value)
            | Q(specialization__icontains=value)
            | Q(qualification__icontains=value)
            | Q(department__name__icontains=value)
        ).distinct()

    def filter_has_evaluations(self, queryset, name, value):
        """Filter teachers who have or don't have evaluations."""
        if value is True:
            return queryset.filter(evaluations__isnull=False).distinct()
        elif value is False:
            return queryset.filter(evaluations__isnull=True).distinct()
        return queryset

    def filter_avg_score_min(self, queryset, name, value):
        """Filter by minimum average evaluation score."""
        if value is not None:
            return queryset.annotate(avg_score=Avg("evaluations__score")).filter(
                avg_score__gte=value
            )
        return queryset

    def filter_avg_score_max(self, queryset, name, value):
        """Filter by maximum average evaluation score."""
        if value is not None:
            return queryset.annotate(avg_score=Avg("evaluations__score")).filter(
                avg_score__lte=value
            )
        return queryset

    def filter_performance_level(self, queryset, name, value):
        """Filter by performance level category."""
        if not value:
            return queryset

        score_ranges = {
            "excellent": (90, 100),
            "good": (80, 89),
            "satisfactory": (70, 79),
            "needs_improvement": (60, 69),
            "poor": (0, 59),
        }

        if value in score_ranges:
            min_score, max_score = score_ranges[value]
            return queryset.annotate(avg_score=Avg("evaluations__score")).filter(
                avg_score__gte=min_score, avg_score__lte=max_score
            )

        return queryset

    def filter_teaches_subject(self, queryset, name, value):
        """Filter teachers who teach a specific subject."""
        if value:
            current_year = AcademicYear.objects.filter(is_current=True).first()
            return queryset.filter(
                class_assignments__subject=value,
                class_assignments__academic_year=current_year,
            ).distinct()
        return queryset

    def filter_is_class_teacher(self, queryset, name, value):
        """Filter teachers who are or aren't class teachers."""
        if value is not None:
            current_year = AcademicYear.objects.filter(is_current=True).first()
            filter_kwargs = {
                "class_assignments__is_class_teacher": value,
                "class_assignments__academic_year": current_year,
            }
            return queryset.filter(**filter_kwargs).distinct()
        return queryset

    def filter_recently_hired(self, queryset, name, value):
        """Filter teachers hired in the last N days."""
        if value:
            cutoff_date = timezone.now().date() - timedelta(days=value)
            return queryset.filter(joining_date__gte=cutoff_date)
        return queryset

    def filter_tenure_min(self, queryset, name, value):
        """Filter by minimum tenure in years."""
        if value is not None:
            cutoff_date = timezone.now().date() - timedelta(days=value * 365)
            return queryset.filter(joining_date__lte=cutoff_date)
        return queryset

    def filter_tenure_max(self, queryset, name, value):
        """Filter by maximum tenure in years."""
        if value is not None:
            cutoff_date = timezone.now().date() - timedelta(days=value * 365)
            return queryset.filter(joining_date__gte=cutoff_date)
        return queryset


class TeacherEvaluationFilter(django_filters.FilterSet):
    """Advanced filtering for TeacherEvaluation model."""

    # Teacher filtering
    teacher = django_filters.ModelChoiceFilter(
        queryset=Teacher.objects.all(), label="Teacher"
    )

    # Date range filtering
    evaluation_date_after = django_filters.DateFilter(
        field_name="evaluation_date", lookup_expr="gte", label="Evaluated After"
    )
    evaluation_date_before = django_filters.DateFilter(
        field_name="evaluation_date", lookup_expr="lte", label="Evaluated Before"
    )

    # Score range filtering
    score_min = django_filters.NumberFilter(
        field_name="score", lookup_expr="gte", label="Minimum Score"
    )
    score_max = django_filters.NumberFilter(
        field_name="score", lookup_expr="lte", label="Maximum Score"
    )

    # Performance level filtering
    performance_level = django_filters.ChoiceFilter(
        method="filter_performance_level",
        choices=[
            ("excellent", "Excellent (90%+)"),
            ("good", "Good (80-89%)"),
            ("satisfactory", "Satisfactory (70-79%)"),
            ("needs_improvement", "Needs Improvement (60-69%)"),
            ("poor", "Poor (<60%)"),
        ],
        label="Performance Level",
    )

    # Status filtering
    status = django_filters.ChoiceFilter(
        choices=TeacherEvaluation._meta.get_field("status").choices,
        label="Evaluation Status",
    )

    # Followup filtering
    requires_followup = django_filters.BooleanFilter(
        method="filter_requires_followup", label="Requires Followup"
    )

    followup_overdue = django_filters.BooleanFilter(
        method="filter_followup_overdue", label="Followup Overdue"
    )

    # Department filtering
    department = django_filters.ModelChoiceFilter(
        queryset=Department.objects.all(),
        method="filter_department",
        label="Department",
    )

    # Academic year filtering
    academic_year = django_filters.NumberFilter(
        method="filter_academic_year", label="Academic Year"
    )

    # Recent evaluations
    recent_days = django_filters.NumberFilter(
        method="filter_recent_days", label="Evaluations in last N days"
    )

    class Meta:
        model = TeacherEvaluation
        fields = {
            "evaluator": ["exact"],
            "remarks": ["icontains"],
            "followup_actions": ["icontains"],
        }

    def filter_performance_level(self, queryset, name, value):
        """Filter by performance level category."""
        score_ranges = {
            "excellent": (90, 100),
            "good": (80, 89),
            "satisfactory": (70, 79),
            "needs_improvement": (60, 69),
            "poor": (0, 59),
        }

        if value in score_ranges:
            min_score, max_score = score_ranges[value]
            return queryset.filter(score__gte=min_score, score__lte=max_score)

        return queryset

    def filter_requires_followup(self, queryset, name, value):
        """Filter evaluations that require followup."""
        if value is True:
            return queryset.filter(score__lt=70, status__in=["submitted", "reviewed"])
        elif value is False:
            return queryset.exclude(score__lt=70, status__in=["submitted", "reviewed"])
        return queryset

    def filter_followup_overdue(self, queryset, name, value):
        """Filter evaluations with overdue followup."""
        if value is True:
            return queryset.filter(
                followup_date__lt=timezone.now().date(),
                status__in=["submitted", "reviewed"],
            )
        elif value is False:
            return queryset.exclude(
                followup_date__lt=timezone.now().date(),
                status__in=["submitted", "reviewed"],
            )
        return queryset

    def filter_department(self, queryset, name, value):
        """Filter by teacher's department."""
        if value:
            return queryset.filter(teacher__department=value)
        return queryset

    def filter_academic_year(self, queryset, name, value):
        """Filter by academic year."""
        if value:
            return queryset.filter(evaluation_date__year=value)
        return queryset

    def filter_recent_days(self, queryset, name, value):
        """Filter evaluations from the last N days."""
        if value:
            cutoff_date = timezone.now().date() - timedelta(days=value)
            return queryset.filter(evaluation_date__gte=cutoff_date)
        return queryset


class TeacherClassAssignmentFilter(django_filters.FilterSet):
    """Advanced filtering for TeacherClassAssignment model."""

    # Teacher filtering
    teacher = django_filters.ModelChoiceFilter(
        queryset=Teacher.objects.all(), label="Teacher"
    )

    # Subject filtering
    subject = django_filters.ModelChoiceFilter(
        queryset=Subject.objects.all(), label="Subject"
    )

    # Academic year filtering
    academic_year = django_filters.ModelChoiceFilter(
        queryset=AcademicYear.objects.all(), label="Academic Year"
    )

    # Class teacher filtering
    is_class_teacher = django_filters.BooleanFilter(label="Is Class Teacher")

    # Department filtering
    department = django_filters.ModelChoiceFilter(
        queryset=Department.objects.all(),
        method="filter_department",
        label="Department",
    )

    # Grade level filtering
    grade_level = django_filters.CharFilter(
        method="filter_grade_level", label="Grade Level"
    )

    # Teacher experience filtering
    teacher_experience_min = django_filters.NumberFilter(
        method="filter_teacher_experience_min", label="Teacher Min Experience"
    )
    teacher_experience_max = django_filters.NumberFilter(
        method="filter_teacher_experience_max", label="Teacher Max Experience"
    )

    # Workload filtering
    teacher_workload = django_filters.ChoiceFilter(
        method="filter_teacher_workload",
        choices=[
            ("light", "Light (1-3 classes)"),
            ("moderate", "Moderate (4-6 classes)"),
            ("heavy", "Heavy (7+ classes)"),
        ],
        label="Teacher Workload",
    )

    # Current assignments only
    current_only = django_filters.BooleanFilter(
        method="filter_current_only", label="Current Academic Year Only"
    )

    class Meta:
        model = TeacherClassAssignment
        fields = {
            "notes": ["icontains"],
        }

    def filter_department(self, queryset, name, value):
        """Filter by teacher's department."""
        if value:
            return queryset.filter(teacher__department=value)
        return queryset

    def filter_grade_level(self, queryset, name, value):
        """Filter by grade level."""
        if value:
            return queryset.filter(class_instance__grade__name__icontains=value)
        return queryset

    def filter_teacher_experience_min(self, queryset, name, value):
        """Filter by minimum teacher experience."""
        if value is not None:
            return queryset.filter(teacher__experience_years__gte=value)
        return queryset

    def filter_teacher_experience_max(self, queryset, name, value):
        """Filter by maximum teacher experience."""
        if value is not None:
            return queryset.filter(teacher__experience_years__lte=value)
        return queryset

    def filter_teacher_workload(self, queryset, name, value):
        """Filter by teacher workload level."""
        if not value:
            return queryset

        # Count assignments per teacher
        teacher_counts = queryset.values("teacher").annotate(
            assignment_count=Count("id")
        )

        if value == "light":
            teacher_ids = [
                tc["teacher"] for tc in teacher_counts if tc["assignment_count"] <= 3
            ]
        elif value == "moderate":
            teacher_ids = [
                tc["teacher"]
                for tc in teacher_counts
                if 4 <= tc["assignment_count"] <= 6
            ]
        elif value == "heavy":
            teacher_ids = [
                tc["teacher"] for tc in teacher_counts if tc["assignment_count"] >= 7
            ]
        else:
            teacher_ids = []

        return queryset.filter(teacher_id__in=teacher_ids)

    def filter_current_only(self, queryset, name, value):
        """Filter to show only current academic year assignments."""
        if value is True:
            current_year = AcademicYear.objects.filter(is_current=True).first()
            if current_year:
                return queryset.filter(academic_year=current_year)
        return queryset


class TeacherAnalyticsFilter(django_filters.FilterSet):
    """Filtering for analytics queries."""

    # Time period filtering
    start_date = django_filters.DateFilter(
        method="filter_start_date", label="Start Date"
    )
    end_date = django_filters.DateFilter(method="filter_end_date", label="End Date")

    # Department filtering
    department = django_filters.ModelMultipleChoiceFilter(
        queryset=Department.objects.all(),
        method="filter_departments",
        label="Departments",
    )

    # Performance level filtering
    performance_levels = django_filters.MultipleChoiceFilter(
        choices=[
            ("excellent", "Excellent"),
            ("good", "Good"),
            ("satisfactory", "Satisfactory"),
            ("needs_improvement", "Needs Improvement"),
            ("poor", "Poor"),
        ],
        method="filter_performance_levels",
        label="Performance Levels",
    )

    # Contract type filtering
    contract_types = django_filters.MultipleChoiceFilter(
        choices=Teacher.CONTRACT_TYPE_CHOICES,
        method="filter_contract_types",
        label="Contract Types",
    )

    # Experience range
    experience_range = django_filters.ChoiceFilter(
        method="filter_experience_range",
        choices=[
            ("0-2", "0-2 years"),
            ("3-5", "3-5 years"),
            ("6-10", "6-10 years"),
            ("11-15", "11-15 years"),
            ("16+", "16+ years"),
        ],
        label="Experience Range",
    )

    # Metrics to include
    include_trends = django_filters.BooleanFilter(
        method="filter_include_trends", label="Include Trends"
    )
    include_comparisons = django_filters.BooleanFilter(
        method="filter_include_comparisons", label="Include Comparisons"
    )

    def filter_start_date(self, queryset, name, value):
        """Filter by start date for analytics."""
        # This would be used in analytics service methods
        self.form.cleaned_data["start_date"] = value
        return queryset

    def filter_end_date(self, queryset, name, value):
        """Filter by end date for analytics."""
        self.form.cleaned_data["end_date"] = value
        return queryset

    def filter_departments(self, queryset, name, value):
        """Filter by multiple departments."""
        if value:
            return queryset.filter(teacher__department__in=value)
        return queryset

    def filter_performance_levels(self, queryset, name, value):
        """Filter by multiple performance levels."""
        if not value:
            return queryset

        score_conditions = []
        for level in value:
            if level == "excellent":
                score_conditions.append(Q(score__gte=90))
            elif level == "good":
                score_conditions.append(Q(score__gte=80, score__lt=90))
            elif level == "satisfactory":
                score_conditions.append(Q(score__gte=70, score__lt=80))
            elif level == "needs_improvement":
                score_conditions.append(Q(score__gte=60, score__lt=70))
            elif level == "poor":
                score_conditions.append(Q(score__lt=60))

        if score_conditions:
            combined_condition = score_conditions[0]
            for condition in score_conditions[1:]:
                combined_condition |= condition
            return queryset.filter(combined_condition)

        return queryset

    def filter_contract_types(self, queryset, name, value):
        """Filter by multiple contract types."""
        if value:
            return queryset.filter(teacher__contract_type__in=value)
        return queryset

    def filter_experience_range(self, queryset, name, value):
        """Filter by experience range."""
        if not value:
            return queryset

        range_mapping = {
            "0-2": (0, 2),
            "3-5": (3, 5),
            "6-10": (6, 10),
            "11-15": (11, 15),
            "16+": (16, 50),
        }

        if value in range_mapping:
            min_exp, max_exp = range_mapping[value]
            return queryset.filter(
                teacher__experience_years__gte=min_exp,
                teacher__experience_years__lte=max_exp,
            )

        return queryset

    def filter_include_trends(self, queryset, name, value):
        """Mark to include trend analysis."""
        self.form.cleaned_data["include_trends"] = value
        return queryset

    def filter_include_comparisons(self, queryset, name, value):
        """Mark to include comparison analysis."""
        self.form.cleaned_data["include_comparisons"] = value
        return queryset
