from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.contrib.auth import get_user_model
from django.db import models
from django.shortcuts import get_object_or_404

from .serializers import (
    UserSerializer,
    UserCreateSerializer,
    UserRoleSerializer,
    UserRoleAssignmentSerializer,
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

from src.accounts.models import UserRole, UserRoleAssignment
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


class UserViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing users.
    """

    queryset = User.objects.all()
    serializer_class = UserSerializer
    pagination_class = StandardResultsSetPagination
    permission_classes = [IsAuthenticated, HasResourcePermission]
    authentication_classes = DefaultAuthentication.authentication_classes
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_class = UserFilter
    search_fields = ["username", "email", "first_name", "last_name", "phone_number"]
    ordering_fields = ["username", "email", "date_joined", "last_login"]
    ordering = ["username"]
    resource_name = "users"

    def get_serializer_class(self):
        if self.action == "create":
            return UserCreateSerializer
        return UserSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        # Assign roles if provided
        roles = request.data.get("roles", [])
        if roles:
            for role_id in roles:
                try:
                    role = UserRole.objects.get(pk=role_id)
                    UserRoleAssignment.objects.create(
                        user=user, role=role, assigned_by=request.user
                    )
                except UserRole.DoesNotExist:
                    pass

        # Return response
        headers = self.get_success_headers(serializer.data)
        return api_response(
            data=serializer.data,
            message="User created successfully",
            status_code=status.HTTP_201_CREATED,
            headers=headers,
        )

    @action(detail=True, methods=["post"])
    def change_password(self, request, pk=None):
        user = self.get_object()

        # Check if the user has permission
        if user != request.user and not RoleService.check_permission(
            request.user, "users", "change"
        ):
            return api_response(
                status="error",
                message="You don't have permission to change this user's password",
                status_code=status.HTTP_403_FORBIDDEN,
            )

        # Check current password if user is changing their own password
        current_password = request.data.get("current_password", "")
        if user == request.user and not user.check_password(current_password):
            return api_response(
                status="error",
                message="Current password is incorrect",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        # Validate new password
        new_password = request.data.get("new_password", "")
        if not new_password:
            return api_response(
                status="error",
                message="New password is required",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        # Set new password
        user.set_password(new_password)
        user.save()

        return api_response(message="Password changed successfully")

    @action(detail=True, methods=["get"])
    def roles(self, request, pk=None):
        user = self.get_object()
        roles = user.role_assignments.all()
        serializer = UserRoleAssignmentSerializer(roles, many=True)
        return api_response(data=serializer.data)

    @action(detail=True, methods=["post"])
    def assign_role(self, request, pk=None):
        user = self.get_object()
        role_id = request.data.get("role")

        if not role_id:
            return api_response(
                status="error",
                message="Role ID is required",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        try:
            role = UserRole.objects.get(pk=role_id)
            assignment, created = UserRoleAssignment.objects.get_or_create(
                user=user, role=role, defaults={"assigned_by": request.user}
            )

            if created:
                return api_response(
                    data=UserRoleAssignmentSerializer(assignment).data,
                    message="Role assigned successfully",
                )
            else:
                return api_response(
                    data=UserRoleAssignmentSerializer(assignment).data,
                    message="Role was already assigned",
                )
        except UserRole.DoesNotExist:
            return api_response(
                status="error",
                message="Role not found",
                status_code=status.HTTP_404_NOT_FOUND,
            )

    @action(detail=True, methods=["post"])
    def remove_role(self, request, pk=None):
        user = self.get_object()
        role_id = request.data.get("role")

        if not role_id:
            return api_response(
                status="error",
                message="Role ID is required",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        try:
            assignment = UserRoleAssignment.objects.get(user=user, role_id=role_id)
            assignment.delete()
            return api_response(message="Role removed successfully")
        except UserRoleAssignment.DoesNotExist:
            return api_response(
                status="error",
                message="Role assignment not found",
                status_code=status.HTTP_404_NOT_FOUND,
            )


class UserRoleViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing user roles.
    """

    queryset = UserRole.objects.all()
    serializer_class = UserRoleSerializer
    pagination_class = StandardResultsSetPagination
    permission_classes = [IsAuthenticated, HasResourcePermission]
    authentication_classes = DefaultAuthentication.authentication_classes
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "description"]
    ordering_fields = ["name"]
    ordering = ["name"]
    resource_name = "roles"

    @action(detail=True, methods=["get"])
    def users(self, request, pk=None):
        role = self.get_object()
        assignments = role.user_assignments.all()
        serializer = UserRoleAssignmentSerializer(assignments, many=True)
        return api_response(data=serializer.data)


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
