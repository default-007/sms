# students/views/import_export_views.py
import csv
import datetime
import io

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.core.cache import cache
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.generic import FormView, TemplateView, View

from ..forms import ParentBulkImportForm, StudentBulkImportForm
from ..models import Parent, Student
from ..services.parent_service import ParentService
from ..services.student_service import StudentService


class StudentBulkImportView(LoginRequiredMixin, PermissionRequiredMixin, FormView):
    template_name = "students/student_bulk_import.html"
    form_class = StudentBulkImportForm
    permission_required = "students.bulk_import_students"
    success_url = "/students/"

    def form_valid(self, form):
        csv_file = form.cleaned_data["csv_file"]
        send_notifications = form.cleaned_data.get("send_email_notifications", False)
        update_existing = form.cleaned_data.get("update_existing", False)

        try:
            # Process the CSV file
            import_result = StudentService.bulk_import_students(
                csv_file=csv_file,
                send_notifications=send_notifications,
                update_existing=update_existing,
                created_by=self.request.user,
            )

            if import_result["success"]:
                messages.success(
                    self.request,
                    f"Import completed! Created: {import_result['created']}, "
                    f"Updated: {import_result['updated']}, "
                    f"Errors: {import_result['errors']}",
                )

                # Show detailed error information if available
                if import_result["errors"] > 0 and import_result.get("error_details"):
                    error_summary = []
                    for error in import_result["error_details"][
                        :5
                    ]:  # Show first 5 errors
                        error_summary.append(f"Row {error['row']}: {error['error']}")

                    if len(import_result["error_details"]) > 5:
                        error_summary.append(
                            f"... and {len(import_result['error_details']) - 5} more errors"
                        )

                    messages.warning(
                        self.request, f"Import errors: {'; '.join(error_summary)}"
                    )
            else:
                messages.error(
                    self.request,
                    f"Import failed: {import_result.get('error', 'Unknown error')}",
                )

        except Exception as e:
            messages.error(self.request, f"Import failed with error: {str(e)}")

        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Bulk Import Students"
        context["description"] = "Upload a CSV file to import multiple students at once"

        # Add CSV template information - email is now optional
        context["csv_template_headers"] = [
            "first_name",
            "last_name",
            "admission_number",  # This is now the primary identifier
            "email",  # Now optional
            "admission_date",
            "roll_number",
            "current_class_id",
            "blood_group",
            "emergency_contact_name",
            "emergency_contact_number",
            "status",
            "nationality",
            "religion",
            "city",
            "state",
            "country",
            "phone_number",
            "date_of_birth",
            "medical_conditions",
        ]

        # Sample data for template - note email is optional
        context["csv_sample_data"] = [
            {
                "first_name": "John",
                "last_name": "Doe",
                "admission_number": "ADM-2024-001",  # Primary identifier
                "email": "john.doe@example.com",  # Optional
                "admission_date": "2024-01-15",
                "emergency_contact_name": "Jane Doe",
                "emergency_contact_number": "+1234567890",
                "status": "Active",
            },
            {
                "first_name": "Alice",
                "last_name": "Smith",
                "admission_number": "ADM-2024-002",  # Primary identifier
                "email": "",  # Can be empty
                "admission_date": "2024-01-16",
                "emergency_contact_name": "Bob Smith",
                "emergency_contact_number": "+1234567891",
                "status": "Active",
            },
        ]

        # Add important note about admission number as username
        context["important_notes"] = [
            "Admission number will be used as the student's username for login",
            "Email address is optional but recommended for communication",
            "Admission number must be unique across all students",
            "Students will login using their admission number, not email",
        ]

        return context


