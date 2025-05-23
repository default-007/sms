# src/api/urls.py
"""Main API URL Router"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
    SpectacularRedocView,
)

# API version prefix
app_name = "api"

# API Documentation URLs
urlpatterns = [
    # API Documentation
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path("docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
    # Module API endpoints (each app manages its own endpoints)
    path("auth/", include("src.accounts.api.urls")),
    path("academics/", include("src.academics.api.urls")),
    path("students/", include("src.students.api.urls")),
    path("teachers/", include("src.teachers.api.urls")),
    path("subjects/", include("src.subjects.api.urls")),
    path("scheduling/", include("src.scheduling.api.urls")),
    path("assignments/", include("src.assignments.api.urls")),
    path("exams/", include("src.exams.api.urls")),
    path("attendance/", include("src.attendance.api.urls")),
    path("finance/", include("src.finance.api.urls")),
    path("library/", include("src.library.api.urls")),
    path("transport/", include("src.transport.api.urls")),
    path("communications/", include("src.communications.api.urls")),
    path("analytics/", include("src.analytics.api.urls")),
    path("reports/", include("src.reports.api.urls")),
    path("core/", include("src.core.api.urls")),
]
