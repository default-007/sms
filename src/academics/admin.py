"""
Django Admin Configuration for Academics Module

This module configures the Django admin interface for academic models,
providing user-friendly interfaces for managing:
- Departments
- Academic Years and Terms
- Sections, Grades, and Classes
"""

from django.contrib import admin
from django.db import models
from django.forms import Textarea
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from .models import AcademicYear, Class, Department, Grade, Section, Term


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    """Admin configuration for Department model"""

    list_display = [
        "name",
        "head_name",
        "teachers_count",
        "subjects_count",
        "is_active",
        "creation_date",
    ]
    list_filter = ["is_active", "creation_date"]
    search_fields = ["name", "description"]
    ordering = ["name"]

    fieldsets = (
        ("Basic Information", {"fields": ("name", "description", "is_active")}),
        (
            "Management",
            {"fields": ("head",), "description": "Department head assignment"},
        ),
        ("Metadata", {"fields": ("creation_date",), "classes": ("collapse",)}),
    )

    readonly_fields = ["creation_date"]

    formfield_overrides = {
        models.TextField: {"widget": Textarea(attrs={"rows": 3, "cols": 60})},
    }

    def head_name(self, obj):
        """Display department head name"""
        if obj.head:
            return f"{obj.head.user.first_name} {obj.head.user.last_name}"
        return "Not assigned"

    head_name.short_description = "Department Head"

    def teachers_count(self, obj):
        """Display count of teachers in department"""
        return obj.get_teachers_count()

    teachers_count.short_description = "Teachers"

    def subjects_count(self, obj):
        """Display count of subjects in department"""
        return obj.get_subjects_count()

    subjects_count.short_description = "Subjects"


class TermInline(admin.TabularInline):
    """Inline admin for Terms within Academic Year"""

    model = Term
    extra = 0
    fields = ["name", "term_number", "start_date", "end_date", "is_current"]
    readonly_fields = []

    def get_readonly_fields(self, request, obj=None):
        """Make term_number readonly for existing terms"""
        if obj and obj.pk:
            return ["term_number"]
        return []


