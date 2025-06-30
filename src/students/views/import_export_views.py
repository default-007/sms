# students/views/import_export_views.py
import csv
import datetime
import io

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.auth.decorators import login_required, permission_required
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.core.cache import cache
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.generic import FormView, TemplateView, View
from django.urls import reverse_lazy

from ..forms import ParentBulkImportForm, StudentBulkImportForm
from ..models import Parent, Student
from ..services.parent_service import ParentService
from ..services.student_service import StudentService


class StudentBulkImportView(LoginRequiredMixin, PermissionRequiredMixin, FormView):
    template_name = "students/student_bulk_import.html"
    form_class = StudentBulkImportForm
    permission_required = "students.bulk_import_students"
    success_url = reverse_lazy("students:student-list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context.update(
            {
                "title": "Bulk Import Students",
                "description": "Import multiple students from CSV file with enhanced class assignment options",
            }
        )

        # Enhanced CSV template headers - simplified and focused
        context["csv_template_headers"] = [
            "first_name",  # Required
            "last_name",  # Required
            "admission_number",  # Required - Primary identifier
            "email",  # Optional - for notifications
            "phone_number",  # Optional - student/parent contact
            "class_id",  # Optional - specific class assignment
            "admission_date",  # Optional - defaults to today
            "roll_number",  # Optional
            "blood_group",  # Optional
            "emergency_contact_name",  # Recommended
            "emergency_contact_number",  # Recommended
            "nationality",  # Optional
            "religion",  # Optional
            "city",  # Optional
            "state",  # Optional
            "country",  # Optional
            "medical_conditions",  # Optional
            "date_of_birth",  # Optional
            "status",  # Optional - defaults to Active
        ]

        # Enhanced sample data with class-based examples
        context["csv_sample_data"] = [
            {
                "first_name": "John",
                "last_name": "Doe",
                "admission_number": "2024-STD-001",
                "email": "john.doe@example.com",  # Optional
                "phone_number": "+1234567890",  # Optional
                "class_id": "15",  # Optional - specific class
                "admission_date": "2024-01-15",
                "emergency_contact_name": "Jane Doe",
                "emergency_contact_number": "+1234567890",
                "blood_group": "O+",
                "status": "Active",
            },
            {
                "first_name": "Alice",
                "last_name": "Smith",
                "admission_number": "2024-STD-002",
                "email": "",  # Can be empty
                "phone_number": "",  # Can be empty
                "class_id": "",  # Empty - will use target class if auto-assign enabled
                "admission_date": "2024-01-16",
                "emergency_contact_name": "Bob Smith",
                "emergency_contact_number": "+1234567891",
                "blood_group": "A+",
                "status": "Active",
            },
        ]

        # Important notes for users
        context["important_notes"] = [
            "Only first_name, last_name, and admission_number are required",
            "Email and phone_number are optional but recommended for communication",
            "Admission number will be used as the student's username for login",
            "Admission number must be unique across all students",
            "Use class_id for specific class assignment, or use target class for bulk assignment",
            "Emergency contact information is highly recommended for safety",
            "Students without email won't receive welcome notifications",
        ]

        # Template usage tips
        context["template_tips"] = [
            {
                "title": "Per-Class Import",
                "description": "Select a target class and enable auto-assign to import all students to that class",
                "icon": "fas fa-users",
            },
            {
                "title": "Mixed Class Import",
                "description": "Use class_id column in CSV to assign different students to different classes",
                "icon": "fas fa-random",
            },
            {
                "title": "Minimal Data Import",
                "description": "Only first_name, last_name, and admission_number are required for basic import",
                "icon": "fas fa-database",
            },
            {
                "title": "Contact Information",
                "description": "Include emergency contact details for student safety and communication",
                "icon": "fas fa-phone",
            },
        ]

        # Available classes for reference
        try:
            current_year = AcademicYear.objects.filter(is_current=True).first()
            if current_year:
                available_classes = (
                    Class.objects.filter(academic_year=current_year, is_active=True)
                    .select_related("grade__section")
                    .order_by(
                        "grade__section__order_sequence",
                        "grade__order_sequence",
                        "name",
                    )
                )

                context["available_classes"] = [
                    {
                        "id": cls.id,
                        "name": cls.display_name,
                        "full_name": cls.full_name,
                        "capacity": cls.capacity,
                        "current_students": cls.students.filter(
                            status="Active"
                        ).count(),
                    }
                    for cls in available_classes
                ]
        except:
            context["available_classes"] = []

        return context

    def form_valid(self, form):
        csv_file = form.cleaned_data["csv_file"]
        target_class = form.cleaned_data.get("target_class")
        academic_year = form.cleaned_data.get("academic_year")
        auto_assign_class = form.cleaned_data.get("auto_assign_class", False)
        send_notifications = form.cleaned_data.get("send_email_notifications", False)
        update_existing = form.cleaned_data.get("update_existing", False)

        try:
            # Process the CSV file with enhanced service
            import_result = StudentService.bulk_import_students(
                csv_file=csv_file,
                target_class=target_class,
                academic_year=academic_year,
                auto_assign_class=auto_assign_class,
                send_notifications=send_notifications,
                update_existing=update_existing,
                created_by=self.request.user,
            )

            if import_result["success"]:
                # Build success message with details
                success_parts = []

                if import_result["created_count"] > 0:
                    success_parts.append(
                        f"Created {import_result['created_count']} new students"
                    )

                if import_result["updated_count"] > 0:
                    success_parts.append(
                        f"Updated {import_result['updated_count']} existing students"
                    )

                success_message = "Import completed! " + ", ".join(success_parts)

                # Add target class info if used
                if target_class and auto_assign_class:
                    success_message += f" (assigned to {target_class.display_name})"

                messages.success(self.request, success_message)

                # Add warnings if any
                if import_result.get("warnings"):
                    for warning in import_result["warnings"][
                        :5
                    ]:  # Show first 5 warnings
                        messages.warning(self.request, warning)

                    if len(import_result["warnings"]) > 5:
                        messages.info(
                            self.request,
                            f"... and {len(import_result['warnings']) - 5} more warnings",
                        )

                # Add error summary if any
                if import_result["error_count"] > 0:
                    messages.error(
                        self.request,
                        f"Failed to import {import_result['error_count']} students. "
                        f"Please check the data and try again.",
                    )

            else:
                messages.error(
                    self.request,
                    f"Import failed: {import_result.get('error', 'Unknown error')}",
                )

        except Exception as e:
            messages.error(self.request, f"Import failed: {str(e)}")

        return super().form_valid(form)

    def form_invalid(self, form):
        """Handle form validation errors with better user feedback"""
        for field, errors in form.errors.items():
            for error in errors:
                messages.error(self.request, f"{field}: {error}")

        return super().form_invalid(form)


