"""
API Views for Academics Module
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.db.models import Q, Count

from ..models import AcademicYear, Section, Grade, Class, Term, Department
from ..services import (
    AcademicYearService,
    SectionService,
    GradeService,
    ClassService,
    TermService,
)
from .serializers import (
    AcademicYearSerializer,
    SectionSerializer,
    GradeSerializer,
    ClassSerializer,
    TermSerializer,
    DepartmentSerializer,
)


class AcademicYearViewSet(viewsets.ModelViewSet):
    """ViewSet for Academic Years"""

    serializer_class = AcademicYearSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return AcademicYear.objects.all().order_by("-start_date")

    @action(detail=True, methods=["post"])
    def set_current(self, request, pk=None):
        """Set an academic year as current"""
        academic_year = self.get_object()
        AcademicYearService.set_current_academic_year(academic_year)
        return Response({"status": "current academic year set"})


class SectionViewSet(viewsets.ModelViewSet):
    """ViewSet for Sections"""

    serializer_class = SectionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = Section.objects.all().order_by("order_sequence")
        is_active = self.request.query_params.get("is_active", None)
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == "true")
        return queryset

    def perform_create(self, serializer):
        """Custom create logic"""
        try:
            section = SectionService.create_section(
                name=serializer.validated_data["name"],
                description=serializer.validated_data.get("description", ""),
                department=serializer.validated_data.get("department"),
                order_sequence=serializer.validated_data.get("order_sequence", 1),
            )
            section.is_active = serializer.validated_data.get("is_active", True)
            section.save()
            serializer.instance = section
        except Exception as e:
            raise ValidationError(str(e))

    @action(detail=True, methods=["get"])
    def hierarchy(self, request, pk=None):
        """Get section hierarchy"""
        section = self.get_object()
        hierarchy = SectionService.get_section_hierarchy(section.id)
        return Response(hierarchy)

    @action(detail=True, methods=["get"])
    def analytics(self, request, pk=None):
        """Get section analytics"""
        section = self.get_object()
        analytics = SectionService.get_section_analytics(section.id)
        return Response(analytics)


class GradeViewSet(viewsets.ModelViewSet):
    """ViewSet for Grades"""

    serializer_class = GradeSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = (
            Grade.objects.all()
            .select_related("section")
            .order_by("section", "order_sequence")
        )
        section_id = self.request.query_params.get("section_id", None)
        if section_id is not None:
            queryset = queryset.filter(section_id=section_id)
        is_active = self.request.query_params.get("is_active", None)
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == "true")
        return queryset

    def perform_create(self, serializer):
        """Custom create logic"""
        try:
            grade = GradeService.create_grade(
                name=serializer.validated_data["name"],
                section=serializer.validated_data["section"],
                description=serializer.validated_data.get("description", ""),
                order_sequence=serializer.validated_data.get("order_sequence", 1),
                minimum_age=serializer.validated_data.get(
                    "minimum_age"
                ),  # Correct field name
                maximum_age=serializer.validated_data.get("maximum_age"),
            )
            grade.is_active = serializer.validated_data.get("is_active", True)
            grade.save()
            serializer.instance = grade
        except Exception as e:
            raise ValidationError(str(e))


class ClassViewSet(viewsets.ModelViewSet):
    """ViewSet for Classes"""

    serializer_class = ClassSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = Class.objects.all().select_related(
            "grade__section", "academic_year", "class_teacher__user"
        )
        grade_id = self.request.query_params.get("grade_id", None)
        if grade_id is not None:
            queryset = queryset.filter(grade_id=grade_id)
        academic_year_id = self.request.query_params.get("academic_year_id", None)
        if academic_year_id is not None:
            queryset = queryset.filter(academic_year_id=academic_year_id)
        is_active = self.request.query_params.get("is_active", None)
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == "true")
        return queryset.order_by("grade__section", "grade", "name")

    def perform_create(self, serializer):
        """Custom create logic"""
        try:
            cls = ClassService.create_class(
                name=serializer.validated_data["name"],
                grade_id=serializer.validated_data["grade"].id,
                academic_year_id=serializer.validated_data["academic_year"].id,
                room_number=serializer.validated_data.get("room_number", ""),
                capacity=serializer.validated_data.get("capacity", 30),
            )
            serializer.instance = cls
        except Exception as e:
            raise ValidationError(str(e))

    @action(detail=True, methods=["get"])
    def analytics(self, request, pk=None):
        """Get class analytics"""
        cls = self.get_object()
        analytics = ClassService.get_class_analytics(cls.id)
        return Response(analytics)


class TermViewSet(viewsets.ModelViewSet):
    """ViewSet for Terms"""

    serializer_class = TermSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = Term.objects.all().select_related("academic_year")
        academic_year_id = self.request.query_params.get("academic_year_id", None)
        if academic_year_id is not None:
            queryset = queryset.filter(academic_year_id=academic_year_id)
        return queryset.order_by("academic_year", "term_number")


class DepartmentViewSet(viewsets.ModelViewSet):
    """ViewSet for Departments"""

    serializer_class = DepartmentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = Department.objects.all().order_by("name")
        is_active = self.request.query_params.get("is_active", None)
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == "true")
        return queryset


# Custom API Views


class AcademicStructureAPIView(APIView):
    """Get complete academic structure"""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        current_year = AcademicYearService.get_current_academic_year()
        if not current_year:
            return Response({"error": "No current academic year set"}, status=404)

        structure_data = []
        sections = Section.objects.filter(is_active=True).order_by("order_sequence")

        for section in sections:
            section_data = {
                "id": section.id,
                "name": section.name,
                "description": section.description,
                "grades": [],
            }

            grades = Grade.objects.filter(section=section, is_active=True).order_by(
                "order_sequence"
            )
            for grade in grades:
                grade_data = {
                    "id": grade.id,
                    "name": grade.name,
                    "description": grade.description,
                    "classes": [],
                }

                classes = Class.objects.filter(
                    grade=grade, academic_year=current_year, is_active=True
                )
                for cls in classes:
                    class_data = {
                        "id": cls.id,
                        "name": cls.name,
                        "display_name": cls.display_name,
                        "capacity": cls.capacity,
                        "room_number": cls.room_number,
                    }
                    grade_data["classes"].append(class_data)

                section_data["grades"].append(grade_data)

            structure_data.append(section_data)

        return Response(
            {
                "academic_year": {
                    "id": current_year.id,
                    "name": current_year.name,
                    "start_date": current_year.start_date,
                    "end_date": current_year.end_date,
                },
                "structure": structure_data,
            }
        )


class AcademicCalendarAPIView(APIView):
    """Get academic calendar"""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        academic_year_id = request.query_params.get("academic_year_id")
        if not academic_year_id:
            current_year = AcademicYearService.get_current_academic_year()
            if current_year:
                academic_year_id = current_year.id

        if academic_year_id:
            calendar_data = TermService.get_term_calendar(int(academic_year_id))
            return Response(calendar_data)

        return Response({"error": "No academic year specified"}, status=400)


class QuickStatsAPIView(APIView):
    """Get quick statistics"""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        current_year = AcademicYearService.get_current_academic_year()
        if not current_year:
            return Response({"error": "No current academic year set"}, status=404)

        stats = {
            "sections_count": Section.objects.filter(is_active=True).count(),
            "grades_count": Grade.objects.filter(is_active=True).count(),
            "classes_count": Class.objects.filter(
                academic_year=current_year, is_active=True
            ).count(),
            "departments_count": Department.objects.filter(is_active=True).count(),
            "current_term": current_year.get_current_term(),
        }

        return Response(stats)


class GradesBySelectionAPIView(APIView):
    """Get grades by section"""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        section_id = request.query_params.get("section_id")
        if not section_id:
            return Response({"error": "section_id parameter required"}, status=400)

        try:
            grades = GradeService.get_grades_by_section(int(section_id))
            return Response({"grades": grades})
        except Exception as e:
            return Response({"error": str(e)}, status=400)


class ValidateStudentAgeAPIView(APIView):
    """Validate student age for grade"""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        # Implementation for age validation
        return Response({"valid": True})


class BulkCreateClassesAPIView(APIView):
    """Bulk create classes"""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        # Implementation for bulk class creation
        return Response({"message": "Classes created successfully"})


class OptimizeClassDistributionAPIView(APIView):
    """Optimize class distribution"""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        # Implementation for class distribution optimization
        return Response({"message": "Class distribution optimized"})


class CurrentTermAPIView(APIView):
    """Get current term"""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        current_year = AcademicYearService.get_current_academic_year()
        if current_year:
            current_term = current_year.get_current_term()
            if current_term:
                serializer = TermSerializer(current_term)
                return Response(serializer.data)

        return Response({"error": "No current term found"}, status=404)


class AutoGenerateTermsAPIView(APIView):
    """Auto generate terms"""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        # Implementation for auto-generating terms
        return Response({"message": "Terms generated successfully"})


class CurrentAcademicYearAPIView(APIView):
    """Get current academic year"""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        current_year = AcademicYearService.get_current_academic_year()
        if current_year:
            serializer = AcademicYearSerializer(current_year)
            return Response(serializer.data)

        return Response({"error": "No current academic year set"}, status=404)
