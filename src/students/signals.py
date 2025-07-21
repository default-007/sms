# students/signals.py
import logging

from django.conf import settings
from django.contrib.auth import get_user_model
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
    """Handle student creation and updates (no user account creation)"""
    try:
        if created:
            logger.info(
                f"Student created: {instance.admission_number} - {instance.full_name}"
            )

            # Send welcome email if email is provided and notifications are enabled
            if (
                instance.email
                and getattr(settings, "ENABLE_EMAIL_NOTIFICATIONS", True)
                and getattr(settings, "STUDENT_EMAIL_SETTINGS", {}).get(
                    "ENABLE_WELCOME_EMAILS", True
                )
            ):
                try:
                    send_welcome_email_to_student(instance)
                except Exception as e:
                    logger.error(
                        f"Failed to send welcome email to student {instance.admission_number}: {str(e)}"
                    )

            # Notify parents about new student creation
            try:
                notify_parents_student_created(instance)
            except Exception as e:
                logger.error(
                    f"Failed to notify parents about student creation: {str(e)}"
                )

            # Send notification to administrators
            try:
                notify_admins_student_created(instance)
            except Exception as e:
                logger.error(
                    f"Failed to notify admins about student creation: {str(e)}"
                )

        else:
            # Student updated
            logger.info(
                f"Student updated: {instance.admission_number} - {instance.full_name}"
            )

            # Clear related caches
            clear_student_caches(instance)

            # Notify parents about updates if enabled
            if (
                getattr(settings, "NOTIFICATION_SETTINGS", {})
                .get("STUDENT_UPDATED", {})
                .get("ENABLED", False)
            ):
                try:
                    notify_parents_student_updated(instance)
                except Exception as e:
                    logger.error(
                        f"Failed to notify parents about student update: {str(e)}"
                    )

    except Exception as e:
        logger.error(f"Error in student post_save signal: {str(e)}")


@receiver(pre_save, sender=Student)
def handle_student_pre_save(sender, instance, **kwargs):
    """Handle pre-save operations for students"""
    try:
        if instance.pk:
            # Get the old instance to compare changes
            try:
                old_instance = Student.objects.get(pk=instance.pk)

                # Check for status changes
                if old_instance.status != instance.status:
                    logger.info(
                        f"Student status changed: {instance.admission_number} from {old_instance.status} to {instance.status}"
                    )

                    # Store status change info for post_save signal
                    instance._status_changed = True
                    instance._old_status = old_instance.status
                    instance._new_status = instance.status

                # Check for class changes
                if old_instance.current_class != instance.current_class:
                    logger.info(
                        f"Student class changed: {instance.admission_number} from {old_instance.current_class} to {instance.current_class}"
                    )

                    # Store class change info for post_save signal
                    instance._class_changed = True
                    instance._old_class = old_instance.current_class
                    instance._new_class = instance.current_class

            except Student.DoesNotExist:
                pass

        # Ensure admission number is uppercase and properly formatted
        if instance.admission_number:
            instance.admission_number = instance.admission_number.upper().strip()

        # Ensure names are properly formatted
        if instance.first_name:
            instance.first_name = instance.first_name.strip().title()
        if instance.last_name:
            instance.last_name = instance.last_name.strip().title()

        # Set default values
        if not instance.status:
            instance.status = getattr(settings, "STUDENT_SETTINGS", {}).get(
                "DEFAULT_STUDENT_STATUS", "Active"
            )

    except Exception as e:
        logger.error(f"Error in student pre_save signal: {str(e)}")


@receiver(post_save, sender=Student)
def handle_student_status_class_changes(sender, instance, created, **kwargs):
    """Handle status and class changes after save"""
    if not created:
        try:
            # Handle status changes
            if getattr(instance, "_status_changed", False):
                notify_status_change(instance)

            # Handle class changes (promotions)
            if getattr(instance, "_class_changed", False):
                notify_class_change(instance)

            # Clean up temporary attributes
            if hasattr(instance, "_status_changed"):
                delattr(instance, "_status_changed")
            if hasattr(instance, "_old_status"):
                delattr(instance, "_old_status")
            if hasattr(instance, "_new_status"):
                delattr(instance, "_new_status")
            if hasattr(instance, "_class_changed"):
                delattr(instance, "_class_changed")
            if hasattr(instance, "_old_class"):
                delattr(instance, "_old_class")
            if hasattr(instance, "_new_class"):
                delattr(instance, "_new_class")

        except Exception as e:
            logger.error(f"Error handling student status/class changes: {str(e)}")


