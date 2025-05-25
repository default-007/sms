# src/teachers/templatetags/teacher_tags.py
"""
Comprehensive template tags for the teachers module.
Provides formatting, display, and utility functions for teacher-related templates.
"""

from django import template
from django.utils.safestring import mark_safe
from django.utils import timezone
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Avg, Count, Q, Sum, Max, Min
from django.core.cache import cache
from django.conf import settings
from datetime import datetime, timedelta, date
import json
import hashlib
from decimal import Decimal
from typing import Dict, List, Any, Optional, Union

from src.teachers.models import Teacher, TeacherEvaluation, TeacherClassAssignment
from src.academics.models import AcademicYear, Department, Term
from src.subjects.models import Subject

register = template.Library()


# =============================================================================
# TEACHER INFORMATION DISPLAY TAGS
# =============================================================================


@register.filter
def teacher_status_badge(status):
    """Return a Bootstrap badge for teacher status with appropriate styling."""
    badges = {
        "Active": '<span class="badge bg-success"><i class="fas fa-check-circle me-1"></i>Active</span>',
        "On Leave": '<span class="badge bg-warning"><i class="fas fa-clock me-1"></i>On Leave</span>',
        "Terminated": '<span class="badge bg-danger"><i class="fas fa-times-circle me-1"></i>Terminated</span>',
        "Suspended": '<span class="badge bg-dark"><i class="fas fa-pause-circle me-1"></i>Suspended</span>',
        "Resigned": '<span class="badge bg-secondary"><i class="fas fa-sign-out-alt me-1"></i>Resigned</span>',
    }
    return mark_safe(
        badges.get(status, f'<span class="badge bg-light text-dark">{status}</span>')
    )


@register.filter
def contract_type_badge(contract_type):
    """Return a Bootstrap badge for contract type."""
    badges = {
        "Permanent": '<span class="badge bg-primary"><i class="fas fa-user-shield me-1"></i>Permanent</span>',
        "Temporary": '<span class="badge bg-info"><i class="fas fa-user-clock me-1"></i>Temporary</span>',
        "Contract": '<span class="badge bg-secondary"><i class="fas fa-file-contract me-1"></i>Contract</span>',
        "Substitute": '<span class="badge bg-warning text-dark"><i class="fas fa-user-plus me-1"></i>Substitute</span>',
        "Part-time": '<span class="badge bg-light text-dark"><i class="fas fa-user-minus me-1"></i>Part-time</span>',
    }
    return mark_safe(
        badges.get(
            contract_type,
            f'<span class="badge bg-light text-dark">{contract_type}</span>',
        )
    )


@register.filter
def performance_badge(score):
    """Return a performance badge based on evaluation score."""
    if score is None:
        return mark_safe('<span class="badge bg-light text-dark">Not Evaluated</span>')

    try:
        score = float(score)
        if score >= 90:
            return mark_safe(
                f'<span class="badge bg-success"><i class="fas fa-star me-1"></i>Excellent ({score:.1f}%)</span>'
            )
        elif score >= 80:
            return mark_safe(
                f'<span class="badge bg-info"><i class="fas fa-thumbs-up me-1"></i>Good ({score:.1f}%)</span>'
            )
        elif score >= 70:
            return mark_safe(
                f'<span class="badge bg-primary"><i class="fas fa-check me-1"></i>Satisfactory ({score:.1f}%)</span>'
            )
        elif score >= 60:
            return mark_safe(
                f'<span class="badge bg-warning"><i class="fas fa-exclamation-triangle me-1"></i>Needs Improvement ({score:.1f}%)</span>'
            )
        else:
            return mark_safe(
                f'<span class="badge bg-danger"><i class="fas fa-times me-1"></i>Poor ({score:.1f}%)</span>'
            )
    except (ValueError, TypeError):
        return mark_safe('<span class="badge bg-secondary">Invalid Score</span>')


