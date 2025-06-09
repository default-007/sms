# src/accounts/validators.py

import re
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .constants import PERMISSION_SCOPES

User = get_user_model()


def validate_username(username: str, exclude_user: Optional[User] = None) -> None:
    """
    Validate username format, length, and uniqueness.

    Args:
        username: Username to validate
        exclude_user: User to exclude from uniqueness check (for updates)

    Raises:
        ValidationError: If username is invalid
    """
    if not username:
        raise ValidationError(_("Username is required."))

    # Check format - only letters, numbers, and underscores
    if not re.match(r"^[a-zA-Z0-9_]+$", username):
        raise ValidationError(
            _("Username must contain only letters, numbers, and underscores.")
        )

    # Check length
    if len(username) < 3:
        raise ValidationError(_("Username must be at least 3 characters long."))

    if len(username) > 150:
        raise ValidationError(_("Username cannot be longer than 150 characters."))

    # Check for reserved usernames
    reserved_usernames = [
        "admin",
        "administrator",
        "root",
        "system",
        "api",
        "www",
        "mail",
        "email",
        "support",
        "help",
        "info",
        "contact",
        "security",
        "privacy",
        "legal",
        "terms",
        "about",
        "null",
        "undefined",
        "anonymous",
        "guest",
        "test",
        "demo",
        "service",
    ]

    if username.lower() in reserved_usernames:
        raise ValidationError(_("This username is reserved and cannot be used."))

    # Check uniqueness
    queryset = User.objects.filter(username__iexact=username)
    if exclude_user:
        queryset = queryset.exclude(pk=exclude_user.pk)

    if queryset.exists():
        raise ValidationError(_("This username is already taken."))


def validate_email_address(email: str, exclude_user: Optional[User] = None) -> None:
    """
    Validate email format, domain, and uniqueness.

    Args:
        email: Email to validate
        exclude_user: User to exclude from uniqueness check

    Raises:
        ValidationError: If email is invalid
    """
    if not email:
        raise ValidationError(_("Email address is required."))

    # Basic format validation
    try:
        validate_email(email)
    except ValidationError:
        raise ValidationError(_("Please enter a valid email address."))

    # Normalize email
    email = email.lower().strip()

    # Domain validation
    domain = email.split("@")[1] if "@" in email else ""

    # Check against blocked domains
    blocked_domains = [
        "tempmail.com",
        "10minutemail.com",
        "guerrillamail.com",
        "mailinator.com",
        "throwaway.email",
        "temp-mail.org",
    ]

    if domain in blocked_domains:
        raise ValidationError(_("Email addresses from this domain are not allowed."))

    # Check for obviously fake patterns
    suspicious_patterns = [
        r"test.*@test\.com",
        r"fake.*@.*\.com",
        r"dummy.*@.*\.com",
        r"temp.*@.*\.com",
    ]

    for pattern in suspicious_patterns:
        if re.match(pattern, email, re.IGNORECASE):
            raise ValidationError(_("This email address appears to be invalid."))

    # Check uniqueness
    queryset = User.objects.filter(email__iexact=email)
    if exclude_user:
        queryset = queryset.exclude(pk=exclude_user.pk)

    if queryset.exists():
        raise ValidationError(_("A user with this email address already exists."))


def validate_admission_number_identifier(identifier: str) -> bool:
    """
    Validate if identifier could be an admission number.

    Args:
        identifier: String to validate

    Returns:
        True if could be valid admission number
    """
    # Basic admission number pattern - adjust based on your format
    admission_pattern = re.compile(r"^[A-Z0-9]{6,20}$", re.IGNORECASE)
    return bool(admission_pattern.match(identifier))


def find_user_by_admission_number(admission_number: str) -> Optional[User]:
    """
    Find user by admission number.

    Args:
        admission_number: Admission number to search for

    Returns:
        User object if found, None otherwise
    """
    try:
        from src.students.models import Student

        student = (
            Student.objects.select_related("user")
            .filter(admission_number=admission_number.upper())
            .first()
        )
        return student.user if student else None
    except ImportError:
        logger.warning("Students module not available")
        return None


