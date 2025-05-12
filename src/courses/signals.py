from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.utils import timezone
from datetime import timedelta
from .models import Assignment, AssignmentSubmission, Class, AcademicYear
from src.communications.models import Notification


@receiver(post_save, sender=Assignment)
def create_assignment_notification(sender, instance, created, **kwargs):
    """Create notification for new or published assignments."""
    if not created and instance.status == "published":
        # Get all students in the class
        students = instance.class_obj.students.all()

        # Create notification for each student
        for student in students:
            # Check if notification already exists
            notification_exists = Notification.objects.filter(
                user=student.user,
                notification_type="Assignment",
                reference_id=instance.id,
            ).exists()

            if not notification_exists:
                # Create new notification
                Notification.objects.create(
                    user=student.user,
                    title="New Assignment",
                    content=f'A new assignment "{instance.title}" has been published for {instance.subject.name}.',
                    notification_type="Assignment",
                    reference_id=instance.id,
                    priority="Medium",
                )


@receiver(post_save, sender=AssignmentSubmission)
def update_assignment_submission(sender, instance, created, **kwargs):
    """Handle notification for graded assignments."""
    if not created and instance.status == "graded":
        # Notify student
        Notification.objects.create(
            user=instance.student.user,
            title="Assignment Graded",
            content=f'Your submission for "{instance.assignment.title}" has been graded.',
            notification_type="Assignment",
            reference_id=instance.id,
            priority="Medium",
        )

        # Notify teacher about late submissions
        if instance.status == "late" and created:
            Notification.objects.create(
                user=instance.assignment.teacher.user,
                title="Late Assignment Submission",
                content=f'{instance.student.user.get_full_name()} has submitted "{instance.assignment.title}" late.',
                notification_type="Assignment",
                reference_id=instance.id,
                priority="Low",
            )


@receiver(post_save, sender=Class)
def assign_class_teacher(sender, instance, created, **kwargs):
    """Update teacher's assigned_classes when set as class teacher."""
    if instance.class_teacher:
        # No need to create a TeacherClassAssignment as we're simply tracking
        # the class teacher relationship directly in the Class model
        pass


@receiver(post_save, sender=AcademicYear)
def update_current_academic_year(sender, instance, **kwargs):
    """Ensure only one academic year is marked as current."""
    if instance.is_current:
        # Set all other academic years as not current
        AcademicYear.objects.exclude(pk=instance.pk).update(is_current=False)