# AJAX endpoint for class information
class ClassInfoAjaxView(LoginRequiredMixin, PermissionRequiredMixin):
    """AJAX view to get class information for import planning"""

    permission_required = "students.view_student"

    def get(self, request, class_id):
        try:
            class_obj = get_object_or_404(Class, id=class_id, is_active=True)
            current_students = class_obj.students.filter(status="Active").count()

            data = {
                "success": True,
                "class_info": {
                    "id": class_obj.id,
                    "name": class_obj.display_name,
                    "full_name": class_obj.full_name,
                    "capacity": class_obj.capacity,
                    "current_students": current_students,
                    "available_spots": max(0, class_obj.capacity - current_students),
                    "utilization_percentage": round(
                        (current_students / class_obj.capacity) * 100, 1
                    ),
                    "room_number": class_obj.room_number or "Not assigned",
                    "class_teacher": (
                        class_obj.class_teacher.user.get_full_name()
                        if class_obj.class_teacher
                        else "Not assigned"
                    ),
                },
            }

            return JsonResponse(data)

        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)}, status=400)


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


@login_required
@csrf_exempt
def preview_import_data(request):
    """AJAX endpoint to preview CSV data before importing"""

    if request.method == "POST":
        try:
            import csv
            import io

            csv_file = request.FILES.get("csv_file")
            if not csv_file:
                return JsonResponse({"success": False, "error": "No file provided"})

            # Read and parse CSV
            decoded_file = csv_file.read().decode("utf-8")
            io_string = io.StringIO(decoded_file)
            reader = csv.DictReader(io_string)

            preview_data = []
            errors = []
            warnings = []

            for row_num, row in enumerate(reader, start=2):
                # Basic validation
                row_errors = []
                row_warnings = []

                # Check required fields
                required_fields = ["first_name", "last_name", "admission_number"]
                for field in required_fields:
                    if not row.get(field, "").strip():
                        row_errors.append(f"Missing {field}")

                # Check admission number uniqueness (simplified check)
                admission_number = row.get("admission_number", "").strip()
                if admission_number:
                    from students.models import Student

                    if Student.objects.filter(
                        admission_number=admission_number
                    ).exists():
                        row_warnings.append(
                            f"Admission number {admission_number} already exists"
                        )

                # Check class_id validity if provided
                class_id = row.get("class_id", "").strip()
                if class_id:
                    try:
                        from academics.models import Class

                        Class.objects.get(id=int(class_id), is_active=True)
                    except (Class.DoesNotExist, ValueError):
                        row_warnings.append(f"Invalid class_id: {class_id}")

                preview_data.append(
                    {
                        "row_number": row_num,
                        "data": dict(row),
                        "errors": row_errors,
                        "warnings": row_warnings,
                        "status": (
                            "error"
                            if row_errors
                            else ("warning" if row_warnings else "valid")
                        ),
                    }
                )

                # Limit preview to first 10 rows for performance
                if len(preview_data) >= 10:
                    break

            # Summary statistics
            total_rows = len(preview_data)
            valid_rows = len([r for r in preview_data if r["status"] == "valid"])
            warning_rows = len([r for r in preview_data if r["status"] == "warning"])
            error_rows = len([r for r in preview_data if r["status"] == "error"])

            return JsonResponse(
                {
                    "success": True,
                    "preview_data": preview_data,
                    "summary": {
                        "total_rows": total_rows,
                        "valid_rows": valid_rows,
                        "warning_rows": warning_rows,
                        "error_rows": error_rows,
                        "can_import": error_rows == 0,
                    },
                    "headers": (
                        reader.fieldnames if hasattr(reader, "fieldnames") else []
                    ),
                }
            )

        except Exception as e:
            return JsonResponse(
                {"success": False, "error": f"Error processing file: {str(e)}"}
            )

    return JsonResponse({"success": False, "error": "Invalid request method"})


