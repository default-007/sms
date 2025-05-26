# src/teachers/config.py
"""
Configuration settings for the teachers module.
This file contains all configurable parameters for teacher management.
"""

import os
from datetime import timedelta

from django.conf import settings


class TeacherModuleConfig:
    """Configuration class for teacher module settings."""

    # Employee ID Configuration
    EMPLOYEE_ID_PREFIX = getattr(settings, "TEACHER_EMPLOYEE_ID_PREFIX", "T")
    EMPLOYEE_ID_LENGTH = getattr(settings, "TEACHER_EMPLOYEE_ID_LENGTH", 6)
    EMPLOYEE_ID_PATTERN = getattr(
        settings,
        "TEACHER_EMPLOYEE_ID_PATTERN",
        rf"^{EMPLOYEE_ID_PREFIX}\d{{{EMPLOYEE_ID_LENGTH}}}$",
    )

    # Performance and Evaluation Settings
    EVALUATION_REQUIRED_INTERVAL_DAYS = getattr(
        settings, "TEACHER_EVALUATION_REQUIRED_INTERVAL_DAYS", 180
    )  # 6 months

    LOW_PERFORMANCE_THRESHOLD = getattr(
        settings, "TEACHER_LOW_PERFORMANCE_THRESHOLD", 70.0
    )

    HIGH_PERFORMANCE_THRESHOLD = getattr(
        settings, "TEACHER_HIGH_PERFORMANCE_THRESHOLD", 85.0
    )

    FOLLOWUP_REQUIRED_DAYS = getattr(settings, "TEACHER_FOLLOWUP_REQUIRED_DAYS", 30)

    # Default evaluation criteria weights
    DEFAULT_EVALUATION_CRITERIA = getattr(
        settings,
        "TEACHER_DEFAULT_EVALUATION_CRITERIA",
        {
            "teaching_methodology": {"weight": 25, "max_score": 10},
            "subject_knowledge": {"weight": 25, "max_score": 10},
            "classroom_management": {"weight": 20, "max_score": 10},
            "student_engagement": {"weight": 20, "max_score": 10},
            "professional_conduct": {"weight": 10, "max_score": 10},
        },
    )

    # Workload Management
    MAX_ASSIGNMENTS_PER_TEACHER = getattr(
        settings, "TEACHER_MAX_ASSIGNMENTS_PER_TEACHER", 8
    )

    MAX_SUBJECTS_PER_TEACHER = getattr(settings, "TEACHER_MAX_SUBJECTS_PER_TEACHER", 4)

    OVERLOAD_THRESHOLD = getattr(settings, "TEACHER_OVERLOAD_THRESHOLD", 8)

    UNDERUTILIZED_THRESHOLD = getattr(settings, "TEACHER_UNDERUTILIZED_THRESHOLD", 3)

    # Salary Configuration
    MIN_SALARY = getattr(settings, "TEACHER_MIN_SALARY", 20000.00)
    MAX_SALARY = getattr(settings, "TEACHER_MAX_SALARY", 200000.00)
    SALARY_CURRENCY = getattr(settings, "TEACHER_SALARY_CURRENCY", "USD")

    # Experience Configuration
    MAX_EXPERIENCE_YEARS = getattr(settings, "TEACHER_MAX_EXPERIENCE_YEARS", 50)
    JUNIOR_TEACHER_THRESHOLD = getattr(settings, "TEACHER_JUNIOR_THRESHOLD", 2)
    SENIOR_TEACHER_THRESHOLD = getattr(settings, "TEACHER_SENIOR_THRESHOLD", 10)

    # Notification Settings
    SEND_EVALUATION_REMINDERS = getattr(
        settings, "TEACHER_SEND_EVALUATION_REMINDERS", True
    )

    SEND_BIRTHDAY_NOTIFICATIONS = getattr(
        settings, "TEACHER_SEND_BIRTHDAY_NOTIFICATIONS", True
    )

    SEND_PERFORMANCE_ALERTS = getattr(settings, "TEACHER_SEND_PERFORMANCE_ALERTS", True)

    EMAIL_EVALUATION_REMINDERS = getattr(
        settings, "TEACHER_EMAIL_EVALUATION_REMINDERS", False
    )

    # Analytics Configuration
    ENABLE_PERFORMANCE_TRACKING = getattr(
        settings, "TEACHER_ENABLE_PERFORMANCE_TRACKING", True
    )

    ANALYTICS_CACHE_TIMEOUT = getattr(
        settings, "TEACHER_ANALYTICS_CACHE_TIMEOUT", 3600
    )  # 1 hour

    PERFORMANCE_TRENDS_MONTHS = getattr(
        settings, "TEACHER_PERFORMANCE_TRENDS_MONTHS", 12
    )

    # Security Settings
    MAX_REQUESTS_PER_MINUTE = getattr(settings, "TEACHER_MAX_REQUESTS_PER_MINUTE", 60)

    ENABLE_AUDIT_LOGGING = getattr(settings, "TEACHER_ENABLE_AUDIT_LOGGING", True)

    ENABLE_PERFORMANCE_MONITORING = getattr(
        settings, "TEACHER_ENABLE_PERFORMANCE_MONITORING", True
    )

    SLOW_REQUEST_THRESHOLD = getattr(
        settings, "TEACHER_SLOW_REQUEST_THRESHOLD", 2.0
    )  # seconds

    # File Upload Settings
    MAX_UPLOAD_SIZE = getattr(
        settings, "TEACHER_MAX_UPLOAD_SIZE", 5 * 1024 * 1024
    )  # 5MB

    ALLOWED_FILE_TYPES = getattr(
        settings, "TEACHER_ALLOWED_FILE_TYPES", ["pdf", "doc", "docx", "jpg", "png"]
    )

    # Export Settings
    MAX_EXPORT_RECORDS = getattr(settings, "TEACHER_MAX_EXPORT_RECORDS", 10000)

    EXPORT_FORMATS = getattr(
        settings, "TEACHER_EXPORT_FORMATS", ["csv", "excel", "pdf"]
    )

    # Backup and Archive Settings
    BACKUP_RETENTION_DAYS = getattr(
        settings, "TEACHER_BACKUP_RETENTION_DAYS", 2555
    )  # ~7 years

    ARCHIVE_OLD_EVALUATIONS = getattr(settings, "TEACHER_ARCHIVE_OLD_EVALUATIONS", True)

    AUTO_CLEANUP_ENABLED = getattr(settings, "TEACHER_AUTO_CLEANUP_ENABLED", True)

    # Celery Task Configuration
    TASK_RETRY_DELAY = getattr(settings, "TEACHER_TASK_RETRY_DELAY", 300)  # 5 minutes

    TASK_MAX_RETRIES = getattr(settings, "TEACHER_TASK_MAX_RETRIES", 3)

    ANALYTICS_CALCULATION_TIME = getattr(
        settings, "TEACHER_ANALYTICS_CALCULATION_TIME", {"hour": 2, "minute": 0}
    )  # 2 AM daily

    # Internationalization
    DEFAULT_LANGUAGE = getattr(settings, "TEACHER_DEFAULT_LANGUAGE", "en")
    SUPPORTED_LANGUAGES = getattr(
        settings, "TEACHER_SUPPORTED_LANGUAGES", ["en", "es", "fr"]
    )

    # Integration Settings
    ENABLE_TIMETABLE_INTEGRATION = getattr(
        settings, "TEACHER_ENABLE_TIMETABLE_INTEGRATION", True
    )

    ENABLE_STUDENT_CORRELATION = getattr(
        settings, "TEACHER_ENABLE_STUDENT_CORRELATION", True
    )

    ENABLE_FINANCE_INTEGRATION = getattr(
        settings, "TEACHER_ENABLE_FINANCE_INTEGRATION", True
    )

    @classmethod
    def get_evaluation_criteria_config(cls):
        """Get evaluation criteria configuration."""
        return cls.DEFAULT_EVALUATION_CRITERIA

    @classmethod
    def get_performance_thresholds(cls):
        """Get performance threshold configuration."""
        return {
            "excellent": 90,
            "good": cls.HIGH_PERFORMANCE_THRESHOLD,
            "satisfactory": 70,
            "needs_improvement": cls.LOW_PERFORMANCE_THRESHOLD,
            "poor": 0,
        }

    @classmethod
    def get_workload_thresholds(cls):
        """Get workload threshold configuration."""
        return {
            "overloaded": cls.OVERLOAD_THRESHOLD,
            "balanced": 4,
            "underutilized": cls.UNDERUTILIZED_THRESHOLD,
        }

    @classmethod
    def get_notification_settings(cls):
        """Get notification configuration."""
        return {
            "evaluation_reminders": cls.SEND_EVALUATION_REMINDERS,
            "birthday_notifications": cls.SEND_BIRTHDAY_NOTIFICATIONS,
            "performance_alerts": cls.SEND_PERFORMANCE_ALERTS,
            "email_reminders": cls.EMAIL_EVALUATION_REMINDERS,
        }

    @classmethod
    def validate_config(cls):
        """Validate configuration settings."""
        errors = []

        # Validate thresholds
        if cls.LOW_PERFORMANCE_THRESHOLD >= cls.HIGH_PERFORMANCE_THRESHOLD:
            errors.append(
                "Low performance threshold must be less than high performance threshold"
            )

        if cls.MAX_ASSIGNMENTS_PER_TEACHER <= 0:
            errors.append("Max assignments per teacher must be positive")

        if cls.MIN_SALARY >= cls.MAX_SALARY:
            errors.append("Min salary must be less than max salary")

        # Validate file upload settings
        if cls.MAX_UPLOAD_SIZE <= 0:
            errors.append("Max upload size must be positive")

        # Validate cache timeout
        if cls.ANALYTICS_CACHE_TIMEOUT <= 0:
            errors.append("Analytics cache timeout must be positive")

        return errors


