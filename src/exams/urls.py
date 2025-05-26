"""
School Management System - Exam Main URLs
File: src/exams/urls.py
"""

from django.urls import path, include
from . import views

app_name = "exams"

urlpatterns = [
    # Dashboard
    path("", views.exam_dashboard, name="dashboard"),
    # Exam Management
    path("exams/", views.exam_list, name="exam_list"),
    path("exams/create/", views.create_exam, name="create_exam"),
    path("exams/<uuid:exam_id>/", views.exam_detail, name="exam_detail"),
    path(
        "exams/<uuid:exam_id>/schedules/", views.exam_schedules, name="exam_schedules"
    ),
    path(
        "exams/<uuid:exam_id>/schedules/create/",
        views.create_exam_schedule,
        name="create_exam_schedule",
    ),
    path(
        "exams/<uuid:exam_id>/analytics/",
        views.exam_analytics_view,
        name="exam_analytics",
    ),
    # Result Management
    path(
        "schedules/<uuid:schedule_id>/results/", views.result_entry, name="result_entry"
    ),
    path(
        "students/<uuid:student_id>/results/",
        views.student_results,
        name="student_results",
    ),
    path(
        "students/results/", views.student_results, name="my_results"
    ),  # For logged-in students
    # Report Cards
    path(
        "report-cards/<uuid:report_card_id>/",
        views.report_card_detail,
        name="report_card_detail",
    ),
    # Question Bank
    path("questions/", views.question_bank, name="question_bank"),
    path("questions/create/", views.create_question, name="create_question"),
    # AJAX Endpoints
    path("ajax/publish-exam/<uuid:exam_id>/", views.publish_exam, name="publish_exam"),
    path(
        "ajax/exam-statistics/<uuid:exam_id>/",
        views.get_exam_statistics,
        name="exam_statistics",
    ),
    # API Routes
    path("api/", include("exams.api.urls")),
]
