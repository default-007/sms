from django.apps import AppConfig


class FinanceConfig(AppConfig):
    """Configuration for the finance app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "src.finance"
    verbose_name = "Finance Management"

    def ready(self):
        """Initialize app when Django starts."""
        # Import signals to ensure they are connected
        try:
            import finance.signals
        except ImportError:
            pass
