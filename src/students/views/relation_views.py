# students/views/relation_views.py
from django.shortcuts import get_object_or_404, redirect
from django.views.generic import (
    CreateView,
    UpdateView,
    DeleteView,
    FormView,
    DetailView,
)
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib import messages
from django.http import JsonResponse
from django.db import transaction
from django.core.exceptions import ValidationError

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

        # Pre-populate from URL parameters
        student_id = self.kwargs.get("student_id")
        parent_id = self.kwargs.get("parent_id")

        if student_id:
            kwargs["student"] = get_object_or_404(Student, pk=student_id)

        if parent_id:
            kwargs["parent"] = get_object_or_404(Parent, pk=parent_id)

        return kwargs

    def get_success_url(self):
        # Smart redirect based on context
        if "student_id" in self.kwargs:
            return reverse_lazy(
                "students:student-detail", kwargs={"pk": self.kwargs["student_id"]}
            )
        elif "parent_id" in self.kwargs:
            return reverse_lazy(
                "students:parent-detail", kwargs={"pk": self.kwargs["parent_id"]}
            )
        else:
            # Check referrer if available
            if self.object.student:
                return reverse_lazy(
                    "students:student-detail", kwargs={"pk": self.object.student.pk}
                )
            else:
                return reverse_lazy("students:student-list")

    def form_valid(self, form):
        # Set created_by
        form.instance.created_by = self.request.user

        messages.success(
            self.request, "Student-parent relationship created successfully!"
        )
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Dynamic title based on context
        if "student_id" in self.kwargs:
            student = get_object_or_404(Student, pk=self.kwargs["student_id"])
            context["title"] = f"Add Parent for {student.get_full_name()}"
            context["subtitle"] = f"Link a parent/guardian to {student.get_full_name()}"
        elif "parent_id" in self.kwargs:
            parent = get_object_or_404(Parent, pk=self.kwargs["parent_id"])
            context["title"] = f"Add Student for {parent.get_full_name()}"
            context["subtitle"] = f"Link a student to {parent.get_full_name()}"
        else:
            context["title"] = "Create Student-Parent Relationship"
            context["subtitle"] = "Link a student with their parent/guardian"

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
        relation = self.get_object()

        # Check referrer to determine best redirect
        referer = self.request.META.get("HTTP_REFERER", "")

        if "parent" in referer:
            return reverse_lazy(
                "students:parent-detail", kwargs={"pk": relation.parent.pk}
            )
        else:
            return reverse_lazy(
                "students:student-detail", kwargs={"pk": relation.student.pk}
            )

    def form_valid(self, form):
        messages.success(self.request, "Relationship updated successfully!")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        relation = self.get_object()
        context["title"] = f"Update Relationship"
        context["subtitle"] = (
            f"{relation.student.get_full_name()} - {relation.parent.get_full_name()}"
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
        relation = self.get_object()

        # Check referrer to determine redirect
        referer = self.request.META.get("HTTP_REFERER", "")

        if "parent" in referer:
            return reverse_lazy(
                "students:parent-detail", kwargs={"pk": relation.parent.pk}
            )
        else:
            return reverse_lazy(
                "students:student-detail", kwargs={"pk": relation.student.pk}
            )

    def delete(self, request, *args, **kwargs):
        relation = self.get_object()
        student_name = relation.student.get_full_name()
        parent_name = relation.parent.get_full_name()

        messages.success(
            request,
            f"Relationship between {student_name} and {parent_name} has been removed successfully.",
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
            with transaction.atomic():
                # Get data from request
                student_id = request.POST.get("student_id")
                parent_id = request.POST.get("parent_id")
                is_primary = request.POST.get("is_primary", "false").lower() == "true"
                relation_type = request.POST.get("relation_type", "Other")

                # Validate required fields
                if not student_id or not parent_id:
                    return JsonResponse(
                        {
                            "success": False,
                            "error": "Both student and parent are required",
                        },
                        status=400,
                    )

                # Get objects
                student = get_object_or_404(Student, pk=student_id)
                parent = get_object_or_404(Parent, pk=parent_id)

                # Check if relationship already exists
                if StudentParentRelation.objects.filter(
                    student=student, parent=parent
                ).exists():
                    return JsonResponse(
                        {
                            "success": False,
                            "error": "Relationship already exists between this student and parent",
                        },
                        status=400,
                    )

                # Create relationship
                relation = ParentService.link_parent_to_student(
                    parent=parent,
                    student=student,
                    is_primary_contact=is_primary,
                    created_by=request.user,
                )

                # Clear related cache
                from django.core.cache import cache

                cache.delete_many(
                    [
                        f"student_parents_{student.id}",
                        f"student_siblings_{student.id}",
                    ]
                )

                return JsonResponse(
                    {
                        "success": True,
                        "relation_id": str(relation.id),
                        "student_name": student.get_full_name(),
                        "parent_name": parent.get_full_name(),
                        "is_primary": relation.is_primary_contact,
                        "message": f"Successfully linked {parent.get_full_name()} to {student.get_full_name()}",
                    }
                )

        except ValidationError as e:
            return JsonResponse(
                {
                    "success": False,
                    "error": str(e.message) if hasattr(e, "message") else str(e),
                },
                status=400,
            )
        except Exception as e:
            return JsonResponse(
                {"success": False, "error": f"An error occurred: {str(e)}"}, status=500
            )


class BulkRelationshipManagementView(
    LoginRequiredMixin, PermissionRequiredMixin, FormView
):
    """View for managing multiple relationships at once"""

    permission_required = "students.add_studentparentrelation"
    template_name = "students/bulk_relationship_form.html"

    def post(self, request, *args, **kwargs):
        action = request.POST.get("action")
        relationship_ids = request.POST.getlist("relationship_ids")

        if not relationship_ids:
            messages.error(request, "No relationships selected.")
            return redirect(request.META.get("HTTP_REFERER", "students:student-list"))

        relations = StudentParentRelation.objects.filter(id__in=relationship_ids)

        try:
            with transaction.atomic():
                if action == "delete":
                    count = relations.count()
                    relations.delete()
                    messages.success(
                        request, f"Successfully deleted {count} relationships."
                    )

                elif action == "set_primary":
                    # Set selected relationships as primary (one per student)
                    for relation in relations:
                        # First, unset other primary relationships for this student
                        StudentParentRelation.objects.filter(
                            student=relation.student, is_primary_contact=True
                        ).update(is_primary_contact=False)

                        # Then set this one as primary
                        relation.is_primary_contact = True
                        relation.save()

                    messages.success(
                        request,
                        f"Successfully updated {relations.count()} relationships.",
                    )

                elif action == "toggle_pickup":
                    # Toggle pickup permission
                    for relation in relations:
                        relation.can_pickup = not relation.can_pickup
                        relation.save()

                    messages.success(
                        request,
                        f"Successfully updated pickup permissions for {relations.count()} relationships.",
                    )

        except Exception as e:
            messages.error(request, f"An error occurred: {str(e)}")

        return redirect(request.META.get("HTTP_REFERER", "students:student-list"))


class RelationshipPermissionsUpdateView(
    LoginRequiredMixin, PermissionRequiredMixin, UpdateView
):
    """AJAX view for updating relationship permissions"""

    model = StudentParentRelation
    permission_required = "students.change_studentparentrelation"
    http_method_names = ["post"]

    def post(self, request, *args, **kwargs):
        relation = self.get_object()

        try:
            # Get permission updates from request
            permissions = {
                "access_to_grades": request.POST.get("access_to_grades") == "true",
                "access_to_attendance": request.POST.get("access_to_attendance")
                == "true",
                "access_to_financial_info": request.POST.get("access_to_financial_info")
                == "true",
                "receive_sms": request.POST.get("receive_sms") == "true",
                "receive_email": request.POST.get("receive_email") == "true",
                "receive_push_notifications": request.POST.get(
                    "receive_push_notifications"
                )
                == "true",
            }

            # Update permissions
            for permission, value in permissions.items():
                if hasattr(relation, permission):
                    setattr(relation, permission, value)

            relation.save()

            return JsonResponse(
                {
                    "success": True,
                    "message": "Permissions updated successfully",
                    "updated_permissions": permissions,
                }
            )

        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)}, status=500)


