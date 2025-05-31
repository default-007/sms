# src/accounts/templatetags/accounts_tags.py

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from django import template
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db.models import Count, Q
from django.utils import timezone
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from ..models import UserAuditLog, UserRole, UserRoleAssignment, UserSession
from ..services import RoleService, UserAnalyticsService
from ..utils import time_since, mask_email, mask_phone

register = template.Library()
User = get_user_model()


# User permission and role tags
@register.simple_tag
def user_has_permission(user, resource, action):
    """Check if user has specific permission."""
    if not user or not user.is_authenticated:
        return False
    return RoleService.check_permission(user, resource, action)


@register.simple_tag
def user_has_role(user, role_name):
    """Check if user has specific role."""
    if not user or not user.is_authenticated:
        return False
    return user.has_role(role_name)


@register.simple_tag
def user_roles(user):
    """Get list of user's roles."""
    if not user or not user.is_authenticated:
        return []
    return user.get_assigned_roles()


@register.simple_tag
def user_permissions(user):
    """Get user's permissions dictionary."""
    if not user or not user.is_authenticated:
        return {}
    return RoleService.get_user_permissions(user)


@register.filter
def has_any_role(user, role_names):
    """Check if user has any of the specified roles."""
    if not user or not user.is_authenticated:
        return False

    if isinstance(role_names, str):
        role_names = [role_names]

    user_role_names = [role.name for role in user.get_assigned_roles()]
    return any(role in user_role_names for role in role_names)


@register.filter
def has_all_roles(user, role_names):
    """Check if user has all of the specified roles."""
    if not user or not user.is_authenticated:
        return False

    if isinstance(role_names, str):
        role_names = [role_names]

    user_role_names = [role.name for role in user.get_assigned_roles()]
    return all(role in user_role_names for role in role_names)


# User information tags - both as simple_tags and filters
@register.simple_tag
def user_display_name(user):
    """Get user's display name."""
    if not user:
        return "Unknown User"
    return user.get_display_name()


@register.filter
def user_display_name_filter(user):
    """Get user's display name as filter."""
    if not user:
        return "Unknown User"
    return user.get_display_name()


@register.simple_tag
def user_initials(user):
    """Get user's initials."""
    if not user:
        return "??"
    return user.get_initials()


@register.filter
def user_initials_filter(user):
    """Get user's initials as filter."""
    if not user:
        return "??"
    return user.get_initials()


# For backward compatibility, add user_initials as a filter too
@register.filter
def user_initials(user):
    """Get user's initials."""
    if not user:
        return "??"
    return user.get_initials()


@register.simple_tag
def user_profile_completion(user):
    """Get user's profile completion percentage."""
    if not user or not user.is_authenticated:
        return 0
    return user.get_profile_completion_percentage()


@register.filter
def user_profile_completion_filter(user):
    """Get user's profile completion percentage as filter."""
    return user_profile_completion(user)


# For backward compatibility
@register.filter
def user_profile_completion(user):
    """Get user's profile completion percentage."""
    if not user or not user.is_authenticated:
        return 0
    return user.get_profile_completion_percentage()


@register.simple_tag
def user_security_score(user):
    """Get user's security score."""
    if not user or not user.is_authenticated:
        return 0
    return user.get_security_score()


@register.filter
def user_security_score_filter(user):
    """Get user's security score as filter."""
    return user_security_score(user)


# For backward compatibility
@register.filter
def user_security_score(user):
    """Get user's security score."""
    if not user or not user.is_authenticated:
        return 0
    return user.get_security_score()


@register.filter
def user_age(user):
    """Get user's age."""
    if not user or not hasattr(user, "date_of_birth") or not user.date_of_birth:
        return None
    return user.get_age()


@register.filter
def mask_user_email(email):
    """Mask email address for privacy."""
    return mask_email(email) if email else ""


@register.filter
def mask_user_phone(phone):
    """Mask phone number for privacy."""
    return mask_phone(phone) if phone else ""


# User status tags - both as simple_tags and filters
@register.simple_tag
def user_is_online(user):
    """Check if user is currently online."""
    if not user or not user.is_authenticated:
        return False

    # Check if user has active session in last 5 minutes
    five_minutes_ago = timezone.now() - timedelta(minutes=5)
    return UserSession.objects.filter(
        user=user, is_active=True, last_activity__gte=five_minutes_ago
    ).exists()


@register.filter
def user_is_online_filter(user):
    """Check if user is currently online as filter."""
    return user_is_online(user)


