"""
API URL patterns for Communications module.
Defines REST API endpoints for notifications, announcements, messaging, and analytics.
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AnnouncementViewSet,
    BulkMessageViewSet,
    CommunicationAnalyticsViewSet,
    CommunicationLogViewSet,
    CommunicationPreferenceViewSet,
    CommunicationUtilityViewSet,
    MessageTemplateViewSet,
    MessageThreadViewSet,
    NotificationViewSet,
)

# Create router for ViewSets
router = DefaultRouter()

# Register ViewSets
router.register(r"notifications", NotificationViewSet, basename="notification")
router.register(r"announcements", AnnouncementViewSet, basename="announcement")
router.register(r"templates", MessageTemplateViewSet, basename="template")
router.register(r"bulk-messages", BulkMessageViewSet, basename="bulk-message")
router.register(r"threads", MessageThreadViewSet, basename="thread")
router.register(r"preferences", CommunicationPreferenceViewSet, basename="preference")
router.register(r"analytics", CommunicationAnalyticsViewSet, basename="analytics")
router.register(r"logs", CommunicationLogViewSet, basename="log")
router.register(r"utils", CommunicationUtilityViewSet, basename="utils")

# URL patterns
urlpatterns = [
    # Include router URLs
    path("", include(router.urls)),
    # Additional custom endpoints can be added here
    # path('custom-endpoint/', custom_view, name='custom-endpoint'),
]

# Namespace for the app
app_name = "communications"
