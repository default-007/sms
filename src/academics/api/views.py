"""
REST API Views for Academics Module

This module provides ViewSets and APIViews for managing academic data
through the REST API, including CRUD operations and analytics endpoints.
"""

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Q
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models import AcademicYear, Class, Department, Grade, Section, Term
from ..services import (
    AcademicYearService,
    ClassService,
    GradeService,
    SectionService,
    TermService,
)
from .serializers import (
    AcademicYearCreateSerializer,
    AcademicYearSerializer,
    AcademicYearSummarySerializer,
    BulkClassCreateSerializer,
    ClassCreateSerializer,
    ClassSerializer,
    ClassSummarySerializer,
    DepartmentSerializer,
    GradeSerializer,
    GradeSummarySerializer,
    SectionHierarchySerializer,
    SectionSerializer,
    TermSerializer,
    TermSummarySerializer,
)


class DepartmentViewSet(viewsets.ModelViewSet):
    """ViewSet for Department CRUD operations"""

    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["is_active"]
    search_fields = ["name", "description"]
    ordering_fields = ["name", "creation_date"]
    ordering = ["name"]

    @action(detail=True, methods=["get"])
    def teachers(self, request, pk=None):
        """Get teachers in this department"""
        department = self.get_object()
        # This would require the teachers app to be imported
        try:
            teachers = department.teachers.filter(status="Active")
            # Return basic teacher info
            teachers_data = [
                {
                    "id": teacher.id,
                    "name": f"{teacher.user.first_name} {teacher.user.last_name}",
                    "employee_id": teacher.employee_id,
                    "specialization": teacher.specialization,
                }
                for teacher in teachers
            ]
            return Response(teachers_data)
        except AttributeError:
            return Response(
                {"detail": "Teachers relationship not available"},
                status=status.HTTP_404_NOT_FOUND,
            )

    @action(detail=True, methods=["get"])
    def subjects(self, request, pk=None):
        """Get subjects in this department"""
        department = self.get_object()
        try:
            subjects = department.subjects.filter(is_active=True)
            subjects_data = [
                {
                    "id": subject.id,
                    "name": subject.name,
                    "code": subject.code,
                    "credit_hours": subject.credit_hours,
                }
                for subject in subjects
            ]
            return Response(subjects_data)
        except AttributeError:
            return Response(
                {"detail": "Subjects relationship not available"},
                status=status.HTTP_404_NOT_FOUND,
            )


