from django.conf import settings
from django.utils import timezone
from django.core.mail import EmailMessage, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.contrib.auth import get_user_model
from django.db import transaction

from .models import Notification, SMSLog, EmailLog, Message, Announcement

User = get_user_model()


class NotificationService:
    """Service for managing system notifications."""

    @staticmethod
    def create_notification(
        user, title, content, notification_type, reference_id=None, priority="medium"
    ):
        """Create a notification for a user."""
        return Notification.objects.create(
            user=user,
            title=title,
            content=content,
            notification_type=notification_type,
            reference_id=reference_id,
            priority=priority,
        )

    @staticmethod
    def create_bulk_notifications(
        users, title, content, notification_type, reference_id=None, priority="medium"
    ):
        """Create notifications for multiple users."""
        notifications = []
        for user in users:
            notifications.append(
                Notification(
                    user=user,
                    title=title,
                    content=content,
                    notification_type=notification_type,
                    reference_id=reference_id,
                    priority=priority,
                )
            )

        return Notification.objects.bulk_create(notifications)

    @staticmethod
    def create_announcement_notifications(announcement):
        """Create notifications for a new announcement."""
        # Determine which users should receive the notification
        users = []

        if announcement.target_audience == "all":
            users = User.objects.filter(is_active=True)
        elif announcement.target_audience == "students":
            users = User.objects.filter(student_profile__isnull=False, is_active=True)
        elif announcement.target_audience == "teachers":
            users = User.objects.filter(teacher_profile__isnull=False, is_active=True)
        elif announcement.target_audience == "parents":
            users = User.objects.filter(parent_profile__isnull=False, is_active=True)
        elif announcement.target_audience == "staff":
            users = User.objects.filter(is_staff=True, is_active=True)

        # Filter by target classes if specified
        if announcement.target_classes:
            class_users = User.objects.filter(
                student_profile__current_class_id__in=announcement.target_classes,
                is_active=True,
            )
            users = users.filter(id__in=class_users)

        # Create notifications for each user
        return NotificationService.create_bulk_notifications(
            users,
            f"New Announcement: {announcement.title}",
            (
                announcement.content[:100] + "..."
                if len(announcement.content) > 100
                else announcement.content
            ),
            "system",
            str(announcement.id),
            "medium",
        )

    @staticmethod
    def create_message_notification(message):
        """Create a notification for a new message."""
        return NotificationService.create_notification(
            message.receiver,
            f"New Message from {message.sender.get_full_name() or message.sender.username}",
            message.subject,
            "message",
            str(message.id),
            "medium",
        )

    @staticmethod
    def count_unread_notifications(user):
        """Count unread notifications for a user."""
        return Notification.objects.filter(user=user, is_read=False).count()


class MessageService:
    """Service for managing messages."""

    @staticmethod
    def get_recipients_by_type(recipient_type, class_id=None, custom_recipients=None):
        """Get recipients based on recipient type."""
        if recipient_type == "all_students":
            return User.objects.filter(student_profile__isnull=False, is_active=True)
        elif recipient_type == "all_teachers":
            return User.objects.filter(teacher_profile__isnull=False, is_active=True)
        elif recipient_type == "all_parents":
            return User.objects.filter(parent_profile__isnull=False, is_active=True)
        elif recipient_type == "class" and class_id:
            return User.objects.filter(
                student_profile__current_class=class_id, is_active=True
            )
        elif recipient_type == "custom" and custom_recipients:
            return custom_recipients

        return User.objects.none()

    @staticmethod
    @transaction.atomic
    def send_bulk_messages(sender, recipients, subject, content, attachment=None):
        """Send messages to multiple recipients."""
        messages_created = 0

        for recipient in recipients:
            if recipient != sender:  # Don't send to self
                message = Message.objects.create(
                    sender=sender,
                    receiver=recipient,
                    subject=subject,
                    content=content,
                    attachment=attachment,
                )

                # Create notification for the recipient
                NotificationService.create_message_notification(message)

                messages_created += 1

        return messages_created

    @staticmethod
    def count_unread_messages(user):
        """Count unread messages for a user."""
        return Message.objects.filter(receiver=user, is_read=False).count()


