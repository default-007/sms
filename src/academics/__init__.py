"""
Academics Module

A comprehensive Django app for managing academic structure including:
- Departments and academic organization
- Academic years and terms
- Sections, grades, and classes hierarchy
- Student enrollment and capacity management
- Academic analytics and reporting

Version: 1.0.0
Author: School Management System Team
"""

from .apps import AcademicsConfig

default_app_config = "academics.apps.AcademicsConfig"

__version__ = "1.0.0"
__author__ = "School Management System Team"

# Module metadata
__all__ = ["AcademicsConfig", "__version__", "__author__"]
