# src/accounts/filters.py

import django_filters
from datetime import datetime, timedelta
from django import forms
from django.contrib.auth import get_user_model
from django.db.models import Count, Q
from django.utils import timezone

from .models import UserRole, UserRoleAssignment, UserAuditLog, UserSession

User = get_user_model()


class UserFilter(django_filters.FilterSet):
    """Advanced filtering for User model."""

    # Text search
    search = django_filters.CharFilter(
        method="filter_search",
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Search by name, email, username, or phone...",
            }
        ),
    )

    # Status filters
    is_active = django_filters.BooleanFilter(
        widget=forms.Select(
            choices=[(None, "All"), (True, "Active"), (False, "Inactive")],
            attrs={"class": "form-control"},
        )
    )

    email_verified = django_filters.BooleanFilter(
        widget=forms.Select(
            choices=[(None, "All"), (True, "Verified"), (False, "Unverified")],
            attrs={"class": "form-control"},
        )
    )

    phone_verified = django_filters.BooleanFilter(
        widget=forms.Select(
            choices=[(None, "All"), (True, "Verified"), (False, "Unverified")],
            attrs={"class": "form-control"},
        )
    )

    requires_password_change = django_filters.BooleanFilter(
        widget=forms.Select(
            choices=[(None, "All"), (True, "Required"), (False, "Not Required")],
            attrs={"class": "form-control"},
        )
    )

    two_factor_enabled = django_filters.BooleanFilter(
        widget=forms.Select(
            choices=[(None, "All"), (True, "Enabled"), (False, "Disabled")],
            attrs={"class": "form-control"},
        )
    )

    # Account security
    account_locked = django_filters.BooleanFilter(
        method="filter_account_locked",
        widget=forms.Select(
            choices=[(None, "All"), (True, "Locked"), (False, "Not Locked")],
            attrs={"class": "form-control"},
        ),
    )

    # Role filters
    role = django_filters.ModelChoiceFilter(
        field_name="role_assignments__role",
        queryset=UserRole.objects.filter(is_active=True),
        widget=forms.Select(attrs={"class": "form-control"}),
        empty_label="All Roles",
    )

    has_multiple_roles = django_filters.BooleanFilter(
        method="filter_multiple_roles",
        widget=forms.Select(
            choices=[
                (None, "All"),
                (True, "Multiple Roles"),
                (False, "Single/No Role"),
            ],
            attrs={"class": "form-control"},
        ),
    )

    no_roles = django_filters.BooleanFilter(
        method="filter_no_roles",
        widget=forms.Select(
            choices=[(None, "All"), (True, "No Roles"), (False, "Has Roles")],
            attrs={"class": "form-control"},
        ),
    )

    # Date filters
    date_joined_after = django_filters.DateFilter(
        field_name="date_joined",
        lookup_expr="gte",
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
    )

    date_joined_before = django_filters.DateFilter(
        field_name="date_joined",
        lookup_expr="lte",
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
    )

    last_login_after = django_filters.DateFilter(
        field_name="last_login",
        lookup_expr="gte",
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
    )

    last_login_before = django_filters.DateFilter(
        field_name="last_login",
        lookup_expr="lte",
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
    )

    # Activity filters
    recently_active = django_filters.ChoiceFilter(
        method="filter_recently_active",
        choices=[
            ("", "Any time"),
            ("1", "Last 24 hours"),
            ("7", "Last 7 days"),
            ("30", "Last 30 days"),
            ("90", "Last 90 days"),
        ],
        widget=forms.Select(attrs={"class": "form-control"}),
        empty_label=None,
    )

    inactive_period = django_filters.ChoiceFilter(
        method="filter_inactive_period",
        choices=[
            ("", "All users"),
            ("30", "Inactive 30+ days"),
            ("60", "Inactive 60+ days"),
            ("90", "Inactive 90+ days"),
            ("180", "Inactive 180+ days"),
            ("365", "Inactive 1+ year"),
        ],
        widget=forms.Select(attrs={"class": "form-control"}),
        empty_label=None,
    )

    # Demographics
    gender = django_filters.ChoiceFilter(
        choices=User.GENDER_CHOICES,
        widget=forms.Select(attrs={"class": "form-control"}),
        empty_label="All Genders",
    )

    age_range = django_filters.ChoiceFilter(
        method="filter_age_range",
        choices=[
            ("", "All ages"),
            ("13-17", "13-17 years"),
            ("18-25", "18-25 years"),
            ("26-35", "26-35 years"),
            ("36-45", "36-45 years"),
            ("46-60", "46-60 years"),
            ("60+", "60+ years"),
        ],
        widget=forms.Select(attrs={"class": "form-control"}),
        empty_label=None,
    )

    # Security filters
    failed_login_attempts = django_filters.RangeFilter(
        widget=django_filters.widgets.RangeWidget(attrs={"class": "form-control"})
    )

    security_score_range = django_filters.ChoiceFilter(
        method="filter_security_score",
        choices=[
            ("", "All scores"),
            ("high", "High (80-100)"),
            ("medium", "Medium (50-79)"),
            ("low", "Low (0-49)"),
        ],
        widget=forms.Select(attrs={"class": "form-control"}),
        empty_label=None,
    )

    class Meta:
        model = User
        fields = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add custom CSS classes to all widgets
        for field in self.form.fields.values():
            if "class" not in field.widget.attrs:
                field.widget.attrs["class"] = "form-control"

    def filter_search(self, queryset, name, value):
        """Filter by search term across multiple fields."""
        if not value:
            return queryset

        # Split search terms
        terms = value.split()

        for term in terms:
            queryset = queryset.filter(
                Q(username__icontains=term)
                | Q(email__icontains=term)
                | Q(first_name__icontains=term)
                | Q(last_name__icontains=term)
                | Q(phone_number__icontains=term)
            )

        return queryset

    def filter_account_locked(self, queryset, name, value):
        """Filter by account lock status."""
        if value is True:
            return queryset.filter(failed_login_attempts__gte=5)
        elif value is False:
            return queryset.filter(failed_login_attempts__lt=5)
        return queryset

    def filter_multiple_roles(self, queryset, name, value):
        """Filter users with multiple roles."""
        if value is True:
            return queryset.annotate(
                role_count=Count(
                    "role_assignments", filter=Q(role_assignments__is_active=True)
                )
            ).filter(role_count__gt=1)
        elif value is False:
            return queryset.annotate(
                role_count=Count(
                    "role_assignments", filter=Q(role_assignments__is_active=True)
                )
            ).filter(role_count__lte=1)
        return queryset

    def filter_no_roles(self, queryset, name, value):
        """Filter users without roles."""
        if value is True:
            return queryset.annotate(
                role_count=Count(
                    "role_assignments", filter=Q(role_assignments__is_active=True)
                )
            ).filter(role_count=0)
        elif value is False:
            return queryset.annotate(
                role_count=Count(
                    "role_assignments", filter=Q(role_assignments__is_active=True)
                )
            ).filter(role_count__gt=0)
        return queryset

    def filter_recently_active(self, queryset, name, value):
        """Filter by recent activity."""
        if not value:
            return queryset

        days = int(value)
        cutoff_date = timezone.now() - timedelta(days=days)
        return queryset.filter(last_login__gte=cutoff_date)

    def filter_inactive_period(self, queryset, name, value):
        """Filter by inactivity period."""
        if not value:
            return queryset

        days = int(value)
        cutoff_date = timezone.now() - timedelta(days=days)
        return queryset.filter(
            Q(last_login__lt=cutoff_date) | Q(last_login__isnull=True)
        )

    def filter_age_range(self, queryset, name, value):
        """Filter by age range."""
        if not value:
            return queryset

        today = timezone.now().date()

        if value == "13-17":
            min_birth = today - timedelta(days=17 * 365)
            max_birth = today - timedelta(days=13 * 365)
        elif value == "18-25":
            min_birth = today - timedelta(days=25 * 365)
            max_birth = today - timedelta(days=18 * 365)
        elif value == "26-35":
            min_birth = today - timedelta(days=35 * 365)
            max_birth = today - timedelta(days=26 * 365)
        elif value == "36-45":
            min_birth = today - timedelta(days=45 * 365)
            max_birth = today - timedelta(days=36 * 365)
        elif value == "46-60":
            min_birth = today - timedelta(days=60 * 365)
            max_birth = today - timedelta(days=46 * 365)
        elif value == "60+":
            min_birth = today - timedelta(days=120 * 365)  # Max reasonable age
            max_birth = today - timedelta(days=60 * 365)
        else:
            return queryset

        return queryset.filter(
            date_of_birth__gte=min_birth, date_of_birth__lte=max_birth
        )

    def filter_security_score(self, queryset, name, value):
        """Filter by security score range."""
        if not value:
            return queryset

        # This would require calculating security scores
        # For now, we'll use a placeholder based on verification status
        if value == "high":
            return queryset.filter(
                email_verified=True,
                phone_verified=True,
                two_factor_enabled=True,
                failed_login_attempts=0,
            )
        elif value == "medium":
            return queryset.filter(email_verified=True, failed_login_attempts__lt=3)
        elif value == "low":
            return queryset.filter(
                Q(email_verified=False) | Q(failed_login_attempts__gte=3)
            )

        return queryset


