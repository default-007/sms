from django.apps import AppConfig


class ApiConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "src.api"
    verbose_name = "API"

    def ready(self):
        # Import signals or perform other initialization
        pass
