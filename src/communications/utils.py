"""
Utility functions and helpers for Communications module.
Provides common functionality for communication processing, formatting, and validation.
"""

from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db.models import Q, Count, Avg
from django.core.exceptions import ValidationError
from django.template import Template, Context
from django.utils.html import strip_tags
from django.utils.text import truncate_words
from typing import List, Dict, Any, Optional, Union
from datetime import datetime, timedelta
import re
import json
import logging

from .models import (
    CommunicationPreference,
    CommunicationChannel,
    Priority,
    TargetAudience,
    MessageStatus,
    Notification,
    MessageThread,
)

User = get_user_model()
logger = logging.getLogger(__name__)


class CommunicationValidator:
    """Validator for communication data and content"""

    @staticmethod
    def validate_email_content(subject: str, content: str) -> Dict[str, Any]:
        """Validate email content for deliverability"""
        issues = []
        warnings = []

        # Subject line validation
        if not subject or len(subject.strip()) == 0:
            issues.append("Subject line is required")
        elif len(subject) > 200:
            issues.append("Subject line is too long (max 200 characters)")
        elif len(subject) < 5:
            warnings.append(
                "Subject line is very short, consider making it more descriptive"
            )

        # Content validation
        if not content or len(content.strip()) == 0:
            issues.append("Message content is required")
        elif len(content) > 10000:
            warnings.append("Message content is very long, consider breaking it up")

        # Check for spam indicators
        spam_words = ["urgent", "act now", "limited time", "free money", "click here"]
        content_lower = content.lower()
        found_spam_words = [word for word in spam_words if word in content_lower]

        if found_spam_words:
            warnings.append(
                f"Content contains potential spam words: {', '.join(found_spam_words)}"
            )

        # Check for excessive capitalization
        if len(re.findall(r"[A-Z]", content)) / len(content) > 0.3:
            warnings.append("Content has excessive capitalization")

        # Check for excessive punctuation
        if len(re.findall(r"[!?]", content)) > 10:
            warnings.append("Content has excessive punctuation")

        return {
            "is_valid": len(issues) == 0,
            "issues": issues,
            "warnings": warnings,
            "score": max(0, 100 - len(issues) * 20 - len(warnings) * 5),
        }

    @staticmethod
    def validate_sms_content(content: str) -> Dict[str, Any]:
        """Validate SMS content for deliverability"""
        issues = []
        warnings = []

        if not content or len(content.strip()) == 0:
            issues.append("SMS content is required")
        elif len(content) > 160:
            warnings.append(
                f"SMS content is {len(content)} characters, may be split into multiple messages"
            )
        elif len(content) > 320:
            issues.append(
                "SMS content is too long (max 320 characters for concatenated SMS)"
            )

        # Check for non-standard characters
        non_standard_chars = re.findall(r"[^\x00-\x7F]", content)
        if non_standard_chars:
            warnings.append(
                "SMS contains non-standard characters that may not display correctly"
            )

        return {
            "is_valid": len(issues) == 0,
            "issues": issues,
            "warnings": warnings,
            "character_count": len(content),
            "estimated_parts": max(1, len(content) // 160),
        }

    @staticmethod
    def validate_user_targeting(target_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate user targeting configuration"""
        issues = []
        warnings = []

        target_audience = target_data.get("target_audience")
        user_ids = target_data.get("user_ids", [])
        filters = target_data.get("filters", {})

        if target_audience == TargetAudience.CUSTOM:
            has_targeting = any(
                [
                    user_ids,
                    filters.get("sections"),
                    filters.get("grades"),
                    filters.get("classes"),
                ]
            )

            if not has_targeting:
                issues.append("Custom audience requires at least one targeting option")

        # Validate user IDs exist
        if user_ids:
            existing_users = User.objects.filter(
                id__in=user_ids, is_active=True
            ).count()
            if existing_users != len(user_ids):
                warnings.append(f"Some user IDs may not exist or are inactive")

        return {"is_valid": len(issues) == 0, "issues": issues, "warnings": warnings}


class ContentFormatter:
    """Formatter for communication content"""

    @staticmethod
    def format_for_email(content: str, user: User = None) -> str:
        """Format content for email delivery"""
        if not content:
            return ""

        # Convert newlines to HTML breaks
        formatted = content.replace("\n", "<br>")

        # Add basic HTML structure if needed
        if not formatted.strip().startswith("<"):
            formatted = f"<div>{formatted}</div>"

        return formatted

    @staticmethod
    def format_for_sms(content: str, max_length: int = 160) -> str:
        """Format content for SMS delivery"""
        if not content:
            return ""

        # Strip HTML tags
        clean_content = strip_tags(content)

        # Remove extra whitespace
        clean_content = " ".join(clean_content.split())

        # Truncate if necessary
        if len(clean_content) > max_length:
            clean_content = clean_content[: max_length - 3] + "..."

        return clean_content

    @staticmethod
    def format_for_push(title: str, content: str) -> Dict[str, str]:
        """Format content for push notification"""
        # Truncate title for push notifications
        clean_title = strip_tags(title)[:50]

        # Truncate content for push notifications
        clean_content = strip_tags(content)[:100]

        return {"title": clean_title, "body": clean_content}

    @staticmethod
    def create_preview(content: str, word_limit: int = 30) -> str:
        """Create a preview of content"""
        clean_content = strip_tags(content)
        return truncate_words(clean_content, word_limit)

    @staticmethod
    def format_notification_summary(notifications: List[Any]) -> str:
        """Format multiple notifications into a summary"""
        if not notifications:
            return "No notifications"

        if len(notifications) == 1:
            return f"1 notification: {notifications[0].title}"

        summary_parts = [f"{len(notifications)} notifications:"]

        for notification in notifications[:3]:
            summary_parts.append(f"• {notification.title}")

        if len(notifications) > 3:
            summary_parts.append(f"• ... and {len(notifications) - 3} more")

        return "\n".join(summary_parts)


class TemplateProcessor:
    """Processor for message templates"""

    @staticmethod
    def render_template(template_content: str, context: Dict[str, Any]) -> str:
        """Render template with context"""
        try:
            template = Template(template_content)
            context_obj = Context(context)
            return template.render(context_obj)
        except Exception as e:
            logger.error(f"Template rendering failed: {str(e)}")
            return template_content

    @staticmethod
    def extract_variables(template_content: str) -> List[str]:
        """Extract variable names from template content"""
        # Simple regex to find Django template variables
        pattern = r"\{\{\s*([^}]+)\s*\}\}"
        matches = re.findall(pattern, template_content)

        variables = []
        for match in matches:
            # Clean up the variable name
            var_name = match.split("|")[0].strip()  # Remove filters
            var_name = var_name.split(".")[0].strip()  # Get base variable

            if var_name not in variables:
                variables.append(var_name)

        return variables

    @staticmethod
    def validate_template(
        template_content: str, required_variables: List[str] = None
    ) -> Dict[str, Any]:
        """Validate template syntax and variables"""
        issues = []
        warnings = []

        try:
            # Try to create template
            Template(template_content)
        except Exception as e:
            issues.append(f"Template syntax error: {str(e)}")

        # Check for required variables
        if required_variables:
            template_variables = TemplateProcessor.extract_variables(template_content)
            missing_variables = [
                var for var in required_variables if var not in template_variables
            ]

            if missing_variables:
                warnings.append(f"Missing variables: {', '.join(missing_variables)}")

        return {
            "is_valid": len(issues) == 0,
            "issues": issues,
            "warnings": warnings,
            "variables": TemplateProcessor.extract_variables(template_content),
        }

    @staticmethod
    def create_sample_context(user: User = None) -> Dict[str, Any]:
        """Create sample context for template preview"""
        context = {
            "school_name": "Sample School",
            "current_date": timezone.now().date(),
            "current_time": timezone.now().time(),
            "academic_year": "2024-2025",
            "term": "First Term",
        }

        if user:
            context.update(
                {
                    "user": user,
                    "user_name": user.get_full_name(),
                    "username": user.username,
                    "email": user.email,
                }
            )

            # Add role-specific context
            if hasattr(user, "student"):
                context.update(
                    {
                        "student_name": user.get_full_name(),
                        "class_name": "Grade 5 North",
                        "roll_number": "12345",
                    }
                )

            if hasattr(user, "parent"):
                context.update(
                    {
                        "parent_name": user.get_full_name(),
                        "children": ["John Doe", "Jane Doe"],
                    }
                )

        return context


class UserTargeting:
    """Utilities for user targeting and filtering"""

    @staticmethod
    def get_users_by_audience(
        audience: str, filters: Dict[str, Any] = None, exclude_users: List[int] = None
    ) -> List[User]:
        """Get users based on audience type and filters"""

        query = Q(is_active=True)

        # Apply audience filter
        if audience == TargetAudience.STUDENTS:
            query &= Q(userroleassignment__role__name="Student")
        elif audience == TargetAudience.TEACHERS:
            query &= Q(userroleassignment__role__name="Teacher")
        elif audience == TargetAudience.PARENTS:
            query &= Q(userroleassignment__role__name="Parent")
        elif audience == TargetAudience.STAFF:
            query &= Q(userroleassignment__role__name="Staff")

        # Apply additional filters
        if filters:
            if filters.get("sections"):
                query &= Q(
                    student__current_class__grade__section__id__in=filters["sections"]
                )

            if filters.get("grades"):
                query &= Q(student__current_class__grade__id__in=filters["grades"])

            if filters.get("classes"):
                query &= Q(student__current_class__id__in=filters["classes"])

            if filters.get("departments"):
                query &= Q(teacher__department__id__in=filters["departments"])

        # Exclude specific users
        if exclude_users:
            query &= ~Q(id__in=exclude_users)

        return list(User.objects.filter(query).distinct())

    @staticmethod
    def filter_by_preferences(
        users: List[User], channel: str, notification_type: str = None
    ) -> List[User]:
        """Filter users based on their communication preferences"""

        filtered_users = []

        for user in users:
            try:
                prefs = CommunicationPreference.objects.get(user=user)

                # Check channel preferences
                if channel == CommunicationChannel.EMAIL and not prefs.email_enabled:
                    continue
                elif channel == CommunicationChannel.SMS and not prefs.sms_enabled:
                    continue
                elif channel == CommunicationChannel.PUSH and not prefs.push_enabled:
                    continue

                # Check notification type preferences
                if notification_type:
                    type_category = notification_type.split("_")[0]

                    if type_category == "academic" and not prefs.academic_notifications:
                        continue
                    elif (
                        type_category == "financial"
                        and not prefs.financial_notifications
                    ):
                        continue
                    elif (
                        type_category == "attendance"
                        and not prefs.attendance_notifications
                    ):
                        continue
                    elif type_category == "general" and not prefs.general_announcements:
                        continue
                    elif type_category == "marketing" and not prefs.marketing_messages:
                        continue

                # Check quiet hours
                now = timezone.now().time()
                if prefs.quiet_hours_start <= now <= prefs.quiet_hours_end:
                    continue

                # Check weekend preferences
                if not prefs.weekend_notifications and timezone.now().weekday() >= 5:
                    continue

                filtered_users.append(user)

            except CommunicationPreference.DoesNotExist:
                # User has no preferences, include them
                filtered_users.append(user)

        return filtered_users

    @staticmethod
    def estimate_reach(audience: str, filters: Dict[str, Any] = None) -> Dict[str, int]:
        """Estimate reach for a given targeting configuration"""

        total_users = UserTargeting.get_users_by_audience(audience, filters)

        reach = {
            "total": len(total_users),
            "email": len(
                UserTargeting.filter_by_preferences(
                    total_users, CommunicationChannel.EMAIL
                )
            ),
            "sms": len(
                UserTargeting.filter_by_preferences(
                    total_users, CommunicationChannel.SMS
                )
            ),
            "push": len(
                UserTargeting.filter_by_preferences(
                    total_users, CommunicationChannel.PUSH
                )
            ),
        }

        return reach


class CommunicationMetrics:
    """Utilities for calculating communication metrics"""

    @staticmethod
    def calculate_engagement_rate(
        sent: int, opened: int, clicked: int = 0
    ) -> Dict[str, float]:
        """Calculate engagement metrics"""

        metrics = {
            "delivery_rate": 100.0,  # Assuming all sent were delivered
            "open_rate": 0.0,
            "click_rate": 0.0,
            "click_to_open_rate": 0.0,
        }

        if sent > 0:
            metrics["open_rate"] = (opened / sent) * 100
            metrics["click_rate"] = (clicked / sent) * 100

        if opened > 0:
            metrics["click_to_open_rate"] = (clicked / opened) * 100

        return metrics

    @staticmethod
    def calculate_performance_score(metrics: Dict[str, float]) -> float:
        """Calculate overall performance score"""

        # Weighted scoring
        weights = {"delivery_rate": 0.3, "open_rate": 0.4, "click_rate": 0.3}

        score = 0.0
        for metric, weight in weights.items():
            score += metrics.get(metric, 0) * weight

        return min(100.0, max(0.0, score))

    @staticmethod
    def get_benchmark_comparison(
        metrics: Dict[str, float], industry: str = "education"
    ) -> Dict[str, str]:
        """Compare metrics against industry benchmarks"""

        # Education industry benchmarks
        benchmarks = {
            "education": {"open_rate": 25.0, "click_rate": 3.5, "delivery_rate": 95.0}
        }

        industry_benchmarks = benchmarks.get(industry, benchmarks["education"])

        comparison = {}
        for metric, value in metrics.items():
            if metric in industry_benchmarks:
                benchmark = industry_benchmarks[metric]
                if value >= benchmark * 1.1:
                    comparison[metric] = "excellent"
                elif value >= benchmark:
                    comparison[metric] = "good"
                elif value >= benchmark * 0.8:
                    comparison[metric] = "average"
                else:
                    comparison[metric] = "below_average"

        return comparison


class NotificationPriority:
    """Utilities for handling notification priorities"""

    PRIORITY_WEIGHTS = {
        Priority.LOW: 1,
        Priority.MEDIUM: 2,
        Priority.HIGH: 3,
        Priority.URGENT: 4,
    }

    @staticmethod
    def get_delivery_delay(priority: str) -> int:
        """Get delivery delay in seconds based on priority"""
        delays = {
            Priority.URGENT: 0,  # Immediate
            Priority.HIGH: 30,  # 30 seconds
            Priority.MEDIUM: 300,  # 5 minutes
            Priority.LOW: 3600,  # 1 hour
        }

        return delays.get(priority, 300)

    @staticmethod
    def sort_by_priority(notifications: List[Any]) -> List[Any]:
        """Sort notifications by priority"""
        return sorted(
            notifications,
            key=lambda n: NotificationPriority.PRIORITY_WEIGHTS.get(n.priority, 2),
            reverse=True,
        )

    @staticmethod
    def should_override_quiet_hours(priority: str) -> bool:
        """Check if priority should override quiet hours"""
        return priority in [Priority.HIGH, Priority.URGENT]


class CommunicationBatcher:
    """Utilities for batching communication operations"""

    @staticmethod
    def batch_users(users: List[User], batch_size: int = 100) -> List[List[User]]:
        """Split users into batches"""
        batches = []
        for i in range(0, len(users), batch_size):
            batches.append(users[i : i + batch_size])
        return batches

    @staticmethod
    def create_delivery_schedule(
        total_count: int,
        priority: str = Priority.MEDIUM,
        rate_limit: int = 1000,  # messages per hour
    ) -> List[Dict[str, Any]]:
        """Create delivery schedule for bulk operations"""

        batch_size = min(100, rate_limit // 60)  # Per minute
        delay_between_batches = 60  # seconds

        # Adjust based on priority
        if priority == Priority.URGENT:
            batch_size = min(200, rate_limit // 30)
            delay_between_batches = 30
        elif priority == Priority.LOW:
            batch_size = min(50, rate_limit // 120)
            delay_between_batches = 120

        schedule = []
        current_time = timezone.now()

        for i in range(0, total_count, batch_size):
            end_index = min(i + batch_size, total_count)

            schedule.append(
                {
                    "batch_number": len(schedule) + 1,
                    "start_index": i,
                    "end_index": end_index,
                    "count": end_index - i,
                    "scheduled_time": current_time,
                    "estimated_duration": 30,  # seconds
                }
            )

            current_time += timedelta(seconds=delay_between_batches)

        return schedule


class CommunicationArchiver:
    """Utilities for archiving old communications"""

    @staticmethod
    def get_archivable_items(days_old: int = 90) -> Dict[str, int]:
        """Get count of items that can be archived"""
        cutoff_date = timezone.now() - timedelta(days=days_old)

        from .models import CommunicationLog, Notification, BulkMessage

        counts = {
            "logs": CommunicationLog.objects.filter(timestamp__lt=cutoff_date).count(),
            "read_notifications": Notification.objects.filter(
                created_at__lt=cutoff_date, is_read=True
            ).count(),
            "completed_bulk_messages": BulkMessage.objects.filter(
                created_at__lt=cutoff_date,
                status__in=[MessageStatus.SENT, MessageStatus.FAILED],
            ).count(),
        }

        return counts

    @staticmethod
    def create_archive_plan(days_old: int = 90) -> Dict[str, Any]:
        """Create plan for archiving operations"""
        counts = CommunicationArchiver.get_archivable_items(days_old)

        total_items = sum(counts.values())
        estimated_time = max(1, total_items // 1000)  # Rough estimate

        return {
            "cutoff_date": timezone.now() - timedelta(days=days_old),
            "items_to_archive": counts,
            "total_items": total_items,
            "estimated_time_minutes": estimated_time,
            "storage_savings_mb": total_items * 0.001,  # Rough estimate
        }


def get_communication_health_status() -> Dict[str, Any]:
    """Get overall health status of communication system"""

    from .models import (
        CommunicationAnalytics,
        CommunicationLog,
        Notification,
        BulkMessage,
    )

    # Recent activity (last 24 hours)
    yesterday = timezone.now() - timedelta(days=1)

    recent_logs = CommunicationLog.objects.filter(timestamp__gte=yesterday)

    recent_notifications = Notification.objects.filter(created_at__gte=yesterday)

    failed_communications = recent_logs.filter(status=MessageStatus.FAILED)

    # Calculate health metrics
    total_recent = recent_logs.count()
    failed_recent = failed_communications.count()

    failure_rate = (failed_recent / total_recent * 100) if total_recent > 0 else 0

    # Determine health status
    if failure_rate < 5:
        health = "excellent"
    elif failure_rate < 10:
        health = "good"
    elif failure_rate < 20:
        health = "fair"
    else:
        health = "poor"

    return {
        "status": health,
        "failure_rate": failure_rate,
        "recent_activity": {
            "total_communications": total_recent,
            "failed_communications": failed_recent,
            "notifications_sent": recent_notifications.count(),
            "unread_notifications": recent_notifications.filter(is_read=False).count(),
        },
        "last_updated": timezone.now(),
    }


def format_time_since(dt: datetime) -> str:
    """Format time since a datetime in human-readable format"""
    if not dt:
        return "Never"

    now = timezone.now()
    if timezone.is_aware(dt) != timezone.is_aware(now):
        if timezone.is_aware(now):
            dt = timezone.make_aware(dt)
        else:
            dt = timezone.make_naive(dt)

    diff = now - dt

    if diff.days > 0:
        return f"{diff.days} day{'s' if diff.days > 1 else ''} ago"
    elif diff.seconds > 3600:
        hours = diff.seconds // 3600
        return f"{hours} hour{'s' if hours > 1 else ''} ago"
    elif diff.seconds > 60:
        minutes = diff.seconds // 60
        return f"{minutes} minute{'s' if minutes > 1 else ''} ago"
    else:
        return "Just now"


def safe_json_loads(json_str: str, default: Any = None) -> Any:
    """Safely load JSON string with fallback"""
    try:
        return json.loads(json_str) if json_str else default
    except (json.JSONDecodeError, TypeError):
        return default


def generate_message_id() -> str:
    """Generate unique message ID for tracking"""
    import uuid

    return f"msg_{uuid.uuid4().hex[:12]}"


def truncate_content(content: str, max_length: int = 100) -> str:
    """Truncate content while preserving word boundaries"""
    if len(content) <= max_length:
        return content

    truncated = content[:max_length].rsplit(" ", 1)[0]
    return f"{truncated}..."
