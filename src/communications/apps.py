"""
Django app configuration for Communications module.
Handles app initialization, signal registration, and ready() setup.
"""

from django.apps import AppConfig
from django.db.models.signals import post_save, post_delete
import logging

logger = logging.getLogger(__name__)


class CommunicationsConfig(AppConfig):
    """Configuration for the Communications app"""

    default_auto_field = "django.db.models.BigAutoField"
    name = "src.communications"
    verbose_name = "Communications"

    def ready(self):
        """
        Initialize the app when Django starts.
        Register signals and perform any setup tasks.
        """
        try:
            # Import signals to register them
            from . import signals

            # Import models to ensure they're loaded
            from .models import (
                Announcement,
                Notification,
                BulkMessage,
                CommunicationAnalytics,
                CommunicationLog,
            )

            # Log successful initialization
            logger.info("Communications app initialized successfully")

            # Register any additional signal handlers
            self._register_signal_handlers()

            # Initialize communication channels if needed
            self._initialize_communication_channels()

        except Exception as e:
            logger.error(f"Error initializing Communications app: {str(e)}")
            raise

    def _register_signal_handlers(self):
        """Register additional signal handlers"""

        from django.contrib.auth import get_user_model
        from .signals import (
            create_user_communication_preferences,
            update_announcement_metrics_on_notification_read,
        )

        User = get_user_model()

        # Connect signals
        post_save.connect(
            create_user_communication_preferences,
            sender=User,
            dispatch_uid="create_user_communication_preferences",
        )

        # Register other signals as needed
        logger.info("Communication signal handlers registered")

    def _initialize_communication_channels(self):
        """Initialize communication channels and default templates"""

        try:
            from .models import MessageTemplate, CommunicationChannel
            from django.contrib.auth import get_user_model

            # Create default message templates if they don't exist
            self._create_default_templates()

            logger.info("Communication channels initialized")

        except Exception as e:
            logger.warning(f"Could not initialize communication channels: {str(e)}")

    def _create_default_templates(self):
        """Create default message templates"""

        from .models import MessageTemplate
        from django.contrib.auth import get_user_model

        User = get_user_model()

        # Get system user (or create one)
        try:
            system_user = User.objects.filter(username="system").first()
            if not system_user:
                # Skip template creation if no system user exists
                return
        except Exception:
            return

        default_templates = [
            {
                "name": "Fee Reminder",
                "description": "Template for fee payment reminders",
                "template_type": "financial",
                "subject_template": "Fee Payment Reminder - {{ student_name }}",
                "content_template": """
Dear {{ parent_name }},

This is a reminder that the fee payment for {{ student_name }} (Class: {{ class_name }}) 
is due on {{ due_date }}.

Amount Due: {{ amount }}
Payment Methods: {{ payment_methods }}

Please ensure payment is made by the due date to avoid late fees.

Thank you,
{{ school_name }} Administration
                """.strip(),
                "supported_channels": ["email", "sms"],
                "variables": {
                    "student_name": "Student full name",
                    "parent_name": "Parent full name",
                    "class_name": "Student class",
                    "due_date": "Fee due date",
                    "amount": "Amount due",
                    "payment_methods": "Available payment methods",
                    "school_name": "School name",
                },
            },
            {
                "name": "Attendance Alert",
                "description": "Template for attendance notifications",
                "template_type": "academic",
                "subject_template": "Attendance Alert - {{ student_name }}",
                "content_template": """
Dear {{ parent_name }},

We would like to inform you that {{ student_name }} was marked {{ status }} 
today ({{ date }}) for {{ subject }}.

If this is unexpected, please contact the school office.

Best regards,
{{ school_name }}
                """.strip(),
                "supported_channels": ["email", "sms", "push"],
                "variables": {
                    "student_name": "Student full name",
                    "parent_name": "Parent full name",
                    "status": "Attendance status",
                    "date": "Date",
                    "subject": "Subject name",
                    "school_name": "School name",
                },
            },
            {
                "name": "Exam Notification",
                "description": "Template for exam announcements",
                "template_type": "academic",
                "subject_template": "Exam Schedule - {{ exam_name }}",
                "content_template": """
Dear {{ recipient_name }},

This is to inform you about the upcoming {{ exam_name }} scheduled for {{ exam_date }}.

Exam Details:
- Subject: {{ subject }}
- Date: {{ exam_date }}
- Time: {{ exam_time }}
- Venue: {{ venue }}
- Duration: {{ duration }}

Please ensure students arrive 15 minutes before the exam time.

Best wishes,
{{ school_name }} Examination Department
                """.strip(),
                "supported_channels": ["email", "in_app"],
                "variables": {
                    "recipient_name": "Recipient name",
                    "exam_name": "Exam name",
                    "exam_date": "Exam date",
                    "exam_time": "Exam time",
                    "subject": "Subject name",
                    "venue": "Exam venue",
                    "duration": "Exam duration",
                    "school_name": "School name",
                },
            },
            {
                "name": "General Announcement",
                "description": "Template for general school announcements",
                "template_type": "general",
                "subject_template": "{{ announcement_title }}",
                "content_template": """
Dear {{ recipient_name }},

{{ announcement_content }}

For more information, please contact the school office.

Regards,
{{ school_name }}
                """.strip(),
                "supported_channels": ["email", "sms", "push", "in_app"],
                "variables": {
                    "recipient_name": "Recipient name",
                    "announcement_title": "Announcement title",
                    "announcement_content": "Announcement content",
                    "school_name": "School name",
                },
            },
            {
                "name": "Welcome Message",
                "description": "Template for welcoming new users",
                "template_type": "system",
                "subject_template": "Welcome to {{ school_name }}",
                "content_template": """
Dear {{ user_name }},

Welcome to {{ school_name }}! Your account has been successfully created.

Your login details:
- Username: {{ username }}
- Role: {{ user_role }}

Please log in to the system to complete your profile and explore the available features.

If you need any assistance, please contact our support team.

Best regards,
{{ school_name }} IT Department
                """.strip(),
                "supported_channels": ["email"],
                "variables": {
                    "user_name": "User full name",
                    "username": "Username",
                    "user_role": "User role",
                    "school_name": "School name",
                },
            },
        ]

        for template_data in default_templates:
            template, created = MessageTemplate.objects.get_or_create(
                name=template_data["name"],
                defaults={**template_data, "created_by": system_user},
            )

            if created:
                logger.info(f"Created default template: {template.name}")
