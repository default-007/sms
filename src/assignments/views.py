import csv
import json
import logging
from datetime import datetime, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Avg, Count, Prefetch, Q, Sum
from django.http import Http404, HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    FormView,
    ListView,
    TemplateView,
    UpdateView,
    View,
)

from src.assignments.services.analytics_service import AssignmentAnalyticsService
from src.core.mixins import (
    StudentMixin,
    TeacherMixin,
)

from .filters import AssignmentFilter, AssignmentSubmissionFilter
from .forms import (
    AssignmentCommentForm,
    AssignmentForm,
    AssignmentRubricForm,
    AssignmentSearchForm,
    AssignmentSubmissionForm,
    AssignmentTemplateForm,
    BulkGradeForm,
    DeadlineExtensionForm,
    NotificationSettingsForm,
    RubricFormSet,
    SubmissionGradingForm,
)
from .models import (
    Assignment,
    AssignmentComment,
    AssignmentRubric,
    AssignmentSubmission,
)
from .services import (
    AssignmentService,
    DeadlineService,
    GradingService,
    PlagiarismService,
    RubricService,
    SubmissionService,
)

logger = logging.getLogger(__name__)


class AssignmentListView(LoginRequiredMixin, ListView):
    """
    List view for assignments with role-based filtering
    """

    model = Assignment
    template_name = "assignments/assignment_list.html"
    context_object_name = "assignments"
    paginate_by = 20

    def get_queryset(self):
        """Filter assignments based on user role"""
        user = self.request.user
        queryset = Assignment.objects.select_related(
            "class_id__grade__section", "subject", "teacher__user", "term"
        ).prefetch_related("submissions")

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
        elif not user.is_staff:
            # Non-staff users without specific roles see nothing
            queryset = queryset.none()

        # Apply search and filters
        self.filterset = AssignmentFilter(
            self.request.GET, queryset=queryset, request=self.request
        )
        return self.filterset.qs.order_by("-created_at")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["filter"] = self.filterset
        context["search_form"] = AssignmentSearchForm(self.request.GET)

        # Add summary statistics
        if hasattr(self.request.user, "teacher"):
            teacher = self.request.user.teacher
            context["stats"] = {
                "total": Assignment.objects.filter(teacher=teacher).count(),
                "published": Assignment.objects.filter(
                    teacher=teacher, status="published"
                ).count(),
                "draft": Assignment.objects.filter(
                    teacher=teacher, status="draft"
                ).count(),
                "overdue": Assignment.objects.filter(
                    teacher=teacher, status="published", due_date__lt=timezone.now()
                ).count(),
            }

        return context


class AssignmentDetailView(LoginRequiredMixin, DetailView):
    """
    Detailed view of an assignment
    """

    model = Assignment
    template_name = "assignments/assignment_detail.html"
    context_object_name = "assignment"

    def get_queryset(self):
        """Ensure user has permission to view assignment"""
        user = self.request.user
        queryset = Assignment.objects.select_related(
            "class_id__grade__section", "subject", "teacher__user", "term"
        ).prefetch_related("rubrics", "comments__user", "submissions__student__user")

        if hasattr(user, "teacher"):
            return queryset.filter(teacher=user.teacher)
        elif hasattr(user, "student"):
            return queryset.filter(
                class_id=user.student.current_class_id, status="published"
            )
        elif hasattr(user, "parent"):
            children_classes = user.parent.children.values_list(
                "current_class_id", flat=True
            )
            return queryset.filter(class_id__in=children_classes, status="published")
        elif user.is_staff:
            return queryset
        else:
            return queryset.none()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        assignment = self.object
        user = self.request.user

        # Add submission information for students
        if hasattr(user, "student"):
            try:
                context["student_submission"] = assignment.submissions.get(
                    student=user.student
                )
            except AssignmentSubmission.DoesNotExist:
                context["student_submission"] = None

        # Add assignment analytics for teachers
        if hasattr(user, "teacher") and assignment.teacher == user.teacher:
            try:
                context["analytics"] = AssignmentService.get_assignment_analytics(
                    assignment.id
                )
                context["submissions"] = assignment.submissions.select_related(
                    "student__user"
                ).order_by("-submission_date")[:10]
            except Exception as e:
                logger.error(f"Error getting assignment analytics: {str(e)}")
                context["analytics"] = None

        # Add comment form
        context["comment_form"] = AssignmentCommentForm(user=user)

        return context


class AssignmentCreateView(TeacherMixin, CreateView):
    """
    Create new assignment
    """

    model = Assignment
    form_class = AssignmentForm
    template_name = "assignments/assignment_form.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["teacher"] = self.request.user.teacher
        return kwargs

    def form_valid(self, form):
        """Save assignment and handle rubrics"""
        try:
            assignment = AssignmentService.create_assignment(
                teacher=self.request.user.teacher, data=form.cleaned_data
            )

            # Handle rubric formset if provided
            if "rubric_formset" in self.request.POST:
                rubric_formset = RubricFormSet(self.request.POST, instance=assignment)
                if rubric_formset.is_valid():
                    rubric_formset.save()

            messages.success(
                self.request, f'Assignment "{assignment.title}" created successfully.'
            )
            return redirect("assignments:assignment_detail", pk=assignment.pk)

        except Exception as e:
            messages.error(self.request, f"Error creating assignment: {str(e)}")
            return self.form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["rubric_formset"] = RubricFormSet()
        return context


class AssignmentUpdateView(TeacherMixin, UpdateView):
    """
    Update existing assignment
    """

    model = Assignment
    form_class = AssignmentForm
    template_name = "assignments/assignment_form.html"

    def get_queryset(self):
        """Only allow teachers to edit their own assignments"""
        return Assignment.objects.filter(teacher=self.request.user.teacher)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["teacher"] = self.request.user.teacher
        return kwargs

    def form_valid(self, form):
        """Update assignment and handle validation"""
        try:
            assignment = AssignmentService.update_assignment(
                assignment_id=self.object.id, data=form.cleaned_data
            )

            messages.success(
                self.request, f'Assignment "{assignment.title}" updated successfully.'
            )
            return redirect("assignments:assignment_detail", pk=assignment.pk)

        except Exception as e:
            messages.error(self.request, f"Error updating assignment: {str(e)}")
            return self.form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["rubric_formset"] = RubricFormSet(instance=self.object)
        return context


