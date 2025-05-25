# src/teachers/validators.py
"""
Custom validators for the teachers module.
These validators provide comprehensive validation for teacher-related data.
"""

import re
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional, Union

from django.core.exceptions import ValidationError
from django.core.validators import EmailValidator, RegexValidator
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from src.teachers.models import Teacher, TeacherEvaluation, TeacherClassAssignment
from src.teachers.exceptions import (
    TeacherValidationException,
    DuplicateEmployeeIdException,
    DuplicateTeacherEmailException,
    InvalidEvaluationCriteriaException,
)

User = get_user_model()


class EmployeeIdValidator:
    """Validator for teacher employee ID format and uniqueness."""

    def __init__(self, pattern=r"^T\d{6}$", exclude_teacher_id=None):
        """
        Initialize validator.

        Args:
            pattern: Regex pattern for employee ID format
            exclude_teacher_id: Teacher ID to exclude from uniqueness check (for updates)
        """
        self.pattern = pattern
        self.exclude_teacher_id = exclude_teacher_id
        self.regex_validator = RegexValidator(
            regex=pattern,
            message=_(
                "Employee ID must be in format T followed by 6 digits (e.g., T123456)"
            ),
            code="invalid_employee_id_format",
        )

    def __call__(self, value):
        """Validate employee ID."""
        # Check format
        self.regex_validator(value)

        # Check uniqueness
        existing = Teacher.objects.filter(employee_id=value)
        if self.exclude_teacher_id:
            existing = existing.exclude(id=self.exclude_teacher_id)

        if existing.exists():
            raise DuplicateEmployeeIdException(value)

        return value


class TeacherEmailValidator:
    """Validator for teacher email uniqueness."""

    def __init__(self, exclude_user_id=None):
        """
        Initialize validator.

        Args:
            exclude_user_id: User ID to exclude from uniqueness check (for updates)
        """
        self.exclude_user_id = exclude_user_id
        self.email_validator = EmailValidator()

    def __call__(self, value):
        """Validate email format and uniqueness."""
        # Check format
        self.email_validator(value)

        # Check uniqueness
        existing = User.objects.filter(email=value)
        if self.exclude_user_id:
            existing = existing.exclude(id=self.exclude_user_id)

        if existing.exists():
            raise DuplicateTeacherEmailException(value)

        return value


class DateRangeValidator:
    """Validator for date ranges."""

    def __init__(self, min_date=None, max_date=None, field_name="date"):
        """
        Initialize validator.

        Args:
            min_date: Minimum allowed date
            max_date: Maximum allowed date
            field_name: Name of the field being validated (for error messages)
        """
        self.min_date = min_date
        self.max_date = max_date
        self.field_name = field_name

    def __call__(self, value):
        """Validate date range."""
        if not isinstance(value, (date, datetime)):
            raise ValidationError(
                _("Invalid date format for {field}").format(field=self.field_name),
                code="invalid_date_format",
            )

        # Convert datetime to date if necessary
        if isinstance(value, datetime):
            value = value.date()

        if self.min_date and value < self.min_date:
            raise ValidationError(
                _("The {field} cannot be earlier than {min_date}").format(
                    field=self.field_name, min_date=self.min_date
                ),
                code="date_too_early",
            )

        if self.max_date and value > self.max_date:
            raise ValidationError(
                _("The {field} cannot be later than {max_date}").format(
                    field=self.field_name, max_date=self.max_date
                ),
                code="date_too_late",
            )

        return value


class JoiningDateValidator(DateRangeValidator):
    """Validator specifically for teacher joining dates."""

    def __init__(self):
        # Teachers can't join before 1950 or in the future
        min_date = date(1950, 1, 1)
        max_date = timezone.now().date()
        super().__init__(
            min_date=min_date, max_date=max_date, field_name="joining date"
        )