@login_required
def validate_csv_data(request):
    """Endpoint to validate CSV structure without processing data"""

    if request.method == "POST":
        try:
            csv_file = request.FILES.get("csv_file")
            if not csv_file:
                return JsonResponse({"success": False, "error": "No file provided"})

            # Basic file validation
            if not csv_file.name.endswith(".csv"):
                return JsonResponse(
                    {"success": False, "error": "File must be a CSV file"}
                )

            if csv_file.size > 5 * 1024 * 1024:  # 5MB limit
                return JsonResponse(
                    {"success": False, "error": "File size must be less than 5MB"}
                )

            # Parse CSV structure
            import csv
            import io

            decoded_file = csv_file.read().decode("utf-8")
            io_string = io.StringIO(decoded_file)
            reader = csv.DictReader(io_string)

            if not reader.fieldnames:
                return JsonResponse(
                    {
                        "success": False,
                        "error": "CSV file appears to be empty or malformed",
                    }
                )

            # Check required columns
            required_columns = ["first_name", "last_name", "admission_number"]
            missing_columns = [
                col for col in required_columns if col not in reader.fieldnames
            ]

            if missing_columns:
                return JsonResponse(
                    {
                        "success": False,
                        "error": f'Missing required columns: {", ".join(missing_columns)}',
                    }
                )

            # Count rows
            row_count = sum(1 for row in reader)

            # Check for reasonable row count
            if row_count == 0:
                return JsonResponse(
                    {"success": False, "error": "CSV file contains no data rows"}
                )

            if row_count > 1000:
                return JsonResponse(
                    {
                        "success": False,
                        "error": f"Too many rows ({row_count}). Maximum allowed is 1000 students per import.",
                    }
                )

            return JsonResponse(
                {
                    "success": True,
                    "validation": {
                        "headers": list(reader.fieldnames),
                        "row_count": row_count,
                        "required_columns_present": True,
                        "file_size_mb": round(csv_file.size / (1024 * 1024), 2),
                        "can_proceed": True,
                    },
                }
            )

        except UnicodeDecodeError:
            return JsonResponse(
                {
                    "success": False,
                    "error": "Unable to decode file. Please ensure it is UTF-8 encoded.",
                }
            )
        except Exception as e:
            return JsonResponse(
                {"success": False, "error": f"Error validating file: {str(e)}"}
            )

    return JsonResponse({"success": False, "error": "Invalid request method"})


