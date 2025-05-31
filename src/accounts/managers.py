# src/accounts/managers.py

import re
from datetime import timedelta
from typing import Dict, List, Optional

from django.contrib.auth.models import BaseUserManager
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import models
from django.db.models import Count, Prefetch, Q, Avg, Max, Min, F
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class UserManager(BaseUserManager):
    """Enhanced manager for User model with comprehensive query methods."""

    def create_user(self, email, password=None, **extra_fields):
        """Create and save a regular user with the given email and password."""
        if not email:
            raise ValueError(_("The Email must be set"))

        email = self.normalize_email(email)

        # Validate email format
        try:
            validate_email(email)
        except ValidationError:
            raise ValueError(_("Invalid email format"))

        # Generate username if not provided
        username = extra_fields.get("username")
        if not username:
            username = self._generate_username_from_email(email)
            extra_fields["username"] = username

        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        """Create and save a superuser with the given email and password."""
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError(_("Superuser must have is_staff=True."))
        if extra_fields.get("is_superuser") is not True:
            raise ValueError(_("Superuser must have is_superuser=True."))

        return self.create_user(email, password, **extra_fields)

    def _generate_username_from_email(self, email):
        """Generate a unique username from email."""
        base_username = email.split("@")[0]
        # Clean username
        base_username = re.sub(r"[^a-zA-Z0-9_]", "", base_username)

        username = base_username
        counter = 1
        while self.filter(username=username).exists():
            username = f"{base_username}{counter}"
            counter += 1
        return username

    def find_by_identifier(self, identifier):
        """Find user by email, phone, or username."""
        identifier = identifier.strip()

        # Try email first
        try:
            validate_email(identifier)
            return self.filter(email=identifier).first()
        except ValidationError:
            pass

        # Try phone number
        phone_pattern = re.compile(r"^\+?[\d\s\-\(\)]{10,15}$")
        if phone_pattern.match(identifier):
            clean_phone = re.sub(r"[\s\-\(\)]", "", identifier)
            return self.filter(phone_number__icontains=clean_phone).first()

        # Try username
        return self.filter(username=identifier).first()

    def active(self):
        """Return only active users."""
        return self.filter(is_active=True)

    def inactive(self):
        """Return only inactive users."""
        return self.filter(is_active=False)

    def verified(self):
        """Return users with verified email."""
        return self.filter(email_verified=True)

    def unverified(self):
        """Return users with unverified email."""
        return self.filter(email_verified=False)

    def with_complete_profiles(self):
        """Return users with complete profile information."""
        return self.exclude(
            Q(first_name="")
            | Q(last_name="")
            | Q(phone_number="")
            | Q(date_of_birth__isnull=True)
            | Q(profile_picture="")
        )

    def with_roles(self):
        """Return users with their roles prefetched."""
        from .models import UserRoleAssignment

        return self.prefetch_related(
            Prefetch(
                "role_assignments",
                queryset=UserRoleAssignment.objects.select_related("role").filter(
                    is_active=True
                ),
                to_attr="active_role_assignments",
            )
        )

    def by_role(self, role_name):
        """Return users with a specific role."""
        return self.filter(
            role_assignments__role__name=role_name, role_assignments__is_active=True
        ).distinct()

    def by_multiple_roles(self, role_names):
        """Return users with any of the specified roles."""
        return self.filter(
            role_assignments__role__name__in=role_names,
            role_assignments__is_active=True,
        ).distinct()

    def without_roles(self):
        """Return users without any active roles."""
        return self.filter(~Q(role_assignments__is_active=True)).distinct()

    def with_multiple_roles(self):
        """Return users with multiple active roles."""
        return self.annotate(
            role_count=Count(
                "role_assignments", filter=Q(role_assignments__is_active=True)
            )
        ).filter(role_count__gt=1)

    def search(self, query):
        """Enhanced search by username, email, first name, last name, or phone."""
        if not query:
            return self.all()

        # Split query into terms for better matching
        terms = query.split()
        q_objects = Q()

        for term in terms:
            q_objects |= (
                Q(username__icontains=term)
                | Q(email__icontains=term)
                | Q(first_name__icontains=term)
                | Q(last_name__icontains=term)
                | Q(phone_number__icontains=term)
            )

        return self.filter(q_objects)

    def recent_registrations(self, days=30):
        """Return users registered in the last N days."""
        cutoff_date = timezone.now() - timedelta(days=days)
        return self.filter(date_joined__gte=cutoff_date)

    def recent_logins(self, days=7):
        """Return users who logged in recently."""
        cutoff_date = timezone.now() - timedelta(days=days)
        return self.filter(last_login__gte=cutoff_date)

    def inactive_users(self, days=90):
        """Return users who haven't logged in for N days."""
        cutoff_date = timezone.now() - timedelta(days=days)
        return self.filter(
            Q(last_login__lt=cutoff_date) | Q(last_login__isnull=True), is_active=True
        )

    def requiring_password_change(self):
        """Return users that require password change."""
        return self.filter(requires_password_change=True, is_active=True)

    def locked_accounts(self):
        """Return accounts that are locked due to failed login attempts."""
        return self.filter(failed_login_attempts__gte=5, is_active=True)

    def password_expired(self, max_age_days=90):
        """Return users with expired passwords."""
        expiry_date = timezone.now() - timedelta(days=max_age_days)
        return self.filter(password_changed_at__lt=expiry_date, is_active=True)

    def by_security_score_range(self, min_score=0, max_score=100):
        """Return users within a security score range (would need custom implementation)."""
        # This would require a security score field or calculation
        # For now, return all users
        return self.all()

    def get_statistics(self):
        """Get comprehensive user statistics."""
        total = self.count()
        active = self.active().count()
        inactive = self.inactive().count()
        verified = self.verified().count()
        unverified = self.unverified().count()

        thirty_days_ago = timezone.now() - timedelta(days=30)
        recent = self.filter(date_joined__gte=thirty_days_ago).count()

        requiring_password_change = self.requiring_password_change().count()
        locked = self.locked_accounts().count()

        return {
            "total": total,
            "active": active,
            "inactive": inactive,
            "verified": verified,
            "unverified": unverified,
            "recent_registrations": recent,
            "requiring_password_change": requiring_password_change,
            "locked_accounts": locked,
            "completion_rate": (verified / total * 100) if total > 0 else 0,
        }

    def get_activity_statistics(self, days=30):
        """Get user activity statistics."""
        cutoff_date = timezone.now() - timedelta(days=days)

        total_users = self.active().count()
        active_users = self.filter(last_login__gte=cutoff_date).count()

        # Users by login frequency
        highly_active = self.filter(
            last_login__gte=timezone.now() - timedelta(days=7)
        ).count()

        moderately_active = self.filter(
            last_login__gte=timezone.now() - timedelta(days=30),
            last_login__lt=timezone.now() - timedelta(days=7),
        ).count()

        inactive = total_users - active_users

        return {
            "total_users": total_users,
            "active_users": active_users,
            "highly_active": highly_active,
            "moderately_active": moderately_active,
            "inactive": inactive,
            "activity_rate": (
                (active_users / total_users * 100) if total_users > 0 else 0
            ),
        }

    def bulk_activate(self, user_ids):
        """Bulk activate users."""
        return self.filter(id__in=user_ids).update(is_active=True)

    def bulk_deactivate(self, user_ids):
        """Bulk deactivate users."""
        return self.filter(id__in=user_ids).update(is_active=False)

    def bulk_require_password_change(self, user_ids):
        """Bulk require password change for users."""
        return self.filter(id__in=user_ids).update(requires_password_change=True)

    def bulk_unlock(self, user_ids):
        """Bulk unlock user accounts."""
        return self.filter(id__in=user_ids).update(
            failed_login_attempts=0, last_failed_login=None
        )

    def export_data(self, fields=None):
        """Export user data for reporting."""
        if fields is None:
            fields = [
                "username",
                "email",
                "first_name",
                "last_name",
                "is_active",
                "date_joined",
                "last_login",
            ]

        return self.values(*fields)


