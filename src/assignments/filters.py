from datetime import datetime, timedelta

import django_filters
from django import forms
from django.db import models
from django.db.models import Q
from django.utils import timezone

from .models import (
    Assignment,
    AssignmentComment,
    AssignmentRubric,
    AssignmentSubmission,
)


class AssignmentFilter(django_filters.FilterSet):
    """
    Advanced filtering for assignments
    """

    # Basic filters
    title = django_filters.CharFilter(
        field_name="title", lookup_expr="icontains", label="Title contains"
    )

    status = django_filters.MultipleChoiceFilter(
        choices=Assignment.STATUS_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        label="Status",
    )

    difficulty_level = django_filters.MultipleChoiceFilter(
        choices=Assignment.DIFFICULTY_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        label="Difficulty",
    )

    submission_type = django_filters.MultipleChoiceFilter(
        choices=Assignment.SUBMISSION_TYPE_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        label="Submission Type",
    )

    # Foreign key filters
    teacher = django_filters.ModelChoiceFilter(
        queryset=None,  # Will be set in __init__
        empty_label="All Teachers",
        label="Teacher",
    )

    subject = django_filters.ModelChoiceFilter(
        queryset=None,  # Will be set in __init__
        empty_label="All Subjects",
        label="Subject",
    )

    class_id = django_filters.ModelChoiceFilter(
        queryset=None,  # Will be set in __init__
        empty_label="All Classes",
        label="Class",
    )

    term = django_filters.ModelChoiceFilter(
        queryset=None, empty_label="All Terms", label="Term"  # Will be set in __init__
    )

    # Date filters
    created_after = django_filters.DateFilter(
        field_name="created_at",
        lookup_expr="gte",
        widget=forms.DateInput(attrs={"type": "date"}),
        label="Created after",
    )

    created_before = django_filters.DateFilter(
        field_name="created_at",
        lookup_expr="lte",
        widget=forms.DateInput(attrs={"type": "date"}),
        label="Created before",
    )

    due_after = django_filters.DateTimeFilter(
        field_name="due_date",
        lookup_expr="gte",
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}),
        label="Due after",
    )

    due_before = django_filters.DateTimeFilter(
        field_name="due_date",
        lookup_expr="lte",
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}),
        label="Due before",
    )

    # Numeric filters
    total_marks = django_filters.RangeFilter(
        field_name="total_marks", label="Total marks range"
    )

    total_marks_min = django_filters.NumberFilter(
        field_name="total_marks", lookup_expr="gte", label="Minimum marks"
    )

    total_marks_max = django_filters.NumberFilter(
        field_name="total_marks", lookup_expr="lte", label="Maximum marks"
    )

    # Boolean filters
    allow_late_submission = django_filters.BooleanFilter(label="Allows late submission")

    auto_grade = django_filters.BooleanFilter(label="Auto grading enabled")

    peer_review = django_filters.BooleanFilter(label="Peer review enabled")

    # Custom filters
    is_overdue = django_filters.BooleanFilter(
        method="filter_overdue", label="Is overdue"
    )

    due_soon = django_filters.NumberFilter(
        method="filter_due_soon", label="Due within days"
    )

    has_submissions = django_filters.BooleanFilter(
        method="filter_has_submissions", label="Has submissions"
    )

    completion_rate = django_filters.RangeFilter(
        method="filter_completion_rate", label="Completion rate %"
    )

    section = django_filters.CharFilter(method="filter_section", label="Section")

    grade = django_filters.CharFilter(method="filter_grade", label="Grade")

    # Search filter
    search = django_filters.CharFilter(method="filter_search", label="Search")

    class Meta:
        model = Assignment
        fields = []  # We define fields explicitly above

    def __init__(self, *args, **kwargs):
        # Get user context for filtering querysets
        request = kwargs.pop("request", None)
        super().__init__(*args, **kwargs)

        # Set up dynamic querysets based on user permissions
        if request and hasattr(request, "user"):
            user = request.user

            # Teachers queryset
            if hasattr(user, "teacher"):
                from teachers.models import Teacher

                self.filters["teacher"].queryset = Teacher.objects.filter(
                    id=user.teacher.id
                )
            else:
                from teachers.models import Teacher

                self.filters["teacher"].queryset = Teacher.objects.all()

            # Subjects queryset
            from subjects.models import Subject

            if hasattr(user, "teacher"):
                # Teacher sees only their subjects
                self.filters["subject"].queryset = user.teacher.subjects.all()
            else:
                self.filters["subject"].queryset = Subject.objects.all()

            # Classes queryset
            from academics.models import Class

            if hasattr(user, "teacher"):
                # Teacher sees only their assigned classes
                self.filters["class_id"].queryset = Class.objects.filter(
                    teacherassignment__teacher=user.teacher
                ).distinct()
            elif hasattr(user, "student"):
                # Student sees only their class
                self.filters["class_id"].queryset = Class.objects.filter(
                    id=user.student.current_class_id.id
                )
            else:
                self.filters["class_id"].queryset = Class.objects.all()

            # Terms queryset
            from academics.models import Term

            self.filters["term"].queryset = Term.objects.all().order_by("-start_date")

        else:
            # Default querysets for non-authenticated contexts
            from academics.models import Class, Term
            from subjects.models import Subject
            from teachers.models import Teacher

            self.filters["teacher"].queryset = Teacher.objects.all()
            self.filters["subject"].queryset = Subject.objects.all()
            self.filters["class_id"].queryset = Class.objects.all()
            self.filters["term"].queryset = Term.objects.all()

    def filter_overdue(self, queryset, name, value):
        """Filter assignments that are overdue"""
        if value:
            return queryset.filter(status="published", due_date__lt=timezone.now())
        else:
            return queryset.filter(
                Q(status__ne="published") | Q(due_date__gte=timezone.now())
            )

    def filter_due_soon(self, queryset, name, value):
        """Filter assignments due within specified days"""
        if value:
            target_date = timezone.now() + timedelta(days=value)
            return queryset.filter(
                status="published",
                due_date__lte=target_date,
                due_date__gte=timezone.now(),
            )
        return queryset

    def filter_has_submissions(self, queryset, name, value):
        """Filter assignments that have submissions"""
        if value:
            return queryset.filter(submissions__isnull=False).distinct()
        else:
            return queryset.filter(submissions__isnull=True)

    def filter_completion_rate(self, queryset, name, value):
        """Filter by completion rate range"""
        if value and value.start is not None and value.stop is not None:
            # This would require a complex annotation, simplified for now
            return queryset
        return queryset

    def filter_section(self, queryset, name, value):
        """Filter by section name"""
        if value:
            return queryset.filter(class_id__grade__section__name__icontains=value)
        return queryset

    def filter_grade(self, queryset, name, value):
        """Filter by grade name"""
        if value:
            return queryset.filter(class_id__grade__name__icontains=value)
        return queryset

    def filter_search(self, queryset, name, value):
        """Search across multiple fields"""
        if value:
            return queryset.filter(
                Q(title__icontains=value)
                | Q(description__icontains=value)
                | Q(instructions__icontains=value)
                | Q(subject__name__icontains=value)
                | Q(teacher__user__first_name__icontains=value)
                | Q(teacher__user__last_name__icontains=value)
                | Q(class_id__name__icontains=value)
            )
        return queryset


