# src/teachers/exceptions.py
"""
Custom exceptions for the teachers module.
These exceptions provide specific error handling for teacher-related operations.
"""

from typing import Any, Dict, Optional

from django.core.exceptions import ValidationError
from rest_framework import status
from rest_framework.exceptions import APIException


class TeacherModuleException(Exception):
    """Base exception for all teacher module related errors."""

    def __init__(self, message: str, code: str = None, details: Dict[str, Any] = None):
        self.message = message
        self.code = code or "TEACHER_ERROR"
        self.details = details or {}
        super().__init__(self.message)

    def __str__(self):
        return f"[{self.code}] {self.message}"


class TeacherNotFoundException(TeacherModuleException):
    """Raised when a teacher is not found."""

    def __init__(self, teacher_id: Any = None, employee_id: str = None):
        if teacher_id:
            message = f"Teacher with ID {teacher_id} not found"
            details = {"teacher_id": teacher_id}
        elif employee_id:
            message = f"Teacher with employee ID {employee_id} not found"
            details = {"employee_id": employee_id}
        else:
            message = "Teacher not found"
            details = {}

        super().__init__(message=message, code="TEACHER_NOT_FOUND", details=details)


class TeacherValidationException(TeacherModuleException):
    """Raised when teacher data validation fails."""

    def __init__(self, message: str, field: str = None, value: Any = None):
        details = {}
        if field:
            details["field"] = field
        if value is not None:
            details["value"] = value

        super().__init__(
            message=message, code="TEACHER_VALIDATION_ERROR", details=details
        )


class DuplicateEmployeeIdException(TeacherValidationException):
    """Raised when attempting to create a teacher with an existing employee ID."""

    def __init__(self, employee_id: str):
        super().__init__(
            message=f"Employee ID '{employee_id}' already exists",
            field="employee_id",
            value=employee_id,
        )
        self.code = "DUPLICATE_EMPLOYEE_ID"


class DuplicateTeacherEmailException(TeacherValidationException):
    """Raised when attempting to create a teacher with an existing email."""

    def __init__(self, email: str):
        super().__init__(
            message=f"Email '{email}' is already in use by another teacher",
            field="email",
            value=email,
        )
        self.code = "DUPLICATE_TEACHER_EMAIL"


class InvalidTeacherStatusException(TeacherValidationException):
    """Raised when an invalid status transition is attempted."""

    def __init__(self, current_status: str, new_status: str, reason: str = None):
        message = (
            f"Cannot change teacher status from '{current_status}' to '{new_status}'"
        )
        if reason:
            message += f": {reason}"

        super().__init__(message=message, field="status")
        self.code = "INVALID_STATUS_TRANSITION"
        self.details.update(
            {
                "current_status": current_status,
                "new_status": new_status,
                "reason": reason,
            }
        )


class TeacherEvaluationException(TeacherModuleException):
    """Base exception for teacher evaluation related errors."""

    def __init__(self, message: str, evaluation_id: Any = None, teacher_id: Any = None):
        details = {}
        if evaluation_id:
            details["evaluation_id"] = evaluation_id
        if teacher_id:
            details["teacher_id"] = teacher_id

        super().__init__(message=message, code="EVALUATION_ERROR", details=details)


class EvaluationNotFoundException(TeacherEvaluationException):
    """Raised when an evaluation is not found."""

    def __init__(self, evaluation_id: Any):
        super().__init__(
            message=f"Evaluation with ID {evaluation_id} not found",
            evaluation_id=evaluation_id,
        )
        self.code = "EVALUATION_NOT_FOUND"


class InvalidEvaluationCriteriaException(TeacherEvaluationException):
    """Raised when evaluation criteria is invalid."""

    def __init__(self, message: str, criteria: Dict[str, Any] = None):
        super().__init__(message=message)
        self.code = "INVALID_EVALUATION_CRITERIA"
        if criteria:
            self.details["criteria"] = criteria


