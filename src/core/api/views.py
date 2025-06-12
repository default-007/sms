# core/api/views.py
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from django.contrib.auth import get_user_model
from django.db.models import Q, Count, Avg, Sum
from django.utils import timezone
from datetime import datetime, timedelta

from src.finance.models import FinancialAnalytics

from ..models import (
    SystemSetting,
    AuditLog,
    StudentPerformanceAnalytics,
    ClassPerformanceAnalytics,
    AttendanceAnalytics,
    TeacherPerformanceAnalytics,
    SystemHealthMetrics,
)
from ..services import (
    ConfigurationService,
    AuditService,
    AnalyticsService,
    SecurityService,
)
from ..permissions import IsSystemAdmin, IsSchoolAdmin
from .serializers import (
    SystemSettingSerializer,
    AuditLogSerializer,
    StudentPerformanceAnalyticsSerializer,
    ClassPerformanceAnalyticsSerializer,
    AttendanceAnalyticsSerializer,
    FinancialAnalyticsSerializer,
    TeacherPerformanceAnalyticsSerializer,
    SystemHealthMetricsSerializer,
)

User = get_user_model()


class SystemSettingViewSet(viewsets.ModelViewSet):
    """ViewSet for managing system settings"""

    queryset = SystemSetting.objects.all()
    serializer_class = SystemSettingSerializer
    permission_classes = [IsSystemAdmin]
    filterset_fields = ["category", "data_type", "is_editable"]
    search_fields = ["setting_key", "description"]
    ordering_fields = ["category", "setting_key", "updated_at"]
    ordering = ["category", "setting_key"]

    def perform_update(self, serializer):
        """Track setting updates"""
        old_value = self.get_object().get_typed_value()
        instance = serializer.save(updated_by=self.request.user)

        AuditService.log_action(
            user=self.request.user,
            action="update",
            content_object=instance,
            description=f"Updated system setting: {instance.setting_key}",
            data_before={"value": old_value},
            data_after={"value": instance.get_typed_value()},
            ip_address=self.request.META.get("REMOTE_ADDR"),
            user_agent=self.request.META.get("HTTP_USER_AGENT", ""),
            module_name="core",
        )

    @action(detail=True, methods=["patch"])
    def update_value(self, request, pk=None):
        """Update only the setting value"""
        setting = self.get_object()
        old_value = setting.get_typed_value()

        new_value = request.data.get("value")
        if new_value is None:
            return Response(
                {"error": "Value is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        setting.set_typed_value(new_value)
        setting.updated_by = request.user
        setting.save()

        # Clear cache
        from ..services import ConfigurationService

        cache_key = f"{ConfigurationService.CACHE_PREFIX}{setting.setting_key}"
        from django.core.cache import cache

        try:
            cache.delete(cache_key)
        except:
            pass

        # Log the change
        AuditService.log_action(
            user=request.user,
            action="update",
            content_object=setting,
            description=f"Updated setting value: {setting.setting_key}",
            data_before={"value": old_value},
            data_after={"value": setting.get_typed_value()},
            ip_address=request.META.get("REMOTE_ADDR"),
            module_name="core",
        )

        serializer = self.get_serializer(setting)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def by_category(self, request):
        """Get settings by category"""
        category = request.query_params.get("category")
        if not category:
            return Response(
                {"error": "Category parameter is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        settings = self.queryset.filter(category=category)
        serializer = self.get_serializer(settings, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["post"])
    def bulk_update(self, request):
        """Bulk update multiple settings"""
        updates = request.data.get("updates", [])
        if not updates:
            return Response(
                {"error": "Updates list is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        updated_settings = []
        errors = []

        for update in updates:
            setting_key = update.get("setting_key")
            value = update.get("value")

            if not setting_key or value is None:
                errors.append(f"Missing setting_key or value in update: {update}")
                continue

            try:
                setting = SystemSetting.objects.get(setting_key=setting_key)
                old_value = setting.get_typed_value()
                setting.set_typed_value(value)
                setting.updated_by = request.user
                setting.save()

                updated_settings.append(
                    {
                        "setting_key": setting_key,
                        "old_value": old_value,
                        "new_value": setting.get_typed_value(),
                    }
                )

            except SystemSetting.DoesNotExist:
                errors.append(f"Setting not found: {setting_key}")
            except Exception as e:
                errors.append(f"Error updating {setting_key}: {str(e)}")

        # Log bulk update
        AuditService.log_action(
            user=request.user,
            action="bulk_action",
            description=f"Bulk updated {len(updated_settings)} system settings",
            data_after={"updated_settings": updated_settings, "errors": errors},
            ip_address=request.META.get("REMOTE_ADDR"),
            module_name="core",
        )

        return Response(
            {
                "updated_count": len(updated_settings),
                "updated_settings": updated_settings,
                "errors": errors,
            }
        )


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for viewing audit logs"""

    queryset = AuditLog.objects.select_related("user", "content_type").all()
    serializer_class = AuditLogSerializer
    permission_classes = [IsSystemAdmin]
    filterset_fields = ["user", "action", "module_name", "content_type"]
    search_fields = [
        "description",
        "user__username",
        "user__first_name",
        "user__last_name",
    ]
    ordering_fields = ["timestamp", "action", "user"]
    ordering = ["-timestamp"]

    @action(detail=False, methods=["get"])
    def user_activity(self, request):
        """Get activity for a specific user"""
        user_id = request.query_params.get("user_id")
        if not user_id:
            return Response(
                {"error": "user_id parameter is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        days = int(request.query_params.get("days", 30))

        try:
            user = User.objects.get(id=user_id)
            logs = AuditService.get_user_activity(user, days)

            page = self.paginate_queryset(logs)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return self.get_paginated_response(serializer.data)

            serializer = self.get_serializer(logs, many=True)
            return Response(serializer.data)

        except User.DoesNotExist:
            return Response(
                {"error": "User not found"}, status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=False, methods=["get"])
    def content_types(self, request):
        """Get available content types for filtering"""
        content_types = (
            AuditLog.objects.values_list(
                "content_type__app_label", "content_type__model"
            )
            .distinct()
            .order_by("content_type__app_label", "content_type__model")
        )

        return Response(
            [
                {"app_label": app_label, "model": model}
                for app_label, model in content_types
                if app_label and model
            ]
        )


class StudentPerformanceAnalyticsViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for student performance analytics"""

    queryset = StudentPerformanceAnalytics.objects.select_related(
        "student__user", "academic_year", "term", "subject"
    ).all()
    serializer_class = StudentPerformanceAnalyticsSerializer
    permission_classes = [IsSchoolAdmin]
    filterset_fields = ["academic_year", "term", "subject", "student"]
    ordering_fields = ["average_marks", "attendance_percentage", "calculated_at"]
    ordering = ["-average_marks"]

    @action(detail=False, methods=["get"])
    def summary(self, request):
        """Get performance summary statistics"""
        queryset = self.filter_queryset(self.get_queryset())

        summary = queryset.aggregate(
            total_students=Count("student", distinct=True),
            avg_performance=Avg("average_marks"),
            avg_attendance=Avg("attendance_percentage"),
            top_performer=queryset.order_by("-average_marks").first(),
        )

        return Response(summary)


class ClassPerformanceAnalyticsViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for class performance analytics"""

    queryset = ClassPerformanceAnalytics.objects.select_related(
        "class_instance__grade__section", "academic_year", "term", "subject"
    ).all()
    serializer_class = ClassPerformanceAnalyticsSerializer
    permission_classes = [IsSchoolAdmin]
    filterset_fields = ["academic_year", "term", "subject", "class_instance"]
    ordering_fields = ["class_average", "pass_rate", "calculated_at"]
    ordering = ["-class_average"]


class AttendanceAnalyticsViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for attendance analytics"""

    queryset = AttendanceAnalytics.objects.select_related("academic_year", "term").all()
    serializer_class = AttendanceAnalyticsSerializer
    permission_classes = [IsSchoolAdmin]
    filterset_fields = ["academic_year", "term", "entity_type"]
    search_fields = ["entity_name"]
    ordering_fields = ["attendance_percentage", "calculated_at"]
    ordering = ["attendance_percentage"]

    @action(detail=False, methods=["get"])
    def low_attendance(self, request):
        """Get entities with low attendance"""
        threshold = float(request.query_params.get("threshold", 75))

        queryset = self.filter_queryset(self.get_queryset())
        low_attendance = queryset.filter(attendance_percentage__lt=threshold)

        page = self.paginate_queryset(low_attendance)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(low_attendance, many=True)
        return Response(serializer.data)


class FinancialAnalyticsViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for financial analytics"""

    queryset = FinancialAnalytics.objects.select_related(
        "academic_year", "term", "section", "grade", "fee_category"
    ).all()
    serializer_class = FinancialAnalyticsSerializer
    permission_classes = [IsSchoolAdmin]
    filterset_fields = ["academic_year", "term", "section", "grade", "fee_category"]
    ordering_fields = ["total_expected_revenue", "collection_rate", "calculated_at"]
    ordering = ["-total_expected_revenue"]

    @action(detail=False, methods=["get"])
    def summary(self, request):
        """Get financial summary statistics"""
        queryset = self.filter_queryset(self.get_queryset())

        summary = queryset.aggregate(
            total_expected=Sum("total_expected_revenue"),
            total_collected=Sum("total_collected_revenue"),
            total_outstanding=Sum("total_outstanding"),
            avg_collection_rate=Avg("collection_rate"),
        )

        return Response(summary)


class TeacherPerformanceAnalyticsViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for teacher performance analytics"""

    queryset = TeacherPerformanceAnalytics.objects.select_related(
        "teacher__user", "academic_year", "term"
    ).all()
    serializer_class = TeacherPerformanceAnalyticsSerializer
    permission_classes = [IsSchoolAdmin]
    filterset_fields = ["academic_year", "term", "teacher"]
    ordering_fields = ["overall_performance_score", "calculated_at"]
    ordering = ["-overall_performance_score"]


class SystemHealthMetricsViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for system health metrics"""

    queryset = SystemHealthMetrics.objects.all()
    serializer_class = SystemHealthMetricsSerializer
    permission_classes = [IsSystemAdmin]
    ordering = ["-timestamp"]

    @action(detail=False, methods=["get"])
    def latest(self, request):
        """Get latest system health metrics"""
        latest = self.get_queryset().first()
        if latest:
            serializer = self.get_serializer(latest)
            return Response(serializer.data)
        return Response({})

    @action(detail=False, methods=["get"])
    def history(self, request):
        """Get health metrics history"""
        hours = int(request.query_params.get("hours", 24))
        since = timezone.now() - timedelta(hours=hours)

        metrics = self.get_queryset().filter(timestamp__gte=since)
        serializer = self.get_serializer(metrics, many=True)
        return Response(serializer.data)


class AnalyticsAPIView(APIView):
    """API for analytics operations"""

    permission_classes = [IsSchoolAdmin]

    def post(self, request):
        """Trigger analytics calculation"""
        analytics_type = request.data.get("type", "all")
        force_recalculate = request.data.get("force", False)
        academic_year_id = request.data.get("academic_year_id")
        term_id = request.data.get("term_id")

        try:
            if analytics_type == "student" or analytics_type == "all":
                AnalyticsService.calculate_student_performance(
                    academic_year_id=academic_year_id,
                    term_id=term_id,
                    force_recalculate=force_recalculate,
                )

            if analytics_type == "class" or analytics_type == "all":
                AnalyticsService.calculate_class_performance(
                    academic_year_id=academic_year_id,
                    term_id=term_id,
                    force_recalculate=force_recalculate,
                )

            if analytics_type == "attendance" or analytics_type == "all":
                AnalyticsService.calculate_attendance_analytics(
                    academic_year_id=academic_year_id,
                    term_id=term_id,
                    force_recalculate=force_recalculate,
                )

            if analytics_type == "financial" or analytics_type == "all":
                AnalyticsService.calculate_financial_analytics(
                    academic_year_id=academic_year_id,
                    term_id=term_id,
                    force_recalculate=force_recalculate,
                )

            # Log the calculation
            AuditService.log_action(
                user=request.user,
                action="system_action",
                description=f"Triggered {analytics_type} analytics calculation",
                data_after={
                    "type": analytics_type,
                    "force": force_recalculate,
                    "academic_year_id": academic_year_id,
                    "term_id": term_id,
                },
                ip_address=request.META.get("REMOTE_ADDR"),
                module_name="core",
            )

            return Response(
                {
                    "status": "success",
                    "message": f"{analytics_type.title()} analytics calculation completed",
                }
            )

        except Exception as e:
            return Response(
                {"status": "error", "message": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class DashboardAPIView(APIView):
    """API for dashboard data"""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """Get dashboard data based on user role"""
        user = request.user

        # Basic statistics
        dashboard_data = {
            "user_role": self.get_user_role(user),
            "current_time": timezone.now(),
        }

        try:
            from src.students.models import Student
            from src.teachers.models import Teacher
            from src.academics.models import Class, AcademicYear, Term

            # Get current academic context
            current_year = AcademicYear.objects.filter(is_current=True).first()
            current_term = Term.objects.filter(is_current=True).first()

            dashboard_data.update(
                {
                    "current_academic_year": (
                        current_year.name if current_year else None
                    ),
                    "current_term": current_term.name if current_term else None,
                    "total_students": Student.objects.filter(status="active").count(),
                    "total_teachers": Teacher.objects.filter(status="active").count(),
                    "total_classes": (
                        Class.objects.filter(academic_year=current_year).count()
                        if current_year
                        else 0
                    ),
                }
            )

            # Role-specific data
            if self.is_admin_user(user):
                dashboard_data.update(
                    self.get_admin_dashboard_data(current_year, current_term)
                )
            elif hasattr(user, "teacher"):
                dashboard_data.update(self.get_teacher_dashboard_data(user.teacher))
            elif hasattr(user, "parent"):
                dashboard_data.update(self.get_parent_dashboard_data(user.parent))
            elif hasattr(user, "student"):
                dashboard_data.update(self.get_student_dashboard_data(user.student))

        except ImportError:
            pass

        return Response(dashboard_data)

    def get_user_role(self, user):
        """Determine user's primary role"""
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

    def is_admin_user(self, user):
        """Check if user is an administrator"""
        return (
            user.is_superuser
            or user.groups.filter(
                name__in=["System Administrators", "School Administrators"]
            ).exists()
        )

    def get_admin_dashboard_data(self, current_year, current_term):
        """Get dashboard data for administrators"""
        data = {}

        if current_year and current_term:
            # Financial summary
            financial_summary = FinancialAnalytics.objects.filter(
                academic_year=current_year, term=current_term
            ).aggregate(
                total_expected=Sum("total_expected_revenue"),
                total_collected=Sum("total_collected_revenue"),
                avg_collection_rate=Avg("collection_rate"),
            )
            data["financial_summary"] = financial_summary

            # Performance summary
            performance_summary = StudentPerformanceAnalytics.objects.filter(
                academic_year=current_year, term=current_term, subject__isnull=True
            ).aggregate(
                avg_performance=Avg("average_marks"),
                avg_attendance=Avg("attendance_percentage"),
            )
            data["performance_summary"] = performance_summary

        # System health
        latest_health = SystemHealthMetrics.objects.first()
        data["system_health"] = {
            "status": "healthy" if latest_health else "unknown",
            "last_check": latest_health.timestamp if latest_health else None,
        }

        return data

    def get_teacher_dashboard_data(self, teacher):
        """Get dashboard data for teachers"""
        try:
            from src.teachers.models import TeacherClassAssignment

            assignments = TeacherClassAssignment.objects.filter(
                teacher=teacher, academic_year__is_current=True
            )

            return {
                "classes_taught": assignments.values("class_instance")
                .distinct()
                .count(),
                "subjects_taught": assignments.values("subject").distinct().count(),
                "total_students": assignments.aggregate(
                    total=Sum("class_instance__student_count")
                )["total"]
                or 0,
            }
        except ImportError:
            return {}

    def get_parent_dashboard_data(self, parent):
        """Get dashboard data for parents"""
        try:
            from src.students.models import StudentParentRelation

            children = StudentParentRelation.objects.filter(parent=parent).count()
            return {"children_count": children}
        except ImportError:
            return {}

    def get_student_dashboard_data(self, student):
        """Get dashboard data for students"""
        # Get latest performance
        latest_performance = (
            StudentPerformanceAnalytics.objects.filter(
                student=student, subject__isnull=True
            )
            .order_by("-calculated_at")
            .first()
        )

        return {
            "current_class": (
                str(student.current_class)
                if hasattr(student, "current_class")
                else None
            ),
            "latest_performance": (
                {
                    "average_marks": (
                        float(latest_performance.average_marks)
                        if latest_performance and latest_performance.average_marks
                        else None
                    ),
                    "attendance_percentage": (
                        float(latest_performance.attendance_percentage)
                        if latest_performance
                        and latest_performance.attendance_percentage
                        else None
                    ),
                }
                if latest_performance
                else None
            ),
        }