@login_required
@permission_required("students.bulk_import_students")
@require_http_methods(["GET"])
def download_student_template(request, template_type="students"):
    """Generate and download enhanced CSV template for student import"""

    # Get query parameters for customization
    class_id = request.GET.get("class_id")
    include_sample_data = request.GET.get("sample", "true").lower() == "true"
    template_style = request.GET.get("style", "standard")  # standard, minimal, complete

    response = HttpResponse(content_type="text/csv")

    # Set filename based on parameters
    filename_parts = ["student_import_template"]
    if class_id:
        try:
            class_obj = Class.objects.get(id=class_id)
            filename_parts.append(f"{class_obj.grade.name}_{class_obj.name}")
        except Class.DoesNotExist:
            pass

    filename = "_".join(filename_parts) + ".csv"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'

    writer = csv.writer(response)

    # Define column sets based on template style
    if template_style == "minimal":
        headers = [
            "first_name",  # Required
            "last_name",  # Required
            "admission_number",  # Required
            "emergency_contact_name",  # Recommended
            "emergency_contact_number",  # Recommended
        ]
    elif template_style == "complete":
        headers = [
            "first_name",
            "last_name",
            "admission_number",  # Required
            "email",
            "phone_number",  # Optional communication
            "class_id",
            "roll_number",  # Class assignment
            "admission_date",
            "date_of_birth",  # Dates
            "blood_group",
            "medical_conditions",  # Health info
            "emergency_contact_name",
            "emergency_contact_number",  # Emergency
            "nationality",
            "religion",  # Demographics
            "address",
            "city",
            "state",
            "postal_code",
            "country",  # Address
            "previous_school",
            "status",  # Academic history
        ]
    else:  # standard template
        headers = [
            # Essential fields
            "first_name",  # Required
            "last_name",  # Required
            "admission_number",  # Required
            # Communication (optional but recommended)
            "email",  # Optional - for notifications
            "phone_number",  # Optional - contact info
            # Class assignment
            "class_id",  # Optional - for mixed import
            "roll_number",  # Optional - within class
            # Important dates
            "admission_date",  # Optional - defaults to today
            "date_of_birth",  # Optional
            # Health & safety
            "blood_group",  # Optional
            "emergency_contact_name",  # Recommended
            "emergency_contact_number",  # Recommended
            "medical_conditions",  # Optional
            # Demographics
            "nationality",  # Optional
            "religion",  # Optional
            "city",  # Optional
            "state",  # Optional
            "country",  # Optional
            # Status
            "status",  # Optional - defaults to Active
        ]

    # Write headers
    writer.writerow(headers)

    # Add sample data if requested
    if include_sample_data:
        sample_rows = generate_sample_data(headers, class_id, template_style)
        for row in sample_rows:
            writer.writerow(row)

    return response


def generate_sample_data(headers, class_id=None, template_style="standard"):
    """Generate sample data rows for the CSV template"""

    # Base sample data
    samples = [
        {
            "first_name": "John",
            "last_name": "Doe",
            "admission_number": "2024-STD-001",
            "email": "john.doe@example.com",
            "phone_number": "+1234567890",
            "class_id": class_id or "15",
            "roll_number": "1",
            "admission_date": "2024-01-15",
            "date_of_birth": "2010-05-20",
            "blood_group": "O+",
            "emergency_contact_name": "Jane Doe (Mother)",
            "emergency_contact_number": "+1234567890",
            "medical_conditions": "",
            "nationality": "Indian",
            "religion": "Hindu",
            "city": "Mumbai",
            "state": "Maharashtra",
            "country": "India",
            "status": "Active",
            "address": "123 Sample Street",
            "postal_code": "400001",
            "previous_school": "ABC Primary School",
        },
        {
            "first_name": "Alice",
            "last_name": "Smith",
            "admission_number": "2024-STD-002",
            "email": "",  # Show that email can be empty
            "phone_number": "",  # Show that phone can be empty
            "class_id": "",  # Show auto-assignment possibility
            "roll_number": "2",
            "admission_date": "2024-01-16",
            "date_of_birth": "2010-08-15",
            "blood_group": "A+",
            "emergency_contact_name": "Bob Smith (Father)",
            "emergency_contact_number": "+1234567891",
            "medical_conditions": "Mild asthma",
            "nationality": "Indian",
            "religion": "Christian",
            "city": "Delhi",
            "state": "Delhi",
            "country": "India",
            "status": "Active",
            "address": "456 Sample Avenue",
            "postal_code": "110001",
            "previous_school": "",
        },
        {
            "first_name": "Raj",
            "last_name": "Patel",
            "admission_number": "2024-STD-003",
            "email": "raj.patel@example.com",
            "phone_number": "+1234567892",
            "class_id": class_id or "15",
            "roll_number": "3",
            "admission_date": "2024-01-17",
            "date_of_birth": "2010-12-03",
            "blood_group": "B+",
            "emergency_contact_name": "Priya Patel (Mother)",
            "emergency_contact_number": "+1234567892",
            "medical_conditions": "",
            "nationality": "Indian",
            "religion": "Hindu",
            "city": "Bangalore",
            "state": "Karnataka",
            "country": "India",
            "status": "Active",
            "address": "789 Sample Road",
            "postal_code": "560001",
            "previous_school": "XYZ School",
        },
    ]

    # Filter samples based on template style
    if template_style == "minimal":
        # Keep only 1 sample for minimal template
        samples = samples[:1]

    # Convert to rows based on headers
    rows = []
    for sample in samples:
        row = []
        for header in headers:
            row.append(sample.get(header, ""))
        rows.append(row)

    return rows


