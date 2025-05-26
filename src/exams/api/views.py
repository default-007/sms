"""
School Management System - Exam API Views
File: src/exams/api/views.py
"""

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q, Prefetch
from django.shortcuts import get_object_or_404

from api.permissions import IsAdminOrTeacher, IsAdminOrTeacherOrParent
from api.paginations import StandardResultsSetPagination
from exams.services.exam_service import ExamService
from ..models import (
    Exam,
    ExamType,
    ExamSchedule,
    StudentExamResult,
    ReportCard,
    GradingSystem,
    ExamQuestion,
    OnlineExam,
    StudentOnlineExamAttempt,
)

# from exams.services.exam_service import ExamService, ResultService, OnlineExamService
from .serializers import (
    ExamTypeSerializer,
    ExamListSerializer,
    ExamDetailSerializer,
    ExamScheduleListSerializer,
    ExamScheduleDetailSerializer,
    StudentExamResultSerializer,
    BulkResultEntrySerializer,
    ReportCardSerializer,
    GradingSystemSerializer,
    ExamQuestionSerializer,
    OnlineExamSerializer,
    StudentOnlineExamAttemptSerializer,
    ExamAnalyticsSerializer,
    QuestionBankFilterSerializer,
    AutoQuestionSelectionSerializer,
)


class ExamTypeViewSet(viewsets.ModelViewSet):
    """ViewSet for managing exam types"""

    queryset = ExamType.objects.all()
    serializer_class = ExamTypeSerializer
    permission_classes = [IsAuthenticated, IsAdminOrTeacher]
    pagination_class = StandardResultsSetPagination
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    search_fields = ["name", "description"]
    filterset_fields = ["is_term_based", "frequency", "is_online", "is_active"]
    ordering_fields = ["name", "contribution_percentage", "created_at"]
    ordering = ["contribution_percentage", "name"]


class ExamViewSet(viewsets.ModelViewSet):
    """ViewSet for managing exams"""

    permission_classes = [IsAuthenticated, IsAdminOrTeacher]
    pagination_class = StandardResultsSetPagination
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    search_fields = ["name", "description"]
    filterset_fields = ["exam_type", "academic_year", "term", "status", "is_published"]
    ordering_fields = ["name", "start_date", "created_at"]
    ordering = ["-start_date", "name"]

    def get_queryset(self):
        return Exam.objects.select_related(
            "exam_type", "academic_year", "term", "created_by"
        ).prefetch_related("schedules")

    def get_serializer_class(self):
        if self.action == "list":
            return ExamListSerializer
        return ExamDetailSerializer

    def create(self, request, *args, **kwargs):
        """Create exam with auto-calculation of total students"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        exam_data = serializer.validated_data
        exam_data["created_by"] = request.user

        exam = ExamService.create_exam(exam_data)

        response_serializer = self.get_serializer(exam)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def publish(self, request, pk=None):
        """Publish exam to make it visible to students"""
        exam = ExamService.publish_exam(pk)
        serializer = self.get_serializer(exam)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def analytics(self, request, pk=None):
        """Get comprehensive exam analytics"""
        analytics_data = ExamService.get_exam_analytics(pk)
        serializer = ExamAnalyticsSerializer(analytics_data)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def bulk_schedule(self, request, pk=None):
        """Create exam schedules for multiple classes/subjects"""
        exam = self.get_object()
        schedule_data = request.data.get("schedules", [])

        try:
            schedules = ExamService.schedule_exam_for_classes(exam, schedule_data)
            serializer = ExamScheduleListSerializer(schedules, many=True)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["get"])
    def report_cards(self, request, pk=None):
        """Get all report cards for this exam's term"""
        exam = self.get_object()
        report_cards = ReportCard.objects.filter(
            term=exam.term, academic_year=exam.academic_year
        ).select_related("student__user", "class_obj")

        serializer = ReportCardSerializer(report_cards, many=True)
        return Response(serializer.data)


