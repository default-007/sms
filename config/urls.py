"""
URL Configuration for School Management System.
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi

# API documentation setup
schema_view = get_schema_view(
    openapi.Info(
        title="Mentura School Management System API",
        default_version="v1",
        description="API for School Management System",
        terms_of_service="https://www.schoolmanagementsystem.com/terms/",
        contact=openapi.Contact(email="contact@schoolmanagementsystem.com"),
        license=openapi.License(name="MIT License"),
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
)

urlpatterns = [
    # Admin site
    path("admin/", admin.site.urls),
    # API endpoints
    path("api/v1/", include("src.api.urls")),
    # API documentation
    path(
        "api/docs/",
        schema_view.with_ui("swagger", cache_timeout=0),
        name="schema-swagger-ui",
    ),
    path(
        "api/redoc/", schema_view.with_ui("redoc", cache_timeout=0), name="schema-redoc"
    ),
    # Web app URLs
    # Core app URLs (dashboard and common functionality)
    path("", include("src.core.urls")),
    # Authentication and user management
    path("accounts/", include("src.accounts.urls")),
    # Student management
    path("students/", include("src.students.urls", namespace="students")),
    # Teacher management
    path("teachers/", include("src.teachers.urls", namespace="teachers")),
    # Course & Class management
    path("courses/", include("src.courses.urls", namespace="courses")),
    # Exams & Assessments
    path("exams/", include("src.exams.urls", namespace="exams")),
    # Attendance tracking
    path("attendance/", include("src.attendance.urls", namespace="attendance")),
    # Finance management
    path("finance/", include("src.finance.urls", namespace="finance")),
    # Library management
    # path("library/", include("src.library.urls", namespace="library")),
    # Transport management
    # path("transport/", include("src.transport.urls", namespace="transport")),
    # Communications
    path(
        "communications/",
        include("src.communications.urls", namespace="communications"),
    ),
    # Reports and analytics
    # path("reports/", include("src.reports.urls", namespace="reports")),
    # Redirect root URL to dashboard or login
    # path("", include("src.accounts.urls")),
    path("", RedirectView.as_view(pattern_name="accounts:login"), name="root"),
]

# Serve static and media files in development
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

    # Debug toolbar
    if "debug_toolbar" in settings.INSTALLED_APPS:
        import debug_toolbar

        urlpatterns = [
            path("__debug__/", include(debug_toolbar.urls)),
        ] + urlpatterns
