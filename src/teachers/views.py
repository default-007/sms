# src/teachers/views.py
from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import (
    ListView,
    DetailView,
    CreateView,
    UpdateView,
    DeleteView,
    TemplateView,
)
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib import messages
from django.db.models import Q, Count, Avg, Sum
from django.http import HttpResponse
from django.utils import timezone

from src.courses.models import AcademicYear
from .models import Teacher, TeacherClassAssignment, TeacherEvaluation
from .forms import TeacherForm, TeacherClassAssignmentForm, TeacherEvaluationForm
from .services import TeacherService, EvaluationService, TimetableService


class TeacherListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = Teacher
    permission_required = "teachers.view_teacher"
    context_object_name = "teachers"
    template_name = "teacher_list.html"
    paginate_by = 20

    def get_queryset(self):
        queryset = super().get_queryset().select_related("user", "department")

        # Apply search filter
        search_query = self.request.GET.get("search", "")
        if search_query:
            queryset = queryset.filter(
                Q(employee_id__icontains=search_query)
                | Q(user__first_name__icontains=search_query)
                | Q(user__last_name__icontains=search_query)
                | Q(user__email__icontains=search_query)
                | Q(position__icontains=search_query)
            )

        # Apply status filter
        status_filter = self.request.GET.get("status", "")
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        # Apply department filter
        department_filter = self.request.GET.get("department", "")
        if department_filter:
            queryset = queryset.filter(department_id=department_filter)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from src.courses.models import Department

        context["departments"] = Department.objects.all()
        context["status_choices"] = Teacher.STATUS_CHOICES
        return context


class TeacherDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = Teacher
    permission_required = "teachers.view_teacher"
    context_object_name = "teacher"
    template_name = "teachers/teacher_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        teacher = self.get_object()

        # Get class assignments
        context["class_assignments"] = TeacherClassAssignment.objects.filter(
            teacher=teacher
        ).select_related("class_instance", "subject", "academic_year")

        # Get timetable for current teacher
        from src.courses.services.timetable_service import TimetableService

        context["timetable"] = TimetableService.get_teacher_timetable(teacher=teacher)

        # Get evaluations if user has permission
        if self.request.user.has_perm("teachers.view_teacherevaluation"):
            context["evaluations"] = EvaluationService.get_evaluations_by_teacher(
                teacher
            )
            context["performance"] = TeacherService.calculate_teacher_performance(
                teacher
            )

        return context


class TeacherCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = Teacher
    permission_required = "teachers.add_teacher"
    form_class = TeacherForm
    template_name = "teachers/teacher_form.html"
    success_url = reverse_lazy("teacher-list")

    def form_valid(self, form):
        messages.success(self.request, "Teacher created successfully.")
        return super().form_valid(form)


class TeacherUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = Teacher
    permission_required = "teachers.change_teacher"
    form_class = TeacherForm
    template_name = "teachers/teacher_form.html"

    def get_success_url(self):
        return reverse_lazy("teacher-detail", kwargs={"pk": self.object.pk})

    def form_valid(self, form):
        messages.success(self.request, "Teacher updated successfully.")
        return super().form_valid(form)


class TeacherDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = Teacher
    permission_required = "teachers.delete_teacher"
    template_name = "teachers/teacher_confirm_delete.html"
    success_url = reverse_lazy("teacher-list")

    def delete(self, request, *args, **kwargs):
        messages.success(request, "Teacher deleted successfully.")
        return super().delete(request, *args, **kwargs)


class TeacherClassAssignmentCreateView(
    LoginRequiredMixin, PermissionRequiredMixin, CreateView
):
    model = TeacherClassAssignment
    permission_required = "teachers.assign_classes"
    form_class = TeacherClassAssignmentForm
    template_name = "teachers/assignment_form.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        teacher_id = self.kwargs.get("teacher_id")
        if teacher_id:
            context["teacher"] = get_object_or_404(Teacher, pk=teacher_id)
        return context

    def get_initial(self):
        initial = super().get_initial()
        teacher_id = self.kwargs.get("teacher_id")
        if teacher_id:
            initial["teacher"] = teacher_id
        return initial

    def get_success_url(self):
        teacher_id = self.object.teacher.id
        return reverse_lazy("teacher-detail", kwargs={"pk": teacher_id})

    def form_valid(self, form):
        messages.success(self.request, "Class assignment created successfully.")
        return super().form_valid(form)


class TeacherEvaluationCreateView(
    LoginRequiredMixin, PermissionRequiredMixin, CreateView
):
    model = TeacherEvaluation
    permission_required = "teachers.add_teacherevaluation"
    form_class = TeacherEvaluationForm
    template_name = "teachers/evaluation_form.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        teacher_id = self.kwargs.get("teacher_id")
        if teacher_id:
            context["teacher"] = get_object_or_404(Teacher, pk=teacher_id)
        return context

    def get_initial(self):
        initial = super().get_initial()
        teacher_id = self.kwargs.get("teacher_id")
        if teacher_id:
            initial["teacher"] = teacher_id
            initial["evaluation_date"] = timezone.now().date()
        return initial

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        form.instance.evaluator = self.request.user
        messages.success(self.request, "Teacher evaluation recorded successfully.")
        return super().form_valid(form)

    def get_success_url(self):
        teacher_id = self.object.teacher.id
        return reverse_lazy("teacher-detail", kwargs={"pk": teacher_id})


