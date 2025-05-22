from django import template
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter
def lookup(d, key):
    """Lookup a key in a dictionary or object."""
    try:
        return d.get(key, None)
    except (AttributeError, TypeError):
        try:
            return d[key]
        except (KeyError, TypeError):
            return None


@register.filter
def split(value, delimiter=" "):
    """Split a string by delimiter."""
    return value.split(delimiter)


@register.filter
def to_int(value):
    """Convert a value to integer."""
    try:
        return int(value)
    except (ValueError, TypeError):
        return 0


@register.filter
def subtract(value, arg):
    """Subtract the arg from the value."""
    try:
        return value - arg
    except (ValueError, TypeError):
        return value


@register.filter
def percentage(value, total):
    """Calculate percentage."""
    try:
        return (value / total) * 100
    except (ValueError, TypeError, ZeroDivisionError):
        return 0


@register.filter
def get_item(dictionary, key):
    """Get an item from a dictionary."""
    return dictionary.get(key)


@register.simple_tag
def progress_bar(value, max_value=100, color="primary"):
    """Render a bootstrap progress bar."""
    percentage = min(100, max(0, (value / max_value) * 100 if max_value else 0))

    # Choose color based on percentage if not specified
    if color == "auto":
        if percentage >= 80:
            color = "success"
        elif percentage >= 60:
            color = "info"
        elif percentage >= 40:
            color = "warning"
        else:
            color = "danger"

    html = f"""
    <div class="progress">
        <div class="progress-bar bg-{color}" role="progressbar" 
             style="width: {percentage}%" 
             aria-valuenow="{percentage}" 
             aria-valuemin="0" 
             aria-valuemax="100">
            {percentage:.1f}%
        </div>
    </div>
    """
    return mark_safe(html)


@register.simple_tag
def status_badge(status, custom_map=None):
    """Render a bootstrap badge for status values."""
    default_map = {
        "active": ("success", "Active"),
        "inactive": ("secondary", "Inactive"),
        "pending": ("warning", "Pending"),
        "completed": ("success", "Completed"),
        "in_progress": ("primary", "In Progress"),
        "cancelled": ("danger", "Cancelled"),
        "draft": ("secondary", "Draft"),
        "published": ("primary", "Published"),
        "closed": ("dark", "Closed"),
        "submitted": ("success", "Submitted"),
        "late": ("warning", "Late"),
        "graded": ("info", "Graded"),
        "not_submitted": ("danger", "Not Submitted"),
        "present": ("success", "Present"),
        "absent": ("danger", "Absent"),
        "excused": ("warning", "Excused"),
        "late_attendance": ("info", "Late"),
    }

    status_map = custom_map or default_map
    color, label = status_map.get(status.lower(), ("secondary", status.title()))

    html = f'<span class="badge bg-{color}">{label}</span>'
    return mark_safe(html)


@register.filter
def unique(items, attribute=None):
    """Return unique items from a list, optionally filtering by attribute."""
    if not items:
        return []

    if attribute:
        seen = set()
        result = []
        for item in items:
            attr_value = getattr(item, attribute, None)
            if attr_value not in seen:
                seen.add(attr_value)
                result.append(item)
        return result
    else:
        return list(set(items))


@register.simple_tag
def time_slot_cell(timetable_matrix, day, time_slot, classes=None):
    """Render a timetable cell for a specific day and time slot."""
    entry = lookup(lookup(timetable_matrix, day), time_slot.id)
    if not entry:
        return mark_safe("<td>-</td>")

    # Apply custom classes if provided
    class_str = f' class="{classes}"' if classes else ""

    html = f"""
    <td{class_str}>
        <div style="background-color: {entry.subject.color if hasattr(entry.subject, 'color') else '#4e73df'}1a; 
                    border-left: 4px solid {entry.subject.color if hasattr(entry.subject, 'color') else '#4e73df'}; 
                    padding: 5px; border-radius: 5px;">
            <strong>{entry.subject.name}</strong><br>
            {entry.teacher.user.get_full_name()}<br>
            <small class="text-muted">Room: {entry.room or "N/A"}</small>
        </div>
    </td>
    """
    return mark_safe(html)
