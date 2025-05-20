from django.urls import path
from . import views

app_name = "teachers"

urlpatterns = [
    path("", views.TeacherListView.as_view(), name="teacher-list"),
    path("<int:pk>/", views.TeacherDetailView.as_view(), name="teacher-detail"),
    path("create/", views.TeacherCreateView.as_view(), name="teacher-create"),
    path("<int:pk>/update/", views.TeacherUpdateView.as_view(), name="teacher-update"),
    path("<int:pk>/delete/", views.TeacherDeleteView.as_view(), name="teacher-delete"),
    path(
        "<int:teacher_id>/assignment/create/",
        views.TeacherClassAssignmentCreateView.as_view(),
        name="teacher-assignment-create",
    ),
    path(
        "<int:teacher_id>/evaluation/create/",
        views.TeacherEvaluationCreateView.as_view(),
        name="teacher-evaluation-create",
    ),
    # New URLs for timetable
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
    # Dashboard
    path(
        "dashboard/",
        views.TeacherDashboardView.as_view(),
        name="teacher-dashboard",
    ),
    # Statistics
    path(
        "statistics/",
        views.TeacherStatisticsView.as_view(),
        name="teacher-statistics",
    ),
]