# Additional utility view for class-specific templates
@login_required
@permission_required("students.bulk_import_students")
def download_class_specific_template(request, class_id):
    """Download template pre-filled for a specific class"""

    class_obj = get_object_or_404(Class, id=class_id, is_active=True)

    response = HttpResponse(content_type="text/csv")
    filename = f"student_import_{class_obj.grade.name}_{class_obj.name}.csv"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'

    writer = csv.writer(response)

    # Headers for class-specific import (class_id pre-filled)
    headers = [
        "first_name",
        "last_name",
        "admission_number",  # Required
        "email",
        "phone_number",  # Optional
        "roll_number",  # Within class
        "admission_date",
        "date_of_birth",  # Dates
        "blood_group",  # Health
        "emergency_contact_name",
        "emergency_contact_number",  # Emergency
        "nationality",
        "religion",  # Demographics
        "city",
        "state",  # Location
        "medical_conditions",  # Health notes
        "status",  # Status
    ]

    writer.writerow(headers)

    # Add instructional row
    instruction_row = [
        "Enter student first name",
        "Enter student last name",
        "Enter unique admission number",
        "Optional email address",
        "Optional phone number",
        "Roll number in class (optional)",
        "YYYY-MM-DD format or leave empty",
        "YYYY-MM-DD format (optional)",
        "Blood group (optional)",
        "Emergency contact name",
        "Emergency contact phone",
        "Student nationality",
        "Student religion",
        "City name",
        "State name",
        "Any medical conditions",
        "Active (default)",
    ]
    writer.writerow(instruction_row)

    # Add sample data with class pre-filled context
    sample_row = [
        "John",
        "Doe",
        "2024-STD-001",
        "john.doe@example.com",
        "+1234567890",
        "1",  # First roll number
        "2024-01-15",
        "2010-05-20",
        "O+",
        "Jane Doe (Mother)",
        "+1234567890",
        "Indian",
        "Hindu",
        "Mumbai",
        "Maharashtra",
        "",
        "Active",
    ]
    writer.writerow(sample_row)

    return response


# Utility function for generating admission numbers
@login_required
def generate_admission_numbers(request):
    """AJAX endpoint to generate suggested admission numbers"""

    if request.method == "GET":
        year = request.GET.get("year", "2024")
        prefix = request.GET.get("prefix", "STD")
        count = int(request.GET.get("count", 10))

        # Get last used number for the year
        from students.models import Student
        import re

        pattern = f"{year}-{prefix}-"
        existing_numbers = Student.objects.filter(
            admission_number__startswith=pattern
        ).values_list("admission_number", flat=True)

        # Extract numeric parts and find the highest
        max_num = 0
        for admission_num in existing_numbers:
            match = re.search(r"-(\d+)$", admission_num)
            if match:
                num = int(match.group(1))
                max_num = max(max_num, num)

        # Generate suggestions
        suggestions = []
        for i in range(1, count + 1):
            num = max_num + i
            suggestion = f"{year}-{prefix}-{num:03d}"
            suggestions.append(suggestion)

        return JsonResponse(
            {
                "success": True,
                "suggestions": suggestions,
                "next_available": suggestions[0] if suggestions else None,
            }
        )

    return JsonResponse({"success": False, "error": "Invalid request method"})
