"""
API serializers for Communications module.
Handles data serialization/deserialization for REST API endpoints.
"""

from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.utils import timezone
from typing import List

from ..models import (
    Announcement,
    Notification,
    BulkMessage,
    MessageRecipient,
    MessageTemplate,
    CommunicationPreference,
    CommunicationAnalytics,
    MessageThread,
    DirectMessage,
    MessageRead,
    CommunicationLog,
    CommunicationChannel,
    Priority,
    MessageStatus,
    TargetAudience,
)

User = get_user_model()


class UserBasicSerializer(serializers.ModelSerializer):
    """Basic user serializer for communication contexts"""

    full_name = serializers.CharField(source="get_full_name", read_only=True)

    class Meta:
        model = User
        fields = ["id", "username", "email", "first_name", "last_name", "full_name"]
        read_only_fields = ["id", "username", "full_name"]


class NotificationSerializer(serializers.ModelSerializer):
    """Serializer for notifications"""

    user = UserBasicSerializer(read_only=True)
    time_since_created = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = [
            "id",
            "user",
            "title",
            "content",
            "notification_type",
            "reference_id",
            "reference_type",
            "created_at",
            "is_read",
            "read_at",
            "priority",
            "channels_used",
            "delivery_status",
            "time_since_created",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "user",
            "delivery_status",
            "time_since_created",
        ]

    def get_time_since_created(self, obj):
        """Get human-readable time since creation"""
        now = timezone.now()
        diff = now - obj.created_at

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


class NotificationCreateSerializer(serializers.Serializer):
    """Serializer for creating notifications"""

    user_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        help_text="List of user IDs to send notification to",
    )
    title = serializers.CharField(max_length=200)
    content = serializers.CharField()
    notification_type = serializers.CharField(max_length=50)
    priority = serializers.ChoiceField(
        choices=Priority.choices, default=Priority.MEDIUM
    )
    channels = serializers.ListField(
        child=serializers.ChoiceField(choices=CommunicationChannel.choices),
        default=[CommunicationChannel.IN_APP],
    )
    reference_id = serializers.CharField(max_length=100, required=False)
    reference_type = serializers.CharField(max_length=50, required=False)

    def validate_user_ids(self, value):
        """Validate that all user IDs exist"""
        if value:
            existing_users = User.objects.filter(id__in=value).count()
            if existing_users != len(value):
                raise serializers.ValidationError("Some user IDs do not exist")
        return value


class AnnouncementSerializer(serializers.ModelSerializer):
    """Serializer for announcements"""

    created_by = UserBasicSerializer(read_only=True)
    read_rate = serializers.ReadOnlyField()
    delivery_rate = serializers.ReadOnlyField()
    is_current = serializers.ReadOnlyField()
    time_since_created = serializers.SerializerMethodField()

    class Meta:
        model = Announcement
        fields = [
            "id",
            "title",
            "content",
            "created_by",
            "created_at",
            "updated_at",
            "target_audience",
            "target_grades",
            "target_classes",
            "target_sections",
            "start_date",
            "end_date",
            "is_active",
            "attachment",
            "priority",
            "channels",
            "total_recipients",
            "total_sent",
            "total_delivered",
            "total_read",
            "read_rate",
            "delivery_rate",
            "is_current",
            "time_since_created",
        ]
        read_only_fields = [
            "id",
            "created_by",
            "created_at",
            "updated_at",
            "total_recipients",
            "total_sent",
            "total_delivered",
            "total_read",
            "read_rate",
            "delivery_rate",
            "is_current",
            "time_since_created",
        ]

    def get_time_since_created(self, obj):
        """Get human-readable time since creation"""
        now = timezone.now()
        diff = now - obj.created_at

        if diff.days > 0:
            return f"{diff.days} day{'s' if diff.days > 1 else ''} ago"
        else:
            hours = diff.seconds // 3600
            return f"{hours} hour{'s' if hours > 1 else ''} ago"


class AnnouncementCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating announcements"""

    class Meta:
        model = Announcement
        fields = [
            "title",
            "content",
            "target_audience",
            "target_grades",
            "target_classes",
            "target_sections",
            "start_date",
            "end_date",
            "priority",
            "channels",
            "attachment",
        ]

    def validate(self, data):
        """Custom validation for announcement creation"""

        # Validate date range
        if data.get("end_date") and data.get("start_date"):
            if data["end_date"] <= data["start_date"]:
                raise serializers.ValidationError("End date must be after start date")

        # Validate targeting
        if data.get("target_audience") == TargetAudience.CUSTOM:
            if not any(
                [
                    data.get("target_grades"),
                    data.get("target_classes"),
                    data.get("target_sections"),
                ]
            ):
                raise serializers.ValidationError(
                    "Custom targeting requires at least one target group"
                )

        return data


class MessageTemplateSerializer(serializers.ModelSerializer):
    """Serializer for message templates"""

    created_by = UserBasicSerializer(read_only=True)

    class Meta:
        model = MessageTemplate
        fields = [
            "id",
            "name",
            "description",
            "template_type",
            "subject_template",
            "content_template",
            "supported_channels",
            "variables",
            "created_by",
            "created_at",
            "updated_at",
            "is_active",
        ]
        read_only_fields = ["id", "created_by", "created_at", "updated_at"]


class BulkMessageSerializer(serializers.ModelSerializer):
    """Serializer for bulk messages"""

    created_by = UserBasicSerializer(read_only=True)
    template = MessageTemplateSerializer(read_only=True)
    delivery_rate = serializers.ReadOnlyField()
    open_rate = serializers.ReadOnlyField()

    class Meta:
        model = BulkMessage
        fields = [
            "id",
            "name",
            "description",
            "subject",
            "content",
            "template",
            "target_audience",
            "target_filters",
            "recipient_count",
            "created_by",
            "created_at",
            "scheduled_at",
            "sent_at",
            "status",
            "channels",
            "priority",
            "total_recipients",
            "successful_deliveries",
            "failed_deliveries",
            "bounced_deliveries",
            "opened_count",
            "clicked_count",
            "delivery_rate",
            "open_rate",
        ]
        read_only_fields = [
            "id",
            "created_by",
            "created_at",
            "sent_at",
            "recipient_count",
            "total_recipients",
            "successful_deliveries",
            "failed_deliveries",
            "bounced_deliveries",
            "opened_count",
            "clicked_count",
            "delivery_rate",
            "open_rate",
        ]


class BulkMessageCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating bulk messages"""

    template_id = serializers.UUIDField(required=False)

    class Meta:
        model = BulkMessage
        fields = [
            "name",
            "description",
            "subject",
            "content",
            "template_id",
            "target_audience",
            "target_filters",
            "scheduled_at",
            "channels",
            "priority",
        ]

    def validate_template_id(self, value):
        """Validate template exists and is active"""
        if value:
            try:
                template = MessageTemplate.objects.get(id=value, is_active=True)
                return template
            except MessageTemplate.DoesNotExist:
                raise serializers.ValidationError("Template not found or inactive")
        return None


class MessageRecipientSerializer(serializers.ModelSerializer):
    """Serializer for message recipients"""

    user = UserBasicSerializer(read_only=True)

    class Meta:
        model = MessageRecipient
        fields = [
            "id",
            "user",
            "email",
            "phone",
            "email_status",
            "sms_status",
            "push_status",
            "sent_at",
            "delivered_at",
            "opened_at",
            "clicked_at",
            "bounced_at",
            "error_message",
            "retry_count",
        ]
        read_only_fields = fields


class CommunicationPreferenceSerializer(serializers.ModelSerializer):
    """Serializer for communication preferences"""

    user = UserBasicSerializer(read_only=True)

    class Meta:
        model = CommunicationPreference
        fields = [
            "user",
            "email_enabled",
            "sms_enabled",
            "push_enabled",
            "whatsapp_enabled",
            "academic_notifications",
            "financial_notifications",
            "attendance_notifications",
            "general_announcements",
            "marketing_messages",
            "quiet_hours_start",
            "quiet_hours_end",
            "weekend_notifications",
            "preferred_language",
            "digest_frequency",
            "updated_at",
        ]
        read_only_fields = ["user", "updated_at"]


class MessageThreadSerializer(serializers.ModelSerializer):
    """Serializer for message threads"""

    participants = UserBasicSerializer(many=True, read_only=True)
    created_by = UserBasicSerializer(read_only=True)
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()

    class Meta:
        model = MessageThread
        fields = [
            "id",
            "subject",
            "participants",
            "created_by",
            "created_at",
            "last_message_at",
            "is_group",
            "is_active",
            "thread_type",
            "reference_id",
            "reference_type",
            "last_message",
            "unread_count",
        ]
        read_only_fields = [
            "id",
            "created_by",
            "created_at",
            "last_message_at",
            "last_message",
            "unread_count",
        ]

    def get_last_message(self, obj):
        """Get the last message in the thread"""
        last_message = obj.messages.last()
        if last_message:
            return {
                "id": last_message.id,
                "sender": last_message.sender.get_full_name(),
                "content": (
                    last_message.content[:100] + "..."
                    if len(last_message.content) > 100
                    else last_message.content
                ),
                "sent_at": last_message.sent_at,
            }
        return None

    def get_unread_count(self, obj):
        """Get unread message count for current user"""
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            user = request.user
            thread_messages = obj.messages.exclude(sender=user)
            read_messages = MessageRead.objects.filter(
                user=user, message__in=thread_messages
            )
            return thread_messages.count() - read_messages.count()
        return 0


class DirectMessageSerializer(serializers.ModelSerializer):
    """Serializer for direct messages"""

    sender = UserBasicSerializer(read_only=True)
    is_read_by_user = serializers.SerializerMethodField()

    class Meta:
        model = DirectMessage
        fields = [
            "id",
            "sender",
            "content",
            "attachment",
            "attachment_type",
            "sent_at",
            "edited_at",
            "is_edited",
            "is_system_message",
            "is_read_by_user",
        ]
        read_only_fields = [
            "id",
            "sender",
            "sent_at",
            "edited_at",
            "is_edited",
            "is_system_message",
            "is_read_by_user",
        ]

    def get_is_read_by_user(self, obj):
        """Check if message is read by current user"""
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            return MessageRead.objects.filter(user=request.user, message=obj).exists()
        return False


