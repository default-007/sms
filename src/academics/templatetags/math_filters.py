from django import template

register = template.Library()


@register.filter
def div(value, divisor):
    """Divide value by divisor"""
    try:
        return float(value) / float(divisor)
    except (ValueError, ZeroDivisionError):
        return 0


@register.filter
def mul(value, multiplier):
    """Multiply value by multiplier"""
    try:
        return float(value) * float(multiplier)
    except ValueError:
        return 0
