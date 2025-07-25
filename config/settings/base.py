"""
Base settings for School Management System.
"""

import os
import logging
from datetime import timedelta
from pathlib import Path

from celery.schedules import crontab
from decouple import Csv, config

# Build paths inside the project
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Security settings
SECRET_KEY = config("SECRET_KEY")
DEBUG = config("DEBUG", default=False, cast=bool)
ALLOWED_HOSTS = config("ALLOWED_HOSTS", cast=Csv())

# Application definition
INSTALLED_APPS = [
    # Django apps
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-party apps
    "rest_framework",
    "rest_framework.authtoken",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "django_filters",
    "drf_yasg",
    "celery",
    "django_celery_beat",
    "crispy_forms",
    "crispy_bootstrap5",
    "widget_tweaks",
    "import_export",
    "qrcode",
    "faker",
    "xhtml2pdf",
    "csp",
    # Local apps
    "src.accounts",
    "src.api",
    "src.core",
    "src.students",
    "src.teachers",
    "src.exams",
    "src.attendance",
    "src.academics",
    "src.subjects",
    "src.scheduling",
    "src.assignments",
    "src.finance",
    "src.library",
    "src.transport",
    "src.communications",
    "src.reports",
    "src.analytics",
]

CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"

CRISPY_TEMPLATE_PACK = "bootstrap5"

from csp.constants import SELF, UNSAFE_INLINE

# ==============================================================================
# MIDDLEWARE SETTINGS
# ==============================================================================


MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "csp.middleware.CSPMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "src.assignments.middleware.AssignmentDeadlineNotificationMiddleware",
    "src.accounts.middleware.SecurityMiddleware",
    "src.accounts.middleware.RateLimitMiddleware",
    "src.accounts.middleware.AuditMiddleware",
    "src.accounts.middleware.SessionSecurityMiddleware",
    "src.assignments.middleware.AssignmentAccessControlMiddleware",
    "src.assignments.middleware.AssignmentActivityTrackingMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [os.path.join(BASE_DIR, "src/templates")],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "src.accounts.context_processors.user_roles",
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# ==============================================================================
# CONTENT SECURITY POLICY SETTINGS (FIXED)
# ==============================================================================

# Updated CSP to allow all necessary script sources
CONTENT_SECURITY_POLICY = {
    "DIRECTIVES": {
        "default-src": ("'self'",),
        "script-src": (
            "'self'",
            "'unsafe-inline'",  # Needed for inline scripts
            "'unsafe-eval'",  # Needed for some libraries
            # CDN Sources - Add all the CDNs you're using
            "cdn.jsdelivr.net",
            "cdnjs.cloudflare.com",
            "unpkg.com",
            "stackpath.bootstrapcdn.com",
            "code.jquery.com",
            "maxcdn.bootstrapcdn.com",
            "ajax.googleapis.com",
            "js.stripe.com",
            "checkout.stripe.com",
            # Chart.js and data visualization
            "cdn.plot.ly",
            "d3js.org",
            "cdn.datatables.net",
            # Bootstrap and UI libraries
            "getbootstrap.com",
            "bootstrap.min.js",
            # Analytics (if you use them)
            "www.google-analytics.com",
            "www.googletagmanager.com",
            "connect.facebook.net",
            # Add any other CDNs you're using
        ),
        "style-src": (
            "'self'",
            "'unsafe-inline'",  # Needed for inline styles and some libraries
            "cdn.jsdelivr.net",
            "cdnjs.cloudflare.com",
            "fonts.googleapis.com",
            "unpkg.com",
            "stackpath.bootstrapcdn.com",
            "maxcdn.bootstrapcdn.com",
            "getbootstrap.com",
            "cdn.datatables.net",
            # Add any other style CDNs
        ),
        "font-src": (
            "'self'",
            "cdn.jsdelivr.net",
            "cdnjs.cloudflare.com",
            "fonts.googleapis.com",
            "fonts.gstatic.com",
            "use.fontawesome.com",
            "ka-f.fontawesome.com",
        ),
        "img-src": (
            "'self'",
            "data:",  # Base64 images
            "blob:",  # Blob URLs
            "cdn.jsdelivr.net",
            "cdnjs.cloudflare.com",
            "via.placeholder.com",  # Placeholder images
            "picsum.photos",  # Lorem Picsum
            "images.unsplash.com",  # Unsplash
            # Analytics tracking pixels
            "www.google-analytics.com",
            "www.googletagmanager.com",
            "connect.facebook.net",
            # Add your media/image CDN domains here
        ),
        "connect-src": (
            "'self'",
            "api.iconify.design",
            "api.simplesvg.com",
            "api.unisvg.com",
            # API endpoints you might need
            # CDN endpoints (these were missing!)
            "cdn.jsdelivr.net",
            "cdnjs.cloudflare.com",
            "unpkg.com",
            "code.jquery.com",
            "ajax.googleapis.com",
            "stackpath.bootstrapcdn.com",
            "maxcdn.bootstrapcdn.com",
            # Analytics
            "www.google-analytics.com",
            "www.googletagmanager.com",
            # Add your API domains here
        ),
        "media-src": ("'self'", "blob:", "data:"),
        "object-src": ("'none'",),
        "base-uri": ("'self'",),
        "form-action": ("'self'",),
        "frame-ancestors": ("'none'",),  # Prevents clickjacking
        "upgrade-insecure-requests": True,  # Force HTTPS in production
    }
}

