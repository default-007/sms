# views.py
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse
from django.views.generic import (
    TemplateView,
    ListView,
    DetailView,
    UpdateView,
    CreateView,
)
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.core.paginator import Paginator
from django.db.models import Q, Count, Avg, Sum
from django.utils import timezone
from django.contrib.auth import get_user_model
from datetime import datetime, timedelta
import json

from .models import (
    SystemSetting,
    AuditLog,
    StudentPerformanceAnalytics,
    ClassPerformanceAnalytics,
    AttendanceAnalytics,
    FinancialAnalytics,
    TeacherPerformanceAnalytics,
    SystemHealthMetrics,
)
from .services import (
    ConfigurationService,
    AuditService,
    AnalyticsService,
    SecurityService,
    UtilityService,
)
from .decorators import system_admin_required, school_admin_required, audit_action
from .forms import SystemSettingForm, UserSearchForm

User = get_user_model()


class SystemAdminMixin(UserPassesTestMixin):
    """Mixin to require system admin access"""

    def test_func(self):
        return self.request.user.is_authenticated and (
            self.request.user.is_superuser
            or self.request.user.groups.filter(name="System Administrators").exists()
        )


class SchoolAdminMixin(UserPassesTestMixin):
    """Mixin to require school admin access or higher"""

    def test_func(self):
        return self.request.user.is_authenticated and (
            self.request.user.is_superuser
            or self.request.user.groups.filter(
                name__in=["System Administrators", "School Administrators"]
            ).exists()
        )


