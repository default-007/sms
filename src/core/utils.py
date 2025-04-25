import uuid
import secrets
import string
from django.utils import timezone
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from .models import SystemSetting, AuditLog


def generate_unique_id(prefix="", length=8):
    """Generate a unique ID with optional prefix."""
    chars = string.ascii_uppercase + string.digits
    unique_id = "".join(secrets.choice(chars) for _ in range(length))
    return f"{prefix}{unique_id}"


def get_system_setting(key, default=None):
    """Get a system setting value by key."""
    try:
        setting = SystemSetting.objects.get(setting_key=key)

        # Convert the value based on its data type
        if setting.data_type == "boolean":
            return setting.setting_value.lower() in ("true", "yes", "1")
        elif setting.data_type == "number":
            return float(setting.setting_value)
        elif setting.data_type == "json":
            import json

            return json.loads(setting.setting_value)

        # Default to string
        return setting.setting_value
    except ObjectDoesNotExist:
        return default


def create_audit_log(
    user,
    action,
    entity_type,
    entity_id=None,
    data_before=None,
    data_after=None,
    request=None,
):
    """Create an audit log entry."""
    ip_address = None
    user_agent = None

    if request:
        ip_address = request.META.get("REMOTE_ADDR")
        user_agent = request.META.get("HTTP_USER_AGENT")

    AuditLog.objects.create(
        user=user,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        data_before=data_before,
        data_after=data_after,
        ip_address=ip_address,
        user_agent=user_agent,
    )


def academic_year_for_date(date=None):
    """Get the academic year for a given date."""
    from django.apps import apps

    if date is None:
        date = timezone.now().date()

    AcademicYear = apps.get_model("courses", "AcademicYear")
    try:
        return AcademicYear.objects.get(
            start_date__lte=date, end_date__gte=date, is_current=True
        )
    except ObjectDoesNotExist:
        # Fallback to the current academic year if one exists
        try:
            return AcademicYear.objects.get(is_current=True)
        except ObjectDoesNotExist:
            return None
