# students/apps.py
from django.apps import AppConfig


class StudentsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "src.students"
    verbose_name = "Student Management"

    def ready(self):
        import src.students.signals  # Make sure this line exists

        try:
            # Initialize analytics cache on startup
            from .services.analytics_service import StudentAnalyticsService

            StudentAnalyticsService.clear_analytics_cache()
        except Exception:
            pass  # Ignore errors during startu