class EmailService:
    """Service for sending emails."""

    @staticmethod
    def send_email(
        recipient_email,
        subject,
        content,
        html_content=None,
        attachments=None,
        recipient_user=None,
    ):
        """Send an email and log it."""
        try:
            if html_content:
                # Send HTML email
                email = EmailMultiAlternatives(
                    subject,
                    strip_tags(content),
                    settings.DEFAULT_FROM_EMAIL,
                    [recipient_email],
                )
                email.attach_alternative(html_content, "text/html")
            else:
                # Send plain text email
                email = EmailMessage(
                    subject, content, settings.DEFAULT_FROM_EMAIL, [recipient_email]
                )

            # Add attachments if any
            if attachments:
                for attachment in attachments:
                    email.attach(
                        attachment.name, attachment.read(), attachment.content_type
                    )

            # Send the email
            email.send(fail_silently=False)

            # Log the email
            log = EmailLog.objects.create(
                recipient_email=recipient_email,
                recipient_user=recipient_user,
                subject=subject,
                content=content,
                status="sent",
            )

            return True, log

        except Exception as e:
            # Log the failed attempt
            log = EmailLog.objects.create(
                recipient_email=recipient_email,
                recipient_user=recipient_user,
                subject=subject,
                content=content,
                status="failed",
                error_message=str(e),
            )

            return False, log

    @staticmethod
    def send_email_from_template(
        recipient_email,
        subject,
        template_name,
        context,
        attachments=None,
        recipient_user=None,
    ):
        """Send an email using a template."""
        try:
            # Render HTML content from template
            html_content = render_to_string(template_name, context)

            # Convert HTML to plain text
            plain_content = strip_tags(html_content)

            return EmailService.send_email(
                recipient_email,
                subject,
                plain_content,
                html_content,
                attachments,
                recipient_user,
            )

        except Exception as e:
            # Log the failed attempt
            log = EmailLog.objects.create(
                recipient_email=recipient_email,
                recipient_user=recipient_user,
                subject=subject,
                content=f"Failed to render template {template_name}",
                status="failed",
                error_message=str(e),
            )

            return False, log


class SMSService:
    """Service for sending SMS messages."""

    @staticmethod
    def send_sms(recipient_number, content, recipient_user=None):
        """Send an SMS and log it."""
        try:
            # This is a placeholder for actual SMS sending logic
            # You would integrate with an SMS provider like Twilio, Nexmo, etc.

            # In a real implementation, you'd call the SMS API here
            # For now, we'll just log the attempt

            # Log the SMS
            log = SMSLog.objects.create(
                recipient_number=recipient_number,
                recipient_user=recipient_user,
                content=content,
                status="sent",  # In a real implementation, this would be set based on the API response
            )

            return True, log

        except Exception as e:
            # Log the failed attempt
            log = SMSLog.objects.create(
                recipient_number=recipient_number,
                recipient_user=recipient_user,
                content=content,
                status="failed",
                error_message=str(e),
            )

            return False, log


class CommunicationService:
    """Unified service for all communications."""

    @staticmethod
    def notify_user(
        user,
        title,
        content,
        notification_type,
        reference_id=None,
        priority="medium",
        send_email=False,
        send_sms=False,
        email_template=None,
        email_context=None,
    ):
        """
        Notify a user through multiple channels.

        Args:
            user: The user to notify
            title: Notification title
            content: Notification content
            notification_type: Type of notification
            reference_id: Optional reference ID
            priority: Notification priority
            send_email: Whether to also send an email
            send_sms: Whether to also send an SMS
            email_template: Optional template for email
            email_context: Optional context for email template

        Returns:
            tuple: (notification, email_log, sms_log)
        """
        # Create in-app notification
        notification = NotificationService.create_notification(
            user, title, content, notification_type, reference_id, priority
        )

        email_log = None
        sms_log = None

        # Send email if requested
        if send_email and user.email:
            if email_template and email_context:
                # Send using template
                context = email_context.copy() if email_context else {}
                context["user"] = user
                context["notification"] = notification

                _, email_log = EmailService.send_email_from_template(
                    user.email, title, email_template, context, None, user
                )
            else:
                # Send plain email
                _, email_log = EmailService.send_email(
                    user.email, title, content, None, None, user
                )

        # Send SMS if requested
        if send_sms and hasattr(user, "phone_number") and user.phone_number:
            _, sms_log = SMSService.send_sms(user.phone_number, content, user)

        return notification, email_log, sms_log

    @staticmethod
    def notify_multiple_users(
        users,
        title,
        content,
        notification_type,
        reference_id=None,
        priority="medium",
        send_email=False,
        send_sms=False,
        email_template=None,
        email_context=None,
    ):
        """Notify multiple users through multiple channels."""
        results = []

        for user in users:
            result = CommunicationService.notify_user(
                user,
                title,
                content,
                notification_type,
                reference_id,
                priority,
                send_email,
                send_sms,
                email_template,
                email_context,
            )
            results.append(result)

        return results