def validate_phone_number(
    phone_number: str, exclude_user: Optional[User] = None
) -> str:
    """
    Validate and normalize phone number.

    Args:
        phone_number: Phone number to validate
        exclude_user: User to exclude from uniqueness check

    Returns:
        Normalized phone number

    Raises:
        ValidationError: If phone number is invalid
    """
    if not phone_number:
        return phone_number  # Allow empty phone numbers

    # Remove all non-digit characters except +
    clean_phone = re.sub(r"[^\d+]", "", phone_number.strip())

    # Ensure it starts with +
    if not clean_phone.startswith("+"):
        clean_phone = "+" + clean_phone

    # Validate format
    if not re.match(r"^\+\d{10,15}$", clean_phone):
        raise ValidationError(
            _("Phone number must be 10-15 digits and may include country code.")
        )

    # Check for obviously invalid patterns
    invalid_patterns = [
        r"^\+0+$",  # All zeros
        r"^\+1{10,}$",  # All ones
        r"^\+123456789",  # Sequential numbers
    ]

    for pattern in invalid_patterns:
        if re.match(pattern, clean_phone):
            raise ValidationError(_("This phone number appears to be invalid."))

    # Check uniqueness
    queryset = User.objects.filter(phone_number=clean_phone)
    if exclude_user:
        queryset = queryset.exclude(pk=exclude_user.pk)

    if queryset.exists():
        raise ValidationError(_("A user with this phone number already exists."))

    return clean_phone


def validate_password_strength(
    password: str, user: Optional[User] = None
) -> Dict[str, Any]:
    """
    Comprehensive password strength validation.

    Args:
        password: Password to validate
        user: User context for personalized validation

    Returns:
        Dictionary with validation results
    """
    result = {"is_valid": True, "score": 0, "feedback": [], "strength_level": "weak"}

    if not password:
        result["is_valid"] = False
        result["feedback"].append(_("Password is required."))
        return result

    # Minimum length check
    min_length = 8
    if len(password) < min_length:
        result["is_valid"] = False
        result["feedback"].append(
            _("Password must be at least {} characters long.").format(min_length)
        )
    else:
        result["score"] += 20

    # Character variety checks
    has_lower = any(c.islower() for c in password)
    has_upper = any(c.isupper() for c in password)
    has_digit = any(c.isdigit() for c in password)
    has_special = any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password)

    if has_lower:
        result["score"] += 15
    else:
        result["feedback"].append(_("Password should contain lowercase letters."))

    if has_upper:
        result["score"] += 15
    else:
        result["feedback"].append(_("Password should contain uppercase letters."))

    if has_digit:
        result["score"] += 15
    else:
        result["feedback"].append(_("Password should contain numbers."))

    if has_special:
        result["score"] += 15
    else:
        result["feedback"].append(_("Password should contain special characters."))

    # Length bonus
    if len(password) >= 12:
        result["score"] += 10
    if len(password) >= 16:
        result["score"] += 10

    # Common password check
    common_passwords = [
        "password",
        "123456",
        "123456789",
        "qwerty",
        "abc123",
        "password123",
        "admin",
        "letmein",
        "welcome",
        "monkey",
        "1234567890",
        "password1",
        "welcome123",
        "admin123",
    ]

    if password.lower() in common_passwords:
        result["is_valid"] = False
        result["score"] = 0
        result["feedback"] = [_("This password is too common.")]
        return result

    # Sequential pattern check
    sequential_patterns = ["123456", "abcdef", "qwerty", "asdfgh"]
    for pattern in sequential_patterns:
        if pattern in password.lower():
            result["score"] -= 10
            result["feedback"].append(_("Avoid sequential patterns in passwords."))
            break

    # User-specific checks
    if user:
        user_related_terms = [
            user.username.lower() if user.username else "",
            user.first_name.lower() if user.first_name else "",
            user.last_name.lower() if user.last_name else "",
            user.email.split("@")[0].lower() if user.email else "",
        ]

        for term in user_related_terms:
            if term and len(term) > 2 and term in password.lower():
                result["score"] -= 15
                result["feedback"].append(
                    _("Password should not contain personal information.")
                )
                break

    # Determine strength level
    if result["score"] >= 85:
        result["strength_level"] = "very_strong"
    elif result["score"] >= 70:
        result["strength_level"] = "strong"
    elif result["score"] >= 50:
        result["strength_level"] = "medium"
    elif result["score"] >= 30:
        result["strength_level"] = "weak"
    else:
        result["strength_level"] = "very_weak"

    # Final validity check
    if result["score"] < 50:
        result["is_valid"] = False

    return result


