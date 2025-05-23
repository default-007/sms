# students/validators.py
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from datetime import date, timedelta
import re


class AdmissionNumberValidator:
    """Validator for admission numbers"""

    def __init__(self, pattern=None, message=None):
        self.pattern = pattern or r"^[A-Z]{2,4}-\d{4}-\d{3,6}$"
        self.message = message or _(
            "Admission number must be in format: AAA-YYYY-NNNN (e.g., STU-2024-001)"
        )

    def __call__(self, value):
        if not value:
            return

        if not re.match(self.pattern, value.upper()):
            raise ValidationError(self.message, code="invalid_admission_number")

        # Check if it's not too old
        try:
            year_part = value.split("-")[1]
            year = int(year_part)
            current_year = timezone.now().year

            if year < 1990 or year > current_year + 1:
                raise ValidationError(
                    _("Admission year must be between 1990 and %(max_year)s"),
                    code="invalid_admission_year",
                    params={"max_year": current_year + 1},
                )
        except (IndexError, ValueError):
            pass  # Let the pattern validation handle this


class PhoneNumberValidator:
    """Enhanced phone number validator"""

    def __init__(self, allow_international=True):
        self.allow_international = allow_international

    def __call__(self, value):
        if not value:
            return

        # Remove all non-digit characters except +
        cleaned = re.sub(r"[^\d+]", "", value)

        # Basic length check
        if len(cleaned) < 10:
            raise ValidationError(
                _("Phone number is too short. Minimum 10 digits required."),
                code="phone_too_short",
            )

        if len(cleaned) > 15:
            raise ValidationError(
                _("Phone number is too long. Maximum 15 digits allowed."),
                code="phone_too_long",
            )

        # Check for valid patterns
        if cleaned.startswith("+"):
            # International format
            if not self.allow_international:
                raise ValidationError(
                    _("International phone numbers are not allowed."),
                    code="international_not_allowed",
                )

            # Basic international validation
            if len(cleaned) < 12:  # +CC + 10 digits minimum
                raise ValidationError(
                    _("Invalid international phone number format."),
                    code="invalid_international",
                )

        else:
            # Domestic format - assume Indian numbers
            if len(cleaned) == 10:
                # Should start with 6, 7, 8, or 9 for mobile
                if cleaned[0] not in "6789":
                    raise ValidationError(
                        _("Mobile number should start with 6, 7, 8, or 9."),
                        code="invalid_mobile_start",
                    )
            elif len(cleaned) == 11:
                # With country code but no +
                if not cleaned.startswith("91"):
                    raise ValidationError(
                        _("Invalid country code. Use +91 for Indian numbers."),
                        code="invalid_country_code",
                    )
            else:
                raise ValidationError(
                    _(
                        "Invalid phone number format. Use 10-digit mobile or +91 format."
                    ),
                    code="invalid_format",
                )


class AgeValidator:
    """Validator for age-related fields"""

    def __init__(self, min_age=3, max_age=25):
        self.min_age = min_age
        self.max_age = max_age

    def __call__(self, value):
        if not value:
            return

        today = date.today()
        age = (
            today.year
            - value.year
            - ((today.month, today.day) < (value.month, value.day))
        )

        if age < self.min_age:
            raise ValidationError(
                _("Age cannot be less than %(min_age)s years."),
                code="age_too_young",
                params={"min_age": self.min_age},
            )

        if age > self.max_age:
            raise ValidationError(
                _("Age cannot be more than %(max_age)s years."),
                code="age_too_old",
                params={"max_age": self.max_age},
            )

        # Check if birth date is not in future
        if value > today:
            raise ValidationError(
                _("Birth date cannot be in the future."), code="future_birth_date"
            )


class AdmissionDateValidator:
    """Validator for admission dates"""

    def __init__(self, allow_future_days=30):
        self.allow_future_days = allow_future_days

    def __call__(self, value):
        if not value:
            return

        today = date.today()

        # Check if too far in the past (more than 20 years)
        twenty_years_ago = today - timedelta(days=20 * 365)
        if value < twenty_years_ago:
            raise ValidationError(
                _("Admission date cannot be more than 20 years old."),
                code="admission_too_old",
            )

        # Check if too far in the future
        max_future_date = today + timedelta(days=self.allow_future_days)
        if value > max_future_date:
            raise ValidationError(
                _("Admission date cannot be more than %(days)s days in the future."),
                code="admission_too_future",
                params={"days": self.allow_future_days},
            )