@register.simple_tag
def user_last_seen(user):
    """Get when user was last seen."""
    if not user or not user.is_authenticated:
        return None

    if user.last_login:
        return time_since(user.last_login)

    return "Never"


@register.filter
def user_last_seen_filter(user):
    """Get when user was last seen as filter."""
    return user_last_seen(user)


@register.simple_tag
def user_active_sessions_count(user):
    """Get count of user's active sessions."""
    if not user or not user.is_authenticated:
        return 0

    return UserSession.objects.filter(user=user, is_active=True).count()


@register.filter
def user_active_sessions_count_filter(user):
    """Get count of user's active sessions as filter."""
    return user_active_sessions_count(user)


@register.simple_tag
def user_failed_login_attempts(user):
    """Get user's failed login attempts count."""
    if not user:
        return 0
    return getattr(user, "failed_login_attempts", 0)


@register.filter
def user_failed_login_attempts_filter(user):
    """Get user's failed login attempts count as filter."""
    return user_failed_login_attempts(user)


@register.simple_tag
def user_is_locked(user):
    """Check if user account is locked."""
    if not user:
        return False
    return user.is_account_locked() if hasattr(user, "is_account_locked") else False


@register.filter
def user_is_locked_filter(user):
    """Check if user account is locked as filter."""
    return user_is_locked(user)


# For backward compatibility, register as filters with original names
@register.filter
def user_is_locked(user):
    """Check if user account is locked."""
    if not user:
        return False
    return user.is_account_locked() if hasattr(user, "is_account_locked") else False


@register.filter
def user_failed_login_attempts(user):
    """Get user's failed login attempts count."""
    if not user:
        return 0
    return getattr(user, "failed_login_attempts", 0)


@register.filter
def user_active_sessions_count(user):
    """Get count of user's active sessions."""
    if not user or not user.is_authenticated:
        return 0
    return UserSession.objects.filter(user=user, is_active=True).count()


# Analytics tags
@register.simple_tag
def user_login_count(user, days=30):
    """Get user's login count for specified period."""
    if not user or not user.is_authenticated:
        return 0

    start_date = timezone.now() - timedelta(days=days)
    return UserAuditLog.objects.filter(
        user=user,
        action="login",
        description__contains="Successful",
        timestamp__gte=start_date,
    ).count()


@register.simple_tag
def user_activity_summary(user, days=30):
    """Get user's activity summary."""
    if not user or not user.is_authenticated:
        return {}

    return UserAnalyticsService.get_user_performance_metrics(user, days)


@register.simple_tag
def recent_user_registrations(days=7, limit=5):
    """Get recent user registrations."""
    start_date = timezone.now() - timedelta(days=days)
    return User.objects.filter(date_joined__gte=start_date).order_by("-date_joined")[
        :limit
    ]


@register.simple_tag
def active_users_count(minutes=30):
    """Get count of recently active users."""
    cutoff = timezone.now() - timedelta(minutes=minutes)
    return User.objects.filter(last_login__gte=cutoff).count()


@register.simple_tag
def total_users_count():
    """Get total users count."""
    return User.objects.count()


@register.simple_tag
def users_by_role():
    """Get user count by role."""
    return UserRole.objects.annotate(
        user_count=Count("user_assignments", filter=Q(user_assignments__is_active=True))
    ).values("name", "user_count")


# Role and permission display tags
@register.simple_tag
def role_display_badge(role):
    """Generate HTML badge for role display."""
    if not role:
        return ""

    color_class = "primary"
    if role.is_system_role:
        color_class = "info"
    elif role.name == "Admin":
        color_class = "danger"
    elif role.name == "Teacher":
        color_class = "success"
    elif role.name == "Student":
        color_class = "secondary"

    return format_html('<span class="badge bg-{}">{}</span>', color_class, role.name)


@register.simple_tag
def user_roles_badges(user):
    """Generate HTML badges for all user roles."""
    if not user or not user.is_authenticated:
        return ""

    badges = []
    for role in user.get_assigned_roles():
        badges.append(role_display_badge(role))

    return mark_safe(" ".join(badges))


@register.simple_tag
def permission_display(permissions):
    """Display permissions in a readable format."""
    if not permissions:
        return ""

    items = []
    for resource, actions in permissions.items():
        if actions:
            items.append(f"{resource}: {', '.join(actions)}")

    return "; ".join(items)


