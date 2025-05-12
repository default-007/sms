from django_filters import rest_framework as filters
from django.contrib.auth import get_user_model
from django.db import models
from src.students.models import Student, Parent
from src.teachers.models import Teacher
from src.courses.models import Class, Assignment

User = get_user_model()


class UserFilter(filters.FilterSet):
    role = filters.CharFilter(method="filter_by_role")

    class Meta:
        model = User
        fields = ["is_active", "date_joined", "role"]

    def filter_by_role(self, queryset, name, value):
        return queryset.filter(role_assignments__role__name=value)


class StudentFilter(filters.FilterSet):
    name = filters.CharFilter(method="filter_by_name")

    class Meta:
        model = Student
        fields = ["status", "current_class", "blood_group", "name"]

    def filter_by_name(self, queryset, name, value):
        return queryset.filter(
            models.Q(user__first_name__icontains=value)
            | models.Q(user__last_name__icontains=value)
        )


class ParentFilter(filters.FilterSet):
    name = filters.CharFilter(method="filter_by_name")

    class Meta:
        model = Parent
        fields = ["relation_with_student", "name"]

    def filter_by_name(self, queryset, name, value):
        return queryset.filter(
            models.Q(user__first_name__icontains=value)
            | models.Q(user__last_name__icontains=value)
        )


class TeacherFilter(filters.FilterSet):
    name = filters.CharFilter(method="filter_by_name")

    class Meta:
        model = Teacher
        fields = ["status", "department", "contract_type", "name"]

    def filter_by_name(self, queryset, name, value):
        return queryset.filter(
            models.Q(user__first_name__icontains=value)
            | models.Q(user__last_name__icontains=value)
        )


class ClassFilter(filters.FilterSet):
    name = filters.CharFilter(method="filter_by_name")

    class Meta:
        model = Class
        fields = ["grade", "section", "academic_year", "class_teacher", "name"]

    def filter_by_name(self, queryset, name, value):
        return queryset.filter(
            models.Q(grade__name__icontains=value)
            | models.Q(section__name__icontains=value)
        )


class AssignmentFilter(filters.FilterSet):
    date_range = filters.DateFromToRangeFilter(field_name="assigned_date")

    class Meta:
        model = Assignment
        fields = ["class_obj", "subject", "teacher", "status", "date_range"]
