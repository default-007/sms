from django.urls import include, path
from django.views.generic import TemplateView

from . import views

app_name = "assignments"

urlpatterns = [
    # Assignment Management URLs
    path("", views.AssignmentListView.as_view(), name="assignment_list"),
    path("create/", views.AssignmentCreateView.as_view(), name="assignment_create"),
    path("<int:pk>/", views.AssignmentDetailView.as_view(), name="assignment_detail"),
    path(
        "<int:pk>/edit/", views.AssignmentUpdateView.as_view(), name="assignment_edit"
    ),
    path(
        "<int:pk>/delete/",
        views.AssignmentDeleteView.as_view(),
        name="assignment_delete",
    ),
    path(
        "<int:pk>/publish/",
        views.AssignmentPublishView.as_view(),
        name="assignment_publish",
    ),
    path(
        "<int:pk>/close/", views.AssignmentCloseView.as_view(), name="assignment_close"
    ),
    path(
        "<int:pk>/duplicate/",
        views.AssignmentDuplicateView.as_view(),
        name="assignment_duplicate",
    ),
    # Assignment Analytics URLs
    path(
        "<int:pk>/analytics/",
        views.AssignmentAnalyticsView.as_view(),
        name="assignment_analytics",
    ),
    path(
        "<int:pk>/analytics/export/",
        views.AssignmentAnalyticsExportView.as_view(),
        name="assignment_analytics_export",
    ),
    # Submission Management URLs
    path(
        "<int:assignment_id>/submissions/",
        views.SubmissionListView.as_view(),
        name="submission_list",
    ),
    path(
        "<int:assignment_id>/submit/",
        views.SubmissionCreateView.as_view(),
        name="submission_create",
    ),
    path(
        "submissions/<int:pk>/",
        views.SubmissionDetailView.as_view(),
        name="submission_detail",
    ),
    path(
        "submissions/<int:pk>/edit/",
        views.SubmissionUpdateView.as_view(),
        name="submission_edit",
    ),
    path(
        "submissions/<int:pk>/delete/",
        views.SubmissionDeleteView.as_view(),
        name="submission_delete",
    ),
    path(
        "submissions/<int:pk>/download/",
        views.SubmissionDownloadView.as_view(),
        name="submission_download",
    ),
    # Grading URLs
    path(
        "submissions/<int:pk>/grade/",
        views.SubmissionGradeView.as_view(),
        name="submission_grade",
    ),
    path(
        "<int:assignment_id>/bulk-grade/",
        views.BulkGradeView.as_view(),
        name="bulk_grade",
    ),
    path("grading/", views.GradingDashboardView.as_view(), name="grading_dashboard"),
    path("grading/queue/", views.GradingQueueView.as_view(), name="grading_queue"),
    # Rubric Management URLs
    path(
        "<int:assignment_id>/rubric/",
        views.RubricManageView.as_view(),
        name="rubric_manage",
    ),
    path(
        "<int:assignment_id>/rubric/create/",
        views.RubricCreateView.as_view(),
        name="rubric_create",
    ),
    path(
        "rubrics/<int:pk>/edit/", views.RubricUpdateView.as_view(), name="rubric_edit"
    ),
    path(
        "rubrics/<int:pk>/delete/",
        views.RubricDeleteView.as_view(),
        name="rubric_delete",
    ),
    # Plagiarism Detection URLs
    path(
        "submissions/<int:pk>/plagiarism/",
        views.PlagiarismCheckView.as_view(),
        name="plagiarism_check",
    ),
    path(
        "<int:assignment_id>/plagiarism/batch/",
        views.BatchPlagiarismCheckView.as_view(),
        name="batch_plagiarism",
    ),
    path(
        "plagiarism/reports/",
        views.PlagiarismReportsView.as_view(),
        name="plagiarism_reports",
    ),
    # Comment and Discussion URLs
    path(
        "<int:assignment_id>/comments/",
        views.AssignmentCommentsView.as_view(),
        name="assignment_comments",
    ),
    path(
        "comments/<int:pk>/reply/",
        views.CommentReplyView.as_view(),
        name="comment_reply",
    ),
    path(
        "comments/<int:pk>/edit/", views.CommentEditView.as_view(), name="comment_edit"
    ),
    path(
        "comments/<int:pk>/delete/",
        views.CommentDeleteView.as_view(),
        name="comment_delete",
    ),
    # Dashboard and Analytics URLs
    path("dashboard/", views.AssignmentDashboardView.as_view(), name="dashboard"),
    path(
        "analytics/", views.AnalyticsDashboardView.as_view(), name="analytics_dashboard"
    ),
    path(
        "analytics/teacher/",
        views.TeacherAnalyticsView.as_view(),
        name="teacher_analytics",
    ),
    path(
        "analytics/student/",
        views.StudentAnalyticsView.as_view(),
        name="student_analytics",
    ),
    path(
        "analytics/class/<int:class_id>/",
        views.ClassAnalyticsView.as_view(),
        name="class_analytics",
    ),
    path(
        "analytics/system/",
        views.SystemAnalyticsView.as_view(),
        name="system_analytics",
    ),
    # Report Generation URLs
    path("reports/", views.ReportsView.as_view(), name="reports"),
    path(
        "reports/student/<int:student_id>/",
        views.StudentReportView.as_view(),
        name="student_report",
    ),
    path(
        "reports/teacher/<int:teacher_id>/",
        views.TeacherReportView.as_view(),
        name="teacher_report",
    ),
    path(
        "reports/class/<int:class_id>/",
        views.ClassReportView.as_view(),
        name="class_report",
    ),
    path("reports/export/", views.ReportExportView.as_view(), name="report_export"),
    # Deadline Management URLs
    path(
        "deadlines/", views.DeadlineManagementView.as_view(), name="deadline_management"
    ),
    path(
        "deadlines/upcoming/",
        views.UpcomingDeadlinesView.as_view(),
        name="upcoming_deadlines",
    ),
    path(
        "deadlines/overdue/",
        views.OverdueAssignmentsView.as_view(),
        name="overdue_assignments",
    ),
    path(
        "deadlines/reminders/",
        views.DeadlineRemindersView.as_view(),
        name="deadline_reminders",
    ),
    # Export and Import URLs
    path("export/", views.AssignmentExportView.as_view(), name="assignment_export"),
    path(
        "export/submissions/<int:assignment_id>/",
        views.SubmissionExportView.as_view(),
        name="submission_export",
    ),
    path("import/", views.AssignmentImportView.as_view(), name="assignment_import"),
    path(
        "import/submissions/",
        views.SubmissionImportView.as_view(),
        name="submission_import",
    ),
    # Calendar Integration URLs
    path(
        "calendar/", views.AssignmentCalendarView.as_view(), name="assignment_calendar"
    ),
    path(
        "calendar/feed/",
        views.AssignmentCalendarFeedView.as_view(),
        name="calendar_feed",
    ),
    # Search URLs
    path("search/", views.AssignmentSearchView.as_view(), name="assignment_search"),
    path(
        "search/advanced/", views.AdvancedSearchView.as_view(), name="advanced_search"
    ),
    # Bulk Operations URLs
    path("bulk/publish/", views.BulkPublishView.as_view(), name="bulk_publish"),
    path("bulk/close/", views.BulkCloseView.as_view(), name="bulk_close"),
    path("bulk/delete/", views.BulkDeleteView.as_view(), name="bulk_delete"),
    path(
        "bulk/extend-deadline/",
        views.BulkExtendDeadlineView.as_view(),
        name="bulk_extend_deadline",
    ),
    # Templates and Sharing URLs
    path(
        "templates/",
        views.AssignmentTemplatesView.as_view(),
        name="assignment_templates",
    ),
    path(
        "<int:pk>/save-template/",
        views.SaveAsTemplateView.as_view(),
        name="save_as_template",
    ),
    path(
        "templates/<int:template_id>/use/",
        views.UseTemplateView.as_view(),
        name="use_template",
    ),
    path(
        "<int:pk>/share/", views.ShareAssignmentView.as_view(), name="share_assignment"
    ),
    # Student Specific URLs
    path(
        "my-assignments/",
        views.StudentAssignmentListView.as_view(),
        name="student_assignments",
    ),
    path(
        "my-submissions/",
        views.StudentSubmissionListView.as_view(),
        name="student_submissions",
    ),
    path("my-grades/", views.StudentGradesView.as_view(), name="student_grades"),
    path(
        "my-performance/",
        views.StudentPerformanceView.as_view(),
        name="student_performance",
    ),
    # Parent Specific URLs
    path(
        "parent/overview/", views.ParentOverviewView.as_view(), name="parent_overview"
    ),
    path(
        "parent/child/<int:student_id>/",
        views.ParentChildAssignmentsView.as_view(),
        name="parent_child_assignments",
    ),
    # Notification URLs
    path(
        "notifications/",
        views.AssignmentNotificationsView.as_view(),
        name="notifications",
    ),
    path(
        "notifications/settings/",
        views.NotificationSettingsView.as_view(),
        name="notification_settings",
    ),
    # Settings and Configuration URLs
    path(
        "settings/", views.AssignmentSettingsView.as_view(), name="assignment_settings"
    ),
    path(
        "settings/file-types/",
        views.FileTypeSettingsView.as_view(),
        name="file_type_settings",
    ),
    path(
        "settings/grading/",
        views.GradingSettingsView.as_view(),
        name="grading_settings",
    ),
    # AJAX and Partial View URLs
    path(
        "ajax/assignment/<int:pk>/info/",
        views.AssignmentInfoAjaxView.as_view(),
        name="assignment_info_ajax",
    ),
    path(
        "ajax/submission/<int:pk>/status/",
        views.SubmissionStatusAjaxView.as_view(),
        name="submission_status_ajax",
    ),
    path(
        "ajax/class/<int:class_id>/students/",
        views.ClassStudentsAjaxView.as_view(),
        name="class_students_ajax",
    ),
    path(
        "ajax/subject/<int:subject_id>/assignments/",
        views.SubjectAssignmentsAjaxView.as_view(),
        name="subject_assignments_ajax",
    ),
    path(
        "ajax/analytics/chart-data/",
        views.AnalyticsChartDataAjaxView.as_view(),
        name="analytics_chart_ajax",
    ),
    # Help and Documentation URLs
    path(
        "help/",
        TemplateView.as_view(template_name="assignments/help/index.html"),
        name="help",
    ),
    path(
        "help/teacher/",
        TemplateView.as_view(template_name="assignments/help/teacher.html"),
        name="help_teacher",
    ),
    path(
        "help/student/",
        TemplateView.as_view(template_name="assignments/help/student.html"),
        name="help_student",
    ),
    path(
        "help/grading/",
        TemplateView.as_view(template_name="assignments/help/grading.html"),
        name="help_grading",
    ),
    # API URLs (namespace for API endpoints)
    path("api/", include("assignments.api.urls", namespace="api")),
]

