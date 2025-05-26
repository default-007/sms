"""
Services module for subjects app.

This module contains business logic services for managing subjects,
syllabi, curriculum planning, analytics, and related operations.
"""

from .analytics_service import SubjectAnalyticsService
from .curriculum_service import CurriculumService
from .syllabus_service import SyllabusService

__all__ = [
    "SyllabusService",
    "CurriculumService",
    "SubjectAnalyticsService",
]