# Development vs Production settings
if DEBUG:
    # Add development-specific sources for local development
    CONTENT_SECURITY_POLICY["DIRECTIVES"]["script-src"] += (
        "localhost:*",
        "127.0.0.1:*",
    )
    CONTENT_SECURITY_POLICY["DIRECTIVES"]["connect-src"] += (
        "localhost:*",  # ✅ Allows local API calls
        "127.0.0.1:*",  # ✅ Allows local development server
        "ws:",  # ✅ WebSocket for development tools
        "wss:",  # ✅ Secure WebSocket
    )

    # Optional: Enable report-only mode for testing new policies
    # CONTENT_SECURITY_POLICY_REPORT_ONLY = True

else:
    # Production settings - force HTTPS
    CONTENT_SECURITY_POLICY["DIRECTIVES"]["upgrade-insecure-requests"] = True

# ==============================================================================
# PERFORMANCE SETTINGS
# ==============================================================================

# Database
# https://docs.djangoproject.com/en/4.2/ref/settings/#databases

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("DB_NAME", "school_db"),
        "USER": os.environ.get("DB_USER", "default_007"),
        "PASSWORD": os.environ.get("DB_PASSWORD", "expandebles7"),
        "HOST": os.environ.get("DB_HOST", "localhost"),
        "PORT": os.environ.get("DB_PORT", "5432"),
    }
}

# Static files optimization
STATICFILES_STORAGE = "django.contrib.staticfiles.storage.StaticFilesStorage"

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.2/howto/static-files/

STATIC_URL = "/static/"
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")
STATICFILES_DIRS = [os.path.join(BASE_DIR, "static")]

# Media files
MEDIA_URL = "/media/"
MEDIA_ROOT = os.path.join(BASE_DIR, "media")

# Default primary key field type
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# ==============================================================================
# AUTHENTICATION BACKENDS
# ==============================================================================

# Authentication backends - Order matters!
# The first backend that successfully authenticates will be used
AUTHENTICATION_BACKENDS = [
    # Primary unified backend supporting all identifier types
    # "src.accounts.authentication.UnifiedAuthenticationBackend",
    # Fallback to Django's default backend for admin/superuser accounts
    "django.contrib.auth.backends.ModelBackend",
    # Specialized backends (optional - for specific use cases)
    # "src.accounts.authentication.EmailAuthenticationBackend",  # Email only
    # "src.accounts.authentication.PhoneAuthenticationBackend",  # Phone only
    # "src.accounts.authentication.StudentAdmissionBackend",     # Admission number only
]


# ==============================================================================
# INTERNATIONALIZATION SETTINGS
# ==============================================================================

# Internationalization
# https://docs.djangoproject.com/en/4.2/topics/i18n/

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_L10N = True
USE_TZ = True

# ==============================================================================
# ACCOUNTS MODULE SETTINGS
# ==============================================================================

# Site Configuration
SITE_NAME = "School Management System"

# Authentication Settings
AUTH_USER_MODEL = "accounts.User"

# Remember me functionality
REMEMBER_ME_DURATION = 60 * 60 * 24 * 14  # 2 weeks in seconds


# Password Validation
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {
            "min_length": 8,
        },
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

