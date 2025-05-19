from rest_framework import viewsets, generics, status, permissions, filters
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db.models import Q, Count
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.contrib.auth import get_user_model
from django.db import models
from django.shortcuts import get_object_or_404

from .serializers import (
    UserSerializer,
    UserCreateSerializer,
    UserUpdateSerializer,
    UserRoleSerializer,
    UserRoleAssignmentSerializer,
    PasswordChangeSerializer,
    UserStatsSerializer,
    UserBulkActionSerializer,
    StudentSerializer,
    ParentSerializer,
    StudentParentRelationSerializer,
    TeacherSerializer,
    TeacherClassAssignmentSerializer,
    TeacherEvaluationSerializer,
    DepartmentSerializer,
    AcademicYearSerializer,
    GradeSerializer,
    SectionSerializer,
    ClassSerializer,
    SubjectSerializer,
    SyllabusSerializer,
    TimeSlotSerializer,
    TimetableSerializer,
    AssignmentSerializer,
    AssignmentSubmissionSerializer,
    SystemSettingSerializer,
    DocumentSerializer,
)
from .permissions import HasAPIAccess, HasResourcePermission
from .pagination import StandardResultsSetPagination
from .filters import (
    UserFilter,
    StudentFilter,
    ParentFilter,
    TeacherFilter,
    ClassFilter,
    AssignmentFilter,
)
from .utils import api_response, get_current_academic_year
from .authentication import DefaultAuthentication

from src.accounts.models import UserRole, UserRoleAssignment, UserAuditLog
from src.accounts.permissions import IsAdmin, CanManageUsers
from src.students.models import Student, Parent, StudentParentRelation
from src.teachers.models import Teacher, TeacherClassAssignment, TeacherEvaluation
from src.courses.models import (
    Department,
    AcademicYear,
    Grade,
    Section,
    Class,
    Subject,
    Syllabus,
    TimeSlot,
    Timetable,
    Assignment,
    AssignmentSubmission,
)
from src.core.models import SystemSetting, Document
from src.accounts.services.role_service import RoleService

User = get_user_model()


class UserListCreateAPIView(generics.ListCreateAPIView):
    """API view for listing and creating users."""

    queryset = User.objects.all()
    permission_classes = [permissions.IsAuthenticated, CanManageUsers]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ["username", "email", "first_name", "last_name"]
    filterset_fields = ["is_active", "gender", "role_assignments__role__name"]
    ordering_fields = ["username", "email", "date_joined", "last_login"]
    ordering = ["-date_joined"]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return UserCreateSerializer
        return UserSerializer

    def get_queryset(self):
        """Optimize queryset with prefetch."""
        return User.objects.select_related("profile").prefetch_related(
            "role_assignments__role"
        )


class UserRetrieveUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
    """API view for retrieving, updating, and deleting users."""

    queryset = User.objects.all()
    permission_classes = [permissions.IsAuthenticated, CanManageUsers]

    def get_serializer_class(self):
        if self.request.method in ["PUT", "PATCH"]:
            return UserUpdateSerializer
        return UserSerializer

    def get_queryset(self):
        """Optimize queryset with prefetch."""
        return User.objects.select_related("profile").prefetch_related(
            "role_assignments__role"
        )

    def perform_destroy(self, instance):
        """Soft delete user instead of hard delete."""
        instance.is_active = False
        instance.save()

        # Create audit log
        UserAuditLog.objects.create(
            user=instance,
            action="delete",
            description=f"User deactivated",
            performed_by=self.request.user,
        )


class UserRoleListCreateAPIView(generics.ListCreateAPIView):
    """API view for listing and creating user roles."""

    queryset = UserRole.objects.all()
    serializer_class = UserRoleSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdmin]
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ["name", "description"]
    ordering_fields = ["name", "created_at"]
    ordering = ["name"]


class UserRoleRetrieveUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
    """API view for retrieving, updating, and deleting user roles."""

    queryset = UserRole.objects.all()
    serializer_class = UserRoleSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdmin]

    def perform_destroy(self, instance):
        """Prevent deletion of system roles."""
        if instance.is_system_role:
            raise ValidationError("Cannot delete system roles.")
        super().perform_destroy(instance)


class UserRoleAssignmentListAPIView(generics.ListAPIView):
    """API view for listing user role assignments."""

    serializer_class = UserRoleAssignmentSerializer
    permission_classes = [permissions.IsAuthenticated, CanManageUsers]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["user", "role", "is_active"]
    ordering_fields = ["assigned_date", "expires_at"]
    ordering = ["-assigned_date"]

    def get_queryset(self):
        return UserRoleAssignment.objects.select_related("user", "role", "assigned_by")


