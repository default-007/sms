from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db.models import Q, Count, Avg, Sum, Max, Min, F
from typing import Dict, List, Optional, Tuple
import logging

from ..models import AssignmentSubmission, SubmissionGrade, AssignmentRubric
from teachers.models import Teacher

logger = logging.getLogger(__name__)


class GradingService:
    """
    Service class for grading assignments and providing feedback
    """

    @staticmethod
    def grade_submission(
        submission_id: int, grader, grading_data: Dict
    ) -> AssignmentSubmission:
        """
        Grade a submission with marks and feedback
        """
        try:
            with transaction.atomic():
                submission = AssignmentSubmission.objects.select_for_update().get(
                    id=submission_id
                )

                # Validate marks
                marks = grading_data.get("marks_obtained")
                if marks is not None:
                    if marks < 0 or marks > submission.assignment.total_marks:
                        raise ValidationError(
                            f"Marks must be between 0 and {submission.assignment.total_marks}"
                        )

                # Update submission
                submission.marks_obtained = marks
                submission.teacher_remarks = grading_data.get("teacher_remarks", "")
                submission.strengths = grading_data.get("strengths", "")
                submission.improvements = grading_data.get("improvements", "")
                submission.graded_by = grader
                submission.graded_at = timezone.now()
                submission.status = "graded"

                # Calculate grade
                submission.grade = submission.calculate_grade()

                submission.save()

                # Process rubric grades if provided
                rubric_grades = grading_data.get("rubric_grades", [])
                for rubric_grade in rubric_grades:
                    GradingService._process_rubric_grade(submission, rubric_grade)

                logger.info(
                    f"Submission graded: {submission.assignment.title} for {submission.student.user.get_full_name()}"
                )
                return submission

        except AssignmentSubmission.DoesNotExist:
            raise ValidationError("Submission not found")
        except Exception as e:
            logger.error(f"Error grading submission {submission_id}: {str(e)}")
            raise

    @staticmethod
    def _process_rubric_grade(submission, rubric_grade_data):
        """
        Process individual rubric criterion grade
        """
        try:
            rubric = AssignmentRubric.objects.get(id=rubric_grade_data["rubric_id"])
            points = rubric_grade_data["points_earned"]

            if points < 0 or points > rubric.max_points:
                raise ValidationError(
                    f"Points must be between 0 and {rubric.max_points}"
                )

            SubmissionGrade.objects.update_or_create(
                submission=submission,
                rubric=rubric,
                defaults={
                    "points_earned": points,
                    "feedback": rubric_grade_data.get("feedback", ""),
                },
            )

        except AssignmentRubric.DoesNotExist:
            raise ValidationError("Rubric not found")

    @staticmethod
    def bulk_grade_submissions(
        assignment_id: int, grader, grading_data: List[Dict]
    ) -> Dict:
        """
        Grade multiple submissions at once
        """
        try:
            results = {"graded": 0, "errors": [], "total": len(grading_data)}

            for data in grading_data:
                try:
                    submission_id = data["submission_id"]
                    GradingService.grade_submission(submission_id, grader, data)
                    results["graded"] += 1
                except Exception as e:
                    results["errors"].append(
                        {"submission_id": data.get("submission_id"), "error": str(e)}
                    )

            logger.info(
                f"Bulk grading completed: {results['graded']}/{results['total']} successful"
            )
            return results

        except Exception as e:
            logger.error(f"Error in bulk grading: {str(e)}")
            raise

    @staticmethod
    def get_grading_analytics(teacher, filters: Dict = None) -> Dict:
        """
        Get grading analytics for a teacher
        """
        try:
            queryset = AssignmentSubmission.objects.filter(
                assignment__teacher=teacher
            ).select_related("assignment", "student__user")

            if filters:
                if filters.get("subject"):
                    queryset = queryset.filter(assignment__subject=filters["subject"])
                if filters.get("class_id"):
                    queryset = queryset.filter(assignment__class_id=filters["class_id"])
                if filters.get("term"):
                    queryset = queryset.filter(assignment__term=filters["term"])

            total_submissions = queryset.count()
            graded_submissions = queryset.filter(status="graded").count()
            pending_submissions = queryset.exclude(status="graded").count()

            analytics = {
                "total_submissions": total_submissions,
                "graded_submissions": graded_submissions,
                "pending_submissions": pending_submissions,
                "grading_rate": (
                    (graded_submissions / total_submissions * 100)
                    if total_submissions > 0
                    else 0
                ),
                "average_grading_time": None,  # Would calculate based on submission_date vs graded_at
                "most_common_grades": {},
                "subject_breakdown": {},
            }

            # Grade distribution
            graded_queryset = queryset.filter(
                status="graded", marks_obtained__isnull=False
            )
            grade_counts = {}
            for submission in graded_queryset:
                grade = submission.calculate_grade()
                grade_counts[grade] = grade_counts.get(grade, 0) + 1
            analytics["most_common_grades"] = grade_counts

            # Subject breakdown
            subject_stats = {}
            for submission in queryset:
                subject = submission.assignment.subject.name
                if subject not in subject_stats:
                    subject_stats[subject] = {"total": 0, "graded": 0}
                subject_stats[subject]["total"] += 1
                if submission.status == "graded":
                    subject_stats[subject]["graded"] += 1

            for subject, stats in subject_stats.items():
                stats["grading_rate"] = (
                    (stats["graded"] / stats["total"] * 100)
                    if stats["total"] > 0
                    else 0
                )

            analytics["subject_breakdown"] = subject_stats

            return analytics

        except Exception as e:
            logger.error(f"Error getting grading analytics: {str(e)}")
            raise
