from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class CoreConfig(AppConfig):
    """Configuration for the Core application."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "src.core"
    verbose_name = "Core System"

    def ready(self):
        import src.core.signals
        from src.core.services import SystemSettingService

        # Initialize default settings
        try:
            SystemSettingService.initialize_default_settings()
        except Exception as e:
            # Handle initialization errors gracefully
            # This might occur during migrations
            pass