# Teacher module specific Django settings to add to settings.py
TEACHER_MODULE_SETTINGS = {
    # Basic Configuration
    "TEACHER_EMPLOYEE_ID_PREFIX": "T",
    "TEACHER_EMPLOYEE_ID_LENGTH": 6,
    "TEACHER_EVALUATION_REQUIRED_INTERVAL_DAYS": 180,
    "TEACHER_LOW_PERFORMANCE_THRESHOLD": 70.0,
    "TEACHER_HIGH_PERFORMANCE_THRESHOLD": 85.0,
    "TEACHER_FOLLOWUP_REQUIRED_DAYS": 30,
    # Workload Management
    "TEACHER_MAX_ASSIGNMENTS_PER_TEACHER": 8,
    "TEACHER_MAX_SUBJECTS_PER_TEACHER": 4,
    "TEACHER_OVERLOAD_THRESHOLD": 8,
    "TEACHER_UNDERUTILIZED_THRESHOLD": 3,
    # Performance Settings
    "TEACHER_MIN_SALARY": 2000.00,
    "TEACHER_MAX_SALARY": 200000.00,
    "TEACHER_SALARY_CURRENCY": "KSH",
    "TEACHER_MAX_EXPERIENCE_YEARS": 50,
    "TEACHER_JUNIOR_THRESHOLD": 2,
    "TEACHER_SENIOR_THRESHOLD": 10,
    # Notification Settings
    "TEACHER_SEND_EVALUATION_REMINDERS": True,
    "TEACHER_SEND_BIRTHDAY_NOTIFICATIONS": True,
    "TEACHER_SEND_PERFORMANCE_ALERTS": True,
    "TEACHER_EMAIL_EVALUATION_REMINDERS": False,
    # Analytics Configuration
    "TEACHER_ENABLE_PERFORMANCE_TRACKING": True,
    "TEACHER_ANALYTICS_CACHE_TIMEOUT": 3600,
    "TEACHER_PERFORMANCE_TRENDS_MONTHS": 12,
    # Security Settings
    "TEACHER_MAX_REQUESTS_PER_MINUTE": 60,
    "TEACHER_ENABLE_AUDIT_LOGGING": True,
    "TEACHER_ENABLE_PERFORMANCE_MONITORING": True,
    "TEACHER_SLOW_REQUEST_THRESHOLD": 2.0,
    # File and Export Settings
    "TEACHER_MAX_UPLOAD_SIZE": 5 * 1024 * 1024,  # 5MB
    "TEACHER_ALLOWED_FILE_TYPES": ["pdf", "doc", "docx", "jpg", "png"],
    "TEACHER_MAX_EXPORT_RECORDS": 10000,
    "TEACHER_EXPORT_FORMATS": ["csv", "excel", "pdf"],
    # Backup and Cleanup
    "TEACHER_BACKUP_RETENTION_DAYS": 2555,  # ~7 years
    "TEACHER_ARCHIVE_OLD_EVALUATIONS": True,
    "TEACHER_AUTO_CLEANUP_ENABLED": True,
    # Task Configuration
    "TEACHER_TASK_RETRY_DELAY": 300,  # 5 minutes
    "TEACHER_TASK_MAX_RETRIES": 3,
    "TEACHER_ANALYTICS_CALCULATION_TIME": {"hour": 2, "minute": 0},
    # Integration Settings
    "TEACHER_ENABLE_TIMETABLE_INTEGRATION": True,
    "TEACHER_ENABLE_STUDENT_CORRELATION": True,
    "TEACHER_ENABLE_FINANCE_INTEGRATION": True,
    # Default Evaluation Criteria
    "TEACHER_DEFAULT_EVALUATION_CRITERIA": {
        "teaching_methodology": {"weight": 25, "max_score": 10},
        "subject_knowledge": {"weight": 25, "max_score": 10},
        "classroom_management": {"weight": 20, "max_score": 10},
        "student_engagement": {"weight": 20, "max_score": 10},
        "professional_conduct": {"weight": 10, "max_score": 10},
    },
}

