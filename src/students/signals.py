# students/signals.py
import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.cache import cache
from django.core.mail import send_mail
from django.db import transaction
from django.db.models.signals import post_delete, post_save, pre_delete, pre_save
from django.dispatch import receiver
from django.template.loader import render_to_string
from django.utils import timezone

from .models import Parent, Student, StudentParentRelation

User = get_user_model()
logger = logging.getLogger(__name__)


@receiver(post_save, sender=Student)
def handle_student_created_updated(sender, instance, created, **kwargs):
    """Handle student creation and updates"""
    try:
        if created:
            # Assign student role
            student_group, _ = Group.objects.get_or_create(name="Student")
            instance.user.groups.add(student_group)

            # Ensure user is active
            if not instance.user.is_active:
                instance.user.is_active = True
                instance.user.save(update_fields=["is_active"])

            # Generate welcome email if email notifications are enabled
            if getattr(settings, "ENABLE_EMAIL_NOTIFICATIONS", True):
                try:
                    send_mail(
                        subject=f'Welcome to {getattr(settings, "SCHOOL_NAME", "School")}',
                        message=render_to_string(
                            "emails/student_welcome.txt",
                            {
                                "student": instance,
                                "school_name": getattr(
                                    settings, "SCHOOL_NAME", "School"
                                ),
                            },
                        ),
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[instance.user.email],
                        fail_silently=True,
                    )
                except Exception as e:
                    logger.error(
                        f"Failed to send welcome email to student {instance.admission_number}: {str(e)}"
                    )

            # Log creation
            logger.info(f"Created student: {instance.admission_number}")

        # Clear related cache on any save
        cache_keys = [
            f"student_attendance_percentage_{instance.id}",
            f"student_siblings_{instance.id}",
            f"student_parents_{instance.id}",
        ]
        cache.delete_many(cache_keys)

        # Log the creation/update in audit log
        from src.core.models import AuditLog

        AuditLog.objects.create(
            user=None,
            action="create" if created else "update",
            entity_type="student",
            entity_id=str(instance.id),
            data_after={
                "id": str(instance.id),
                "admission_number": instance.admission_number,
                "full_name": instance.get_full_name(),
                "status": instance.status,
            },
        )

    except Exception as e:
        logger.error(f"Error in student post_save signal: {str(e)}")


@receiver(post_save, sender=Parent)
def handle_parent_created_updated(sender, instance, created, **kwargs):
    """Handle parent creation and updates"""
    try:
        if created:
            # Assign parent role
            parent_group, _ = Group.objects.get_or_create(name="Parent")
            instance.user.groups.add(parent_group)

            # Ensure user is active
            if not instance.user.is_active:
                instance.user.is_active = True
                instance.user.save(update_fields=["is_active"])

            # Generate welcome email
            if getattr(settings, "ENABLE_EMAIL_NOTIFICATIONS", True):
                try:
                    send_mail(
                        subject=f'Parent Account Created - {getattr(settings, "SCHOOL_NAME", "School")}',
                        message=render_to_string(
                            "emails/parent_welcome.txt",
                            {
                                "parent": instance,
                                "school_name": getattr(
                                    settings, "SCHOOL_NAME", "School"
                                ),
                            },
                        ),
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[instance.user.email],
                        fail_silently=True,
                    )
                except Exception as e:
                    logger.error(
                        f"Failed to send welcome email to parent {instance.user.email}: {str(e)}"
                    )

            # Log creation
            logger.info(f"Created parent: {instance.get_full_name()}")

        # Log the creation/update in audit log
        from src.core.models import AuditLog

        AuditLog.objects.create(
            user=None,
            action="create" if created else "update",
            entity_type="parent",
            entity_id=str(instance.id),
            data_after={
                "id": str(instance.id),
                "full_name": instance.get_full_name(),
                "relation": instance.relation_with_student,
                "email": instance.user.email,
            },
        )

    except Exception as e:
        logger.error(f"Error in parent post_save signal: {str(e)}")


@receiver(pre_delete, sender=Student)
def handle_student_pre_delete(sender, instance, **kwargs):
    """Handle student deletion - log before deletion"""
    try:
        # Log the deletion
        from src.core.models import AuditLog

        AuditLog.objects.create(
            user=None,
            action="delete",
            entity_type="student",
            entity_id=str(instance.id),
            data_before={
                "id": str(instance.id),
                "admission_number": instance.admission_number,
                "full_name": instance.get_full_name(),
                "status": instance.status,
            },
        )
        logger.info(f"Deleting student: {instance.admission_number}")
    except Exception as e:
        logger.error(f"Error in student pre_delete signal: {str(e)}")