class EvaluationPermissionException(TeacherEvaluationException):
    """Raised when user doesn't have permission to evaluate a teacher."""

    def __init__(self, evaluator_id: Any, teacher_id: Any, reason: str = None):
        message = (
            f"User {evaluator_id} is not authorized to evaluate teacher {teacher_id}"
        )
        if reason:
            message += f": {reason}"

        super().__init__(message=message, teacher_id=teacher_id)
        self.code = "EVALUATION_PERMISSION_DENIED"
        self.details["evaluator_id"] = evaluator_id


class EvaluationAlreadyExistsException(TeacherEvaluationException):
    """Raised when trying to create a duplicate evaluation."""

    def __init__(self, teacher_id: Any, evaluation_date: str):
        super().__init__(
            message=f"Evaluation for teacher {teacher_id} already exists for date {evaluation_date}",
            teacher_id=teacher_id,
        )
        self.code = "EVALUATION_ALREADY_EXISTS"
        self.details["evaluation_date"] = evaluation_date


class TeacherAssignmentException(TeacherModuleException):
    """Base exception for teacher assignment related errors."""

    def __init__(
        self,
        message: str,
        teacher_id: Any = None,
        class_id: Any = None,
        subject_id: Any = None,
    ):
        details = {}
        if teacher_id:
            details["teacher_id"] = teacher_id
        if class_id:
            details["class_id"] = class_id
        if subject_id:
            details["subject_id"] = subject_id

        super().__init__(message=message, code="ASSIGNMENT_ERROR", details=details)


class DuplicateAssignmentException(TeacherAssignmentException):
    """Raised when trying to create a duplicate assignment."""

    def __init__(
        self, teacher_id: Any, class_id: Any, subject_id: Any, academic_year: str
    ):
        super().__init__(
            message=f"Teacher {teacher_id} is already assigned to class {class_id} for subject {subject_id} in {academic_year}",
            teacher_id=teacher_id,
            class_id=class_id,
            subject_id=subject_id,
        )
        self.code = "DUPLICATE_ASSIGNMENT"
        self.details["academic_year"] = academic_year


class MaxWorkloadExceededException(TeacherAssignmentException):
    """Raised when teacher's maximum workload would be exceeded."""

    def __init__(self, teacher_id: Any, current_assignments: int, max_assignments: int):
        super().__init__(
            message=f"Teacher {teacher_id} already has {current_assignments} assignments (max: {max_assignments})",
            teacher_id=teacher_id,
        )
        self.code = "MAX_WORKLOAD_EXCEEDED"
        self.details.update(
            {
                "current_assignments": current_assignments,
                "max_assignments": max_assignments,
            }
        )


class TeacherNotQualifiedException(TeacherAssignmentException):
    """Raised when teacher is not qualified for a subject."""

    def __init__(self, teacher_id: Any, subject_name: str, teacher_specialization: str):
        super().__init__(
            message=f"Teacher {teacher_id} with specialization '{teacher_specialization}' is not qualified to teach '{subject_name}'",
            teacher_id=teacher_id,
        )
        self.code = "TEACHER_NOT_QUALIFIED"
        self.details.update(
            {
                "subject_name": subject_name,
                "teacher_specialization": teacher_specialization,
            }
        )


class ClassTeacherAlreadyAssignedException(TeacherAssignmentException):
    """Raised when trying to assign a class teacher to a class that already has one."""

    def __init__(self, class_id: Any, existing_teacher_id: Any, new_teacher_id: Any):
        super().__init__(
            message=f"Class {class_id} already has teacher {existing_teacher_id} as class teacher",
            class_id=class_id,
        )
        self.code = "CLASS_TEACHER_ALREADY_ASSIGNED"
        self.details.update(
            {
                "existing_teacher_id": existing_teacher_id,
                "new_teacher_id": new_teacher_id,
            }
        )


class TeacherInactiveException(TeacherModuleException):
    """Raised when trying to perform operations on inactive teachers."""

    def __init__(self, teacher_id: Any, status: str, operation: str):
        super().__init__(
            message=f"Cannot perform '{operation}' on teacher {teacher_id} with status '{status}'",
            code="TEACHER_INACTIVE",
        )
        self.details.update(
            {"teacher_id": teacher_id, "status": status, "operation": operation}
        )


