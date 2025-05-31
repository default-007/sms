"""
URL Configuration for School Management System.
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView
from drf_yasg import openapi
from drf_yasg.views import get_schema_view
from rest_framework import permissions

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
    path("accounts/", include("src.accounts.urls")),
    path("students/", include("src.students.urls")),
    path("teachers/", include("src.teachers.urls")),
    path("academics/", include("src.academics.urls")),
    path("subjects/", include("src.subjects.urls")),
    path("scheduling/", include("src.scheduling.urls")),
    path("assignments/", include("src.assignments.urls")),
    path("exams/", include("src.exams.urls")),
    path("attendance/", include("src.attendance.urls")),
    path("finance/", include("src.finance.urls")),
    # path("library/", include("src.library.urls")),
    # path("transport/", include("src.transport.urls")),
    path("communications/", include("src.communications.urls")),
    # path("analytics/", include("src.analytics.urls")),
    # path("reports/", include("src.reports.urls")),
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
