# src/teachers/api/views.py
from django.db.models import Avg, Count, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from src.api.filters import TeacherFilter
from src.api.permissions import TeacherModulePermissions
from src.courses.models import AcademicYear, Department
from src.teachers.api.serializers import (
    TeacherAnalyticsSerializer,
    TeacherClassAssignmentCreateSerializer,
    TeacherClassAssignmentSerializer,
    TeacherCreateUpdateSerializer,
    TeacherDetailSerializer,
    TeacherEvaluationCreateSerializer,
    TeacherEvaluationDetailSerializer,
    TeacherEvaluationListSerializer,
    TeacherListSerializer,
    TeacherPerformanceSerializer,
    TeacherWorkloadSerializer,
)
from src.teachers.models import Teacher, TeacherClassAssignment, TeacherEvaluation
from src.teachers.services import EvaluationService, TeacherService
from src.teachers.services.analytics_service import TeacherAnalyticsService


class StandardResultsSetPagination(PageNumberPagination):
    """Standard pagination for teacher API views."""

    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class TeacherListCreateAPIView(generics.ListCreateAPIView):
    """List all teachers or create a new teacher."""

    queryset = Teacher.objects.select_related("user", "department").order_by(
        "employee_id"
    )
    permission_classes = [IsAuthenticated, TeacherModulePermissions]
    pagination_class = StandardResultsSetPagination
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_class = TeacherFilter
    search_fields = [
        "user__first_name",
        "user__last_name",
        "employee_id",
        "user__email",
    ]
    ordering_fields = [
        "employee_id",
        "joining_date",
        "experience_years",
        "user__first_name",
    ]
    ordering = ["employee_id"]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return TeacherCreateUpdateSerializer
        return TeacherListSerializer

    def get_queryset(self):
        queryset = super().get_queryset()

        # Filter by status
        status_filter = self.request.query_params.get("status", None)
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        # Filter by department
        department_id = self.request.query_params.get("department", None)
        if department_id:
            queryset = queryset.filter(department_id=department_id)

        # Filter by contract type
        contract_type = self.request.query_params.get("contract_type", None)
        if contract_type:
            queryset = queryset.filter(contract_type=contract_type)

        # Filter by experience range
        min_experience = self.request.query_params.get("min_experience", None)
        max_experience = self.request.query_params.get("max_experience", None)
        if min_experience:
            queryset = queryset.filter(experience_years__gte=min_experience)
        if max_experience:
            queryset = queryset.filter(experience_years__lte=max_experience)

        # Include evaluation stats if requested
        include_performance = (
            self.request.query_params.get("include_performance", "false").lower()
            == "true"
        )
        if include_performance:
            queryset = queryset.annotate(
                avg_evaluation_score=Avg("evaluations__score"),
                evaluation_count=Count("evaluations"),
            )

        return queryset

    def perform_create(self, serializer):
        """Perform additional actions when creating a teacher."""
        teacher = serializer.save()

        # Log the creation
        from src.core.models import AuditLog

        AuditLog.objects.create(
            user=self.request.user,
            action="CREATE",
            entity_type="Teacher",
            entity_id=teacher.id,
            data_after={
                "employee_id": teacher.employee_id,
                "name": teacher.get_full_name(),
                "department": teacher.department.name if teacher.department else None,
            },
        )


class TeacherRetrieveUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update or delete a teacher."""

    queryset = Teacher.objects.select_related("user", "department")
    permission_classes = [IsAuthenticated, TeacherModulePermissions]

    def get_serializer_class(self):
        if self.request.method in ["PUT", "PATCH"]:
            return TeacherCreateUpdateSerializer
        return TeacherDetailSerializer

    def perform_update(self, serializer):
        """Perform additional actions when updating a teacher."""
        old_data = {
            "employee_id": self.get_object().employee_id,
            "status": self.get_object().status,
            "department": (
                self.get_object().department.name
                if self.get_object().department
                else None
            ),
        }

        teacher = serializer.save()

        # Log the update
        from src.core.models import AuditLog

        AuditLog.objects.create(
            user=self.request.user,
            action="UPDATE",
            entity_type="Teacher",
            entity_id=teacher.id,
            data_before=old_data,
            data_after={
                "employee_id": teacher.employee_id,
                "status": teacher.status,
                "department": teacher.department.name if teacher.department else None,
            },
        )

    def perform_destroy(self, instance):
        """Perform additional actions when deleting a teacher."""
        # Log the deletion
        from src.core.models import AuditLog

        AuditLog.objects.create(
            user=self.request.user,
            action="DELETE",
            entity_type="Teacher",
            entity_id=instance.id,
            data_before={
                "employee_id": instance.employee_id,
                "name": instance.get_full_name(),
                "department": instance.department.name if instance.department else None,
            },
        )

        super().perform_destroy(instance)


class TeacherClassAssignmentListCreateAPIView(generics.ListCreateAPIView):
    """List or create teacher class assignments."""

    permission_classes = [IsAuthenticated, TeacherModulePermissions]
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["teacher", "academic_year", "subject", "is_class_teacher"]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return TeacherClassAssignmentCreateSerializer
        return TeacherClassAssignmentSerializer

    def get_queryset(self):
        queryset = TeacherClassAssignment.objects.select_related(
            "teacher", "teacher__user", "class_instance", "subject", "academic_year"
        )

        # Filter by teacher if provided in URL
        teacher_id = self.kwargs.get("teacher_id")
        if teacher_id:
            queryset = queryset.filter(teacher_id=teacher_id)

        # Filter by current academic year by default
        if not self.request.query_params.get("academic_year"):
            current_year = AcademicYear.objects.filter(is_current=True).first()
            if current_year:
                queryset = queryset.filter(academic_year=current_year)

        return queryset.order_by("class_instance__name", "subject__name")

    def perform_create(self, serializer):
        """Perform validation and logging when creating assignment."""
        assignment = serializer.save()

        # Log the assignment
        from src.core.models import AuditLog

        AuditLog.objects.create(
            user=self.request.user,
            action="CREATE",
            entity_type="TeacherClassAssignment",
            entity_id=assignment.id,
            data_after={
                "teacher": assignment.teacher.get_full_name(),
                "class": str(assignment.class_instance),
                "subject": assignment.subject.name,
                "is_class_teacher": assignment.is_class_teacher,
            },
        )


class TeacherClassAssignmentDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update or delete a teacher class assignment."""

    queryset = TeacherClassAssignment.objects.select_related(
        "teacher", "teacher__user", "class_instance", "subject", "academic_year"
    )
    permission_classes = [IsAuthenticated, TeacherModulePermissions]

    def get_serializer_class(self):
        if self.request.method in ["PUT", "PATCH"]:
            return TeacherClassAssignmentCreateSerializer
        return TeacherClassAssignmentSerializer


class TeacherEvaluationListCreateAPIView(generics.ListCreateAPIView):
    """List or create teacher evaluations."""

    permission_classes = [IsAuthenticated, TeacherModulePermissions]
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["teacher", "status", "evaluator"]
    ordering_fields = ["evaluation_date", "score", "created_at"]
    ordering = ["-evaluation_date"]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return TeacherEvaluationCreateSerializer
        return TeacherEvaluationListSerializer

    def get_queryset(self):
        queryset = TeacherEvaluation.objects.select_related(
            "teacher", "teacher__user", "evaluator"
        )

        # Filter by teacher if provided in URL
        teacher_id = self.kwargs.get("teacher_id")
        if teacher_id:
            queryset = queryset.filter(teacher_id=teacher_id)

        # Filter by evaluation year
        year = self.request.query_params.get("year")
        if year:
            queryset = queryset.filter(evaluation_date__year=year)

        # Filter by score range
        min_score = self.request.query_params.get("min_score")
        max_score = self.request.query_params.get("max_score")
        if min_score:
            queryset = queryset.filter(score__gte=min_score)
        if max_score:
            queryset = queryset.filter(score__lte=max_score)

        return queryset

    def perform_create(self, serializer):
        """Add evaluator and perform logging."""
        evaluation = serializer.save()

        # Create notification for teacher
        from src.communications.models import Notification

        Notification.objects.create(
            user=evaluation.teacher.user,
            title="New Performance Evaluation",
            content=f"You have received a new performance evaluation with a score of {evaluation.score}%.",
            notification_type="Evaluation",
            reference_id=evaluation.id,
            priority="High" if evaluation.score < 70 else "Medium",
        )


class TeacherEvaluationDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update or delete a teacher evaluation."""

    queryset = TeacherEvaluation.objects.select_related(
        "teacher", "teacher__user", "evaluator"
    )
    serializer_class = TeacherEvaluationDetailSerializer
    permission_classes = [IsAuthenticated, TeacherModulePermissions]


@api_view(["GET"])
@permission_classes([IsAuthenticated, TeacherModulePermissions])
def teacher_analytics_overview(request):
    """Get comprehensive teacher analytics overview."""

    # Get query parameters
    academic_year_id = request.query_params.get("academic_year")
    department_id = request.query_params.get("department")

    try:
        academic_year = None
        if academic_year_id:
            academic_year = AcademicYear.objects.get(id=academic_year_id)

        # Get performance overview
        performance_data = TeacherAnalyticsService.get_performance_overview(
            academic_year=academic_year, department_id=department_id
        )

        # Get workload analysis
        workload_data = TeacherAnalyticsService.get_workload_analysis(
            academic_year=academic_year
        )

        # Get evaluation trends
        trends_data = TeacherAnalyticsService.get_evaluation_trends(
            months=12, department_id=department_id
        )

        # Get departmental comparison
        dept_comparison = TeacherAnalyticsService.get_departmental_comparison()

        return Response(
            {
                "performance_overview": performance_data,
                "workload_analysis": workload_data,
                "evaluation_trends": trends_data,
                "departmental_comparison": dept_comparison,
            }
        )

    except AcademicYear.DoesNotExist:
        raise NotFound("Academic year not found.")
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(["GET"])
@permission_classes([IsAuthenticated, TeacherModulePermissions])
def teacher_performance_analysis(request, teacher_id):
    """Get detailed performance analysis for a specific teacher."""

    try:
        teacher = Teacher.objects.get(id=teacher_id)

        # Get months parameter
        months = int(request.query_params.get("months", 24))

        # Get growth analysis
        growth_data = TeacherAnalyticsService.get_teacher_growth_analysis(
            teacher_id=teacher_id, months=months
        )

        if not growth_data:
            return Response(
                {"error": "No evaluation data found for this teacher."},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(growth_data)

    except Teacher.DoesNotExist:
        raise NotFound("Teacher not found.")
    except ValueError:
        return Response(
            {"error": "Invalid months parameter."}, status=status.HTTP_400_BAD_REQUEST
        )


@api_view(["GET"])
@permission_classes([IsAuthenticated, TeacherModulePermissions])
def teacher_workload_analysis(request):
    """Get teacher workload analysis."""

    try:
        academic_year_id = request.query_params.get("academic_year")
        academic_year = None

        if academic_year_id:
            academic_year = AcademicYear.objects.get(id=academic_year_id)

        workload_data = TeacherAnalyticsService.get_workload_analysis(
            academic_year=academic_year
        )

        return Response(workload_data)

    except AcademicYear.DoesNotExist:
        raise NotFound("Academic year not found.")


@api_view(["GET"])
@permission_classes([IsAuthenticated, TeacherModulePermissions])
def evaluation_criteria_analysis(request):
    """Get detailed analysis of evaluation criteria."""

    try:
        department_id = request.query_params.get("department")
        year = request.query_params.get("year", timezone.now().year)

        criteria_data = TeacherAnalyticsService.get_evaluation_criteria_analysis(
            department_id=department_id, year=int(year)
        )

        return Response(
            {
                "criteria_analysis": criteria_data,
                "year": year,
                "department_id": department_id,
            }
        )

    except ValueError:
        return Response(
            {"error": "Invalid year parameter."}, status=status.HTTP_400_BAD_REQUEST
        )


@api_view(["GET"])
@permission_classes([IsAuthenticated, TeacherModulePermissions])
def teacher_dashboard_metrics(request):
    """Get key metrics for teacher dashboard."""

    try:
        academic_year_id = request.query_params.get("academic_year")
        department_id = request.query_params.get("department")

        academic_year = None
        if academic_year_id:
            academic_year = AcademicYear.objects.get(id=academic_year_id)

        metrics = TeacherAnalyticsService.get_dashboard_metrics(
            academic_year=academic_year, department_id=department_id
        )

        return Response(metrics)

    except AcademicYear.DoesNotExist:
        raise NotFound("Academic year not found.")


@api_view(["GET"])
@permission_classes([IsAuthenticated, TeacherModulePermissions])
def evaluation_trends(request):
    """Get evaluation trends over time."""

    try:
        months = int(request.query_params.get("months", 12))
        department_id = request.query_params.get("department")

        trends = TeacherAnalyticsService.get_evaluation_trends(
            months=months, department_id=department_id
        )

        return Response(trends)

    except ValueError:
        return Response(
            {"error": "Invalid months parameter."}, status=status.HTTP_400_BAD_REQUEST
        )


@api_view(["GET"])
@permission_classes([IsAuthenticated, TeacherModulePermissions])
def teacher_timetable(request, teacher_id):
    """Get teacher's timetable."""

    try:
        teacher = Teacher.objects.get(id=teacher_id)

        academic_year_id = request.query_params.get("academic_year")
        academic_year = None

        if academic_year_id:
            academic_year = AcademicYear.objects.get(id=academic_year_id)
        else:
            academic_year = AcademicYear.objects.filter(is_current=True).first()

        timetable = TeacherService.get_teacher_timetable(
            teacher=teacher, academic_year=academic_year
        )

        return Response(
            {
                "teacher": TeacherListSerializer(teacher).data,
                "academic_year": academic_year.name if academic_year else None,
                "timetable": timetable,
            }
        )

    except Teacher.DoesNotExist:
        raise NotFound("Teacher not found.")
    except AcademicYear.DoesNotExist:
        raise NotFound("Academic year not found.")


