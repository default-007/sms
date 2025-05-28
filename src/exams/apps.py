from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class ExamsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "src.exams"
    verbose_name = "Examinations & Assessments"

    def ready(self):
        """Import signals when the app is ready"""
        import src.exams.signals