class UserRoleFilter(django_filters.FilterSet):
    """Advanced filtering for UserRole model."""

    name = django_filters.CharFilter(
        lookup_expr="icontains",
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Search role name..."}
        ),
    )

    description = django_filters.CharFilter(
        lookup_expr="icontains",
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Search description..."}
        ),
    )

    is_system_role = django_filters.BooleanFilter(
        widget=forms.Select(
            choices=[(None, "All"), (True, "System Roles"), (False, "Custom Roles")],
            attrs={"class": "form-control"},
        )
    )

    is_active = django_filters.BooleanFilter(
        widget=forms.Select(
            choices=[(None, "All"), (True, "Active"), (False, "Inactive")],
            attrs={"class": "form-control"},
        )
    )

    user_count_range = django_filters.ChoiceFilter(
        method="filter_user_count",
        choices=[
            ("", "Any count"),
            ("0", "No users"),
            ("1-10", "1-10 users"),
            ("11-50", "11-50 users"),
            ("51-100", "51-100 users"),
            ("100+", "100+ users"),
        ],
        widget=forms.Select(attrs={"class": "form-control"}),
        empty_label=None,
    )

    has_permission = django_filters.CharFilter(
        method="filter_has_permission",
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "e.g., users.view, students.add",
            }
        ),
    )

    class Meta:
        model = UserRole
        fields = []

    def filter_user_count(self, queryset, name, value):
        """Filter by user count ranges."""
        if not value:
            return queryset

        queryset = queryset.annotate(
            user_count=Count(
                "user_assignments", filter=Q(user_assignments__is_active=True)
            )
        )

        if value == "0":
            return queryset.filter(user_count=0)
        elif value == "1-10":
            return queryset.filter(user_count__gte=1, user_count__lte=10)
        elif value == "11-50":
            return queryset.filter(user_count__gte=11, user_count__lte=50)
        elif value == "51-100":
            return queryset.filter(user_count__gte=51, user_count__lte=100)
        elif value == "100+":
            return queryset.filter(user_count__gt=100)

        return queryset

    def filter_has_permission(self, queryset, name, value):
        """Filter roles that have specific permission."""
        if not value:
            return queryset

        try:
            resource, action = value.split(".")
            # This would need to search in the JSON permissions field
            # Implementation depends on your database backend
            return queryset.filter(permissions__has_key=resource).extra(
                where=["JSON_CONTAINS(permissions->'$.%s', %s)"],
                params=[resource, f'"{action}"'],
            )
        except (ValueError, AttributeError):
            return queryset


