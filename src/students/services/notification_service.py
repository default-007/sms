# students/services/notification_service.py
from django.core.mail import send_mail, send_mass_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.utils import timezone
from django.db import transaction
from django.core.cache import cache
from celery import shared_task
import logging
import json
from typing import List, Dict, Any

from ..models import Student, Parent, StudentParentRelation

logger = logging.getLogger(__name__)


class NotificationService:
    """Advanced notification service for students and parents"""

    NOTIFICATION_TYPES = {
        "admission": {
            "name": "Admission Notification",
            "template": "emails/admission_notification.html",
            "priority": "high",
            "channels": ["email", "sms"],
        },
        "fee_reminder": {
            "name": "Fee Reminder",
            "template": "emails/fee_reminder.html",
            "priority": "medium",
            "channels": ["email", "sms"],
        },
        "attendance_alert": {
            "name": "Attendance Alert",
            "template": "emails/attendance_alert.html",
            "priority": "high",
            "channels": ["email", "sms", "push"],
        },
        "grade_update": {
            "name": "Grade Update",
            "template": "emails/grade_update.html",
            "priority": "medium",
            "channels": ["email"],
        },
        "event_announcement": {
            "name": "Event Announcement",
            "template": "emails/event_announcement.html",
            "priority": "low",
            "channels": ["email", "push"],
        },
        "emergency": {
            "name": "Emergency Alert",
            "template": "emails/emergency_alert.html",
            "priority": "critical",
            "channels": ["email", "sms", "push", "call"],
        },
    }

    @staticmethod
    def send_notification(
        notification_type: str,
        recipients: List[Dict],
        context: Dict[str, Any],
        sender=None,
        scheduled_at=None,
    ):
        """
        Send notification to multiple recipients

        Args:
            notification_type: Type of notification (key from NOTIFICATION_TYPES)
            recipients: List of recipient dictionaries with type and contact info
            context: Context data for template rendering
            sender: User sending the notification
            scheduled_at: When to send (for scheduled notifications)
        """
        try:
            if notification_type not in NotificationService.NOTIFICATION_TYPES:
                raise ValueError(f"Unknown notification type: {notification_type}")

            notification_config = NotificationService.NOTIFICATION_TYPES[
                notification_type
            ]

            # If scheduled, queue the task
            if scheduled_at:
                return NotificationService._schedule_notification(
                    notification_type, recipients, context, sender, scheduled_at
                )

            # Send immediately
            return NotificationService._send_immediate_notification(
                notification_type, notification_config, recipients, context, sender
            )

        except Exception as e:
            logger.error(f"Error sending notification: {str(e)}")
            raise

    @staticmethod
    def _send_immediate_notification(
        notification_type, config, recipients, context, sender
    ):
        """Send notification immediately"""
        results = {
            "notification_type": notification_type,
            "total_recipients": len(recipients),
            "successful": {"email": 0, "sms": 0, "push": 0},
            "failed": {"email": 0, "sms": 0, "push": 0},
            "errors": [],
        }

        # Prepare context with common data
        base_context = {
            "school_name": getattr(settings, "SCHOOL_NAME", "School"),
            "sender_name": sender.get_full_name() if sender else "System",
            "timestamp": timezone.now(),
            "notification_type": notification_type,
            **context,
        }

        # Group recipients by type for batch processing
        email_recipients = []
        sms_recipients = []
        push_recipients = []

        for recipient in recipients:
            recipient_type = recipient.get("type")  # 'student', 'parent'
            recipient_id = recipient.get("id")

            try:
                if recipient_type == "student":
                    student = Student.objects.get(id=recipient_id)
                    if "email" in config["channels"] and student.user.email:
                        email_recipients.append(
                            {
                                "email": student.user.email,
                                "name": student.get_full_name(),
                                "context": {
                                    **base_context,
                                    "student": student,
                                    "recipient_type": "student",
                                },
                            }
                        )

                    if "sms" in config["channels"] and student.user.phone_number:
                        sms_recipients.append(
                            {
                                "phone": student.user.phone_number,
                                "name": student.get_full_name(),
                                "context": {
                                    **base_context,
                                    "student": student,
                                    "recipient_type": "student",
                                },
                            }
                        )

                elif recipient_type == "parent":
                    parent = Parent.objects.get(id=recipient_id)
                    if "email" in config["channels"] and parent.user.email:
                        email_recipients.append(
                            {
                                "email": parent.user.email,
                                "name": parent.get_full_name(),
                                "context": {
                                    **base_context,
                                    "parent": parent,
                                    "recipient_type": "parent",
                                },
                            }
                        )

                    if "sms" in config["channels"] and parent.user.phone_number:
                        sms_recipients.append(
                            {
                                "phone": parent.user.phone_number,
                                "name": parent.get_full_name(),
                                "context": {
                                    **base_context,
                                    "parent": parent,
                                    "recipient_type": "parent",
                                },
                            }
                        )

            except (Student.DoesNotExist, Parent.DoesNotExist) as e:
                results["errors"].append(
                    f"Recipient {recipient_id} not found: {str(e)}"
                )

        # Send emails
        if email_recipients:
            email_result = NotificationService._send_bulk_emails(
                config["template"], email_recipients, config["name"]
            )
            results["successful"]["email"] = email_result["successful"]
            results["failed"]["email"] = email_result["failed"]
            results["errors"].extend(email_result["errors"])

        # Send SMS
        if sms_recipients:
            sms_result = NotificationService._send_bulk_sms(
                sms_recipients, base_context
            )
            results["successful"]["sms"] = sms_result["successful"]
            results["failed"]["sms"] = sms_result["failed"]
            results["errors"].extend(sms_result["errors"])

        # Send push notifications
        if push_recipients:
            push_result = NotificationService._send_bulk_push(
                push_recipients, base_context
            )
            results["successful"]["push"] = push_result["successful"]
            results["failed"]["push"] = push_result["failed"]
            results["errors"].extend(push_result["errors"])

        # Log notification
        NotificationService._log_notification(notification_type, results, sender)

        return results

    @staticmethod
    def _send_bulk_emails(template_name, recipients, subject_prefix):
        """Send bulk emails"""
        results = {"successful": 0, "failed": 0, "errors": []}

        try:
            messages = []

            for recipient in recipients:
                try:
                    # Render template with recipient-specific context
                    subject = (
                        f"{subject_prefix} - {recipient['context']['school_name']}"
                    )
                    html_content = render_to_string(template_name, recipient["context"])

                    messages.append(
                        (
                            subject,
                            html_content,
                            settings.DEFAULT_FROM_EMAIL,
                            [recipient["email"]],
                        )
                    )

                except Exception as e:
                    results["errors"].append(
                        f"Error preparing email for {recipient['email']}: {str(e)}"
                    )
                    results["failed"] += 1

            # Send all emails
            if messages:
                try:
                    sent_count = send_mass_mail(messages, fail_silently=False)
                    results["successful"] = sent_count
                except Exception as e:
                    results["errors"].append(f"Bulk email send failed: {str(e)}")
                    results["failed"] = len(messages)

        except Exception as e:
            results["errors"].append(f"Email preparation failed: {str(e)}")

        return results

    @staticmethod
    def _send_bulk_sms(recipients, context):
        """Send bulk SMS messages"""
        results = {"successful": 0, "failed": 0, "errors": []}

        try:
            for recipient in recipients:
                try:
                    # Generate SMS content (short version of notification)
                    message = NotificationService._generate_sms_content(
                        recipient["context"]
                    )

                    # Send SMS (implement with your SMS provider)
                    success = NotificationService._send_single_sms(
                        recipient["phone"], message
                    )

                    if success:
                        results["successful"] += 1
                    else:
                        results["failed"] += 1

                except Exception as e:
                    results["errors"].append(
                        f"SMS failed for {recipient['phone']}: {str(e)}"
                    )
                    results["failed"] += 1

        except Exception as e:
            results["errors"].append(f"Bulk SMS failed: {str(e)}")

        return results

    @staticmethod
    def _send_bulk_push(recipients, context):
        """Send bulk push notifications"""
        results = {"successful": 0, "failed": 0, "errors": []}

        # Implement push notification logic here
        # This would integrate with services like Firebase, OneSignal, etc.

        return results

    @staticmethod
    def _generate_sms_content(context):
        """Generate short SMS content from context"""
        notification_type = context.get("notification_type")
        school_name = context.get("school_name")

        if notification_type == "fee_reminder":
            return f"Fee reminder from {school_name}. Please check your account for details."
        elif notification_type == "attendance_alert":
            return f"Attendance alert from {school_name}. Your child's attendance needs attention."
        elif notification_type == "emergency":
            return f"EMERGENCY: {context.get('message', 'Please contact school immediately')} - {school_name}"
        else:
            return (
                f"Notification from {school_name}. Please check your email for details."
            )

    @staticmethod
    def _send_single_sms(phone_number, message):
        """Send single SMS (implement with your SMS provider)"""
        try:
            # Example implementation with Twilio
            # from twilio.rest import Client
            # client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
            # client.messages.create(
            #     body=message,
            #     from_=settings.TWILIO_PHONE_NUMBER,
            #     to=phone_number
            # )

            # For now, just log the SMS
            logger.info(f"SMS sent to {phone_number}: {message[:50]}...")
            return True

        except Exception as e:
            logger.error(f"SMS send failed: {str(e)}")
            return False

    @staticmethod
    def _schedule_notification(
        notification_type, recipients, context, sender, scheduled_at
    ):
        """Schedule notification for later delivery"""
        try:
            # Store in cache or database for scheduled delivery
            notification_data = {
                "notification_type": notification_type,
                "recipients": recipients,
                "context": context,
                "sender_id": sender.id if sender else None,
                "scheduled_at": scheduled_at.isoformat(),
                "created_at": timezone.now().isoformat(),
            }

            # Use Celery for scheduling
            send_scheduled_notification.apply_async(
                args=[notification_data], eta=scheduled_at
            )

            return {"status": "scheduled", "scheduled_at": scheduled_at}

        except Exception as e:
            logger.error(f"Error scheduling notification: {str(e)}")
            raise

    @staticmethod
    def _log_notification(notification_type, results, sender):
        """Log notification results"""
        try:
            log_data = {
                "notification_type": notification_type,
                "sender_id": sender.id if sender else None,
                "results": results,
                "timestamp": timezone.now().isoformat(),
            }

            # Store in cache for recent activity
            cache_key = f"notification_log_{timezone.now().strftime('%Y%m%d')}"
            recent_logs = cache.get(cache_key, [])
            recent_logs.append(log_data)
            recent_logs = recent_logs[-100:]  # Keep only last 100
            cache.set(cache_key, recent_logs, 86400)  # 24 hours

            logger.info(f"Notification logged: {notification_type} - {results}")

        except Exception as e:
            logger.error(f"Error logging notification: {str(e)}")

    @staticmethod
    def send_student_notification(
        student, notification_type, context, include_parents=True
    ):
        """Send notification to student and optionally their parents"""
        recipients = [{"type": "student", "id": str(student.id)}]

        if include_parents:
            for parent in student.get_parents():
                recipients.append({"type": "parent", "id": str(parent.id)})

        context["student"] = student

        return NotificationService.send_notification(
            notification_type, recipients, context
        )

    @staticmethod
    def send_class_notification(class_id, notification_type, context):
        """Send notification to all students in a class and their parents"""
        try:
            from src.academics.models import Class

            class_obj = Class.objects.get(id=class_id)
            students = Student.objects.filter(current_class=class_obj, status="Active")

            recipients = []
            for student in students:
                recipients.append({"type": "student", "id": str(student.id)})
                for parent in student.get_parents():
                    recipients.append({"type": "parent", "id": str(parent.id)})

            context["class"] = class_obj
            context["student_count"] = students.count()

            return NotificationService.send_notification(
                notification_type, recipients, context
            )

        except Exception as e:
            logger.error(f"Error sending class notification: {str(e)}")
            raise

    @staticmethod
    def get_notification_statistics():
        """Get notification statistics"""
        try:
            today = timezone.now().strftime("%Y%m%d")
            cache_key = f"notification_log_{today}"
            logs = cache.get(cache_key, [])

            stats = {
                "total_notifications": len(logs),
                "by_type": {},
                "by_channel": {"email": 0, "sms": 0, "push": 0},
                "success_rate": 0,
            }

            total_successful = 0
            total_attempted = 0

            for log in logs:
                notification_type = log["notification_type"]
                results = log["results"]

                stats["by_type"][notification_type] = (
                    stats["by_type"].get(notification_type, 0) + 1
                )

                for channel in ["email", "sms", "push"]:
                    successful = results["successful"].get(channel, 0)
                    failed = results["failed"].get(channel, 0)

                    stats["by_channel"][channel] += successful
                    total_successful += successful
                    total_attempted += successful + failed

            if total_attempted > 0:
                stats["success_rate"] = round(
                    (total_successful / total_attempted) * 100, 1
                )

            return stats

        except Exception as e:
            logger.error(f"Error getting notification statistics: {str(e)}")
            return {}


@shared_task
def send_scheduled_notification(notification_data):
    """Celery task for sending scheduled notifications"""
    try:
        notification_type = notification_data["notification_type"]
        recipients = notification_data["recipients"]
        context = notification_data["context"]
        sender_id = notification_data.get("sender_id")

        sender = None
        if sender_id:
            from django.contrib.auth import get_user_model

            User = get_user_model()
            try:
                sender = User.objects.get(id=sender_id)
            except User.DoesNotExist:
                pass

        return NotificationService.send_notification(
            notification_type, recipients, context, sender
        )

    except Exception as e:
        logger.error(f"Error in scheduled notification task: {str(e)}")
        raise
