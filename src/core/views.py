from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.generic import (
    ListView,
    DetailView,
    UpdateView,
    CreateView,
    DeleteView,
)
from django.utils.decorators import method_decorator
from django.contrib import messages
from django.db.models import Q, Count
from django.apps import apps
from django.urls import reverse_lazy
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.core.paginator import Paginator
import csv
import json
from datetime import timedelta, datetime

from .models import SystemSetting, AuditLog, Document
from .forms import (
    SystemSettingForm,
    DocumentForm,
    DocumentSearchForm,
    AuditLogSearchForm,
)
from .decorators import role_required, module_access_required, audit_log
from .utils import get_system_setting, safe_get_count, academic_year_for_date
from django.contrib.auth import get_user_model

User = get_user_model()


@login_required
def dashboard(request):
    """Main dashboard view with enhanced statistics."""
    context = {
        "title": "Dashboard",
    }

    # Get current academic year
    current_academic_year = academic_year_for_date()
    if current_academic_year:
        context["current_academic_year"] = current_academic_year

    # Get relevant statistics based on user role
    if request.user.is_staff:
        # Admin dashboard with enhanced statistics
        Student = apps.get_model("students", "Student")
        Teacher = apps.get_model("teachers", "Teacher")
        Class = apps.get_model("courses", "Class")

        # Basic counts
        student_count = safe_get_count(Student)
        teacher_count = safe_get_count(Teacher)
        class_count = safe_get_count(Class)

        # Enhanced student statistics
        try:
            # Student status distribution for pie chart
            student_status = list(
                Student.objects.values("status")
                .annotate(count=Count("status"))
                .order_by("status")
            )

            # Gender distribution
            gender_distribution = list(
                Student.objects.values("user__gender")
                .annotate(count=Count("user__gender"))
                .order_by("user__gender")
            )

            # Class distribution (top 5 classes by enrollment)
            class_distribution = list(
                Student.objects.values(
                    "current_class__grade__name", "current_class__section__name"
                )
                .annotate(count=Count("id"))
                .order_by("-count")[:5]
            )

            # New admissions in the last 6 months
            six_months_ago = timezone.now() - timedelta(days=180)
            monthly_admissions = list(
                Student.objects.filter(admission_date__gte=six_months_ago)
                .annotate(month=TruncMonth("admission_date"))
                .values("month")
                .annotate(count=Count("id"))
                .order_by("month")
            )
        except:
            student_status = []
            gender_distribution = []
            class_distribution = []
            monthly_admissions = []

        # Teacher statistics
        try:
            # Department distribution
            department_distribution = list(
                Teacher.objects.values("department__name")
                .annotate(count=Count("id"))
                .order_by("-count")
            )

            # Experience levels
            experience_levels = {
                "0-2 years": Teacher.objects.filter(experience_years__lt=2).count(),
                "2-5 years": Teacher.objects.filter(
                    experience_years__gte=2, experience_years__lt=5
                ).count(),
                "5-10 years": Teacher.objects.filter(
                    experience_years__gte=5, experience_years__lt=10
                ).count(),
                "10+ years": Teacher.objects.filter(experience_years__gte=10).count(),
            }
        except:
            department_distribution = []
            experience_levels = {}

        # Attendance statistics
        try:
            Attendance = apps.get_model("attendance", "Attendance")
            # Last 30 days attendance trend
            thirty_days_ago = timezone.now().date() - timedelta(days=30)
            attendance_trend = list(
                Attendance.objects.filter(date__gte=thirty_days_ago)
                .values("date")
                .annotate(
                    present=Count("id", filter=Q(status="Present")),
                    absent=Count("id", filter=Q(status="Absent")),
                    late=Count("id", filter=Q(status="Late")),
                )
                .order_by("date")
            )

            # Overall attendance rate
            total_records = Attendance.objects.filter(date__gte=thirty_days_ago).count()
            present_count = Attendance.objects.filter(
                date__gte=thirty_days_ago, status="Present"
            ).count()
            attendance_rate = (
                round((present_count / total_records) * 100, 2)
                if total_records > 0
                else 0
            )
        except:
            attendance_trend = []
            attendance_rate = 0

        # Financial statistics
        try:
            Invoice = apps.get_model("finance", "Invoice")
            Payment = apps.get_model("finance", "Payment")

            # Fee collection statistics for current academic year
            current_year_invoices = Invoice.objects.filter(
                academic_year=current_academic_year
            )
            total_invoiced = (
                current_year_invoices.aggregate(Sum("total_amount"))[
                    "total_amount__sum"
                ]
                or 0
            )
            total_collected = (
                Payment.objects.filter(
                    invoice__academic_year=current_academic_year
                ).aggregate(Sum("amount"))["amount__sum"]
                or 0
            )
            collection_rate = (
                round((total_collected / total_invoiced) * 100, 2)
                if total_invoiced > 0
                else 0
            )

            # Monthly fee collection for the current academic year
            monthly_collection = list(
                Payment.objects.filter(invoice__academic_year=current_academic_year)
                .annotate(month=TruncMonth("payment_date"))
                .values("month")
                .annotate(amount=Sum("amount"))
                .order_by("month")
            )
        except:
            total_invoiced = 0
            total_collected = 0
            collection_rate = 0
            monthly_collection = []

        # System usage statistics
        active_users_24h = User.objects.filter(
            last_login__gte=timezone.now() - timedelta(hours=24)
        ).count()
        document_count = safe_get_count(Document)

        # Compile all statistics
        context.update(
            {
                # Basic counts
                "total_students": student_count,
                "total_teachers": teacher_count,
                "total_classes": class_count,
                # Student statistics
                "student_status": student_status,
                "gender_distribution": gender_distribution,
                "class_distribution": class_distribution,
                "monthly_admissions": monthly_admissions,
                # Teacher statistics
                "department_distribution": department_distribution,
                "experience_levels": experience_levels,
                # Attendance statistics
                "attendance_trend": attendance_trend,
                "attendance_rate": attendance_rate,
                # Financial statistics
                "total_invoiced": total_invoiced,
                "total_collected": total_collected,
                "collection_rate": collection_rate,
                "monthly_collection": monthly_collection,
                # System statistics
                "active_users_24h": active_users_24h,
                "document_count": document_count,
                # Recent activities for audit log
                "recent_activities": AuditLog.objects.order_by("-timestamp")[:10],
                "recent_documents": Document.objects.filter(is_public=True).order_by(
                    "-upload_date"
                )[:5],
            }
        )

    # Continue with role-specific dashboards with enhanced statistics
    elif hasattr(request.user, "teacher_profile"):
        # Teacher dashboard with enhanced statistics
        teacher = request.user.teacher_profile

        # Get assigned classes with student counts
        assigned_classes = []
        try:
            from django.db.models import Count

            TeacherClassAssignment = apps.get_model(
                "teachers", "TeacherClassAssignment"
            )

            assigned_classes = (
                TeacherClassAssignment.objects.filter(teacher=teacher)
                .select_related("class_instance", "subject", "academic_year")
                .annotate(student_count=Count("class_instance__students"))
                .order_by("class_instance__grade__name")
            )

            # Get assignment statistics
            Assignment = apps.get_model("courses", "Assignment")
            AssignmentSubmission = apps.get_model("courses", "AssignmentSubmission")

            # Assignments by status
            assignment_stats = (
                Assignment.objects.filter(teacher=teacher)
                .values("status")
                .annotate(count=Count("id"))
                .order_by("status")
            )

            # Assignments by submission status (for published assignments)
            published_assignments = Assignment.objects.filter(
                teacher=teacher, status="published"
            )
            submission_stats = []

            for assignment in published_assignments:
                total_students = assignment.class_obj.students.count()
                submitted = AssignmentSubmission.objects.filter(
                    assignment=assignment
                ).count()
                not_submitted = total_students - submitted

                submission_stats.append(
                    {
                        "assignment": assignment.title,
                        "submitted": submitted,
                        "not_submitted": not_submitted,
                    }
                )

            # Recent submissions
            recent_submissions = (
                AssignmentSubmission.objects.filter(assignment__teacher=teacher)
                .select_related("student", "student__user", "assignment")
                .order_by("-submission_date")[:10]
            )
        except:
            assigned_classes = []
            assignment_stats = []
            submission_stats = []
            recent_submissions = []

        context.update(
            {
                "teacher": teacher,
                "assigned_classes": assigned_classes,
                "assignment_stats": assignment_stats,
                "submission_stats": submission_stats,
                "recent_submissions": recent_submissions,
            }
        )

    elif hasattr(request.user, "parent_profile"):
        # Parent dashboard with enhanced statistics
        parent = request.user.parent_profile

        try:
            # Get children with enhanced data
            Student = apps.get_model("students", "Student")
            StudentParentRelation = apps.get_model("students", "StudentParentRelation")
            Attendance = apps.get_model("attendance", "Attendance")
            ExamResult = apps.get_model("exams", "StudentExamResult")

            # Get children IDs
            children_relations = StudentParentRelation.objects.filter(parent=parent)
            children_ids = [rel.student_id for rel in children_relations]

            # Get children with attendance data
            children = Student.objects.filter(id__in=children_ids).select_related(
                "user", "current_class"
            )

            children_data = []
            for child in children:
                # Get attendance statistics
                thirty_days_ago = timezone.now().date() - timedelta(days=30)
                attendance_records = Attendance.objects.filter(
                    student=child, date__gte=thirty_days_ago
                )
                present_count = attendance_records.filter(status="Present").count()
                absent_count = attendance_records.filter(status="Absent").count()
                late_count = attendance_records.filter(status="Late").count()
                total_days = present_count + absent_count + late_count

                # Calculate attendance percentage
                attendance_percentage = (
                    (present_count / total_days * 100) if total_days > 0 else 0
                )

                # Get recent exam results
                recent_exams = (
                    ExamResult.objects.filter(student=child)
                    .select_related("exam_schedule", "exam_schedule__subject")
                    .order_by("-entry_date")[:3]
                )

                # Calculate average marks
                all_exams = ExamResult.objects.filter(student=child)
                avg_percentage = (
                    all_exams.aggregate(Avg("percentage"))["percentage__avg"] or 0
                )

                children_data.append(
                    {
                        "student": child,
                        "attendance": {
                            "present": present_count,
                            "absent": absent_count,
                            "late": late_count,
                            "percentage": round(attendance_percentage, 2),
                        },
                        "recent_exams": recent_exams,
                        "avg_percentage": round(avg_percentage, 2),
                    }
                )

            # Fee information
            Invoice = apps.get_model("finance", "Invoice")
            pending_invoices = Invoice.objects.filter(
                student__in=children_ids,
                status__in=["unpaid", "partially_paid", "overdue"],
            ).select_related("student", "student__user")
        except:
            children_data = []
            pending_invoices = []

        context.update(
            {
                "parent": parent,
                "children_data": children_data,
                "pending_invoices": pending_invoices,
            }
        )

    elif hasattr(request.user, "student_profile"):
        # Student dashboard with enhanced statistics
        student = request.user.student_profile

        try:
            # Get attendance statistics
            Attendance = apps.get_model("attendance", "Attendance")

            # Monthly attendance for current academic year
            current_year_start = (
                current_academic_year.start_date
                if current_academic_year
                else timezone.now().date().replace(month=1, day=1)
            )

            monthly_attendance = (
                Attendance.objects.filter(student=student, date__gte=current_year_start)
                .annotate(month=TruncMonth("date"))
                .values("month", "status")
                .annotate(count=Count("id"))
                .order_by("month", "status")
            )

            # Format for chart display
            attendance_by_month = {}
            for item in monthly_attendance:
                month_str = item["month"].strftime("%b %Y")
                if month_str not in attendance_by_month:
                    attendance_by_month[month_str] = {
                        "Present": 0,
                        "Absent": 0,
                        "Late": 0,
                    }
                attendance_by_month[month_str][item["status"]] = item["count"]

            # Get academic performance data
            ExamResult = apps.get_model("exams", "StudentExamResult")

            # Get all exam results for the student
            exam_results = (
                ExamResult.objects.filter(student=student)
                .select_related("exam_schedule", "exam_schedule__subject")
                .order_by("-exam_schedule__date")
            )

            # Calculate subject-wise performance
            subject_performance = {}
            for result in exam_results:
                subject_name = result.exam_schedule.subject.name
                if subject_name not in subject_performance:
                    subject_performance[subject_name] = {
                        "total_exams": 0,
                        "total_percentage": 0,
                        "highest": 0,
                        "lowest": 100,
                    }

                subject_performance[subject_name]["total_exams"] += 1
                subject_performance[subject_name][
                    "total_percentage"
                ] += result.percentage
                subject_performance[subject_name]["highest"] = max(
                    subject_performance[subject_name]["highest"], result.percentage
                )
                subject_performance[subject_name]["lowest"] = min(
                    subject_performance[subject_name]["lowest"], result.percentage
                )

            # Calculate averages
            for subject in subject_performance:
                if subject_performance[subject]["total_exams"] > 0:
                    subject_performance[subject]["average"] = round(
                        subject_performance[subject]["total_percentage"]
                        / subject_performance[subject]["total_exams"],
                        2,
                    )

            # Get assignment statistics
            Assignment = apps.get_model("courses", "Assignment")
            AssignmentSubmission = apps.get_model("courses", "AssignmentSubmission")

            if student.current_class:
                # Get all assignments for student's class
                assignments = Assignment.objects.filter(class_obj=student.current_class)

                # Count by status
                completed_assignments = AssignmentSubmission.objects.filter(
                    student=student, assignment__in=assignments
                ).count()

                pending_assignments = assignments.filter(
                    status="published", due_date__gte=timezone.now().date()
                ).exclude(submissions__student=student)

                overdue_assignments = assignments.filter(
                    status="published", due_date__lt=timezone.now().date()
                ).exclude(submissions__student=student)

                # Assignment statistics
                assignment_stats = {
                    "completed": completed_assignments,
                    "pending": pending_assignments.count(),
                    "overdue": overdue_assignments.count(),
                    "total": assignments.count(),
                }
        except:
            attendance_by_month = {}
            exam_results = []
            subject_performance = {}
            assignment_stats = {"completed": 0, "pending": 0, "overdue": 0, "total": 0}
            pending_assignments = []
            overdue_assignments = []

        context.update(
            {
                "student": student,
                "attendance_by_month": attendance_by_month,
                "exam_results": exam_results[:5],  # Most recent 5
                "subject_performance": subject_performance,
                "assignment_stats": assignment_stats,
                "pending_assignments": pending_assignments[:5],  # Top 5 pending
                "overdue_assignments": overdue_assignments[:5],  # Top 5 overdue
            }
        )

    return render(request, "dashboard.html", context)


