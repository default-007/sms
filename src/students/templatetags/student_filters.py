# students/templatetags/student_filters.py
from django import template
from django.db.models import Count
from ..models import StudentParentRelation

register = template.Library()


@register.filter
def percentage(value, total):
    """
    Calculate percentage of value from total
    Usage: {{ value|percentage:total }}
    """
    try:
        value = float(value or 0)
        total = float(total or 0)
        if total == 0:
            return 0
        return round((value / total) * 100, 1)
    except (ValueError, TypeError, ZeroDivisionError):
        return 0


@register.simple_tag
def parent_count_by_relation(relation_type):
    """
    Get count of parents by relation type
    Usage: {% parent_count_by_relation "Father" %}
    """
    try:
        return (
            StudentParentRelation.objects.filter(relation_type=relation_type)
            .values("parent")
            .distinct()
            .count()
        )
    except:
        return 0


@register.filter
def multiply(value, arg):
    """
    Multiply value by argument
    Usage: {{ value|multiply:arg }}
    """
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0


@register.filter
def divide(value, arg):
    """
    Divide value by argument
    Usage: {{ value|divide:arg }}
    """
    try:
        divisor = float(arg)
        if divisor == 0:
            return 0
        return float(value) / divisor
    except (ValueError, TypeError):
        return 0


@register.filter
def default_if_zero(value, default):
    """
    Return default if value is zero
    Usage: {{ value|default_if_zero:"N/A" }}
    """
    try:
        if float(value) == 0:
            return default
        return value
    except (ValueError, TypeError):
        return default


@register.simple_tag
def get_parent_stats():
    """
    Get comprehensive parent statistics
    Usage: {% get_parent_stats as stats %}
    """
    from ..models import Parent, StudentParentRelation

    try:
        total_parents = Parent.objects.count()

        # Parents who are emergency contacts
        emergency_contacts = (
            StudentParentRelation.objects.filter(is_primary_contact=True)
            .values("parent")
            .distinct()
            .count()
        )

        # Parents with multiple children
        parents_with_multiple = (
            StudentParentRelation.objects.values("parent")
            .annotate(child_count=Count("student"))
            .filter(child_count__gt=1)
            .count()
        )

        # Primary contacts
        primary_contacts = StudentParentRelation.objects.filter(
            is_primary_contact=True
        ).count()

        return {
            "total": total_parents,
            "emergency_contacts": emergency_contacts,
            "with_multiple_children": parents_with_multiple,
            "primary_contacts": primary_contacts,
        }
    except:
        return {
            "total": 0,
            "emergency_contacts": 0,
            "with_multiple_children": 0,
            "primary_contacts": 0,
        }


@register.simple_tag
def get_student_stats():
    """
    Get comprehensive student statistics
    Usage: {% get_student_stats as stats %}
    """
    from ..models import Student

    try:
        total_students = Student.objects.filter(status="active").count()

        # Students by status
        enrolled = Student.objects.filter(status="active").count()
        graduated = Student.objects.filter(status="graduated").count()
        transferred = Student.objects.filter(status="transferred").count()
        inactive = Student.objects.filter(status="inactive").count()

        return {
            "total": total_students,
            "enrolled": enrolled,
            "graduated": graduated,
            "transferred": transferred,
            "inactive": inactive,
        }
    except:
        return {
            "total": 0,
            "enrolled": 0,
            "graduated": 0,
            "transferred": 0,
            "inactive": 0,
        }


@register.filter
def progress_width(value, max_value):
    """
    Calculate progress bar width percentage
    Usage: {{ current|progress_width:maximum }}
    """
    try:
        current = float(value or 0)
        maximum = float(max_value or 0)
        if maximum == 0:
            return 0
        width = (current / maximum) * 100
        return min(100, max(0, width))  # Clamp between 0 and 100
    except (ValueError, TypeError):
        return 0


@register.simple_tag
def attendance_color_class(percentage):
    """
    Get Bootstrap color class based on attendance percentage
    Usage: {% attendance_color_class attendance_percent %}
    """
    try:
        percent = float(percentage)
        if percent >= 90:
            return "success"
        elif percent >= 75:
            return "warning"
        elif percent >= 60:
            return "info"
        else:
            return "danger"
    except (ValueError, TypeError):
        return "secondary"


@register.simple_tag
def performance_color_class(marks):
    """
    Get Bootstrap color class based on performance marks
    Usage: {% performance_color_class marks %}
    """
    try:
        marks = float(marks)
        if marks >= 90:
            return "success"
        elif marks >= 75:
            return "info"
        elif marks >= 60:
            return "warning"
        else:
            return "danger"
    except (ValueError, TypeError):
        return "secondary"


@register.filter
def format_phone(phone_number):
    """
    Format phone number for display
    Usage: {{ phone|format_phone }}
    """
    if not phone_number:
        return ""

    # Remove all non-digit characters
    import re

    digits = re.sub(r"\D", "", str(phone_number))

    # Format as (XXX) XXX-XXXX for 10-digit numbers
    if len(digits) == 10:
        return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    elif len(digits) == 11 and digits[0] == "1":
        return f"+1 ({digits[1:4]}) {digits[4:7]}-{digits[7:]}"
    else:
        return phone_number


@register.filter
def truncate_words_smart(value, arg):
    """
    Truncate text smartly at word boundaries
    Usage: {{ text|truncate_words_smart:5 }}
    """
    try:
        words = str(value).split()
        limit = int(arg)
        if len(words) <= limit:
            return value
        return " ".join(words[:limit]) + "..."
    except (ValueError, TypeError):
        return value


@register.simple_tag
def get_grade_distribution():
    """
    Get student distribution by grade
    Usage: {% get_grade_distribution as grade_dist %}
    """
    from ..models import Student
    from src.academics.models import Grade

    try:
        distribution = []
        grades = Grade.objects.all().order_by("order_sequence")

        for grade in grades:
            student_count = Student.objects.filter(
                current_class__grade=grade, status="active"
            ).count()

            distribution.append(
                {
                    "grade": grade,
                    "count": student_count,
                    "percentage": 0,  # Will be calculated in template if needed
                }
            )

        return distribution
    except:
        return []
