"""
Django App Configuration for Academics Module

This module configures the academics Django app and handles
initialization tasks including signal registration.
"""

from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class AcademicsConfig(AppConfig):
    """Configuration for the academics app"""

    default_auto_field = "django.db.models.BigAutoField"
    name = "src.academics"
    verbose_name = _("Academic Management")

    def ready(self):
        """
        Called when the app is ready. Used to import signal handlers
        and perform any other initialization tasks.
        """
        # Import signal handlers
        try:
            from . import signals
        except ImportError:
            pass

        # Register custom checks
        self.register_custom_checks()

        # Initialize default academic structure if needed
        self.initialize_defaults()

    def register_custom_checks(self):
        """Register custom system checks for the academics app"""
        from django.core.checks import register, Tags

        @register(Tags.models)
        def check_academic_year_consistency(app_configs, **kwargs):
            """Check for academic year data consistency"""
            from .models import AcademicYear, Term

            errors = []

            # Check for multiple current academic years
            current_years = AcademicYear.objects.filter(is_current=True).count()
            if current_years > 1:
                errors.append(
                    f"Multiple academic years marked as current: {current_years} found. "
                    "Only one academic year should be current at a time."
                )

            # Check for academic years without terms
            years_without_terms = AcademicYear.objects.filter(
                terms__isnull=True
            ).count()
            if years_without_terms > 0:
                errors.append(
                    f"{years_without_terms} academic year(s) have no terms defined. "
                    "Each academic year should have at least one term."
                )

            # Check for terms with invalid date ranges
            invalid_terms = Term.objects.filter(
                start_date__gte=models.F("end_date")
            ).count()
            if invalid_terms > 0:
                errors.append(
                    f"{invalid_terms} term(s) have invalid date ranges "
                    "(start date >= end date)."
                )

            return errors

        @register(Tags.models)
        def check_class_capacity_consistency(app_configs, **kwargs):
            """Check for class capacity issues"""
            from .models import Class

            warnings = []

            # Check for classes with zero capacity
            zero_capacity = Class.objects.filter(capacity=0, is_active=True).count()
            if zero_capacity > 0:
                warnings.append(
                    f"{zero_capacity} active class(es) have zero capacity. "
                    "Classes should have a positive capacity."
                )

            # Check for classes with very high capacity
            high_capacity = Class.objects.filter(
                capacity__gt=50, is_active=True
            ).count()
            if high_capacity > 0:
                warnings.append(
                    f"{high_capacity} class(es) have capacity > 50 students. "
                    "Consider reviewing if these capacities are appropriate."
                )

            return warnings

    def initialize_defaults(self):
        """Initialize default academic structure if needed"""
        # This could be used to create default sections, departments, etc.
        # For now, we'll just check if the app is properly configured
        pass


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
