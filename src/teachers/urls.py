# teachers/urls.py - Enhanced with credential preview endpoint

from django.urls import path
from . import views

app_name = "teachers"

urlpatterns = [
    # Teacher CRUD operations
    path("", views.TeacherListView.as_view(), name="teacher-list"),
    path("create/", views.TeacherCreateView.as_view(), name="teacher-create"),
    path("<int:pk>/", views.TeacherDetailView.as_view(), name="teacher-detail"),
    path("<int:pk>/edit/", views.TeacherUpdateView.as_view(), name="teacher-update"),
    path("<int:pk>/delete/", views.TeacherDeleteView.as_view(), name="teacher-delete"),
    # Enhanced auto-generation endpoints
    path(
        "credential-preview/",
        views.TeacherCredentialPreviewView.as_view(),
        name="credential-preview",
    ),
    path("api/create/", views.create_teacher_api_endpoint, name="api-create-teacher"),
    # Class assignments
    path(
        "<int:teacher_id>/assign-class/",
        views.TeacherClassAssignmentCreateView.as_view(),
        name="assign-class",
    ),
    # Evaluations
    path(
        "<int:teacher_id>/evaluate/",
        views.TeacherEvaluationCreateView.as_view(),
        name="evaluate-teacher",
    ),
    # Timetable
    path(
        "<int:teacher_id>/timetable/",
        views.TeacherTimetableView.as_view(),
        name="teacher-timetable",
    ),
    path(
        "<int:teacher_id>/timetable/pdf/",
        views.TeacherTimetablePDFView.as_view(),
        name="teacher-timetable-pdf",
    ),
    # Analytics and reports
    path("dashboard/", views.TeacherDashboardView.as_view(), name="teacher-dashboard"),
    path(
        "statistics/", views.TeacherStatisticsView.as_view(), name="teacher-statistics"
    ),
    path(
        "performance/",
        views.TeacherPerformanceView.as_view(),
        name="teacher-performance",
    ),
    # Export
    path(
        "export/<str:format>/", views.TeacherExportView.as_view(), name="teacher-export"
    ),
    # API endpoints
    path("api/", views.TeacherApiView.as_view(), name="teacher-api"),
    # Bulk operations
    path(
        "bulk-create/",
        views.TeacherBulkCreateView.as_view(),
        name="teacher-bulk-create",
    ),
]
