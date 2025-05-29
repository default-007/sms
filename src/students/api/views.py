# students/api/views.py
from django.core.cache import cache
from django.db import transaction
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import generics, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from ..exceptions import handle_service_exceptions
from ..filters import ParentFilter, StudentFilter
from ..models import Parent, Student, StudentParentRelation
from ..permissions import IsParent, IsSchoolAdmin, IsTeacher
from ..services.analytics_service import StudentAnalyticsService
from ..services.parent_service import ParentService
from ..services.search_service import StudentSearchService
from ..services.student_service import StudentService
from .serializers import (
    AutocompleteSerializer,
    BulkImportResultSerializer,
    ParentDetailSerializer,
    ParentListSerializer,
    SearchResultSerializer,
    StudentAnalyticsSerializer,
    StudentDetailSerializer,
    StudentListSerializer,
    StudentParentRelationSerializer,
)


class StudentListCreateAPIView(generics.ListCreateAPIView):
    """API view for listing and creating students"""

    queryset = Student.objects.with_related().with_parents()
    permission_classes = [permissions.IsAuthenticated, IsSchoolAdmin | IsTeacher]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = StudentFilter
    search_fields = [
        "admission_number",
        "user__first_name",
        "user__last_name",
        "user__email",
    ]
    ordering_fields = ["admission_date", "user__first_name", "status"]
    ordering = ["admission_number"]

    def get_serializer_class(self):
        if self.request.method == "GET":
            return StudentListSerializer
        return StudentDetailSerializer

    @handle_service_exceptions
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class StudentRetrieveUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
    """API view for retrieving, updating, and deleting individual students"""

    queryset = Student.objects.with_related().with_parents()
    serializer_class = StudentDetailSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_permissions(self):
        if self.request.method == "GET":
            return [
                permissions.IsAuthenticated(),
                (IsSchoolAdmin() | IsTeacher() | IsParent()),
            ]
        else:
            return [permissions.IsAuthenticated(), IsSchoolAdmin()]

    def check_object_permissions(self, request, obj):
        super().check_object_permissions(request, obj)

        # Additional check for parents - they can only view their children
        if hasattr(request.user, "parent_profile"):
            if not obj.student_parent_relations.filter(
                parent=request.user.parent_profile
            ).exists():
                self.permission_denied(
                    request, message="You can only view your children's information"
                )


class ParentListCreateAPIView(generics.ListCreateAPIView):
    """API view for listing and creating parents"""

    queryset = Parent.objects.with_related().with_students()
    permission_classes = [permissions.IsAuthenticated, IsSchoolAdmin | IsTeacher]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = ParentFilter
    search_fields = ["user__first_name", "user__last_name", "user__email", "occupation"]
    ordering_fields = ["user__first_name", "relation_with_student"]
    ordering = ["user__first_name"]

    def get_serializer_class(self):
        if self.request.method == "GET":
            return ParentListSerializer
        return ParentDetailSerializer

    @handle_service_exceptions
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class ParentRetrieveUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
    """API view for retrieving, updating, and deleting individual parents"""

    queryset = Parent.objects.with_related().with_students()
    serializer_class = ParentDetailSerializer
    permission_classes = [permissions.IsAuthenticated, IsSchoolAdmin | IsTeacher]