# Login/Logout URLs
LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "core:dashboard"
LOGOUT_REDIRECT_URL = "accounts:login"


# ==============================================================================
# SECURITY SETTINGS
# ==============================================================================

# Account Lockout Settings
MAX_FAILED_LOGIN_ATTEMPTS = 5
ACCOUNT_LOCKOUT_DURATION = 30  # minutes

# Session Settings
SESSION_TIMEOUT = 30  # minutes
MAX_CONCURRENT_SESSIONS = 5
SESSION_COOKIE_AGE = 1800  # 30 minutes
SESSION_SAVE_EVERY_REQUEST = True
SESSION_EXPIRE_AT_BROWSER_CLOSE = True

# Password Policy
PASSWORD_EXPIRY_DAYS = 90
REQUIRE_PASSWORD_CHANGE_ON_FIRST_LOGIN = True

# Notification Settings
SEND_LOGIN_NOTIFICATIONS = True
SEND_ROLE_NOTIFICATIONS = True
SECURITY_ALERT_EMAIL = "security@yourdomain.com"
ADMIN_EMAIL = "admin@yourdomain.com"

# ==============================================================================
# RATE LIMITING SETTINGS
# ==============================================================================

RATE_LIMITS = {
    "login": {"requests": 5, "window": 300},  # 5 attempts per 5 minutes
    "api": {"requests": 100, "window": 3600},  # 100 requests per hour
    "password_reset": {"requests": 3, "window": 900},  # 3 attempts per 15 minutes
}


# ==============================================================================
# AUDIT SETTINGS
# ==============================================================================

# Paths to audit
AUDIT_PATHS = [
    "/accounts/",
    "/api/",
]

# Paths to exclude from auditing
AUDIT_EXCLUDE_PATHS = [
    "/static/",
    "/media/",
    "/admin/jsi18n/",
]

# Audit log retention (in days)
AUDIT_LOG_RETENTION_DAYS = 365

# ==============================================================================
# EMAIL SETTINGS
# ==============================================================================

# Email configuration
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = "smtp.gmail.com"  # Replace with your SMTP server
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = "your-email@gmail.com"  # Replace with your email
EMAIL_HOST_PASSWORD = "your-app-password"  # Replace with your app password
DEFAULT_FROM_EMAIL = "noreply@yourdomain.com"

# Email templates directory
EMAIL_TEMPLATE_DIR = "accounts/emails/"

SCHOOL_NAME = "Your School Name"
ENABLE_EMAIL_NOTIFICATIONS = True

# ==============================================================================
# FILE UPLOAD SETTINGS
# ==============================================================================

# Profile picture settings
PROFILE_PICTURE_MAX_SIZE = 2 * 1024 * 1024  # 2MB
PROFILE_PICTURE_ALLOWED_TYPES = ["jpg", "jpeg", "png"]

# General file upload settings
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024  # 5MB
# File upload settings for student profiles
FILE_UPLOAD_SETTINGS = {
    "STUDENT_PROFILE_PICTURES": {
        "UPLOAD_TO": "student_photos/%Y/%m/",
        "MAX_SIZE": 5 * 1024 * 1024,  # 5MB
        "ALLOWED_EXTENSIONS": ["jpg", "jpeg", "png", "gif"],
        "RESIZE_TO": (300, 300),
        "QUALITY": 85,
    },
    "STUDENT_DOCUMENTS": {
        "UPLOAD_TO": "student_documents/%Y/%m/",
        "MAX_SIZE": 10 * 1024 * 1024,  # 10MB
        "ALLOWED_EXTENSIONS": ["pdf", "doc", "docx", "jpg", "jpeg", "png"],
    },
    "BULK_IMPORT_FILES": {
        "UPLOAD_TO": "imports/%Y/%m/",
        "MAX_SIZE": 5 * 1024 * 1024,  # 5MB
        "ALLOWED_EXTENSIONS": ["csv", "xlsx"],
    },
}

# ==============================================================================
# CACHE SETTINGS
# ==============================================================================