class AssignRoleAPIView(APIView):
    """API view for assigning roles to users."""

    permission_classes = [permissions.IsAuthenticated, CanManageUsers]

    def post(self, request):
        user_id = request.data.get("user_id")
        role_name = request.data.get("role_name")
        expires_at = request.data.get("expires_at")
        notes = request.data.get("notes", "")

        try:
            user = User.objects.get(id=user_id)
            assignment, created = RoleService.assign_role_to_user(
                user=user,
                role_name=role_name,
                assigned_by=request.user,
                expires_at=expires_at,
                notes=notes,
            )

            serializer = UserRoleAssignmentSerializer(assignment)

            if created:
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            else:
                return Response(
                    {"detail": "Role already assigned to user"},
                    status=status.HTTP_200_OK,
                )
        except User.DoesNotExist:
            return Response(
                {"error": "User not found"}, status=status.HTTP_404_NOT_FOUND
            )
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class RemoveRoleAPIView(APIView):
    """API view for removing roles from users."""

    permission_classes = [permissions.IsAuthenticated, CanManageUsers]

    def post(self, request):
        user_id = request.data.get("user_id")
        role_name = request.data.get("role_name")

        try:
            user = User.objects.get(id=user_id)
            removed = RoleService.remove_role_from_user(
                user=user, role_name=role_name, removed_by=request.user
            )

            if removed:
                return Response(
                    {"detail": "Role removed successfully"}, status=status.HTTP_200_OK
                )
            else:
                return Response(
                    {"detail": "Role was not assigned to user"},
                    status=status.HTTP_200_OK,
                )
        except User.DoesNotExist:
            return Response(
                {"error": "User not found"}, status=status.HTTP_404_NOT_FOUND
            )


class PasswordChangeAPIView(APIView):
    """API view for changing user password."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = PasswordChangeSerializer(
            data=request.data, context={"request": request}
        )

        if serializer.is_valid():
            serializer.save()

            # Create audit log
            UserAuditLog.objects.create(
                user=request.user,
                action="password_change",
                description="Password changed via API",
                performed_by=request.user,
            )

            return Response(
                {"detail": "Password changed successfully"}, status=status.HTTP_200_OK
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UserStatsAPIView(APIView):
    """API view for user statistics."""

    permission_classes = [permissions.IsAuthenticated, IsAdmin]

    def get(self, request):
        # Calculate statistics
        total_users = User.objects.count()
        active_users = User.objects.filter(is_active=True).count()
        inactive_users = total_users - active_users

        # Users by role
        users_by_role = {}
        role_counts = (
            UserRoleAssignment.objects.filter(is_active=True)
            .values("role__name")
            .annotate(count=Count("user"))
            .order_by("role__name")
        )

        for item in role_counts:
            users_by_role[item["role__name"]] = item["count"]

        # Recent registrations (last 30 days)
        thirty_days_ago = timezone.now() - timezone.timedelta(days=30)
        recent_registrations = User.objects.filter(
            date_joined__gte=thirty_days_ago
        ).count()

        # Users requiring password change
        users_requiring_password_change = User.objects.filter(
            requires_password_change=True, is_active=True
        ).count()

        stats_data = {
            "total_users": total_users,
            "active_users": active_users,
            "inactive_users": inactive_users,
            "users_by_role": users_by_role,
            "recent_registrations": recent_registrations,
            "users_requiring_password_change": users_requiring_password_change,
        }

        serializer = UserStatsSerializer(stats_data)
        return Response(serializer.data)


class UserBulkActionAPIView(APIView):
    """API view for bulk user actions."""

    permission_classes = [permissions.IsAuthenticated, IsAdmin]

    def post(self, request):
        serializer = UserBulkActionSerializer(data=request.data)

        if serializer.is_valid():
            user_ids = serializer.validated_data["user_ids"]
            action = serializer.validated_data["action"]
            roles = serializer.validated_data.get("roles", [])

            users = User.objects.filter(id__in=user_ids)
            affected_count = 0

            with transaction.atomic():
                if action == "activate":
                    affected_count = users.update(is_active=True)

                elif action == "deactivate":
                    affected_count = users.update(is_active=False)

                elif action == "require_password_change":
                    affected_count = users.update(requires_password_change=True)

                elif action == "assign_roles":
                    for user in users:
                        for role_name in roles:
                            RoleService.assign_role_to_user(
                                user, role_name, assigned_by=request.user
                            )
                    affected_count = len(users)

                elif action == "remove_roles":
                    for user in users:
                        for role_name in roles:
                            RoleService.remove_role_from_user(
                                user, role_name, removed_by=request.user
                            )
                    affected_count = len(users)

                # Create audit logs
                for user in users:
                    UserAuditLog.objects.create(
                        user=user,
                        action=action,
                        description=f"Bulk action: {action}",
                        performed_by=request.user,
                        extra_data={"roles": roles} if roles else {},
                    )

            return Response(
                {
                    "detail": f'{action.replace("_", " ").title()} applied to {affected_count} users'
                }
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class MyProfileAPIView(generics.RetrieveUpdateAPIView):
    """API view for user's own profile."""

    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def user_permissions_view(request):
    """Get current user's permissions."""
    permissions = request.user.get_permissions()
    return Response({"permissions": permissions})


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated, IsAdmin])
def expire_role_assignments_view(request):
    """Manually trigger expiration of role assignments."""
    expired_count = RoleService.expire_role_assignments()
    return Response({"detail": f"{expired_count} role assignments have been expired"})


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated, IsAdmin])
def role_statistics_view(request):
    """Get role statistics."""
    stats = RoleService.get_role_statistics()
    return Response({"role_statistics": stats})


class StudentViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing students.
    """

    queryset = Student.objects.all()
    serializer_class = StudentSerializer
    pagination_class = StandardResultsSetPagination
    permission_classes = [IsAuthenticated, HasResourcePermission]
    authentication_classes = DefaultAuthentication.authentication_classes
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_class = StudentFilter
    search_fields = [
        "admission_number",
        "user__first_name",
        "user__last_name",
        "user__email",
    ]
    ordering_fields = ["admission_number", "admission_date", "status"]
    ordering = ["admission_number"]
    resource_name = "students"

    @action(detail=True, methods=["get"])
    def parents(self, request, pk=None):
        student = self.get_object()
        relations = student.student_parent_relations.all()
        parents = [relation.parent for relation in relations]
        serializer = ParentSerializer(parents, many=True)
        return api_response(data=serializer.data)

    @action(detail=True, methods=["get"])
    def attendance(self, request, pk=None):
        student = self.get_object()

        # Import attendance model dynamically to avoid circular imports
        from src.attendance.models import Attendance
        from src.attendance.serializers import AttendanceSerializer

        # Get attendance records for the student
        queryset = Attendance.objects.filter(student=student)

        # Apply date range filter if provided
        start_date = request.query_params.get("start_date")
        end_date = request.query_params.get("end_date")

        if start_date:
            queryset = queryset.filter(date__gte=start_date)
        if end_date:
            queryset = queryset.filter(date__lte=end_date)

        # Apply class filter if provided
        class_id = request.query_params.get("class_id")
        if class_id:
            queryset = queryset.filter(class_obj_id=class_id)

        serializer = AttendanceSerializer(queryset, many=True)
        return api_response(data=serializer.data)


class ParentViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing parents.
    """

    queryset = Parent.objects.all()
    serializer_class = ParentSerializer
    pagination_class = StandardResultsSetPagination
    permission_classes = [IsAuthenticated, HasResourcePermission]
    authentication_classes = DefaultAuthentication.authentication_classes
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_class = ParentFilter
    search_fields = ["user__first_name", "user__last_name", "user__email", "occupation"]
    ordering_fields = ["user__first_name", "user__last_name", "relation_with_student"]
    ordering = ["user__first_name"]
    resource_name = "parents"

    @action(detail=True, methods=["get"])
    def students(self, request, pk=None):
        parent = self.get_object()
        relations = parent.parent_student_relations.all()
        students = [relation.student for relation in relations]
        serializer = StudentSerializer(students, many=True)
        return api_response(data=serializer.data)


class StudentParentRelationViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing student-parent relations.
    """

    queryset = StudentParentRelation.objects.all()
    serializer_class = StudentParentRelationSerializer
    pagination_class = StandardResultsSetPagination
    permission_classes = [IsAuthenticated, HasResourcePermission]
    authentication_classes = DefaultAuthentication.authentication_classes
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["student", "parent", "is_primary_contact"]
    ordering_fields = ["student__admission_number", "parent__user__first_name"]
    ordering = ["student__admission_number"]
    resource_name = "student_parent_relations"


class TeacherViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing teachers.
    """

    queryset = Teacher.objects.all()
    serializer_class = TeacherSerializer
    pagination_class = StandardResultsSetPagination
    permission_classes = [IsAuthenticated, HasResourcePermission]
    authentication_classes = DefaultAuthentication.authentication_classes
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_class = TeacherFilter
    search_fields = [
        "employee_id",
        "user__first_name",
        "user__last_name",
        "user__email",
        "specialization",
    ]
    ordering_fields = ["employee_id", "joining_date", "status"]
    ordering = ["employee_id"]
    resource_name = "teachers"

    @action(detail=True, methods=["get"])
    def classes(self, request, pk=None):
        teacher = self.get_object()

        # Get class assignments for the teacher
        queryset = TeacherClassAssignment.objects.filter(teacher=teacher)

        # Apply academic year filter if provided
        academic_year_id = request.query_params.get("academic_year")
        if not academic_year_id:
            # Default to current academic year
            current_year = get_current_academic_year()
            if current_year:
                academic_year_id = current_year.id

        if academic_year_id:
            queryset = queryset.filter(academic_year_id=academic_year_id)

        serializer = TeacherClassAssignmentSerializer(queryset, many=True)
        return api_response(data=serializer.data)

    @action(detail=True, methods=["get"])
    def timetable(self, request, pk=None):
        teacher = self.get_object()

        # Get timetable entries for the teacher
        queryset = Timetable.objects.filter(teacher=teacher, is_active=True)

        # Apply day filter if provided
        day = request.query_params.get("day")
        if day is not None:
            queryset = queryset.filter(time_slot__day_of_week=day)

        serializer = TimetableSerializer(queryset, many=True)
        return api_response(data=serializer.data)


class TeacherClassAssignmentViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing teacher-class assignments.
    """

    queryset = TeacherClassAssignment.objects.all()
    serializer_class = TeacherClassAssignmentSerializer
    pagination_class = StandardResultsSetPagination
    permission_classes = [IsAuthenticated, HasResourcePermission]
    authentication_classes = DefaultAuthentication.authentication_classes
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = [
        "teacher",
        "class_instance",
        "subject",
        "academic_year",
        "is_class_teacher",
    ]
    ordering_fields = [
        "teacher__employee_id",
        "class_instance__grade__name",
        "subject__name",
    ]
    ordering = ["teacher__employee_id"]
    resource_name = "teacher_class_assignments"


class TeacherEvaluationViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing teacher evaluations.
    """

    queryset = TeacherEvaluation.objects.all()
    serializer_class = TeacherEvaluationSerializer
    pagination_class = StandardResultsSetPagination
    permission_classes = [IsAuthenticated, HasResourcePermission]
    authentication_classes = DefaultAuthentication.authentication_classes
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["teacher", "evaluator", "evaluation_date"]
    ordering_fields = ["evaluation_date", "score"]
    ordering = ["-evaluation_date"]
    resource_name = "teacher_evaluations"

    def perform_create(self, serializer):
        serializer.save(evaluator=self.request.user)


class DepartmentViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing departments.
    """

    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer
    pagination_class = StandardResultsSetPagination
    permission_classes = [IsAuthenticated, HasResourcePermission]
    authentication_classes = DefaultAuthentication.authentication_classes
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "description"]
    ordering_fields = ["name", "creation_date"]
    ordering = ["name"]
    resource_name = "departments"

    @action(detail=True, methods=["get"])
    def teachers(self, request, pk=None):
        department = self.get_object()
        teachers = Teacher.objects.filter(department=department)
        serializer = TeacherSerializer(teachers, many=True)
        return api_response(data=serializer.data)

    @action(detail=True, methods=["get"])
    def subjects(self, request, pk=None):
        department = self.get_object()
        subjects = Subject.objects.filter(department=department)
        serializer = SubjectSerializer(subjects, many=True)
        return api_response(data=serializer.data)


class AcademicYearViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing academic years.
    """

    queryset = AcademicYear.objects.all()
    serializer_class = AcademicYearSerializer
    pagination_class = StandardResultsSetPagination
    permission_classes = [IsAuthenticated, HasResourcePermission]
    authentication_classes = DefaultAuthentication.authentication_classes
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name"]
    ordering_fields = ["name", "start_date", "end_date", "is_current"]
    ordering = ["-is_current", "-start_date"]
    resource_name = "academic_years"

    @action(detail=True, methods=["post"])
    def set_current(self, request, pk=None):
        academic_year = self.get_object()

        if academic_year.is_current:
            return api_response(message="This academic year is already set as current")

        # Update all academic years
        AcademicYear.objects.filter(is_current=True).update(is_current=False)
        academic_year.is_current = True
        academic_year.save()

        return api_response(message="Academic year set as current successfully")


class GradeViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing grades.
    """

    queryset = Grade.objects.all()
    serializer_class = GradeSerializer
    pagination_class = StandardResultsSetPagination
    permission_classes = [IsAuthenticated, HasResourcePermission]
    authentication_classes = DefaultAuthentication.authentication_classes
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["department"]
    search_fields = ["name", "description"]
    ordering_fields = ["name", "department__name"]
    ordering = ["name"]
    resource_name = "grades"


class SectionViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing sections.
    """

    queryset = Section.objects.all()
    serializer_class = SectionSerializer
    pagination_class = StandardResultsSetPagination
    permission_classes = [IsAuthenticated, HasResourcePermission]
    authentication_classes = DefaultAuthentication.authentication_classes
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "description"]
    ordering_fields = ["name"]
    ordering = ["name"]
    resource_name = "sections"


class ClassViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing classes.
    """

    queryset = Class.objects.all()
    serializer_class = ClassSerializer
    pagination_class = StandardResultsSetPagination
    permission_classes = [IsAuthenticated, HasResourcePermission]
    authentication_classes = DefaultAuthentication.authentication_classes
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_class = ClassFilter
    search_fields = ["grade__name", "section__name", "academic_year__name"]
    ordering_fields = ["grade__name", "section__name", "academic_year__name"]
    ordering = ["grade__name", "section__name"]
    resource_name = "classes"

    @action(detail=True, methods=["get"])
    def students(self, request, pk=None):
        class_obj = self.get_object()
        students = Student.objects.filter(current_class=class_obj)
        serializer = StudentSerializer(students, many=True)
        return api_response(data=serializer.data)

    @action(detail=True, methods=["get"])
    def timetable(self, request, pk=None):
        class_obj = self.get_object()

        # Get timetable entries for the class
        queryset = Timetable.objects.filter(class_obj=class_obj, is_active=True)

        # Apply day filter if provided
        day = request.query_params.get("day")
        if day is not None:
            queryset = queryset.filter(time_slot__day_of_week=day)

        serializer = TimetableSerializer(queryset, many=True)
        return api_response(data=serializer.data)


class SubjectViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing subjects.
    """

    queryset = Subject.objects.all()
    serializer_class = SubjectSerializer
    pagination_class = StandardResultsSetPagination
    permission_classes = [IsAuthenticated, HasResourcePermission]
    authentication_classes = DefaultAuthentication.authentication_classes
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["department", "is_elective"]
    search_fields = ["name", "code", "description"]
    ordering_fields = ["name", "code", "department__name"]
    ordering = ["name"]
    resource_name = "subjects"


class SyllabusViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing syllabi.
    """

    queryset = Syllabus.objects.all()
    serializer_class = SyllabusSerializer
    pagination_class = StandardResultsSetPagination
    permission_classes = [IsAuthenticated, HasResourcePermission]
    authentication_classes = DefaultAuthentication.authentication_classes
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["subject", "grade", "academic_year"]
    search_fields = ["title", "description"]
    ordering_fields = ["title", "subject__name", "grade__name", "academic_year__name"]
    ordering = ["subject__name", "grade__name"]
    resource_name = "syllabi"

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, last_updated_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save(last_updated_by=self.request.user)


class TimeSlotViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing time slots.
    """

    queryset = TimeSlot.objects.all()
    serializer_class = TimeSlotSerializer
    pagination_class = StandardResultsSetPagination
    permission_classes = [IsAuthenticated, HasResourcePermission]
    authentication_classes = DefaultAuthentication.authentication_classes
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["day_of_week"]
    ordering_fields = ["day_of_week", "start_time"]
    ordering = ["day_of_week", "start_time"]
    resource_name = "time_slots"


class TimetableViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing timetables.
    """

    queryset = Timetable.objects.all()
    serializer_class = TimetableSerializer
    pagination_class = StandardResultsSetPagination
    permission_classes = [IsAuthenticated, HasResourcePermission]
    authentication_classes = DefaultAuthentication.authentication_classes
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["class_obj", "subject", "teacher", "time_slot", "is_active"]
    ordering_fields = [
        "class_obj__grade__name",
        "time_slot__day_of_week",
        "time_slot__start_time",
    ]
    ordering = ["time_slot__day_of_week", "time_slot__start_time"]
    resource_name = "timetables"


class AssignmentViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing assignments.
    """

    queryset = Assignment.objects.all()
    serializer_class = AssignmentSerializer
    pagination_class = StandardResultsSetPagination
    permission_classes = [IsAuthenticated, HasResourcePermission]
    authentication_classes = DefaultAuthentication.authentication_classes
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_class = AssignmentFilter
    search_fields = ["title", "description"]
    ordering_fields = ["assigned_date", "due_date", "title"]
    ordering = ["-assigned_date"]
    resource_name = "assignments"

    @action(detail=True, methods=["get"])
    def submissions(self, request, pk=None):
        assignment = self.get_object()
        submissions = AssignmentSubmission.objects.filter(assignment=assignment)
        serializer = AssignmentSubmissionSerializer(submissions, many=True)
        return api_response(data=serializer.data)


class AssignmentSubmissionViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing assignment submissions.
    """

    queryset = AssignmentSubmission.objects.all()
    serializer_class = AssignmentSubmissionSerializer
    pagination_class = StandardResultsSetPagination
    permission_classes = [IsAuthenticated, HasResourcePermission]
    authentication_classes = DefaultAuthentication.authentication_classes
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["assignment", "student", "status"]
    ordering_fields = ["submission_date", "student__user__first_name"]
    ordering = ["-submission_date"]
    resource_name = "assignment_submissions"

    @action(detail=True, methods=["post"])
    def grade(self, request, pk=None):
        submission = self.get_object()

        # Check if the user is a teacher
        if not hasattr(request.user, "teacher_profile"):
            return api_response(
                status="error",
                message="Only teachers can grade submissions",
                status_code=status.HTTP_403_FORBIDDEN,
            )

        # Get grading data
        marks = request.data.get("marks_obtained")
        remarks = request.data.get("remarks", "")

        if marks is None:
            return api_response(
                status="error",
                message="Marks are required",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        # Update submission
        submission.marks_obtained = marks
        submission.remarks = remarks
        submission.status = "graded"
        submission.graded_by = request.user.teacher_profile
        submission.graded_at = timezone.now()
        submission.save()

        serializer = self.get_serializer(submission)
        return api_response(
            data=serializer.data, message="Submission graded successfully"
        )


class SystemSettingViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing system settings.
    """

    queryset = SystemSetting.objects.all()
    serializer_class = SystemSettingSerializer
    pagination_class = StandardResultsSetPagination
    permission_classes = [IsAuthenticated, HasResourcePermission]
    authentication_classes = DefaultAuthentication.authentication_classes
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["setting_key", "description"]
    ordering_fields = ["setting_key", "updated_at"]
    ordering = ["setting_key"]
    resource_name = "system_settings"

    # Override update to prevent modification of non-editable settings
    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        if not instance.is_editable:
            return api_response(
                status="error",
                message="This setting cannot be modified",
                status_code=status.HTTP_403_FORBIDDEN,
            )
        return super().update(request, *args, **kwargs)

    # Override delete to prevent deletion of system settings
    def destroy(self, request, *args, **kwargs):
        return api_response(
            status="error",
            message="System settings cannot be deleted",
            status_code=status.HTTP_403_FORBIDDEN,
        )


class DocumentViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing documents.
    """

    queryset = Document.objects.all()
    serializer_class = DocumentSerializer
    pagination_class = StandardResultsSetPagination
    permission_classes = [IsAuthenticated, HasResourcePermission]
    authentication_classes = DefaultAuthentication.authentication_classes
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["category", "related_to_type", "related_to_id", "is_public"]
    search_fields = ["title", "description", "category"]
    ordering_fields = ["upload_date", "title"]
    ordering = ["-upload_date"]
    resource_name = "documents"

    def get_queryset(self):
        queryset = super().get_queryset()

        # Non-admin users can only see public documents or their own documents
        if not self.request.user.is_staff and not self.request.user.has_role("Admin"):
            queryset = queryset.filter(
                models.Q(is_public=True) | models.Q(uploaded_by=self.request.user)
            )

        return queryset

    def perform_create(self, serializer):
        serializer.save(uploaded_by=self.request.user)
