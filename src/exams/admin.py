from django.contrib import admin
from .models import (
    ExamType,
    Exam,
    ExamSchedule,
    Quiz,
    Question,
    StudentExamResult,
    StudentQuizAttempt,
    StudentQuizResponse,
    GradingSystem,
    ReportCard,
)


@admin.register(ExamType)
class ExamTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "contribution_percentage", "description")
    search_fields = ("name", "description")
    ordering = ("name",)


class ExamScheduleInline(admin.TabularInline):
    model = ExamSchedule
    extra = 0
    fields = (
        "class_obj",
        "subject",
        "date",
        "start_time",
        "end_time",
        "room",
        "supervisor",
        "status",
    )
    autocomplete_fields = ["class_obj", "subject", "supervisor"]


@admin.register(Exam)
class ExamAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "exam_type",
        "academic_year",
        "start_date",
        "end_date",
        "status",
    )
    list_filter = ("exam_type", "academic_year", "status")
    search_fields = ("name", "description")
    date_hierarchy = "start_date"
    inlines = [ExamScheduleInline]
    autocomplete_fields = ["exam_type", "academic_year", "created_by"]


@admin.register(ExamSchedule)
class ExamScheduleAdmin(admin.ModelAdmin):
    list_display = (
        "exam",
        "class_obj",
        "subject",
        "date",
        "start_time",
        "end_time",
        "status",
    )
    list_filter = ("status", "exam__academic_year", "exam")
    search_fields = ("exam__name", "class_obj__grade__name", "subject__name")
    date_hierarchy = "date"
    autocomplete_fields = ["exam", "class_obj", "subject", "supervisor"]


class QuestionInline(admin.StackedInline):
    model = Question
    extra = 0
    fieldsets = (
        (
            None,
            {"fields": ("question_text", "question_type", "marks", "difficulty_level")},
        ),
        ("Options & Answer", {"fields": ("options", "correct_answer", "explanation")}),
    )


@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "class_obj",
        "subject",
        "teacher",
        "start_datetime",
        "end_datetime",
        "status",
    )
    list_filter = ("status", "class_obj__academic_year", "class_obj", "subject")
    search_fields = (
        "title",
        "description",
        "teacher__user__first_name",
        "teacher__user__last_name",
    )
    date_hierarchy = "start_datetime"
    inlines = [QuestionInline]
    autocomplete_fields = ["class_obj", "subject", "teacher"]


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = (
        "quiz",
        "question_text_short",
        "question_type",
        "marks",
        "difficulty_level",
    )
    list_filter = ("question_type", "difficulty_level", "quiz")
    search_fields = ("question_text", "quiz__title")
    autocomplete_fields = ["quiz"]

    def question_text_short(self, obj):
        return (
            obj.question_text[:50] + "..."
            if len(obj.question_text) > 50
            else obj.question_text
        )

    question_text_short.short_description = "Question"


@admin.register(StudentExamResult)
class StudentExamResultAdmin(admin.ModelAdmin):
    list_display = (
        "student",
        "exam_schedule",
        "marks_obtained",
        "percentage",
        "grade",
        "is_pass",
    )
    list_filter = ("is_pass", "exam_schedule__exam", "exam_schedule__class_obj")
    search_fields = (
        "student__user__first_name",
        "student__user__last_name",
        "student__admission_number",
    )
    autocomplete_fields = ["student", "exam_schedule", "entered_by"]
    readonly_fields = ("percentage", "is_pass")


@admin.register(StudentQuizAttempt)
class StudentQuizAttemptAdmin(admin.ModelAdmin):
    list_display = (
        "student",
        "quiz",
        "start_time",
        "end_time",
        "marks_obtained",
        "percentage",
        "is_pass",
    )
    list_filter = ("is_pass", "quiz", "start_time")
    search_fields = (
        "student__user__first_name",
        "student__user__last_name",
        "quiz__title",
    )
    autocomplete_fields = ["student", "quiz"]
    readonly_fields = ("marks_obtained", "percentage", "is_pass")


@admin.register(StudentQuizResponse)
class StudentQuizResponseAdmin(admin.ModelAdmin):
    list_display = (
        "student_quiz_attempt",
        "question",
        "selected_option",
        "answer_text_short",
        "is_correct",
        "marks_obtained",
    )
    list_filter = ("is_correct", "question__quiz")
    autocomplete_fields = ["student_quiz_attempt", "question"]

    def answer_text_short(self, obj):
        return (
            obj.answer_text[:30] + "..."
            if len(obj.answer_text) > 30
            else obj.answer_text
        )

    answer_text_short.short_description = "Answer"


@admin.register(GradingSystem)
class GradingSystemAdmin(admin.ModelAdmin):
    list_display = (
        "grade_name",
        "academic_year",
        "min_percentage",
        "max_percentage",
        "grade_point",
    )
    list_filter = ("academic_year",)
    search_fields = ("grade_name",)
    ordering = ("academic_year", "-grade_point")
    autocomplete_fields = ["academic_year"]


@admin.register(ReportCard)
class ReportCardAdmin(admin.ModelAdmin):
    list_display = (
        "student",
        "class_obj",
        "academic_year",
        "term",
        "percentage",
        "grade",
        "status",
    )
    list_filter = ("status", "academic_year", "class_obj", "term")
    search_fields = (
        "student__user__first_name",
        "student__user__last_name",
        "student__admission_number",
    )
    readonly_fields = ("generation_date",)
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "student",
                    "class_obj",
                    "academic_year",
                    "term",
                    "generation_date",
                    "status",
                )
            },
        ),
        (
            "Academic Results",
            {
                "fields": (
                    "total_marks",
                    "marks_obtained",
                    "percentage",
                    "grade",
                    "grade_point_average",
                    "rank",
                )
            },
        ),
        (
            "Additional Information",
            {
                "fields": (
                    "attendance_percentage",
                    "remarks",
                    "class_teacher_remarks",
                    "principal_remarks",
                )
            },
        ),
    )
    autocomplete_fields = ["student", "class_obj", "academic_year", "created_by"]
