# api/urls.py
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
    AnalyticsDashboardView,
    BulkAnalyticsCalculationView,
    SystemMetricsView,
)

# Create router and register viewsets
router = DefaultRouter()

# System management endpoints
router.register(r"settings", SystemSettingViewSet, basename="systemsetting")
router.register(r"audit-logs", AuditLogViewSet, basename="auditlog")
router.register(r"system-health", SystemHealthMetricsViewSet, basename="systemhealth")

# Analytics endpoints
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

urlpatterns = [
    # Include router URLs
    path("", include(router.urls)),
    # Custom API views
    path("dashboard/", AnalyticsDashboardView.as_view(), name="analytics-dashboard"),
    path(
        "analytics/calculate/",
        BulkAnalyticsCalculationView.as_view(),
        name="analytics-calculate",
    ),
    path("system/metrics/", SystemMetricsView.as_view(), name="system-metrics"),
]
