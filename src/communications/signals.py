"""
Django signals for Communications module.
Handles automatic communication preferences creation, metric updates, and event tracking.
"""

import logging

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone

from .models import (
    Announcement,
    CommunicationChannel,
    CommunicationLog,
    CommunicationPreference,
    DirectMessage,
    MessageStatus,
    MessageThread,
    Notification,
)

User = get_user_model()
logger = logging.getLogger(__name__)


@receiver(post_save, sender=User)
def create_user_communication_preferences(sender, instance, created, **kwargs):
    """
    Create default communication preferences for new users.
    """
    if created:
        try:
            # Create default preferences
            CommunicationPreference.objects.create(
                user=instance,
                email_enabled=True,
                sms_enabled=True,
                push_enabled=True,
                whatsapp_enabled=False,
                academic_notifications=True,
                financial_notifications=True,
                attendance_notifications=True,
                general_announcements=True,
                marketing_messages=False,
                preferred_language="en",
                digest_frequency="immediate",
            )

            logger.info(
                f"Created communication preferences for user: {instance.username}"
            )

        except Exception as e:
            logger.error(
                f"Failed to create communication preferences for {instance.username}: {str(e)}"
            )


@receiver(post_save, sender=Notification)
def log_notification_creation(sender, instance, created, **kwargs):
    """
    Log notification creation events.
    """
    if created:
        try:
            CommunicationLog.objects.create(
                event_type="notification_created",
                channel=CommunicationChannel.IN_APP,
                status=MessageStatus.SENT,
                recipient=instance.user,
                content_type="notification",
                content_id=str(instance.id),
                metadata={
                    "notification_type": instance.notification_type,
                    "priority": instance.priority,
                    "title": instance.title,
                },
            )

        except Exception as e:
            logger.error(f"Failed to log notification creation: {str(e)}")


@receiver(post_save, sender=Notification)
def update_announcement_metrics_on_notification_read(sender, instance, **kwargs):
    """
    Update announcement metrics when notifications are read.
    """
    if instance.is_read and instance.announcement:
        try:
            # Use transaction to avoid race conditions
            with transaction.atomic():
                announcement = instance.announcement

                # Update read count
                total_read = announcement.notifications.filter(is_read=True).count()
                announcement.total_read = total_read
                announcement.save(update_fields=["total_read"])

        except Exception as e:
            logger.error(f"Failed to update announcement metrics: {str(e)}")


@receiver(post_save, sender=DirectMessage)
def log_message_sent(sender, instance, created, **kwargs):
    """
    Log direct message creation events.
    """
    if created:
        try:
            # Get thread participants except sender
            recipients = instance.thread.participants.exclude(id=instance.sender.id)

            # Create log entries for each recipient
            for recipient in recipients:
                CommunicationLog.objects.create(
                    event_type="direct_message_sent",
                    channel=CommunicationChannel.IN_APP,
                    status=MessageStatus.SENT,
                    sender=instance.sender,
                    recipient=recipient,
                    content_type="direct_message",
                    content_id=str(instance.id),
                    metadata={
                        "thread_id": str(instance.thread.id),
                        "thread_subject": instance.thread.subject,
                        "is_group": instance.thread.is_group,
                    },
                )

        except Exception as e:
            logger.error(f"Failed to log direct message: {str(e)}")


@receiver(post_save, sender=DirectMessage)
def update_thread_last_message(sender, instance, created, **kwargs):
    """
    Update thread's last message timestamp when a new message is sent.
    """
    if created:
        try:
            thread = instance.thread
            thread.last_message_at = instance.sent_at
            thread.save(update_fields=["last_message_at"])

        except Exception as e:
            logger.error(f"Failed to update thread last message time: {str(e)}")


@receiver(post_save, sender=Announcement)
def log_announcement_creation(sender, instance, created, **kwargs):
    """
    Log announcement creation events.
    """
    if created:
        try:
            CommunicationLog.objects.create(
                event_type="announcement_created",
                channel=CommunicationChannel.IN_APP,
                status=MessageStatus.SENT,
                sender=instance.created_by,
                content_type="announcement",
                content_id=str(instance.id),
                metadata={
                    "title": instance.title,
                    "target_audience": instance.target_audience,
                    "priority": instance.priority,
                    "channels": instance.channels,
                },
            )

        except Exception as e:
            logger.error(f"Failed to log announcement creation: {str(e)}")


