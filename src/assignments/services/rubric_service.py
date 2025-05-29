import logging
from typing import Dict, List, Optional, Tuple

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Avg, Count, F, Q, Sum
from django.utils import timezone

from ..models import Assignment, AssignmentRubric, AssignmentSubmission, SubmissionGrade

logger = logging.getLogger(__name__)


class RubricService:
    """
    Service class for managing assignment rubrics
    """

    @staticmethod
    def create_rubric(
        assignment_id: int, rubric_data: List[Dict]
    ) -> List[AssignmentRubric]:
        """
        Create rubric criteria for an assignment
        """
        try:
            with transaction.atomic():
                assignment = Assignment.objects.get(id=assignment_id)

                # Validate total weight percentage
                total_weight = sum(item["weight_percentage"] for item in rubric_data)
                if total_weight != 100:
                    raise ValidationError("Total weight percentage must equal 100")

                # Delete existing rubrics
                assignment.rubrics.all().delete()

                # Create new rubrics
                rubrics = []
                for data in rubric_data:
                    rubric = AssignmentRubric.objects.create(
                        assignment=assignment, **data
                    )
                    rubrics.append(rubric)

                logger.info(f"Rubric created for assignment: {assignment.title}")
                return rubrics

        except Assignment.DoesNotExist:
            raise ValidationError("Assignment not found")
        except Exception as e:
            logger.error(f"Error creating rubric: {str(e)}")
            raise

    @staticmethod
    def calculate_rubric_score(submission_id: int) -> Dict:
        """
        Calculate total score based on rubric grades
        """
        try:
            submission = AssignmentSubmission.objects.get(id=submission_id)
            rubric_grades = submission.rubric_grades.select_related("rubric")

            if not rubric_grades.exists():
                return {"total_score": None, "weighted_score": None, "breakdown": []}

            total_weighted_score = 0
            breakdown = []

            for grade in rubric_grades:
                rubric = grade.rubric
                percentage = (grade.points_earned / rubric.max_points) * 100
                weighted_contribution = (percentage * rubric.weight_percentage) / 100
                total_weighted_score += weighted_contribution

                breakdown.append(
                    {
                        "criteria": rubric.criteria_name,
                        "points_earned": grade.points_earned,
                        "max_points": rubric.max_points,
                        "percentage": round(percentage, 2),
                        "weight": rubric.weight_percentage,
                        "weighted_contribution": round(weighted_contribution, 2),
                    }
                )

            # Calculate equivalent marks
            total_marks = submission.assignment.total_marks
            equivalent_marks = (total_weighted_score / 100) * total_marks

            return {
                "total_score": round(total_weighted_score, 2),
                "equivalent_marks": round(equivalent_marks, 2),
                "total_marks": total_marks,
                "breakdown": breakdown,
            }

        except AssignmentSubmission.DoesNotExist:
            raise ValidationError("Submission not found")
        except Exception as e:
            logger.error(f"Error calculating rubric score: {str(e)}")
            raise
