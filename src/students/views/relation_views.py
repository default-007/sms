# students/views/relation_views.py
from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import (
    CreateView,
    UpdateView,
    DeleteView,
)
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib import messages
from django.http import JsonResponse

from ..models import Student, Parent, StudentParentRelation
from ..forms import StudentParentRelationForm
from ..services.parent_service import ParentService


class StudentParentRelationCreateView(
    LoginRequiredMixin, PermissionRequiredMixin, CreateView
):
    model = StudentParentRelation
    permission_required = "students.add_studentparentrelation"
    form_class = StudentParentRelationForm
    template_name = "students/relation_form.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()

        # Get student or parent from URL if provided
        student_id = self.kwargs.get("student_id")
        parent_id = self.kwargs.get("parent_id")

        if student_id:
            kwargs["student"] = get_object_or_404(Student, pk=student_id)

        if parent_id:
            kwargs["parent"] = get_object_or_404(Parent, pk=parent_id)

        return kwargs

    def get_success_url(self):
        # Determine where to redirect based on context
        if "student_id" in self.kwargs:
            return reverse_lazy(
                "student-detail", kwargs={"pk": self.kwargs["student_id"]}
            )
        elif "parent_id" in self.kwargs:
            return reverse_lazy(
                "parent-detail", kwargs={"pk": self.kwargs["parent_id"]}
            )
        else:
            return reverse_lazy("student-list")

    def form_valid(self, form):
        messages.success(
            self.request, "Student-parent relationship created successfully!"
        )
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Set title based on context
        if "student_id" in self.kwargs:
            student = get_object_or_404(Student, pk=self.kwargs["student_id"])
            context["title"] = f"Add Parent for {student.get_full_name()}"
        elif "parent_id" in self.kwargs:
            parent = get_object_or_404(Parent, pk=self.kwargs["parent_id"])
            context["title"] = f"Add Student for {parent.get_full_name()}"
        else:
            context["title"] = "Create Student-Parent Relationship"

        context["button_label"] = "Create Relationship"
        return context


class StudentParentRelationUpdateView(
    LoginRequiredMixin, PermissionRequiredMixin, UpdateView
):
    model = StudentParentRelation
    permission_required = "students.change_studentparentrelation"
    form_class = StudentParentRelationForm
    template_name = "students/relation_form.html"

    def get_success_url(self):
        # Redirect back to the detail page of either student or parent
        relation = self.get_object()

        # Default to student detail
        return reverse_lazy("student-detail", kwargs={"pk": relation.student.id})

    def form_valid(self, form):
        messages.success(
            self.request, "Student-parent relationship updated successfully!"
        )
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        relation = self.get_object()
        context["title"] = (
            f"Update Relationship: {relation.student.get_full_name()} - {relation.parent.get_full_name()}"
        )
        context["button_label"] = "Update Relationship"
        return context


class StudentParentRelationDeleteView(
    LoginRequiredMixin, PermissionRequiredMixin, DeleteView
):
    model = StudentParentRelation
    permission_required = "students.delete_studentparentrelation"
    template_name = "students/relation_confirm_delete.html"
    context_object_name = "relation"

    def get_success_url(self):
        # Determine where to redirect based on referrer
        relation = self.get_object()

        # Check the referrer URL to determine where to redirect
        referrer = self.request.META.get("HTTP_REFERER", "")

        if f"student/{relation.student.id}" in referrer:
            return reverse_lazy("student-detail", kwargs={"pk": relation.student.id})
        else:
            return reverse_lazy("parent-detail", kwargs={"pk": relation.parent.id})

    def delete(self, request, *args, **kwargs):
        relation = self.get_object()
        messages.success(
            request,
            f"Relationship between {relation.student.get_full_name()} and {relation.parent.get_full_name()} has been removed.",
        )
        return super().delete(request, *args, **kwargs)


class QuickLinkParentToStudentView(
    LoginRequiredMixin, PermissionRequiredMixin, CreateView
):
    """AJAX view for quickly linking a parent to a student"""

    model = StudentParentRelation
    permission_required = "students.add_studentparentrelation"
    http_method_names = ["post"]

    def post(self, request, *args, **kwargs):
        try:
            # Get student and parent IDs from POST data
            student_id = request.POST.get("student_id")
            parent_id = request.POST.get("parent_id")
            is_primary = request.POST.get("is_primary") == "true"

            if not student_id or not parent_id:
                return JsonResponse(
                    {
                        "success": False,
                        "error": "Both student_id and parent_id are required",
                    },
                    status=400,
                )

            # Get student and parent
            student = get_object_or_404(Student, pk=student_id)
            parent = get_object_or_404(Parent, pk=parent_id)

            # Create relationship
            relation = ParentService.link_parent_to_student(
                parent=parent, student=student, is_primary_contact=is_primary
            )

            # Return success response
            return JsonResponse(
                {
                    "success": True,
                    "relation_id": relation.id,
                    "student_name": student.get_full_name(),
                    "parent_name": parent.get_full_name(),
                    "is_primary": relation.is_primary_contact,
                }
            )
        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)}, status=500)
