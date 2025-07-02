"""
API URLs for Academics Module

This module defines all REST API endpoints for the academics app,
including ViewSet routes and custom API endpoints.
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework import permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Q
from . import views
from .views import *
from ..models import Section, Grade, Class, Department


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


# Create a router and register our viewsets with it
router = DefaultRouter()
router.register("academic-years", views.AcademicYearViewSet, basename="academicyear")
router.register("sections", views.SectionViewSet, basename="section")
router.register("grades", views.GradeViewSet, basename="grade")
router.register("classes", views.ClassViewSet, basename="class")
router.register("terms", views.TermViewSet, basename="term")
router.register("departments", views.DepartmentViewSet, basename="department")

# The API URLs are now determined automatically by the router
urlpatterns = [
    path("", include(router.urls)),
    # Additional custom endpoints
    path(
        "structure/",
        views.AcademicStructureAPIView.as_view(),
        name="academic-structure",
    ),
    path(
        "calendar/", views.AcademicCalendarAPIView.as_view(), name="academic-calendar"
    ),
    path("quick-stats/", views.QuickStatsAPIView.as_view(), name="quick-stats"),
    path(
        "grades/by_section/",
        views.GradesBySelectionAPIView.as_view(),
        name="grades-by-section",
    ),
    path(
        "grades/validate_student_age/",
        views.ValidateStudentAgeAPIView.as_view(),
        name="validate-student-age",
    ),
    path(
        "classes/bulk_create/",
        views.BulkCreateClassesAPIView.as_view(),
        name="bulk-create-classes",
    ),
    path(
        "classes/optimize_distribution/",
        views.OptimizeClassDistributionAPIView.as_view(),
        name="optimize-class-distribution",
    ),
    path("terms/current/", views.CurrentTermAPIView.as_view(), name="current-term"),
    path(
        "terms/auto_generate/",
        views.AutoGenerateTermsAPIView.as_view(),
        name="auto-generate-terms",
    ),
    path(
        "academic-years/current/",
        views.CurrentAcademicYearAPIView.as_view(),
        name="current-academic-year",
    ),
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


from django.db.models import Q

# Import statements for the additional views
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models import Class, Department, Grade, Section
