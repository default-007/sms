"""
Communications module for School Management System.

This module provides comprehensive communication functionality including:
- Notifications and announcements
- Direct messaging between users
- Bulk email and SMS campaigns
- Communication analytics and reporting
- Template management
- User preferences management

Main Components:
- Models: Data structures for communications
- Services: Business logic and operations
- API: REST endpoints for mobile/web clients
- Views: Web interface for communication management
- Tasks: Background processing for bulk operations
- Utils: Helper functions and utilities

Usage Examples:

    # Send a notification
    from src.communications.services import NotificationService

    notification = NotificationService.create_notification(
        user=user,
        title="Welcome to the system",
        content="Your account has been created successfully",
        notification_type="welcome",
        channels=['in_app', 'email']
    )

    # Create an announcement
    from src.communications.services import AnnouncementService

    announcement = AnnouncementService.create_announcement(
        title="School Holiday Notice",
        content="School will be closed for the holidays",
        created_by=admin_user,
        target_audience="all",
        priority="high"
    )

    # Send bulk notifications
    notifications = NotificationService.bulk_create_notifications(
        users=student_list,
        title="Exam Schedule Released",
        content="Please check the exam schedule",
        notification_type="academic"
    )

    # Get communication analytics
    from src.communications.services import CommunicationAnalyticsService

    summary = CommunicationAnalyticsService.get_communication_summary(days=30)
    daily_analytics = CommunicationAnalyticsService.calculate_daily_analytics()

Configuration:

    Add to INSTALLED_APPS:
        'src.communications',

    Add to CELERY_BEAT_SCHEDULE:
        'calculate-daily-communication-analytics': {
            'task': 'src.communications.tasks.calculate_daily_analytics_task',
            'schedule': crontab(hour=2, minute=0),
        },

Dependencies:
- Django 4.2+
- Django REST Framework
- Celery (for background tasks)
- Redis (for caching and task queue)
"""

# Version information
__version__ = "1.0.0"
__author__ = "School Management System Team"

# Default app configuration
default_app_config = "src.communications.apps.CommunicationsConfig"

# Import main services for easy access
from .services import (
    NotificationService,
    AnnouncementService,
    MessagingService,
    EmailService,
    SMSService,
    CommunicationAnalyticsService,
)

# Import main models
from .models import (
    Announcement,
    Notification,
    BulkMessage,
    MessageTemplate,
    MessageThread,
    DirectMessage,
    CommunicationPreference,
    CommunicationAnalytics,
    CommunicationLog,
)

# Import utilities
from .utils import (
    CommunicationValidator,
    ContentFormatter,
    TemplateProcessor,
    UserTargeting,
    CommunicationMetrics,
)

# Import constants
from .models import CommunicationChannel, Priority, TargetAudience, MessageStatus

# Export main components
__all__ = [
    # Services
    "NotificationService",
    "AnnouncementService",
    "MessagingService",
    "EmailService",
    "SMSService",
    "CommunicationAnalyticsService",
    # Models
    "Announcement",
    "Notification",
    "BulkMessage",
    "MessageTemplate",
    "MessageThread",
    "DirectMessage",
    "CommunicationPreference",
    "CommunicationAnalytics",
    "CommunicationLog",
    # Utilities
    "CommunicationValidator",
    "ContentFormatter",
    "TemplateProcessor",
    "UserTargeting",
    "CommunicationMetrics",
    # Constants
    "CommunicationChannel",
    "Priority",
    "TargetAudience",
    "MessageStatus",
]

# Module metadata
__title__ = "Communications"
__description__ = "Comprehensive communication system for school management"
__url__ = "https://github.com/your-org/school-management-system"
__license__ = "MIT"

