from django.apps import AppConfig
from django.db.models.signals import post_save, post_delete
import logging

logger = logging.getLogger(__name__)


class AssignmentsConfig(AppConfig):
    """
    Django app configuration for the assignments module.

    This app manages the complete assignment lifecycle including:
    - Assignment creation and management
    - Student submissions and grading
    - Rubric-based assessment
    - Plagiarism detection
    - Analytics and reporting
    - Deadline management
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "src.assignments"
    verbose_name = "Assignment Management"

    def ready(self):
        """
        Called when Django starts up. Used to register signals and
        perform any necessary initialization.
        """
        try:
            # Import signals to register them
            from . import signals

            # Import models to ensure they're loaded
            from .models import Assignment, AssignmentSubmission

            # Log app initialization
            logger.info("Assignments app initialized successfully")

        except ImportError as e:
            logger.warning(f"Could not import assignments signals: {e}")
        except Exception as e:
            logger.error(f"Error initializing assignments app: {e}")

    def get_models(self):
        """
        Get all models in this app for management commands and utilities.
        """
        return [
            "Assignment",
            "AssignmentSubmission",
            "AssignmentRubric",
            "SubmissionGrade",
            "AssignmentComment",
        ]

    @property
    def permissions(self):
        """
        Define custom permissions for the assignments module.
        """
        return [
            ("view_all_assignments", "Can view all assignments"),
            ("manage_assignments", "Can create and manage assignments"),
            ("grade_submissions", "Can grade student submissions"),
            ("view_analytics", "Can view assignment analytics"),
            ("export_data", "Can export assignment data"),
            ("check_plagiarism", "Can run plagiarism checks"),
            ("send_notifications", "Can send assignment notifications"),
            ("manage_deadlines", "Can manage assignment deadlines"),
            ("view_overdue_reports", "Can view overdue assignment reports"),
            ("bulk_operations", "Can perform bulk operations on assignments"),
        ]

    @property
    def default_settings(self):
        """
        Default settings for the assignments module.
        """
        return {
            "ASSIGNMENTS_MAX_FILE_SIZE_MB": 50,
            "ASSIGNMENTS_ALLOWED_FILE_TYPES": "pdf,doc,docx,txt,jpg,jpeg,png",
            "ASSIGNMENTS_DEFAULT_LATE_PENALTY": 10,
            "ASSIGNMENTS_PLAGIARISM_THRESHOLD": 30,
            "ASSIGNMENTS_AUTO_GRADE_ENABLED": False,
            "ASSIGNMENTS_PEER_REVIEW_ENABLED": True,
            "ASSIGNMENTS_NOTIFICATION_DAYS_BEFORE": 2,
            "ASSIGNMENTS_BATCH_SIZE": 100,
            "ASSIGNMENTS_EXPORT_FORMAT": "csv",
            "ASSIGNMENTS_ANALYTICS_RETENTION_DAYS": 365,
        }

    def get_menu_items(self):
        """
        Return menu items for the assignments module.
        Used by the main navigation system.
        """
        return [
            {
                "name": "Assignments",
                "icon": "fas fa-tasks",
                "url": "assignments:assignment_list",
                "permission": "assignments.view_assignment",
                "children": [
                    {
                        "name": "All Assignments",
                        "url": "assignments:assignment_list",
                        "permission": "assignments.view_assignment",
                    },
                    {
                        "name": "Create Assignment",
                        "url": "assignments:assignment_create",
                        "permission": "assignments.add_assignment",
                    },
                    {
                        "name": "Submissions",
                        "url": "assignments:submission_list",
                        "permission": "assignments.view_assignmentsubmission",
                    },
                    {
                        "name": "Grading",
                        "url": "assignments:grading_dashboard",
                        "permission": "assignments.grade_submissions",
                    },
                    {
                        "name": "Analytics",
                        "url": "assignments:analytics_dashboard",
                        "permission": "assignments.view_analytics",
                    },
                    {
                        "name": "Overdue Assignments",
                        "url": "assignments:overdue_list",
                        "permission": "assignments.view_overdue_reports",
                    },
                ],
            }
        ]

    def get_dashboard_widgets(self, user):
        """
        Return dashboard widgets for different user types.
        """
        widgets = []

        if hasattr(user, "teacher"):
            widgets.extend(
                [
                    {
                        "title": "My Assignments",
                        "template": "assignments/widgets/teacher_assignments.html",
                        "context_processor": "assignments.context_processors.teacher_assignments",
                        "size": "col-md-6",
                        "order": 10,
                    },
                    {
                        "title": "Pending Grading",
                        "template": "assignments/widgets/pending_grading.html",
                        "context_processor": "assignments.context_processors.pending_grading",
                        "size": "col-md-6",
                        "order": 11,
                    },
                    {
                        "title": "Assignment Analytics",
                        "template": "assignments/widgets/assignment_analytics.html",
                        "context_processor": "assignments.context_processors.assignment_analytics",
                        "size": "col-md-12",
                        "order": 20,
                    },
                ]
            )

        elif hasattr(user, "student"):
            widgets.extend(
                [
                    {
                        "title": "My Assignments",
                        "template": "assignments/widgets/student_assignments.html",
                        "context_processor": "assignments.context_processors.student_assignments",
                        "size": "col-md-8",
                        "order": 10,
                    },
                    {
                        "title": "Upcoming Deadlines",
                        "template": "assignments/widgets/upcoming_deadlines.html",
                        "context_processor": "assignments.context_processors.upcoming_deadlines",
                        "size": "col-md-4",
                        "order": 11,
                    },
                    {
                        "title": "My Performance",
                        "template": "assignments/widgets/student_performance.html",
                        "context_processor": "assignments.context_processors.student_performance",
                        "size": "col-md-12",
                        "order": 20,
                    },
                ]
            )

        elif hasattr(user, "parent"):
            widgets.extend(
                [
                    {
                        "title": "Children's Assignments",
                        "template": "assignments/widgets/parent_assignments.html",
                        "context_processor": "assignments.context_processors.parent_assignments",
                        "size": "col-md-12",
                        "order": 15,
                    }
                ]
            )

        return widgets

    def get_notification_types(self):
        """
        Return notification types handled by this app.
        """
        return [
            {
                "type": "assignment_published",
                "name": "Assignment Published",
                "description": "New assignment has been published",
                "default_enabled": True,
                "channels": ["email", "in_app", "push"],
            },
            {
                "type": "assignment_due_soon",
                "name": "Assignment Due Soon",
                "description": "Assignment deadline approaching",
                "default_enabled": True,
                "channels": ["email", "in_app", "sms", "push"],
            },
            {
                "type": "assignment_overdue",
                "name": "Assignment Overdue",
                "description": "Assignment deadline has passed",
                "default_enabled": True,
                "channels": ["email", "in_app", "sms"],
            },
            {
                "type": "submission_graded",
                "name": "Submission Graded",
                "description": "Assignment has been graded",
                "default_enabled": True,
                "channels": ["email", "in_app", "push"],
            },
            {
                "type": "submission_received",
                "name": "Submission Received",
                "description": "Student submission received",
                "default_enabled": True,
                "channels": ["email", "in_app"],
            },
            {
                "type": "plagiarism_detected",
                "name": "Plagiarism Detected",
                "description": "High plagiarism score detected",
                "default_enabled": True,
                "channels": ["email", "in_app"],
            },
        ]

    def get_scheduled_tasks(self):
        """
        Return scheduled tasks for this app.
        """
        return [
            {
                "name": "send_deadline_reminders",
                "task": "assignments.tasks.send_deadline_reminders",
                "schedule": "cron(hour=8, minute=0)",  # Daily at 8 AM
                "description": "Send deadline reminder notifications",
            },
            {
                "name": "calculate_assignment_analytics",
                "task": "assignments.tasks.calculate_assignment_analytics",
                "schedule": "cron(hour=2, minute=0)",  # Daily at 2 AM
                "description": "Calculate and update assignment analytics",
            },
            {
                "name": "check_overdue_assignments",
                "task": "assignments.tasks.check_overdue_assignments",
                "schedule": "cron(hour=9, minute=0)",  # Daily at 9 AM
                "description": "Check and update overdue assignment status",
            },
            {
                "name": "cleanup_old_files",
                "task": "assignments.tasks.cleanup_old_files",
                "schedule": "cron(hour=3, minute=0, day_of_week=0)",  # Weekly on Sunday
                "description": "Clean up old assignment files",
            },
            {
                "name": "generate_weekly_reports",
                "task": "assignments.tasks.generate_weekly_reports",
                "schedule": "cron(hour=6, minute=0, day_of_week=1)",  # Monday at 6 AM
                "description": "Generate weekly assignment reports",
            },
        ]

    def get_export_formats(self):
        """
        Return supported export formats for this app.
        """
        return [
            {
                "format": "csv",
                "name": "CSV (Comma Separated Values)",
                "content_type": "text/csv",
                "extension": ".csv",
                "supports": ["assignments", "submissions", "grades"],
            },
            {
                "format": "excel",
                "name": "Excel Spreadsheet",
                "content_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "extension": ".xlsx",
                "supports": ["assignments", "submissions", "grades", "analytics"],
            },
            {
                "format": "pdf",
                "name": "PDF Report",
                "content_type": "application/pdf",
                "extension": ".pdf",
                "supports": ["assignments", "report_cards", "analytics"],
            },
        ]

    def get_api_documentation(self):
        """
        Return API documentation metadata for this app.
        """
        return {
            "title": "Assignments API",
            "description": "Complete assignment management system with submissions, grading, and analytics",
            "version": "1.0.0",
            "base_path": "/api/assignments/",
            "authentication": "JWT Token",
            "tags": [
                {
                    "name": "assignments",
                    "description": "Assignment management operations",
                },
                {"name": "submissions", "description": "Student submission operations"},
                {"name": "grading", "description": "Grading and rubric operations"},
                {
                    "name": "analytics",
                    "description": "Assignment analytics and reporting",
                },
            ],
        }