class StudentFamilyTreeView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    """View to display family tree for a student"""

    model = Student
    permission_required = "students.view_student"
    template_name = "students/family_tree.html"
    context_object_name = "student"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        student = self.get_object()

        # Build family tree data
        family_tree = {
            "student": student,
            "parents": [],
            "siblings": student.get_siblings(),
            "relationships": [],
        }

        # Get all parent relationships
        relations = student.student_parent_relations.select_related("parent__user")
        for relation in relations:
            family_tree["parents"].append(
                {
                    "parent": relation.parent,
                    "relation": relation,
                    "is_primary": relation.is_primary_contact,
                    "can_pickup": relation.can_pickup,
                    "emergency_priority": relation.emergency_contact_priority,
                }
            )

        # For AJAX requests, return JSON
        if self.request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse(
                {
                    "family_tree": {
                        "student": {
                            "id": str(student.id),
                            "name": student.get_full_name(),
                            "admission_number": student.admission_number,
                            "class": (
                                str(student.current_class)
                                if student.current_class
                                else None
                            ),
                        },
                        "parents": [
                            {
                                "id": str(item["parent"].id),
                                "name": item["parent"].get_full_name(),
                                "relation": item["parent"].relation_with_student,
                                "is_primary": item["is_primary"],
                                "phone": item["parent"].user.phone_number or "",
                            }
                            for item in family_tree["parents"]
                        ],
                        "siblings": [
                            {
                                "id": str(sibling.id),
                                "name": sibling.get_full_name(),
                                "admission_number": sibling.admission_number,
                                "class": (
                                    str(sibling.current_class)
                                    if sibling.current_class
                                    else None
                                ),
                            }
                            for sibling in family_tree["siblings"]
                        ],
                    }
                }
            )

        context["family_tree"] = family_tree
        return context
