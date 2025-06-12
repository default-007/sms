# core/api/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    SystemSettingViewSet,
    AuditLogViewSet,
    StudentPerformanceAnalyticsViewSet,
    ClassPerformanceAnalyticsViewSet,
    AttendanceAnalyticsViewSet,
    FinancialAnalyticsViewSet,
    TeacherPerformanceAnalyticsViewSet,
    SystemHealthMetricsViewSet,
    AnalyticsAPIView,
    DashboardAPIView,
)

# Create router and register viewsets
router = DefaultRouter()
router.register(r"settings", SystemSettingViewSet, basename="systemsetting")
router.register(r"audit-logs", AuditLogViewSet, basename="auditlog")
router.register(
    r"analytics/student-performance",
    StudentPerformanceAnalyticsViewSet,
    basename="student-analytics",
)
router.register(
    r"analytics/class-performance",
    ClassPerformanceAnalyticsViewSet,
    basename="class-analytics",
)
router.register(
    r"analytics/attendance", AttendanceAnalyticsViewSet, basename="attendance-analytics"
)
router.register(
    r"analytics/financial", FinancialAnalyticsViewSet, basename="financial-analytics"
)
router.register(
    r"analytics/teacher-performance",
    TeacherPerformanceAnalyticsViewSet,
    basename="teacher-analytics",
)
router.register(
    r"system/health-metrics", SystemHealthMetricsViewSet, basename="health-metrics"
)

urlpatterns = [
    # Include router URLs
    path("", include(router.urls)),
    # Custom API endpoints
    path(
        "analytics/calculate/", AnalyticsAPIView.as_view(), name="analytics-calculate"
    ),
    path("dashboard/", DashboardAPIView.as_view(), name="analytics-dashboard"),
    # System metrics and status
    path("system/metrics/", DashboardAPIView.as_view(), name="system-metrics"),
    path("system/status/", DashboardAPIView.as_view(), name="system-status"),
]
