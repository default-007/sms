# students/views/student_views.py
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db import transaction
from django.db.models import Prefetch, Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    FormView,
    ListView,
    TemplateView,
    UpdateView,
)

from students.exceptions import *
from students.services.analytics_service import StudentAnalyticsService

from ..forms import QuickStudentAddForm, StudentForm, StudentPromotionForm
from ..models import Parent, Student, StudentParentRelation
from ..services.student_service import StudentService


class StudentListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = Student
    permission_required = "students.view_student"
    context_object_name = "students"
    template_name = "students/student_list.html"
    paginate_by = 25

    def get_queryset(self):
        queryset = Student.objects.with_related().with_parents()

        # Apply search filter
        search_query = self.request.GET.get("search", "")
        if search_query:
            queryset = queryset.search(search_query)

        # Apply other filters
        for filter_name in ["status", "blood_group"]:
            filter_value = self.request.GET.get(filter_name)
            if filter_value:
                queryset = queryset.filter(**{filter_name: filter_value})

        # Apply class filter
        class_filter = self.request.GET.get("class")
        if class_filter:
            queryset = queryset.filter(current_class_id=class_filter)

        return queryset.order_by("admission_number")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Add filter choices and current filters
        context.update(
            {
                "status_choices": Student.STATUS_CHOICES,
                "blood_group_choices": Student.BLOOD_GROUP_CHOICES,
                "current_filters": {
                    key: self.request.GET.get(key, "")
                    for key in ["search", "status", "class", "blood_group"]
                },
            }
        )

        # Add available classes
        from src.academics.models import Class

        context["available_classes"] = Class.objects.filter(
            academic_year__is_current=True
        ).select_related("grade", "section")

        return context


