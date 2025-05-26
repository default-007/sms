"""
Celery tasks for Communications module.
Background processing for bulk messaging, analytics calculation, and scheduled communications.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List

from celery import shared_task
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mass_mail
from django.db import transaction
from django.template.loader import render_to_string
from django.utils import timezone

from .models import (
    Announcement,
    BulkMessage,
    CommunicationAnalytics,
    CommunicationChannel,
    CommunicationLog,
    MessageRecipient,
    MessageStatus,
    MessageTemplate,
    Notification,
    Priority,
    TargetAudience,
)
from .services import (
    AnnouncementService,
    CommunicationAnalyticsService,
    EmailService,
    NotificationService,
    SMSService,
)
from .signals import send_bulk_notification_signal, send_communication_failure_signal

User = get_user_model()
logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def send_bulk_notification_task(
    self,
    user_ids: List[int],
    title: str,
    content: str,
    notification_type: str,
    priority: str = Priority.MEDIUM,
    channels: List[str] = None,
):
    """
    Background task for sending bulk notifications.
    """
    try:
        if channels is None:
            channels = [CommunicationChannel.IN_APP]

        users = User.objects.filter(id__in=user_ids, is_active=True)

        if not users.exists():
            logger.warning(f"No active users found for bulk notification: {user_ids}")
            return {"status": "warning", "message": "No active users found"}

        # Send notifications in batches to avoid memory issues
        batch_size = 100
        total_sent = 0

        for i in range(0, len(users), batch_size):
            batch_users = users[i : i + batch_size]

            notifications = NotificationService.bulk_create_notifications(
                users=list(batch_users),
                title=title,
                content=content,
                notification_type=notification_type,
                priority=priority,
                channels=channels,
            )

            total_sent += len(notifications)

            # Small delay between batches
            if i + batch_size < len(users):
                self.retry(countdown=1, max_retries=0)

        # Send completion signal
        send_bulk_notification_signal(total_sent, len(users), notification_type)

        logger.info(
            f"Bulk notification task completed: {total_sent} notifications sent"
        )

        return {
            "status": "success",
            "notifications_sent": total_sent,
            "users_targeted": len(users),
        }

    except Exception as exc:
        logger.error(f"Bulk notification task failed: {str(exc)}")
        send_communication_failure_signal(
            "bulk_notification_task", str(exc), CommunicationChannel.IN_APP
        )

        # Retry with exponential backoff
        raise self.retry(exc=exc, countdown=60 * (2**self.request.retries))


@shared_task(bind=True, max_retries=3)
def send_bulk_message_task(self, bulk_message_id: str):
    """
    Background task for processing bulk message sending.
    """
    try:
        bulk_message = BulkMessage.objects.get(id=bulk_message_id)

        # Update status
        bulk_message.status = MessageStatus.SENDING
        bulk_message.save(update_fields=["status"])

        # Get target users based on audience and filters
        target_users = _get_bulk_message_recipients(bulk_message)

        if not target_users:
            bulk_message.status = MessageStatus.FAILED
            bulk_message.save(update_fields=["status"])
            return {"status": "error", "message": "No target users found"}

        # Create recipient records
        recipients = []
        for user in target_users:
            recipient = MessageRecipient.objects.create(
                bulk_message=bulk_message,
                user=user,
                email=user.email,
                phone=getattr(user, "phone_number", ""),
            )
            recipients.append(recipient)

        bulk_message.total_recipients = len(recipients)
        bulk_message.save(update_fields=["total_recipients"])

        # Send via configured channels
        results = {"email": 0, "sms": 0, "push": 0}

        if CommunicationChannel.EMAIL in bulk_message.channels:
            email_results = _send_bulk_email_task(bulk_message, recipients)
            results["email"] = email_results["sent"]

        if CommunicationChannel.SMS in bulk_message.channels:
            sms_results = _send_bulk_sms_task(bulk_message, recipients)
            results["sms"] = sms_results["sent"]

        if CommunicationChannel.PUSH in bulk_message.channels:
            push_results = _send_bulk_push_task(bulk_message, recipients)
            results["push"] = push_results["sent"]

        # Update final status and metrics
        total_successful = sum(results.values())
        bulk_message.successful_deliveries = total_successful
        bulk_message.failed_deliveries = (
            bulk_message.total_recipients - total_successful
        )
        bulk_message.sent_at = timezone.now()
        bulk_message.status = (
            MessageStatus.SENT if total_successful > 0 else MessageStatus.FAILED
        )
        bulk_message.save()

        logger.info(f"Bulk message task completed: {bulk_message.name}")

        return {
            "status": "success",
            "bulk_message_id": bulk_message_id,
            "results": results,
            "total_recipients": bulk_message.total_recipients,
            "successful_deliveries": total_successful,
        }

    except BulkMessage.DoesNotExist:
        logger.error(f"Bulk message not found: {bulk_message_id}")
        return {"status": "error", "message": "Bulk message not found"}

    except Exception as exc:
        logger.error(f"Bulk message task failed: {str(exc)}")

        # Update bulk message status
        try:
            bulk_message = BulkMessage.objects.get(id=bulk_message_id)
            bulk_message.status = MessageStatus.FAILED
            bulk_message.save(update_fields=["status"])
        except:
            pass

        send_communication_failure_signal(
            "bulk_message_task", str(exc), CommunicationChannel.EMAIL
        )

        raise self.retry(exc=exc, countdown=60 * (2**self.request.retries))


@shared_task
def calculate_daily_analytics_task(date_str: str = None):
    """
    Background task for calculating daily communication analytics.
    """
    try:
        if date_str:
            date = datetime.strptime(date_str, "%Y-%m-%d").date()
        else:
            date = timezone.now().date()

        analytics = CommunicationAnalyticsService.calculate_daily_analytics(date)

        logger.info(f"Daily analytics calculated for {date}")

        return {
            "status": "success",
            "date": date.isoformat(),
            "analytics_id": str(analytics.id),
        }

    except Exception as exc:
        logger.error(f"Daily analytics calculation failed: {str(exc)}")
        return {"status": "error", "message": str(exc)}


@shared_task
def update_announcement_metrics_task(announcement_id: str):
    """
    Background task for updating announcement metrics.
    """
    try:
        AnnouncementService.update_announcement_metrics(announcement_id)

        logger.info(f"Announcement metrics updated: {announcement_id}")

        return {"status": "success", "announcement_id": announcement_id}

    except Exception as exc:
        logger.error(f"Announcement metrics update failed: {str(exc)}")
        return {"status": "error", "message": str(exc)}


@shared_task
def send_scheduled_announcements_task():
    """
    Background task for sending scheduled announcements.
    """
    try:
        now = timezone.now()

        # Get announcements that should be sent now
        scheduled_announcements = Announcement.objects.filter(
            is_active=True, start_date__lte=now, total_sent=0  # Not yet sent
        ).filter(models.Q(end_date__isnull=True) | models.Q(end_date__gte=now))

        results = []

        for announcement in scheduled_announcements:
            try:
                # Get target users
                target_users = AnnouncementService._get_target_users(announcement)

                if target_users:
                    # Create notifications
                    notifications = NotificationService.bulk_create_notifications(
                        users=target_users,
                        title=f"📢 {announcement.title}",
                        content=announcement.content,
                        notification_type="announcement",
                        priority=announcement.priority,
                        channels=announcement.channels,
                    )

                    # Update announcement metrics
                    announcement.total_recipients = len(target_users)
                    announcement.total_sent = len(notifications)
                    announcement.save(update_fields=["total_recipients", "total_sent"])

                    results.append(
                        {
                            "announcement_id": str(announcement.id),
                            "title": announcement.title,
                            "notifications_sent": len(notifications),
                        }
                    )

            except Exception as e:
                logger.error(
                    f"Failed to send scheduled announcement {announcement.id}: {str(e)}"
                )
                continue

        logger.info(f"Scheduled announcements processed: {len(results)}")

        return {
            "status": "success",
            "announcements_processed": len(results),
            "results": results,
        }

    except Exception as exc:
        logger.error(f"Scheduled announcements task failed: {str(exc)}")
        return {"status": "error", "message": str(exc)}


@shared_task
def cleanup_old_communications_task(days: int = 90):
    """
    Background task for cleaning up old communication records.
    """
    try:
        cutoff_date = timezone.now() - timedelta(days=days)

        # Clean up old communication logs
        deleted_logs = CommunicationLog.objects.filter(
            timestamp__lt=cutoff_date
        ).delete()[0]

        # Clean up old read notifications (keep unread ones)
        deleted_notifications = Notification.objects.filter(
            created_at__lt=cutoff_date, is_read=True
        ).delete()[0]

        # Clean up completed bulk messages
        deleted_bulk_messages = BulkMessage.objects.filter(
            created_at__lt=cutoff_date,
            status__in=[MessageStatus.SENT, MessageStatus.FAILED],
        ).delete()[0]

        logger.info(
            f"Cleanup completed: {deleted_logs} logs, {deleted_notifications} notifications, {deleted_bulk_messages} bulk messages"
        )

        return {
            "status": "success",
            "deleted_logs": deleted_logs,
            "deleted_notifications": deleted_notifications,
            "deleted_bulk_messages": deleted_bulk_messages,
        }

    except Exception as exc:
        logger.error(f"Cleanup task failed: {str(exc)}")
        return {"status": "error", "message": str(exc)}


@shared_task
def send_digest_notifications_task():
    """
    Background task for sending digest notifications to users who prefer them.
    """
    try:
        from .models import CommunicationPreference

        # Get users who want daily digests
        daily_users = User.objects.filter(
            communication_preferences__digest_frequency="daily", is_active=True
        )

        results = []

        for user in daily_users:
            try:
                # Get unread notifications from the last day
                yesterday = timezone.now() - timedelta(days=1)
                unread_notifications = Notification.objects.filter(
                    user=user, is_read=False, created_at__gte=yesterday
                ).order_by("-created_at")

                if unread_notifications.exists():
                    # Create digest content
                    digest_content = _create_digest_content(unread_notifications)

                    # Send digest notification
                    digest_notification = NotificationService.create_notification(
                        user=user,
                        title=f"Daily Digest - {unread_notifications.count()} unread notifications",
                        content=digest_content,
                        notification_type="digest",
                        priority=Priority.LOW,
                        channels=[CommunicationChannel.EMAIL],
                    )

                    results.append(
                        {
                            "user_id": user.id,
                            "notifications_count": unread_notifications.count(),
                        }
                    )

            except Exception as e:
                logger.error(f"Failed to send digest to user {user.id}: {str(e)}")
                continue

        logger.info(f"Digest notifications sent to {len(results)} users")

        return {"status": "success", "digests_sent": len(results), "results": results}

    except Exception as exc:
        logger.error(f"Digest notifications task failed: {str(exc)}")
        return {"status": "error", "message": str(exc)}


# Helper functions


def _get_bulk_message_recipients(bulk_message: BulkMessage) -> List[User]:
    """Get target users for bulk message based on audience and filters."""

    from django.db.models import Q

    query = Q(is_active=True)

    # Apply audience filter
    if bulk_message.target_audience == TargetAudience.STUDENTS:
        query &= Q(userroleassignment__role__name="Student")
    elif bulk_message.target_audience == TargetAudience.TEACHERS:
        query &= Q(userroleassignment__role__name="Teacher")
    elif bulk_message.target_audience == TargetAudience.PARENTS:
        query &= Q(userroleassignment__role__name="Parent")
    elif bulk_message.target_audience == TargetAudience.STAFF:
        query &= Q(userroleassignment__role__name="Staff")

    # Apply additional filters
    filters = bulk_message.target_filters

    if filters.get("sections"):
        query &= Q(student__current_class__grade__section__id__in=filters["sections"])

    if filters.get("grades"):
        query &= Q(student__current_class__grade__id__in=filters["grades"])

    if filters.get("classes"):
        query &= Q(student__current_class__id__in=filters["classes"])

    return list(User.objects.filter(query).distinct())


def _send_bulk_email_task(
    bulk_message: BulkMessage, recipients: List[MessageRecipient]
) -> Dict[str, int]:
    """Send bulk email to recipients."""

    results = {"sent": 0, "failed": 0}

    try:
        email_data = []

        for recipient in recipients:
            if not recipient.email:
                recipient.email_status = MessageStatus.FAILED
                recipient.error_message = "No email address"
                recipient.save()
                continue

            # Render content
            if bulk_message.template:
                context = {"user": recipient.user}
                content = bulk_message.template.render_content(context)
                subject = (
                    bulk_message.template.render_subject(context)
                    or bulk_message.subject
                )
            else:
                content = bulk_message.content
                subject = bulk_message.subject

            # Prepare email data
            email_data.append(
                (subject, content, settings.DEFAULT_FROM_EMAIL, [recipient.email])
            )

            recipient.email_status = MessageStatus.SENDING
            recipient.save()

        # Send emails in batches
        batch_size = 50
        for i in range(0, len(email_data), batch_size):
            batch = email_data[i : i + batch_size]

            try:
                send_mass_mail(batch, fail_silently=False)

                # Update status for successful sends
                batch_recipients = recipients[i : i + batch_size]
                for recipient in batch_recipients:
                    if recipient.email_status == MessageStatus.SENDING:
                        recipient.email_status = MessageStatus.SENT
                        recipient.sent_at = timezone.now()
                        recipient.save()
                        results["sent"] += 1

            except Exception as e:
                # Update status for failed sends
                batch_recipients = recipients[i : i + batch_size]
                for recipient in batch_recipients:
                    if recipient.email_status == MessageStatus.SENDING:
                        recipient.email_status = MessageStatus.FAILED
                        recipient.error_message = str(e)
                        recipient.save()
                        results["failed"] += 1

                logger.error(f"Batch email sending failed: {str(e)}")

    except Exception as e:
        logger.error(f"Bulk email sending failed: {str(e)}")
        results["failed"] = len(recipients)

    return results


def _send_bulk_sms_task(
    bulk_message: BulkMessage, recipients: List[MessageRecipient]
) -> Dict[str, int]:
    """Send bulk SMS to recipients."""

    results = {"sent": 0, "failed": 0}

    # SMS implementation would depend on your SMS provider
    # This is a placeholder implementation

    for recipient in recipients:
        if not recipient.phone:
            recipient.sms_status = MessageStatus.FAILED
            recipient.error_message = "No phone number"
            recipient.save()
            results["failed"] += 1
            continue

        try:
            # Format content for SMS
            content = bulk_message.content[:160]  # SMS character limit

            # Send SMS (implement based on your provider)
            success = SMSService._send_sms(recipient.phone, content)

            if success:
                recipient.sms_status = MessageStatus.SENT
                recipient.sent_at = timezone.now()
                results["sent"] += 1
            else:
                recipient.sms_status = MessageStatus.FAILED
                recipient.error_message = "SMS sending failed"
                results["failed"] += 1

            recipient.save()

        except Exception as e:
            recipient.sms_status = MessageStatus.FAILED
            recipient.error_message = str(e)
            recipient.save()
            results["failed"] += 1

    return results


def _send_bulk_push_task(
    bulk_message: BulkMessage, recipients: List[MessageRecipient]
) -> Dict[str, int]:
    """Send bulk push notifications to recipients."""

    results = {"sent": 0, "failed": 0}

    # Push notification implementation would depend on your provider
    # This is a placeholder implementation

    for recipient in recipients:
        try:
            # Send push notification
            success = True  # Placeholder

            if success:
                recipient.push_status = MessageStatus.SENT
                recipient.sent_at = timezone.now()
                results["sent"] += 1
            else:
                recipient.push_status = MessageStatus.FAILED
                recipient.error_message = "Push notification failed"
                results["failed"] += 1

            recipient.save()

        except Exception as e:
            recipient.push_status = MessageStatus.FAILED
            recipient.error_message = str(e)
            recipient.save()
            results["failed"] += 1

    return results


def _create_digest_content(notifications: List[Notification]) -> str:
    """Create digest content from notifications."""

    content_parts = ["Here are your unread notifications:\n"]

    for notification in notifications[:10]:  # Limit to 10 notifications
        content_parts.append(f"• {notification.title}")
        if notification.content:
            preview = (
                notification.content[:100] + "..."
                if len(notification.content) > 100
                else notification.content
            )
            content_parts.append(f"  {preview}")
        content_parts.append("")

    if notifications.count() > 10:
        content_parts.append(f"... and {notifications.count() - 10} more notifications")

    content_parts.append("\nPlease log in to view all notifications.")

    return "\n".join(content_parts)
