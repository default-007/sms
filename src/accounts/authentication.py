# src/accounts/authentication.py

import logging
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import BaseBackend
from django.core.exceptions import ObjectDoesNotExist

from .services.authentication_service import UnifiedAuthenticationService

logger = logging.getLogger(__name__)
User = get_user_model()


class UnifiedAuthenticationBackend(BaseBackend):
    """
    Unified authentication backend that supports login with:
    - Email address
    - Phone number
    - Username
    - Admission number (for students)
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        """
        Authenticate user with any supported identifier type.

        Args:
            request: The HTTP request object
            username: The identifier (email, phone, username, or admission number)
            password: The password
            **kwargs: Additional arguments

        Returns:
            User object if authentication successful, None otherwise
        """
        if username is None or password is None:
            return None

        try:
            # Use the unified authentication service
            user, result = UnifiedAuthenticationService.authenticate_user(
                identifier=username, password=password, request=request
            )

            if result == "success" and user:
                # Additional checks can be added here if needed
                if self.user_can_authenticate(user):
                    return user
                else:
                    logger.warning(
                        f"User {user.id} cannot authenticate (inactive or other restrictions)"
                    )
                    return None
            else:
                # Log the authentication failure reason
                logger.debug(f"Authentication failed for '{username}': {result}")
                return None

        except Exception as e:
            logger.error(f"Error in unified authentication backend: {str(e)}")
            return None

    def get_user(self, user_id):
        """
        Get user by ID for session management.
        """
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None

    def user_can_authenticate(self, user):
        """
        Reject users with is_active=False. Custom backends can override this.
        """
        return getattr(user, "is_active", None)


class StudentAdmissionBackend(BaseBackend):
    """
    Specialized backend for student admission number authentication.
    This is kept for backward compatibility and specific student-only authentication needs.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        """
        Authenticate a student using admission number and password.
        """
        if username is None or password is None:
            return None

        # Only handle admission number patterns
        if not self._looks_like_admission_number(username):
            return None

        try:
            from src.students.models import Student

            # Find student by admission number
            student = Student.objects.select_related("user").get(
                admission_number__iexact=username.strip()
            )
            user = student.user

            # Check if user is active
            if not user.is_active:
                logger.warning(
                    f"Inactive user attempted login with admission number: {username}"
                )
                return None

            # Check if student is active
            if student.status != "Active":
                logger.warning(f"Inactive student attempted login: {username}")
                return None

            # Verify password
            if user.check_password(password):
                logger.info(
                    f"Successful student login with admission number: {username}"
                )
                return user
            else:
                logger.warning(f"Invalid password for admission number: {username}")
                return None

        except Student.DoesNotExist:
            logger.debug(f"No student found with admission number: {username}")
            return None
        except ImportError:
            logger.error(
                "Students module not available for admission number authentication"
            )
            return None
        except Exception as e:
            logger.error(f"Error during student admission authentication: {str(e)}")
            return None

    def get_user(self, user_id):
        """Get user by ID for session management."""
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None

    def _looks_like_admission_number(self, identifier):
        """Check if the identifier looks like an admission number."""
        return UnifiedAuthenticationService._is_admission_number(identifier)

    def user_can_authenticate(self, user):
        """Reject users with is_active=False."""
        return getattr(user, "is_active", None)


class EmailAuthenticationBackend(BaseBackend):
    """
    Email-only authentication backend for cases where you want to restrict to email only.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        """Authenticate using email address only."""
        if username is None or password is None:
            return None

        # Only handle email addresses
        if not UnifiedAuthenticationService._is_email(username):
            return None

        try:
            user = User.objects.get(email__iexact=username.strip())

            if user.check_password(password) and self.user_can_authenticate(user):
                logger.info(f"Successful email authentication for: {username}")
                return user
            else:
                logger.warning(f"Failed email authentication for: {username}")
                return None

        except User.DoesNotExist:
            logger.debug(f"No user found with email: {username}")
            return None
        except Exception as e:
            logger.error(f"Error during email authentication: {str(e)}")
            return None

    def get_user(self, user_id):
        """Get user by ID for session management."""
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None

    def user_can_authenticate(self, user):
        """Reject users with is_active=False."""
        return getattr(user, "is_active", None)


class PhoneAuthenticationBackend(BaseBackend):
    """
    Phone number authentication backend for mobile apps or SMS-based login.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        """Authenticate using phone number only."""
        if username is None or password is None:
            return None

        # Only handle phone numbers
        if not UnifiedAuthenticationService._is_phone_number(username):
            return None

        try:
            # Normalize phone number
            normalized_phone = UnifiedAuthenticationService._normalize_phone_number(
                username
            )
            if not normalized_phone:
                return None

            # Try exact match first
            try:
                user = User.objects.get(phone_number=normalized_phone)
            except User.DoesNotExist:
                # Try partial match for last 10 digits
                if len(normalized_phone) >= 10:
                    last_digits = normalized_phone[-10:]
                    user = User.objects.get(phone_number__endswith=last_digits)
                else:
                    return None

            if user.check_password(password) and self.user_can_authenticate(user):
                logger.info(f"Successful phone authentication for: {username}")
                return user
            else:
                logger.warning(f"Failed phone authentication for: {username}")
                return None

        except User.DoesNotExist:
            logger.debug(f"No user found with phone: {username}")
            return None
        except User.MultipleObjectsReturned:
            logger.warning(f"Multiple users found with phone pattern: {username}")
            return None
        except Exception as e:
            logger.error(f"Error during phone authentication: {str(e)}")
            return None

    def get_user(self, user_id):
        """Get user by ID for session management."""
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None

    def user_can_authenticate(self, user):
        """Reject users with is_active=False."""
        return getattr(user, "is_active", None)


# Legacy alias for backward compatibility
StudentAdmissionNumberBackend = StudentAdmissionBackend
EnhancedStudentBackend = UnifiedAuthenticationBackend
