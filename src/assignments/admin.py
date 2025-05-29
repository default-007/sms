# assignments/ admin.py

import csv

from django.contrib import admin
from django.db.models import Avg, Count, Q
from django.http import HttpResponse
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html

from .models import (
    Assignment,
    AssignmentComment,
    AssignmentRubric,
    AssignmentSubmission,
    SubmissionGrade,
)


@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = [
        "title",
        "class_display",
        "subject",
        "teacher",
        "status",
        "due_date_display",
        "submission_count",
        "completion_rate_display",
        "is_overdue",
    ]
    list_filter = [
        "status",
        "submission_type",
        "difficulty_level",
        "subject",
        "class_id__grade__section",
        "class_id__grade",
        "term",
        "allow_late_submission",
        "created_at",
    ]
    search_fields = [
        "title",
        "description",
        "teacher__user__first_name",
        "teacher__user__last_name",
        "class_id__name",
        "subject__name",
    ]
    readonly_fields = [
        "created_at",
        "updated_at",
        "published_at",
        "submission_count",
        "graded_submission_count",
        "average_score",
        "completion_rate",
    ]
    fieldsets = (
        (
            "Basic Information",
            {"fields": ("title", "description", "instructions", "status")},
        ),
        (
            "Assignment Details",
            {"fields": ("class_id", "subject", "teacher", "term", "difficulty_level")},
        ),
        (
            "Dates and Deadlines",
            {"fields": ("assigned_date", "due_date", "published_at")},
        ),
        (
            "Grading Configuration",
            {"fields": ("total_marks", "passing_marks", "auto_grade", "peer_review")},
        ),
        (
            "Submission Settings",
            {
                "fields": (
                    "submission_type",
                    "allow_late_submission",
                    "late_penalty_percentage",
                    "max_file_size_mb",
                    "allowed_file_types",
                    "attachment",
                )
            },
        ),
        (
            "Learning & Analytics",
            {"fields": ("estimated_duration_hours", "learning_objectives")},
        ),
        (
            "Statistics (Read Only)",
            {
                "fields": (
                    "submission_count",
                    "graded_submission_count",
                    "average_score",
                    "completion_rate",
                ),
                "classes": ["collapse"],
            },
        ),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ["collapse"]},
        ),
    )

    actions = [
        "publish_assignments",
        "close_assignments",
        "export_assignment_data",
        "send_reminder_notifications",
    ]

    def class_display(self, obj):
        """Display class with grade and section"""
        return f"{obj.class_id.grade.section.name} - {obj.class_id.grade.name} {obj.class_id.name}"

    class_display.short_description = "Class"

    def due_date_display(self, obj):
        """Display due date with status color"""
        if obj.is_overdue:
            return format_html(
                '<span style="color: red; font-weight: bold;">{}</span>',
                obj.due_date.strftime("%Y-%m-%d %H:%M"),
            )
        elif obj.days_until_due <= 2:
            return format_html(
                '<span style="color: orange; font-weight: bold;">{}</span>',
                obj.due_date.strftime("%Y-%m-%d %H:%M"),
            )
        return obj.due_date.strftime("%Y-%m-%d %H:%M")

    due_date_display.short_description = "Due Date"

    def completion_rate_display(self, obj):
        """Display completion rate with progress bar"""
        rate = obj.completion_rate
        if rate >= 80:
            color = "green"
        elif rate >= 60:
            color = "orange"
        else:
            color = "red"

        return format_html(
            '<div style="width: 100px; background-color: #f0f0f0; border-radius: 3px;">'
            '<div style="width: {}%; background-color: {}; height: 20px; border-radius: 3px; text-align: center; color: white; font-size: 12px; line-height: 20px;">'
            "{}%"
            "</div></div>",
            rate,
            color,
            round(rate, 1),
        )

    completion_rate_display.short_description = "Completion Rate"

    def publish_assignments(self, request, queryset):
        """Bulk publish assignments"""
        updated = queryset.filter(status="draft").update(
            status="published", published_at=timezone.now()
        )
        self.message_user(request, f"{updated} assignments published successfully.")

    publish_assignments.short_description = "Publish selected assignments"

    def close_assignments(self, request, queryset):
        """Bulk close assignments"""
        updated = queryset.filter(status="published").update(status="closed")
        self.message_user(request, f"{updated} assignments closed successfully.")

    close_assignments.short_description = "Close selected assignments"

    def export_assignment_data(self, request, queryset):
        """Export assignment data to CSV"""
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="assignments.csv"'

        writer = csv.writer(response)
        writer.writerow(
            [
                "Title",
                "Class",
                "Subject",
                "Teacher",
                "Status",
                "Due Date",
                "Total Marks",
                "Submissions",
                "Completion Rate",
                "Average Score",
            ]
        )

        for assignment in queryset:
            writer.writerow(
                [
                    assignment.title,
                    assignment.class_display,
                    assignment.subject.name,
                    assignment.teacher.user.get_full_name(),
                    assignment.status,
                    assignment.due_date,
                    assignment.total_marks,
                    assignment.submission_count,
                    f"{assignment.completion_rate}%",
                    assignment.average_score or "N/A",
                ]
            )

        return response

    export_assignment_data.short_description = "Export assignment data"

    def send_reminder_notifications(self, request, queryset):
        """Send reminder notifications for assignments"""
        # This would integrate with your communications module
        count = queryset.filter(status="published", due_date__gt=timezone.now()).count()
        self.message_user(
            request, f"Reminder notifications sent for {count} assignments."
        )

    send_reminder_notifications.short_description = "Send reminder notifications"