@method_decorator(login_required, name="dispatch")
class DocumentListView(ListView):
    model = Document
    template_name = "core/document_list.html"
    context_object_name = "documents"
    paginate_by = 20

    def get_queryset(self):
        queryset = super().get_queryset()

        # Filter by public documents or user's own documents
        if not self.request.user.is_staff:
            queryset = queryset.filter(
                Q(is_public=True) | Q(uploaded_by=self.request.user)
            )

        # Get form data
        form = DocumentSearchForm(self.request.GET)

        # Apply search if provided
        search_query = self.request.GET.get("q")
        if search_query:
            queryset = queryset.filter(
                Q(title__icontains=search_query)
                | Q(description__icontains=search_query)
                | Q(category__icontains=search_query)
            )

        # Filter by category if provided
        category = self.request.GET.get("category")
        if category:
            queryset = queryset.filter(category=category)

        return queryset.order_by("-upload_date")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["form"] = DocumentSearchForm(self.request.GET)
        return context


@method_decorator(login_required, name="dispatch")
class DocumentDetailView(DetailView):
    model = Document
    template_name = "core/document_detail.html"
    context_object_name = "document"

    def get_object(self):
        obj = super().get_object()
        # Check access permissions
        if (
            not obj.is_public
            and obj.uploaded_by != self.request.user
            and not self.request.user.is_staff
        ):
            raise PermissionDenied
        return obj


