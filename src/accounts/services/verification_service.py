# src/accounts/services/verification_service.py

import logging
import re
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Tuple
from django.db.models import Q
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.utils import timezone

from ..models import UserAuditLog
from ..services.notification_service import NotificationService
from ..utils import generate_otp, validate_phone_number

logger = logging.getLogger(__name__)
User = get_user_model()


class VerificationService:
    """Service for handling email and phone verification processes."""

    # Configuration
    OTP_LENGTH = getattr(settings, "VERIFICATION_OTP_LENGTH", 6)
    OTP_EXPIRY_MINUTES = getattr(settings, "VERIFICATION_OTP_EXPIRY_MINUTES", 10)
    MAX_ATTEMPTS = getattr(settings, "VERIFICATION_MAX_ATTEMPTS", 5)
    COOLDOWN_MINUTES = getattr(settings, "VERIFICATION_COOLDOWN_MINUTES", 5)

    @staticmethod
    def send_email_verification(
        user: User, force_resend: bool = False
    ) -> Dict[str, Any]:
        """
        Send email verification code to user.

        Args:
            user: User to send verification to
            force_resend: Whether to bypass cooldown period

        Returns:
            Dictionary with operation result
        """
        try:
            # Check if already verified
            if user.email_verified:
                return {
                    "success": False,
                    "error": "Email is already verified",
                    "code": "ALREADY_VERIFIED",
                }

            # Check cooldown period
            if not force_resend:
                cooldown_key = f"email_verification_cooldown_{user.id}"
                if cache.get(cooldown_key):
                    remaining = cache.ttl(cooldown_key)
                    return {
                        "success": False,
                        "error": f"Please wait {remaining} seconds before requesting again",
                        "code": "COOLDOWN_ACTIVE",
                        "remaining_seconds": remaining,
                    }

            # Check daily limit
            daily_key = f"email_verification_daily_{user.id}_{timezone.now().date()}"
            daily_count = cache.get(daily_key, 0)

            if daily_count >= 10:  # Max 10 attempts per day
                return {
                    "success": False,
                    "error": "Daily verification limit exceeded",
                    "code": "DAILY_LIMIT_EXCEEDED",
                }

            # Generate OTP
            otp = generate_otp(VerificationService.OTP_LENGTH)

            # Store OTP in cache
            otp_key = f"email_otp_{user.id}"
            cache.set(
                otp_key,
                {"code": otp, "created_at": timezone.now().isoformat(), "attempts": 0},
                timeout=VerificationService.OTP_EXPIRY_MINUTES * 60,
            )

            # Send notification
            context = {
                "verification_code": otp,
                "expiry_minutes": VerificationService.OTP_EXPIRY_MINUTES,
                "user": user,
            }

            success = NotificationService.send_email_notification(
                user, "email_verification", context, priority="high"
            )

            if success:
                # Set cooldown
                cache.set(
                    cooldown_key,
                    True,
                    timeout=VerificationService.COOLDOWN_MINUTES * 60,
                )

                # Increment daily counter
                cache.set(daily_key, daily_count + 1, timeout=24 * 3600)

                # Log verification send
                UserAuditLog.objects.create(
                    user=user,
                    action="email_verification_send",
                    description="Email verification code sent",
                    extra_data={"email": user.email, "otp_length": len(otp)},
                )

                return {
                    "success": True,
                    "message": f"Verification code sent to {user.email}",
                    "expiry_minutes": VerificationService.OTP_EXPIRY_MINUTES,
                }
            else:
                return {
                    "success": False,
                    "error": "Failed to send verification email",
                    "code": "SEND_FAILED",
                }

        except Exception as e:
            logger.error(f"Email verification send error for user {user.username}: {e}")
            return {
                "success": False,
                "error": "Internal error occurred",
                "code": "INTERNAL_ERROR",
            }

    @staticmethod
    def verify_email(user: User, otp: str) -> Dict[str, Any]:
        """
        Verify email using OTP.

        Args:
            user: User attempting verification
            otp: OTP code provided by user

        Returns:
            Dictionary with verification result
        """
        try:
            otp_key = f"email_otp_{user.id}"
            otp_data = cache.get(otp_key)

            if not otp_data:
                return {
                    "success": False,
                    "error": "Verification code expired or not found",
                    "code": "CODE_EXPIRED",
                }

            # Check attempt limit
            if otp_data["attempts"] >= VerificationService.MAX_ATTEMPTS:
                cache.delete(otp_key)
                return {
                    "success": False,
                    "error": "Too many verification attempts",
                    "code": "TOO_MANY_ATTEMPTS",
                }

            # Verify OTP
            if otp_data["code"] != otp:
                # Increment attempts
                otp_data["attempts"] += 1
                cache.set(otp_key, otp_data, timeout=cache.ttl(otp_key))

                # Log failed attempt
                UserAuditLog.objects.create(
                    user=user,
                    action="email_verification_failed",
                    description=f'Email verification failed (attempt {otp_data["attempts"]})',
                    severity="low",
                    extra_data={
                        "attempts": otp_data["attempts"],
                        "max_attempts": VerificationService.MAX_ATTEMPTS,
                    },
                )

                return {
                    "success": False,
                    "error": "Invalid verification code",
                    "code": "INVALID_CODE",
                    "attempts_remaining": VerificationService.MAX_ATTEMPTS
                    - otp_data["attempts"],
                }

            # Successful verification
            user.email_verified = True
            user.save(update_fields=["email_verified"])

            # Clear OTP
            cache.delete(otp_key)

            # Log successful verification
            UserAuditLog.objects.create(
                user=user,
                action="email_verified",
                description="Email address verified successfully",
                extra_data={
                    "email": user.email,
                    "verification_time": timezone.now().isoformat(),
                },
            )

            # Send confirmation notification
            NotificationService.send_email_notification(
                user, "email_verified", {"user": user}
            )

            return {"success": True, "message": "Email verified successfully"}

        except Exception as e:
            logger.error(f"Email verification error for user {user.username}: {e}")
            return {
                "success": False,
                "error": "Internal error occurred",
                "code": "INTERNAL_ERROR",
            }

    @staticmethod
    def send_phone_verification(
        user: User, force_resend: bool = False
    ) -> Dict[str, Any]:
        """
        Send phone verification code to user.

        Args:
            user: User to send verification to
            force_resend: Whether to bypass cooldown period

        Returns:
            Dictionary with operation result
        """
        try:
            # Check if phone number exists
            if not user.phone_number:
                return {
                    "success": False,
                    "error": "No phone number registered",
                    "code": "NO_PHONE_NUMBER",
                }

            # Validate phone number format
            validation = validate_phone_number(user.phone_number)
            if not validation["is_valid"]:
                return {
                    "success": False,
                    "error": f'Invalid phone number: {validation["error"]}',
                    "code": "INVALID_PHONE_NUMBER",
                }

            # Check if already verified
            if user.phone_verified:
                return {
                    "success": False,
                    "error": "Phone number is already verified",
                    "code": "ALREADY_VERIFIED",
                }

            # Check cooldown period
            if not force_resend:
                cooldown_key = f"phone_verification_cooldown_{user.id}"
                if cache.get(cooldown_key):
                    remaining = cache.ttl(cooldown_key)
                    return {
                        "success": False,
                        "error": f"Please wait {remaining} seconds before requesting again",
                        "code": "COOLDOWN_ACTIVE",
                        "remaining_seconds": remaining,
                    }

            # Check daily limit
            daily_key = f"phone_verification_daily_{user.id}_{timezone.now().date()}"
            daily_count = cache.get(daily_key, 0)

            if daily_count >= 5:  # Max 5 SMS per day (lower than email due to cost)
                return {
                    "success": False,
                    "error": "Daily SMS verification limit exceeded",
                    "code": "DAILY_LIMIT_EXCEEDED",
                }

            # Generate OTP
            otp = generate_otp(VerificationService.OTP_LENGTH)

            # Store OTP in cache
            otp_key = f"phone_otp_{user.id}"
            cache.set(
                otp_key,
                {
                    "code": otp,
                    "created_at": timezone.now().isoformat(),
                    "attempts": 0,
                    "phone_number": user.phone_number,
                },
                timeout=VerificationService.OTP_EXPIRY_MINUTES * 60,
            )

            # Send SMS
            sms_message = f"Your verification code is: {otp}. Valid for {VerificationService.OTP_EXPIRY_MINUTES} minutes."

            sms_success = NotificationService.send_sms_notification(
                user, sms_message, priority="high"
            )

            # Also send via email as backup
            email_context = {
                "verification_code": otp,
                "phone_number": user.phone_number,
                "expiry_minutes": VerificationService.OTP_EXPIRY_MINUTES,
            }

            email_success = NotificationService.send_email_notification(
                user, "phone_verification", email_context
            )

            if sms_success or email_success:
                # Set cooldown
                cache.set(
                    cooldown_key,
                    True,
                    timeout=VerificationService.COOLDOWN_MINUTES * 60,
                )

                # Increment daily counter
                cache.set(daily_key, daily_count + 1, timeout=24 * 3600)

                # Log verification send
                UserAuditLog.objects.create(
                    user=user,
                    action="phone_verification_send",
                    description="Phone verification code sent",
                    extra_data={
                        "phone_number": user.phone_number,
                        "sms_success": sms_success,
                        "email_backup": email_success,
                    },
                )

                delivery_method = "SMS" if sms_success else "Email (as backup)"
                return {
                    "success": True,
                    "message": f"Verification code sent via {delivery_method}",
                    "expiry_minutes": VerificationService.OTP_EXPIRY_MINUTES,
                    "delivery_method": delivery_method.lower(),
                }
            else:
                return {
                    "success": False,
                    "error": "Failed to send verification code",
                    "code": "SEND_FAILED",
                }

        except Exception as e:
            logger.error(f"Phone verification send error for user {user.username}: {e}")
            return {
                "success": False,
                "error": "Internal error occurred",
                "code": "INTERNAL_ERROR",
            }

    @staticmethod
    def verify_phone(user: User, otp: str) -> Dict[str, Any]:
        """
        Verify phone number using OTP.

        Args:
            user: User attempting verification
            otp: OTP code provided by user

        Returns:
            Dictionary with verification result
        """
        try:
            otp_key = f"phone_otp_{user.id}"
            otp_data = cache.get(otp_key)

            if not otp_data:
                return {
                    "success": False,
                    "error": "Verification code expired or not found",
                    "code": "CODE_EXPIRED",
                }

            # Check if phone number changed
            if otp_data.get("phone_number") != user.phone_number:
                cache.delete(otp_key)
                return {
                    "success": False,
                    "error": "Phone number was changed after verification was sent",
                    "code": "PHONE_NUMBER_CHANGED",
                }

            # Check attempt limit
            if otp_data["attempts"] >= VerificationService.MAX_ATTEMPTS:
                cache.delete(otp_key)
                return {
                    "success": False,
                    "error": "Too many verification attempts",
                    "code": "TOO_MANY_ATTEMPTS",
                }

            # Verify OTP
            if otp_data["code"] != otp:
                # Increment attempts
                otp_data["attempts"] += 1
                cache.set(otp_key, otp_data, timeout=cache.ttl(otp_key))

                # Log failed attempt
                UserAuditLog.objects.create(
                    user=user,
                    action="phone_verification_failed",
                    description=f'Phone verification failed (attempt {otp_data["attempts"]})',
                    severity="low",
                    extra_data={
                        "attempts": otp_data["attempts"],
                        "max_attempts": VerificationService.MAX_ATTEMPTS,
                        "phone_number": user.phone_number,
                    },
                )

                return {
                    "success": False,
                    "error": "Invalid verification code",
                    "code": "INVALID_CODE",
                    "attempts_remaining": VerificationService.MAX_ATTEMPTS
                    - otp_data["attempts"],
                }

            # Successful verification
            user.phone_verified = True
            user.save(update_fields=["phone_verified"])

            # Clear OTP
            cache.delete(otp_key)

            # Log successful verification
            UserAuditLog.objects.create(
                user=user,
                action="phone_verified",
                description="Phone number verified successfully",
                extra_data={
                    "phone_number": user.phone_number,
                    "verification_time": timezone.now().isoformat(),
                },
            )

            # Send confirmation SMS
            confirmation_message = "Your phone number has been verified successfully."
            NotificationService.send_sms_notification(user, confirmation_message)

            return {"success": True, "message": "Phone number verified successfully"}

        except Exception as e:
            logger.error(f"Phone verification error for user {user.username}: {e}")
            return {
                "success": False,
                "error": "Internal error occurred",
                "code": "INTERNAL_ERROR",
            }

    @staticmethod
    def get_verification_status(user: User) -> Dict[str, Any]:
        """
        Get verification status for user.

        Args:
            user: User to check status for

        Returns:
            Dictionary with verification status
        """
        return {
            "email": {
                "address": user.email,
                "verified": user.email_verified,
                "pending_verification": bool(cache.get(f"email_otp_{user.id}")),
                "can_resend": not bool(
                    cache.get(f"email_verification_cooldown_{user.id}")
                ),
            },
            "phone": {
                "number": user.phone_number,
                "verified": user.phone_verified,
                "pending_verification": bool(cache.get(f"phone_otp_{user.id}")),
                "can_resend": not bool(
                    cache.get(f"phone_verification_cooldown_{user.id}")
                ),
            },
            "overall_completion": {
                "percentage": (
                    (50 if user.email_verified else 0)
                    + (50 if user.phone_verified else 0)
                ),
                "required_verifications": ["email"],
                "optional_verifications": ["phone"],
            },
        }

    @staticmethod
    def resend_verification(user: User, verification_type: str) -> Dict[str, Any]:
        """
        Resend verification code.

        Args:
            user: User requesting resend
            verification_type: 'email' or 'phone'

        Returns:
            Dictionary with operation result
        """
        if verification_type == "email":
            return VerificationService.send_email_verification(user, force_resend=False)
        elif verification_type == "phone":
            return VerificationService.send_phone_verification(user, force_resend=False)
        else:
            return {
                "success": False,
                "error": "Invalid verification type",
                "code": "INVALID_TYPE",
            }

    @staticmethod
    def cancel_verification(user: User, verification_type: str) -> Dict[str, Any]:
        """
        Cancel pending verification.

        Args:
            user: User canceling verification
            verification_type: 'email' or 'phone'

        Returns:
            Dictionary with operation result
        """
        try:
            if verification_type == "email":
                otp_key = f"email_otp_{user.id}"
                cooldown_key = f"email_verification_cooldown_{user.id}"
            elif verification_type == "phone":
                otp_key = f"phone_otp_{user.id}"
                cooldown_key = f"phone_verification_cooldown_{user.id}"
            else:
                return {
                    "success": False,
                    "error": "Invalid verification type",
                    "code": "INVALID_TYPE",
                }

            # Clear OTP and cooldown
            cache.delete(otp_key)
            cache.delete(cooldown_key)

            # Log cancellation
            UserAuditLog.objects.create(
                user=user,
                action=f"{verification_type}_verification_cancelled",
                description=f"{verification_type.title()} verification cancelled by user",
            )

            return {
                "success": True,
                "message": f"{verification_type.title()} verification cancelled",
            }

        except Exception as e:
            logger.error(f"Verification cancellation error: {e}")
            return {
                "success": False,
                "error": "Internal error occurred",
                "code": "INTERNAL_ERROR",
            }

    @staticmethod
    def cleanup_expired_verifications():
        """
        Clean up expired verification attempts.
        This would be called by a periodic task.
        """
        try:
            # Get all users with pending verifications
            email_keys = cache.keys("email_otp_*")
            phone_keys = cache.keys("phone_otp_*")

            cleaned_count = 0

            # Clean expired email verifications
            for key in email_keys:
                if not cache.get(key):  # Already expired
                    cleaned_count += 1

            # Clean expired phone verifications
            for key in phone_keys:
                if not cache.get(key):  # Already expired
                    cleaned_count += 1

            logger.info(f"Cleaned up {cleaned_count} expired verification attempts")

        except Exception as e:
            logger.error(f"Verification cleanup error: {e}")

    @staticmethod
    def get_verification_statistics(days: int = 30) -> Dict[str, Any]:
        """
        Get verification statistics.

        Args:
            days: Number of days to analyze

        Returns:
            Dictionary with verification statistics
        """
        start_date = timezone.now() - timedelta(days=days)

        # Email verification stats
        email_sent = UserAuditLog.objects.filter(
            action="email_verification_send", timestamp__gte=start_date
        ).count()

        email_verified = UserAuditLog.objects.filter(
            action="email_verified", timestamp__gte=start_date
        ).count()

        email_failed = UserAuditLog.objects.filter(
            action="email_verification_failed", timestamp__gte=start_date
        ).count()

        # Phone verification stats
        phone_sent = UserAuditLog.objects.filter(
            action="phone_verification_send", timestamp__gte=start_date
        ).count()

        phone_verified = UserAuditLog.objects.filter(
            action="phone_verified", timestamp__gte=start_date
        ).count()

        phone_failed = UserAuditLog.objects.filter(
            action="phone_verification_failed", timestamp__gte=start_date
        ).count()

        # Overall verification rates
        total_users = User.objects.count()
        email_verified_users = User.objects.filter(email_verified=True).count()
        phone_verified_users = User.objects.filter(phone_verified=True).count()

        return {
            "period_days": days,
            "email": {
                "codes_sent": email_sent,
                "successful_verifications": email_verified,
                "failed_attempts": email_failed,
                "success_rate": (
                    (email_verified / email_sent * 100) if email_sent > 0 else 0
                ),
                "total_verified_users": email_verified_users,
                "verification_percentage": (
                    (email_verified_users / total_users * 100) if total_users > 0 else 0
                ),
            },
            "phone": {
                "codes_sent": phone_sent,
                "successful_verifications": phone_verified,
                "failed_attempts": phone_failed,
                "success_rate": (
                    (phone_verified / phone_sent * 100) if phone_sent > 0 else 0
                ),
                "total_verified_users": phone_verified_users,
                "verification_percentage": (
                    (phone_verified_users / total_users * 100) if total_users > 0 else 0
                ),
            },
            "overall": {
                "total_users": total_users,
                "fully_verified_users": User.objects.filter(
                    email_verified=True, phone_verified=True
                ).count(),
                "partially_verified_users": User.objects.filter(
                    Q(email_verified=True) | Q(phone_verified=True)
                )
                .exclude(email_verified=True, phone_verified=True)
                .count(),
                "unverified_users": User.objects.filter(
                    email_verified=False, phone_verified=False
                ).count(),
            },
        }