class UserRoleManager(models.Manager):
    """Enhanced manager for UserRole model."""

    def system_roles(self):
        """Return only system-defined roles."""
        return self.filter(is_system_role=True)

    def custom_roles(self):
        """Return only custom roles."""
        return self.filter(is_system_role=False)

    def active_roles(self):
        """Return only active roles."""
        return self.filter(is_active=True)

    def with_user_counts(self):
        """Return roles with user assignment counts."""
        return self.annotate(
            user_count=Count(
                "user_assignments", filter=Q(user_assignments__is_active=True)
            ),
            total_assignments=Count("user_assignments"),
        )

    def popular_roles(self, limit=10):
        """Return most popular roles by user count."""
        return self.with_user_counts().order_by("-user_count")[:limit]

    def search(self, query):
        """Search roles by name or description."""
        if not query:
            return self.all()

        return self.filter(Q(name__icontains=query) | Q(description__icontains=query))

    def by_permission(self, resource, action):
        """Return roles that have a specific permission."""
        # This would need to check the JSON permissions field
        return self.filter(permissions__has_key=resource).extra(
            where=["JSON_CONTAINS(permissions->'$.%s', %s)"],
            params=[resource, f'"{action}"'],
        )

    def hierarchical(self):
        """Return roles with their hierarchy."""
        return self.select_related("parent_role").prefetch_related("child_roles")

    def get_role_statistics(self):
        """Get role assignment statistics."""
        return self.with_user_counts().values(
            "id",
            "name",
            "description",
            "user_count",
            "total_assignments",
            "is_system_role",
            "is_active",
        )

    def validate_permissions(self, permissions):
        """Validate permission structure."""
        from .constants import PERMISSION_SCOPES

        if not isinstance(permissions, dict):
            raise ValidationError("Permissions must be a dictionary")

        for resource, actions in permissions.items():
            if resource not in PERMISSION_SCOPES:
                raise ValidationError(f"Invalid resource: {resource}")

            if not isinstance(actions, list):
                raise ValidationError(
                    f"Actions for resource '{resource}' must be a list"
                )

            available_actions = list(PERMISSION_SCOPES[resource].keys())
            for action in actions:
                if action not in available_actions:
                    raise ValidationError(
                        f"Invalid action '{action}' for resource '{resource}'"
                    )

        return True