def validate_date_of_birth(
    birth_date: date, min_age: int = 13, max_age: int = 120
) -> None:
    """
    Validate date of birth for reasonable age ranges.

    Args:
        birth_date: Date of birth to validate
        min_age: Minimum allowed age
        max_age: Maximum allowed age

    Raises:
        ValidationError: If date is invalid
    """
    if not birth_date:
        return  # Allow empty birth dates

    today = date.today()

    # Check if date is in the future
    if birth_date > today:
        raise ValidationError(_("Date of birth cannot be in the future."))

    # Calculate age
    age = (
        today.year
        - birth_date.year
        - ((today.month, today.day) < (birth_date.month, birth_date.day))
    )

    # Check minimum age
    if age < min_age:
        raise ValidationError(_("User must be at least {} years old.").format(min_age))

    # Check maximum age (sanity check)
    if age > max_age:
        raise ValidationError(_("Please enter a valid birth date."))


def validate_role_permissions(permissions: Dict[str, Any]) -> None:
    """
    Validate role permissions structure against available scopes.

    Args:
        permissions: Permissions dictionary to validate

    Raises:
        ValidationError: If permissions structure is invalid
    """
    if not isinstance(permissions, dict):
        raise ValidationError(_("Permissions must be a dictionary."))

    for resource, actions in permissions.items():
        # Check if resource exists
        if resource not in PERMISSION_SCOPES:
            raise ValidationError(_("Invalid resource: {}").format(resource))

        # Check if actions is a list
        if not isinstance(actions, list):
            raise ValidationError(
                _('Actions for resource "{}" must be a list.').format(resource)
            )

        # Check each action
        available_actions = list(PERMISSION_SCOPES[resource].keys())
        for action in actions:
            if action not in available_actions:
                raise ValidationError(
                    _('Invalid action "{}" for resource "{}".').format(action, resource)
                )


def validate_profile_picture(file) -> None:
    """
    Validate uploaded profile picture.

    Args:
        file: Uploaded file object

    Raises:
        ValidationError: If file is invalid
    """
    if not file:
        return  # Allow empty files

    # Check file size (2MB max)
    max_size = 2 * 1024 * 1024  # 2MB
    if file.size > max_size:
        raise ValidationError(_("Profile picture must be less than 2MB."))

    # Check file type
    allowed_types = ["image/jpeg", "image/png", "image/jpg", "image/gif"]
    if hasattr(file, "content_type") and file.content_type not in allowed_types:
        raise ValidationError(_("Only JPEG, PNG, and GIF images are allowed."))

    # Check file extension
    if hasattr(file, "name") and file.name:
        ext = file.name.split(".")[-1].lower() if "." in file.name else ""
        allowed_extensions = ["jpg", "jpeg", "png", "gif"]
        if ext not in allowed_extensions:
            raise ValidationError(
                _("File must have a valid image extension (.jpg, .png, .gif).")
            )


def validate_csv_file(file) -> None:
    """
    Validate CSV file for bulk import.

    Args:
        file: Uploaded CSV file

    Raises:
        ValidationError: If file is invalid
    """
    if not file:
        raise ValidationError(_("CSV file is required."))

    # Check file size (5MB max for CSV)
    max_size = 5 * 1024 * 1024  # 5MB
    if file.size > max_size:
        raise ValidationError(_("CSV file must be less than 5MB."))

    # Check file extension
    if not file.name.lower().endswith(".csv"):
        raise ValidationError(_("File must be a CSV file with .csv extension."))

    # Check content type
    if hasattr(file, "content_type"):
        allowed_types = ["text/csv", "application/csv", "text/plain"]
        if file.content_type not in allowed_types:
            raise ValidationError(
                _("Invalid file type. Please upload a valid CSV file.")
            )