@method_decorator(login_required, name="dispatch")
class DocumentCreateView(CreateView):
    model = Document
    form_class = DocumentForm
    template_name = "core/document_form.html"
    success_url = reverse_lazy("core:document_list")

    def form_valid(self, form):
        form.instance.uploaded_by = self.request.user

        # Set file type based on uploaded file
        file = form.cleaned_data.get("file_path")
        if file:
            form.instance.file_type = file.name.split(".")[-1].lower()

        messages.success(self.request, "Document uploaded successfully.")
        return super().form_valid(form)


@method_decorator(login_required, name="dispatch")
class DocumentUpdateView(UpdateView):
    model = Document
    form_class = DocumentForm
    template_name = "core/document_form.html"
    success_url = reverse_lazy("core:document_list")

    def get_queryset(self):
        # Only allow users to edit their own documents or staff to edit any
        if self.request.user.is_staff:
            return Document.objects.all()
        return Document.objects.filter(uploaded_by=self.request.user)

    def form_valid(self, form):
        messages.success(self.request, "Document updated successfully.")
        return super().form_valid(form)


@method_decorator(login_required, name="dispatch")
class DocumentDeleteView(DeleteView):
    model = Document
    template_name = "core/document_confirm_delete.html"
    success_url = reverse_lazy("core:document_list")

    def get_queryset(self):
        # Only allow users to delete their own documents or staff to delete any
        if self.request.user.is_staff:
            return Document.objects.all()
        return Document.objects.filter(uploaded_by=self.request.user)

    def delete(self, request, *args, **kwargs):
        messages.success(request, "Document deleted successfully.")
        return super().delete(request, *args, **kwargs)