# Celery configuration for teacher tasks
TEACHER_CELERY_BEAT_SCHEDULE = {
    "calculate-daily-teacher-analytics": {
        "task": "src.teachers.tasks.calculate_daily_teacher_analytics",
        "schedule": "crontab(hour=2, minute=0)",  # Daily at 2 AM
        "options": {"expires": 3600},
    },
    "send-evaluation-reminders": {
        "task": "src.teachers.tasks.send_evaluation_reminders",
        "schedule": "crontab(hour=8, minute=0, day_of_week=1)",  # Monday at 8 AM
        "options": {"expires": 3600},
    },
    "send-followup-notifications": {
        "task": "src.teachers.tasks.send_followup_notifications",
        "schedule": "crontab(hour=9, minute=0)",  # Daily at 9 AM
        "options": {"expires": 3600},
    },
    "update-teacher-performance-metrics": {
        "task": "src.teachers.tasks.update_teacher_performance_metrics",
        "schedule": "crontab(hour=3, minute=0, day_of_week=0)",  # Sunday at 3 AM
        "options": {"expires": 7200},
    },
    "send-birthday-notifications": {
        "task": "src.teachers.tasks.send_birthday_notifications",
        "schedule": "crontab(hour=7, minute=0)",  # Daily at 7 AM
        "options": {"expires": 3600},
    },
    "cleanup-old-evaluations": {
        "task": "src.teachers.tasks.cleanup_old_evaluations",
        "schedule": "crontab(hour=1, minute=0, day_of_month=1)",  # First day of month at 1 AM
        "options": {"expires": 7200},
    },
}