class UserRoleAssignmentManager(models.Manager):
    """Enhanced manager for UserRoleAssignment model."""

    def active(self):
        """Return only active assignments."""
        return self.filter(is_active=True)

    def inactive(self):
        """Return only inactive assignments."""
        return self.filter(is_active=False)

    def approved(self):
        """Return only approved assignments."""
        return self.filter(approved_at__isnull=False)

    def pending_approval(self):
        """Return assignments pending approval."""
        return self.filter(requires_approval=True, approved_at__isnull=True)

    def expired(self):
        """Return expired assignments."""
        return self.filter(expires_at__lt=timezone.now(), is_active=True)

    def expiring_soon(self, days=7):
        """Return assignments expiring within N days."""
        expiry_date = timezone.now() + timedelta(days=days)
        return self.filter(
            expires_at__lte=expiry_date, expires_at__gt=timezone.now(), is_active=True
        )

    def by_user(self, user):
        """Get assignments for a specific user."""
        return self.filter(user=user, is_active=True).select_related("role")

    def by_role(self, role):
        """Get assignments for a specific role."""
        return self.filter(role=role, is_active=True).select_related("user")

    def by_date_range(self, start_date, end_date):
        """Get assignments within a date range."""
        return self.filter(assigned_date__range=[start_date, end_date])

    def recent_assignments(self, days=30):
        """Get recent role assignments."""
        cutoff_date = timezone.now() - timedelta(days=days)
        return self.filter(assigned_date__gte=cutoff_date)

    def long_term_assignments(self, days=365):
        """Get long-term role assignments."""
        cutoff_date = timezone.now() - timedelta(days=days)
        return self.filter(assigned_date__lt=cutoff_date, is_active=True)

    def cleanup_expired(self):
        """Deactivate expired assignments."""
        expired_assignments = self.expired()
        count = expired_assignments.update(is_active=False)

        # Clear cache for affected users
        from django.core.cache import cache

        for assignment in expired_assignments:
            cache.delete(f"user_permissions_{assignment.user.pk}")
            cache.delete(f"user_roles_{assignment.user.pk}")

        return count

    def get_assignment_statistics(self):
        """Get assignment statistics."""
        active = self.active().count()
        inactive = self.inactive().count()
        expired = self.expired().count()
        expiring_soon = self.expiring_soon().count()
        pending_approval = self.pending_approval().count()

        return {
            "active": active,
            "inactive": inactive,
            "expired": expired,
            "expiring_soon": expiring_soon,
            "pending_approval": pending_approval,
            "total": active + inactive,
        }

    def get_assignment_trends(self, days=30):
        """Get assignment trends over time."""
        cutoff_date = timezone.now() - timedelta(days=days)

        return (
            self.filter(assigned_date__gte=cutoff_date)
            .extra(select={"day": "DATE(assigned_date)"})
            .values("day")
            .annotate(count=Count("id"))
            .order_by("day")
        )