# Security and status indicators
@register.simple_tag
def security_status_badge(user):
    """Generate security status badge."""
    if not user:
        return ""

    score = user.get_security_score() if hasattr(user, "get_security_score") else 50

    if score >= 80:
        badge_class = "success"
        text = "High"
    elif score >= 60:
        badge_class = "warning"
        text = "Medium"
    else:
        badge_class = "danger"
        text = "Low"

    return format_html(
        '<span class="badge bg-{}" title="Security Score: {}">{}</span>',
        badge_class,
        score,
        text,
    )


@register.simple_tag
def account_status_badge(user):
    """Generate account status badge."""
    if not user:
        return ""

    if not user.is_active:
        return format_html('<span class="badge bg-secondary">Inactive</span>')

    if user.is_account_locked():
        return format_html('<span class="badge bg-danger">Locked</span>')

    if getattr(user, "requires_password_change", False):
        return format_html(
            '<span class="badge bg-warning">Password Change Required</span>'
        )

    if not getattr(user, "email_verified", True):
        return format_html('<span class="badge bg-info">Email Unverified</span>')

    return format_html('<span class="badge bg-success">Active</span>')


@register.simple_tag
def verification_status_badges(user):
    """Generate verification status badges."""
    if not user:
        return ""

    badges = []

    # Email verification
    if getattr(user, "email_verified", False):
        badges.append('<span class="badge bg-success badge-sm">Email ✓</span>')
    else:
        badges.append('<span class="badge bg-warning badge-sm">Email ✗</span>')

    # Phone verification
    if getattr(user, "phone_verified", False):
        badges.append('<span class="badge bg-success badge-sm">Phone ✓</span>')
    else:
        badges.append('<span class="badge bg-warning badge-sm">Phone ✗</span>')

    # Two-factor authentication
    if getattr(user, "two_factor_enabled", False):
        badges.append('<span class="badge bg-info badge-sm">2FA ✓</span>')

    return mark_safe(" ".join(badges))


# Time and date formatting
@register.filter
def time_since_filter(dt):
    """Format datetime as time since."""
    if not dt:
        return "Never"
    return time_since(dt)


@register.filter
def format_datetime(dt, format_string="%Y-%m-%d %H:%M"):
    """Format datetime with custom format."""
    if not dt:
        return ""
    return dt.strftime(format_string)


@register.filter
def days_since(dt):
    """Get number of days since datetime."""
    if not dt:
        return None

    diff = timezone.now() - dt
    return diff.days


# Utility tags
@register.simple_tag
def user_avatar_url(user, size=40):
    """Get user avatar URL."""
    if not user:
        return ""

    if hasattr(user, "profile_picture") and user.profile_picture:
        return user.profile_picture.url

    # Generate Gravatar URL or default avatar
    import hashlib

    email_hash = hashlib.md5(user.email.lower().encode()).hexdigest()
    return f"https://www.gravatar.com/avatar/{email_hash}?s={size}&d=identicon"


@register.simple_tag
def user_activity_indicator(user):
    """Generate activity indicator for user."""
    if not user:
        return ""

    if user_is_online(user):
        return format_html(
            '<span class="status-indicator online" title="Online"></span>'
        )

    last_login = user.last_login
    if last_login:
        days_ago = (timezone.now() - last_login).days
        if days_ago <= 1:
            status_class = "recent"
            title = "Active today"
        elif days_ago <= 7:
            status_class = "away"
            title = f"Active {days_ago} days ago"
        else:
            status_class = "offline"
            title = f"Last seen {days_ago} days ago"
    else:
        status_class = "offline"
        title = "Never logged in"

    return format_html(
        '<span class="status-indicator {}" title="{}"></span>', status_class, title
    )


@register.simple_tag
def progress_bar(value, max_value=100, color="primary"):
    """Generate progress bar HTML."""
    if max_value == 0:
        percentage = 0
    else:
        percentage = min(100, (value / max_value) * 100)

    return format_html(
        '<div class="progress"><div class="progress-bar bg-{}" role="progressbar" '
        'style="width: {}%" aria-valuenow="{}" aria-valuemin="0" aria-valuemax="{}">'
        "</div></div>",
        color,
        percentage,
        value,
        max_value,
    )


# Conditional display tags
@register.simple_tag
def if_user_can(user, resource, action):
    """Return content if user has permission."""
    if user_has_permission(user, resource, action):
        return "show"
    return "hide"


@register.simple_tag
def unless_user_can(user, resource, action):
    """Return content unless user has permission."""
    if not user_has_permission(user, resource, action):
        return "show"
    return "hide"


