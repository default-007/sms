from django.urls import path
from . import views

app_name = "exams"

urlpatterns = [
    # Exam Type URLs
    path("exam-types/", views.ExamTypeListView.as_view(), name="exam-type-list"),
    path(
        "exam-types/create/",
        views.ExamTypeCreateView.as_view(),
        name="exam-type-create",
    ),
    path(
        "exam-types/<int:pk>/",
        views.ExamTypeDetailView.as_view(),
        name="exam-type-detail",
    ),
    path(
        "exam-types/<int:pk>/update/",
        views.ExamTypeUpdateView.as_view(),
        name="exam-type-update",
    ),
    path(
        "exam-types/<int:pk>/delete/",
        views.ExamTypeDeleteView.as_view(),
        name="exam-type-delete",
    ),
    # Exam URLs
    path("", views.ExamListView.as_view(), name="exam-list"),
    path("create/", views.ExamCreateView.as_view(), name="exam-create"),
    path("<int:pk>/", views.ExamDetailView.as_view(), name="exam-detail"),
    path("<int:pk>/update/", views.ExamUpdateView.as_view(), name="exam-update"),
    path("<int:pk>/delete/", views.ExamDeleteView.as_view(), name="exam-delete"),
    path(
        "<int:pk>/update-status/",
        views.ExamUpdateStatusView.as_view(),
        name="exam-update-status",
    ),
    # Exam Schedule URLs
    path(
        "<int:exam_id>/schedule/create/",
        views.ExamScheduleCreateView.as_view(),
        name="schedule-create",
    ),
    path(
        "schedule/<int:pk>/",
        views.ExamScheduleDetailView.as_view(),
        name="schedule-detail",
    ),
    path(
        "schedule/<int:pk>/update/",
        views.ExamScheduleUpdateView.as_view(),
        name="schedule-update",
    ),
    path(
        "schedule/<int:pk>/delete/",
        views.ExamScheduleDeleteView.as_view(),
        name="schedule-delete",
    ),
    # Results URLs
    path(
        "schedule/<int:schedule_id>/results/",
        views.ResultListView.as_view(),
        name="result-list",
    ),
    path(
        "schedule/<int:schedule_id>/results/enter/",
        views.BulkResultEntryView.as_view(),
        name="bulk-result-entry",
    ),
    path("results/<int:pk>/", views.ResultDetailView.as_view(), name="result-detail"),
    path(
        "results/<int:pk>/update/",
        views.ResultUpdateView.as_view(),
        name="result-update",
    ),
    # Quiz URLs
    path("quizzes/", views.QuizListView.as_view(), name="quiz-list"),
    path("quizzes/create/", views.QuizCreateView.as_view(), name="quiz-create"),
    path("quizzes/<int:pk>/", views.QuizDetailView.as_view(), name="quiz-detail"),
    path(
        "quizzes/<int:pk>/update/", views.QuizUpdateView.as_view(), name="quiz-update"
    ),
    path(
        "quizzes/<int:pk>/delete/", views.QuizDeleteView.as_view(), name="quiz-delete"
    ),
    path(
        "quizzes/<int:pk>/update-status/",
        views.QuizUpdateStatusView.as_view(),
        name="quiz-update-status",
    ),
    # Question URLs
    path(
        "quizzes/<int:quiz_id>/questions/create/",
        views.QuestionCreateView.as_view(),
        name="question-create",
    ),
    path(
        "questions/<int:pk>/",
        views.QuestionDetailView.as_view(),
        name="question-detail",
    ),
    path(
        "questions/<int:pk>/update/",
        views.QuestionUpdateView.as_view(),
        name="question-update",
    ),
    path(
        "questions/<int:pk>/delete/",
        views.QuestionDeleteView.as_view(),
        name="question-delete",
    ),
    # Quiz Attempt URLs
    path(
        "quizzes/<int:quiz_id>/attempt/",
        views.QuizAttemptView.as_view(),
        name="quiz-attempt",
    ),
    path(
        "attempts/<int:pk>/",
        views.QuizAttemptDetailView.as_view(),
        name="attempt-detail",
    ),
    path(
        "attempts/<int:pk>/question/<int:question_id>/",
        views.QuizQuestionView.as_view(),
        name="attempt-question",
    ),
    path(
        "attempts/<int:pk>/complete/",
        views.QuizAttemptCompleteView.as_view(),
        name="attempt-complete",
    ),
    # Grading System URLs
    path(
        "grading-systems/",
        views.GradingSystemListView.as_view(),
        name="grading-system-list",
    ),
    path(
        "grading-systems/create/",
        views.GradingSystemCreateView.as_view(),
        name="grading-system-create",
    ),
    path(
        "grading-systems/<int:pk>/",
        views.GradingSystemDetailView.as_view(),
        name="grading-system-detail",
    ),
    path(
        "grading-systems/<int:pk>/update/",
        views.GradingSystemUpdateView.as_view(),
        name="grading-system-update",
    ),
    path(
        "grading-systems/<int:pk>/delete/",
        views.GradingSystemDeleteView.as_view(),
        name="grading-system-delete",
    ),
    # Report Card URLs
    path("report-cards/", views.ReportCardListView.as_view(), name="report-card-list"),
    path(
        "report-cards/generate/",
        views.ReportCardGenerateView.as_view(),
        name="report-card-generate",
    ),
    path(
        "report-cards/<int:pk>/",
        views.ReportCardDetailView.as_view(),
        name="report-card-detail",
    ),
    path(
        "report-cards/<int:pk>/update/",
        views.ReportCardUpdateView.as_view(),
        name="report-card-update",
    ),
    path(
        "report-cards/<int:pk>/publish/",
        views.ReportCardPublishView.as_view(),
        name="report-card-publish",
    ),
    path(
        "report-cards/<int:pk>/print/",
        views.ReportCardPrintView.as_view(),
        name="report-card-print",
    ),
    # Student portal views
    path(
        "student/exams/", views.StudentExamListView.as_view(), name="student-exam-list"
    ),
    path(
        "student/results/",
        views.StudentResultListView.as_view(),
        name="student-result-list",
    ),
    path(
        "student/quizzes/",
        views.StudentQuizListView.as_view(),
        name="student-quiz-list",
    ),
    path(
        "student/report-cards/",
        views.StudentReportCardListView.as_view(),
        name="student-report-card-list",
    ),
]
