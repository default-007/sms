"""
Django admin configuration for Communications module.
Provides admin interface for managing communications, notifications, and analytics.
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.db.models import Count, Avg
from django.utils import timezone
from datetime import timedelta

from .models import (
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
)


class BaseReadOnlyAdmin(admin.ModelAdmin):
    """Base class for read-only admin interfaces"""

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    """Admin interface for announcements"""

    list_display = [
        "title",
        "created_by",
        "target_audience",
        "priority",
        "is_active",
        "total_recipients",
        "read_rate_display",
        "created_at",
    ]
    list_filter = [
        "target_audience",
        "priority",
        "is_active",
        "channels",
        "created_at",
        "start_date",
    ]
    search_fields = ["title", "content", "created_by__username"]
    readonly_fields = [
        "id",
        "created_at",
        "updated_at",
        "total_recipients",
        "total_sent",
        "total_delivered",
        "total_read",
        "read_rate_display",
        "delivery_rate_display",
    ]
    filter_horizontal = ["target_users"]

    fieldsets = (
        (
            "Basic Information",
            {"fields": ("title", "content", "attachment", "priority")},
        ),
        (
            "Targeting",
            {
                "fields": (
                    "target_audience",
                    "target_sections",
                    "target_grades",
                    "target_classes",
                    "target_users",
                )
            },
        ),
        ("Scheduling", {"fields": ("start_date", "end_date", "is_active")}),
        ("Delivery", {"fields": ("channels",)}),
        (
            "Analytics",
            {
                "fields": (
                    "total_recipients",
                    "total_sent",
                    "total_delivered",
                    "total_read",
                    "read_rate_display",
                    "delivery_rate_display",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Metadata",
            {"fields": ("id", "created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    def read_rate_display(self, obj):
        """Display read rate with color coding"""
        rate = obj.read_rate
        if rate >= 80:
            color = "green"
        elif rate >= 60:
            color = "orange"
        else:
            color = "red"
        return format_html('<span style="color: {};">{:.1f}%</span>', color, rate)

    read_rate_display.short_description = "Read Rate"

    def delivery_rate_display(self, obj):
        """Display delivery rate with color coding"""
        rate = obj.delivery_rate
        if rate >= 95:
            color = "green"
        elif rate >= 85:
            color = "orange"
        else:
            color = "red"
        return format_html('<span style="color: {};">{:.1f}%</span>', color, rate)

    delivery_rate_display.short_description = "Delivery Rate"

    def save_model(self, request, obj, form, change):
        """Set created_by when saving"""
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    """Admin interface for notifications"""

    list_display = [
        "title",
        "user",
        "notification_type",
        "priority",
        "is_read",
        "created_at",
    ]
    list_filter = [
        "notification_type",
        "priority",
        "is_read",
        "created_at",
        "channels_used",
    ]
    search_fields = ["title", "content", "user__username", "user__email"]
    readonly_fields = ["id", "created_at", "read_at", "delivery_status"]

    fieldsets = (
        ("Content", {"fields": ("title", "content", "notification_type", "priority")}),
        ("Target", {"fields": ("user",)}),
        (
            "Reference",
            {"fields": ("reference_id", "reference_type"), "classes": ("collapse",)},
        ),
        (
            "Delivery",
            {"fields": ("channels_used", "delivery_status"), "classes": ("collapse",)},
        ),
        ("Status", {"fields": ("is_read", "read_at"), "classes": ("collapse",)}),
        ("Metadata", {"fields": ("id", "created_at"), "classes": ("collapse",)}),
    )

    def has_add_permission(self, request):
        return False


@admin.register(MessageTemplate)
class MessageTemplateAdmin(admin.ModelAdmin):
    """Admin interface for message templates"""

    list_display = [
        "name",
        "template_type",
        "created_by",
        "is_active",
        "supported_channels_display",
        "created_at",
    ]
    list_filter = ["template_type", "is_active", "supported_channels"]
    search_fields = ["name", "description", "template_type"]
    readonly_fields = ["id", "created_by", "created_at", "updated_at"]

    fieldsets = (
        (
            "Basic Information",
            {"fields": ("name", "description", "template_type", "is_active")},
        ),
        ("Template Content", {"fields": ("subject_template", "content_template")}),
        ("Configuration", {"fields": ("supported_channels", "variables")}),
        (
            "Metadata",
            {
                "fields": ("id", "created_by", "created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    def supported_channels_display(self, obj):
        """Display supported channels as badges"""
        if not obj.supported_channels:
            return "-"

        badges = []
        for channel in obj.supported_channels:
            badges.append(f'<span class="badge">{channel}</span>')
        return mark_safe(" ".join(badges))

    supported_channels_display.short_description = "Channels"

    def save_model(self, request, obj, form, change):
        """Set created_by when saving"""
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(BulkMessage)
class BulkMessageAdmin(admin.ModelAdmin):
    """Admin interface for bulk messages"""

    list_display = [
        "name",
        "target_audience",
        "status",
        "total_recipients",
        "delivery_rate_display",
        "created_by",
        "created_at",
    ]
    list_filter = [
        "status",
        "target_audience",
        "priority",
        "channels",
        "created_at",
        "sent_at",
    ]
    search_fields = ["name", "description", "subject", "created_by__username"]
    readonly_fields = [
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
        "delivery_rate_display",
        "open_rate_display",
    ]

    fieldsets = (
        (
            "Basic Information",
            {"fields": ("name", "description", "status", "priority")},
        ),
        ("Content", {"fields": ("subject", "content", "template")}),
        ("Targeting", {"fields": ("target_audience", "target_filters")}),
        ("Delivery", {"fields": ("channels", "scheduled_at")}),
        (
            "Analytics",
            {
                "fields": (
                    "recipient_count",
                    "total_recipients",
                    "successful_deliveries",
                    "failed_deliveries",
                    "bounced_deliveries",
                    "opened_count",
                    "clicked_count",
                    "delivery_rate_display",
                    "open_rate_display",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Metadata",
            {
                "fields": ("id", "created_by", "created_at", "sent_at"),
                "classes": ("collapse",),
            },
        ),
    )

    def delivery_rate_display(self, obj):
        """Display delivery rate with color coding"""
        rate = obj.delivery_rate
        if rate >= 95:
            color = "green"
        elif rate >= 85:
            color = "orange"
        else:
            color = "red"
        return format_html('<span style="color: {};">{:.1f}%</span>', color, rate)

    delivery_rate_display.short_description = "Delivery Rate"

    def open_rate_display(self, obj):
        """Display open rate with color coding"""
        rate = obj.open_rate
        if rate >= 30:
            color = "green"
        elif rate >= 20:
            color = "orange"
        else:
            color = "red"
        return format_html('<span style="color: {};">{:.1f}%</span>', color, rate)

    open_rate_display.short_description = "Open Rate"

    def save_model(self, request, obj, form, change):
        """Set created_by when saving"""
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


class MessageRecipientInline(admin.TabularInline):
    """Inline for message recipients"""

    model = MessageRecipient
    extra = 0
    readonly_fields = [
        "user",
        "email",
        "phone",
        "email_status",
        "sms_status",
        "push_status",
        "sent_at",
        "delivered_at",
        "error_message",
    ]

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(MessageRecipient)
class MessageRecipientAdmin(BaseReadOnlyAdmin):
    """Admin interface for message recipients"""

    list_display = [
        "bulk_message",
        "user",
        "email_status",
        "sms_status",
        "push_status",
        "sent_at",
        "delivered_at",
    ]
    list_filter = [
        "email_status",
        "sms_status",
        "push_status",
        "sent_at",
        "delivered_at",
    ]
    search_fields = [
        "user__username",
        "user__email",
        "email",
        "phone",
        "bulk_message__name",
    ]


@admin.register(MessageThread)
class MessageThreadAdmin(admin.ModelAdmin):
    """Admin interface for message threads"""

    list_display = [
        "subject",
        "created_by",
        "is_group",
        "participant_count",
        "message_count",
        "last_message_at",
        "is_active",
    ]
    list_filter = [
        "is_group",
        "is_active",
        "thread_type",
        "created_at",
        "last_message_at",
    ]
    search_fields = ["subject", "created_by__username"]
    readonly_fields = [
        "id",
        "created_by",
        "created_at",
        "last_message_at",
        "participant_count",
        "message_count",
    ]
    filter_horizontal = ["participants"]

    fieldsets = (
        (
            "Basic Information",
            {"fields": ("subject", "thread_type", "is_group", "is_active")},
        ),
        ("Participants", {"fields": ("participants",)}),
        (
            "Reference",
            {"fields": ("reference_id", "reference_type"), "classes": ("collapse",)},
        ),
        (
            "Statistics",
            {
                "fields": ("participant_count", "message_count"),
                "classes": ("collapse",),
            },
        ),
        (
            "Metadata",
            {
                "fields": ("id", "created_by", "created_at", "last_message_at"),
                "classes": ("collapse",),
            },
        ),
    )

    def participant_count(self, obj):
        """Get number of participants"""
        return obj.participants.count()

    participant_count.short_description = "Participants"

    def message_count(self, obj):
        """Get number of messages"""
        return obj.messages.count()

    message_count.short_description = "Messages"

    def save_model(self, request, obj, form, change):
        """Set created_by when saving"""
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


class DirectMessageInline(admin.TabularInline):
    """Inline for direct messages"""

    model = DirectMessage
    extra = 0
    readonly_fields = ["sender", "content", "sent_at", "is_edited"]
    fields = ["sender", "content", "sent_at", "is_edited"]

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(DirectMessage)
class DirectMessageAdmin(BaseReadOnlyAdmin):
    """Admin interface for direct messages"""

    list_display = [
        "thread",
        "sender",
        "content_preview",
        "sent_at",
        "is_edited",
        "is_system_message",
    ]
    list_filter = ["is_edited", "is_system_message", "sent_at", "thread__thread_type"]
    search_fields = ["content", "sender__username", "thread__subject"]

    def content_preview(self, obj):
        """Show preview of message content"""
        return obj.content[:50] + "..." if len(obj.content) > 50 else obj.content

    content_preview.short_description = "Content"


@admin.register(CommunicationPreference)
class CommunicationPreferenceAdmin(admin.ModelAdmin):
    """Admin interface for communication preferences"""

    list_display = [
        "user",
        "email_enabled",
        "sms_enabled",
        "push_enabled",
        "digest_frequency",
        "updated_at",
    ]
    list_filter = [
        "email_enabled",
        "sms_enabled",
        "push_enabled",
        "academic_notifications",
        "financial_notifications",
        "digest_frequency",
        "preferred_language",
    ]
    search_fields = ["user__username", "user__email"]
    readonly_fields = ["updated_at"]

    fieldsets = (
        ("User", {"fields": ("user",)}),
        (
            "Channel Preferences",
            {
                "fields": (
                    "email_enabled",
                    "sms_enabled",
                    "push_enabled",
                    "whatsapp_enabled",
                )
            },
        ),
        (
            "Notification Types",
            {
                "fields": (
                    "academic_notifications",
                    "financial_notifications",
                    "attendance_notifications",
                    "general_announcements",
                    "marketing_messages",
                )
            },
        ),
        (
            "Timing",
            {
                "fields": (
                    "quiet_hours_start",
                    "quiet_hours_end",
                    "weekend_notifications",
                )
            },
        ),
        ("Format", {"fields": ("preferred_language", "digest_frequency")}),
        ("Metadata", {"fields": ("updated_at",), "classes": ("collapse",)}),
    )


@admin.register(CommunicationAnalytics)
class CommunicationAnalyticsAdmin(BaseReadOnlyAdmin):
    """Admin interface for communication analytics"""

    list_display = [
        "date",
        "total_messages_sent",
        "avg_delivery_rate",
        "avg_read_rate",
        "total_cost",
        "calculated_at",
    ]
    list_filter = ["year", "month", "calculated_at"]
    search_fields = ["date"]

    fieldsets = (
        ("Period", {"fields": ("date", "month", "year")}),
        (
            "Volume Metrics",
            {
                "fields": (
                    "total_emails_sent",
                    "total_sms_sent",
                    "total_push_sent",
                    "total_announcements",
                )
            },
        ),
        (
            "Delivery Metrics",
            {
                "fields": (
                    "email_delivery_rate",
                    "sms_delivery_rate",
                    "push_delivery_rate",
                )
            },
        ),
        (
            "Engagement Metrics",
            {
                "fields": (
                    "email_open_rate",
                    "email_click_rate",
                    "notification_read_rate",
                )
            },
        ),
        ("Cost Metrics", {"fields": ("email_cost", "sms_cost", "total_cost")}),
        (
            "Audience Breakdown",
            {
                "fields": (
                    "student_messages",
                    "parent_messages",
                    "teacher_messages",
                    "staff_messages",
                ),
                "classes": ("collapse",),
            },
        ),
        ("Metadata", {"fields": ("calculated_at",), "classes": ("collapse",)}),
    )

    def total_messages_sent(self, obj):
        """Calculate total messages sent"""
        return obj.total_emails_sent + obj.total_sms_sent + obj.total_push_sent

    total_messages_sent.short_description = "Total Messages"

    def avg_delivery_rate(self, obj):
        """Calculate average delivery rate"""
        rates = [obj.email_delivery_rate, obj.sms_delivery_rate, obj.push_delivery_rate]
        non_zero_rates = [rate for rate in rates if rate > 0]
        return sum(non_zero_rates) / len(non_zero_rates) if non_zero_rates else 0

    avg_delivery_rate.short_description = "Avg Delivery Rate"

    def avg_read_rate(self, obj):
        """Display notification read rate"""
        return f"{obj.notification_read_rate:.1f}%"

    avg_read_rate.short_description = "Read Rate"


@admin.register(CommunicationLog)
class CommunicationLogAdmin(BaseReadOnlyAdmin):
    """Admin interface for communication logs"""

    list_display = [
        "timestamp",
        "event_type",
        "channel",
        "status",
        "sender",
        "recipient",
        "content_type",
    ]
    list_filter = [
        "event_type",
        "channel",
        "status",
        "content_type",
        "timestamp",
        "processed_at",
    ]
    search_fields = [
        "sender__username",
        "recipient__username",
        "content_id",
        "event_type",
    ]
    date_hierarchy = "timestamp"

    fieldsets = (
        ("Event Details", {"fields": ("event_type", "channel", "status", "timestamp")}),
        ("Participants", {"fields": ("sender", "recipient")}),
        ("Content Reference", {"fields": ("content_type", "content_id")}),
        (
            "Additional Data",
            {
                "fields": ("metadata", "error_details", "processed_at"),
                "classes": ("collapse",),
            },
        ),
    )


# Custom admin site modifications
class CommunicationAdminSite(admin.AdminSite):
    """Custom admin site for communications"""

    site_header = "Communications Administration"
    site_title = "Communications Admin"
    index_title = "Communication Management"


# Register admin actions
def mark_announcements_active(modeladmin, request, queryset):
    """Mark selected announcements as active"""
    updated = queryset.update(is_active=True)
    modeladmin.message_user(request, f"{updated} announcements marked as active.")


mark_announcements_active.short_description = "Mark selected announcements as active"


def mark_announcements_inactive(modeladmin, request, queryset):
    """Mark selected announcements as inactive"""
    updated = queryset.update(is_active=False)
    modeladmin.message_user(request, f"{updated} announcements marked as inactive.")


mark_announcements_inactive.short_description = (
    "Mark selected announcements as inactive"
)


# Add actions to AnnouncementAdmin
AnnouncementAdmin.actions = [mark_announcements_active, mark_announcements_inactive]
