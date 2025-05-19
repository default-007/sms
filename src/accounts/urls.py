from django.urls import path
from django.contrib.auth import views as auth_views

from .views import (
    CustomLoginView,
    CustomLogoutView,
    CustomPasswordChangeView,
    CustomPasswordResetView,
    CustomPasswordResetConfirmView,
    UserListView,
    UserDetailView,
    UserCreateView,
    UserUpdateView,
    UserDeleteView,
    RoleListView,
    RoleDetailView,
    RoleCreateView,
    RoleUpdateView,
    RoleDeleteView,
    bulk_user_action,
    export_users,
    profile_view,
    reset_user_password,
    toggle_user_status,
)

app_name = "accounts"

urlpatterns = [
    # Authentication views
    path("login/", CustomLoginView.as_view(), name="login"),
    path("logout/", CustomLogoutView.as_view(), name="logout"),
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
    # User management views
    path("users/", UserListView.as_view(), name="user_list"),
    path("users/add/", UserCreateView.as_view(), name="user_create"),
    path("users/<int:pk>/", UserDetailView.as_view(), name="user_detail"),
    path("users/<int:pk>/edit/", UserUpdateView.as_view(), name="user_update"),
    path("users/<int:pk>/delete/", UserDeleteView.as_view(), name="user_delete"),
    # Role management views
    path("roles/", RoleListView.as_view(), name="role_list"),
    path("roles/add/", RoleCreateView.as_view(), name="role_create"),
    path("roles/<int:pk>/", RoleDetailView.as_view(), name="role_detail"),
    path("roles/<int:pk>/edit/", RoleUpdateView.as_view(), name="role_update"),
    path("roles/<int:pk>/delete/", RoleDeleteView.as_view(), name="role_delete"),
    # Profile view
    path("profile/", profile_view, name="profile"),
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
    path("bulk-action/", bulk_user_action, name="bulk_action"),
    path("export/", export_users, name="export_users"),
]
