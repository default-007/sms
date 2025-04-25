from django.contrib import admin
from .models import Teacher, TeacherClassAssignment, TeacherEvaluation


class TeacherClassAssignmentInline(admin.TabularInline):
    model = TeacherClassAssignment
    extra = 1


class TeacherEvaluationInline(admin.TabularInline):
    model = TeacherEvaluation
    extra = 0
    readonly_fields = ("evaluator", "evaluation_date", "score")
    can_delete = False


@admin.register(Teacher)
class TeacherAdmin(admin.ModelAdmin):
    list_display = (
        "employee_id",
        "get_full_name",
        "department",
        "position",
        "status",
        "joining_date",
    )
    list_filter = ("status", "department", "contract_type", "joining_date")
    search_fields = (
        "employee_id",
        "user__first_name",
        "user__last_name",
        "user__email",
        "position",
    )
    date_hierarchy = "joining_date"
    inlines = [TeacherClassAssignmentInline, TeacherEvaluationInline]

    def get_full_name(self, obj):
        return obj.get_full_name()

    get_full_name.short_description = "Full Name"


@admin.register(TeacherClassAssignment)
class TeacherClassAssignmentAdmin(admin.ModelAdmin):
    list_display = (
        "teacher",
        "class_instance",
        "subject",
        "academic_year",
        "is_class_teacher",
    )
    list_filter = ("academic_year", "is_class_teacher", "subject")
    search_fields = (
        "teacher__user__first_name",
        "teacher__user__last_name",
        "class_instance__grade__name",
    )


@admin.register(TeacherEvaluation)
class TeacherEvaluationAdmin(admin.ModelAdmin):
    list_display = ("teacher", "evaluator", "evaluation_date", "score")
    list_filter = ("evaluation_date", "score")
    search_fields = ("teacher__user__first_name", "teacher__user__last_name", "remarks")
    date_hierarchy = "evaluation_date"
    readonly_fields = ("created_at", "updated_at")
