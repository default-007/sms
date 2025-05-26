# Import all services for easy access
from .analytics_service import AssignmentAnalyticsService
from .assignment_service import AssignmentService
from .deadline_service import DeadlineService
from .grading_service import GradingService
from .plagiarism_service import PlagiarismService
from .rubric_service import RubricService
from .submission_service import SubmissionService

__all__ = [
    "AssignmentService",
    "SubmissionService",
    "GradingService",
    "PlagiarismService",
    "DeadlineService",
    "RubricService",
    "AssignmentAnalyticsService",
]

"""
Assignments Services Module

This module provides a comprehensive set of services for managing assignments,
submissions, grading, and analytics in the school management system.

Services Overview:
- AssignmentService: Core assignment lifecycle management
- SubmissionService: Student submission handling
- GradingService: Teacher grading and feedback
- PlagiarismService: Content similarity detection
- DeadlineService: Deadline management and notifications
- RubricService: Rubric-based assessment
- AssignmentAnalyticsService: Performance analytics and insights

Usage:
    from assignments.services import AssignmentService, SubmissionService
    
    # Create assignment
    assignment = AssignmentService.create_assignment(teacher, data)
    
    # Handle submission
    submission = SubmissionService.create_submission(student, assignment_id, data)
    
    # Grade submission
    graded = GradingService.grade_submission(submission_id, teacher, grading_data)
"""
