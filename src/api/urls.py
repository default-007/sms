from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from .views import UserViewSet, UserRoleViewSet, LoginView, LogoutView

# Create a router and register our viewsets with it
router = DefaultRouter()
router.register(r"users", UserViewSet, basename="api-user")
router.register(r"roles", UserRoleViewSet, basename="api-role")

# The API URLs are now determined automatically by the router
urlpatterns = [
    path("", include(router.urls)),
    path("auth/login/", LoginView.as_view(), name="api-token-obtain"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="api-token-refresh"),
    path("auth/logout/", LogoutView.as_view(), name="api-auth-logout"),
]
