import difflib
import logging
from typing import Dict, List, Optional, Tuple

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Avg, Count, Q
from django.utils import timezone

from ..models import Assignment, AssignmentSubmission

logger = logging.getLogger(__name__)


class PlagiarismService:
    """
    Service class for plagiarism detection and content similarity analysis
    """

    @staticmethod
    def check_submission_plagiarism(submission_id: int) -> Dict:
        """
        Check submission for plagiarism
        """
        try:
            submission = AssignmentSubmission.objects.get(id=submission_id)

            # Basic text similarity check
            similarity_results = PlagiarismService._check_text_similarity(
                submission.content, submission.assignment
            )

            # File-based plagiarism check would go here
            # This would integrate with external services like Turnitin

            plagiarism_score = similarity_results["max_similarity"]

            # Update submission
            submission.plagiarism_score = plagiarism_score
            submission.plagiarism_checked = True
            submission.plagiarism_report = similarity_results
            submission.save()

            logger.info(
                f"Plagiarism check completed for submission {submission_id}: {plagiarism_score}%"
            )

            return {
                "submission_id": submission_id,
                "plagiarism_score": plagiarism_score,
                "is_suspicious": plagiarism_score > 30,  # Configurable threshold
                "detailed_report": similarity_results,
            }

        except AssignmentSubmission.DoesNotExist:
            raise ValidationError("Submission not found")
        except Exception as e:
            logger.error(
                f"Error checking plagiarism for submission {submission_id}: {str(e)}"
            )
            raise

    @staticmethod
    def _check_text_similarity(content: str, assignment) -> Dict:
        """
        Check text similarity against other submissions
        """
        try:
            other_submissions = (
                AssignmentSubmission.objects.filter(assignment=assignment)
                .exclude(content="")
                .values_list("content", flat=True)
            )

            similarities = []
            max_similarity = 0

            for other_content in other_submissions:
                if other_content and content:
                    # Calculate similarity using difflib
                    similarity = (
                        difflib.SequenceMatcher(None, content, other_content).ratio()
                        * 100
                    )
                    similarities.append(
                        {
                            "similarity_percentage": round(similarity, 2),
                            "matched_content": (
                                other_content[:100] + "..."
                                if len(other_content) > 100
                                else other_content
                            ),
                        }
                    )
                    max_similarity = max(max_similarity, similarity)

            return {
                "max_similarity": round(max_similarity, 2),
                "average_similarity": (
                    round(
                        sum(s["similarity_percentage"] for s in similarities)
                        / len(similarities),
                        2,
                    )
                    if similarities
                    else 0
                ),
                "total_comparisons": len(similarities),
                "detailed_similarities": sorted(
                    similarities, key=lambda x: x["similarity_percentage"], reverse=True
                )[:5],
            }

        except Exception as e:
            logger.error(f"Error in text similarity check: {str(e)}")
            return {
                "max_similarity": 0,
                "average_similarity": 0,
                "total_comparisons": 0,
                "detailed_similarities": [],
            }

    @staticmethod
    def batch_plagiarism_check(assignment_id: int) -> Dict:
        """
        Run plagiarism check for all submissions of an assignment
        """
        try:
            assignment = Assignment.objects.get(id=assignment_id)
            submissions = assignment.submissions.filter(plagiarism_checked=False)

            results = {
                "checked": 0,
                "suspicious": 0,
                "errors": [],
                "total": submissions.count(),
            }

            for submission in submissions:
                try:
                    result = PlagiarismService.check_submission_plagiarism(
                        submission.id
                    )
                    results["checked"] += 1
                    if result["is_suspicious"]:
                        results["suspicious"] += 1
                except Exception as e:
                    results["errors"].append(
                        {"submission_id": submission.id, "error": str(e)}
                    )

            logger.info(
                f"Batch plagiarism check completed for assignment {assignment_id}: {results['checked']}/{results['total']} checked"
            )
            return results

        except Assignment.DoesNotExist:
            raise ValidationError("Assignment not found")
        except Exception as e:
            logger.error(f"Error in batch plagiarism check: {str(e)}")
            raise
