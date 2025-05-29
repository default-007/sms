from django.urls import include, path

from . import views

app_name = "scheduling"

urlpatterns = [
    # API URLs - delegated to api/urls.py
    path("api/", include("src.scheduling.api.urls")),
    # Dashboard and main views
    path("", views.SchedulingDashboardView.as_view(), name="dashboard"),
    # Timetable management
    path("timetables/", views.TimetableListView.as_view(), name="timetable_list"),
    path(
        "timetables/create/",
        views.TimetableCreateView.as_view(),
        name="timetable_create",
    ),
    path(
        "timetables/<uuid:pk>/",
        views.TimetableDetailView.as_view(),
        name="timetable_detail",
    ),
    path(
        "timetables/<uuid:pk>/edit/",
        views.TimetableUpdateView.as_view(),
        name="timetable_edit",
    ),
    path(
        "timetables/<uuid:pk>/delete/",
        views.TimetableDeleteView.as_view(),
        name="timetable_delete",
    ),
    path(
        "timetables/bulk-create/",
        views.BulkTimetableCreateView.as_view(),
        name="bulk_timetable_create",
    ),
    # path("timetables/copy/", views.CopyTimetableView.as_view(), name="copy_timetable"),
    # Class and teacher timetable views
    path(
        "timetables/class/<uuid:class_id>/",
        views.ClassTimetableView.as_view(),
        name="class_timetable",
    ),
    path(
        "timetables/teacher/<uuid:teacher_id>/",
        views.TeacherTimetableView.as_view(),
        name="teacher_timetable",
    ),
    path(
        "timetables/grade/<uuid:grade_id>/",
        views.GradeTimetableView.as_view(),
        name="grade_timetable",
    ),
    # Time slot management
    path("time-slots/", views.TimeSlotListView.as_view(), name="timeslot_list"),
    path(
        "time-slots/create/", views.TimeSlotCreateView.as_view(), name="timeslot_create"
    ),
    path(
        "time-slots/<uuid:pk>/",
        views.TimeSlotDetailView.as_view(),
        name="timeslot_detail",
    ),
    path(
        "time-slots/<uuid:pk>/edit/",
        views.TimeSlotUpdateView.as_view(),
        name="timeslot_edit",
    ),
    path(
        "time-slots/<uuid:pk>/delete/",
        views.TimeSlotDeleteView.as_view(),
        name="timeslot_delete",
    ),
    path(
        "time-slots/bulk-create/",
        views.BulkTimeSlotCreateView.as_view(),
        name="bulk_timeslot_create",
    ),
    # Room management
    path("rooms/", views.RoomListView.as_view(), name="room_list"),
    path("rooms/create/", views.RoomCreateView.as_view(), name="room_create"),
    path("rooms/<uuid:pk>/", views.RoomDetailView.as_view(), name="room_detail"),
    path("rooms/<uuid:pk>/edit/", views.RoomUpdateView.as_view(), name="room_edit"),
    path("rooms/<uuid:pk>/delete/", views.RoomDeleteView.as_view(), name="room_delete"),
    path(
        "rooms/<uuid:pk>/utilization/",
        views.RoomUtilizationView.as_view(),
        name="room_utilization",
    ),
    path(
        "rooms/<uuid:pk>/calendar/",
        views.RoomCalendarView.as_view(),
        name="room_calendar",
    ),
    # Substitute teacher management
    path(
        "substitutes/",
        views.SubstituteTeacherListView.as_view(),
        name="substitute_list",
    ),
    path(
        "substitutes/create/",
        views.SubstituteTeacherCreateView.as_view(),
        name="substitute_create",
    ),
    path(
        "substitutes/<uuid:pk>/",
        views.SubstituteTeacherDetailView.as_view(),
        name="substitute_detail",
    ),
    path(
        "substitutes/<uuid:pk>/edit/",
        views.SubstituteTeacherUpdateView.as_view(),
        name="substitute_edit",
    ),
    path(
        "substitutes/<uuid:pk>/delete/",
        views.SubstituteTeacherDeleteView.as_view(),
        name="substitute_delete",
    ),
    path(
        "substitutes/<uuid:pk>/approve/",
        views.ApproveSubstituteView.as_view(),
        name="approve_substitute",
    ),
    path(
        "substitutes/suggestions/",
        views.SubstituteSuggestionsView.as_view(),
        name="substitute_suggestions",
    ),
    # Timetable generation and optimization
    path(
        "generate/",
        views.TimetableGenerationView.as_view(),
        name="timetable_generation",
    ),
    path(
        "generate/history/",
        views.GenerationHistoryView.as_view(),
        name="generation_history",
    ),
    path(
        "generate/<uuid:pk>/",
        views.GenerationDetailView.as_view(),
        name="generation_detail",
    ),
    path("optimize/", views.OptimizationView.as_view(), name="optimization"),
    # Templates
    path("templates/", views.TimetableTemplateListView.as_view(), name="template_list"),
    path(
        "templates/create/",
        views.TimetableTemplateCreateView.as_view(),
        name="template_create",
    ),
    path(
        "templates/<uuid:pk>/",
        views.TimetableTemplateDetailView.as_view(),
        name="template_detail",
    ),
    path(
        "templates/<uuid:pk>/edit/",
        views.TimetableTemplateUpdateView.as_view(),
        name="template_edit",
    ),
    path(
        "templates/<uuid:pk>/delete/",
        views.TimetableTemplateDeleteView.as_view(),
        name="template_delete",
    ),
    path(
        "templates/<uuid:pk>/apply/",
        views.ApplyTemplateView.as_view(),
        name="apply_template",
    ),
    # Constraints
    path(
        "constraints/",
        views.SchedulingConstraintListView.as_view(),
        name="constraint_list",
    ),
    path(
        "constraints/create/",
        views.SchedulingConstraintCreateView.as_view(),
        name="constraint_create",
    ),
    path(
        "constraints/<uuid:pk>/",
        views.SchedulingConstraintDetailView.as_view(),
        name="constraint_detail",
    ),
    path(
        "constraints/<uuid:pk>/edit/",
        views.SchedulingConstraintUpdateView.as_view(),
        name="constraint_edit",
    ),
    path(
        "constraints/<uuid:pk>/delete/",
        views.SchedulingConstraintDeleteView.as_view(),
        name="constraint_delete",
    ),
    # Analytics and reporting
    path("analytics/", views.SchedulingAnalyticsView.as_view(), name="analytics"),
    path(
        "analytics/teacher-workload/",
        views.TeacherWorkloadAnalyticsView.as_view(),
        name="teacher_workload_analytics",
    ),
    path(
        "analytics/room-utilization/",
        views.RoomUtilizationAnalyticsView.as_view(),
        name="room_utilization_analytics",
    ),
    path(
        "analytics/conflicts/",
        views.ConflictAnalyticsView.as_view(),
        name="conflict_analytics",
    ),
    path(
        "analytics/optimization-score/",
        views.OptimizationScoreView.as_view(),
        name="optimization_score",
    ),
    path(
        "analytics/subject-distribution/",
        views.SubjectDistributionView.as_view(),
        name="subject_distribution",
    ),
    # Reports
    path("reports/", views.SchedulingReportsView.as_view(), name="reports"),
    path(
        "reports/timetable/",
        views.TimetableReportView.as_view(),
        name="timetable_report",
    ),
    path(
        "reports/teacher-schedule/",
        views.TeacherScheduleReportView.as_view(),
        name="teacher_schedule_report",
    ),
    path(
        "reports/room-usage/",
        views.RoomUsageReportView.as_view(),
        name="room_usage_report",
    ),
    path(
        "reports/conflicts/", views.ConflictReportView.as_view(), name="conflict_report"
    ),
    # Export functions
    path(
        "export/timetable/<uuid:class_id>/",
        views.ExportClassTimetableView.as_view(),
        name="export_class_timetable",
    ),
    path(
        "export/teacher/<uuid:teacher_id>/",
        views.ExportTeacherScheduleView.as_view(),
        name="export_teacher_schedule",
    ),
    path(
        "export/room-utilization/",
        views.ExportRoomUtilizationView.as_view(),
        name="export_room_utilization",
    ),
    path(
        "export/master-timetable/",
        views.ExportMasterTimetableView.as_view(),
        name="export_master_timetable",
    ),
    # AJAX endpoints for dynamic loading
    path(
        "ajax/available-teachers/",
        views.AvailableTeachersAjaxView.as_view(),
        name="ajax_available_teachers",
    ),
    path(
        "ajax/available-rooms/",
        views.AvailableRoomsAjaxView.as_view(),
        name="ajax_available_rooms",
    ),
    path(
        "ajax/check-conflicts/",
        views.CheckConflictsAjaxView.as_view(),
        name="ajax_check_conflicts",
    ),
    path(
        "ajax/teacher-subjects/",
        views.TeacherSubjectsAjaxView.as_view(),
        name="ajax_teacher_subjects",
    ),
    path(
        "ajax/class-students/",
        views.ClassStudentsAjaxView.as_view(),
        name="ajax_class_students",
    ),
    # Utility views
    path(
        "conflicts/", views.ConflictManagementView.as_view(), name="conflict_management"
    ),
    path("settings/", views.SchedulingSettingsView.as_view(), name="settings"),
    path("help/", views.SchedulingHelpView.as_view(), name="help"),
]