class AssignmentDeleteView(TeacherMixin, DeleteView):
    """
    Delete assignment with confirmation
    """

    model = Assignment
    template_name = "assignments/assignment_confirm_delete.html"
    success_url = reverse_lazy("assignments:assignment_list")

    def get_queryset(self):
        """Only allow teachers to delete their own assignments"""
        return Assignment.objects.filter(teacher=self.request.user.teacher)

    def delete(self, request, *args, **kwargs):
        assignment = self.get_object()

        # Check if assignment has submissions
        if assignment.submissions.exists():
            messages.error(request, "Cannot delete assignment that has submissions.")
            return redirect("assignments:assignment_detail", pk=assignment.pk)

        messages.success(
            request, f'Assignment "{assignment.title}" deleted successfully.'
        )
        return super().delete(request, *args, **kwargs)


class AssignmentPublishView(TeacherMixin, View):
    """
    Publish an assignment
    """

    def post(self, request, pk):
        assignment = get_object_or_404(Assignment, pk=pk, teacher=request.user.teacher)

        try:
            AssignmentService.publish_assignment(assignment.id)
            messages.success(
                request, f'Assignment "{assignment.title}" published successfully.'
            )
        except Exception as e:
            messages.error(request, f"Error publishing assignment: {str(e)}")

        return redirect("assignments:assignment_detail", pk=assignment.pk)


class SubmissionCreateView(StudentMixin, CreateView):
    """
    Student submission creation
    """

    model = AssignmentSubmission
    form_class = AssignmentSubmissionForm
    template_name = "assignments/submission_form.html"

    def dispatch(self, request, *args, **kwargs):
        """Check if assignment accepts submissions"""
        self.assignment = get_object_or_404(
            Assignment,
            pk=kwargs["assignment_id"],
            class_id=request.user.student.current_class_id,
            status="published",
        )

        # Check if student already submitted
        if self.assignment.is_submitted_by_student(request.user.student):
            messages.info(request, "You have already submitted this assignment.")
            return redirect("assignments:assignment_detail", pk=self.assignment.pk)

        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["assignment"] = self.assignment
        kwargs["student"] = self.request.user.student
        return kwargs

    def form_valid(self, form):
        """Save submission"""
        try:
            submission = SubmissionService.create_submission(
                student=self.request.user.student,
                assignment_id=self.assignment.id,
                data=form.cleaned_data,
            )

            messages.success(self.request, "Assignment submitted successfully.")
            return redirect("assignments:assignment_detail", pk=self.assignment.pk)

        except Exception as e:
            messages.error(self.request, f"Error submitting assignment: {str(e)}")
            return self.form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["assignment"] = self.assignment
        return context


class SubmissionDetailView(LoginRequiredMixin, DetailView):
    """
    Detailed view of a submission
    """

    model = AssignmentSubmission
    template_name = "assignments/submission_detail.html"
    context_object_name = "submission"

    def get_queryset(self):
        """Filter submissions based on user role"""
        user = self.request.user

        if hasattr(user, "teacher"):
            # Teachers see submissions for their assignments
            return (
                AssignmentSubmission.objects.filter(assignment__teacher=user.teacher)
                .select_related("assignment", "student__user", "graded_by__user")
                .prefetch_related("rubric_grades__rubric")
            )
        elif hasattr(user, "student"):
            # Students see only their own submissions
            return (
                AssignmentSubmission.objects.filter(student=user.student)
                .select_related("assignment", "graded_by__user")
                .prefetch_related("rubric_grades__rubric")
            )
        elif hasattr(user, "parent"):
            # Parents see their children's submissions
            children = user.parent.children.all()
            return AssignmentSubmission.objects.filter(
                student__in=children
            ).select_related("assignment", "student__user", "graded_by__user")
        else:
            return AssignmentSubmission.objects.none()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        submission = self.object

        # Add grading form for teachers
        if (
            hasattr(self.request.user, "teacher")
            and submission.assignment.teacher == self.request.user.teacher
        ):
            context["grading_form"] = SubmissionGradingForm(instance=submission)

            # Add rubric grading if rubrics exist
            if submission.assignment.rubrics.exists():
                context["rubric_grades"] = submission.rubric_grades.select_related(
                    "rubric"
                )

        return context


class SubmissionGradeView(TeacherMixin, UpdateView):
    """
    Grade a student submission
    """

    model = AssignmentSubmission
    form_class = SubmissionGradingForm
    template_name = "assignments/submission_grade.html"

    def get_queryset(self):
        """Only allow teachers to grade their assignment submissions"""
        return AssignmentSubmission.objects.filter(
            assignment__teacher=self.request.user.teacher
        )

    def form_valid(self, form):
        """Process grading"""
        try:
            submission = GradingService.grade_submission(
                submission_id=self.object.id,
                grader=self.request.user.teacher,
                grading_data=form.cleaned_data,
            )

            messages.success(self.request, "Submission graded successfully.")
            return redirect("assignments:submission_detail", pk=submission.pk)

        except Exception as e:
            messages.error(self.request, f"Error grading submission: {str(e)}")
            return self.form_invalid(form)


