# students/templatetags/student_tags.py
import datetime

from django import template
from django.core.cache import cache
from django.db.models import Count, Q
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from ..models import Parent, Student, StudentParentRelation

register = template.Library()


@register.filter
def student_status_badge(status):
    """Display student status as a colored badge"""
    color_map = {
        "Active": "success",
        "Inactive": "secondary",
        "Graduated": "info",
        "Suspended": "warning",
        "Expelled": "danger",
        "Withdrawn": "secondary",
    }
    color = color_map.get(status, "secondary")
    return format_html('<span class="badge bg-{}">{}</span>', color, status)


@register.filter
def parent_relation_icon(relation):
    """Display appropriate icon for parent relation"""
    icon_map = {
        "Father": "fas fa-male",
        "Mother": "fas fa-female",
        "Guardian": "fas fa-user-shield",
        "Grandparent": "fas fa-user-friends",
        "Uncle": "fas fa-male",
        "Aunt": "fas fa-female",
        "Other": "fas fa-user",
    }
    icon = icon_map.get(relation, "fas fa-user")
    return format_html('<i class="{}"></i>', icon)


@register.filter
def blood_group_color(blood_group):
    """Get appropriate color for blood group display"""
    color_map = {
        "A+": "success",
        "A-": "info",
        "B+": "primary",
        "B-": "secondary",
        "AB+": "warning",
        "AB-": "danger",
        "O+": "dark",
        "O-": "light",
        "Unknown": "muted",
    }
    return color_map.get(blood_group, "muted")


@register.filter
def attendance_percentage_color(percentage):
    """Get color class based on attendance percentage"""
    if percentage >= 90:
        return "success"
    elif percentage >= 75:
        return "warning"
    else:
        return "danger"


@register.simple_tag
def student_count_by_status(status=None):
    """Get count of students by status"""
    cache_key = f"student_count_{status or 'all'}"
    count = cache.get(cache_key)

    if count is None:
        if status:
            count = Student.objects.filter(status=status).count()
        else:
            count = Student.objects.count()
        cache.set(cache_key, count, 3600)  # Cache for 1 hour

    return count


@register.simple_tag
def parent_count_by_relation(relation=None):
    """Get count of parents by relation"""
    cache_key = f"parent_count_{relation or 'all'}"
    count = cache.get(cache_key)

    if count is None:
        if relation:
            count = Parent.objects.filter(relation_with_student=relation).count()
        else:
            count = Parent.objects.count()
        cache.set(cache_key, count, 3600)  # Cache for 1 hour

    return count


@register.inclusion_tag("students/templatetags/student_quick_stats.html")
def student_quick_stats():
    """Display quick statistics about students"""
    cache_key = "student_quick_stats"
    stats = cache.get(cache_key)

    if stats is None:
        stats = {
            "total": Student.objects.count(),
            "active": Student.objects.filter(status="Active").count(),
            "with_photos": Student.objects.exclude(photo="").count(),
            "without_parents": Student.objects.filter(
                student_parent_relations__isnull=True
            ).count(),
            "recent_admissions": Student.objects.filter(
                admission_date__gte=datetime.date.today() - datetime.timedelta(days=30)
            ).count(),
        }
        cache.set(cache_key, stats, 1800)  # Cache for 30 minutes

    return {"stats": stats}


@register.inclusion_tag("students/templatetags/parent_quick_stats.html")
def parent_quick_stats():
    """Display quick statistics about parents"""
    cache_key = "parent_quick_stats"
    stats = cache.get(cache_key)

    if stats is None:
        stats = {
            "total": Parent.objects.count(),
            "emergency_contacts": Parent.objects.filter(emergency_contact=True).count(),
            "with_multiple_children": Parent.objects.annotate(
                child_count=Count("parent_student_relations")
            )
            .filter(child_count__gt=1)
            .count(),
            "primary_contacts": StudentParentRelation.objects.filter(
                is_primary_contact=True
            ).count(),
        }
        cache.set(cache_key, stats, 1800)  # Cache for 30 minutes

    return {"stats": stats}


@register.simple_tag
def student_profile_completion(student):
    """Calculate student profile completion percentage"""
    total_fields = 10
    completed_fields = 0

    # Check required fields
    if student.user.first_name:
        completed_fields += 1
    if student.user.last_name:
        completed_fields += 1
    if student.user.email:
        completed_fields += 1
    if student.emergency_contact_name:
        completed_fields += 1
    if student.emergency_contact_number:
        completed_fields += 1

    # Check optional but important fields
    if student.photo:
        completed_fields += 1
    if student.user.date_of_birth:
        completed_fields += 1
    if student.address:
        completed_fields += 1
    if student.current_class:
        completed_fields += 1
    if student.student_parent_relations.exists():
        completed_fields += 1

    return round((completed_fields / total_fields) * 100)


@register.simple_tag
def parent_profile_completion(parent):
    """Calculate parent profile completion percentage"""
    total_fields = 8
    completed_fields = 0

    # Check required fields
    if parent.user.first_name:
        completed_fields += 1
    if parent.user.last_name:
        completed_fields += 1
    if parent.user.email:
        completed_fields += 1
    if parent.relation_with_student:
        completed_fields += 1

    # Check optional but important fields
    if parent.user.phone_number:
        completed_fields += 1
    if parent.occupation:
        completed_fields += 1
    if parent.workplace:
        completed_fields += 1
    if parent.parent_student_relations.exists():
        completed_fields += 1

    return round((completed_fields / total_fields) * 100)


