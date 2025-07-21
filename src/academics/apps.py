"""
Django App Configuration for Academics Module

This module configures the academics Django app and handles
initialization tasks including signal registration.
"""

import logging
from django.apps import AppConfig
from django.core.checks import register, Warning, Error, Tags

logger = logging.getLogger(__name__)

from django.utils.translation import gettext_lazy as _


class AcademicsConfig(AppConfig):
    """Configuration for the academics app"""

    default_auto_field = "django.db.models.BigAutoField"
    name = "src.academics"
    verbose_name = _("Academic Management")

    def ready(self):
        """
        Called when Django starts up. Used to register signals and
        perform any necessary initialization.
        """
        if not hasattr(self, "_ready_called"):
            try:
                # Import signals to register them
                from . import signals

                # Register custom system checks with proper tags
                register(Tags.models, Tags.database)(
                    self.check_academic_structure_consistency
                )

                logger.info("Academics app initialized successfully")

                self._ready_called = True

            except ImportError as e:
                logger.warning(f"Could not import academics signals: {e}")
            except Exception as e:
                logger.error(f"Error initializing academics app: {e}")

    def check_academic_structure_consistency(self, app_configs, **kwargs):
        """
        Custom Django system check for academic structure consistency.

        NOTE: This runs during system checks, so we need to handle the case
        where database tables might not exist yet (e.g., before migrations).
        """
        errors = []

        try:
            # Check if the database tables exist before running queries
            from django.db import connection

            table_names = connection.introspection.table_names()
            required_tables = [
                "academics_section",
                "academics_grade",
                "academics_class",
            ]

            # Only run checks if all required tables exist
            if not all(table in table_names for table in required_tables):
                # Tables don't exist yet (probably before migrations)
                return errors

            # Now it's safe to import models and run queries
            from .models import Section, Grade, Class

            # Check for classes with zero capacity
            zero_capacity_classes = Class.objects.filter(capacity=0).count()
            if zero_capacity_classes > 0:
                errors.append(
                    Warning(
                        f"{zero_capacity_classes} classes have zero capacity",
                        hint="Consider setting appropriate capacity values for all classes",
                        id="academics.W001",
                    )
                )

            # Check for grades without classes
            grades_without_classes = (
                Grade.objects.filter(classes__isnull=True).distinct().count()
            )
            if grades_without_classes > 0:
                errors.append(
                    Warning(
                        f"{grades_without_classes} grades have no classes assigned",
                        hint="Consider creating classes for all grades",
                        id="academics.W002",
                    )
                )

        except Exception as e:
            # If there's any error during checks, log it but don't crash Django
            logger.warning(f"Could not run academic structure checks: {e}")

        return errors

    @property
    def permissions(self):
        """
        Define custom permissions for the academics module.
        """
        return [
            ("view_all_academics", "Can view all academic structures"),
            ("manage_sections", "Can create and manage sections"),
            ("manage_grades", "Can create and manage grades"),
            ("manage_classes", "Can create and manage classes"),
            ("manage_academic_years", "Can manage academic years"),
            ("manage_terms", "Can manage terms"),
            ("view_analytics", "Can view academic analytics"),
            ("export_data", "Can export academic data"),
            ("bulk_operations", "Can perform bulk operations"),
        ]

    @property
    def default_settings(self):
        """
        Default settings for the academics module.
        """
        return {
            "ACADEMICS_DEFAULT_TERMS_PER_YEAR": 3,
            "ACADEMICS_DEFAULT_CLASS_CAPACITY": 30,
            "ACADEMICS_AUTO_GENERATE_CLASS_NAMES": True,
            "ACADEMICS_SECTION_COLORS": {
                "Lower Primary": "#FF6B6B",
                "Upper Primary": "#4ECDC4",
                "Secondary": "#45B7D1",
                "Senior Secondary": "#96CEB4",
            },
            "ACADEMICS_GRADE_PROGRESSION_RULES": {
                "min_attendance_percentage": 75,
                "min_passing_grade": 40,
                "allow_grade_skip": False,
            },
        }

    def get_menu_items(self):
        """
        Return menu items for the academics module.
        """
        return [
            {
                "name": "Academic Structure",
                "icon": "fas fa-graduation-cap",
                "url": "academics:dashboard",
                "permission": "academics.view_section",
                "children": [
                    {
                        "name": "Sections",
                        "url": "academics:section_list",
                        "permission": "academics.view_section",
                    },
                    {
                        "name": "Grades",
                        "url": "academics:grade_list",
                        "permission": "academics.view_grade",
                    },
                    {
                        "name": "Classes",
                        "url": "academics:class_list",
                        "permission": "academics.view_class",
                    },
                    {
                        "name": "Academic Years",
                        "url": "academics:academic_year_list",
                        "permission": "academics.view_academicyear",
                    },
                    {
                        "name": "Terms",
                        "url": "academics:term_list",
                        "permission": "academics.view_term",
                    },
                ],
            }
        ]

    def get_dashboard_widgets(self, user):
        """
        Return dashboard widgets for different user types.
        """
        widgets = []

        if user.has_perm("academics.view_section"):
            widgets.extend(
                [
                    {
                        "title": "Academic Structure Overview",
                        "template": "academics/widgets/structure_overview.html",
                        "context_processor": "academics.context_processors.structure_overview",
                        "size": "col-md-6",
                        "order": 5,
                    },
                    {
                        "title": "Current Term Info",
                        "template": "academics/widgets/current_term.html",
                        "context_processor": "academics.context_processors.current_term_info",
                        "size": "col-md-6",
                        "order": 6,
                    },
                ]
            )

        return widgets


# App metadata
__version__ = "1.0.0"
__author__ = "School Management System Team"
__email__ = "developers@schoolsms.com"

# Feature flags for the app
FEATURES = {
    "multi_academic_years": True,
    "flexible_terms": True,
    "section_hierarchy": True,
    "age_requirements": True,
    "class_capacity_limits": True,
    "teacher_assignments": True,
    "analytics_integration": True,
}


def get_app_info():
    """
    Get information about the academics app

    Returns:
        Dictionary containing app metadata
    """
    return {
        "name": "Academic Management",
        "version": __version__,
        "author": __author__,
        "email": __email__,
        "features": FEATURES,
        "models": ["Department", "AcademicYear", "Term", "Section", "Grade", "Class"],
        "services": [
            "AcademicYearService",
            "SectionService",
            "GradeService",
            "ClassService",
            "TermService",
        ],
    }


def check_app_requirements():
    """
    Check if all required dependencies are available

    Returns:
        Dictionary with check results
    """
    requirements = {
        "django": True,
        "teachers_app": False,
        "students_app": False,
        "users_app": False,
    }

    try:
        import django

        requirements["django"] = True
    except ImportError:
        requirements["django"] = False

    try:
        from django.apps import apps

        # Check for related apps
        if apps.is_installed("teachers"):
            requirements["teachers_app"] = True

        if apps.is_installed("students"):
            requirements["students_app"] = True

        if apps.is_installed("accounts"):
            requirements["users_app"] = True

    except Exception:
        pass

    return {
        "requirements": requirements,
        "all_met": all(requirements.values()),
        "missing": [k for k, v in requirements.items() if not v],
    }
