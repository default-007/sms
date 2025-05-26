from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib import messages
from django.views.generic import (
    ListView,
    DetailView,
    CreateView,
    UpdateView,
    DeleteView,
    TemplateView,
)
from django.urls import reverse_lazy
from django.http import JsonResponse, HttpResponse
from django.core.paginator import Paginator
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from .models import Subject, Syllabus, TopicProgress, SubjectAssignment
from .services import SyllabusService, CurriculumService, SubjectAnalyticsService
from academics.models import Grade, AcademicYear, Term


class SubjectListView(LoginRequiredMixin, ListView):
    """List view for subjects with filtering and search."""

    model = Subject
    template_name = "subjects/subject_list.html"
    context_object_name = "subjects"
    paginate_by = 20

    def get_queryset(self):
        """Filter queryset based on user permissions and search."""
        queryset = Subject.objects.filter(is_active=True).select_related("department")

        # Search functionality
        search_query = self.request.GET.get("search")
        if search_query:
            queryset = queryset.filter(
                Q(name__icontains=search_query)
                | Q(code__icontains=search_query)
                | Q(description__icontains=search_query)
            )

        # Department filter
        department_id = self.request.GET.get("department")
        if department_id:
            queryset = queryset.filter(department_id=department_id)

        # Grade filter
        grade_id = self.request.GET.get("grade")
        if grade_id:
            queryset = queryset.filter(
                Q(grade_level__contains=[int(grade_id)]) | Q(grade_level=[])
            )

        return queryset.order_by("department__name", "name")

    def get_context_data(self, **kwargs):
        """Add additional context data."""
        context = super().get_context_data(**kwargs)
        # Add filter options for template
        # Implementation will be added when HTML templates are created
        return context


class SubjectDetailView(LoginRequiredMixin, DetailView):
    """Detail view for a single subject."""

    model = Subject
    template_name = "subjects/subject_detail.html"
    context_object_name = "subject"

    def get_queryset(self):
        """Get subject with related data."""
        return Subject.objects.filter(is_active=True).select_related("department")


class SubjectCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    """Create view for new subjects."""

    model = Subject
    template_name = "subjects/subject_form.html"
    fields = [
        "name",
        "code",
        "description",
        "department",
        "credit_hours",
        "is_elective",
        "grade_level",
    ]
    permission_required = "subjects.add_subject"
    success_url = reverse_lazy("subjects:subject-list")

    def form_valid(self, form):
        """Add success message and save."""
        messages.success(self.request, _("Subject created successfully."))
        return super().form_valid(form)


class SubjectUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    """Update view for existing subjects."""

    model = Subject
    template_name = "subjects/subject_form.html"
    fields = [
        "name",
        "code",
        "description",
        "department",
        "credit_hours",
        "is_elective",
        "grade_level",
    ]
    permission_required = "subjects.change_subject"

    def get_success_url(self):
        """Return to subject detail page."""
        return reverse_lazy("subjects:subject-detail", kwargs={"pk": self.object.pk})

    def form_valid(self, form):
        """Add success message and save."""
        messages.success(self.request, _("Subject updated successfully."))
        return super().form_valid(form)


class SubjectDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    """Delete view for subjects (soft delete)."""

    model = Subject
    template_name = "subjects/subject_confirm_delete.html"
    permission_required = "subjects.delete_subject"
    success_url = reverse_lazy("subjects:subject-list")

    def delete(self, request, *args, **kwargs):
        """Perform soft delete."""
        self.object = self.get_object()
        self.object.is_active = False
        self.object.save()
        messages.success(request, _("Subject deleted successfully."))
        return redirect(self.success_url)


