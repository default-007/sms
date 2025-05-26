"""
Communications app models for School Management System.
Handles announcements, notifications, messaging, and communication analytics.
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import EmailValidator, RegexValidator
from django.utils import timezone
from django.contrib.postgres.fields import JSONField
import uuid

User = get_user_model()


class CommunicationChannel(models.TextChoices):
    """Communication channel types"""

    EMAIL = "email", "Email"
    SMS = "sms", "SMS"
    PUSH = "push", "Push Notification"
    IN_APP = "in_app", "In-App Notification"
    WHATSAPP = "whatsapp", "WhatsApp"


class Priority(models.TextChoices):
    """Priority levels"""

    LOW = "low", "Low"
    MEDIUM = "medium", "Medium"
    HIGH = "high", "High"
    URGENT = "urgent", "Urgent"


class MessageStatus(models.TextChoices):
    """Message delivery status"""

    DRAFT = "draft", "Draft"
    SCHEDULED = "scheduled", "Scheduled"
    SENDING = "sending", "Sending"
    SENT = "sent", "Sent"
    DELIVERED = "delivered", "Delivered"
    READ = "read", "Read"
    FAILED = "failed", "Failed"
    CANCELLED = "cancelled", "Cancelled"


class TargetAudience(models.TextChoices):
    """Target audience types"""

    ALL = "all", "All Users"
    STUDENTS = "students", "Students"
    TEACHERS = "teachers", "Teachers"
    PARENTS = "parents", "Parents"
    STAFF = "staff", "Staff"
    CUSTOM = "custom", "Custom Selection"


class Announcement(models.Model):
    """School announcements and notifications"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200)
    content = models.TextField()
    created_by = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="created_announcements"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Targeting
    target_audience = models.CharField(
        max_length=20, choices=TargetAudience.choices, default=TargetAudience.ALL
    )
    target_grades = JSONField(default=list, blank=True, help_text="List of grade IDs")
    target_classes = JSONField(default=list, blank=True, help_text="List of class IDs")
    target_sections = JSONField(
        default=list, blank=True, help_text="List of section IDs"
    )
    target_users = models.ManyToManyField(
        User, blank=True, related_name="targeted_announcements"
    )

    # Scheduling
    start_date = models.DateTimeField(default=timezone.now)
    end_date = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    # Properties
    attachment = models.FileField(
        upload_to="announcements/attachments/", null=True, blank=True
    )
    priority = models.CharField(
        max_length=10, choices=Priority.choices, default=Priority.MEDIUM
    )
    channels = JSONField(default=list, help_text="List of communication channels")

    # Analytics
    total_recipients = models.PositiveIntegerField(default=0)
    total_sent = models.PositiveIntegerField(default=0)
    total_delivered = models.PositiveIntegerField(default=0)
    total_read = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["target_audience", "is_active"]),
            models.Index(fields=["start_date", "end_date"]),
            models.Index(fields=["created_by", "-created_at"]),
        ]

    def __str__(self):
        return self.title

    @property
    def is_current(self):
        """Check if announcement is currently active"""
        now = timezone.now()
        if not self.is_active:
            return False
        if self.start_date > now:
            return False
        if self.end_date and self.end_date < now:
            return False
        return True

    @property
    def read_rate(self):
        """Calculate read rate percentage"""
        if self.total_sent == 0:
            return 0
        return round((self.total_read / self.total_sent) * 100, 2)

    @property
    def delivery_rate(self):
        """Calculate delivery rate percentage"""
        if self.total_sent == 0:
            return 0
        return round((self.total_delivered / self.total_sent) * 100, 2)


