from celery import shared_task
from django.utils import timezone
from django.db import transaction
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from datetime import datetime, timedelta
import logging
from typing import Dict, List

from .models import Assignment, AssignmentSubmission, AssignmentRubric
from .services import (
    AssignmentService,
    SubmissionService,
    PlagiarismService,
    DeadlineService,
)
from .services.analytics_service import AssignmentAnalyticsService

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def send_assignment_published_notification(self, assignment_id: int):
    """
    Send notification when assignment is published
    """
    try:
        assignment = Assignment.objects.get(id=assignment_id)

        # Get students in the class
        students = assignment.class_id.students.filter(status="active")

        # Send notifications to students
        for student in students:
            try:
                # Email notification
                if student.user.email:
                    send_assignment_notification_email(
                        student.user.email, student.user.get_full_name(), assignment
                    )

                # In-app notification (would integrate with communications module)
                create_in_app_notification(
                    user=student.user,
                    title=f"New Assignment: {assignment.title}",
                    message=f"A new assignment has been published for {assignment.subject.name}",
                    assignment=assignment,
                )

            except Exception as e:
                logger.warning(f"Failed to notify student {student.id}: {str(e)}")

        # Send notification to parents
        for student in students:
            parents = student.parents.all()
            for parent in parents:
                try:
                    if parent.user.email:
                        send_assignment_parent_notification_email(
                            parent.user.email,
                            parent.user.get_full_name(),
                            student.user.get_full_name(),
                            assignment,
                        )
                except Exception as e:
                    logger.warning(f"Failed to notify parent {parent.id}: {str(e)}")

        logger.info(f"Assignment published notifications sent for: {assignment.title}")
        return {
            "assignment_id": assignment_id,
            "students_notified": students.count(),
            "status": "success",
        }

    except Assignment.DoesNotExist:
        logger.error(f"Assignment {assignment_id} not found")
        return {"error": "Assignment not found"}
    except Exception as e:
        logger.error(f"Error sending assignment notifications: {str(e)}")
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=60, exc=e)
        return {"error": str(e)}


@shared_task(bind=True, max_retries=3)
def send_submission_received_notification(self, submission_id: int):
    """
    Send notification when submission is received
    """
    try:
        submission = AssignmentSubmission.objects.get(id=submission_id)
        teacher = submission.assignment.teacher

        # Send email to teacher
        if teacher.user.email:
            send_submission_received_email(
                teacher.user.email, teacher.user.get_full_name(), submission
            )

        # Create in-app notification
        create_in_app_notification(
            user=teacher.user,
            title=f"New Submission: {submission.assignment.title}",
            message=f"Submission received from {submission.student.user.get_full_name()}",
            submission=submission,
        )

        logger.info(f"Submission received notification sent for: {submission.id}")
        return {
            "submission_id": submission_id,
            "teacher_notified": True,
            "status": "success",
        }

    except AssignmentSubmission.DoesNotExist:
        logger.error(f"Submission {submission_id} not found")
        return {"error": "Submission not found"}
    except Exception as e:
        logger.error(f"Error sending submission notification: {str(e)}")
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=60, exc=e)
        return {"error": str(e)}


@shared_task(bind=True, max_retries=3)
def send_grade_notification(self, submission_id: int):
    """
    Send notification when submission is graded
    """
    try:
        submission = AssignmentSubmission.objects.get(id=submission_id)
        student = submission.student

        # Send email to student
        if student.user.email:
            send_grade_notification_email(
                student.user.email, student.user.get_full_name(), submission
            )

        # Create in-app notification
        create_in_app_notification(
            user=student.user,
            title=f"Grade Available: {submission.assignment.title}",
            message=f"Your assignment has been graded. Score: {submission.marks_obtained}/{submission.assignment.total_marks}",
            submission=submission,
        )

        # Send notification to parents
        parents = student.parents.all()
        for parent in parents:
            try:
                if parent.user.email:
                    send_grade_parent_notification_email(
                        parent.user.email,
                        parent.user.get_full_name(),
                        student.user.get_full_name(),
                        submission,
                    )
            except Exception as e:
                logger.warning(f"Failed to notify parent {parent.id}: {str(e)}")

        logger.info(f"Grade notification sent for submission: {submission.id}")
        return {
            "submission_id": submission_id,
            "student_notified": True,
            "parents_notified": parents.count(),
            "status": "success",
        }

    except AssignmentSubmission.DoesNotExist:
        logger.error(f"Submission {submission_id} not found")
        return {"error": "Submission not found"}
    except Exception as e:
        logger.error(f"Error sending grade notification: {str(e)}")
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=60, exc=e)
        return {"error": str(e)}


