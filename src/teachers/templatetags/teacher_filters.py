# src/teachers/templatetags/teacher_filters.py
from django import template
from django.utils.safestring import mark_safe
import json

register = template.Library()


@register.filter
def get_item(dictionary, key):
    """Get an item from a dictionary using the key."""
    return dictionary.get(key)


@register.filter
def split(value, delimiter):
    """Split a string by delimiter."""
    return value.split(delimiter)


@register.filter
def teacher_status_badge(status):
    """Return a Bootstrap badge for teacher status."""
    badges = {
        "Active": '<span class="badge bg-success">Active</span>',
        "On Leave": '<span class="badge bg-warning">On Leave</span>',
        "Terminated": '<span class="badge bg-danger">Terminated</span>',
    }
    return mark_safe(
        badges.get(status, f'<span class="badge bg-secondary">{status}</span>')
    )


@register.filter
def format_criteria_name(name):
    """Format snake_case criteria name to Title Case with spaces."""
    return " ".join(word.capitalize() for word in name.split("_"))


@register.filter
def percentage(value, max_value):
    """Calculate percentage."""
    try:
        return (float(value) / float(max_value)) * 100
    except (ValueError, ZeroDivisionError):
        return 0


@register.filter
def percentage_of(value, total):
    """Calculate percentage of total."""
    try:
        return (float(value) / float(total)) * 100
    except (ValueError, ZeroDivisionError):
        return 0


@register.filter
def percentage_of_total_evaluations(value):
    """Calculate percentage of total evaluations."""
    from src.teachers.models import TeacherEvaluation

    total = TeacherEvaluation.objects.count()
    try:
        return (float(value) / float(total)) * 100
    except (ValueError, ZeroDivisionError):
        return 0


@register.filter
def percentage_color(value):
    """Return a color based on percentage value."""
    try:
        value = float(value)
        if value >= 90:
            return "success"
        elif value >= 80:
            return "info"
        elif value >= 70:
            return "primary"
        elif value >= 60:
            return "warning"
        else:
            return "danger"
    except (ValueError, TypeError):
        return "secondary"