class SyllabusListView(LoginRequiredMixin, ListView):
    """List view for syllabi with filtering."""

    model = Syllabus
    template_name = "subjects/syllabus_list.html"
    context_object_name = "syllabi"
    paginate_by = 20

    def get_queryset(self):
        """Filter queryset based on user permissions and filters."""
        queryset = Syllabus.objects.filter(is_active=True).select_related(
            "subject", "grade", "academic_year", "term", "created_by"
        )

        # Filter by current user's assignments if they're a teacher
        if hasattr(self.request.user, "teacher_profile"):
            teacher = self.request.user.teacher_profile
            # Filter syllabi based on teacher assignments
            # Implementation depends on teacher assignment logic

        # Various filters
        filters = {}
        for field in ["subject", "grade", "academic_year", "term"]:
            value = self.request.GET.get(field)
            if value:
                filters[f"{field}_id"] = value

        if filters:
            queryset = queryset.filter(**filters)

        return queryset.order_by(
            "-academic_year__start_date", "term__term_number", "subject__name"
        )


class SyllabusDetailView(LoginRequiredMixin, DetailView):
    """Detail view for a single syllabus."""

    model = Syllabus
    template_name = "subjects/syllabus_detail.html"
    context_object_name = "syllabus"

    def get_queryset(self):
        """Get syllabus with related data."""
        return (
            Syllabus.objects.filter(is_active=True)
            .select_related(
                "subject",
                "grade",
                "academic_year",
                "term",
                "created_by",
                "last_updated_by",
            )
            .prefetch_related("topic_progress")
        )

    def get_context_data(self, **kwargs):
        """Add progress data to context."""
        context = super().get_context_data(**kwargs)

        # Get detailed progress information
        try:
            progress_data = SyllabusService.get_syllabus_progress(self.object.id)
            context["progress_data"] = progress_data
        except Exception as e:
            messages.error(self.request, f"Error loading progress data: {str(e)}")

        return context


class SyllabusCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    """Create view for new syllabi."""

    model = Syllabus
    template_name = "subjects/syllabus_form.html"
    fields = [
        "title",
        "description",
        "subject",
        "grade",
        "academic_year",
        "term",
        "content",
        "learning_objectives",
        "estimated_duration_hours",
        "difficulty_level",
        "prerequisites",
        "assessment_methods",
        "resources",
    ]
    permission_required = "subjects.add_syllabus"

    def form_valid(self, form):
        """Set created_by and last_updated_by fields."""
        form.instance.created_by = self.request.user
        form.instance.last_updated_by = self.request.user
        messages.success(self.request, _("Syllabus created successfully."))
        return super().form_valid(form)

    def get_success_url(self):
        """Return to syllabus detail page."""
        return reverse_lazy("subjects:syllabus-detail", kwargs={"pk": self.object.pk})


class SyllabusUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    """Update view for existing syllabi."""

    model = Syllabus
    template_name = "subjects/syllabus_form.html"
    fields = [
        "title",
        "description",
        "content",
        "learning_objectives",
        "estimated_duration_hours",
        "difficulty_level",
        "prerequisites",
        "assessment_methods",
        "resources",
    ]
    permission_required = "subjects.change_syllabus"

    def form_valid(self, form):
        """Set last_updated_by field."""
        form.instance.last_updated_by = self.request.user
        messages.success(self.request, _("Syllabus updated successfully."))
        return super().form_valid(form)

    def get_success_url(self):
        """Return to syllabus detail page."""
        return reverse_lazy("subjects:syllabus-detail", kwargs={"pk": self.object.pk})


class SyllabusDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    """Delete view for syllabi (soft delete)."""

    model = Syllabus
    template_name = "subjects/syllabus_confirm_delete.html"
    permission_required = "subjects.delete_syllabus"
    success_url = reverse_lazy("subjects:syllabus-list")

    def delete(self, request, *args, **kwargs):
        """Perform soft delete."""
        self.object = self.get_object()
        self.object.is_active = False
        self.object.save()
        messages.success(request, _("Syllabus deleted successfully."))
        return redirect(self.success_url)


class SyllabusProgressView(LoginRequiredMixin, TemplateView):
    """View for tracking syllabus progress."""

    template_name = "subjects/syllabus_progress.html"

    def get_context_data(self, **kwargs):
        """Get syllabus and progress data."""
        context = super().get_context_data(**kwargs)

        syllabus_id = kwargs.get("syllabus_id")
        try:
            syllabus = get_object_or_404(Syllabus, id=syllabus_id, is_active=True)
            progress_data = SyllabusService.get_syllabus_progress(syllabus_id)

            context["syllabus"] = syllabus
            context["progress_data"] = progress_data
        except Exception as e:
            messages.error(self.request, f"Error loading progress data: {str(e)}")

        return context


