from django.apps import AppConfig


class SchedulingConfig(AppConfig):
    """Scheduling module configuration"""

    default_auto_field = "django.db.models.BigAutoField"
    name = "src.scheduling"
    verbose_name = "Scheduling & Timetables"

    def ready(self):
        """Initialize scheduling module"""
        # Import signals to register them
        try:
            from . import signals
        except ImportError:
            pass

        # Register module permissions
        self._register_permissions()

        # Initialize scheduling constraints
        self._initialize_default_constraints()

    def _register_permissions(self):
        """Register module-specific permissions"""
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType
        from django.db import transaction

        permissions = [
            # Timetable permissions
            ("view_timetable_analytics", "Can view timetable analytics"),
            ("generate_timetable", "Can generate automated timetables"),
            ("optimize_timetable", "Can optimize timetable assignments"),
            ("copy_timetable", "Can copy timetables between terms"),
            ("bulk_edit_timetable", "Can bulk edit timetable entries"),
            # Room permissions
            ("manage_rooms", "Can manage room assignments"),
            ("view_room_utilization", "Can view room utilization reports"),
            ("book_special_rooms", "Can book special purpose rooms"),
            # Teacher permissions
            ("assign_substitute_teacher", "Can assign substitute teachers"),
            ("approve_substitutions", "Can approve substitute assignments"),
            ("view_teacher_workload", "Can view teacher workload analytics"),
            # Schedule permissions
            ("create_time_slots", "Can create and modify time slots"),
            ("manage_constraints", "Can manage scheduling constraints"),
            ("access_optimization", "Can access optimization features"),
            # Analytics permissions
            ("view_schedule_analytics", "Can view scheduling analytics"),
            ("export_timetables", "Can export timetable data"),
            ("generate_reports", "Can generate scheduling reports"),
        ]

        try:
            with transaction.atomic():
                # Get content type for the app
                app_content_type, created = ContentType.objects.get_or_create(
                    app_label="scheduling",
                    model="schedulingmodule",  # Dummy model for app-level permissions
                )

                for codename, name in permissions:
                    Permission.objects.get_or_create(
                        codename=codename, name=name, content_type=app_content_type
                    )
        except Exception as e:
            # Handle during migrations or when database is not ready
            pass

    def _initialize_default_constraints(self):
        """Initialize default scheduling constraints"""
        from django.db import transaction

        default_constraints = [
            {
                "name": "Core Subjects Morning Preference",
                "constraint_type": "time_preference",
                "parameters": {
                    "subjects": ["mathematics", "english", "science"],
                    "preferred_periods": [1, 2, 3],
                    "weight": 0.8,
                },
                "priority": 8,
                "is_hard_constraint": False,
                "is_active": True,
            },
            {
                "name": "Teacher Daily Limit",
                "constraint_type": "daily_limit",
                "parameters": {
                    "max_periods_per_day": 6,
                    "break_time_required": 30,  # minutes
                },
                "priority": 9,
                "is_hard_constraint": True,
                "is_active": True,
            },
            {
                "name": "Laboratory Double Periods",
                "constraint_type": "consecutive_periods",
                "parameters": {
                    "subjects": ["physics", "chemistry", "biology", "computer"],
                    "require_consecutive": True,
                    "min_duration": 90,  # minutes
                },
                "priority": 7,
                "is_hard_constraint": False,
                "is_active": True,
            },
            {
                "name": "Same Subject Daily Limit",
                "constraint_type": "daily_limit",
                "parameters": {
                    "max_same_subject_per_day": 2,
                    "exceptions": ["physical_education"],
                },
                "priority": 6,
                "is_hard_constraint": False,
                "is_active": True,
            },
            {
                "name": "Room Type Requirements",
                "constraint_type": "room_requirement",
                "parameters": {
                    "subject_room_mapping": {
                        "physics": ["laboratory"],
                        "chemistry": ["laboratory"],
                        "biology": ["laboratory"],
                        "computer": ["computer_lab"],
                        "physical_education": ["gymnasium", "outdoor"],
                        "music": ["music_room"],
                        "art": ["art_room"],
                    }
                },
                "priority": 9,
                "is_hard_constraint": True,
                "is_active": True,
            },
        ]

        try:
            with transaction.atomic():
                from .models import SchedulingConstraint

                for constraint_data in default_constraints:
                    SchedulingConstraint.objects.get_or_create(
                        name=constraint_data["name"], defaults=constraint_data
                    )
        except Exception as e:
            # Handle during migrations or when database is not ready
            pass
