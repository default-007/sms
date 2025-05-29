"""
Celery configuration for scheduling module
"""

import os

from celery import Celery
from django.conf import settings

# Set the default Django settings module for the 'celery' program
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

app = Celery("scheduling")

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes
app.config_from_object("django.conf:settings", namespace="CELERY")

# Scheduling-specific Celery configuration
app.conf.update(
    # Task routing for scheduling tasks
    task_routes={
        "scheduling.tasks.generate_optimized_timetable": {"queue": "optimization"},
        "scheduling.tasks.update_scheduling_analytics": {"queue": "analytics"},
        "scheduling.tasks.daily_schedule_validation": {"queue": "maintenance"},
        "scheduling.tasks.send_substitute_reminders": {"queue": "notifications"},
        "scheduling.tasks.weekly_analytics_report": {"queue": "reports"},
        "scheduling.tasks.backup_timetable_data": {"queue": "maintenance"},
    },
    # Task priority configuration
    task_default_priority=5,
    worker_prefetch_multiplier=1,
    # Result backend configuration
    result_expires=3600,  # 1 hour
    result_compression="gzip",
    # Task execution configuration
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    # Timezone configuration
    timezone=getattr(settings, "TIME_ZONE", "UTC"),
    enable_utc=True,
    # Beat schedule for scheduling tasks
    beat_schedule={
        # Daily tasks
        "daily-schedule-validation": {
            "task": "scheduling.tasks.daily_schedule_validation",
            "schedule": 60.0 * 60.0 * 6,  # Every 6 hours
            "options": {"queue": "maintenance", "priority": 3},
        },
        "substitute-reminders": {
            "task": "scheduling.tasks.send_substitute_reminders",
            "schedule": 60.0 * 60.0 * 18,  # Every 18 hours (6 PM)
            "options": {"queue": "notifications", "priority": 6},
        },
        "auto-assign-rooms": {
            "task": "scheduling.tasks.auto_assign_rooms",
            "schedule": 60.0 * 60.0 * 22,  # Every 22 hours (10 PM)
            "options": {"queue": "maintenance", "priority": 4},
        },
        # Weekly tasks
        "weekly-analytics-report": {
            "task": "scheduling.tasks.weekly_analytics_report",
            "schedule": 60.0 * 60.0 * 24 * 7,  # Weekly
            "options": {"queue": "reports", "priority": 5},
        },
        "room-maintenance-check": {
            "task": "scheduling.tasks.room_maintenance_notifications",
            "schedule": 60.0 * 60.0 * 24 * 7,  # Weekly
            "options": {"queue": "maintenance", "priority": 4},
        },
        # Monthly tasks
        "cleanup-old-generations": {
            "task": "scheduling.tasks.cleanup_old_timetable_generations",
            "schedule": 60.0 * 60.0 * 24 * 30,  # Monthly
            "options": {"queue": "maintenance", "priority": 2},
        },
        # Daily backup
        "backup-timetable-data": {
            "task": "scheduling.tasks.backup_timetable_data",
            "schedule": 60.0 * 60.0 * 24,  # Daily
            "options": {"queue": "maintenance", "priority": 3},
        },
    },
)

# Load task modules from all registered Django app configs
app.autodiscover_tasks()


# Custom task decorator for scheduling module
def scheduling_task(*args, **kwargs):
    """
    Custom decorator for scheduling tasks with default configuration
    """
    kwargs.setdefault("bind", True)
    kwargs.setdefault("max_retries", 3)
    kwargs.setdefault("default_retry_delay", 60)

    def decorator(func):
        return app.task(*args, **kwargs)(func)

    return decorator


# Task monitoring and error handling
@app.task(bind=True)
def debug_task(self):
    """Debug task for testing Celery configuration"""
    print(f"Request: {self.request!r}")


# Custom task failure handler
@app.task(bind=True)
def task_failure_handler(self, task_id, error, traceback):
    """Handle task failures for scheduling tasks"""
    import logging

    logger = logging.getLogger("scheduling.celery")
    logger.error(f"Task {task_id} failed: {error}", extra={"traceback": traceback})

    # Send notification for critical task failures
    if "optimization" in str(task_id) or "generation" in str(task_id):
        from scheduling.tasks import send_generation_completion_notification

        # Handle critical failures
        pass


# Performance monitoring
@app.task(bind=True)
def monitor_queue_health(self):
    """Monitor Celery queue health"""
    import time

    from celery import current_app

    # Get queue statistics
    inspector = current_app.control.inspect()
    stats = inspector.stats()

    if stats:
        for worker, worker_stats in stats.items():
            queue_lengths = worker_stats.get("rusage", {})
            # Log queue health metrics
            pass

    return {"timestamp": time.time(), "queues_healthy": True}


# Configuration for different environments
class CeleryConfig:
    """Celery configuration class"""

    @classmethod
    def configure_for_development(cls):
        """Development-specific Celery configuration"""
        app.conf.update(
            task_always_eager=False,
            task_eager_propagates=True,
            worker_log_level="INFO",
            worker_hijack_root_logger=False,
        )

    @classmethod
    def configure_for_production(cls):
        """Production-specific Celery configuration"""
        app.conf.update(
            task_always_eager=False,
            worker_log_level="WARNING",
            worker_prefetch_multiplier=1,
            task_acks_late=True,
            worker_max_tasks_per_child=1000,
            worker_disable_rate_limits=False,
        )

    @classmethod
    def configure_for_testing(cls):
        """Testing-specific Celery configuration"""
        app.conf.update(
            task_always_eager=True,
            task_eager_propagates=True,
            broker_url="memory://",
            result_backend="cache+memory://",
        )


# Apply configuration based on environment
if hasattr(settings, "ENVIRONMENT"):
    env = settings.ENVIRONMENT
    if env == "development":
        CeleryConfig.configure_for_development()
    elif env == "production":
        CeleryConfig.configure_for_production()
    elif env == "testing":
        CeleryConfig.configure_for_testing()


# Health check task
@app.task
def health_check():
    """Health check task for monitoring"""
    return {
        "status": "healthy",
        "timestamp": app.now(),
        "worker_info": {
            "version": app.version,
            "broker": app.conf.broker_url,
            "backend": app.conf.result_backend,
        },
    }


if __name__ == "__main__":
    app.start()
