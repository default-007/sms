# src/accounts/session_utils.py

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.core.cache import cache
from django.db.models import Count, Q
from django.utils import timezone

from .models import UserAuditLog, UserSession
from .utils import get_client_info, parse_user_agent

logger = logging.getLogger(__name__)
User = get_user_model()


class SessionManager:
    """Comprehensive session management utilities."""

    # Configuration
    MAX_CONCURRENT_SESSIONS = getattr(settings, "MAX_CONCURRENT_SESSIONS", 5)
    SESSION_TIMEOUT_MINUTES = getattr(settings, "SESSION_TIMEOUT_MINUTES", 30)
    TRACK_SESSION_ACTIVITY = getattr(settings, "TRACK_SESSION_ACTIVITY", True)
    SESSION_SECURITY_CHECKS = getattr(settings, "SESSION_SECURITY_CHECKS", True)

    @staticmethod
    def create_session_record(user: User, request) -> UserSession:
        """
        Create or update session record for user.

        Args:
            user: User starting the session
            request: HTTP request object

        Returns:
            UserSession object
        """
        try:
            # Ensure session exists
            if not request.session.session_key:
                request.session.create()

            session_key = request.session.session_key
            client_info = get_client_info(request)

            # Parse user agent for device information
            ua_info = parse_user_agent(client_info.get("user_agent", ""))

            # Create or update session record
            session_obj, created = UserSession.objects.get_or_create(
                session_key=session_key,
                defaults={
                    "user": user,
                    "ip_address": client_info.get("ip_address", ""),
                    "user_agent": client_info.get("user_agent", ""),
                    "country": client_info.get("country", ""),
                    "city": client_info.get("city", ""),
                    "device_type": ua_info.get("device_type", "unknown"),
                    "browser": ua_info.get("browser", ""),
                    "os": ua_info.get("os", ""),
                    "is_active": True,
                },
            )

            if not created:
                # Update existing session
                session_obj.user = user
                session_obj.last_activity = timezone.now()
                session_obj.is_active = True
                session_obj.save(update_fields=["user", "last_activity", "is_active"])

            # Check concurrent session limits
            if SessionManager.MAX_CONCURRENT_SESSIONS:
                SessionManager._enforce_concurrent_session_limit(user, session_key)

            # Log session creation
            if created:
                UserAuditLog.objects.create(
                    user=user,
                    action="session_created",
                    description="New session created",
                    ip_address=client_info.get("ip_address"),
                    user_agent=client_info.get("user_agent"),
                    extra_data={
                        "session_key": session_key[:8]
                        + "...",  # Partial key for security
                        "device_type": ua_info.get("device_type"),
                        "browser": ua_info.get("browser"),
                        "location": f"{client_info.get('city', '')}, {client_info.get('country', '')}",
                    },
                )

            return session_obj

        except Exception as e:
            logger.error(f"Error creating session record: {e}")
            raise

    @staticmethod
    def update_session_activity(request) -> bool:
        """
        Update session activity timestamp.

        Args:
            request: HTTP request object

        Returns:
            True if updated successfully
        """
        try:
            if not SessionManager.TRACK_SESSION_ACTIVITY:
                return True

            if not hasattr(request, "session") or not request.session.session_key:
                return False

            session_key = request.session.session_key

            # Use cache to throttle database updates (update max once per minute)
            cache_key = f"session_activity_{session_key}"
            if cache.get(cache_key):
                return True

            # Update session activity
            updated = UserSession.objects.filter(
                session_key=session_key, is_active=True
            ).update(last_activity=timezone.now())

            if updated:
                # Set cache to prevent frequent updates
                cache.set(cache_key, True, timeout=60)  # 1 minute
                return True

            return False

        except Exception as e:
            logger.error(f"Error updating session activity: {e}")
            return False

    @staticmethod
    def terminate_session(session_key: str, reason: str = "user") -> bool:
        """
        Terminate a specific session.

        Args:
            session_key: Session key to terminate
            reason: Reason for termination

        Returns:
            True if terminated successfully
        """
        try:
            # Update session record
            session_obj = UserSession.objects.filter(
                session_key=session_key, is_active=True
            ).first()

            if session_obj:
                session_obj.is_active = False
                session_obj.logout_reason = reason
                session_obj.save(update_fields=["is_active", "logout_reason"])

                # Log session termination
                UserAuditLog.objects.create(
                    user=session_obj.user,
                    action="session_terminated",
                    description=f"Session terminated: {reason}",
                    extra_data={
                        "session_key": session_key[:8] + "...",
                        "reason": reason,
                        "duration_minutes": SessionManager.get_session_duration(
                            session_obj
                        ),
                    },
                )

            # Delete Django session
            try:
                Session.objects.filter(session_key=session_key).delete()
            except:
                pass  # Session might already be expired

            # Clear related cache
            cache.delete(f"session_activity_{session_key}")

            return True

        except Exception as e:
            logger.error(f"Error terminating session {session_key}: {e}")
            return False

    @staticmethod
    def terminate_user_sessions(
        user: User, exclude_session: Optional[str] = None, reason: str = "admin"
    ) -> int:
        """
        Terminate all sessions for a user.

        Args:
            user: User whose sessions to terminate
            exclude_session: Session key to exclude from termination
            reason: Reason for termination

        Returns:
            Number of sessions terminated
        """
        try:
            # Get active sessions
            sessions = UserSession.objects.filter(user=user, is_active=True)

            if exclude_session:
                sessions = sessions.exclude(session_key=exclude_session)

            terminated_count = 0

            for session in sessions:
                if SessionManager.terminate_session(session.session_key, reason):
                    terminated_count += 1

            logger.info(
                f"Terminated {terminated_count} sessions for user {user.username}"
            )
            return terminated_count

        except Exception as e:
            logger.error(f"Error terminating sessions for user {user.username}: {e}")
            return 0

    @staticmethod
    def get_active_sessions(user: User) -> List[Dict[str, Any]]:
        """
        Get active sessions for a user.

        Args:
            user: User to get sessions for

        Returns:
            List of session information dictionaries
        """
        try:
            sessions = UserSession.objects.filter(user=user, is_active=True).order_by(
                "-last_activity"
            )

            session_list = []

            for session in sessions:
                session_info = {
                    "session_key": session.session_key[:8]
                    + "...",  # Partial for security
                    "ip_address": session.ip_address,
                    "location": (
                        f"{session.city}, {session.country}"
                        if session.city
                        else session.country
                    ),
                    "device_type": session.device_type,
                    "browser": session.browser,
                    "os": session.os,
                    "created_at": session.created_at,
                    "last_activity": session.last_activity,
                    "duration_minutes": SessionManager.get_session_duration(session),
                    "is_current": False,  # This would need to be determined by the caller
                }
                session_list.append(session_info)

            return session_list

        except Exception as e:
            logger.error(f"Error getting active sessions for user {user.username}: {e}")
            return []

    @staticmethod
    def check_session_security(request, user: User) -> Dict[str, Any]:
        """
        Perform security checks on current session.

        Args:
            request: HTTP request object
            user: Current user

        Returns:
            Dictionary with security check results
        """
        security_check = {"is_secure": True, "warnings": [], "actions_taken": []}

        try:
            if not SessionManager.SESSION_SECURITY_CHECKS:
                return security_check

            session_key = request.session.session_key
            if not session_key:
                return security_check

            session_obj = UserSession.objects.filter(
                session_key=session_key, is_active=True
            ).first()

            if not session_obj:
                security_check["is_secure"] = False
                security_check["warnings"].append("Session record not found")
                return security_check

            client_info = get_client_info(request)
            current_ip = client_info.get("ip_address", "")
            current_ua = client_info.get("user_agent", "")

            # Check for IP address changes
            if session_obj.ip_address != current_ip:
                # Log IP change
                UserAuditLog.objects.create(
                    user=user,
                    action="session_ip_change",
                    description=f"Session IP changed from {session_obj.ip_address} to {current_ip}",
                    ip_address=current_ip,
                    severity="medium",
                    extra_data={
                        "old_ip": session_obj.ip_address,
                        "new_ip": current_ip,
                        "session_key": session_key[:8] + "...",
                    },
                )

                # Update session IP
                session_obj.ip_address = current_ip
                session_obj.save(update_fields=["ip_address"])

                security_check["warnings"].append("IP address changed during session")

            # Check for user agent changes (more suspicious)
            if session_obj.user_agent != current_ua:
                security_check["is_secure"] = False
                security_check["warnings"].append("User agent changed during session")

                # Log suspicious activity
                UserAuditLog.objects.create(
                    user=user,
                    action="session_ua_change",
                    description="Suspicious: User agent changed during session",
                    ip_address=current_ip,
                    severity="high",
                    extra_data={
                        "old_ua": session_obj.user_agent,
                        "new_ua": current_ua,
                        "session_key": session_key[:8] + "...",
                    },
                )

            # Check session timeout
            if SessionManager._is_session_expired(session_obj):
                security_check["is_secure"] = False
                security_check["warnings"].append("Session has expired")
                security_check["actions_taken"].append("Session will be terminated")

                # Terminate expired session
                SessionManager.terminate_session(session_key, "expired")

            return security_check

        except Exception as e:
            logger.error(f"Error in session security check: {e}")
            security_check["is_secure"] = False
            security_check["warnings"].append("Security check failed")
            return security_check

    @staticmethod
    def cleanup_expired_sessions() -> int:
        """
        Clean up expired sessions.

        Returns:
            Number of sessions cleaned up
        """
        try:
            timeout_minutes = SessionManager.SESSION_TIMEOUT_MINUTES
            cutoff_time = timezone.now() - timedelta(minutes=timeout_minutes)

            # Find expired sessions
            expired_sessions = UserSession.objects.filter(
                last_activity__lt=cutoff_time, is_active=True
            )

            expired_count = 0

            for session in expired_sessions:
                if SessionManager.terminate_session(session.session_key, "expired"):
                    expired_count += 1

            logger.info(f"Cleaned up {expired_count} expired sessions")
            return expired_count

        except Exception as e:
            logger.error(f"Error cleaning up expired sessions: {e}")
            return 0

    @staticmethod
    def get_session_analytics(days: int = 30) -> Dict[str, Any]:
        """
        Get session analytics for the specified period.

        Args:
            days: Number of days to analyze

        Returns:
            Dictionary with session analytics
        """
        try:
            start_date = timezone.now() - timedelta(days=days)

            # Total sessions in period
            total_sessions = UserSession.objects.filter(
                created_at__gte=start_date
            ).count()

            # Active sessions
            active_sessions = UserSession.objects.filter(is_active=True).count()

            # Unique users with sessions
            unique_users = (
                UserSession.objects.filter(created_at__gte=start_date)
                .values("user")
                .distinct()
                .count()
            )

            # Average sessions per user
            avg_sessions_per_user = (
                total_sessions / unique_users if unique_users > 0 else 0
            )

            # Device type distribution
            device_stats = (
                UserSession.objects.filter(created_at__gte=start_date)
                .values("device_type")
                .annotate(count=Count("id"))
                .order_by("-count")
            )

            # Browser distribution
            browser_stats = (
                UserSession.objects.filter(created_at__gte=start_date)
                .values("browser")
                .annotate(count=Count("id"))
                .order_by("-count")[:10]
            )

            # Geographic distribution
            country_stats = (
                UserSession.objects.filter(created_at__gte=start_date)
                .exclude(country="")
                .values("country")
                .annotate(count=Count("id"))
                .order_by("-count")[:10]
            )

            # Concurrent sessions analysis
            max_concurrent = (
                User.objects.annotate(
                    concurrent_count=Count(
                        "sessions", filter=Q(sessions__is_active=True)
                    )
                ).aggregate(max_concurrent=Count("concurrent_count"))["max_concurrent"]
                or 0
            )

            return {
                "period_days": days,
                "total_sessions": total_sessions,
                "active_sessions": active_sessions,
                "unique_users": unique_users,
                "average_sessions_per_user": round(avg_sessions_per_user, 2),
                "max_concurrent_sessions": max_concurrent,
                "device_distribution": list(device_stats),
                "browser_distribution": list(browser_stats),
                "geographic_distribution": list(country_stats),
            }

        except Exception as e:
            logger.error(f"Error generating session analytics: {e}")
            return {}

    @staticmethod
    def detect_session_anomalies(user: User) -> List[Dict[str, Any]]:
        """
        Detect session anomalies for a user.

        Args:
            user: User to analyze

        Returns:
            List of detected anomalies
        """
        anomalies = []

        try:
            # Get recent sessions (last 7 days)
            recent_sessions = UserSession.objects.filter(
                user=user, created_at__gte=timezone.now() - timedelta(days=7)
            ).order_by("-created_at")

            if not recent_sessions.exists():
                return anomalies

            # Multiple concurrent sessions
            active_sessions = recent_sessions.filter(is_active=True)
            if active_sessions.count() > 3:
                unique_ips = active_sessions.values_list(
                    "ip_address", flat=True
                ).distinct()
                anomalies.append(
                    {
                        "type": "multiple_concurrent_sessions",
                        "severity": "medium",
                        "description": f"{active_sessions.count()} concurrent sessions from {len(unique_ips)} IP addresses",
                        "session_count": active_sessions.count(),
                        "ip_count": len(unique_ips),
                    }
                )

            # Rapid session creation
            if recent_sessions.count() >= 10:
                session_times = list(
                    recent_sessions.values_list("created_at", flat=True)[:10]
                )
                time_diffs = []

                for i in range(1, len(session_times)):
                    diff = (session_times[i - 1] - session_times[i]).total_seconds()
                    time_diffs.append(diff)

                avg_interval = sum(time_diffs) / len(time_diffs)

                if avg_interval < 60:  # Less than 1 minute between sessions
                    anomalies.append(
                        {
                            "type": "rapid_session_creation",
                            "severity": "high",
                            "description": f"Rapid session creation: average {avg_interval:.1f} seconds between sessions",
                            "average_interval_seconds": avg_interval,
                        }
                    )

            # Geographic anomalies
            countries = (
                recent_sessions.exclude(country="")
                .values_list("country", flat=True)
                .distinct()
            )
            if len(countries) > 5:  # Sessions from more than 5 countries
                anomalies.append(
                    {
                        "type": "geographic_anomaly",
                        "severity": "medium",
                        "description": f"Sessions from {len(countries)} different countries",
                        "countries": list(countries),
                    }
                )

            # Unusual session durations
            for session in active_sessions:
                duration_hours = (
                    timezone.now() - session.created_at
                ).total_seconds() / 3600
                if duration_hours > 24:  # Session longer than 24 hours
                    anomalies.append(
                        {
                            "type": "long_session",
                            "severity": "low",
                            "description": f"Session active for {duration_hours:.1f} hours",
                            "duration_hours": duration_hours,
                            "session_key": session.session_key[:8] + "...",
                        }
                    )

            return anomalies

        except Exception as e:
            logger.error(
                f"Error detecting session anomalies for user {user.username}: {e}"
            )
            return []

    @staticmethod
    def get_session_duration(session: UserSession) -> int:
        """
        Calculate session duration in minutes.

        Args:
            session: UserSession object

        Returns:
            Duration in minutes
        """
        if session.is_active:
            end_time = timezone.now()
        else:
            end_time = session.last_activity or session.created_at

        duration = end_time - session.created_at
        return int(duration.total_seconds() / 60)

    @staticmethod
    def _enforce_concurrent_session_limit(user: User, current_session_key: str):
        """
        Enforce concurrent session limits by terminating oldest sessions.

        Args:
            user: User to enforce limits for
            current_session_key: Current session to exclude
        """
        try:
            active_sessions = (
                UserSession.objects.filter(user=user, is_active=True)
                .exclude(session_key=current_session_key)
                .order_by("last_activity")
            )

            if active_sessions.count() >= SessionManager.MAX_CONCURRENT_SESSIONS:
                # Terminate oldest sessions
                sessions_to_terminate = active_sessions[
                    : (
                        active_sessions.count()
                        - SessionManager.MAX_CONCURRENT_SESSIONS
                        + 1
                    )
                ]

                for session in sessions_to_terminate:
                    SessionManager.terminate_session(
                        session.session_key, "concurrent_limit"
                    )

                logger.info(
                    f"Terminated {len(sessions_to_terminate)} sessions for user {user.username} due to concurrent limit"
                )

        except Exception as e:
            logger.error(f"Error enforcing concurrent session limit: {e}")

    @staticmethod
    def _is_session_expired(session: UserSession) -> bool:
        """
        Check if a session has expired based on inactivity.

        Args:
            session: UserSession to check

        Returns:
            True if session is expired
        """
        if not session.last_activity:
            return False

        timeout_minutes = SessionManager.SESSION_TIMEOUT_MINUTES
        expiry_time = session.last_activity + timedelta(minutes=timeout_minutes)

        return timezone.now() > expiry_time