class NameValidator:
    """Validator for names (first name, last name)"""

    def __init__(self, min_length=2, max_length=50, allow_special_chars=True):
        self.min_length = min_length
        self.max_length = max_length
        self.allow_special_chars = allow_special_chars

    def __call__(self, value):
        if not value:
            raise ValidationError(_("Name is required."), code="name_required")

        # Strip whitespace
        value = value.strip()

        if len(value) < self.min_length:
            raise ValidationError(
                _("Name must be at least %(min_length)s characters long."),
                code="name_too_short",
                params={"min_length": self.min_length},
            )

        if len(value) > self.max_length:
            raise ValidationError(
                _("Name cannot be more than %(max_length)s characters long."),
                code="name_too_long",
                params={"max_length": self.max_length},
            )

        # Check for valid characters
        if self.allow_special_chars:
            # Allow letters, spaces, hyphens, apostrophes, and dots
            pattern = r"^[a-zA-Z\s\-'\.]+$"
        else:
            # Only letters and spaces
            pattern = r"^[a-zA-Z\s]+$"

        if not re.match(pattern, value):
            raise ValidationError(
                _(
                    "Name contains invalid characters. Only letters, spaces, and basic punctuation allowed."
                ),
                code="invalid_name_characters",
            )

        # Check for consecutive spaces or starting/ending with space
        if "  " in value or value.startswith(" ") or value.endswith(" "):
            raise ValidationError(
                _("Name cannot have leading/trailing spaces or consecutive spaces."),
                code="invalid_name_spacing",
            )


class EmailDomainValidator:
    """Validator to restrict email domains"""

    def __init__(self, allowed_domains=None, blocked_domains=None):
        self.allowed_domains = allowed_domains or []
        self.blocked_domains = blocked_domains or [
            "tempmail.org",
            "10minutemail.com",
            "guerrillamail.com",
            "mailinator.com",
            "throwaway.email",
        ]

    def __call__(self, value):
        if not value:
            return

        try:
            domain = value.split("@")[1].lower()
        except IndexError:
            raise ValidationError(_("Invalid email format."), code="invalid_email")

        # Check blocked domains
        if domain in self.blocked_domains:
            raise ValidationError(
                _("This email domain is not allowed."), code="blocked_domain"
            )

        # Check allowed domains (if specified)
        if self.allowed_domains and domain not in self.allowed_domains:
            raise ValidationError(
                _("Email must be from one of these domains: %(domains)s"),
                code="domain_not_allowed",
                params={"domains": ", ".join(self.allowed_domains)},
            )


class BloodGroupValidator:
    """Validator for blood group field"""

    VALID_BLOOD_GROUPS = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-", "Unknown"]

    def __call__(self, value):
        if not value:
            return

        if value not in self.VALID_BLOOD_GROUPS:
            raise ValidationError(
                _("Invalid blood group. Valid options: %(groups)s"),
                code="invalid_blood_group",
                params={"groups": ", ".join(self.VALID_BLOOD_GROUPS)},
            )


class StudentStatusValidator:
    """Validator for student status transitions"""

    VALID_TRANSITIONS = {
        "Active": ["Inactive", "Suspended", "Graduated", "Withdrawn"],
        "Inactive": ["Active", "Withdrawn"],
        "Suspended": ["Active", "Expelled", "Withdrawn"],
        "Graduated": [],  # Cannot change from graduated
        "Expelled": [],  # Cannot change from expelled
        "Withdrawn": ["Active"],  # Can re-admit withdrawn students
    }

    def __init__(self, current_status=None):
        self.current_status = current_status

    def __call__(self, value):
        if not value:
            return

        if not self.current_status:
            return  # New student, any status is allowed

        if self.current_status == value:
            return  # No change

        allowed_transitions = self.VALID_TRANSITIONS.get(self.current_status, [])

        if value not in allowed_transitions:
            raise ValidationError(
                _(
                    'Cannot change status from "%(current)s" to "%(new)s". Allowed: %(allowed)s'
                ),
                code="invalid_status_transition",
                params={
                    "current": self.current_status,
                    "new": value,
                    "allowed": (
                        ", ".join(allowed_transitions)
                        if allowed_transitions
                        else "None"
                    ),
                },
            )


