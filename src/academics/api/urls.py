"""
API URLs for Academics Module

This module defines all REST API endpoints for the academics app,
including ViewSet routes and custom API endpoints.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    DepartmentViewSet,
    AcademicYearViewSet,
    TermViewSet,
    SectionViewSet,
    GradeViewSet,
    ClassViewSet,
    AcademicStructureAPIView,
    AcademicCalendarAPIView,
    AcademicValidationAPIView,
)

# Create router and register ViewSets
router = DefaultRouter()
router.register(r"departments", DepartmentViewSet, basename="department")
router.register(r"academic-years", AcademicYearViewSet, basename="academicyear")
router.register(r"terms", TermViewSet, basename="term")
router.register(r"sections", SectionViewSet, basename="section")
router.register(r"grades", GradeViewSet, basename="grade")
router.register(r"classes", ClassViewSet, basename="class")

app_name = "academics_api"

urlpatterns = [
    # ViewSet routes
    path("", include(router.urls)),
    # Custom API endpoints
    path("structure/", AcademicStructureAPIView.as_view(), name="academic-structure"),
    path("calendar/", AcademicCalendarAPIView.as_view(), name="academic-calendar"),
    path("validate/", AcademicValidationAPIView.as_view(), name="academic-validation"),
    # Additional utility endpoints
    path("quick-stats/", QuickStatsAPIView.as_view(), name="quick-stats"),
    path("search/", SearchAPIView.as_view(), name="search"),
]


# Additional custom endpoints that could be useful
class QuickStatsAPIView(APIView):
    """Quick statistics endpoint for dashboard"""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """Get quick statistics for current academic year"""
        from ..services import AcademicYearService

        current_year = AcademicYearService.get_current_academic_year()
        if not current_year:
            return Response(
                {"detail": "No current academic year"}, status=status.HTTP_404_NOT_FOUND
            )

        # Get basic counts
        total_sections = Section.objects.filter(is_active=True).count()
        total_grades = Grade.objects.filter(is_active=True).count()
        total_classes = Class.objects.filter(
            academic_year=current_year, is_active=True
        ).count()

        # Get student count
        total_students = sum(
            cls.get_students_count()
            for cls in Class.objects.filter(academic_year=current_year, is_active=True)
        )

        # Get capacity utilization
        total_capacity = sum(
            cls.capacity
            for cls in Class.objects.filter(academic_year=current_year, is_active=True)
        )

        utilization_rate = (
            (total_students / total_capacity * 100) if total_capacity > 0 else 0
        )

        # Get current term
        current_term = current_year.get_current_term()

        return Response(
            {
                "academic_year": {"id": current_year.id, "name": current_year.name},
                "current_term": (
                    {
                        "id": current_term.id,
                        "name": current_term.name,
                        "term_number": current_term.term_number,
                    }
                    if current_term
                    else None
                ),
                "statistics": {
                    "total_sections": total_sections,
                    "total_grades": total_grades,
                    "total_classes": total_classes,
                    "total_students": total_students,
                    "total_capacity": total_capacity,
                    "utilization_rate": round(utilization_rate, 2),
                },
            }
        )


class SearchAPIView(APIView):
    """Global search endpoint for academics"""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """Search across academic entities"""
        query = request.query_params.get("q", "").strip()
        entity_type = request.query_params.get("type", "all")
        limit = min(int(request.query_params.get("limit", 10)), 50)

        if len(query) < 2:
            return Response(
                {"detail": "Query must be at least 2 characters"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        results = {
            "query": query,
            "sections": [],
            "grades": [],
            "classes": [],
            "departments": [],
        }

        if entity_type in ["all", "sections"]:
            sections = Section.objects.filter(
                Q(name__icontains=query) | Q(description__icontains=query),
                is_active=True,
            )[:limit]

            results["sections"] = [
                {
                    "id": section.id,
                    "name": section.name,
                    "description": section.description,
                    "type": "section",
                }
                for section in sections
            ]

        if entity_type in ["all", "grades"]:
            grades = Grade.objects.filter(
                Q(name__icontains=query) | Q(description__icontains=query),
                is_active=True,
            ).select_related("section")[:limit]

            results["grades"] = [
                {
                    "id": grade.id,
                    "name": grade.name,
                    "display_name": grade.display_name,
                    "section": grade.section.name,
                    "type": "grade",
                }
                for grade in grades
            ]

        if entity_type in ["all", "classes"]:
            from ..services import AcademicYearService

            current_year = AcademicYearService.get_current_academic_year()

            classes_qs = Class.objects.filter(
                Q(name__icontains=query) | Q(room_number__icontains=query),
                is_active=True,
            ).select_related("grade__section")

            if current_year:
                classes_qs = classes_qs.filter(academic_year=current_year)

            classes = classes_qs[:limit]

            results["classes"] = [
                {
                    "id": cls.id,
                    "name": cls.name,
                    "display_name": cls.display_name,
                    "full_name": cls.full_name,
                    "room_number": cls.room_number,
                    "students_count": cls.get_students_count(),
                    "type": "class",
                }
                for cls in classes
            ]

        if entity_type in ["all", "departments"]:
            departments = Department.objects.filter(
                Q(name__icontains=query) | Q(description__icontains=query),
                is_active=True,
            )[:limit]

            results["departments"] = [
                {
                    "id": dept.id,
                    "name": dept.name,
                    "description": dept.description,
                    "type": "department",
                }
                for dept in departments
            ]

        # Count total results
        total_results = sum(len(results[key]) for key in results if key != "query")
        results["total_results"] = total_results

        return Response(results)


# Import statements for the additional views
from rest_framework import permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Q
from ..models import Section, Grade, Class, Department
