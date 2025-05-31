import logging

from django.core.exceptions import ValidationError
from django.db.models import Avg, Count, Q
from django.http import Http404, HttpResponse
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

# from src.api.filters import AssignmentFilter, SubmissionFilter
from src.assignments.services.deadline_service import DeadlineService
from src.api.permissions import IsTeacherOrReadOnly
from src.assignments.filters import AssignmentFilter
from src.subjects.api.views import StandardResultsSetPagination

# from src.api.paginations import StandardResultsSetPagination
# from src.api.permissions import IsStudentOwnerOrTeacher, IsTeacherOrReadOnly

from ..models import (
    Assignment,
    AssignmentComment,
    AssignmentRubric,
    AssignmentSubmission,
    SubmissionGrade,
)
from ..services import (
    AssignmentService,
    # DeadlineService,
    GradingService,
    PlagiarismService,
    RubricService,
    SubmissionService,
)
from .serializers import (
    AssignmentAnalyticsSerializer,
    AssignmentCommentSerializer,
    AssignmentCreateSerializer,
    AssignmentDetailSerializer,
    AssignmentListSerializer,
    AssignmentRubricSerializer,
    AssignmentSubmissionCreateSerializer,
    AssignmentSubmissionDetailSerializer,
    AssignmentSubmissionGradeSerializer,
    AssignmentSubmissionListSerializer,
    AssignmentUpdateSerializer,
    DeadlineReminderSerializer,
    PlagiarismResultSerializer,
    SubmissionGradeSerializer,
)

logger = logging.getLogger(__name__)


class AssignmentViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing assignments
    """

    queryset = Assignment.objects.select_related(
        "class_id__grade__section", "subject", "teacher__user", "term"
    ).prefetch_related("submissions", "rubrics")

    permission_classes = [permissions.IsAuthenticated, IsTeacherOrReadOnly]
    filter_backends = [DjangoFilterBackend]
    filterset_class = AssignmentFilter
    pagination_class = StandardResultsSetPagination

    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == "list":
            return AssignmentListSerializer
        elif self.action == "create":
            return AssignmentCreateSerializer
        elif self.action in ["update", "partial_update"]:
            return AssignmentUpdateSerializer
        return AssignmentDetailSerializer

    def get_queryset(self):
        """Filter queryset based on user role"""
        user = self.request.user
        queryset = self.queryset

        if hasattr(user, "teacher"):
            # Teachers see their own assignments
            queryset = queryset.filter(teacher=user.teacher)
        elif hasattr(user, "student"):
            # Students see assignments for their class
            queryset = queryset.filter(
                class_id=user.student.current_class_id, status="published"
            )
        elif hasattr(user, "parent"):
            # Parents see assignments for their children's classes
            children_classes = user.parent.children.values_list(
                "current_class_id", flat=True
            )
            queryset = queryset.filter(
                class_id__in=children_classes, status="published"
            )

        return queryset

    def get_serializer_context(self):
        """Add additional context for serializers"""
        context = super().get_serializer_context()

        # Add student context for student-specific data
        if hasattr(self.request.user, "student"):
            context["student"] = self.request.user.student

        return context

    def perform_create(self, serializer):
        """Create assignment with teacher context"""
        try:
            assignment = AssignmentService.create_assignment(
                teacher=self.request.user.teacher, data=serializer.validated_data
            )
            serializer.instance = assignment
        except Exception as e:
            logger.error(f"Error creating assignment: {str(e)}")
            raise ValidationError(str(e))

    def perform_update(self, serializer):
        """Update assignment with validation"""
        try:
            assignment = AssignmentService.update_assignment(
                assignment_id=self.get_object().id, data=serializer.validated_data
            )
            serializer.instance = assignment
        except Exception as e:
            logger.error(f"Error updating assignment: {str(e)}")
            raise ValidationError(str(e))

    @action(detail=True, methods=["post"])
    def publish(self, request, pk=None):
        """Publish an assignment"""
        try:
            assignment = AssignmentService.publish_assignment(pk)
            serializer = self.get_serializer(assignment)
            return Response(serializer.data)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["get"])
    def analytics(self, request, pk=None):
        """Get assignment analytics"""
        try:
            analytics_data = AssignmentService.get_assignment_analytics(pk)
            serializer = AssignmentAnalyticsSerializer(analytics_data)
            return Response(serializer.data)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["get"])
    def submissions(self, request, pk=None):
        """Get all submissions for an assignment"""
        try:
            assignment = self.get_object()

            # Check permissions
            if not (
                hasattr(request.user, "teacher")
                and request.user.teacher == assignment.teacher
            ):
                return Response(
                    {"error": "Permission denied"}, status=status.HTTP_403_FORBIDDEN
                )

            submissions_data = SubmissionService.get_assignment_submissions(pk)
            submissions = submissions_data["submissions"]

            # Apply filters
            status_filter = request.query_params.get("status")
            if status_filter:
                submissions = submissions.filter(status=status_filter)

            graded_only = request.query_params.get("graded_only") == "true"
            if graded_only:
                submissions = submissions.filter(status="graded")

            ungraded_only = request.query_params.get("ungraded_only") == "true"
            if ungraded_only:
                submissions = submissions.exclude(status="graded")

            # Paginate results
            page = self.paginate_queryset(submissions)
            if page is not None:
                serializer = AssignmentSubmissionListSerializer(page, many=True)
                return self.get_paginated_response(serializer.data)

            serializer = AssignmentSubmissionListSerializer(submissions, many=True)
            return Response(
                {
                    "submissions": serializer.data,
                    "summary": {
                        "total_count": submissions_data["total_count"],
                        "graded_count": submissions_data["graded_count"],
                        "ungraded_count": submissions_data["ungraded_count"],
                        "late_count": submissions_data["late_count"],
                    },
                }
            )

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["get"])
    def export_submissions(self, request, pk=None):
        """Export assignment submissions to CSV"""
        try:
            assignment = self.get_object()

            # Check permissions
            if not (
                hasattr(request.user, "teacher")
                and request.user.teacher == assignment.teacher
            ):
                return Response(
                    {"error": "Permission denied"}, status=status.HTTP_403_FORBIDDEN
                )

            import csv
            from io import StringIO

            output = StringIO()
            writer = csv.writer(output)

            # Write header
            writer.writerow(
                [
                    "Student Name",
                    "Admission Number",
                    "Submission Date",
                    "Status",
                    "Marks Obtained",
                    "Total Marks",
                    "Percentage",
                    "Grade",
                    "Is Late",
                    "Days Late",
                    "Teacher Remarks",
                ]
            )

            # Write data
            submissions = assignment.submissions.select_related("student__user")
            for submission in submissions:
                writer.writerow(
                    [
                        submission.student.user.get_full_name(),
                        submission.student.admission_number,
                        submission.submission_date.strftime("%Y-%m-%d %H:%M"),
                        submission.status,
                        submission.marks_obtained or "",
                        assignment.total_marks,
                        (
                            f"{submission.percentage:.1f}%"
                            if submission.percentage
                            else ""
                        ),
                        submission.grade or "",
                        "Yes" if submission.is_late else "No",
                        submission.days_late,
                        submission.teacher_remarks or "",
                    ]
                )

            response = HttpResponse(output.getvalue(), content_type="text/csv")
            response["Content-Disposition"] = (
                f'attachment; filename="assignment_{assignment.id}_submissions.csv"'
            )
            return response

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=["get"])
    def upcoming_deadlines(self, request):
        # Get upcoming assignment deadlines
        try:
            days_ahead = int(request.query_params.get("days", 7))

            if hasattr(request.user, "student"):
                deadlines = DeadlineService.get_upcoming_deadlines(
                    "student", request.user.student.id, days_ahead
                )
            elif hasattr(request.user, "teacher"):
                deadlines = DeadlineService.get_upcoming_deadlines(
                    "teacher", request.user.teacher.id, days_ahead
                )
            else:
                deadlines = []

            serializer = DeadlineReminderSerializer(deadlines, many=True)
            return Response(serializer.data)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=["get"])
    def overdue(self, request):
        # Get overdue assignments summary
        try:
            # Only allow administrators and principals
            if not request.user.has_perm("assignments.view_assignment"):
                return Response(
                    {"error": "Permission denied"}, status=status.HTTP_403_FORBIDDEN
                )

            overdue_data = DeadlineService.get_overdue_assignments()
            return Response(overdue_data)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class AssignmentSubmissionViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing assignment submissions
    """

    queryset = AssignmentSubmission.objects.select_related(
        "assignment__subject",
        "assignment__class_id",
        "student__user",
        "graded_by__user",
    ).prefetch_related("rubric_grades__rubric")

    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    # filterset_class = SubmissionFilter
    pagination_class = StandardResultsSetPagination
    parser_classes = [MultiPartParser, FormParser]

    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == "list":
            return AssignmentSubmissionListSerializer
        elif self.action == "create":
            return AssignmentSubmissionCreateSerializer
        elif self.action == "grade":
            return AssignmentSubmissionGradeSerializer
        return AssignmentSubmissionDetailSerializer

    def get_queryset(self):
        """Filter queryset based on user role"""
        user = self.request.user
        queryset = self.queryset

        if hasattr(user, "student"):
            # Students see only their submissions
            queryset = queryset.filter(student=user.student)
        elif hasattr(user, "teacher"):
            # Teachers see submissions for their assignments
            queryset = queryset.filter(assignment__teacher=user.teacher)
        elif hasattr(user, "parent"):
            # Parents see their children's submissions
            children = user.parent.children.all()
            queryset = queryset.filter(student__in=children)

        return queryset

    def get_serializer_context(self):
        """Add assignment context for validation"""
        context = super().get_serializer_context()

        if self.action == "create":
            assignment_id = self.request.data.get("assignment_id")
            if assignment_id:
                try:
                    assignment = Assignment.objects.get(id=assignment_id)
                    context["assignment"] = assignment
                except Assignment.DoesNotExist:
                    pass

        return context

    def create(self, request, *args, **kwargs):
        """Create or update a submission"""
        try:
            assignment_id = request.data.get("assignment_id")
            if not assignment_id:
                return Response(
                    {"error": "Assignment ID is required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Ensure user is a student
            if not hasattr(request.user, "student"):
                return Response(
                    {"error": "Only students can submit assignments"},
                    status=status.HTTP_403_FORBIDDEN,
                )

            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            submission = SubmissionService.create_submission(
                student=request.user.student,
                assignment_id=assignment_id,
                data=serializer.validated_data,
            )

            response_serializer = AssignmentSubmissionDetailSerializer(submission)
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"])
    def grade(self, request, pk=None):
        """Grade a submission"""
        try:
            submission = self.get_object()

            # Check permissions
            if not (
                hasattr(request.user, "teacher")
                and request.user.teacher == submission.assignment.teacher
            ):
                return Response(
                    {"error": "Permission denied"}, status=status.HTTP_403_FORBIDDEN
                )

            serializer = AssignmentSubmissionGradeSerializer(
                submission, data=request.data, context={"request": request}
            )
            serializer.is_valid(raise_exception=True)
            serializer.save()

            response_serializer = AssignmentSubmissionDetailSerializer(submission)
            return Response(response_serializer.data)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"])
    def check_plagiarism(self, request, pk=None):
        """Check submission for plagiarism"""
        try:
            submission = self.get_object()

            # Check permissions
            if not (
                hasattr(request.user, "teacher")
                and request.user.teacher == submission.assignment.teacher
            ):
                return Response(
                    {"error": "Permission denied"}, status=status.HTTP_403_FORBIDDEN
                )

            result = PlagiarismService.check_submission_plagiarism(pk)
            serializer = PlagiarismResultSerializer(result)
            return Response(serializer.data)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["get"])
    def download(self, request, pk=None):
        """Download submission attachment"""
        try:
            submission = self.get_object()

            # Check permissions
            if not (
                submission.student.user == request.user
                or (
                    hasattr(request.user, "teacher")
                    and request.user.teacher == submission.assignment.teacher
                )
            ):
                return Response(
                    {"error": "Permission denied"}, status=status.HTTP_403_FORBIDDEN
                )

            if not submission.attachment:
                return Response(
                    {"error": "No attachment found"}, status=status.HTTP_404_NOT_FOUND
                )

            response = HttpResponse(
                submission.attachment.read(), content_type="application/octet-stream"
            )
            response["Content-Disposition"] = (
                f'attachment; filename="{submission.attachment.name}"'
            )
            return response

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=["post"])
    def bulk_grade(self, request):
        """Grade multiple submissions at once"""
        try:
            # Check permissions
            if not hasattr(request.user, "teacher"):
                return Response(
                    {"error": "Only teachers can grade submissions"},
                    status=status.HTTP_403_FORBIDDEN,
                )

            grading_data = request.data.get("submissions", [])
            assignment_id = request.data.get("assignment_id")

            if not assignment_id:
                return Response(
                    {"error": "Assignment ID is required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            result = GradingService.bulk_grade_submissions(
                assignment_id=assignment_id,
                grader=request.user.teacher,
                grading_data=grading_data,
            )

            return Response(result)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class AssignmentRubricViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing assignment rubrics
    """

    queryset = AssignmentRubric.objects.select_related("assignment")
    serializer_class = AssignmentRubricSerializer
    permission_classes = [permissions.IsAuthenticated, IsTeacherOrReadOnly]

    def get_queryset(self):
        """Filter rubrics based on assignment access"""
        user = self.request.user

        if hasattr(user, "teacher"):
            return self.queryset.filter(assignment__teacher=user.teacher)
        elif hasattr(user, "student"):
            return self.queryset.filter(
                assignment__class_id=user.student.current_class_id,
                assignment__status="published",
            )

        return self.queryset.none()

    @action(detail=False, methods=["post"])
    def create_rubric(self, request):
        """Create rubric for an assignment"""
        try:
            assignment_id = request.data.get("assignment_id")
            rubric_data = request.data.get("rubrics", [])

            if not assignment_id:
                return Response(
                    {"error": "Assignment ID is required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Check permissions
            try:
                assignment = Assignment.objects.get(id=assignment_id)
                if assignment.teacher != request.user.teacher:
                    return Response(
                        {"error": "Permission denied"}, status=status.HTTP_403_FORBIDDEN
                    )
            except Assignment.DoesNotExist:
                return Response(
                    {"error": "Assignment not found"}, status=status.HTTP_404_NOT_FOUND
                )

            rubrics = RubricService.create_rubric(assignment_id, rubric_data)
            serializer = AssignmentRubricSerializer(rubrics, many=True)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class AssignmentCommentViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing assignment comments
    """

    queryset = AssignmentComment.objects.select_related("user", "assignment")
    serializer_class = AssignmentCommentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Filter comments based on assignment access"""
        user = self.request.user

        if hasattr(user, "teacher"):
            # Teachers see all comments on their assignments
            return self.queryset.filter(assignment__teacher=user.teacher)
        elif hasattr(user, "student"):
            # Students see public comments on their class assignments
            return self.queryset.filter(
                assignment__class_id=user.student.current_class_id,
                assignment__status="published",
                is_private=False,
            )

        return self.queryset.none()

    def perform_create(self, serializer):
        """Set user when creating comment"""
        serializer.save(user=self.request.user)


class TeacherAnalyticsView(viewsets.ViewSet):
    """
    ViewSet for teacher-specific assignment analytics
    """

    permission_classes = [permissions.IsAuthenticated]

    def list(self, request):
        """Get comprehensive teacher analytics"""
        try:
            if not hasattr(request.user, "teacher"):
                return Response(
                    {"error": "Only teachers can access this endpoint"},
                    status=status.HTTP_403_FORBIDDEN,
                )

            # Get filters from query params
            filters = {}
            if request.query_params.get("subject"):
                filters["subject"] = request.query_params.get("subject")
            if request.query_params.get("class_id"):
                filters["class_id"] = request.query_params.get("class_id")
            if request.query_params.get("term"):
                filters["term"] = request.query_params.get("term")

            analytics = GradingService.get_grading_analytics(
                request.user.teacher, filters
            )

            # Get assignment overview
            assignment_overview = AssignmentService.get_teacher_assignments(
                request.user.teacher, filters
            )

            combined_analytics = {
                "grading_analytics": analytics,
                "assignment_overview": {
                    "total_assignments": assignment_overview["total_count"],
                    "draft_assignments": assignment_overview["draft_count"],
                    "published_assignments": assignment_overview["published_count"],
                    "closed_assignments": assignment_overview["closed_count"],
                    "overdue_assignments": assignment_overview["overdue_count"],
                },
            }

            return Response(combined_analytics)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=["get"])
    def assignment_performance(self, request):
        """Get performance analytics for teacher's assignments"""
        try:
            if not hasattr(request.user, "teacher"):
                return Response(
                    {"error": "Only teachers can access this endpoint"},
                    status=status.HTTP_403_FORBIDDEN,
                )

            teacher = request.user.teacher
            assignments = Assignment.objects.filter(teacher=teacher)

            performance_data = []
            for assignment in assignments:
                analytics = AssignmentService.get_assignment_analytics(assignment.id)
                performance_data.append(analytics)

            return Response(performance_data)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class StudentAnalyticsView(viewsets.ViewSet):
    """
    ViewSet for student-specific assignment analytics
    """

    permission_classes = [permissions.IsAuthenticated]

    def list(self, request):
        """Get comprehensive student analytics"""
        try:
            if not hasattr(request.user, "student"):
                return Response(
                    {"error": "Only students can access this endpoint"},
                    status=status.HTTP_403_FORBIDDEN,
                )

            # Get filters from query params
            filters = {}
            if request.query_params.get("subject"):
                filters["subject"] = request.query_params.get("subject")
            if request.query_params.get("term"):
                filters["term"] = request.query_params.get("term")

            submissions_data = SubmissionService.get_student_submissions(
                request.user.student, filters
            )

            # Calculate additional analytics
            submissions = submissions_data["submissions"]

            # Subject-wise performance
            subject_performance = {}
            for submission in submissions.filter(marks_obtained__isnull=False):
                subject = submission.assignment.subject.name
                if subject not in subject_performance:
                    subject_performance[subject] = {
                        "total_assignments": 0,
                        "completed": 0,
                        "total_marks": 0,
                        "obtained_marks": 0,
                        "average_percentage": 0,
                    }

                subject_performance[subject]["total_assignments"] += 1
                subject_performance[subject]["completed"] += 1
                subject_performance[subject][
                    "total_marks"
                ] += submission.assignment.total_marks
                subject_performance[subject][
                    "obtained_marks"
                ] += submission.marks_obtained

            # Calculate averages
            for subject, data in subject_performance.items():
                if data["total_marks"] > 0:
                    data["average_percentage"] = (
                        data["obtained_marks"] / data["total_marks"]
                    ) * 100

            analytics = {
                "submission_summary": {
                    "total_submissions": submissions_data["total_count"],
                    "graded_submissions": submissions_data["graded_count"],
                    "pending_submissions": submissions_data["pending_count"],
                    "late_submissions": submissions_data["late_count"],
                    "average_score": submissions_data["average_score"],
                },
                "subject_performance": subject_performance,
                "recent_submissions": AssignmentSubmissionListSerializer(
                    submissions[:5], many=True
                ).data,
            }

            return Response(analytics)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
