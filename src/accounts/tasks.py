# src/accounts/tasks.py

import csv
import io
import logging
from datetime import timedelta
from typing import Dict, List

from celery import shared_task
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail, send_mass_mail
from django.db.models import Count, Q
from django.template.loader import render_to_string
from django.utils import timezone

from .models import UserAuditLog, UserRole, UserRoleAssignment, UserSession
from .services import AuthenticationService, RoleService, UserAnalyticsService
from .utils import generate_secure_password, send_notification_email

logger = logging.getLogger(__name__)
User = get_user_model()


@shared_task(bind=True, max_retries=3)
def send_user_notification_email(
    self, user_id: int, subject: str, template_name: str, context: Dict = None
):
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

            # Create audit log
            UserAuditLog.objects.create(
                user=user,
                action="email_send",
                description=f"Email sent: {subject}",
                extra_data={"template": template_name, "subject": subject},
            )
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
def send_bulk_notification_emails(
    self, user_ids: List[int], subject: str, template_name: str, context: Dict = None
):
    """
    Send notification emails to multiple users.

    Args:
        user_ids: List of user IDs
        subject: Email subject
        template_name: Template to use for email
        context: Additional context for template
    """
    try:
        users = User.objects.filter(
            id__in=user_ids, is_active=True, email_notifications=True
        )
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

                    # Create audit logs for successful sends
                    for j, message in enumerate(batch):
                        user_email = message[3][0]  # recipient email
                        try:
                            user = users.get(email=user_email)
                            UserAuditLog.objects.create(
                                user=user,
                                action="email_send",
                                description=f"Bulk email sent: {subject}",
                                extra_data={
                                    "template": template_name,
                                    "batch": i // batch_size + 1,
                                },
                            )
                        except User.DoesNotExist:
                            pass

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
    Cleanup expired role assignments and send notifications.
    """
    try:
        # Get assignments that will expire soon (7 days)
        expiring_soon = UserRoleAssignment.objects.expiring_soon(days=7)

        # Send notifications for assignments expiring soon
        for assignment in expiring_soon:
            days_until_expiry = assignment.days_until_expiry()

            # Send notification to user
            send_user_notification_email.delay(
                assignment.user.id,
                f'Role "{assignment.role.name}" Expiring Soon',
                "accounts/emails/role_expiry_notification.html",
                {"assignment": assignment, "days_until_expiry": days_until_expiry},
            )

            # Send notification to admin if configured
            if hasattr(settings, "ADMIN_EMAIL") and settings.ADMIN_EMAIL:
                send_mail(
                    subject=f"Role Assignment Expiring: {assignment.user.username}",
                    message=f'Role "{assignment.role.name}" for user {assignment.user.username} expires in {days_until_expiry} days.',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[settings.ADMIN_EMAIL],
                    fail_silently=True,
                )

        # Actually expire the assignments
        expired_count = RoleService.expire_role_assignments()

        logger.info(f"Cleaned up {expired_count} expired role assignments")
        logger.info(f"Sent notifications for {len(expiring_soon)} expiring assignments")

        return {
            "status": "success",
            "expired_count": expired_count,
            "expiring_notifications": len(expiring_soon),
        }

    except Exception as e:
        logger.error(f"Error cleaning up expired role assignments: {str(e)}")
        return {"status": "error", "message": str(e)}


@shared_task
def cleanup_old_audit_logs(retention_days: int = 365):
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
def cleanup_old_sessions(retention_days: int = 30):
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
        password_policy_days = getattr(settings, "PASSWORD_EXPIRY_DAYS", 90)
        reminder_threshold = getattr(settings, "PASSWORD_EXPIRY_REMINDER_DAYS", 7)

        expiry_date = timezone.now() - timedelta(
            days=password_policy_days - reminder_threshold
        )

        users_to_remind = User.objects.filter(
            password_changed_at__lt=expiry_date,
            is_active=True,
            requires_password_change=False,
        )

        reminder_count = 0

        for user in users_to_remind:
            # Check if password expires in next 7 days
            days_until_expiry = (
                user.password_changed_at
                + timedelta(days=password_policy_days)
                - timezone.now()
            ).days

            if 0 <= days_until_expiry <= reminder_threshold:
                # Send reminder email
                send_user_notification_email.delay(
                    user.id,
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
            AuthenticationService.unlock_account(user)
            unlocked_count += 1

        logger.info(f"Unlocked {unlocked_count} user accounts")
        return {"status": "success", "unlocked_count": unlocked_count}

    except Exception as e:
        logger.error(f"Error unlocking accounts: {str(e)}")
        return {"status": "error", "message": str(e)}


@shared_task
def send_security_alerts():
    """
    Send alerts for suspicious login activities and security events.
    """
    try:
        # Check for suspicious activities in the last hour
        one_hour_ago = timezone.now() - timedelta(hours=1)
        alert_count = 0

        # Find users with multiple failed login attempts
        suspicious_activity = (
            UserAuditLog.objects.filter(
                timestamp__gte=one_hour_ago,
                action="login",
                description__contains="Failed",
            )
            .values("user_id", "ip_address")
            .annotate(attempt_count=Count("id"))
            .filter(attempt_count__gte=3)
        )

        for activity in suspicious_activity:
            try:
                user = (
                    User.objects.get(id=activity["user_id"])
                    if activity["user_id"]
                    else None
                )
                attempt_count = activity["attempt_count"]
                ip_address = activity["ip_address"]

                # Send alert email to security team
                if (
                    hasattr(settings, "SECURITY_ALERT_EMAIL")
                    and settings.SECURITY_ALERT_EMAIL
                ):
                    subject = "Security Alert: Multiple Failed Login Attempts"
                    message = f"{'User ' + user.username if user else 'Unknown user'} has {attempt_count} failed login attempts from IP {ip_address} in the last hour."

                    send_mail(
                        subject=subject,
                        message=message,
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[settings.SECURITY_ALERT_EMAIL],
                        fail_silently=True,
                    )

                    # Log the security alert
                    UserAuditLog.objects.create(
                        user=user,
                        action="security_alert",
                        description=f"Security alert sent: {attempt_count} failed attempts from {ip_address}",
                        severity="high",
                        extra_data={
                            "alert_type": "failed_login_attempts",
                            "attempt_count": attempt_count,
                            "ip_address": ip_address,
                        },
                    )

                alert_count += 1

            except User.DoesNotExist:
                pass

        # Check for accounts locked in the last hour
        recently_locked = User.objects.filter(
            last_failed_login__gte=one_hour_ago, failed_login_attempts__gte=5
        )

        for user in recently_locked:
            if (
                hasattr(settings, "SECURITY_ALERT_EMAIL")
                and settings.SECURITY_ALERT_EMAIL
            ):
                send_mail(
                    subject=f"Account Locked: {user.username}",
                    message=f"User account {user.username} has been locked due to multiple failed login attempts.",
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[settings.SECURITY_ALERT_EMAIL],
                    fail_silently=True,
                )
                alert_count += 1

        logger.info(f"Sent {alert_count} security alerts")
        return {"status": "success", "alerts_sent": alert_count}

    except Exception as e:
        logger.error(f"Error sending security alerts: {str(e)}")
        return {"status": "error", "message": str(e)}


@shared_task(bind=True, max_retries=3)
def bulk_user_import(
    self,
    csv_data: str,
    default_password: str,
    default_roles: List[str],
    created_by_id: int,
    send_emails: bool = True,
    update_existing: bool = False,
):
    """
    Import users from CSV data.

    Args:
        csv_data: CSV data as string
        default_password: Default password for new users
        default_roles: List of default role names
        created_by_id: ID of user performing the import
        send_emails: Whether to send welcome emails
        update_existing: Whether to update existing users
    """
    try:
        created_by = User.objects.get(id=created_by_id)
        csv_file = io.StringIO(csv_data)
        reader = csv.DictReader(csv_file)

        created_count = 0
        updated_count = 0
        error_count = 0
        errors = []

        for row_num, row in enumerate(reader, start=2):
            try:
                email = row.get("email", "").strip().lower()
                username = row.get("username", "").strip()

                if not email:
                    errors.append(f"Row {row_num}: Email is required")
                    error_count += 1
                    continue

                # Check if user exists
                existing_user = User.objects.filter(email=email).first()

                if existing_user and not update_existing:
                    errors.append(
                        f"Row {row_num}: User with email {email} already exists"
                    )
                    error_count += 1
                    continue

                # Prepare user data
                user_data = {
                    "email": email,
                    "first_name": row.get("first_name", "").strip(),
                    "last_name": row.get("last_name", "").strip(),
                    "phone_number": row.get("phone_number", "").strip(),
                    "address": row.get("address", "").strip(),
                    "gender": row.get("gender", "").strip(),
                }

                if username:
                    user_data["username"] = username
                elif not existing_user:
                    # Generate username if not provided and user doesn't exist
                    user_data["username"] = AuthenticationService._generate_username(
                        user_data["first_name"], user_data["last_name"], email
                    )

                if existing_user and update_existing:
                    # Update existing user
                    for field, value in user_data.items():
                        if value and field != "email":  # Don't update email
                            setattr(existing_user, field, value)
                    existing_user.save()

                    # Update roles
                    existing_user.role_assignments.update(is_active=False)
                    for role_name in default_roles:
                        try:
                            RoleService.assign_role_to_user(
                                existing_user, role_name, assigned_by=created_by
                            )
                        except ValueError:
                            pass

                    updated_count += 1

                else:
                    # Create new user
                    user_data["password"] = default_password
                    user = AuthenticationService.register_user(
                        user_data,
                        role_names=default_roles,
                        created_by=created_by,
                        send_email=send_emails,
                    )
                    created_count += 1

            except Exception as e:
                errors.append(f"Row {row_num}: {str(e)}")
                error_count += 1

        # Send completion notification to the admin
        completion_context = {
            "created_count": created_count,
            "updated_count": updated_count,
            "error_count": error_count,
            "errors": errors[:10],  # Show first 10 errors
            "total_errors": len(errors),
        }

        send_user_notification_email.delay(
            created_by.id,
            "User Import Completed",
            "accounts/emails/import_completed.html",
            completion_context,
        )

        logger.info(
            f"User import completed: {created_count} created, {updated_count} updated, {error_count} errors"
        )

        return {
            "status": "success",
            "created_count": created_count,
            "updated_count": updated_count,
            "error_count": error_count,
            "errors": errors,
        }

    except Exception as exc:
        logger.error(f"Error in bulk user import: {str(exc)}")
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=60 * (2**self.request.retries))
        return {"status": "error", "message": str(exc)}


@shared_task
def generate_analytics_report(report_type: str = "daily", days: int = 30):
    """
    Generate analytics reports and cache them.

    Args:
        report_type: Type of report (daily, weekly, monthly)
        days: Number of days to include in the report
    """
    try:
        # Generate comprehensive analytics report
        report_data = UserAnalyticsService.generate_comprehensive_report(days)

        # Store in cache with appropriate expiration
        cache_key = f"analytics_report_{report_type}_{days}days"
        cache_timeout = {
            "daily": 86400,  # 24 hours
            "weekly": 604800,  # 7 days
            "monthly": 2592000,  # 30 days
        }.get(report_type, 86400)

        from django.core.cache import cache

        cache.set(cache_key, report_data, cache_timeout)

        # Send report to administrators if configured
        if (
            hasattr(settings, "ANALYTICS_REPORT_EMAILS")
            and settings.ANALYTICS_REPORT_EMAILS
        ):
            for admin_email in settings.ANALYTICS_REPORT_EMAILS:
                try:
                    admin_user = User.objects.filter(
                        email=admin_email, is_active=True
                    ).first()
                    if admin_user:
                        send_user_notification_email.delay(
                            admin_user.id,
                            f"Analytics Report - {report_type.title()}",
                            "accounts/emails/analytics_report.html",
                            {"report_data": report_data, "report_type": report_type},
                        )
                except Exception as e:
                    logger.error(
                        f"Error sending analytics report to {admin_email}: {str(e)}"
                    )

        logger.info(f"Generated {report_type} analytics report for {days} days")
        return {"status": "success", "report_type": report_type, "days": days}

    except Exception as e:
        logger.error(f"Error generating analytics report: {str(e)}")
        return {"status": "error", "message": str(e)}


@shared_task
def send_welcome_email(user_id: int, temporary_password: str = None):
    """
    Send welcome email to a new user.

    Args:
        user_id: ID of the user
        temporary_password: Temporary password if applicable
    """
    try:
        user = User.objects.get(id=user_id)

        context = {
            "temporary_password": temporary_password,
            "login_url": getattr(settings, "LOGIN_URL", "/accounts/login/"),
        }

        success = send_notification_email(
            user,
            "Welcome to the School Management System",
            "accounts/emails/welcome_email.html",
            context,
        )

        if success:
            UserAuditLog.objects.create(
                user=user,
                action="email_send",
                description="Welcome email sent",
                extra_data={"email_type": "welcome"},
            )

        return {"status": "success", "user_id": user_id}

    except User.DoesNotExist:
        logger.error(f"User with ID {user_id} not found")
        return {"status": "error", "message": "User not found"}
    except Exception as e:
        logger.error(f"Error sending welcome email: {str(e)}")
        return {"status": "error", "message": str(e)}


@shared_task
def send_verification_email(user_id: int, verification_type: str = "email"):
    """
    Send verification email or SMS to user.

    Args:
        user_id: ID of the user
        verification_type: Type of verification (email, phone)
    """
    try:
        user = User.objects.get(id=user_id)

        if verification_type == "email":
            # Generate and send email verification
            otp = AuthenticationService.send_otp(user, "email_verification")

            context = {"verification_code": otp, "user": user}

            success = send_notification_email(
                user,
                "Verify Your Email Address",
                "accounts/emails/email_verification.html",
                context,
            )

        elif verification_type == "phone":
            # Generate and send phone verification
            otp = AuthenticationService.send_otp(user, "phone_verification")

            # Here you would integrate with SMS service
            # For now, we'll just send an email with the SMS code
            context = {"verification_code": otp, "user": user}

            success = send_notification_email(
                user,
                "Verify Your Phone Number",
                "accounts/emails/phone_verification.html",
                context,
            )
        else:
            raise ValueError(f"Invalid verification type: {verification_type}")

        if success:
            UserAuditLog.objects.create(
                user=user,
                action="verification_send",
                description=f"{verification_type} verification sent",
                extra_data={"verification_type": verification_type},
            )

        return {"status": "success", "user_id": user_id, "type": verification_type}

    except User.DoesNotExist:
        logger.error(f"User with ID {user_id} not found")
        return {"status": "error", "message": "User not found"}
    except Exception as e:
        logger.error(f"Error sending verification: {str(e)}")
        return {"status": "error", "message": str(e)}


@shared_task
def cleanup_unverified_accounts(days: int = 7):
    """
    Cleanup accounts that haven't been verified within the specified days.

    Args:
        days: Number of days after which to cleanup unverified accounts
    """
    try:
        cutoff_date = timezone.now() - timedelta(days=days)

        # Find unverified accounts older than cutoff date
        unverified_accounts = User.objects.filter(
            date_joined__lt=cutoff_date, email_verified=False, is_active=True
        )

        deactivated_count = 0
        for user in unverified_accounts:
            # Deactivate instead of deleting
            user.is_active = False
            user.save()

            UserAuditLog.objects.create(
                user=user,
                action="account_deactivate",
                description="Account deactivated due to unverified email",
                severity="medium",
                extra_data={
                    "reason": "email_unverified",
                    "days_since_registration": days,
                },
            )

            deactivated_count += 1

        logger.info(f"Deactivated {deactivated_count} unverified accounts")
        return {"status": "success", "deactivated_count": deactivated_count}

    except Exception as e:
        logger.error(f"Error cleaning up unverified accounts: {str(e)}")
        return {"status": "error", "message": str(e)}


@shared_task
def update_user_activity_scores():
    """
    Update user activity scores based on recent login patterns.
    """
    try:
        # Calculate activity scores for all users
        updated_count = 0

        for user in User.objects.filter(is_active=True):
            try:
                # Get login statistics for the last 30 days
                stats = AuthenticationService.get_login_statistics(user, days=30)

                # Calculate activity score (0-100)
                activity_score = min(
                    100,
                    max(
                        0,
                        (stats["successful_logins"] * 10)  # 10 points per login
                        + (stats["success_rate"])  # Success rate percentage
                        + (
                            20
                            if user.last_login
                            and (timezone.now() - user.last_login).days <= 7
                            else 0
                        ),  # 20 points for recent login
                    ),
                )

                # Store in user profile or custom field
                # For now, we'll store in extra_data of audit log
                UserAuditLog.objects.create(
                    user=user,
                    action="activity_score_update",
                    description=f"Activity score updated to {activity_score}",
                    extra_data={"activity_score": activity_score, "login_stats": stats},
                )

                updated_count += 1

            except Exception as e:
                logger.error(
                    f"Error updating activity score for user {user.username}: {str(e)}"
                )

        logger.info(f"Updated activity scores for {updated_count} users")
        return {"status": "success", "updated_count": updated_count}

    except Exception as e:
        logger.error(f"Error updating user activity scores: {str(e)}")
        return {"status": "error", "message": str(e)}
