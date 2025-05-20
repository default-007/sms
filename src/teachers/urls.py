from django.urls import path
from . import views

app_name = "teachers"

urlpatterns = [
    # List and CRUD views
    path("", views.TeacherListView.as_view(), name="teacher-list"),
    path("<int:pk>/", views.TeacherDetailView.as_view(), name="teacher-detail"),
    path("create/", views.TeacherCreateView.as_view(), name="teacher-create"),
    path("<int:pk>/update/", views.TeacherUpdateView.as_view(), name="teacher-update"),
    path("<int:pk>/delete/", views.TeacherDeleteView.as_view(), name="teacher-delete"),
    # Class assignments
    path(
        "<int:teacher_id>/assignment/create/",
        views.TeacherClassAssignmentCreateView.as_view(),
        name="teacher-assignment-create",
    ),
    # Evaluations
    path(
        "<int:teacher_id>/evaluation/create/",
        views.TeacherEvaluationCreateView.as_view(),
        name="teacher-evaluation-create",
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
    # Analytics & Dashboard
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
    # API endpoints for datatables
    path("api/teachers/", views.TeacherApiView.as_view(), name="teacher-api"),
]