class FileValidator:
    """Validator for uploaded files"""

    def __init__(self, allowed_extensions=None, max_size_mb=5, min_size_bytes=1024):
        self.allowed_extensions = allowed_extensions or [
            "jpg",
            "jpeg",
            "png",
            "gif",
            "pdf",
        ]
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.min_size_bytes = min_size_bytes

    def __call__(self, value):
        if not value:
            return

        # Check file size
        if value.size > self.max_size_bytes:
            raise ValidationError(
                _("File size cannot exceed %(max_size)sMB."),
                code="file_too_large",
                params={"max_size": self.max_size_bytes // (1024 * 1024)},
            )

        if value.size < self.min_size_bytes:
            raise ValidationError(
                _("File is too small. Minimum size: %(min_size)s bytes."),
                code="file_too_small",
                params={"min_size": self.min_size_bytes},
            )

        # Check file extension
        try:
            extension = value.name.split(".")[-1].lower()
        except (AttributeError, IndexError):
            raise ValidationError(
                _("File must have a valid extension."), code="no_extension"
            )

        if extension not in self.allowed_extensions:
            raise ValidationError(
                _("File type not allowed. Allowed types: %(types)s"),
                code="invalid_extension",
                params={"types": ", ".join(self.allowed_extensions)},
            )


class AddressValidator:
    """Validator for address fields"""

    def __init__(self, max_length=500, require_components=True):
        self.max_length = max_length
        self.require_components = require_components

    def __call__(self, value):
        if not value:
            if self.require_components:
                raise ValidationError(
                    _("Address is required."), code="address_required"
                )
            return

        value = value.strip()

        if len(value) > self.max_length:
            raise ValidationError(
                _("Address cannot be more than %(max_length)s characters."),
                code="address_too_long",
                params={"max_length": self.max_length},
            )

        # Basic validation - should contain some alphanumeric characters
        if not re.search(r"[a-zA-Z0-9]", value):
            raise ValidationError(
                _("Address must contain alphanumeric characters."),
                code="invalid_address",
            )

        # Check for minimum meaningful content
        if len(value.split()) < 2:
            raise ValidationError(
                _("Address seems too short. Please provide a complete address."),
                code="address_too_short",
            )


# Predefined validator instances for common use cases
admission_number_validator = AdmissionNumberValidator()
phone_validator = PhoneNumberValidator()
student_age_validator = AgeValidator(min_age=3, max_age=25)
admission_date_validator = AdmissionDateValidator()
name_validator = NameValidator()
email_domain_validator = EmailDomainValidator()
blood_group_validator = BloodGroupValidator()
photo_validator = FileValidator(
    allowed_extensions=["jpg", "jpeg", "png"], max_size_mb=2
)
document_validator = FileValidator(
    allowed_extensions=["pdf", "doc", "docx", "jpg", "jpeg", "png"], max_size_mb=10
)
address_validator = AddressValidator()


def validate_student_data(student_data, user_data=None):
    """
    Comprehensive validation for student data

    Args:
        student_data (dict): Student model data
        user_data (dict): User model data

    Returns:
        list: List of validation errors
    """
    errors = []

    try:
        # Validate admission number
        if "admission_number" in student_data:
            admission_number_validator(student_data["admission_number"])
    except ValidationError as e:
        errors.append(f"Admission Number: {e.message}")

    try:
        # Validate admission date
        if "admission_date" in student_data:
            admission_date_validator(student_data["admission_date"])
    except ValidationError as e:
        errors.append(f"Admission Date: {e.message}")

    try:
        # Validate blood group
        if "blood_group" in student_data:
            blood_group_validator(student_data["blood_group"])
    except ValidationError as e:
        errors.append(f"Blood Group: {e.message}")

    try:
        # Validate emergency contact number
        if "emergency_contact_number" in student_data:
            phone_validator(student_data["emergency_contact_number"])
    except ValidationError as e:
        errors.append(f"Emergency Contact Number: {e.message}")

    # Validate user data if provided
    if user_data:
        try:
            if "first_name" in user_data:
                name_validator(user_data["first_name"])
        except ValidationError as e:
            errors.append(f"First Name: {e.message}")

        try:
            if "last_name" in user_data:
                name_validator(user_data["last_name"])
        except ValidationError as e:
            errors.append(f"Last Name: {e.message}")

        try:
            if "email" in user_data:
                email_domain_validator(user_data["email"])
        except ValidationError as e:
            errors.append(f"Email: {e.message}")

        try:
            if "date_of_birth" in user_data and user_data["date_of_birth"]:
                student_age_validator(user_data["date_of_birth"])
        except ValidationError as e:
            errors.append(f"Date of Birth: {e.message}")

        try:
            if "phone_number" in user_data and user_data["phone_number"]:
                phone_validator(user_data["phone_number"])
        except ValidationError as e:
            errors.append(f"Phone Number: {e.message}")

    return errors


def validate_parent_data(parent_data, user_data=None):
    """
    Comprehensive validation for parent data

    Args:
        parent_data (dict): Parent model data
        user_data (dict): User model data

    Returns:
        list: List of validation errors
    """
    errors = []

    # Validate user data if provided
    if user_data:
        try:
            if "first_name" in user_data:
                name_validator(user_data["first_name"])
        except ValidationError as e:
            errors.append(f"First Name: {e.message}")

        try:
            if "last_name" in user_data:
                name_validator(user_data["last_name"])
        except ValidationError as e:
            errors.append(f"Last Name: {e.message}")

        try:
            if "email" in user_data:
                email_domain_validator(user_data["email"])
        except ValidationError as e:
            errors.append(f"Email: {e.message}")

        try:
            if "phone_number" in user_data:
                phone_validator(user_data["phone_number"])
        except ValidationError as e:
            errors.append(f"Phone Number: {e.message}")

    # Validate work phone if provided
    try:
        if "work_phone" in parent_data and parent_data["work_phone"]:
            phone_validator(parent_data["work_phone"])
    except ValidationError as e:
        errors.append(f"Work Phone: {e.message}")

    return errors
