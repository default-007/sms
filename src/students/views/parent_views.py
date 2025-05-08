# students/views/parent_views.py
from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import (
    ListView,
    DetailView,
    CreateView,
    UpdateView,
    DeleteView,
)
from django.urls import reverse_lazy, reverse
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib import messages
from django.db.models import Q, Count

from ..models import Student, Parent, StudentParentRelation
from ..forms import ParentForm
from ..services.parent_service import ParentService


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
                | Q(user__phone_number__icontains=search_query)
                | Q(occupation__icontains=search_query)
            )

        # Apply relation filter
        relation_filter = self.request.GET.get("relation", "")
        if relation_filter:
            queryset = queryset.filter(relation_with_student=relation_filter)

        # Annotate with student count
        queryset = queryset.annotate(student_count=Count("parent_student_relations"))

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["relation_choices"] = Parent.RELATION_CHOICES

        # Pass current filters to template
        context["current_filters"] = {
            "search": self.request.GET.get("search", ""),
            "relation": self.request.GET.get("relation", ""),
        }

        return context


class ParentDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = Parent
    permission_required = "students.view_parent"
    context_object_name = "parent"
    template_name = "students/parent_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        parent = self.get_object()

        # Get related students with their relations
        student_relations = StudentParentRelation.objects.filter(
            parent=parent
        ).select_related("student", "student__user", "student__current_class")

        context["student_relations"] = student_relations

        # Get all available students for potential linking
        context["available_students"] = (
            Student.objects.filter(status="Active")
            .exclude(id__in=[rel.student.id for rel in student_relations])
            .select_related("user")[:10]
        )  # Limit to 10 for performance

        return context


class ParentCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = Parent
    permission_required = "students.add_parent"
    form_class = ParentForm
    template_name = "students/parent_form.html"
    success_url = reverse_lazy("parent-list")

    def form_valid(self, form):
        messages.success(self.request, "Parent created successfully!")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Add New Parent"
        context["button_label"] = "Create Parent"
        return context


class ParentUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = Parent
    permission_required = "students.change_parent"
    form_class = ParentForm
    template_name = "students/parent_form.html"

    def get_success_url(self):
        return reverse_lazy("parent-detail", kwargs={"pk": self.object.pk})

    def form_valid(self, form):
        messages.success(self.request, "Parent updated successfully!")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = f"Edit Parent: {self.object.get_full_name()}"
        context["button_label"] = "Update Parent"
        return context


class ParentDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = Parent
    permission_required = "students.delete_parent"
    template_name = "students/parent_confirm_delete.html"
    success_url = reverse_lazy("parent-list")
    context_object_name = "parent"

    def delete(self, request, *args, **kwargs):
        parent = self.get_object()
        messages.success(
            request, f"Parent '{parent.get_full_name()}' has been deleted successfully!"
        )
        return super().delete(request, *args, **kwargs)
