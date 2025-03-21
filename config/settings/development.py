"""
Development settings for School Management System.
"""

from .base import *

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

# Additional allowed hosts for development
ALLOWED_HOSTS = ["localhost", "127.0.0.1"]

# CORS settings for development
CORS_ALLOW_ALL_ORIGINS = True

# Email settings for development
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Development-specific middleware
MIDDLEWARE += [
    "debug_toolbar.middleware.DebugToolbarMiddleware",
]

# Development-specific apps
INSTALLED_APPS += [
    "debug_toolbar",
]

# Debug toolbar settings
INTERNAL_IPS = [
    "127.0.0.1",
]

# Simplified password validation for development
AUTH_PASSWORD_VALIDATORS = []

# Log SQL queries
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
        },
    },
    "loggers": {
        "django.db.backends": {
            "handlers": ["console"],
            "level": "DEBUG",
        },
    },
}
