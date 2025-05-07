from django.apps import AppConfig


class FinanceConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "src.finance"
    verbose_name = "Finance Management"

    def ready(self):
        import src.finance.signals
