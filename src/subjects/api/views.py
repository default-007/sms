from rest_framework import generics, status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext_lazy as _

from ..models import Subject, Syllabus, TopicProgress, SubjectAssignment
from ..services import SyllabusService, CurriculumService
from .serializers import (
    SubjectListSerializer,
    SubjectDetailSerializer,
    SubjectCreateUpdateSerializer,
    SyllabusListSerializer,
    SyllabusDetailSerializer,
    SyllabusCreateUpdateSerializer,
    TopicProgressSerializer,
    SubjectAssignmentSerializer,
    BulkSubjectCreateSerializer,
    SyllabusProgressUpdateSerializer,
    CurriculumAnalyticsSerializer,
    TeacherWorkloadSerializer,
)


class StandardResultsSetPagination(PageNumberPagination):
    """Standard pagination for list views."""

    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class SubjectFilter:
    """Custom filter class for subjects."""

    @staticmethod
    def filter_by_grade(queryset, grade_id):
        """Filter subjects applicable for a specific grade."""
        return queryset.filter(
            Q(grade_level__contains=[int(grade_id)]) | Q(grade_level=[])
        )

    @staticmethod
    def filter_by_department(queryset, department_id):
        """Filter subjects by department."""
        return queryset.filter(department_id=department_id)


class SubjectListCreateAPIView(generics.ListCreateAPIView):
    """
    API view for listing and creating subjects.

    GET: List all subjects with filtering and search
    POST: Create a new subject
    """

    queryset = Subject.objects.filter(is_active=True)
    pagination_class = StandardResultsSetPagination
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["department", "is_elective", "credit_hours"]
    search_fields = ["name", "code", "description"]
    ordering_fields = ["name", "code", "department__name", "created_at"]
    ordering = ["department__name", "name"]
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.request.method == "POST":
            return SubjectCreateUpdateSerializer
        return SubjectListSerializer

    def get_queryset(self):
        """Filter queryset based on query parameters."""
        queryset = super().get_queryset().select_related("department")

        # Filter by grade if provided
        grade_id = self.request.query_params.get("grade")
        if grade_id:
            queryset = SubjectFilter.filter_by_grade(queryset, grade_id)

        # Filter by department if provided
        department_id = self.request.query_params.get("department_id")
        if department_id:
            queryset = SubjectFilter.filter_by_department(queryset, department_id)

        return queryset

    def perform_create(self, serializer):
        """Set additional fields when creating a subject."""
        serializer.save()


class SubjectDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    """
    API view for retrieving, updating, and deleting subjects.

    GET: Retrieve subject details
    PUT/PATCH: Update subject
    DELETE: Soft delete subject (set is_active=False)
    """

    queryset = Subject.objects.filter(is_active=True)
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.request.method in ["PUT", "PATCH"]:
            return SubjectCreateUpdateSerializer
        return SubjectDetailSerializer

    def get_object(self):
        """Get subject with related data."""
        return get_object_or_404(
            Subject.objects.select_related("department"),
            pk=self.kwargs["pk"],
            is_active=True,
        )

    def perform_destroy(self, instance):
        """Soft delete the subject."""
        instance.is_active = False
        instance.save()


