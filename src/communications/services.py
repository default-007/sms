"""
Communications services for School Management System.
Business logic for notifications, announcements, messaging, and communication analytics.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from celery import shared_task
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail, send_mass_mail
from django.db import transaction
from django.db.models import Avg, Count, Q, Sum
from django.template.loader import render_to_string
from django.utils import timezone

from .models import (
    Announcement,
    BulkMessage,
    CommunicationAnalytics,
    CommunicationChannel,
    CommunicationLog,
    CommunicationPreference,
    DirectMessage,
    MessageRead,
    MessageRecipient,
    MessageStatus,
    MessageTemplate,
    MessageThread,
    Notification,
    Priority,
    TargetAudience,
)

User = get_user_model()
logger = logging.getLogger(__name__)


class NotificationService:
    """Service for managing notifications and in-app messaging"""

    @staticmethod
    def create_notification(
        user: User,
        title: str,
        content: str,
        notification_type: str,
        priority: str = Priority.MEDIUM,
        reference_id: str = None,
        reference_type: str = None,
        channels: List[str] = None,
    ) -> Notification:
        """Create a new notification for a user"""

        if channels is None:
            channels = [CommunicationChannel.IN_APP]

        notification = Notification.objects.create(
            user=user,
            title=title,
            content=content,
            notification_type=notification_type,
            priority=priority,
            reference_id=reference_id,
            reference_type=reference_type,
            channels_used=channels,
        )

        # Send via additional channels if requested
        if CommunicationChannel.EMAIL in channels:
            EmailService.send_notification_email(notification)

        if CommunicationChannel.SMS in channels:
            SMSService.send_notification_sms(notification)

        if CommunicationChannel.PUSH in channels:
            PushNotificationService.send_push_notification(notification)

        # Log the communication
        CommunicationLog.objects.create(
            event_type="notification_created",
            channel=CommunicationChannel.IN_APP,
            status=MessageStatus.SENT,
            recipient=user,
            content_type="notification",
            content_id=str(notification.id),
            metadata={"notification_type": notification_type, "priority": priority},
        )

        return notification

    @staticmethod
    def bulk_create_notifications(
        users: List[User],
        title: str,
        content: str,
        notification_type: str,
        priority: str = Priority.MEDIUM,
        channels: List[str] = None,
    ) -> List[Notification]:
        """Create notifications for multiple users"""

        notifications = []
        for user in users:
            # Check user preferences
            prefs = CommunicationPreference.objects.filter(user=user).first()
            if prefs and not NotificationService._should_send_notification(
                prefs, notification_type
            ):
                continue

            notification = NotificationService.create_notification(
                user=user,
                title=title,
                content=content,
                notification_type=notification_type,
                priority=priority,
                channels=channels,
            )
            notifications.append(notification)

        return notifications

    @staticmethod
    def mark_as_read(notification_id: str, user: User) -> bool:
        """Mark a notification as read"""
        try:
            notification = Notification.objects.get(id=notification_id, user=user)
            notification.mark_as_read()
            return True
        except Notification.DoesNotExist:
            return False

    @staticmethod
    def get_user_notifications(
        user: User,
        unread_only: bool = False,
        notification_type: str = None,
        limit: int = 50,
    ) -> List[Notification]:
        """Get notifications for a user"""

        queryset = Notification.objects.filter(user=user)

        if unread_only:
            queryset = queryset.filter(is_read=False)

        if notification_type:
            queryset = queryset.filter(notification_type=notification_type)

        return queryset.order_by("-created_at")[:limit]

    @staticmethod
    def get_unread_count(user: User) -> int:
        """Get count of unread notifications for a user"""
        return Notification.objects.filter(user=user, is_read=False).count()

    @staticmethod
    def _should_send_notification(
        prefs: CommunicationPreference, notification_type: str
    ) -> bool:
        """Check if notification should be sent based on user preferences"""

        # Check notification type preferences
        type_mapping = {
            "academic": prefs.academic_notifications,
            "financial": prefs.financial_notifications,
            "attendance": prefs.attendance_notifications,
            "general": prefs.general_announcements,
            "marketing": prefs.marketing_messages,
        }

        category = notification_type.split("_")[0]  # Extract category from type
        if category in type_mapping and not type_mapping[category]:
            return False

        # Check quiet hours
        now = timezone.now().time()
        if prefs.quiet_hours_start <= now <= prefs.quiet_hours_end:
            return False

        # Check weekend preferences
        if not prefs.weekend_notifications and timezone.now().weekday() >= 5:
            return False

        return True


class AnnouncementService:
    """Service for managing school announcements"""

    @staticmethod
    def create_announcement(
        title: str,
        content: str,
        created_by: User,
        target_audience: str = TargetAudience.ALL,
        target_grades: List[int] = None,
        target_classes: List[int] = None,
        target_sections: List[int] = None,
        priority: str = Priority.MEDIUM,
        channels: List[str] = None,
        start_date: datetime = None,
        end_date: datetime = None,
        attachment=None,
    ) -> Announcement:
        """Create a new announcement"""

        if channels is None:
            channels = [CommunicationChannel.IN_APP]

        if start_date is None:
            start_date = timezone.now()

        announcement = Announcement.objects.create(
            title=title,
            content=content,
            created_by=created_by,
            target_audience=target_audience,
            target_grades=target_grades or [],
            target_classes=target_classes or [],
            target_sections=target_sections or [],
            priority=priority,
            channels=channels,
            start_date=start_date,
            end_date=end_date,
            attachment=attachment,
        )

        # Get target users and create notifications
        target_users = AnnouncementService._get_target_users(announcement)
        announcement.total_recipients = len(target_users)
        announcement.save(update_fields=["total_recipients"])

        # Create notifications for target users
        notifications = NotificationService.bulk_create_notifications(
            users=target_users,
            title=f"📢 {title}",
            content=content,
            notification_type="announcement",
            priority=priority,
            channels=channels,
        )

        # Update announcement metrics
        announcement.total_sent = len(notifications)
        announcement.save(update_fields=["total_sent"])

        return announcement

    @staticmethod
    def _get_target_users(announcement: Announcement) -> List[User]:
        """Get list of users targeted by an announcement"""

        if announcement.target_audience == TargetAudience.ALL:
            return list(User.objects.filter(is_active=True))

        # Build query based on target audience
        query = Q(is_active=True)

        if announcement.target_audience == TargetAudience.STUDENTS:
            query &= Q(userroleassignment__role__name="Student")
        elif announcement.target_audience == TargetAudience.TEACHERS:
            query &= Q(userroleassignment__role__name="Teacher")
        elif announcement.target_audience == TargetAudience.PARENTS:
            query &= Q(userroleassignment__role__name="Parent")
        elif announcement.target_audience == TargetAudience.STAFF:
            query &= Q(userroleassignment__role__name="Staff")

        # Apply additional filters
        if announcement.target_sections:
            query &= Q(
                student__current_class__grade__section__id__in=announcement.target_sections
            )

        if announcement.target_grades:
            query &= Q(student__current_class__grade__id__in=announcement.target_grades)

        if announcement.target_classes:
            query &= Q(student__current_class__id__in=announcement.target_classes)

        return list(User.objects.filter(query).distinct())

    @staticmethod
    def update_announcement_metrics(announcement_id: str):
        """Update announcement delivery and read metrics"""

        try:
            announcement = Announcement.objects.get(id=announcement_id)
            notifications = Notification.objects.filter(announcement=announcement)

            announcement.total_delivered = notifications.count()
            announcement.total_read = notifications.filter(is_read=True).count()
            announcement.save(update_fields=["total_delivered", "total_read"])

        except Announcement.DoesNotExist:
            logger.error(f"Announcement {announcement_id} not found for metrics update")

    @staticmethod
    def get_active_announcements(user: User = None) -> List[Announcement]:
        """Get currently active announcements"""

        now = timezone.now()
        queryset = Announcement.objects.filter(
            is_active=True, start_date__lte=now
        ).filter(Q(end_date__isnull=True) | Q(end_date__gte=now))

        if user:
            # Filter based on user's role and associations
            # This would need to be implemented based on your specific targeting logic
            pass

        return list(queryset.order_by("-start_date"))


class MessagingService:
    """Service for direct messaging between users"""

    @staticmethod
    def create_thread(
        subject: str,
        participants: List[User],
        created_by: User,
        is_group: bool = False,
        thread_type: str = "general",
    ) -> MessageThread:
        """Create a new message thread"""

        thread = MessageThread.objects.create(
            subject=subject,
            created_by=created_by,
            is_group=is_group,
            thread_type=thread_type,
        )

        thread.participants.set(participants)
        return thread

    @staticmethod
    def send_message(
        thread: MessageThread, sender: User, content: str, attachment=None
    ) -> DirectMessage:
        """Send a message in a thread"""

        message = DirectMessage.objects.create(
            thread=thread, sender=sender, content=content, attachment=attachment
        )

        # Update thread last message time
        thread.last_message_at = message.sent_at
        thread.save(update_fields=["last_message_at"])

        # Create notifications for other participants
        other_participants = thread.participants.exclude(id=sender.id)
        for participant in other_participants:
            NotificationService.create_notification(
                user=participant,
                title=f"New message in: {thread.subject}",
                content=f"{sender.get_full_name()}: {content[:100]}...",
                notification_type="direct_message",
                reference_id=str(message.id),
                reference_type="direct_message",
            )

        return message

    @staticmethod
    def mark_message_as_read(message: DirectMessage, user: User):
        """Mark a message as read by a user"""

        MessageRead.objects.get_or_create(user=user, message=message)

    @staticmethod
    def get_user_threads(user: User, limit: int = 50) -> List[MessageThread]:
        """Get message threads for a user"""

        return list(
            MessageThread.objects.filter(participants=user, is_active=True).order_by(
                "-last_message_at"
            )[:limit]
        )

    @staticmethod
    def get_unread_message_count(user: User) -> int:
        """Get count of unread messages for a user"""

        # Get all messages in threads the user participates in
        user_threads = MessageThread.objects.filter(participants=user)
        all_messages = DirectMessage.objects.filter(thread__in=user_threads).exclude(
            sender=user
        )

        # Count messages not read by this user
        read_messages = MessageRead.objects.filter(user=user, message__in=all_messages)
        return all_messages.count() - read_messages.count()


class EmailService:
    """Service for email communications"""

    @staticmethod
    def send_notification_email(notification: Notification):
        """Send notification via email"""

        try:
            user = notification.user
            prefs = CommunicationPreference.objects.filter(user=user).first()

            if prefs and not prefs.email_enabled:
                return False

            subject = notification.title
            content = notification.content

            # Use template if available
            html_content = render_to_string(
                "emails/notification.html",
                {
                    "notification": notification,
                    "user": user,
                    "school_name": getattr(settings, "SCHOOL_NAME", "School"),
                },
            )

            send_mail(
                subject=subject,
                message=content,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                html_message=html_content,
                fail_silently=False,
            )

            # Update delivery status
            notification.delivery_status["email"] = MessageStatus.SENT
            notification.save(update_fields=["delivery_status"])

            # Log the communication
            CommunicationLog.objects.create(
                event_type="email_sent",
                channel=CommunicationChannel.EMAIL,
                status=MessageStatus.SENT,
                recipient=user,
                content_type="notification",
                content_id=str(notification.id),
            )

            return True

        except Exception as e:
            logger.error(f"Failed to send email notification: {str(e)}")

            # Update delivery status
            notification.delivery_status["email"] = MessageStatus.FAILED
            notification.save(update_fields=["delivery_status"])

            return False

    @staticmethod
    def send_bulk_email(
        subject: str,
        content: str,
        recipients: List[User],
        template: MessageTemplate = None,
        sender: User = None,
    ) -> Dict[str, int]:
        """Send bulk email to multiple recipients"""

        results = {"sent": 0, "failed": 0}
        email_data = []

        for user in recipients:
            prefs = CommunicationPreference.objects.filter(user=user).first()
            if prefs and not prefs.email_enabled:
                continue

            # Render template if provided
            if template:
                context = {"user": user, "sender": sender}
                rendered_content = template.render_content(context)
                rendered_subject = template.render_subject(context) or subject
            else:
                rendered_content = content
                rendered_subject = subject

            html_content = render_to_string(
                "emails/bulk_message.html",
                {
                    "content": rendered_content,
                    "user": user,
                    "sender": sender,
                    "school_name": getattr(settings, "SCHOOL_NAME", "School"),
                },
            )

            email_data.append(
                (
                    rendered_subject,
                    rendered_content,
                    settings.DEFAULT_FROM_EMAIL,
                    [user.email],
                )
            )

        try:
            send_mass_mail(email_data, fail_silently=False)
            results["sent"] = len(email_data)
        except Exception as e:
            logger.error(f"Failed to send bulk email: {str(e)}")
            results["failed"] = len(email_data)

        return results


class SMSService:
    """Service for SMS communications"""

    @staticmethod
    def send_notification_sms(notification: Notification):
        """Send notification via SMS"""

        try:
            user = notification.user
            prefs = CommunicationPreference.objects.filter(user=user).first()

            if prefs and not prefs.sms_enabled:
                return False

            if not user.phone_number:
                return False

            # Format content for SMS (limit length)
            content = f"{notification.title}\n{notification.content[:140]}..."

            # Here you would integrate with your SMS provider (Twilio, etc.)
            success = SMSService._send_sms(user.phone_number, content)

            if success:
                notification.delivery_status["sms"] = MessageStatus.SENT
                CommunicationLog.objects.create(
                    event_type="sms_sent",
                    channel=CommunicationChannel.SMS,
                    status=MessageStatus.SENT,
                    recipient=user,
                    content_type="notification",
                    content_id=str(notification.id),
                )
            else:
                notification.delivery_status["sms"] = MessageStatus.FAILED

            notification.save(update_fields=["delivery_status"])
            return success

        except Exception as e:
            logger.error(f"Failed to send SMS notification: {str(e)}")
            return False

    @staticmethod
    def _send_sms(phone_number: str, message: str) -> bool:
        """Send SMS using configured provider"""

        # Placeholder for SMS provider integration
        # You would implement this based on your chosen SMS service

        try:
            # Example Twilio integration
            # from twilio.rest import Client
            # client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
            # message = client.messages.create(
            #     body=message,
            #     from_=settings.TWILIO_PHONE_NUMBER,
            #     to=phone_number
            # )
            # return True

            logger.info(f"SMS sent to {phone_number}: {message}")
            return True

        except Exception as e:
            logger.error(f"SMS sending failed: {str(e)}")
            return False


class PushNotificationService:
    """Service for push notifications"""

    @staticmethod
    def send_push_notification(notification: Notification):
        """Send push notification"""

        try:
            user = notification.user
            prefs = CommunicationPreference.objects.filter(user=user).first()

            if prefs and not prefs.push_enabled:
                return False

            # Here you would integrate with Firebase Cloud Messaging or similar
            success = PushNotificationService._send_push(
                user_id=user.id, title=notification.title, body=notification.content
            )

            if success:
                notification.delivery_status["push"] = MessageStatus.SENT
                CommunicationLog.objects.create(
                    event_type="push_sent",
                    channel=CommunicationChannel.PUSH,
                    status=MessageStatus.SENT,
                    recipient=user,
                    content_type="notification",
                    content_id=str(notification.id),
                )
            else:
                notification.delivery_status["push"] = MessageStatus.FAILED

            notification.save(update_fields=["delivery_status"])
            return success

        except Exception as e:
            logger.error(f"Failed to send push notification: {str(e)}")
            return False

    @staticmethod
    def _send_push(user_id: int, title: str, body: str) -> bool:
        """Send push notification using configured service"""

        # Placeholder for push notification service integration
        logger.info(f"Push notification sent to user {user_id}: {title}")
        return True


class CommunicationAnalyticsService:
    """Service for communication analytics and reporting"""

    @staticmethod
    def calculate_daily_analytics(date: datetime = None):
        """Calculate communication analytics for a specific date"""

        if date is None:
            date = timezone.now().date()

        # Get or create analytics record
        analytics, created = CommunicationAnalytics.objects.get_or_create(
            date=date, defaults={"month": date.month, "year": date.year}
        )

        # Calculate metrics for the date
        date_start = timezone.make_aware(datetime.combine(date, datetime.min.time()))
        date_end = date_start + timedelta(days=1)

        # Communication volume
        logs = CommunicationLog.objects.filter(
            timestamp__gte=date_start, timestamp__lt=date_end
        )

        analytics.total_emails_sent = logs.filter(
            channel=CommunicationChannel.EMAIL
        ).count()
        analytics.total_sms_sent = logs.filter(channel=CommunicationChannel.SMS).count()
        analytics.total_push_sent = logs.filter(
            channel=CommunicationChannel.PUSH
        ).count()

        # Announcements
        analytics.total_announcements = Announcement.objects.filter(
            created_at__gte=date_start, created_at__lt=date_end
        ).count()

        # Delivery rates
        email_logs = logs.filter(channel=CommunicationChannel.EMAIL)
        if email_logs.exists():
            email_success = email_logs.filter(status=MessageStatus.SENT).count()
            analytics.email_delivery_rate = (email_success / email_logs.count()) * 100

        sms_logs = logs.filter(channel=CommunicationChannel.SMS)
        if sms_logs.exists():
            sms_success = sms_logs.filter(status=MessageStatus.SENT).count()
            analytics.sms_delivery_rate = (sms_success / sms_logs.count()) * 100

        # Engagement metrics
        notifications = Notification.objects.filter(
            created_at__gte=date_start, created_at__lt=date_end
        )

        if notifications.exists():
            read_notifications = notifications.filter(is_read=True).count()
            analytics.notification_read_rate = (
                read_notifications / notifications.count()
            ) * 100

        # Audience breakdown
        analytics.student_messages = logs.filter(
            recipient__userroleassignment__role__name="Student"
        ).count()

        analytics.parent_messages = logs.filter(
            recipient__userroleassignment__role__name="Parent"
        ).count()

        analytics.teacher_messages = logs.filter(
            recipient__userroleassignment__role__name="Teacher"
        ).count()

        analytics.staff_messages = logs.filter(
            recipient__userroleassignment__role__name="Staff"
        ).count()

        analytics.save()
        return analytics

    @staticmethod
    def get_communication_summary(days: int = 30) -> Dict[str, Any]:
        """Get communication summary for the last N days"""

        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)

        analytics = CommunicationAnalytics.objects.filter(
            date__gte=start_date, date__lte=end_date
        )

        return {
            "total_emails": analytics.aggregate(Sum("total_emails_sent"))[
                "total_emails_sent__sum"
            ]
            or 0,
            "total_sms": analytics.aggregate(Sum("total_sms_sent"))[
                "total_sms_sent__sum"
            ]
            or 0,
            "total_push": analytics.aggregate(Sum("total_push_sent"))[
                "total_push_sent__sum"
            ]
            or 0,
            "total_announcements": analytics.aggregate(Sum("total_announcements"))[
                "total_announcements__sum"
            ]
            or 0,
            "avg_email_delivery_rate": analytics.aggregate(Avg("email_delivery_rate"))[
                "email_delivery_rate__avg"
            ]
            or 0,
            "avg_sms_delivery_rate": analytics.aggregate(Avg("sms_delivery_rate"))[
                "sms_delivery_rate__avg"
            ]
            or 0,
            "avg_read_rate": analytics.aggregate(Avg("notification_read_rate"))[
                "notification_read_rate__avg"
            ]
            or 0,
            "total_cost": analytics.aggregate(Sum("total_cost"))["total_cost__sum"]
            or 0,
        }

    @staticmethod
    def get_user_engagement_stats(user: User) -> Dict[str, Any]:
        """Get engagement statistics for a specific user"""

        notifications = Notification.objects.filter(user=user)

        return {
            "total_notifications": notifications.count(),
            "unread_notifications": notifications.filter(is_read=False).count(),
            "read_rate": (
                (
                    notifications.filter(is_read=True).count()
                    / notifications.count()
                    * 100
                )
                if notifications.exists()
                else 0
            ),
            "last_activity": notifications.filter(is_read=True).aggregate(
                last=timezone.datetime.max
            )["last"],
            "preferred_channels": CommunicationPreference.objects.filter(
                user=user
            ).first(),
        }


# Celery tasks for background processing
@shared_task
def send_bulk_notification_task(
    user_ids: List[int],
    title: str,
    content: str,
    notification_type: str,
    priority: str = Priority.MEDIUM,
    channels: List[str] = None,
):
    """Background task for sending bulk notifications"""

    users = User.objects.filter(id__in=user_ids)
    notifications = NotificationService.bulk_create_notifications(
        users=users,
        title=title,
        content=content,
        notification_type=notification_type,
        priority=priority,
        channels=channels or [CommunicationChannel.IN_APP],
    )

    return len(notifications)


@shared_task
def calculate_daily_analytics_task(date_str: str = None):
    """Background task for calculating daily analytics"""

    if date_str:
        date = datetime.strptime(date_str, "%Y-%m-%d").date()
    else:
        date = timezone.now().date()

    analytics = CommunicationAnalyticsService.calculate_daily_analytics(date)
    return str(analytics.id)


@shared_task
def update_announcement_metrics_task(announcement_id: str):
    """Background task for updating announcement metrics"""

    AnnouncementService.update_announcement_metrics(announcement_id)
    return announcement_id