class UserAuditLogFilter(django_filters.FilterSet):
    """Advanced filtering for UserAuditLog model."""

    user = django_filters.ModelChoiceFilter(
        queryset=User.objects.all(),
        widget=forms.Select(attrs={"class": "form-control"}),
        empty_label="All Users",
    )

    action = django_filters.ChoiceFilter(
        choices=UserAuditLog.ACTION_CHOICES,
        widget=forms.Select(attrs={"class": "form-control"}),
        empty_label="All Actions",
    )

    severity = django_filters.ChoiceFilter(
        choices=UserAuditLog.SEVERITY_CHOICES,
        widget=forms.Select(attrs={"class": "form-control"}),
        empty_label="All Severities",
    )

    ip_address = django_filters.CharFilter(
        lookup_expr="exact",
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Filter by IP address..."}
        ),
    )

    timestamp_after = django_filters.DateTimeFilter(
        field_name="timestamp",
        lookup_expr="gte",
        widget=forms.DateTimeInput(
            attrs={"class": "form-control", "type": "datetime-local"}
        ),
    )

    timestamp_before = django_filters.DateTimeFilter(
        field_name="timestamp",
        lookup_expr="lte",
        widget=forms.DateTimeInput(
            attrs={"class": "form-control", "type": "datetime-local"}
        ),
    )

    description = django_filters.CharFilter(
        lookup_expr="icontains",
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Search description..."}
        ),
    )

    time_range = django_filters.ChoiceFilter(
        method="filter_time_range",
        choices=[
            ("", "All time"),
            ("1h", "Last hour"),
            ("24h", "Last 24 hours"),
            ("7d", "Last 7 days"),
            ("30d", "Last 30 days"),
            ("90d", "Last 90 days"),
        ],
        widget=forms.Select(attrs={"class": "form-control"}),
        empty_label=None,
    )

    security_events_only = django_filters.BooleanFilter(
        method="filter_security_events",
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )

    class Meta:
        model = UserAuditLog
        fields = []

    def filter_time_range(self, queryset, name, value):
        """Filter by predefined time ranges."""
        if not value:
            return queryset

        now = timezone.now()

        if value == "1h":
            cutoff = now - timedelta(hours=1)
        elif value == "24h":
            cutoff = now - timedelta(hours=24)
        elif value == "7d":
            cutoff = now - timedelta(days=7)
        elif value == "30d":
            cutoff = now - timedelta(days=30)
        elif value == "90d":
            cutoff = now - timedelta(days=90)
        else:
            return queryset

        return queryset.filter(timestamp__gte=cutoff)

    def filter_security_events(self, queryset, name, value):
        """Filter for security-related events only."""
        if value:
            security_actions = [
                "login",
                "logout",
                "password_change",
                "password_reset",
                "account_lock",
                "account_unlock",
                "2fa_enable",
                "2fa_disable",
                "email_verified",
                "phone_verified",
            ]
            return queryset.filter(action__in=security_actions)
        return queryset