class TeacherTimetableView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = Teacher
    permission_required = "teachers.view_teacher"
    context_object_name = "teacher"
    template_name = "teachers/teacher_timetable.html"
    pk_url_kwarg = "teacher_id"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        teacher = self.get_object()

        # Get current academic year
        current_academic_year = AcademicYear.objects.filter(is_current=True).first()

        # Get timetable for the teacher
        from src.courses.services.timetable_service import (
            TimetableService as CourseTimetableService,
        )

        timetable = CourseTimetableService.get_teacher_timetable(
            teacher=teacher, academic_year=current_academic_year
        )

        context["timetable"] = timetable
        context["current_academic_year"] = current_academic_year

        return context


class TeacherTimetablePDFView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = Teacher
    permission_required = "teachers.view_teacher"
    pk_url_kwarg = "teacher_id"

    def get(self, request, *args, **kwargs):
        teacher = self.get_object()

        # Get current academic year
        current_academic_year = AcademicYear.objects.filter(is_current=True).first()

        # Generate PDF response
        return TimetableService.generate_timetable_pdf(
            teacher=teacher, academic_year=current_academic_year
        )


class TeacherDashboardView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    template_name = "teachers/teacher_dashboard.html"
    permission_required = "teachers.view_teacher"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get summary statistics
        context["total_teachers"] = Teacher.objects.count()
        context["active_teachers"] = Teacher.objects.filter(status="Active").count()
        context["on_leave_teachers"] = Teacher.objects.filter(status="On Leave").count()
        context["departments"] = (
            Teacher.objects.values("department__name")
            .annotate(count=Count("id"))
            .order_by("-count")
        )

        # Get recent evaluations
        context["recent_evaluations"] = TeacherEvaluation.objects.select_related(
            "teacher", "teacher__user", "evaluator"
        ).order_by("-evaluation_date")[:5]

        # Get average score by department
        context["department_scores"] = (
            TeacherEvaluation.objects.values("teacher__department__name")
            .annotate(avg_score=Avg("score"), count=Count("id"))
            .order_by("-avg_score")
        )

        # Get current academic year
        context["current_academic_year"] = AcademicYear.objects.filter(
            is_current=True
        ).first()

        # For charts
        departments = []
        dept_counts = []

        for dept in context["departments"]:
            departments.append(dept["department__name"] or "Unassigned")
            dept_counts.append(dept["count"])

        context["chart_departments"] = departments
        context["chart_dept_counts"] = dept_counts

        return context


class TeacherStatisticsView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    template_name = "teachers/teacher_statistics.html"
    permission_required = "teachers.view_teacher"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Basic statistics
        context["total_teachers"] = Teacher.objects.count()
        context["avg_experience"] = Teacher.objects.aggregate(Avg("experience_years"))[
            "experience_years__avg"
        ]
        context["avg_salary"] = Teacher.objects.aggregate(Avg("salary"))["salary__avg"]

        # Teachers by contract type
        context["contract_types"] = (
            Teacher.objects.values("contract_type")
            .annotate(count=Count("id"))
            .order_by("contract_type")
        )

        # Teachers by status
        context["status_counts"] = (
            Teacher.objects.values("status")
            .annotate(count=Count("id"))
            .order_by("status")
        )

        # Experience distribution (0-2, 2-5, 5-10, 10+ years)
        context["experience_distribution"] = [
            {
                "range": "0-2 years",
                "count": Teacher.objects.filter(experience_years__lt=2).count(),
            },
            {
                "range": "2-5 years",
                "count": Teacher.objects.filter(
                    experience_years__gte=2, experience_years__lt=5
                ).count(),
            },
            {
                "range": "5-10 years",
                "count": Teacher.objects.filter(
                    experience_years__gte=5, experience_years__lt=10
                ).count(),
            },
            {
                "range": "10+ years",
                "count": Teacher.objects.filter(experience_years__gte=10).count(),
            },
        ]

        # Evaluation scores distribution
        context["evaluation_distribution"] = [
            {
                "range": "Excellent (90-100%)",
                "count": TeacherEvaluation.objects.filter(score__gte=90).count(),
            },
            {
                "range": "Good (80-89%)",
                "count": TeacherEvaluation.objects.filter(
                    score__gte=80, score__lt=90
                ).count(),
            },
            {
                "range": "Average (70-79%)",
                "count": TeacherEvaluation.objects.filter(
                    score__gte=70, score__lt=80
                ).count(),
            },
            {
                "range": "Below Average (60-69%)",
                "count": TeacherEvaluation.objects.filter(
                    score__gte=60, score__lt=70
                ).count(),
            },
            {
                "range": "Poor (Below 60%)",
                "count": TeacherEvaluation.objects.filter(score__lt=60).count(),
            },
        ]

        return context