@admin.register(AcademicYear)
class AcademicYearAdmin(admin.ModelAdmin):
    """Admin configuration for AcademicYear model"""

    list_display = [
        "name",
        "start_date",
        "end_date",
        "is_current",
        "terms_count",
        "classes_count",
        "created_by",
    ]
    list_filter = ["is_current", "start_date"]
    search_fields = ["name"]
    ordering = ["-start_date"]

    fieldsets = (
        (
            "Basic Information",
            {"fields": ("name", "start_date", "end_date", "is_current")},
        ),
        (
            "Metadata",
            {
                "fields": ("created_by", "created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    readonly_fields = ["created_at", "updated_at"]
    inlines = [TermInline]

    def terms_count(self, obj):
        """Display count of terms in academic year"""
        return obj.terms.count()

    terms_count.short_description = "Terms"

    def classes_count(self, obj):
        """Display count of classes in academic year"""
        return obj.classes.filter(is_active=True).count()

    classes_count.short_description = "Active Classes"

    def save_model(self, request, obj, form, change):
        """Set created_by field on new academic years"""
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(Term)
class TermAdmin(admin.ModelAdmin):
    """Admin configuration for Term model"""

    list_display = [
        "name",
        "academic_year",
        "term_number",
        "start_date",
        "end_date",
        "is_current",
        "duration_display",
    ]
    list_filter = ["is_current", "academic_year", "term_number"]
    search_fields = ["name", "academic_year__name"]
    ordering = ["academic_year", "term_number"]

    fieldsets = (
        ("Basic Information", {"fields": ("academic_year", "name", "term_number")}),
        ("Dates", {"fields": ("start_date", "end_date", "is_current")}),
        (
            "Metadata",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    readonly_fields = ["created_at", "updated_at"]

    def duration_display(self, obj):
        """Display term duration in days"""
        return f"{obj.get_duration_days()} days"

    duration_display.short_description = "Duration"


class GradeInline(admin.TabularInline):
    """Inline admin for Grades within Section"""

    model = Grade
    extra = 0
    fields = ["name", "order_sequence", "minimum_age", "maximum_age", "is_active"]
    ordering = ["order_sequence"]


@admin.register(Section)
class SectionAdmin(admin.ModelAdmin):
    """Admin configuration for Section model"""

    list_display = [
        "name",
        "department",
        "grades_count",
        "total_students_display",
        "order_sequence",
        "is_active",
    ]
    list_filter = ["is_active", "department"]
    search_fields = ["name", "description"]
    ordering = ["order_sequence", "name"]

    fieldsets = (
        (
            "Basic Information",
            {"fields": ("name", "description", "order_sequence", "is_active")},
        ),
        ("Organization", {"fields": ("department",)}),
        (
            "Metadata",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    readonly_fields = ["created_at", "updated_at"]
    inlines = [GradeInline]

    formfield_overrides = {
        models.TextField: {"widget": Textarea(attrs={"rows": 3, "cols": 60})},
    }

    def grades_count(self, obj):
        """Display count of grades in section"""
        return obj.get_grades_count()

    grades_count.short_description = "Grades"

    def total_students_display(self, obj):
        """Display total students across all grades in section"""
        total = obj.get_total_students()
        return format_html("<strong>{}</strong>", total)

    total_students_display.short_description = "Total Students"


class ClassInline(admin.TabularInline):
    """Inline admin for Classes within Grade"""

    model = Class
    extra = 0
    fields = [
        "name",
        "academic_year",
        "capacity",
        "room_number",
        "class_teacher",
        "is_active",
    ]

    def get_queryset(self, request):
        """Filter to current academic year by default"""
        qs = super().get_queryset(request)
        return qs.select_related("academic_year", "class_teacher__user")


@admin.register(Grade)
class GradeAdmin(admin.ModelAdmin):
    """Admin configuration for Grade model"""

    list_display = [
        "name",
        "section",
        "classes_count_display",
        "students_count_display",
        "age_range",
        "order_sequence",
        "is_active",
    ]
    list_filter = ["is_active", "section", "department"]
    search_fields = ["name", "section__name", "description"]
    ordering = ["section", "order_sequence"]

    fieldsets = (
        (
            "Basic Information",
            {
                "fields": (
                    "section",
                    "name",
                    "description",
                    "order_sequence",
                    "is_active",
                )
            },
        ),
        (
            "Age Requirements",
            {
                "fields": ("minimum_age", "maximum_age"),
                "description": "Age requirements for student admission",
            },
        ),
        ("Organization", {"fields": ("department",)}),
        (
            "Metadata",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    readonly_fields = ["created_at", "updated_at"]
    inlines = [ClassInline]

    formfield_overrides = {
        models.TextField: {"widget": Textarea(attrs={"rows": 3, "cols": 60})},
    }

    def classes_count_display(self, obj):
        """Display count of classes for current academic year"""
        from .services import AcademicYearService

        current_year = AcademicYearService.get_current_academic_year()
        count = obj.get_classes_count(current_year) if current_year else 0
        return format_html('<span style="color: blue;">{}</span>', count)

    classes_count_display.short_description = "Classes (Current Year)"

    def students_count_display(self, obj):
        """Display count of students for current academic year"""
        from .services import AcademicYearService

        current_year = AcademicYearService.get_current_academic_year()
        count = obj.get_total_students(current_year) if current_year else 0
        return format_html('<strong style="color: green;">{}</strong>', count)

    students_count_display.short_description = "Students (Current Year)"

    def age_range(self, obj):
        """Display age range"""
        if obj.minimum_age and obj.maximum_age:
            return f"{obj.minimum_age}-{obj.maximum_age} years"
        elif obj.minimum_age:
            return f"{obj.minimum_age}+ years"
        elif obj.maximum_age:
            return f"≤{obj.maximum_age} years"
        return "Not specified"

    age_range.short_description = "Age Range"


@admin.register(Class)
class ClassAdmin(admin.ModelAdmin):
    """Admin configuration for Class model"""

    list_display = [
        "display_name",
        "grade_section",
        "academic_year",
        "students_count_display",
        "capacity_display",
        "class_teacher_name",
        "room_number",
        "is_active",
    ]
    list_filter = ["is_active", "academic_year", "section", "grade"]
    search_fields = ["name", "grade__name", "section__name", "room_number"]
    ordering = ["section", "grade", "name"]

    fieldsets = (
        (
            "Basic Information",
            {"fields": ("grade", "name", "academic_year", "is_active")},
        ),
        ("Capacity & Location", {"fields": ("capacity", "room_number")}),
        (
            "Assignment",
            {
                "fields": ("class_teacher",),
                "description": "Teacher assignment for this class",
            },
        ),
        (
            "Metadata",
            {
                "fields": ("section", "created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    readonly_fields = ["section", "created_at", "updated_at"]

    def grade_section(self, obj):
        """Display grade and section"""
        return f"{obj.section.name} - {obj.grade.name}"

    grade_section.short_description = "Grade & Section"

    def students_count_display(self, obj):
        """Display current student count with color coding"""
        count = obj.get_students_count()
        utilization = (count / obj.capacity * 100) if obj.capacity > 0 else 0

        if utilization > 95:
            color = "red"
        elif utilization > 80:
            color = "orange"
        else:
            color = "green"

        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>', color, count
        )

    students_count_display.short_description = "Students"

    def capacity_display(self, obj):
        """Display capacity with utilization"""
        count = obj.get_students_count()
        utilization = (count / obj.capacity * 100) if obj.capacity > 0 else 0

        return format_html(
            '{} <small style="color: gray;">({:.1f}%)</small>',
            obj.capacity,
            utilization,
        )

    capacity_display.short_description = "Capacity"

    def class_teacher_name(self, obj):
        """Display class teacher name with link"""
        if obj.class_teacher:
            teacher_name = f"{obj.class_teacher.user.first_name} {obj.class_teacher.user.last_name}"
            # If you have a teacher detail view, you can add a link here
            return teacher_name
        return "Not assigned"

    class_teacher_name.short_description = "Class Teacher"

    def save_model(self, request, obj, form, change):
        """Auto-set section from grade"""
        if obj.grade:
            obj.section = obj.grade.section
        super().save_model(request, obj, form, change)


# Custom admin site configuration
admin.site.site_header = "School Management System - Academics"
admin.site.site_title = "SMS Academics"
admin.site.index_title = "Academic Management"


# Register custom actions
def make_active(modeladmin, request, queryset):
    """Bulk action to activate selected items"""
    queryset.update(is_active=True)


make_active.short_description = "Mark selected items as active"


def make_inactive(modeladmin, request, queryset):
    """Bulk action to deactivate selected items"""
    queryset.update(is_active=False)


make_inactive.short_description = "Mark selected items as inactive"

# Add actions to relevant admin classes
SectionAdmin.actions = [make_active, make_inactive]
GradeAdmin.actions = [make_active, make_inactive]
ClassAdmin.actions = [make_active, make_inactive]
DepartmentAdmin.actions = [make_active, make_inactive]
