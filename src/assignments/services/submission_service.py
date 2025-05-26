from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db.models import Q, Count, Avg, Sum, Max, Min
from typing import Dict, List, Optional, Tuple
import logging
import os

from ..models import Assignment, AssignmentSubmission
from students.models import Student

logger = logging.getLogger(__name__)


class SubmissionService:
    """
    Service class for managing assignment submissions
    """

    @staticmethod
    def create_submission(
        student, assignment_id: int, data: Dict
    ) -> AssignmentSubmission:
        """
        Create or update a student submission
        """
        try:
            with transaction.atomic():
                assignment = Assignment.objects.get(id=assignment_id)

                # Validate assignment status
                if assignment.status != "published":
                    raise ValidationError("Assignment is not available for submission")

                # Check if submission already exists
                submission, created = AssignmentSubmission.objects.get_or_create(
                    assignment=assignment, student=student, defaults=data
                )

                if not created:
                    # Update existing submission
                    if submission.status == "graded":
                        raise ValidationError("Cannot modify graded submission")

                    # Track revision
                    submission.revision_count += 1
                    for field, value in data.items():
                        setattr(submission, field, value)

                # Validate file if provided
                if data.get("attachment"):
                    SubmissionService._validate_submission_file(
                        data["attachment"], assignment
                    )

                submission.submission_date = timezone.now()
                submission.status = "submitted"
                submission.save()

                logger.info(
                    f"Submission created/updated: {assignment.title} by {student.user.get_full_name()}"
                )
                return submission

        except Assignment.DoesNotExist:
            raise ValidationError("Assignment not found")
        except Exception as e:
            logger.error(f"Error creating submission: {str(e)}")
            raise

    @staticmethod
    def _validate_submission_file(file, assignment):
        """
        Validate submission file against assignment constraints
        """
        # Check file size
        max_size_bytes = assignment.max_file_size_mb * 1024 * 1024
        if file.size > max_size_bytes:
            raise ValidationError(
                f"File size exceeds {assignment.max_file_size_mb}MB limit"
            )

        # Check file type
        allowed_types = [
            ext.strip().lower() for ext in assignment.allowed_file_types.split(",")
        ]
        file_ext = os.path.splitext(file.name)[1][1:].lower()  # Remove the dot

        if file_ext not in allowed_types:
            raise ValidationError(
                f"File type '{file_ext}' not allowed. Allowed types: {', '.join(allowed_types)}"
            )

    @staticmethod
    def get_student_submissions(student, filters: Dict = None) -> Dict:
        """
        Get submissions for a student with optional filters
        """
        try:
            queryset = AssignmentSubmission.objects.filter(student=student)

            if filters:
                if filters.get("status"):
                    queryset = queryset.filter(status=filters["status"])
                if filters.get("subject"):
                    queryset = queryset.filter(assignment__subject=filters["subject"])
                if filters.get("term"):
                    queryset = queryset.filter(assignment__term=filters["term"])
                if filters.get("pending_only"):
                    queryset = queryset.filter(status__in=["submitted", "late"])

            submissions = queryset.select_related(
                "assignment__subject", "assignment__class_id", "graded_by__user"
            ).order_by("-submission_date")

            return {
                "submissions": submissions,
                "total_count": submissions.count(),
                "graded_count": submissions.filter(status="graded").count(),
                "pending_count": submissions.filter(
                    status__in=["submitted", "late"]
                ).count(),
                "late_count": submissions.filter(is_late=True).count(),
                "average_score": submissions.filter(
                    marks_obtained__isnull=False
                ).aggregate(avg=Avg("marks_obtained"))["avg"],
            }

        except Exception as e:
            logger.error(f"Error getting student submissions: {str(e)}")
            raise

    @staticmethod
    def get_assignment_submissions(assignment_id: int, filters: Dict = None) -> Dict:
        """
        Get all submissions for an assignment
        """
        try:
            assignment = Assignment.objects.get(id=assignment_id)
            queryset = assignment.submissions.all()

            if filters:
                if filters.get("status"):
                    queryset = queryset.filter(status=filters["status"])
                if filters.get("graded_only"):
                    queryset = queryset.filter(status="graded")
                if filters.get("ungraded_only"):
                    queryset = queryset.exclude(status="graded")
                if filters.get("late_only"):
                    queryset = queryset.filter(is_late=True)

            submissions = queryset.select_related(
                "student__user", "graded_by__user"
            ).order_by("student__user__last_name", "student__user__first_name")

            return {
                "assignment": assignment,
                "submissions": submissions,
                "total_count": submissions.count(),
                "graded_count": submissions.filter(status="graded").count(),
                "ungraded_count": submissions.exclude(status="graded").count(),
                "late_count": submissions.filter(is_late=True).count(),
            }

        except Assignment.DoesNotExist:
            raise ValidationError("Assignment not found")
        except Exception as e:
            logger.error(f"Error getting assignment submissions: {str(e)}")
            raise