class ExperienceValidator:
    """Validator for teacher experience years."""

    def __init__(self, min_experience=0, max_experience=50):
        """
        Initialize validator.

        Args:
            min_experience: Minimum years of experience
            max_experience: Maximum years of experience
        """
        self.min_experience = min_experience
        self.max_experience = max_experience

    def __call__(self, value):
        """Validate experience years."""
        try:
            experience = Decimal(str(value))
        except (InvalidOperation, ValueError):
            raise ValidationError(
                _("Experience must be a valid number"), code="invalid_experience_format"
            )

        if experience < self.min_experience:
            raise ValidationError(
                _("Experience cannot be negative"), code="negative_experience"
            )

        if experience > self.max_experience:
            raise ValidationError(
                _("Experience cannot exceed {max_years} years").format(
                    max_years=self.max_experience
                ),
                code="excessive_experience",
            )

        return experience


class SalaryValidator:
    """Validator for teacher salary."""

    def __init__(self, min_salary=0, max_salary=1000000, currency="USD"):
        """
        Initialize validator.

        Args:
            min_salary: Minimum allowed salary
            max_salary: Maximum allowed salary
            currency: Currency code for error messages
        """
        self.min_salary = min_salary
        self.max_salary = max_salary
        self.currency = currency

    def __call__(self, value):
        """Validate salary amount."""
        try:
            salary = Decimal(str(value))
        except (InvalidOperation, ValueError):
            raise ValidationError(
                _("Salary must be a valid number"), code="invalid_salary_format"
            )

        if salary < self.min_salary:
            raise ValidationError(
                _("Salary cannot be negative"), code="negative_salary"
            )

        if salary > self.max_salary:
            raise ValidationError(
                _("Salary cannot exceed {max_amount} {currency}").format(
                    max_amount=self.max_salary, currency=self.currency
                ),
                code="excessive_salary",
            )

        return salary


class PhoneNumberValidator:
    """Validator for phone numbers."""

    def __init__(self, pattern=r"^\+?[\d\s\-\(\)\.]{10,20}$"):
        """
        Initialize validator.

        Args:
            pattern: Regex pattern for phone number validation
        """
        self.pattern = pattern
        self.regex_validator = RegexValidator(
            regex=pattern,
            message=_(
                "Enter a valid phone number (10-20 digits, may include +, spaces, hyphens, parentheses)"
            ),
            code="invalid_phone_number",
        )

    def __call__(self, value):
        """Validate phone number."""
        if not value:  # Allow empty phone numbers
            return value

        # Remove common formatting characters for validation
        cleaned = re.sub(r"[\s\-\(\)\.]", "", value)

        # Check if it contains only digits and optional + at the start
        if not re.match(r"^\+?\d{10,15}$", cleaned):
            raise ValidationError(
                _("Phone number must contain 10-15 digits and may start with +"),
                code="invalid_phone_format",
            )

        return value


class EvaluationCriteriaValidator:
    """Validator for teacher evaluation criteria."""

    def __init__(self, required_criteria=None, max_score=10):
        """
        Initialize validator.

        Args:
            required_criteria: List of required criteria keys
            max_score: Maximum score per criterion
        """
        self.required_criteria = required_criteria or [
            "teaching_methodology",
            "subject_knowledge",
            "classroom_management",
            "student_engagement",
            "professional_conduct",
        ]
        self.max_score = max_score

    def __call__(self, value):
        """Validate evaluation criteria structure."""
        if not isinstance(value, dict):
            raise InvalidEvaluationCriteriaException(
                "Evaluation criteria must be a dictionary", criteria=value
            )

        # Check for required criteria
        missing_criteria = [
            criterion for criterion in self.required_criteria if criterion not in value
        ]

        if missing_criteria:
            raise InvalidEvaluationCriteriaException(
                f"Missing required criteria: {', '.join(missing_criteria)}",
                criteria=value,
            )

        # Validate each criterion
        for criterion, data in value.items():
            self._validate_criterion(criterion, data)

        return value

    def _validate_criterion(self, criterion, data):
        """Validate individual criterion data."""
        if not isinstance(data, dict):
            raise InvalidEvaluationCriteriaException(
                f"Criterion '{criterion}' must be a dictionary",
                criteria={criterion: data},
            )

        required_fields = ["score", "max_score"]
        missing_fields = [field for field in required_fields if field not in data]

        if missing_fields:
            raise InvalidEvaluationCriteriaException(
                f"Criterion '{criterion}' missing required fields: {', '.join(missing_fields)}",
                criteria={criterion: data},
            )

        # Validate score values
        try:
            score = float(data["score"])
            max_score = float(data["max_score"])
        except (ValueError, TypeError):
            raise InvalidEvaluationCriteriaException(
                f"Criterion '{criterion}' has invalid score values",
                criteria={criterion: data},
            )

        if score < 0 or score > max_score:
            raise InvalidEvaluationCriteriaException(
                f"Criterion '{criterion}' score must be between 0 and {max_score}",
                criteria={criterion: data},
            )

        if max_score <= 0 or max_score > self.max_score:
            raise InvalidEvaluationCriteriaException(
                f"Criterion '{criterion}' max_score must be between 1 and {self.max_score}",
                criteria={criterion: data},
            )