@shared_task(bind=True, max_retries=3)
def send_deadline_reminders(self, days_before: int = 2):
    """
    Send deadline reminder notifications
    """
    try:
        result = DeadlineService.send_deadline_reminders(days_before)

        logger.info(f"Deadline reminders task completed: {result}")
        return result

    except Exception as e:
        logger.error(f"Error in deadline reminders task: {str(e)}")
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=300, exc=e)  # Retry after 5 minutes
        return {"error": str(e)}


@shared_task(bind=True)
def schedule_deadline_reminder(self, assignment_id: int):
    """
    Scheduled task for individual assignment deadline reminder
    """
    try:
        assignment = Assignment.objects.get(id=assignment_id)

        # Check if assignment is still published and due
        if assignment.status != "published" or assignment.due_date <= timezone.now():
            logger.info(
                f"Skipping reminder for assignment {assignment_id} - status changed or overdue"
            )
            return {"skipped": True}

        # Get students who haven't submitted
        submitted_students = assignment.submissions.values_list("student_id", flat=True)
        pending_students = assignment.class_id.students.filter(status="active").exclude(
            id__in=submitted_students
        )

        # Send reminders
        notifications_sent = 0
        for student in pending_students:
            try:
                # Email reminder
                if student.user.email:
                    send_deadline_reminder_email(
                        student.user.email, student.user.get_full_name(), assignment
                    )

                # In-app notification
                create_in_app_notification(
                    user=student.user,
                    title=f"Deadline Reminder: {assignment.title}",
                    message=f'Assignment due in 2 days. Due date: {assignment.due_date.strftime("%Y-%m-%d %H:%M")}',
                    assignment=assignment,
                    priority="high",
                )

                notifications_sent += 1

            except Exception as e:
                logger.warning(
                    f"Failed to send reminder to student {student.id}: {str(e)}"
                )

        logger.info(
            f"Deadline reminders sent for assignment {assignment_id}: {notifications_sent} students"
        )
        return {
            "assignment_id": assignment_id,
            "reminders_sent": notifications_sent,
            "status": "success",
        }

    except Assignment.DoesNotExist:
        logger.error(f"Assignment {assignment_id} not found for reminder")
        return {"error": "Assignment not found"}
    except Exception as e:
        logger.error(f"Error in scheduled reminder: {str(e)}")
        return {"error": str(e)}


@shared_task(bind=True, max_retries=2)
def update_assignment_analytics(self, assignment_id: int):
    """
    Update analytics data for an assignment
    """
    try:
        analytics = AssignmentService.get_assignment_analytics(assignment_id)

        # Cache the results
        from django.core.cache import cache

        cache.set(f"assignment_analytics_{assignment_id}", analytics, 3600)

        logger.info(f"Analytics updated for assignment {assignment_id}")
        return {
            "assignment_id": assignment_id,
            "analytics_updated": True,
            "status": "success",
        }

    except Exception as e:
        logger.error(
            f"Error updating analytics for assignment {assignment_id}: {str(e)}"
        )
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=120, exc=e)
        return {"error": str(e)}


@shared_task(bind=True, max_retries=2)
def calculate_assignment_analytics(self):
    """
    Calculate analytics for all recent assignments
    """
    try:
        # Get assignments from last 30 days
        recent_assignments = Assignment.objects.filter(
            created_at__gte=timezone.now() - timedelta(days=30)
        )

        processed = 0
        errors = 0

        for assignment in recent_assignments:
            try:
                update_assignment_analytics.delay(assignment.id)
                processed += 1
            except Exception as e:
                logger.warning(
                    f"Failed to queue analytics for assignment {assignment.id}: {str(e)}"
                )
                errors += 1

        logger.info(
            f"Analytics calculation queued for {processed} assignments, {errors} errors"
        )
        return {"processed": processed, "errors": errors, "status": "success"}

    except Exception as e:
        logger.error(f"Error in analytics calculation task: {str(e)}")
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=300, exc=e)
        return {"error": str(e)}


