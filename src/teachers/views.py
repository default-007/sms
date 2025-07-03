import csv
import json
import re
from datetime import datetime, timedelta
from django.contrib.auth import get_user_model

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Avg, Case, Count, F, IntegerField, Q, Sum, Value, When
from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    TemplateView,
    UpdateView,
    View,
)
from django.views.generic.edit import FormView

from src.academics.models import AcademicYear, Department
from src.accounts.services import AuthenticationService

from .forms import (
    TeacherClassAssignmentForm,
    TeacherEvaluationForm,
    TeacherFilterForm,
    TeacherForm,
)
from .models import Teacher, TeacherClassAssignment, TeacherEvaluation
from .services import EvaluationService, TeacherService, TimetableService

User = get_user_model()


class TeacherListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = Teacher
    permission_required = "teachers.view_teacher"
    context_object_name = "teachers"
    template_name = "teachers/teacher_list.html"
    paginate_by = 20

    def get_queryset(self):
        queryset = super().get_queryset().select_related("user", "department")

        # Get filter form data
        form = TeacherFilterForm(self.request.GET)
        if form.is_valid():
            # Filter by name
            name = form.cleaned_data.get("name")
            if name:
                queryset = queryset.filter(
                    Q(user__first_name__icontains=name)
                    | Q(user__last_name__icontains=name)
                    | Q(employee_id__icontains=name)
                )

            # Filter by department
            department = form.cleaned_data.get("department")
            if department:
                queryset = queryset.filter(department=department)

            # Filter by status
            status = form.cleaned_data.get("status")
            if status:
                queryset = queryset.filter(status=status)

            # Filter by contract type
            contract_type = form.cleaned_data.get("contract_type")
            if contract_type:
                queryset = queryset.filter(contract_type=contract_type)

            # Filter by experience range
            experience_min = form.cleaned_data.get("experience_min")
            experience_max = form.cleaned_data.get("experience_max")
            if experience_min is not None:
                queryset = queryset.filter(experience_years__gte=experience_min)
            if experience_max is not None:
                queryset = queryset.filter(experience_years__lte=experience_max)

        # Annotate with evaluation stats if needed
        if self.request.GET.get("show_performance", False):
            queryset = queryset.annotate(
                avg_score=Avg("evaluations__score"),
                evaluation_count=Count("evaluations"),
            )

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["filter_form"] = TeacherFilterForm(self.request.GET)
        context["departments"] = Department.objects.all()
        context["status_choices"] = Teacher.STATUS_CHOICES
        context["contract_choices"] = Teacher.CONTRACT_TYPE_CHOICES
        context["show_performance"] = self.request.GET.get("show_performance", False)

        # Add export options
        context["export_formats"] = ["csv", "excel", "pdf"]

        # Statistics for summary
        context["total_teachers"] = Teacher.objects.count()
        context["active_teachers"] = Teacher.objects.filter(status="Active").count()
        context["on_leave_teachers"] = Teacher.objects.filter(status="On Leave").count()

        return context

    def render_to_response(self, context, **response_kwargs):
        # Check if this is an export request
        export_format = self.request.GET.get("export")
        if export_format in ["csv", "excel", "pdf"]:
            return self.export_data(export_format, context["teachers"])
        return super().render_to_response(context, **response_kwargs)

    def export_data(self, format, queryset):
        if format == "csv":
            response = HttpResponse(content_type="text/csv")
            response["Content-Disposition"] = 'attachment; filename="teachers.csv"'

            writer = csv.writer(response)
            writer.writerow(
                [
                    "Employee ID",
                    "First Name",
                    "Last Name",
                    "Email",
                    "Department",
                    "Position",
                    "Status",
                    "Contract Type",
                    "Experience (Years)",
                    "Joining Date",
                    "Qualification",
                ]
            )

            for teacher in queryset:
                writer.writerow(
                    [
                        teacher.employee_id,
                        teacher.user.first_name,
                        teacher.user.last_name,
                        teacher.user.email,
                        teacher.department.name if teacher.department else "N/A",
                        teacher.position,
                        teacher.status,
                        teacher.contract_type,
                        teacher.experience_years,
                        teacher.joining_date,
                        teacher.qualification,
                    ]
                )

            return response

        # For other formats (excel, pdf) - these would be implemented with appropriate libraries
        # This is a placeholder to show the structure
        messages.warning(self.request, f"{format.upper()} export not yet implemented.")
        return redirect(self.request.path)


class TeacherDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = Teacher
    permission_required = "teachers.view_teacher"
    context_object_name = "teacher"
    template_name = "teachers/teacher_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        teacher = self.get_object()

        # Get current academic year
        current_academic_year = AcademicYear.objects.filter(is_current=True).first()
        context["current_academic_year"] = current_academic_year

        # Get class assignments
        context["class_assignments"] = TeacherClassAssignment.objects.filter(
            teacher=teacher, academic_year=current_academic_year
        ).select_related("class_instance", "subject", "academic_year")

        # Get timetable for current teacher
        from src.scheduling.services.timetable_service import TimetableService

        context["timetable"] = TimetableService.get_teacher_timetable(
            teacher=teacher, academic_year=current_academic_year
        )

        # Get evaluations if user has permission
        if self.request.user.has_perm("teachers.view_teacherevaluation"):
            context["evaluations"] = EvaluationService.get_evaluations_by_teacher(
                teacher, year=timezone.now().year
            )

            # Get performance metrics
            performance = TeacherService.calculate_teacher_performance(teacher)
            context["performance"] = performance

            # Prepare data for ApexCharts
            if performance and "trend" in performance:
                context["performance_chart_data"] = json.dumps(
                    {
                        "dates": [
                            item["date"].strftime("%b %d")
                            for item in performance["trend"]
                        ],
                        "scores": [
                            float(item["score"]) for item in performance["trend"]
                        ],
                    }
                )

        return context


class TeacherCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    """Enhanced teacher creation with auto-generation"""

    model = Teacher
    permission_required = "teachers.add_teacher"
    form_class = TeacherForm
    template_name = "teachers/teacher_form.html"
    success_url = reverse_lazy("teachers:teacher-list")

    def get_form_kwargs(self):
        """Pass current user to form for auto-generation"""
        kwargs = super().get_form_kwargs()
        kwargs["created_by"] = self.request.user
        return kwargs

    def form_valid(self, form):
        """Handle successful form submission with enhanced messaging"""
        try:
            with transaction.atomic():
                teacher = form.save()

                # Create comprehensive success message
                success_parts = [
                    f'Teacher "{teacher.user.get_full_name()}" created successfully!'
                ]

                # Add information about auto-generated credentials
                form_data = form.cleaned_data

                if not form_data.get("username"):
                    success_parts.append(f"Generated username: {teacher.user.username}")

                if not form_data.get("employee_id"):
                    success_parts.append(
                        f"Generated employee ID: {teacher.employee_id}"
                    )

                if not form_data.get("password"):
                    success_parts.append("Generated secure password")

                if form_data.get("send_welcome_email", True):
                    success_parts.append("Welcome email sent with login credentials")

                messages.success(self.request, " | ".join(success_parts))
                return redirect(self.success_url)

        except Exception as e:
            messages.error(self.request, f"Error creating teacher: {e}")
            return self.form_invalid(form)

    def form_invalid(self, form):
        """Handle form validation errors with detailed messages"""
        for field, errors in form.errors.items():
            for error in errors:
                if field == "__all__":
                    messages.error(self.request, f"Form Error: {error}")
                else:
                    field_name = field.replace("_", " ").title()
                    messages.error(self.request, f"{field_name}: {error}")
        return super().form_invalid(form)

    def get_context_data(self, **kwargs):
        """Add extra context for template"""
        context = super().get_context_data(**kwargs)
        context["title"] = "Create New Teacher"
        context["subtitle"] = (
            "Username, password, and employee ID will be auto-generated if not provided"
        )
        return context


class TeacherUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    """Enhanced teacher update"""

    model = Teacher
    permission_required = "teachers.change_teacher"
    form_class = TeacherForm
    template_name = "teachers/teacher_form.html"

    def get_form_kwargs(self):
        """Pass current user to form"""
        kwargs = super().get_form_kwargs()
        kwargs["created_by"] = self.request.user
        return kwargs

    def get_success_url(self):
        return reverse_lazy("teachers:teacher-detail", kwargs={"pk": self.object.pk})

    def form_valid(self, form):
        """Enhanced success messaging"""
        try:
            with transaction.atomic():
                teacher = form.save()
                messages.success(
                    self.request,
                    f'Teacher "{teacher.user.get_full_name()}" updated successfully.',
                )
                return redirect(self.get_success_url())

        except Exception as e:
            messages.error(self.request, f"Error updating teacher: {e}")
            return self.form_invalid(form)

    def get_context_data(self, **kwargs):
        """Add extra context for template"""
        context = super().get_context_data(**kwargs)
        context["title"] = f"Edit Teacher: {self.object.user.get_full_name()}"
        context["subtitle"] = "Update teacher information"
        return context


class TeacherDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = Teacher
    permission_required = "teachers.delete_teacher"
    template_name = "teachers/teacher_confirm_delete.html"
    success_url = reverse_lazy("teachers:teacher-list")

    def delete(self, request, *args, **kwargs):
        messages.success(request, "Teacher deleted successfully.")
        return super().delete(request, *args, **kwargs)


class TeacherCredentialPreviewView(LoginRequiredMixin, View):
    """AJAX endpoint to preview auto-generated credentials"""

    def post(self, request):
        first_name = request.POST.get("first_name", "").strip()
        last_name = request.POST.get("last_name", "").strip()
        email = request.POST.get("email", "").strip()

        if not (first_name and last_name):
            return JsonResponse({"error": "First name and last name required"})

        try:
            # Generate preview username (same logic as AuthenticationService)
            if first_name and last_name:
                base_username = f"{first_name.lower()}.{last_name.lower()}"
            else:
                base_username = email.split("@")[0].lower() if email else "teacher"

            # Clean username
            base_username = re.sub(r"[^a-zA-Z0-9_]", "", base_username)

            # Check if username would be unique
            username_preview = base_username
            counter = 1
            while User.objects.filter(username=username_preview).exists():
                username_preview = f"{base_username}{counter}"
                counter += 1

            # Generate preview employee ID
            current_year = timezone.now().year
            prefix = f"TCH{current_year}"

            last_teacher = (
                Teacher.objects.filter(employee_id__startswith=prefix)
                .order_by("employee_id")
                .last()
            )

            if last_teacher:
                try:
                    last_number = int(last_teacher.employee_id.replace(prefix, ""))
                    new_number = last_number + 1
                except ValueError:
                    new_number = 1
            else:
                new_number = 1

            employee_id_preview = f"{prefix}{new_number:04d}"

            return JsonResponse(
                {
                    "username": username_preview,
                    "employee_id": employee_id_preview,
                    "password_info": "Secure 12-character password with uppercase, lowercase, numbers, and symbols",
                }
            )

        except Exception as e:
            return JsonResponse({"error": f"Error generating preview: {str(e)}"})