@receiver(post_delete, sender=Student)
def handle_student_post_delete(sender, instance, **kwargs):
    """Handle cleanup after student deletion"""
    try:
        # Clear related cache
        cache_keys = [
            f"student_attendance_percentage_{instance.id}",
            f"student_siblings_{instance.id}",
            f"student_parents_{instance.id}",
        ]
        cache.delete_many(cache_keys)

        # Clean up user if no other profiles exist
        user = instance.user
        if user and not user.is_staff:
            # Check if user has other profiles
            has_other_profiles = (
                hasattr(user, "teacher_profile")
                or hasattr(user, "parent_profile")
                or hasattr(user, "staff_profile")
            )

            if not has_other_profiles:
                logger.info(f"Deleting user {user.email} after student deletion")
                user.delete()

    except Exception as e:
        logger.error(f"Error in student post_delete signal: {str(e)}")


@receiver(pre_delete, sender=Parent)
def handle_parent_pre_delete(sender, instance, **kwargs):
    """Handle parent deletion - log before deletion"""
    try:
        # Log the deletion
        from src.core.models import AuditLog

        AuditLog.objects.create(
            user=None,
            action="delete",
            entity_type="parent",
            entity_id=str(instance.id),
            data_before={
                "id": str(instance.id),
                "full_name": instance.get_full_name(),
                "relation": instance.relation_with_student,
                "email": instance.user.email,
            },
        )
        logger.info(f"Deleting parent: {instance.get_full_name()}")
    except Exception as e:
        logger.error(f"Error in parent pre_delete signal: {str(e)}")


@receiver(post_delete, sender=Parent)
def handle_parent_post_delete(sender, instance, **kwargs):
    """Handle cleanup after parent deletion"""
    try:
        # Clean up user if no other profiles exist
        user = instance.user
        if user and not user.is_staff:
            # Check if user has other profiles
            has_other_profiles = (
                hasattr(user, "teacher_profile")
                or hasattr(user, "student_profile")
                or hasattr(user, "staff_profile")
            )

            if not has_other_profiles:
                logger.info(f"Deleting user {user.email} after parent deletion")
                user.delete()

    except Exception as e:
        logger.error(f"Error in parent post_delete signal: {str(e)}")


@receiver(post_save, sender=StudentParentRelation)
def handle_relation_created_updated(sender, instance, created, **kwargs):
    """Handle student-parent relationship creation and updates"""
    try:
        if created:
            # Clear related cache
            cache.delete_many(
                [
                    f"student_parents_{instance.student.id}",
                    f"student_siblings_{instance.student.id}",
                ]
            )

            # Send notification to parent if enabled
            if getattr(settings, "ENABLE_EMAIL_NOTIFICATIONS", True):
                try:
                    send_mail(
                        subject=f'Student Relationship - {getattr(settings, "SCHOOL_NAME", "School")}',
                        message=render_to_string(
                            "emails/parent_student_linked.txt",
                            {
                                "student": instance.student,
                                "parent": instance.parent,
                                "is_primary": instance.is_primary_contact,
                                "school_name": getattr(
                                    settings, "SCHOOL_NAME", "School"
                                ),
                            },
                        ),
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[instance.parent.user.email],
                        fail_silently=True,
                    )
                except Exception as e:
                    logger.error(f"Failed to send relationship notification: {str(e)}")

            # Log creation
            logger.info(
                f"Created relationship: {instance.student.admission_number} - {instance.parent.get_full_name()}"
            )

        # Log the creation/update in audit log
        from src.core.models import AuditLog

        AuditLog.objects.create(
            user=getattr(instance, "created_by", None),
            action="create" if created else "update",
            entity_type="student_parent_relation",
            entity_id=str(instance.id),
            data_after={
                "student_id": str(instance.student.id),
                "parent_id": str(instance.parent.id),
                "is_primary_contact": instance.is_primary_contact,
                "can_pickup": instance.can_pickup,
            },
        )

    except Exception as e:
        logger.error(f"Error in relation post_save signal: {str(e)}")