@shared_task(bind=True, max_retries=2)
def check_overdue_assignments(self):
    """
    Check and process overdue assignments
    """
    try:
        overdue_assignments = Assignment.objects.filter(
            status="published", due_date__lt=timezone.now()
        )

        processed = 0
        for assignment in overdue_assignments:
            try:
                # Send overdue notifications
                send_overdue_notifications.delay(assignment.id)
                processed += 1

            except Exception as e:
                logger.warning(
                    f"Failed to process overdue assignment {assignment.id}: {str(e)}"
                )

        logger.info(f"Processed {processed} overdue assignments")
        return {
            "overdue_count": overdue_assignments.count(),
            "processed": processed,
            "status": "success",
        }

    except Exception as e:
        logger.error(f"Error checking overdue assignments: {str(e)}")
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=300, exc=e)
        return {"error": str(e)}


@shared_task(bind=True, max_retries=2)
def send_overdue_notifications(self, assignment_id: int):
    """
    Send notifications for overdue assignments
    """
    try:
        assignment = Assignment.objects.get(id=assignment_id)

        # Get students who haven't submitted
        submitted_students = assignment.submissions.values_list("student_id", flat=True)
        pending_students = assignment.class_id.students.filter(status="active").exclude(
            id__in=submitted_students
        )

        notifications_sent = 0
        for student in pending_students:
            try:
                # Email notification
                if student.user.email:
                    send_overdue_notification_email(
                        student.user.email, student.user.get_full_name(), assignment
                    )

                # In-app notification
                create_in_app_notification(
                    user=student.user,
                    title=f"Overdue Assignment: {assignment.title}",
                    message=f"Assignment is overdue. Please submit as soon as possible.",
                    assignment=assignment,
                    priority="urgent",
                )

                notifications_sent += 1

            except Exception as e:
                logger.warning(
                    f"Failed to send overdue notification to student {student.id}: {str(e)}"
                )

        logger.info(
            f"Overdue notifications sent for assignment {assignment_id}: {notifications_sent} students"
        )
        return {
            "assignment_id": assignment_id,
            "notifications_sent": notifications_sent,
            "status": "success",
        }

    except Assignment.DoesNotExist:
        logger.error(f"Assignment {assignment_id} not found for overdue notification")
        return {"error": "Assignment not found"}
    except Exception as e:
        logger.error(f"Error sending overdue notifications: {str(e)}")
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=120, exc=e)
        return {"error": str(e)}


@shared_task(bind=True, max_retries=2)
def batch_plagiarism_check(self, assignment_id: int = None):
    """
    Run batch plagiarism check
    """
    try:
        if assignment_id:
            result = PlagiarismService.batch_plagiarism_check(assignment_id)
        else:
            # Check all unchecked submissions
            unchecked_submissions = AssignmentSubmission.objects.filter(
                plagiarism_checked=False, content__isnull=False
            ).exclude(content="")

            result = {
                "checked": 0,
                "suspicious": 0,
                "errors": [],
                "total": unchecked_submissions.count(),
            }

            for submission in unchecked_submissions:
                try:
                    check_result = PlagiarismService.check_submission_plagiarism(
                        submission.id
                    )
                    result["checked"] += 1
                    if check_result["is_suspicious"]:
                        result["suspicious"] += 1

                        # Send notification for suspicious submission
                        send_plagiarism_alert.delay(submission.id)

                except Exception as e:
                    result["errors"].append(
                        {"submission_id": submission.id, "error": str(e)}
                    )

        logger.info(f"Batch plagiarism check completed: {result}")
        return result

    except Exception as e:
        logger.error(f"Error in batch plagiarism check: {str(e)}")
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=300, exc=e)
        return {"error": str(e)}


@shared_task(bind=True, max_retries=2)
def send_plagiarism_alert(self, submission_id: int):
    """
    Send plagiarism alert to teacher
    """
    try:
        submission = AssignmentSubmission.objects.get(id=submission_id)
        teacher = submission.assignment.teacher

        # Send email alert
        if teacher.user.email:
            send_plagiarism_alert_email(
                teacher.user.email, teacher.user.get_full_name(), submission
            )

        # Create in-app notification
        create_in_app_notification(
            user=teacher.user,
            title=f"Plagiarism Alert: {submission.assignment.title}",
            message=f"High plagiarism score detected in submission from {submission.student.user.get_full_name()}",
            submission=submission,
            priority="high",
        )

        logger.info(f"Plagiarism alert sent for submission {submission_id}")
        return {"submission_id": submission_id, "alert_sent": True, "status": "success"}

    except AssignmentSubmission.DoesNotExist:
        logger.error(f"Submission {submission_id} not found for plagiarism alert")
        return {"error": "Submission not found"}
    except Exception as e:
        logger.error(f"Error sending plagiarism alert: {str(e)}")
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=120, exc=e)
        return {"error": str(e)}


