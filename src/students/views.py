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

from .models import Student, Parent, StudentParentRelation
from .forms import StudentForm, ParentForm, StudentParentRelationForm


class StudentListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = Student
    permission_required = "students.view_student"
    context_object_name = "students"
    template_name = "students/student_list.html"
    paginate_by = 20

    def get_queryset(self):
        queryset = super().get_queryset().select_related("user", "current_class")

        # Apply search filter
        search_query = self.request.GET.get("search", "")
        if search_query:
            queryset = queryset.filter(
                Q(admission_number__icontains=search_query)
                | Q(user__first_name__icontains=search_query)
                | Q(user__last_name__icontains=search_query)
                | Q(user__email__icontains=search_query)
            )

        # Apply status filter
        status_filter = self.request.GET.get("status", "")
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        # Apply class filter
        class_filter = self.request.GET.get("class", "")
        if class_filter:
            queryset = queryset.filter(current_class_id=class_filter)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from src.courses.models import Class

        context["classes"] = Class.objects.select_related("grade", "section").all()
        context["status_choices"] = Student.STATUS_CHOICES
        return context


class StudentDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = Student
    permission_required = "students.view_student"
    context_object_name = "student"
    template_name = "students/student_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        student = self.get_object()

        # Get parents
        context["parents"] = Parent.objects.filter(
            parent_student_relations__student=student
        ).select_related("user")

        # Get primary parent
        context["primary_parent"] = Parent.objects.filter(
            parent_student_relations__student=student,
            parent_student_relations__is_primary_contact=True,
        ).first()

        return context


class StudentCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = Student
    permission_required = "students.add_student"
    form_class = StudentForm
    template_name = "students/student_form.html"
    success_url = reverse_lazy("student-list")

    def form_valid(self, form):
        messages.success(self.request, "Student created successfully.")
        return super().form_valid(form)


class StudentUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = Student
    permission_required = "students.change_student"
    form_class = StudentForm
    template_name = "students/student_form.html"

    def get_success_url(self):
        return reverse_lazy("student-detail", kwargs={"pk": self.object.pk})

    def form_valid(self, form):
        messages.success(self.request, "Student updated successfully.")
        return super().form_valid(form)


class StudentDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = Student
    permission_required = "students.delete_student"
    template_name = "students/student_confirm_delete.html"
    success_url = reverse_lazy("student-list")

    def delete(self, request, *args, **kwargs):
        messages.success(request, "Student deleted successfully.")
        return super().delete(request, *args, **kwargs)


class ParentListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = Parent
    permission_required = "students.view_parent"
    context_object_name = "parents"
    template_name = "students/parent_list.html"
    paginate_by = 20

    def get_queryset(self):
        queryset = super().get_queryset().select_related("user")

        # Apply search filter
        search_query = self.request.GET.get("search", "")
        if search_query:
            queryset = queryset.filter(
                Q(user__first_name__icontains=search_query)
                | Q(user__last_name__icontains=search_query)
                | Q(user__email__icontains=search_query)
                | Q(occupation__icontains=search_query)
            )

        # Apply relation filter
        relation_filter = self.request.GET.get("relation", "")
        if relation_filter:
            queryset = queryset.filter(relation_with_student=relation_filter)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["relation_choices"] = Parent.RELATION_CHOICES
        return context


class ParentDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = Parent
    permission_required = "students.view_parent"
    context_object_name = "parent"
    template_name = "students/parent_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        parent = self.get_object()

        # Get related students
        context["students"] = Student.objects.filter(
            student_parent_relations__parent=parent
        ).select_related("user", "current_class")

        return context


class ParentCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = Parent
    permission_required = "students.add_parent"
    form_class = ParentForm
    template_name = "students/parent_form.html"
    success_url = reverse_lazy("parent-list")

    def form_valid(self, form):
        messages.success(self.request, "Parent created successfully.")
        return super().form_valid(form)


class ParentUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = Parent
    permission_required = "students.change_parent"
    form_class = ParentForm
    template_name = "students/parent_form.html"

    def get_success_url(self):
        return reverse_lazy("parent-detail", kwargs={"pk": self.object.pk})

    def form_valid(self, form):
        messages.success(self.request, "Parent updated successfully.")
        return super().form_valid(form)


class StudentParentRelationCreateView(
    LoginRequiredMixin, PermissionRequiredMixin, CreateView
):
    model = StudentParentRelation
    permission_required = "students.add_studentparentrelation"
    form_class = StudentParentRelationForm
    template_name = "students/relation_form.html"

    def get_success_url(self):
        return reverse_lazy("student-detail", kwargs={"pk": self.object.student.pk})

    def form_valid(self, form):
        messages.success(
            self.request, "Student-parent relationship created successfully."
        )
        return super().form_valid(form)
