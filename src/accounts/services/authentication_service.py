# src/accounts/services/authentication_service.py

import hashlib
import logging
import re
from typing import Any, Dict, Optional, Tuple

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken

from ..models import UserAuditLog, UserSession
from ..utils import get_client_info

logger = logging.getLogger(__name__)
User = get_user_model()


class UnifiedAuthenticationService:
    """Enhanced service for handling unified authentication with multiple identifier types."""

    # Identifier types
    IDENTIFIER_EMAIL = "email"
    IDENTIFIER_PHONE = "phone"
    IDENTIFIER_USERNAME = "username"
    IDENTIFIER_ADMISSION = "admission_number"

    @staticmethod
    def authenticate_user(
        identifier: str, password: str, request=None
    ) -> Tuple[Optional[User], str]:
        """
        Authenticate a user with email, phone, username, or admission number.

        Args:
            identifier: User identifier (email, phone, username, or admission number)
            password: User password
            request: HTTP request object for logging

        Returns:
            Tuple of (user_object, authentication_result)

        Authentication results:
            - "success": Authentication successful
            - "user_not_found": No user found with identifier
            - "account_locked": Account is locked
            - "account_inactive": Account is not active
            - "invalid_credentials": Wrong password
            - "authentication_error": System error
        """
        client_info = get_client_info(request) if request else {}

        try:
            # Clean and validate identifier
            identifier = identifier.strip()
            if not identifier:
                return None, "user_not_found"

            # Find user by identifier
            user = UnifiedAuthenticationService._find_user_by_identifier(identifier)

            if not user:
                UnifiedAuthenticationService._log_failed_attempt(
                    None,
                    f"User not found for identifier: {identifier}",
                    client_info,
                    identifier,
                )
                return None, "user_not_found"

            # Check if account is locked
            if user.is_account_locked():
                UnifiedAuthenticationService._log_failed_attempt(
                    user, "Account locked", client_info, identifier
                )
                return None, "account_locked"

            # Check if account is active
            if not user.is_active:
                UnifiedAuthenticationService._log_failed_attempt(
                    user, "Account inactive", client_info, identifier
                )
                return None, "account_inactive"

            # For students, check if student record is active
            if user.is_student:
                try:
                    from src.students.models import Student

                    student = Student.objects.select_related("user").get(user=user)
                    if student.status != "Active":
                        UnifiedAuthenticationService._log_failed_attempt(
                            user, "Student account inactive", client_info, identifier
                        )
                        return None, "account_inactive"
                except Student.DoesNotExist:
                    UnifiedAuthenticationService._log_failed_attempt(
                        user, "Student record not found", client_info, identifier
                    )
                    return None, "account_inactive"
                except ImportError:
                    # Students module not available
                    pass

            # Verify password
            if user.check_password(password):
                # Successful authentication
                user.reset_failed_login_attempts()
                UnifiedAuthenticationService.update_last_login(user)

                # Log successful login
                identifier_type = UnifiedAuthenticationService._get_identifier_type(
                    identifier
                )
                UserAuditLog.objects.create(
                    user=user,
                    action="login",
                    description=f"Successful authentication using {identifier_type}",
                    ip_address=client_info.get("ip_address"),
                    user_agent=client_info.get("user_agent"),
                    extra_data={
                        **client_info,
                        "identifier_type": identifier_type,
                        "identifier_used": identifier,
                    },
                )

                # Create or update session record
                if request and hasattr(request, "session"):
                    UnifiedAuthenticationService._create_session_record(user, request)

                return user, "success"
            else:
                # Invalid password
                user.increment_failed_login_attempts()
                UnifiedAuthenticationService._log_failed_attempt(
                    user,
                    f"Invalid password (attempt #{user.failed_login_attempts})",
                    client_info,
                    identifier,
                )
                return None, "invalid_credentials"

        except Exception as e:
            logger.error(
                f"Authentication error for identifier '{identifier}': {str(e)}"
            )
            UnifiedAuthenticationService._log_failed_attempt(
                None, f"System authentication error: {str(e)}", client_info, identifier
            )
            return None, "authentication_error"

    @staticmethod
    def _find_user_by_identifier(identifier: str) -> Optional[User]:
        """
        Find user by email, phone number, username, or admission number.

        Priority order:
        1. Email (exact match)
        2. Phone number (normalized match)
        3. Admission number (for students)
        4. Username (exact match)
        """
        identifier = identifier.strip()

        # 1. Check if it's an email
        if UnifiedAuthenticationService._is_email(identifier):
            try:
                return User.objects.select_related().get(email__iexact=identifier)
            except User.DoesNotExist:
                pass

        # 2. Check if it's a phone number
        if UnifiedAuthenticationService._is_phone_number(identifier):
            normalized_phone = UnifiedAuthenticationService._normalize_phone_number(
                identifier
            )
            if normalized_phone:
                try:
                    # Try exact match first
                    return User.objects.select_related().get(
                        phone_number=normalized_phone
                    )
                except User.DoesNotExist:
                    # Try partial match (last 10 digits)
                    if len(normalized_phone) >= 10:
                        last_digits = normalized_phone[-10:]
                        try:
                            return User.objects.select_related().get(
                                phone_number__endswith=last_digits
                            )
                        except (User.DoesNotExist, User.MultipleObjectsReturned):
                            pass

        # 3. Check if it's an admission number (for students)
        if UnifiedAuthenticationService._is_admission_number(identifier):
            try:
                from src.students.models import Student

                student = Student.objects.select_related("user").get(
                    admission_number__iexact=identifier
                )
                return student.user
            except Student.DoesNotExist:
                pass
            except ImportError:
                logger.warning(
                    "Students module not available for admission number lookup"
                )

        # 4. Check if it's a username
        try:
            return User.objects.select_related().get(username__iexact=identifier)
        except User.DoesNotExist:
            pass

        return None

    @staticmethod
    def _is_email(identifier: str) -> bool:
        """Check if identifier is a valid email format."""
        try:
            validate_email(identifier)
            return True
        except ValidationError:
            return False

    @staticmethod
    def _is_phone_number(identifier: str) -> bool:
        """Check if identifier looks like a phone number."""
        # Remove common phone number characters
        clean_identifier = re.sub(r"[\s\-\(\)\+]", "", identifier)

        # Check if it's mostly digits and reasonable length
        if clean_identifier.isdigit() and 10 <= len(clean_identifier) <= 15:
            return True

        # Check for international format with +
        phone_pattern = r"^\+?[\d\s\-\(\)]{10,15}$"
        return bool(re.match(phone_pattern, identifier))

    @staticmethod
    def _normalize_phone_number(phone: str) -> Optional[str]:
        """Normalize phone number for database lookup."""
        if not phone:
            return None

        # Remove all non-digit characters except +
        clean_phone = re.sub(r"[^\d\+]", "", phone)

        # Handle different formats
        if clean_phone.startswith("+"):
            return clean_phone
        elif clean_phone.startswith("0") and len(clean_phone) == 11:
            # Convert local format to international (adjust for your country)
            return f"+1{clean_phone[1:]}"  # Adjust country code as needed
        elif len(clean_phone) == 10:
            # Add country code for 10-digit numbers
            return f"+1{clean_phone}"  # Adjust country code as needed

        return clean_phone

    @staticmethod
    def _is_admission_number(identifier: str) -> bool:
        """Check if identifier looks like an admission number."""
        if not identifier:
            return False

        # Clean identifier
        clean_identifier = identifier.strip().upper()

        # Common admission number patterns
        patterns = [
            r"^[A-Z]{2,4}-\d{4}-[A-Z0-9]{3,8}$",  # STU-2024-ABC123
            r"^\d{4}[A-Z0-9]{3,8}$",  # 2024ABC123
            r"^[A-Z]{2,4}\d{4}[A-Z0-9]{3,8}$",  # STU2024ABC123
            r"^\d{7,12}$",  # 202400001
            r"^[A-Z]{2,4}/\d{4}/\d{3,6}$",  # STU/2024/001
        ]

        for pattern in patterns:
            if re.match(pattern, clean_identifier):
                return True

        return False

    @staticmethod
    def _get_identifier_type(identifier: str) -> str:
        """Determine the type of identifier used."""
        if UnifiedAuthenticationService._is_email(identifier):
            return UnifiedAuthenticationService.IDENTIFIER_EMAIL
        elif UnifiedAuthenticationService._is_phone_number(identifier):
            return UnifiedAuthenticationService.IDENTIFIER_PHONE
        elif UnifiedAuthenticationService._is_admission_number(identifier):
            return UnifiedAuthenticationService.IDENTIFIER_ADMISSION
        else:
            return UnifiedAuthenticationService.IDENTIFIER_USERNAME

    @staticmethod
    def generate_tokens_for_user(user: User) -> Dict[str, Any]:
        """Generate JWT tokens for a user."""
        refresh = RefreshToken.for_user(user)
        return {
            "refresh": str(refresh),
            "access": str(refresh.access_token),
            "expires_in": settings.SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"].total_seconds(),
            "token_type": "Bearer",
        }

    @staticmethod
    def update_last_login(user: User) -> None:
        """Update the last login timestamp for a user."""
        user.last_login = timezone.now()
        user.save(update_fields=["last_login"])

    @staticmethod
    def _log_failed_attempt(
        user: Optional[User], reason: str, client_info: Dict, identifier: str = ""
    ) -> None:
        """Log failed authentication attempt."""
        identifier_type = (
            UnifiedAuthenticationService._get_identifier_type(identifier)
            if identifier
            else "unknown"
        )

        UserAuditLog.objects.create(
            user=user,
            action="login",
            description=f"Failed authentication: {reason}",
            ip_address=client_info.get("ip_address"),
            user_agent=client_info.get("user_agent"),
            extra_data={
                **client_info,
                "identifier_type": identifier_type,
                "identifier_used": identifier,
                "failure_reason": reason,
            },
            severity="medium" if user else "low",
        )

    @staticmethod
    def _create_session_record(user: User, request) -> None:
        """Create or update session record."""
        try:
            client_info = get_client_info(request)
            session_key = request.session.session_key

            if not session_key:
                request.session.create()
                session_key = request.session.session_key

            # Update or create session record
            UserSession.objects.update_or_create(
                user=user,
                session_key=session_key,
                defaults={
                    "ip_address": client_info.get("ip_address"),
                    "user_agent": client_info.get("user_agent"),
                    "last_activity": timezone.now(),
                    "is_active": True,
                    "extra_data": client_info,
                },
            )
        except Exception as e:
            logger.error(f"Failed to create session record: {str(e)}")

    @staticmethod
    def logout_user(user: User, request=None) -> None:
        """Handle user logout."""
        try:
            client_info = get_client_info(request) if request else {}

            # Log logout
            UserAuditLog.objects.create(
                user=user,
                action="logout",
                description="User logged out",
                ip_address=client_info.get("ip_address"),
                user_agent=client_info.get("user_agent"),
                extra_data=client_info,
            )

            # Mark session as inactive
            if request and hasattr(request, "session"):
                session_key = request.session.session_key
                if session_key:
                    UserSession.objects.filter(
                        user=user, session_key=session_key
                    ).update(is_active=False)

        except Exception as e:
            logger.error(f"Error during logout for user {user.id}: {str(e)}")

    @staticmethod
    def get_login_statistics(user: User, days: int = 30) -> Dict[str, Any]:
        """Get login statistics for a user."""
        from datetime import timedelta

        start_date = timezone.now() - timedelta(days=days)

        # Get recent login attempts
        recent_attempts = UserAuditLog.objects.filter(
            user=user, action="login", timestamp__gte=start_date
        )

        successful_logins = recent_attempts.filter(description__icontains="Successful")

        failed_logins = recent_attempts.filter(description__icontains="Failed")

        return {
            "total_attempts": recent_attempts.count(),
            "successful_logins": successful_logins.count(),
            "failed_logins": failed_logins.count(),
            "success_rate": (
                successful_logins.count() / max(recent_attempts.count(), 1)
            )
            * 100,
            "last_login": user.last_login,
            "current_failed_attempts": user.failed_login_attempts,
        }

    @staticmethod
    def reset_password(
        user: User,
        new_password: Optional[str] = None,
        request=None,
        reset_by: Optional[User] = None,
    ) -> str:
        """
        Reset user password (admin action).

        Args:
            user: User whose password to reset
            new_password: New password (auto-generated if not provided)
            request: HTTP request object
            reset_by: User performing the reset (for audit)

        Returns:
            The new password (temporary if auto-generated)
        """
        import secrets
        import string

        # Generate password if not provided
        if not new_password:
            # Generate temporary password
            chars = string.ascii_letters + string.digits + "!@#$%^&*"
            new_password = "".join(secrets.choice(chars) for _ in range(12))

        # Set new password
        user.set_password(new_password)
        user.requires_password_change = True
        user.password_changed_at = timezone.now()
        user.failed_login_attempts = 0  # Reset failed attempts
        user.save(
            update_fields=[
                "password",
                "requires_password_change",
                "password_changed_at",
                "failed_login_attempts",
            ]
        )

        # Log password reset
        client_info = get_client_info(request) if request else {}
        reset_description = (
            f"Password reset by {reset_by.username if reset_by else 'system'}"
        )

        UserAuditLog.objects.create(
            user=user,
            action="password_reset",
            description=reset_description,
            performed_by=reset_by,
            ip_address=client_info.get("ip_address"),
            user_agent=client_info.get("user_agent"),
            extra_data={
                **client_info,
                "reset_by_id": reset_by.id if reset_by else None,
                "password_auto_generated": new_password != new_password,
            },
            severity="medium",
        )

        # Send notification email
        try:
            from .utils import send_notification_email

            send_notification_email(
                user,
                "Password Reset - Action Required",
                "accounts/emails/password_reset_notification.html",
                {
                    "reset_by": reset_by,
                    "temporary_password": new_password,
                    "client_info": client_info,
                },
            )
        except Exception as e:
            logger.error(f"Failed to send password reset notification: {e}")

        logger.info(
            f"Password reset for user {user.username} by {reset_by.username if reset_by else 'system'}"
        )

        return new_password

    @staticmethod
    def change_password(
        user: User, old_password: str, new_password: str, request=None
    ) -> Tuple[bool, str]:
        """
        Change user password with validation and logging.

        Args:
            user: User changing password
            old_password: Current password
            new_password: New password
            request: HTTP request object

        Returns:
            Tuple of (success, message)
        """
        # Verify old password
        if not user.check_password(old_password):
            # Log failed password change attempt
            client_info = get_client_info(request) if request else {}
            UserAuditLog.objects.create(
                user=user,
                action="password_change_failed",
                description="Failed password change: incorrect current password",
                ip_address=client_info.get("ip_address"),
                user_agent=client_info.get("user_agent"),
                extra_data=client_info,
                severity="medium",
            )
            return False, "Current password is incorrect"

        # Validate new password (basic validation)
        if len(new_password) < 8:
            return False, "New password must be at least 8 characters long"

        if new_password == old_password:
            return False, "New password must be different from current password"

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

        # Log successful password change
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
            from .utils import send_notification_email

            send_notification_email(
                user,
                "Password Changed Successfully",
                "accounts/emails/password_changed.html",
                {"client_info": client_info},
            )
        except Exception as e:
            logger.error(f"Failed to send password change notification: {e}")

        logger.info(f"Password changed successfully for user {user.username}")

        return True, "Password changed successfully"

    @staticmethod
    def generate_temporary_password(length: int = 12) -> str:
        """Generate a secure temporary password."""
        import secrets
        import string

        # Include uppercase, lowercase, digits, and some special characters
        chars = string.ascii_letters + string.digits + "!@#$%^&*"
        return "".join(secrets.choice(chars) for _ in range(length))

    @staticmethod
    def unlock_account(
        user: User, unlocked_by: Optional[User] = None, request=None
    ) -> bool:
        """
        Unlock a locked user account.

        Args:
            user: User to unlock
            unlocked_by: User performing the unlock
            request: HTTP request object

        Returns:
            True if account was unlocked, False if already unlocked
        """
        if (
            not hasattr(user, "failed_login_attempts")
            or user.failed_login_attempts == 0
        ):
            return False  # Account not locked

        # Reset failed login attempts
        user.failed_login_attempts = 0
        if hasattr(user, "last_failed_login"):
            user.last_failed_login = None
        user.save(update_fields=["failed_login_attempts", "last_failed_login"])

        # Log account unlock
        client_info = get_client_info(request) if request else {}
        unlock_description = (
            f"Account unlocked by {unlocked_by.username if unlocked_by else 'system'}"
        )

        UserAuditLog.objects.create(
            user=user,
            action="account_unlock",
            description=unlock_description,
            performed_by=unlocked_by,
            ip_address=client_info.get("ip_address"),
            user_agent=client_info.get("user_agent"),
            extra_data={
                **client_info,
                "unlocked_by_id": unlocked_by.id if unlocked_by else None,
            },
        )

        logger.info(
            f"Account unlocked for user {user.username} by {unlocked_by.username if unlocked_by else 'system'}"
        )

        return True

    @staticmethod
    def get_user_sessions(user: User, active_only: bool = True) -> list:
        """
        Get user's active sessions.

        Args:
            user: User to get sessions for
            active_only: Whether to return only active sessions

        Returns:
            List of user sessions
        """
        try:
            sessions = UserSession.objects.filter(user=user)
            if active_only:
                sessions = sessions.filter(is_active=True)
            return list(sessions.order_by("-last_activity"))
        except Exception as e:
            logger.error(f"Error getting user sessions: {e}")
            return []

    @staticmethod
    def terminate_session(
        user: User, session_key: str, terminated_by: Optional[User] = None
    ) -> bool:
        """
        Terminate a specific user session.

        Args:
            user: User whose session to terminate
            session_key: Session key to terminate
            terminated_by: User performing the termination

        Returns:
            True if session was terminated, False if not found
        """
        try:
            session = UserSession.objects.get(
                user=user, session_key=session_key, is_active=True
            )
            session.is_active = False
            session.terminated_at = timezone.now()
            session.save()

            # Log session termination
            UserAuditLog.objects.create(
                user=user,
                action="session_terminate",
                description=f"Session terminated by {terminated_by.username if terminated_by else 'user'}",
                performed_by=terminated_by,
                extra_data={
                    "session_key": session_key,
                    "terminated_by_id": terminated_by.id if terminated_by else None,
                },
            )

            return True
        except UserSession.DoesNotExist:
            return False


# Backward compatibility alias
AuthenticationService = UnifiedAuthenticationService