@shared_task
def cleanup_old_files(days_old: int = 30):
    """
    Clean up old assignment and submission files
    """
    try:
        from django.core.files.storage import default_storage

        cutoff_date = timezone.now() - timedelta(days=days_old)

        # Clean assignment files
        old_assignments = Assignment.objects.filter(
            created_at__lt=cutoff_date, attachment__isnull=False
        )

        assignment_files_deleted = 0
        for assignment in old_assignments:
            try:
                if assignment.attachment:
                    default_storage.delete(assignment.attachment.name)
                    assignment.attachment = None
                    assignment.save()
                    assignment_files_deleted += 1
            except Exception as e:
                logger.warning(f"Could not delete assignment file: {str(e)}")

        # Clean submission files
        old_submissions = AssignmentSubmission.objects.filter(
            created_at__lt=cutoff_date, attachment__isnull=False
        )

        submission_files_deleted = 0
        for submission in old_submissions:
            try:
                if submission.attachment:
                    default_storage.delete(submission.attachment.name)
                    submission.attachment = None
                    submission.save()
                    submission_files_deleted += 1
            except Exception as e:
                logger.warning(f"Could not delete submission file: {str(e)}")

        logger.info(
            f"File cleanup completed: {assignment_files_deleted} assignment files, {submission_files_deleted} submission files"
        )
        return {
            "assignment_files_deleted": assignment_files_deleted,
            "submission_files_deleted": submission_files_deleted,
            "status": "success",
        }

    except Exception as e:
        logger.error(f"Error in file cleanup task: {str(e)}")
        return {"error": str(e)}


@shared_task
def generate_weekly_reports():
    """
    Generate weekly assignment reports
    """
    try:
        from django.db.models import Count, Avg

        week_start = timezone.now() - timedelta(days=7)

        # Generate teacher reports
        teachers_with_assignments = (
            Assignment.objects.filter(created_at__gte=week_start)
            .values("teacher")
            .distinct()
        )

        reports_generated = 0
        for teacher_data in teachers_with_assignments:
            try:
                generate_teacher_weekly_report.delay(teacher_data["teacher"])
                reports_generated += 1
            except Exception as e:
                logger.warning(
                    f"Failed to generate report for teacher {teacher_data['teacher']}: {str(e)}"
                )

        logger.info(f"Weekly report generation queued for {reports_generated} teachers")
        return {"reports_queued": reports_generated, "status": "success"}

    except Exception as e:
        logger.error(f"Error generating weekly reports: {str(e)}")
        return {"error": str(e)}


@shared_task(bind=True, max_retries=2)
def generate_teacher_weekly_report(self, teacher_id: int):
    """
    Generate weekly report for a specific teacher
    """
    try:
        from teachers.models import Teacher

        teacher = Teacher.objects.get(id=teacher_id)
        week_start = timezone.now() - timedelta(days=7)

        # Get teacher's analytics for the week
        analytics = AssignmentAnalyticsService.get_teacher_analytics(
            teacher_id, filters={"date_from": week_start}
        )

        # Generate and send report email
        if teacher.user.email:
            send_weekly_report_email(
                teacher.user.email, teacher.user.get_full_name(), analytics
            )

        logger.info(f"Weekly report generated for teacher {teacher_id}")
        return {"teacher_id": teacher_id, "report_generated": True, "status": "success"}

    except Teacher.DoesNotExist:
        logger.error(f"Teacher {teacher_id} not found")
        return {"error": "Teacher not found"}
    except Exception as e:
        logger.error(f"Error generating teacher report: {str(e)}")
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=120, exc=e)
        return {"error": str(e)}


# Email helper functions
def send_assignment_notification_email(email, name, assignment):
    """Send assignment published notification email"""
    try:
        subject = f"New Assignment: {assignment.title}"
        message = render_to_string(
            "assignments/emails/assignment_published.html",
            {"name": name, "assignment": assignment},
        )

        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            html_message=message,
        )
    except Exception as e:
        logger.error(f"Failed to send assignment notification email: {str(e)}")


