from django.apps import AppConfig


class FinanceConfig(AppConfig):
    """Configuration for the finance app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "src.finance"
    verbose_name = "Finance Management"

    def ready(self):
        # Use a flag to prevent multiple signal imports
        if hasattr(self, "_ready_called"):
            return

        try:
            # Import your existing signals file
            from . import signals  # noqa

            self._ready_called = True
        except ImportError:
            pass