class AssignmentDashboardView(LoginRequiredMixin, TemplateView):
    """
    Main assignment dashboard for different user roles
    """

    template_name = "assignments/dashboard.html"

    def get_template_names(self):
        """Return role-specific template"""
        user = self.request.user

        if hasattr(user, "teacher"):
            return ["assignments/dashboard_teacher.html"]
        elif hasattr(user, "student"):
            return ["assignments/dashboard_student.html"]
        elif hasattr(user, "parent"):
            return ["assignments/dashboard_parent.html"]
        else:
            return ["assignments/dashboard.html"]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        if hasattr(user, "teacher"):
            context.update(self._get_teacher_dashboard_data(user.teacher))
        elif hasattr(user, "student"):
            context.update(self._get_student_dashboard_data(user.student))
        elif hasattr(user, "parent"):
            context.update(self._get_parent_dashboard_data(user.parent))

        return context

    def _get_teacher_dashboard_data(self, teacher):
        """Get dashboard data for teachers"""
        try:
            # Get recent assignments
            recent_assignments = Assignment.objects.filter(teacher=teacher).order_by(
                "-created_at"
            )[:5]

            # Get pending grading
            pending_grading = AssignmentSubmission.objects.filter(
                assignment__teacher=teacher, status="submitted"
            ).select_related("assignment", "student__user")[:10]

            # Get upcoming deadlines
            upcoming_deadlines = DeadlineService.get_upcoming_deadlines(
                "teacher", teacher.id, 7
            )

            # Get analytics summary
            analytics = AssignmentAnalyticsService.get_teacher_analytics(teacher.id)

            return {
                "recent_assignments": recent_assignments,
                "pending_grading": pending_grading,
                "upcoming_deadlines": upcoming_deadlines,
                "analytics_summary": analytics,
            }
        except Exception as e:
            logger.error(f"Error getting teacher dashboard data: {str(e)}")
            return {}

    def _get_student_dashboard_data(self, student):
        """Get dashboard data for students"""
        try:
            # Get recent assignments
            class_assignments = Assignment.objects.filter(
                class_id=student.current_class_id, status="published"
            ).order_by("-created_at")[:5]

            # Get upcoming deadlines
            upcoming_deadlines = DeadlineService.get_upcoming_deadlines(
                "student", student.id, 7
            )

            # Get recent grades
            recent_grades = (
                AssignmentSubmission.objects.filter(student=student, status="graded")
                .select_related("assignment__subject")
                .order_by("-graded_at")[:5]
            )

            # Get performance analytics
            analytics = AssignmentAnalyticsService.get_student_performance_analytics(
                student.id
            )

            return {
                "recent_assignments": class_assignments,
                "upcoming_deadlines": upcoming_deadlines,
                "recent_grades": recent_grades,
                "performance_summary": analytics,
            }
        except Exception as e:
            logger.error(f"Error getting student dashboard data: {str(e)}")
            return {}

    def _get_parent_dashboard_data(self, parent):
        """Get dashboard data for parents"""
        try:
            children_data = []
            for child in parent.children.filter(status="active"):
                # Get child's recent assignments and grades
                assignments = Assignment.objects.filter(
                    class_id=child.current_class_id, status="published"
                ).count()

                recent_grades = AssignmentSubmission.objects.filter(
                    student=child, status="graded"
                ).order_by("-graded_at")[:3]

                children_data.append(
                    {
                        "child": child,
                        "total_assignments": assignments,
                        "recent_grades": recent_grades,
                    }
                )

            return {"children_data": children_data}
        except Exception as e:
            logger.error(f"Error getting parent dashboard data: {str(e)}")
            return {}


class AnalyticsDashboardView(LoginRequiredMixin, TemplateView):
    """
    Analytics dashboard for assignments
    """

    template_name = "assignments/analytics_dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        try:
            if hasattr(user, "teacher"):
                analytics = AssignmentAnalyticsService.get_teacher_analytics(
                    user.teacher.id
                )
                context["analytics"] = analytics
                context["role"] = "teacher"
            elif hasattr(user, "student"):
                analytics = (
                    AssignmentAnalyticsService.get_student_performance_analytics(
                        user.student.id
                    )
                )
                context["analytics"] = analytics
                context["role"] = "student"
            elif user.is_staff:
                analytics = AssignmentAnalyticsService.get_system_wide_analytics()
                context["analytics"] = analytics
                context["role"] = "admin"
        except Exception as e:
            logger.error(f"Error getting analytics data: {str(e)}")
            context["analytics"] = None

        return context


class PlagiarismCheckView(TeacherMixin, View):
    """
    Run plagiarism check on a submission
    """

    def post(self, request, pk):
        submission = get_object_or_404(
            AssignmentSubmission, pk=pk, assignment__teacher=request.user.teacher
        )

        try:
            result = PlagiarismService.check_submission_plagiarism(submission.id)

            if result["is_suspicious"]:
                messages.warning(
                    request,
                    f'High plagiarism score detected: {result["plagiarism_score"]}%',
                )
            else:
                messages.info(
                    request,
                    f'Plagiarism check completed. Score: {result["plagiarism_score"]}%',
                )
        except Exception as e:
            messages.error(request, f"Error checking plagiarism: {str(e)}")

        return redirect("assignments:submission_detail", pk=submission.pk)


class BulkGradeView(TeacherMixin, FormView):
    """
    Bulk grade submissions from CSV
    """

    form_class = BulkGradeForm
    template_name = "assignments/bulk_grade.html"

    def dispatch(self, request, *args, **kwargs):
        self.assignment = get_object_or_404(
            Assignment, pk=kwargs["assignment_id"], teacher=request.user.teacher
        )
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        """Process bulk grading CSV"""
        try:
            csv_file = form.cleaned_data["csv_file"]

            # Process CSV file here
            # This would parse the CSV and call GradingService.bulk_grade_submissions

            messages.success(self.request, "Bulk grading completed successfully.")
            return redirect("assignments:assignment_detail", pk=self.assignment.pk)

        except Exception as e:
            messages.error(self.request, f"Error in bulk grading: {str(e)}")
            return self.form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["assignment"] = self.assignment
        return context


class AssignmentSearchView(LoginRequiredMixin, ListView):
    """
    Search assignments across the system
    """

    model = Assignment
    template_name = "assignments/search_results.html"
    context_object_name = "assignments"
    paginate_by = 20

    def get_queryset(self):
        """Search assignments based on query"""
        form = AssignmentSearchForm(self.request.GET)
        queryset = Assignment.objects.select_related(
            "class_id__grade__section", "subject", "teacher__user"
        )

        # Apply role-based filtering
        user = self.request.user
        if hasattr(user, "teacher"):
            queryset = queryset.filter(teacher=user.teacher)
        elif hasattr(user, "student"):
            queryset = queryset.filter(
                class_id=user.student.current_class_id, status="published"
            )
        elif not user.is_staff:
            queryset = queryset.none()

        if form.is_valid():
            query = form.cleaned_data.get("query")
            if query:
                queryset = queryset.filter(
                    Q(title__icontains=query)
                    | Q(description__icontains=query)
                    | Q(subject__name__icontains=query)
                    | Q(teacher__user__first_name__icontains=query)
                    | Q(teacher__user__last_name__icontains=query)
                )

            # Apply other filters
            status = form.cleaned_data.get("status")
            if status:
                queryset = queryset.filter(status__in=status)

            subject = form.cleaned_data.get("subject")
            if subject:
                queryset = queryset.filter(subject=subject)

            difficulty = form.cleaned_data.get("difficulty")
            if difficulty:
                queryset = queryset.filter(difficulty_level=difficulty)

            due_from = form.cleaned_data.get("due_from")
            if due_from:
                queryset = queryset.filter(due_date__gte=due_from)

            due_to = form.cleaned_data.get("due_to")
            if due_to:
                queryset = queryset.filter(due_date__lte=due_to)

            overdue_only = form.cleaned_data.get("overdue_only")
            if overdue_only:
                queryset = queryset.filter(
                    status="published", due_date__lt=timezone.now()
                )

        return queryset.order_by("-created_at")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["search_form"] = AssignmentSearchForm(self.request.GET)
        context["query"] = self.request.GET.get("query", "")
        return context


