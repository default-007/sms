"""
URL patterns for Communications module.
Defines web interface URLs for notifications, announcements, messaging, and analytics.
"""

from django.urls import include, path

from . import views

# App namespace
app_name = "communications"

urlpatterns = [
    # Dashboard and Overview
    path("", views.communications_dashboard, name="dashboard"),
    path("notifications/", views.notifications_overview, name="notifications_overview"),
    # Announcements
    path(
        "announcements/", views.AnnouncementListView.as_view(), name="announcement_list"
    ),
    path(
        "announcements/create/",
        views.AnnouncementCreateView.as_view(),
        name="announcement_create",
    ),
    path(
        "announcements/<uuid:pk>/",
        views.AnnouncementDetailView.as_view(),
        name="announcement_detail",
    ),
    path(
        "announcements/<uuid:pk>/edit/",
        views.AnnouncementUpdateView.as_view(),
        name="announcement_edit",
    ),
    # Direct Messaging
    path("messages/", views.MessageThreadListView.as_view(), name="thread_list"),
    path(
        "messages/new/", views.MessageThreadCreateView.as_view(), name="thread_create"
    ),
    path(
        "messages/<uuid:pk>/",
        views.MessageThreadDetailView.as_view(),
        name="thread_detail",
    ),
    # Message Templates
    path("templates/", views.MessageTemplateListView.as_view(), name="template_list"),
    path(
        "templates/create/",
        views.MessageTemplateCreateView.as_view(),
        name="template_create",
    ),
    # Bulk Messaging
    path("bulk/", views.BulkMessageListView.as_view(), name="bulk_message_list"),
    path(
        "bulk/create/",
        views.BulkMessageCreateView.as_view(),
        name="bulk_message_create",
    ),
    # Quick Actions
    path("quick/notification/", views.quick_notification, name="quick_notification"),
    path("quick/bulk/", views.bulk_notification, name="bulk_notification"),
    # Preferences
    path("preferences/", views.communication_preferences, name="preferences"),
    # Analytics (Staff only)
    path("analytics/", views.analytics_dashboard, name="analytics_dashboard"),
    path("analytics/export/", views.export_analytics, name="export_analytics"),
    # Search
    path("search/", views.communication_search, name="search"),
    # AJAX Endpoints
    path(
        "ajax/notification/<uuid:notification_id>/read/",
        views.mark_notification_read,
        name="mark_notification_read",
    ),
    path(
        "ajax/notifications/read-all/",
        views.mark_all_notifications_read,
        name="mark_all_notifications_read",
    ),
    path("ajax/unread-counts/", views.get_unread_counts, name="get_unread_counts"),
    path("ajax/search-users/", views.search_users, name="search_users"),
    path(
        "ajax/template/<uuid:template_id>/preview/",
        views.template_preview,
        name="template_preview",
    ),
    # API URLs
    path("api/", include("src.communications.api.urls")),
]
