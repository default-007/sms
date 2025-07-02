"""
Base settings for School Management System.
"""

import os
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

CONTENT_SECURITY_POLICY = {
    "DIRECTIVES": {
        "default-src": ("'self'",),
        "script-src": (
            "'self'",
            "'unsafe-inline'",  # Needed for some Django admin and inline scripts
            "'unsafe-eval'",  # Needed for some JavaScript libraries
            "cdn.jsdelivr.net",
            "cdnjs.cloudflare.com",
            "unpkg.com",
            "code.jquery.com",  # jQuery
            "ajax.googleapis.com",  # Google Libraries
            "stackpath.bootstrapcdn.com",  # Bootstrap
            "maxcdn.bootstrapcdn.com",  # If using Bootstrap from here
            # Google Services (common sources of violations)
            "www.google-analytics.com",
            "www.googletagmanager.com",
            "www.google.com",  # reCAPTCHA
            "www.gstatic.com",
            "apis.google.com",
            # Social Media Widgets
            "connect.facebook.net",
            "platform.twitter.com",
            # Payment Processors
            "js.stripe.com",
            "checkout.stripe.com",
            # Common Widget Providers
            "widget.intercom.io",  # Intercom chat
            "js.driftt.com",  # Drift chat
            "static.hotjar.com",
            # Additional domains you might need
            "cdn.datatables.net",  # If using DataTables
            "chartjs-cdn.org",  # If using Chart.js
            "cdn.plot.ly",  # If using Plotly
            "d3js.org",  # If using D3.js
            "momentjs.com",  # If using Moment.js
            "cdn.tiny.cloud",
        ),
        "style-src": (
            "'self'",
            "'unsafe-inline'",  # Needed for Django admin and inline styles
            "cdn.jsdelivr.net",
            "cdnjs.cloudflare.com",
            "fonts.googleapis.com",  # Google Fonts CSS
            "unpkg.com",
            "stackpath.bootstrapcdn.com",  # Bootstrap CSS
            "maxcdn.bootstrapcdn.com",
        ),
        "font-src": (
            "'self'",
            "cdn.jsdelivr.net",
            "cdnjs.cloudflare.com",
            "fonts.googleapis.com",  # Google Fonts
            "fonts.gstatic.com",  # Google Fonts assets
        ),
        "img-src": (
            "'self'",
            "data:",  # Base64 images
            "blob:",  # Blob URLs
            "cdn.jsdelivr.net",
            "cdnjs.cloudflare.com",
            "www.google-analytics.com",  # Google Analytics tracking pixels
            "www.googletagmanager.com",
            # Add your media/image CDN domains here
        ),
        "connect-src": (
            "'self'",
            "api.iconify.design",
            "api.simplesvg.com",  # Add this line
            "api.unisvg.com",
            # Add API domains here if needed
        ),
        "media-src": ("'self'",),
        "object-src": ("'none'",),
        "base-uri": ("'self'",),
        "form-action": ("'self'",),
        # Optional: Force HTTPS in production
        # 'upgrade-insecure-requests': True,
    }
}

if DEBUG:
    CONTENT_SECURITY_POLICY["DIRECTIVES"].update(
        {
            "script-src": CONTENT_SECURITY_POLICY["DIRECTIVES"]["script-src"]
            + ("'unsafe-eval'",),  # Allow eval() for development tools
            "style-src": CONTENT_SECURITY_POLICY["DIRECTIVES"]["style-src"]
            + ("'unsafe-inline'",),  # Allow inline styles for development
        }
    )

    # Enable report-only mode for development testing
    # CONTENT_SECURITY_POLICY_REPORT_ONLY = True

# For production - more restrictive
else:
    # Remove unsafe-eval from production
    script_src = list(CONTENT_SECURITY_POLICY["DIRECTIVES"]["script-src"])
    if "'unsafe-eval'" in script_src:
        script_src.remove("'unsafe-eval'")

    CONTENT_SECURITY_POLICY["DIRECTIVES"]["script-src"] = tuple(script_src)

    # Force HTTPS in production
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


# Authentication backends
AUTHENTICATION_BACKENDS = [
    "src.accounts.authentication.UnifiedAuthenticationBackend",
    "django.contrib.auth.backends.ModelBackend",
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

# ==============================================================================
# CACHE SETTINGS
# ==============================================================================

# Cache configuration
# CACHES = {
#    "default": {
#        "BACKEND": "django.core.cache.backends.redis.RedisCache",
#        "LOCATION": "redis://127.0.0.1:6379/1",
#        "OPTIONS": {
#            "CLIENT_CLASS": "django_redis.client.DefaultClient",
#        },
#        "KEY_PREFIX": {
#            "sms",
#            "academics_cache",
#        },
#        "TIMEOUT": 300,  # 5 minutes default timeout
#    }
# }
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "unique-snowflake",
        "KEY_PREFIX": "sms_cache",  # Simple prefix without special characters
        "OPTIONS": {
            "MAX_ENTRIES": 1000,
            "CULL_FREQUENCY": 3,
        },
    }
}


# Cache key function to avoid special characters
def make_cache_key(key, key_prefix, version):
    """
    Generate cache key without special characters
    """
    import re

    # Remove special characters and replace with underscores
    clean_key = re.sub(r"[^a-zA-Z0-9_]", "_", str(key))
    return f"{key_prefix}:{version}:{clean_key}"


# Cache timeouts for specific functions
CACHE_TIMEOUTS = {
    "user_permissions": 3600,  # 1 hour
    "user_roles": 3600,  # 1 hour
    "role_statistics": 1800,  # 30 minutes
}


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

""" LOGGING = {
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
    },
    "filters": {
        "require_debug_false": {
            "()": "django.utils.log.RequireDebugFalse",
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
            "class": "logging.FileHandler",
            "filename": "logs/accounts.log",
            "formatter": "verbose",
        },
        "security_file": {
            "level": "WARNING",
            "class": "logging.FileHandler",
            "filename": "logs/security.log",
            "formatter": "verbose",
        },
        "mail_admins": {
            "level": "ERROR",
            "class": "django.utils.log.AdminEmailHandler",
            "filters": ["require_debug_false"],
            "formatter": "verbose",
        },
    },
    "loggers": {
        "accounts": {
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": True,
        },
        "accounts.security": {
            "handlers": ["security_file", "mail_admins"],
            "level": "WARNING",
            "propagate": False,
        },
        "accounts.tasks": {
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": True,
        },
        "csp": {
            "handlers": ["console", "file"],
            "level": "WARNING",
            "propagate": True,
        },
        "django.security": {
            "handlers": ["console", "file"],
            "level": "WARNING",
            "propagate": True,
        },
    },
} """
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
        },
    },
    "loggers": {
        "django.contrib.auth": {
            "handlers": ["console"],
            "level": "DEBUG",
            "propagate": True,
        },
        "accounts": {
            "handlers": ["console"],
            "level": "DEBUG",
            "propagate": True,
        },
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

AUTH_FEATURE_FLAGS = {
    "UNIFIED_LOGIN": True,
    "PHONE_LOGIN": True,
    "ADMISSION_LOGIN": True,
    "USERNAME_LOGIN": True,
    "EMAIL_LOGIN": True,
    "REMEMBER_ME": True,
    "ACCOUNT_LOCKOUT": True,
}

# Rate limiting settings
RATE_LIMITING = {
    "LOGIN_ATTEMPTS": {
        "RATE": "10/hour",
        "BURST": 3,
    },
}

# Session settings
REMEMBER_ME_DURATION = 1209600  # 2 weeks in seconds
