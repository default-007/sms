from django.urls import path, include
from . import views

app_name = "subjects"

urlpatterns = [
    # API endpoints
    path("api/", include("subjects.api.urls")),
    # Web interface URLs (can be implemented later)
    path("", views.SubjectListView.as_view(), name="subject-list"),
    path("create/", views.SubjectCreateView.as_view(), name="subject-create"),
    path("<int:pk>/", views.SubjectDetailView.as_view(), name="subject-detail"),
    path("<int:pk>/edit/", views.SubjectUpdateView.as_view(), name="subject-update"),
    path("<int:pk>/delete/", views.SubjectDeleteView.as_view(), name="subject-delete"),
    # Syllabus URLs
    path("syllabi/", views.SyllabusListView.as_view(), name="syllabus-list"),
    path("syllabi/create/", views.SyllabusCreateView.as_view(), name="syllabus-create"),
    path(
        "syllabi/<int:pk>/", views.SyllabusDetailView.as_view(), name="syllabus-detail"
    ),
    path(
        "syllabi/<int:pk>/edit/",
        views.SyllabusUpdateView.as_view(),
        name="syllabus-update",
    ),
    path(
        "syllabi/<int:pk>/delete/",
        views.SyllabusDeleteView.as_view(),
        name="syllabus-delete",
    ),
    # Progress tracking URLs
    path(
        "syllabi/<int:syllabus_id>/progress/",
        views.SyllabusProgressView.as_view(),
        name="syllabus-progress",
    ),
    path(
        "syllabi/<int:syllabus_id>/topics/<int:topic_index>/complete/",
        views.MarkTopicCompleteView.as_view(),
        name="mark-topic-complete",
    ),
    # Assignment URLs
    path(
        "assignments/",
        views.SubjectAssignmentListView.as_view(),
        name="assignment-list",
    ),
    path(
        "assignments/create/",
        views.SubjectAssignmentCreateView.as_view(),
        name="assignment-create",
    ),
    path(
        "assignments/<int:pk>/",
        views.SubjectAssignmentDetailView.as_view(),
        name="assignment-detail",
    ),
    path(
        "assignments/<int:pk>/edit/",
        views.SubjectAssignmentUpdateView.as_view(),
        name="assignment-update",
    ),
    # Analytics and Reports URLs
    path(
        "analytics/",
        views.CurriculumAnalyticsView.as_view(),
        name="curriculum-analytics",
    ),
    path(
        "reports/curriculum/",
        views.CurriculumReportView.as_view(),
        name="curriculum-report",
    ),
    path(
        "reports/teacher-workload/",
        views.TeacherWorkloadReportView.as_view(),
        name="teacher-workload-report",
    ),
    path(
        "reports/grade-overview/<int:grade_id>/",
        views.GradeOverviewView.as_view(),
        name="grade-overview",
    ),
    # Bulk operations URLs
    path(
        "bulk/import-subjects/",
        views.BulkImportSubjectsView.as_view(),
        name="bulk-import-subjects",
    ),
    path(
        "bulk/create-syllabi/<int:term_id>/",
        views.BulkCreateSyllabiView.as_view(),
        name="bulk-create-syllabi",
    ),
    # Dashboard and overview URLs
    path("dashboard/", views.SubjectsDashboardView.as_view(), name="dashboard"),
    path(
        "curriculum-structure/",
        views.CurriculumStructureView.as_view(),
        name="curriculum-structure",
    ),
]
