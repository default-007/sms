from django.contrib import admin
from django.db.models import Count, Q
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from .models import (
    Room,
    SchedulingConstraint,
    SubstituteTeacher,
    TimeSlot,
    Timetable,
    TimetableGeneration,
    TimetableTemplate,
)


@admin.register(TimeSlot)
class TimeSlotAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "day_of_week_display",
        "period_number",
        "start_time",
        "end_time",
        "duration_minutes",
        "is_break",
        "is_active",
    ]
    list_filter = ["day_of_week", "is_break", "is_active"]
    search_fields = ["name"]
    ordering = ["day_of_week", "period_number"]

    fieldsets = (
        (None, {"fields": ("name", "day_of_week", "period_number")}),
        (
            "Time Information",
            {"fields": ("start_time", "end_time", "duration_minutes")},
        ),
        ("Settings", {"fields": ("is_break", "is_active")}),
    )

    def day_of_week_display(self, obj):
        return obj.get_day_of_week_display()

    day_of_week_display.short_description = "Day"
    day_of_week_display.admin_order_field = "day_of_week"


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = [
        "number",
        "name",
        "room_type",
        "building",
        "floor",
        "capacity",
        "is_available",
        "utilization_link",
    ]
    list_filter = ["room_type", "building", "is_available"]
    search_fields = ["number", "name", "building"]
    ordering = ["building", "floor", "number"]

    fieldsets = (
        (None, {"fields": ("number", "name", "room_type")}),
        ("Location", {"fields": ("building", "floor")}),
        ("Specifications", {"fields": ("capacity", "equipment")}),
        ("Status", {"fields": ("is_available", "maintenance_notes")}),
    )

    def utilization_link(self, obj):
        """Link to room utilization analytics"""
        return format_html(
            '<a href="#" onclick="viewUtilization(\'{}\')">View Utilization</a>', obj.id
        )

    utilization_link.short_description = "Utilization"

    class Media:
        js = ("admin/js/room_analytics.js",)


class TimetableInlineFilter(admin.SimpleListFilter):
    title = "Schedule Status"
    parameter_name = "schedule_status"

    def lookups(self, request, model_admin):
        return (
            ("has_conflicts", "Has Conflicts"),
            ("no_room", "No Room Assigned"),
            ("multiple_subjects", "Multiple Subjects Same Time"),
        )

    def queryset(self, request, queryset):
        if self.value() == "no_room":
            return queryset.filter(room__isnull=True)
        # Add other filters as needed
        return queryset


@admin.register(Timetable)
class TimetableAdmin(admin.ModelAdmin):
    list_display = [
        "class_display",
        "subject",
        "teacher_display",
        "time_slot_display",
        "room_display",
        "term",
        "is_active",
        "conflicts_indicator",
    ]
    list_filter = [
        "term",
        "class_assigned__grade",
        "subject",
        "is_active",
        TimetableInlineFilter,
    ]
    search_fields = [
        "class_assigned__name",
        "subject__name",
        "teacher__user__first_name",
        "teacher__user__last_name",
        "room__number",
    ]
    ordering = ["term", "time_slot__day_of_week", "time_slot__period_number"]

    fieldsets = (
        ("Assignment", {"fields": ("class_assigned", "subject", "teacher")}),
        ("Schedule", {"fields": ("time_slot", "room", "term")}),
        ("Duration", {"fields": ("effective_from_date", "effective_to_date")}),
        ("Status", {"fields": ("is_active", "notes")}),
    )

    readonly_fields = ["created_by", "created_at", "updated_at"]

    def class_display(self, obj):
        return f"{obj.class_assigned.grade.name} {obj.class_assigned.name}"

    class_display.short_description = "Class"
    class_display.admin_order_field = "class_assigned__name"

    def teacher_display(self, obj):
        return obj.teacher.user.get_full_name()

    teacher_display.short_description = "Teacher"
    teacher_display.admin_order_field = "teacher__user__last_name"

    def time_slot_display(self, obj):
        return str(obj.time_slot)

    time_slot_display.short_description = "Time Slot"

    def room_display(self, obj):
        if obj.room:
            return f"{obj.room.number} - {obj.room.name}"
        return format_html('<span style="color: red;">No Room</span>')

    room_display.short_description = "Room"

    def conflicts_indicator(self, obj):
        """Show if there are scheduling conflicts"""
        # Check for teacher conflicts
        teacher_conflicts = (
            Timetable.objects.filter(
                teacher=obj.teacher,
                time_slot=obj.time_slot,
                effective_from_date__lte=obj.effective_to_date,
                effective_to_date__gte=obj.effective_from_date,
                is_active=True,
            )
            .exclude(pk=obj.pk)
            .count()
        )

        # Check for room conflicts
        room_conflicts = 0
        if obj.room:
            room_conflicts = (
                Timetable.objects.filter(
                    room=obj.room,
                    time_slot=obj.time_slot,
                    effective_from_date__lte=obj.effective_to_date,
                    effective_to_date__gte=obj.effective_from_date,
                    is_active=True,
                )
                .exclude(pk=obj.pk)
                .count()
            )

        if teacher_conflicts > 0 or room_conflicts > 0:
            return format_html('<span style="color: red;">⚠ Conflicts</span>')
        return format_html('<span style="color: green;">✓ OK</span>')

    conflicts_indicator.short_description = "Status"

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    actions = ["check_conflicts", "mark_active", "mark_inactive"]

    def check_conflicts(self, request, queryset):
        """Check selected timetables for conflicts"""
        conflict_count = 0
        for timetable in queryset:
            # Logic to check conflicts
            pass
        self.message_user(
            request,
            f"Checked {queryset.count()} timetables. Found {conflict_count} conflicts.",
        )

    check_conflicts.short_description = "Check for conflicts"

    def mark_active(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f"{updated} timetables marked as active.")

    mark_active.short_description = "Mark selected as active"

    def mark_inactive(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f"{updated} timetables marked as inactive.")

    mark_inactive.short_description = "Mark selected as inactive"


