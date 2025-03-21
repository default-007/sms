"""
Testing settings for School Management System.
"""

from .base import *

# Use in-memory SQLite database for testing
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

# Use console email backend for testing
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Disable password hashing to speed up tests
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

# Simplified password validation for testing
AUTH_PASSWORD_VALIDATORS = []

# Turn off logging during tests
LOGGING = {
    "version": 1,
    "disable_existing_loggers": True,
}

# Use a faster test runner
TEST_RUNNER = "django.test.runner.DiscoverRunner"
