from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db.models import Q, Count, Avg, Sum, Max, Min
from django.core.cache import cache
from typing import Dict, List, Optional
import logging

from ..models import Assignment, AssignmentSubmission

logger = logging.getLogger(__name__)


class AssignmentService:
    """
    Service class for managing assignment lifecycle and operations
    """

    @staticmethod
    def create_assignment(teacher, data: Dict) -> Assignment:
        """
        Create a new assignment with validation
        """
        try:
            with transaction.atomic():
                # Validate due date
                if data.get("due_date") and data["due_date"] <= timezone.now():
                    raise ValidationError("Due date must be in the future")

                # Validate passing marks
                if (
                    data.get("passing_marks")
                    and data.get("total_marks")
                    and data["passing_marks"] > data["total_marks"]
                ):
                    raise ValidationError("Passing marks cannot exceed total marks")

                # Create assignment
                assignment = Assignment.objects.create(teacher=teacher, **data)

                logger.info(
                    f"Assignment created: {assignment.title} by {teacher.user.get_full_name()}"
                )
                return assignment

        except Exception as e:
            logger.error(f"Error creating assignment: {str(e)}")
            raise

    @staticmethod
    def update_assignment(assignment_id: int, data: Dict) -> Assignment:
        """
        Update an existing assignment
        """
        try:
            with transaction.atomic():
                assignment = Assignment.objects.select_for_update().get(
                    id=assignment_id
                )

                # Prevent updates if assignment has submissions
                if assignment.submissions.exists() and "total_marks" in data:
                    raise ValidationError(
                        "Cannot change total marks after submissions exist"
                    )

                # Update fields
                for field, value in data.items():
                    setattr(assignment, field, value)

                assignment.full_clean()
                assignment.save()

                logger.info(f"Assignment updated: {assignment.title}")
                return assignment

        except Assignment.DoesNotExist:
            raise ValidationError("Assignment not found")
        except Exception as e:
            logger.error(f"Error updating assignment {assignment_id}: {str(e)}")
            raise

    @staticmethod
    def publish_assignment(assignment_id: int) -> Assignment:
        """
        Publish an assignment and notify students
        """
        try:
            with transaction.atomic():
                assignment = Assignment.objects.select_for_update().get(
                    id=assignment_id
                )

                if assignment.status != "draft":
                    raise ValidationError("Only draft assignments can be published")

                assignment.status = "published"
                assignment.published_at = timezone.now()
                assignment.save()

                # TODO: Send notifications to students
                # NotificationService.send_assignment_notification(assignment)

                logger.info(f"Assignment published: {assignment.title}")
                return assignment

        except Assignment.DoesNotExist:
            raise ValidationError("Assignment not found")
        except Exception as e:
            logger.error(f"Error publishing assignment {assignment_id}: {str(e)}")
            raise

    @staticmethod
    def close_assignment(assignment_id: int) -> Assignment:
        """
        Close an assignment to new submissions
        """
        try:
            with transaction.atomic():
                assignment = Assignment.objects.select_for_update().get(
                    id=assignment_id
                )

                if assignment.status != "published":
                    raise ValidationError("Only published assignments can be closed")

                assignment.status = "closed"
                assignment.save()

                logger.info(f"Assignment closed: {assignment.title}")
                return assignment

        except Assignment.DoesNotExist:
            raise ValidationError("Assignment not found")
        except Exception as e:
            logger.error(f"Error closing assignment {assignment_id}: {str(e)}")
            raise

    @staticmethod
    def duplicate_assignment(
        assignment_id: int, teacher, modifications: Dict = None
    ) -> Assignment:
        """
        Create a duplicate of an existing assignment
        """
        try:
            with transaction.atomic():
                original = Assignment.objects.get(id=assignment_id)

                # Create duplicate with new data
                duplicate_data = {
                    "title": f"{original.title} (Copy)",
                    "description": original.description,
                    "instructions": original.instructions,
                    "class_id": original.class_id,
                    "subject": original.subject,
                    "term": original.term,
                    "due_date": timezone.now()
                    + timezone.timedelta(days=7),  # Default to 1 week from now
                    "total_marks": original.total_marks,
                    "passing_marks": original.passing_marks,
                    "submission_type": original.submission_type,
                    "difficulty_level": original.difficulty_level,
                    "allow_late_submission": original.allow_late_submission,
                    "late_penalty_percentage": original.late_penalty_percentage,
                    "max_file_size_mb": original.max_file_size_mb,
                    "allowed_file_types": original.allowed_file_types,
                    "estimated_duration_hours": original.estimated_duration_hours,
                    "learning_objectives": original.learning_objectives,
                    "auto_grade": original.auto_grade,
                    "peer_review": original.peer_review,
                }

                # Apply modifications if provided
                if modifications:
                    duplicate_data.update(modifications)

                duplicate = AssignmentService.create_assignment(teacher, duplicate_data)

                # Copy rubrics if they exist
                for rubric in original.rubrics.all():
                    from ..models import AssignmentRubric

                    AssignmentRubric.objects.create(
                        assignment=duplicate,
                        criteria_name=rubric.criteria_name,
                        description=rubric.description,
                        max_points=rubric.max_points,
                        weight_percentage=rubric.weight_percentage,
                        excellent_description=rubric.excellent_description,
                        good_description=rubric.good_description,
                        satisfactory_description=rubric.satisfactory_description,
                        needs_improvement_description=rubric.needs_improvement_description,
                    )

                logger.info(
                    f"Assignment duplicated: {original.title} -> {duplicate.title}"
                )
                return duplicate

        except Assignment.DoesNotExist:
            raise ValidationError("Original assignment not found")
        except Exception as e:
            logger.error(f"Error duplicating assignment {assignment_id}: {str(e)}")
            raise

    @staticmethod
    def get_assignment_analytics(assignment_id: int) -> Dict:
        """
        Get comprehensive analytics for an assignment
        """
        try:
            cache_key = f"assignment_analytics_{assignment_id}"
            cached_result = cache.get(cache_key)
            if cached_result:
                return cached_result

            assignment = Assignment.objects.get(id=assignment_id)
            submissions = assignment.submissions.all()

            total_students = assignment.class_id.students.filter(
                status="active"
            ).count()
            submitted_count = submissions.count()
            graded_count = submissions.filter(status="graded").count()

            analytics = {
                "assignment_id": assignment_id,
                "title": assignment.title,
                "total_students": total_students,
                "submission_count": submitted_count,
                "graded_count": graded_count,
                "completion_rate": (
                    (submitted_count / total_students * 100)
                    if total_students > 0
                    else 0
                ),
                "grading_rate": (
                    (graded_count / submitted_count * 100) if submitted_count > 0 else 0
                ),
                "late_submissions": submissions.filter(is_late=True).count(),
                "on_time_submissions": submissions.filter(is_late=False).count(),
                "average_score": submissions.filter(
                    marks_obtained__isnull=False
                ).aggregate(avg=Avg("marks_obtained"))["avg"],
                "highest_score": submissions.aggregate(max=Max("marks_obtained"))[
                    "max"
                ],
                "lowest_score": submissions.aggregate(min=Min("marks_obtained"))["min"],
                "pass_rate": 0,
                "grade_distribution": {},
            }

            # Calculate pass rate
            if assignment.passing_marks and graded_count > 0:
                passed = submissions.filter(
                    marks_obtained__gte=assignment.passing_marks
                ).count()
                analytics["pass_rate"] = passed / graded_count * 100

            # Grade distribution
            grade_counts = {}
            for submission in submissions.filter(marks_obtained__isnull=False):
                grade = submission.calculate_grade()
                grade_counts[grade] = grade_counts.get(grade, 0) + 1
            analytics["grade_distribution"] = grade_counts

            # Cache for 30 minutes
            cache.set(cache_key, analytics, 1800)
            return analytics

        except Assignment.DoesNotExist:
            raise ValidationError("Assignment not found")
        except Exception as e:
            logger.error(
                f"Error getting assignment analytics {assignment_id}: {str(e)}"
            )
            raise

    @staticmethod
    def get_teacher_assignments(teacher, filters: Dict = None) -> Dict:
        """
        Get assignments for a teacher with optional filters
        """
        try:
            queryset = Assignment.objects.filter(teacher=teacher)

            if filters:
                if filters.get("status"):
                    queryset = queryset.filter(status=filters["status"])
                if filters.get("subject"):
                    queryset = queryset.filter(subject=filters["subject"])
                if filters.get("class_id"):
                    queryset = queryset.filter(class_id=filters["class_id"])
                if filters.get("term"):
                    queryset = queryset.filter(term=filters["term"])
                if filters.get("overdue_only"):
                    queryset = queryset.filter(
                        due_date__lt=timezone.now(), status="published"
                    )

            assignments = queryset.select_related(
                "class_id__grade__section", "subject", "term"
            ).prefetch_related("submissions")

            return {
                "assignments": assignments,
                "total_count": assignments.count(),
                "draft_count": assignments.filter(status="draft").count(),
                "published_count": assignments.filter(status="published").count(),
                "closed_count": assignments.filter(status="closed").count(),
                "overdue_count": assignments.filter(
                    due_date__lt=timezone.now(), status="published"
                ).count(),
            }

        except Exception as e:
            logger.error(f"Error getting teacher assignments: {str(e)}")
            raise

    @staticmethod
    def extend_deadline(
        assignment_id: int, new_due_date, reason: str = None
    ) -> Assignment:
        """
        Extend assignment deadline
        """
        try:
            with transaction.atomic():
                assignment = Assignment.objects.select_for_update().get(
                    id=assignment_id
                )

                if new_due_date <= timezone.now():
                    raise ValidationError("New due date must be in the future")

                if new_due_date <= assignment.due_date:
                    raise ValidationError(
                        "New due date must be later than current due date"
                    )

                old_due_date = assignment.due_date
                assignment.due_date = new_due_date
                assignment.save()

                # Log the change
                logger.info(
                    f"Assignment deadline extended: {assignment.title} from {old_due_date} to {new_due_date}. Reason: {reason}"
                )

                # TODO: Send notifications about deadline change
                # NotificationService.send_deadline_change_notification(assignment, old_due_date, reason)

                return assignment

        except Assignment.DoesNotExist:
            raise ValidationError("Assignment not found")
        except Exception as e:
            logger.error(
                f"Error extending deadline for assignment {assignment_id}: {str(e)}"
            )
            raise

    @staticmethod
    def get_assignment_progress(assignment_id: int) -> Dict:
        """
        Get detailed progress information for an assignment
        """
        try:
            assignment = Assignment.objects.get(id=assignment_id)

            total_students = assignment.class_id.students.filter(
                status="active"
            ).count()
            submissions = assignment.submissions.all()

            # Categorize submissions by status
            status_breakdown = {
                "not_submitted": total_students - submissions.count(),
                "submitted": submissions.filter(status="submitted").count(),
                "graded": submissions.filter(status="graded").count(),
                "late": submissions.filter(is_late=True).count(),
            }

            # Performance breakdown
            graded_submissions = submissions.filter(
                status="graded", marks_obtained__isnull=False
            )
            performance_breakdown = {
                "excellent": graded_submissions.filter(percentage__gte=90).count(),
                "good": graded_submissions.filter(
                    percentage__gte=70, percentage__lt=90
                ).count(),
                "satisfactory": graded_submissions.filter(
                    percentage__gte=50, percentage__lt=70
                ).count(),
                "needs_improvement": graded_submissions.filter(
                    percentage__lt=50
                ).count(),
            }

            # Time analysis
            time_to_deadline = (
                assignment.due_date - timezone.now()
            ).total_seconds() / 3600  # hours

            return {
                "assignment": {
                    "id": assignment.id,
                    "title": assignment.title,
                    "due_date": assignment.due_date,
                    "status": assignment.status,
                    "is_overdue": assignment.is_overdue,
                    "time_to_deadline_hours": (
                        time_to_deadline if time_to_deadline > 0 else 0
                    ),
                },
                "status_breakdown": status_breakdown,
                "performance_breakdown": performance_breakdown,
                "completion_percentage": (
                    (submissions.count() / total_students * 100)
                    if total_students > 0
                    else 0
                ),
                "grading_percentage": (
                    (graded_submissions.count() / submissions.count() * 100)
                    if submissions.count() > 0
                    else 0
                ),
            }

        except Assignment.DoesNotExist:
            raise ValidationError("Assignment not found")
        except Exception as e:
            logger.error(f"Error getting assignment progress {assignment_id}: {str(e)}")
            raise
