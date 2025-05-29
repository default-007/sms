# api/views.py
from rest_framework import viewsets, status, permissions, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db.models import Q, Count, Avg, Sum, Max, Min
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django_filters.rest_framework import DjangoFilterFilter
from datetime import datetime, timedelta
import logging

from ..models import (
    SystemSetting,
    AuditLog,
    StudentPerformanceAnalytics,
    ClassPerformanceAnalytics,
    AttendanceAnalytics,
    FinancialAnalytics,
    TeacherPerformanceAnalytics,
    SystemHealthMetrics,
)
from ..services import (
    ConfigurationService,
    AuditService,
    AnalyticsService,
    SecurityService,
    ValidationService,
)
from .serializers import (
    SystemSettingSerializer,
    SystemSettingUpdateSerializer,
    AuditLogSerializer,
    StudentPerformanceAnalyticsSerializer,
    ClassPerformanceAnalyticsSerializer,
    AttendanceAnalyticsSerializer,
    FinancialAnalyticsSerializer,
    TeacherPerformanceAnalyticsSerializer,
    SystemHealthMetricsSerializer,
    AnalyticsSummarySerializer,
    ContentTypeSerializer,
    UserActivitySummarySerializer,
    SystemMetricsSummarySerializer,
    BulkAnalyticsCalculationSerializer,
)
from api.filters import BaseFilterSet
from api.permissions import IsAdminOrReadOnly, IsSystemAdmin

logger = logging.getLogger(__name__)


class SystemSettingFilter(BaseFilterSet):
    """Filter for system settings"""

    class Meta:
        model = SystemSetting
        fields = {
            "category": ["exact", "in"],
            "data_type": ["exact", "in"],
            "is_editable": ["exact"],
            "setting_key": ["exact", "icontains"],
        }


