from django.contrib import admin
from django.db.models import Avg, Count
from django.utils.html import format_html

from .models import Teacher, TeacherClassAssignment, TeacherEvaluation


class TeacherClassAssignmentInline(admin.TabularInline):
    model = TeacherClassAssignment
    extra = 1
    autocomplete_fields = ["class_instance", "subject", "academic_year"]
    fields = ("class_instance", "subject", "academic_year", "is_class_teacher")


class TeacherEvaluationInline(admin.TabularInline):
    model = TeacherEvaluation
    extra = 0
    readonly_fields = ("evaluator", "evaluation_date", "score", "status")
    can_delete = False
    fields = ("evaluation_date", "evaluator", "score", "status", "followup_date")
    ordering = ("-evaluation_date",)
    max_num = 5
    verbose_name = "Recent Evaluation"
    verbose_name_plural = "Recent Evaluations"


@admin.register(Teacher)
class TeacherAdmin(admin.ModelAdmin):
    list_display = (
        "employee_id",
        "get_full_name",
        "department",
        "position",
        "status_with_badge",
        "experience_years",
        "joining_date",
        "get_avg_score",
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
    autocomplete_fields = ["user", "department"]
    fieldsets = (
        (
            "Basic Information",
            {"fields": ("user", "employee_id", "status", "joining_date")},
        ),
        (
            "Professional Details",
            {"fields": ("department", "position", "contract_type", "salary")},
        ),
        (
            "Qualifications",
            {"fields": ("qualification", "specialization", "experience_years")},
        ),
        (
            "Additional Information",
            {
                "fields": ("bio", "emergency_contact", "emergency_phone"),
                "classes": ("collapse",),
            },
        ),
    )

    def get_full_name(self, obj):
        return obj.get_full_name()

    get_full_name.short_description = "Full Name"
    get_full_name.admin_order_field = "user__first_name"

    def status_with_badge(self, obj):
        colors = {"Active": "success", "On Leave": "warning", "Terminated": "danger"}
        color = colors.get(obj.status, "secondary")
        return format_html('<span class="badge bg-{}">{}</span>', color, obj.status)

    status_with_badge.short_description = "Status"
    status_with_badge.admin_order_field = "status"

    def get_avg_score(self, obj):
        avg_score = obj.evaluations.aggregate(avg=Avg("score"))["avg"]
        if avg_score:
            color = (
                "success"
                if avg_score >= 80
                else "warning" if avg_score >= 60 else "danger"
            )
            return format_html(
                '<span class="badge bg-{}">{:.1f}%</span>', color, avg_score
            )
        return "-"

    get_avg_score.short_description = "Avg. Score"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("user", "department")


@admin.register(TeacherClassAssignment)
class TeacherClassAssignmentAdmin(admin.ModelAdmin):
    list_display = (
        "teacher",
        "class_instance",
        "subject",
        "academic_year",
        "is_class_teacher",
    )
    list_filter = (
        "academic_year",
        "is_class_teacher",
        "subject",
        "teacher__department",
    )
    search_fields = (
        "teacher__user__first_name",
        "teacher__user__last_name",
        "class_instance__grade__name",
        "subject__name",
    )
    autocomplete_fields = ["teacher", "class_instance", "subject", "academic_year"]
    date_hierarchy = "created_at"

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related(
                "teacher", "teacher__user", "class_instance", "subject", "academic_year"
            )
        )


@admin.register(TeacherEvaluation)
class TeacherEvaluationAdmin(admin.ModelAdmin):
    list_display = (
        "teacher",
        "evaluator",
        "evaluation_date",
        "score_with_badge",
        "status",
        "followup_required",
    )
    list_filter = ("evaluation_date", "status", "teacher__department")
    search_fields = ("teacher__user__first_name", "teacher__user__last_name", "remarks")
    date_hierarchy = "evaluation_date"
    readonly_fields = ("created_at", "updated_at")
    autocomplete_fields = ["teacher", "evaluator"]
    fieldsets = (
        (
            "Evaluation Details",
            {"fields": ("teacher", "evaluator", "evaluation_date", "status")},
        ),
        ("Scores", {"fields": ("score", "criteria")}),
        ("Comments", {"fields": ("remarks", "followup_actions", "followup_date")}),
        (
            "System",
            {
                "fields": ("created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    def score_with_badge(self, obj):
        color = (
            "success" if obj.score >= 80 else "warning" if obj.score >= 60 else "danger"
        )
        return format_html('<span class="badge bg-{}">{:.1f}%</span>', color, obj.score)

    score_with_badge.short_description = "Score"
    score_with_badge.admin_order_field = "score"

    def followup_required(self, obj):
        if obj.is_followup_required():
            if obj.is_followup_overdue():
                return format_html('<span class="badge bg-danger">Overdue</span>')
            return format_html('<span class="badge bg-warning">Required</span>')
        return format_html('<span class="badge bg-success">No</span>')

    followup_required.short_description = "Followup"

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("teacher", "teacher__user", "evaluator")
        )
