from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class CoreConfig(AppConfig):
    """Configuration for the Core application."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "src.core"
    verbose_name = _("Core")

    def ready(self):
        """Register signals when the app is ready."""
        import src.core.signals