# Utility function for programmatic teacher creation
def create_teacher_with_defaults(
    first_name, last_name, email, phone_number=None, created_by=None, **kwargs
):
    """
    Utility function to create a teacher with auto-generated credentials

    Args:
        first_name: Teacher's first name
        last_name: Teacher's last name
        email: Teacher's email address
        phone_number: Teacher's phone number (optional)
        created_by: User creating the teacher (optional)
        **kwargs: Additional teacher fields

    Returns:
        Teacher instance with auto-generated username and password
    """

    # Prepare user data
    user_data = {
        "first_name": first_name,
        "last_name": last_name,
        "email": email,
        "is_active": True,
    }

    if phone_number:
        user_data["phone_number"] = phone_number

    try:
        # Create user with auto-generated credentials
        user = AuthenticationService.register_user(
            user_data=user_data,
            role_names=["Teacher"],
            created_by=created_by,
            send_email=kwargs.pop("send_welcome_email", True),
        )

        # Generate employee ID
        current_year = timezone.now().year
        prefix = f"TCH{current_year}"
        last_teacher = (
            Teacher.objects.filter(employee_id__startswith=prefix)
            .order_by("employee_id")
            .last()
        )

        if last_teacher:
            try:
                last_number = int(last_teacher.employee_id.replace(prefix, ""))
                new_number = last_number + 1
            except ValueError:
                new_number = 1
        else:
            new_number = 1

        employee_id = f"{prefix}{new_number:04d}"

        # Prepare teacher data with defaults
        teacher_data = {
            "user": user,
            "employee_id": employee_id,
            "joining_date": kwargs.pop("joining_date", timezone.now().date()),
            "qualification": kwargs.pop("qualification", ""),
            "experience_years": kwargs.pop("experience_years", 0),
            "specialization": kwargs.pop("specialization", ""),
            "position": kwargs.pop("position", "Teacher"),
            "salary": kwargs.pop("salary", 0),
            "contract_type": kwargs.pop("contract_type", "Permanent"),
            "status": kwargs.pop("status", "Active"),
            **kwargs,  # Any additional teacher fields
        }

        # Create teacher
        teacher = Teacher.objects.create(**teacher_data)

        return teacher

    except Exception as e:
        raise Exception(f"Failed to create teacher: {str(e)}")


# API endpoint for external systems
def create_teacher_api_endpoint(request):
    """
    API endpoint for creating teachers with defaults (for external systems)
    """
    if request.method != "POST":
        return JsonResponse({"error": "Only POST method allowed"}, status=405)

    if not request.user.has_perm("teachers.add_teacher"):
        return JsonResponse({"error": "Permission denied"}, status=403)

    try:
        data = json.loads(request.body)

        required_fields = ["first_name", "last_name", "email"]
        if not all(field in data for field in required_fields):
            return JsonResponse(
                {"error": f"Missing required fields: {required_fields}"}, status=400
            )

        teacher = create_teacher_with_defaults(
            first_name=data["first_name"],
            last_name=data["last_name"],
            email=data["email"],
            phone_number=data.get("phone_number"),
            qualification=data.get("qualification", ""),
            specialization=data.get("specialization", ""),
            created_by=request.user,
            send_welcome_email=data.get("send_welcome_email", True),
        )

        return JsonResponse(
            {
                "success": True,
                "teacher_id": teacher.id,
                "employee_id": teacher.employee_id,
                "username": teacher.user.username,
                "email": teacher.user.email,
                "full_name": teacher.user.get_full_name(),
                "message": "Teacher created successfully with auto-generated credentials",
            }
        )

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)


# NEW: Add bulk creation view (optional enhancement)
class TeacherBulkCreateView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    """Bulk create teachers from CSV data"""

    template_name = "teachers/teacher_bulk_create.html"
    permission_required = "teachers.add_teacher"

    def post(self, request):
        """Handle CSV upload and process teachers"""
        if "csv_data" not in request.POST:
            messages.error(request, "No CSV data provided")
            return self.render_to_response(self.get_context_data())

        csv_data = request.POST["csv_data"].strip()
        send_emails = request.POST.get("send_emails") == "on"

        if not csv_data:
            messages.error(request, "CSV data is empty")
            return self.render_to_response(self.get_context_data())

        # Process CSV data
        lines = csv_data.split("\n")
        if len(lines) < 2:
            messages.error(request, "CSV must have at least a header and one data row")
            return self.render_to_response(self.get_context_data())

        headers = [h.strip().lower() for h in lines[0].split(",")]
        required_headers = ["first_name", "last_name", "email"]

        if not all(header in headers for header in required_headers):
            messages.error(
                request, f'CSV must contain headers: {", ".join(required_headers)}'
            )
            return self.render_to_response(self.get_context_data())

        created_count = 0
        errors = []

        try:
            with transaction.atomic():
                for line_num, line in enumerate(lines[1:], start=2):
                    if not line.strip():
                        continue

                    try:
                        values = [v.strip() for v in line.split(",")]
                        if len(values) != len(headers):
                            errors.append(f"Line {line_num}: Column count mismatch")
                            continue

                        row_data = dict(zip(headers, values))

                        # Create teacher using utility function
                        teacher = create_teacher_with_defaults(
                            first_name=row_data["first_name"],
                            last_name=row_data["last_name"],
                            email=row_data["email"],
                            phone_number=row_data.get("phone_number", ""),
                            qualification=row_data.get("qualification", ""),
                            specialization=row_data.get("specialization", ""),
                            created_by=request.user,
                            send_welcome_email=send_emails,
                        )
                        created_count += 1

                    except Exception as e:
                        errors.append(f"Line {line_num}: {str(e)}")
                        continue

            # Show results
            if created_count > 0:
                messages.success(
                    request,
                    f"Successfully created {created_count} teacher(s) with auto-generated credentials.",
                )

            if errors:
                for error in errors[:5]:  # Show first 5 errors
                    messages.warning(request, error)

                if len(errors) > 5:
                    messages.warning(request, f"... and {len(errors) - 5} more errors.")

        except Exception as e:
            messages.error(request, f"Error processing CSV: {e}")

        return self.render_to_response(self.get_context_data())