class ExamScheduleViewSet(viewsets.ModelViewSet):
    """ViewSet for managing exam schedules"""

    permission_classes = [IsAuthenticated, IsAdminOrTeacher]
    pagination_class = StandardResultsSetPagination
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    search_fields = ["exam__name", "subject__name", "class_obj__name"]
    filterset_fields = [
        "exam",
        "class_obj",
        "subject",
        "supervisor",
        "is_active",
        "is_completed",
        "date",
    ]
    ordering_fields = ["date", "start_time", "exam__name"]
    ordering = ["date", "start_time"]

    def get_queryset(self):
        return ExamSchedule.objects.select_related(
            "exam", "class_obj", "subject", "supervisor__user"
        ).prefetch_related("additional_supervisors")

    def get_serializer_class(self):
        if self.action == "list":
            return ExamScheduleListSerializer
        return ExamScheduleDetailSerializer

    @action(detail=True, methods=["post"])
    def mark_completed(self, request, pk=None):
        """Mark exam schedule as completed"""
        schedule = self.get_object()
        schedule.is_completed = True
        schedule.save()

        serializer = self.get_serializer(schedule)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def student_list(self, request, pk=None):
        """Get list of students for this exam schedule"""
        schedule = self.get_object()
        students = schedule.class_obj.students.filter(status="ACTIVE")

        student_data = [
            {
                "id": student.id,
                "name": student.user.get_full_name(),
                "admission_number": student.admission_number,
                "has_result": StudentExamResult.objects.filter(
                    student=student, exam_schedule=schedule
                ).exists(),
            }
            for student in students
        ]

        return Response(student_data)

    @action(detail=True, methods=["post"])
    def bulk_results(self, request, pk=None):
        """Bulk entry of exam results"""
        schedule = self.get_object()
        serializer = BulkResultEntrySerializer(data=request.data)

        if serializer.is_valid():
            results_data = serializer.validated_data["results"]

            try:
                results = ResultService.enter_results(pk, results_data, request.user)
                response_serializer = StudentExamResultSerializer(results, many=True)
                return Response(
                    response_serializer.data, status=status.HTTP_201_CREATED
                )
            except Exception as e:
                return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["get"])
    def results(self, request, pk=None):
        """Get all results for this exam schedule"""
        schedule = self.get_object()
        results = StudentExamResult.objects.filter(
            exam_schedule=schedule
        ).select_related("student__user", "entered_by")

        serializer = StudentExamResultSerializer(results, many=True)
        return Response(serializer.data)