class MessageThreadCreateSerializer(serializers.Serializer):
    """Serializer for creating message threads"""

    subject = serializers.CharField(max_length=200)
    participant_ids = serializers.ListField(
        child=serializers.IntegerField(), min_length=1
    )
    is_group = serializers.BooleanField(default=False)
    thread_type = serializers.CharField(max_length=50, default="general")
    initial_message = serializers.CharField(required=False)

    def validate_participant_ids(self, value):
        """Validate that all participant IDs exist"""
        existing_users = User.objects.filter(id__in=value).count()
        if existing_users != len(value):
            raise serializers.ValidationError("Some participant IDs do not exist")
        return value


class DirectMessageCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating direct messages"""

    class Meta:
        model = DirectMessage
        fields = ["content", "attachment"]


class CommunicationAnalyticsSerializer(serializers.ModelSerializer):
    """Serializer for communication analytics"""

    class Meta:
        model = CommunicationAnalytics
        fields = [
            "id",
            "date",
            "month",
            "year",
            "total_emails_sent",
            "total_sms_sent",
            "total_push_sent",
            "total_announcements",
            "email_delivery_rate",
            "sms_delivery_rate",
            "push_delivery_rate",
            "email_open_rate",
            "email_click_rate",
            "notification_read_rate",
            "email_cost",
            "sms_cost",
            "total_cost",
            "student_messages",
            "parent_messages",
            "teacher_messages",
            "staff_messages",
            "calculated_at",
        ]
        read_only_fields = fields


class CommunicationSummarySerializer(serializers.Serializer):
    """Serializer for communication summary data"""

    total_emails = serializers.IntegerField()
    total_sms = serializers.IntegerField()
    total_push = serializers.IntegerField()
    total_announcements = serializers.IntegerField()
    avg_email_delivery_rate = serializers.DecimalField(max_digits=5, decimal_places=2)
    avg_sms_delivery_rate = serializers.DecimalField(max_digits=5, decimal_places=2)
    avg_read_rate = serializers.DecimalField(max_digits=5, decimal_places=2)
    total_cost = serializers.DecimalField(max_digits=10, decimal_places=2)


class UserEngagementStatsSerializer(serializers.Serializer):
    """Serializer for user engagement statistics"""

    total_notifications = serializers.IntegerField()
    unread_notifications = serializers.IntegerField()
    read_rate = serializers.DecimalField(max_digits=5, decimal_places=2)
    last_activity = serializers.DateTimeField(allow_null=True)
    preferred_channels = CommunicationPreferenceSerializer(allow_null=True)


class CommunicationLogSerializer(serializers.ModelSerializer):
    """Serializer for communication logs"""

    sender = UserBasicSerializer(read_only=True)
    recipient = UserBasicSerializer(read_only=True)

    class Meta:
        model = CommunicationLog
        fields = [
            "id",
            "event_type",
            "channel",
            "status",
            "sender",
            "recipient",
            "content_type",
            "content_id",
            "metadata",
            "error_details",
            "timestamp",
            "processed_at",
        ]
        read_only_fields = fields


class BulkNotificationSerializer(serializers.Serializer):
    """Serializer for bulk notification operations"""

    user_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        help_text="Specific user IDs (optional if using filters)",
    )
    target_audience = serializers.ChoiceField(
        choices=TargetAudience.choices, required=False, help_text="Target audience type"
    )
    target_filters = serializers.DictField(
        required=False, help_text="Additional filtering criteria"
    )
    title = serializers.CharField(max_length=200)
    content = serializers.CharField()
    notification_type = serializers.CharField(max_length=50)
    priority = serializers.ChoiceField(
        choices=Priority.choices, default=Priority.MEDIUM
    )
    channels = serializers.ListField(
        child=serializers.ChoiceField(choices=CommunicationChannel.choices),
        default=[CommunicationChannel.IN_APP],
    )
    scheduled_at = serializers.DateTimeField(required=False)

    def validate(self, data):
        """Validate bulk notification data"""
        if not data.get("user_ids") and not data.get("target_audience"):
            raise serializers.ValidationError(
                "Either user_ids or target_audience must be provided"
            )
        return data


class MessageMarkAsReadSerializer(serializers.Serializer):
    """Serializer for marking messages as read"""

    message_ids = serializers.ListField(
        child=serializers.UUIDField(), help_text="List of message IDs to mark as read"
    )

    def validate_message_ids(self, value):
        """Validate that all message IDs exist"""
        existing_messages = DirectMessage.objects.filter(id__in=value).count()
        if existing_messages != len(value):
            raise serializers.ValidationError("Some message IDs do not exist")
        return value


class NotificationMarkAsReadSerializer(serializers.Serializer):
    """Serializer for marking notifications as read"""

    notification_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        help_text="List of notification IDs to mark as read (optional - marks all if empty)",
    )
