"""
School Management System - Exam URL Configurations
File: src/exams/api/urls.py
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    ExamQuestionViewSet,
    ExamScheduleViewSet,
    ExamTypeViewSet,
    ExamViewSet,
    GradingSystemViewSet,
    OnlineExamViewSet,
    ReportCardViewSet,
    StudentExamResultViewSet,
    StudentOnlineExamAttemptViewSet,
)

# Create router and register viewsets
router = DefaultRouter()
router.register(r"exam-types", ExamTypeViewSet, basename="examtype")
router.register(r"exams", ExamViewSet, basename="exam")
router.register(r"exam-schedules", ExamScheduleViewSet, basename="examschedule")
router.register(r"results", StudentExamResultViewSet, basename="studentexamresult")
router.register(r"report-cards", ReportCardViewSet, basename="reportcard")
router.register(r"grading-systems", GradingSystemViewSet, basename="gradingsystem")
router.register(r"questions", ExamQuestionViewSet, basename="examquestion")
router.register(r"online-exams", OnlineExamViewSet, basename="onlineexam")
router.register(
    r"online-attempts", StudentOnlineExamAttemptViewSet, basename="onlineexamattempt"
)

app_name = "exams"

urlpatterns = [
    path("", include(router.urls)),
]

"""
URL Patterns for Exams API:

Exam Types:
- GET /api/exams/exam-types/ - List exam types
- POST /api/exams/exam-types/ - Create exam type
- GET /api/exams/exam-types/{id}/ - Get exam type details
- PUT/PATCH /api/exams/exam-types/{id}/ - Update exam type
- DELETE /api/exams/exam-types/{id}/ - Delete exam type

Exams:
- GET /api/exams/exams/ - List exams
- POST /api/exams/exams/ - Create exam
- GET /api/exams/exams/{id}/ - Get exam details
- PUT/PATCH /api/exams/exams/{id}/ - Update exam
- DELETE /api/exams/exams/{id}/ - Delete exam
- POST /api/exams/exams/{id}/publish/ - Publish exam
- GET /api/exams/exams/{id}/analytics/ - Get exam analytics
- POST /api/exams/exams/{id}/bulk_schedule/ - Bulk create schedules
- GET /api/exams/exams/{id}/report_cards/ - Get exam report cards

Exam Schedules:
- GET /api/exams/exam-schedules/ - List exam schedules
- POST /api/exams/exam-schedules/ - Create exam schedule
- GET /api/exams/exam-schedules/{id}/ - Get schedule details
- PUT/PATCH /api/exams/exam-schedules/{id}/ - Update schedule
- DELETE /api/exams/exam-schedules/{id}/ - Delete schedule
- POST /api/exams/exam-schedules/{id}/mark_completed/ - Mark as completed
- GET /api/exams/exam-schedules/{id}/student_list/ - Get student list
- POST /api/exams/exam-schedules/{id}/bulk_results/ - Bulk enter results
- GET /api/exams/exam-schedules/{id}/results/ - Get all results

Results:
- GET /api/exams/results/ - List all results
- POST /api/exams/results/ - Create result
- GET /api/exams/results/{id}/ - Get result details
- PUT/PATCH /api/exams/results/{id}/ - Update result
- DELETE /api/exams/results/{id}/ - Delete result
- GET /api/exams/results/student_performance/ - Get student performance

Report Cards:
- GET /api/exams/report-cards/ - List report cards
- POST /api/exams/report-cards/ - Create report card
- GET /api/exams/report-cards/{id}/ - Get report card details
- PUT/PATCH /api/exams/report-cards/{id}/ - Update report card
- POST /api/exams/report-cards/generate_bulk/ - Generate bulk report cards
- POST /api/exams/report-cards/{id}/publish/ - Publish report card

Grading Systems:
- GET /api/exams/grading-systems/ - List grading systems
- POST /api/exams/grading-systems/ - Create grading system
- GET /api/exams/grading-systems/{id}/ - Get grading system details
- PUT/PATCH /api/exams/grading-systems/{id}/ - Update grading system

Questions:
- GET /api/exams/questions/ - List questions
- POST /api/exams/questions/ - Create question
- GET /api/exams/questions/{id}/ - Get question details
- PUT/PATCH /api/exams/questions/{id}/ - Update question
- DELETE /api/exams/questions/{id}/ - Delete question
- POST /api/exams/questions/filter_questions/ - Advanced filtering
- GET /api/exams/questions/statistics/ - Question bank statistics

Online Exams:
- GET /api/exams/online-exams/ - List online exams
- POST /api/exams/online-exams/ - Create online exam
- GET /api/exams/online-exams/{id}/ - Get online exam details
- PUT/PATCH /api/exams/online-exams/{id}/ - Update online exam
- POST /api/exams/online-exams/{id}/add_questions/ - Add questions
- POST /api/exams/online-exams/{id}/auto_select_questions/ - Auto-select questions
- GET /api/exams/online-exams/{id}/attempts/ - Get all attempts

Online Attempts:
- GET /api/exams/online-attempts/ - List attempts
- POST /api/exams/online-attempts/ - Create attempt
- GET /api/exams/online-attempts/{id}/ - Get attempt details
- POST /api/exams/online-attempts/{id}/submit/ - Submit attempt
- POST /api/exams/online-attempts/{id}/grade/ - Grade attempt
"""
