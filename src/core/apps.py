# core/apps.py
from django.apps import AppConfig
from django.db.models.signals import post_migrate
import logging

logger = logging.getLogger(__name__)


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "src.core"
    verbose_name = "Core System"

    def ready(self):
        """Initialize the core app"""
        try:
            # Import signals to register them
            from . import signals

            # Connect post-migration signal to initialize default settings
            post_migrate.connect(self.create_default_settings, sender=self)

            logger.info("Core app initialized successfully")

        except Exception as e:
            logger.error(f"Error initializing core app: {e}")

    def create_default_settings(self, sender, **kwargs):
        """Create default system settings after migrations"""
        try:
            from .services import ConfigurationService

            ConfigurationService.initialize_default_settings()
            logger.info("Default system settings initialized")

        except Exception as e:
            # Log error but don't fail app startup
            logger.error(f"Error initializing default settings: {str(e)}")

    @classmethod
    def ensure_required_groups(cls):
        """Ensure required user groups exist"""
        try:
            from django.contrib.auth.models import Group

            required_groups = [
                ("System Administrators", "Full system access"),
                ("School Administrators", "School-wide administration"),
                ("Teachers", "Teaching staff access"),
                ("Parents", "Parent portal access"),
                ("Students", "Student portal access"),
                ("Staff", "General staff access"),
            ]

            created_count = 0
            for group_name, description in required_groups:
                group, created = Group.objects.get_or_create(name=group_name)
                if created:
                    created_count += 1

            if created_count > 0:
                logger.info(f"Created {created_count} user groups")

        except Exception as e:
            logger.error(f"Error creating user groups: {e}")

    @classmethod
    def setup_cache_configuration(cls):
        """Setup cache configuration if not already configured"""
        try:
            from django.conf import settings
            from django.core.cache import cache

            # Test cache connectivity
            cache.set("core_cache_test", "test_value", 30)
            test_value = cache.get("core_cache_test")

            if test_value == "test_value":
                logger.info("Cache system is working properly")
                cache.delete("core_cache_test")
            else:
                logger.warning("Cache system may not be working properly")

        except Exception as e:
            logger.warning(f"Cache configuration issue: {e}")

    @classmethod
    def verify_database_configuration(cls):
        """Verify database configuration"""
        try:
            from django.db import connection

            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                result = cursor.fetchone()

            if result and result[0] == 1:
                logger.info("Database connection verified")
            else:
                logger.warning("Database connection verification failed")

        except Exception as e:
            logger.error(f"Database configuration error: {e}")

    @classmethod
    def initialize_system_health_monitoring(cls):
        """Initialize system health monitoring"""
        try:
            from .services import ConfigurationService

            # Check if system health monitoring is enabled
            monitoring_enabled = ConfigurationService.get_setting(
                "system.health_monitoring_enabled", True
            )

            if monitoring_enabled:
                logger.info("System health monitoring initialized")

                # Here you would typically start background monitoring tasks
                # For example, with Celery:
                # from .tasks import start_health_monitoring
                # start_health_monitoring.delay()

        except Exception as e:
            logger.error(f"Error initializing health monitoring: {e}")

    @classmethod
    def setup_logging_configuration(cls):
        """Setup additional logging configuration"""
        try:
            import logging.config
            from django.conf import settings

            # Configure core-specific loggers if not already configured
            core_logger_config = {
                "version": 1,
                "disable_existing_loggers": False,
                "formatters": {
                    "core_formatter": {
                        "format": "[CORE] {levelname} {asctime} {module} {message}",
                        "style": "{",
                    },
                },
                "handlers": {
                    "core_console": {
                        "level": "INFO",
                        "class": "logging.StreamHandler",
                        "formatter": "core_formatter",
                    },
                },
                "loggers": {
                    "src.core": {
                        "handlers": ["core_console"],
                        "level": "INFO",
                        "propagate": True,
                    },
                },
            }

            # Only apply if not already configured
            if not hasattr(
                settings, "LOGGING"
            ) or "src.core" not in settings.LOGGING.get("loggers", {}):
                logging.config.dictConfig(core_logger_config)
                logger.info("Core logging configuration applied")

        except Exception as e:
            logger.warning(f"Error setting up logging configuration: {e}")

    @classmethod
    def validate_required_dependencies(cls):
        """Validate that required dependencies are available"""
        try:
            required_packages = [
                "django",
                "djangorestframework",
                "django_filters",
                "django_extensions",
            ]

            missing_packages = []
            for package in required_packages:
                try:
                    __import__(package.replace("-", "_"))
                except ImportError:
                    missing_packages.append(package)

            if missing_packages:
                logger.warning(
                    f"Missing optional packages: {', '.join(missing_packages)}"
                )
            else:
                logger.info("All required dependencies are available")

        except Exception as e:
            logger.error(f"Error validating dependencies: {e}")

    @classmethod
    def run_system_checks(cls):
        """Run comprehensive system checks"""
        try:
            logger.info("Running core system checks...")

            # Check database
            cls.verify_database_configuration()

            # Check cache
            cls.setup_cache_configuration()

            # Check dependencies
            cls.validate_required_dependencies()

            # Ensure groups exist
            cls.ensure_required_groups()

            # Initialize monitoring
            cls.initialize_system_health_monitoring()

            # Setup logging
            cls.setup_logging_configuration()

            logger.info("Core system checks completed")

        except Exception as e:
            logger.error(f"Error during system checks: {e}")

    def __str__(self):
        return "Core System Configuration"