# AJAX Views for dynamic content
class AssignmentInfoAjaxView(LoginRequiredMixin, View):
    """
    AJAX view for assignment information
    """

    def get(self, request, pk):
        try:
            assignment = Assignment.objects.select_related(
                "subject", "teacher__user"
            ).get(pk=pk)

            # Check permissions
            user = request.user
            if hasattr(user, "teacher"):
                if assignment.teacher != user.teacher:
                    return JsonResponse({"error": "Permission denied"}, status=403)
            elif hasattr(user, "student"):
                if assignment.class_id != user.student.current_class_id:
                    return JsonResponse({"error": "Permission denied"}, status=403)

            data = {
                "title": assignment.title,
                "description": assignment.description,
                "subject": assignment.subject.name,
                "teacher": assignment.teacher.user.get_full_name(),
                "due_date": assignment.due_date.isoformat(),
                "total_marks": assignment.total_marks,
                "status": assignment.status,
                "submission_count": assignment.submission_count,
                "is_overdue": assignment.is_overdue,
            }

            return JsonResponse(data)

        except Assignment.DoesNotExist:
            return JsonResponse({"error": "Assignment not found"}, status=404)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)


class SubmissionStatusAjaxView(LoginRequiredMixin, View):
    """
    AJAX view for submission status updates
    """

    def get(self, request, pk):
        try:
            submission = AssignmentSubmission.objects.select_related(
                "assignment", "student__user"
            ).get(pk=pk)

            # Check permissions
            user = request.user
            if hasattr(user, "teacher"):
                if submission.assignment.teacher != user.teacher:
                    return JsonResponse({"error": "Permission denied"}, status=403)
            elif hasattr(user, "student"):
                if submission.student != user.student:
                    return JsonResponse({"error": "Permission denied"}, status=403)

            data = {
                "status": submission.status,
                "marks_obtained": submission.marks_obtained,
                "percentage": (
                    float(submission.percentage) if submission.percentage else None
                ),
                "grade": submission.grade,
                "is_late": submission.is_late,
                "submission_date": submission.submission_date.isoformat(),
                "graded_at": (
                    submission.graded_at.isoformat() if submission.graded_at else None
                ),
            }

            return JsonResponse(data)

        except AssignmentSubmission.DoesNotExist:
            return JsonResponse({"error": "Submission not found"}, status=404)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)


# Additional view classes for other functionalities would be implemented here
# Following the same patterns:
# - Proper permission checking
# - Error handling
# - Context data preparation
# - Service layer usage
# - Success/error messaging


class StudentAssignmentListView(StudentMixin, ListView):
    """
    List view for student's assignments
    """

    model = Assignment
    template_name = "assignments/student_assignments.html"
    context_object_name = "assignments"
    paginate_by = 20

    def get_queryset(self):
        return (
            Assignment.objects.filter(
                class_id=self.request.user.student.current_class_id, status="published"
            )
            .select_related("subject", "teacher__user")
            .order_by("-created_at")
        )


class GradingDashboardView(TeacherMixin, TemplateView):
    """
    Dashboard for teacher grading activities
    """

    template_name = "assignments/grading_dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        teacher = self.request.user.teacher

        # Get pending submissions for grading
        pending_submissions = (
            AssignmentSubmission.objects.filter(
                assignment__teacher=teacher, status="submitted"
            )
            .select_related("assignment", "student__user")
            .order_by("-submission_date")
        )

        context["pending_submissions"] = pending_submissions
        context["grading_stats"] = GradingService.get_grading_analytics(teacher)

        return context


class OverdueAssignmentsView(LoginRequiredMixin, TemplateView):
    """
    View for overdue assignments management
    """

    template_name = "assignments/overdue_assignments.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        try:
            overdue_data = DeadlineService.get_overdue_assignments()
            context["overdue_data"] = overdue_data
        except Exception as e:
            logger.error(f"Error getting overdue assignments: {str(e)}")
            context["overdue_data"] = {}

        return context


class TeacherRequiredMixin(PermissionRequiredMixin):
    """Mixin to ensure only teachers can access the view."""

    permission_required = "assignments.teacher_access"

    def dispatch(self, request, *args, **kwargs):
        if not hasattr(request.user, "teacher"):
            raise PermissionDenied("Only teachers can access this page.")
        return super().dispatch(request, *args, **kwargs)


class StudentRequiredMixin(PermissionRequiredMixin):
    """Mixin to ensure only students can access the view."""

    permission_required = "assignments.student_access"

    def dispatch(self, request, *args, **kwargs):
        if not hasattr(request.user, "student"):
            raise PermissionDenied("Only students can access this page.")
        return super().dispatch(request, *args, **kwargs)


class ParentRequiredMixin(PermissionRequiredMixin):
    """Mixin to ensure only parents can access the view."""

    permission_required = "assignments.parent_access"

    def dispatch(self, request, *args, **kwargs):
        if not hasattr(request.user, "parent"):
            raise PermissionDenied("Only parents can access this page.")
        return super().dispatch(request, *args, **kwargs)


class AssignmentOwnerMixin:
    """Mixin to ensure user can only access their own assignments."""

    def get_queryset(self):
        queryset = super().get_queryset()
        if hasattr(self.request.user, "teacher"):
            return queryset.filter(teacher=self.request.user.teacher)
        return queryset.none()