@receiver(post_delete, sender=StudentParentRelation)
def handle_relation_deleted(sender, instance, **kwargs):
    """Handle relationship deletion"""
    try:
        # Clear related cache
        cache.delete_many(
            [
                f"student_parents_{instance.student.id}",
                f"student_siblings_{instance.student.id}",
            ]
        )

        # Log the deletion
        from src.core.models import AuditLog

        AuditLog.objects.create(
            user=None,
            action="delete",
            entity_type="student_parent_relation",
            entity_id=str(instance.id),
            data_before={
                "student_id": str(instance.student.id),
                "parent_id": str(instance.parent.id),
                "is_primary_contact": instance.is_primary_contact,
            },
        )

        logger.info(
            f"Deleted relationship: {instance.student.admission_number} - {instance.parent.get_full_name()}"
        )

    except Exception as e:
        logger.error(f"Error in relation post_delete signal: {str(e)}")


@receiver(pre_save, sender=Student)
def handle_student_status_change(sender, instance, **kwargs):
    """Handle student status changes"""
    try:
        if instance.pk:
            # Get the previous state
            try:
                old_instance = Student.objects.get(pk=instance.pk)

                # Check if status changed
                if old_instance.status != instance.status:
                    # Log status change
                    from src.core.models import AuditLog

                    AuditLog.objects.create(
                        user=None,
                        action="status_change",
                        entity_type="student",
                        entity_id=str(instance.id),
                        data_before={"status": old_instance.status},
                        data_after={"status": instance.status},
                    )

                    # Handle graduation
                    if (
                        instance.status == "Graduated"
                        and old_instance.status != "Graduated"
                    ):
                        # Send graduation notification
                        if getattr(settings, "ENABLE_EMAIL_NOTIFICATIONS", True):
                            try:
                                # Notify student
                                send_mail(
                                    subject="Congratulations on Your Graduation!",
                                    message=render_to_string(
                                        "emails/student_graduated.txt",
                                        {
                                            "student": instance,
                                            "school_name": getattr(
                                                settings, "SCHOOL_NAME", "School"
                                            ),
                                        },
                                    ),
                                    from_email=settings.DEFAULT_FROM_EMAIL,
                                    recipient_list=[instance.user.email],
                                    fail_silently=True,
                                )

                                # Notify parents
                                for parent in instance.get_parents():
                                    send_mail(
                                        subject=f"Graduation Notification - {instance.get_full_name()}",
                                        message=render_to_string(
                                            "emails/parent_child_graduated.txt",
                                            {
                                                "student": instance,
                                                "parent": parent,
                                                "school_name": getattr(
                                                    settings, "SCHOOL_NAME", "School"
                                                ),
                                            },
                                        ),
                                        from_email=settings.DEFAULT_FROM_EMAIL,
                                        recipient_list=[parent.user.email],
                                        fail_silently=True,
                                    )
                            except Exception as e:
                                logger.error(
                                    f"Failed to send graduation notifications: {str(e)}"
                                )

                        # Create graduation document record
                        try:
                            from src.core.models import Document

                            Document.objects.create(
                                title=f"Graduation Certificate - {instance.get_full_name()}",
                                description=f"Graduation certificate for {instance.get_full_name()}",
                                file_path=f"certificates/graduation_{instance.admission_number}_{timezone.now().strftime('%Y%m%d')}.pdf",
                                file_type="pdf",
                                uploaded_by=None,
                                category="Certificate",
                                related_to_id=str(instance.id),
                                related_to_type="Student",
                                is_public=False,
                            )
                        except ImportError:
                            # Document model not available
                            pass

                    logger.info(
                        f"Student {instance.admission_number} status changed from {old_instance.status} to {instance.status}"
                    )

            except Student.DoesNotExist:
                # New student, no previous state
                pass

    except Exception as e:
        logger.error(f"Error in student pre_save signal: {str(e)}")


# Signal for clearing cache when class is updated
@receiver(post_save, sender="courses.Class")
def clear_student_cache_on_class_update(sender, instance, **kwargs):
    """Clear student cache when class information is updated"""
    try:
        # Clear cache for all students in this class
        students = Student.objects.filter(current_class=instance)
        cache_keys = []
        for student in students:
            cache_keys.extend(
                [
                    f"student_attendance_percentage_{student.id}",
                    f"student_siblings_{student.id}",
                ]
            )

        if cache_keys:
            cache.delete_many(cache_keys)
            logger.info(
                f"Cleared cache for {len(students)} students in class {instance}"
            )

    except Exception as e:
        logger.error(f"Error clearing student cache on class update: {str(e)}")
