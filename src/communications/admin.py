from django.contrib import admin
from .models import Announcement, Message, Notification, SMSLog, EmailLog


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "created_by",
        "target_audience",
        "start_date",
        "end_date",
        "is_active",
    )
    list_filter = ("target_audience", "is_active", "start_date")
    search_fields = ("title", "content", "created_by__username")
    date_hierarchy = "created_at"


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("subject", "sender", "receiver", "sent_at", "is_read")
    list_filter = ("is_read", "sent_at")
    search_fields = ("subject", "content", "sender__username", "receiver__username")
    date_hierarchy = "sent_at"


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("title", "user", "notification_type", "created_at", "is_read")
    list_filter = ("is_read", "notification_type", "priority", "created_at")
    search_fields = ("title", "content", "user__username")
    date_hierarchy = "created_at"


@admin.register(SMSLog)
class SMSLogAdmin(admin.ModelAdmin):
    list_display = ("recipient_number", "sent_at", "status")
    list_filter = ("status", "sent_at")
    search_fields = ("recipient_number", "content", "recipient_user__username")
    date_hierarchy = "sent_at"


@admin.register(EmailLog)
class EmailLogAdmin(admin.ModelAdmin):
    list_display = ("recipient_email", "subject", "sent_at", "status")
    list_filter = ("status", "sent_at")
    search_fields = (
        "recipient_email",
        "subject",
        "content",
        "recipient_user__username",
    )
    date_hierarchy = "sent_at"
