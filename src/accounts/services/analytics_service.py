# src/accounts/services/analytics_service.py

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from django.contrib.auth import get_user_model
from django.db.models import Count, Q, Avg, Max, Min
from django.db.models.functions import TruncDate, TruncMonth
from django.utils import timezone

from ..models import UserAuditLog, UserRole, UserRoleAssignment, UserSession

logger = logging.getLogger(__name__)
User = get_user_model()


class UserAnalyticsService:
    """Service for user-related analytics and insights."""

    @staticmethod
    def get_user_registration_trends(days: int = 30) -> Dict[str, Any]:
        """Get user registration trends over specified days."""
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)

        # Daily registration counts
        daily_registrations = (
            User.objects.filter(date_joined__gte=start_date)
            .annotate(date=TruncDate("date_joined"))
            .values("date")
            .annotate(count=Count("id"))
            .order_by("date")
        )

        # Convert to list of dictionaries for easier frontend consumption
        daily_data = [
            {"date": item["date"].strftime("%Y-%m-%d"), "count": item["count"]}
            for item in daily_registrations
        ]

        # Calculate statistics
        total_registrations = User.objects.filter(date_joined__gte=start_date).count()
        avg_daily = total_registrations / days if days > 0 else 0

        # Compare with previous period
        previous_start = start_date - timedelta(days=days)
        previous_registrations = User.objects.filter(
            date_joined__gte=previous_start, date_joined__lt=start_date
        ).count()

        growth_rate = 0
        if previous_registrations > 0:
            growth_rate = (
                (total_registrations - previous_registrations) / previous_registrations
            ) * 100

        return {
            "period_days": days,
            "total_registrations": total_registrations,
            "average_daily": round(avg_daily, 2),
            "growth_rate": round(growth_rate, 2),
            "daily_data": daily_data,
            "previous_period_total": previous_registrations,
        }

    @staticmethod
    def get_user_activity_analytics(days: int = 30) -> Dict[str, Any]:
        """Analyze user activity patterns."""
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)

        # Login activity
        login_logs = UserAuditLog.objects.filter(
            action="login", timestamp__gte=start_date
        )

        total_logins = login_logs.count()
        successful_logins = login_logs.filter(
            description__contains="Successful"
        ).count()
        failed_logins = total_logins - successful_logins

        # Unique active users
        active_users = (
            login_logs.filter(description__contains="Successful")
            .values("user")
            .distinct()
            .count()
        )

        # Daily login patterns
        daily_logins = (
            login_logs.filter(description__contains="Successful")
            .annotate(date=TruncDate("timestamp"))
            .values("date")
            .annotate(
                login_count=Count("id"), unique_users=Count("user", distinct=True)
            )
            .order_by("date")
        )

        daily_activity = [
            {
                "date": item["date"].strftime("%Y-%m-%d"),
                "login_count": item["login_count"],
                "unique_users": item["unique_users"],
            }
            for item in daily_logins
        ]

        # Top active users
        top_users = (
            login_logs.filter(description__contains="Successful")
            .values("user__username", "user__first_name", "user__last_name")
            .annotate(login_count=Count("id"))
            .order_by("-login_count")[:10]
        )

        # Login failure analysis
        failure_analysis = (
            login_logs.filter(description__contains="Failed")
            .values("ip_address")
            .annotate(failure_count=Count("id"))
            .order_by("-failure_count")[:10]
        )

        return {
            "period_days": days,
            "total_logins": total_logins,
            "successful_logins": successful_logins,
            "failed_logins": failed_logins,
            "success_rate": round(
                (successful_logins / total_logins * 100) if total_logins > 0 else 0, 2
            ),
            "active_users": active_users,
            "daily_activity": daily_activity,
            "top_active_users": list(top_users),
            "top_failure_ips": list(failure_analysis),
        }

    @staticmethod
    def get_role_distribution_analytics() -> Dict[str, Any]:
        """Analyze role distribution among users."""
        # Get role assignment counts
        role_stats = (
            UserRole.objects.annotate(
                active_users=Count(
                    "user_assignments", filter=Q(user_assignments__is_active=True)
                ),
                total_assignments=Count("user_assignments"),
            )
            .values(
                "name",
                "description",
                "is_system_role",
                "active_users",
                "total_assignments",
            )
            .order_by("-active_users")
        )

        # Calculate percentages
        total_active_assignments = sum(role["active_users"] for role in role_stats)

        role_distribution = []
        for role in role_stats:
            percentage = 0
            if total_active_assignments > 0:
                percentage = (role["active_users"] / total_active_assignments) * 100

            role_distribution.append(
                {
                    "role_name": role["name"],
                    "description": role["description"],
                    "is_system_role": role["is_system_role"],
                    "active_users": role["active_users"],
                    "total_assignments": role["total_assignments"],
                    "percentage": round(percentage, 2),
                }
            )

        # Users with multiple roles
        multiple_roles_users = (
            User.objects.annotate(
                role_count=Count(
                    "role_assignments", filter=Q(role_assignments__is_active=True)
                )
            )
            .filter(role_count__gt=1)
            .count()
        )

        # Users with no roles
        no_roles_users = (
            User.objects.annotate(
                role_count=Count(
                    "role_assignments", filter=Q(role_assignments__is_active=True)
                )
            )
            .filter(role_count=0)
            .count()
        )

        return {
            "role_distribution": role_distribution,
            "total_active_assignments": total_active_assignments,
            "users_with_multiple_roles": multiple_roles_users,
            "users_with_no_roles": no_roles_users,
            "total_roles": UserRole.objects.count(),
            "system_roles_count": UserRole.objects.filter(is_system_role=True).count(),
            "custom_roles_count": UserRole.objects.filter(is_system_role=False).count(),
        }

    @staticmethod
    def get_security_analytics(days: int = 30) -> Dict[str, Any]:
        """Analyze security-related metrics."""
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)

        # Account lockouts
        locked_accounts = User.objects.filter(failed_login_attempts__gte=5).count()

        # Recent security events
        security_events = UserAuditLog.objects.filter(
            timestamp__gte=start_date,
            action__in=["login", "password_change", "account_lock", "account_unlock"],
        )

        # Failed login attempts
        failed_login_attempts = security_events.filter(
            action="login", description__contains="Failed"
        )

        # Geographic analysis (by IP)
        ip_analysis = (
            failed_login_attempts.values("ip_address")
            .annotate(
                attempt_count=Count("id"), unique_users=Count("user", distinct=True)
            )
            .order_by("-attempt_count")[:20]
        )

        # Suspicious activity patterns
        suspicious_ips = [
            ip
            for ip in ip_analysis
            if ip["attempt_count"] >= 10 or ip["unique_users"] >= 3
        ]

        # Password change frequency
        password_changes = security_events.filter(action="password_change").count()

        # Users requiring password change
        users_need_password_change = User.objects.filter(
            requires_password_change=True
        ).count()

        # Account unlock events
        account_unlocks = security_events.filter(action="account_unlock").count()

        return {
            "period_days": days,
            "locked_accounts": locked_accounts,
            "failed_login_attempts": failed_login_attempts.count(),
            "password_changes": password_changes,
            "users_requiring_password_change": users_need_password_change,
            "account_unlocks": account_unlocks,
            "suspicious_ip_count": len(suspicious_ips),
            "suspicious_ips": suspicious_ips,
            "top_failure_ips": list(ip_analysis),
        }

    @staticmethod
    def get_user_lifecycle_analytics() -> Dict[str, Any]:
        """Analyze user lifecycle stages."""
        total_users = User.objects.count()

        # User status distribution
        active_users = User.objects.filter(is_active=True).count()
        inactive_users = User.objects.filter(is_active=False).count()

        # New users (last 30 days)
        thirty_days_ago = timezone.now() - timedelta(days=30)
        new_users = User.objects.filter(date_joined__gte=thirty_days_ago).count()

        # Users who never logged in
        never_logged_in = User.objects.filter(last_login__isnull=True).count()

        # Users by registration period
        now = timezone.now()
        periods = {
            "last_7_days": now - timedelta(days=7),
            "last_30_days": now - timedelta(days=30),
            "last_90_days": now - timedelta(days=90),
            "last_year": now - timedelta(days=365),
        }

        registration_periods = {}
        for period_name, start_date in periods.items():
            count = User.objects.filter(date_joined__gte=start_date).count()
            registration_periods[period_name] = count

        # User engagement levels based on login frequency
        engagement_levels = {
            "highly_active": 0,  # Logged in last 7 days
            "moderately_active": 0,  # Logged in last 30 days
            "low_activity": 0,  # Logged in last 90 days
            "inactive": 0,  # Haven't logged in for 90+ days
        }

        for level, threshold in [
            ("highly_active", 7),
            ("moderately_active", 30),
            ("low_activity", 90),
        ]:
            cutoff_date = now - timedelta(days=threshold)
            count = User.objects.filter(
                last_login__gte=cutoff_date, is_active=True
            ).count()
            engagement_levels[level] = count

        # Inactive users (no login for 90+ days or never logged in)
        ninety_days_ago = now - timedelta(days=90)
        engagement_levels["inactive"] = User.objects.filter(
            Q(last_login__lt=ninety_days_ago) | Q(last_login__isnull=True),
            is_active=True,
        ).count()

        return {
            "total_users": total_users,
            "active_users": active_users,
            "inactive_users": inactive_users,
            "new_users_30_days": new_users,
            "never_logged_in": never_logged_in,
            "registration_periods": registration_periods,
            "engagement_levels": engagement_levels,
            "active_percentage": round(
                (active_users / total_users * 100) if total_users > 0 else 0, 2
            ),
        }

    @staticmethod
    def get_session_analytics(days: int = 30) -> Dict[str, Any]:
        """Analyze user session patterns."""
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)

        # Active sessions
        active_sessions = UserSession.objects.filter(is_active=True).count()

        # Session duration analysis (approximation based on activity)
        recent_sessions = UserSession.objects.filter(created_at__gte=start_date)

        # Average sessions per user
        total_sessions = recent_sessions.count()
        unique_users = recent_sessions.values("user").distinct().count()
        avg_sessions_per_user = total_sessions / unique_users if unique_users > 0 else 0

        # Browser/device analysis
        user_agents = (
            recent_sessions.values("user_agent")
            .annotate(session_count=Count("id"))
            .order_by("-session_count")[:10]
        )

        # Geographic analysis (by IP)
        ip_locations = (
            recent_sessions.values("ip_address")
            .annotate(
                session_count=Count("id"), unique_users=Count("user", distinct=True)
            )
            .order_by("-session_count")[:20]
        )

        # Concurrent sessions analysis
        max_concurrent = User.objects.annotate(
            concurrent_sessions=Count("sessions", filter=Q(sessions__is_active=True))
        ).aggregate(max_concurrent=Max("concurrent_sessions"))

        return {
            "period_days": days,
            "active_sessions": active_sessions,
            "total_sessions_period": total_sessions,
            "unique_users_with_sessions": unique_users,
            "average_sessions_per_user": round(avg_sessions_per_user, 2),
            "max_concurrent_sessions": max_concurrent.get("max_concurrent", 0),
            "top_user_agents": list(user_agents),
            "top_ip_locations": list(ip_locations),
        }

    @staticmethod
    def generate_comprehensive_report(days: int = 30) -> Dict[str, Any]:
        """Generate a comprehensive analytics report."""
        return {
            "generated_at": timezone.now().isoformat(),
            "period_days": days,
            "registration_trends": UserAnalyticsService.get_user_registration_trends(
                days
            ),
            "activity_analytics": UserAnalyticsService.get_user_activity_analytics(
                days
            ),
            "role_distribution": UserAnalyticsService.get_role_distribution_analytics(),
            "security_analytics": UserAnalyticsService.get_security_analytics(days),
            "lifecycle_analytics": UserAnalyticsService.get_user_lifecycle_analytics(),
            "session_analytics": UserAnalyticsService.get_session_analytics(days),
        }

    @staticmethod
    def get_user_performance_metrics(user: User, days: int = 30) -> Dict[str, Any]:
        """Get performance metrics for a specific user."""
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)

        # Login activity
        login_logs = UserAuditLog.objects.filter(
            user=user, action="login", timestamp__gte=start_date
        )

        successful_logins = login_logs.filter(
            description__contains="Successful"
        ).count()
        failed_logins = login_logs.filter(description__contains="Failed").count()

        # Session activity
        user_sessions = UserSession.objects.filter(
            user=user, created_at__gte=start_date
        )

        # Security events
        security_events = UserAuditLog.objects.filter(
            user=user,
            timestamp__gte=start_date,
            action__in=["password_change", "account_lock", "account_unlock"],
        ).count()

        # Role changes
        role_changes = UserAuditLog.objects.filter(
            user=user,
            timestamp__gte=start_date,
            action__in=["role_assign", "role_remove"],
        ).count()

        return {
            "user_id": user.id,
            "username": user.username,
            "period_days": days,
            "successful_logins": successful_logins,
            "failed_logins": failed_logins,
            "total_sessions": user_sessions.count(),
            "security_events": security_events,
            "role_changes": role_changes,
            "is_active": user.is_active,
            "is_locked": user.is_account_locked(),
            "requires_password_change": user.requires_password_change,
            "last_login": user.last_login.isoformat() if user.last_login else None,
        }