class UserAuditLogManager(models.Manager):
    """Enhanced manager for UserAuditLog model."""

    def by_user(self, user):
        """Get audit logs for a specific user."""
        return self.filter(user=user).order_by("-timestamp")

    def by_action(self, action):
        """Get audit logs for a specific action."""
        return self.filter(action=action).order_by("-timestamp")

    def by_severity(self, severity):
        """Get audit logs by severity level."""
        return self.filter(severity=severity).order_by("-timestamp")

    def security_events(self):
        """Get security-related audit logs."""
        security_actions = [
            "login",
            "logout",
            "password_change",
            "password_reset",
            "account_lock",
            "account_unlock",
            "2fa_enable",
            "2fa_disable",
        ]
        return self.filter(action__in=security_actions).order_by("-timestamp")

    def critical_events(self):
        """Get critical security events."""
        return self.filter(severity="critical").order_by("-timestamp")

    def role_changes(self):
        """Get role-related audit logs."""
        role_actions = ["role_assign", "role_remove"]
        return self.filter(action__in=role_actions).order_by("-timestamp")

    def login_attempts(self):
        """Get all login attempts."""
        return self.filter(action="login").order_by("-timestamp")

    def failed_logins(self):
        """Get failed login attempts."""
        return self.filter(action="login", description__contains="Failed").order_by(
            "-timestamp"
        )

    def successful_logins(self):
        """Get successful login attempts."""
        return self.filter(action="login", description__contains="Successful").order_by(
            "-timestamp"
        )

    def recent(self, days=30):
        """Get recent audit logs."""
        cutoff_date = timezone.now() - timedelta(days=days)
        return self.filter(timestamp__gte=cutoff_date).order_by("-timestamp")

    def by_ip_address(self, ip_address):
        """Get logs from a specific IP address."""
        return self.filter(ip_address=ip_address).order_by("-timestamp")

    def suspicious_activity(self, threshold_hours=24):
        """Get potentially suspicious activity."""
        since = timezone.now() - timedelta(hours=threshold_hours)

        # Multiple failed logins from same IP
        return (
            self.filter(
                timestamp__gte=since, action="login", description__contains="Failed"
            )
            .values("ip_address")
            .annotate(attempt_count=Count("id"))
            .filter(attempt_count__gte=5)
        )

    def cleanup_old_logs(self, days=365):
        """Clean up old audit logs."""
        cutoff_date = timezone.now() - timedelta(days=days)
        deleted_count, _ = self.filter(timestamp__lt=cutoff_date).delete()
        return deleted_count

    def get_activity_summary(self, user=None, days=30):
        """Get activity summary for a user or all users."""
        cutoff_date = timezone.now() - timedelta(days=days)
        queryset = self.filter(timestamp__gte=cutoff_date)

        if user:
            queryset = queryset.filter(user=user)

        return queryset.values("action").annotate(count=Count("id")).order_by("-count")

    def get_login_statistics(self, days=30):
        """Get login statistics."""
        cutoff_date = timezone.now() - timedelta(days=days)

        login_logs = self.filter(action="login", timestamp__gte=cutoff_date)

        total_attempts = login_logs.count()
        successful = login_logs.filter(description__contains="Successful").count()
        failed = total_attempts - successful

        return {
            "total_attempts": total_attempts,
            "successful_logins": successful,
            "failed_logins": failed,
            "success_rate": (
                (successful / total_attempts * 100) if total_attempts > 0 else 0
            ),
        }

    def get_user_activity_report(self, user, days=30):
        """Get detailed activity report for a user."""
        cutoff_date = timezone.now() - timedelta(days=days)

        user_logs = self.filter(user=user, timestamp__gte=cutoff_date)

        activities = (
            user_logs.values("action")
            .annotate(count=Count("id"), last_occurrence=Max("timestamp"))
            .order_by("-count")
        )

        return {
            "total_activities": user_logs.count(),
            "activities": list(activities),
            "period_days": days,
        }


