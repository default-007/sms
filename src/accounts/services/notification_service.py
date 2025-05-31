# src/accounts/services/notification_service.py

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import EmailMultiAlternatives, send_mail
from django.template.loader import render_to_string
from django.utils import timezone

from ..models import UserAuditLog
from ..utils import get_client_info, mask_email, mask_phone

logger = logging.getLogger(__name__)
User = get_user_model()


class NotificationService:
    """Comprehensive service for handling user notifications."""

    # Email templates mapping
    EMAIL_TEMPLATES = {
        "welcome": {
            "subject": "Welcome to {site_name}",
            "html_template": "accounts/emails/welcome.html",
            "text_template": "accounts/emails/welcome.txt",
        },
        "password_reset": {
            "subject": "Password Reset Request",
            "html_template": "accounts/emails/password_reset.html",
            "text_template": "accounts/emails/password_reset.txt",
        },
        "password_changed": {
            "subject": "Password Changed Successfully",
            "html_template": "accounts/emails/password_changed.html",
            "text_template": "accounts/emails/password_changed.txt",
        },
        "account_locked": {
            "subject": "Account Security Alert",
            "html_template": "accounts/emails/account_locked.html",
            "text_template": "accounts/emails/account_locked.txt",
        },
        "account_unlocked": {
            "subject": "Account Unlocked",
            "html_template": "accounts/emails/account_unlocked.html",
            "text_template": "accounts/emails/account_unlocked.txt",
        },
        "role_assigned": {
            "subject": "New Role Assigned: {role_name}",
            "html_template": "accounts/emails/role_assigned.html",
            "text_template": "accounts/emails/role_assigned.txt",
        },
        "role_removed": {
            "subject": "Role Removed: {role_name}",
            "html_template": "accounts/emails/role_removed.html",
            "text_template": "accounts/emails/role_removed.txt",
        },
        "email_verification": {
            "subject": "Verify Your Email Address",
            "html_template": "accounts/emails/email_verification.html",
            "text_template": "accounts/emails/email_verification.txt",
        },
        "phone_verification": {
            "subject": "Phone Verification Code",
            "html_template": "accounts/emails/phone_verification.html",
            "text_template": "accounts/emails/phone_verification.txt",
        },
        "security_alert": {
            "subject": "Security Alert - Unusual Activity",
            "html_template": "accounts/emails/security_alert.html",
            "text_template": "accounts/emails/security_alert.txt",
        },
        "login_notification": {
            "subject": "New Login to Your Account",
            "html_template": "accounts/emails/login_notification.html",
            "text_template": "accounts/emails/login_notification.txt",
        },
        "profile_updated": {
            "subject": "Profile Updated Successfully",
            "html_template": "accounts/emails/profile_updated.html",
            "text_template": "accounts/emails/profile_updated.txt",
        },
        "bulk_import_complete": {
            "subject": "User Import Completed",
            "html_template": "accounts/emails/bulk_import_complete.html",
            "text_template": "accounts/emails/bulk_import_complete.txt",
        },
    }

    @staticmethod
    def send_email_notification(
        user: User,
        notification_type: str,
        context: Dict[str, Any] = None,
        from_email: str = None,
        priority: str = "normal",
    ) -> bool:
        """
        Send email notification to user.

        Args:
            user: User to send notification to
            notification_type: Type of notification (key from EMAIL_TEMPLATES)
            context: Additional context for template
            from_email: Custom from email
            priority: Email priority (low, normal, high)

        Returns:
            True if sent successfully, False otherwise
        """
        try:
            # Check if user wants email notifications
            if not user.email_notifications:
                logger.info(f"Email notifications disabled for user {user.username}")
                return False

            # Get template configuration
            if notification_type not in NotificationService.EMAIL_TEMPLATES:
                logger.error(f"Unknown notification type: {notification_type}")
                return False

            template_config = NotificationService.EMAIL_TEMPLATES[notification_type]

            # Prepare context
            context = context or {}
            context.update(
                {
                    "user": user,
                    "site_name": getattr(
                        settings, "SITE_NAME", "School Management System"
                    ),
                    "site_url": getattr(settings, "SITE_URL", "http://localhost:8000"),
                    "support_email": getattr(
                        settings, "SUPPORT_EMAIL", settings.DEFAULT_FROM_EMAIL
                    ),
                    "current_year": timezone.now().year,
                }
            )

            # Format subject
            subject = template_config["subject"].format(**context)

            # Render email content
            html_content = render_to_string(template_config["html_template"], context)

            # Try to render text content
            text_content = None
            if template_config.get("text_template"):
                try:
                    text_content = render_to_string(
                        template_config["text_template"], context
                    )
                except:
                    pass

            # Create email message
            email = EmailMultiAlternatives(
                subject=subject,
                body=text_content or NotificationService._html_to_text(html_content),
                from_email=from_email or settings.DEFAULT_FROM_EMAIL,
                to=[user.email],
            )

            # Add HTML content
            email.attach_alternative(html_content, "text/html")

            # Set priority headers
            if priority == "high":
                email.extra_headers["X-Priority"] = "1"
                email.extra_headers["X-MSMail-Priority"] = "High"
            elif priority == "low":
                email.extra_headers["X-Priority"] = "5"
                email.extra_headers["X-MSMail-Priority"] = "Low"

            # Send email
            email.send()

            # Log successful send
            UserAuditLog.objects.create(
                user=user,
                action="email_send",
                description=f"Email notification sent: {notification_type}",
                extra_data={
                    "notification_type": notification_type,
                    "subject": subject,
                    "to_email": mask_email(user.email),
                    "priority": priority,
                },
            )

            logger.info(
                f"Email notification '{notification_type}' sent to {user.username}"
            )
            return True

        except Exception as e:
            logger.error(
                f"Failed to send email notification to {user.username}: {str(e)}"
            )

            # Log failed send
            UserAuditLog.objects.create(
                user=user,
                action="email_send_failed",
                description=f"Failed to send email notification: {notification_type}",
                severity="medium",
                extra_data={
                    "notification_type": notification_type,
                    "error": str(e),
                    "to_email": mask_email(user.email),
                },
            )

            return False

    @staticmethod
    def send_sms_notification(
        user: User, message: str, priority: str = "normal"
    ) -> bool:
        """
        Send SMS notification to user.

        Args:
            user: User to send SMS to
            message: SMS message content
            priority: Message priority

        Returns:
            True if sent successfully, False otherwise
        """
        try:
            # Check if user wants SMS notifications and has phone
            if not user.sms_notifications or not user.phone_number:
                return False

            # Here you would integrate with your SMS provider
            # Examples: Twilio, AWS SNS, etc.
            success = NotificationService._send_sms_via_provider(
                user.phone_number, message, priority
            )

            if success:
                # Log successful send
                UserAuditLog.objects.create(
                    user=user,
                    action="sms_send",
                    description="SMS notification sent",
                    extra_data={
                        "to_phone": mask_phone(user.phone_number),
                        "message_length": len(message),
                        "priority": priority,
                    },
                )

                logger.info(f"SMS notification sent to {user.username}")
            else:
                # Log failed send
                UserAuditLog.objects.create(
                    user=user,
                    action="sms_send_failed",
                    description="Failed to send SMS notification",
                    severity="medium",
                    extra_data={
                        "to_phone": mask_phone(user.phone_number),
                        "message_length": len(message),
                    },
                )

            return success

        except Exception as e:
            logger.error(f"Failed to send SMS to {user.username}: {str(e)}")
            return False

    @staticmethod
    def send_push_notification(
        user: User, title: str, message: str, data: Dict[str, Any] = None
    ) -> bool:
        """
        Send push notification to user's devices.

        Args:
            user: User to send notification to
            title: Notification title
            message: Notification message
            data: Additional data payload

        Returns:
            True if sent successfully, False otherwise
        """
        try:
            # Here you would integrate with push notification service
            # Examples: Firebase Cloud Messaging, OneSignal, etc.
            success = NotificationService._send_push_via_provider(
                user, title, message, data
            )

            if success:
                UserAuditLog.objects.create(
                    user=user,
                    action="push_send",
                    description="Push notification sent",
                    extra_data={"title": title, "message": message, "data": data or {}},
                )

            return success

        except Exception as e:
            logger.error(
                f"Failed to send push notification to {user.username}: {str(e)}"
            )
            return False

    @staticmethod
    def send_multi_channel_notification(
        user: User,
        notification_type: str,
        channels: List[str],
        context: Dict[str, Any] = None,
        priority: str = "normal",
    ) -> Dict[str, bool]:
        """
        Send notification across multiple channels.

        Args:
            user: User to notify
            notification_type: Type of notification
            channels: List of channels ('email', 'sms', 'push')
            context: Template context
            priority: Notification priority

        Returns:
            Dictionary of channel -> success status
        """
        results = {}

        if "email" in channels:
            results["email"] = NotificationService.send_email_notification(
                user, notification_type, context, priority=priority
            )

        if "sms" in channels and context:
            # Generate SMS message from context
            sms_message = NotificationService._generate_sms_message(
                notification_type, context
            )
            results["sms"] = NotificationService.send_sms_notification(
                user, sms_message, priority
            )

        if "push" in channels and context:
            # Generate push notification from context
            title, message = NotificationService._generate_push_content(
                notification_type, context
            )
            results["push"] = NotificationService.send_push_notification(
                user, title, message, context
            )

        return results

    @staticmethod
    def send_bulk_notification(
        users: List[User],
        notification_type: str,
        context: Dict[str, Any] = None,
        channels: List[str] = ["email"],
        batch_size: int = 50,
    ) -> Dict[str, int]:
        """
        Send bulk notifications to multiple users.

        Args:
            users: List of users to notify
            notification_type: Type of notification
            context: Template context
            channels: Notification channels
            batch_size: Number of users per batch

        Returns:
            Dictionary with success/failure counts
        """
        results = {"total": len(users), "success": 0, "failed": 0, "skipped": 0}

        # Process users in batches
        for i in range(0, len(users), batch_size):
            batch = users[i : i + batch_size]

            for user in batch:
                try:
                    # Send to each channel
                    channel_results = (
                        NotificationService.send_multi_channel_notification(
                            user, notification_type, channels, context
                        )
                    )

                    # Check if at least one channel succeeded
                    if any(channel_results.values()):
                        results["success"] += 1
                    else:
                        results["failed"] += 1

                except Exception as e:
                    logger.error(f"Failed to send notification to {user.username}: {e}")
                    results["failed"] += 1

        # Log bulk operation
        UserAuditLog.objects.create(
            action="bulk_notification",
            description=f"Bulk notification sent: {notification_type}",
            extra_data={
                "notification_type": notification_type,
                "channels": channels,
                "results": results,
            },
        )

        return results

    @staticmethod
    def get_notification_preferences(user: User) -> Dict[str, bool]:
        """Get user's notification preferences."""
        return {
            "email_notifications": user.email_notifications,
            "sms_notifications": user.sms_notifications,
            "has_email": bool(user.email),
            "has_phone": bool(user.phone_number),
            "email_verified": user.email_verified,
            "phone_verified": user.phone_verified,
        }

    @staticmethod
    def update_notification_preferences(
        user: User, preferences: Dict[str, bool]
    ) -> bool:
        """Update user's notification preferences."""
        try:
            if "email_notifications" in preferences:
                user.email_notifications = preferences["email_notifications"]

            if "sms_notifications" in preferences:
                user.sms_notifications = preferences["sms_notifications"]

            user.save(update_fields=["email_notifications", "sms_notifications"])

            # Log preference change
            UserAuditLog.objects.create(
                user=user,
                action="notification_preferences_update",
                description="Notification preferences updated",
                extra_data=preferences,
            )

            return True

        except Exception as e:
            logger.error(
                f"Failed to update notification preferences for {user.username}: {e}"
            )
            return False

    @staticmethod
    def get_notification_history(
        user: User, days: int = 30, notification_types: List[str] = None
    ) -> List[Dict[str, Any]]:
        """Get user's notification history."""
        start_date = timezone.now() - timedelta(days=days)

        logs = UserAuditLog.objects.filter(
            user=user,
            timestamp__gte=start_date,
            action__in=["email_send", "sms_send", "push_send"],
        ).order_by("-timestamp")

        if notification_types:
            logs = logs.filter(extra_data__notification_type__in=notification_types)

        history = []
        for log in logs:
            history.append(
                {
                    "id": log.id,
                    "timestamp": log.timestamp,
                    "action": log.action,
                    "notification_type": log.extra_data.get("notification_type"),
                    "subject": log.extra_data.get("subject"),
                    "success": "failed" not in log.action,
                    "description": log.description,
                }
            )

        return history

    @staticmethod
    def _send_sms_via_provider(phone: str, message: str, priority: str) -> bool:
        """
        Send SMS via configured provider.
        This is a placeholder - implement with your SMS provider.
        """
        # Example implementation for Twilio
        try:
            if hasattr(settings, "TWILIO_ACCOUNT_SID") and hasattr(
                settings, "TWILIO_AUTH_TOKEN"
            ):
                from twilio.rest import Client

                client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)

                message = client.messages.create(
                    body=message, from_=settings.TWILIO_PHONE_NUMBER, to=phone
                )

                return message.status != "failed"
            else:
                logger.warning("Twilio credentials not configured")
                return False

        except ImportError:
            logger.warning("Twilio library not installed")
            return False
        except Exception as e:
            logger.error(f"SMS sending failed: {e}")
            return False

    @staticmethod
    def _send_push_via_provider(
        user: User, title: str, message: str, data: Dict[str, Any]
    ) -> bool:
        """
        Send push notification via configured provider.
        This is a placeholder - implement with your push provider.
        """
        # Example implementation for Firebase Cloud Messaging
        try:
            # This would require user device tokens stored in the database
            # and Firebase Admin SDK configuration
            return False  # Placeholder

        except Exception as e:
            logger.error(f"Push notification failed: {e}")
            return False

    @staticmethod
    def _generate_sms_message(notification_type: str, context: Dict[str, Any]) -> str:
        """Generate SMS message content."""
        templates = {
            "welcome": "Welcome to {site_name}! Your account has been created successfully.",
            "password_reset": "Your password reset code is: {reset_code}",
            "account_locked": "Your account has been locked due to security reasons. Contact support.",
            "role_assigned": "You have been assigned the role: {role_name}",
            "email_verification": "Your email verification code is: {verification_code}",
            "phone_verification": "Your phone verification code is: {verification_code}",
        }

        template = templates.get(notification_type, "You have a new notification.")
        return template.format(**context)

    @staticmethod
    def _generate_push_content(
        notification_type: str, context: Dict[str, Any]
    ) -> tuple[str, str]:
        """Generate push notification title and message."""
        configs = {
            "welcome": ("Welcome!", "Your account has been created successfully."),
            "password_reset": ("Password Reset", "Your password has been reset."),
            "account_locked": ("Security Alert", "Your account has been locked."),
            "role_assigned": (
                "New Role",
                f"You have been assigned: {context.get('role_name', 'New Role')}",
            ),
        }

        return configs.get(
            notification_type, ("Notification", "You have a new notification.")
        )

    @staticmethod
    def _html_to_text(html_content: str) -> str:
        """Convert HTML content to plain text."""
        import re

        # Remove HTML tags
        text = re.sub(r"<[^>]+>", "", html_content)

        # Replace common HTML entities
        text = text.replace("&nbsp;", " ")
        text = text.replace("&amp;", "&")
        text = text.replace("&lt;", "<")
        text = text.replace("&gt;", ">")

        # Clean up whitespace
        text = re.sub(r"\s+", " ", text).strip()

        return text

    @staticmethod
    def schedule_notification(
        user: User,
        notification_type: str,
        scheduled_time: datetime,
        context: Dict[str, Any] = None,
        channels: List[str] = ["email"],
    ) -> bool:
        """
        Schedule a notification to be sent later.
        This would require a task queue system like Celery.
        """
        try:
            from ..tasks import send_scheduled_notification

            # Schedule the task
            send_scheduled_notification.apply_async(
                args=[user.id, notification_type, context, channels], eta=scheduled_time
            )

            return True

        except ImportError:
            logger.warning("Task queue not available for scheduled notifications")
            return False
        except Exception as e:
            logger.error(f"Failed to schedule notification: {e}")
            return False
