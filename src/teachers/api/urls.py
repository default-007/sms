# src/teachers/api/urls.py
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

app_name = "teachers_api"

# URL patterns for teacher API endpoints
urlpatterns = [
    # Teacher CRUD endpoints
    path(
        "teachers/",
        views.TeacherListCreateAPIView.as_view(),
        name="teacher-list-create",
    ),
    path(
        "teachers/<int:pk>/",
        views.TeacherRetrieveUpdateDestroyAPIView.as_view(),
        name="teacher-detail",
    ),
    path("teachers/search/", views.teacher_search, name="teacher-search"),
    path(
        "teachers/bulk-assign/", views.bulk_assign_teachers, name="teacher-bulk-assign"
    ),
    # Teacher profile endpoints (for authenticated teacher users)
    path("profile/", views.teacher_profile, name="teacher-profile"),
    path(
        "profile/update/", views.update_teacher_profile, name="update-teacher-profile"
    ),
    # Teacher Class Assignment endpoints
    path(
        "assignments/",
        views.TeacherClassAssignmentListCreateAPIView.as_view(),
        name="assignment-list-create",
    ),
    path(
        "assignments/<int:pk>/",
        views.TeacherClassAssignmentDetailAPIView.as_view(),
        name="assignment-detail",
    ),
    path(
        "teachers/<int:teacher_id>/assignments/",
        views.TeacherClassAssignmentListCreateAPIView.as_view(),
        name="teacher-assignments",
    ),
    # Teacher Evaluation endpoints
    path(
        "evaluations/",
        views.TeacherEvaluationListCreateAPIView.as_view(),
        name="evaluation-list-create",
    ),
    path(
        "evaluations/<int:pk>/",
        views.TeacherEvaluationDetailAPIView.as_view(),
        name="evaluation-detail",
    ),
    path(
        "teachers/<int:teacher_id>/evaluations/",
        views.TeacherEvaluationListCreateAPIView.as_view(),
        name="teacher-evaluations",
    ),
    # Teacher Timetable endpoints
    path(
        "teachers/<int:teacher_id>/timetable/",
        views.teacher_timetable,
        name="teacher-timetable",
    ),
    # Analytics endpoints
    path(
        "analytics/overview/",
        views.teacher_analytics_overview,
        name="analytics-overview",
    ),
    path(
        "analytics/performance/<int:teacher_id>/",
        views.teacher_performance_analysis,
        name="teacher-performance-analysis",
    ),
    path(
        "analytics/workload/", views.teacher_workload_analysis, name="workload-analysis"
    ),
    path(
        "analytics/criteria/",
        views.evaluation_criteria_analysis,
        name="criteria-analysis",
    ),
    path(
        "analytics/dashboard/",
        views.teacher_dashboard_metrics,
        name="dashboard-metrics",
    ),
    path("analytics/trends/", views.evaluation_trends, name="evaluation-trends"),
    path(
        "analytics/correlation/",
        views.teacher_student_correlation,
        name="student-correlation",
    ),
    path("analytics/retention/", views.retention_analysis, name="retention-analysis"),
    path("analytics/hiring/", views.hiring_analysis, name="hiring-analysis"),
]
