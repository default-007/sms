"""Template filters for academics templates (simple math helpers)."""

from django import template

register = template.Library()


def _to_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


@register.filter
def mul(value, arg):
    """Multiply: {{ value|mul:arg }}"""
    return _to_float(value) * _to_float(arg)


@register.filter
def div(value, arg):
    """Divide: {{ value|div:arg }} (returns 0 if divisor is 0)."""
    divisor = _to_float(arg)
    if divisor == 0:
        return 0
    return _to_float(value) / divisor


@register.filter
def sub(value, arg):
    """Subtract: {{ value|sub:arg }}"""
    return _to_float(value) - _to_float(arg)