class UserSessionFilter(django_filters.FilterSet):
    """Advanced filtering for UserSession model."""

    user = django_filters.ModelChoiceFilter(
        queryset=User.objects.all(),
        widget=forms.Select(attrs={"class": "form-control"}),
        empty_label="All Users",
    )

    is_active = django_filters.BooleanFilter(
        widget=forms.Select(
            choices=[(None, "All"), (True, "Active"), (False, "Inactive")],
            attrs={"class": "form-control"},
        )
    )

    ip_address = django_filters.CharFilter(
        lookup_expr="exact",
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Filter by IP address..."}
        ),
    )

    device_type = django_filters.ChoiceFilter(
        choices=[
            ("desktop", "Desktop"),
            ("mobile", "Mobile"),
            ("tablet", "Tablet"),
            ("unknown", "Unknown"),
        ],
        widget=forms.Select(attrs={"class": "form-control"}),
        empty_label="All Devices",
    )

    browser = django_filters.CharFilter(
        lookup_expr="icontains",
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Browser name..."}
        ),
    )

    country = django_filters.CharFilter(
        lookup_expr="icontains",
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Country..."}
        ),
    )

    session_duration = django_filters.ChoiceFilter(
        method="filter_session_duration",
        choices=[
            ("", "Any duration"),
            ("short", "Short (< 1 hour)"),
            ("medium", "Medium (1-8 hours)"),
            ("long", "Long (> 8 hours)"),
        ],
        widget=forms.Select(attrs={"class": "form-control"}),
        empty_label=None,
    )

    concurrent_sessions = django_filters.BooleanFilter(
        method="filter_concurrent_sessions",
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )

    class Meta:
        model = UserSession
        fields = []

    def filter_session_duration(self, queryset, name, value):
        """Filter by session duration categories."""
        if not value:
            return queryset

        now = timezone.now()

        if value == "short":
            # Sessions shorter than 1 hour
            cutoff = now - timedelta(hours=1)
            return queryset.filter(created_at__gte=cutoff)
        elif value == "medium":
            # Sessions between 1-8 hours
            short_cutoff = now - timedelta(hours=1)
            long_cutoff = now - timedelta(hours=8)
            return queryset.filter(
                created_at__lt=short_cutoff, created_at__gte=long_cutoff
            )
        elif value == "long":
            # Sessions longer than 8 hours
            cutoff = now - timedelta(hours=8)
            return queryset.filter(created_at__lt=cutoff)

        return queryset

    def filter_concurrent_sessions(self, queryset, name, value):
        """Filter users with concurrent sessions."""
        if value:
            # Find users with multiple active sessions
            concurrent_users = (
                User.objects.annotate(
                    active_session_count=Count(
                        "sessions", filter=Q(sessions__is_active=True)
                    )
                )
                .filter(active_session_count__gt=1)
                .values_list("id", flat=True)
            )

            return queryset.filter(user_id__in=concurrent_users, is_active=True)

        return queryset


