# src/api/exceptions.py
"""Custom API Exception Handling"""

import logging

from django.core.exceptions import ObjectDoesNotExist
from django.db import IntegrityError
from django.http import Http404
from rest_framework import status
from rest_framework.exceptions import (
    AuthenticationFailed,
    MethodNotAllowed,
    NotFound,
    PermissionDenied,
    Throttled,
    ValidationError,
)
from rest_framework.response import Response
from rest_framework.views import exception_handler

logger = logging.getLogger(__name__)


class APIException(Exception):
    """Base custom API exception"""

    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_detail = "A server error occurred."
    default_code = "error"

    def __init__(self, detail=None, code=None, status_code=None):
        if detail is not None:
            self.detail = detail
        else:
            self.detail = self.default_detail

        if code is not None:
            self.code = code
        else:
            self.code = self.default_code

        if status_code is not None:
            self.status_code = status_code


class ValidationException(APIException):
    """Custom validation exception"""

    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Invalid data provided."
    default_code = "validation_error"


class BusinessLogicException(APIException):
    """Exception for business logic violations"""

    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_detail = "Business logic violation."
    default_code = "business_logic_error"


class ResourceNotFoundException(APIException):
    """Exception for resource not found"""

    status_code = status.HTTP_404_NOT_FOUND
    default_detail = "Resource not found."
    default_code = "not_found"


class DuplicateResourceException(APIException):
    """Exception for duplicate resource creation"""

    status_code = status.HTTP_409_CONFLICT
    default_detail = "Resource already exists."
    default_code = "duplicate_resource"


class InsufficientPermissionException(APIException):
    """Exception for insufficient permissions"""

    status_code = status.HTTP_403_FORBIDDEN
    default_detail = "Insufficient permissions."
    default_code = "insufficient_permission"


class AcademicYearException(BusinessLogicException):
    """Exception for academic year related issues"""

    default_detail = "Academic year operation not allowed."
    default_code = "academic_year_error"


class TermException(BusinessLogicException):
    """Exception for term related issues"""

    default_detail = "Term operation not allowed."
    default_code = "term_error"


class FeeException(BusinessLogicException):
    """Exception for fee related issues"""

    default_detail = "Fee operation not allowed."
    default_code = "fee_error"


class EnrollmentException(BusinessLogicException):
    """Exception for enrollment related issues"""

    default_detail = "Enrollment operation not allowed."
    default_code = "enrollment_error"


def custom_exception_handler(exc, context):
    """Custom exception handler for the API"""

    # Call REST framework's default exception handler first
    response = exception_handler(exc, context)

    # Log the exception
    logger.error(
        f"API Exception: {exc}",
        exc_info=True,
        extra={"request": context.get("request"), "view": context.get("view")},
    )

    # If response is not None, format it consistently
    if response is not None:
        custom_response_data = {
            "success": False,
            "error": {
                "code": getattr(exc, "default_code", "error"),
                "message": str(exc.detail) if hasattr(exc, "detail") else str(exc),
                "details": response.data if isinstance(response.data, dict) else None,
            },
            "timestamp": context["request"].META.get("HTTP_X_REQUEST_TIME"),
            "path": context["request"].path,
        }

        response.data = custom_response_data
        return response

    # Handle custom exceptions
    if isinstance(exc, APIException):
        return Response(
            {
                "success": False,
                "error": {"code": exc.code, "message": exc.detail, "details": None},
                "timestamp": context["request"].META.get("HTTP_X_REQUEST_TIME"),
                "path": context["request"].path,
            },
            status=exc.status_code,
        )

    # Handle Django's built-in exceptions
    if isinstance(exc, ObjectDoesNotExist):
        return Response(
            {
                "success": False,
                "error": {
                    "code": "not_found",
                    "message": "The requested resource was not found.",
                    "details": None,
                },
            },
            status=status.HTTP_404_NOT_FOUND,
        )

    if isinstance(exc, IntegrityError):
        return Response(
            {
                "success": False,
                "error": {
                    "code": "integrity_error",
                    "message": "Data integrity constraint violation.",
                    "details": str(exc),
                },
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Return None for unhandled exceptions (let Django handle them)
    return None


def format_validation_errors(errors):
    """Format DRF validation errors consistently"""

    formatted_errors = {}

    if isinstance(errors, dict):
        for field, field_errors in errors.items():
            if isinstance(field_errors, list):
                formatted_errors[field] = [str(error) for error in field_errors]
            else:
                formatted_errors[field] = [str(field_errors)]
    elif isinstance(errors, list):
        formatted_errors["non_field_errors"] = [str(error) for error in errors]
    else:
        formatted_errors["non_field_errors"] = [str(errors)]

    return formatted_errors
