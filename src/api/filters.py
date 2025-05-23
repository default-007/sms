# src/api/filters.py
"""Common API Filters"""

import django_filters
from django.db import models
from django_filters import rest_framework as filters
from django.contrib.auth import get_user_model
from datetime import datetime, timedelta
from django.utils import timezone

User = get_user_model()


class BaseFilter(filters.FilterSet):
    """Base filter with common fields"""

    # Date range filters
    created_after = filters.DateTimeFilter(field_name="created_at", lookup_expr="gte")
    created_before = filters.DateTimeFilter(field_name="created_at", lookup_expr="lte")
    updated_after = filters.DateTimeFilter(field_name="updated_at", lookup_expr="gte")
    updated_before = filters.DateTimeFilter(field_name="updated_at", lookup_expr="lte")

    # Search filter
    search = filters.CharFilter(method="filter_search")

    def filter_search(self, queryset, name, value):
        """Generic search filter - override in subclasses"""
        return queryset


class AcademicFilter(BaseFilter):
    """Filter for academic-related models"""

    academic_year = filters.NumberFilter(field_name="academic_year__id")
    term = filters.NumberFilter(field_name="term__id")
    section = filters.NumberFilter(field_name="section__id")
    grade = filters.NumberFilter(field_name="grade__id")
    class_id = filters.NumberFilter(field_name="class_id")

    # Academic year by name
    academic_year_name = filters.CharFilter(
        field_name="academic_year__name", lookup_expr="icontains"
    )

    # Current academic entities
    is_current_year = filters.BooleanFilter(field_name="academic_year__is_current")
    is_current_term = filters.BooleanFilter(field_name="term__is_current")


class UserFilter(BaseFilter):
    """Filter for user-related models"""

    user_type = filters.ChoiceFilter(
        field_name="user__user_type",
        choices=[
            ("admin", "Admin"),
            ("teacher", "Teacher"),
            ("student", "Student"),
            ("parent", "Parent"),
            ("staff", "Staff"),
        ],
    )

    is_active = filters.BooleanFilter(field_name="user__is_active")
    has_role = filters.CharFilter(method="filter_by_role")

    def filter_by_role(self, queryset, name, value):
        """Filter by user role"""
        return queryset.filter(user__roles__name__icontains=value)


class StudentFilter(AcademicFilter, UserFilter):
    """Filter for student-related models"""

    # Student specific filters
    admission_number = filters.CharFilter(
        field_name="student__admission_number", lookup_expr="icontains"
    )

    roll_number = filters.CharFilter(
        field_name="student__roll_number", lookup_expr="icontains"
    )

    status = filters.ChoiceFilter(
        field_name="student__status",
        choices=[
            ("active", "Active"),
            ("inactive", "Inactive"),
            ("graduated", "Graduated"),
            ("transferred", "Transferred"),
        ],
    )

    # Parent filter
    parent_id = filters.NumberFilter(field_name="student__parents__id")


class TeacherFilter(AcademicFilter, UserFilter):
    """Filter for teacher-related models"""

    employee_id = filters.CharFilter(
        field_name="teacher__employee_id", lookup_expr="icontains"
    )

    department = filters.NumberFilter(field_name="teacher__department__id")

    specialization = filters.CharFilter(
        field_name="teacher__specialization", lookup_expr="icontains"
    )

    is_class_teacher = filters.BooleanFilter(
        field_name="teacher__teacherclassassignment__is_class_teacher"
    )


class FinancialFilter(AcademicFilter):
    """Filter for financial models"""

    # Amount range filters
    amount_min = filters.NumberFilter(field_name="amount", lookup_expr="gte")
    amount_max = filters.NumberFilter(field_name="amount", lookup_expr="lte")

    # Fee category
    fee_category = filters.NumberFilter(field_name="fee_category__id")

    # Payment status
    payment_status = filters.ChoiceFilter(
        choices=[
            ("paid", "Paid"),
            ("unpaid", "Unpaid"),
            ("partial", "Partially Paid"),
            ("overdue", "Overdue"),
        ]
    )

    # Date range for financial operations
    due_date_after = filters.DateFilter(field_name="due_date", lookup_expr="gte")
    due_date_before = filters.DateFilter(field_name="due_date", lookup_expr="lte")


class DateRangeFilter(filters.FilterSet):
    """Flexible date range filter"""

    date_from = filters.DateFilter(method="filter_date_from")
    date_to = filters.DateFilter(method="filter_date_to")
    date_range = filters.ChoiceFilter(
        method="filter_date_range",
        choices=[
            ("today", "Today"),
            ("yesterday", "Yesterday"),
            ("this_week", "This Week"),
            ("last_week", "Last Week"),
            ("this_month", "This Month"),
            ("last_month", "Last Month"),
            ("this_year", "This Year"),
            ("last_year", "Last Year"),
        ],
    )

    def filter_date_from(self, queryset, name, value):
        """Filter from date"""
        date_field = getattr(self.Meta, "date_field", "created_at")
        return queryset.filter(**{f"{date_field}__gte": value})

    def filter_date_to(self, queryset, name, value):
        """Filter to date"""
        date_field = getattr(self.Meta, "date_field", "created_at")
        return queryset.filter(**{f"{date_field}__lte": value})

    def filter_date_range(self, queryset, name, value):
        """Filter by predefined date ranges"""
        now = timezone.now()
        date_field = getattr(self.Meta, "date_field", "created_at")

        ranges = {
            "today": (now.replace(hour=0, minute=0, second=0), now),
            "yesterday": (
                (now - timedelta(days=1)).replace(hour=0, minute=0, second=0),
                (now - timedelta(days=1)).replace(hour=23, minute=59, second=59),
            ),
            "this_week": (now - timedelta(days=now.weekday()), now),
            "last_week": (
                now - timedelta(days=now.weekday() + 7),
                now - timedelta(days=now.weekday() + 1),
            ),
            "this_month": (now.replace(day=1, hour=0, minute=0, second=0), now),
            "last_month": (
                (now.replace(day=1) - timedelta(days=1)).replace(day=1),
                now.replace(day=1) - timedelta(seconds=1),
            ),
            "this_year": (now.replace(month=1, day=1, hour=0, minute=0, second=0), now),
            "last_year": (
                now.replace(
                    year=now.year - 1, month=1, day=1, hour=0, minute=0, second=0
                ),
                now.replace(month=1, day=1, hour=0, minute=0, second=0)
                - timedelta(seconds=1),
            ),
        }

        if value in ranges:
            start_date, end_date = ranges[value]
            return queryset.filter(
                **{f"{date_field}__gte": start_date, f"{date_field}__lte": end_date}
            )

        return queryset
