import json
from datetime import datetime, timedelta

from django import template
from django.contrib.humanize.templatetags.humanize import naturaltime
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html, mark_safe

from ..models import Assignment, AssignmentSubmission
from src.assignments.services.deadline_service import DeadlineService

register = template.Library()


@register.simple_tag
def assignment_status_badge(assignment):
    """
    Display status badge for assignment
    """
    status_classes = {
        "draft": "badge-secondary",
        "published": "badge-success",
        "closed": "badge-warning",
        "archived": "badge-dark",
    }

    css_class = status_classes.get(assignment.status, "badge-secondary")

    return format_html(
        '<span class="badge {}">{}</span>', css_class, assignment.get_status_display()
    )


@register.simple_tag
def submission_status_badge(submission):
    """
    Display status badge for submission
    """
    status_classes = {
        "draft": "badge-secondary",
        "submitted": "badge-info",
        "late": "badge-warning",
        "graded": "badge-success",
        "returned": "badge-primary",
    }

    css_class = status_classes.get(submission.status, "badge-secondary")
    icon = ""

    if submission.is_late:
        icon = '<i class="fas fa-clock text-warning"></i> '

    return format_html(
        '<span class="badge {}">{}{}</span>',
        css_class,
        mark_safe(icon),
        submission.get_status_display(),
    )


@register.simple_tag
def assignment_deadline_warning(assignment):
    """
    Display deadline warning based on time remaining
    """
    if assignment.is_overdue:
        return format_html(
            '<span class="text-danger"><i class="fas fa-exclamation-triangle"></i> Overdue</span>'
        )

    days_until_due = assignment.days_until_due

    if days_until_due <= 1:
        return format_html(
            '<span class="text-danger"><i class="fas fa-clock"></i> Due soon</span>'
        )
    elif days_until_due <= 3:
        return format_html(
            '<span class="text-warning"><i class="fas fa-clock"></i> Due in {} days</span>',
            days_until_due,
        )
    else:
        return format_html(
            '<span class="text-muted"><i class="fas fa-clock"></i> Due in {} days</span>',
            days_until_due,
        )


@register.simple_tag
def grade_badge(percentage):
    """
    Display grade badge based on percentage
    """
    if percentage is None:
        return format_html('<span class="badge badge-secondary">Not Graded</span>')

    if percentage >= 90:
        grade = "A+"
        css_class = "badge-success"
    elif percentage >= 85:
        grade = "A"
        css_class = "badge-success"
    elif percentage >= 80:
        grade = "A-"
        css_class = "badge-success"
    elif percentage >= 75:
        grade = "B+"
        css_class = "badge-info"
    elif percentage >= 70:
        grade = "B"
        css_class = "badge-info"
    elif percentage >= 65:
        grade = "B-"
        css_class = "badge-info"
    elif percentage >= 60:
        grade = "C+"
        css_class = "badge-warning"
    elif percentage >= 55:
        grade = "C"
        css_class = "badge-warning"
    elif percentage >= 50:
        grade = "C-"
        css_class = "badge-warning"
    elif percentage >= 45:
        grade = "D"
        css_class = "badge-danger"
    else:
        grade = "F"
        css_class = "badge-danger"

    return format_html(
        '<span class="badge {}">{} ({}%)</span>', css_class, grade, round(percentage, 1)
    )


@register.simple_tag
def progress_bar(current, total, css_class="progress-bar-primary"):
    """
    Display progress bar
    """
    if total == 0:
        percentage = 0
    else:
        percentage = (current / total) * 100

    return format_html(
        '<div class="progress">'
        '<div class="progress-bar {}" role="progressbar" style="width: {}%" '
        'aria-valuenow="{}" aria-valuemin="0" aria-valuemax="{}">'
        "{}/{}"
        "</div>"
        "</div>",
        css_class,
        percentage,
        current,
        total,
        current,
        total,
    )