@method_decorator(login_required, name="dispatch")
@method_decorator(role_required("Admin"), name="dispatch")
class SystemSettingListView(ListView):
    model = SystemSetting
    template_name = "core/system_setting_list.html"
    context_object_name = "settings"

    def get_queryset(self):
        return SystemSetting.objects.filter(is_editable=True).order_by("setting_key")


@method_decorator(login_required, name="dispatch")
@method_decorator(role_required("Admin"), name="dispatch")
class SystemSettingUpdateView(UpdateView):
    model = SystemSetting
    form_class = SystemSettingForm
    template_name = "core/system_setting_form.html"
    success_url = reverse_lazy("core:system_setting_list")

    def get_queryset(self):
        return SystemSetting.objects.filter(is_editable=True)

    def form_valid(self, form):
        messages.success(
            self.request,
            f"System setting '{self.object.setting_key}' updated successfully.",
        )
        return super().form_valid(form)


@login_required
@role_required("Admin")
def system_maintenance_toggle(request):
    """Toggle maintenance mode."""
    from .services import SystemSettingService

    current_state = get_system_setting("maintenance_mode", False)
    new_state = not current_state

    success, message = SystemSettingService.update_setting(
        "maintenance_mode", new_state
    )

    if success:
        status_message = "enabled" if new_state else "disabled"
        messages.success(request, f"Maintenance mode {status_message} successfully.")
    else:
        messages.error(request, f"Failed to update maintenance mode: {message}")

    return redirect("core:system_setting_list")


