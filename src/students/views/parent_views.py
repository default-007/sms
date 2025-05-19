# students/views/parent_views.py
from django.shortcuts import get_object_or_404, redirect
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
from django.db.models import Q, Count, Prefetch
from django.http import JsonResponse
from django.core.cache import cache
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page

from ..models import Student, Parent, StudentParentRelation
from ..forms import ParentForm
from ..services.parent_service import ParentService


class ParentListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = Parent
    permission_required = "students.view_parent"
    context_object_name = "parents"
    template_name = "students/parent_list.html"
    paginate_by = 25

    def get_queryset(self):
        queryset = Parent.objects.with_related().annotate(
            student_count=Count("parent_student_relations")
        )

        # Apply search filter
        search_query = self.request.GET.get("search", "")
        if search_query:
            queryset = queryset.search(search_query)

        # Apply filters
        relation_filter = self.request.GET.get("relation", "")
        if relation_filter:
            queryset = queryset.filter(relation_with_student=relation_filter)

        emergency_filter = self.request.GET.get("emergency_contact", "")
        if emergency_filter:
            queryset = queryset.filter(emergency_contact=emergency_filter == "true")

        return queryset.order_by("user__first_name", "user__last_name")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["relation_choices"] = Parent.RELATION_CHOICES
        context["current_filters"] = {
            "search": self.request.GET.get("search", ""),
            "relation": self.request.GET.get("relation", ""),
            "emergency_contact": self.request.GET.get("emergency_contact", ""),
        }

        # Add statistics
        total_parents = Parent.objects.count()
        context["statistics"] = {
            "total_parents": total_parents,
            "fathers": Parent.objects.filter(relation_with_student="Father").count(),
            "mothers": Parent.objects.filter(relation_with_student="Mother").count(),
            "guardians": Parent.objects.filter(
                relation_with_student="Guardian"
            ).count(),
            "emergency_contacts": Parent.objects.filter(emergency_contact=True).count(),
            "parents_with_multiple_children": Parent.objects.annotate(
                child_count=Count("parent_student_relations")
            )
            .filter(child_count__gt=1)
            .count(),
        }

        return context


@method_decorator(cache_page(300), name="get")  # Cache for 5 minutes
class ParentDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = Parent
    permission_required = "students.view_parent"
    context_object_name = "parent"
    template_name = "students/parent_detail.html"

    def get_queryset(self):
        return Parent.objects.select_related("user").prefetch_related(
            Prefetch(
                "parent_student_relations",
                queryset=StudentParentRelation.objects.select_related(
                    "student__user",
                    "student__current_class__grade",
                    "student__current_class__section",
                ),
            )
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        parent = self.get_object()

        # Get student relations with detailed info
        student_relations = parent.parent_student_relations.all()
        context["student_relations"] = student_relations

        # Get available students for quick linking
        existing_student_ids = [rel.student.id for rel in student_relations]
        context["available_students"] = (
            Student.objects.filter(status="Active")
            .exclude(id__in=existing_student_ids)
            .with_related()[:10]
        )

        # Get family statistics
        context["family_stats"] = {
            "total_children": student_relations.count(),
            "active_children": student_relations.filter(
                student__status="Active"
            ).count(),
            "primary_contacts": student_relations.filter(
                is_primary_contact=True
            ).count(),
            "financial_responsibility": student_relations.filter(
                financial_responsibility=True
            ).count(),
        }

        return context


class ParentCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = Parent
    permission_required = "students.add_parent"
    form_class = ParentForm
    template_name = "students/parent_form.html"
    success_url = reverse_lazy("students:parent-list")

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
        return reverse_lazy("students:parent-detail", kwargs={"pk": self.object.pk})

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
    success_url = reverse_lazy("students:parent-list")
    context_object_name = "parent"

    def delete(self, request, *args, **kwargs):
        parent = self.get_object()

        # Check if parent has students
        if parent.parent_student_relations.exists():
            messages.error(
                request,
                f"Cannot delete parent '{parent.get_full_name()}' as they have linked students. "
                "Please remove all student relationships first.",
            )
            return redirect("students:parent-detail", pk=parent.pk)

        messages.success(
            request, f"Parent '{parent.get_full_name()}' has been deleted successfully!"
        )
        return super().delete(request, *args, **kwargs)


class ParentAutocompleteView(LoginRequiredMixin, ListView):
    """AJAX autocomplete for parents"""

    def get(self, request, *args, **kwargs):
        query = request.GET.get("q", "")
        parents = Parent.objects.filter(
            Q(user__first_name__icontains=query)
            | Q(user__last_name__icontains=query)
            | Q(user__email__icontains=query)
        ).select_related("user")[:10]

        results = [
            {
                "id": str(parent.id),
                "text": f"{parent.get_full_name()} ({parent.relation_with_student})",
                "email": parent.user.email,
                "phone": parent.user.phone_number or "",
                "relation": parent.relation_with_student,
            }
            for parent in parents
        ]

        return JsonResponse({"results": results})


class ParentStudentsView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    """AJAX view to get parent's students"""

    model = Parent
    permission_required = "students.view_parent"

    def get(self, request, *args, **kwargs):
        parent = self.get_object()
        students = parent.get_students()

        data = [
            {
                "id": str(student.id),
                "name": student.get_full_name(),
                "admission_number": student.admission_number,
                "class": str(student.current_class) if student.current_class else None,
                "status": student.status,
                "is_primary": parent.parent_student_relations.filter(
                    student=student, is_primary_contact=True
                ).exists(),
            }
            for student in students
        ]

        return JsonResponse({"students": data})
