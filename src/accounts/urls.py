# src/accounts/urls.py (Updated with new endpoints)

from django.contrib.auth import views as auth_views
from django.urls import path, include

from .views import (
    # Enhanced authentication views
    EnhancedLoginView,
    AjaxLoginView,
    CustomLogoutView,
    CustomPasswordChangeView,
    CustomPasswordResetView,
    CustomPasswordResetConfirmView,
    # User management views
    UserCreateView,
    UserDeleteView,
    UserDetailView,
    UserListView,
    UserUpdateView,
    # Role management views
    RoleCreateView,
    RoleDeleteView,
    RoleDetailView,
    RoleListView,
    RoleUpdateView,
    # Utility views
    bulk_import_users,
    bulk_user_action,
    export_users,
    profile_view,
    reset_user_password,
    toggle_user_status,
    validate_identifier,
    # API views for mobile/AJAX support
    # api_login,
    # api_logout,
    # api_user_info,
    # api_validate_identifier,
)

app_name = "accounts"

urlpatterns = [
    # ==============================================================================
    # AUTHENTICATION URLS
    # ==============================================================================
    # Enhanced login/logout
    path("login/", EnhancedLoginView.as_view(), name="login"),
    path("logout/", CustomLogoutView.as_view(), name="logout"),
    # AJAX/API login for mobile apps
    # path("api/login/", AjaxLoginView.as_view(), name="api_login"),
    # path("api/logout/", api_logout, name="api_logout"),
    # Password management
    path(
        "password-change/", CustomPasswordChangeView.as_view(), name="password_change"
    ),
    path("password-reset/", CustomPasswordResetView.as_view(), name="password_reset"),
    path(
        "password-reset/done/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="accounts/password_reset_done.html"
        ),
        name="password_reset_done",
    ),
    path(
        "password-reset/<uidb64>/<token>/",
        CustomPasswordResetConfirmView.as_view(),
        name="password_reset_confirm",
    ),
    path(
        "password-reset/complete/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="accounts/password_reset_complete.html"
        ),
        name="password_reset_complete",
    ),
    # ==============================================================================
    # VALIDATION AND UTILITY URLS
    # ==============================================================================
    # Identifier validation (AJAX)
    path("validate-identifier/", validate_identifier, name="validate_identifier"),
    # API endpoints for identifier validation
    # path("api/validate-identifier/",api_validate_identifier,name="api_validate_identifier",),
    # path("api/user-info/", api_user_info, name="api_user_info"),
    # ==============================================================================
    # USER MANAGEMENT URLS
    # ==============================================================================
    # User CRUD operations
    path("users/", UserListView.as_view(), name="user_list"),
    path("users/add/", UserCreateView.as_view(), name="user_create"),
    path("users/<int:pk>/", UserDetailView.as_view(), name="user_detail"),
    path("users/<int:pk>/edit/", UserUpdateView.as_view(), name="user_update"),
    path("users/<int:pk>/delete/", UserDeleteView.as_view(), name="user_delete"),
    # User management actions
    path(
        "users/<int:user_id>/toggle-status/",
        toggle_user_status,
        name="toggle_user_status",
    ),
    path(
        "users/<int:user_id>/reset-password/",
        reset_user_password,
        name="reset_user_password",
    ),
    # Bulk operations
    path("bulk-action/", bulk_user_action, name="bulk_action"),
    path("bulk-import/", bulk_import_users, name="bulk_import_users"),
    path("export/", export_users, name="export_users"),
    # ==============================================================================
    # ROLE MANAGEMENT URLS
    # ==============================================================================
    # Role CRUD operations
    path("roles/", RoleListView.as_view(), name="role_list"),
    path("roles/add/", RoleCreateView.as_view(), name="role_create"),
    path("roles/<int:pk>/", RoleDetailView.as_view(), name="role_detail"),
    path("roles/<int:pk>/edit/", RoleUpdateView.as_view(), name="role_update"),
    path("roles/<int:pk>/delete/", RoleDeleteView.as_view(), name="role_delete"),
    # ==============================================================================
    # PROFILE MANAGEMENT URLS
    # ==============================================================================
    # User profile
    path("profile/", profile_view, name="profile"),
    # ==============================================================================
    # API URLS (for mobile apps and AJAX)
    # ==============================================================================
    # API endpoints grouped under api/ prefix
    # path(
    #    "api/",
    #    include(
    #        [
    #            # Authentication endpoints
    #            path("auth/login/", AjaxLoginView.as_view(), name="api_auth_login"),
    #            path("auth/logout/", api_logout, name="api_auth_logout"),
    #            path(
    #                "auth/validate/", api_validate_identifier, name="api_auth_validate"
    #            ),
    #            # User information endpoints
    #            path("user/info/", api_user_info, name="api_user_info"),
    #            path("user/profile/", api_user_profile, name="api_user_profile"),
    #            # Authentication status
    #            path("auth/status/", api_auth_status, name="api_auth_status"),
    #        ]
    #    ),
    # ),
]