class StudentExamResultViewSet(viewsets.ModelViewSet):
    """ViewSet for managing individual exam results"""

    queryset = StudentExamResult.objects.select_related(
        "student__user", "exam_schedule__subject", "entered_by"
    )
    serializer_class = StudentExamResultSerializer
    permission_classes = [IsAuthenticated, IsAdminOrTeacher]
    pagination_class = StandardResultsSetPagination
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    search_fields = ["student__user__first_name", "student__user__last_name"]
    filterset_fields = [
        "student",
        "exam_schedule",
        "term",
        "grade",
        "is_pass",
        "is_absent",
        "is_exempted",
    ]
    ordering_fields = ["percentage", "marks_obtained", "entry_date"]
    ordering = ["-percentage"]

    def create(self, request, *args, **kwargs):
        """Create result with auto-calculated fields"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        data["entered_by"] = request.user

        result = StudentExamResult.objects.create(**data)
        response_serializer = self.get_serializer(result)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["get"])
    def student_performance(self, request):
        """Get performance data for a specific student"""
        student_id = request.query_params.get("student_id")
        term_id = request.query_params.get("term_id")

        if not student_id:
            return Response(
                {"error": "student_id is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        queryset = self.get_queryset().filter(student_id=student_id)
        if term_id:
            queryset = queryset.filter(term_id=term_id)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class ReportCardViewSet(viewsets.ModelViewSet):
    """ViewSet for managing report cards"""

    queryset = ReportCard.objects.select_related(
        "student__user", "class_obj", "academic_year", "term"
    )
    serializer_class = ReportCardSerializer
    permission_classes = [IsAuthenticated, IsAdminOrTeacherOrParent]
    pagination_class = StandardResultsSetPagination
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    search_fields = ["student__user__first_name", "student__user__last_name"]
    filterset_fields = [
        "student",
        "class_obj",
        "academic_year",
        "term",
        "status",
        "grade",
    ]
    ordering_fields = ["class_rank", "percentage", "generation_date"]
    ordering = ["class_rank"]

    def get_queryset(self):
        queryset = super().get_queryset()

        # Filter based on user role
        if self.request.user.role == "PARENT":
            # Parents can only see their children's report cards
            parent_students = self.request.user.parent.students.all()
            queryset = queryset.filter(student__in=parent_students)
        elif self.request.user.role == "STUDENT":
            # Students can only see their own report cards
            queryset = queryset.filter(student__user=self.request.user)

        return queryset

    @action(detail=False, methods=["post"])
    def generate_bulk(self, request):
        """Generate report cards for a term/class"""
        term_id = request.data.get("term_id")
        class_ids = request.data.get("class_ids", [])

        if not term_id:
            return Response(
                {"error": "term_id is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            report_cards = ResultService.generate_report_cards(term_id, class_ids)
            serializer = self.get_serializer(report_cards, many=True)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"])
    def publish(self, request, pk=None):
        """Publish a report card"""
        report_card = self.get_object()
        report_card.status = "PUBLISHED"
        report_card.save()

        serializer = self.get_serializer(report_card)
        return Response(serializer.data)


class GradingSystemViewSet(viewsets.ModelViewSet):
    """ViewSet for managing grading systems"""

    queryset = GradingSystem.objects.prefetch_related("grade_scales")
    serializer_class = GradingSystemSerializer
    permission_classes = [IsAuthenticated, IsAdminOrTeacher]
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    search_fields = ["name", "description"]
    filterset_fields = ["academic_year", "is_default", "is_active"]


class ExamQuestionViewSet(viewsets.ModelViewSet):
    """ViewSet for managing exam questions"""

    queryset = ExamQuestion.objects.select_related("subject", "grade", "created_by")
    serializer_class = ExamQuestionSerializer
    permission_classes = [IsAuthenticated, IsAdminOrTeacher]
    pagination_class = StandardResultsSetPagination
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    search_fields = ["question_text", "topic", "learning_objective"]
    filterset_fields = [
        "subject",
        "grade",
        "question_type",
        "difficulty_level",
        "is_active",
        "created_by",
    ]
    ordering_fields = ["created_at", "usage_count", "marks"]
    ordering = ["-created_at"]

    def create(self, request, *args, **kwargs):
        """Create question with creator tracking"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        data["created_by"] = request.user

        question = ExamQuestion.objects.create(**data)
        response_serializer = self.get_serializer(question)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["post"])
    def filter_questions(self, request):
        """Advanced filtering for question bank"""
        filter_serializer = QuestionBankFilterSerializer(data=request.data)
        filter_serializer.is_valid(raise_exception=True)

        queryset = self.get_queryset()
        filters = filter_serializer.validated_data

        if "subject" in filters:
            queryset = queryset.filter(subject_id=filters["subject"])
        if "grade" in filters:
            queryset = queryset.filter(grade_id=filters["grade"])
        if "question_type" in filters:
            queryset = queryset.filter(question_type=filters["question_type"])
        if "difficulty_level" in filters:
            queryset = queryset.filter(difficulty_level=filters["difficulty_level"])
        if "topic" in filters:
            queryset = queryset.filter(topic__icontains=filters["topic"])
        if "marks" in filters:
            queryset = queryset.filter(marks=filters["marks"])

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def statistics(self, request):
        """Get question bank statistics"""
        queryset = self.get_queryset()

        stats = {
            "total_questions": queryset.count(),
            "by_subject": dict(
                queryset.values_list("subject__name").annotate(count=Count("id"))
            ),
            "by_difficulty": dict(
                queryset.values_list("difficulty_level").annotate(count=Count("id"))
            ),
            "by_type": dict(
                queryset.values_list("question_type").annotate(count=Count("id"))
            ),
            "by_grade": dict(
                queryset.values_list("grade__name").annotate(count=Count("id"))
            ),
        }

        return Response(stats)


