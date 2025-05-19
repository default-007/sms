from django.db.models import Count
from accounts.task import shared_task
from django.contrib.auth import get_user_model
from django.core.mail import send_mail, send_mass_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
import logging
import csv
import io

from .models import UserRole, UserRoleAssignment, UserAuditLog, UserSession
from .services import RoleService
from .utils import send_notification_email, generate_secure_password

logger = logging.getLogger(__name__)
User = get_user_model()


@shared_task(bind=True, max_retries=3)
def send_user_notification_email(self, user_id, subject, template_name, context=None):
    """
    Send notification email to a specific user.

    Args:
        user_id: ID of the user to send email to
        subject: Email subject
        template_name: Template to use for email
        context: Additional context for template
    """
    try:
        user = User.objects.get(id=user_id)
        context = context or {}

        success = send_notification_email(user, subject, template_name, context)

        if success:
            logger.info(f"Successfully sent email to user {user.username}")
        else:
            logger.error(f"Failed to send email to user {user.username}")
            raise Exception("Failed to send email")

        return {"status": "success", "user_id": user_id}

    except User.DoesNotExist:
        logger.error(f"User with ID {user_id} not found")
        return {"status": "error", "message": "User not found"}

    except Exception as exc:
        logger.error(f"Error sending email to user {user_id}: {str(exc)}")
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=60 * (2**self.request.retries))
        return {"status": "error", "message": str(exc)}


@shared_task(bind=True, max_retries=2)
def send_bulk_notification_emails(self, user_ids, subject, template_name, context=None):
    """
    Send notification emails to multiple users.

    Args:
        user_ids: List of user IDs
        subject: Email subject
        template_name: Template to use for email
        context: Additional context for template
    """
    try:
        users = User.objects.filter(id__in=user_ids, is_active=True)
        context = context or {}
        context["site_name"] = getattr(
            settings, "SITE_NAME", "School Management System"
        )

        email_messages = []
        successful_sends = 0

        for user in users:
            try:
                user_context = context.copy()
                user_context["user"] = user

                html_message = render_to_string(template_name, user_context)

                email_messages.append(
                    (
                        subject,
                        "",  # Plain text message
                        settings.DEFAULT_FROM_EMAIL,
                        [user.email],
                        html_message,
                    )
                )

            except Exception as e:
                logger.error(
                    f"Error preparing email for user {user.username}: {str(e)}"
                )

        if email_messages:
            # Send emails in batches
            batch_size = 50
            for i in range(0, len(email_messages), batch_size):
                batch = email_messages[i : i + batch_size]
                try:
                    send_mass_mail(batch)
                    successful_sends += len(batch)
                except Exception as e:
                    logger.error(f"Error sending email batch: {str(e)}")

        logger.info(
            f"Successfully sent {successful_sends} out of {len(user_ids)} emails"
        )
        return {"status": "success", "sent": successful_sends, "total": len(user_ids)}

    except Exception as exc:
        logger.error(f"Error in bulk email task: {str(exc)}")
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=60 * (2**self.request.retries))
        return {"status": "error", "message": str(exc)}


@shared_task
def cleanup_expired_role_assignments():
    """
    Cleanup expired role assignments.
    """
    try:
        expired_count = RoleService.expire_role_assignments()
        logger.info(f"Cleaned up {expired_count} expired role assignments")
        return {"status": "success", "expired_count": expired_count}

    except Exception as e:
        logger.error(f"Error cleaning up expired role assignments: {str(e)}")
        return {"status": "error", "message": str(e)}


@shared_task
def cleanup_old_audit_logs(retention_days=365):
    """
    Cleanup old audit logs.

    Args:
        retention_days: Number of days to retain logs
    """
    try:
        deleted_count = UserAuditLog.objects.cleanup_old_logs(retention_days)
        logger.info(f"Cleaned up {deleted_count} old audit log entries")
        return {"status": "success", "deleted_count": deleted_count}

    except Exception as e:
        logger.error(f"Error cleaning up old audit logs: {str(e)}")
        return {"status": "error", "message": str(e)}


@shared_task
def cleanup_old_sessions(retention_days=30):
    """
    Cleanup old inactive sessions.

    Args:
        retention_days: Number of days to retain sessions
    """
    try:
        deleted_count = UserSession.objects.cleanup_old_sessions(retention_days)
        logger.info(f"Cleaned up {deleted_count} old session records")
        return {"status": "success", "deleted_count": deleted_count}

    except Exception as e:
        logger.error(f"Error cleaning up old sessions: {str(e)}")
        return {"status": "error", "message": str(e)}


