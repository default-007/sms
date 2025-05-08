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


@login_required
def dashboard(request):
    """Main dashboard view."""
    context = {
        "title": "Dashboard",
    }

    # Get current academic year
    current_academic_year = academic_year_for_date()
    if current_academic_year:
        context["current_academic_year"] = current_academic_year

    # Get relevant statistics based on user role
    if request.user.is_staff:
        # Admin dashboard
        Student = apps.get_model("students", "Student")
        Teacher = apps.get_model("teachers", "Teacher")
        Class = apps.get_model("courses", "Class")

        # Get statistics for admin dashboard
        student_count = safe_get_count(Student)
        teacher_count = safe_get_count(Teacher)
        class_count = safe_get_count(Class)

        # Get student status distribution
        try:
            student_status = Student.objects.values("status").annotate(
                count=Count("status")
            )
            context["student_status"] = student_status
        except:
            context["student_status"] = []

        # Get recent activities
        context.update(
            {
                "total_students": student_count,
                "total_teachers": teacher_count,
                "total_classes": class_count,
                "recent_activities": AuditLog.objects.order_by("-timestamp")[:10],
            }
        )

        # Get recent documents
        context["recent_documents"] = Document.objects.filter(is_public=True).order_by(
            "-upload_date"
        )[:5]

        # Get online users (active in last 15 minutes)
        User = apps.get_model("auth", "User")
        fifteen_minutes_ago = timezone.now() - timedelta(minutes=15)
        context["online_users_count"] = User.objects.filter(
            last_login__gte=fifteen_minutes_ago
        ).count()

    elif hasattr(request.user, "teacher_profile"):
        # Teacher dashboard
        Teacher = apps.get_model("teachers", "Teacher")
        Class = apps.get_model("courses", "Class")
        Assignment = apps.get_model("courses", "Assignment")

        teacher = request.user.teacher_profile

        # Get teacher's assigned classes
        assigned_classes = []
        try:
            assigned_classes = Class.objects.filter(
                teacherclassassignment__teacher=teacher
            ).distinct()
        except:
            pass

        # Get pending assignments
        pending_assignments = 0
        try:
            pending_assignments = Assignment.objects.filter(
                teacher=teacher, status__in=["draft", "published"]
            ).count()
        except:
            pass

        # Get upcoming evaluations if applicable
        upcoming_evaluations = []
        TeacherEvaluation = apps.get_model("teachers", "TeacherEvaluation")
        try:
            upcoming_evaluations = TeacherEvaluation.objects.filter(
                teacher=teacher, evaluation_date__gte=timezone.now().date()
            ).order_by("evaluation_date")[:5]
        except:
            pass

        context.update(
            {
                "teacher": teacher,
                "assigned_classes": assigned_classes,
                "pending_assignments": pending_assignments,
                "upcoming_evaluations": upcoming_evaluations,
            }
        )

    elif hasattr(request.user, "parent_profile"):
        # Parent dashboard
        Parent = apps.get_model("students", "Parent")
        Student = apps.get_model("students", "Student")

        parent = request.user.parent_profile
        children = []

        try:
            # Get parent's children
            children = Student.objects.filter(student_parent_relations__parent=parent)

            # Get fee information if available
            Invoice = apps.get_model("finance", "Invoice")
            pending_invoices = Invoice.objects.filter(
                student__in=children, status__in=["unpaid", "partially_paid", "overdue"]
            ).count()
            context["pending_invoices"] = pending_invoices
        except:
            pass

        context.update(
            {
                "parent": parent,
                "children": children,
            }
        )

    elif hasattr(request.user, "student_profile"):
        # Student dashboard
        student = request.user.student_profile

        # Get student's assignments
        assignments = []
        try:
            Assignment = apps.get_model("courses", "Assignment")
            AssignmentSubmission = apps.get_model("courses", "AssignmentSubmission")

            if student.current_class:
                # Get pending assignments
                assignments = Assignment.objects.filter(
                    class_obj=student.current_class,
                    status="published",
                    due_date__gte=timezone.now().date(),
                ).order_by("due_date")[:5]

                # Annotate with submission status
                for assignment in assignments:
                    assignment.is_submitted = AssignmentSubmission.objects.filter(
                        assignment=assignment, student=student
                    ).exists()
        except:
            pass

        # Get upcoming exams
        exams = []
        try:
            ExamSchedule = apps.get_model("exams", "ExamSchedule")
            if student.current_class:
                exams = ExamSchedule.objects.filter(
                    class_obj=student.current_class, date__gte=timezone.now().date()
                ).order_by("date")[:5]
        except:
            pass

        context.update(
            {
                "student": student,
                "pending_assignments": assignments,
                "upcoming_exams": exams,
            }
        )

    return render(request, "core/dashboard.html", context)


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
