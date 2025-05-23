# src/accounts/api/urls.py

from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    CustomTokenObtainPairView,
    UserListCreateView,
    UserDetailView,
    UserProfileView,
    PasswordChangeView,
    PasswordResetView,
    UserRoleListCreateView,
    UserRoleDetailView,
    UserRoleAssignmentView,
    BulkUserActionView,
    UserAuditLogView,
    UserStatisticsView,
    UserToggleStatusView,
    logout_view,
    user_permissions_view,
    unlock_account_view,
    login_statistics_view,
    suspicious_activity_view,
)

app_name = "accounts_api"

urlpatterns = [
    # Authentication
    path("auth/login/", CustomTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("auth/logout/", logout_view, name="logout"),
    # Users
    path("users/", UserListCreateView.as_view(), name="user_list_create"),
    path("users/<int:pk>/", UserDetailView.as_view(), name="user_detail"),
    path("users/profile/", UserProfileView.as_view(), name="user_profile"),
    path(
        "users/<int:user_id>/toggle-status/",
        UserToggleStatusView.as_view(),
        name="user_toggle_status",
    ),
    path(
        "users/<int:user_id>/reset-password/",
        PasswordResetView.as_view(),
        name="user_reset_password",
    ),
    path("users/<int:user_id>/unlock/", unlock_account_view, name="user_unlock"),
    path("users/bulk-action/", BulkUserActionView.as_view(), name="bulk_user_action"),
    path("users/statistics/", UserStatisticsView.as_view(), name="user_statistics"),
    # Password management
    path("password/change/", PasswordChangeView.as_view(), name="password_change"),
    # Roles
    path("roles/", UserRoleListCreateView.as_view(), name="role_list_create"),
    path("roles/<int:pk>/", UserRoleDetailView.as_view(), name="role_detail"),
    # Role assignments
    path(
        "users/<int:user_id>/roles/",
        UserRoleAssignmentView.as_view(),
        name="user_role_assign",
    ),
    path(
        "users/<int:user_id>/roles/<int:role_id>/",
        UserRoleAssignmentView.as_view(),
        name="user_role_remove",
    ),
    # Audit logs
    path("audit-logs/", UserAuditLogView.as_view(), name="audit_logs"),
    path(
        "users/<int:user_id>/audit-logs/",
        UserAuditLogView.as_view(),
        name="user_audit_logs",
    ),
    # Permissions
    path("permissions/", user_permissions_view, name="user_permissions"),
    # Analytics
    path(
        "users/<int:user_id>/login-statistics/",
        login_statistics_view,
        name="login_statistics",
    ),
    path(
        "users/<int:user_id>/suspicious-activity/",
        suspicious_activity_view,
        name="suspicious_activity",
    ),
]
