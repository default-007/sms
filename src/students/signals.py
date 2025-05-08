# students/signals.py
from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.utils import timezone
from django.db import transaction

from .models import Student, Parent, StudentParentRelation

User = get_user_model()


@receiver(post_save, sender=Student)
def assign_student_role(sender, instance, created, **kwargs):
    """
    Assign the Student role to user when a Student profile is created.
    """
    if created:
        # Get or create Student group
        student_group, _ = Group.objects.get_or_create(name="Student")
        instance.user.groups.add(student_group)

        # Ensure the user is active
        if not instance.user.is_active:
            instance.user.is_active = True
            instance.user.save(update_fields=["is_active"])

        # Log the creation
        from src.core.models import AuditLog

        try:
            AuditLog.objects.create(
                user=None,  # Can be set to the user performing the action
                action="create",
                entity_type="student",
                entity_id=instance.id,
                data_after={
                    "id": instance.id,
                    "admission_number": instance.admission_number,
                    "full_name": instance.get_full_name(),
                },
            )
        except:
            # AuditLog might not be available
            pass


@receiver(post_save, sender=Parent)
def assign_parent_role(sender, instance, created, **kwargs):
    """
    Assign the Parent role to user when a Parent profile is created.
    """
    if created:
        # Get or create Parent group
        parent_group, _ = Group.objects.get_or_create(name="Parent")
        instance.user.groups.add(parent_group)

        # Ensure the user is active
        if not instance.user.is_active:
            instance.user.is_active = True
            instance.user.save(update_fields=["is_active"])

        # Log the creation
        from src.core.models import AuditLog

        try:
            AuditLog.objects.create(
                user=None,
                action="create",
                entity_type="parent",
                entity_id=instance.id,
                data_after={
                    "id": instance.id,
                    "full_name": instance.get_full_name(),
                    "relation": instance.relation_with_student,
                },
            )
        except:
            pass


@receiver(post_delete, sender=Student)
def handle_student_delete(sender, instance, **kwargs):
    """
    Handle user cleanup when a Student profile is deleted.
    """
    # Log the deletion
    from src.core.models import AuditLog

    try:
        AuditLog.objects.create(
            user=None,
            action="delete",
            entity_type="student",
            entity_id=instance.id,
            data_before={
                "id": instance.id,
                "admission_number": instance.admission_number,
                "full_name": instance.get_full_name(),
            },
        )
    except:
        pass

    # Delete user if no other profiles exist
    user = instance.user
    if (
        user
        and not user.is_staff
        and not hasattr(user, "teacher_profile")
        and not hasattr(user, "parent_profile")
    ):
        user.delete()


@receiver(post_delete, sender=Parent)
def handle_parent_delete(sender, instance, **kwargs):
    """
    Handle user cleanup when a Parent profile is deleted.
    """
    # Log the deletion
    from src.core.models import AuditLog

    try:
        AuditLog.objects.create(
            user=None,
            action="delete",
            entity_type="parent",
            entity_id=instance.id,
            data_before={
                "id": instance.id,
                "full_name": instance.get_full_name(),
                "relation": instance.relation_with_student,
            },
        )
    except:
        pass

    # Delete user if no other profiles exist
    user = instance.user
    if (
        user
        and not user.is_staff
        and not hasattr(user, "teacher_profile")
        and not hasattr(user, "student_profile")
    ):
        user.delete()


@receiver(post_save, sender=StudentParentRelation)
def handle_relation_created(sender, instance, created, **kwargs):
    """
    Handle events when a student-parent relationship is created or updated
    """
    if created:
        # Send notification to parent if communication module is available
        try:
            from src.communications.models import Notification

            Notification.objects.create(
                user=instance.parent.user,
                title="Student Link",
                content=f"You have been linked as {instance.parent.relation_with_student} to student {instance.student.get_full_name()}.",
                notification_type="System",
                reference_id=instance.id,
                priority="Medium",
            )
        except:
            pass


@receiver(pre_save, sender=Student)
def handle_student_status_change(sender, instance, **kwargs):
    """
    Handle events when a student's status changes
    """
    # Check if this is an update operation
    if instance.pk:
        try:
            # Get the previous state
            old_instance = Student.objects.get(pk=instance.pk)

            # Check if status changed
            if old_instance.status != instance.status:
                # Log the status change
                from src.core.models import AuditLog

                try:
                    AuditLog.objects.create(
                        user=None,
                        action="update",
                        entity_type="student_status",
                        entity_id=instance.id,
                        data_before={"status": old_instance.status},
                        data_after={"status": instance.status},
                    )
                except:
                    pass

                # If graduated, create certificate if documents module is available
                if (
                    instance.status == "Graduated"
                    and old_instance.status != "Graduated"
                ):
                    try:
                        from src.core.models import Document
                        from src.core.services import DocumentService

                        # Generate certificate (placeholder for actual certificate generation)
                        certificate_path = f"certificates/graduation_{instance.admission_number}_{timezone.now().strftime('%Y%m%d')}.pdf"

                        # Create document record
                        Document.objects.create(
                            title=f"Graduation Certificate - {instance.get_full_name()}",
                            description=f"Graduation certificate for {instance.get_full_name()}",
                            file_path=certificate_path,
                            file_type="pdf",
                            uploaded_by=None,  # Can be set to the user performing the action
                            category="Certificate",
                            related_to_id=str(instance.id),
                            related_to_type="Student",
                            is_public=False,
                        )
                    except:
                        pass
        except Student.DoesNotExist:
            pass
