# src/api/documentation.py
"""API Documentation Configuration"""

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)
from rest_framework import status

# Common parameters
ACADEMIC_YEAR_PARAM = OpenApiParameter(
    name="academic_year",
    type=OpenApiTypes.INT,
    location=OpenApiParameter.QUERY,
    description="Filter by academic year ID",
)

TERM_PARAM = OpenApiParameter(
    name="term",
    type=OpenApiTypes.INT,
    location=OpenApiParameter.QUERY,
    description="Filter by term ID",
)

SECTION_PARAM = OpenApiParameter(
    name="section",
    type=OpenApiTypes.INT,
    location=OpenApiParameter.QUERY,
    description="Filter by section ID",
)

GRADE_PARAM = OpenApiParameter(
    name="grade",
    type=OpenApiTypes.INT,
    location=OpenApiParameter.QUERY,
    description="Filter by grade ID",
)

CLASS_PARAM = OpenApiParameter(
    name="class",
    type=OpenApiTypes.INT,
    location=OpenApiParameter.QUERY,
    description="Filter by class ID",
)

PAGINATION_PARAMS = [
    OpenApiParameter(
        name="page",
        type=OpenApiTypes.INT,
        location=OpenApiParameter.QUERY,
        description="Page number",
    ),
    OpenApiParameter(
        name="page_size",
        type=OpenApiTypes.INT,
        location=OpenApiParameter.QUERY,
        description="Number of items per page",
    ),
]

# Common responses
STANDARD_RESPONSES = {
    200: OpenApiResponse(description="Success"),
    400: OpenApiResponse(description="Bad Request"),
    401: OpenApiResponse(description="Unauthorized"),
    403: OpenApiResponse(description="Forbidden"),
    404: OpenApiResponse(description="Not Found"),
    500: OpenApiResponse(description="Internal Server Error"),
}


# Schema extensions for common operations
def list_schema(summary, description, parameters=None, responses=None):
    """Standard schema for list operations"""
    return extend_schema(
        summary=summary,
        description=description,
        parameters=(parameters or []) + PAGINATION_PARAMS,
        responses=responses or STANDARD_RESPONSES,
    )


def retrieve_schema(summary, description, responses=None):
    """Standard schema for retrieve operations"""
    return extend_schema(
        summary=summary,
        description=description,
        responses=responses or STANDARD_RESPONSES,
    )


def create_schema(summary, description, responses=None):
    """Standard schema for create operations"""
    return extend_schema(
        summary=summary,
        description=description,
        responses=responses
        or {201: OpenApiResponse(description="Created"), **STANDARD_RESPONSES},
    )


def update_schema(summary, description, responses=None):
    """Standard schema for update operations"""
    return extend_schema(
        summary=summary,
        description=description,
        responses=responses or STANDARD_RESPONSES,
    )


def delete_schema(summary, description):
    """Standard schema for delete operations"""
    return extend_schema(
        summary=summary,
        description=description,
        responses={
            204: OpenApiResponse(description="No Content"),
            **STANDARD_RESPONSES,
        },
    )


# Academic-related parameters group
ACADEMIC_PARAMS = [
    ACADEMIC_YEAR_PARAM,
    TERM_PARAM,
    SECTION_PARAM,
    GRADE_PARAM,
    CLASS_PARAM,
]