@register.simple_tag
def assignment_completion_bar(assignment):
    """
    Display assignment completion progress bar
    """
    total_students = assignment.class_id.students.filter(status="active").count()
    submitted_count = assignment.submission_count

    if total_students == 0:
        return format_html('<span class="text-muted">No students in class</span>')

    percentage = (submitted_count / total_students) * 100

    if percentage >= 80:
        css_class = "progress-bar bg-success"
    elif percentage >= 60:
        css_class = "progress-bar bg-warning"
    else:
        css_class = "progress-bar bg-danger"

    return format_html(
        '<div class="progress" style="height: 20px;">'
        '<div class="{}" role="progressbar" style="width: {}%" '
        'aria-valuenow="{}" aria-valuemin="0" aria-valuemax="{}">'
        "{}/{} ({}%)"
        "</div>"
        "</div>",
        css_class,
        percentage,
        submitted_count,
        total_students,
        submitted_count,
        total_students,
        round(percentage, 1),
    )


@register.filter
def has_submitted(assignment, student):
    """
    Check if student has submitted assignment
    """
    return assignment.is_submitted_by_student(student)


@register.filter
def get_student_submission(assignment, student):
    """
    Get student's submission for assignment
    """
    return assignment.get_student_submission(student)


@register.simple_tag
def assignment_difficulty_icon(difficulty):
    """
    Display difficulty icon
    """
    icons = {
        "easy": '<i class="fas fa-star text-success"></i>',
        "medium": '<i class="fas fa-star text-warning"></i><i class="fas fa-star text-warning"></i>',
        "hard": '<i class="fas fa-star text-danger"></i><i class="fas fa-star text-danger"></i><i class="fas fa-star text-danger"></i>',
    }

    return mark_safe(
        icons.get(difficulty, '<i class="fas fa-question text-muted"></i>')
    )


@register.simple_tag
def time_until_deadline(assignment):
    """
    Display human-readable time until deadline
    """
    if assignment.is_overdue:
        time_overdue = timezone.now() - assignment.due_date
        return format_html(
            '<span class="text-danger">Overdue by {}</span>',
            naturaltime(assignment.due_date),
        )
    else:
        return format_html(
            '<span class="text-info">Due {}</span>', naturaltime(assignment.due_date)
        )


@register.inclusion_tag("assignments/tags/assignment_card.html")
def assignment_card(assignment, user=None):
    """
    Render assignment card with user-specific context
    """
    context = {"assignment": assignment, "user": user}

    if user and hasattr(user, "student"):
        context["student_submission"] = assignment.get_student_submission(user.student)

    return context


@register.inclusion_tag("assignments/tags/submission_summary.html")
def submission_summary(assignment):
    """
    Render submission summary for an assignment
    """
    submissions = assignment.submissions.all()
    total_students = assignment.class_id.students.filter(status="active").count()

    return {
        "assignment": assignment,
        "total_students": total_students,
        "submitted_count": submissions.count(),
        "graded_count": submissions.filter(status="graded").count(),
        "late_count": submissions.filter(is_late=True).count(),
        "pending_count": submissions.filter(status="submitted").count(),
    }


@register.inclusion_tag("assignments/tags/grade_distribution_chart.html")
def grade_distribution_chart(assignment):
    """
    Render grade distribution chart
    """
    graded_submissions = assignment.submissions.filter(
        status="graded", marks_obtained__isnull=False
    )

    grade_counts = {}
    for submission in graded_submissions:
        grade = submission.calculate_grade()
        grade_counts[grade] = grade_counts.get(grade, 0) + 1

    # Prepare data for chart
    labels = list(grade_counts.keys())
    data = list(grade_counts.values())

    return {
        "assignment": assignment,
        "labels": json.dumps(labels),
        "data": json.dumps(data),
        "total_graded": graded_submissions.count(),
    }


@register.simple_tag
def upcoming_assignments_count(user, days=7):
    """
    Get count of upcoming assignments for user
    """
    try:
        if hasattr(user, "student"):
            deadlines = DeadlineService.get_upcoming_deadlines(
                "student", user.student.id, days
            )
            return len([d for d in deadlines if not d.get("is_submitted", False)])
        elif hasattr(user, "teacher"):
            deadlines = DeadlineService.get_upcoming_deadlines(
                "teacher", user.teacher.id, days
            )
            return len(deadlines)
        return 0
    except:
        return 0