@shared_task
def send_password_expiry_reminders():
    """
    Send password expiry reminders to users.
    """
    try:
        # Get users whose passwords expire in the next 7 days
        expiry_date = timezone.now() + timedelta(
            days=90 - 7
        )  # Assuming 90-day password policy

        users_to_remind = User.objects.filter(
            password_changed_at__lt=expiry_date,
            is_active=True,
            requires_password_change=False,
        )

        reminder_count = 0

        for user in users_to_remind:
            from .utils import is_password_expired

            # Check if password expires in next 7 days
            days_until_expiry = (
                user.password_changed_at + timedelta(days=90) - timezone.now()
            ).days

            if 0 <= days_until_expiry <= 7:
                # Send reminder email
                send_notification_email(
                    user,
                    "Password Expiry Reminder",
                    "accounts/emails/password_expiry_reminder.html",
                    {"days_until_expiry": days_until_expiry},
                )
                reminder_count += 1

        logger.info(f"Sent password expiry reminders to {reminder_count} users")
        return {"status": "success", "reminders_sent": reminder_count}

    except Exception as e:
        logger.error(f"Error sending password expiry reminders: {str(e)}")
        return {"status": "error", "message": str(e)}


@shared_task
def send_role_expiry_notifications():
    """
    Send notifications for role assignments expiring soon.
    """
    try:
        # Get assignments expiring in the next 7 days
        expiring_assignments = UserRoleAssignment.objects.expiring_soon(days=7)

        notification_count = 0

        for assignment in expiring_assignments:
            days_until_expiry = assignment.days_until_expiry()

            # Send notification to user
            send_notification_email(
                assignment.user,
                f'Role "{assignment.role.name}" Expiring Soon',
                "accounts/emails/role_expiry_notification.html",
                {"assignment": assignment, "days_until_expiry": days_until_expiry},
            )

            # Send notification to admin (if configured)
            if hasattr(settings, "ADMIN_EMAIL") and settings.ADMIN_EMAIL:
                send_mail(
                    subject=f"Role Assignment Expiring: {assignment.user.username}",
                    message=f'Role "{assignment.role.name}" for user {assignment.user.username} expires in {days_until_expiry} days.',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[settings.ADMIN_EMAIL],
                    fail_silently=True,
                )

            notification_count += 1

        logger.info(
            f"Sent role expiry notifications for {notification_count} assignments"
        )
        return {"status": "success", "notifications_sent": notification_count}

    except Exception as e:
        logger.error(f"Error sending role expiry notifications: {str(e)}")
        return {"status": "error", "message": str(e)}


@shared_task
def generate_user_activity_report(start_date, end_date, email_to):
    """
    Generate and email user activity report.

    Args:
        start_date: Start date for report (YYYY-MM-DD)
        end_date: End date for report (YYYY-MM-DD)
        email_to: Email address to send report to
    """
    try:
        from datetime import datetime

        start_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
        end_dt = datetime.strptime(end_date, "%Y-%m-%d").date()

        # Generate report data
        activity_data = (
            UserAuditLog.objects.filter(timestamp__date__range=[start_dt, end_dt])
            .values("action")
            .annotate(count=Count("id"))
            .order_by("-count")
        )

        login_data = (
            UserAuditLog.objects.filter(
                timestamp__date__range=[start_dt, end_dt], action="login"
            )
            .values("user__username", "user__email")
            .annotate(login_count=Count("id"))
            .order_by("-login_count")[:20]
        )  # Top 20 most active users

        # Create CSV report
        output = io.StringIO()

        # Activity summary
        output.write("User Activity Report\n")
        output.write(f"Period: {start_date} to {end_date}\n\n")
        output.write("Activity Summary:\n")
        output.write("Action,Count\n")

        for item in activity_data:
            output.write(f"{item['action']},{item['count']}\n")

        output.write("\n\nTop Active Users (by logins):\n")
        output.write("Username,Email,Login Count\n")

        for item in login_data:
            output.write(
                f"{item['user__username']},{item['user__email']},{item['login_count']}\n"
            )

        # Send email with report
        from django.core.mail import EmailMessage

        email = EmailMessage(
            subject=f"User Activity Report ({start_date} to {end_date})",
            body=f"Please find attached the user activity report for the period {start_date} to {end_date}.",
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[email_to],
        )

        email.attach(
            f"user_activity_report_{start_date}_to_{end_date}.csv",
            output.getvalue(),
            "text/csv",
        )

        email.send()

        logger.info(f"Successfully generated and sent activity report to {email_to}")
        return {"status": "success", "email_sent_to": email_to}

    except Exception as e:
        logger.error(f"Error generating activity report: {str(e)}")
        return {"status": "error", "message": str(e)}


