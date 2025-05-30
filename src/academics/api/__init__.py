"""
Academics API Module

This module provides REST API functionality for the academics app,
including serializers, views, and URL configurations.

Available endpoints:
- /api/academics/departments/ - Department management
- /api/academics/academic-years/ - Academic year management
- /api/academics/terms/ - Term management
- /api/academics/sections/ - Section management
- /api/academics/grades/ - Grade management
- /api/academics/classes/ - Class management
- /api/academics/structure/ - Complete academic structure
- /api/academics/calendar/ - Academic calendar
- /api/academics/validate/ - Structure validation
"""

from .serializers import (
    AcademicYearCreateSerializer,
    AcademicYearSerializer,
    BulkClassCreateSerializer,
    ClassCreateSerializer,
    ClassSerializer,
    DepartmentSerializer,
    GradeSerializer,
    SectionHierarchySerializer,
    SectionSerializer,
    TermSerializer,
)
from .views import (
    AcademicCalendarAPIView,
    AcademicStructureAPIView,
    AcademicValidationAPIView,
    AcademicYearViewSet,
    ClassViewSet,
    DepartmentViewSet,
    GradeViewSet,
    SectionViewSet,
    TermViewSet,
)

__all__ = [
    # Serializers
    "DepartmentSerializer",
    "AcademicYearSerializer",
    "AcademicYearCreateSerializer",
    "TermSerializer",
    "SectionSerializer",
    "SectionHierarchySerializer",
    "GradeSerializer",
    "ClassSerializer",
    "ClassCreateSerializer",
    "BulkClassCreateSerializer",
    # Views
    "DepartmentViewSet",
    "AcademicYearViewSet",
    "TermViewSet",
    "SectionViewSet",
    "GradeViewSet",
    "ClassViewSet",
    "AcademicStructureAPIView",
    "AcademicCalendarAPIView",
    "AcademicValidationAPIView",
]