class AssignmentSubmissionFilter(django_filters.FilterSet):
    """
    Advanced filtering for assignment submissions
    """

    # Basic filters
    status = django_filters.MultipleChoiceFilter(
        choices=AssignmentSubmission.STATUS_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        label="Status",
    )

    submission_method = django_filters.MultipleChoiceFilter(
        choices=AssignmentSubmission.SUBMISSION_METHOD_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        label="Submission Method",
    )

    # Foreign key filters
    assignment = django_filters.ModelChoiceFilter(
        queryset=None,  # Will be set in __init__
        empty_label="All Assignments",
        label="Assignment",
    )

    student = django_filters.ModelChoiceFilter(
        queryset=None,  # Will be set in __init__
        empty_label="All Students",
        label="Student",
    )

    graded_by = django_filters.ModelChoiceFilter(
        queryset=None,  # Will be set in __init__
        empty_label="All Teachers",
        label="Graded by",
    )

    # Date filters
    submitted_after = django_filters.DateTimeFilter(
        field_name="submission_date",
        lookup_expr="gte",
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}),
        label="Submitted after",
    )

    submitted_before = django_filters.DateTimeFilter(
        field_name="submission_date",
        lookup_expr="lte",
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}),
        label="Submitted before",
    )

    graded_after = django_filters.DateTimeFilter(
        field_name="graded_at",
        lookup_expr="gte",
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}),
        label="Graded after",
    )

    graded_before = django_filters.DateTimeFilter(
        field_name="graded_at",
        lookup_expr="lte",
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}),
        label="Graded before",
    )

    # Numeric filters
    marks_obtained = django_filters.RangeFilter(
        field_name="marks_obtained", label="Marks range"
    )

    marks_min = django_filters.NumberFilter(
        field_name="marks_obtained", lookup_expr="gte", label="Minimum marks"
    )

    marks_max = django_filters.NumberFilter(
        field_name="marks_obtained", lookup_expr="lte", label="Maximum marks"
    )

    percentage = django_filters.RangeFilter(
        field_name="percentage", label="Percentage range"
    )

    percentage_min = django_filters.NumberFilter(
        field_name="percentage", lookup_expr="gte", label="Minimum percentage"
    )

    percentage_max = django_filters.NumberFilter(
        field_name="percentage", lookup_expr="lte", label="Maximum percentage"
    )

    plagiarism_score = django_filters.RangeFilter(
        field_name="plagiarism_score", label="Plagiarism score range"
    )

    # Boolean filters
    is_late = django_filters.BooleanFilter(label="Is late submission")

    late_penalty_applied = django_filters.BooleanFilter(label="Late penalty applied")

    plagiarism_checked = django_filters.BooleanFilter(label="Plagiarism checked")

    # Custom filters
    grade = django_filters.CharFilter(method="filter_grade", label="Grade")

    is_passed = django_filters.BooleanFilter(method="filter_passed", label="Has passed")

    subject = django_filters.CharFilter(method="filter_subject", label="Subject")

    class_name = django_filters.CharFilter(method="filter_class", label="Class")

    high_plagiarism = django_filters.BooleanFilter(
        method="filter_high_plagiarism", label="High plagiarism score (>30%)"
    )

    needs_grading = django_filters.BooleanFilter(
        method="filter_needs_grading", label="Needs grading"
    )

    # Search filter
    search = django_filters.CharFilter(method="filter_search", label="Search")

    class Meta:
        model = AssignmentSubmission
        fields = []

    def __init__(self, *args, **kwargs):
        request = kwargs.pop("request", None)
        super().__init__(*args, **kwargs)

        if request and hasattr(request, "user"):
            user = request.user

            # Assignments queryset
            if hasattr(user, "teacher"):
                self.filters["assignment"].queryset = Assignment.objects.filter(
                    teacher=user.teacher
                )
            elif hasattr(user, "student"):
                self.filters["assignment"].queryset = Assignment.objects.filter(
                    class_id=user.student.current_class_id
                )
            else:
                self.filters["assignment"].queryset = Assignment.objects.all()

            # Students queryset
            from students.models import Student

            if hasattr(user, "teacher"):
                # Teacher sees students from their classes
                teacher_classes = user.teacher.teacherassignment_set.values_list(
                    "class_id", flat=True
                )
                self.filters["student"].queryset = Student.objects.filter(
                    current_class_id__in=teacher_classes
                )
            else:
                self.filters["student"].queryset = Student.objects.all()

            # Teachers queryset
            from teachers.models import Teacher

            self.filters["graded_by"].queryset = Teacher.objects.all()

        else:
            # Default querysets
            self.filters["assignment"].queryset = Assignment.objects.all()
            from students.models import Student
            from teachers.models import Teacher

            self.filters["student"].queryset = Student.objects.all()
            self.filters["graded_by"].queryset = Teacher.objects.all()

    def filter_grade(self, queryset, name, value):
        """Filter by calculated grade"""
        if value:
            return queryset.filter(grade__icontains=value)
        return queryset

    def filter_passed(self, queryset, name, value):
        """Filter submissions that passed"""
        if value:
            return queryset.filter(
                marks_obtained__gte=models.F("assignment__passing_marks")
            )
        else:
            return queryset.filter(
                marks_obtained__lt=models.F("assignment__passing_marks")
            )

    def filter_subject(self, queryset, name, value):
        """Filter by subject name"""
        if value:
            return queryset.filter(assignment__subject__name__icontains=value)
        return queryset

    def filter_class(self, queryset, name, value):
        """Filter by class name"""
        if value:
            return queryset.filter(assignment__class_id__name__icontains=value)
        return queryset

    def filter_high_plagiarism(self, queryset, name, value):
        """Filter submissions with high plagiarism scores"""
        if value:
            return queryset.filter(plagiarism_score__gt=30)
        return queryset

    def filter_needs_grading(self, queryset, name, value):
        """Filter submissions that need grading"""
        if value:
            return queryset.filter(status="submitted")
        return queryset

    def filter_search(self, queryset, name, value):
        """Search across multiple fields"""
        if value:
            return queryset.filter(
                Q(assignment__title__icontains=value)
                | Q(student__user__first_name__icontains=value)
                | Q(student__user__last_name__icontains=value)
                | Q(student__admission_number__icontains=value)
                | Q(content__icontains=value)
                | Q(teacher_remarks__icontains=value)
            )
        return queryset