class EvaluationScoreValidator:
    """Validator for evaluation scores."""

    def __init__(self, min_score=0, max_score=100):
        """
        Initialize validator.

        Args:
            min_score: Minimum allowed score
            max_score: Maximum allowed score
        """
        self.min_score = min_score
        self.max_score = max_score

    def __call__(self, value):
        """Validate evaluation score."""
        try:
            score = float(value)
        except (ValueError, TypeError):
            raise ValidationError(
                _("Evaluation score must be a valid number"),
                code="invalid_score_format",
            )

        if score < self.min_score or score > self.max_score:
            raise ValidationError(
                _(
                    "Evaluation score must be between {min_score} and {max_score}"
                ).format(min_score=self.min_score, max_score=self.max_score),
                code="score_out_of_range",
            )

        return score


class AssignmentConstraintsValidator:
    """Validator for teacher class assignment constraints."""

    def __init__(self, max_assignments=8, assignment_id=None):
        """
        Initialize validator.

        Args:
            max_assignments: Maximum assignments per teacher
            assignment_id: Existing assignment ID (for updates)
        """
        self.max_assignments = max_assignments
        self.assignment_id = assignment_id

    def __call__(self, data):
        """Validate assignment constraints."""
        teacher = data.get("teacher")
        class_instance = data.get("class_instance")
        subject = data.get("subject")
        academic_year = data.get("academic_year")

        if not all([teacher, class_instance, subject, academic_year]):
            raise ValidationError(
                _(
                    "All assignment fields (teacher, class, subject, academic year) are required"
                ),
                code="missing_assignment_fields",
            )

        # Check teacher status
        if teacher.status != "Active":
            raise ValidationError(
                _("Cannot assign inactive teacher to classes"),
                code="inactive_teacher_assignment",
            )

        # Check for duplicate assignment
        existing = TeacherClassAssignment.objects.filter(
            teacher=teacher,
            class_instance=class_instance,
            subject=subject,
            academic_year=academic_year,
        )

        if self.assignment_id:
            existing = existing.exclude(id=self.assignment_id)

        if existing.exists():
            raise ValidationError(
                _("Teacher is already assigned to this class and subject"),
                code="duplicate_assignment",
            )

        # Check workload limits
        current_assignments = teacher.class_assignments.filter(
            academic_year=academic_year
        ).count()

        if self.assignment_id is None and current_assignments >= self.max_assignments:
            raise ValidationError(
                _(
                    "Teacher already has maximum number of assignments ({max_assignments})"
                ).format(max_assignments=self.max_assignments),
                code="max_assignments_exceeded",
            )

        return data


class QualificationValidator:
    """Validator for teacher qualifications."""

    def __init__(self, min_length=5, max_length=200):
        """
        Initialize validator.

        Args:
            min_length: Minimum qualification length
            max_length: Maximum qualification length
        """
        self.min_length = min_length
        self.max_length = max_length

    def __call__(self, value):
        """Validate qualification string."""
        if not value or not value.strip():
            raise ValidationError(
                _("Qualification is required"), code="qualification_required"
            )

        value = value.strip()

        if len(value) < self.min_length:
            raise ValidationError(
                _("Qualification must be at least {min_length} characters long").format(
                    min_length=self.min_length
                ),
                code="qualification_too_short",
            )

        if len(value) > self.max_length:
            raise ValidationError(
                _("Qualification cannot exceed {max_length} characters").format(
                    max_length=self.max_length
                ),
                code="qualification_too_long",
            )

        return value


