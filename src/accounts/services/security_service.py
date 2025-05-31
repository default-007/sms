# src/accounts/services/security_service.py

import hashlib
import hmac
import logging
import secrets
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db.models import Count, Q
from django.utils import timezone

from ..models import UserAuditLog, UserSession
from ..utils import get_client_info, generate_otp, validate_password_strength

logger = logging.getLogger(__name__)
User = get_user_model()


class SecurityService:
    """Comprehensive service for handling security-related operations."""

    # Security configuration
    MAX_LOGIN_ATTEMPTS = getattr(settings, "MAX_LOGIN_ATTEMPTS", 5)
    LOCKOUT_DURATION = getattr(settings, "LOCKOUT_DURATION_MINUTES", 30)
    SESSION_TIMEOUT = getattr(settings, "SESSION_TIMEOUT_MINUTES", 30)
    PASSWORD_EXPIRY_DAYS = getattr(settings, "PASSWORD_EXPIRY_DAYS", 90)
    SUSPICIOUS_ACTIVITY_THRESHOLD = getattr(
        settings, "SUSPICIOUS_ACTIVITY_THRESHOLD", 10
    )

    @staticmethod
    def analyze_login_attempt(
        identifier: str, success: bool, request=None
    ) -> Dict[str, Any]:
        """
        Analyze login attempt for security threats.

        Args:
            identifier: Login identifier (email/phone/username)
            success: Whether login was successful
            request: HTTP request object

        Returns:
            Dictionary with security analysis results
        """
        client_info = get_client_info(request) if request else {}
        ip_address = client_info.get("ip_address", "unknown")

        analysis = {
            "is_suspicious": False,
            "risk_score": 0,
            "reasons": [],
            "actions_taken": [],
            "recommendations": [],
        }

        # Check for rapid login attempts from same IP
        one_hour_ago = timezone.now() - timedelta(hours=1)
        recent_attempts = UserAuditLog.objects.filter(
            action="login", ip_address=ip_address, timestamp__gte=one_hour_ago
        ).count()

        if recent_attempts > SecurityService.SUSPICIOUS_ACTIVITY_THRESHOLD:
            analysis["is_suspicious"] = True
            analysis["risk_score"] += 30
            analysis["reasons"].append(
                f"High login attempt rate from IP: {recent_attempts} attempts"
            )

        # Check for failed attempts from same IP
        failed_attempts = UserAuditLog.objects.filter(
            action="login",
            description__contains="Failed",
            ip_address=ip_address,
            timestamp__gte=one_hour_ago,
        ).count()

        if failed_attempts > 5:
            analysis["is_suspicious"] = True
            analysis["risk_score"] += 25
            analysis["reasons"].append(
                f"High failure rate from IP: {failed_attempts} failed attempts"
            )

        # Check for login from new location
        if success:
            user = User.objects.filter(
                Q(email=identifier)
                | Q(username=identifier)
                | Q(phone_number__icontains=identifier)
            ).first()

            if user:
                # Check historical IPs
                historical_ips = (
                    UserAuditLog.objects.filter(
                        user=user,
                        action="login",
                        description__contains="Successful",
                        timestamp__lt=timezone.now() - timedelta(days=1),
                    )
                    .values_list("ip_address", flat=True)
                    .distinct()
                )

                if ip_address not in historical_ips and len(historical_ips) > 0:
                    analysis["risk_score"] += 15
                    analysis["reasons"].append("Login from new location")
                    analysis["recommendations"].append(
                        "Verify login location with user"
                    )

        # Check for unusual timing
        current_hour = timezone.now().hour
        if current_hour < 6 or current_hour > 22:  # Outside normal hours
            analysis["risk_score"] += 5
            analysis["reasons"].append("Login attempt outside normal hours")

        # Determine overall suspicion level
        if analysis["risk_score"] >= 50:
            analysis["is_suspicious"] = True
            analysis["actions_taken"].append("Flagged for security review")

        return analysis

    @staticmethod
    def check_account_security(user: User) -> Dict[str, Any]:
        """
        Comprehensive security check for user account.

        Args:
            user: User to analyze

        Returns:
            Dictionary with security assessment
        """
        security_check = {
            "overall_score": 0,
            "risk_level": "low",
            "issues": [],
            "recommendations": [],
            "last_assessment": timezone.now(),
        }

        # Password security
        password_age = (
            (timezone.now() - user.password_changed_at).days
            if user.password_changed_at
            else 999
        )
        if password_age > SecurityService.PASSWORD_EXPIRY_DAYS:
            security_check["issues"].append("Password is expired")
            security_check["recommendations"].append("Force password change")
        elif password_age > (SecurityService.PASSWORD_EXPIRY_DAYS * 0.8):
            security_check["issues"].append("Password expires soon")
            security_check["recommendations"].append("Remind user to change password")
        else:
            security_check["overall_score"] += 20

        # Account verification
        if user.email_verified:
            security_check["overall_score"] += 20
        else:
            security_check["issues"].append("Email not verified")
            security_check["recommendations"].append("Send email verification")

        if user.phone_verified:
            security_check["overall_score"] += 15
        else:
            security_check["issues"].append("Phone not verified")
            security_check["recommendations"].append("Send phone verification")

        # Two-factor authentication
        if user.two_factor_enabled:
            security_check["overall_score"] += 25
        else:
            security_check["issues"].append("Two-factor authentication disabled")
            security_check["recommendations"].append("Enable 2FA")

        # Recent login activity
        recent_logins = UserAuditLog.objects.filter(
            user=user,
            action="login",
            description__contains="Successful",
            timestamp__gte=timezone.now() - timedelta(days=30),
        ).count()

        if recent_logins > 0:
            security_check["overall_score"] += 10

        # Failed login attempts
        if user.failed_login_attempts == 0:
            security_check["overall_score"] += 10
        elif user.failed_login_attempts >= SecurityService.MAX_LOGIN_ATTEMPTS:
            security_check["issues"].append("Account is locked")
            security_check["recommendations"].append(
                "Investigate and unlock if legitimate"
            )

        # Determine risk level
        if security_check["overall_score"] >= 80:
            security_check["risk_level"] = "low"
        elif security_check["overall_score"] >= 60:
            security_check["risk_level"] = "medium"
        elif security_check["overall_score"] >= 40:
            security_check["risk_level"] = "high"
        else:
            security_check["risk_level"] = "critical"

        return security_check

    @staticmethod
    def detect_session_anomalies(user: User) -> List[Dict[str, Any]]:
        """
        Detect anomalies in user sessions.

        Args:
            user: User to analyze

        Returns:
            List of detected anomalies
        """
        anomalies = []

        # Get recent sessions
        recent_sessions = UserSession.objects.filter(
            user=user, created_at__gte=timezone.now() - timedelta(days=7)
        ).order_by("-created_at")

        if not recent_sessions.exists():
            return anomalies

        # Check for concurrent sessions from different locations
        active_sessions = recent_sessions.filter(is_active=True)
        unique_ips = active_sessions.values_list("ip_address", flat=True).distinct()

        if len(unique_ips) > 3:  # More than 3 different IPs
            anomalies.append(
                {
                    "type": "multiple_locations",
                    "severity": "medium",
                    "description": f"Active sessions from {len(unique_ips)} different IP addresses",
                    "details": {
                        "ip_addresses": list(unique_ips),
                        "session_count": active_sessions.count(),
                    },
                }
            )

        # Check for rapid session creation
        session_times = list(recent_sessions.values_list("created_at", flat=True)[:10])
        if len(session_times) >= 5:
            time_diffs = []
            for i in range(1, len(session_times)):
                diff = (session_times[i - 1] - session_times[i]).total_seconds()
                time_diffs.append(diff)

            avg_diff = sum(time_diffs) / len(time_diffs)
            if avg_diff < 60:  # Less than 1 minute between sessions
                anomalies.append(
                    {
                        "type": "rapid_sessions",
                        "severity": "high",
                        "description": "Unusually rapid session creation",
                        "details": {
                            "average_interval": avg_diff,
                            "recent_sessions": len(session_times),
                        },
                    }
                )

        # Check for unusual session duration
        for session in active_sessions:
            duration = (
                timezone.now() - session.created_at
            ).total_seconds() / 3600  # hours
            if duration > 24:  # Session longer than 24 hours
                anomalies.append(
                    {
                        "type": "long_session",
                        "severity": "low",
                        "description": f"Session active for {duration:.1f} hours",
                        "details": {
                            "session_id": session.id,
                            "duration_hours": duration,
                            "ip_address": session.ip_address,
                        },
                    }
                )

        return anomalies

    @staticmethod
    def generate_security_token(
        user: User, purpose: str, expiry_minutes: int = 15
    ) -> str:
        """
        Generate secure token for various purposes (password reset, email verification, etc.).

        Args:
            user: User for whom token is generated
            purpose: Purpose of the token
            expiry_minutes: Token expiry time in minutes

        Returns:
            Generated token
        """
        # Create token payload
        timestamp = int(time.time())
        expiry = timestamp + (expiry_minutes * 60)

        payload = f"{user.id}:{purpose}:{expiry}:{timestamp}"

        # Generate HMAC signature
        secret_key = getattr(settings, "SECRET_KEY", "default-secret")
        signature = hmac.new(
            secret_key.encode(), payload.encode(), hashlib.sha256
        ).hexdigest()

        token = f"{payload}:{signature}"

        # Store token in cache for validation
        cache_key = f"security_token_{hashlib.sha256(token.encode()).hexdigest()}"
        cache.set(
            cache_key,
            {"user_id": user.id, "purpose": purpose, "created_at": timestamp},
            timeout=expiry_minutes * 60,
        )

        return token

    @staticmethod
    def validate_security_token(
        token: str, purpose: str, user: User = None
    ) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Validate security token.

        Args:
            token: Token to validate
            purpose: Expected purpose
            user: Optional user to validate against

        Returns:
            Tuple of (is_valid, token_data)
        """
        try:
            # Parse token
            parts = token.split(":")
            if len(parts) != 5:
                return False, None

            user_id, token_purpose, expiry, timestamp, signature = parts

            # Verify purpose
            if token_purpose != purpose:
                return False, None

            # Verify user if provided
            if user and str(user.id) != user_id:
                return False, None

            # Check expiry
            if int(expiry) < int(time.time()):
                return False, None

            # Verify signature
            payload = f"{user_id}:{token_purpose}:{expiry}:{timestamp}"
            secret_key = getattr(settings, "SECRET_KEY", "default-secret")
            expected_signature = hmac.new(
                secret_key.encode(), payload.encode(), hashlib.sha256
            ).hexdigest()

            if not hmac.compare_digest(signature, expected_signature):
                return False, None

            # Check cache
            cache_key = f"security_token_{hashlib.sha256(token.encode()).hexdigest()}"
            token_data = cache.get(cache_key)

            if not token_data:
                return False, None

            # Remove from cache (single use)
            cache.delete(cache_key)

            return True, {
                "user_id": int(user_id),
                "purpose": token_purpose,
                "created_at": int(timestamp),
                "expiry": int(expiry),
            }

        except Exception as e:
            logger.error(f"Token validation error: {e}")
            return False, None

    @staticmethod
    def enable_two_factor_auth(user: User) -> Dict[str, Any]:
        """
        Enable two-factor authentication for user.

        Args:
            user: User to enable 2FA for

        Returns:
            Dictionary with 2FA setup information
        """
        try:
            import pyotp
            import qrcode
            from io import BytesIO
            import base64

            # Generate secret
            secret = pyotp.random_base32()

            # Create TOTP instance
            totp = pyotp.TOTP(secret)

            # Generate QR code
            site_name = getattr(settings, "SITE_NAME", "School Management System")
            provisioning_uri = totp.provisioning_uri(
                name=user.email, issuer_name=site_name
            )

            # Generate QR code image
            qr = qrcode.QRCode(version=1, box_size=10, border=5)
            qr.add_data(provisioning_uri)
            qr.make(fit=True)

            img = qr.make_image(fill_color="black", back_color="white")
            buffer = BytesIO()
            img.save(buffer, format="PNG")
            qr_code_data = base64.b64encode(buffer.getvalue()).decode()

            # Generate backup codes
            backup_codes = []
            for _ in range(10):
                code = secrets.token_hex(4).upper()
                backup_codes.append(f"{code[:4]}-{code[4:]}")

            # Store temporarily in cache (to be saved after verification)
            cache_key = f"2fa_setup_{user.id}"
            cache.set(
                cache_key, {"secret": secret, "backup_codes": backup_codes}, timeout=600
            )  # 10 minutes

            return {
                "success": True,
                "secret": secret,
                "qr_code": qr_code_data,
                "backup_codes": backup_codes,
                "provisioning_uri": provisioning_uri,
            }

        except ImportError:
            return {"success": False, "error": "2FA libraries not available"}
        except Exception as e:
            logger.error(f"2FA setup error: {e}")
            return {"success": False, "error": str(e)}

    @staticmethod
    def verify_two_factor_code(
        user: User, code: str, backup_code: bool = False
    ) -> bool:
        """
        Verify two-factor authentication code.

        Args:
            user: User to verify
            code: TOTP code or backup code
            backup_code: Whether this is a backup code

        Returns:
            True if code is valid
        """
        try:
            if backup_code:
                # Verify backup code
                if not user.backup_codes:
                    return False

                # Normalize code
                normalized_code = code.upper().replace("-", "").replace(" ", "")

                for stored_code in user.backup_codes:
                    normalized_stored = (
                        stored_code.upper().replace("-", "").replace(" ", "")
                    )
                    if normalized_code == normalized_stored:
                        # Remove used backup code
                        user.backup_codes.remove(stored_code)
                        user.save(update_fields=["backup_codes"])

                        # Log backup code usage
                        UserAuditLog.objects.create(
                            user=user,
                            action="2fa_backup_used",
                            description="Two-factor backup code used",
                            severity="medium",
                        )

                        return True

                return False

            else:
                # Verify TOTP code
                import pyotp

                # Get user's 2FA secret (this would be stored encrypted)
                secret = getattr(user, "two_factor_secret", None)
                if not secret:
                    return False

                totp = pyotp.TOTP(secret)
                is_valid = totp.verify(code, valid_window=1)  # Allow 30-second window

                if is_valid:
                    # Log successful 2FA
                    UserAuditLog.objects.create(
                        user=user,
                        action="2fa_verified",
                        description="Two-factor authentication successful",
                    )

                return is_valid

        except ImportError:
            logger.error("2FA libraries not available")
            return False
        except Exception as e:
            logger.error(f"2FA verification error: {e}")
            return False

    @staticmethod
    def disable_two_factor_auth(user: User, verification_code: str) -> bool:
        """
        Disable two-factor authentication for user.

        Args:
            user: User to disable 2FA for
            verification_code: Current TOTP code for verification

        Returns:
            True if successfully disabled
        """
        # Verify current code before disabling
        if not SecurityService.verify_two_factor_code(user, verification_code):
            return False

        try:
            user.two_factor_enabled = False
            user.backup_codes = []
            # user.two_factor_secret = None  # Would need to add this field
            user.save(update_fields=["two_factor_enabled", "backup_codes"])

            # Log 2FA disable
            UserAuditLog.objects.create(
                user=user,
                action="2fa_disabled",
                description="Two-factor authentication disabled",
                severity="medium",
            )

            return True

        except Exception as e:
            logger.error(f"Error disabling 2FA: {e}")
            return False

    @staticmethod
    def generate_audit_report(
        start_date: datetime, end_date: datetime, severity_levels: List[str] = None
    ) -> Dict[str, Any]:
        """
        Generate security audit report.

        Args:
            start_date: Report start date
            end_date: Report end date
            severity_levels: List of severity levels to include

        Returns:
            Comprehensive audit report
        """
        logs = UserAuditLog.objects.filter(
            timestamp__gte=start_date, timestamp__lte=end_date
        )

        if severity_levels:
            logs = logs.filter(severity__in=severity_levels)

        # Group by action type
        action_summary = (
            logs.values("action").annotate(count=Count("id")).order_by("-count")
        )

        # Group by severity
        severity_summary = (
            logs.values("severity").annotate(count=Count("id")).order_by("severity")
        )

        # Top users by activity
        user_activity = (
            logs.exclude(user__isnull=True)
            .values("user__username", "user__email")
            .annotate(count=Count("id"))
            .order_by("-count")[:10]
        )

        # Top IP addresses
        ip_activity = (
            logs.exclude(ip_address__isnull=True)
            .values("ip_address")
            .annotate(count=Count("id"))
            .order_by("-count")[:10]
        )

        # Failed login attempts by IP
        failed_logins = (
            logs.filter(action="login", description__contains="Failed")
            .values("ip_address")
            .annotate(count=Count("id"))
            .order_by("-count")[:10]
        )

        # Security events
        security_events = logs.filter(
            action__in=[
                "account_lock",
                "account_unlock",
                "password_change",
                "password_reset",
                "2fa_enabled",
                "2fa_disabled",
            ]
        ).count()

        report = {
            "period": {
                "start_date": start_date,
                "end_date": end_date,
                "days": (end_date - start_date).days,
            },
            "summary": {
                "total_events": logs.count(),
                "security_events": security_events,
                "unique_users": logs.exclude(user__isnull=True)
                .values("user")
                .distinct()
                .count(),
                "unique_ips": logs.exclude(ip_address__isnull=True)
                .values("ip_address")
                .distinct()
                .count(),
            },
            "action_breakdown": list(action_summary),
            "severity_breakdown": list(severity_summary),
            "top_user_activity": list(user_activity),
            "top_ip_activity": list(ip_activity),
            "failed_login_attempts": list(failed_logins),
            "generated_at": timezone.now(),
        }

        return report

    @staticmethod
    def cleanup_expired_tokens():
        """Clean up expired security tokens from cache."""
        # This would be called by a periodic task
        # Cache cleanup is handled automatically by expiry
        pass

    @staticmethod
    def get_security_recommendations(user: User) -> List[Dict[str, str]]:
        """
        Get personalized security recommendations for user.

        Args:
            user: User to get recommendations for

        Returns:
            List of security recommendations
        """
        recommendations = []

        security_check = SecurityService.check_account_security(user)

        for recommendation in security_check["recommendations"]:
            if "password" in recommendation.lower():
                recommendations.append(
                    {
                        "type": "password",
                        "priority": "high",
                        "title": "Update Password",
                        "description": recommendation,
                        "action_url": "/accounts/password-change/",
                    }
                )
            elif "2fa" in recommendation.lower():
                recommendations.append(
                    {
                        "type": "two_factor",
                        "priority": "medium",
                        "title": "Enable Two-Factor Authentication",
                        "description": recommendation,
                        "action_url": "/accounts/2fa/setup/",
                    }
                )
            elif "email" in recommendation.lower():
                recommendations.append(
                    {
                        "type": "verification",
                        "priority": "medium",
                        "title": "Verify Email Address",
                        "description": recommendation,
                        "action_url": "/accounts/verify-email/",
                    }
                )
            elif "phone" in recommendation.lower():
                recommendations.append(
                    {
                        "type": "verification",
                        "priority": "low",
                        "title": "Verify Phone Number",
                        "description": recommendation,
                        "action_url": "/accounts/verify-phone/",
                    }
                )

        return recommendations
