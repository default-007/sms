from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class CoreConfig(AppConfig):
    """Configuration for the Core application."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "src.core"
    verbose_name = "Core System"

    def ready(self):
        """
        Initialize application during startup.
        """
        # Import any signals
        import src.core.signals

        # Use an atomic transaction to avoid issues during app startup
        from django.db import connection

        if connection.connection is not None:
            # Only run if database is ready
            from django.db.utils import ProgrammingError, OperationalError

            try:
                from django.core.management import call_command

                # Only check, don't create during startup
                from .models import SystemSetting

                if not SystemSetting.objects.exists():
                    self.stdout.write(
                        'No system settings found. Run "python manage.py init_settings" to initialize settings.'
                    )
            except (ProgrammingError, OperationalError):
                # Table doesn't exist yet, likely during migration
                pass