@register.filter
def workload_indicator(teacher, academic_year=None):
    """Return workload indicator for teacher with color coding."""
    if not academic_year:
        academic_year = AcademicYear.objects.filter(is_current=True).first()

    if not academic_year:
        return mark_safe('<span class="text-muted">No Data</span>')

    workload = teacher.get_current_workload(academic_year)
    assignment_count = workload["total_assignments"]

    if assignment_count >= 8:
        return mark_safe(
            f'<span class="badge bg-danger"><i class="fas fa-exclamation-triangle me-1"></i>Overloaded ({assignment_count})</span>'
        )
    elif assignment_count >= 6:
        return mark_safe(
            f'<span class="badge bg-warning"><i class="fas fa-clock me-1"></i>Heavy ({assignment_count})</span>'
        )
    elif assignment_count >= 3:
        return mark_safe(
            f'<span class="badge bg-success"><i class="fas fa-check me-1"></i>Balanced ({assignment_count})</span>'
        )
    elif assignment_count >= 1:
        return mark_safe(
            f'<span class="badge bg-info"><i class="fas fa-minus me-1"></i>Light ({assignment_count})</span>'
        )
    else:
        return mark_safe(
            f'<span class="badge bg-secondary"><i class="fas fa-user-slash me-1"></i>No Assignments</span>'
        )


@register.filter
def experience_level_badge(experience_years):
    """Return experience level badge based on years of experience."""
    try:
        years = float(experience_years)
        if years < 2:
            return mark_safe(
                f'<span class="badge bg-light text-dark"><i class="fas fa-seedling me-1"></i>Beginner ({years:.1f}y)</span>'
            )
        elif years < 5:
            return mark_safe(
                f'<span class="badge bg-info"><i class="fas fa-user me-1"></i>Junior ({years:.1f}y)</span>'
            )
        elif years < 10:
            return mark_safe(
                f'<span class="badge bg-primary"><i class="fas fa-user-graduate me-1"></i>Experienced ({years:.1f}y)</span>'
            )
        else:
            return mark_safe(
                f'<span class="badge bg-success"><i class="fas fa-crown me-1"></i>Senior ({years:.1f}y)</span>'
            )
    except (ValueError, TypeError):
        return mark_safe('<span class="badge bg-secondary">Unknown</span>')


@register.filter
def years_of_service(teacher):
    """Calculate and format years of service."""
    years = teacher.get_years_of_service()
    if years == 1:
        return "1 year"
    return f"{years:.1f} years"


@register.filter
def format_teacher_name(teacher, format_type="full"):
    """Format teacher name in various ways."""
    if format_type == "full":
        return teacher.get_full_name()
    elif format_type == "short":
        return teacher.get_short_name()
    elif format_type == "initials":
        first_initial = teacher.user.first_name[0] if teacher.user.first_name else ""
        last_initial = teacher.user.last_name[0] if teacher.user.last_name else ""
        return f"{first_initial}.{last_initial}."
    elif format_type == "last_first":
        return f"{teacher.user.last_name}, {teacher.user.first_name}"
    elif format_type == "formal":
        title = (
            "Dr."
            if "phd" in teacher.qualification.lower()
            or "doctor" in teacher.qualification.lower()
            else "Mr./Ms."
        )
        return f"{title} {teacher.user.last_name}"
    else:
        return teacher.get_full_name()


@register.filter
def teacher_avatar(teacher, size=40):
    """Generate teacher avatar HTML with fallback to initials."""
    if teacher.get_avatar_url():
        return mark_safe(
            f'<img src="{teacher.get_avatar_url()}" '
            f'class="rounded-circle" width="{size}" height="{size}" '
            f'alt="{teacher.get_full_name()}" title="{teacher.get_full_name()}">'
        )
    else:
        # Generate initials avatar with consistent color
        initials = f"{teacher.user.first_name[0] if teacher.user.first_name else ''}{teacher.user.last_name[0] if teacher.user.last_name else ''}"

        # Generate consistent color based on teacher ID
        colors = [
            "bg-primary",
            "bg-success",
            "bg-info",
            "bg-warning",
            "bg-danger",
            "bg-dark",
            "bg-secondary",
        ]
        color = colors[teacher.id % len(colors)]

        return mark_safe(
            f'<div class="rounded-circle d-flex align-items-center justify-content-center {color} text-white" '
            f'style="width: {size}px; height: {size}px; font-size: {size//2.5}px; font-weight: bold;" '
            f'title="{teacher.get_full_name()}">'
            f"{initials}</div>"
        )


