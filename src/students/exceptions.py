# students/exceptions.py
import logging

from django.core.exceptions import ValidationError
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler

logger = logging.getLogger(__name__)


class StudentModuleException(Exception):
    """Base exception for student module"""

    pass


class StudentNotFoundError(StudentModuleException):
    """Raised when student is not found"""

    pass


class ParentNotFoundError(StudentModuleException):
    """Raised when parent is not found"""

    pass


class RelationshipExistsError(StudentModuleException):
    """Raised when trying to create duplicate relationship"""

    pass


class InvalidStudentStatusError(StudentModuleException):
    """Raised when invalid status transition is attempted"""

    pass


class AdmissionNumberExistsError(StudentModuleException):
    """Raised when admission number already exists"""

    pass


class ImportValidationError(StudentModuleException):
    """Raised during bulk import validation failures"""

    def __init__(self, errors, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.errors = errors


class ExportError(StudentModuleException):
    """Raised during export operations"""

    pass


class ReportingError(StudentModuleException):
    """Raised during report generation"""

    pass


class CommunicationError(StudentModuleException):
    """Raised during communication operations"""

    pass


class AnalyticsError(StudentModuleException):
    """Raised during analytics calculations"""

    pass


def custom_exception_handler(exc, context):
    """Custom exception handler for student module API"""
    response = exception_handler(exc, context)

    if response is not None:
        custom_response_data = {
            "error": True,
            "message": "An error occurred",
            "details": response.data,
        }

        if isinstance(exc, StudentNotFoundError):
            custom_response_data["message"] = "Student not found"
            custom_response_data["code"] = "STUDENT_NOT_FOUND"

        elif isinstance(exc, ParentNotFoundError):
            custom_response_data["message"] = "Parent not found"
            custom_response_data["code"] = "PARENT_NOT_FOUND"

        elif isinstance(exc, RelationshipExistsError):
            custom_response_data["message"] = "Relationship already exists"
            custom_response_data["code"] = "RELATIONSHIP_EXISTS"

        elif isinstance(exc, InvalidStudentStatusError):
            custom_response_data["message"] = "Invalid status transition"
            custom_response_data["code"] = "INVALID_STATUS_TRANSITION"

        elif isinstance(exc, AdmissionNumberExistsError):
            custom_response_data["message"] = "Admission number already exists"
            custom_response_data["code"] = "ADMISSION_NUMBER_EXISTS"

        elif isinstance(exc, ImportValidationError):
            custom_response_data["message"] = "Import validation failed"
            custom_response_data["code"] = "IMPORT_VALIDATION_ERROR"
            custom_response_data["validation_errors"] = exc.errors

        elif isinstance(exc, ValidationError):
            custom_response_data["message"] = "Validation error"
            custom_response_data["code"] = "VALIDATION_ERROR"

        # Log the exception
        logger.error(f"API Exception: {exc.__class__.__name__}: {str(exc)}")

        response.data = custom_response_data

    return response


# Decorator for handling service layer exceptions
def handle_service_exceptions(func):
    """Decorator to handle service layer exceptions"""

    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except StudentModuleException:
            raise  # Re-raise student module exceptions
        except ValidationError as e:
            logger.error(f"Validation error in {func.__name__}: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in {func.__name__}: {str(e)}")
            raise StudentModuleException(f"Service error: {str(e)}")

    return wrapper