"""
URL Pattern Structure and Organization:

1. Core Assignment Management:
   - CRUD operations for assignments
   - Publishing and lifecycle management
   - Duplication and templating

2. Submission Management:
   - Student submission interface
   - Teacher grading interface
   - File downloads and attachments

3. Analytics and Reporting:
   - Multiple levels of analytics (student, teacher, class, system)
   - Export capabilities
   - Performance tracking

4. Administrative Features:
   - Bulk operations
   - Settings and configuration
   - Import/export functionality

5. User-Specific Views:
   - Role-based interfaces (teacher, student, parent)
   - Personalized dashboards
   - Custom workflows

6. Advanced Features:
   - Plagiarism detection
   - Rubric management
   - Calendar integration
   - Search functionality

7. Communication:
   - Comments and discussions
   - Notifications
   - Sharing capabilities

8. Technical Endpoints:
   - AJAX endpoints for dynamic content
   - API integration
   - Partial view rendering

URL Naming Conventions:
- Kebab-case for multi-word URLs
- Resource-action pattern (e.g., assignment_create, submission_grade)
- Clear hierarchy for nested resources
- Consistent naming across similar operations

Permission Handling:
- All views implement proper permission checking
- Role-based access control
- Object-level permissions where appropriate
- Graceful handling of unauthorized access

Error Handling:
- Custom 404 pages for not found resources
- Permission denied handling
- Validation error display
- User-friendly error messages

Security Considerations:
- CSRF protection on all forms
- File upload validation
- SQL injection prevention
- XSS protection in templates

Mobile Responsiveness:
- All views support mobile access
- Touch-friendly interfaces
- Responsive layouts
- Optimized for various screen sizes

Performance Optimization:
- Efficient database queries
- Caching for frequently accessed data
- Pagination for large datasets
- Lazy loading where appropriate

Accessibility:
- ARIA labels and roles
- Keyboard navigation support
- Screen reader compatibility
- High contrast support

Integration Points:
- Communications module for notifications
- Students/Teachers modules for user data
- Academics module for class structure
- Reports module for document generation
"""