# Cache configuration
# Cache configuration - Use django-redis consistently
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": "redis://127.0.0.1:6379/1",
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "CONNECTION_POOL_KWARGS": {"max_connections": 50},
            "IGNORE_EXCEPTIONS": True,  # Don't crash if Redis is unavailable
        },
        "KEY_PREFIX": "sms",
        "TIMEOUT": 300,  # 5 minutes default timeout
    },
    "sessions": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": "redis://127.0.0.1:6379/2",
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "CONNECTION_POOL_KWARGS": {"max_connections": 20},
            "IGNORE_EXCEPTIONS": True,
        },
        "KEY_PREFIX": "sms_session",
        "TIMEOUT": 3600,  # 1 hour
    },
    "finance": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": "redis://127.0.0.1:6379/3",
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "CONNECTION_POOL_KWARGS": {"max_connections": 20},
            "IGNORE_EXCEPTIONS": True,
        },
        "KEY_PREFIX": "finance",
        "TIMEOUT": 3600,
    },
}
# Cache timeouts for specific functions
CACHE_TIMEOUTS = {
    "user_permissions": 3600,  # 1 hour
    "user_roles": 3600,  # 1 hour
    "role_statistics": 1800,  # 30 minutes
}

# Session configuration to use Redis
SESSION_ENGINE = "django.contrib.sessions.backends.cache"
SESSION_CACHE_ALIAS = "sessions"

# Redis connection settings
REDIS_HOST = "127.0.0.1"
REDIS_PORT = 6379
REDIS_DB = 0

# ==============================================================================
# DJANGO REST FRAMEWORK SETTINGS
# ==============================================================================

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 25,
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {"anon": "100/hour", "user": "1000/hour"},
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
        "rest_framework.renderers.BrowsableAPIRenderer",
    ],
    "EXCEPTION_HANDLER": "src.students.exceptions.custom_exception_handler",
}

# ==============================================================================
# LOGGING SETTINGS
# ==============================================================================
# Ensure logs directory exists
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)

# Robust logging configuration
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {process:d} {thread:d} {message}",
            "style": "{",
        },
        "simple": {
            "format": "{levelname} {message}",
            "style": "{",
        },
        "audit": {
            "format": "{asctime} {levelname} {module} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "level": "INFO",
            "class": "logging.StreamHandler",
            "formatter": "simple",
        },
        "file": {
            "level": "INFO",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(LOGS_DIR / "accounts.log"),
            "maxBytes": 1024 * 1024 * 15,  # 15MB
            "backupCount": 5,
            "formatter": "verbose",
        },
        "core_file": {
            "level": "INFO",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(LOGS_DIR / "core.log"),
            "maxBytes": 1024 * 1024 * 10,  # 10MB
            "backupCount": 5,
            "formatter": "verbose",
        },
        "audit_file": {
            "level": "INFO",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(LOGS_DIR / "audit.log"),
            "maxBytes": 1024 * 1024 * 10,  # 10MB
            "backupCount": 10,
            "formatter": "audit",
        },
        "security_file": {
            "level": "WARNING",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(LOGS_DIR / "security.log"),
            "maxBytes": 1024 * 1024 * 5,  # 5MB
            "backupCount": 10,
            "formatter": "verbose",
        },
        "finance_file": {
            "level": "INFO",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(LOGS_DIR / "finance.log"),
            "maxBytes": 1024 * 1024 * 15,  # 15MB
            "backupCount": 10,
            "formatter": "verbose",
        },
        "exam_file": {
            "level": "INFO",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(LOGS_DIR / "exams.log"),
            "maxBytes": 1024 * 1024 * 10,  # 10MB
            "backupCount": 5,
            "formatter": "verbose",
        },
    },
    "loggers": {
        "django": {
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": True,
        },
        "accounts": {
            "handlers": ["file", "console"],
            "level": "INFO",
            "propagate": False,
        },
        "core": {
            "handlers": ["core_file", "console"],
            "level": "INFO",
            "propagate": True,
        },
        "core.services.audit": {
            "handlers": ["audit_file"],
            "level": "INFO",
            "propagate": False,
        },
        "core.services.security": {
            "handlers": ["security_file", "console"],
            "level": "WARNING",
            "propagate": False,
        },
        "finance": {
            "handlers": ["finance_file", "console"],
            "level": "INFO",
            "propagate": True,
        },
        "exams": {
            "handlers": ["exam_file", "console"],
            "level": "INFO",
            "propagate": True,
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "WARNING",
    },
}

