"""
Services module for subjects app.

This module contains business logic services for managing subjects,
syllabi, curriculum planning, analytics, and related operations.
"""

from .syllabus_service import SyllabusService
from .curriculum_service import CurriculumService
from .analytics_service import SubjectAnalyticsService

__all__ = [
    "SyllabusService",
    "CurriculumService",
    "SubjectAnalyticsService",
]