class DashboardView(LoginRequiredMixin, TemplateView):
    """Main dashboard view"""

    template_name = "core/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get current academic year and term
        from academics.models import AcademicYear, Term

        current_year = AcademicYear.objects.filter(is_current=True).first()
        current_term = (
            Term.objects.filter(is_current=True).first() if current_year else None
        )

        # Basic statistics
        from students.models import Student
        from teachers.models import Teacher
        from academics.models import Class

        context.update(
            {
                "current_academic_year": current_year,
                "current_term": current_term,
                "total_students": Student.objects.filter(status="active").count(),
                "total_teachers": Teacher.objects.filter(status="active").count(),
                "total_classes": (
                    Class.objects.filter(academic_year=current_year).count()
                    if current_year
                    else 0
                ),
                "user_role": self.get_user_role(),
            }
        )

        # Role-specific dashboard data
        if (
            self.request.user.is_superuser
            or self.request.user.groups.filter(
                name__in=["System Administrators", "School Administrators"]
            ).exists()
        ):
            context.update(self.get_admin_dashboard_data(current_year, current_term))
        elif hasattr(self.request.user, "teacher"):
            context.update(self.get_teacher_dashboard_data())
        elif hasattr(self.request.user, "parent"):
            context.update(self.get_parent_dashboard_data())
        elif hasattr(self.request.user, "student"):
            context.update(self.get_student_dashboard_data())

        return context

    def get_user_role(self):
        """Determine user's primary role"""
        user = self.request.user

        if user.is_superuser:
            return "superuser"
        elif user.groups.filter(name="System Administrators").exists():
            return "system_admin"
        elif user.groups.filter(name="School Administrators").exists():
            return "school_admin"
        elif hasattr(user, "teacher"):
            return "teacher"
        elif hasattr(user, "parent"):
            return "parent"
        elif hasattr(user, "student"):
            return "student"
        else:
            return "user"

    def get_admin_dashboard_data(self, current_year, current_term):
        """Get dashboard data for administrators"""
        data = {}

        if current_year and current_term:
            # Financial summary
            financial_analytics = FinancialAnalytics.objects.filter(
                academic_year=current_year, term=current_term
            ).aggregate(
                total_expected=Sum("total_expected_revenue"),
                total_collected=Sum("total_collected_revenue"),
                avg_collection_rate=Avg("collection_rate"),
            )

            data["financial_summary"] = financial_analytics

            # Performance summary
            student_analytics = StudentPerformanceAnalytics.objects.filter(
                academic_year=current_year, term=current_term, subject__isnull=True
            ).aggregate(
                avg_performance=Avg("average_marks"),
                avg_attendance=Avg("attendance_percentage"),
            )

            data["performance_summary"] = student_analytics

        # System health
        latest_health = SystemHealthMetrics.objects.first()
        data["system_health"] = latest_health

        # Recent activity
        recent_logs = AuditLog.objects.select_related("user").order_by("-timestamp")[
            :10
        ]
        data["recent_activity"] = recent_logs

        return data

    def get_teacher_dashboard_data(self):
        """Get dashboard data for teachers"""
        teacher = self.request.user.teacher

        # Get classes taught
        from teachers.models import TeacherClassAssignment

        assignments = TeacherClassAssignment.objects.filter(
            teacher=teacher, academic_year__is_current=True
        ).select_related("class_instance", "subject")

        return {
            "teacher_assignments": assignments,
            "classes_count": assignments.values("class_instance").distinct().count(),
            "subjects_count": assignments.values("subject").distinct().count(),
        }

    def get_parent_dashboard_data(self):
        """Get dashboard data for parents"""
        parent = self.request.user.parent

        # Get children
        from students.models import StudentParentRelation

        children_relations = StudentParentRelation.objects.filter(
            parent=parent
        ).select_related("student__user", "student__current_class")

        children_data = []
        for relation in children_relations:
            student = relation.student

            # Get latest performance
            latest_performance = (
                StudentPerformanceAnalytics.objects.filter(
                    student=student, subject__isnull=True
                )
                .order_by("-calculated_at")
                .first()
            )

            children_data.append(
                {
                    "student": student,
                    "relation_type": relation.relation_type,
                    "performance": latest_performance,
                }
            )

        return {"children": children_data, "children_count": len(children_data)}

    def get_student_dashboard_data(self):
        """Get dashboard data for students"""
        student = self.request.user.student

        # Get latest performance
        latest_performance = (
            StudentPerformanceAnalytics.objects.filter(
                student=student, subject__isnull=True
            )
            .order_by("-calculated_at")
            .first()
        )

        # Get recent assignments
        from assignments.models import AssignmentSubmission

        recent_assignments = (
            AssignmentSubmission.objects.filter(student=student)
            .select_related("assignment")
            .order_by("-submission_date")[:5]
        )

        return {
            "student": student,
            "performance": latest_performance,
            "recent_assignments": recent_assignments,
        }


class SystemAdminView(SystemAdminMixin, TemplateView):
    """System administration overview"""

    template_name = "core/system_admin.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # System statistics
        context.update(
            {
                "total_users": User.objects.count(),
                "active_users": User.objects.filter(is_active=True).count(),
                "total_settings": SystemSetting.objects.count(),
                "audit_logs_count": AuditLog.objects.count(),
            }
        )

        # Recent system activity
        recent_logs = (
            AuditLog.objects.filter(
                action__in=["create", "update", "delete", "system_action"]
            )
            .select_related("user")
            .order_by("-timestamp")[:20]
        )

        context["recent_system_activity"] = recent_logs

        # System health metrics
        latest_health = SystemHealthMetrics.objects.first()
        context["system_health"] = latest_health

        return context


class SystemSettingsView(SystemAdminMixin, ListView):
    """System settings management"""

    model = SystemSetting
    template_name = "core/system_settings.html"
    context_object_name = "settings"
    paginate_by = 20

    def get_queryset(self):
        queryset = SystemSetting.objects.all()

        # Filter by category
        category = self.request.GET.get("category")
        if category:
            queryset = queryset.filter(category=category)

        # Search
        search = self.request.GET.get("search")
        if search:
            queryset = queryset.filter(
                Q(setting_key__icontains=search) | Q(description__icontains=search)
            )

        return queryset.order_by("category", "setting_key")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get categories for filter
        categories = (
            SystemSetting.objects.values_list("category", flat=True)
            .distinct()
            .order_by("category")
        )

        context["categories"] = categories
        context["current_category"] = self.request.GET.get("category", "")
        context["search_query"] = self.request.GET.get("search", "")

        return context


