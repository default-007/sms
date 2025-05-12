from django.urls import path
from . import views

app_name = "communications"

urlpatterns = [
    # Announcement URLs
    path(
        "announcements/", views.AnnouncementListView.as_view(), name="announcement-list"
    ),
    path(
        "announcements/<int:pk>/",
        views.AnnouncementDetailView.as_view(),
        name="announcement-detail",
    ),
    path(
        "announcements/create/",
        views.AnnouncementCreateView.as_view(),
        name="announcement-create",
    ),
    path(
        "announcements/<int:pk>/update/",
        views.AnnouncementUpdateView.as_view(),
        name="announcement-update",
    ),
    path(
        "announcements/<int:pk>/delete/",
        views.AnnouncementDeleteView.as_view(),
        name="announcement-delete",
    ),
    # Message URLs
    path("messages/", views.MessageListView.as_view(), name="message-list"),
    path(
        "messages/<int:pk>/", views.MessageDetailView.as_view(), name="message-detail"
    ),
    path("messages/create/", views.MessageCreateView.as_view(), name="message-create"),
    path("messages/bulk/", views.bulk_message_view, name="message-bulk"),
    # Notification URLs
    path(
        "notifications/", views.NotificationListView.as_view(), name="notification-list"
    ),
    path(
        "notifications/<int:pk>/mark-read/",
        views.mark_notification_read,
        name="notification-mark-read",
    ),
    path(
        "notifications/mark-all-read/",
        views.mark_all_notifications_read,
        name="notification-mark-all-read",
    ),
    # Log URLs
    path("logs/sms/", views.sms_log_list_view, name="sms-log-list"),
    path("logs/email/", views.email_log_list_view, name="email-log-list"),
]
