import logging
from datetime import timedelta

from django.conf import settings
from django.core.cache import cache
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone

from src.assignments.models import SubmissionGrade
from src.core.models import AuditLog

# from .models import Assignment, AssignmentSubmission, SubmissionGrade

logger = logging.getLogger(__name__)

try:
    from .models import Assignment, AssignmentSubmission
except ImportError:
    # Models not yet loaded, will be imported later
    Assignment = None
    AssignmentSubmission = None


@receiver(pre_save, sender=Assignment)
def assignment_pre_save(sender, instance, **kwargs):
    """
    Handle pre-save operations for assignments
    """
    try:
        # Check if this is an update
        if instance.pk:
            try:
                old_instance = Assignment.objects.get(pk=instance.pk)

                # Track status changes
                if old_instance.status != instance.status:
                    logger.info(
                        f"Assignment {instance.id} status changed: {old_instance.status} -> {instance.status}"
                    )

                    # Set published_at when status changes to published
                    if instance.status == "published" and not instance.published_at:
                        instance.published_at = timezone.now()

                # Track due date changes
                if old_instance.due_date != instance.due_date:
                    logger.info(
                        f"Assignment {instance.id} due date changed: {old_instance.due_date} -> {instance.due_date}"
                    )

            except Assignment.DoesNotExist:
                pass  # New assignment

    except Exception as e:
        logger.error(f"Error in assignment pre_save signal: {str(e)}")


@receiver(post_save, sender=Assignment)
def assignment_post_save(sender, instance, created, **kwargs):
    """
    Handle post-save operations for assignments
    """
    try:
        if created:
            # Log assignment creation
            logger.info(
                f"New assignment created: {instance.title} by {instance.teacher.user.get_full_name()}"
            )

            # Create audit log entry
            AuditLog.objects.create(
                user=instance.teacher.user,
                action="CREATE",
                entity_type="Assignment",
                entity_id=instance.id,
                data_after={
                    "title": instance.title,
                    "class": str(instance.class_id),
                    "subject": instance.subject.name,
                    "due_date": instance.due_date.isoformat(),
                    "total_marks": instance.total_marks,
                },
            )

        else:
            # Handle assignment updates
            if instance.status == "published":
                # Send notification to students when assignment is published
                send_assignment_published_notification.delay(instance.id)

                # Schedule deadline reminder
                reminder_date = instance.due_date - timedelta(days=2)  # 2 days before
                if reminder_date > timezone.now():
                    schedule_deadline_reminder.delay(
                        instance.id, reminder_date.isoformat()
                    )

        # Clear related caches
        clear_assignment_caches(instance)

    except Exception as e:
        logger.error(f"Error in assignment post_save signal: {str(e)}")


@receiver(post_delete, sender=Assignment)
def assignment_post_delete(sender, instance, **kwargs):
    """
    Handle assignment deletion
    """
    try:
        # Log assignment deletion
        logger.info(f"Assignment deleted: {instance.title}")

        # Clean up related files
        if instance.attachment:
            try:
                instance.attachment.delete(save=False)
            except Exception as e:
                logger.warning(f"Could not delete assignment attachment: {str(e)}")

        # Clear caches
        clear_assignment_caches(instance)

    except Exception as e:
        logger.error(f"Error in assignment post_delete signal: {str(e)}")


@receiver(pre_save, sender=AssignmentSubmission)
def submission_pre_save(sender, instance, **kwargs):
    """
    Handle pre-save operations for submissions
    """
    try:
        # Check if this is an update
        if instance.pk:
            try:
                old_instance = AssignmentSubmission.objects.get(pk=instance.pk)

                # Track status changes
                if old_instance.status != instance.status:
                    logger.info(
                        f"Submission {instance.id} status changed: {old_instance.status} -> {instance.status}"
                    )

                # Track grading
                if (
                    old_instance.marks_obtained != instance.marks_obtained
                    and instance.marks_obtained is not None
                ):
                    logger.info(
                        f"Submission {instance.id} graded: {instance.marks_obtained}/{instance.assignment.total_marks}"
                    )

            except AssignmentSubmission.DoesNotExist:
                pass  # New submission

        # Auto-calculate derived fields
        if instance.marks_obtained is not None and instance.assignment.total_marks:
            instance.percentage = (
                instance.marks_obtained / instance.assignment.total_marks
            ) * 100

        # Check if submission is late
        if instance.submission_date and instance.assignment.due_date:
            instance.is_late = instance.submission_date > instance.assignment.due_date

    except Exception as e:
        logger.error(f"Error in submission pre_save signal: {str(e)}")


