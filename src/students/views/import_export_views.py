# students/views/import_export_views.py
from django.shortcuts import render, redirect
from django.views.generic import FormView, View
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib import messages
from django.http import HttpResponse
import csv
import datetime

from ..forms import StudentBulkImportForm, ParentBulkImportForm
from ..services.student_service import StudentService
from ..services.parent_service import ParentService
from ..models import Student, Parent


class StudentBulkImportView(LoginRequiredMixin, PermissionRequiredMixin, FormView):
    template_name = "students/student_bulk_import.html"
    form_class = StudentBulkImportForm
    permission_required = "students.add_student"
    success_url = "/students/"

    def form_valid(self, form):
        csv_file = form.cleaned_data["csv_file"]

        # Process the CSV file
        import_result = StudentService.bulk_import_students(csv_file)

        if import_result["success"]:
            messages.success(
                self.request,
                f"Successfully imported {import_result['created']} new students and updated {import_result['updated']} existing students.",
            )

            if import_result["errors"] > 0:
                messages.warning(
                    self.request,
                    f"Failed to import {import_result['errors']} records. Please check the data and try again.",
                )
        else:
            messages.error(self.request, f"Import failed: {import_result['error']}")

        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Bulk Import Students"

        # Add template CSV data
        context["csv_template"] = [
            "first_name,last_name,email,admission_number,admission_date,roll_number,current_class_id,blood_group,emergency_contact_name,emergency_contact_number,status",
            "John,Doe,john.doe@example.com,ADM-2023-001,2023-09-01,101,1,O+,Parent Name,+1234567890,Active",
            "Jane,Smith,jane.smith@example.com,ADM-2023-002,2023-09-01,102,1,A+,Parent Name,+1234567891,Active",
        ]

        return context


class ParentBulkImportView(LoginRequiredMixin, PermissionRequiredMixin, FormView):
    template_name = "students/parent_bulk_import.html"
    form_class = ParentBulkImportForm
    permission_required = "students.add_parent"
    success_url = "/students/parents/"

    def form_valid(self, form):
        csv_file = form.cleaned_data["csv_file"]

        # Process the CSV file
        import_result = ParentService.bulk_import_parents(csv_file)

        if import_result["success"]:
            messages.success(
                self.request,
                f"Successfully imported {import_result['created']} new parents and updated {import_result['updated']} existing parents.",
            )

            if import_result["errors"] > 0:
                messages.warning(
                    self.request,
                    f"Failed to import {import_result['errors']} records. Please check the data and try again.",
                )
        else:
            messages.error(self.request, f"Import failed: {import_result['error']}")

        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Bulk Import Parents"

        # Add template CSV data
        context["csv_template"] = [
            "first_name,last_name,email,phone_number,relation_with_student,occupation,student_admission_number,is_primary_contact",
            "Robert,Doe,robert.doe@example.com,+1234567890,Father,Engineer,ADM-2023-001,true",
            "Mary,Smith,mary.smith@example.com,+1234567891,Mother,Doctor,ADM-2023-002,true",
        ]

        return context


class ExportStudentsView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = "students.export_student_data"

    def get(self, request, *args, **kwargs):
        # Get filter parameters
        status = request.GET.get("status", "")
        class_id = request.GET.get("class", "")
        blood_group = request.GET.get("blood_group", "")

        # Build queryset based on filters
        queryset = Student.objects.all().select_related("user", "current_class")

        if status:
            queryset = queryset.filter(status=status)

        if class_id:
            queryset = queryset.filter(current_class_id=class_id)

        if blood_group:
            queryset = queryset.filter(blood_group=blood_group)

        # Generate CSV content
        csv_content = StudentService.export_students_to_csv(queryset)

        # Create HTTP response with CSV content
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = (
            f'attachment; filename="students_export_{timestamp}.csv"'
        )
        response.write(csv_content)

        return response


class ExportParentsView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = "students.export_student_data"

    def get(self, request, *args, **kwargs):
        # Get filter parameters
        relation = request.GET.get("relation", "")

        # Build queryset based on filters
        queryset = Parent.objects.all().select_related("user")

        if relation:
            queryset = queryset.filter(relation_with_student=relation)

        # Generate CSV content
        csv_content = ParentService.export_parents_to_csv(queryset)

        # Create HTTP response with CSV content
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = (
            f'attachment; filename="parents_export_{timestamp}.csv"'
        )
        response.write(csv_content)

        return response