class Notification(models.Model):
    """Individual user notifications"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="notifications"
    )
    title = models.CharField(max_length=200)
    content = models.TextField()
    notification_type = models.CharField(max_length=50)

    # Reference to related objects
    reference_id = models.CharField(max_length=100, null=True, blank=True)
    reference_type = models.CharField(max_length=50, null=True, blank=True)

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    priority = models.CharField(
        max_length=10, choices=Priority.choices, default=Priority.MEDIUM
    )

    # Delivery tracking
    channels_used = JSONField(default=list)
    delivery_status = JSONField(default=dict)

    # Related announcement
    announcement = models.ForeignKey(
        Announcement,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="notifications",
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "is_read"]),
            models.Index(fields=["notification_type", "-created_at"]),
            models.Index(fields=["priority", "-created_at"]),
            models.Index(fields=["user", "notification_type"]),
        ]

    def __str__(self):
        return f"{self.title} - {self.user.get_full_name()}"

    def mark_as_read(self):
        """Mark notification as read"""
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=["is_read", "read_at"])


class MessageTemplate(models.Model):
    """Reusable message templates"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    template_type = models.CharField(max_length=50)

    # Template content
    subject_template = models.CharField(max_length=200, blank=True)
    content_template = models.TextField()

    # Supported channels
    supported_channels = JSONField(default=list)

    # Variables and placeholders
    variables = JSONField(default=dict, help_text="Available template variables")

    # Metadata
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def render_content(self, context=None):
        """Render template with provided context"""
        if context is None:
            context = {}

        try:
            from django.template import Template, Context

            template = Template(self.content_template)
            return template.render(Context(context))
        except Exception:
            return self.content_template

    def render_subject(self, context=None):
        """Render subject template with provided context"""
        if context is None:
            context = {}

        try:
            from django.template import Template, Context

            template = Template(self.subject_template)
            return template.render(Context(context))
        except Exception:
            return self.subject_template


class BulkMessage(models.Model):
    """Bulk messaging campaigns"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)

    # Message content
    subject = models.CharField(max_length=200, blank=True)
    content = models.TextField()
    template = models.ForeignKey(
        MessageTemplate, on_delete=models.SET_NULL, null=True, blank=True
    )

    # Targeting
    target_audience = models.CharField(max_length=20, choices=TargetAudience.choices)
    target_filters = JSONField(default=dict, help_text="Advanced filtering criteria")
    recipient_count = models.PositiveIntegerField(default=0)

    # Scheduling
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    scheduled_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    # Status and analytics
    status = models.CharField(
        max_length=20, choices=MessageStatus.choices, default=MessageStatus.DRAFT
    )
    channels = JSONField(default=list)
    priority = models.CharField(
        max_length=10, choices=Priority.choices, default=Priority.MEDIUM
    )

    # Delivery metrics
    total_recipients = models.PositiveIntegerField(default=0)
    successful_deliveries = models.PositiveIntegerField(default=0)
    failed_deliveries = models.PositiveIntegerField(default=0)
    bounced_deliveries = models.PositiveIntegerField(default=0)
    opened_count = models.PositiveIntegerField(default=0)
    clicked_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "-created_at"]),
            models.Index(fields=["created_by", "-created_at"]),
        ]

    def __str__(self):
        return self.name

    @property
    def delivery_rate(self):
        """Calculate delivery success rate"""
        if self.total_recipients == 0:
            return 0
        return round((self.successful_deliveries / self.total_recipients) * 100, 2)

    @property
    def open_rate(self):
        """Calculate open rate for emails"""
        if self.successful_deliveries == 0:
            return 0
        return round((self.opened_count / self.successful_deliveries) * 100, 2)


class MessageRecipient(models.Model):
    """Individual message recipients and delivery tracking"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    bulk_message = models.ForeignKey(
        BulkMessage, on_delete=models.CASCADE, related_name="recipients"
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    # Contact info used
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)

    # Delivery tracking per channel
    email_status = models.CharField(
        max_length=20, choices=MessageStatus.choices, default=MessageStatus.DRAFT
    )
    sms_status = models.CharField(
        max_length=20, choices=MessageStatus.choices, default=MessageStatus.DRAFT
    )
    push_status = models.CharField(
        max_length=20, choices=MessageStatus.choices, default=MessageStatus.DRAFT
    )

    # Timestamps
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    opened_at = models.DateTimeField(null=True, blank=True)
    clicked_at = models.DateTimeField(null=True, blank=True)
    bounced_at = models.DateTimeField(null=True, blank=True)

    # Error tracking
    error_message = models.TextField(blank=True)
    retry_count = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ["bulk_message", "user"]
        indexes = [
            models.Index(fields=["bulk_message", "email_status"]),
            models.Index(fields=["bulk_message", "sms_status"]),
        ]

    def __str__(self):
        return f"{self.bulk_message.name} - {self.user.get_full_name()}"