@register.simple_tag
def pending_grading_count(teacher):
    """
    Get count of submissions pending grading for teacher
    """
    try:
        return AssignmentSubmission.objects.filter(
            assignment__teacher=teacher, status="submitted"
        ).count()
    except:
        return 0


@register.filter
def file_icon(filename):
    """
    Return appropriate icon for file type
    """
    if not filename:
        return '<i class="fas fa-file text-muted"></i>'

    extension = filename.split(".")[-1].lower()

    icons = {
        "pdf": '<i class="fas fa-file-pdf text-danger"></i>',
        "doc": '<i class="fas fa-file-word text-primary"></i>',
        "docx": '<i class="fas fa-file-word text-primary"></i>',
        "txt": '<i class="fas fa-file-alt text-muted"></i>',
        "jpg": '<i class="fas fa-file-image text-success"></i>',
        "jpeg": '<i class="fas fa-file-image text-success"></i>',
        "png": '<i class="fas fa-file-image text-success"></i>',
        "zip": '<i class="fas fa-file-archive text-warning"></i>',
        "rar": '<i class="fas fa-file-archive text-warning"></i>',
    }

    return mark_safe(icons.get(extension, '<i class="fas fa-file text-muted"></i>'))


@register.simple_tag
def file_size_human(size_bytes):
    """
    Convert file size to human readable format
    """
    if not size_bytes:
        return "0 B"

    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"


@register.simple_tag
def assignment_action_buttons(assignment, user):
    """
    Generate appropriate action buttons for assignment based on user role
    """
    buttons = []

    if hasattr(user, "teacher") and assignment.teacher == user.teacher:
        # Teacher buttons
        if assignment.status == "draft":
            buttons.append(
                {
                    "url": reverse(
                        "assignments:assignment_edit", kwargs={"pk": assignment.pk}
                    ),
                    "text": "Edit",
                    "class": "btn btn-sm btn-primary",
                    "icon": "fas fa-edit",
                }
            )
            buttons.append(
                {
                    "url": reverse(
                        "assignments:assignment_publish", kwargs={"pk": assignment.pk}
                    ),
                    "text": "Publish",
                    "class": "btn btn-sm btn-success",
                    "icon": "fas fa-paper-plane",
                }
            )

        buttons.append(
            {
                "url": reverse(
                    "assignments:submission_list",
                    kwargs={"assignment_id": assignment.pk},
                ),
                "text": f"Submissions ({assignment.submission_count})",
                "class": "btn btn-sm btn-info",
                "icon": "fas fa-list",
            }
        )

        buttons.append(
            {
                "url": reverse(
                    "assignments:assignment_analytics", kwargs={"pk": assignment.pk}
                ),
                "text": "Analytics",
                "class": "btn btn-sm btn-secondary",
                "icon": "fas fa-chart-bar",
            }
        )

    elif hasattr(user, "student") and assignment.status == "published":
        # Student buttons
        student_submission = assignment.get_student_submission(user.student)

        if student_submission:
            buttons.append(
                {
                    "url": reverse(
                        "assignments:submission_detail",
                        kwargs={"pk": student_submission.pk},
                    ),
                    "text": "View Submission",
                    "class": "btn btn-sm btn-info",
                    "icon": "fas fa-eye",
                }
            )

            if student_submission.status != "graded":
                buttons.append(
                    {
                        "url": reverse(
                            "assignments:submission_edit",
                            kwargs={"pk": student_submission.pk},
                        ),
                        "text": "Edit Submission",
                        "class": "btn btn-sm btn-warning",
                        "icon": "fas fa-edit",
                    }
                )
        else:
            if not assignment.is_overdue or assignment.allow_late_submission:
                buttons.append(
                    {
                        "url": reverse(
                            "assignments:submission_create",
                            kwargs={"assignment_id": assignment.pk},
                        ),
                        "text": "Submit",
                        "class": "btn btn-sm btn-success",
                        "icon": "fas fa-upload",
                    }
                )

    return buttons