class TeacherAnalyticsException(TeacherModuleException):
    """Exception for analytics-related errors."""

    def __init__(
        self,
        message: str,
        analytics_type: str = None,
        error_details: Dict[str, Any] = None,
    ):
        super().__init__(message=message, code="ANALYTICS_ERROR")
        if analytics_type:
            self.details["analytics_type"] = analytics_type
        if error_details:
            self.details.update(error_details)


class InsufficientDataException(TeacherAnalyticsException):
    """Raised when there's insufficient data for analytics calculation."""

    def __init__(
        self, analytics_type: str, required_data: str, available_data: str = None
    ):
        message = f"Insufficient data for {analytics_type} analytics: requires {required_data}"
        if available_data:
            message += f", but only {available_data} available"

        super().__init__(message=message, analytics_type=analytics_type)
        self.code = "INSUFFICIENT_DATA"
        self.details.update(
            {"required_data": required_data, "available_data": available_data}
        )


class TeacherImportException(TeacherModuleException):
    """Exception for teacher import/export operations."""

    def __init__(self, message: str, row_number: int = None, field_name: str = None):
        super().__init__(message=message, code="IMPORT_ERROR")
        if row_number:
            self.details["row_number"] = row_number
        if field_name:
            self.details["field_name"] = field_name


class InvalidFileFormatException(TeacherImportException):
    """Raised when import file format is invalid."""

    def __init__(self, filename: str, expected_format: str, actual_format: str = None):
        message = f"Invalid file format for '{filename}': expected {expected_format}"
        if actual_format:
            message += f", got {actual_format}"

        super().__init__(message=message)
        self.code = "INVALID_FILE_FORMAT"
        self.details.update(
            {
                "filename": filename,
                "expected_format": expected_format,
                "actual_format": actual_format,
            }
        )


class TeacherBulkOperationException(TeacherModuleException):
    """Exception for bulk operations on teachers."""

    def __init__(
        self,
        message: str,
        operation: str,
        successful_count: int = 0,
        failed_count: int = 0,
        errors: list = None,
    ):
        super().__init__(message=message, code="BULK_OPERATION_ERROR")
        self.details.update(
            {
                "operation": operation,
                "successful_count": successful_count,
                "failed_count": failed_count,
                "errors": errors or [],
            }
        )


# REST API Exceptions (for DRF integration)


class TeacherAPIException(APIException):
    """Base API exception for teacher module."""

    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "A teacher module error occurred."
    default_code = "teacher_error"

    def __init__(self, detail=None, code=None, status_code=None):
        if status_code:
            self.status_code = status_code
        super().__init__(detail, code)


class TeacherNotFoundAPIException(TeacherAPIException):
    """API exception for teacher not found."""

    status_code = status.HTTP_404_NOT_FOUND
    default_detail = "Teacher not found."
    default_code = "teacher_not_found"


class TeacherValidationAPIException(TeacherAPIException):
    """API exception for validation errors."""

    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Teacher validation failed."
    default_code = "teacher_validation_error"


class EvaluationPermissionAPIException(TeacherAPIException):
    """API exception for evaluation permission errors."""

    status_code = status.HTTP_403_FORBIDDEN
    default_detail = "You do not have permission to perform this evaluation operation."
    default_code = "evaluation_permission_denied"


class AssignmentConflictAPIException(TeacherAPIException):
    """API exception for assignment conflicts."""

    status_code = status.HTTP_409_CONFLICT
    default_detail = "Teacher assignment conflict detected."
    default_code = "assignment_conflict"


class InsufficientDataAPIException(TeacherAPIException):
    """API exception for insufficient data in analytics."""

    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_detail = "Insufficient data for the requested operation."
    default_code = "insufficient_data"


# Exception utility functions


def handle_teacher_exception(exception: Exception) -> Dict[str, Any]:
    """
    Convert teacher module exceptions to a standardized error response format.

    Args:
        exception: The exception that occurred

    Returns:
        Dict containing error information
    """
    if isinstance(exception, TeacherModuleException):
        return {
            "error": True,
            "code": exception.code,
            "message": exception.message,
            "details": exception.details,
        }
    elif isinstance(exception, ValidationError):
        return {
            "error": True,
            "code": "VALIDATION_ERROR",
            "message": str(exception),
            "details": {},
        }
    else:
        return {
            "error": True,
            "code": "UNKNOWN_ERROR",
            "message": "An unexpected error occurred",
            "details": {"original_error": str(exception)},
        }