@method_decorator(cache_page(300), name="get")  # Cache for 5 minutes
class StudentDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = Student
    permission_required = "students.view_student"
    context_object_name = "student"
    template_name = "students/student_detail.html"

    def get_queryset(self):
        return Student.objects.select_related(
            "user", "current_class__grade", "current_class__section"
        ).prefetch_related(
            Prefetch(
                "student_parent_relations",
                queryset=StudentParentRelation.objects.select_related(
                    "parent__user"
                ).order_by("emergency_contact_priority"),
            )
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        student = self.get_object()

        # Get related data
        context["parents"] = student.get_parents()
        context["primary_parent"] = student.get_primary_parent()
        context["siblings"] = student.get_siblings()
        context["attendance_percentage"] = student.get_attendance_percentage()

        # Get student-parent relations with details
        context["parent_relations"] = student.student_parent_relations.all()

        # Add action permissions
        context["can_edit"] = self.request.user.has_perm("students.change_student")
        context["can_delete"] = self.request.user.has_perm("students.delete_student")
        context["can_generate_id"] = self.request.user.has_perm(
            "students.generate_student_id"
        )

        return context


class StudentCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = Student
    permission_required = "students.add_student"
    form_class = StudentForm
    template_name = "students/student_form.html"
    success_url = reverse_lazy("students:student-list")

    def form_valid(self, form):
        try:
            with transaction.atomic():
                messages.success(self.request, "Student created successfully!")
                return super().form_valid(form)
        except ValidationError as e:
            form.add_error(None, str(e))
            return self.form_invalid(form)
        except Exception as e:
            messages.error(self.request, f"Error creating student: {str(e)}")
            return self.form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Add New Student"
        context["button_label"] = "Create Student"
        return context


class StudentUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = Student
    permission_required = "students.change_student"
    form_class = StudentForm
    template_name = "students/student_form.html"

    def get_success_url(self):
        return reverse_lazy("students:student-detail", kwargs={"pk": self.object.pk})

    def form_valid(self, form):
        try:
            with transaction.atomic():
                messages.success(self.request, "Student updated successfully!")
                return super().form_valid(form)
        except ValidationError as e:
            form.add_error(None, str(e))
            return self.form_invalid(form)
        except Exception as e:
            messages.error(self.request, f"Error updating student: {str(e)}")
            return self.form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = f"Edit Student: {self.object.get_full_name()}"
        context["button_label"] = "Update Student"
        return context


class StudentDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = Student
    permission_required = "students.delete_student"
    template_name = "students/student_confirm_delete.html"
    success_url = reverse_lazy("students:student-list")
    context_object_name = "student"

    def delete(self, request, *args, **kwargs):
        student = self.get_object()

        # Check if student has relationships that prevent deletion
        if student.student_parent_relations.exists():
            messages.error(
                request,
                f"Cannot delete student '{student.get_full_name()}' as they have linked parents. "
                "Please remove all parent relationships first.",
            )
            return redirect("students:student-detail", pk=student.pk)

        messages.success(
            request,
            f"Student '{student.get_full_name()}' has been deleted successfully!",
        )
        return super().delete(request, *args, **kwargs)


class QuickStudentAddView(LoginRequiredMixin, PermissionRequiredMixin, FormView):
    """Quick student addition with minimal required fields"""

    form_class = QuickStudentAddForm
    permission_required = "students.add_student"
    template_name = "students/quick_student_add.html"
    success_url = reverse_lazy("students:student-list")

    def form_valid(self, form):
        try:
            student = form.save()
            messages.success(
                self.request,
                f"Student '{student.get_full_name()}' created successfully! "
                f"Please complete their profile by editing their details.",
            )
            return super().form_valid(form)
        except Exception as e:
            messages.error(self.request, f"Error creating student: {str(e)}")
            return self.form_invalid(form)


class StudentStatusUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    """View for updating student status"""

    model = Student
    permission_required = "students.change_student"
    fields = ["status"]
    template_name = "students/student_status_update.html"

    def get_success_url(self):
        return reverse_lazy("students:student-detail", kwargs={"pk": self.object.pk})

    def form_valid(self, form):
        try:
            old_status = self.get_object().status
            new_status = form.cleaned_data["status"]

            if old_status != new_status:
                messages.success(
                    self.request,
                    f"Student status changed from '{old_status}' to '{new_status}'",
                )

            return super().form_valid(form)
        except InvalidStudentStatusError as e:
            form.add_error("status", str(e))
            return self.form_invalid(form)


class GenerateStudentIDCardView(
    LoginRequiredMixin, PermissionRequiredMixin, DetailView
):
    """Generate and download student ID card"""

    model = Student
    permission_required = "students.generate_student_id"

    def get(self, request, *args, **kwargs):
        student = self.get_object()

        try:
            # Generate ID card PDF
            pdf_path = StudentService.generate_student_id_card(student)

            # Return PDF response
            with open(pdf_path, "rb") as pdf_file:
                response = HttpResponse(pdf_file.read(), content_type="application/pdf")
                response["Content-Disposition"] = (
                    f'attachment; filename="id_card_{student.admission_number}.pdf"'
                )
                return response

        except Exception as e:
            messages.error(request, f"Error generating ID card: {str(e)}")
            return redirect("students:student-detail", pk=student.pk)


class StudentPromotionView(LoginRequiredMixin, PermissionRequiredMixin, FormView):
    """Bulk student promotion view"""

    form_class = StudentPromotionForm
    permission_required = "students.promote_student"
    template_name = "students/student_promotion.html"
    success_url = reverse_lazy("students:student-list")

    def form_valid(self, form):
        try:
            students = form.cleaned_data["students"]
            target_class = form.cleaned_data["target_class"]
            send_notifications = form.cleaned_data["send_notifications"]

            result = StudentService.promote_students(
                students, target_class, send_notifications
            )

            messages.success(
                self.request,
                f"Promoted {result['promoted']} students successfully. "
                f"{result['errors']} errors occurred.",
            )

            if result["errors"] > 0:
                for error in result.get("error_details", [])[:5]:  # Show first 5 errors
                    messages.warning(
                        self.request, f"Error: {error.get('error', 'Unknown error')}"
                    )

            return super().form_valid(form)
        except Exception as e:
            messages.error(self.request, f"Promotion failed: {str(e)}")
            return self.form_invalid(form)


class StudentGraduationView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    """Bulk student graduation view"""

    permission_required = "students.graduate_student"
    template_name = "students/student_graduation.html"

    def post(self, request, *args, **kwargs):
        try:
            student_ids = request.POST.getlist("student_ids")
            send_notifications = request.POST.get("send_notifications") == "on"

            if not student_ids:
                messages.error(request, "No students selected for graduation")
                return self.get(request, *args, **kwargs)

            students = Student.objects.filter(id__in=student_ids)
            result = StudentService.graduate_students(students, send_notifications)

            messages.success(
                request,
                f"Graduated {result['graduated']} students successfully. "
                f"{result['errors']} errors occurred.",
            )

            return redirect("students:student-list")
        except Exception as e:
            messages.error(request, f"Graduation failed: {str(e)}")
            return self.get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get eligible students for graduation (typically final year students)
        context["eligible_students"] = Student.objects.filter(
            status="Active"
        ).select_related("user", "current_class")

        return context


class StudentAutocompleteView(LoginRequiredMixin, ListView):
    """AJAX autocomplete for students"""

    def get(self, request, *args, **kwargs):
        query = request.GET.get("q", "")
        limit = int(request.GET.get("limit", 10))

        students = Student.objects.filter(
            Q(admission_number__icontains=query)
            | Q(user__first_name__icontains=query)
            | Q(user__last_name__icontains=query)
            | Q(user__email__icontains=query)
        ).select_related("user", "current_class")[:limit]

        results = [
            {
                "id": str(student.id),
                "text": f"{student.get_full_name()} ({student.admission_number})",
                "admission_number": student.admission_number,
                "class": str(student.current_class) if student.current_class else "",
                "status": student.status,
                "email": student.user.email,
            }
            for student in students
        ]

        return JsonResponse({"results": results})


class StudentFamilyTreeView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    """View to display student family relationships"""

    model = Student
    permission_required = "students.view_student"
    template_name = "students/student_family_tree.html"
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

        # Get all parent relationships with details
        relations = student.student_parent_relations.select_related("parent__user")
        for relation in relations:
            family_tree["parents"].append(
                {
                    "parent": relation.parent,
                    "relation": relation,
                    "is_primary": relation.is_primary_contact,
                    "can_pickup": relation.can_pickup,
                    "emergency_priority": relation.emergency_contact_priority,
                    "permissions": {
                        "financial_responsibility": relation.financial_responsibility,
                        "access_to_grades": relation.access_to_grades,
                        "access_to_attendance": relation.access_to_attendance,
                        "access_to_financial_info": relation.access_to_financial_info,
                    },
                }
            )

        context["family_tree"] = family_tree
        return context


class StudentAnalyticsView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    """Student analytics dashboard"""

    permission_required = "students.view_student"
    template_name = "students/student_analytics.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        try:
            # Get comprehensive analytics data
            context["analytics"] = (
                StudentAnalyticsService.get_comprehensive_dashboard_data()
            )
            context["real_time_metrics"] = (
                StudentAnalyticsService.get_real_time_metrics()
            )
        except Exception as e:
            messages.error(self.request, f"Error loading analytics: {str(e)}")
            context["analytics"] = {}
            context["real_time_metrics"] = {}

        return context
