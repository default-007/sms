import csv
import json
from datetime import datetime, timedelta

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Avg, Case, Count, F, IntegerField, Q, Sum, Value, When
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

from src.courses.models import AcademicYear, Department

from .forms import (
    TeacherClassAssignmentForm,
    TeacherEvaluationForm,
    TeacherFilterForm,
    TeacherForm,
)
from .models import Teacher, TeacherClassAssignment, TeacherEvaluation
from .services import EvaluationService, TeacherService, TimetableService


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
        from src.courses.services.timetable_service import TimetableService

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
    model = Teacher
    permission_required = "teachers.add_teacher"
    form_class = TeacherForm
    template_name = "teachers/teacher_form.html"
    success_url = reverse_lazy("teachers:teacher-list")

    def form_valid(self, form):
        messages.success(self.request, "Teacher created successfully.")
        return super().form_valid(form)


class TeacherUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = Teacher
    permission_required = "teachers.change_teacher"
    form_class = TeacherForm
    template_name = "teachers/teacher_form.html"

    def get_success_url(self):
        return reverse_lazy("teachers:teacher-detail", kwargs={"pk": self.object.pk})

    def form_valid(self, form):
        messages.success(self.request, "Teacher updated successfully.")
        return super().form_valid(form)


class TeacherDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = Teacher
    permission_required = "teachers.delete_teacher"
    template_name = "teachers/teacher_confirm_delete.html"
    success_url = reverse_lazy("teachers:teacher-list")

    def delete(self, request, *args, **kwargs):
        messages.success(request, "Teacher deleted successfully.")
        return super().delete(request, *args, **kwargs)


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
        from src.courses.services.timetable_service import (
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