class StudentParentRelationListCreateAPIView(generics.ListCreateAPIView):
    """API view for listing and creating student-parent relationships"""

    queryset = StudentParentRelation.objects.select_related(
        "student__user", "parent__user"
    )
    serializer_class = StudentParentRelationSerializer
    permission_classes = [permissions.IsAuthenticated, IsSchoolAdmin | IsTeacher]
    filter_backends = [DjangoFilterBackend]

    @handle_service_exceptions
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class StudentParentRelationRetrieveUpdateDestroyAPIView(
    generics.RetrieveUpdateDestroyAPIView
):
    """API view for retrieving, updating, and deleting individual relationships"""

    queryset = StudentParentRelation.objects.select_related(
        "student__user", "parent__user"
    )
    serializer_class = StudentParentRelationSerializer
    permission_classes = [permissions.IsAuthenticated, IsSchoolAdmin | IsTeacher]


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated, IsSchoolAdmin])
def bulk_import_students(request):
    """API endpoint for bulk importing students"""
    try:
        csv_file = request.FILES.get("csv_file")
        if not csv_file:
            return Response(
                {"error": "CSV file is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        send_notifications = request.data.get("send_notifications", False)
        update_existing = request.data.get("update_existing", False)

        result = StudentService.bulk_import_students(
            csv_file=csv_file,
            send_notifications=send_notifications,
            update_existing=update_existing,
            created_by=request.user,
        )

        serializer = BulkImportResultSerializer(result)
        return Response(serializer.data, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated, IsSchoolAdmin])
def bulk_import_parents(request):
    """API endpoint for bulk importing parents"""
    try:
        csv_file = request.FILES.get("csv_file")
        if not csv_file:
            return Response(
                {"error": "CSV file is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        send_notifications = request.data.get("send_notifications", False)
        update_existing = request.data.get("update_existing", False)

        result = ParentService.bulk_import_parents(
            csv_file=csv_file,
            send_notifications=send_notifications,
            update_existing=update_existing,
            created_by=request.user,
        )

        serializer = BulkImportResultSerializer(result)
        return Response(serializer.data, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def student_analytics(request):
    """API endpoint for student analytics"""
    try:
        # Check cache first
        cache_key = "student_analytics_dashboard"
        analytics_data = cache.get(cache_key)

        if analytics_data is None:
            analytics_data = StudentAnalyticsService.get_comprehensive_dashboard_data()
            cache.set(cache_key, analytics_data, 1800)  # Cache for 30 minutes

        serializer = StudentAnalyticsSerializer(analytics_data)
        return Response(serializer.data, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated, IsSchoolAdmin])
def advanced_search(request):
    """API endpoint for advanced student search"""
    try:
        search_params = request.data
        page = int(request.GET.get("page", 1))
        page_size = int(request.GET.get("page_size", 25))

        # Perform search
        queryset = StudentSearchService.advanced_search(search_params)

        # Paginate results
        start = (page - 1) * page_size
        end = start + page_size
        total_count = queryset.count()
        page_count = (total_count + page_size - 1) // page_size

        results = queryset[start:end]

        # Get analytics if requested
        analytics = None
        if request.data.get("include_analytics"):
            analytics = StudentSearchService.get_search_analytics(search_params)

        response_data = {
            "results": StudentListSerializer(results, many=True).data,
            "total_count": total_count,
            "page_count": page_count,
            "current_page": page,
            "analytics": analytics,
        }

        serializer = SearchResultSerializer(response_data)
        return Response(serializer.data, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def student_autocomplete(request):
    """API endpoint for student autocomplete"""
    try:
        query = request.GET.get("q", "")
        limit = int(request.GET.get("limit", 10))

        suggestions = StudentSearchService.get_search_suggestions(query, limit)

        serializer = AutocompleteSerializer(suggestions, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def parent_autocomplete(request):
    """API endpoint for parent autocomplete"""
    try:
        query = request.GET.get("q", "")

        parents = Parent.objects.filter(
            user__first_name__icontains=query
        ).select_related("user")[:10]

        suggestions = [
            {
                "id": str(parent.id),
                "text": f"{parent.get_full_name()} ({parent.relation_with_student})",
                "category": "Parents",
                "additional_info": {
                    "email": parent.user.email,
                    "phone": parent.user.phone_number or "",
                    "relation": parent.relation_with_student,
                },
            }
            for parent in parents
        ]

        serializer = AutocompleteSerializer(suggestions, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated, IsSchoolAdmin])
def promote_students(request):
    """API endpoint for promoting students"""
    try:
        student_ids = request.data.get("student_ids", [])
        target_class_id = request.data.get("target_class_id")
        send_notifications = request.data.get("send_notifications", False)

        if not student_ids or not target_class_id:
            return Response(
                {"error": "Student IDs and target class ID are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from src.academics.models import Class

        target_class = get_object_or_404(Class, id=target_class_id)
        students = Student.objects.filter(id__in=student_ids)

        result = StudentService.promote_students(
            students, target_class, send_notifications
        )

        return Response(result, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated, IsSchoolAdmin])
def graduate_students(request):
    """API endpoint for graduating students"""
    try:
        student_ids = request.data.get("student_ids", [])
        send_notifications = request.data.get("send_notifications", False)

        if not student_ids:
            return Response(
                {"error": "Student IDs are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        students = Student.objects.filter(id__in=student_ids)
        result = StudentService.graduate_students(students, send_notifications)

        return Response(result, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def student_family_tree(request, student_id):
    """API endpoint for student family tree"""
    try:
        student = get_object_or_404(Student, id=student_id)

        # Check permissions
        if hasattr(request.user, "parent_profile"):
            if not student.student_parent_relations.filter(
                parent=request.user.parent_profile
            ).exists():
                return Response(
                    {"error": "Permission denied"}, status=status.HTTP_403_FORBIDDEN
                )

        family_tree = {
            "student": {
                "id": str(student.id),
                "name": student.get_full_name(),
                "admission_number": student.admission_number,
                "class": str(student.current_class) if student.current_class else None,
            },
            "parents": [],
            "siblings": [],
        }

        # Get parents
        for relation in student.student_parent_relations.select_related("parent__user"):
            family_tree["parents"].append(
                {
                    "id": str(relation.parent.id),
                    "name": relation.parent.get_full_name(),
                    "relation": relation.parent.relation_with_student,
                    "is_primary": relation.is_primary_contact,
                    "phone": relation.parent.user.phone_number or "",
                    "email": relation.parent.user.email,
                }
            )

        # Get siblings
        for sibling in student.get_siblings():
            family_tree["siblings"].append(
                {
                    "id": str(sibling.id),
                    "name": sibling.get_full_name(),
                    "admission_number": sibling.admission_number,
                    "class": (
                        str(sibling.current_class) if sibling.current_class else None
                    ),
                }
            )

        return Response(family_tree, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