def create_teacher_with_defaults_endpoint(request):
    """
    API endpoint for creating teachers with defaults (for external systems)
    """
    if request.method != "POST":
        return JsonResponse({"error": "Only POST method allowed"}, status=405)

    if not request.user.has_perm("teachers.add_teacher"):
        return JsonResponse({"error": "Permission denied"}, status=403)

    try:
        import json

        data = json.loads(request.body)

        required_fields = ["first_name", "last_name", "email"]
        if not all(field in data for field in required_fields):
            return JsonResponse(
                {"error": f"Missing required fields: {required_fields}"}, status=400
            )

        teacher = create_teacher_with_defaults(
            first_name=data["first_name"],
            last_name=data["last_name"],
            email=data["email"],
            phone_number=data.get("phone_number"),
            qualification=data.get("qualification", ""),
            specialization=data.get("specialization", ""),
            created_by=request.user,
            send_welcome_email=data.get("send_welcome_email", True),
        )

        return JsonResponse(
            {
                "success": True,
                "teacher_id": teacher.id,
                "employee_id": teacher.employee_id,
                "username": teacher.user.username,
                "email": teacher.user.email,
                "full_name": teacher.user.get_full_name(),
            }
        )

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)


class TeacherClassAssignmentCreateView(
    LoginRequiredMixin, PermissionRequiredMixin, CreateView
):
    model = TeacherClassAssignment
    permission_required = "teachers.assign_classes"
    form_class = TeacherClassAssignmentForm
    template_name = "teachers/assignment_form.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        teacher_id = self.kwargs.get("teacher_id")
        if teacher_id:
            context["teacher"] = get_object_or_404(Teacher, pk=teacher_id)
        return context

    def get_initial(self):
        initial = super().get_initial()
        teacher_id = self.kwargs.get("teacher_id")
        if teacher_id:
            initial["teacher"] = teacher_id
        return initial

    def get_success_url(self):
        teacher_id = self.object.teacher.id
        return reverse_lazy("teachers:teacher-detail", kwargs={"pk": teacher_id})

    def form_valid(self, form):
        messages.success(self.request, "Class assignment created successfully.")
        return super().form_valid(form)


class TeacherEvaluationCreateView(
    LoginRequiredMixin, PermissionRequiredMixin, CreateView
):
    model = TeacherEvaluation
    permission_required = "teachers.add_teacherevaluation"
    form_class = TeacherEvaluationForm
    template_name = "teachers/evaluation_form.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        teacher_id = self.kwargs.get("teacher_id")
        if teacher_id:
            context["teacher"] = get_object_or_404(Teacher, pk=teacher_id)
        return context

    def get_initial(self):
        initial = super().get_initial()
        teacher_id = self.kwargs.get("teacher_id")
        if teacher_id:
            initial["teacher"] = teacher_id
            initial["evaluation_date"] = timezone.now().date()
            initial["status"] = "submitted"
        return initial

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        form.instance.evaluator = self.request.user
        messages.success(self.request, "Teacher evaluation recorded successfully.")
        return super().form_valid(form)

    def get_success_url(self):
        teacher_id = self.object.teacher.id
        return reverse_lazy("teachers:teacher-detail", kwargs={"pk": teacher_id})


