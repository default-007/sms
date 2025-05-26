"""
School Management System - Exam Admin Configuration
File: src/exams/admin.py
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.db.models import Count, Avg
from django.utils import timezone

from .models import (
    ExamType,
    Exam,
    ExamSchedule,
    StudentExamResult,
    ReportCard,
    GradingSystem,
    GradeScale,
    ExamQuestion,
    OnlineExam,
    OnlineExamQuestion,
    StudentOnlineExamAttempt,
)


@admin.register(ExamType)
class ExamTypeAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "contribution_percentage",
        "frequency",
        "is_term_based",
        "is_online",
        "max_attempts",
        "is_active",
        "created_at",
    ]
    list_filter = ["is_term_based", "frequency", "is_online", "is_active"]
    search_fields = ["name", "description"]
    ordering = ["contribution_percentage", "name"]
    readonly_fields = ["created_at", "updated_at"]

    fieldsets = (
        (
            "Basic Information",
            {"fields": ("name", "description", "contribution_percentage")},
        ),
        (
            "Configuration",
            {
                "fields": (
                    "is_term_based",
                    "frequency",
                    "max_attempts",
                    "is_online",
                    "duration_minutes",
                )
            },
        ),
        ("Status", {"fields": ("is_active",)}),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )


class ExamScheduleInline(admin.TabularInline):
    model = ExamSchedule
    extra = 0
    fields = [
        "class_obj",
        "subject",
        "date",
        "start_time",
        "end_time",
        "total_marks",
        "passing_marks",
        "supervisor",
        "is_completed",
    ]
    readonly_fields = ["is_completed"]


@admin.register(Exam)
class ExamAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "exam_type",
        "academic_year",
        "term",
        "start_date",
        "end_date",
        "status",
        "completion_rate_display",
        "is_published",
    ]
    list_filter = [
        "exam_type",
        "academic_year",
        "term",
        "status",
        "is_published",
        "start_date",
    ]
    search_fields = ["name", "description"]
    date_hierarchy = "start_date"
    ordering = ["-start_date", "name"]
    readonly_fields = [
        "total_students",
        "completed_count",
        "completion_rate",
        "is_active",
        "created_at",
        "updated_at",
    ]
    inlines = [ExamScheduleInline]

    fieldsets = (
        (
            "Basic Information",
            {"fields": ("name", "exam_type", "academic_year", "term")},
        ),
        ("Schedule", {"fields": ("start_date", "end_date")}),
        ("Content", {"fields": ("description", "instructions")}),
        ("Grading", {"fields": ("grading_system", "passing_percentage")}),
        ("Status", {"fields": ("status", "is_published", "publish_results")}),
        (
            "Statistics",
            {
                "fields": (
                    "total_students",
                    "completed_count",
                    "completion_rate",
                    "is_active",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Meta",
            {
                "fields": ("created_by", "created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    def completion_rate_display(self, obj):
        rate = obj.completion_rate
        if rate >= 80:
            color = "green"
        elif rate >= 50:
            color = "orange"
        else:
            color = "red"
        return format_html('<span style="color: {};">{:.1f}%</span>', color, rate)

    completion_rate_display.short_description = "Completion Rate"

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("exam_type", "academic_year", "term", "created_by")
        )


@admin.register(ExamSchedule)
class ExamScheduleAdmin(admin.ModelAdmin):
    list_display = [
        "exam",
        "class_obj",
        "subject",
        "date",
        "start_time",
        "total_marks",
        "supervisor",
        "results_count",
        "is_completed",
    ]
    list_filter = [
        "exam__academic_year",
        "exam__term",
        "subject",
        "supervisor",
        "date",
        "is_completed",
        "is_active",
    ]
    search_fields = [
        "exam__name",
        "class_obj__name",
        "subject__name",
        "supervisor__user__first_name",
        "supervisor__user__last_name",
    ]
    date_hierarchy = "date"
    ordering = ["date", "start_time"]
    readonly_fields = ["results_count", "created_at", "updated_at"]
    filter_horizontal = ["additional_supervisors"]

    fieldsets = (
        ("Exam Details", {"fields": ("exam", "class_obj", "subject")}),
        (
            "Schedule",
            {"fields": ("date", "start_time", "end_time", "duration_minutes", "room")},
        ),
        ("Supervision", {"fields": ("supervisor", "additional_supervisors")}),
        ("Marking", {"fields": ("total_marks", "passing_marks")}),
        ("Instructions", {"fields": ("special_instructions", "materials_allowed")}),
        ("Status", {"fields": ("is_active", "is_completed")}),
        ("Statistics", {"fields": ("results_count",), "classes": ("collapse",)}),
        ("Meta", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )

    def results_count(self, obj):
        count = obj.student_results.count()
        if count > 0:
            url = reverse("admin:exams_studentexamresult_changelist")
            return format_html(
                '<a href="{}?exam_schedule__id__exact={}">{} results</a>',
                url,
                obj.id,
                count,
            )
        return "No results"

    results_count.short_description = "Results Entered"

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("exam", "class_obj", "subject", "supervisor__user")
            .prefetch_related("additional_supervisors")
        )


@admin.register(StudentExamResult)
class StudentExamResultAdmin(admin.ModelAdmin):
    list_display = [
        "student_name",
        "exam_name",
        "subject_name",
        "marks_display",
        "percentage",
        "grade",
        "is_pass",
        "class_rank",
        "entry_date",
    ]
    list_filter = [
        "exam_schedule__exam__academic_year",
        "exam_schedule__exam__term",
        "exam_schedule__subject",
        "grade",
        "is_pass",
        "is_absent",
        "is_exempted",
    ]
    search_fields = [
        "student__user__first_name",
        "student__user__last_name",
        "student__admission_number",
        "exam_schedule__exam__name",
    ]
    ordering = ["-entry_date", "-percentage"]
    readonly_fields = [
        "percentage",
        "grade",
        "is_pass",
        "class_rank",
        "grade_rank",
        "entry_date",
        "last_modified_at",
    ]

    fieldsets = (
        ("Student & Exam", {"fields": ("student", "exam_schedule", "term")}),
        ("Marks", {"fields": ("marks_obtained", "percentage", "grade", "grade_point")}),
        ("Status", {"fields": ("is_pass", "is_absent", "is_exempted")}),
        ("Comments", {"fields": ("remarks", "teacher_comments")}),
        (
            "Rankings",
            {"fields": ("class_rank", "grade_rank"), "classes": ("collapse",)},
        ),
        (
            "Meta",
            {
                "fields": (
                    "entered_by",
                    "entry_date",
                    "last_modified_by",
                    "last_modified_at",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    def student_name(self, obj):
        return obj.student.user.get_full_name()

    student_name.short_description = "Student"

    def exam_name(self, obj):
        return obj.exam_schedule.exam.name

    exam_name.short_description = "Exam"

    def subject_name(self, obj):
        return obj.exam_schedule.subject.name

    subject_name.short_description = "Subject"

    def marks_display(self, obj):
        return f"{obj.marks_obtained}/{obj.exam_schedule.total_marks}"

    marks_display.short_description = "Marks"

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related(
                "student__user",
                "exam_schedule__exam",
                "exam_schedule__subject",
                "entered_by",
                "last_modified_by",
            )
        )


@admin.register(ReportCard)
class ReportCardAdmin(admin.ModelAdmin):
    list_display = [
        "student_name",
        "class_name",
        "term_name",
        "percentage",
        "grade",
        "class_rank_display",
        "attendance_percentage",
        "status",
    ]
    list_filter = [
        "academic_year",
        "term",
        "class_obj__grade",
        "grade",
        "status",
        "generation_date",
    ]
    search_fields = [
        "student__user__first_name",
        "student__user__last_name",
        "student__admission_number",
    ]
    ordering = ["-generation_date", "class_rank"]
    readonly_fields = [
        "total_marks",
        "marks_obtained",
        "percentage",
        "grade",
        "grade_point_average",
        "class_rank",
        "class_size",
        "grade_rank",
        "grade_size",
        "rank_suffix",
        "generation_date",
    ]

    fieldsets = (
        ("Student Info", {"fields": ("student", "class_obj", "academic_year", "term")}),
        (
            "Academic Performance",
            {
                "fields": (
                    "total_marks",
                    "marks_obtained",
                    "percentage",
                    "grade",
                    "grade_point_average",
                )
            },
        ),
        (
            "Rankings",
            {"fields": ("class_rank", "class_size", "grade_rank", "grade_size")},
        ),
        (
            "Attendance",
            {
                "fields": (
                    "attendance_percentage",
                    "days_present",
                    "days_absent",
                    "total_days",
                )
            },
        ),
        (
            "Comments",
            {
                "fields": (
                    "class_teacher_remarks",
                    "principal_remarks",
                    "achievements",
                    "areas_for_improvement",
                )
            },
        ),
        ("Status", {"fields": ("status", "generation_date", "published_date")}),
    )

    def student_name(self, obj):
        return obj.student.user.get_full_name()

    student_name.short_description = "Student"

    def class_name(self, obj):
        return str(obj.class_obj)

    class_name.short_description = "Class"

    def term_name(self, obj):
        return obj.term.name

    term_name.short_description = "Term"

    def class_rank_display(self, obj):
        return f"{obj.rank_suffix} of {obj.class_size}"

    class_rank_display.short_description = "Class Rank"

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("student__user", "class_obj", "academic_year", "term")
        )


class GradeScaleInline(admin.TabularInline):
    model = GradeScale
    extra = 1
    ordering = ["-min_percentage"]


@admin.register(GradingSystem)
class GradingSystemAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "academic_year",
        "is_default",
        "is_active",
        "grade_scales_count",
        "created_at",
    ]
    list_filter = ["academic_year", "is_default", "is_active"]
    search_fields = ["name", "description"]
    ordering = ["-created_at"]
    inlines = [GradeScaleInline]

    def grade_scales_count(self, obj):
        return obj.grade_scales.count()

    grade_scales_count.short_description = "Grade Scales"


@admin.register(ExamQuestion)
class ExamQuestionAdmin(admin.ModelAdmin):
    list_display = [
        "question_preview",
        "subject",
        "grade",
        "question_type",
        "difficulty_level",
        "marks",
        "usage_count",
        "is_active",
    ]
    list_filter = [
        "subject",
        "grade",
        "question_type",
        "difficulty_level",
        "marks",
        "is_active",
        "created_at",
    ]
    search_fields = ["question_text", "topic", "learning_objective"]
    ordering = ["-created_at"]
    readonly_fields = ["usage_count", "created_at", "updated_at"]

    fieldsets = (
        (
            "Question Details",
            {"fields": ("subject", "grade", "question_text", "question_type")},
        ),
        ("Difficulty & Marking", {"fields": ("difficulty_level", "marks")}),
        (
            "Answer Options",
            {
                "fields": ("options", "correct_answer", "explanation"),
                "description": "For MCQ questions, provide options as JSON array",
            },
        ),
        ("Categorization", {"fields": ("topic", "learning_objective")}),
        ("Status", {"fields": ("is_active", "usage_count")}),
        (
            "Meta",
            {
                "fields": ("created_by", "created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    def question_preview(self, obj):
        return (
            obj.question_text[:100] + "..."
            if len(obj.question_text) > 100
            else obj.question_text
        )

    question_preview.short_description = "Question"

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("subject", "grade", "created_by")
        )


class OnlineExamQuestionInline(admin.TabularInline):
    model = OnlineExamQuestion
    extra = 0
    ordering = ["order"]
    fields = ["question", "order", "marks"]


@admin.register(OnlineExam)
class OnlineExamAdmin(admin.ModelAdmin):
    list_display = [
        "exam_schedule",
        "questions_count",
        "time_limit_minutes",
        "max_attempts",
        "enable_proctoring",
        "created_at",
    ]
    list_filter = [
        "exam_schedule__exam__academic_year",
        "enable_proctoring",
        "shuffle_questions",
        "show_results_immediately",
    ]
    search_fields = ["exam_schedule__exam__name", "exam_schedule__subject__name"]
    ordering = ["-created_at"]
    readonly_fields = ["questions_count", "total_marks", "created_at", "updated_at"]
    inlines = [OnlineExamQuestionInline]

    fieldsets = (
        (
            "Exam Configuration",
            {"fields": ("exam_schedule", "time_limit_minutes", "max_attempts")},
        ),
        (
            "Question Settings",
            {
                "fields": (
                    "shuffle_questions",
                    "shuffle_options",
                    "show_results_immediately",
                )
            },
        ),
        (
            "Proctoring",
            {"fields": ("enable_proctoring", "webcam_required", "fullscreen_required")},
        ),
        ("Access Control", {"fields": ("access_code", "ip_restrictions")}),
        (
            "Statistics",
            {"fields": ("questions_count", "total_marks"), "classes": ("collapse",)},
        ),
        ("Meta", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )

    def questions_count(self, obj):
        return obj.questions.count()

    questions_count.short_description = "Questions"

    def total_marks(self, obj):
        return sum(q.marks for q in obj.onlineexamquestion_set.all())

    total_marks.short_description = "Total Marks"


@admin.register(StudentOnlineExamAttempt)
class StudentOnlineExamAttemptAdmin(admin.ModelAdmin):
    list_display = [
        "student_name",
        "exam_name",
        "attempt_number",
        "status",
        "marks_display",
        "start_time",
        "time_taken",
        "violation_count",
    ]
    list_filter = [
        "online_exam__exam_schedule__exam__academic_year",
        "status",
        "is_graded",
        "start_time",
    ]
    search_fields = [
        "student__user__first_name",
        "student__user__last_name",
        "online_exam__exam_schedule__exam__name",
    ]
    ordering = ["-start_time"]
    readonly_fields = [
        "start_time",
        "time_taken_display",
        "percentage",
        "auto_graded_marks",
        "violation_count",
    ]

    fieldsets = (
        (
            "Attempt Info",
            {"fields": ("student", "online_exam", "attempt_number", "status")},
        ),
        (
            "Timing",
            {
                "fields": (
                    "start_time",
                    "submit_time",
                    "time_remaining_seconds",
                    "time_taken_display",
                )
            },
        ),
        ("Responses", {"fields": ("responses",), "classes": ("collapse",)}),
        (
            "Scoring",
            {
                "fields": (
                    "total_marks",
                    "marks_obtained",
                    "auto_graded_marks",
                    "manual_graded_marks",
                    "percentage",
                    "is_graded",
                )
            },
        ),
        (
            "Proctoring",
            {
                "fields": ("proctoring_data", "violation_count"),
                "classes": ("collapse",),
            },
        ),
    )

    def student_name(self, obj):
        return obj.student.user.get_full_name()

    student_name.short_description = "Student"

    def exam_name(self, obj):
        return obj.online_exam.exam_schedule.exam.name

    exam_name.short_description = "Exam"

    def marks_display(self, obj):
        return f"{obj.marks_obtained}/{obj.total_marks}"

    marks_display.short_description = "Marks"

    def time_taken(self, obj):
        if obj.submit_time and obj.start_time:
            delta = obj.submit_time - obj.start_time
            return f"{int(delta.total_seconds() / 60)} min"
        return "-"

    time_taken.short_description = "Time Taken"

    def time_taken_display(self, obj):
        return self.time_taken(obj)

    time_taken_display.short_description = "Time Taken"

    def percentage(self, obj):
        if obj.total_marks > 0:
            return f"{(obj.marks_obtained / obj.total_marks) * 100:.1f}%"
        return "0%"

    percentage.short_description = "Percentage"

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("student__user", "online_exam__exam_schedule__exam")
        )


# Custom admin site configurations
admin.site.site_header = "School Management System - Exams"
admin.site.site_title = "SMS Exams Admin"
admin.site.index_title = "Exams Administration"