class UserSessionManager(models.Manager):
    """Enhanced manager for UserSession model."""

    def active(self):
        """Return only active sessions."""
        return self.filter(is_active=True)

    def inactive(self):
        """Return only inactive sessions."""
        return self.filter(is_active=False)

    def by_user(self, user):
        """Get sessions for a specific user."""
        return self.filter(user=user).order_by("-last_activity")

    def recent(self, days=30):
        """Get recent sessions."""
        cutoff_date = timezone.now() - timedelta(days=days)
        return self.filter(last_activity__gte=cutoff_date)

    def by_ip_address(self, ip_address):
        """Get sessions from a specific IP address."""
        return self.filter(ip_address=ip_address).order_by("-last_activity")

    def by_device_type(self, device_type):
        """Get sessions by device type."""
        return self.filter(device_type=device_type).order_by("-last_activity")

    def expired_sessions(self, timeout_minutes=30):
        """Get sessions that have expired."""
        cutoff_time = timezone.now() - timedelta(minutes=timeout_minutes)
        return self.filter(last_activity__lt=cutoff_time, is_active=True)

    def long_sessions(self, hours=8):
        """Get sessions longer than specified hours."""
        cutoff_time = timezone.now() - timedelta(hours=hours)
        return self.filter(created_at__lt=cutoff_time, is_active=True)

    def concurrent_sessions(self, user):
        """Get concurrent sessions for a user."""
        return self.filter(user=user, is_active=True).count()

    def get_concurrent_users(self):
        """Get count of users with concurrent sessions."""
        return self.active().values("user").distinct().count()

    def cleanup_old_sessions(self, days=30):
        """Clean up old inactive sessions."""
        cutoff_date = timezone.now() - timedelta(days=days)
        deleted_count, _ = self.filter(
            last_activity__lt=cutoff_date, is_active=False
        ).delete()
        return deleted_count

    def terminate_user_sessions(self, user, exclude_session=None):
        """Terminate all sessions for a user except the current one."""
        sessions = self.filter(user=user, is_active=True)

        if exclude_session:
            sessions = sessions.exclude(session_key=exclude_session)

        return sessions.update(is_active=False, logout_reason="admin")

    def get_session_statistics(self, days=30):
        """Get session statistics."""
        cutoff_date = timezone.now() - timedelta(days=days)

        recent_sessions = self.filter(created_at__gte=cutoff_date)

        total_sessions = recent_sessions.count()
        active_sessions = self.active().count()
        unique_users = recent_sessions.values("user").distinct().count()

        # Device type distribution
        device_stats = (
            recent_sessions.values("device_type")
            .annotate(count=Count("id"))
            .order_by("-count")
        )

        # Browser distribution
        browser_stats = (
            recent_sessions.values("browser")
            .annotate(count=Count("id"))
            .order_by("-count")[:10]
        )

        return {
            "total_sessions": total_sessions,
            "active_sessions": active_sessions,
            "unique_users": unique_users,
            "avg_sessions_per_user": (
                total_sessions / unique_users if unique_users > 0 else 0
            ),
            "device_distribution": list(device_stats),
            "browser_distribution": list(browser_stats),
        }

    def get_geographic_distribution(self, days=30):
        """Get geographic distribution of sessions."""
        cutoff_date = timezone.now() - timedelta(days=days)

        return (
            self.filter(created_at__gte=cutoff_date)
            .exclude(country="")
            .values("country", "city")
            .annotate(
                session_count=Count("id"), user_count=Count("user", distinct=True)
            )
            .order_by("-session_count")[:20]
        )