# Permission checking filter for template conditionals
@register.filter
def can_do(user, permission_string):
    """
    Check if user can perform action.
    Usage: {% if user|can_do:"users:change" %}
    """
    if not user or not user.is_authenticated:
        return False

    try:
        resource, action = permission_string.split(":")
        return RoleService.check_permission(user, resource, action)
    except (ValueError, AttributeError):
        return False


# Caching tags for performance
@register.simple_tag
def cached_user_stats(cache_timeout=300):
    """Get cached user statistics."""
    cache_key = "user_stats_summary"
    stats = cache.get(cache_key)

    if stats is None:
        stats = {
            "total_users": User.objects.count(),
            "active_users": User.objects.filter(is_active=True).count(),
            "verified_users": User.objects.filter(email_verified=True).count(),
            "recent_logins": User.objects.filter(
                last_login__gte=timezone.now() - timedelta(days=7)
            ).count(),
        }
        cache.set(cache_key, stats, cache_timeout)

    return stats


@register.simple_tag
def cached_role_stats(cache_timeout=300):
    """Get cached role statistics."""
    cache_key = "role_stats_summary"
    stats = cache.get(cache_key)

    if stats is None:
        stats = list(
            UserRole.objects.annotate(
                user_count=Count(
                    "user_assignments", filter=Q(user_assignments__is_active=True)
                )
            ).values("name", "user_count", "is_system_role")
        )
        cache.set(cache_key, stats, cache_timeout)

    return stats


# Form helper tags
@register.inclusion_tag("accounts/templatetags/user_select.html")
def user_select_field(field_name, selected_user=None, placeholder="Select user..."):
    """Render user selection field."""
    return {
        "field_name": field_name,
        "selected_user": selected_user,
        "placeholder": placeholder,
        "users": User.objects.filter(is_active=True).order_by(
            "first_name", "last_name"
        ),
    }


@register.inclusion_tag("accounts/templatetags/role_select.html")
def role_select_field(field_name, selected_roles=None, multiple=False):
    """Render role selection field."""
    return {
        "field_name": field_name,
        "selected_roles": selected_roles or [],
        "multiple": multiple,
        "roles": UserRole.objects.filter(is_active=True).order_by("name"),
    }


# Data formatting tags
@register.filter
def format_file_size(size_bytes):
    """Format file size in human readable format."""
    if not size_bytes:
        return "0 B"

    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0

    return f"{size_bytes:.1f} TB"


@register.filter
def pluralize_count(count, singular, plural=None):
    """Pluralize based on count."""
    if count == 1:
        return f"{count} {singular}"
    else:
        plural_form = plural or f"{singular}s"
        return f"{count} {plural_form}"


# Security helpers
@register.simple_tag
def csrf_token_input(request):
    """Generate CSRF token input field."""
    from django.middleware.csrf import get_token

    token = get_token(request)
    return format_html(
        '<input type="hidden" name="csrfmiddlewaretoken" value="{}">', token
    )


@register.simple_tag
def security_headers():
    """Generate security-related meta tags."""
    return mark_safe(
        '<meta http-equiv="X-Content-Type-Options" content="nosniff">'
        '<meta http-equiv="X-Frame-Options" content="DENY">'
        '<meta http-equiv="X-XSS-Protection" content="1; mode=block">'
    )


# List processing tags
@register.filter
def sort_by(queryset, field):
    """Sort queryset by field."""
    return queryset.order_by(field)


@register.filter
def filter_by_role(users, role_name):
    """Filter users by role."""
    return [user for user in users if user.has_role(role_name)]


@register.filter
def filter_active(users):
    """Filter only active users."""
    return [user for user in users if user.is_active]


# JSON helpers
@register.filter
def to_json(value):
    """Convert value to JSON string."""
    import json

    return json.dumps(value)


@register.simple_tag
def json_script(value, element_id):
    """Generate JSON script tag."""
    import json

    json_str = json.dumps(value)
    return format_html(
        '<script id="{}" type="application/json">{}</script>', element_id, json_str
    )


# URL helpers
@register.simple_tag(takes_context=True)
def query_transform(context, **kwargs):
    """Transform current query parameters."""
    request = context["request"]
    query = request.GET.copy()

    for k, v in kwargs.items():
        if v is not None:
            query[k] = v
        elif k in query:
            del query[k]

    return query.urlencode()


@register.simple_tag
def build_url(base_url, **params):
    """Build URL with query parameters."""
    from urllib.parse import urlencode

    if params:
        return f"{base_url}?{urlencode(params)}"
    return base_url