@register.filter
def format_phone_number(phone):
    """Format phone number for display"""
    if not phone:
        return "Not provided"

    # Remove non-numeric characters except +
    cleaned = "".join(char for char in phone if char.isdigit() or char == "+")

    # Format based on length
    if len(cleaned) == 10:
        return f"({cleaned[:3]}) {cleaned[3:6]}-{cleaned[6:]}"
    elif len(cleaned) == 11 and cleaned.startswith("1"):
        return f"+1 ({cleaned[1:4]}) {cleaned[4:7]}-{cleaned[7:]}"
    elif cleaned.startswith("+"):
        return cleaned
    else:
        return phone


@register.simple_tag
def get_student_siblings(student):
    """Get siblings for a student"""
    return student.get_siblings()[:5]  # Limit to 5 for display


@register.simple_tag
def get_parent_children(parent):
    """Get children for a parent"""
    return parent.get_students()


@register.filter
def has_permission_for_student(user, student):
    """Check if user has permission to view/edit student"""
    if user.is_staff or user.is_superuser:
        return True

    # Check if user is the student
    if hasattr(user, "student_profile") and user.student_profile.id == student.id:
        return True

    # Check if user is a parent of the student
    if hasattr(user, "parent_profile"):
        return StudentParentRelation.objects.filter(
            parent=user.parent_profile, student=student
        ).exists()

    return False


@register.simple_tag(takes_context=True)
def student_action_buttons(context, student):
    """Generate action buttons for a student"""
    user = context["user"]
    buttons = []

    # View button (always available if user has permission)
    if has_permission_for_student(user, student):
        buttons.append(
            {
                "url": reverse("students:student-detail", args=[student.id]),
                "icon": "fas fa-eye",
                "class": "btn-info",
                "title": "View Details",
            }
        )

    # Edit button (for staff)
    if user.is_staff and user.has_perm("students.change_student"):
        buttons.append(
            {
                "url": reverse("students:student-update", args=[student.id]),
                "icon": "fas fa-edit",
                "class": "btn-primary",
                "title": "Edit",
            }
        )

    # ID Card button
    if user.is_staff and user.has_perm("students.generate_student_id"):
        buttons.append(
            {
                "url": reverse("students:student-id-card", args=[student.id]),
                "icon": "fas fa-id-card",
                "class": "btn-warning",
                "title": "ID Card",
            }
        )

    # Delete button (for admin)
    if user.is_staff and user.has_perm("students.delete_student"):
        buttons.append(
            {
                "url": reverse("students:student-delete", args=[student.id]),
                "icon": "fas fa-trash",
                "class": "btn-danger",
                "title": "Delete",
                "confirm": True,
            }
        )

    return buttons


@register.filter
def age_from_dob(date_of_birth):
    """Calculate age from date of birth"""
    if not date_of_birth:
        return "Not specified"

    today = datetime.date.today()
    age = today.year - date_of_birth.year

    # Adjust if birthday hasn't occurred this year
    if today.month < date_of_birth.month or (
        today.month == date_of_birth.month and today.day < date_of_birth.day
    ):
        age -= 1

    return f"{age} years old"


@register.simple_tag
def relationship_permissions_summary(relation):
    """Get a summary of relationship permissions"""
    permissions = []

    if relation.is_primary_contact:
        permissions.append("Primary Contact")
    if relation.can_pickup:
        permissions.append("Can Pickup")
    if relation.financial_responsibility:
        permissions.append("Financial Responsibility")
    if relation.access_to_grades:
        permissions.append("Grade Access")
    if relation.access_to_attendance:
        permissions.append("Attendance Access")

    return permissions


@register.inclusion_tag("students/templatetags/student_search_widget.html")
def student_search_widget(placeholder="Search students...", show_filters=True):
    """Render a student search widget"""
    return {
        "placeholder": placeholder,
        "show_filters": show_filters,
        "status_choices": Student.STATUS_CHOICES,
        "blood_group_choices": Student.BLOOD_GROUP_CHOICES,
    }


@register.inclusion_tag("students/templatetags/parent_search_widget.html")
def parent_search_widget(placeholder="Search parents...", show_filters=True):
    """Render a parent search widget"""
    return {
        "placeholder": placeholder,
        "show_filters": show_filters,
        "relation_choices": Parent.RELATION_CHOICES,
    }


@register.filter
def truncate_smart(value, length=50):
    """Smart truncation that doesn't cut words in half"""
    if len(value) <= length:
        return value

    truncated = value[:length]
    # Find the last space
    last_space = truncated.rfind(" ")
    if last_space > 0:
        truncated = truncated[:last_space]

    return truncated + "..."


@register.simple_tag
def render_field_with_icon(field, icon):
    """Render a form field with an icon"""
    return format_html(
        '<div class="input-group"><span class="input-group-text"><i class="{}"></i></span>{}</div>',
        icon,
        field,
    )
