from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db.models import Q, Count, Avg
from typing import Dict, List, Optional, Tuple
import logging
from datetime import datetime, timedelta

from ..models import Assignment, AssignmentSubmission

logger = logging.getLogger(__name__)


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