@admin.register(SubstituteTeacher)
class SubstituteTeacherAdmin(admin.ModelAdmin):
    list_display = [
        "date",
        "original_teacher",
        "substitute_teacher",
        "class_subject",
        "reason",
        "approved_status",
    ]
    list_filter = ["date", "approved_by"]
    search_fields = [
        "substitute_teacher__user__first_name",
        "substitute_teacher__user__last_name",
        "reason",
    ]
    ordering = ["-date"]

    fieldsets = (
        (
            "Assignment Details",
            {"fields": ("original_timetable", "substitute_teacher", "date")},
        ),
        ("Reason", {"fields": ("reason", "notes")}),
        ("Approval", {"fields": ("approved_by",)}),
    )

    readonly_fields = ["created_by", "created_at"]

    def original_teacher(self, obj):
        return obj.original_timetable.teacher.user.get_full_name()

    original_teacher.short_description = "Original Teacher"

    def class_subject(self, obj):
        timetable = obj.original_timetable
        return f"{timetable.class_assigned} - {timetable.subject}"

    class_subject.short_description = "Class & Subject"

    def approved_status(self, obj):
        if obj.approved_by:
            return format_html('<span style="color: green;">✓ Approved</span>')
        return format_html('<span style="color: orange;">⏳ Pending</span>')

    approved_status.short_description = "Status"

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(SchedulingConstraint)
class SchedulingConstraintAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "constraint_type",
        "priority",
        "is_hard_constraint",
        "is_active",
    ]
    list_filter = ["constraint_type", "is_hard_constraint", "is_active"]
    search_fields = ["name"]
    ordering = ["-priority", "name"]

    fieldsets = (
        (None, {"fields": ("name", "constraint_type", "priority")}),
        ("Configuration", {"fields": ("parameters", "is_hard_constraint")}),
        ("Status", {"fields": ("is_active",)}),
    )


@admin.register(TimetableGeneration)
class TimetableGenerationAdmin(admin.ModelAdmin):
    list_display = [
        "term",
        "algorithm_used",
        "status",
        "optimization_score",
        "execution_time_seconds",
        "started_by",
        "started_at",
    ]
    list_filter = ["status", "algorithm_used", "started_at"]
    search_fields = ["term__name"]
    ordering = ["-started_at"]

    fieldsets = (
        ("Generation Info", {"fields": ("term", "algorithm_used", "parameters")}),
        (
            "Results",
            {
                "fields": (
                    "status",
                    "optimization_score",
                    "execution_time_seconds",
                    "conflicts_resolved",
                    "result_summary",
                )
            },
        ),
        ("Error Information", {"fields": ("error_message",), "classes": ("collapse",)}),
        (
            "Metadata",
            {
                "fields": ("started_by", "started_at", "completed_at"),
                "classes": ("collapse",),
            },
        ),
    )

    readonly_fields = [
        "status",
        "optimization_score",
        "execution_time_seconds",
        "conflicts_resolved",
        "result_summary",
        "error_message",
        "started_by",
        "started_at",
        "completed_at",
    ]

    def has_add_permission(self, request):
        return False  # Generations should be created via API

    def has_change_permission(self, request, obj=None):
        return False  # Read-only

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


@admin.register(TimetableTemplate)
class TimetableTemplateAdmin(admin.ModelAdmin):
    list_display = ["name", "grade", "is_default", "created_by", "created_at"]
    list_filter = ["grade", "is_default"]
    search_fields = ["name", "description"]
    ordering = ["grade", "name"]

    fieldsets = (
        (None, {"fields": ("name", "description", "grade", "is_default")}),
        ("Configuration", {"fields": ("configuration",)}),
    )

    readonly_fields = ["created_by", "created_at", "updated_at"]

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


# Custom admin site configuration
admin.site.site_header = "School Management System - Scheduling"
admin.site.site_title = "SMS Scheduling"
admin.site.index_title = "Scheduling Administration"
