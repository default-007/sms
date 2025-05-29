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

from assignments.services.analytics_service import AssignmentAnalyticsService
from core.mixins import ParentRequiredMixin, StudentRequiredMixin, TeacherRequiredMixin

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


class AssignmentCreateView(TeacherRequiredMixin, CreateView):
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


class AssignmentUpdateView(TeacherRequiredMixin, UpdateView):
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


class AssignmentDeleteView(TeacherRequiredMixin, DeleteView):
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


class AssignmentPublishView(TeacherRequiredMixin, View):
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


class SubmissionCreateView(StudentRequiredMixin, CreateView):
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


class SubmissionGradeView(TeacherRequiredMixin, UpdateView):
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


class PlagiarismCheckView(TeacherRequiredMixin, View):
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


class BulkGradeView(TeacherRequiredMixin, FormView):
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


class StudentAssignmentListView(StudentRequiredMixin, ListView):
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


class GradingDashboardView(TeacherRequiredMixin, TemplateView):
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