# =============================================================================
# EVALUATION AND PERFORMANCE TAGS
# =============================================================================


@register.filter
def evaluation_trend_icon(teacher, months=6):
    """Show trend icon based on recent evaluations."""
    evaluations = teacher.evaluations.filter(
        evaluation_date__gte=timezone.now().date() - timedelta(days=30 * months)
    ).order_by("-evaluation_date")

    if evaluations.count() < 2:
        return mark_safe(
            '<i class="fas fa-minus text-muted" title="Insufficient data for trend analysis"></i>'
        )

    recent_scores = list(evaluations[:3].values_list("score", flat=True))

    if len(recent_scores) >= 2:
        latest_score = float(recent_scores[0])
        previous_score = float(recent_scores[1])

        if latest_score > previous_score + 5:
            return mark_safe(
                '<i class="fas fa-arrow-up text-success" title="Performance improving"></i>'
            )
        elif latest_score < previous_score - 5:
            return mark_safe(
                '<i class="fas fa-arrow-down text-danger" title="Performance declining"></i>'
            )
        else:
            return mark_safe(
                '<i class="fas fa-arrows-alt-h text-info" title="Performance stable"></i>'
            )

    return mark_safe(
        '<i class="fas fa-minus text-muted" title="No trend data available"></i>'
    )


@register.filter
def evaluation_status_badge(status):
    """Return badge for evaluation status."""
    badges = {
        "draft": '<span class="badge bg-secondary"><i class="fas fa-edit me-1"></i>Draft</span>',
        "submitted": '<span class="badge bg-primary"><i class="fas fa-paper-plane me-1"></i>Submitted</span>',
        "reviewed": '<span class="badge bg-info"><i class="fas fa-eye me-1"></i>Reviewed</span>',
        "approved": '<span class="badge bg-success"><i class="fas fa-check me-1"></i>Approved</span>',
        "closed": '<span class="badge bg-dark"><i class="fas fa-archive me-1"></i>Closed</span>',
    }
    return mark_safe(
        badges.get(status, f'<span class="badge bg-light text-dark">{status}</span>')
    )


@register.filter
def is_followup_overdue(evaluation):
    """Check if evaluation followup is overdue."""
    if not evaluation.followup_date or evaluation.status == "closed":
        return False
    return evaluation.followup_date < timezone.now().date()


@register.filter
def days_until_followup(evaluation):
    """Calculate days until followup is due."""
    if not evaluation.followup_date:
        return None

    days = (evaluation.followup_date - timezone.now().date()).days
    return days


@register.filter
def time_since_evaluation(teacher):
    """Get time since last evaluation in human-readable format."""
    latest_eval = teacher.get_latest_evaluation()
    if not latest_eval:
        return "Never evaluated"

    days_ago = (timezone.now().date() - latest_eval.evaluation_date).days

    if days_ago == 0:
        return "Today"
    elif days_ago == 1:
        return "Yesterday"
    elif days_ago < 30:
        return f"{days_ago} days ago"
    elif days_ago < 365:
        months = days_ago // 30
        return f"{months} month{'s' if months > 1 else ''} ago"
    else:
        years = days_ago // 365
        return f"{years} year{'s' if years > 1 else ''} ago"


@register.filter
def performance_color_class(score):
    """Get CSS color class for performance score."""
    if score is None:
        return "text-muted"

    try:
        score = float(score)
        if score >= 90:
            return "text-success"
        elif score >= 80:
            return "text-info"
        elif score >= 70:
            return "text-primary"
        elif score >= 60:
            return "text-warning"
        else:
            return "text-danger"
    except (ValueError, TypeError):
        return "text-muted"


# =============================================================================
# ASSIGNMENT AND WORKLOAD TAGS
# =============================================================================


@register.filter
def teacher_subjects(teacher, academic_year=None):
    """Get subjects taught by teacher."""
    if not academic_year:
        academic_year = AcademicYear.objects.filter(is_current=True).first()

    if not academic_year:
        return []

    return teacher.get_assigned_subjects(academic_year)


