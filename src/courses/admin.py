from django.contrib import admin
from .models import (
    Department,
    AcademicYear,
    Grade,
    Section,
    Class,
    Subject,
    Syllabus,
    TimeSlot,
    Timetable,
    Assignment,
    AssignmentSubmission,
)


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("name", "head", "creation_date")
    search_fields = ("name", "description")
    list_filter = ("creation_date",)


@admin.register(AcademicYear)
class AcademicYearAdmin(admin.ModelAdmin):
    list_display = ("name", "start_date", "end_date", "is_current")
    search_fields = ("name",)
    list_filter = ("is_current",)


@admin.register(Grade)
class GradeAdmin(admin.ModelAdmin):
    list_display = ("name", "department")
    search_fields = ("name", "description")
    list_filter = ("department",)


@admin.register(Section)
class SectionAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name", "description")


@admin.register(Class)
class ClassAdmin(admin.ModelAdmin):
    list_display = (
        "__str__",
        "grade",
        "section",
        "academic_year",
        "class_teacher",
        "capacity",
    )
    search_fields = ("grade__name", "section__name", "room_number")
    list_filter = ("academic_year", "grade", "section")
    autocomplete_fields = ("grade", "section", "academic_year", "class_teacher")


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "department", "credit_hours", "is_elective")
    search_fields = ("name", "code", "description")
    list_filter = ("department", "is_elective")


@admin.register(Syllabus)
class SyllabusAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "subject",
        "grade",
        "academic_year",
        "created_by",
        "last_updated_at",
    )
    search_fields = ("title", "description", "subject__name", "grade__name")
    list_filter = ("academic_year", "subject", "grade")
    autocomplete_fields = (
        "subject",
        "grade",
        "academic_year",
        "created_by",
        "last_updated_by",
    )


@admin.register(TimeSlot)
class TimeSlotAdmin(admin.ModelAdmin):
    list_display = (
        "__str__",
        "day_of_week",
        "start_time",
        "end_time",
        "duration_minutes",
    )
    list_filter = ("day_of_week",)
    search_fields = ("day_of_week", "start_time", "end_time")


@admin.register(Timetable)
class TimetableAdmin(admin.ModelAdmin):
    list_display = ("class_obj", "subject", "teacher", "time_slot", "is_active")
    search_fields = (
        "class_obj__grade__name",
        "subject__name",
        "teacher__user__username",
    )
    list_filter = ("is_active", "time_slot__day_of_week", "class_obj__academic_year")
    autocomplete_fields = ("class_obj", "subject", "teacher", "time_slot")


@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "class_obj",
        "subject",
        "teacher",
        "assigned_date",
        "due_date",
        "status",
    )
    search_fields = ("title", "description", "class_obj__grade__name", "subject__name")
    list_filter = ("status", "submission_type", "assigned_date", "due_date")
    autocomplete_fields = ("class_obj", "subject", "teacher")
    date_hierarchy = "assigned_date"


@admin.register(AssignmentSubmission)
class AssignmentSubmissionAdmin(admin.ModelAdmin):
    list_display = (
        "assignment",
        "student",
        "submission_date",
        "status",
        "marks_obtained",
        "graded_by",
    )
    search_fields = ("assignment__title", "student__user__username", "content")
    list_filter = ("status", "submission_date", "graded_at")
    autocomplete_fields = ("assignment", "student", "graded_by")
    readonly_fields = ("submission_date", "graded_at")