# Module configuration
MODULE_CONFIG = {
    "name": "Communications",
    "version": __version__,
    "description": __description__,
    "features": [
        "Multi-channel notifications (Email, SMS, Push, In-app)",
        "Direct messaging between users",
        "Announcement broadcasting",
        "Bulk messaging campaigns",
        "Message templates",
        "User communication preferences",
        "Analytics and reporting",
        "Background task processing",
        "Mobile API support",
    ],
    "dependencies": [
        "django>=4.2",
        "djangorestframework>=3.14",
        "celery>=5.0",
        "redis>=4.0",
    ],
    "settings": {
        "default_channels": [CommunicationChannel.IN_APP],
        "default_priority": Priority.MEDIUM,
        "analytics_retention_days": 365,
        "cleanup_days": 90,
        "batch_size": 100,
        "rate_limit_per_hour": 1000,
    },
}


# Initialization check
def check_configuration():
    """Check if module is properly configured"""
    from django.conf import settings
    from django.core.exceptions import ImproperlyConfigured

    required_settings = ["DEFAULT_FROM_EMAIL", "EMAIL_HOST", "CELERY_BROKER_URL"]

    missing_settings = []
    for setting in required_settings:
        if not hasattr(settings, setting) or not getattr(settings, setting):
            missing_settings.append(setting)

    if missing_settings:
        raise ImproperlyConfigured(
            f"Communications module requires the following settings: {', '.join(missing_settings)}"
        )

    return True


# Quick setup function
def setup_default_templates():
    """Set up default message templates"""
    from .models import MessageTemplate
    from django.contrib.auth import get_user_model

    User = get_user_model()

    try:
        system_user = User.objects.filter(username="system").first()
        if not system_user:
            return False

        default_templates = [
            {
                "name": "Welcome Message",
                "template_type": "system",
                "subject_template": "Welcome to {{ school_name }}",
                "content_template": """
Dear {{ user_name }},

Welcome to {{ school_name }}! Your account has been successfully created.

Best regards,
{{ school_name }} Administration
                """.strip(),
                "supported_channels": ["email", "in_app"],
            },
            {
                "name": "Password Reset",
                "template_type": "system",
                "subject_template": "Password Reset Request",
                "content_template": """
Dear {{ user_name }},

A password reset has been requested for your account. 
If you did not request this, please ignore this message.

Best regards,
{{ school_name }} IT Support
                """.strip(),
                "supported_channels": ["email"],
            },
        ]

        created_count = 0
        for template_data in default_templates:
            template, created = MessageTemplate.objects.get_or_create(
                name=template_data["name"],
                defaults={**template_data, "created_by": system_user},
            )
            if created:
                created_count += 1

        return created_count

    except Exception:
        return False


# Health check function
def health_check():
    """Perform health check for communications module"""
    from .utils import get_communication_health_status

    try:
        status = get_communication_health_status()
        return {
            "module": "communications",
            "status": (
                "healthy" if status["status"] in ["excellent", "good"] else "degraded"
            ),
            "details": status,
        }
    except Exception as e:
        return {"module": "communications", "status": "error", "error": str(e)}


# Debugging utilities
def get_module_info():
    """Get module information for debugging"""
    from django.apps import apps

    try:
        app_config = apps.get_app_config("communications")
        models_count = len(app_config.get_models())

        return {
            "name": app_config.name,
            "verbose_name": app_config.verbose_name,
            "version": __version__,
            "models_count": models_count,
            "services_available": [
                "NotificationService",
                "AnnouncementService",
                "MessagingService",
                "EmailService",
                "SMSService",
                "CommunicationAnalyticsService",
            ],
        }
    except Exception as e:
        return {"error": str(e)}


# Shortcuts for common operations
def send_notification(user, title, content, **kwargs):
    """Shortcut for sending a notification"""
    return NotificationService.create_notification(
        user=user, title=title, content=content, **kwargs
    )


def send_announcement(title, content, created_by, **kwargs):
    """Shortcut for creating an announcement"""
    return AnnouncementService.create_announcement(
        title=title, content=content, created_by=created_by, **kwargs
    )


def bulk_notify(users, title, content, **kwargs):
    """Shortcut for bulk notifications"""
    return NotificationService.bulk_create_notifications(
        users=users, title=title, content=content, **kwargs
    )


# Signal shortcuts
def connect_signals():
    """Connect module signals"""
    from . import signals  # This will register the signals

    return True
