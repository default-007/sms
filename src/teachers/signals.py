from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from django.utils import timezone

from src.teachers.models import Teacher, TeacherEvaluation

User = get_user_model()


@receiver(post_save, sender=Teacher)
def assign_teacher_role(sender, instance, created, **kwargs):
    """
    Assign the Teacher role to user when a Teacher profile is created.
    """
    if created:
        # Add to Teacher group
        teacher_group, _ = Group.objects.get_or_create(name="Teacher")
        instance.user.groups.add(teacher_group)

        # Ensure the user is active
        if not instance.user.is_active:
            instance.user.is_active = True
            instance.user.save()

        # Log the creation
        from src.core.models import AuditLog

        AuditLog.objects.create(
            user=instance.user,
            action="CREATE",
            entity_type="Teacher",
            entity_id=instance.id,
            data_after={
                "employee_id": instance.employee_id,
                "status": instance.status,
                "position": instance.position,
                "department": instance.department.name if instance.department else None,
            },
        )


@receiver(post_delete, sender=Teacher)
def handle_teacher_delete(sender, instance, **kwargs):
    """
    Handle user cleanup when a Teacher profile is deleted.
    """
    user = instance.user
    if (
        user
        and not user.is_staff
        and not hasattr(user, "student_profile")
        and not hasattr(user, "parent_profile")
    ):
        user.delete()


@receiver(post_save, sender=TeacherEvaluation)
def handle_evaluation_save(sender, instance, created, **kwargs):
    """
    Handle follow-up actions when an evaluation is created or updated.
    """
    if created:
        # Set follow-up date for low scores
        if instance.score < 70 and not instance.followup_date:
            # Set follow-up date to 30 days from evaluation date
            instance.followup_date = instance.evaluation_date + timezone.timedelta(
                days=30
            )
            instance.save(update_fields=["followup_date"])

        # Log the evaluation
        from src.communications.models import Notification
        from src.core.models import AuditLog

        # Create audit log
        AuditLog.objects.create(
            user=instance.evaluator,
            action="CREATE",
            entity_type="TeacherEvaluation",
            entity_id=instance.id,
            data_after={
                "teacher": instance.teacher.get_full_name(),
                "score": float(instance.score),
                "status": instance.status,
                "evaluation_date": instance.evaluation_date.isoformat(),
            },
        )

        # Create notification for the teacher
        Notification.objects.create(
            user=instance.teacher.user,
            title="New Evaluation",
            content=f"You have a new evaluation with a score of {instance.score}%. Please review it.",
            notification_type="Evaluation",
            reference_id=instance.id,
            priority="High" if instance.score < 70 else "Medium",
        )

        # Create notification for department head if score is low
        if (
            instance.score < 70
            and instance.teacher.department
            and instance.teacher.department.head
        ):
            Notification.objects.create(
                user=instance.teacher.department.head.user,
                title="Low Performance Evaluation",
                content=f"{instance.teacher.get_full_name()} has a low evaluation score of {instance.score}%. Please review.",
                notification_type="Evaluation",
                reference_id=instance.id,
                priority="High",
            )