@register.filter
def teacher_classes(teacher, academic_year=None):
    """Get classes taught by teacher."""
    if not academic_year:
        academic_year = AcademicYear.objects.filter(is_current=True).first()

    if not academic_year:
        return []

    return teacher.get_assigned_classes(academic_year)


@register.filter
def is_class_teacher(teacher, academic_year=None):
    """Check if teacher is a class teacher for any class."""
    if not academic_year:
        academic_year = AcademicYear.objects.filter(is_current=True).first()

    if not academic_year:
        return False

    return teacher.class_assignments.filter(
        academic_year=academic_year, is_class_teacher=True, is_active=True
    ).exists()


@register.filter
def class_teacher_for(teacher, academic_year=None):
    """Get classes where teacher is the class teacher."""
    if not academic_year:
        academic_year = AcademicYear.objects.filter(is_current=True).first()

    if not academic_year:
        return []

    return teacher.get_class_teacher_classes(academic_year)


# =============================================================================
# DEPARTMENT AND ADMINISTRATIVE TAGS
# =============================================================================


@register.filter
def is_department_head(teacher):
    """Check if teacher is a department head."""
    return teacher.is_department_head()


@register.simple_tag
def get_department_head(department):
    """Get department head teacher."""
    if department and hasattr(department, "head") and department.head:
        return department.head
    return None


@register.simple_tag
def teacher_count_by_status(status=None, department_id=None):
    """Get count of teachers by status and optionally department."""
    queryset = Teacher.objects.all()

    if status:
        queryset = queryset.filter(status=status)

    if department_id:
        queryset = queryset.filter(department_id=department_id)

    return queryset.count()


@register.simple_tag
def department_teacher_stats(department_id):
    """Get teacher statistics for a department."""
    stats = Teacher.objects.filter(department_id=department_id).aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(status="Active")),
        avg_experience=Avg("experience_years"),
        avg_evaluation_score=Avg("average_evaluation_score"),
    )

    return {
        "total": stats["total"] or 0,
        "active": stats["active"] or 0,
        "avg_experience": round(float(stats["avg_experience"] or 0), 1),
        "avg_score": round(float(stats["avg_evaluation_score"] or 0), 1),
    }


# =============================================================================
# ANALYTICS AND SUMMARY TAGS
# =============================================================================


@register.simple_tag
def teacher_performance_summary(academic_year=None, department_id=None):
    """Get overall teacher performance summary."""
    teachers = Teacher.objects.filter(status="Active")

    if department_id:
        teachers = teachers.filter(department_id=department_id)

    if academic_year:
        evaluations = TeacherEvaluation.objects.filter(
            academic_year=academic_year, teacher__in=teachers
        )
    else:
        evaluations = TeacherEvaluation.objects.filter(teacher__in=teachers)

    summary = evaluations.aggregate(
        avg_score=Avg("score"),
        total_evaluations=Count("id"),
        excellent=Count("id", filter=Q(score__gte=90)),
        good=Count("id", filter=Q(score__gte=80, score__lt=90)),
        satisfactory=Count("id", filter=Q(score__gte=70, score__lt=80)),
        needs_improvement=Count("id", filter=Q(score__gte=60, score__lt=70)),
        poor=Count("id", filter=Q(score__lt=60)),
    )

    summary["total_teachers"] = teachers.count()
    return summary


@register.simple_tag
def workload_distribution_stats(academic_year=None, department_id=None):
    """Get workload distribution statistics."""
    teachers = Teacher.objects.filter(status="Active")

    if department_id:
        teachers = teachers.filter(department_id=department_id)

    if not academic_year:
        academic_year = AcademicYear.objects.filter(is_current=True).first()

    if not academic_year:
        return {"error": "No academic year found"}

    workload_stats = {
        "total_teachers": teachers.count(),
        "overloaded": 0,
        "heavy": 0,
        "balanced": 0,
        "light": 0,
        "no_assignments": 0,
    }

    for teacher in teachers:
        workload = teacher.get_current_workload(academic_year)
        assignment_count = workload["total_assignments"]

        if assignment_count >= 8:
            workload_stats["overloaded"] += 1
        elif assignment_count >= 6:
            workload_stats["heavy"] += 1
        elif assignment_count >= 3:
            workload_stats["balanced"] += 1
        elif assignment_count >= 1:
            workload_stats["light"] += 1
        else:
            workload_stats["no_assignments"] += 1

    return workload_stats


