# apps.py
from django.apps import AppConfig
from django.db.models.signals import post_migrate


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"
    verbose_name = "Core System"

    def ready(self):
        """Initialize the core app"""
        # Import signals to register them
        from . import signals

        # Connect post-migration signal to initialize default settings
        post_migrate.connect(self.create_default_settings, sender=self)

    def create_default_settings(self, sender, **kwargs):
        """Create default system settings after migrations"""
        from .services import ConfigurationService

        try:
            ConfigurationService.initialize_default_settings()
        except Exception as e:
            # Log error but don't fail app startup
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"Error initializing default settings: {str(e)}")
