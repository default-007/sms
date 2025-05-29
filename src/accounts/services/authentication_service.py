# src/accounts/services/authentication_service.py

import hashlib
import logging
import secrets

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken
from rest_framework_simplejwt.tokens import RefreshToken

from ..models import UserAuditLog, UserSession
from ..utils import get_client_info, send_notification_email

logger = logging.getLogger(__name__)
User = get_user_model()


class AuthenticationService:
    """Enhanced service for handling authentication-related operations."""

    @staticmethod
    def generate_tokens_for_user(user):
        """Generate JWT tokens for a user."""
        refresh = RefreshToken.for_user(user)
        return {
            "refresh": str(refresh),
            "access": str(refresh.access_token),
            "expires_in": settings.SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"].total_seconds(),
        }

    @staticmethod
    def update_last_login(user):
        """Update the last login timestamp for a user."""
        user.last_login = timezone.now()
        user.save(update_fields=["last_login"])

    @staticmethod
    def authenticate_user(username, password, request=None):
        """
        Authenticate a user with username and password.
        Returns: (user_object, authentication_result)
        """
        client_info = get_client_info(request) if request else {}

        try:
            # Try to find user by username or email
            user = User.objects.get(Q(username=username) | Q(email=username))

            # Check if account is locked
            if user.is_account_locked():
                AuthenticationService._log_failed_attempt(
                    user, "Account locked", client_info
                )
                return None, "account_locked"

            # Check password
            if user.check_password(password):
                if user.is_active:
                    # Successful authentication
                    user.reset_failed_login_attempts()
                    AuthenticationService.update_last_login(user)

                    # Create audit log
                    UserAuditLog.objects.create(
                        user=user,
                        action="login",
                        description="Successful authentication",
                        ip_address=client_info.get("ip_address"),
                        user_agent=client_info.get("user_agent"),
                        extra_data=client_info,
                    )

                    # Create or update session record
                    if request and hasattr(request, "session"):
                        AuthenticationService._create_session_record(user, request)

                    return user, "success"
                else:
                    AuthenticationService._log_failed_attempt(
                        user, "Account inactive", client_info
                    )
                    return None, "account_inactive"
            else:
                # Invalid password
                user.increment_failed_login_attempts()
                AuthenticationService._log_failed_attempt(
                    user,
                    f"Invalid password (attempt #{user.failed_login_attempts})",
                    client_info,
                )
                return None, "invalid_credentials"

        except User.DoesNotExist:
            # Log failed attempt for non-existent user
            UserAuditLog.objects.create(
                user=None,
                action="login",
                description=f"Failed login attempt for non-existent user: {username}",
                ip_address=client_info.get("ip_address"),
                user_agent=client_info.get("user_agent"),
                extra_data=client_info,
            )
            return None, "user_not_found"

    @staticmethod
    def _log_failed_attempt(user, reason, client_info):
        """Log failed authentication attempt."""
        UserAuditLog.objects.create(
            user=user,
            action="login",
            description=f"Failed authentication: {reason}",
            ip_address=client_info.get("ip_address"),
            user_agent=client_info.get("user_agent"),
            extra_data=client_info,
        )

    @staticmethod
    def _create_session_record(user, request):
        """Create or update session record."""
        if not request.session.session_key:
            request.session.create()

        client_info = get_client_info(request)

        session_obj, created = UserSession.objects.get_or_create(
            session_key=request.session.session_key,
            defaults={
                "user": user,
                "ip_address": client_info["ip_address"],
                "user_agent": client_info["user_agent"],
                "is_active": True,
            },
        )

        if not created:
            session_obj.user = user
            session_obj.last_activity = timezone.now()
            session_obj.is_active = True
            session_obj.save(update_fields=["user", "last_activity", "is_active"])

    @staticmethod
    @transaction.atomic
    def register_user(user_data, role_names=None, created_by=None, send_email=True):
        """Register a new user with optional roles and email notification."""
        from .role_service import RoleService

        # Create the user
        password = user_data.pop("password", None)
        if not password:
            password = secrets.token_urlsafe(12)  # Generate secure password

        user = User.objects.create(**user_data)
        user.set_password(password)
        user.requires_password_change = True
        user.save()

        # Assign roles if provided
        if role_names:
            for role_name in role_names:
                try:
                    RoleService.assign_role_to_user(
                        user, role_name, assigned_by=created_by
                    )
                except ValueError as e:
                    logger.warning(f"Could not assign role {role_name}: {e}")

        # Create audit log
        UserAuditLog.objects.create(
            user=user,
            action="create",
            description=f'User account created{"" if not created_by else f" by {created_by.username}"}',
            performed_by=created_by,
            extra_data={"roles": role_names or []},
        )

        # Send welcome email if requested
        if send_email:
            try:
                send_notification_email(
                    user,
                    "Welcome to the School Management System",
                    "accounts/emails/account_created.html",
                    {
                        "temporary_password": password,
                        "created_by": created_by,
                    },
                )
            except Exception as e:
                logger.error(f"Failed to send welcome email to {user.email}: {e}")

        return user

    @staticmethod
    def logout_user(user, request=None):
        """Log out a user and clean up session data."""
        # Create audit log
        client_info = get_client_info(request) if request else {}
        UserAuditLog.objects.create(
            user=user,
            action="logout",
            description="User logged out",
            ip_address=client_info.get("ip_address"),
            user_agent=client_info.get("user_agent"),
            extra_data=client_info,
        )

        # Deactivate session record
        if request and hasattr(request, "session") and request.session.session_key:
            UserSession.objects.filter(session_key=request.session.session_key).update(
                is_active=False
            )
            # Clear session data
            request.session.flush()

    @staticmethod
    def change_password(user, old_password, new_password, request=None):
        """Change user password with validation and logging."""
        # Verify old password
        if not user.check_password(old_password):
            return False, "Current password is incorrect"

        # Set new password
        user.set_password(new_password)
        user.password_changed_at = timezone.now()
        user.requires_password_change = False
        user.save(
            update_fields=[
                "password",
                "password_changed_at",
                "requires_password_change",
            ]
        )

        # Create audit log
        client_info = get_client_info(request) if request else {}
        UserAuditLog.objects.create(
            user=user,
            action="password_change",
            description="Password changed by user",
            ip_address=client_info.get("ip_address"),
            user_agent=client_info.get("user_agent"),
            extra_data=client_info,
        )

        # Send notification email
        try:
            send_notification_email(
                user,
                "Password Changed Successfully",
                "accounts/emails/password_changed.html",
                {"client_info": client_info},
            )
        except Exception as e:
            logger.error(f"Failed to send password change notification: {e}")

        return True, "Password changed successfully"

    @staticmethod
    def reset_password(user, new_password=None, request=None, reset_by=None):
        """Reset user password (admin action)."""
        if not new_password:
            new_password = secrets.token_urlsafe(12)

        user.set_password(new_password)
        user.requires_password_change = True
        user.password_changed_at = timezone.now()
        user.failed_login_attempts = 0
        user.last_failed_login = None
        user.save(
            update_fields=[
                "password",
                "requires_password_change",
                "password_changed_at",
                "failed_login_attempts",
                "last_failed_login",
            ]
        )

        # Create audit log
        client_info = get_client_info(request) if request else {}
        UserAuditLog.objects.create(
            user=user,
            action="password_change",
            description=f'Password reset by {"admin" if reset_by else "system"}',
            performed_by=reset_by,
            ip_address=client_info.get("ip_address"),
            user_agent=client_info.get("user_agent"),
            extra_data=client_info,
        )

        # Send notification email
        try:
            send_notification_email(
                user,
                "Password Reset by Administrator",
                "accounts/emails/password_reset_by_admin.html",
                {
                    "temporary_password": new_password,
                    "reset_by": (
                        reset_by.get_full_name() if reset_by else "System Administrator"
                    ),
                },
            )
        except Exception as e:
            logger.error(f"Failed to send password reset notification: {e}")

        return new_password

    @staticmethod
    def invalidate_user_tokens(user):
        """Invalidate all JWT tokens for a user."""
        try:
            from rest_framework_simplejwt.token_blacklist.models import OutstandingToken

            tokens = OutstandingToken.objects.filter(user=user)
            for token in tokens:
                try:
                    BlacklistedToken.objects.get_or_create(token=token)
                except Exception as e:
                    logger.error(f"Error blacklisting token: {e}")
        except ImportError:
            logger.warning("Token blacklist not available")

    @staticmethod
    def unlock_account(user, unlocked_by=None):
        """Unlock a locked user account."""
        user.failed_login_attempts = 0
        user.last_failed_login = None
        user.save(update_fields=["failed_login_attempts", "last_failed_login"])

        # Create audit log
        UserAuditLog.objects.create(
            user=user,
            action="account_unlock",
            description=f'Account unlocked by {"admin" if unlocked_by else "system"}',
            performed_by=unlocked_by,
        )

        # Send notification email
        try:
            send_notification_email(
                user, "Account Unlocked", "accounts/emails/account_unlocked.html"
            )
        except Exception as e:
            logger.error(f"Failed to send unlock notification: {e}")

    @staticmethod
    def get_login_statistics(user, days=30):
        """Get login statistics for a user."""
        from datetime import timedelta

        from django.db.models import Count

        start_date = timezone.now() - timedelta(days=days)

        # Get login attempts
        total_attempts = UserAuditLog.objects.filter(
            user=user, action="login", timestamp__gte=start_date
        ).count()

        successful_logins = UserAuditLog.objects.filter(
            user=user,
            action="login",
            description__contains="Successful",
            timestamp__gte=start_date,
        ).count()

        failed_attempts = total_attempts - successful_logins

        # Get unique IP addresses
        unique_ips = (
            UserAuditLog.objects.filter(
                user=user,
                action="login",
                description__contains="Successful",
                timestamp__gte=start_date,
            )
            .values_list("ip_address", flat=True)
            .distinct()
            .count()
        )

        return {
            "total_attempts": total_attempts,
            "successful_logins": successful_logins,
            "failed_attempts": failed_attempts,
            "unique_ip_addresses": unique_ips,
            "success_rate": (
                (successful_logins / total_attempts * 100) if total_attempts > 0 else 0
            ),
            "period_days": days,
        }

    @staticmethod
    def check_suspicious_activity(user, threshold_hours=24):
        """Check for suspicious login activity."""
        from datetime import timedelta

        from django.db.models import Count

        since = timezone.now() - timedelta(hours=threshold_hours)

        # Get failed attempts in the period
        failed_attempts = UserAuditLog.objects.filter(
            user=user,
            action="login",
            description__contains="Failed",
            timestamp__gte=since,
        )

        # Get unique IP addresses from failed attempts
        suspicious_ips = (
            failed_attempts.values("ip_address")
            .annotate(attempt_count=Count("id"))
            .filter(attempt_count__gte=3)
        )

        # Check for logins from new locations
        recent_successful = (
            UserAuditLog.objects.filter(
                user=user,
                action="login",
                description__contains="Successful",
                timestamp__gte=since,
            )
            .values_list("ip_address", flat=True)
            .distinct()
        )

        # Compare with historical IPs
        historical_ips = (
            UserAuditLog.objects.filter(
                user=user,
                action="login",
                description__contains="Successful",
                timestamp__lt=since,
            )
            .values_list("ip_address", flat=True)
            .distinct()
        )

        new_locations = set(recent_successful) - set(historical_ips)

        return {
            "suspicious_ip_count": len(suspicious_ips),
            "suspicious_ips": list(suspicious_ips),
            "new_location_count": len(new_locations),
            "new_locations": list(new_locations),
            "total_failed_attempts": failed_attempts.count(),
            "is_suspicious": len(suspicious_ips) > 0 or len(new_locations) > 0,
        }
