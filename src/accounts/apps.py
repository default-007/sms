from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class AccountsConfig(AppConfig):
    """Configuration for the Accounts application."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "src.accounts"
    verbose_name = _("Accounts")

    def ready(self):
        """Import signals when app is ready."""
        import src.accounts.signals