@receiver(pre_delete, sender=Student)
def handle_student_pre_delete(sender, instance, **kwargs):
    """Handle student deletion preparation"""
    try:
        logger.warning(
            f"Student deletion initiated: {instance.admission_number} - {instance.full_name}"
        )

        # Store student info for post_delete signal
        instance._deleted_info = {
            "admission_number": instance.admission_number,
            "full_name": instance.full_name,
            "email": instance.email,
            "parent_emails": [
                parent.user.email
                for parent in instance.get_parents()
                if parent.user.email
            ],
        }

    except Exception as e:
        logger.error(f"Error in student pre_delete signal: {str(e)}")


@receiver(post_delete, sender=Student)
def handle_student_deleted(sender, instance, **kwargs):
    """Handle post-deletion cleanup"""
    try:
        deleted_info = getattr(instance, "_deleted_info", {})
        admission_number = deleted_info.get("admission_number", "Unknown")

        logger.warning(f"Student deleted: {admission_number}")

        # Clear all related caches
        cache_keys = [
            f"student_attendance_percentage_{instance.id}",
            f"student_siblings_{instance.id}",
            f"student_parents_{instance.id}",
            f"student_analytics_{instance.id}",
        ]
        cache.delete_many(cache_keys)

        # Notify parents about deletion if enabled
        parent_emails = deleted_info.get("parent_emails", [])
        if parent_emails and getattr(settings, "ENABLE_EMAIL_NOTIFICATIONS", True):
            try:
                notify_parents_student_deleted(deleted_info, parent_emails)
            except Exception as e:
                logger.error(
                    f"Failed to notify parents about student deletion: {str(e)}"
                )

    except Exception as e:
        logger.error(f"Error in student post_delete signal: {str(e)}")


@receiver(post_save, sender=StudentParentRelation)
def handle_student_parent_relation_created(sender, instance, created, **kwargs):
    """Handle student-parent relationship changes"""
    try:
        if created:
            logger.info(
                f"New parent-student relationship: {instance.parent.full_name} -> {instance.student.full_name}"
            )

        # Clear related caches
        clear_student_caches(instance.student)

        # Clear parent-related caches
        cache_keys = [
            f"parent_students_{instance.parent.id}",
            f"parent_primary_students_{instance.parent.id}",
        ]
        cache.delete_many(cache_keys)

    except Exception as e:
        logger.error(f"Error in student-parent relation signal: {str(e)}")


@receiver(post_delete, sender=StudentParentRelation)
def handle_student_parent_relation_deleted(sender, instance, **kwargs):
    """Handle student-parent relationship deletion"""
    try:
        logger.info(
            f"Parent-student relationship deleted: {instance.parent.full_name} -> {instance.student.full_name}"
        )

        # Clear related caches
        clear_student_caches(instance.student)

    except Exception as e:
        logger.error(f"Error in student-parent relation deletion signal: {str(e)}")


# Helper functions for notifications


def send_welcome_email_to_student(student):
    """Send welcome email directly to student if email provided"""
    if not student.email:
        return

    try:
        subject = (
            f'Welcome to {getattr(settings, "SCHOOL_INFO", {}).get("NAME", "School")}'
        )

        context = {
            "student": student,
            "school_name": getattr(settings, "SCHOOL_INFO", {}).get("NAME", "School"),
            "school_email": getattr(settings, "SCHOOL_INFO", {}).get("EMAIL", ""),
            "school_phone": getattr(settings, "SCHOOL_INFO", {}).get("PHONE", ""),
            "current_year": timezone.now().year,
        }

        # Render email template
        try:
            template_path = (
                getattr(settings, "STUDENT_EMAIL_SETTINGS", {})
                .get("EMAIL_TEMPLATES", {})
                .get("WELCOME", "emails/student_welcome.html")
            )

            html_message = render_to_string(template_path, context)
            plain_message = render_to_string(
                template_path.replace(".html", ".txt"), context
            )
        except Exception:
            # Fallback to simple message
            plain_message = f"""
Welcome to {context['school_name']}!

Dear {student.first_name} {student.last_name},

We are pleased to welcome you to our school. Your admission number is: {student.admission_number}

Please contact us if you have any questions.

Best regards,
{context['school_name']} Administration
            """.strip()
            html_message = None

        send_mail(
            subject=subject,
            message=plain_message,
            from_email=getattr(settings, "STUDENT_EMAIL_SETTINGS", {}).get(
                "FROM_EMAIL", settings.DEFAULT_FROM_EMAIL
            ),
            recipient_list=[student.email],
            html_message=html_message,
            fail_silently=False,
        )

        logger.info(f"Welcome email sent to student: {student.email}")

    except Exception as e:
        logger.error(f"Failed to send welcome email to student: {str(e)}")
        raise


