"""
Configuration settings for the scheduling module
"""

from django.conf import settings
from datetime import time


class SchedulingConfig:
    """
    Configuration class for scheduling module settings
    """

    # Default time slot configuration
    DEFAULT_SCHOOL_START_TIME = time(8, 0)
    DEFAULT_SCHOOL_END_TIME = time(15, 30)
    DEFAULT_PERIOD_DURATION = 45  # minutes
    DEFAULT_BREAK_DURATION = 15  # minutes
    DEFAULT_LUNCH_DURATION = 45  # minutes
    DEFAULT_LUNCH_AFTER_PERIOD = 4

    # Working days (0=Monday, 6=Sunday)
    DEFAULT_WORKING_DAYS = [0, 1, 2, 3, 4]  # Monday to Friday

    # Optimization settings
    OPTIMIZATION_DEFAULTS = {
        "genetic_algorithm": {
            "population_size": 50,
            "generations": 100,
            "mutation_rate": 0.1,
            "crossover_rate": 0.8,
            "tournament_size": 3,
            "elite_size": 5,
        },
        "greedy_algorithm": {
            "priority_weights": {
                "teacher_preference": 0.3,
                "room_suitability": 0.3,
                "time_preference": 0.2,
                "constraint_satisfaction": 0.2,
            }
        },
        "general": {
            "max_execution_time": 3600,  # 1 hour
            "convergence_threshold": 0.01,
            "max_retries": 3,
        },
    }

    # Analytics settings
    ANALYTICS_CONFIG = {
        "cache_duration": 900,  # 15 minutes
        "history_retention_days": 90,
        "performance_thresholds": {
            "good_optimization_score": 85.0,
            "acceptable_optimization_score": 70.0,
            "good_utilization_rate": 80.0,
            "acceptable_utilization_rate": 60.0,
        },
        "report_generation": {
            "weekly_reports": True,
            "monthly_reports": True,
            "term_reports": True,
        },
    }

    # Conflict resolution settings
    CONFLICT_RESOLUTION = {
        "auto_resolve_minor_conflicts": True,
        "conflict_priority_order": [
            "teacher_conflicts",
            "room_conflicts",
            "class_conflicts",
            "constraint_violations",
        ],
        "resolution_strategies": {
            "teacher_conflicts": "find_alternative_time",
            "room_conflicts": "find_alternative_room",
            "class_conflicts": "adjust_schedule",
        },
    }

    # Notification settings
    NOTIFICATION_CONFIG = {
        "send_conflict_alerts": True,
        "send_generation_completion": True,
        "send_substitute_reminders": True,
        "send_weekly_reports": True,
        "email_notifications": True,
        "sms_notifications": False,
        "push_notifications": True,
    }

    # Cache settings
    CACHE_CONFIG = {
        "timetable_cache_duration": 1800,  # 30 minutes
        "analytics_cache_duration": 900,  # 15 minutes
        "room_availability_cache_duration": 300,  # 5 minutes
        "teacher_availability_cache_duration": 300,  # 5 minutes
        "use_redis_cache": True,
        "cache_key_prefix": "scheduling:",
    }

    # API settings
    API_CONFIG = {
        "pagination_size": 25,
        "max_pagination_size": 100,
        "rate_limiting": {
            "optimization_requests": {"max_requests": 5, "time_window": 3600},  # 1 hour
            "bulk_operations": {"max_requests": 10, "time_window": 3600},
        },
        "export_formats": ["csv", "json", "pdf", "xlsx"],
        "max_export_records": 10000,
    }

    # Security settings
    SECURITY_CONFIG = {
        "require_authentication": True,
        "require_staff_for_generation": True,
        "audit_all_operations": True,
        "log_sensitive_operations": True,
        "session_timeout": 3600,  # 1 hour
        "max_concurrent_generations": 2,
    }

    # Subject configuration
    SUBJECT_CONFIG = {
        "default_periods_per_week": {
            "Mathematics": 6,
            "English": 5,
            "Science": 5,
            "Physics": 4,
            "Chemistry": 4,
            "Biology": 4,
            "Social Studies": 4,
            "History": 3,
            "Geography": 3,
            "Computer Science": 3,
            "Physical Education": 3,
            "Art": 2,
            "Music": 2,
        },
        "subject_priorities": {
            "Mathematics": 9,
            "English": 9,
            "Science": 8,
            "Physics": 8,
            "Chemistry": 8,
            "Biology": 8,
            "Social Studies": 7,
            "History": 6,
            "Geography": 6,
            "Computer Science": 6,
            "Physical Education": 5,
            "Art": 4,
            "Music": 4,
        },
        "lab_subjects": ["Physics", "Chemistry", "Biology", "Computer Science"],
        "consecutive_period_subjects": [
            "Physics",
            "Chemistry",
            "Biology",
            "Computer Science",
            "Art",
        ],
    }

    # Room configuration
    ROOM_CONFIG = {
        "default_capacities": {
            "classroom": 30,
            "laboratory": 25,
            "computer_lab": 25,
            "library": 50,
            "gymnasium": 100,
            "auditorium": 200,
            "music_room": 20,
            "art_room": 25,
        },
        "required_equipment": {
            "laboratory": ["safety_equipment", "laboratory_equipment"],
            "computer_lab": ["computers", "projector"],
            "gymnasium": ["sports_equipment"],
            "music_room": ["piano", "sound_system"],
            "art_room": ["art_supplies", "easels"],
        },
        "utilization_targets": {
            "minimum": 50.0,  # %
            "optimal": 75.0,  # %
            "maximum": 90.0,  # %
        },
    }

    # Teacher configuration
    TEACHER_CONFIG = {
        "max_periods_per_day": 6,
        "max_consecutive_periods": 3,
        "min_break_between_periods": 0,  # periods
        "max_classes_per_teacher": 8,
        "max_subjects_per_teacher": 3,
        "workload_balance_threshold": 0.2,  # 20% deviation
    }

    # Performance settings
    PERFORMANCE_CONFIG = {
        "slow_query_threshold": 1.0,  # seconds
        "memory_usage_warning": 1024,  # MB
        "optimization_timeout": 1800,  # 30 minutes
        "max_concurrent_users": 50,
        "database_connection_pool_size": 10,
    }

    # Backup and maintenance
    MAINTENANCE_CONFIG = {
        "auto_backup_enabled": True,
        "backup_frequency": "daily",
        "backup_retention_days": 30,
        "maintenance_window": {
            "start_time": time(2, 0),  # 2:00 AM
            "duration_hours": 2,
        },
        "auto_cleanup_old_data": True,
        "cleanup_retention_days": 365,
    }

    @classmethod
    def get_setting(cls, setting_name, default=None):
        """
        Get a configuration setting with fallback to Django settings

        Args:
            setting_name: Name of the setting
            default: Default value if not found

        Returns:
            Setting value
        """
        # Check Django settings first
        django_setting_name = f"SCHEDULING_{setting_name.upper()}"
        if hasattr(settings, django_setting_name):
            return getattr(settings, django_setting_name)

        # Check class attributes
        if hasattr(cls, setting_name.upper()):
            return getattr(cls, setting_name.upper())

        return default

    @classmethod
    def update_from_settings(cls):
        """Update configuration from Django settings"""

        if hasattr(settings, "SCHEDULING_CONFIG"):
            config = settings.SCHEDULING_CONFIG

            for section, values in config.items():
                section_attr = f"{section.upper()}_CONFIG"
                if hasattr(cls, section_attr):
                    current_config = getattr(cls, section_attr)
                    current_config.update(values)
                    setattr(cls, section_attr, current_config)

    @classmethod
    def get_optimization_config(cls, algorithm="genetic"):
        """Get optimization configuration for specific algorithm"""

        base_config = cls.OPTIMIZATION_DEFAULTS.get("general", {})
        algo_config = cls.OPTIMIZATION_DEFAULTS.get(f"{algorithm}_algorithm", {})

        return {**base_config, **algo_config}

    @classmethod
    def get_subject_periods_per_week(cls, subject_name):
        """Get default periods per week for a subject"""

        return cls.SUBJECT_CONFIG["default_periods_per_week"].get(
            subject_name, 4  # Default 4 periods
        )

    @classmethod
    def get_subject_priority(cls, subject_name):
        """Get priority level for a subject"""

        return cls.SUBJECT_CONFIG["subject_priorities"].get(
            subject_name, 5  # Default priority
        )

    @classmethod
    def is_lab_subject(cls, subject_name):
        """Check if subject requires laboratory facilities"""

        return subject_name in cls.SUBJECT_CONFIG["lab_subjects"]

    @classmethod
    def requires_consecutive_periods(cls, subject_name):
        """Check if subject requires consecutive periods"""

        return subject_name in cls.SUBJECT_CONFIG["consecutive_period_subjects"]

    @classmethod
    def get_room_capacity(cls, room_type):
        """Get default capacity for room type"""

        return cls.ROOM_CONFIG["default_capacities"].get(room_type, 30)

    @classmethod
    def get_required_equipment(cls, room_type):
        """Get required equipment for room type"""

        return cls.ROOM_CONFIG["required_equipment"].get(room_type, [])

    @classmethod
    def get_cache_duration(cls, cache_type):
        """Get cache duration for specific type"""

        cache_durations = {
            "timetable": cls.CACHE_CONFIG["timetable_cache_duration"],
            "analytics": cls.CACHE_CONFIG["analytics_cache_duration"],
            "room_availability": cls.CACHE_CONFIG["room_availability_cache_duration"],
            "teacher_availability": cls.CACHE_CONFIG[
                "teacher_availability_cache_duration"
            ],
        }

        return cache_durations.get(cache_type, 300)  # Default 5 minutes

    @classmethod
    def is_notification_enabled(cls, notification_type):
        """Check if notification type is enabled"""

        return cls.NOTIFICATION_CONFIG.get(notification_type, False)

    @classmethod
    def get_performance_threshold(cls, metric_name):
        """Get performance threshold for metric"""

        return cls.ANALYTICS_CONFIG["performance_thresholds"].get(metric_name, 0)

    @classmethod
    def validate_config(cls):
        """Validate configuration settings"""

        errors = []
        warnings = []

        # Validate time settings
        if cls.DEFAULT_SCHOOL_START_TIME >= cls.DEFAULT_SCHOOL_END_TIME:
            errors.append("School start time must be before end time")

        # Validate optimization settings
        genetic_config = cls.OPTIMIZATION_DEFAULTS["genetic_algorithm"]
        if genetic_config["population_size"] < 10:
            warnings.append("Small population size may affect optimization quality")

        if genetic_config["mutation_rate"] > 0.5:
            warnings.append("High mutation rate may prevent convergence")

        # Validate teacher settings
        if cls.TEACHER_CONFIG["max_periods_per_day"] > 8:
            warnings.append("High maximum periods per day may cause teacher fatigue")

        # Validate room utilization targets
        room_targets = cls.ROOM_CONFIG["utilization_targets"]
        if room_targets["minimum"] >= room_targets["optimal"]:
            errors.append("Minimum utilization must be less than optimal")

        if room_targets["optimal"] >= room_targets["maximum"]:
            errors.append("Optimal utilization must be less than maximum")

        return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}

    @classmethod
    def export_config(cls):
        """Export current configuration as dictionary"""

        config = {}

        for attr_name in dir(cls):
            if attr_name.endswith("_CONFIG") or attr_name.startswith("DEFAULT_"):
                config[attr_name] = getattr(cls, attr_name)

        return config

    @classmethod
    def import_config(cls, config_dict):
        """Import configuration from dictionary"""

        for key, value in config_dict.items():
            if hasattr(cls, key):
                setattr(cls, key, value)


