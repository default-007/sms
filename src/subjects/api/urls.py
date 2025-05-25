from django.urls import path, include
from . import views

app_name = "subjects_api"

urlpatterns = [
    # Subject endpoints
    path(
        "subjects/",
        views.SubjectListCreateAPIView.as_view(),
        name="subject-list-create",
    ),
    path(
        "subjects/<int:pk>/",
        views.SubjectDetailAPIView.as_view(),
        name="subject-detail",
    ),
    path(
        "subjects/bulk-create/", views.bulk_create_subjects, name="subject-bulk-create"
    ),
    path(
        "subjects/by-grade/<int:grade_id>/",
        views.subjects_by_grade,
        name="subjects-by-grade",
    ),
    # Syllabus endpoints
    path(
        "syllabi/",
        views.SyllabusListCreateAPIView.as_view(),
        name="syllabus-list-create",
    ),
    path(
        "syllabi/<int:pk>/",
        views.SyllabusDetailAPIView.as_view(),
        name="syllabus-detail",
    ),
    path(
        "syllabi/<int:syllabus_id>/progress/",
        views.syllabus_progress,
        name="syllabus-progress",
    ),
    path(
        "syllabi/<int:syllabus_id>/mark-topic-completed/",
        views.mark_topic_completed,
        name="mark-topic-completed",
    ),
    path(
        "syllabi/bulk-create/<int:term_id>/",
        views.bulk_create_syllabi,
        name="syllabus-bulk-create",
    ),
    # Topic Progress endpoints
    path(
        "topic-progress/",
        views.TopicProgressListCreateAPIView.as_view(),
        name="topic-progress-list-create",
    ),
    path(
        "topic-progress/<int:pk>/",
        views.TopicProgressDetailAPIView.as_view(),
        name="topic-progress-detail",
    ),
    # Subject Assignment endpoints
    path(
        "assignments/",
        views.SubjectAssignmentListCreateAPIView.as_view(),
        name="assignment-list-create",
    ),
    path(
        "assignments/<int:pk>/",
        views.SubjectAssignmentDetailAPIView.as_view(),
        name="assignment-detail",
    ),
    # Analytics and Overview endpoints
    path(
        "curriculum/analytics/", views.curriculum_analytics, name="curriculum-analytics"
    ),
    path(
        "curriculum/structure/", views.curriculum_structure, name="curriculum-structure"
    ),
    path(
        "grades/<int:grade_id>/overview/",
        views.grade_syllabus_overview,
        name="grade-syllabus-overview",
    ),
    # Teacher-related endpoints
    path(
        "teachers/<int:teacher_id>/assignments/",
        views.teacher_assignments,
        name="teacher-assignments",
    ),
    path(
        "teachers/<int:teacher_id>/workload/",
        views.teacher_workload,
        name="teacher-workload",
    ),
]