# Custom filter widgets
class AdvancedDateRangeWidget(forms.MultiWidget):
    """Custom widget for date range filtering."""

    def __init__(self, attrs=None):
        widgets = [
            forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            forms.DateInput(attrs={"type": "date", "class": "form-control"}),
        ]
        super().__init__(widgets, attrs)

    def decompress(self, value):
        if value:
            return [value.start, value.stop]
        return [None, None]


class SecurityScoreRangeFilter(django_filters.Filter):
    """Custom filter for security score ranges."""

    def filter(self, qs, value):
        if not value:
            return qs

        # This would need to be implemented based on how security scores are calculated
        # For now, return the original queryset
        return qs


# Filter form helpers
def get_user_filter_form(data=None, queryset=None):
    """Get configured user filter form."""
    filter_obj = UserFilter(data, queryset=queryset)
    return filter_obj.form


def get_audit_log_filter_form(data=None, queryset=None):
    """Get configured audit log filter form."""
    filter_obj = UserAuditLogFilter(data, queryset=queryset)
    return filter_obj.form


def apply_common_filters(queryset, filter_data):
    """Apply common filters to any queryset."""
    if not filter_data:
        return queryset

    # Date range filtering
    if filter_data.get("date_from"):
        queryset = queryset.filter(created_at__gte=filter_data["date_from"])

    if filter_data.get("date_to"):
        queryset = queryset.filter(created_at__lte=filter_data["date_to"])

    # Status filtering
    if filter_data.get("is_active") is not None:
        queryset = queryset.filter(is_active=filter_data["is_active"])

    return queryset
