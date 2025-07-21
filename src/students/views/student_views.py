# students/views/student_views.py
import csv
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Prefetch, Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
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

from src.students.exceptions import *
from src.students.services.analytics_service import StudentAnalyticsService

from ..forms import (
    BulkStudentImportForm,
    QuickStudentForm,
    StudentForm,
    StudentParentRelationForm,
    StudentPromotionForm,
    StudentSearchForm,
)
from ..models import Parent, Student, StudentParentRelation
from ..services.student_service import InvalidStudentDataError, StudentService


class StudentListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    """List view for students with search and filtering"""

    model = Student
    permission_required = "students.view_student"
    template_name = "students/student_list.html"
    context_object_name = "students"
    paginate_by = 20

    def get_queryset(self):
        queryset = Student.objects.with_related().with_parents()

        # Apply search and filters
        form = StudentSearchForm(self.request.GET)
        if form.is_valid():
            query = form.cleaned_data.get("query")
            class_filter = form.cleaned_data.get("class_filter")
            status_filter = form.cleaned_data.get("status_filter")
            blood_group_filter = form.cleaned_data.get("blood_group_filter")

            if query:
                queryset = queryset.search(query)

            if class_filter:
                queryset = queryset.filter(current_class=class_filter)

            if status_filter:
                queryset = queryset.filter(status=status_filter)

            if blood_group_filter:
                queryset = queryset.filter(blood_group=blood_group_filter)

        return queryset.order_by("-date_joined")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["search_form"] = StudentSearchForm(self.request.GET)
        context["total_students"] = Student.objects.count()
        context["active_students"] = Student.objects.active().count()
        context["can_add"] = self.request.user.has_perm("students.add_student")
        context["can_export"] = self.request.user.has_perm(
            "students.export_student_data"
        )
        return context


class StudentDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    """Detail view for a single student"""

    model = Student
    permission_required = "students.view_student"
    template_name = "students/student_detail.html"
    context_object_name = "student"

    def get_queryset(self):
        return Student.objects.with_related().prefetch_related(
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

        # Get analytics
        context["analytics"] = StudentService.get_student_analytics(student)

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
                # Set created_by
                form.instance.created_by = self.request.user

                # Save the form
                response = super().form_valid(form)

                messages.success(
                    self.request,
                    f"Student {self.object.full_name} created successfully! "
                    f"Please complete their profile by editing their details.",
                )
                return response
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
        context["title"] = f"Edit {self.object.full_name}"
        context["button_label"] = "Update Student"
        return context


class StudentDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = Student
    permission_required = "students.delete_student"
    template_name = "students/student_confirm_delete.html"
    success_url = reverse_lazy("students:student-list")

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        student_name = self.object.full_name

        try:
            response = super().delete(request, *args, **kwargs)
            messages.success(request, f"Student {student_name} deleted successfully.")
            return response
        except Exception as e:
            messages.error(request, f"Error deleting student: {str(e)}")
            return redirect("students:student-detail", pk=self.object.pk)


class QuickStudentCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    """Quick student creation with minimal fields"""

    model = Student
    permission_required = "students.add_student"
    form_class = QuickStudentForm
    template_name = "students/quick_student_form.html"

    def get_success_url(self):
        return reverse_lazy("students:student-detail", kwargs={"pk": self.object.pk})

    def form_valid(self, form):
        try:
            # Use the service to create student
            student_data = {
                "first_name": form.cleaned_data["first_name"],
                "last_name": form.cleaned_data["last_name"],
                "admission_number": form.cleaned_data["admission_number"],
                "current_class": form.cleaned_data.get("current_class"),
                "emergency_contact_name": form.cleaned_data["emergency_contact_name"],
                "emergency_contact_number": form.cleaned_data[
                    "emergency_contact_number"
                ],
            }

            self.object = StudentService.create_student(
                student_data, created_by=self.request.user
            )

            messages.success(
                self.request,
                f"Student {self.object.full_name} created successfully! "
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
        except Exception as e:
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
                f"Failed: {result['failed']}",
            )

            if result["errors"]:
                for error in result["errors"][:5]:  # Show first 5 errors
                    messages.error(self.request, error)

            return super().form_valid(form)

        except Exception as e:
            messages.error(self.request, f"Error during promotion: {str(e)}")
            return self.form_invalid(form)


class BulkStudentImportView(LoginRequiredMixin, PermissionRequiredMixin, FormView):
    """Bulk import students from CSV"""

    form_class = BulkStudentImportForm
    permission_required = "students.bulk_import_students"
    template_name = "students/bulk_import.html"
    success_url = reverse_lazy("students:student-list")

    def form_valid(self, form):
        try:
            csv_file = form.cleaned_data["csv_file"]
            default_class = form.cleaned_data.get("default_class")
            send_welcome_emails = form.cleaned_data["send_welcome_emails"]

            result = StudentService.bulk_import_students(
                csv_file=csv_file,
                default_class=default_class,
                send_welcome_emails=send_welcome_emails,
                created_by=self.request.user,
            )

            messages.success(
                self.request,
                f"Import completed! Created: {result['created']}, "
                f"Failed: {result['failed']}",
            )

            if result["errors"]:
                for error in result["errors"][:10]:  # Show first 10 errors
                    messages.error(self.request, error)

            return super().form_valid(form)

        except Exception as e:
            messages.error(self.request, f"Import failed: {str(e)}")
            return self.form_invalid(form)


@login_required
@permission_required("students.export_student_data")
def export_students_csv(request):
    """Export students to CSV"""
    try:
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="students.csv"'

        writer = csv.writer(response)

        # Write header
        writer.writerow(
            [
                "Admission Number",
                "First Name",
                "Last Name",
                "Email",
                "Phone Number",
                "Date of Birth",
                "Gender",
                "Class",
                "Roll Number",
                "Blood Group",
                "Status",
                "Admission Date",
                "Emergency Contact Name",
                "Emergency Contact Number",
            ]
        )

        # Write student data
        students = Student.objects.select_related("current_class").all()
        for student in students:
            writer.writerow(
                [
                    student.admission_number,
                    student.first_name,
                    student.last_name,
                    student.email or "",
                    student.phone_number or "",
                    (
                        student.date_of_birth.strftime("%Y-%m-%d")
                        if student.date_of_birth
                        else ""
                    ),
                    student.get_gender_display(),
                    str(student.current_class) if student.current_class else "",
                    student.roll_number,
                    student.blood_group,
                    student.status,
                    student.admission_date.strftime("%Y-%m-%d"),
                    student.emergency_contact_name,
                    student.emergency_contact_number,
                ]
            )

        return response

    except Exception as e:
        messages.error(request, f"Export failed: {str(e)}")
        return redirect("students:student-list")


@csrf_exempt
@require_http_methods(["GET"])
def student_search_ajax(request):
    """AJAX endpoint for student search"""
    query = request.GET.get("q", "").strip()

    if len(query) < 2:
        return JsonResponse({"students": []})

    try:
        students = Student.objects.search(query).select_related("current_class")[:10]

        results = [
            {
                "id": str(student.id),
                "admission_number": student.admission_number,
                "name": student.full_name,
                "class": (
                    str(student.current_class) if student.current_class else "No Class"
                ),
                "status": student.status,
            }
            for student in students
        ]

        return JsonResponse({"students": results})

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def toggle_student_status(request, pk):
    """AJAX endpoint to toggle student active status"""
    try:
        student = get_object_or_404(Student, pk=pk)

        if not request.user.has_perm("students.change_student"):
            return JsonResponse({"error": "Permission denied"}, status=403)

        student.is_active = not student.is_active

        # Update status based on is_active
        if student.is_active:
            student.status = "Active"
        else:
            student.status = "Inactive"

        student.save()

        return JsonResponse(
            {
                "success": True,
                "is_active": student.is_active,
                "status": student.status,
            }
        )

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@login_required
@permission_required("students.view_student_details")
def student_analytics_view(request, pk):
    """View for student analytics"""
    student = get_object_or_404(Student, pk=pk)
    analytics = StudentService.get_student_analytics(student)

    context = {
        "student": student,
        "analytics": analytics,
    }

    return render(request, "students/student_analytics.html", context)


@login_required
@require_http_methods(["POST"])
def bulk_student_action(request):
    """Handle bulk actions on students"""
    try:
        action = request.POST.get("action")
        student_ids = request.POST.getlist("student_ids")

        if not action or not student_ids:
            messages.error(request, "Invalid bulk action request.")
            return redirect("students:student-list")

        # Get students
        students = Student.objects.filter(id__in=student_ids)

        if not students.exists():
            messages.error(request, "No valid students selected.")
            return redirect("students:student-list")

        # Execute action based on type
        if action == "activate":
            if not request.user.has_perm("students.change_student"):
                messages.error(request, "Permission denied.")
                return redirect("students:student-list")

            updated_count = students.update(is_active=True, status="Active")
            messages.success(request, f"Activated {updated_count} students.")

        elif action == "deactivate":
            if not request.user.has_perm("students.change_student"):
                messages.error(request, "Permission denied.")
                return redirect("students:student-list")

            updated_count = students.update(is_active=False, status="Inactive")
            messages.success(request, f"Deactivated {updated_count} students.")

        elif action == "export":
            if not request.user.has_perm("students.export_student_data"):
                messages.error(request, "Permission denied.")
                return redirect("students:student-list")

            # Create CSV response for selected students
            response = HttpResponse(content_type="text/csv")
            response["Content-Disposition"] = (
                'attachment; filename="selected_students.csv"'
            )

            writer = csv.writer(response)

            # Write header
            writer.writerow(
                [
                    "Admission Number",
                    "First Name",
                    "Last Name",
                    "Email",
                    "Phone Number",
                    "Class",
                    "Status",
                    "Blood Group",
                ]
            )

            # Write student data
            for student in students.select_related("current_class"):
                writer.writerow(
                    [
                        student.admission_number,
                        student.first_name,
                        student.last_name,
                        student.email or "",
                        student.phone_number or "",
                        str(student.current_class) if student.current_class else "",
                        student.status,
                        student.blood_group,
                    ]
                )

            return response

        else:
            messages.error(request, f"Unknown action: {action}")

        return redirect("students:student-list")

    except Exception as e:
        messages.error(request, f"Error performing bulk action: {str(e)}")
        return redirect("students:student-list")