class OnlineExamViewSet(viewsets.ModelViewSet):
    """ViewSet for managing online exams"""

    queryset = OnlineExam.objects.select_related("exam_schedule")
    serializer_class = OnlineExamSerializer
    permission_classes = [IsAuthenticated, IsAdminOrTeacher]
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    search_fields = ["exam_schedule__exam__name", "exam_schedule__subject__name"]
    filterset_fields = [
        "exam_schedule__exam",
        "exam_schedule__subject",
        "enable_proctoring",
        "shuffle_questions",
    ]

    @action(detail=True, methods=["post"])
    def add_questions(self, request, pk=None):
        """Add questions to online exam"""
        online_exam = self.get_object()
        question_configs = request.data.get("questions", [])

        try:
            updated_exam = OnlineExamService.add_questions_to_exam(pk, question_configs)
            serializer = self.get_serializer(updated_exam)
            return Response(serializer.data)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"])
    def auto_select_questions(self, request, pk=None):
        """Automatically select questions based on criteria"""
        selection_serializer = AutoQuestionSelectionSerializer(data=request.data)
        selection_serializer.is_valid(raise_exception=True)

        criteria = selection_serializer.validated_data

        try:
            questions = OnlineExamService.auto_select_questions(pk, criteria)
            question_serializer = ExamQuestionSerializer(questions, many=True)
            return Response(question_serializer.data)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["get"])
    def attempts(self, request, pk=None):
        """Get all student attempts for this online exam"""
        online_exam = self.get_object()
        attempts = StudentOnlineExamAttempt.objects.filter(
            online_exam=online_exam
        ).select_related("student__user")

        serializer = StudentOnlineExamAttemptSerializer(attempts, many=True)
        return Response(serializer.data)


class StudentOnlineExamAttemptViewSet(viewsets.ModelViewSet):
    """ViewSet for managing student online exam attempts"""

    queryset = StudentOnlineExamAttempt.objects.select_related(
        "student__user", "online_exam__exam_schedule"
    )
    serializer_class = StudentOnlineExamAttemptSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = [
        "student",
        "online_exam",
        "status",
        "is_graded",
        "attempt_number",
    ]
    ordering_fields = ["start_time", "marks_obtained", "attempt_number"]
    ordering = ["-start_time"]

    def get_queryset(self):
        queryset = super().get_queryset()

        # Students can only see their own attempts
        if self.request.user.role == "STUDENT":
            queryset = queryset.filter(student__user=self.request.user)

        return queryset

    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        """Submit online exam attempt"""
        attempt = self.get_object()

        if attempt.status != "IN_PROGRESS":
            return Response(
                {"error": "Exam attempt is not in progress"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        attempt.responses = request.data.get("responses", {})
        attempt.submit_time = timezone.now()
        attempt.status = "SUBMITTED"
        attempt.save()

        # Auto-grade if possible
        # This would involve checking answers against correct answers

        serializer = self.get_serializer(attempt)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def grade(self, request, pk=None):
        """Manual grading for subjective questions"""
        attempt = self.get_object()

        if attempt.status != "SUBMITTED":
            return Response(
                {"error": "Exam attempt must be submitted before grading"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        manual_grades = request.data.get("manual_grades", {})
        attempt.manual_graded_marks = sum(manual_grades.values())
        attempt.marks_obtained = attempt.auto_graded_marks + attempt.manual_graded_marks
        attempt.is_graded = True
        attempt.save()

        serializer = self.get_serializer(attempt)
        return Response(serializer.data)