class CommunicationPreference(models.Model):
    """User communication preferences"""

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="communication_preferences"
    )

    # Channel preferences
    email_enabled = models.BooleanField(default=True)
    sms_enabled = models.BooleanField(default=True)
    push_enabled = models.BooleanField(default=True)
    whatsapp_enabled = models.BooleanField(default=False)

    # Notification types
    academic_notifications = models.BooleanField(default=True)
    financial_notifications = models.BooleanField(default=True)
    attendance_notifications = models.BooleanField(default=True)
    general_announcements = models.BooleanField(default=True)
    marketing_messages = models.BooleanField(default=False)

    # Timing preferences
    quiet_hours_start = models.TimeField(default="22:00")
    quiet_hours_end = models.TimeField(default="08:00")
    weekend_notifications = models.BooleanField(default=False)

    # Language and format
    preferred_language = models.CharField(max_length=10, default="en")
    digest_frequency = models.CharField(
        max_length=20,
        choices=[
            ("immediate", "Immediate"),
            ("hourly", "Hourly"),
            ("daily", "Daily"),
            ("weekly", "Weekly"),
        ],
        default="immediate",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Preferences for {self.user.get_full_name()}"


class CommunicationAnalytics(models.Model):
    """Communication analytics and metrics"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Time period
    date = models.DateField()
    month = models.PositiveIntegerField()
    year = models.PositiveIntegerField()

    # Channel metrics
    total_emails_sent = models.PositiveIntegerField(default=0)
    total_sms_sent = models.PositiveIntegerField(default=0)
    total_push_sent = models.PositiveIntegerField(default=0)
    total_announcements = models.PositiveIntegerField(default=0)

    # Delivery metrics
    email_delivery_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    sms_delivery_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    push_delivery_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    # Engagement metrics
    email_open_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    email_click_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    notification_read_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=0
    )

    # Cost metrics
    email_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    sms_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    # Audience breakdown
    student_messages = models.PositiveIntegerField(default=0)
    parent_messages = models.PositiveIntegerField(default=0)
    teacher_messages = models.PositiveIntegerField(default=0)
    staff_messages = models.PositiveIntegerField(default=0)

    calculated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ["date"]
        indexes = [
            models.Index(fields=["year", "month"]),
            models.Index(fields=["date"]),
        ]

    def __str__(self):
        return f"Communication Analytics for {self.date}"


class MessageThread(models.Model):
    """Message thread for conversations"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    subject = models.CharField(max_length=200)
    participants = models.ManyToManyField(User, related_name="message_threads")
    created_by = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="created_threads"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    last_message_at = models.DateTimeField(auto_now_add=True)
    is_group = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    # Context
    thread_type = models.CharField(max_length=50, default="general")
    reference_id = models.CharField(max_length=100, null=True, blank=True)
    reference_type = models.CharField(max_length=50, null=True, blank=True)

    class Meta:
        ordering = ["-last_message_at"]

    def __str__(self):
        return self.subject


class DirectMessage(models.Model):
    """Individual messages within a thread"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    thread = models.ForeignKey(
        MessageThread, on_delete=models.CASCADE, related_name="messages"
    )
    sender = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="sent_messages"
    )
    content = models.TextField()

    # Attachments
    attachment = models.FileField(
        upload_to="messages/attachments/", null=True, blank=True
    )
    attachment_type = models.CharField(max_length=50, blank=True)

    # Timestamps
    sent_at = models.DateTimeField(auto_now_add=True)
    edited_at = models.DateTimeField(null=True, blank=True)

    # Status
    is_edited = models.BooleanField(default=False)
    is_system_message = models.BooleanField(default=False)

    class Meta:
        ordering = ["sent_at"]

    def __str__(self):
        return f"Message from {self.sender.get_full_name()} at {self.sent_at}"


class MessageRead(models.Model):
    """Message read receipts"""

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    message = models.ForeignKey(
        DirectMessage, on_delete=models.CASCADE, related_name="read_receipts"
    )
    read_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ["user", "message"]

    def __str__(self):
        return f"{self.user.get_full_name()} read message at {self.read_at}"


class CommunicationLog(models.Model):
    """Log of all communication activities"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Event details
    event_type = models.CharField(max_length=50)
    channel = models.CharField(max_length=20, choices=CommunicationChannel.choices)
    status = models.CharField(max_length=20, choices=MessageStatus.choices)

    # Participants
    sender = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="sent_communications"
    )
    recipient = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="received_communications",
    )

    # Content reference
    content_type = models.CharField(max_length=50)
    content_id = models.CharField(max_length=100)

    # Metadata
    metadata = JSONField(default=dict)
    error_details = models.TextField(blank=True)

    # Timing
    timestamp = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["event_type", "-timestamp"]),
            models.Index(fields=["channel", "status"]),
            models.Index(fields=["recipient", "-timestamp"]),
        ]

    def __str__(self):
        return f"{self.event_type} via {self.channel} at {self.timestamp}"
