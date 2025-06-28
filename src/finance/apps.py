from django.apps import AppConfig


class FinanceConfig(AppConfig):
    """Configuration for the finance app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "src.finance"
    verbose_name = "Finance Management"

    def ready(self):
        # Import signals only once
        if not hasattr(self, "_signals_imported"):
            try:
                import finance.signals  # noqa

                self._signals_imported = True
            except ImportError:
                pass
