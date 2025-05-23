# src/api/apps.py
"""API Application Configuration"""

from django.apps import AppConfig


class ApiConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "src.api"
    verbose_name = "API Infrastructure"

    def ready(self):
        """Initialize API configurations when app is ready"""
        # Import signal handlers
        from . import signals  # noqa

        # Register custom exception handlers
        from . import exceptions  # noqa