@register.inclusion_tag("assignments/tags/assignment_timeline.html")
def assignment_timeline(assignment):
    """
    Render assignment timeline showing key dates and events
    """
    timeline_events = []

    # Assignment created
    timeline_events.append(
        {
            "date": assignment.created_at,
            "title": "Assignment Created",
            "icon": "fas fa-plus-circle",
            "color": "primary",
        }
    )

    # Assignment published
    if assignment.published_at:
        timeline_events.append(
            {
                "date": assignment.published_at,
                "title": "Assignment Published",
                "icon": "fas fa-paper-plane",
                "color": "success",
            }
        )

    # Due date
    timeline_events.append(
        {
            "date": assignment.due_date,
            "title": "Due Date",
            "icon": "fas fa-clock",
            "color": "danger" if assignment.is_overdue else "warning",
            "is_future": assignment.due_date > timezone.now(),
        }
    )

    # First submission
    first_submission = assignment.submissions.order_by("submission_date").first()
    if first_submission:
        timeline_events.append(
            {
                "date": first_submission.submission_date,
                "title": "First Submission Received",
                "icon": "fas fa-upload",
                "color": "info",
            }
        )

    # Sort by date
    timeline_events.sort(key=lambda x: x["date"])

    return {"assignment": assignment, "timeline_events": timeline_events}


@register.simple_tag
def assignment_statistics(assignment):
    """
    Get comprehensive statistics for an assignment
    """
    try:
        analytics = AssignmentService.get_assignment_analytics(assignment.id)
        return analytics
    except:
        return {}


@register.filter
def plagiarism_color(score):
    """
    Return color class based on plagiarism score
    """
    if score is None:
        return "text-muted"

    score = float(score)
    if score > 50:
        return "text-danger"
    elif score > 30:
        return "text-warning"
    elif score > 10:
        return "text-info"
    else:
        return "text-success"


@register.simple_tag
def submission_feedback_summary(submission):
    """
    Generate feedback summary for submission
    """
    summary = []

    if submission.marks_obtained is not None:
        percentage = (
            submission.marks_obtained / submission.assignment.total_marks
        ) * 100
        summary.append(
            f"Score: {submission.marks_obtained}/{submission.assignment.total_marks} ({percentage:.1f}%)"
        )

    if submission.is_late:
        summary.append("Late submission")

    if submission.plagiarism_score and submission.plagiarism_score > 30:
        summary.append(f"High plagiarism score: {submission.plagiarism_score}%")

    return " | ".join(summary) if summary else "No feedback available"


@register.simple_tag(takes_context=True)
def assignment_permissions(context, assignment):
    """
    Check user permissions for assignment actions
    """
    user = context.get("user")
    if not user:
        return {}

    permissions = {
        "can_view": False,
        "can_edit": False,
        "can_delete": False,
        "can_publish": False,
        "can_grade": False,
        "can_submit": False,
    }

    if hasattr(user, "teacher") and assignment.teacher == user.teacher:
        permissions.update(
            {
                "can_view": True,
                "can_edit": assignment.status == "draft",
                "can_delete": not assignment.submissions.exists(),
                "can_publish": assignment.status == "draft",
                "can_grade": True,
            }
        )
    elif (
        hasattr(user, "student")
        and assignment.class_id == user.student.current_class_id
    ):
        permissions.update(
            {
                "can_view": assignment.status == "published",
                "can_submit": (
                    assignment.status == "published"
                    and (not assignment.is_overdue or assignment.allow_late_submission)
                    and not assignment.is_submitted_by_student(user.student)
                ),
            }
        )
    elif hasattr(user, "parent"):
        children_classes = user.parent.children.values_list(
            "current_class_id", flat=True
        )
        if assignment.class_id.id in children_classes:
            permissions["can_view"] = assignment.status == "published"
    elif user.is_staff:
        permissions.update({"can_view": True, "can_edit": True, "can_delete": True})

    return permissions