@receiver(post_save, sender=AssignmentSubmission)
def submission_post_save(sender, instance, created, **kwargs):
    """
    Handle post-save operations for submissions
    """
    try:
        if created:
            # Log submission creation
            logger.info(
                f"New submission: {instance.assignment.title} by {instance.student.user.get_full_name()}"
            )

            # Send notification to teacher
            send_submission_received_notification.delay(instance.id)

            # Create audit log entry
            AuditLog.objects.create(
                user=instance.student.user,
                action="CREATE",
                entity_type="AssignmentSubmission",
                entity_id=instance.id,
                data_after={
                    "assignment": instance.assignment.title,
                    "student": instance.student.user.get_full_name(),
                    "submission_date": instance.submission_date.isoformat(),
                    "is_late": instance.is_late,
                },
            )

        else:
            # Handle submission updates
            if instance.status == "graded" and instance.marks_obtained is not None:
                # Send grade notification to student and parents
                send_grade_notification.delay(instance.id)

                # Update assignment analytics
                update_assignment_analytics.delay(instance.assignment.id)

        # Clear related caches
        clear_submission_caches(instance)

    except Exception as e:
        logger.error(f"Error in submission post_save signal: {str(e)}")


@receiver(post_delete, sender=AssignmentSubmission)
def submission_post_delete(sender, instance, **kwargs):
    """
    Handle submission deletion
    """
    try:
        # Log submission deletion
        logger.info(
            f"Submission deleted: {instance.assignment.title} by {instance.student.user.get_full_name()}"
        )

        # Clean up attachment file
        if instance.attachment:
            try:
                instance.attachment.delete(save=False)
            except Exception as e:
                logger.warning(f"Could not delete submission attachment: {str(e)}")

        # Update assignment analytics
        update_assignment_analytics.delay(instance.assignment.id)

        # Clear caches
        clear_submission_caches(instance)

    except Exception as e:
        logger.error(f"Error in submission post_delete signal: {str(e)}")


@receiver(post_save, sender=SubmissionGrade)
def rubric_grade_post_save(sender, instance, created, **kwargs):
    """
    Handle rubric grade changes
    """
    try:
        if created or not created:  # Both create and update
            # Recalculate total submission score based on rubric
            from .services import RubricService

            rubric_score = RubricService.calculate_rubric_score(instance.submission.id)

            # Update submission marks if rubric scoring is complete
            if rubric_score["equivalent_marks"]:
                submission = instance.submission
                submission.marks_obtained = rubric_score["equivalent_marks"]
                submission.save()

                logger.info(
                    f"Rubric-based score calculated for submission {submission.id}: {rubric_score['equivalent_marks']}"
                )

    except Exception as e:
        logger.error(f"Error in rubric grade post_save signal: {str(e)}")


def clear_assignment_caches(assignment):
    """
    Clear all caches related to an assignment
    """
    try:
        cache_keys = [
            f"assignment_{assignment.id}",
            f"assignment_analytics_{assignment.id}",
            f"teacher_assignments_{assignment.teacher.id}",
            f"class_assignments_{assignment.class_id.id}",
            f"subject_assignments_{assignment.subject.id}",
            f"term_assignments_{assignment.term.id}",
        ]

        cache.delete_many(cache_keys)

        # Clear pattern-based caches
        cache.delete(f"assignments_*")

    except Exception as e:
        logger.warning(f"Error clearing assignment caches: {str(e)}")


def clear_submission_caches(submission):
    """
    Clear all caches related to a submission
    """
    try:
        cache_keys = [
            f"submission_{submission.id}",
            f"student_submissions_{submission.student.id}",
            f"assignment_submissions_{submission.assignment.id}",
            f"grading_analytics_{submission.assignment.teacher.id}",
        ]

        cache.delete_many(cache_keys)

        # Clear pattern-based caches
        cache.delete(f"submissions_*")

    except Exception as e:
        logger.warning(f"Error clearing submission caches: {str(e)}")