def raise_for_teacher_status(teacher, allowed_statuses: list, operation: str):
    """
    Raise an exception if teacher status is not in allowed statuses.

    Args:
        teacher: Teacher instance
        allowed_statuses: List of allowed statuses
        operation: The operation being attempted

    Raises:
        TeacherInactiveException: If teacher status is not allowed
    """
    if teacher.status not in allowed_statuses:
        raise TeacherInactiveException(
            teacher_id=teacher.id, status=teacher.status, operation=operation
        )


def validate_evaluation_permission(evaluator, teacher, operation: str = "evaluate"):
    """
    Validate if evaluator has permission to evaluate the teacher.

    Args:
        evaluator: User attempting to evaluate
        teacher: Teacher being evaluated
        operation: Type of operation being performed

    Raises:
        EvaluationPermissionException: If evaluator lacks permission
    """
    # Check if evaluator is admin/principal
    if (
        evaluator.is_superuser
        or evaluator.groups.filter(name__in=["Admin", "Principal"]).exists()
    ):
        return True

    # Check if evaluator is department head of teacher's department
    if (
        hasattr(evaluator, "teacher_profile")
        and teacher.department
        and teacher.department.head
        and teacher.department.head == evaluator.teacher_profile
    ):
        return True

    # Check if evaluator has specific evaluation permissions
    if evaluator.has_perm("teachers.add_teacherevaluation"):
        return True

    raise EvaluationPermissionException(
        evaluator_id=evaluator.id,
        teacher_id=teacher.id,
        reason=f"User does not have permission to {operation} this teacher",
    )


def validate_assignment_constraints(
    teacher, class_instance, subject, academic_year, assignment_id=None
):
    """
    Validate all constraints for teacher assignment.

    Args:
        teacher: Teacher instance
        class_instance: Class instance
        subject: Subject instance
        academic_year: Academic year instance
        assignment_id: Existing assignment ID (for updates)

    Raises:
        Various assignment-related exceptions
    """
    from src.teachers.models import TeacherClassAssignment

    # Check for duplicate assignment
    existing = TeacherClassAssignment.objects.filter(
        teacher=teacher,
        class_instance=class_instance,
        subject=subject,
        academic_year=academic_year,
    )

    if assignment_id:
        existing = existing.exclude(id=assignment_id)

    if existing.exists():
        raise DuplicateAssignmentException(
            teacher_id=teacher.id,
            class_id=class_instance.id,
            subject_id=subject.id,
            academic_year=academic_year.name,
        )

    # Check teacher status
    raise_for_teacher_status(teacher, ["Active"], "assign to class")

    # Check workload limits
    current_assignments = teacher.class_assignments.filter(
        academic_year=academic_year
    ).count()
    max_assignments = getattr(teacher, "max_assignments", 8)  # Default limit

    if assignment_id is None and current_assignments >= max_assignments:
        raise MaxWorkloadExceededException(
            teacher_id=teacher.id,
            current_assignments=current_assignments,
            max_assignments=max_assignments,
        )


# Context manager for exception handling


class TeacherExceptionContext:
    """Context manager for handling teacher module exceptions."""

    def __init__(self, operation: str, teacher_id: Any = None, log_errors: bool = True):
        self.operation = operation
        self.teacher_id = teacher_id
        self.log_errors = log_errors
        self.error_info = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.error_info = handle_teacher_exception(exc_val)

            if self.log_errors:
                import logging

                logger = logging.getLogger(__name__)
                logger.error(
                    f"Teacher operation '{self.operation}' failed: {self.error_info['message']}",
                    extra={
                        "teacher_id": self.teacher_id,
                        "error_code": self.error_info["code"],
                        "error_details": self.error_info["details"],
                    },
                )

            # Return True to suppress the exception if it's a known teacher exception
            return isinstance(exc_val, TeacherModuleException)

        return False