# Logging configuration for teacher module
TEACHER_LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "teacher_detailed": {
            "format": "{levelname} {asctime} {module} {process:d} {thread:d} {message}",
            "style": "{",
        },
        "teacher_simple": {
            "format": "{levelname} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "teacher_file": {
            "level": "INFO",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": os.path.join(settings.BASE_DIR, "logs", "teachers.log"),
            "maxBytes": 1024 * 1024 * 10,  # 10MB
            "backupCount": 5,
            "formatter": "teacher_detailed",
        },
        "teacher_analytics_file": {
            "level": "INFO",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": os.path.join(
                settings.BASE_DIR, "logs", "teacher_analytics.log"
            ),
            "maxBytes": 1024 * 1024 * 5,  # 5MB
            "backupCount": 3,
            "formatter": "teacher_detailed",
        },
        "teacher_performance_file": {
            "level": "WARNING",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": os.path.join(
                settings.BASE_DIR, "logs", "teacher_performance.log"
            ),
            "maxBytes": 1024 * 1024 * 5,  # 5MB
            "backupCount": 3,
            "formatter": "teacher_detailed",
        },
    },
    "loggers": {
        "src.teachers": {
            "handlers": ["teacher_file"],
            "level": "INFO",
            "propagate": True,
        },
        "src.teachers.analytics": {
            "handlers": ["teacher_analytics_file"],
            "level": "INFO",
            "propagate": False,
        },
        "src.teachers.performance": {
            "handlers": ["teacher_performance_file"],
            "level": "WARNING",
            "propagate": False,
        },
        "src.teachers.middleware": {
            "handlers": ["teacher_performance_file"],
            "level": "WARNING",
            "propagate": False,
        },
    },
}

# Cache configuration for teacher module
TEACHER_CACHE_CONFIG = {
    "teacher_analytics": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": "redis://127.0.0.1:6379/2",
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        },
        "TIMEOUT": 3600,  # 1 hour
        "KEY_PREFIX": "teacher_analytics",
    },
    "teacher_performance": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": "redis://127.0.0.1:6379/3",
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        },
        "TIMEOUT": 1800,  # 30 minutes
        "KEY_PREFIX": "teacher_performance",
    },
}