@register.simple_tag
def evaluation_reminder_count(department_id=None):
    """Get count of teachers needing evaluation reminders."""
    six_months_ago = timezone.now().date() - timedelta(days=180)

    teachers = Teacher.objects.filter(status="Active")
    if department_id:
        teachers = teachers.filter(department_id=department_id)

    needing_evaluation = teachers.exclude(
        evaluations__evaluation_date__gte=six_months_ago
    ).count()

    return needing_evaluation


@register.simple_tag
def overdue_followups_count(department_id=None):
    """Get count of overdue evaluation followups."""
    queryset = TeacherEvaluation.objects.filter(
        followup_date__lt=timezone.now().date(),
        followup_completed=False,
        status__in=["submitted", "reviewed", "approved"],
    )

    if department_id:
        queryset = queryset.filter(teacher__department_id=department_id)

    return queryset.count()


# =============================================================================
# UTILITY AND FORMATTING TAGS
# =============================================================================


@register.filter
def get_item(dictionary, key):
    """Get an item from a dictionary using the key."""
    if isinstance(dictionary, dict):
        return dictionary.get(key)
    return None


@register.filter
def split(value, delimiter):
    """Split a string by delimiter."""
    if value:
        return value.split(delimiter)
    return []


@register.filter
def multiply(value, arg):
    """Multiply the value by the argument."""
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0


@register.filter
def percentage_of(value, total):
    """Calculate percentage of total."""
    try:
        if float(total) == 0:
            return 0
        return round((float(value) / float(total)) * 100, 1)
    except (ValueError, TypeError, ZeroDivisionError):
        return 0


@register.filter
def format_criteria_name(name):
    """Format criteria name from snake_case to Title Case."""
    return name.replace("_", " ").title()


@register.filter
def format_currency(amount, currency_symbol="$"):
    """Format amount as currency."""
    try:
        amount = float(amount)
        return f"{currency_symbol}{amount:,.2f}"
    except (ValueError, TypeError):
        return f"{currency_symbol}0.00"


@register.filter
def format_percentage(value, decimal_places=1):
    """Format value as percentage."""
    try:
        value = float(value)
        return f"{value:.{decimal_places}f}%"
    except (ValueError, TypeError):
        return "0.0%"


# =============================================================================
# INCLUSION TAGS FOR REUSABLE COMPONENTS
# =============================================================================


@register.inclusion_tag("teachers/components/teacher_card.html")
def teacher_card(
    teacher, show_performance=True, show_workload=True, show_contact=False
):
    """Render a teacher card component."""
    context = {
        "teacher": teacher,
        "show_performance": show_performance,
        "show_workload": show_workload,
        "show_contact": show_contact,
    }

    if show_performance:
        context["evaluation_summary"] = teacher.get_evaluation_summary()
        context["latest_evaluation"] = teacher.get_latest_evaluation()

    if show_workload:
        current_year = AcademicYear.objects.filter(is_current=True).first()
        if current_year:
            context["workload"] = teacher.get_current_workload(current_year)

    return context


@register.inclusion_tag("teachers/components/evaluation_progress.html")
def evaluation_progress(criteria, show_details=True):
    """Render evaluation criteria progress bars."""
    if not isinstance(criteria, dict):
        return {"criteria": {}, "show_details": show_details}

    formatted_criteria = {}
    total_score = 0
    total_max = 0

    for criterion, data in criteria.items():
        if isinstance(data, dict) and "score" in data and "max_score" in data:
            score = data["score"]
            max_score = data["max_score"]
            percentage = (score / max_score * 100) if max_score > 0 else 0

            formatted_criteria[criterion] = {
                "name": criterion.replace("_", " ").title(),
                "score": score,
                "max_score": max_score,
                "percentage": round(percentage, 1),
                "color_class": _get_progress_color(percentage),
                "comments": data.get("comments", ""),
            }

            total_score += score
            total_max += max_score

    overall_percentage = (total_score / total_max * 100) if total_max > 0 else 0

    return {
        "criteria": formatted_criteria,
        "overall": {
            "score": total_score,
            "max_score": total_max,
            "percentage": round(overall_percentage, 1),
            "color_class": _get_progress_color(overall_percentage),
        },
        "show_details": show_details,
    }


