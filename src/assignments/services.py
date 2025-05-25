from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db.models import Q, Count, Avg, Sum, Max, Min
from django.core.files.storage import default_storage
from django.conf import settings
import os
import hashlib
import difflib
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import logging

from .models import (
    Assignment,
    AssignmentSubmission,
    AssignmentRubric,
    SubmissionGrade,
    AssignmentComment,
)

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
    def get_assignment_analytics(assignment_id: int) -> Dict:
        """
        Get comprehensive analytics for an assignment
        """
        try:
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


class DeadlineService:
    """
    Service class for managing assignment deadlines and notifications
    """

    @staticmethod
    def get_upcoming_deadlines(
        user_type: str, user_id: int, days_ahead: int = 7
    ) -> List[Dict]:
        """
        Get upcoming assignment deadlines for a user
        """
        try:
            end_date = timezone.now() + timedelta(days=days_ahead)

            if user_type == "student":
                # Get assignments for student's class
                from students.models import Student

                student = Student.objects.get(id=user_id)

                assignments = Assignment.objects.filter(
                    class_id=student.current_class_id,
                    status="published",
                    due_date__range=[timezone.now(), end_date],
                ).select_related("subject")

                deadlines = []
                for assignment in assignments:
                    submission = assignment.get_student_submission(student)
                    deadlines.append(
                        {
                            "assignment_id": assignment.id,
                            "title": assignment.title,
                            "subject": assignment.subject.name,
                            "due_date": assignment.due_date,
                            "days_until_due": assignment.days_until_due,
                            "is_submitted": submission is not None,
                            "submission_status": (
                                submission.status if submission else None
                            ),
                        }
                    )

            elif user_type == "teacher":
                # Get assignments created by teacher
                from teachers.models import Teacher

                teacher = Teacher.objects.get(id=user_id)

                assignments = Assignment.objects.filter(
                    teacher=teacher,
                    status="published",
                    due_date__range=[timezone.now(), end_date],
                ).select_related("subject", "class_id__grade")

                deadlines = []
                for assignment in assignments:
                    deadlines.append(
                        {
                            "assignment_id": assignment.id,
                            "title": assignment.title,
                            "subject": assignment.subject.name,
                            "class": str(assignment.class_id),
                            "due_date": assignment.due_date,
                            "days_until_due": assignment.days_until_due,
                            "submission_count": assignment.submission_count,
                            "graded_count": assignment.graded_submission_count,
                        }
                    )

            return sorted(deadlines, key=lambda x: x["due_date"])

        except Exception as e:
            logger.error(f"Error getting upcoming deadlines: {str(e)}")
            raise

    @staticmethod
    def get_overdue_assignments() -> Dict:
        """
        Get all overdue assignments across the system
        """
        try:
            overdue_assignments = Assignment.objects.filter(
                status="published", due_date__lt=timezone.now()
            ).select_related("teacher__user", "class_id__grade", "subject")

            summary = {
                "total_overdue": overdue_assignments.count(),
                "by_teacher": {},
                "by_class": {},
                "by_subject": {},
                "assignments": [],
            }

            for assignment in overdue_assignments:
                # Teacher breakdown
                teacher_name = assignment.teacher.user.get_full_name()
                if teacher_name not in summary["by_teacher"]:
                    summary["by_teacher"][teacher_name] = 0
                summary["by_teacher"][teacher_name] += 1

                # Class breakdown
                class_name = str(assignment.class_id)
                if class_name not in summary["by_class"]:
                    summary["by_class"][class_name] = 0
                summary["by_class"][class_name] += 1

                # Subject breakdown
                subject_name = assignment.subject.name
                if subject_name not in summary["by_subject"]:
                    summary["by_subject"][subject_name] = 0
                summary["by_subject"][subject_name] += 1

                # Assignment details
                summary["assignments"].append(
                    {
                        "id": assignment.id,
                        "title": assignment.title,
                        "teacher": teacher_name,
                        "class": class_name,
                        "subject": subject_name,
                        "due_date": assignment.due_date,
                        "days_overdue": (timezone.now() - assignment.due_date).days,
                        "submission_count": assignment.submission_count,
                        "completion_rate": assignment.completion_rate,
                    }
                )

            return summary

        except Exception as e:
            logger.error(f"Error getting overdue assignments: {str(e)}")
            raise

    @staticmethod
    def send_deadline_reminders(days_before: int = 2) -> Dict:
        """
        Send deadline reminders for assignments due soon
        """
        try:
            reminder_date = timezone.now() + timedelta(days=days_before)

            assignments = Assignment.objects.filter(
                status="published", due_date__date=reminder_date.date()
            ).select_related("class_id", "subject", "teacher__user")

            reminder_stats = {
                "assignments_found": assignments.count(),
                "reminders_sent": 0,
                "errors": [],
            }

            for assignment in assignments:
                try:
                    # Get students who haven't submitted
                    submitted_students = assignment.submissions.values_list(
                        "student_id", flat=True
                    )
                    pending_students = assignment.class_id.students.filter(
                        status="active"
                    ).exclude(id__in=submitted_students)

                    # TODO: Send notifications through communications module
                    # NotificationService.send_deadline_reminder(assignment, pending_students)

                    reminder_stats["reminders_sent"] += pending_students.count()

                except Exception as e:
                    reminder_stats["errors"].append(
                        {"assignment_id": assignment.id, "error": str(e)}
                    )

            logger.info(
                f"Deadline reminders sent: {reminder_stats['reminders_sent']} for {reminder_stats['assignments_found']} assignments"
            )
            return reminder_stats

        except Exception as e:
            logger.error(f"Error sending deadline reminders: {str(e)}")
            raise


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