@receiver(pre_save, sender=Notification)
def track_notification_read_timestamp(sender, instance, **kwargs):
    """
    Set read timestamp when notification is marked as read.
    """
    if instance.pk:  # Only for existing notifications
        try:
            # Get the original notification to compare
            original = Notification.objects.get(pk=instance.pk)

            # If notification is being marked as read for the first time
            if not original.is_read and instance.is_read:
                instance.read_at = timezone.now()

                # Log the read event
                CommunicationLog.objects.create(
                    event_type="notification_read",
                    channel=CommunicationChannel.IN_APP,
                    status=MessageStatus.READ,
                    recipient=instance.user,
                    content_type="notification",
                    content_id=str(instance.id),
                    metadata={
                        "notification_type": instance.notification_type,
                        "read_time": instance.read_at.isoformat(),
                    },
                )

        except Notification.DoesNotExist:
            # New notification, skip
            pass
        except Exception as e:
            logger.error(f"Failed to track notification read: {str(e)}")


@receiver(post_delete, sender=Notification)
def log_notification_deletion(sender, instance, **kwargs):
    """
    Log notification deletion events.
    """
    try:
        CommunicationLog.objects.create(
            event_type="notification_deleted",
            channel=CommunicationChannel.IN_APP,
            status=MessageStatus.CANCELLED,
            recipient=instance.user,
            content_type="notification",
            content_id=str(instance.id),
            metadata={
                "notification_type": instance.notification_type,
                "was_read": instance.is_read,
                "deleted_at": timezone.now().isoformat(),
            },
        )

    except Exception as e:
        logger.error(f"Failed to log notification deletion: {str(e)}")


@receiver(post_delete, sender=Announcement)
def log_announcement_deletion(sender, instance, **kwargs):
    """
    Log announcement deletion events.
    """
    try:
        CommunicationLog.objects.create(
            event_type="announcement_deleted",
            channel=CommunicationChannel.IN_APP,
            status=MessageStatus.CANCELLED,
            sender=instance.created_by,
            content_type="announcement",
            content_id=str(instance.id),
            metadata={
                "title": instance.title,
                "target_audience": instance.target_audience,
                "total_recipients": instance.total_recipients,
                "total_read": instance.total_read,
                "deleted_at": timezone.now().isoformat(),
            },
        )

    except Exception as e:
        logger.error(f"Failed to log announcement deletion: {str(e)}")


# Custom signal for bulk operations
from django.dispatch import Signal

# Define custom signals
bulk_notification_sent = Signal()
bulk_message_sent = Signal()
communication_failed = Signal()


@receiver(bulk_notification_sent)
def log_bulk_notification_completion(sender, **kwargs):
    """
    Log completion of bulk notification operations.
    """
    try:
        notification_count = kwargs.get("notification_count", 0)
        user_count = kwargs.get("user_count", 0)
        notification_type = kwargs.get("notification_type", "unknown")

        CommunicationLog.objects.create(
            event_type="bulk_notification_completed",
            channel=CommunicationChannel.IN_APP,
            status=MessageStatus.SENT,
            content_type="bulk_operation",
            content_id=f"bulk_{timezone.now().timestamp()}",
            metadata={
                "notification_count": notification_count,
                "user_count": user_count,
                "notification_type": notification_type,
                "completed_at": timezone.now().isoformat(),
            },
        )

        logger.info(
            f"Bulk notification completed: {notification_count} notifications to {user_count} users"
        )

    except Exception as e:
        logger.error(f"Failed to log bulk notification completion: {str(e)}")


@receiver(communication_failed)
def log_communication_failure(sender, **kwargs):
    """
    Log communication failures for monitoring and debugging.
    """
    try:
        error_type = kwargs.get("error_type", "unknown")
        error_message = kwargs.get("error_message", "")
        channel = kwargs.get("channel", CommunicationChannel.IN_APP)
        recipient = kwargs.get("recipient")

        CommunicationLog.objects.create(
            event_type="communication_failed",
            channel=channel,
            status=MessageStatus.FAILED,
            recipient=recipient,
            content_type="error",
            error_details=error_message,
            metadata={
                "error_type": error_type,
                "failed_at": timezone.now().isoformat(),
            },
        )

        logger.error(f"Communication failure: {error_type} - {error_message}")

    except Exception as e:
        logger.error(f"Failed to log communication failure: {str(e)}")


# Utility function to send custom signals
def send_bulk_notification_signal(notification_count, user_count, notification_type):
    """
    Send bulk notification completion signal.
    """
    bulk_notification_sent.send(
        sender=None,
        notification_count=notification_count,
        user_count=user_count,
        notification_type=notification_type,
    )


def send_communication_failure_signal(
    error_type, error_message, channel=None, recipient=None
):
    """
    Send communication failure signal.
    """
    communication_failed.send(
        sender=None,
        error_type=error_type,
        error_message=error_message,
        channel=channel,
        recipient=recipient,
    )