class TeacherTimetableView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = Teacher
    permission_required = "teachers.view_teacher"
    context_object_name = "teacher"
    template_name = "teachers/teacher_timetable.html"
    pk_url_kwarg = "teacher_id"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        teacher = self.get_object()

        # Get current academic year
        current_academic_year = AcademicYear.objects.filter(is_current=True).first()

        # Get timetable for the teacher
        from src.scheduling.services.timetable_service import (
            TimetableService as CourseTimetableService,
        )

        timetable = CourseTimetableService.get_teacher_timetable(
            teacher=teacher, academic_year=current_academic_year
        )

        context["timetable"] = timetable
        context["current_academic_year"] = current_academic_year
        context["days_of_week"] = [
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday",
            "Saturday",
        ]

        return context


class TeacherTimetablePDFView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = Teacher
    permission_required = "teachers.view_teacher"
    pk_url_kwarg = "teacher_id"

    def get(self, request, *args, **kwargs):
        teacher = self.get_object()

        # Get current academic year
        current_academic_year = AcademicYear.objects.filter(is_current=True).first()

        # Generate PDF response
        return TimetableService.generate_timetable_pdf(
            teacher=teacher, academic_year=current_academic_year
        )


class TeacherDashboardView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    template_name = "teachers/teacher_dashboard.html"
    permission_required = "teachers.view_teacher"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get summary statistics
        stats = TeacherService.get_teacher_statistics()
        context.update(stats)

        # Get recent evaluations
        context["recent_evaluations"] = TeacherEvaluation.objects.select_related(
            "teacher", "teacher__user", "evaluator"
        ).order_by("-evaluation_date")[:5]

        # Get average score by department for ApexCharts
        dept_scores = TeacherService.get_departmental_performance()

        # Get top performing teachers
        context["top_teachers"] = TeacherService.get_top_performing_teachers(5)

        # Get teachers by workload
        context["teacher_workload"] = TeacherService.get_teacher_workload()[:10]

        # Get teachers requiring follow-up
        context["followup_evaluations"] = (
            EvaluationService.get_evaluations_requiring_followup()[:5]
        )

        # Get performance trends for charts
        performance_trend = TeacherService.get_teacher_performance_trend()

        # Prepare apex chart data
        context["chart_data"] = {
            "departments": json.dumps([d.name for d in dept_scores]),
            "dept_counts": json.dumps([d.teacher_count for d in dept_scores]),
            "dept_scores": json.dumps(
                [float(d.avg_score) if d.avg_score else 0 for d in dept_scores]
            ),
            "trend_months": json.dumps(performance_trend["months"]),
            "trend_scores": json.dumps(performance_trend["scores"]),
            "trend_counts": json.dumps(performance_trend["counts"]),
        }

        # Get current academic year
        context["current_academic_year"] = AcademicYear.objects.filter(
            is_current=True
        ).first()

        return context