class SyllabusListCreateAPIView(generics.ListCreateAPIView):
    """
    API view for listing and creating syllabi.

    GET: List syllabi with filtering
    POST: Create a new syllabus
    """

    queryset = Syllabus.objects.filter(is_active=True)
    pagination_class = StandardResultsSetPagination
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["subject", "grade", "academic_year", "term", "difficulty_level"]
    search_fields = ["title", "description", "subject__name", "subject__code"]
    ordering_fields = [
        "title",
        "completion_percentage",
        "created_at",
        "last_updated_at",
    ]
    ordering = ["academic_year", "term__term_number", "subject__name"]
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.request.method == "POST":
            return SyllabusCreateUpdateSerializer
        return SyllabusListSerializer

    def get_queryset(self):
        """Filter queryset based on query parameters."""
        queryset = (
            super()
            .get_queryset()
            .select_related("subject", "grade", "academic_year", "term", "created_by")
        )

        # Filter by teacher assignments if teacher_id provided
        teacher_id = self.request.query_params.get("teacher_id")
        if teacher_id:
            assignment_filters = {"teacher_id": teacher_id, "is_active": True}

            # Add academic year and term filters if provided
            academic_year = self.request.query_params.get("academic_year")
            term = self.request.query_params.get("term")

            if academic_year:
                assignment_filters["academic_year_id"] = academic_year
            if term:
                assignment_filters["term_id"] = term

            assignments = SubjectAssignment.objects.filter(**assignment_filters)

            # Get unique combinations of subject, grade, academic_year, term
            assignment_filters_list = []
            for assignment in assignments:
                assignment_filters_list.append(
                    Q(subject=assignment.subject)
                    & Q(grade=assignment.class_assigned.grade)
                    & Q(academic_year=assignment.academic_year)
                    & Q(term=assignment.term)
                )

            if assignment_filters_list:
                from functools import reduce
                import operator

                combined_filter = reduce(operator.or_, assignment_filters_list)
                queryset = queryset.filter(combined_filter)
            else:
                queryset = queryset.none()

        return queryset

    def perform_create(self, serializer):
        """Set additional fields when creating a syllabus."""
        serializer.save(created_by=self.request.user, last_updated_by=self.request.user)


class SyllabusDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    """
    API view for retrieving, updating, and deleting syllabi.

    GET: Retrieve syllabus details with full content
    PUT/PATCH: Update syllabus
    DELETE: Soft delete syllabus
    """

    queryset = Syllabus.objects.filter(is_active=True)
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.request.method in ["PUT", "PATCH"]:
            return SyllabusCreateUpdateSerializer
        return SyllabusDetailSerializer

    def get_object(self):
        """Get syllabus with related data."""
        return get_object_or_404(
            Syllabus.objects.select_related(
                "subject",
                "grade",
                "academic_year",
                "term",
                "created_by",
                "last_updated_by",
            ).prefetch_related("topic_progress"),
            pk=self.kwargs["pk"],
            is_active=True,
        )

    def perform_update(self, serializer):
        """Set last updated by when updating."""
        serializer.save(last_updated_by=self.request.user)

    def perform_destroy(self, instance):
        """Soft delete the syllabus."""
        instance.is_active = False
        instance.save()


class TopicProgressListCreateAPIView(generics.ListCreateAPIView):
    """
    API view for listing and creating topic progress entries.

    GET: List topic progress for a syllabus
    POST: Create new topic progress entry
    """

    serializer_class = TopicProgressSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ["topic_index", "completion_date", "created_at"]
    ordering = ["topic_index"]

    def get_queryset(self):
        """Filter by syllabus if provided."""
        queryset = TopicProgress.objects.all()

        syllabus_id = self.request.query_params.get("syllabus_id")
        if syllabus_id:
            queryset = queryset.filter(syllabus_id=syllabus_id)

        return queryset.select_related("syllabus")


class TopicProgressDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    """
    API view for retrieving, updating, and deleting topic progress.

    GET: Retrieve topic progress details
    PUT/PATCH: Update topic progress
    DELETE: Delete topic progress entry
    """

    queryset = TopicProgress.objects.all()
    serializer_class = TopicProgressSerializer
    permission_classes = [permissions.IsAuthenticated]