@login_required
@role_required("Admin")
def audit_log_view(request):
    """View system audit logs with filtering."""
    # Initialize queryset
    queryset = AuditLog.objects.select_related("user").order_by("-timestamp")

    # Create and populate form
    form = AuditLogSearchForm(request.GET)

    # Apply filters if form is valid
    if form.is_valid():
        # Filter by user
        user_filter = form.cleaned_data.get("user")
        if user_filter:
            queryset = queryset.filter(
                Q(user__username__icontains=user_filter)
                | Q(user__first_name__icontains=user_filter)
                | Q(user__last_name__icontains=user_filter)
            )

        # Filter by action
        action_filter = form.cleaned_data.get("action")
        if action_filter:
            queryset = queryset.filter(action=action_filter)

        # Filter by entity type
        entity_type_filter = form.cleaned_data.get("entity_type")
        if entity_type_filter:
            queryset = queryset.filter(entity_type__icontains=entity_type_filter)

        # Filter by date range
        date_from = form.cleaned_data.get("date_from")
        if date_from:
            queryset = queryset.filter(timestamp__date__gte=date_from)

        date_to = form.cleaned_data.get("date_to")
        if date_to:
            queryset = queryset.filter(timestamp__date__lte=date_to)

    # Paginate results
    paginator = Paginator(queryset, 30)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "form": form,
        "page_obj": page_obj,
        "audit_logs": page_obj.object_list,
    }

    # Handle export if requested
    if "export" in request.GET:
        return export_audit_logs(request, queryset)

    return render(request, "core/audit_log.html", context)


def export_audit_logs(request, queryset):
    """Export audit logs to CSV."""
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="audit_logs.csv"'

    writer = csv.writer(response)
    writer.writerow(
        ["Timestamp", "User", "Action", "Entity Type", "Entity ID", "IP Address"]
    )

    for log in queryset:
        writer.writerow(
            [
                log.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                log.user.username if log.user else "System",
                log.action,
                log.entity_type,
                log.entity_id or "",
                log.ip_address or "",
            ]
        )

    return response


@login_required
@role_required("Admin")
def system_info_view(request):
    """View system information including versions, environment, etc."""
    import platform
    import sys
    import django

    context = {
        "python_version": platform.python_version(),
        "django_version": django.get_version(),
        "system_platform": platform.platform(),
        "system_node": platform.node(),
        "system_time": timezone.now(),
    }

    # Get installed apps
    context["installed_apps"] = [app.name for app in apps.get_app_configs()]

    # Get database info
    from django.db import connection

    db_info = connection.settings_dict
    context["database_engine"] = db_info["ENGINE"].split(".")[-1]
    context["database_name"] = db_info["NAME"]

    return render(request, "core/system_info.html", context)
