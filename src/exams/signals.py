from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.utils import timezone

from .models import (
    Exam,
    ExamSchedule,
    Quiz,
    StudentExamResult,
    StudentQuizAttempt,
    StudentQuizResponse,
)
from src.communications.models import Notification


@receiver(post_save, sender=Exam)
def handle_exam_status_change(sender, instance, **kwargs):
    """
    Signal to handle status changes for exams.
    """
    if (
        not kwargs.get("created", False)
        and kwargs.get("update_fields")
        and "status" in kwargs["update_fields"]
    ):
        if instance.status == "ongoing":
            # Notify students in classes that have schedules for this exam
            class_ids = (
                ExamSchedule.objects.filter(exam=instance)
                .values_list("class_obj_id", flat=True)
                .distinct()
            )
            students = []

            try:
                from src.students.models import Student

                students = Student.objects.filter(current_class_id__in=class_ids)
            except (ImportError, ValueError):
                pass

            for student in students:
                try:
                    Notification.objects.create(
                        user=student.user,
                        title=f"Exam {instance.name} Started",
                        content=f"The {instance.name} exam has now started and will run until {instance.end_date}.",
                        notification_type="Exam",
                        reference_id=instance.id,
                        priority="High",
                    )
                except Exception:
                    pass


@receiver(post_save, sender=ExamSchedule)
def notify_exam_schedule_creation(sender, instance, created, **kwargs):
    """
    Signal to notify about new exam schedules.
    """
    if created:
        # Notify students in the class
        try:
            from src.students.models import Student

            students = Student.objects.filter(current_class=instance.class_obj)

            for student in students:
                Notification.objects.create(
                    user=student.user,
                    title=f"New Exam Schedule: {instance.subject.name}",
                    content=f"Your {instance.subject.name} exam for {instance.exam.name} is scheduled on {instance.date} from {instance.start_time} to {instance.end_time} in {instance.room}.",
                    notification_type="Exam",
                    reference_id=instance.id,
                    priority="Medium",
                )
        except Exception:
            pass


@receiver(post_save, sender=StudentExamResult)
def notify_exam_result(sender, instance, created, **kwargs):
    """
    Signal to notify students when their exam results are entered.
    """
    if created or (not created and "marks_obtained" in kwargs.get("update_fields", [])):
        # Notify the student
        try:
            Notification.objects.create(
                user=instance.student.user,
                title=f"Exam Result: {instance.exam_schedule.subject.name}",
                content=f"Your result for {instance.exam_schedule.subject.name} in {instance.exam_schedule.exam.name} has been published. You scored {instance.marks_obtained}/{instance.exam_schedule.total_marks}.",
                notification_type="Result",
                reference_id=instance.id,
                priority="High",
            )
        except Exception:
            pass


@receiver(post_save, sender=Quiz)
def notify_quiz_publication(sender, instance, **kwargs):
    """
    Signal to notify students when a quiz is published.
    """
    if instance.status == "published" and (
        kwargs.get("created", False)
        or (kwargs.get("update_fields") and "status" in kwargs["update_fields"])
    ):
        # Notify students in the class
        try:
            from src.students.models import Student

            students = Student.objects.filter(current_class=instance.class_obj)

            for student in students:
                Notification.objects.create(
                    user=student.user,
                    title=f"New Quiz: {instance.title}",
                    content=f"A new quiz '{instance.title}' for {instance.subject.name} has been published. It is available from {instance.start_datetime} to {instance.end_datetime}.",
                    notification_type="Quiz",
                    reference_id=instance.id,
                    priority="Medium",
                )
        except Exception:
            pass


@receiver(post_save, sender=StudentQuizAttempt)
def notify_quiz_completion(sender, instance, **kwargs):
    """
    Signal to notify when a quiz attempt is completed and graded.
    """
    if (
        instance.end_time
        and instance.marks_obtained is not None
        and (
            kwargs.get("created", False)
            or (
                kwargs.get("update_fields")
                and (
                    "end_time" in kwargs["update_fields"]
                    or "marks_obtained" in kwargs["update_fields"]
                )
            )
        )
    ):
        # Notify the student
        try:
            Notification.objects.create(
                user=instance.student.user,
                title=f"Quiz Completed: {instance.quiz.title}",
                content=f"Your attempt for '{instance.quiz.title}' has been completed and graded. You scored {instance.marks_obtained}/{instance.quiz.total_marks}.",
                notification_type="Quiz",
                reference_id=instance.id,
                priority="Medium",
            )
        except Exception:
            pass
