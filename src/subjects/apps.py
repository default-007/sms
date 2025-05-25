from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class SubjectsConfig(AppConfig):
    """
    Configuration for the subjects application.

    This app handles subject management, syllabus planning, curriculum tracking,
    and related academic operations in the school management system.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "src.subjects"
    verbose_name = _("Subjects & Curriculum")

    def ready(self):
        """
        Initialize the app when Django starts.
        Import signals and perform any required setup.
        """
        try:
            # Import signals to ensure they are registered
            from . import signals
        except ImportError:
            # Signals module doesn't exist yet, which is fine
            pass

        # Register any additional app-specific setup here
        self._setup_default_permissions()

    def _setup_default_permissions(self):
        """
        Setup default permissions for the subjects app.
        This will be called when the app is ready.
        """
        # This could be used to create custom permissions
        # or perform other initialization tasks
        pass