class SpecializationValidator:
    """Validator for teacher specializations."""

    def __init__(self, allowed_specializations=None, allow_custom=True):
        """
        Initialize validator.

        Args:
            allowed_specializations: List of allowed specializations
            allow_custom: Whether to allow custom specializations
        """
        self.allowed_specializations = allowed_specializations or [
            "Mathematics",
            "Science",
            "English",
            "History",
            "Geography",
            "Physics",
            "Chemistry",
            "Biology",
            "Computer Science",
            "Art",
            "Music",
            "Physical Education",
            "Languages",
            "Social Studies",
        ]
        self.allow_custom = allow_custom

    def __call__(self, value):
        """Validate specialization."""
        if not value or not value.strip():
            raise ValidationError(
                _("Specialization is required"), code="specialization_required"
            )

        value = value.strip()

        # Check if it's in allowed list
        if not self.allow_custom and value not in self.allowed_specializations:
            raise ValidationError(
                _("Invalid specialization. Must be one of: {allowed}").format(
                    allowed=", ".join(self.allowed_specializations)
                ),
                code="invalid_specialization",
            )

        return value


class BulkImportValidator:
    """Validator for bulk teacher import data."""

    def __init__(self, required_fields=None):
        """
        Initialize validator.

        Args:
            required_fields: List of required fields for import
        """
        self.required_fields = required_fields or [
            "employee_id",
            "first_name",
            "last_name",
            "email",
            "joining_date",
            "qualification",
            "specialization",
        ]

        # Initialize individual validators
        self.employee_id_validator = EmployeeIdValidator()
        self.email_validator = TeacherEmailValidator()
        self.phone_validator = PhoneNumberValidator()
        self.experience_validator = ExperienceValidator()
        self.salary_validator = SalaryValidator()

    def validate_row(self, row_data, row_number):
        """
        Validate a single row of import data.

        Args:
            row_data: Dictionary containing row data
            row_number: Row number for error reporting

        Returns:
            Dictionary with validation results
        """
        errors = []
        warnings = []

        # Check required fields
        missing_fields = [
            field
            for field in self.required_fields
            if field not in row_data or not str(row_data[field]).strip()
        ]

        if missing_fields:
            errors.append(f"Missing required fields: {', '.join(missing_fields)}")

        # Validate individual fields
        try:
            if "employee_id" in row_data:
                self.employee_id_validator(row_data["employee_id"])
        except ValidationError as e:
            errors.append(f"Employee ID: {e.message}")

        try:
            if "email" in row_data:
                self.email_validator(row_data["email"])
        except ValidationError as e:
            errors.append(f"Email: {e.message}")

        if "phone_number" in row_data and row_data["phone_number"]:
            try:
                self.phone_validator(row_data["phone_number"])
            except ValidationError as e:
                warnings.append(f"Phone number: {e.message}")

        if "experience_years" in row_data and row_data["experience_years"]:
            try:
                self.experience_validator(row_data["experience_years"])
            except ValidationError as e:
                errors.append(f"Experience: {e.message}")

        if "salary" in row_data and row_data["salary"]:
            try:
                self.salary_validator(row_data["salary"])
            except ValidationError as e:
                errors.append(f"Salary: {e.message}")

        # Validate joining date
        if "joining_date" in row_data:
            try:
                # Try to parse the date
                if isinstance(row_data["joining_date"], str):
                    # Handle common date formats
                    for fmt in ["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"]:
                        try:
                            parsed_date = datetime.strptime(
                                row_data["joining_date"], fmt
                            ).date()
                            row_data["joining_date"] = parsed_date
                            break
                        except ValueError:
                            continue
                    else:
                        errors.append("Joining date: Invalid date format")

                if isinstance(row_data["joining_date"], date):
                    validator = JoiningDateValidator()
                    validator(row_data["joining_date"])
            except ValidationError as e:
                errors.append(f"Joining date: {e.message}")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "row_number": row_number,
            "data": row_data,
        }

    def validate_bulk_data(self, data_rows):
        """
        Validate multiple rows of import data.

        Args:
            data_rows: List of dictionaries containing row data

        Returns:
            Dictionary with overall validation results
        """
        results = []
        valid_count = 0
        error_count = 0

        for i, row_data in enumerate(data_rows, 1):
            result = self.validate_row(row_data, i)
            results.append(result)

            if result["valid"]:
                valid_count += 1
            else:
                error_count += 1

        return {
            "total_rows": len(data_rows),
            "valid_rows": valid_count,
            "error_rows": error_count,
            "success_rate": (valid_count / len(data_rows) * 100) if data_rows else 0,
            "results": results,
        }


