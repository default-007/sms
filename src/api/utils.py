# src/api/utils.py
"""API Utility Functions"""

import hashlib
import json
from datetime import datetime, timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response


def success_response(data=None, message="Success", status_code=status.HTTP_200_OK):
    """Standardized success response"""
    response_data = {
        "success": True,
        "message": message,
        "data": data,
        "timestamp": timezone.now().isoformat(),
    }
    return Response(response_data, status=status_code)


def error_response(
    message="Error", errors=None, status_code=status.HTTP_400_BAD_REQUEST
):
    """Standardized error response"""
    response_data = {
        "success": False,
        "message": message,
        "errors": errors,
        "timestamp": timezone.now().isoformat(),
    }
    return Response(response_data, status=status_code)


def validate_academic_year_operation(academic_year, operation_type="general"):
    """Validate if operation is allowed for academic year"""
    if not academic_year.is_current:
        raise ValidationError(f"Operation not allowed for non-current academic year")

    # Add more specific validations based on operation_type
    return True


def validate_term_operation(term, operation_type="general"):
    """Validate if operation is allowed for term"""
    if not term.is_current:
        raise ValidationError(f"Operation not allowed for non-current term")

    # Check if term dates allow the operation
    now = timezone.now().date()
    if operation_type == "enrollment" and now > term.end_date:
        raise ValidationError("Enrollment not allowed after term end date")

    return True


def generate_cache_key(*args):
    """Generate consistent cache key"""
    key_string = ":".join(str(arg) for arg in args)
    return hashlib.md5(key_string.encode()).hexdigest()


def get_current_academic_context():
    """Get current academic year and term"""
    from src.academics.models import AcademicYear, Term

    try:
        current_year = AcademicYear.objects.get(is_current=True)
        current_term = Term.objects.get(academic_year=current_year, is_current=True)
        return {"academic_year": current_year, "term": current_term}
    except (AcademicYear.DoesNotExist, Term.DoesNotExist):
        return None


def check_user_access_to_student(user, student):
    """Check if user has access to student data"""
    if user.is_admin or user.is_teacher:
        return True

    if user.is_parent:
        return student.parents.filter(user=user).exists()

    if user.is_student:
        return user.student == student

    return False


def apply_academic_filters(queryset, request):
    """Apply common academic filters to queryset"""
    # Academic year filter
    academic_year_id = request.query_params.get("academic_year")
    if academic_year_id:
        queryset = queryset.filter(academic_year_id=academic_year_id)

    # Term filter
    term_id = request.query_params.get("term")
    if term_id:
        queryset = queryset.filter(term_id=term_id)

    # Section filter
    section_id = request.query_params.get("section")
    if section_id:
        queryset = queryset.filter(section_id=section_id)

    # Grade filter
    grade_id = request.query_params.get("grade")
    if grade_id:
        queryset = queryset.filter(grade_id=grade_id)

    # Class filter
    class_id = request.query_params.get("class")
    if class_id:
        queryset = queryset.filter(class_id=class_id)

    return queryset


def format_response_data(data, serializer_class=None, many=False):
    """Format response data consistently"""
    if serializer_class and data:
        if many:
            return serializer_class(data, many=True).data
        else:
            return serializer_class(data).data
    return data


class APIResponseMixin:
    """Mixin for consistent API responses"""

    def success_response(
        self, data=None, message="Success", status_code=status.HTTP_200_OK
    ):
        return success_response(data, message, status_code)

    def error_response(
        self, message="Error", errors=None, status_code=status.HTTP_400_BAD_REQUEST
    ):
        return error_response(message, errors, status_code)

    def paginated_response(self, queryset, serializer_class, message="Success"):
        """Return paginated response"""
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = serializer_class(
                page, many=True, context={"request": self.request}
            )
            return self.get_paginated_response(serializer.data)

        serializer = serializer_class(
            queryset, many=True, context={"request": self.request}
        )
        return self.success_response(serializer.data, message)
