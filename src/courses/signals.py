from django.db.models.signals import post_save
from django.dispatch import receiver
from src.courses.models import Assignment, AssignmentSubmission
from src.communications.models import Notification


@receiver(post_save, sender=Assignment)
def assignment_notification(sender, instance, created, **kwargs):
    """Send notification to students when an assignment is published"""
    if created or (not created and instance.status == "published"):
        if instance.status == "published":
            # Get all students in the class
            students = instance.class_obj.students.all()

            # Create notification for each student
            for student in students:
                Notification.objects.create(
                    user=student.user,
                    title="New Assignment",
                    content=f"A new assignment '{instance.title}' has been published for {instance.subject.name}.",
                    notification_type="Assignment",
                    reference_id=instance.id,
                    priority="Medium",
                )


@receiver(post_save, sender=AssignmentSubmission)
def submission_notification(sender, instance, created, **kwargs):
    """Send notification when an assignment is graded"""
    if not created and instance.status == "graded":
        # Notify student
        Notification.objects.create(
            user=instance.student.user,
            title="Assignment Graded",
            content=f"Your submission for '{instance.assignment.title}' has been graded.",
            notification_type="Assignment",
            reference_id=instance.id,
            priority="Medium",
        )