class ParentBulkImportView(LoginRequiredMixin, PermissionRequiredMixin, FormView):
    template_name = "students/parent_bulk_import.html"
    form_class = ParentBulkImportForm
    permission_required = "students.bulk_import_parents"
    success_url = "/students/parents/"

    def form_valid(self, form):
        csv_file = form.cleaned_data["csv_file"]
        send_notifications = form.cleaned_data.get("send_email_notifications", False)
        update_existing = form.cleaned_data.get("update_existing", False)

        try:
            # Process the CSV file
            import_result = ParentService.bulk_import_parents(
                csv_file=csv_file,
                send_notifications=send_notifications,
                update_existing=update_existing,
                created_by=self.request.user,
            )

            if import_result["success"]:
                messages.success(
                    self.request,
                    f"Import completed! Created: {import_result['created']}, "
                    f"Updated: {import_result['updated']}, "
                    f"Errors: {import_result['errors']}",
                )

                if import_result["errors"] > 0 and import_result.get("error_details"):
                    error_summary = []
                    for error in import_result["error_details"][:5]:
                        error_summary.append(f"Row {error['row']}: {error['error']}")

                    if len(import_result["error_details"]) > 5:
                        error_summary.append(
                            f"... and {len(import_result['error_details']) - 5} more errors"
                        )

                    messages.warning(
                        self.request, f"Import errors: {'; '.join(error_summary)}"
                    )
            else:
                messages.error(
                    self.request,
                    f"Import failed: {import_result.get('error', 'Unknown error')}",
                )

        except Exception as e:
            messages.error(self.request, f"Import failed with error: {str(e)}")

        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Bulk Import Parents"
        context["description"] = "Upload a CSV file to import multiple parents at once"

        # Add CSV template information
        context["csv_template_headers"] = [
            "first_name",
            "last_name",
            "email",
            "phone_number",
            "relation_with_student",
            "occupation",
            "workplace",
            "work_phone",
            "student_admission_number",
            "is_primary_contact",
            "can_pickup",
            "financial_responsibility",
        ]

        # Sample data for template
        context["csv_sample_data"] = [
            {
                "first_name": "Jane",
                "last_name": "Doe",
                "email": "jane.doe@example.com",
                "phone_number": "+1234567890",
                "relation_with_student": "Mother",
                "occupation": "Teacher",
                "student_admission_number": "ADM-2024-001",
                "is_primary_contact": "true",
            },
            {
                "first_name": "Bob",
                "last_name": "Smith",
                "email": "bob.smith@example.com",
                "phone_number": "+1234567891",
                "relation_with_student": "Father",
                "occupation": "Engineer",
                "student_admission_number": "ADM-2024-002",
                "is_primary_contact": "true",
            },
        ]

        return context


class ExportStudentsView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = "students.export_student_data"

    def get(self, request, *args, **kwargs):
        # Get filter parameters
        filters = {
            "status": request.GET.get("status", ""),
            "class_id": request.GET.get("class", ""),
            "blood_group": request.GET.get("blood_group", ""),
            "admission_year": request.GET.get("admission_year", ""),
        }

        # Build queryset based on filters
        queryset = StudentService.search_students(
            query=request.GET.get("search", ""),
            filters={k: v for k, v in filters.items() if v},
        )

        # Generate CSV content
        csv_content = StudentService.export_students_to_csv(queryset)

        # Create HTTP response with CSV content
        timestamp = timezone.now().strftime("%Y%m%d_%H%M%S")
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = (
            f'attachment; filename="students_export_{timestamp}.csv"'
        )
        response.write(csv_content)

        return response


class ExportParentsView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = "students.export_parent_data"

    def get(self, request, *args, **kwargs):
        # Get filter parameters
        filters = {
            "relation": request.GET.get("relation", ""),
            "emergency_contact": request.GET.get("emergency_contact", ""),
        }

        # Build queryset based on filters
        queryset = Parent.objects.all().with_related()

        # Apply filters
        if filters["relation"]:
            queryset = queryset.filter(relation_with_student=filters["relation"])

        if filters["emergency_contact"]:
            queryset = queryset.filter(
                emergency_contact=filters["emergency_contact"] == "true"
            )

        # Apply search
        search_query = request.GET.get("search", "")
        if search_query:
            queryset = queryset.search(search_query)

        # Generate CSV content
        csv_content = ParentService.export_parents_to_csv(queryset)

        # Create HTTP response with CSV content
        timestamp = timezone.now().strftime("%Y%m%d_%H%M%S")
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = (
            f'attachment; filename="parents_export_{timestamp}.csv"'
        )
        response.write(csv_content)

        return response


class DownloadCSVTemplateView(LoginRequiredMixin, View):
    """Download CSV templates for import"""

    def get(self, request, template_type):
        if template_type == "students":
            headers = [
                "first_name",
                "last_name",
                "admission_number",  # Primary identifier
                "email",  # Optional
                "admission_date",
                "roll_number",
                "current_class_id",
                "blood_group",
                "emergency_contact_name",
                "emergency_contact_number",
                "status",
                "nationality",
                "religion",
                "city",
                "state",
                "country",
                "phone_number",
                "date_of_birth",
                "medical_conditions",
            ]
            filename = "student_import_template.csv"

            # Add sample data with emphasis on admission_number
            sample_data = [
                {
                    "first_name": "John",
                    "last_name": "Doe",
                    "admission_number": "ADM-2024-001",  # Required
                    "email": "john.doe@example.com",  # Optional
                    "admission_date": "2024-01-15",
                    "emergency_contact_name": "Jane Doe",
                    "emergency_contact_number": "+1234567890",
                    "status": "Active",
                    "blood_group": "O+",
                    "nationality": "Indian",
                    "city": "Mumbai",
                    "state": "Maharashtra",
                    "country": "India",
                },
                {
                    "first_name": "Alice",
                    "last_name": "Smith",
                    "admission_number": "ADM-2024-002",  # Required
                    "email": "",  # Can be empty
                    "admission_date": "2024-01-16",
                    "emergency_contact_name": "Bob Smith",
                    "emergency_contact_number": "+1234567891",
                    "status": "Active",
                    "blood_group": "A+",
                    "nationality": "Indian",
                    "city": "Delhi",
                    "state": "Delhi",
                    "country": "India",
                },
            ]

        elif template_type == "parents":
            headers = [
                "first_name",
                "last_name",
                "email",
                "phone_number",
                "relation_with_student",
                "occupation",
                "workplace",
                "work_phone",
                "student_admission_number",
                "is_primary_contact",
                "can_pickup",
                "financial_responsibility",
            ]
            filename = "parent_import_template.csv"

            # Add sample data
            sample_data = [
                {
                    "first_name": "Jane",
                    "last_name": "Doe",
                    "email": "jane.doe@example.com",
                    "phone_number": "+1234567890",
                    "relation_with_student": "Mother",
                    "occupation": "Teacher",
                    "student_admission_number": "ADM-2024-001",
                    "is_primary_contact": "true",
                    "can_pickup": "true",
                    "financial_responsibility": "true",
                }
            ]

        else:
            return JsonResponse({"error": "Invalid template type"}, status=400)

        # Create CSV response
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'

        writer = csv.DictWriter(response, fieldnames=headers)
        writer.writeheader()

        # Write sample data
        for row in sample_data:
            writer.writerow(row)

        return response


