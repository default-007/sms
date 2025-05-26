"""
Academics Services Module

This module provides all business logic services for the academics app.

Services included:
- AcademicYearService: Academic year and term management
- SectionService: Section hierarchy management
- GradeService: Grade management within sections
- ClassService: Class management and student enrollment
- TermService: Term scheduling and transitions

Usage:
    from academics.services import AcademicYearService, SectionService

    # Create new academic year
    academic_year = AcademicYearService.create_academic_year(
        name="2024-2025",
        start_date=datetime(2024, 4, 1),
        end_date=datetime(2025, 3, 31),
        user=request.user,
        is_current=True
    )

    # Get section hierarchy
    hierarchy = SectionService.get_section_hierarchy(section_id=1)
"""

from .academic_year_service import AcademicYearService
from .section_service import SectionService
from .grade_service import GradeService
from .class_service import ClassService
from .term_service import TermService

__all__ = [
    "AcademicYearService",
    "SectionService",
    "GradeService",
    "ClassService",
    "TermService",
]

# Service registry for dynamic access
SERVICE_REGISTRY = {
    "academic_year": AcademicYearService,
    "section": SectionService,
    "grade": GradeService,
    "class": ClassService,
    "term": TermService,
}


def get_service(service_name: str):
    """
    Get a service by name from the registry

    Args:
        service_name: Name of the service to retrieve

    Returns:
        Service class

    Raises:
        KeyError: If service name not found
    """
    if service_name not in SERVICE_REGISTRY:
        raise KeyError(
            f"Service '{service_name}' not found. Available services: {list(SERVICE_REGISTRY.keys())}"
        )

    return SERVICE_REGISTRY[service_name]
