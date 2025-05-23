from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class ExamsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "src.exams"
    verbose_name = _("Examinations")

    def ready(self):
        import src.exams.signals
