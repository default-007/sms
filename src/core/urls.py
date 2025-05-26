from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

app_name = "core"

urlpatterns = [
    # Dashboard
    path("", views.dashboard, name="dashboard"),
    # Document management
    path("documents/", views.DocumentListView.as_view(), name="document_list"),
    path(
        "documents/<int:pk>/",
        views.DocumentDetailView.as_view(),
        name="document_detail",
    ),
    path(
        "documents/create/", views.DocumentCreateView.as_view(), name="document_create"
    ),
    path(
        "documents/<int:pk>/update/",
        views.DocumentUpdateView.as_view(),
        name="document_update",
    ),
    path(
        "documents/<int:pk>/delete/",
        views.DocumentDeleteView.as_view(),
        name="document_delete",
    ),
    # System settings
    path(
        "settings/", views.SystemSettingListView.as_view(), name="system_setting_list"
    ),
    path(
        "settings/<int:pk>/update/",
        views.SystemSettingUpdateView.as_view(),
        name="system_setting_update",
    ),
    path(
        "settings/maintenance-toggle/",
        views.system_maintenance_toggle,
        name="maintenance_toggle",
    ),
    path("system-info/", views.system_info_view, name="system_info"),
    # Audit logs
    path("audit-logs/", views.audit_log_view, name="audit_logs"),
    # API endpoints will be registered in src.api.urls
]
