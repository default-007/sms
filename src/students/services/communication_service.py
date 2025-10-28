# students/services/communication_service.py
import json
import logging

from django.conf import settings
from django.core.cache import cache
from django.core.mail import send_mail, send_mass_mail
from django.db import transaction
from django.template.loader import render_to_string
from django.utils import timezone

from ..models import Parent, Student, StudentParentRelation

logger = logging.getLogger(__name__)


class CommunicationService:
    """Service for handling all student-related communications"""

    MESSAGE_TYPES = {
        "admission": "Admission Notification",
        "fee_reminder": "Fee Reminder",
        "attendance_alert": "Attendance Alert",
        "exam_notification": "Exam Notification",
        "general": "General Announcement",
        "emergency": "Emergency Alert",
        "report_card": "Report Card Available",
        "event": "Event Notification",
    }

    @staticmethod
    def send_admission_notification(student, send_sms=True, send_email=True):
        """Send admission confirmation to student and parents"""
        try:
            notifications_sent = {"email": 0, "sms": 0, "errors": []}

            context = {
                "student": student,
                "school_name": getattr(settings, "SCHOOL_NAME", "School"),
                "admission_date": student.admission_date,
                "class": student.current_class,
            }

            # Send to student
            if send_email and student.email:
                try:
                    send_mail(
                        subject=f'Admission Confirmation - {context["school_name"]}',
                        message=render_to_string(
                            "emails/student_admission.txt", context
                        ),
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[student.email],
                        fail_silently=False,
                    )
                    notifications_sent["email"] += 1
                except Exception as e:
                    notifications_sent["errors"].append(f"Student email: {str(e)}")

            # Send to parents
            parents = student.get_parents()
            for parent in parents:
                relation = student.student_parent_relations.filter(
                    parent=parent
                ).first()

                if send_email and relation.receive_email and parent.user.email:
                    try:
                        parent_context = {
                            **context,
                            "parent": parent,
                            "relation": relation,
                        }
                        send_mail(
                            subject=f'Student Admission Notification - {context["school_name"]}',
                            message=render_to_string(
                                "emails/parent_admission_notification.txt",
                                parent_context,
                            ),
                            from_email=settings.DEFAULT_FROM_EMAIL,
                            recipient_list=[parent.user.email],
                            fail_silently=False,
                        )
                        notifications_sent["email"] += 1
                    except Exception as e:
                        notifications_sent["errors"].append(
                            f"Parent email {parent.user.email}: {str(e)}"
                        )

                if send_sms and relation.receive_sms and parent.user.phone_number:
                    try:
                        CommunicationService._send_sms(
                            parent.user.phone_number,
                            f"Admission confirmed for {student.get_full_name()} in {student.current_class}. {context['school_name']}",
                        )
                        notifications_sent["sms"] += 1
                    except Exception as e:
                        notifications_sent["errors"].append(
                            f"Parent SMS {parent.user.phone_number}: {str(e)}"
                        )

            logger.info(
                f"Admission notifications sent for {student.admission_number}: {notifications_sent}"
            )
            return notifications_sent

        except Exception as e:
            logger.error(f"Error sending admission notification: {str(e)}")
            return {"email": 0, "sms": 0, "errors": [str(e)]}

    @staticmethod
    def send_fee_reminder(
        student, amount_due, due_date, send_sms=True, send_email=True
    ):
        """Send fee reminder to parents"""
        try:
            notifications_sent = {"email": 0, "sms": 0, "errors": []}

            context = {
                "student": student,
                "amount_due": amount_due,
                "due_date": due_date,
                "school_name": getattr(settings, "SCHOOL_NAME", "School"),
            }

            # Get parents with financial responsibility
            parents = student.student_parent_relations.filter(
                financial_responsibility=True
            ).select_related("parent__user")

            if not parents.exists():
                # Fallback to primary contact
                parents = student.student_parent_relations.filter(
                    is_primary_contact=True
                ).select_related("parent__user")

            for relation in parents:
                parent = relation.parent

                if send_email and relation.receive_email and parent.user.email:
                    try:
                        parent_context = {**context, "parent": parent}
                        send_mail(
                            subject=f"Fee Reminder - {student.get_full_name()}",
                            message=render_to_string(
                                "emails/fee_reminder.txt", parent_context
                            ),
                            from_email=settings.DEFAULT_FROM_EMAIL,
                            recipient_list=[parent.user.email],
                            fail_silently=False,
                        )
                        notifications_sent["email"] += 1
                    except Exception as e:
                        notifications_sent["errors"].append(
                            f"Email {parent.user.email}: {str(e)}"
                        )

                if send_sms and relation.receive_sms and parent.user.phone_number:
                    try:
                        message = f"Fee reminder: ₹{amount_due} due on {due_date.strftime('%d/%m/%Y')} for {student.get_full_name()}"
                        CommunicationService._send_sms(
                            parent.user.phone_number, message
                        )
                        notifications_sent["sms"] += 1
                    except Exception as e:
                        notifications_sent["errors"].append(
                            f"SMS {parent.user.phone_number}: {str(e)}"
                        )

            return notifications_sent

        except Exception as e:
            logger.error(f"Error sending fee reminder: {str(e)}")
            return {"email": 0, "sms": 0, "errors": [str(e)]}

    @staticmethod
    def send_attendance_alert(
        student, attendance_percentage, send_sms=True, send_email=True
    ):
        """Send attendance alert to parents"""
        try:
            notifications_sent = {"email": 0, "sms": 0, "errors": []}

            context = {
                "student": student,
                "attendance_percentage": attendance_percentage,
                "school_name": getattr(settings, "SCHOOL_NAME", "School"),
                "threshold": 75,  # Minimum attendance requirement
            }

            # Get parents who want attendance notifications
            parents = student.student_parent_relations.filter(
                access_to_attendance=True
            ).select_related("parent__user")

            for relation in parents:
                parent = relation.parent

                if send_email and relation.receive_email and parent.user.email:
                    try:
                        parent_context = {**context, "parent": parent}
                        send_mail(
                            subject=f"Attendance Alert - {student.get_full_name()}",
                            message=render_to_string(
                                "emails/attendance_alert.txt", parent_context
                            ),
                            from_email=settings.DEFAULT_FROM_EMAIL,
                            recipient_list=[parent.user.email],
                            fail_silently=False,
                        )
                        notifications_sent["email"] += 1
                    except Exception as e:
                        notifications_sent["errors"].append(
                            f"Email {parent.user.email}: {str(e)}"
                        )

                if send_sms and relation.receive_sms and parent.user.phone_number:
                    try:
                        message = f"Attendance Alert: {student.get_full_name()} - {attendance_percentage}% attendance. Contact school if needed."
                        CommunicationService._send_sms(
                            parent.user.phone_number, message
                        )
                        notifications_sent["sms"] += 1
                    except Exception as e:
                        notifications_sent["errors"].append(
                            f"SMS {parent.user.phone_number}: {str(e)}"
                        )

            return notifications_sent

        except Exception as e:
            logger.error(f"Error sending attendance alert: {str(e)}")
            return {"email": 0, "sms": 0, "errors": [str(e)]}

    @staticmethod
    def send_bulk_announcement(
        student_ids,
        subject,
        message,
        message_type="general",
        send_sms=True,
        send_email=True,
        sender=None,
    ):
        """Send bulk announcement to multiple students and their parents"""
        try:
            students = Student.objects.filter(id__in=student_ids).prefetch_related(
                "student_parent_relations__parent__user"
            )

            notifications_sent = {
                "email": 0,
                "sms": 0,
                "errors": [],
                "total_recipients": 0,
            }
            email_messages = []
            sms_queue = []

            context = {
                "subject": subject,
                "message": message,
                "message_type": message_type,
                "school_name": getattr(settings, "SCHOOL_NAME", "School"),
                "sender": sender.get_full_name() if sender else "School Administration",
                "timestamp": timezone.now(),
            }

            for student in students:
                # Send to student if they have email
                if send_email and student.email:
                    student_context = {
                        **context,
                        "student": student,
                        "recipient_type": "student",
                    }
                    email_messages.append(
                        (
                            subject,
                            render_to_string(
                                "emails/bulk_announcement.txt", student_context
                            ),
                            settings.DEFAULT_FROM_EMAIL,
                            [student.email],
                        )
                    )

                # Send to parents
                for relation in student.student_parent_relations.all():
                    parent = relation.parent
                    notifications_sent["total_recipients"] += 1

                    if send_email and relation.receive_email and parent.user.email:
                        parent_context = {
                            **context,
                            "student": student,
                            "parent": parent,
                            "recipient_type": "parent",
                        }
                        email_messages.append(
                            (
                                f"{subject} - {student.get_full_name()}",
                                render_to_string(
                                    "emails/bulk_announcement.txt", parent_context
                                ),
                                settings.DEFAULT_FROM_EMAIL,
                                [parent.user.email],
                            )
                        )

                    if send_sms and relation.receive_sms and parent.user.phone_number:
                        sms_message = f"{subject}: {message[:100]}{'...' if len(message) > 100 else ''}"
                        sms_queue.append((parent.user.phone_number, sms_message))

            # Send bulk emails
            if email_messages:
                try:
                    sent_count = send_mass_mail(email_messages, fail_silently=False)
                    notifications_sent["email"] = sent_count
                except Exception as e:
                    notifications_sent["errors"].append(f"Bulk email error: {str(e)}")

            # Send bulk SMS
            if sms_queue:
                for phone_number, sms_message in sms_queue:
                    try:
                        CommunicationService._send_sms(phone_number, sms_message)
                        notifications_sent["sms"] += 1
                    except Exception as e:
                        notifications_sent["errors"].append(
                            f"SMS {phone_number}: {str(e)}"
                        )

            logger.info(f"Bulk announcement sent: {notifications_sent}")
            return notifications_sent

        except Exception as e:
            logger.error(f"Error sending bulk announcement: {str(e)}")
            return {"email": 0, "sms": 0, "errors": [str(e)], "total_recipients": 0}

    @staticmethod
    def send_emergency_alert(
        student_ids, alert_message, send_sms=True, send_email=True, sender=None
    ):
        """Send emergency alert with high priority"""
        try:
            notifications_sent = CommunicationService.send_bulk_announcement(
                student_ids=student_ids,
                subject="EMERGENCY ALERT",
                message=alert_message,
                message_type="emergency",
                send_sms=send_sms,
                send_email=send_email,
                sender=sender,
            )

            # Also send push notifications if available
            CommunicationService._send_push_notifications(
                student_ids, "Emergency Alert", alert_message
            )

            return notifications_sent

        except Exception as e:
            logger.error(f"Error sending emergency alert: {str(e)}")
            return {"email": 0, "sms": 0, "errors": [str(e)]}

    @staticmethod
    def send_report_card_notification(student, report_card_url=None):
        """Send report card availability notification"""
        try:
            notifications_sent = {"email": 0, "sms": 0, "errors": []}

            context = {
                "student": student,
                "report_card_url": report_card_url,
                "school_name": getattr(settings, "SCHOOL_NAME", "School"),
            }

            # Send to parents with grade access
            parents = student.student_parent_relations.filter(
                access_to_grades=True
            ).select_related("parent__user")

            for relation in parents:
                parent = relation.parent

                if relation.receive_email and parent.user.email:
                    try:
                        parent_context = {**context, "parent": parent}
                        send_mail(
                            subject=f"Report Card Available - {student.get_full_name()}",
                            message=render_to_string(
                                "emails/report_card_notification.txt", parent_context
                            ),
                            from_email=settings.DEFAULT_FROM_EMAIL,
                            recipient_list=[parent.user.email],
                            fail_silently=False,
                        )
                        notifications_sent["email"] += 1
                    except Exception as e:
                        notifications_sent["errors"].append(
                            f"Email {parent.user.email}: {str(e)}"
                        )

                if relation.receive_sms and parent.user.phone_number:
                    try:
                        message = f"Report card available for {student.get_full_name()}. Please check school portal."
                        CommunicationService._send_sms(
                            parent.user.phone_number, message
                        )
                        notifications_sent["sms"] += 1
                    except Exception as e:
                        notifications_sent["errors"].append(
                            f"SMS {parent.user.phone_number}: {str(e)}"
                        )

            return notifications_sent

        except Exception as e:
            logger.error(f"Error sending report card notification: {str(e)}")
            return {"email": 0, "sms": 0, "errors": [str(e)]}

    @staticmethod
    def get_communication_preferences(parent):
        """Get communication preferences for a parent"""
        try:
            relations = parent.parent_student_relations.all()
            preferences = {
                "email_enabled": any(r.receive_email for r in relations),
                "sms_enabled": any(r.receive_sms for r in relations),
                "push_enabled": any(r.receive_push_notifications for r in relations),
                "children": [],
            }

            for relation in relations:
                preferences["children"].append(
                    {
                        "student_id": str(relation.student.id),
                        "student_name": relation.student.get_full_name(),
                        "email": relation.receive_email,
                        "sms": relation.receive_sms,
                        "push": relation.receive_push_notifications,
                        "access_grades": relation.access_to_grades,
                        "access_attendance": relation.access_to_attendance,
                        "access_financial": relation.access_to_financial_info,
                    }
                )

            return preferences

        except Exception as e:
            logger.error(f"Error getting communication preferences: {str(e)}")
            return {}

    @staticmethod
    def update_communication_preferences(parent, preferences):
        """Update communication preferences for a parent"""
        try:
            with transaction.atomic():
                for child_pref in preferences.get("children", []):
                    relation = parent.parent_student_relations.filter(
                        student_id=child_pref["student_id"]
                    ).first()

                    if relation:
                        relation.receive_email = child_pref.get("email", True)
                        relation.receive_sms = child_pref.get("sms", True)
                        relation.receive_push_notifications = child_pref.get(
                            "push", True
                        )
                        relation.access_to_grades = child_pref.get(
                            "access_grades", True
                        )
                        relation.access_to_attendance = child_pref.get(
                            "access_attendance", True
                        )
                        relation.access_to_financial_info = child_pref.get(
                            "access_financial", False
                        )
                        relation.save()

            logger.info(
                f"Communication preferences updated for parent {parent.get_full_name()}"
            )
            return True

        except Exception as e:
            logger.error(f"Error updating communication preferences: {str(e)}")
            return False

    @staticmethod
    def _send_sms(phone_number, message):
        """Send SMS using configured SMS provider"""
        # This would integrate with SMS providers like Twilio, AWS SNS, etc.
        logger.info(f"SMS sent to {phone_number}: {message[:50]}...")
        return True

    @staticmethod
    def _send_push_notifications(student_ids, title, message):
        """Send push notifications to mobile apps"""
        # This would integrate with push notification services
        logger.info(f"Push notifications sent to {len(student_ids)} students: {title}")
        return True

    @staticmethod
    def get_communication_stats():
        """Get communication statistics"""
        try:
            cache_key = "communication_stats"
            stats = cache.get(cache_key)

            if stats is None:
                relations = StudentParentRelation.objects.all()
                stats = {
                    "total_parents": relations.values("parent").distinct().count(),
                    "email_enabled": relations.filter(receive_email=True).count(),
                    "sms_enabled": relations.filter(receive_sms=True).count(),
                    "push_enabled": relations.filter(
                        receive_push_notifications=True
                    ).count(),
                    "grade_access": relations.filter(access_to_grades=True).count(),
                    "attendance_access": relations.filter(
                        access_to_attendance=True
                    ).count(),
                    "financial_access": relations.filter(
                        access_to_financial_info=True
                    ).count(),
                }
                cache.set(cache_key, stats, 1800)  # Cache for 30 minutes

            return stats

        except Exception as e:
            logger.error(f"Error getting communication stats: {str(e)}")
            return {}
