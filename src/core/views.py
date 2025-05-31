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

from src.finance.models import FinancialAnalytics

from .models import (
    SystemSetting,
    AuditLog,
    StudentPerformanceAnalytics,
    ClassPerformanceAnalytics,
    AttendanceAnalytics,
    # FinancialAnalytics,
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
from .forms import SystemSettingForm, UserSearchForm, ReportGenerationForm

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

    template_name = "dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get current academic year and term
        from src.academics.models import AcademicYear, Term

        current_year = AcademicYear.objects.filter(is_current=True).first()
        current_term = (
            Term.objects.filter(is_current=True).first() if current_year else None
        )

        # Basic statistics
        from src.students.models import Student
        from src.teachers.models import Teacher
        from src.academics.models import Class

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
        from src.assignments.models import AssignmentSubmission

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


class ClassAnalyticsView(SchoolAdminMixin, ListView):
    """Class analytics view"""

    model = ClassPerformanceAnalytics
    template_name = "core/class_analytics.html"
    context_object_name = "analytics"
    paginate_by = 20

    def get_queryset(self):
        queryset = ClassPerformanceAnalytics.objects.select_related(
            "class_instance__grade__section", "academic_year", "term", "subject"
        )

        # Filter by academic year and term
        academic_year_id = self.request.GET.get("academic_year")
        term_id = self.request.GET.get("term")

        if academic_year_id:
            queryset = queryset.filter(academic_year_id=academic_year_id)
        else:
            # Default to current academic year
            from academics.models import AcademicYear

            current_year = AcademicYear.objects.filter(is_current=True).first()
            if current_year:
                queryset = queryset.filter(academic_year=current_year)

        if term_id:
            queryset = queryset.filter(term_id=term_id)
        else:
            # Default to current term
            from academics.models import Term

            current_term = Term.objects.filter(is_current=True).first()
            if current_term:
                queryset = queryset.filter(term=current_term)

        # Filter by subject (or overall performance)
        subject_id = self.request.GET.get("subject")
        if subject_id == "overall":
            queryset = queryset.filter(subject__isnull=True)
        elif subject_id:
            queryset = queryset.filter(subject_id=subject_id)
        else:
            # Default to overall performance
            queryset = queryset.filter(subject__isnull=True)

        # Filter by section
        section_id = self.request.GET.get("section")
        if section_id:
            queryset = queryset.filter(class_instance__grade__section_id=section_id)

        # Filter by grade
        grade_id = self.request.GET.get("grade")
        if grade_id:
            queryset = queryset.filter(class_instance__grade_id=grade_id)

        return queryset.order_by("-class_average")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get filter options
        from academics.models import AcademicYear, Term, Section, Grade
        from subjects.models import Subject

        context["academic_years"] = AcademicYear.objects.all().order_by("-start_date")
        context["terms"] = Term.objects.all().order_by("term_number")
        context["sections"] = Section.objects.all().order_by("name")
        context["grades"] = Grade.objects.all().order_by("order_sequence")
        context["subjects"] = Subject.objects.all().order_by("name")

        # Current filter values
        context["current_filters"] = {
            "academic_year": self.request.GET.get("academic_year", ""),
            "term": self.request.GET.get("term", ""),
            "section": self.request.GET.get("section", ""),
            "grade": self.request.GET.get("grade", ""),
            "subject": self.request.GET.get("subject", "overall"),
        }

        # Summary statistics
        analytics = context["analytics"]
        if analytics:
            context["summary_stats"] = self.get_summary_statistics(analytics)

        return context

    def get_summary_statistics(self, analytics):
        """Calculate summary statistics for the filtered analytics"""
        if not analytics:
            return {}

        # Get all analytics for calculations (not just the paginated ones)
        all_analytics = self.get_queryset()

        return {
            "total_classes": all_analytics.count(),
            "avg_class_performance": all_analytics.aggregate(avg=Avg("class_average"))[
                "avg"
            ]
            or 0,
            "highest_performing_class": all_analytics.order_by(
                "-class_average"
            ).first(),
            "lowest_performing_class": all_analytics.order_by("class_average").first(),
            "avg_pass_rate": all_analytics.aggregate(avg=Avg("pass_rate"))["avg"] or 0,
            "total_students": all_analytics.aggregate(sum=Sum("total_students"))["sum"]
            or 0,
        }


class AttendanceAnalyticsView(SchoolAdminMixin, ListView):
    """Attendance analytics view"""

    model = AttendanceAnalytics
    template_name = "core/attendance_analytics.html"
    context_object_name = "analytics"
    paginate_by = 20

    def get_queryset(self):
        queryset = AttendanceAnalytics.objects.select_related("academic_year", "term")

        # Filter by academic year and term
        academic_year_id = self.request.GET.get("academic_year")
        term_id = self.request.GET.get("term")

        if academic_year_id:
            queryset = queryset.filter(academic_year_id=academic_year_id)

        if term_id:
            queryset = queryset.filter(term_id=term_id)

        # Filter by entity type
        entity_type = self.request.GET.get("entity_type", "student")
        queryset = queryset.filter(entity_type=entity_type)

        # Filter by attendance threshold (show low attendance)
        threshold = self.request.GET.get("threshold")
        if threshold:
            try:
                threshold_val = float(threshold)
                queryset = queryset.filter(attendance_percentage__lt=threshold_val)
            except ValueError:
                pass

        # Search by entity name
        search = self.request.GET.get("search")
        if search:
            queryset = queryset.filter(entity_name__icontains=search)

        return queryset.order_by("attendance_percentage")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get filter options
        from academics.models import AcademicYear, Term

        context["academic_years"] = AcademicYear.objects.all().order_by("-start_date")
        context["terms"] = Term.objects.all().order_by("term_number")
        context["entity_types"] = AttendanceAnalytics.ENTITY_TYPES

        # Current filter values
        context["current_filters"] = {
            "academic_year": self.request.GET.get("academic_year", ""),
            "term": self.request.GET.get("term", ""),
            "entity_type": self.request.GET.get("entity_type", "student"),
            "threshold": self.request.GET.get("threshold", ""),
            "search": self.request.GET.get("search", ""),
        }

        # Summary statistics
        analytics = context["analytics"]
        if analytics:
            context["summary_stats"] = self.get_summary_statistics()

        return context

    def get_summary_statistics(self):
        """Calculate summary statistics for attendance"""
        all_analytics = self.get_queryset()

        if not all_analytics.exists():
            return {}

        return {
            "total_entities": all_analytics.count(),
            "avg_attendance": all_analytics.aggregate(avg=Avg("attendance_percentage"))[
                "avg"
            ]
            or 0,
            "below_75_percent": all_analytics.filter(
                attendance_percentage__lt=75
            ).count(),
            "below_80_percent": all_analytics.filter(
                attendance_percentage__lt=80
            ).count(),
            "above_90_percent": all_analytics.filter(
                attendance_percentage__gte=90
            ).count(),
            "chronic_absentees": all_analytics.filter(
                consecutive_absences__gte=5
            ).count(),
        }


class FinancialAnalyticsView(SchoolAdminMixin, ListView):
    """Financial analytics view"""

    model = FinancialAnalytics
    template_name = "core/financial_analytics.html"
    context_object_name = "analytics"
    paginate_by = 20

    def get_queryset(self):
        queryset = FinancialAnalytics.objects.select_related(
            "academic_year", "term", "section", "grade", "fee_category"
        )

        # Filter by academic year and term
        academic_year_id = self.request.GET.get("academic_year")
        term_id = self.request.GET.get("term")

        if academic_year_id:
            queryset = queryset.filter(academic_year_id=academic_year_id)

        if term_id:
            queryset = queryset.filter(term_id=term_id)

        # Filter by section
        section_id = self.request.GET.get("section")
        if section_id:
            queryset = queryset.filter(section_id=section_id)

        # Filter by grade
        grade_id = self.request.GET.get("grade")
        if grade_id:
            queryset = queryset.filter(grade_id=grade_id)

        # Filter by fee category
        fee_category_id = self.request.GET.get("fee_category")
        if fee_category_id:
            queryset = queryset.filter(fee_category_id=fee_category_id)

        # Filter by collection rate
        collection_filter = self.request.GET.get("collection_filter")
        if collection_filter == "low":
            queryset = queryset.filter(collection_rate__lt=70)
        elif collection_filter == "high":
            queryset = queryset.filter(collection_rate__gte=90)

        return queryset.order_by("-total_expected_revenue")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get filter options
        from academics.models import AcademicYear, Term, Section, Grade
        from finance.models import FeeCategory

        context["academic_years"] = AcademicYear.objects.all().order_by("-start_date")
        context["terms"] = Term.objects.all().order_by("term_number")
        context["sections"] = Section.objects.all().order_by("name")
        context["grades"] = Grade.objects.all().order_by("order_sequence")
        context["fee_categories"] = FeeCategory.objects.all().order_by("name")

        # Current filter values
        context["current_filters"] = {
            "academic_year": self.request.GET.get("academic_year", ""),
            "term": self.request.GET.get("term", ""),
            "section": self.request.GET.get("section", ""),
            "grade": self.request.GET.get("grade", ""),
            "fee_category": self.request.GET.get("fee_category", ""),
            "collection_filter": self.request.GET.get("collection_filter", ""),
        }

        # Summary statistics
        context["summary_stats"] = self.get_summary_statistics()

        return context

    def get_summary_statistics(self):
        """Calculate summary financial statistics"""
        all_analytics = self.get_queryset()

        if not all_analytics.exists():
            return {}

        totals = all_analytics.aggregate(
            total_expected=Sum("total_expected_revenue"),
            total_collected=Sum("total_collected_revenue"),
            total_outstanding=Sum("total_outstanding"),
            avg_collection_rate=Avg("collection_rate"),
            total_students=Sum("total_students"),
        )

        return {
            "total_expected_revenue": totals["total_expected"] or 0,
            "total_collected_revenue": totals["total_collected"] or 0,
            "total_outstanding": totals["total_outstanding"] or 0,
            "overall_collection_rate": totals["avg_collection_rate"] or 0,
            "total_students": totals["total_students"] or 0,
            "collection_efficiency": (
                (totals["total_collected"] / totals["total_expected"] * 100)
                if totals["total_expected"] and totals["total_expected"] > 0
                else 0
            ),
            "high_performers": all_analytics.filter(collection_rate__gte=90).count(),
            "low_performers": all_analytics.filter(collection_rate__lt=70).count(),
        }


class TeacherAnalyticsView(SchoolAdminMixin, ListView):
    """Teacher analytics view"""

    model = TeacherPerformanceAnalytics
    template_name = "core/teacher_analytics.html"
    context_object_name = "analytics"
    paginate_by = 20

    def get_queryset(self):
        queryset = TeacherPerformanceAnalytics.objects.select_related(
            "teacher__user", "academic_year", "term"
        )

        # Filter by academic year and term
        academic_year_id = self.request.GET.get("academic_year")
        term_id = self.request.GET.get("term")

        if academic_year_id:
            queryset = queryset.filter(academic_year_id=academic_year_id)

        if term_id:
            queryset = queryset.filter(term_id=term_id)

        # Search by teacher name
        search = self.request.GET.get("search")
        if search:
            queryset = queryset.filter(
                Q(teacher__user__first_name__icontains=search)
                | Q(teacher__user__last_name__icontains=search)
                | Q(teacher__employee_id__icontains=search)
            )

        # Filter by performance level
        performance_filter = self.request.GET.get("performance_filter")
        if performance_filter == "high":
            queryset = queryset.filter(overall_performance_score__gte=4.0)
        elif performance_filter == "low":
            queryset = queryset.filter(overall_performance_score__lt=3.0)

        # Sort by performance score by default
        return queryset.order_by("-overall_performance_score")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get filter options
        from academics.models import AcademicYear, Term

        context["academic_years"] = AcademicYear.objects.all().order_by("-start_date")
        context["terms"] = Term.objects.all().order_by("term_number")

        # Current filter values
        context["current_filters"] = {
            "academic_year": self.request.GET.get("academic_year", ""),
            "term": self.request.GET.get("term", ""),
            "search": self.request.GET.get("search", ""),
            "performance_filter": self.request.GET.get("performance_filter", ""),
        }

        # Summary statistics
        context["summary_stats"] = self.get_summary_statistics()

        return context

    def get_summary_statistics(self):
        """Calculate teacher performance statistics"""
        all_analytics = self.get_queryset()

        if not all_analytics.exists():
            return {}

        stats = all_analytics.aggregate(
            total_teachers=Count("teacher", distinct=True),
            avg_performance=Avg("overall_performance_score"),
            avg_class_performance=Avg("average_class_performance"),
            avg_attendance_rate=Avg("attendance_rate"),
            total_classes_taught=Sum("classes_taught"),
            total_students_taught=Sum("total_students"),
        )

        return {
            "total_teachers": stats["total_teachers"] or 0,
            "avg_performance_score": stats["avg_performance"] or 0,
            "avg_class_performance": stats["avg_class_performance"] or 0,
            "avg_attendance_rate": stats["avg_attendance_rate"] or 0,
            "total_classes_taught": stats["total_classes_taught"] or 0,
            "total_students_taught": stats["total_students_taught"] or 0,
            "high_performers": all_analytics.filter(
                overall_performance_score__gte=4.0
            ).count(),
            "low_performers": all_analytics.filter(
                overall_performance_score__lt=3.0
            ).count(),
            "top_performer": all_analytics.order_by(
                "-overall_performance_score"
            ).first(),
        }


class ReportsView(SchoolAdminMixin, TemplateView):
    """Reports dashboard and management"""

    template_name = "core/reports.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Available report types
        context["report_types"] = [
            {
                "id": "student_performance",
                "name": "Student Performance Report",
                "description": "Comprehensive student academic performance analysis",
                "icon": "fas fa-user-graduate",
                "category": "Academic",
            },
            {
                "id": "class_performance",
                "name": "Class Performance Report",
                "description": "Class-wise performance comparison and analysis",
                "icon": "fas fa-door-open",
                "category": "Academic",
            },
            {
                "id": "attendance_summary",
                "name": "Attendance Summary Report",
                "description": "Attendance patterns and statistics",
                "icon": "fas fa-user-check",
                "category": "Academic",
            },
            {
                "id": "financial_summary",
                "name": "Financial Summary Report",
                "description": "Fee collection and financial overview",
                "icon": "fas fa-money-bill-wave",
                "category": "Financial",
            },
            {
                "id": "teacher_performance",
                "name": "Teacher Performance Report",
                "description": "Teacher effectiveness and performance metrics",
                "icon": "fas fa-chalkboard-teacher",
                "category": "Administrative",
            },
            {
                "id": "enrollment_report",
                "name": "Enrollment Report",
                "description": "Student enrollment statistics and trends",
                "icon": "fas fa-chart-line",
                "category": "Administrative",
            },
            {
                "id": "fee_defaulters",
                "name": "Fee Defaulters Report",
                "description": "List of students with outstanding fees",
                "icon": "fas fa-exclamation-triangle",
                "category": "Financial",
            },
            {
                "id": "system_usage",
                "name": "System Usage Report",
                "description": "System usage statistics and user activity",
                "icon": "fas fa-chart-bar",
                "category": "System",
            },
        ]

        # Group reports by category
        context["reports_by_category"] = {}
        for report in context["report_types"]:
            category = report["category"]
            if category not in context["reports_by_category"]:
                context["reports_by_category"][category] = []
            context["reports_by_category"][category].append(report)

        # Recent reports (this would be from a ReportGeneration model if you have one)
        context["recent_reports"] = []  # Placeholder for recent report history

        # Quick stats
        context["stats"] = {
            "total_reports_available": len(context["report_types"]),
            "reports_generated_today": 0,  # Would query actual data
            "reports_generated_this_month": 0,  # Would query actual data
        }

        return context


class GenerateReportView(SchoolAdminMixin, TemplateView):
    """Generate specific reports"""

    template_name = "core/generate_report.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get report type from URL or query params
        report_type = self.request.GET.get("type", "student_performance")
        context["report_type"] = report_type

        # Get report configuration
        context["report_config"] = self.get_report_config(report_type)

        # Get filter options
        from academics.models import AcademicYear, Term, Section, Grade

        context["academic_years"] = AcademicYear.objects.all().order_by("-start_date")
        context["terms"] = Term.objects.all().order_by("term_number")
        context["sections"] = Section.objects.all().order_by("name")
        context["grades"] = Grade.objects.all().order_by("order_sequence")

        return context

    def get_report_config(self, report_type):
        """Get configuration for specific report type"""
        configs = {
            "student_performance": {
                "name": "Student Performance Report",
                "description": "Generate comprehensive student performance analysis",
                "filters": ["academic_year", "term", "section", "grade", "date_range"],
                "formats": ["pdf", "excel", "csv"],
                "template": "reports/student_performance.html",
            },
            "class_performance": {
                "name": "Class Performance Report",
                "description": "Generate class-wise performance comparison",
                "filters": ["academic_year", "term", "section", "grade"],
                "formats": ["pdf", "excel"],
                "template": "reports/class_performance.html",
            },
            "attendance_summary": {
                "name": "Attendance Summary Report",
                "description": "Generate attendance patterns and statistics",
                "filters": ["academic_year", "term", "section", "grade", "date_range"],
                "formats": ["pdf", "excel", "csv"],
                "template": "reports/attendance_summary.html",
            },
            "financial_summary": {
                "name": "Financial Summary Report",
                "description": "Generate fee collection and financial overview",
                "filters": [
                    "academic_year",
                    "term",
                    "section",
                    "grade",
                    "fee_category",
                ],
                "formats": ["pdf", "excel"],
                "template": "reports/financial_summary.html",
            },
            "teacher_performance": {
                "name": "Teacher Performance Report",
                "description": "Generate teacher effectiveness metrics",
                "filters": ["academic_year", "term", "department"],
                "formats": ["pdf", "excel"],
                "template": "reports/teacher_performance.html",
            },
        }

        return configs.get(report_type, configs["student_performance"])

    def post(self, request, *args, **kwargs):
        """Handle report generation request"""
        report_type = request.POST.get("report_type")
        format_type = request.POST.get("format", "pdf")

        # Get filters from POST data
        filters = {
            "academic_year_id": request.POST.get("academic_year"),
            "term_id": request.POST.get("term"),
            "section_id": request.POST.get("section"),
            "grade_id": request.POST.get("grade"),
            "start_date": request.POST.get("start_date"),
            "end_date": request.POST.get("end_date"),
            "fee_category_id": request.POST.get("fee_category"),
        }

        # Remove empty filters
        filters = {k: v for k, v in filters.items() if v}

        try:
            # Queue report generation task
            from .tasks import generate_reports

            task = generate_reports.delay(
                report_type=report_type,
                parameters={
                    "format": format_type,
                    "filters": filters,
                    "generated_by": request.user.id,
                },
            )

            messages.success(
                request,
                f"Report generation has been queued. You will be notified when it's ready. Task ID: {task.id}",
            )

            # Log the report generation request
            AuditService.log_action(
                user=request.user,
                action="create",
                description=f"Requested {report_type} report generation",
                data_after={
                    "report_type": report_type,
                    "format": format_type,
                    "filters": filters,
                    "task_id": task.id,
                },
                ip_address=request.META.get("REMOTE_ADDR"),
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
                module_name="core",
            )

            return JsonResponse(
                {
                    "status": "success",
                    "message": "Report generation queued successfully",
                    "task_id": task.id,
                }
            )

        except Exception as e:
            messages.error(request, f"Error generating report: {str(e)}")
            return JsonResponse({"status": "error", "message": str(e)}, status=500)
