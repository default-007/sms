from django.apps import AppConfig


class CoursesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "src.courses"
    verbose_name = "Courses & Classes"

    """ def ready(self):
        import src.courses.signals """