def send_assignment_parent_notification_email(
    email, parent_name, student_name, assignment
):
    """Send assignment notification to parent"""
    try:
        subject = f"New Assignment for {student_name}: {assignment.title}"
        message = render_to_string(
            "assignments/emails/assignment_parent_notification.html",
            {
                "parent_name": parent_name,
                "student_name": student_name,
                "assignment": assignment,
            },
        )

        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            html_message=message,
        )
    except Exception as e:
        logger.error(f"Failed to send parent notification email: {str(e)}")


def send_submission_received_email(email, teacher_name, submission):
    """Send submission received email to teacher"""
    try:
        subject = f"New Submission: {submission.assignment.title}"
        message = render_to_string(
            "assignments/emails/submission_received.html",
            {"teacher_name": teacher_name, "submission": submission},
        )

        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            html_message=message,
        )
    except Exception as e:
        logger.error(f"Failed to send submission received email: {str(e)}")


def send_grade_notification_email(email, student_name, submission):
    """Send grade notification email to student"""
    try:
        subject = f"Grade Available: {submission.assignment.title}"
        message = render_to_string(
            "assignments/emails/grade_notification.html",
            {"student_name": student_name, "submission": submission},
        )

        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            html_message=message,
        )
    except Exception as e:
        logger.error(f"Failed to send grade notification email: {str(e)}")


def send_grade_parent_notification_email(email, parent_name, student_name, submission):
    """Send grade notification to parent"""
    try:
        subject = f"Grade Available for {student_name}: {submission.assignment.title}"
        message = render_to_string(
            "assignments/emails/grade_parent_notification.html",
            {
                "parent_name": parent_name,
                "student_name": student_name,
                "submission": submission,
            },
        )

        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            html_message=message,
        )
    except Exception as e:
        logger.error(f"Failed to send grade parent notification email: {str(e)}")


def send_deadline_reminder_email(email, student_name, assignment):
    """Send deadline reminder email"""
    try:
        subject = f"Deadline Reminder: {assignment.title}"
        message = render_to_string(
            "assignments/emails/deadline_reminder.html",
            {"student_name": student_name, "assignment": assignment},
        )

        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            html_message=message,
        )
    except Exception as e:
        logger.error(f"Failed to send deadline reminder email: {str(e)}")


def send_overdue_notification_email(email, student_name, assignment):
    """Send overdue notification email"""
    try:
        subject = f"Overdue Assignment: {assignment.title}"
        message = render_to_string(
            "assignments/emails/overdue_notification.html",
            {"student_name": student_name, "assignment": assignment},
        )

        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            html_message=message,
        )
    except Exception as e:
        logger.error(f"Failed to send overdue notification email: {str(e)}")


def send_plagiarism_alert_email(email, teacher_name, submission):
    """Send plagiarism alert email"""
    try:
        subject = f"Plagiarism Alert: {submission.assignment.title}"
        message = render_to_string(
            "assignments/emails/plagiarism_alert.html",
            {"teacher_name": teacher_name, "submission": submission},
        )

        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            html_message=message,
        )
    except Exception as e:
        logger.error(f"Failed to send plagiarism alert email: {str(e)}")


def send_weekly_report_email(email, teacher_name, analytics):
    """Send weekly report email"""
    try:
        subject = "Weekly Assignment Report"
        message = render_to_string(
            "assignments/emails/weekly_report.html",
            {"teacher_name": teacher_name, "analytics": analytics},
        )

        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            html_message=message,
        )
    except Exception as e:
        logger.error(f"Failed to send weekly report email: {str(e)}")


def create_in_app_notification(
    user, title, message, assignment=None, submission=None, priority="normal"
):
    """Create in-app notification (would integrate with communications module)"""
    try:
        # This would integrate with your communications module
        # For now, just log the notification
        logger.info(f"In-app notification for {user.username}: {title}")

        # Example integration:
        # from communications.models import Notification
        # Notification.objects.create(
        #     user=user,
        #     title=title,
        #     content=message,
        #     notification_type='assignment',
        #     reference_id=assignment.id if assignment else submission.id,
        #     priority=priority
        # )

    except Exception as e:
        logger.error(f"Failed to create in-app notification: {str(e)}")