@api_view(["GET"])
@permission_classes([IsAuthenticated, TeacherModulePermissions])
def teacher_student_correlation(request):
    """Get correlation between teacher performance and student outcomes."""

    try:
        academic_year_id = request.query_params.get("academic_year")
        academic_year = None

        if academic_year_id:
            academic_year = AcademicYear.objects.get(id=academic_year_id)

        correlation_data = TeacherAnalyticsService.get_student_performance_correlation(
            academic_year=academic_year
        )

        return Response(
            {
                "correlations": correlation_data,
                "academic_year": academic_year.name if academic_year else None,
            }
        )

    except AcademicYear.DoesNotExist:
        raise NotFound("Academic year not found.")


@api_view(["GET"])
@permission_classes([IsAuthenticated, TeacherModulePermissions])
def retention_analysis(request):
    """Get teacher retention analysis."""

    retention_data = TeacherAnalyticsService.get_retention_analysis()
    return Response(retention_data)


@api_view(["GET"])
@permission_classes([IsAuthenticated, TeacherModulePermissions])
def hiring_analysis(request):
    """Get teacher hiring analysis."""

    hiring_data = TeacherAnalyticsService.get_hiring_analysis()
    return Response(hiring_data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def teacher_profile(request):
    """Get current user's teacher profile if they are a teacher."""

    try:
        teacher = request.user.teacher_profile
        serializer = TeacherDetailSerializer(teacher)
        return Response(serializer.data)
    except AttributeError:
        return Response(
            {"error": "User is not a teacher."}, status=status.HTTP_404_NOT_FOUND
        )


@api_view(["PUT", "PATCH"])
@permission_classes([IsAuthenticated])
def update_teacher_profile(request):
    """Update current user's teacher profile."""

    try:
        teacher = request.user.teacher_profile

        # Teachers can only update certain fields
        allowed_fields = ["bio", "emergency_contact", "emergency_phone"]

        # Filter the data to only include allowed fields
        filtered_data = {k: v for k, v in request.data.items() if k in allowed_fields}

        serializer = TeacherCreateUpdateSerializer(
            teacher, data=filtered_data, partial=True
        )

        if serializer.is_valid():
            serializer.save()
            return Response(TeacherDetailSerializer(teacher).data)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    except AttributeError:
        return Response(
            {"error": "User is not a teacher."}, status=status.HTTP_404_NOT_FOUND
        )


@api_view(["POST"])
@permission_classes([IsAuthenticated, TeacherModulePermissions])
def bulk_assign_teachers(request):
    """Bulk assign teachers to classes and subjects."""

    assignments_data = request.data.get("assignments", [])

    if not assignments_data:
        return Response(
            {"error": "No assignments provided."}, status=status.HTTP_400_BAD_REQUEST
        )

    created_assignments = []
    errors = []

    for assignment_data in assignments_data:
        serializer = TeacherClassAssignmentCreateSerializer(data=assignment_data)

        if serializer.is_valid():
            assignment = serializer.save()
            created_assignments.append(
                TeacherClassAssignmentSerializer(assignment).data
            )
        else:
            errors.append({"data": assignment_data, "errors": serializer.errors})

    return Response(
        {
            "created": created_assignments,
            "errors": errors,
            "success_count": len(created_assignments),
            "error_count": len(errors),
        }
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated, TeacherModulePermissions])
def teacher_search(request):
    """Advanced teacher search with multiple criteria."""

    query = request.query_params.get("q", "")
    department_id = request.query_params.get("department")
    status_filter = request.query_params.get("status", "Active")
    min_experience = request.query_params.get("min_experience")
    max_experience = request.query_params.get("max_experience")

    teachers = Teacher.objects.select_related("user", "department")

    # Apply filters
    if query:
        teachers = teachers.filter(
            Q(user__first_name__icontains=query)
            | Q(user__last_name__icontains=query)
            | Q(employee_id__icontains=query)
            | Q(user__email__icontains=query)
            | Q(specialization__icontains=query)
        )

    if department_id:
        teachers = teachers.filter(department_id=department_id)

    if status_filter:
        teachers = teachers.filter(status=status_filter)

    if min_experience:
        teachers = teachers.filter(experience_years__gte=min_experience)

    if max_experience:
        teachers = teachers.filter(experience_years__lte=max_experience)

    # Limit results for performance
    teachers = teachers[:50]

    serializer = TeacherListSerializer(teachers, many=True)
    return Response({"teachers": serializer.data, "count": len(serializer.data)})
