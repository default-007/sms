# src/teachers/views.py
from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import (
    ListView,
    DetailView,
    CreateView,
    UpdateView,
    DeleteView,
)
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib import messages
from django.db.models import Q
from django.utils import timezone

from .models import Teacher, TeacherClassAssignment, TeacherEvaluation
from .forms import TeacherForm, TeacherClassAssignmentForm, TeacherEvaluationForm
from .services import TeacherService, EvaluationService


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