class MarkTopicCompleteView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    """View for marking topics as complete."""

    template_name = "subjects/mark_topic_complete.html"
    permission_required = "subjects.change_syllabus"

    def post(self, request, syllabus_id, topic_index):
        """Handle topic completion."""
        try:
            completion_data = {
                "hours_taught": request.POST.get("hours_taught", 0),
                "teaching_method": request.POST.get("teaching_method", ""),
                "notes": request.POST.get("notes", ""),
            }

            topic_progress = SyllabusService.mark_topic_completed(
                syllabus_id, topic_index, completion_data
            )

            messages.success(request, _("Topic marked as completed successfully."))

            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return JsonResponse(
                    {
                        "success": True,
                        "message": _("Topic marked as completed successfully."),
                    }
                )

        except Exception as e:
            messages.error(request, f"Error marking topic as complete: {str(e)}")

            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return JsonResponse({"success": False, "error": str(e)})

        return redirect("subjects:syllabus-progress", syllabus_id=syllabus_id)


class SubjectAssignmentListView(LoginRequiredMixin, ListView):
    """List view for subject assignments."""

    model = SubjectAssignment
    template_name = "subjects/assignment_list.html"
    context_object_name = "assignments"
    paginate_by = 20

    def get_queryset(self):
        """Filter assignments based on user role."""
        queryset = SubjectAssignment.objects.filter(is_active=True).select_related(
            "subject", "teacher__user", "class_assigned", "academic_year", "term"
        )

        # Filter by current user if they're a teacher
        if hasattr(self.request.user, "teacher_profile"):
            queryset = queryset.filter(teacher=self.request.user.teacher_profile)

        return queryset.order_by("-academic_year__start_date", "term__term_number")


class SubjectAssignmentCreateView(
    LoginRequiredMixin, PermissionRequiredMixin, CreateView
):
    """Create view for subject assignments."""

    model = SubjectAssignment
    template_name = "subjects/assignment_form.html"
    fields = [
        "subject",
        "teacher",
        "class_assigned",
        "academic_year",
        "term",
        "is_primary_teacher",
    ]
    permission_required = "subjects.add_subjectassignment"
    success_url = reverse_lazy("subjects:assignment-list")

    def form_valid(self, form):
        """Set assigned_by field."""
        form.instance.assigned_by = self.request.user
        messages.success(self.request, _("Subject assignment created successfully."))
        return super().form_valid(form)


class SubjectAssignmentDetailView(LoginRequiredMixin, DetailView):
    """Detail view for subject assignments."""

    model = SubjectAssignment
    template_name = "subjects/assignment_detail.html"
    context_object_name = "assignment"


class SubjectAssignmentUpdateView(
    LoginRequiredMixin, PermissionRequiredMixin, UpdateView
):
    """Update view for subject assignments."""

    model = SubjectAssignment
    template_name = "subjects/assignment_form.html"
    fields = ["teacher", "is_primary_teacher"]
    permission_required = "subjects.change_subjectassignment"

    def get_success_url(self):
        """Return to assignment detail page."""
        return reverse_lazy("subjects:assignment-detail", kwargs={"pk": self.object.pk})


class CurriculumAnalyticsView(LoginRequiredMixin, TemplateView):
    """View for curriculum analytics dashboard."""

    template_name = "subjects/curriculum_analytics.html"

    def get_context_data(self, **kwargs):
        """Get analytics data for the dashboard."""
        context = super().get_context_data(**kwargs)

        # Get current academic year (this should be improved to get actual current year)
        try:
            current_year = AcademicYear.objects.filter(is_current=True).first()
            if current_year:
                analytics_data = CurriculumService.get_curriculum_analytics(
                    current_year.id
                )
                context["analytics_data"] = analytics_data
                context["current_year"] = current_year
        except Exception as e:
            messages.error(self.request, f"Error loading analytics: {str(e)}")

        return context