@register.inclusion_tag("teachers/components/performance_chart.html")
def performance_chart(teacher, chart_type="line", months=12):
    """Render performance chart for teacher."""
    trend_data = teacher.get_performance_trend(months=months)

    chart_data = {
        "labels": trend_data["labels"],
        "scores": trend_data["scores"],
        "chart_type": chart_type,
        "teacher_name": teacher.get_full_name(),
        "has_data": trend_data["count"] > 0,
    }

    return {"chart_data": json.dumps(chart_data), "teacher": teacher, "months": months}


@register.inclusion_tag("teachers/components/workload_summary.html")
def workload_summary(teacher, academic_year=None, detailed=False):
    """Render workload summary for teacher."""
    if not academic_year:
        academic_year = AcademicYear.objects.filter(is_current=True).first()

    if not academic_year:
        return {"teacher": teacher, "no_data": True, "detailed": detailed}

    workload = teacher.get_current_workload(academic_year)

    return {
        "teacher": teacher,
        "workload": workload,
        "academic_year": academic_year,
        "detailed": detailed,
        "no_data": False,
    }


@register.inclusion_tag("teachers/components/assignment_list.html")
def assignment_list(teacher, academic_year=None, limit=None):
    """Render list of teacher assignments."""
    if not academic_year:
        academic_year = AcademicYear.objects.filter(is_current=True).first()

    if not academic_year:
        return {"assignments": [], "teacher": teacher}

    assignments = (
        teacher.class_assignments.filter(academic_year=academic_year, is_active=True)
        .select_related("class_instance", "subject")
        .order_by("class_instance__name", "subject__name")
    )

    if limit:
        assignments = assignments[:limit]

    return {
        "assignments": assignments,
        "teacher": teacher,
        "academic_year": academic_year,
    }


@register.inclusion_tag("teachers/components/recent_evaluations.html")
def recent_evaluations(teacher, limit=5):
    """Render recent evaluations for teacher."""
    evaluations = teacher.evaluations.order_by("-evaluation_date")[:limit]

    return {
        "evaluations": evaluations,
        "teacher": teacher,
        "has_evaluations": evaluations.exists(),
    }


# =============================================================================
# CHART DATA TAGS
# =============================================================================


@register.simple_tag
def teacher_chart_data(teacher_id, chart_type="performance"):
    """Generate chart data for various teacher charts."""
    try:
        teacher = Teacher.objects.get(id=teacher_id)
    except Teacher.DoesNotExist:
        return "{}"

    if chart_type == "performance":
        trend_data = teacher.get_performance_trend(months=12)
        data = {
            "labels": trend_data["labels"],
            "datasets": [
                {
                    "label": "Performance Score",
                    "data": trend_data["scores"],
                    "borderColor": "rgb(75, 192, 192)",
                    "backgroundColor": "rgba(75, 192, 192, 0.2)",
                    "tension": 0.1,
                }
            ],
        }

    elif chart_type == "criteria":
        latest_eval = teacher.get_latest_evaluation()
        if latest_eval and isinstance(latest_eval.criteria, dict):
            labels = []
            scores = []

            for criterion, data in latest_eval.criteria.items():
                if isinstance(data, dict) and "score" in data and "max_score" in data:
                    labels.append(criterion.replace("_", " ").title())
                    percentage = (
                        (data["score"] / data["max_score"] * 100)
                        if data["max_score"] > 0
                        else 0
                    )
                    scores.append(round(percentage, 1))

            data = {
                "labels": labels,
                "datasets": [
                    {
                        "label": "Criteria Scores (%)",
                        "data": scores,
                        "backgroundColor": [
                            "rgba(255, 99, 132, 0.8)",
                            "rgba(54, 162, 235, 0.8)",
                            "rgba(255, 205, 86, 0.8)",
                            "rgba(75, 192, 192, 0.8)",
                            "rgba(153, 102, 255, 0.8)",
                        ],
                    }
                ],
            }
        else:
            data = {"labels": [], "datasets": []}

    elif chart_type == "workload":
        current_year = AcademicYear.objects.filter(is_current=True).first()
        if current_year:
            workload = teacher.get_current_workload(current_year)
            data = {
                "labels": ["Classes", "Subjects", "Total Assignments"],
                "datasets": [
                    {
                        "label": "Workload Distribution",
                        "data": [
                            workload["classes"],
                            workload["subjects"],
                            workload["total_assignments"],
                        ],
                        "backgroundColor": [
                            "rgba(54, 162, 235, 0.8)",
                            "rgba(255, 99, 132, 0.8)",
                            "rgba(75, 192, 192, 0.8)",
                        ],
                    }
                ],
            }
        else:
            data = {"labels": [], "datasets": []}

    else:
        data = {}

    return json.dumps(data)


