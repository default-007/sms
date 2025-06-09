# src/students/authentication.py
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import BaseBackend
from django.core.exceptions import ObjectDoesNotExist
import logging

from .models import Student

logger = logging.getLogger(__name__)
User = get_user_model()


class StudentAdmissionNumberBackend(BaseBackend):
    """
    Custom authentication backend that allows students to login using their admission number.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        """
        Authenticate a student using admission number and password.

        Args:
            request: The HTTP request object
            username: The admission number (or other identifier)
            password: The password

        Returns:
            User object if authentication successful, None otherwise
        """
        if username is None or password is None:
            return None

        try:
            # First, check if it's an admission number
            if self._looks_like_admission_number(username):
                student = Student.objects.select_related("user").get(
                    admission_number=username
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
                    logger.info(f"Successful login with admission number: {username}")
                    return user
                else:
                    logger.warning(f"Invalid password for admission number: {username}")
                    return None

            # If not an admission number, let other backends handle it
            return None

        except Student.DoesNotExist:
            # Not a valid admission number, let other backends handle it
            logger.debug(f"No student found with admission number: {username}")
            return None
        except Exception as e:
            logger.error(f"Error during admission number authentication: {str(e)}")
            return None

    def get_user(self, user_id):
        """
        Get user by ID for session management.
        """
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None

    def _looks_like_admission_number(self, identifier):
        """
        Check if the identifier looks like an admission number.
        Customize this based on your admission number format.
        """
        if not identifier:
            return False

        # Remove spaces and convert to uppercase for comparison
        clean_identifier = identifier.strip().upper()

        # Basic checks for admission number format
        # Adjust these patterns based on your actual admission number format
        patterns = [
            # Pattern: STU-2024-001, ADM-2024-123, etc.
            r"^[A-Z]{2,4}-\d{4}-\d{3,6}$",
            # Pattern: 2024001, 2024123, etc. (year + sequential)
            r"^\d{7,10}$",
            # Pattern: STU2024001
            r"^[A-Z]{2,4}\d{7,10}$",
        ]

        import re

        for pattern in patterns:
            if re.match(pattern, clean_identifier):
                return True

        return False

    def user_can_authenticate(self, user):
        """
        Reject users with is_active=False.
        """
        return getattr(user, "is_active", None)


class EnhancedStudentBackend(StudentAdmissionNumberBackend):
    """
    Enhanced authentication backend that supports multiple student identifiers.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        """
        Authenticate using admission number, registration number, or roll number.
        """
        if username is None or password is None:
            return None

        user = None
        clean_username = username.strip()

        try:
            # Try admission number first
            if self._looks_like_admission_number(clean_username):
                try:
                    student = Student.objects.select_related("user").get(
                        admission_number=clean_username
                    )
                    user = student.user
                except Student.DoesNotExist:
                    pass

            # Try registration number if admission number failed
            if not user and clean_username:
                try:
                    student = Student.objects.select_related("user").get(
                        registration_number=clean_username
                    )
                    user = student.user
                except Student.DoesNotExist:
                    pass

            # Try roll number if others failed (but only if it's numeric)
            if not user and clean_username.isdigit():
                try:
                    student = Student.objects.select_related("user").get(
                        roll_number=clean_username
                    )
                    user = student.user
                except Student.DoesNotExist:
                    pass

            if user:
                # Verify the user and student are active
                if not user.is_active:
                    logger.warning(f"Inactive user attempted login: {clean_username}")
                    return None

                # Get the student to check status
                try:
                    student = user.student_profile
                    if student.status != "Active":
                        logger.warning(
                            f"Inactive student attempted login: {clean_username}"
                        )
                        return None
                except AttributeError:
                    logger.error(
                        f"User {user.username} does not have a student profile"
                    )
                    return None

                # Verify password
                if user.check_password(password):
                    logger.info(f"Successful student login: {clean_username}")
                    return user
                else:
                    logger.warning(f"Invalid password for student: {clean_username}")
                    return None

            return None

        except Exception as e:
            logger.error(f"Error during enhanced student authentication: {str(e)}")
            return None