class AssignmentRubricFilter(django_filters.FilterSet):
    """
    Filtering for assignment rubrics
    """

    assignment = django_filters.ModelChoiceFilter(
        queryset=Assignment.objects.all(),
        empty_label="All Assignments",
        label="Assignment",
    )

    criteria_name = django_filters.CharFilter(
        field_name="criteria_name",
        lookup_expr="icontains",
        label="Criteria name contains",
    )

    max_points = django_filters.RangeFilter(
        field_name="max_points", label="Max points range"
    )

    weight_percentage = django_filters.RangeFilter(
        field_name="weight_percentage", label="Weight percentage range"
    )

    # Search filter
    search = django_filters.CharFilter(method="filter_search", label="Search")

    class Meta:
        model = AssignmentRubric
        fields = []

    def filter_search(self, queryset, name, value):
        """Search across multiple fields"""
        if value:
            return queryset.filter(
                Q(criteria_name__icontains=value)
                | Q(description__icontains=value)
                | Q(assignment__title__icontains=value)
            )
        return queryset


class AssignmentCommentFilter(django_filters.FilterSet):
    """
    Filtering for assignment comments
    """

    assignment = django_filters.ModelChoiceFilter(
        queryset=Assignment.objects.all(),
        empty_label="All Assignments",
        label="Assignment",
    )

    user = django_filters.ModelChoiceFilter(
        queryset=None, empty_label="All Users", label="User"  # Will be set in __init__
    )

    is_private = django_filters.BooleanFilter(label="Private comments")

    has_replies = django_filters.BooleanFilter(
        method="filter_has_replies", label="Has replies"
    )

    created_after = django_filters.DateTimeFilter(
        field_name="created_at",
        lookup_expr="gte",
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}),
        label="Created after",
    )

    created_before = django_filters.DateTimeFilter(
        field_name="created_at",
        lookup_expr="lte",
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}),
        label="Created before",
    )

    # Search filter
    search = django_filters.CharFilter(method="filter_search", label="Search")

    class Meta:
        model = AssignmentComment
        fields = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Set up users queryset
        from django.contrib.auth import get_user_model

        User = get_user_model()
        self.filters["user"].queryset = User.objects.filter(
            Q(teacher__isnull=False) | Q(student__isnull=False)
        )

    def filter_has_replies(self, queryset, name, value):
        """Filter comments that have replies"""
        if value:
            return queryset.filter(replies__isnull=False).distinct()
        else:
            return queryset.filter(replies__isnull=True)

    def filter_search(self, queryset, name, value):
        """Search across multiple fields"""
        if value:
            return queryset.filter(
                Q(content__icontains=value)
                | Q(assignment__title__icontains=value)
                | Q(user__first_name__icontains=value)
                | Q(user__last_name__icontains=value)
            )
        return queryset


