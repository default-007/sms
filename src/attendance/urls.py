from django.urls import path

from . import views

app_name = "attendance"

urlpatterns = [
    # Dashboard
    path("dashboard/", views.attendance_dashboard_view, name="dashboard"),
    # Attendance record management
    path("records/", views.AttendanceRecordListView.as_view(), name="record-list"),
    path(
        "records/<int:pk>/",
        views.AttendanceRecordDetailView.as_view(),
        name="record-detail",
    ),
    path("mark/", views.mark_attendance_view, name="mark-attendance"),
    path(
        "mark/<int:class_id>/", views.mark_attendance_view, name="mark-class-attendance"
    ),
    # Attendance reports
    path(
        "student/<int:student_id>/",
        views.student_attendance_report_view,
        name="student-report",
    ),
    path(
        "class/<int:class_id>/", views.class_attendance_report_view, name="class-report"
    ),
]