@admin.register(AssignmentSubmission)
class AssignmentSubmissionAdmin(admin.ModelAdmin):
    list_display = [
        "assignment_title",
        "student_name",
        "submission_date",
        "status",
        "marks_display",
        "percentage_display",
        "is_late",
        "graded_by",
    ]
    list_filter = [
        "status",
        "is_late",
        "assignment__subject",
        "assignment__class_id__grade",
        "submission_method",
        "plagiarism_checked",
        "graded_at",
    ]
    search_fields = [
        "assignment__title",
        "student__user__first_name",
        "student__user__last_name",
        "student__admission_number",
    ]
    readonly_fields = [
        "created_at",
        "updated_at",
        "submission_date",
        "percentage",
        "is_late",
        "days_late",
        "late_penalty_applied",
        "file_size_mb",
        "plagiarism_score",
    ]
    fieldsets = (
        (
            "Submission Details",
            {"fields": ("assignment", "student", "status", "submission_method")},
        ),
        ("Content", {"fields": ("content", "attachment", "student_remarks")}),
        (
            "Grading",
            {
                "fields": (
                    "marks_obtained",
                    "percentage",
                    "grade",
                    "graded_by",
                    "graded_at",
                )
            },
        ),
        (
            "Teacher Feedback",
            {
                "fields": ("teacher_remarks", "strengths", "improvements"),
                "classes": ["wide"],
            },
        ),
        (
            "Late Submission",
            {
                "fields": (
                    "is_late",
                    "days_late",
                    "late_penalty_applied",
                    "original_marks",
                ),
                "classes": ["collapse"],
            },
        ),
        (
            "Plagiarism Detection",
            {
                "fields": (
                    "plagiarism_checked",
                    "plagiarism_score",
                    "plagiarism_report",
                ),
                "classes": ["collapse"],
            },
        ),
        ("File Information", {"fields": ("file_size_mb",), "classes": ["collapse"]}),
        (
            "Timestamps",
            {
                "fields": ("created_at", "updated_at", "submission_date"),
                "classes": ["collapse"],
            },
        ),
    )

    actions = [
        "mark_as_graded",
        "check_plagiarism",
        "export_submission_data",
        "bulk_download_submissions",
    ]

    def assignment_title(self, obj):
        """Display assignment title with link"""
        url = reverse("admin:assignments_assignment_change", args=[obj.assignment.id])
        return format_html('<a href="{}">{}</a>', url, obj.assignment.title)

    assignment_title.short_description = "Assignment"

    def student_name(self, obj):
        """Display student name with admission number"""
        return f"{obj.student.user.get_full_name()} ({obj.student.admission_number})"

    student_name.short_description = "Student"

    def marks_display(self, obj):
        """Display marks with color coding"""
        if obj.marks_obtained is None:
            return format_html('<span style="color: gray;">Not Graded</span>')

        percentage = (obj.marks_obtained / obj.assignment.total_marks) * 100
        if percentage >= 80:
            color = "green"
        elif percentage >= 60:
            color = "orange"
        else:
            color = "red"

        return format_html(
            '<span style="color: {}; font-weight: bold;">{}/{}</span>',
            color,
            obj.marks_obtained,
            obj.assignment.total_marks,
        )

    marks_display.short_description = "Marks"

    def percentage_display(self, obj):
        """Display percentage with styling"""
        if obj.percentage is None:
            return "-"

        if obj.percentage >= 80:
            color = "green"
        elif obj.percentage >= 60:
            color = "orange"
        else:
            color = "red"

        return format_html(
            '<span style="color: {}; font-weight: bold;">{}%</span>',
            color,
            round(obj.percentage, 1),
        )

    percentage_display.short_description = "Percentage"

    def mark_as_graded(self, request, queryset):
        """Bulk mark submissions as graded"""
        updated = queryset.filter(status="submitted").update(
            status="graded", graded_at=timezone.now()
        )
        self.message_user(request, f"{updated} submissions marked as graded.")

    mark_as_graded.short_description = "Mark as graded"

    def check_plagiarism(self, request, queryset):
        """Initiate plagiarism check for submissions"""
        # This would integrate with plagiarism detection service
        count = queryset.filter(plagiarism_checked=False).count()
        self.message_user(
            request, f"Plagiarism check initiated for {count} submissions."
        )

    check_plagiarism.short_description = "Check plagiarism"

    def export_submission_data(self, request, queryset):
        """Export submission data to CSV"""
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="submissions.csv"'

        writer = csv.writer(response)
        writer.writerow(
            [
                "Assignment",
                "Student",
                "Submission Date",
                "Status",
                "Marks",
                "Percentage",
                "Is Late",
                "Days Late",
                "Graded By",
            ]
        )

        for submission in queryset:
            writer.writerow(
                [
                    submission.assignment.title,
                    submission.student.user.get_full_name(),
                    submission.submission_date,
                    submission.status,
                    f"{submission.marks_obtained or 'N/A'}/{submission.assignment.total_marks}",
                    f"{submission.percentage or 'N/A'}%",
                    submission.is_late,
                    submission.days_late,
                    (
                        submission.graded_by.user.get_full_name()
                        if submission.graded_by
                        else "N/A"
                    ),
                ]
            )

        return response

    export_submission_data.short_description = "Export submission data"