@register.simple_tag
def department_chart_data():
    """Generate chart data for department comparison."""
    departments = Department.objects.annotate(
        teacher_count=Count("teachers", filter=Q(teachers__status="Active")),
        avg_score=Avg("teachers__average_evaluation_score"),
    ).filter(teacher_count__gt=0)

    data = {
        "labels": [dept.name for dept in departments],
        "datasets": [
            {
                "label": "Teacher Count",
                "data": [dept.teacher_count for dept in departments],
                "backgroundColor": "rgba(54, 162, 235, 0.8)",
                "yAxisID": "y",
            },
            {
                "label": "Average Score",
                "data": [round(float(dept.avg_score or 0), 1) for dept in departments],
                "backgroundColor": "rgba(255, 99, 132, 0.8)",
                "yAxisID": "y1",
            },
        ],
    }

    return json.dumps(data)


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def _get_progress_color(percentage):
    """Get Bootstrap color class based on percentage."""
    if percentage >= 90:
        return "bg-success"
    elif percentage >= 80:
        return "bg-info"
    elif percentage >= 70:
        return "bg-primary"
    elif percentage >= 60:
        return "bg-warning"
    else:
        return "bg-danger"


# =============================================================================
# CACHE-AWARE TAGS
# =============================================================================


@register.simple_tag
def cached_teacher_stats(cache_key_suffix=""):
    """Get cached teacher statistics."""
    cache_key = f"teacher_stats_{cache_key_suffix}"
    stats = cache.get(cache_key)

    if stats is None:
        stats = {
            "total_teachers": Teacher.objects.count(),
            "active_teachers": Teacher.objects.filter(status="Active").count(),
            "on_leave": Teacher.objects.filter(status="On Leave").count(),
            "avg_experience": Teacher.objects.aggregate(avg=Avg("experience_years"))[
                "avg"
            ]
            or 0,
            "avg_performance": Teacher.objects.exclude(
                average_evaluation_score__isnull=True
            ).aggregate(avg=Avg("average_evaluation_score"))["avg"]
            or 0,
        }

        # Cache for 1 hour
        cache.set(cache_key, stats, 3600)

    return stats


@register.simple_tag
def performance_distribution_data():
    """Get performance distribution data for charts."""
    cache_key = "teacher_performance_distribution"
    data = cache.get(cache_key)

    if data is None:
        evaluations = TeacherEvaluation.objects.exclude(score__isnull=True)

        data = {
            "excellent": evaluations.filter(score__gte=90).count(),
            "good": evaluations.filter(score__gte=80, score__lt=90).count(),
            "satisfactory": evaluations.filter(score__gte=70, score__lt=80).count(),
            "needs_improvement": evaluations.filter(
                score__gte=60, score__lt=70
            ).count(),
            "poor": evaluations.filter(score__lt=60).count(),
        }

        total = sum(data.values())
        if total > 0:
            data["percentages"] = {
                key: round((value / total) * 100, 1) for key, value in data.items()
            }
        else:
            data["percentages"] = {key: 0 for key in data.keys()}

        # Cache for 30 minutes
        cache.set(cache_key, data, 1800)

    return data