def validate_role_assignment_dates(assigned_date, expires_at) -> None:
    """
    Validate role assignment dates.

    Args:
        assigned_date: Date when role was assigned
        expires_at: Optional expiry date

    Raises:
        ValidationError: If dates are invalid
    """
    if assigned_date and expires_at:
        if expires_at <= assigned_date:
            raise ValidationError(_("Expiry date must be after assignment date."))

    if expires_at:
        if expires_at <= timezone.now():
            raise ValidationError(_("Expiry date must be in the future."))


def validate_json_structure(
    value: Any, required_keys: Optional[List[str]] = None
) -> None:
    """
    Validate JSON field structure.

    Args:
        value: JSON value to validate
        required_keys: List of required keys

    Raises:
        ValidationError: If JSON structure is invalid
    """
    if not isinstance(value, dict):
        raise ValidationError(_("Value must be a valid JSON object."))

    if required_keys:
        missing_keys = set(required_keys) - set(value.keys())
        if missing_keys:
            raise ValidationError(
                _("Missing required keys: {}").format(", ".join(missing_keys))
            )


def validate_timezone(timezone_str: str) -> None:
    """
    Validate timezone string.

    Args:
        timezone_str: Timezone string to validate

    Raises:
        ValidationError: If timezone is invalid
    """
    if not timezone_str:
        return  # Allow empty timezone

    try:
        import pytz

        pytz.timezone(timezone_str)
    except:
        raise ValidationError(_("Invalid timezone."))


def validate_language_code(language_code: str) -> None:
    """
    Validate language code.

    Args:
        language_code: Language code to validate

    Raises:
        ValidationError: If language code is invalid
    """
    if not language_code:
        return  # Allow empty language code

    # List of supported language codes (ISO 639-1)
    supported_languages = [
        "en",
        "es",
        "fr",
        "de",
        "it",
        "pt",
        "ru",
        "zh",
        "ja",
        "ko",
        "ar",
        "hi",
        "th",
        "vi",
        "tr",
        "pl",
        "nl",
        "sv",
        "da",
        "no",
    ]

    if language_code not in supported_languages:
        raise ValidationError(_("Unsupported language code."))


def validate_otp_code(otp: str, expected_length: int = 6) -> None:
    """
    Validate OTP code format.

    Args:
        otp: OTP code to validate
        expected_length: Expected length of OTP

    Raises:
        ValidationError: If OTP format is invalid
    """
    if not otp:
        raise ValidationError(_("Verification code is required."))

    # Remove any spaces or dashes
    clean_otp = otp.replace(" ", "").replace("-", "")

    if not clean_otp.isdigit():
        raise ValidationError(_("Verification code must contain only digits."))

    if len(clean_otp) != expected_length:
        raise ValidationError(
            _("Verification code must be {} digits long.").format(expected_length)
        )


def validate_backup_code(code: str) -> str:
    """
    Validate and normalize backup code format.

    Args:
        code: Backup code to validate

    Returns:
        Normalized backup code

    Raises:
        ValidationError: If backup code format is invalid
    """
    if not code:
        raise ValidationError(_("Backup code is required."))

    # Remove spaces and convert to uppercase
    clean_code = code.replace(" ", "").replace("-", "").upper()

    if not re.match(r"^[A-Z0-9]{8}$", clean_code):
        raise ValidationError(_("Backup code must be 8 alphanumeric characters."))

    # Format as XXXX-XXXX
    return f"{clean_code[:4]}-{clean_code[4:]}"


def validate_security_token(token: str) -> None:
    """
    Validate security token format.

    Args:
        token: Security token to validate

    Raises:
        ValidationError: If token format is invalid
    """
    if not token:
        raise ValidationError(_("Security token is required."))

    # Check basic format (should have 5 parts separated by colons)
    parts = token.split(":")
    if len(parts) != 5:
        raise ValidationError(_("Invalid token format."))

    # Check if parts are not empty
    if any(not part for part in parts):
        raise ValidationError(_("Invalid token format."))


