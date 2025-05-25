"""
URL Configuration for Academics Module

This module defines URL patterns for the academics app,
including both web views and API endpoints.
"""

from django.urls import path, include
from . import views

app_name = "academics"

urlpatterns = [
    # API endpoints
    path("api/", include("academics.api.urls")),
    # Web views (if needed for dashboard/admin interface)
    path("", views.AcademicsHomeView.as_view(), name="home"),
    # Department URLs
    path("departments/", views.DepartmentListView.as_view(), name="department-list"),
    path(
        "departments/<int:pk>/",
        views.DepartmentDetailView.as_view(),
        name="department-detail",
    ),
    # Academic Year URLs
    path(
        "academic-years/",
        views.AcademicYearListView.as_view(),
        name="academic-year-list",
    ),
    path(
        "academic-years/<int:pk>/",
        views.AcademicYearDetailView.as_view(),
        name="academic-year-detail",
    ),
    path(
        "academic-years/create/",
        views.AcademicYearCreateView.as_view(),
        name="academic-year-create",
    ),
    # Section URLs
    path("sections/", views.SectionListView.as_view(), name="section-list"),
    path(
        "sections/<int:pk>/", views.SectionDetailView.as_view(), name="section-detail"
    ),
    path(
        "sections/<int:pk>/hierarchy/",
        views.SectionHierarchyView.as_view(),
        name="section-hierarchy",
    ),
    # Grade URLs
    path("grades/", views.GradeListView.as_view(), name="grade-list"),
    path("grades/<int:pk>/", views.GradeDetailView.as_view(), name="grade-detail"),
    # Class URLs
    path("classes/", views.ClassListView.as_view(), name="class-list"),
    path("classes/<int:pk>/", views.ClassDetailView.as_view(), name="class-detail"),
    path("classes/create/", views.ClassCreateView.as_view(), name="class-create"),
    # Term URLs
    path("terms/", views.TermListView.as_view(), name="term-list"),
    path("terms/<int:pk>/", views.TermDetailView.as_view(), name="term-detail"),
    # Analytics and Reports
    path("analytics/", views.AcademicsAnalyticsView.as_view(), name="analytics"),
    path("reports/", views.AcademicsReportsView.as_view(), name="reports"),
    # Utility URLs
    path("structure/", views.AcademicStructureView.as_view(), name="structure"),
    path("calendar/", views.AcademicCalendarView.as_view(), name="calendar"),
]