class TeacherStatisticsView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    template_name = "teachers/teacher_statistics.html"
    permission_required = "teachers.view_teacher_analytics"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Basic statistics
        stats = TeacherService.get_teacher_statistics()
        context.update(stats)

        # Get performance by experience
        experience_stats = TeacherService.get_performance_by_experience()

        # Get departmental performance
        dept_performance = TeacherService.get_departmental_performance()

        # Get evaluation trends
        evaluation_trends = EvaluationService.get_evaluation_trend()

        # Get evaluation summary by criteria
        criteria_summary = EvaluationService.get_evaluation_summary_by_criteria()

        # Prepare ApexCharts data
        context["chart_data"] = {
            "contract_types": json.dumps(
                [c["contract_type"] for c in stats["contract_distribution"]]
            ),
            "contract_counts": json.dumps(
                [c["count"] for c in stats["contract_distribution"]]
            ),
            "tenure_ranges": json.dumps(
                [t["range"] for t in stats["tenure_distribution"]]
            ),
            "tenure_counts": json.dumps(
                [t["count"] for t in stats["tenure_distribution"]]
            ),
            "exp_ranges": json.dumps([e["range"] for e in experience_stats]),
            "exp_scores": json.dumps(
                [
                    float(e["avg_score"]) if e["avg_score"] else 0
                    for e in experience_stats
                ]
            ),
            "exp_counts": json.dumps([e["count"] for e in experience_stats]),
            "departments": json.dumps([d.name for d in dept_performance]),
            "dept_teachers": json.dumps([d.teacher_count for d in dept_performance]),
            "dept_scores": json.dumps(
                [float(d.avg_score) if d.avg_score else 0 for d in dept_performance]
            ),
            "dept_experience": json.dumps(
                [
                    float(d.avg_experience) if d.avg_experience else 0
                    for d in dept_performance
                ]
            ),
            "eval_months": json.dumps(evaluation_trends["labels"]),
            "eval_scores": json.dumps(evaluation_trends["avg_scores"]),
            "eval_counts": json.dumps(evaluation_trends["counts"]),
            "eval_min": json.dumps(evaluation_trends["min_scores"]),
            "eval_max": json.dumps(evaluation_trends["max_scores"]),
            "criteria": json.dumps(list(criteria_summary.keys())),
            "criteria_scores": json.dumps(
                [float(c["percentage"]) for c in criteria_summary.values()]
            ),
        }

        return context


class TeacherPerformanceView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    template_name = "teachers/teacher_performance.html"
    permission_required = "teachers.view_teacher_analytics"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get performance data
        performance_by_exp = TeacherService.get_performance_by_experience()

        # Get performance ranking
        teachers_with_scores = (
            Teacher.objects.active()
            .with_evaluation_stats()
            .filter(avg_evaluation_score__isnull=False)
            .order_by("-avg_evaluation_score")[:50]
        )

        # Evaluation distribution
        evaluation_distribution = [
            {
                "range": "Excellent (90-100%)",
                "count": TeacherEvaluation.objects.filter(score__gte=90).count(),
                "percentage": TeacherEvaluation.objects.filter(score__gte=90).count()
                / max(TeacherEvaluation.objects.count(), 1)
                * 100,
            },
            {
                "range": "Good (80-89%)",
                "count": TeacherEvaluation.objects.filter(
                    score__gte=80, score__lt=90
                ).count(),
                "percentage": TeacherEvaluation.objects.filter(
                    score__gte=80, score__lt=90
                ).count()
                / max(TeacherEvaluation.objects.count(), 1)
                * 100,
            },
            {
                "range": "Satisfactory (70-79%)",
                "count": TeacherEvaluation.objects.filter(
                    score__gte=70, score__lt=80
                ).count(),
                "percentage": TeacherEvaluation.objects.filter(
                    score__gte=70, score__lt=80
                ).count()
                / max(TeacherEvaluation.objects.count(), 1)
                * 100,
            },
            {
                "range": "Needs Improvement (60-69%)",
                "count": TeacherEvaluation.objects.filter(
                    score__gte=60, score__lt=70
                ).count(),
                "percentage": TeacherEvaluation.objects.filter(
                    score__gte=60, score__lt=70
                ).count()
                / max(TeacherEvaluation.objects.count(), 1)
                * 100,
            },
            {
                "range": "Poor (Below 60%)",
                "count": TeacherEvaluation.objects.filter(score__lt=60).count(),
                "percentage": TeacherEvaluation.objects.filter(score__lt=60).count()
                / max(TeacherEvaluation.objects.count(), 1)
                * 100,
            },
        ]

        # Set context data
        context["teachers_ranking"] = teachers_with_scores
        context["evaluation_distribution"] = evaluation_distribution
        context["performance_by_exp"] = performance_by_exp

        # Prepare chart data
        context["chart_data"] = {
            "exp_ranges": json.dumps([e["range"] for e in performance_by_exp]),
            "exp_scores": json.dumps(
                [
                    float(e["avg_score"]) if e["avg_score"] else 0
                    for e in performance_by_exp
                ]
            ),
            "eval_ranges": json.dumps([e["range"] for e in evaluation_distribution]),
            "eval_counts": json.dumps([e["count"] for e in evaluation_distribution]),
            "eval_percentages": json.dumps(
                [e["percentage"] for e in evaluation_distribution]
            ),
            "teacher_names": json.dumps(
                [t.get_full_name() for t in teachers_with_scores]
            ),
            "teacher_scores": json.dumps(
                [float(t.avg_evaluation_score) for t in teachers_with_scores]
            ),
        }

        return context