# JWT Settings
from datetime import timedelta

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=60),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=1),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,
    "VERIFYING_KEY": None,
    "AUDIENCE": None,
    "ISSUER": None,
    "JWK_URL": None,
    "LEEWAY": 0,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "AUTH_HEADER_NAME": "HTTP_AUTHORIZATION",
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
    "USER_AUTHENTICATION_RULE": "rest_framework_simplejwt.authentication.default_user_authentication_rule",
    "AUTH_TOKEN_CLASSES": ("rest_framework_simplejwt.tokens.AccessToken",),
    "TOKEN_TYPE_CLAIM": "token_type",
    "TOKEN_USER_CLASS": "rest_framework_simplejwt.models.TokenUser",
    "JTI_CLAIM": "jti",
    "SLIDING_TOKEN_REFRESH_EXP_CLAIM": "refresh_exp",
    "SLIDING_TOKEN_LIFETIME": timedelta(minutes=60),
    "SLIDING_TOKEN_REFRESH_LIFETIME": timedelta(days=1),
}

# CORS settings
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = [
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]


# ==============================================================================
# CELERY SETTINGS (for async tasks)
# ==============================================================================

# Celery Configuration
CELERY_BROKER_URL = "redis://localhost:6379/0"
CELERY_RESULT_BACKEND = "redis://localhost:6379/0"
CELERY_ACCEPT_CONTENT = ["application/json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = "UTC"

# Celery Beat Schedule (for periodic tasks)
CELERY_BEAT_SCHEDULE = {
    "cleanup-expired-role-assignments": {
        "task": "accounts.tasks.cleanup_expired_role_assignments",
        "schedule": 3600.0,  # Run every hour
    },
    "cleanup-old-audit-logs": {
        "task": "accounts.tasks.cleanup_old_audit_logs",
        "schedule": 86400.0,  # Run daily
        "kwargs": {"retention_days": 365},
    },
    "cleanup-old-sessions": {
        "task": "accounts.tasks.cleanup_old_sessions",
        "schedule": 3600.0,  # Run every hour
        "kwargs": {"retention_days": 30},
    },
    "send-password-expiry-reminders": {
        "task": "accounts.tasks.send_password_expiry_reminders",
        "schedule": 86400.0,  # Run daily
    },
    "send-role-expiry-notifications": {
        "task": "accounts.tasks.send_role_expiry_notifications",
        "schedule": 86400.0,  # Run daily
    },
    "unlock-locked-accounts": {
        "task": "accounts.tasks.unlock_locked_accounts",
        "schedule": 1800.0,  # Run every 30 minutes
    },
    "send-login-alerts": {
        "task": "accounts.tasks.send_login_alerts",
        "schedule": 3600.0,  # Run every hour
    },
    """ SUBJECTS """
    "update-syllabus-completion": {
        "task": "subjects.tasks.update_syllabus_completion_percentages",
        "schedule": crontab(hour=2, minute=0),  # Daily at 2 AM
    },
    "check-syllabus-deadlines": {
        "task": "subjects.tasks.send_syllabus_deadline_alerts",
        "schedule": crontab(hour=8, minute=0),  # Daily at 8 AM
    },
    "weekly-curriculum-report": {
        "task": "subjects.tasks.generate_weekly_curriculum_report",
        "schedule": crontab(hour=6, minute=0, day_of_week=1),  # Monday at 6 AM
    },
    "cleanup-analytics-cache": {
        "task": "subjects.tasks.cleanup_old_analytics_cache",
        "schedule": crontab(hour=3, minute=0, day_of_week=0),  # Sunday at 3 AM
    },
}

ASSIGNMENTS_SETTINGS = {
    "MAX_FILE_SIZE_MB": 50,
    "ALLOWED_FILE_TYPES": ["pdf", "doc", "docx", "txt", "jpg", "jpeg", "png"],
    "DEFAULT_LATE_PENALTY": 10,  # Percentage
    "PLAGIARISM_THRESHOLD": 30,  # Percentage
    "AUTO_GRADE_ENABLED": False,
    "PEER_REVIEW_ENABLED": True,
    "NOTIFICATION_DAYS_BEFORE": 2,
    "BATCH_SIZE": 100,
}

# ==============================================================================
# UNIFIED AUTHENTICATION SETTINGS
# ==============================================================================

# Settings for the unified authentication system
UNIFIED_AUTH_SETTINGS = {
    # Identifier type priorities (lower number = higher priority)
    "IDENTIFIER_PRIORITIES": {
        "email": 1,
        "phone": 2,
        "admission_number": 3,
        "username": 4,
    },
    # Phone number settings
    "PHONE_NUMBER_SETTINGS": {
        "DEFAULT_COUNTRY_CODE": "+1",  # Adjust for your country
        "ALLOW_INTERNATIONAL": True,
        "MIN_LENGTH": 10,
        "MAX_LENGTH": 15,
        "NORMALIZE_FORMAT": True,
    },
    # Admission number settings
    "ADMISSION_NUMBER_SETTINGS": {
        "PATTERNS": [
            r"^[A-Z]{2,4}-\d{4}-[A-Z0-9]{3,8}$",  # STU-2024-ABC123
            r"^\d{4}[A-Z0-9]{3,8}$",  # 2024ABC123
            r"^[A-Z]{2,4}\d{4}[A-Z0-9]{3,8}$",  # STU2024ABC123
            r"^\d{7,12}$",  # 202400001
            r"^[A-Z]{2,4}/\d{4}/\d{3,6}$",  # STU/2024/001
        ],
        "CASE_SENSITIVE": False,
        "MIN_LENGTH": 3,
        "MAX_LENGTH": 20,
    },
    # Security settings
    "SECURITY_SETTINGS": {
        "LOG_ALL_ATTEMPTS": True,
        "LOG_SUCCESSFUL_LOGINS": True,
        "LOG_FAILED_ATTEMPTS": True,
        "ENABLE_RATE_LIMITING": True,
        "MAX_ATTEMPTS_PER_IP": 10,  # Per hour
        "LOCKOUT_DURATION": 3600,  # 1 hour in seconds
    },
    # User experience settings
    "UX_SETTINGS": {
        "SHOW_IDENTIFIER_TYPE": True,
        "PROVIDE_HINTS": True,
        "REMEMBER_LAST_IDENTIFIER_TYPE": True,
        "AUTO_DETECT_IDENTIFIER_TYPE": True,
    },
}
# ==============================================================================
# FEATURE FLAGS FOR AUTHENTICATION
# ==============================================================================

# Feature flags for authentication system
AUTH_FEATURE_FLAGS = {
    "UNIFIED_LOGIN": True,  # Enable unified login system
    "PHONE_LOGIN": True,  # Allow login with phone numbers
    "ADMISSION_LOGIN": False,  # Allow login with admission numbers
    "USERNAME_LOGIN": True,  # Allow login with usernames
    "EMAIL_LOGIN": True,  # Allow login with email addresses
    "REMEMBER_ME": True,  # Enable "remember me" functionality
    "ACCOUNT_LOCKOUT": True,  # Enable account lockout after failed attempts
    "DETAILED_LOGIN_LOGS": True,  # Log detailed authentication information
    "LOGIN_ATTEMPT_TRACKING": True,  # Track and store login attempts
    "SUSPICIOUS_ACTIVITY_DETECTION": False,  # Advanced threat detection
    "TWO_FACTOR_AUTH": False,  # Two-factor authentication (if implemented)
}

# ==============================================================================
# RATE LIMITING SETTINGS
# ==============================================================================

# Rate limiting for authentication endpoints
RATE_LIMITING = {
    "LOGIN_ATTEMPTS": {
        "RATE": "10/hour",  # 10 attempts per hour per IP
        "BURST": 3,  # Allow 3 rapid attempts initially
    },
    "PASSWORD_RESET": {
        "RATE": "5/hour",  # 5 password reset attempts per hour per IP
        "BURST": 1,
    },
    "ACCOUNT_CREATION": {
        "RATE": "3/hour",  # 3 account creations per hour per IP
        "BURST": 1,
    },
}

# ==============================================================================
# DEVELOPMENT/DEBUG SETTINGS
# ==============================================================================

if DEBUG:
    # Additional debug settings for authentication
    AUTH_FEATURE_FLAGS["DEBUG_AUTH_DETAILS"] = True

    # Log all authentication attempts in development
    UNIFIED_AUTH_SETTINGS["SECURITY_SETTINGS"]["LOG_ALL_ATTEMPTS"] = True

    # Relaxed rate limiting in development
    RATE_LIMITING["LOGIN_ATTEMPTS"]["RATE"] = "100/hour"

    # Allow easier testing
    MAX_FAILED_LOGIN_ATTEMPTS = 10
    ACCOUNT_LOCKOUT_DURATION = 5  # 5 minutes