class CurriculumReportView(LoginRequiredMixin, TemplateView):
    """View for curriculum reports."""

    template_name = "subjects/curriculum_report.html"

    def get_context_data(self, **kwargs):
        """Get report data."""
        context = super().get_context_data(**kwargs)
        # Implementation for curriculum reports
        return context


class TeacherWorkloadReportView(LoginRequiredMixin, TemplateView):
    """View for teacher workload reports."""

    template_name = "subjects/teacher_workload_report.html"

    def get_context_data(self, **kwargs):
        """Get workload report data."""
        context = super().get_context_data(**kwargs)
        # Implementation for teacher workload reports
        return context


class GradeOverviewView(LoginRequiredMixin, TemplateView):
    """View for grade-level curriculum overview."""

    template_name = "subjects/grade_overview.html"

    def get_context_data(self, **kwargs):
        """Get grade overview data."""
        context = super().get_context_data(**kwargs)

        grade_id = kwargs.get("grade_id")
        academic_year_id = self.request.GET.get("academic_year_id")
        term_id = self.request.GET.get("term_id")

        if grade_id and academic_year_id:
            try:
                overview_data = SyllabusService.get_grade_syllabus_overview(
                    grade_id, academic_year_id, term_id
                )
                context["overview_data"] = overview_data
                context["grade"] = get_object_or_404(Grade, id=grade_id)
            except Exception as e:
                messages.error(self.request, f"Error loading overview: {str(e)}")

        return context


class BulkImportSubjectsView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    """View for bulk importing subjects."""

    template_name = "subjects/bulk_import_subjects.html"
    permission_required = "subjects.add_subject"

    def post(self, request, *args, **kwargs):
        """Handle bulk import."""
        # Implementation for bulk import from CSV/Excel
        # This would process uploaded files and create subjects
        messages.info(request, _("Bulk import functionality will be implemented."))
        return self.get(request, *args, **kwargs)


class BulkCreateSyllabiView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    """View for bulk creating syllabi for a term."""

    template_name = "subjects/bulk_create_syllabi.html"
    permission_required = "subjects.add_syllabus"

    def post(self, request, term_id, *args, **kwargs):
        """Handle bulk syllabus creation."""
        try:
            template_data = {
                "description": request.POST.get("description", ""),
                "difficulty_level": request.POST.get(
                    "difficulty_level", "intermediate"
                ),
                "estimated_duration_hours": int(
                    request.POST.get("estimated_duration_hours", 0)
                ),
            }

            created_syllabi = SyllabusService.bulk_create_syllabi_for_term(
                term_id, template_data, request.user.id
            )

            messages.success(
                request,
                _("Successfully created {} syllabi.").format(len(created_syllabi)),
            )

        except Exception as e:
            messages.error(request, f"Error creating syllabi: {str(e)}")

        return redirect("subjects:syllabus-list")


class SubjectsDashboardView(LoginRequiredMixin, TemplateView):
    """Main dashboard for subjects module."""

    template_name = "subjects/dashboard.html"

    def get_context_data(self, **kwargs):
        """Get dashboard data."""
        context = super().get_context_data(**kwargs)

        # Get current academic year and term
        try:
            current_year = AcademicYear.objects.filter(is_current=True).first()
            if current_year:
                current_term = Term.objects.filter(
                    academic_year=current_year, is_current=True
                ).first()

                context["current_year"] = current_year
                context["current_term"] = current_term

                # Get summary statistics
                # Implementation depends on specific dashboard requirements

        except Exception as e:
            messages.error(self.request, f"Error loading dashboard: {str(e)}")

        return context


class CurriculumStructureView(LoginRequiredMixin, TemplateView):
    """View for displaying curriculum structure."""

    template_name = "subjects/curriculum_structure.html"

    def get_context_data(self, **kwargs):
        """Get curriculum structure data."""
        context = super().get_context_data(**kwargs)

        academic_year_id = self.request.GET.get("academic_year_id")
        if academic_year_id:
            try:
                structure_data = CurriculumService.get_curriculum_structure(
                    academic_year_id
                )
                context["structure_data"] = structure_data
                context["academic_year"] = get_object_or_404(
                    AcademicYear, id=academic_year_id
                )
            except Exception as e:
                messages.error(self.request, f"Error loading structure: {str(e)}")

        return context
