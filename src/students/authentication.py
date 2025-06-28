# src/students/authentication.py
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import BaseBackend
from django.core.exceptions import ObjectDoesNotExist
import logging

from .models import Student

logger = logging.getLogger(__name__)
User = get_user_model()


class EnhancedStudentBackend(BaseBackend):
    """
    Enhanced authentication backend for students that supports:
    - Admission number login
    - Registration number login
    - Roll number login (if unique)
    - Standard username/email login for students
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        """
        Authenticate a student using various identifier types.

        Priority order:
        1. Admission number (primary student identifier)
        2. Registration number (secondary identifier)
        3. Roll number (if configured as unique)
        4. Username (fallback)

        Args:
            request: The HTTP request object
            username: The identifier (admission/registration/roll number or username)
            password: The password

        Returns:
            User object if authentication successful, None otherwise
        """
        if username is None or password is None:
            return None

        try:
            # Clean the identifier
            identifier = username.strip()

            # Try to find student by various identifiers
            student = self._find_student_by_identifier(identifier)

            if not student:
                logger.debug(f"No student found with identifier: {identifier}")
                return None

            user = student.user

            # Validate user and student status
            if not self._validate_student_access(student, user, identifier):
                return None

            # Verify password
            if user.check_password(password):
                logger.info(
                    f"Successful student login: {identifier} -> {user.username}"
                )

                # Update last login
                user.last_login = timezone.now()
                user.save(update_fields=["last_login"])

                # Reset failed login attempts
                if hasattr(user, "reset_failed_login_attempts"):
                    user.reset_failed_login_attempts()

                return user
            else:
                logger.warning(f"Invalid password for student identifier: {identifier}")

                # Increment failed login attempts
                if hasattr(user, "increment_failed_login_attempts"):
                    user.increment_failed_login_attempts()

                return None

        except Exception as e:
            logger.error(f"Error during student authentication: {str(e)}")
            return None

    def get_user(self, user_id):
        """Get user by ID for session management."""
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None

    def user_can_authenticate(self, user):
        """Check if user can authenticate (is active)."""
        return getattr(user, "is_active", None)

    def _find_student_by_identifier(self, identifier):
        """
        Find student by various identifier types.

        Args:
            identifier: The identifier to search for

        Returns:
            Student object if found, None otherwise
        """
        # Try admission number first (most common)
        student = self._find_by_admission_number(identifier)
        if student:
            return student

        # Try registration number
        student = self._find_by_registration_number(identifier)
        if student:
            return student

        # Try roll number (if configured as searchable)
        student = self._find_by_roll_number(identifier)
        if student:
            return student

        # Try username (fallback)
        student = self._find_by_username(identifier)
        if student:
            return student

        return None

    def _find_by_admission_number(self, identifier):
        """Find student by admission number."""
        try:
            # Direct exact match (case insensitive)
            return Student.objects.select_related("user").get(
                admission_number__iexact=identifier
            )
        except Student.DoesNotExist:
            # Try with normalized format
            normalized = self._normalize_admission_number(identifier)
            if normalized != identifier:
                try:
                    return Student.objects.select_related("user").get(
                        admission_number__iexact=normalized
                    )
                except Student.DoesNotExist:
                    pass
            return None

    def _find_by_registration_number(self, identifier):
        """Find student by registration number."""
        try:
            return Student.objects.select_related("user").get(
                registration_number__iexact=identifier
            )
        except Student.DoesNotExist:
            return None

    def _find_by_roll_number(self, identifier):
        """Find student by roll number (only if unique within current academic year)."""
        try:
            # Only search roll numbers if they're configured as unique identifiers
            # This depends on your school's policy
            from django.conf import settings

            if getattr(settings, "ALLOW_ROLL_NUMBER_LOGIN", False):
                # Get current academic year
                from src.academics.models import AcademicYear

                try:
                    current_year = AcademicYear.objects.get(is_current=True)
                    students = Student.objects.select_related("user").filter(
                        roll_number__iexact=identifier,
                        current_class__academic_year=current_year,
                    )

                    # Only return if exactly one student found
                    if students.count() == 1:
                        return students.first()
                except AcademicYear.DoesNotExist:
                    pass

            return None
        except Exception:
            return None

    def _find_by_username(self, identifier):
        """Find student by username."""
        try:
            user = User.objects.get(username__iexact=identifier)
            # Only return if user is actually a student
            if hasattr(user, "student_profile"):
                return user.student_profile
            elif hasattr(user, "is_student") and user.is_student:
                try:
                    return Student.objects.select_related("user").get(user=user)
                except Student.DoesNotExist:
                    pass
            return None
        except User.DoesNotExist:
            return None

    def _normalize_admission_number(self, admission_number):
        """
        Normalize admission number format for consistent searching.

        Args:
            admission_number: Raw admission number

        Returns:
            Normalized admission number
        """
        if not admission_number:
            return admission_number

        # Remove extra spaces and convert to uppercase
        clean_number = admission_number.strip().upper()

        # Common normalization patterns
        # Add your institution's specific patterns here

        # Pattern: Convert "STU2024001" to "STU-2024-001"
        if re.match(r"^[A-Z]{2,4}\d{7,10}$", clean_number):
            prefix = re.match(r"^([A-Z]{2,4})", clean_number).group(1)
            numbers = clean_number[len(prefix) :]
            if len(numbers) >= 7:
                year = numbers[:4]
                sequence = numbers[4:]
                clean_number = f"{prefix}-{year}-{sequence}"

        # Pattern: Add leading zeros to sequence part
        # "STU-2024-1" -> "STU-2024-001"
        pattern = r"^([A-Z]{2,4})-(\d{4})-(\d+)$"
        match = re.match(pattern, clean_number)
        if match:
            prefix, year, sequence = match.groups()
            if len(sequence) < 3:
                sequence = sequence.zfill(3)
                clean_number = f"{prefix}-{year}-{sequence}"

        return clean_number

    def _validate_student_access(self, student, user, identifier):
        """
        Validate if student can access the system.

        Args:
            student: Student object
            user: User object
            identifier: Identifier used for login

        Returns:
            True if access allowed, False otherwise
        """
        # Check if user account is active
        if not user.is_active:
            logger.warning(f"Inactive user attempted login: {identifier}")
            return False

        # Check if student record is active
        if student.status not in ["Active", "active"]:
            logger.warning(
                f"Inactive student attempted login: {identifier} (status: {student.status})"
            )
            return False

        # Check if account is locked
        if hasattr(user, "is_account_locked") and user.is_account_locked():
            logger.warning(f"Locked account attempted login: {identifier}")
            return False

        # Additional validation can be added here
        # e.g., check if student is in current academic year, fees paid, etc.

        return True

    def _looks_like_admission_number(self, identifier):
        """
        Check if the identifier looks like an admission number.
        This method is kept for backward compatibility.

        Args:
            identifier: Identifier to check

        Returns:
            True if looks like admission number, False otherwise
        """
        if not identifier:
            return False

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


class StudentAdmissionNumberBackend(EnhancedStudentBackend):
    """
    Backward compatibility backend that only handles admission numbers.
    This is kept for legacy support.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        """Only authenticate if identifier looks like admission number."""
        if username is None or password is None:
            return None

        # Only handle identifiers that look like admission numbers
        if not self._looks_like_admission_number(username):
            return None

        # Use parent class authentication
        return super().authenticate(request, username, password, **kwargs)

    def _find_student_by_identifier(self, identifier):
        """Only search by admission number."""
        return self._find_by_admission_number(identifier)

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
