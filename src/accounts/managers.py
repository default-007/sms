from django.contrib.auth.models import BaseUserManager
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Count, Prefetch, Q
from django.utils.translation import gettext_lazy as _


class UserManager(BaseUserManager):
    """Enhanced manager for User model with additional query methods."""

    def create_user(self, username, email, password=None, **extra_fields):
        """Create and save a regular user with the given username, email, and password."""
        if not username:
            raise ValueError(_("The Username must be set"))
        if not email:
            raise ValueError(_("The Email must be set"))

        email = self.normalize_email(email)

        # Validate email format
        from django.core.validators import validate_email

        try:
            validate_email(email)
        except ValidationError:
            raise ValueError(_("Invalid email format"))

        user = self.model(username=username, email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, email, password=None, **extra_fields):
        """Create and save a superuser with the given username, email, and password."""
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError(_("Superuser must have is_staff=True."))
        if extra_fields.get("is_superuser") is not True:
            raise ValueError(_("Superuser must have is_superuser=True."))

        return self.create_user(username, email, password, **extra_fields)

    def active(self):
        """Return only active users."""
        return self.filter(is_active=True)

    def inactive(self):
        """Return only inactive users."""
        return self.filter(is_active=False)

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

    def search(self, query):
        """Search users by username, email, first name, or last name."""
        if not query:
            return self.all()

        return self.filter(
            Q(username__icontains=query)
            | Q(email__icontains=query)
            | Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
        )

    def recent_registrations(self, days=30):
        """Return users registered in the last N days."""
        from datetime import timedelta

        from django.utils import timezone

        cutoff_date = timezone.now() - timedelta(days=days)
        return self.filter(date_joined__gte=cutoff_date)

    def requiring_password_change(self):
        """Return users that require password change."""
        return self.filter(requires_password_change=True, is_active=True)

    def locked_accounts(self):
        """Return accounts that are locked due to failed login attempts."""
        from datetime import timedelta

        from django.utils import timezone

        lockout_time = timezone.now() - timedelta(minutes=30)
        return self.filter(
            failed_login_attempts__gte=5, last_failed_login__gt=lockout_time
        )

    def get_statistics(self):
        """Get user statistics."""
        from datetime import timedelta

        from django.utils import timezone

        total = self.count()
        active = self.active().count()
        inactive = self.inactive().count()

        thirty_days_ago = timezone.now() - timedelta(days=30)
        recent = self.filter(date_joined__gte=thirty_days_ago).count()

        requiring_password_change = self.requiring_password_change().count()
        locked = self.locked_accounts().count()

        return {
            "total": total,
            "active": active,
            "inactive": inactive,
            "recent_registrations": recent,
            "requiring_password_change": requiring_password_change,
            "locked_accounts": locked,
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

    def bulk_create_users(self, user_data_list):
        """Efficiently create multiple users."""
        users = []
        for data in user_data_list:
            password = data.pop("password")
            user = self.model(**data)
            user.set_password(password)
            users.append(user)
        return self.bulk_create(users)


class UserRoleManager(models.Manager):
    """Enhanced manager for UserRole model."""

    def system_roles(self):
        """Return only system-defined roles."""
        return self.filter(is_system_role=True)

    def custom_roles(self):
        """Return only custom roles."""
        return self.filter(is_system_role=False)

    def with_user_counts(self):
        """Return roles with user assignment counts."""
        return self.annotate(
            user_count=Count(
                "user_assignments", filter=Q(user_assignments__is_active=True)
            )
        )

    def get_role_statistics(self):
        """Get role assignment statistics."""
        return self.with_user_counts().values(
            "id", "name", "description", "user_count", "is_system_role"
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


class UserRoleAssignmentManager(models.Manager):
    """Enhanced manager for UserRoleAssignment model."""

    def active(self):
        """Return only active assignments."""
        return self.filter(is_active=True)

    def inactive(self):
        """Return only inactive assignments."""
        return self.filter(is_active=False)

    def expired(self):
        """Return expired assignments."""
        from django.utils import timezone

        return self.filter(expires_at__lt=timezone.now(), is_active=True)

    def expiring_soon(self, days=7):
        """Return assignments expiring within N days."""
        from datetime import timedelta

        from django.utils import timezone

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
        from django.utils import timezone

        active = self.active().count()
        inactive = self.inactive().count()
        expired = self.expired().count()
        expiring_soon = self.expiring_soon().count()

        return {
            "active": active,
            "inactive": inactive,
            "expired": expired,
            "expiring_soon": expiring_soon,
        }


class UserAuditLogManager(models.Manager):
    """Enhanced manager for UserAuditLog model."""

    def by_user(self, user):
        """Get audit logs for a specific user."""
        return self.filter(user=user).order_by("-timestamp")

    def by_action(self, action):
        """Get audit logs for a specific action."""
        return self.filter(action=action).order_by("-timestamp")

    def recent(self, days=30):
        """Get recent audit logs."""
        from datetime import timedelta

        from django.utils import timezone

        cutoff_date = timezone.now() - timedelta(days=days)
        return self.filter(timestamp__gte=cutoff_date).order_by("-timestamp")

    def logins(self):
        """Get login audit logs."""
        return self.filter(action="login").order_by("-timestamp")

    def security_events(self):
        """Get security-related audit logs."""
        security_actions = [
            "login",
            "logout",
            "password_change",
            "account_lock",
            "account_unlock",
        ]
        return self.filter(action__in=security_actions).order_by("-timestamp")

    def role_changes(self):
        """Get role-related audit logs."""
        role_actions = ["role_assign", "role_remove"]
        return self.filter(action__in=role_actions).order_by("-timestamp")

    def cleanup_old_logs(self, days=365):
        """Clean up old audit logs."""
        from datetime import timedelta

        from django.utils import timezone

        cutoff_date = timezone.now() - timedelta(days=days)
        deleted_count, _ = self.filter(timestamp__lt=cutoff_date).delete()
        return deleted_count

    def get_activity_summary(self, user=None, days=30):
        """Get activity summary for a user or all users."""
        from datetime import timedelta

        from django.db.models import Count
        from django.utils import timezone

        cutoff_date = timezone.now() - timedelta(days=days)
        queryset = self.filter(timestamp__gte=cutoff_date)

        if user:
            queryset = queryset.filter(user=user)

        return queryset.values("action").annotate(count=Count("id")).order_by("-count")


class UserSessionManager(models.Manager):
    """Enhanced manager for UserSession model."""

    def active(self):
        """Return only active sessions."""
        return self.filter(is_active=True)

    def by_user(self, user):
        """Get sessions for a specific user."""
        return self.filter(user=user).order_by("-last_activity")

    def recent(self, days=30):
        """Get recent sessions."""
        from datetime import timedelta

        from django.utils import timezone

        cutoff_date = timezone.now() - timedelta(days=days)
        return self.filter(last_activity__gte=cutoff_date)

    def cleanup_old_sessions(self, days=30):
        """Clean up old inactive sessions."""
        from datetime import timedelta

        from django.utils import timezone

        cutoff_date = timezone.now() - timedelta(days=days)
        deleted_count, _ = self.filter(
            last_activity__lt=cutoff_date, is_active=False
        ).delete()
        return deleted_count

    def get_concurrent_sessions(self, user):
        """Get concurrent active sessions for a user."""
        return self.filter(user=user, is_active=True).count()

    def terminate_user_sessions(self, user, exclude_session=None):
        """Terminate all sessions for a user except the current one."""
        sessions = self.filter(user=user, is_active=True)

        if exclude_session:
            sessions = sessions.exclude(session_key=exclude_session)

        return sessions.update(is_active=False)
