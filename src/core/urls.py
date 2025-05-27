# urls.py
from django.urls import path, include
from . import views

app_name = "core"

urlpatterns = [
    # Dashboard
    path("", views.DashboardView.as_view(), name="dashboard"),
    # System Administration
    path("admin/", views.SystemAdminView.as_view(), name="system_admin"),
    path("settings/", views.SystemSettingsView.as_view(), name="settings"),
    path(
        "settings/<int:pk>/edit/",
        views.SystemSettingEditView.as_view(),
        name="setting_edit",
    ),
    path("audit-logs/", views.AuditLogsView.as_view(), name="audit_logs"),
    path("system-health/", views.SystemHealthView.as_view(), name="system_health"),
    # Analytics
    path("analytics/", views.AnalyticsView.as_view(), name="analytics"),
    path(
        "analytics/student/",
        views.StudentAnalyticsView.as_view(),
        name="student_analytics",
    ),
    path(
        "analytics/class/", views.ClassAnalyticsView.as_view(), name="class_analytics"
    ),
    path(
        "analytics/attendance/",
        views.AttendanceAnalyticsView.as_view(),
        name="attendance_analytics",
    ),
    path(
        "analytics/financial/",
        views.FinancialAnalyticsView.as_view(),
        name="financial_analytics",
    ),
    path(
        "analytics/teacher/",
        views.TeacherAnalyticsView.as_view(),
        name="teacher_analytics",
    ),
    # Reports
    path("reports/", views.ReportsView.as_view(), name="reports"),
    path(
        "reports/generate/", views.GenerateReportView.as_view(), name="generate_report"
    ),
    # User Management
    path("users/", views.UserManagementView.as_view(), name="user_management"),
    path("users/<int:pk>/", views.UserDetailView.as_view(), name="user_detail"),
    path(
        "users/<int:pk>/activity/",
        views.UserActivityView.as_view(),
        name="user_activity",
    ),
    # API URLs
    path("api/", include("core.api.urls")),
]