class SystemSettingEditView(SystemAdminMixin, UpdateView):
    """Edit system setting"""

    model = SystemSetting
    form_class = SystemSettingForm
    template_name = "core/system_setting_edit.html"

    def form_valid(self, form):
        # Track changes for audit
        old_value = self.object.get_typed_value()

        response = super().form_valid(form)

        # Log the change
        AuditService.log_action(
            user=self.request.user,
            action="update",
            content_object=self.object,
            description=f"Updated system setting: {self.object.setting_key}",
            data_before={"value": old_value},
            data_after={"value": self.object.get_typed_value()},
            ip_address=self.request.META.get("REMOTE_ADDR"),
            user_agent=self.request.META.get("HTTP_USER_AGENT", ""),
            module_name="core",
        )

        messages.success(
            self.request, f"Setting '{self.object.setting_key}' updated successfully."
        )

        return response

    def get_success_url(self):
        return reverse("core:settings")


class AuditLogsView(SystemAdminMixin, ListView):
    """Audit logs view"""

    model = AuditLog
    template_name = "core/audit_logs.html"
    context_object_name = "logs"
    paginate_by = 50

    def get_queryset(self):
        queryset = AuditLog.objects.select_related("user", "content_type")

        # Filter by user
        user_id = self.request.GET.get("user")
        if user_id:
            queryset = queryset.filter(user_id=user_id)

        # Filter by action
        action = self.request.GET.get("action")
        if action:
            queryset = queryset.filter(action=action)

        # Filter by module
        module = self.request.GET.get("module")
        if module:
            queryset = queryset.filter(module_name=module)

        # Filter by date range
        start_date = self.request.GET.get("start_date")
        end_date = self.request.GET.get("end_date")

        if start_date:
            try:
                start_dt = datetime.strptime(start_date, "%Y-%m-%d")
                queryset = queryset.filter(timestamp__gte=start_dt)
            except ValueError:
                pass

        if end_date:
            try:
                end_dt = datetime.strptime(end_date, "%Y-%m-%d")
                end_dt = end_dt.replace(hour=23, minute=59, second=59)
                queryset = queryset.filter(timestamp__lte=end_dt)
            except ValueError:
                pass

        return queryset.order_by("-timestamp")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get filter options
        context["actions"] = (
            AuditLog.objects.values_list("action", flat=True)
            .distinct()
            .order_by("action")
        )

        context["modules"] = (
            AuditLog.objects.values_list("module_name", flat=True)
            .distinct()
            .order_by("module_name")
        )

        # Current filters
        context["current_filters"] = {
            "user": self.request.GET.get("user", ""),
            "action": self.request.GET.get("action", ""),
            "module": self.request.GET.get("module", ""),
            "start_date": self.request.GET.get("start_date", ""),
            "end_date": self.request.GET.get("end_date", ""),
        }

        return context