# Utility functions for template context
def get_user_session_context(
    user: User, current_session_key: str = None
) -> Dict[str, Any]:
    """
    Get session context data for templates.

    Args:
        user: Current user
        current_session_key: Current session key

    Returns:
        Dictionary with session context
    """
    active_sessions = SessionManager.get_active_sessions(user)

    # Mark current session
    for session in active_sessions:
        if current_session_key and session["session_key"].startswith(
            current_session_key[:8]
        ):
            session["is_current"] = True

    return {
        "active_sessions": active_sessions,
        "session_count": len(active_sessions),
        "max_concurrent_sessions": SessionManager.MAX_CONCURRENT_SESSIONS,
        "session_timeout_minutes": SessionManager.SESSION_TIMEOUT_MINUTES,
    }


def get_session_security_status(user: User) -> Dict[str, Any]:
    """
    Get session security status for user.

    Args:
        user: User to check

    Returns:
        Dictionary with security status
    """
    anomalies = SessionManager.detect_session_anomalies(user)
    active_sessions = UserSession.objects.filter(user=user, is_active=True)

    # Count unique locations
    unique_locations = (
        active_sessions.exclude(country="").values("country", "city").distinct().count()
    )

    return {
        "anomaly_count": len(anomalies),
        "anomalies": anomalies,
        "unique_locations": unique_locations,
        "has_security_concerns": len(anomalies) > 0 or unique_locations > 3,
        "active_session_count": active_sessions.count(),
    }