# Composite validators for complete teacher validation


def validate_teacher_data(data, teacher_id=None, user_id=None):
    """
    Comprehensive validation for teacher data.

    Args:
        data: Dictionary containing teacher data
        teacher_id: Existing teacher ID (for updates)
        user_id: Existing user ID (for updates)

    Returns:
        Validated and cleaned data

    Raises:
        ValidationError: If validation fails
    """
    errors = {}

    # Validate employee ID
    if "employee_id" in data:
        try:
            validator = EmployeeIdValidator(exclude_teacher_id=teacher_id)
            data["employee_id"] = validator(data["employee_id"])
        except ValidationError as e:
            errors["employee_id"] = e.message

    # Validate email
    if "email" in data:
        try:
            validator = TeacherEmailValidator(exclude_user_id=user_id)
            data["email"] = validator(data["email"])
        except ValidationError as e:
            errors["email"] = e.message

    # Validate joining date
    if "joining_date" in data:
        try:
            validator = JoiningDateValidator()
            data["joining_date"] = validator(data["joining_date"])
        except ValidationError as e:
            errors["joining_date"] = e.message

    # Validate experience
    if "experience_years" in data:
        try:
            validator = ExperienceValidator()
            data["experience_years"] = validator(data["experience_years"])
        except ValidationError as e:
            errors["experience_years"] = e.message

    # Validate salary
    if "salary" in data:
        try:
            validator = SalaryValidator()
            data["salary"] = validator(data["salary"])
        except ValidationError as e:
            errors["salary"] = e.message

    # Validate phone number
    if "phone_number" in data:
        try:
            validator = PhoneNumberValidator()
            data["phone_number"] = validator(data["phone_number"])
        except ValidationError as e:
            errors["phone_number"] = e.message

    # Validate qualification
    if "qualification" in data:
        try:
            validator = QualificationValidator()
            data["qualification"] = validator(data["qualification"])
        except ValidationError as e:
            errors["qualification"] = e.message

    # Validate specialization
    if "specialization" in data:
        try:
            validator = SpecializationValidator()
            data["specialization"] = validator(data["specialization"])
        except ValidationError as e:
            errors["specialization"] = e.message

    if errors:
        raise ValidationError(errors)

    return data


def validate_evaluation_data(data, evaluation_id=None):
    """
    Comprehensive validation for evaluation data.

    Args:
        data: Dictionary containing evaluation data
        evaluation_id: Existing evaluation ID (for updates)

    Returns:
        Validated and cleaned data

    Raises:
        ValidationError: If validation fails
    """
    errors = {}

    # Validate criteria
    if "criteria" in data:
        try:
            validator = EvaluationCriteriaValidator()
            data["criteria"] = validator(data["criteria"])
        except InvalidEvaluationCriteriaException as e:
            errors["criteria"] = e.message

    # Validate score
    if "score" in data:
        try:
            validator = EvaluationScoreValidator()
            data["score"] = validator(data["score"])
        except ValidationError as e:
            errors["score"] = e.message

    # Validate evaluation date
    if "evaluation_date" in data:
        try:
            validator = DateRangeValidator(
                min_date=date(2000, 1, 1),
                max_date=timezone.now().date(),
                field_name="evaluation date",
            )
            data["evaluation_date"] = validator(data["evaluation_date"])
        except ValidationError as e:
            errors["evaluation_date"] = e.message

    # Validate followup date (if provided)
    if "followup_date" in data and data["followup_date"]:
        try:
            validator = DateRangeValidator(
                min_date=timezone.now().date(),
                max_date=timezone.now().date() + timedelta(days=365),
                field_name="followup date",
            )
            data["followup_date"] = validator(data["followup_date"])
        except ValidationError as e:
            errors["followup_date"] = e.message

    if errors:
        raise ValidationError(errors)

    return data