class AcademicYearViewSet(viewsets.ModelViewSet):
    """ViewSet for AcademicYear CRUD operations"""

    queryset = AcademicYear.objects.all()
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["is_current"]
    search_fields = ["name"]
    ordering_fields = ["start_date", "name"]
    ordering = ["-start_date"]

    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == "create":
            return AcademicYearCreateSerializer
        return AcademicYearSerializer

    @action(detail=False, methods=["get"])
    def current(self, request):
        """Get current academic year"""
        current_year = AcademicYearService.get_current_academic_year()
        if current_year:
            serializer = self.get_serializer(current_year)
            return Response(serializer.data)
        return Response(
            {"detail": "No current academic year found"},
            status=status.HTTP_404_NOT_FOUND,
        )

    @action(detail=True, methods=["post"])
    def set_current(self, request, pk=None):
        """Set this academic year as current"""
        try:
            academic_year = AcademicYearService.set_current_academic_year(int(pk))
            serializer = self.get_serializer(academic_year)
            return Response(serializer.data)
        except DjangoValidationError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["get"])
    def summary(self, request, pk=None):
        """Get comprehensive summary of academic year"""
        try:
            summary = AcademicYearService.get_academic_year_summary(int(pk))
            return Response(summary)
        except DjangoValidationError as e:
            return Response({"detail": str(e)}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=["post"])
    def transition_term(self, request, pk=None):
        """Transition to next term in this academic year"""
        try:
            next_term = AcademicYearService.transition_to_next_term(int(pk))
            if next_term:
                return Response(
                    {
                        "detail": f"Transitioned to {next_term.name}",
                        "current_term": TermSummarySerializer(next_term).data,
                    }
                )
            else:
                return Response(
                    {"detail": "No next term available"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        except DjangoValidationError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=["get"])
    def active(self, request):
        """Get all currently active academic years"""
        active_years = AcademicYearService.get_active_academic_years()
        serializer = AcademicYearSummarySerializer(active_years, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def upcoming(self, request):
        """Get upcoming academic years"""
        upcoming_years = AcademicYearService.get_upcoming_academic_years()
        serializer = AcademicYearSummarySerializer(upcoming_years, many=True)
        return Response(serializer.data)


class TermViewSet(viewsets.ModelViewSet):
    """ViewSet for Term CRUD operations"""

    queryset = Term.objects.all()
    serializer_class = TermSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["academic_year", "is_current", "term_number"]
    search_fields = ["name", "academic_year__name"]
    ordering_fields = ["academic_year", "term_number", "start_date"]
    ordering = ["academic_year", "term_number"]

    @action(detail=False, methods=["get"])
    def current(self, request):
        """Get current term"""
        academic_year_id = request.query_params.get("academic_year_id")
        current_term = TermService.get_current_term(academic_year_id)
        if current_term:
            serializer = self.get_serializer(current_term)
            return Response(serializer.data)
        return Response(
            {"detail": "No current term found"}, status=status.HTTP_404_NOT_FOUND
        )

    @action(detail=True, methods=["post"])
    def set_current(self, request, pk=None):
        """Set this term as current"""
        try:
            term = TermService.set_current_term(int(pk))
            serializer = self.get_serializer(term)
            return Response(serializer.data)
        except DjangoValidationError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["get"])
    def summary(self, request, pk=None):
        """Get comprehensive summary of term"""
        try:
            summary = TermService.get_term_summary(int(pk))
            return Response(summary)
        except DjangoValidationError as e:
            return Response({"detail": str(e)}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=False, methods=["get"])
    def by_academic_year(self, request):
        """Get terms by academic year"""
        academic_year_id = request.query_params.get("academic_year_id")
        if not academic_year_id:
            return Response(
                {"detail": "academic_year_id parameter required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            terms = TermService.get_terms_by_academic_year(int(academic_year_id))
            return Response(terms)
        except DjangoValidationError as e:
            return Response({"detail": str(e)}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=False, methods=["post"])
    def auto_generate(self, request):
        """Auto-generate terms for an academic year"""
        academic_year_id = request.data.get("academic_year_id")
        num_terms = request.data.get("num_terms", 3)
        term_names = request.data.get("term_names")

        if not academic_year_id:
            return Response(
                {"detail": "academic_year_id is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            terms = TermService.auto_generate_terms(
                academic_year_id=int(academic_year_id),
                num_terms=num_terms,
                term_names=term_names,
            )
            serializer = self.get_serializer(terms, many=True)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except DjangoValidationError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class SectionViewSet(viewsets.ModelViewSet):
    """ViewSet for Section CRUD operations"""

    queryset = Section.objects.all()
    serializer_class = SectionSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["is_active", "department"]
    search_fields = ["name", "description"]
    ordering_fields = ["order_sequence", "name"]
    ordering = ["order_sequence"]

    @action(detail=True, methods=["get"])
    def hierarchy(self, request, pk=None):
        """Get section hierarchy with grades and classes"""
        try:
            hierarchy = SectionService.get_section_hierarchy(int(pk))
            return Response(hierarchy)
        except DjangoValidationError as e:
            return Response({"detail": str(e)}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=["get"])
    def analytics(self, request, pk=None):
        """Get section analytics"""
        academic_year_id = request.query_params.get("academic_year_id")
        try:
            analytics = SectionService.get_section_analytics(
                int(pk),
                academic_year_id=int(academic_year_id) if academic_year_id else None,
            )
            return Response(analytics)
        except DjangoValidationError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=["post"])
    def reorder(self, request):
        """Reorder sections"""
        section_orders = request.data.get("section_orders", [])
        if not section_orders:
            return Response(
                {"detail": "section_orders is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            updated_sections = SectionService.reorder_sections(section_orders)
            serializer = self.get_serializer(updated_sections, many=True)
            return Response(serializer.data)
        except DjangoValidationError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=["get"])
    def summary(self, request):
        """Get summary of all sections"""
        summary = SectionService.get_sections_summary()
        return Response(summary)


class GradeViewSet(viewsets.ModelViewSet):
    """ViewSet for Grade CRUD operations"""

    queryset = Grade.objects.all()
    serializer_class = GradeSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["is_active", "section", "department"]
    search_fields = ["name", "section__name", "description"]
    ordering_fields = ["section", "order_sequence", "name"]
    ordering = ["section", "order_sequence"]

    @action(detail=True, methods=["get"])
    def details(self, request, pk=None):
        """Get detailed grade information"""
        academic_year_id = request.query_params.get("academic_year_id")
        try:
            details = GradeService.get_grade_details(
                int(pk),
                academic_year_id=int(academic_year_id) if academic_year_id else None,
            )
            return Response(details)
        except DjangoValidationError as e:
            return Response({"detail": str(e)}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=["get"])
    def progression_analysis(self, request, pk=None):
        """Get grade progression analysis"""
        try:
            analysis = GradeService.get_grade_progression_analysis(int(pk))
            return Response(analysis)
        except DjangoValidationError as e:
            return Response({"detail": str(e)}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=False, methods=["get"])
    def by_section(self, request):
        """Get grades by section"""
        section_id = request.query_params.get("section_id")
        include_inactive = (
            request.query_params.get("include_inactive", "false").lower() == "true"
        )

        if not section_id:
            return Response(
                {"detail": "section_id parameter required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            grades = GradeService.get_grades_by_section(
                int(section_id), include_inactive=include_inactive
            )
            return Response(grades)
        except DjangoValidationError as e:
            return Response({"detail": str(e)}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=False, methods=["post"])
    def reorder_in_section(self, request):
        """Reorder grades within a section"""
        section_id = request.data.get("section_id")
        grade_orders = request.data.get("grade_orders", [])

        if not section_id or not grade_orders:
            return Response(
                {"detail": "section_id and grade_orders are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            updated_grades = GradeService.reorder_grades_in_section(
                int(section_id), grade_orders
            )
            serializer = self.get_serializer(updated_grades, many=True)
            return Response(serializer.data)
        except DjangoValidationError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=["post"])
    def validate_student_age(self, request):
        """Validate student age for grade"""
        grade_id = request.data.get("grade_id")
        student_age = request.data.get("student_age")

        if not grade_id or student_age is None:
            return Response(
                {"detail": "grade_id and student_age are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            validation_result = GradeService.validate_student_age_for_grade(
                int(grade_id), int(student_age)
            )
            return Response(validation_result)
        except DjangoValidationError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class ClassViewSet(viewsets.ModelViewSet):
    """ViewSet for Class CRUD operations"""

    queryset = Class.objects.all()
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["is_active", "grade", "section", "academic_year"]
    search_fields = ["name", "grade__name", "section__name", "room_number"]
    ordering_fields = ["section", "grade", "name"]
    ordering = ["section", "grade", "name"]

    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == "create":
            return ClassCreateSerializer
        return ClassSerializer

    @action(detail=True, methods=["get"])
    def details(self, request, pk=None):
        """Get detailed class information"""
        try:
            details = ClassService.get_class_details(int(pk))
            return Response(details)
        except DjangoValidationError as e:
            return Response({"detail": str(e)}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=["get"])
    def analytics(self, request, pk=None):
        """Get class analytics"""
        try:
            analytics = ClassService.get_class_analytics(int(pk))
            return Response(analytics)
        except DjangoValidationError as e:
            return Response({"detail": str(e)}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=False, methods=["get"])
    def by_grade(self, request):
        """Get classes by grade"""
        grade_id = request.query_params.get("grade_id")
        academic_year_id = request.query_params.get("academic_year_id")
        include_inactive = (
            request.query_params.get("include_inactive", "false").lower() == "true"
        )

        if not grade_id:
            return Response(
                {"detail": "grade_id parameter required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            classes = ClassService.get_classes_by_grade(
                int(grade_id),
                academic_year_id=int(academic_year_id) if academic_year_id else None,
                include_inactive=include_inactive,
            )
            return Response(classes)
        except DjangoValidationError as e:
            return Response({"detail": str(e)}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=False, methods=["post"])
    def bulk_create(self, request):
        """Create multiple classes at once"""
        serializer = BulkClassCreateSerializer(data=request.data)
        if serializer.is_valid():
            try:
                classes = serializer.save()
                response_serializer = ClassSerializer(classes, many=True)
                return Response(
                    response_serializer.data, status=status.HTTP_201_CREATED
                )
            except DjangoValidationError as e:
                return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=["post"])
    def optimize_distribution(self, request):
        """Get optimization suggestions for class distribution"""
        grade_id = request.data.get("grade_id")
        academic_year_id = request.data.get("academic_year_id")

        if not grade_id or not academic_year_id:
            return Response(
                {"detail": "grade_id and academic_year_id are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            optimization = ClassService.optimize_class_distribution(
                int(grade_id), int(academic_year_id)
            )
            return Response(optimization)
        except DjangoValidationError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=["post"])
    def transfer_student(self, request):
        """Transfer student between classes"""
        student_id = request.data.get("student_id")
        from_class_id = request.data.get("from_class_id")
        to_class_id = request.data.get("to_class_id")
        reason = request.data.get("reason", "")

        if not all([student_id, from_class_id, to_class_id]):
            return Response(
                {"detail": "student_id, from_class_id, and to_class_id are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            result = ClassService.transfer_student_between_classes(
                int(student_id), int(from_class_id), int(to_class_id), reason
            )
            return Response(result)
        except DjangoValidationError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class AcademicStructureAPIView(APIView):
    """API view for academic structure operations"""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """Get complete academic structure"""
        academic_year_id = request.query_params.get("academic_year_id")

        # Get current academic year if not specified
        if not academic_year_id:
            current_year = AcademicYearService.get_current_academic_year()
            if current_year:
                academic_year_id = current_year.id
            else:
                return Response(
                    {"detail": "No academic year available"},
                    status=status.HTTP_404_NOT_FOUND,
                )

        try:
            academic_year = AcademicYear.objects.get(id=academic_year_id)
        except AcademicYear.DoesNotExist:
            return Response(
                {"detail": "Academic year not found"}, status=status.HTTP_404_NOT_FOUND
            )

        # Build complete structure
        sections = Section.objects.filter(is_active=True).order_by("order_sequence")
        structure_data = []

        for section in sections:
            section_data = {"id": section.id, "name": section.name, "grades": []}

            grades = section.get_grades()
            for grade in grades:
                grade_data = {"id": grade.id, "name": grade.name, "classes": []}

                classes = grade.get_classes(academic_year)
                for cls in classes:
                    class_data = {
                        "id": cls.id,
                        "name": cls.name,
                        "display_name": cls.display_name,
                        "capacity": cls.capacity,
                        "students_count": cls.get_students_count(),
                        "room_number": cls.room_number,
                        "class_teacher": (
                            {
                                "id": cls.class_teacher.id,
                                "name": f"{cls.class_teacher.user.first_name} {cls.class_teacher.user.last_name}",
                            }
                            if cls.class_teacher
                            else None
                        ),
                    }
                    grade_data["classes"].append(class_data)

                section_data["grades"].append(grade_data)

            structure_data.append(section_data)

        return Response(
            {
                "academic_year": {"id": academic_year.id, "name": academic_year.name},
                "structure": structure_data,
            }
        )


class AcademicCalendarAPIView(APIView):
    """API view for academic calendar"""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """Get academic calendar for an academic year"""
        academic_year_id = request.query_params.get("academic_year_id")

        if not academic_year_id:
            return Response(
                {"detail": "academic_year_id parameter required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            calendar = TermService.get_term_calendar(int(academic_year_id))
            return Response(calendar)
        except DjangoValidationError as e:
            return Response({"detail": str(e)}, status=status.HTTP_404_NOT_FOUND)


class AcademicValidationAPIView(APIView):
    """API view for academic validation"""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        """Validate academic structure"""
        validation_type = request.data.get("type")

        if validation_type == "term_structure":
            academic_year_id = request.data.get("academic_year_id")
            if not academic_year_id:
                return Response(
                    {"detail": "academic_year_id is required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            try:
                validation = TermService.validate_term_structure(int(academic_year_id))
                return Response(validation)
            except DjangoValidationError as e:
                return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        elif validation_type == "academic_year_transition":
            current_year_id = request.data.get("current_year_id")
            new_year_id = request.data.get("new_year_id")

            if not all([current_year_id, new_year_id]):
                return Response(
                    {"detail": "current_year_id and new_year_id are required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            validation = AcademicYearService.validate_academic_year_transition(
                int(current_year_id), int(new_year_id)
            )
            return Response(validation)

        else:
            return Response(
                {"detail": "Invalid validation type"},
                status=status.HTTP_400_BAD_REQUEST,
            )
