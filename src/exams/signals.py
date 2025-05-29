from django.db import transaction
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone

from src.communications.models import Notification

from .models import (
    Exam,
    ExamSchedule,
    ReportCard,
    StudentExamResult,
    StudentOnlineExamAttempt,
)
from .tasks import (
    auto_grade_online_exam,
    calculate_exam_rankings,
    send_report_card_notifications,
    send_result_notifications,
)


@receiver(post_save, sender=StudentExamResult)
def handle_exam_result_saved(sender, instance, created, **kwargs):
    """Handle actions when exam result is saved"""
    if created:
        # Schedule ranking calculation (delayed to batch process)
        transaction.on_commit(
            lambda: calculate_exam_rankings.apply_async(
                args=[str(instance.exam_schedule.id)],
                countdown=30,  # Wait 30 seconds to batch multiple results
            )
        )

        # Send result notification
        transaction.on_commit(
            lambda: send_result_notifications.delay([str(instance.id)])
        )


@receiver(post_save, sender=StudentOnlineExamAttempt)
def handle_online_exam_submitted(sender, instance, created, **kwargs):
    """Handle online exam submission"""
    if not created and instance.status == "SUBMITTED" and not instance.is_graded:
        # Auto-grade objective questions
        transaction.on_commit(lambda: auto_grade_online_exam.delay(str(instance.id)))


@receiver(post_save, sender=ExamSchedule)
def handle_exam_schedule_completed(sender, instance, created, **kwargs):
    """Handle exam schedule completion"""
    if not created and instance.is_completed:
        # Update exam completion statistics
        exam = instance.exam
        total_schedules = exam.schedules.count()
        completed_schedules = exam.schedules.filter(is_completed=True).count()

        if total_schedules > 0:
            completion_percentage = (completed_schedules / total_schedules) * 100
            if completion_percentage == 100:
                exam.status = "COMPLETED"
                exam.save(update_fields=["status"])


@receiver(post_save, sender=ReportCard)
def handle_report_card_published(sender, instance, created, **kwargs):
    """Handle report card publication"""
    if not created and instance.status == "PUBLISHED":
        # Send report card notification
        transaction.on_commit(
            lambda: send_report_card_notifications.delay([str(instance.id)])
        )


@receiver(pre_save, sender=Exam)
def handle_exam_status_change(sender, instance, **kwargs):
    """Handle exam status changes"""
    if instance.pk:
        try:
            old_instance = Exam.objects.get(pk=instance.pk)

            # If exam is being published
            if not old_instance.is_published and instance.is_published:
                instance.status = "SCHEDULED"

                # Create notifications for relevant students
                # This could be expanded to notify students of the exam
                pass

        except Exam.DoesNotExist:
            pass