class ImportStatusView(LoginRequiredMixin, TemplateView):
    """View to check import status using AJAX"""

    template_name = "students/import_status.html"

    def get(self, request, *args, **kwargs):
        import_id = request.GET.get("import_id")

        if not import_id:
            return JsonResponse({"error": "Import ID required"}, status=400)

        # Get import status from cache (this would be set during import process)
        cache_key = f"import_status_{import_id}"
        status = cache.get(cache_key)

        if status is None:
            return JsonResponse({"error": "Import not found"}, status=404)

        return JsonResponse(status)


class BulkExportView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    """Enhanced bulk export with multiple formats"""

    template_name = "students/bulk_export.html"
    permission_required = "students.export_student_data"

    def post(self, request, *args, **kwargs):
        export_type = request.POST.get(
            "export_type"
        )  # students, parents, relationships
        format_type = request.POST.get("format", "csv")  # csv, xlsx, pdf
        include_photos = request.POST.get("include_photos") == "on"

        try:
            if export_type == "students":
                queryset = Student.objects.all().with_related().with_parents()

                # Apply filters from form
                filters = {}
                for key in ["status", "class", "blood_group", "admission_year"]:
                    value = request.POST.get(key)
                    if value:
                        filters[key] = value

                if filters:
                    queryset = StudentService.search_students("", filters)

                if format_type == "csv":
                    response = self._export_students_csv(queryset)
                elif format_type == "xlsx":
                    response = self._export_students_xlsx(queryset)
                elif format_type == "pdf":
                    response = self._export_students_pdf(queryset, include_photos)
                else:
                    messages.error(request, "Invalid export format")
                    return redirect(request.path)

            elif export_type == "parents":
                queryset = Parent.objects.all().with_related().with_students()

                # Apply filters
                relation = request.POST.get("relation")
                if relation:
                    queryset = queryset.filter(relation_with_student=relation)

                if format_type == "csv":
                    response = self._export_parents_csv(queryset)
                else:
                    messages.error(request, "Format not supported for parents export")
                    return redirect(request.path)

            else:
                messages.error(request, "Invalid export type")
                return redirect(request.path)

            return response

        except Exception as e:
            messages.error(request, f"Export failed: {str(e)}")
            return redirect(request.path)

    def _export_students_csv(self, queryset):
        csv_content = StudentService.export_students_to_csv(queryset)
        timestamp = timezone.now().strftime("%Y%m%d_%H%M%S")

        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = (
            f'attachment; filename="students_export_{timestamp}.csv"'
        )
        response.write(csv_content)
        return response

    def _export_parents_csv(self, queryset):
        csv_content = ParentService.export_parents_to_csv(queryset)
        timestamp = timezone.now().strftime("%Y%m%d_%H%M%S")

        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = (
            f'attachment; filename="parents_export_{timestamp}.csv"'
        )
        response.write(csv_content)
        return response

    def _export_students_xlsx(self, queryset):
        # Excel export implementation would go here
        # For now, fallback to CSV
        return self._export_students_csv(queryset)

    def _export_students_pdf(self, queryset, include_photos=False):
        # PDF export implementation would go here
        # For now, fallback to CSV
        return self._export_students_csv(queryset)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["export_types"] = [
            ("students", "Students"),
            ("parents", "Parents"),
            ("relationships", "Student-Parent Relationships"),
        ]
        context["format_types"] = [
            ("csv", "CSV"),
            ("xlsx", "Excel (XLSX)"),
            ("pdf", "PDF"),
        ]
        return context
