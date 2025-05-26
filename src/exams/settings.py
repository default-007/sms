"""
School Management System - Exam Module Settings Configuration
File: src/exams/settings.py
"""

# Exam module specific settings

# Exam Configuration
EXAM_SETTINGS = {
    # Default exam duration in minutes
    "DEFAULT_EXAM_DURATION": 120,
    # Default passing percentage
    "DEFAULT_PASSING_PERCENTAGE": 40.0,
    # Maximum number of exam attempts for online exams
    "MAX_ONLINE_EXAM_ATTEMPTS": 3,
    # Auto-save interval for online exams (in seconds)
    "ONLINE_EXAM_AUTO_SAVE_INTERVAL": 30,
    # Question bank pagination
    "QUESTION_BANK_PAGE_SIZE": 20,
    # Result entry batch size
    "RESULT_ENTRY_BATCH_SIZE": 50,
    # Analytics cache timeout (in seconds)
    "ANALYTICS_CACHE_TIMEOUT": 3600,  # 1 hour
    # Report card generation timeout (in seconds)
    "REPORT_CARD_GENERATION_TIMEOUT": 300,  # 5 minutes
    # Exam notification settings
    "EXAM_REMINDER_DAYS": 3,  # Send reminders 3 days before exam
    # Grade calculation precision
    "GRADE_CALCULATION_PRECISION": 2,
    # Online exam security settings
    "ONLINE_EXAM_SECURITY": {
        "ENABLE_PROCTORING_BY_DEFAULT": False,
        "REQUIRE_WEBCAM_BY_DEFAULT": False,
        "REQUIRE_FULLSCREEN_BY_DEFAULT": True,
        "MAX_VIOLATION_COUNT": 5,
        "AUTO_SUBMIT_ON_VIOLATION_LIMIT": True,
    },
    # File upload settings for exam materials
    "EXAM_FILE_UPLOAD": {
        "MAX_FILE_SIZE": 10 * 1024 * 1024,  # 10MB
        "ALLOWED_EXTENSIONS": ["pdf", "doc", "docx", "jpg", "jpeg", "png"],
        "UPLOAD_PATH": "exam_materials/",
    },
    # Performance optimization settings
    "PERFORMANCE": {
        "ENABLE_QUERY_OPTIMIZATION": True,
        "CACHE_EXPENSIVE_QUERIES": True,
        "BULK_OPERATION_CHUNK_SIZE": 1000,
        "ENABLE_DATABASE_INDEXES": True,
    },
    # Integration settings
    "INTEGRATIONS": {
        "ENABLE_SMS_NOTIFICATIONS": True,
        "ENABLE_EMAIL_NOTIFICATIONS": True,
        "SYNC_WITH_FINANCE_MODULE": True,
        "EXPORT_TO_EXTERNAL_SYSTEMS": False,
    },
}

# Celery task settings for exams
CELERY_EXAM_SETTINGS = {
    "exam-rankings-calculation": {
        "task": "exams.tasks.calculate_exam_rankings",
        "options": {"queue": "analytics"},
    },
    "auto-grade-online-exam": {
        "task": "exams.tasks.auto_grade_online_exam",
        "options": {"queue": "grading"},
    },
    "generate-bulk-report-cards": {
        "task": "exams.tasks.generate_bulk_report_cards",
        "options": {"queue": "reports"},
    },
}

# Cache keys for exam module
EXAM_CACHE_KEYS = {
    "EXAM_ANALYTICS": "exam_analytics_{exam_id}",
    "STUDENT_PERFORMANCE": "student_performance_{student_id}_{academic_year_id}",
    "CLASS_PERFORMANCE": "class_performance_{class_id}_{term_id}",
    "QUESTION_BANK_STATS": "question_bank_stats_{subject_id}_{grade_id}",
    "REPORT_CARD_DATA": "report_card_data_{term_id}",
}

# Logging configuration for exam module
EXAM_LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "exam_file": {
            "level": "INFO",
            "class": "logging.FileHandler",
            "filename": "logs/exams.log",
            "formatter": "standard",
        },
    },
    "loggers": {
        "exams": {
            "handlers": ["exam_file"],
            "level": "INFO",
            "propagate": True,
        },
        "exams.services": {
            "handlers": ["exam_file"],
            "level": "DEBUG",
            "propagate": True,
        },
        "exams.tasks": {
            "handlers": ["exam_file"],
            "level": "INFO",
            "propagate": True,
        },
    },
}