# Celery task stubs - these would be implemented in tasks.py
def send_assignment_published_notification(assignment_id):
    """
    Celery task to send assignment published notification
    """
    try:
        from .tasks import send_assignment_published_notification as task

        task.delay(assignment_id)
    except ImportError:
        logger.warning("Celery tasks not available, skipping notification")


def send_submission_received_notification(submission_id):
    """
    Celery task to send submission received notification
    """
    try:
        from .tasks import send_submission_received_notification as task

        task.delay(submission_id)
    except ImportError:
        logger.warning("Celery tasks not available, skipping notification")


def send_grade_notification(submission_id):
    """
    Celery task to send grade notification
    """
    try:
        from .tasks import send_grade_notification as task

        task.delay(submission_id)
    except ImportError:
        logger.warning("Celery tasks not available, skipping notification")


def schedule_deadline_reminder(assignment_id, reminder_date):
    """
    Celery task to schedule deadline reminder
    """
    try:
        from .tasks import schedule_deadline_reminder as task

        task.apply_async(args=[assignment_id], eta=reminder_date)
    except ImportError:
        logger.warning("Celery tasks not available, skipping reminder scheduling")


def update_assignment_analytics(assignment_id):
    """
    Celery task to update assignment analytics
    """
    try:
        from .tasks import update_assignment_analytics as task

        task.delay(assignment_id)
    except ImportError:
        logger.warning("Celery tasks not available, skipping analytics update")


# Signal for handling file cleanup when assignments/submissions are updated
@receiver(pre_save, sender=Assignment)
def cleanup_old_assignment_files(sender, instance, **kwargs):
    """
    Clean up old files when assignment attachments are updated
    """
    if instance.pk:
        try:
            old_instance = Assignment.objects.get(pk=instance.pk)
            if (
                old_instance.attachment
                and old_instance.attachment != instance.attachment
            ):
                # Delete old file
                old_instance.attachment.delete(save=False)
        except Assignment.DoesNotExist:
            pass
        except Exception as e:
            logger.warning(f"Error cleaning up old assignment file: {str(e)}")


@receiver(pre_save, sender=AssignmentSubmission)
def cleanup_old_submission_files(sender, instance, **kwargs):
    """
    Clean up old files when submission attachments are updated
    """
    if instance.pk:
        try:
            old_instance = AssignmentSubmission.objects.get(pk=instance.pk)
            if (
                old_instance.attachment
                and old_instance.attachment != instance.attachment
            ):
                # Delete old file
                old_instance.attachment.delete(save=False)
        except AssignmentSubmission.DoesNotExist:
            pass
        except Exception as e:
            logger.warning(f"Error cleaning up old submission file: {str(e)}")


# Signal for tracking user activity
@receiver(post_save, sender=Assignment)
def track_assignment_activity(sender, instance, created, **kwargs):
    """
    Track assignment-related user activity for analytics
    """
    try:
        from core.services import ActivityTracker

        action = "assignment_created" if created else "assignment_updated"

        ActivityTracker.track_activity(
            user=instance.teacher.user,
            action=action,
            entity_type="Assignment",
            entity_id=instance.id,
            metadata={
                "class_id": instance.class_id.id,
                "subject_id": instance.subject.id,
                "total_marks": instance.total_marks,
                "due_date": instance.due_date.isoformat(),
            },
        )

    except ImportError:
        pass  # ActivityTracker not available
    except Exception as e:
        logger.warning(f"Error tracking assignment activity: {str(e)}")


@receiver(post_save, sender=AssignmentSubmission)
def track_submission_activity(sender, instance, created, **kwargs):
    """
    Track submission-related user activity for analytics
    """
    try:
        from core.services import ActivityTracker

        action = "submission_created" if created else "submission_updated"

        ActivityTracker.track_activity(
            user=instance.student.user,
            action=action,
            entity_type="AssignmentSubmission",
            entity_id=instance.id,
            metadata={
                "assignment_id": instance.assignment.id,
                "is_late": instance.is_late,
                "marks_obtained": instance.marks_obtained,
                "status": instance.status,
            },
        )

    except ImportError:
        pass  # ActivityTracker not available
    except Exception as e:
        logger.warning(f"Error tracking submission activity: {str(e)}")