def notify_parents_student_created(student):
    """Notify parents about new student creation"""
    parents = student.get_parents()

    for parent in parents:
        if parent.user.email:
            try:
                subject = f"New Student Profile Created - {student.full_name}"

                context = {
                    "parent": parent,
                    "student": student,
                    "school_name": getattr(settings, "SCHOOL_INFO", {}).get(
                        "NAME", "School"
                    ),
                }

                message = f"""
Dear {parent.full_name},

A new student profile has been created for {student.full_name}.

Student Details:
- Admission Number: {student.admission_number}
- Class: {student.current_class or 'Not assigned'}
- Status: {student.status}

Please log in to the parent portal to view complete details.

Best regards,
{context['school_name']} Administration
                """.strip()

                send_mail(
                    subject=subject,
                    message=message,
                    from_email=getattr(settings, "STUDENT_EMAIL_SETTINGS", {}).get(
                        "FROM_EMAIL", settings.DEFAULT_FROM_EMAIL
                    ),
                    recipient_list=[parent.user.email],
                    fail_silently=False,
                )

            except Exception as e:
                logger.error(
                    f"Failed to send notification to parent {parent.user.email}: {str(e)}"
                )


def notify_parents_student_updated(student):
    """Notify parents about student profile updates"""
    parents = student.get_parents()

    for parent in parents:
        if parent.user.email:
            try:
                subject = f"Student Profile Updated - {student.full_name}"

                message = f"""
Dear {parent.full_name},

The profile for {student.full_name} (Admission Number: {student.admission_number}) has been updated.

Please log in to the parent portal to view the latest information.

Best regards,
{getattr(settings, "SCHOOL_INFO", {}).get("NAME", "School")} Administration
                """.strip()

                send_mail(
                    subject=subject,
                    message=message,
                    from_email=getattr(settings, "STUDENT_EMAIL_SETTINGS", {}).get(
                        "FROM_EMAIL", settings.DEFAULT_FROM_EMAIL
                    ),
                    recipient_list=[parent.user.email],
                    fail_silently=False,
                )

            except Exception as e:
                logger.error(
                    f"Failed to send update notification to parent {parent.user.email}: {str(e)}"
                )


def notify_admins_student_created(student):
    """Notify administrators about new student creation"""
    try:
        admin_emails = getattr(settings, "ADMINS", [])
        admin_email_list = [email for name, email in admin_emails]

        if admin_email_list:
            subject = f"New Student Created - {student.full_name}"

            message = f"""
A new student has been created in the system.

Student Details:
- Name: {student.full_name}
- Admission Number: {student.admission_number}
- Email: {student.email or 'Not provided'}
- Class: {student.current_class or 'Not assigned'}
- Status: {student.status}
- Created by: {student.created_by.get_full_name() if student.created_by else 'System'}

Student Profile: {getattr(settings, "SCHOOL_INFO", {}).get("WEBSITE", "")}/admin/students/student/{student.id}/change/
            """.strip()

            send_mail(
                subject=subject,
                message=message,
                from_email=getattr(settings, "STUDENT_EMAIL_SETTINGS", {}).get(
                    "FROM_EMAIL", settings.DEFAULT_FROM_EMAIL
                ),
                recipient_list=admin_email_list,
                fail_silently=True,  # Don't fail if admin notification fails
            )

    except Exception as e:
        logger.error(f"Failed to notify admins about student creation: {str(e)}")