# Default permissions for teacher module
TEACHER_DEFAULT_PERMISSIONS = {
    "Admin": [
        "teachers.add_teacher",
        "teachers.change_teacher",
        "teachers.delete_teacher",
        "teachers.view_teacher",
        "teachers.add_teacherevaluation",
        "teachers.change_teacherevaluation",
        "teachers.delete_teacherevaluation",
        "teachers.view_teacherevaluation",
        "teachers.assign_classes",
        "teachers.view_teacher_analytics",
        "teachers.export_teacher_data",
    ],
    "Principal": [
        "teachers.add_teacher",
        "teachers.change_teacher",
        "teachers.view_teacher",
        "teachers.add_teacherevaluation",
        "teachers.change_teacherevaluation",
        "teachers.view_teacherevaluation",
        "teachers.assign_classes",
        "teachers.view_teacher_analytics",
        "teachers.export_teacher_data",
    ],
    "Department Head": [
        "teachers.view_teacher",
        "teachers.add_teacherevaluation",
        "teachers.change_teacherevaluation",
        "teachers.view_teacherevaluation",
        "teachers.view_teacher_analytics",
    ],
    "Academic Coordinator": [
        "teachers.view_teacher",
        "teachers.assign_classes",
        "teachers.view_teacher_analytics",
    ],
    "HR Manager": [
        "teachers.add_teacher",
        "teachers.change_teacher",
        "teachers.view_teacher",
        "teachers.export_teacher_data",
    ],
    "Teacher": [
        "teachers.view_teacher",
    ],
}

# Email templates configuration
TEACHER_EMAIL_TEMPLATES = {
    "evaluation_reminder": {
        "subject": "Teacher Evaluation Reminder - {teacher_name}",
        "template": "teachers/emails/evaluation_reminder.html",
        "text_template": "teachers/emails/evaluation_reminder.txt",
    },
    "performance_report": {
        "subject": "Teacher Performance Report - {department}",
        "template": "teachers/emails/performance_report.html",
        "text_template": "teachers/emails/performance_report.txt",
    },
    "low_performance_alert": {
        "subject": "Performance Alert - {teacher_name}",
        "template": "teachers/emails/low_performance_alert.html",
        "text_template": "teachers/emails/low_performance_alert.txt",
    },
    "birthday_notification": {
        "subject": "Birthday Reminder - {teacher_name}",
        "template": "teachers/emails/birthday_notification.html",
        "text_template": "teachers/emails/birthday_notification.txt",
    },
}

# API throttling configuration
TEACHER_API_THROTTLING = {
    "anon": "100/hour",
    "user": "1000/hour",
    "teacher_analytics": "200/hour",
    "teacher_bulk_operations": "50/hour",
}

# File storage configuration
TEACHER_FILE_STORAGE = {
    "profile_pictures": {
        "upload_to": "teachers/profile_pictures/",
        "max_size": 2 * 1024 * 1024,  # 2MB
        "allowed_extensions": ["jpg", "jpeg", "png"],
    },
    "documents": {
        "upload_to": "teachers/documents/",
        "max_size": 5 * 1024 * 1024,  # 5MB
        "allowed_extensions": ["pdf", "doc", "docx"],
    },
    "evaluation_attachments": {
        "upload_to": "teachers/evaluations/",
        "max_size": 10 * 1024 * 1024,  # 10MB
        "allowed_extensions": ["pdf", "doc", "docx", "jpg", "png"],
    },
}

# Performance monitoring configuration
TEACHER_PERFORMANCE_MONITORING = {
    "enable_query_logging": True,
    "slow_query_threshold": 1.0,  # seconds
    "enable_memory_monitoring": True,
    "memory_threshold": 100 * 1024 * 1024,  # 100MB
    "enable_cache_monitoring": True,
    "cache_hit_rate_threshold": 0.8,  # 80%
}


def get_teacher_config():
    """Get complete teacher module configuration."""
    return {
        "module_settings": TEACHER_MODULE_SETTINGS,
        "celery_schedule": TEACHER_CELERY_BEAT_SCHEDULE,
        "logging_config": TEACHER_LOGGING_CONFIG,
        "cache_config": TEACHER_CACHE_CONFIG,
        "permissions": TEACHER_DEFAULT_PERMISSIONS,
        "email_templates": TEACHER_EMAIL_TEMPLATES,
        "api_throttling": TEACHER_API_THROTTLING,
        "file_storage": TEACHER_FILE_STORAGE,
        "performance_monitoring": TEACHER_PERFORMANCE_MONITORING,
    }


def validate_teacher_configuration():
    """Validate teacher module configuration."""
    config = TeacherModuleConfig()
    errors = config.validate_config()

    if errors:
        raise ValueError(f"Teacher configuration errors: {', '.join(errors)}")

    return True
