from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class ApiConfig(AppConfig):
    """Configuration for the API application."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "src.api"
    verbose_name = _("API")