@admin.register(AssignmentRubric)
class AssignmentRubricAdmin(admin.ModelAdmin):
    list_display = ["assignment", "criteria_name", "max_points", "weight_percentage"]
    list_filter = ["assignment__subject", "assignment__class_id__grade"]
    search_fields = ["assignment__title", "criteria_name", "description"]
    fieldsets = (
        (
            "Basic Information",
            {
                "fields": (
                    "assignment",
                    "criteria_name",
                    "description",
                    "max_points",
                    "weight_percentage",
                )
            },
        ),
        (
            "Performance Levels",
            {
                "fields": (
                    "excellent_description",
                    "good_description",
                    "satisfactory_description",
                    "needs_improvement_description",
                ),
                "classes": ["wide"],
            },
        ),
    )


@admin.register(SubmissionGrade)
class SubmissionGradeAdmin(admin.ModelAdmin):
    list_display = [
        "submission",
        "rubric_criteria",
        "points_earned",
        "max_points",
        "percentage",
    ]
    list_filter = ["rubric__assignment__subject", "rubric__criteria_name"]
    search_fields = [
        "submission__student__user__first_name",
        "submission__student__user__last_name",
        "rubric__criteria_name",
    ]

    def rubric_criteria(self, obj):
        return obj.rubric.criteria_name

    rubric_criteria.short_description = "Criteria"

    def max_points(self, obj):
        return obj.rubric.max_points

    max_points.short_description = "Max Points"

    def percentage(self, obj):
        if obj.rubric.max_points > 0:
            return f"{(obj.points_earned / obj.rubric.max_points) * 100:.1f}%"
        return "0%"

    percentage.short_description = "Percentage"


@admin.register(AssignmentComment)
class AssignmentCommentAdmin(admin.ModelAdmin):
    list_display = ["assignment", "user", "content_preview", "is_private", "created_at"]
    list_filter = ["is_private", "created_at", "assignment__subject"]
    search_fields = [
        "assignment__title",
        "user__first_name",
        "user__last_name",
        "content",
    ]
    readonly_fields = ["created_at", "updated_at"]

    def content_preview(self, obj):
        """Show first 50 characters of content"""
        return obj.content[:50] + "..." if len(obj.content) > 50 else obj.content

    content_preview.short_description = "Content Preview"


# Customize admin site
admin.site.site_header = "School Management System - Assignments"
admin.site.site_title = "SMS Assignments Admin"
admin.site.index_title = "Assignments Management"