# Initialize configuration from Django settings on import
SchedulingConfig.update_from_settings()


# Convenience functions for accessing configuration
def get_scheduling_config(section=None):
    """Get scheduling configuration section or all configuration"""

    if section:
        section_attr = f"{section.upper()}_CONFIG"
        return getattr(SchedulingConfig, section_attr, {})

    return SchedulingConfig.export_config()


def update_scheduling_config(updates):
    """Update scheduling configuration"""

    SchedulingConfig.import_config(updates)


def validate_scheduling_config():
    """Validate current scheduling configuration"""

    return SchedulingConfig.validate_config()


# Default Django settings that can be used in settings.py
SCHEDULING_DJANGO_SETTINGS = {
    "SCHEDULING_CONFIG": {
        "optimization": {
            "genetic_algorithm": {"population_size": 50, "generations": 100}
        },
        "analytics": {"cache_duration": 900},
        "notifications": {"email_notifications": True, "send_weekly_reports": True},
    },
    "SCHEDULING_CACHE_TIMEOUT": 900,
    "SCHEDULING_OPTIMIZATION_TIMEOUT": 1800,
    "SCHEDULING_MAX_CONCURRENT_GENERATIONS": 2,
    "SCHEDULING_ENABLE_AUDIT_LOGGING": True,
    "SCHEDULING_SLOW_REQUEST_THRESHOLD": 2.0,
    "CELERY_BEAT_SCHEDULE_SCHEDULING": {
        "daily-schedule-validation": {
            "task": "scheduling.tasks.daily_schedule_validation",
            "schedule": "0 6 * * *",
        },
        "substitute-reminders": {
            "task": "scheduling.tasks.send_substitute_reminders",
            "schedule": "0 18 * * *",
        },
        "weekly-analytics-report": {
            "task": "scheduling.tasks.weekly_analytics_report",
            "schedule": "0 8 * * 1",
        },
    },
}


# Export configuration for easy access in other modules
__all__ = [
    "SchedulingConfig",
    "get_scheduling_config",
    "update_scheduling_config",
    "validate_scheduling_config",
    "SCHEDULING_DJANGO_SETTINGS",
]