@shared_task(bind=True, max_retries=3)
def bulk_user_import(self, csv_data, default_password, default_roles, created_by_id):
    """
    Import users from CSV data.

    Args:
        csv_data: CSV data as string
        default_password: Default password for new users
        default_roles: List of default role names
        created_by_id: ID of user performing the import
    """
    try:
        from io import StringIO
        import csv

        created_by = User.objects.get(id=created_by_id)
        csv_file = StringIO(csv_data)
        reader = csv.DictReader(csv_file)

        created_count = 0
        error_count = 0
        errors = []

        for row_num, row in enumerate(reader, start=2):
            try:
                username = row.get("username", "").strip()
                email = row.get("email", "").strip()

                if not username or not email:
                    errors.append(f"Row {row_num}: Missing username or email")
                    error_count += 1
                    continue

                # Check if user exists
                if User.objects.filter(username=username).exists():
                    errors.append(f"Row {row_num}: Username {username} already exists")
                    error_count += 1
                    continue

                if User.objects.filter(email=email).exists():
                    errors.append(f"Row {row_num}: Email {email} already exists")
                    error_count += 1
                    continue

                # Create user
                user_data = {
                    "username": username,
                    "email": email,
                    "first_name": row.get("first_name", ""),
                    "last_name": row.get("last_name", ""),
                    "phone_number": row.get("phone_number", ""),
                }

                user = User.objects.create_user(**user_data, password=default_password)
                user.requires_password_change = True
                user.save()

                # Assign roles
                for role_name in default_roles:
                    try:
                        RoleService.assign_role_to_user(
                            user, role_name, assigned_by=created_by
                        )
                    except ValueError:
                        pass

                # Send welcome email
                send_notification_email(
                    user,
                    "Welcome to the School Management System",
                    "accounts/emails/welcome_new_user.html",
                    {"temporary_password": default_password},
                )

                created_count += 1

            except Exception as e:
                errors.append(f"Row {row_num}: {str(e)}")
                error_count += 1

        # Send completion notification to the admin
        send_notification_email(
            created_by,
            "User Import Completed",
            "accounts/emails/import_completed.html",
            {
                "created_count": created_count,
                "error_count": error_count,
                "errors": errors[:10],  # Show first 10 errors
            },
        )

        logger.info(
            f"User import completed: {created_count} created, {error_count} errors"
        )
        return {
            "status": "success",
            "created_count": created_count,
            "error_count": error_count,
            "errors": errors,
        }

    except Exception as exc:
        logger.error(f"Error in bulk user import: {str(exc)}")
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=60 * (2**self.request.retries))
        return {"status": "error", "message": str(exc)}


@shared_task
def unlock_locked_accounts():
    """
    Unlock accounts that have been locked for more than the lockout duration.
    """
    try:
        lockout_duration = getattr(settings, "ACCOUNT_LOCKOUT_DURATION", 30)  # minutes
        unlock_time = timezone.now() - timedelta(minutes=lockout_duration)

        locked_users = User.objects.filter(
            failed_login_attempts__gte=5, last_failed_login__lt=unlock_time
        )

        unlocked_count = 0
        for user in locked_users:
            user.failed_login_attempts = 0
            user.last_failed_login = None
            user.save(update_fields=["failed_login_attempts", "last_failed_login"])

            # Create audit log
            UserAuditLog.objects.create(
                user=user,
                action="account_unlock",
                description="Account unlocked automatically after lockout duration",
            )

            # Send notification
            send_notification_email(
                user, "Account Unlocked", "accounts/emails/account_unlocked.html"
            )

            unlocked_count += 1

        logger.info(f"Unlocked {unlocked_count} user accounts")
        return {"status": "success", "unlocked_count": unlocked_count}

    except Exception as e:
        logger.error(f"Error unlocking accounts: {str(e)}")
        return {"status": "error", "message": str(e)}


@shared_task
def send_login_alerts():
    """
    Send alerts for suspicious login activities.
    """
    try:
        # Find users with multiple failed login attempts in the last hour
        one_hour_ago = timezone.now() - timedelta(hours=1)

        suspicious_activity = (
            UserAuditLog.objects.filter(
                timestamp__gte=one_hour_ago,
                action="login",
                description__contains="Failed login attempt",
            )
            .values("user_id")
            .annotate(attempt_count=Count("id"))
            .filter(attempt_count__gte=3)
        )

        alert_count = 0

        for activity in suspicious_activity:
            try:
                user = User.objects.get(id=activity["user_id"])
                attempt_count = activity["attempt_count"]

                # Send alert email to admin
                if (
                    hasattr(settings, "SECURITY_ALERT_EMAIL")
                    and settings.SECURITY_ALERT_EMAIL
                ):
                    send_mail(
                        subject=f"Security Alert: Multiple Failed Login Attempts",
                        message=f"User {user.username} has {attempt_count} failed login attempts in the last hour.",
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[settings.SECURITY_ALERT_EMAIL],
                        fail_silently=True,
                    )

                alert_count += 1

            except User.DoesNotExist:
                pass

        logger.info(f"Sent {alert_count} security alerts")
        return {"status": "success", "alerts_sent": alert_count}

    except Exception as e:
        logger.error(f"Error sending login alerts: {str(e)}")
        return {"status": "error", "message": str(e)}