class TeacherExportView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = "teachers.export_teacher_data"

    def get(self, request, *args, **kwargs):
        export_format = kwargs.get("format", "csv")

        # Get filter parameters
        filters = {
            "status": request.GET.get("status"),
            "department": request.GET.get("department"),
            "contract_type": request.GET.get("contract_type"),
        }

        # Get teacher data
        teachers = TeacherService.get_teacher_export_data(filters)

        if export_format == "csv":
            response = HttpResponse(content_type="text/csv")
            response["Content-Disposition"] = (
                'attachment; filename="teachers_export.csv"'
            )

            writer = csv.writer(response)
            writer.writerow(
                [
                    "Employee ID",
                    "First Name",
                    "Last Name",
                    "Email",
                    "Department",
                    "Position",
                    "Status",
                    "Contract Type",
                    "Experience (Years)",
                    "Joining Date",
                    "Salary",
                    "Qualification",
                ]
            )

            for teacher in teachers:
                writer.writerow(
                    [
                        teacher.employee_id,
                        teacher.user.first_name,
                        teacher.user.last_name,
                        teacher.user.email,
                        teacher.department.name if teacher.department else "N/A",
                        teacher.position,
                        teacher.status,
                        teacher.contract_type,
                        teacher.experience_years,
                        teacher.joining_date,
                        teacher.salary,
                        teacher.qualification,
                    ]
                )

            return response

        else:
            # For other formats (could be implemented with appropriate libraries)
            messages.warning(
                request, f"Export to {export_format} is not yet implemented."
            )
            return redirect("teachers:teacher-list")


class TeacherApiView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = "teachers.view_teacher"

    def get(self, request, *args, **kwargs):
        """API endpoint for AJAX requests from DataTables"""
        # Get request parameters
        draw = int(request.GET.get("draw", 1))
        start = int(request.GET.get("start", 0))
        length = int(request.GET.get("length", 10))
        search_value = request.GET.get("search[value]", "")

        # Initial queryset
        queryset = Teacher.objects.select_related("user", "department")

        # Apply search filter
        if search_value:
            queryset = queryset.filter(
                Q(employee_id__icontains=search_value)
                | Q(user__first_name__icontains=search_value)
                | Q(user__last_name__icontains=search_value)
                | Q(user__email__icontains=search_value)
                | Q(department__name__icontains=search_value)
                | Q(position__icontains=search_value)
            )

        # Get total record count
        total_records = Teacher.objects.count()
        filtered_records = queryset.count()

        # Apply pagination
        queryset = queryset[start : start + length]

        # Prepare data for response
        data = []
        for teacher in queryset:
            data.append(
                {
                    "id": teacher.id,
                    "employee_id": teacher.employee_id,
                    "name": f"{teacher.user.first_name} {teacher.user.last_name}",
                    "email": teacher.user.email,
                    "department": (
                        teacher.department.name if teacher.department else "N/A"
                    ),
                    "position": teacher.position,
                    "status": teacher.status,
                    "experience": float(teacher.experience_years),
                    "joining_date": teacher.joining_date.strftime("%Y-%m-%d"),
                    "actions": f'<a href="{reverse("teachers:teacher-detail", kwargs={"pk": teacher.id})}" class="btn btn-sm btn-info"><i class="fas fa-eye"></i></a>',
                }
            )

        # Return JSON response
        return JsonResponse(
            {
                "draw": draw,
                "recordsTotal": total_records,
                "recordsFiltered": filtered_records,
                "data": data,
            }
        )
