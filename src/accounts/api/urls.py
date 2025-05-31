# src/accounts/api/urls.py

from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    AuditLogListView,
    BulkUserImportView,
    CustomTokenObtainPairView,
    ProfileView,
    SendOTPView,
    SystemHealthView,
    UserRoleViewSet,
    UserStatsView,
    UserViewSet,
    VerifyOTPView,
)

# Create router and register viewsets
router = DefaultRouter()
router.register(r"users", UserViewSet, basename="user")
router.register(r"roles", UserRoleViewSet, basename="role")

app_name = "accounts_api"

urlpatterns = [
    # Authentication endpoints
    path("auth/login/", CustomTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    # Profile endpoints
    path("profile/", ProfileView.as_view(), name="profile"),
    # OTP endpoints
    path("otp/send/", SendOTPView.as_view(), name="send_otp"),
    path("otp/verify/", VerifyOTPView.as_view(), name="verify_otp"),
    # Statistics endpoints
    path("stats/", UserStatsView.as_view(), name="user_stats"),
    # Bulk operations
    path("bulk-import/", BulkUserImportView.as_view(), name="bulk_import"),
    # Audit logs
    path("audit-logs/", AuditLogListView.as_view(), name="audit_logs"),
    # System health
    path("health/", SystemHealthView.as_view(), name="system_health"),
    # Include router URLs
    path("", include(router.urls)),
]