class SystemHealthView(SystemAdminMixin, TemplateView):
    """System health monitoring"""

    template_name = "core/system_health.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Latest health metrics
        latest_health = SystemHealthMetrics.objects.first()
        context["latest_health"] = latest_health

        # Health metrics over time (last 24 hours)
        twenty_four_hours_ago = timezone.now() - timedelta(hours=24)
        health_history = SystemHealthMetrics.objects.filter(
            timestamp__gte=twenty_four_hours_ago
        ).order_by("timestamp")

        context["health_history"] = health_history

        # System status indicators
        if latest_health:
            context["system_status"] = {
                "overall": self.get_overall_status(latest_health),
                "database": self.get_database_status(latest_health),
                "cache": self.get_cache_status(latest_health),
                "storage": self.get_storage_status(latest_health),
                "performance": self.get_performance_status(latest_health),
            }

        return context

    def get_overall_status(self, health):
        """Determine overall system status"""
        if (
            health.avg_response_time_ms < 500
            and health.error_rate < 1
            and health.cache_hit_rate > 80
        ):
            return "healthy"
        elif health.error_rate > 5 or health.avg_response_time_ms > 2000:
            return "critical"
        else:
            return "warning"

    def get_database_status(self, health):
        """Determine database status"""
        if health.avg_query_time_ms < 100:
            return "healthy"
        elif health.avg_query_time_ms < 500:
            return "warning"
        else:
            return "critical"

    def get_cache_status(self, health):
        """Determine cache status"""
        if health.cache_hit_rate > 80:
            return "healthy"
        elif health.cache_hit_rate > 60:
            return "warning"
        else:
            return "critical"

    def get_storage_status(self, health):
        """Determine storage status"""
        total_storage = health.storage_used_gb + health.storage_available_gb
        if total_storage > 0:
            usage_percentage = (health.storage_used_gb / total_storage) * 100
            if usage_percentage < 70:
                return "healthy"
            elif usage_percentage < 85:
                return "warning"
            else:
                return "critical"
        return "unknown"

    def get_performance_status(self, health):
        """Determine performance status"""
        if health.avg_response_time_ms < 300:
            return "healthy"
        elif health.avg_response_time_ms < 1000:
            return "warning"
        else:
            return "critical"


class AnalyticsView(SchoolAdminMixin, TemplateView):
    """Analytics overview"""

    template_name = "core/analytics.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get current academic year and term
        from academics.models import AcademicYear, Term

        current_year = AcademicYear.objects.filter(is_current=True).first()
        current_term = Term.objects.filter(is_current=True).first()

        context["current_academic_year"] = current_year
        context["current_term"] = current_term

        if current_year and current_term:
            # Analytics summary
            context["analytics_summary"] = self.get_analytics_summary(
                current_year, current_term
            )

        return context

    def get_analytics_summary(self, academic_year, term):
        """Get analytics summary data"""
        summary = {}

        # Student performance
        student_analytics = StudentPerformanceAnalytics.objects.filter(
            academic_year=academic_year, term=term, subject__isnull=True
        )

        summary["student_performance"] = {
            "total_students": student_analytics.count(),
            "avg_marks": student_analytics.aggregate(avg=Avg("average_marks"))["avg"]
            or 0,
            "avg_attendance": student_analytics.aggregate(
                avg=Avg("attendance_percentage")
            )["avg"]
            or 0,
        }

        # Class performance
        class_analytics = ClassPerformanceAnalytics.objects.filter(
            academic_year=academic_year, term=term, subject__isnull=True
        )

        summary["class_performance"] = {
            "total_classes": class_analytics.count(),
            "avg_class_performance": class_analytics.aggregate(
                avg=Avg("class_average")
            )["avg"]
            or 0,
            "avg_pass_rate": class_analytics.aggregate(avg=Avg("pass_rate"))["avg"]
            or 0,
        }

        # Financial analytics
        financial_analytics = FinancialAnalytics.objects.filter(
            academic_year=academic_year, term=term
        )

        summary["financial"] = {
            "total_expected": financial_analytics.aggregate(
                sum=Sum("total_expected_revenue")
            )["sum"]
            or 0,
            "total_collected": financial_analytics.aggregate(
                sum=Sum("total_collected_revenue")
            )["sum"]
            or 0,
            "avg_collection_rate": financial_analytics.aggregate(
                avg=Avg("collection_rate")
            )["avg"]
            or 0,
        }

        return summary


