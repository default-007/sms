from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class CommunicationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "src.communications"
    verbose_name = _("Communications")

    def ready(self):
        # Import signals to ensure they are registered
        import src.communications.signals
