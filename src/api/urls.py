from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)

from . import views

# Create router for ViewSets (if we had any)
router = DefaultRouter()
# router.register(r"users", views.UserViewSet)
# router.register(r"roles", views.UserRoleViewSet)
router.register(r"students", views.StudentViewSet)
router.register(r"parents", views.ParentViewSet)
router.register(r"student-parent-relations", views.StudentParentRelationViewSet)
router.register(r"teachers", views.TeacherViewSet)
router.register(r"teacher-class-assignments", views.TeacherClassAssignmentViewSet)
router.register(r"teacher-evaluations", views.TeacherEvaluationViewSet)
router.register(r"departments", views.DepartmentViewSet)
router.register(r"academic-years", views.AcademicYearViewSet)
router.register(r"grades", views.GradeViewSet)
router.register(r"sections", views.SectionViewSet)
router.register(r"classes", views.ClassViewSet)
router.register(r"subjects", views.SubjectViewSet)
router.register(r"syllabi", views.SyllabusViewSet)
router.register(r"time-slots", views.TimeSlotViewSet)
router.register(r"timetables", views.TimetableViewSet)
router.register(r"assignments", views.AssignmentViewSet)
router.register(r"assignment-submissions", views.AssignmentSubmissionViewSet)
router.register(r"system-settings", views.SystemSettingViewSet)
router.register(r"documents", views.DocumentViewSet)

# Authentication endpoints
urlpatterns = [
    # Authentication endpoints
    path("auth/login/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("auth/verify/", TokenVerifyView.as_view(), name="token_verify"),
    # path("auth/logout/", views.LogoutAPIView.as_view(), name="logout"),
    # User management endpoints
    path("users/", views.UserListCreateAPIView.as_view(), name="user_list_create"),
    path(
        "users/<int:pk>/",
        views.UserRetrieveUpdateDestroyAPIView.as_view(),
        name="user_detail",
    ),
    path("users/me/", views.MyProfileAPIView.as_view(), name="my_profile"),
    path(
        "users/statistics/",
        views.UserStatsAPIView.as_view(),
        name="user_statistics",
    ),
    path(
        "users/bulk-action/",
        views.UserBulkActionAPIView.as_view(),
        name="user_bulk_action",
    ),
    # path(
    # "users/<int:pk>/toggle-status/",
    # views.ToggleUserStatusAPIView.as_view(),
    # name="toggle_user_status",
    # ),
    # path(
    # "users/<int:pk>/reset-password/",
    # views.ResetUserPasswordAPIView.as_view(),
    # name="reset_user_password",
    # ),
    # path(
    #    "users/<int:pk>/sessions/",
    #    views.UserSessionsAPIView.as_view(),
    #    name="user_sessions",
    # ),
    # path(
    #    "users/<int:pk>/audit-logs/",
    #    views.UserAuditLogsAPIView.as_view(),
    #    name="user_audit_logs",
    # ),
    # Role management endpoints
    path("roles/", views.UserRoleListCreateAPIView.as_view(), name="role_list_create"),
    path(
        "roles/<int:pk>/",
        views.UserRoleRetrieveUpdateDestroyAPIView.as_view(),
        name="role_detail",
    ),
    # path(
    #    "roles/statistics/",
    #    views.RoleStatisticsAPIView.as_view(),
    #    name="role_statistics",
    # ),
    # Role assignment endpoints
    path(
        "role-assignments/",
        views.UserRoleAssignmentListAPIView.as_view(),
        name="role_assignment_list",
    ),
    path(
        "role-assignments/assign/",
        views.AssignRoleAPIView.as_view(),
        name="assign_role",
    ),
    path(
        "role-assignments/remove/",
        views.RemoveRoleAPIView.as_view(),
        name="remove_role",
    ),
    # path(
    #    "role-assignments/expire/",
    #    views.ExpireRoleAssignmentsAPIView.as_view(),
    #    name="expire_role_assignments",
    # ),
    # path(
    #    "role-assignments/<int:pk>/",
    #    views.UserRoleAssignmentDetailAPIView.as_view(),
    #    name="role_assignment_detail",
    # ),
    # Password management endpoints
    path(
        "password/change/",
        views.PasswordChangeAPIView.as_view(),
        name="password_change",
    ),
    # path(
    #    "password/reset/",
    #    views.PasswordResetAPIView.as_view(),
    #    name="password_reset",
    # ),
    # path(
    #    "password/reset/confirm/",
    #    views.PasswordResetConfirmAPIView.as_view(),
    #    name="password_reset_confirm",
    # ),
    # path(
    #    "password/validate/",
    #    views.PasswordValidationAPIView.as_view(),
    #    name="password_validate",
    # ),
    # Permissions and security endpoints
    # path(
    #    "permissions/my/",
    #    views.MyPermissionsAPIView.as_view(),
    #    name="my_permissions",
    # ),
    # path(
    #    "permissions/check/",
    #    views.CheckPermissionAPIView.as_view(),
    #    name="check_permission",
    # ),
    # path(
    #    "permissions/scopes/",
    #    views.PermissionScopesAPIView.as_view(),
    #    name="permission_scopes",
    # ),
    # Session management endpoints
    # path("sessions/", views.MySessionsAPIView.as_view(), name="my_sessions"),
    # path(
    #    "sessions/<str:session_key>/terminate/",
    #    views.TerminateSessionAPIView.as_view(),
    #    name="terminate_session",
    # ),
    # path(
    #    "sessions/terminate-all/",
    #    views.TerminateAllSessionsAPIView.as_view(),
    #    name="terminate_all_sessions",
    # ),
    # Audit and activity endpoints
    # path("audit-logs/", views.AuditLogListAPIView.as_view(), name="audit_log_list"),
    # path("audit-logs/my/", views.MyAuditLogsAPIView.as_view(), name="my_audit_logs"),
    # path(
    #    "audit-logs/export/",
    #    views.ExportAuditLogsAPIView.as_view(),
    #    name="export_audit_logs",
    # ),
    # Utility endpoints
    # path(
    #    "generate-username/",
    #    views.GenerateUsernameAPIView.as_view(),
    #    name="generate_username",
    # ),
    # path(
    #    "generate-password/",
    #    views.GeneratePasswordAPIView.as_view(),
    #    name="generate_password",
    # ),
    # path(
    #    "validate-email/",
    #    views.ValidateEmailAPIView.as_view(),
    #    name="validate_email",
    # ),
    # path(
    #    "validate-username/",
    #    views.ValidateUsernameAPIView.as_view(),
    #    name="validate_username",
    # ),
    # Include router URLs
    path("", include(router.urls)),
]