# ================== CORE ASSIGNMENT MANAGEMENT VIEWS ==================


class AssignmentListView(LoginRequiredMixin, ListView):
    """List all assignments with filtering and pagination."""

    model = Assignment
    template_name = "assignments/assignment_list.html"
    context_object_name = "assignments"
    paginate_by = 20

    def get_queryset(self):
        queryset = Assignment.objects.all()

        if hasattr(self.request.user, "teacher"):
            queryset = queryset.filter(teacher=self.request.user.teacher)
        elif hasattr(self.request.user, "student"):
            queryset = queryset.filter(
                class_id=self.request.user.student.current_class_id
            )
        elif hasattr(self.request.user, "parent"):
            # Show assignments for parent's children
            student_classes = self.request.user.parent.students.values_list(
                "current_class_id", flat=True
            )
            queryset = queryset.filter(class_id__in=student_classes)

        # Apply filters
        status = self.request.GET.get("status")
        if status:
            queryset = queryset.filter(status=status)

        subject_id = self.request.GET.get("subject")
        if subject_id:
            queryset = queryset.filter(subject_id=subject_id)

        class_id = self.request.GET.get("class")
        if class_id:
            queryset = queryset.filter(class_id=class_id)

        return queryset.select_related("teacher", "subject", "class_id").order_by(
            "-assigned_date"
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["subjects"] = Subject.objects.all()
        context["classes"] = Class.objects.all()
        context["status_choices"] = Assignment.STATUS_CHOICES
        return context


class AssignmentCreateView(LoginRequiredMixin, TeacherRequiredMixin, CreateView):
    """Create new assignment."""

    model = Assignment
    form_class = AssignmentForm
    template_name = "assignments/assignment_create.html"
    success_url = reverse_lazy("assignments:assignment_list")

    def form_valid(self, form):
        form.instance.teacher = self.request.user.teacher
        messages.success(self.request, "Assignment created successfully!")
        return super().form_valid(form)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["teacher"] = self.request.user.teacher
        return kwargs


class AssignmentDetailView(LoginRequiredMixin, DetailView):
    """Display assignment details."""

    model = Assignment
    template_name = "assignments/assignment_detail.html"
    context_object_name = "assignment"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        assignment = self.object

        # Add submission statistics
        submissions = AssignmentSubmission.objects.filter(assignment=assignment)
        context["total_submissions"] = submissions.count()
        context["graded_submissions"] = submissions.filter(status="graded").count()
        context["pending_submissions"] = submissions.filter(status="submitted").count()

        # Add user-specific context
        if hasattr(self.request.user, "student"):
            try:
                context["user_submission"] = submissions.get(
                    student=self.request.user.student
                )
            except AssignmentSubmission.DoesNotExist:
                context["user_submission"] = None

        context["can_submit"] = (
            hasattr(self.request.user, "student")
            and assignment.status == "published"
            and assignment.due_date > timezone.now()
        )

        return context


class AssignmentUpdateView(
    LoginRequiredMixin, TeacherRequiredMixin, AssignmentOwnerMixin, UpdateView
):
    """Update assignment."""

    model = Assignment
    form_class = AssignmentForm
    template_name = "assignments/assignment_edit.html"

    def get_success_url(self):
        return reverse("assignments:assignment_detail", kwargs={"pk": self.object.pk})

    def form_valid(self, form):
        messages.success(self.request, "Assignment updated successfully!")
        return super().form_valid(form)


class AssignmentDeleteView(
    LoginRequiredMixin, TeacherRequiredMixin, AssignmentOwnerMixin, DeleteView
):
    """Delete assignment."""

    model = Assignment
    template_name = "assignments/assignment_delete.html"
    success_url = reverse_lazy("assignments:assignment_list")

    def delete(self, request, *args, **kwargs):
        messages.success(request, "Assignment deleted successfully!")
        return super().delete(request, *args, **kwargs)


class AssignmentPublishView(LoginRequiredMixin, TeacherRequiredMixin, View):
    """Publish assignment."""

    def post(self, request, pk):
        assignment = get_object_or_404(Assignment, pk=pk, teacher=request.user.teacher)
        assignment.status = "published"
        assignment.save()

        # Send notifications to students
        NotificationService.send_assignment_notification(assignment)

        messages.success(
            request, f'Assignment "{assignment.title}" has been published!'
        )
        return redirect("assignments:assignment_detail", pk=pk)


class AssignmentCloseView(LoginRequiredMixin, TeacherRequiredMixin, View):
    """Close assignment."""

    def post(self, request, pk):
        assignment = get_object_or_404(Assignment, pk=pk, teacher=request.user.teacher)
        assignment.status = "closed"
        assignment.save()

        messages.success(request, f'Assignment "{assignment.title}" has been closed!')
        return redirect("assignments:assignment_detail", pk=pk)


class AssignmentDuplicateView(LoginRequiredMixin, TeacherRequiredMixin, View):
    """Duplicate assignment."""

    def post(self, request, pk):
        original = get_object_or_404(Assignment, pk=pk, teacher=request.user.teacher)

        # Create duplicate
        duplicate = Assignment.objects.create(
            title=f"{original.title} (Copy)",
            description=original.description,
            teacher=original.teacher,
            subject=original.subject,
            class_id=original.class_id,
            term=original.term,
            total_marks=original.total_marks,
            submission_type=original.submission_type,
            status="draft",
        )

        messages.success(request, f"Assignment duplicated successfully!")
        return redirect("assignments:assignment_edit", pk=duplicate.pk)


# ================== ASSIGNMENT ANALYTICS VIEWS ==================


class AssignmentAnalyticsView(LoginRequiredMixin, TeacherRequiredMixin, DetailView):
    """Display assignment analytics."""

    model = Assignment
    template_name = "assignments/assignment_analytics.html"
    context_object_name = "assignment"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        assignment = self.object

        analytics_data = AnalyticsService.get_assignment_analytics(assignment)
        context.update(analytics_data)

        return context


class AssignmentAnalyticsExportView(LoginRequiredMixin, TeacherRequiredMixin, View):
    """Export assignment analytics to CSV."""

    def get(self, request, pk):
        assignment = get_object_or_404(Assignment, pk=pk, teacher=request.user.teacher)

        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = (
            f'attachment; filename="{assignment.title}_analytics.csv"'
        )

        writer = csv.writer(response)
        writer.writerow(["Student", "Submission Date", "Status", "Marks", "Grade"])

        submissions = AssignmentSubmission.objects.filter(
            assignment=assignment
        ).select_related("student__user")
        for submission in submissions:
            writer.writerow(
                [
                    submission.student.user.get_full_name(),
                    submission.submission_date,
                    submission.status,
                    submission.marks_obtained or "Not graded",
                    submission.grade or "Not graded",
                ]
            )

        return response


# ================== SUBMISSION MANAGEMENT VIEWS ==================


class SubmissionListView(LoginRequiredMixin, TeacherRequiredMixin, ListView):
    """List submissions for an assignment."""

    model = AssignmentSubmission
    template_name = "assignments/submission_list.html"
    context_object_name = "submissions"
    paginate_by = 30

    def get_queryset(self):
        assignment_id = self.kwargs["assignment_id"]
        self.assignment = get_object_or_404(
            Assignment, pk=assignment_id, teacher=self.request.user.teacher
        )
        return AssignmentSubmission.objects.filter(
            assignment=self.assignment
        ).select_related("student__user")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["assignment"] = self.assignment
        return context


class SubmissionCreateView(LoginRequiredMixin, StudentRequiredMixin, CreateView):
    """Student submission creation."""

    model = AssignmentSubmission
    form_class = AssignmentSubmissionForm
    template_name = "assignments/submission_create.html"

    def dispatch(self, request, *args, **kwargs):
        self.assignment = get_object_or_404(Assignment, pk=kwargs["assignment_id"])

        # Check if assignment is open for submission
        if self.assignment.status != "published":
            messages.error(request, "This assignment is not available for submission.")
            return redirect("assignments:assignment_detail", pk=self.assignment.pk)

        if self.assignment.due_date < timezone.now():
            messages.error(request, "Submission deadline has passed.")
            return redirect("assignments:assignment_detail", pk=self.assignment.pk)

        # Check if student already submitted
        if AssignmentSubmission.objects.filter(
            assignment=self.assignment, student=request.user.student
        ).exists():
            messages.error(request, "You have already submitted this assignment.")
            return redirect("assignments:assignment_detail", pk=self.assignment.pk)

        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.assignment = self.assignment
        form.instance.student = self.request.user.student
        form.instance.submission_date = timezone.now()
        form.instance.status = "submitted"

        messages.success(self.request, "Assignment submitted successfully!")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse(
            "assignments:assignment_detail", kwargs={"pk": self.assignment.pk}
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["assignment"] = self.assignment
        return context


class SubmissionDetailView(LoginRequiredMixin, DetailView):
    """Display submission details."""

    model = AssignmentSubmission
    template_name = "assignments/submission_detail.html"
    context_object_name = "submission"

    def dispatch(self, request, *args, **kwargs):
        submission = self.get_object()

        # Check permissions
        if hasattr(request.user, "teacher"):
            if submission.assignment.teacher != request.user.teacher:
                raise PermissionDenied()
        elif hasattr(request.user, "student"):
            if submission.student != request.user.student:
                raise PermissionDenied()
        elif hasattr(request.user, "parent"):
            if submission.student not in request.user.parent.students.all():
                raise PermissionDenied()
        else:
            raise PermissionDenied()

        return super().dispatch(request, *args, **kwargs)


class SubmissionUpdateView(LoginRequiredMixin, StudentRequiredMixin, UpdateView):
    """Update submission (before deadline)."""

    model = AssignmentSubmission
    form_class = AssignmentSubmissionForm
    template_name = "assignments/submission_edit.html"

    def dispatch(self, request, *args, **kwargs):
        submission = self.get_object()

        # Check if user owns this submission
        if submission.student != request.user.student:
            raise PermissionDenied()

        # Check if assignment is still open
        if submission.assignment.due_date < timezone.now():
            messages.error(request, "Cannot edit submission after deadline.")
            return redirect("assignments:submission_detail", pk=submission.pk)

        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        return reverse("assignments:submission_detail", kwargs={"pk": self.object.pk})


class SubmissionDeleteView(LoginRequiredMixin, StudentRequiredMixin, DeleteView):
    """Delete submission (student can delete their own submission)."""

    model = AssignmentSubmission
    template_name = "assignments/submission_delete.html"

    def dispatch(self, request, *args, **kwargs):
        submission = self.get_object()

        if submission.student != request.user.student:
            raise PermissionDenied()

        if submission.assignment.due_date < timezone.now():
            messages.error(request, "Cannot delete submission after deadline.")
            return redirect("assignments:submission_detail", pk=submission.pk)

        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        return reverse(
            "assignments:assignment_detail", kwargs={"pk": self.object.assignment.pk}
        )


class SubmissionDownloadView(LoginRequiredMixin, View):
    """Download submission file."""

    def get(self, request, pk):
        submission = get_object_or_404(AssignmentSubmission, pk=pk)

        # Check permissions
        if hasattr(request.user, "teacher"):
            if submission.assignment.teacher != request.user.teacher:
                raise PermissionDenied()
        elif hasattr(request.user, "student"):
            if submission.student != request.user.student:
                raise PermissionDenied()
        elif hasattr(request.user, "parent"):
            if submission.student not in request.user.parent.students.all():
                raise PermissionDenied()
        else:
            raise PermissionDenied()

        if submission.content and hasattr(submission.content, "path"):
            return FileResponse(open(submission.content.path, "rb"), as_attachment=True)
        else:
            raise Http404("File not found")


# ================== GRADING VIEWS ==================


class SubmissionGradeView(LoginRequiredMixin, TeacherRequiredMixin, UpdateView):
    """Grade individual submission."""

    model = AssignmentSubmission
    fields = ["marks_obtained", "remarks"]
    template_name = "assignments/submission_grade.html"

    def dispatch(self, request, *args, **kwargs):
        submission = self.get_object()
        if submission.assignment.teacher != request.user.teacher:
            raise PermissionDenied()
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        submission = form.instance
        submission.status = "graded"
        submission.graded_by = self.request.user.teacher
        submission.graded_at = timezone.now()

        # Calculate grade based on marks
        if submission.marks_obtained is not None:
            submission.grade = GradingService.calculate_grade(
                submission.marks_obtained, submission.assignment.total_marks
            )

        messages.success(self.request, "Submission graded successfully!")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse(
            "assignments:submission_list",
            kwargs={"assignment_id": self.object.assignment.pk},
        )


class BulkGradeView(LoginRequiredMixin, TeacherRequiredMixin, FormView):
    """Bulk grade submissions."""

    form_class = BulkGradeForm
    template_name = "assignments/bulk_grade.html"

    def dispatch(self, request, *args, **kwargs):
        assignment_id = kwargs["assignment_id"]
        self.assignment = get_object_or_404(
            Assignment, pk=assignment_id, teacher=request.user.teacher
        )
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["assignment"] = self.assignment
        context["submissions"] = AssignmentSubmission.objects.filter(
            assignment=self.assignment
        ).select_related("student__user")
        return context

    def form_valid(self, form):
        GradingService.bulk_grade_submissions(self.assignment, form.cleaned_data)
        messages.success(self.request, "Bulk grading completed successfully!")
        return redirect("assignments:submission_list", assignment_id=self.assignment.pk)


class GradingDashboardView(LoginRequiredMixin, TeacherRequiredMixin, TemplateView):
    """Teacher grading dashboard."""

    template_name = "assignments/grading_dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        teacher = self.request.user.teacher

        # Get grading statistics
        ungraded_submissions = AssignmentSubmission.objects.filter(
            assignment__teacher=teacher, status="submitted"
        ).count()

        context["ungraded_count"] = ungraded_submissions
        context["recent_submissions"] = (
            AssignmentSubmission.objects.filter(
                assignment__teacher=teacher, status="submitted"
            )
            .select_related("assignment", "student__user")
            .order_by("-submission_date")[:10]
        )

        return context


class GradingQueueView(LoginRequiredMixin, TeacherRequiredMixin, ListView):
    """Queue of submissions waiting for grading."""

    model = AssignmentSubmission
    template_name = "assignments/grading_queue.html"
    context_object_name = "submissions"
    paginate_by = 20

    def get_queryset(self):
        return (
            AssignmentSubmission.objects.filter(
                assignment__teacher=self.request.user.teacher, status="submitted"
            )
            .select_related("assignment", "student__user")
            .order_by("submission_date")
        )


# ================== PLACEHOLDER VIEWS FOR REMAINING FUNCTIONALITY ==================
# Note: The following views are basic implementations that would need to be expanded
# based on your specific requirements


class RubricManageView(LoginRequiredMixin, TeacherRequiredMixin, TemplateView):
    template_name = "assignments/rubric_manage.html"


class RubricCreateView(LoginRequiredMixin, TeacherRequiredMixin, CreateView):
    template_name = "assignments/rubric_create.html"
    fields = "__all__"


class RubricUpdateView(LoginRequiredMixin, TeacherRequiredMixin, UpdateView):
    template_name = "assignments/rubric_edit.html"
    fields = "__all__"


class RubricDeleteView(LoginRequiredMixin, TeacherRequiredMixin, DeleteView):
    template_name = "assignments/rubric_delete.html"


class PlagiarismCheckView(LoginRequiredMixin, TeacherRequiredMixin, TemplateView):
    template_name = "assignments/plagiarism_check.html"


class BatchPlagiarismCheckView(LoginRequiredMixin, TeacherRequiredMixin, TemplateView):
    template_name = "assignments/batch_plagiarism.html"


class PlagiarismReportsView(LoginRequiredMixin, TeacherRequiredMixin, TemplateView):
    template_name = "assignments/plagiarism_reports.html"


class AssignmentCommentsView(LoginRequiredMixin, TemplateView):
    template_name = "assignments/assignment_comments.html"


class CommentReplyView(LoginRequiredMixin, CreateView):
    template_name = "assignments/comment_reply.html"
    fields = "__all__"


class CommentEditView(LoginRequiredMixin, UpdateView):
    template_name = "assignments/comment_edit.html"
    fields = "__all__"


class CommentDeleteView(LoginRequiredMixin, DeleteView):
    template_name = "assignments/comment_delete.html"


class AssignmentDashboardView(LoginRequiredMixin, TemplateView):
    template_name = "assignments/dashboard.html"


class AnalyticsDashboardView(LoginRequiredMixin, TemplateView):
    template_name = "assignments/analytics_dashboard.html"


class TeacherAnalyticsView(LoginRequiredMixin, TeacherRequiredMixin, TemplateView):
    template_name = "assignments/teacher_analytics.html"


class StudentAnalyticsView(LoginRequiredMixin, StudentRequiredMixin, TemplateView):
    template_name = "assignments/student_analytics.html"


class ClassAnalyticsView(LoginRequiredMixin, TemplateView):
    template_name = "assignments/class_analytics.html"


class SystemAnalyticsView(LoginRequiredMixin, TemplateView):
    template_name = "assignments/system_analytics.html"


class ReportsView(LoginRequiredMixin, TemplateView):
    template_name = "assignments/reports.html"


class StudentReportView(LoginRequiredMixin, TemplateView):
    template_name = "assignments/student_report.html"


class TeacherReportView(LoginRequiredMixin, TemplateView):
    template_name = "assignments/teacher_report.html"


class ClassReportView(LoginRequiredMixin, TemplateView):
    template_name = "assignments/class_report.html"


class ReportExportView(LoginRequiredMixin, View):
    def get(self, request):
        # Implement report export logic
        return HttpResponse("Report exported")


class DeadlineManagementView(LoginRequiredMixin, TemplateView):
    template_name = "assignments/deadline_management.html"


class UpcomingDeadlinesView(LoginRequiredMixin, TemplateView):
    template_name = "assignments/upcoming_deadlines.html"


class OverdueAssignmentsView(LoginRequiredMixin, TemplateView):
    template_name = "assignments/overdue_assignments.html"


class DeadlineRemindersView(LoginRequiredMixin, TemplateView):
    template_name = "assignments/deadline_reminders.html"


class AssignmentExportView(LoginRequiredMixin, View):
    def get(self, request):
        # Implement assignment export logic
        return HttpResponse("Assignments exported")


class SubmissionExportView(LoginRequiredMixin, View):
    def get(self, request, assignment_id):
        # Implement submission export logic
        return HttpResponse("Submissions exported")


class AssignmentImportView(LoginRequiredMixin, TemplateView):
    template_name = "assignments/assignment_import.html"


class SubmissionImportView(LoginRequiredMixin, TemplateView):
    template_name = "assignments/submission_import.html"


class AssignmentCalendarView(LoginRequiredMixin, TemplateView):
    template_name = "assignments/assignment_calendar.html"


class AssignmentCalendarFeedView(LoginRequiredMixin, View):
    def get(self, request):
        # Return calendar feed
        return HttpResponse("Calendar feed")


class AssignmentSearchView(LoginRequiredMixin, ListView):
    model = Assignment
    template_name = "assignments/assignment_search.html"


class AdvancedSearchView(LoginRequiredMixin, TemplateView):
    template_name = "assignments/advanced_search.html"


class BulkPublishView(LoginRequiredMixin, TeacherRequiredMixin, View):
    def post(self, request):
        # Implement bulk publish logic
        return redirect("assignments:assignment_list")


class BulkCloseView(LoginRequiredMixin, TeacherRequiredMixin, View):
    def post(self, request):
        # Implement bulk close logic
        return redirect("assignments:assignment_list")


class BulkDeleteView(LoginRequiredMixin, TeacherRequiredMixin, View):
    def post(self, request):
        # Implement bulk delete logic
        return redirect("assignments:assignment_list")


class BulkExtendDeadlineView(LoginRequiredMixin, TeacherRequiredMixin, View):
    def post(self, request):
        # Implement bulk deadline extension logic
        return redirect("assignments:assignment_list")


class AssignmentTemplatesView(LoginRequiredMixin, TemplateView):
    template_name = "assignments/assignment_templates.html"


class SaveAsTemplateView(LoginRequiredMixin, View):
    def post(self, request, pk):
        # Implement save as template logic
        return redirect("assignments:assignment_detail", pk=pk)


class UseTemplateView(LoginRequiredMixin, View):
    def get(self, request, template_id):
        # Implement use template logic
        return redirect("assignments:assignment_create")


class ShareAssignmentView(LoginRequiredMixin, TemplateView):
    template_name = "assignments/share_assignment.html"


class StudentAssignmentListView(LoginRequiredMixin, StudentRequiredMixin, ListView):
    model = Assignment
    template_name = "assignments/student_assignments.html"

    def get_queryset(self):
        return Assignment.objects.filter(
            class_id=self.request.user.student.current_class_id, status="published"
        )


class StudentSubmissionListView(LoginRequiredMixin, StudentRequiredMixin, ListView):
    model = AssignmentSubmission
    template_name = "assignments/student_submissions.html"

    def get_queryset(self):
        return AssignmentSubmission.objects.filter(student=self.request.user.student)


class StudentGradesView(LoginRequiredMixin, StudentRequiredMixin, TemplateView):
    template_name = "assignments/student_grades.html"


class StudentPerformanceView(LoginRequiredMixin, StudentRequiredMixin, TemplateView):
    template_name = "assignments/student_performance.html"


class ParentOverviewView(LoginRequiredMixin, ParentRequiredMixin, TemplateView):
    template_name = "assignments/parent_overview.html"


class ParentChildAssignmentsView(LoginRequiredMixin, ParentRequiredMixin, ListView):
    model = Assignment
    template_name = "assignments/parent_child_assignments.html"


class AssignmentNotificationsView(LoginRequiredMixin, TemplateView):
    template_name = "assignments/notifications.html"


class NotificationSettingsView(LoginRequiredMixin, TemplateView):
    template_name = "assignments/notification_settings.html"


class AssignmentSettingsView(LoginRequiredMixin, TemplateView):
    template_name = "assignments/assignment_settings.html"


class FileTypeSettingsView(LoginRequiredMixin, TemplateView):
    template_name = "assignments/file_type_settings.html"


class GradingSettingsView(LoginRequiredMixin, TemplateView):
    template_name = "assignments/grading_settings.html"


# ================== AJAX VIEWS ==================


class AssignmentInfoAjaxView(LoginRequiredMixin, View):
    def get(self, request, pk):
        assignment = get_object_or_404(Assignment, pk=pk)
        data = {
            "title": assignment.title,
            "description": assignment.description,
            "due_date": (
                assignment.due_date.isoformat() if assignment.due_date else None
            ),
            "total_marks": assignment.total_marks,
            "status": assignment.status,
        }
        return JsonResponse(data)


class SubmissionStatusAjaxView(LoginRequiredMixin, View):
    def get(self, request, pk):
        submission = get_object_or_404(AssignmentSubmission, pk=pk)
        data = {
            "status": submission.status,
            "marks_obtained": submission.marks_obtained,
            "grade": submission.grade,
            "submission_date": (
                submission.submission_date.isoformat()
                if submission.submission_date
                else None
            ),
        }
        return JsonResponse(data)


class ClassStudentsAjaxView(LoginRequiredMixin, View):
    def get(self, request, class_id):
        students = Student.objects.filter(current_class_id=class_id).select_related(
            "user"
        )
        data = {
            "students": [
                {
                    "id": student.id,
                    "name": student.user.get_full_name(),
                    "roll_number": student.roll_number,
                }
                for student in students
            ]
        }
        return JsonResponse(data)


class SubjectAssignmentsAjaxView(LoginRequiredMixin, View):
    def get(self, request, subject_id):
        assignments = Assignment.objects.filter(subject_id=subject_id)
        data = {
            "assignments": [
                {
                    "id": assignment.id,
                    "title": assignment.title,
                    "due_date": (
                        assignment.due_date.isoformat() if assignment.due_date else None
                    ),
                    "status": assignment.status,
                }
                for assignment in assignments
            ]
        }
        return JsonResponse(data)


class AnalyticsChartDataAjaxView(LoginRequiredMixin, View):
    def get(self, request):
        # Return chart data for analytics
        data = {
            "labels": ["Jan", "Feb", "Mar", "Apr", "May"],
            "datasets": [
                {
                    "label": "Assignments",
                    "data": [10, 15, 12, 18, 20],
                }
            ],
        }
        return JsonResponse(data)