class SystemSettingViewSet(viewsets.ModelViewSet):
    """ViewSet for system settings management"""

    queryset = SystemSetting.objects.all()
    serializer_class = SystemSettingSerializer
    permission_classes = [IsSystemAdmin]
    filterset_class = SystemSettingFilter
    search_fields = ["setting_key", "description"]
    ordering_fields = ["category", "setting_key", "updated_at"]
    ordering = ["category", "setting_key"]

    def perform_update(self, serializer):
        """Log setting updates and clear cache"""
        old_value = self.get_object().get_typed_value()
        serializer.save(updated_by=self.request.user)

        # Log the change
        AuditService.log_action(
            user=self.request.user,
            action="update",
            content_object=serializer.instance,
            description=f"Updated system setting: {serializer.instance.setting_key}",
            data_before={"value": old_value},
            data_after={"value": serializer.instance.get_typed_value()},
            ip_address=self.request.META.get("REMOTE_ADDR"),
            user_agent=self.request.META.get("HTTP_USER_AGENT", ""),
            module_name="core",
        )

    @action(detail=True, methods=["patch"])
    def update_value(self, request, pk=None):
        """Update only the value of a system setting"""
        setting = self.get_object()

        if not setting.is_editable:
            return Response(
                {"error": "This setting is not editable"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = SystemSettingUpdateSerializer(
            data=request.data, context={"setting": setting}
        )

        if serializer.is_valid():
            old_value = setting.get_typed_value()
            setting.set_typed_value(serializer.validated_data["value"])
            setting.updated_by = request.user
            setting.save()

            # Log the change
            AuditService.log_action(
                user=request.user,
                action="update",
                content_object=setting,
                description=f"Updated system setting value: {setting.setting_key}",
                data_before={"value": old_value},
                data_after={"value": setting.get_typed_value()},
                ip_address=request.META.get("REMOTE_ADDR"),
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
                module_name="core",
            )

            return Response(SystemSettingSerializer(setting).data)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=["get"])
    def by_category(self, request):
        """Get settings grouped by category"""
        category = request.query_params.get("category")
        if not category:
            return Response(
                {"error": "Category parameter is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        settings = ConfigurationService.get_settings_by_category(category)
        return Response(settings)

    @action(detail=False, methods=["post"])
    def bulk_update(self, request):
        """Bulk update multiple settings"""
        updates = request.data.get("updates", [])
        if not isinstance(updates, list):
            return Response(
                {"error": "Updates must be a list"}, status=status.HTTP_400_BAD_REQUEST
            )

        updated_settings = []
        errors = []

        for update in updates:
            setting_key = update.get("setting_key")
            value = update.get("value")

            if not setting_key:
                errors.append({"error": "setting_key is required"})
                continue

            try:
                setting = SystemSetting.objects.get(setting_key=setting_key)
                if not setting.is_editable:
                    errors.append(
                        {"setting_key": setting_key, "error": "Setting is not editable"}
                    )
                    continue

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

                # Log each update
                AuditService.log_action(
                    user=request.user,
                    action="update",
                    content_object=setting,
                    description=f"Bulk updated system setting: {setting_key}",
                    data_before={"value": old_value},
                    data_after={"value": setting.get_typed_value()},
                    ip_address=request.META.get("REMOTE_ADDR"),
                    user_agent=request.META.get("HTTP_USER_AGENT", ""),
                    module_name="core",
                )

            except SystemSetting.DoesNotExist:
                errors.append(
                    {"setting_key": setting_key, "error": "Setting not found"}
                )

        return Response({"updated": updated_settings, "errors": errors})


class AuditLogFilter(BaseFilterSet):
    """Filter for audit logs"""

    class Meta:
        model = AuditLog
        fields = {
            "user": ["exact"],
            "action": ["exact", "in"],
            "content_type": ["exact"],
            "module_name": ["exact", "in"],
            "timestamp": ["gte", "lte", "date"],
        }


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for audit logs (read-only)"""

    queryset = AuditLog.objects.select_related("user", "content_type").all()
    serializer_class = AuditLogSerializer
    permission_classes = [IsSystemAdmin]
    filterset_class = AuditLogFilter
    search_fields = [
        "description",
        "user__username",
        "user__first_name",
        "user__last_name",
    ]
    ordering_fields = ["timestamp", "user", "action"]
    ordering = ["-timestamp"]

    @action(detail=False, methods=["get"])
    def user_activity(self, request):
        """Get activity summary for a specific user"""
        user_id = request.query_params.get("user_id")
        days = int(request.query_params.get("days", 30))

        if not user_id:
            return Response(
                {"error": "user_id parameter is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            from django.contrib.auth import get_user_model

            User = get_user_model()
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response(
                {"error": "User not found"}, status=status.HTTP_404_NOT_FOUND
            )

        logs = AuditService.get_user_activity(user, days)

        # Calculate summary statistics
        total_actions = logs.count()
        action_counts = (
            logs.values("action").annotate(count=Count("id")).order_by("-count")
        )
        most_common_action = action_counts.first()["action"] if action_counts else None
        modules_accessed = list(logs.values_list("module_name", flat=True).distinct())

        # Group actions by day
        actions_by_day = {}
        for log in logs:
            day = log.timestamp.date().isoformat()
            actions_by_day[day] = actions_by_day.get(day, 0) + 1

        summary_data = {
            "user_id": user.id,
            "username": user.username,
            "full_name": user.get_full_name(),
            "total_actions": total_actions,
            "last_login": user.last_login,
            "most_common_action": most_common_action,
            "modules_accessed": modules_accessed,
            "actions_by_day": actions_by_day,
        }

        serializer = UserActivitySummarySerializer(summary_data)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def content_types(self, request):
        """Get available content types for filtering"""
        content_types = ContentType.objects.filter(
            id__in=AuditLog.objects.values_list("content_type", flat=True).distinct()
        )
        serializer = ContentTypeSerializer(content_types, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["post"])
    def export(self, request):
        """Export audit logs to CSV"""
        # Implementation would create and return a CSV file
        # For now, return a placeholder response
        return Response(
            {
                "message": "Export functionality to be implemented",
                "total_logs": self.get_queryset().count(),
            }
        )


class StudentPerformanceAnalyticsViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for student performance analytics"""

    queryset = StudentPerformanceAnalytics.objects.select_related(
        "student__user", "student__current_class", "academic_year", "term", "subject"
    ).all()
    serializer_class = StudentPerformanceAnalyticsSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["student", "academic_year", "term", "subject"]
    ordering_fields = ["average_marks", "attendance_percentage", "ranking_in_class"]
    ordering = ["-average_marks"]

    def get_queryset(self):
        """Filter queryset based on user permissions"""
        queryset = super().get_queryset()
        user = self.request.user

        # Teachers can only see their students' analytics
        if hasattr(user, "teacher"):
            # Get classes taught by this teacher
            from teachers.models import TeacherClassAssignment

            taught_classes = TeacherClassAssignment.objects.filter(
                teacher=user.teacher
            ).values_list("class_id", flat=True)

            queryset = queryset.filter(student__current_class__in=taught_classes)

        # Parents can only see their children's analytics
        elif hasattr(user, "parent"):
            from students.models import StudentParentRelation

            children = StudentParentRelation.objects.filter(
                parent=user.parent
            ).values_list("student", flat=True)

            queryset = queryset.filter(student__in=children)

        # Students can only see their own analytics
        elif hasattr(user, "student"):
            queryset = queryset.filter(student=user.student)

        return queryset

    @action(detail=False, methods=["get"])
    def class_comparison(self, request):
        """Compare student performance across classes"""
        academic_year_id = request.query_params.get("academic_year")
        term_id = request.query_params.get("term")
        subject_id = request.query_params.get("subject")

        queryset = self.get_queryset()

        if academic_year_id:
            queryset = queryset.filter(academic_year_id=academic_year_id)
        if term_id:
            queryset = queryset.filter(term_id=term_id)
        if subject_id:
            queryset = queryset.filter(subject_id=subject_id)

        # Group by class and calculate averages
        class_data = (
            queryset.values(
                "student__current_class__id",
                "student__current_class__name",
                "student__current_class__grade__name",
            )
            .annotate(
                avg_marks=Avg("average_marks"),
                avg_attendance=Avg("attendance_percentage"),
                student_count=Count("student", distinct=True),
            )
            .order_by("-avg_marks")
        )

        return Response(list(class_data))

    @action(detail=False, methods=["get"])
    def trending_students(self, request):
        """Get students with improving or declining trends"""
        trend = request.query_params.get("trend", "improving")
        limit = int(request.query_params.get("limit", 10))

        queryset = self.get_queryset().filter(improvement_trend=trend)

        if trend == "improving":
            queryset = queryset.order_by("-trend_percentage")
        else:
            queryset = queryset.order_by("trend_percentage")

        queryset = queryset[:limit]
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class ClassPerformanceAnalyticsViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for class performance analytics"""

    queryset = ClassPerformanceAnalytics.objects.select_related(
        "class_instance__grade__section", "academic_year", "term", "subject"
    ).all()
    serializer_class = ClassPerformanceAnalyticsSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["class_instance", "academic_year", "term", "subject"]
    ordering_fields = ["class_average", "pass_rate", "total_students"]
    ordering = ["-class_average"]

    @action(detail=False, methods=["get"])
    def section_comparison(self, request):
        """Compare performance across sections"""
        academic_year_id = request.query_params.get("academic_year")
        term_id = request.query_params.get("term")

        queryset = self.get_queryset()

        if academic_year_id:
            queryset = queryset.filter(academic_year_id=academic_year_id)
        if term_id:
            queryset = queryset.filter(term_id=term_id)

        # Group by section
        section_data = (
            queryset.values(
                "class_instance__grade__section__id",
                "class_instance__grade__section__name",
            )
            .annotate(
                avg_performance=Avg("class_average"),
                avg_pass_rate=Avg("pass_rate"),
                total_classes=Count("class_instance", distinct=True),
                total_students=Sum("total_students"),
            )
            .order_by("-avg_performance")
        )

        return Response(list(section_data))


class AttendanceAnalyticsViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for attendance analytics"""

    queryset = AttendanceAnalytics.objects.select_related("academic_year", "term").all()
    serializer_class = AttendanceAnalyticsSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["entity_type", "academic_year", "term", "month", "year"]
    ordering_fields = ["attendance_percentage", "total_days"]
    ordering = ["-attendance_percentage"]

    @action(detail=False, methods=["get"])
    def low_attendance_alerts(self, request):
        """Get entities with low attendance rates"""
        threshold = float(request.query_params.get("threshold", 75.0))
        entity_type = request.query_params.get("entity_type", "student")

        queryset = (
            self.get_queryset()
            .filter(entity_type=entity_type, attendance_percentage__lt=threshold)
            .order_by("attendance_percentage")
        )

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class FinancialAnalyticsViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for financial analytics"""

    queryset = FinancialAnalytics.objects.select_related(
        "academic_year", "term", "section", "grade", "fee_category"
    ).all()
    serializer_class = FinancialAnalyticsSerializer
    permission_classes = [IsAdminOrReadOnly]
    filterset_fields = ["academic_year", "term", "section", "grade", "fee_category"]
    ordering_fields = ["total_expected_revenue", "collection_rate"]
    ordering = ["-total_expected_revenue"]

    @action(detail=False, methods=["get"])
    def collection_summary(self, request):
        """Get collection summary for dashboard"""
        academic_year_id = request.query_params.get("academic_year")
        term_id = request.query_params.get("term")

        queryset = self.get_queryset()

        if academic_year_id:
            queryset = queryset.filter(academic_year_id=academic_year_id)
        if term_id:
            queryset = queryset.filter(term_id=term_id)

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
    permission_classes = [IsAdminOrReadOnly]
    filterset_fields = ["teacher", "academic_year", "term"]
    ordering_fields = ["overall_performance_score", "average_class_performance"]
    ordering = ["-overall_performance_score"]

    @action(detail=False, methods=["get"])
    def top_performers(self, request):
        """Get top performing teachers"""
        limit = int(request.query_params.get("limit", 10))
        metric = request.query_params.get("metric", "overall_performance_score")

        if metric not in [
            "overall_performance_score",
            "average_class_performance",
            "attendance_rate",
        ]:
            metric = "overall_performance_score"

        queryset = self.get_queryset().order_by(f"-{metric}")[:limit]
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class SystemHealthMetricsViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for system health metrics"""

    queryset = SystemHealthMetrics.objects.all()
    serializer_class = SystemHealthMetricsSerializer
    permission_classes = [IsSystemAdmin]
    filterset_fields = ["timestamp"]
    ordering = ["-timestamp"]

    @action(detail=False, methods=["get"])
    def current_status(self, request):
        """Get current system status"""
        latest_metric = self.get_queryset().first()

        if not latest_metric:
            return Response(
                {"error": "No metrics available"}, status=status.HTTP_404_NOT_FOUND
            )

        # Calculate status indicators
        status_data = {
            "timestamp": latest_metric.timestamp,
            "overall_health": "good",  # Simple logic - would be more complex in production
            "database_health": (
                "good" if latest_metric.avg_query_time_ms < 100 else "warning"
            ),
            "cache_health": "good" if latest_metric.cache_hit_rate > 80 else "warning",
            "performance_health": (
                "good" if latest_metric.avg_response_time_ms < 500 else "warning"
            ),
            "storage_health": (
                "good"
                if latest_metric.storage_used_gb
                / (latest_metric.storage_used_gb + latest_metric.storage_available_gb)
                < 0.8
                else "warning"
            ),
        }

        return Response(status_data)


class AnalyticsDashboardView(APIView):
    """API view for analytics dashboard data"""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """Get dashboard analytics summary"""
        academic_year_id = request.query_params.get("academic_year")
        term_id = request.query_params.get("term")

        # Get current academic year/term if not specified
        if not academic_year_id:
            from academics.models import AcademicYear

            current_year = AcademicYear.objects.filter(is_current=True).first()
            academic_year_id = current_year.id if current_year else None

        if not term_id:
            from academics.models import Term

            current_term = Term.objects.filter(
                academic_year_id=academic_year_id, is_current=True
            ).first()
            term_id = current_term.id if current_term else None

        # Cache key for dashboard data
        cache_key = f"dashboard_analytics_{academic_year_id}_{term_id}"
        cached_data = cache.get(cache_key)

        if cached_data:
            return Response(cached_data)

        # Calculate dashboard metrics
        dashboard_data = self._calculate_dashboard_metrics(academic_year_id, term_id)

        # Cache for 15 minutes
        cache.set(cache_key, dashboard_data, 900)

        return Response(dashboard_data)

    def _calculate_dashboard_metrics(self, academic_year_id, term_id):
        """Calculate metrics for dashboard"""
        from students.models import Student
        from academics.models import Class, AcademicYear, Term
        from teachers.models import Teacher

        # Get academic year and term names
        try:
            academic_year = AcademicYear.objects.get(id=academic_year_id)
            term = Term.objects.get(id=term_id)
        except (AcademicYear.DoesNotExist, Term.DoesNotExist):
            return {"error": "Invalid academic year or term"}

        # Student metrics
        total_students = Student.objects.filter(status="active").count()
        student_analytics = StudentPerformanceAnalytics.objects.filter(
            academic_year_id=academic_year_id,
            term_id=term_id,
            subject__isnull=True,  # Overall performance
        )

        student_stats = student_analytics.aggregate(
            avg_performance=Avg("average_marks"),
            avg_attendance=Avg("attendance_percentage"),
        )

        # Class metrics
        total_classes = Class.objects.filter(academic_year_id=academic_year_id).count()
        class_analytics = ClassPerformanceAnalytics.objects.filter(
            academic_year_id=academic_year_id, term_id=term_id, subject__isnull=True
        )

        best_class = class_analytics.order_by("-class_average").first()
        worst_class = class_analytics.order_by("class_average").first()

        # Financial metrics
        financial_analytics = FinancialAnalytics.objects.filter(
            academic_year_id=academic_year_id, term_id=term_id
        )

        financial_stats = financial_analytics.aggregate(
            total_expected=Sum("total_expected_revenue"),
            total_collected=Sum("total_collected_revenue"),
            total_outstanding=Sum("total_outstanding"),
            avg_collection_rate=Avg("collection_rate"),
        )

        # Teacher metrics
        total_teachers = Teacher.objects.filter(status="active").count()
        teacher_analytics = TeacherPerformanceAnalytics.objects.filter(
            academic_year_id=academic_year_id, term_id=term_id
        )

        teacher_stats = teacher_analytics.aggregate(
            avg_performance=Avg("overall_performance_score")
        )

        return {
            "academic_year": academic_year.name,
            "term": term.name,
            "total_students": total_students,
            "active_students": total_students,  # Simplified
            "average_performance": student_stats["avg_performance"] or 0,
            "attendance_rate": student_stats["avg_attendance"] or 0,
            "total_classes": total_classes,
            "best_performing_class": (
                str(best_class.class_instance) if best_class else None
            ),
            "lowest_performing_class": (
                str(worst_class.class_instance) if worst_class else None
            ),
            "total_revenue_expected": financial_stats["total_expected"] or 0,
            "total_revenue_collected": financial_stats["total_collected"] or 0,
            "collection_rate": financial_stats["avg_collection_rate"] or 0,
            "outstanding_amount": financial_stats["total_outstanding"] or 0,
            "total_teachers": total_teachers,
            "average_teacher_performance": teacher_stats["avg_performance"] or 0,
        }


class BulkAnalyticsCalculationView(APIView):
    """API view for triggering bulk analytics calculations"""

    permission_classes = [IsSystemAdmin]

    def post(self, request):
        """Trigger analytics calculation"""
        serializer = BulkAnalyticsCalculationSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        analytics_type = data["analytics_type"]
        academic_year_id = data.get("academic_year_id")
        term_id = data.get("term_id")
        force_recalculate = data["force_recalculate"]

        # Get academic year and term objects
        academic_year = None
        term = None

        if academic_year_id:
            from academics.models import AcademicYear

            academic_year = AcademicYear.objects.get(id=academic_year_id)

        if term_id:
            from academics.models import Term

            term = Term.objects.get(id=term_id)

        try:
            # Trigger appropriate analytics calculation
            if analytics_type in ["student", "all"]:
                AnalyticsService.calculate_student_performance(
                    academic_year=academic_year,
                    term=term,
                    force_recalculate=force_recalculate,
                )

            if analytics_type in ["class", "all"]:
                AnalyticsService.calculate_class_performance(
                    academic_year=academic_year,
                    term=term,
                    force_recalculate=force_recalculate,
                )

            if analytics_type in ["attendance", "all"]:
                AnalyticsService.calculate_attendance_analytics(
                    academic_year=academic_year,
                    term=term,
                    force_recalculate=force_recalculate,
                )

            if analytics_type in ["financial", "all"]:
                AnalyticsService.calculate_financial_analytics(
                    academic_year=academic_year,
                    term=term,
                    force_recalculate=force_recalculate,
                )

            # Log the calculation request
            AuditService.log_action(
                user=request.user,
                action="system_action",
                description=f"Triggered {analytics_type} analytics calculation",
                data_after={
                    "analytics_type": analytics_type,
                    "academic_year": str(academic_year) if academic_year else None,
                    "term": str(term) if term else None,
                    "force_recalculate": force_recalculate,
                },
                ip_address=request.META.get("REMOTE_ADDR"),
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
                module_name="core",
            )

            return Response(
                {
                    "message": f"{analytics_type.title()} analytics calculation triggered successfully",
                    "analytics_type": analytics_type,
                    "academic_year": str(academic_year) if academic_year else "current",
                    "term": str(term) if term else "current",
                    "force_recalculate": force_recalculate,
                }
            )

        except Exception as e:
            logger.error(f"Error triggering analytics calculation: {str(e)}")
            return Response(
                {"error": f"Analytics calculation failed: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class SystemMetricsView(APIView):
    """API view for system metrics and health"""

    permission_classes = [IsSystemAdmin]

    def get(self, request):
        """Get current system metrics"""
        # Calculate current metrics
        from django.contrib.auth import get_user_model
        from django.contrib.sessions.models import Session

        User = get_user_model()

        # Current active users (simplified - users with active sessions)
        active_sessions = Session.objects.filter(expire_date__gte=timezone.now())
        current_users = active_sessions.count()

        # Total users
        total_users = User.objects.count()

        # Get latest health metrics
        latest_health = SystemHealthMetrics.objects.first()

        metrics = {
            "current_users": current_users,
            "total_users": total_users,
            "database_size_mb": 0,  # Would calculate actual database size
            "average_response_time": (
                latest_health.avg_response_time_ms if latest_health else 0
            ),
            "error_rate": latest_health.error_rate if latest_health else 0,
            "uptime_percentage": 99.9,  # Would calculate actual uptime
            "last_backup": None,  # Would get from backup logs
            "pending_tasks": latest_health.pending_tasks if latest_health else 0,
        }

        serializer = SystemMetricsSummarySerializer(metrics)
        return Response(serializer.data)
