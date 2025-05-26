"""
School Management System - Exam API Filters
File: src/exams/filters.py
"""

import django_filters
from django.db.models import Q
from django_filters import rest_framework as filters

from .models import (
    Exam,
    ExamType,
    ExamSchedule,
    StudentExamResult,
    ReportCard,
    ExamQuestion,
    OnlineExam,
    StudentOnlineExamAttempt,
)
from academics.models import AcademicYear, Term, Grade, Class
from subjects.models import Subject
from students.models import Student


class ExamFilter(filters.FilterSet):
    """Filter for Exam model"""

    name = filters.CharFilter(lookup_expr="icontains")
    academic_year = filters.ModelChoiceFilter(queryset=AcademicYear.objects.all())
    term = filters.ModelChoiceFilter(queryset=Term.objects.all())
    exam_type = filters.ModelChoiceFilter(queryset=ExamType.objects.all())
    status = filters.ChoiceFilter(choices=Exam._meta.get_field("status").choices)
    is_published = filters.BooleanFilter()
    start_date_from = filters.DateFilter(field_name="start_date", lookup_expr="gte")
    start_date_to = filters.DateFilter(field_name="start_date", lookup_expr="lte")
    end_date_from = filters.DateFilter(field_name="end_date", lookup_expr="gte")
    end_date_to = filters.DateFilter(field_name="end_date", lookup_expr="lte")
    created_by = filters.ModelChoiceFilter(queryset=None)
    search = filters.CharFilter(method="filter_search")

    class Meta:
        model = Exam
        fields = [
            "name",
            "academic_year",
            "term",
            "exam_type",
            "status",
            "is_published",
            "created_by",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from django.contrib.auth import get_user_model

        User = get_user_model()
        self.filters["created_by"].queryset = User.objects.filter(
            role__in=["ADMIN", "PRINCIPAL", "TEACHER"]
        )

    def filter_search(self, queryset, name, value):
        return queryset.filter(
            Q(name__icontains=value)
            | Q(description__icontains=value)
            | Q(instructions__icontains=value)
        )


class ExamScheduleFilter(filters.FilterSet):
    """Filter for ExamSchedule model"""

    exam = filters.ModelChoiceFilter(queryset=Exam.objects.all())
    class_obj = filters.ModelChoiceFilter(queryset=Class.objects.all())
    subject = filters.ModelChoiceFilter(queryset=Subject.objects.all())
    supervisor = filters.ModelChoiceFilter(queryset=None)
    date_from = filters.DateFilter(field_name="date", lookup_expr="gte")
    date_to = filters.DateFilter(field_name="date", lookup_expr="lte")
    is_completed = filters.BooleanFilter()
    is_active = filters.BooleanFilter()
    academic_year = filters.ModelChoiceFilter(
        field_name="exam__academic_year", queryset=AcademicYear.objects.all()
    )
    term = filters.ModelChoiceFilter(
        field_name="exam__term", queryset=Term.objects.all()
    )
    grade = filters.ModelChoiceFilter(
        field_name="class_obj__grade", queryset=Grade.objects.all()
    )

    class Meta:
        model = ExamSchedule
        fields = [
            "exam",
            "class_obj",
            "subject",
            "supervisor",
            "is_completed",
            "is_active",
            "date",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from teachers.models import Teacher

        self.filters["supervisor"].queryset = Teacher.objects.filter(status="ACTIVE")


class StudentExamResultFilter(filters.FilterSet):
    """Filter for StudentExamResult model"""

    student = filters.ModelChoiceFilter(queryset=Student.objects.all())
    exam_schedule = filters.ModelChoiceFilter(queryset=ExamSchedule.objects.all())
    term = filters.ModelChoiceFilter(queryset=Term.objects.all())
    grade = filters.ChoiceFilter(
        choices=StudentExamResult._meta.get_field("grade").choices
    )
    is_pass = filters.BooleanFilter()
    is_absent = filters.BooleanFilter()
    is_exempted = filters.BooleanFilter()
    percentage_min = filters.NumberFilter(field_name="percentage", lookup_expr="gte")
    percentage_max = filters.NumberFilter(field_name="percentage", lookup_expr="lte")
    marks_min = filters.NumberFilter(field_name="marks_obtained", lookup_expr="gte")
    marks_max = filters.NumberFilter(field_name="marks_obtained", lookup_expr="lte")
    class_rank_min = filters.NumberFilter(field_name="class_rank", lookup_expr="gte")
    class_rank_max = filters.NumberFilter(field_name="class_rank", lookup_expr="lte")

    # Filter by class, subject, academic year
    class_obj = filters.ModelChoiceFilter(
        field_name="exam_schedule__class_obj", queryset=Class.objects.all()
    )
    subject = filters.ModelChoiceFilter(
        field_name="exam_schedule__subject", queryset=Subject.objects.all()
    )
    academic_year = filters.ModelChoiceFilter(
        field_name="exam_schedule__exam__academic_year",
        queryset=AcademicYear.objects.all(),
    )

    entry_date_from = filters.DateTimeFilter(field_name="entry_date", lookup_expr="gte")
    entry_date_to = filters.DateTimeFilter(field_name="entry_date", lookup_expr="lte")

    class Meta:
        model = StudentExamResult
        fields = [
            "student",
            "exam_schedule",
            "term",
            "grade",
            "is_pass",
            "is_absent",
            "is_exempted",
        ]


class ReportCardFilter(filters.FilterSet):
    """Filter for ReportCard model"""

    student = filters.ModelChoiceFilter(queryset=Student.objects.all())
    class_obj = filters.ModelChoiceFilter(queryset=Class.objects.all())
    academic_year = filters.ModelChoiceFilter(queryset=AcademicYear.objects.all())
    term = filters.ModelChoiceFilter(queryset=Term.objects.all())
    status = filters.ChoiceFilter(choices=ReportCard._meta.get_field("status").choices)
    grade = filters.ChoiceFilter(choices=ReportCard._meta.get_field("grade").choices)
    percentage_min = filters.NumberFilter(field_name="percentage", lookup_expr="gte")
    percentage_max = filters.NumberFilter(field_name="percentage", lookup_expr="lte")
    class_rank_min = filters.NumberFilter(field_name="class_rank", lookup_expr="gte")
    class_rank_max = filters.NumberFilter(field_name="class_rank", lookup_expr="lte")

    # Filter by grade level
    grade_level = filters.ModelChoiceFilter(
        field_name="class_obj__grade", queryset=Grade.objects.all()
    )

    generation_date_from = filters.DateTimeFilter(
        field_name="generation_date", lookup_expr="gte"
    )
    generation_date_to = filters.DateTimeFilter(
        field_name="generation_date", lookup_expr="lte"
    )

    class Meta:
        model = ReportCard
        fields = ["student", "class_obj", "academic_year", "term", "status", "grade"]


class ExamQuestionFilter(filters.FilterSet):
    """Filter for ExamQuestion model"""

    subject = filters.ModelChoiceFilter(queryset=Subject.objects.all())
    grade = filters.ModelChoiceFilter(queryset=Grade.objects.all())
    question_type = filters.ChoiceFilter(choices=ExamQuestion.QUESTION_TYPES)
    difficulty_level = filters.ChoiceFilter(choices=ExamQuestion.DIFFICULTY_LEVELS)
    marks = filters.NumberFilter()
    marks_min = filters.NumberFilter(field_name="marks", lookup_expr="gte")
    marks_max = filters.NumberFilter(field_name="marks", lookup_expr="lte")
    is_active = filters.BooleanFilter()
    topic = filters.CharFilter(lookup_expr="icontains")
    learning_objective = filters.CharFilter(lookup_expr="icontains")
    created_by = filters.ModelChoiceFilter(queryset=None)
    usage_count_min = filters.NumberFilter(field_name="usage_count", lookup_expr="gte")
    usage_count_max = filters.NumberFilter(field_name="usage_count", lookup_expr="lte")
    search = filters.CharFilter(method="filter_search")

    class Meta:
        model = ExamQuestion
        fields = [
            "subject",
            "grade",
            "question_type",
            "difficulty_level",
            "marks",
            "is_active",
            "topic",
            "created_by",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from django.contrib.auth import get_user_model

        User = get_user_model()
        self.filters["created_by"].queryset = User.objects.filter(
            role__in=["ADMIN", "TEACHER", "PRINCIPAL"]
        )

    def filter_search(self, queryset, name, value):
        return queryset.filter(
            Q(question_text__icontains=value)
            | Q(topic__icontains=value)
            | Q(learning_objective__icontains=value)
            | Q(explanation__icontains=value)
        )


class OnlineExamFilter(filters.FilterSet):
    """Filter for OnlineExam model"""

    exam_schedule = filters.ModelChoiceFilter(queryset=ExamSchedule.objects.all())
    enable_proctoring = filters.BooleanFilter()
    shuffle_questions = filters.BooleanFilter()
    show_results_immediately = filters.BooleanFilter()
    time_limit_min = filters.NumberFilter(
        field_name="time_limit_minutes", lookup_expr="gte"
    )
    time_limit_max = filters.NumberFilter(
        field_name="time_limit_minutes", lookup_expr="lte"
    )
    max_attempts = filters.NumberFilter()

    # Filter by exam details
    academic_year = filters.ModelChoiceFilter(
        field_name="exam_schedule__exam__academic_year",
        queryset=AcademicYear.objects.all(),
    )
    term = filters.ModelChoiceFilter(
        field_name="exam_schedule__exam__term", queryset=Term.objects.all()
    )
    subject = filters.ModelChoiceFilter(
        field_name="exam_schedule__subject", queryset=Subject.objects.all()
    )

    class Meta:
        model = OnlineExam
        fields = [
            "exam_schedule",
            "enable_proctoring",
            "shuffle_questions",
            "show_results_immediately",
            "max_attempts",
        ]


class StudentOnlineExamAttemptFilter(filters.FilterSet):
    """Filter for StudentOnlineExamAttempt model"""

    student = filters.ModelChoiceFilter(queryset=Student.objects.all())
    online_exam = filters.ModelChoiceFilter(queryset=OnlineExam.objects.all())
    status = filters.ChoiceFilter(
        choices=StudentOnlineExamAttempt._meta.get_field("status").choices
    )
    is_graded = filters.BooleanFilter()
    attempt_number = filters.NumberFilter()
    marks_min = filters.NumberFilter(field_name="marks_obtained", lookup_expr="gte")
    marks_max = filters.NumberFilter(field_name="marks_obtained", lookup_expr="lte")
    violation_count_max = filters.NumberFilter(
        field_name="violation_count", lookup_expr="lte"
    )

    start_time_from = filters.DateTimeFilter(field_name="start_time", lookup_expr="gte")
    start_time_to = filters.DateTimeFilter(field_name="start_time", lookup_expr="lte")
    submit_time_from = filters.DateTimeFilter(
        field_name="submit_time", lookup_expr="gte"
    )
    submit_time_to = filters.DateTimeFilter(field_name="submit_time", lookup_expr="lte")

    # Filter by subject and exam details
    subject = filters.ModelChoiceFilter(
        field_name="online_exam__exam_schedule__subject", queryset=Subject.objects.all()
    )
    academic_year = filters.ModelChoiceFilter(
        field_name="online_exam__exam_schedule__exam__academic_year",
        queryset=AcademicYear.objects.all(),
    )

    class Meta:
        model = StudentOnlineExamAttempt
        fields = ["student", "online_exam", "status", "is_graded", "attempt_number"]