class PasswordValidator:
    """
    Django-compatible password validator class.
    """

    def __init__(
        self,
        min_length=8,
        require_uppercase=True,
        require_lowercase=True,
        require_digits=True,
        require_symbols=True,
    ):
        self.min_length = min_length
        self.require_uppercase = require_uppercase
        self.require_lowercase = require_lowercase
        self.require_digits = require_digits
        self.require_symbols = require_symbols

    def validate(self, password, user=None):
        """Validate password according to policy."""
        validation_result = validate_password_strength(password, user)

        if not validation_result["is_valid"]:
            raise ValidationError(
                validation_result["feedback"], code="password_too_weak"
            )

    def get_help_text(self):
        """Return help text for password requirements."""
        requirements = [f"at least {self.min_length} characters"]

        if self.require_uppercase:
            requirements.append("uppercase letters")
        if self.require_lowercase:
            requirements.append("lowercase letters")
        if self.require_digits:
            requirements.append("numbers")
        if self.require_symbols:
            requirements.append("special characters")

        return _("Password must contain: ") + ", ".join(requirements) + "."


# Utility validation functions
def is_valid_identifier(identifier: str) -> bool:
    """
    Check if string could be a valid login identifier.

    Args:
        identifier: String to check

    Returns:
        True if could be valid identifier
    """
    if not identifier or len(identifier) < 3:
        return False

    # Could be email
    if "@" in identifier:
        try:
            validate_email(identifier)
            return True
        except ValidationError:
            pass

    # Could be phone
    if re.match(r"^\+?[\d\s\-\(\)]{10,15}$", identifier):
        return True

    # Could be admission number
    if validate_admission_number_identifier(identifier):
        return True

    # Could be username
    if re.match(r"^[a-zA-Z0-9_]{3,150}$", identifier):
        return True

    return False


def sanitize_input(value: str, max_length: int = 255) -> str:
    """
    Sanitize user input by removing dangerous characters.

    Args:
        value: Input string to sanitize
        max_length: Maximum allowed length

    Returns:
        Sanitized string
    """
    if not value:
        return ""

    # Remove null bytes and control characters
    sanitized = "".join(char for char in value if ord(char) >= 32 or char in "\t\n\r")

    # Trim whitespace
    sanitized = sanitized.strip()

    # Limit length
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length]

    return sanitized


def validate_bulk_import_data(csv_data: str) -> Dict[str, Any]:
    """
    Validate CSV data for bulk import.

    Args:
        csv_data: CSV content as string

    Returns:
        Dictionary with validation results
    """
    import csv
    from io import StringIO

    result = {
        "is_valid": True,
        "errors": [],
        "warnings": [],
        "row_count": 0,
        "valid_rows": 0,
    }

    try:
        csv_file = StringIO(csv_data)
        reader = csv.DictReader(csv_file)

        # Check required columns
        required_columns = ["email", "first_name", "last_name"]
        if not all(col in reader.fieldnames for col in required_columns):
            result["is_valid"] = False
            result["errors"].append(
                f"Missing required columns: {', '.join(required_columns)}"
            )
            return result

        # Validate each row
        for row_num, row in enumerate(reader, start=2):
            result["row_count"] += 1
            row_errors = []

            # Validate email
            email = row.get("email", "").strip()
            if not email:
                row_errors.append("Email is required")
            else:
                try:
                    validate_email_address(email)
                except ValidationError as e:
                    row_errors.append(f"Email: {e.message}")

            # Validate names
            if not row.get("first_name", "").strip():
                row_errors.append("First name is required")
            if not row.get("last_name", "").strip():
                row_errors.append("Last name is required")

            # Validate phone if provided
            phone = row.get("phone_number", "").strip()
            if phone:
                try:
                    validate_phone_number(phone)
                except ValidationError as e:
                    row_errors.append(f"Phone: {e.message}")

            if row_errors:
                result["errors"].append(f"Row {row_num}: {'; '.join(row_errors)}")
            else:
                result["valid_rows"] += 1

        if result["errors"]:
            result["is_valid"] = False

    except Exception as e:
        result["is_valid"] = False
        result["errors"].append(f"CSV parsing error: {str(e)}")

    return result
