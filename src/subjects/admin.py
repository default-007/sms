import json

from django.contrib import admin
from django.db import models
from django.db.models import Avg, Count
from django.urls import reverse
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from .models import Subject, SubjectAssignment, Syllabus, TopicProgress


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    """Admin configuration for Subject model."""

    list_display = [
        "code",
        "name",
        "department",
        "credit_hours",
        "is_elective",
        "get_applicable_grades",
        "syllabi_count",
        "is_active",
        "created_at",
    ]
    list_filter = [
        "department",
        "is_elective",
        "is_active",
        "credit_hours",
        "created_at",
    ]
    search_fields = ["name", "code", "description", "department__name"]
    ordering = ["department__name", "name"]
    readonly_fields = ["created_at", "updated_at", "syllabi_count", "completion_stats"]

    fieldsets = (
        (
            _("Basic Information"),
            {"fields": ("name", "code", "description", "department")},
        ),
        (
            _("Academic Settings"),
            {"fields": ("credit_hours", "is_elective", "grade_level")},
        ),
        (_("Status"), {"fields": ("is_active",)}),
        (
            _("Statistics"),
            {"fields": ("syllabi_count", "completion_stats"), "classes": ("collapse",)},
        ),
        (
            _("Timestamps"),
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    filter_horizontal = []

    def get_queryset(self, request):
        """Optimize queryset with related data."""
        return (
            super()
            .get_queryset(request)
            .select_related("department")
            .annotate(
                syllabi_count=Count(
                    "syllabi", filter=models.Q(syllabi__is_active=True)
                ),
                avg_completion=Avg(
                    "syllabi__completion_percentage",
                    filter=models.Q(syllabi__is_active=True),
                ),
            )
        )

    def get_applicable_grades(self, obj):
        """Display applicable grades in a readable format."""
        if not obj.grade_level:
            return _("All Grades")

        from academics.models import Grade

        grades = Grade.objects.filter(id__in=obj.grade_level)
        grade_names = [grade.name for grade in grades]

        if len(grade_names) > 3:
            return f"{', '.join(grade_names[:3])}... (+{len(grade_names)-3} more)"
        return ", ".join(grade_names)

    get_applicable_grades.short_description = _("Applicable Grades")

    def syllabi_count(self, obj):
        """Display number of syllabi for this subject."""
        count = getattr(
            obj, "syllabi_count", obj.syllabi.filter(is_active=True).count()
        )
        if count > 0:
            url = (
                reverse("admin:subjects_syllabus_changelist") + f"?subject__id={obj.id}"
            )
            return format_html('<a href="{}">{} syllabi</a>', url, count)
        return "0 syllabi"

    syllabi_count.short_description = _("Syllabi")

    def completion_stats(self, obj):
        """Display completion statistics."""
        avg_completion = getattr(obj, "avg_completion", None)
        if avg_completion is not None:
            return f"{avg_completion:.1f}% average completion"
        return _("No syllabi")

    completion_stats.short_description = _("Completion Stats")


class TopicProgressInline(admin.TabularInline):
    """Inline admin for topic progress."""

    model = TopicProgress
    extra = 0
    readonly_fields = ["completion_date", "created_at", "updated_at"]
    fields = [
        "topic_index",
        "topic_name",
        "is_completed",
        "completion_date",
        "hours_taught",
        "teaching_method",
        "notes",
    ]

    def get_queryset(self, request):
        """Order by topic index."""
        return super().get_queryset(request).order_by("topic_index")


@admin.register(Syllabus)
class SyllabusAdmin(admin.ModelAdmin):
    """Admin configuration for Syllabus model."""

    list_display = [
        "title",
        "subject",
        "grade",
        "term",
        "academic_year",
        "get_completion_status",
        "get_topics_progress",
        "difficulty_level",
        "last_updated_at",
        "is_active",
    ]
    list_filter = [
        "academic_year",
        "term",
        "subject__department",
        "grade",
        "difficulty_level",
        "is_active",
        "created_at",
    ]
    search_fields = [
        "title",
        "description",
        "subject__name",
        "subject__code",
        "grade__name",
        "created_by__first_name",
        "created_by__last_name",
    ]
    ordering = [
        "academic_year",
        "term__term_number",
        "subject__name",
        "grade__order_sequence",
    ]
    readonly_fields = [
        "created_at",
        "last_updated_at",
        "get_completion_status",
        "get_topics_progress",
        "get_content_summary",
    ]

    fieldsets = (
        (
            _("Basic Information"),
            {
                "fields": (
                    "title",
                    "description",
                    "subject",
                    "grade",
                    "academic_year",
                    "term",
                )
            },
        ),
        (
            _("Content Structure"),
            {"fields": ("content", "learning_objectives"), "classes": ("collapse",)},
        ),
        (
            _("Progress & Completion"),
            {
                "fields": (
                    "completion_percentage",
                    "get_completion_status",
                    "get_topics_progress",
                )
            },
        ),
        (
            _("Academic Details"),
            {
                "fields": (
                    "estimated_duration_hours",
                    "difficulty_level",
                    "prerequisites",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            _("Assessment & Resources"),
            {"fields": ("assessment_methods", "resources"), "classes": ("collapse",)},
        ),
        (
            _("Status & Metadata"),
            {"fields": ("is_active", "created_by", "last_updated_by")},
        ),
        (
            _("Content Summary"),
            {"fields": ("get_content_summary",), "classes": ("collapse",)},
        ),
        (
            _("Timestamps"),
            {"fields": ("created_at", "last_updated_at"), "classes": ("collapse",)},
        ),
    )

    inlines = [TopicProgressInline]

    def get_queryset(self, request):
        """Optimize queryset with related data."""
        return (
            super()
            .get_queryset(request)
            .select_related(
                "subject",
                "grade",
                "academic_year",
                "term",
                "created_by",
                "last_updated_by",
            )
            .annotate(
                total_topics=Count("topic_progress"),
                completed_topics=Count(
                    "topic_progress", filter=models.Q(topic_progress__is_completed=True)
                ),
            )
        )

    def get_completion_status(self, obj):
        """Display completion status with visual indicator."""
        percentage = obj.completion_percentage
        status = obj.progress_status

        color_map = {
            "not_started": "#dc3545",  # Red
            "in_progress": "#ffc107",  # Yellow
            "nearing_completion": "#17a2b8",  # Blue
            "completed": "#28a745",  # Green
        }

        color = color_map.get(status, "#6c757d")

        return format_html(
            '<span style="color: {}; font-weight: bold;">{:.1f}% ({})</span>',
            color,
            percentage,
            status.replace("_", " ").title(),
        )

    get_completion_status.short_description = _("Completion Status")

    def get_topics_progress(self, obj):
        """Display topics progress."""
        total_topics = getattr(obj, "total_topics", obj.get_total_topics())
        completed_topics = getattr(obj, "completed_topics", obj.get_completed_topics())

        if total_topics == 0:
            return _("No topics defined")

        return f"{completed_topics}/{total_topics} topics completed"

    get_topics_progress.short_description = _("Topics Progress")

    def get_content_summary(self, obj):
        """Display content summary."""
        content = obj.content or {}

        summary_parts = []

        if "topics" in content:
            summary_parts.append(f"Topics: {len(content['topics'])}")

        if "units" in content:
            summary_parts.append(f"Units: {len(content['units'])}")

        if obj.learning_objectives:
            summary_parts.append(f"Learning Objectives: {len(obj.learning_objectives)}")

        if obj.prerequisites:
            summary_parts.append(f"Prerequisites: {len(obj.prerequisites)}")

        return (
            ", ".join(summary_parts)
            if summary_parts
            else _("No content structure defined")
        )

    get_content_summary.short_description = _("Content Summary")

    def save_model(self, request, obj, form, change):
        """Set created_by and last_updated_by fields."""
        if not change:  # Creating new object
            obj.created_by = request.user
        obj.last_updated_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(TopicProgress)
class TopicProgressAdmin(admin.ModelAdmin):
    """Admin configuration for TopicProgress model."""

    list_display = [
        "get_syllabus_info",
        "topic_name",
        "topic_index",
        "is_completed",
        "completion_date",
        "hours_taught",
        "created_at",
    ]
    list_filter = [
        "is_completed",
        "completion_date",
        "syllabus__academic_year",
        "syllabus__term",
        "syllabus__subject__department",
        "created_at",
    ]
    search_fields = [
        "topic_name",
        "notes",
        "syllabus__title",
        "syllabus__subject__name",
        "teaching_method",
    ]
    ordering = ["syllabus", "topic_index"]
    readonly_fields = ["created_at", "updated_at"]

    fieldsets = (
        (_("Topic Information"), {"fields": ("syllabus", "topic_name", "topic_index")}),
        (
            _("Progress"),
            {"fields": ("is_completed", "completion_date", "hours_taught")},
        ),
        (_("Teaching Details"), {"fields": ("teaching_method", "notes")}),
        (
            _("Timestamps"),
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    def get_queryset(self, request):
        """Optimize queryset with related data."""
        return (
            super()
            .get_queryset(request)
            .select_related("syllabus__subject", "syllabus__grade", "syllabus__term")
        )

    def get_syllabus_info(self, obj):
        """Display syllabus information."""
        return f"{obj.syllabus.subject.code} - {obj.syllabus.grade.name} - {obj.syllabus.term.name}"

    get_syllabus_info.short_description = _("Syllabus")


@admin.register(SubjectAssignment)
class SubjectAssignmentAdmin(admin.ModelAdmin):
    """Admin configuration for SubjectAssignment model."""

    list_display = [
        "get_assignment_info",
        "teacher",
        "class_assigned",
        "term",
        "is_primary_teacher",
        "assigned_date",
        "is_active",
    ]
    list_filter = [
        "academic_year",
        "term",
        "subject__department",
        "is_primary_teacher",
        "is_active",
        "assigned_date",
    ]
    search_fields = [
        "subject__name",
        "subject__code",
        "teacher__user__first_name",
        "teacher__user__last_name",
        "class_assigned__name",
    ]
    ordering = ["academic_year", "term__term_number", "teacher__user__last_name"]
    readonly_fields = ["assigned_date"]

    fieldsets = (
        (
            _("Assignment Details"),
            {
                "fields": (
                    "subject",
                    "teacher",
                    "class_assigned",
                    "academic_year",
                    "term",
                )
            },
        ),
        (_("Assignment Type"), {"fields": ("is_primary_teacher",)}),
        (_("Metadata"), {"fields": ("assigned_by", "assigned_date", "is_active")}),
    )

    def get_queryset(self, request):
        """Optimize queryset with related data."""
        return (
            super()
            .get_queryset(request)
            .select_related(
                "subject",
                "teacher__user",
                "class_assigned",
                "academic_year",
                "term",
                "assigned_by",
            )
        )

    def get_assignment_info(self, obj):
        """Display assignment information."""
        return f"{obj.subject.code} - {obj.class_assigned}"

    get_assignment_info.short_description = _("Assignment")

    def save_model(self, request, obj, form, change):
        """Set assigned_by field."""
        if not change:  # Creating new object
            obj.assigned_by = request.user
        super().save_model(request, obj, form, change)


# Additional admin customizations
admin.site.site_header = _("School Management System - Subjects Administration")
admin.site.site_title = _("Subjects Admin")
admin.site.index_title = _("Subjects Management")