class StudentAnalyticsView(SchoolAdminMixin, ListView):
    """Student analytics view"""

    model = StudentPerformanceAnalytics
    template_name = "core/student_analytics.html"
    context_object_name = "analytics"
    paginate_by = 20

    def get_queryset(self):
        queryset = StudentPerformanceAnalytics.objects.select_related(
            "student__user",
            "student__current_class",
            "academic_year",
            "term",
            "subject",
        )

        # Filter by academic year and term
        academic_year_id = self.request.GET.get("academic_year")
        term_id = self.request.GET.get("term")

        if academic_year_id:
            queryset = queryset.filter(academic_year_id=academic_year_id)

        if term_id:
            queryset = queryset.filter(term_id=term_id)

        # Filter by subject (or overall performance)
        subject_id = self.request.GET.get("subject")
        if subject_id == "overall":
            queryset = queryset.filter(subject__isnull=True)
        elif subject_id:
            queryset = queryset.filter(subject_id=subject_id)

        return queryset.order_by("-average_marks")


class UserManagementView(SystemAdminMixin, ListView):
    """User management view"""

    model = User
    template_name = "core/user_management.html"
    context_object_name = "users"
    paginate_by = 20

    def get_queryset(self):
        queryset = User.objects.select_related().prefetch_related("groups")

        # Search functionality
        search = self.request.GET.get("search")
        if search:
            queryset = queryset.filter(
                Q(username__icontains=search)
                | Q(first_name__icontains=search)
                | Q(last_name__icontains=search)
                | Q(email__icontains=search)
            )

        # Filter by role
        role = self.request.GET.get("role")
        if role == "teacher":
            queryset = queryset.filter(teacher__isnull=False)
        elif role == "parent":
            queryset = queryset.filter(parent__isnull=False)
        elif role == "student":
            queryset = queryset.filter(student__isnull=False)
        elif role == "admin":
            queryset = queryset.filter(
                Q(is_superuser=True)
                | Q(groups__name__in=["System Administrators", "School Administrators"])
            )

        # Filter by status
        status = self.request.GET.get("status")
        if status == "active":
            queryset = queryset.filter(is_active=True)
        elif status == "inactive":
            queryset = queryset.filter(is_active=False)

        return queryset.distinct().order_by("-date_joined")


class UserDetailView(SystemAdminMixin, DetailView):
    """User detail view"""

    model = User
    template_name = "core/user_detail.html"
    context_object_name = "user_obj"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        user = self.object

        # User's roles
        context["user_roles"] = self.get_user_roles(user)

        # Recent activity
        recent_activity = AuditLog.objects.filter(user=user).order_by("-timestamp")[:20]
        context["recent_activity"] = recent_activity

        # Related objects
        if hasattr(user, "student"):
            context["student"] = user.student
        if hasattr(user, "teacher"):
            context["teacher"] = user.teacher
        if hasattr(user, "parent"):
            context["parent"] = user.parent

        return context

    def get_user_roles(self, user):
        """Get user's roles"""
        roles = []

        if user.is_superuser:
            roles.append("Superuser")

        for group in user.groups.all():
            roles.append(group.name)

        if hasattr(user, "teacher"):
            roles.append("Teacher")
        if hasattr(user, "parent"):
            roles.append("Parent")
        if hasattr(user, "student"):
            roles.append("Student")

        return roles


class UserActivityView(SystemAdminMixin, TemplateView):
    """User activity view"""

    template_name = "core/user_activity.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        user = get_object_or_404(User, pk=kwargs["pk"])
        context["user_obj"] = user

        # Get activity logs
        days = int(self.request.GET.get("days", 30))
        logs = AuditService.get_user_activity(user, days)

        # Paginate logs
        paginator = Paginator(logs, 50)
        page_number = self.request.GET.get("page")
        page_obj = paginator.get_page(page_number)

        context["logs"] = page_obj
        context["days"] = days

        # Activity summary
        context["activity_summary"] = {
            "total_actions": logs.count(),
            "most_common_action": logs.values("action")
            .annotate(count=Count("id"))
            .order_by("-count")
            .first(),
            "modules_accessed": logs.values_list("module_name", flat=True)
            .distinct()
            .count(),
        }

        return context