def notify_status_change(student):
    """Notify about student status changes"""
    if (
        not getattr(settings, "NOTIFICATION_SETTINGS", {})
        .get("STUDENT_STATUS_CHANGED", {})
        .get("ENABLED", False)
    ):
        return

    try:
        old_status = getattr(student, "_old_status", "")
        new_status = getattr(student, "_new_status", "")

        # Notify parents
        parents = student.get_parents()
        for parent in parents:
            if parent.user.email:
                subject = f"Student Status Updated - {student.full_name}"

                message = f"""
Dear {parent.full_name},

The status for {student.full_name} (Admission Number: {student.admission_number}) has been updated.

Status Change: {old_status} → {new_status}

Please contact the school if you have any questions.

Best regards,
{getattr(settings, "SCHOOL_INFO", {}).get("NAME", "School")} Administration
                """.strip()

                send_mail(
                    subject=subject,
                    message=message,
                    from_email=getattr(settings, "STUDENT_EMAIL_SETTINGS", {}).get(
                        "FROM_EMAIL", settings.DEFAULT_FROM_EMAIL
                    ),
                    recipient_list=[parent.user.email],
                    fail_silently=True,
                )

    except Exception as e:
        logger.error(f"Failed to notify about status change: {str(e)}")


def notify_class_change(student):
    """Notify about student class changes (promotions)"""
    if (
        not getattr(settings, "NOTIFICATION_SETTINGS", {})
        .get("STUDENT_PROMOTED", {})
        .get("ENABLED", False)
    ):
        return

    try:
        old_class = getattr(student, "_old_class", None)
        new_class = getattr(student, "_new_class", None)

        # Notify parents
        parents = student.get_parents()
        for parent in parents:
            if parent.user.email:
                subject = f"Student Class Updated - {student.full_name}"

                message = f"""
Dear {parent.full_name},

{student.full_name} (Admission Number: {student.admission_number}) has been moved to a new class.

Class Change: {old_class or 'Unassigned'} → {new_class or 'Unassigned'}

Best regards,
{getattr(settings, "SCHOOL_INFO", {}).get("NAME", "School")} Administration
                """.strip()

                send_mail(
                    subject=subject,
                    message=message,
                    from_email=getattr(settings, "STUDENT_EMAIL_SETTINGS", {}).get(
                        "FROM_EMAIL", settings.DEFAULT_FROM_EMAIL
                    ),
                    recipient_list=[parent.user.email],
                    fail_silently=True,
                )

        # Also notify student if email provided
        if student.email and getattr(settings, "STUDENT_EMAIL_SETTINGS", {}).get(
            "ENABLE_PROMOTION_EMAILS", True
        ):
            subject = f'Class Update - {getattr(settings, "SCHOOL_INFO", {}).get("NAME", "School")}'

            message = f"""
Dear {student.first_name},

You have been moved to a new class.

Class Change: {old_class or 'Unassigned'} → {new_class or 'Unassigned'}

Best regards,
{getattr(settings, "SCHOOL_INFO", {}).get("NAME", "School")} Administration
            """.strip()

            send_mail(
                subject=subject,
                message=message,
                from_email=getattr(settings, "STUDENT_EMAIL_SETTINGS", {}).get(
                    "FROM_EMAIL", settings.DEFAULT_FROM_EMAIL
                ),
                recipient_list=[student.email],
                fail_silently=True,
            )

    except Exception as e:
        logger.error(f"Failed to notify about class change: {str(e)}")


def notify_parents_student_deleted(deleted_info, parent_emails):
    """Notify parents about student deletion"""
    try:
        for email in parent_emails:
            subject = f'Student Profile Removed - {deleted_info.get("full_name", "")}'

            message = f"""
Dear Parent/Guardian,

The student profile for {deleted_info.get("full_name", "")} (Admission Number: {deleted_info.get("admission_number", "")}) has been removed from our system.

If this was done in error or if you have any questions, please contact the school administration immediately.

Best regards,
{getattr(settings, "SCHOOL_INFO", {}).get("NAME", "School")} Administration
            """.strip()

            send_mail(
                subject=subject,
                message=message,
                from_email=getattr(settings, "STUDENT_EMAIL_SETTINGS", {}).get(
                    "FROM_EMAIL", settings.DEFAULT_FROM_EMAIL
                ),
                recipient_list=[email],
                fail_silently=True,
            )

    except Exception as e:
        logger.error(f"Failed to notify parents about student deletion: {str(e)}")


def clear_student_caches(student):
    """Clear all caches related to a student"""
    try:
        cache_keys = [
            f"student_attendance_percentage_{student.id}",
            f"student_siblings_{student.id}",
            f"student_parents_{student.id}",
            f"student_analytics_{student.id}",
        ]
        cache.delete_many(cache_keys)

        logger.debug(f"Cleared caches for student {student.admission_number}")

    except Exception as e:
        logger.error(f"Error clearing student caches: {str(e)}")