# Additional utility filters for common use cases
class TeacherAssignmentFilter(AssignmentFilter):
    """
    Specialized filter for teacher assignment views
    """

    class Meta:
        model = Assignment
        fields = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Remove teacher filter since it's implied
        if "teacher" in self.filters:
            del self.filters["teacher"]


class StudentAssignmentFilter(django_filters.FilterSet):
    """
    Simplified filter for student assignment views
    """

    status = django_filters.ChoiceFilter(
        choices=[("published", "Active"), ("closed", "Closed")],
        empty_label="All Assignments",
    )

    subject = django_filters.ModelChoiceFilter(
        queryset=None, empty_label="All Subjects"  # Will be set in __init__
    )

    due_soon = django_filters.NumberFilter(
        method="filter_due_soon", label="Due within days"
    )

    is_submitted = django_filters.BooleanFilter(
        method="filter_submitted", label="Submitted"
    )

    search = django_filters.CharFilter(method="filter_search", label="Search")

    class Meta:
        model = Assignment
        fields = []

    def __init__(self, *args, **kwargs):
        request = kwargs.pop("request", None)
        super().__init__(*args, **kwargs)

        if request and hasattr(request.user, "student"):
            # Get subjects for student's class
            from subjects.models import Subject

            class_subjects = Subject.objects.filter(
                assignments__class_id=request.user.student.current_class_id
            ).distinct()
            self.filters["subject"].queryset = class_subjects

    def filter_due_soon(self, queryset, name, value):
        """Filter assignments due within specified days"""
        if value:
            target_date = timezone.now() + timedelta(days=value)
            return queryset.filter(
                due_date__lte=target_date, due_date__gte=timezone.now()
            )
        return queryset

    def filter_submitted(self, queryset, name, value):
        """Filter based on submission status for current student"""
        request = getattr(self, "request", None)
        if request and hasattr(request.user, "student"):
            student = request.user.student
            if value:
                return queryset.filter(submissions__student=student)
            else:
                return queryset.exclude(submissions__student=student)
        return queryset

    def filter_search(self, queryset, name, value):
        """Search assignments"""
        if value:
            return queryset.filter(
                Q(title__icontains=value)
                | Q(description__icontains=value)
                | Q(subject__name__icontains=value)
            )
        return queryset