class SubjectAssignmentListCreateAPIView(generics.ListCreateAPIView):
    """
    API view for listing and creating subject assignments.

    GET: List subject assignments with filtering
    POST: Create new subject assignment
    """

    queryset = SubjectAssignment.objects.filter(is_active=True)
    serializer_class = SubjectAssignmentSerializer
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = [
        "teacher",
        "subject",
        "class_assigned",
        "academic_year",
        "term",
        "is_primary_teacher",
    ]
    ordering_fields = ["assigned_date", "teacher__user__last_name", "subject__name"]
    ordering = ["academic_year", "term__term_number", "teacher__user__last_name"]
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Filter queryset with related data."""
        return (
            super()
            .get_queryset()
            .select_related(
                "subject",
                "teacher__user",
                "class_assigned",
                "academic_year",
                "term",
                "assigned_by",
            )
        )

    def perform_create(self, serializer):
        """Set assigned_by when creating assignment."""
        serializer.save(assigned_by=self.request.user)


class SubjectAssignmentDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    """
    API view for retrieving, updating, and deleting subject assignments.
    """

    queryset = SubjectAssignment.objects.filter(is_active=True)
    serializer_class = SubjectAssignmentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_destroy(self, instance):
        """Soft delete the assignment."""
        instance.is_active = False
        instance.save()


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def bulk_create_subjects(request):
    """
    Bulk create subjects from uploaded data.

    POST: Create multiple subjects at once
    """
    serializer = BulkSubjectCreateSerializer(data=request.data)
    if serializer.is_valid():
        department = serializer.validated_data["department"]
        subjects_data = serializer.validated_data["subjects_data"]

        try:
            created_subjects, errors = CurriculumService.bulk_import_subjects(
                subjects_data, department.id
            )

            response_data = {
                "created_count": len(created_subjects),
                "error_count": len(errors),
                "errors": errors,
                "created_subjects": SubjectListSerializer(
                    created_subjects, many=True
                ).data,
            }

            if errors:
                return Response(response_data, status=status.HTTP_206_PARTIAL_CONTENT)
            else:
                return Response(response_data, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response(
                {"error": _("Failed to create subjects: {}").format(str(e))},
                status=status.HTTP_400_BAD_REQUEST,
            )

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def mark_topic_completed(request, syllabus_id):
    """
    Mark a specific topic as completed in a syllabus.

    POST: Mark topic as completed with optional completion data
    """
    try:
        syllabus = Syllabus.objects.get(id=syllabus_id, is_active=True)
    except Syllabus.DoesNotExist:
        return Response(
            {"error": _("Syllabus not found")}, status=status.HTTP_404_NOT_FOUND
        )

    serializer = SyllabusProgressUpdateSerializer(
        data=request.data, context={"syllabus": syllabus}
    )

    if serializer.is_valid():
        topic_index = serializer.validated_data["topic_index"]
        completion_data = serializer.validated_data.get("completion_data", {})

        try:
            topic_progress = SyllabusService.mark_topic_completed(
                syllabus_id, topic_index, completion_data
            )

            response_data = {
                "message": _("Topic marked as completed successfully"),
                "topic_progress": TopicProgressSerializer(topic_progress).data,
                "syllabus_completion": syllabus.completion_percentage,
            }

            return Response(response_data, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {"error": _("Failed to mark topic as completed: {}").format(str(e))},
                status=status.HTTP_400_BAD_REQUEST,
            )

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def syllabus_progress(request, syllabus_id):
    """
    Get detailed progress information for a syllabus.

    GET: Retrieve comprehensive progress data
    """
    try:
        progress_data = SyllabusService.get_syllabus_progress(syllabus_id)
        return Response(progress_data, status=status.HTTP_200_OK)
    except Exception as e:
        return Response(
            {"error": _("Failed to get progress data: {}").format(str(e))},
            status=status.HTTP_400_BAD_REQUEST,
        )


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def grade_syllabus_overview(request, grade_id):
    """
    Get overview of all syllabi for a specific grade.

    GET: Retrieve grade-level syllabus overview
    """
    academic_year_id = request.query_params.get("academic_year_id")
    term_id = request.query_params.get("term_id")

    if not academic_year_id:
        return Response(
            {"error": _("academic_year_id parameter is required")},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        overview_data = SyllabusService.get_grade_syllabus_overview(
            grade_id, academic_year_id, term_id
        )
        return Response(overview_data, status=status.HTTP_200_OK)
    except Exception as e:
        return Response(
            {"error": _("Failed to get grade overview: {}").format(str(e))},
            status=status.HTTP_400_BAD_REQUEST,
        )


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def teacher_assignments(request, teacher_id):
    """
    Get all syllabus assignments for a specific teacher.

    GET: Retrieve teacher's subject assignments and syllabi
    """
    academic_year_id = request.query_params.get("academic_year_id")
    term_id = request.query_params.get("term_id")

    if not academic_year_id:
        return Response(
            {"error": _("academic_year_id parameter is required")},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        assignments_data = SyllabusService.get_teacher_syllabus_assignments(
            teacher_id, academic_year_id, term_id
        )
        return Response(assignments_data, status=status.HTTP_200_OK)
    except Exception as e:
        return Response(
            {"error": _("Failed to get teacher assignments: {}").format(str(e))},
            status=status.HTTP_400_BAD_REQUEST,
        )


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def teacher_workload(request, teacher_id):
    """
    Get teacher workload information.

    GET: Retrieve comprehensive workload data
    """
    academic_year_id = request.query_params.get("academic_year_id")
    term_id = request.query_params.get("term_id")

    if not academic_year_id:
        return Response(
            {"error": _("academic_year_id parameter is required")},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        workload_data = CurriculumService.get_teacher_workload(
            teacher_id, academic_year_id, term_id
        )

        serializer = TeacherWorkloadSerializer(workload_data)
        return Response(serializer.data, status=status.HTTP_200_OK)
    except Exception as e:
        return Response(
            {"error": _("Failed to get teacher workload: {}").format(str(e))},
            status=status.HTTP_400_BAD_REQUEST,
        )


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def curriculum_analytics(request):
    """
    Get comprehensive curriculum analytics.

    GET: Retrieve curriculum analytics data
    """
    academic_year_id = request.query_params.get("academic_year_id")
    grade_id = request.query_params.get("grade_id")
    department_id = request.query_params.get("department_id")

    if not academic_year_id:
        return Response(
            {"error": _("academic_year_id parameter is required")},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        analytics_data = CurriculumService.get_curriculum_analytics(
            academic_year_id, grade_id, department_id
        )

        serializer = CurriculumAnalyticsSerializer(analytics_data)
        return Response(serializer.data, status=status.HTTP_200_OK)
    except Exception as e:
        return Response(
            {"error": _("Failed to get curriculum analytics: {}").format(str(e))},
            status=status.HTTP_400_BAD_REQUEST,
        )


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def curriculum_structure(request):
    """
    Get comprehensive curriculum structure.

    GET: Retrieve organized curriculum structure
    """
    academic_year_id = request.query_params.get("academic_year_id")
    grade_id = request.query_params.get("grade_id")
    department_id = request.query_params.get("department_id")

    if not academic_year_id:
        return Response(
            {"error": _("academic_year_id parameter is required")},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        structure_data = CurriculumService.get_curriculum_structure(
            academic_year_id, grade_id, department_id
        )
        return Response(structure_data, status=status.HTTP_200_OK)
    except Exception as e:
        return Response(
            {"error": _("Failed to get curriculum structure: {}").format(str(e))},
            status=status.HTTP_400_BAD_REQUEST,
        )


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def bulk_create_syllabi(request, term_id):
    """
    Bulk create syllabi for all subjects in a term.

    POST: Create syllabi for all subject assignments in a term
    """
    template_data = request.data.get("template_data", {})

    try:
        created_syllabi = SyllabusService.bulk_create_syllabi_for_term(
            term_id, template_data, request.user.id
        )

        response_data = {
            "created_count": len(created_syllabi),
            "created_syllabi": SyllabusListSerializer(created_syllabi, many=True).data,
        }

        return Response(response_data, status=status.HTTP_201_CREATED)

    except Exception as e:
        return Response(
            {"error": _("Failed to create syllabi: {}").format(str(e))},
            status=status.HTTP_400_BAD_REQUEST,
        )


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def subjects_by_grade(request, grade_id):
    """
    Get all subjects applicable for a specific grade.

    GET: Retrieve subjects filtered by grade applicability
    """
    department_id = request.query_params.get("department_id")
    include_electives = (
        request.query_params.get("include_electives", "true").lower() == "true"
    )

    try:
        subjects = CurriculumService.get_subjects_by_grade(
            grade_id, department_id, include_electives
        )

        serializer = SubjectListSerializer(subjects, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    except Exception as e:
        return Response(
            {"error": _("Failed to get subjects: {}").format(str(e))},
            status=status.HTTP_400_BAD_REQUEST,
        )
