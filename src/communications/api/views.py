"""
API views for Communications module.
Handles REST API endpoints for notifications, announcements, messaging, and analytics.
"""

from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from django.db.models import Q, Count, Avg
from django.contrib.auth import get_user_model
from datetime import datetime, timedelta
import logging

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
from ..services import (
    NotificationService,
    AnnouncementService,
    MessagingService,
    EmailService,
    SMSService,
    CommunicationAnalyticsService,
)
from .serializers import (
    NotificationSerializer,
    NotificationCreateSerializer,
    AnnouncementSerializer,
    AnnouncementCreateSerializer,
    MessageTemplateSerializer,
    BulkMessageSerializer,
    BulkMessageCreateSerializer,
    MessageRecipientSerializer,
    CommunicationPreferenceSerializer,
    MessageThreadSerializer,
    DirectMessageSerializer,
    MessageThreadCreateSerializer,
    DirectMessageCreateSerializer,
    CommunicationAnalyticsSerializer,
    CommunicationSummarySerializer,
    UserEngagementStatsSerializer,
    CommunicationLogSerializer,
    BulkNotificationSerializer,
    MessageMarkAsReadSerializer,
    NotificationMarkAsReadSerializer,
)

User = get_user_model()
logger = logging.getLogger(__name__)


class StandardResultPagination(PageNumberPagination):
    """Standard pagination for communication endpoints"""

    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class NotificationViewSet(viewsets.ModelViewSet):
    """ViewSet for managing notifications"""

    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultPagination
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["notification_type", "priority", "is_read"]

    def get_queryset(self):
        """Get notifications for the current user"""
        return Notification.objects.filter(user=self.request.user).order_by(
            "-created_at"
        )

    @action(detail=False, methods=["post"])
    def create_notification(self, request):
        """Create notification(s) for specified users"""
        serializer = NotificationCreateSerializer(data=request.data)
        if serializer.is_valid():
            data = serializer.validated_data

            # Get target users
            if data.get("user_ids"):
                users = User.objects.filter(id__in=data["user_ids"])
            else:
                users = [request.user]  # Send to self if no users specified

            # Create notifications
            notifications = NotificationService.bulk_create_notifications(
                users=users,
                title=data["title"],
                content=data["content"],
                notification_type=data["notification_type"],
                priority=data["priority"],
                channels=data["channels"],
            )

            return Response(
                {
                    "message": f"Successfully created {len(notifications)} notifications",
                    "notification_count": len(notifications),
                },
                status=status.HTTP_201_CREATED,
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"])
    def mark_as_read(self, request, pk=None):
        """Mark a notification as read"""
        try:
            notification = self.get_object()
            success = NotificationService.mark_as_read(
                str(notification.id), request.user
            )

            if success:
                return Response({"message": "Notification marked as read"})
            else:
                return Response(
                    {"error": "Unable to mark notification as read"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        except Notification.DoesNotExist:
            return Response(
                {"error": "Notification not found"}, status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=False, methods=["post"])
    def mark_multiple_as_read(self, request):
        """Mark multiple notifications as read"""
        serializer = NotificationMarkAsReadSerializer(data=request.data)
        if serializer.is_valid():
            notification_ids = serializer.validated_data.get("notification_ids")

            if notification_ids:
                # Mark specific notifications as read
                notifications = Notification.objects.filter(
                    id__in=notification_ids, user=request.user, is_read=False
                )
            else:
                # Mark all unread notifications as read
                notifications = Notification.objects.filter(
                    user=request.user, is_read=False
                )

            updated_count = 0
            for notification in notifications:
                notification.mark_as_read()
                updated_count += 1

            return Response(
                {
                    "message": f"Marked {updated_count} notifications as read",
                    "updated_count": updated_count,
                }
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=["get"])
    def unread_count(self, request):
        """Get count of unread notifications"""
        count = NotificationService.get_unread_count(request.user)
        return Response({"unread_count": count})

    @action(detail=False, methods=["get"])
    def by_type(self, request):
        """Get notifications grouped by type"""
        notification_type = request.query_params.get("type")
        if not notification_type:
            return Response(
                {"error": "notification type parameter is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        notifications = NotificationService.get_user_notifications(
            user=request.user, notification_type=notification_type, limit=50
        )

        serializer = NotificationSerializer(notifications, many=True)
        return Response(serializer.data)


class AnnouncementViewSet(viewsets.ModelViewSet):
    """ViewSet for managing announcements"""

    queryset = Announcement.objects.all()
    pagination_class = StandardResultPagination
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["target_audience", "priority", "is_active"]

    def get_serializer_class(self):
        if self.action == "create":
            return AnnouncementCreateSerializer
        return AnnouncementSerializer

    def get_permissions(self):
        """Set permissions based on action"""
        if self.action in ["create", "update", "partial_update", "destroy"]:
            permission_classes = [
                permissions.IsAuthenticated
            ]  # Add role-based permissions
        else:
            permission_classes = [permissions.IsAuthenticated]
        return [permission() for permission in permission_classes]

    def perform_create(self, serializer):
        """Create announcement with current user as creator"""
        announcement = AnnouncementService.create_announcement(
            title=serializer.validated_data["title"],
            content=serializer.validated_data["content"],
            created_by=self.request.user,
            target_audience=serializer.validated_data.get(
                "target_audience", TargetAudience.ALL
            ),
            target_grades=serializer.validated_data.get("target_grades"),
            target_classes=serializer.validated_data.get("target_classes"),
            target_sections=serializer.validated_data.get("target_sections"),
            priority=serializer.validated_data.get("priority", Priority.MEDIUM),
            channels=serializer.validated_data.get(
                "channels", [CommunicationChannel.IN_APP]
            ),
            start_date=serializer.validated_data.get("start_date"),
            end_date=serializer.validated_data.get("end_date"),
            attachment=serializer.validated_data.get("attachment"),
        )
        serializer.instance = announcement

    @action(detail=False, methods=["get"])
    def active(self, request):
        """Get currently active announcements"""
        announcements = AnnouncementService.get_active_announcements(request.user)
        serializer = AnnouncementSerializer(announcements, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def update_metrics(self, request, pk=None):
        """Update announcement delivery metrics"""
        try:
            announcement = self.get_object()
            AnnouncementService.update_announcement_metrics(str(announcement.id))

            # Return updated announcement
            serializer = AnnouncementSerializer(announcement)
            return Response(serializer.data)

        except Announcement.DoesNotExist:
            return Response(
                {"error": "Announcement not found"}, status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=False, methods=["get"])
    def analytics(self, request):
        """Get announcement analytics"""
        days = int(request.query_params.get("days", 30))
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)

        announcements = Announcement.objects.filter(
            created_at__date__gte=start_date, created_at__date__lte=end_date
        )

        analytics = {
            "total_announcements": announcements.count(),
            "active_announcements": announcements.filter(is_active=True).count(),
            "avg_read_rate": announcements.aggregate(Avg("total_read"))[
                "total_read__avg"
            ]
            or 0,
            "total_recipients": announcements.aggregate(Count("total_recipients"))[
                "total_recipients"
            ]
            or 0,
            "by_priority": {
                priority[0]: announcements.filter(priority=priority[0]).count()
                for priority in Priority.choices
            },
            "by_audience": {
                audience[0]: announcements.filter(target_audience=audience[0]).count()
                for audience in TargetAudience.choices
            },
        }

        return Response(analytics)


class MessageTemplateViewSet(viewsets.ModelViewSet):
    """ViewSet for managing message templates"""

    queryset = MessageTemplate.objects.filter(is_active=True)
    serializer_class = MessageTemplateSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultPagination
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["template_type", "is_active"]

    def perform_create(self, serializer):
        """Set current user as template creator"""
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=["post"])
    def render_preview(self, request, pk=None):
        """Preview template with sample data"""
        template = self.get_object()
        sample_context = request.data.get("context", {})

        try:
            rendered_content = template.render_content(sample_context)
            rendered_subject = template.render_subject(sample_context)

            return Response({"subject": rendered_subject, "content": rendered_content})
        except Exception as e:
            return Response(
                {"error": f"Template rendering failed: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )


class BulkMessageViewSet(viewsets.ModelViewSet):
    """ViewSet for managing bulk messages"""

    queryset = BulkMessage.objects.all()
    pagination_class = StandardResultPagination
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["status", "target_audience", "priority"]

    def get_serializer_class(self):
        if self.action == "create":
            return BulkMessageCreateSerializer
        return BulkMessageSerializer

    def get_permissions(self):
        """Set permissions for bulk messaging"""
        permission_classes = [
            permissions.IsAuthenticated
        ]  # Add admin/staff permissions
        return [permission() for permission in permission_classes]

    def perform_create(self, serializer):
        """Create bulk message"""
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=["post"])
    def send(self, request, pk=None):
        """Send bulk message"""
        bulk_message = self.get_object()

        if bulk_message.status != MessageStatus.DRAFT:
            return Response(
                {"error": "Message can only be sent from draft status"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            # Update status
            bulk_message.status = MessageStatus.SENDING
            bulk_message.save(update_fields=["status"])

            # Queue for background processing
            from ..tasks import send_bulk_message_task

            send_bulk_message_task.delay(str(bulk_message.id))

            return Response(
                {
                    "message": "Bulk message queued for sending",
                    "status": bulk_message.status,
                }
            )

        except Exception as e:
            bulk_message.status = MessageStatus.FAILED
            bulk_message.save(update_fields=["status"])

            return Response(
                {"error": f"Failed to queue message: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=True, methods=["get"])
    def recipients(self, request, pk=None):
        """Get bulk message recipients"""
        bulk_message = self.get_object()
        recipients = MessageRecipient.objects.filter(bulk_message=bulk_message)

        # Apply filters
        status_filter = request.query_params.get("status")
        if status_filter:
            recipients = recipients.filter(email_status=status_filter)

        serializer = MessageRecipientSerializer(recipients, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def analytics(self, request, pk=None):
        """Get bulk message analytics"""
        bulk_message = self.get_object()

        analytics = {
            "delivery_rate": bulk_message.delivery_rate,
            "open_rate": bulk_message.open_rate,
            "total_recipients": bulk_message.total_recipients,
            "successful_deliveries": bulk_message.successful_deliveries,
            "failed_deliveries": bulk_message.failed_deliveries,
            "bounced_deliveries": bulk_message.bounced_deliveries,
            "opened_count": bulk_message.opened_count,
            "clicked_count": bulk_message.clicked_count,
            "by_channel": {
                "email": MessageRecipient.objects.filter(
                    bulk_message=bulk_message, email_status=MessageStatus.SENT
                ).count(),
                "sms": MessageRecipient.objects.filter(
                    bulk_message=bulk_message, sms_status=MessageStatus.SENT
                ).count(),
            },
        }

        return Response(analytics)


class MessageThreadViewSet(viewsets.ModelViewSet):
    """ViewSet for managing message threads"""

    serializer_class = MessageThreadSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultPagination
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["thread_type", "is_group", "is_active"]

    def get_queryset(self):
        """Get threads where user is a participant"""
        return MessageThread.objects.filter(
            participants=self.request.user, is_active=True
        ).order_by("-last_message_at")

    def get_serializer_context(self):
        """Add request to serializer context"""
        return {"request": self.request}

    @action(detail=False, methods=["post"])
    def create_thread(self, request):
        """Create a new message thread"""
        serializer = MessageThreadCreateSerializer(data=request.data)
        if serializer.is_valid():
            data = serializer.validated_data

            # Get participants
            participants = User.objects.filter(id__in=data["participant_ids"])
            if request.user not in participants:
                participants = list(participants) + [request.user]

            # Create thread
            thread = MessagingService.create_thread(
                subject=data["subject"],
                participants=participants,
                created_by=request.user,
                is_group=data["is_group"],
                thread_type=data["thread_type"],
            )

            # Send initial message if provided
            if data.get("initial_message"):
                MessagingService.send_message(
                    thread=thread, sender=request.user, content=data["initial_message"]
                )

            serializer = MessageThreadSerializer(thread, context={"request": request})
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["get"])
    def messages(self, request, pk=None):
        """Get messages in a thread"""
        thread = self.get_object()
        messages = DirectMessage.objects.filter(thread=thread).order_by("sent_at")

        # Pagination
        page = self.paginate_queryset(messages)
        if page is not None:
            serializer = DirectMessageSerializer(
                page, many=True, context={"request": request}
            )
            return self.get_paginated_response(serializer.data)

        serializer = DirectMessageSerializer(
            messages, many=True, context={"request": request}
        )
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def send_message(self, request, pk=None):
        """Send a message in a thread"""
        thread = self.get_object()
        serializer = DirectMessageCreateSerializer(data=request.data)

        if serializer.is_valid():
            message = MessagingService.send_message(
                thread=thread,
                sender=request.user,
                content=serializer.validated_data["content"],
                attachment=serializer.validated_data.get("attachment"),
            )

            # Mark as read by sender
            MessagingService.mark_message_as_read(message, request.user)

            response_serializer = DirectMessageSerializer(
                message, context={"request": request}
            )
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"])
    def mark_messages_read(self, request, pk=None):
        """Mark messages in thread as read"""
        thread = self.get_object()
        serializer = MessageMarkAsReadSerializer(data=request.data)

        if serializer.is_valid():
            message_ids = serializer.validated_data["message_ids"]
            messages = DirectMessage.objects.filter(id__in=message_ids, thread=thread)

            for message in messages:
                MessagingService.mark_message_as_read(message, request.user)

            return Response(
                {
                    "message": f"Marked {len(messages)} messages as read",
                    "marked_count": len(messages),
                }
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CommunicationPreferenceViewSet(viewsets.ModelViewSet):
    """ViewSet for managing communication preferences"""

    serializer_class = CommunicationPreferenceSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Get preferences for current user"""
        return CommunicationPreference.objects.filter(user=self.request.user)

    def get_object(self):
        """Get or create preferences for current user"""
        obj, created = CommunicationPreference.objects.get_or_create(
            user=self.request.user
        )
        return obj

    @action(detail=False, methods=["get"])
    def my_preferences(self, request):
        """Get current user's preferences"""
        preferences = self.get_object()
        serializer = CommunicationPreferenceSerializer(preferences)
        return Response(serializer.data)

    @action(detail=False, methods=["post", "put"])
    def update_preferences(self, request):
        """Update current user's preferences"""
        preferences = self.get_object()
        serializer = CommunicationPreferenceSerializer(
            preferences, data=request.data, partial=True
        )

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CommunicationAnalyticsViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for communication analytics"""

    queryset = CommunicationAnalytics.objects.all()
    serializer_class = CommunicationAnalyticsSerializer
    permission_classes = [permissions.IsAuthenticated]  # Add admin permissions
    pagination_class = StandardResultPagination
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["year", "month"]

    @action(detail=False, methods=["get"])
    def summary(self, request):
        """Get communication summary"""
        days = int(request.query_params.get("days", 30))
        summary = CommunicationAnalyticsService.get_communication_summary(days)
        serializer = CommunicationSummarySerializer(summary)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def user_engagement(self, request):
        """Get user engagement statistics"""
        user_id = request.query_params.get("user_id")
        if user_id:
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                return Response(
                    {"error": "User not found"}, status=status.HTTP_404_NOT_FOUND
                )
        else:
            user = request.user

        stats = CommunicationAnalyticsService.get_user_engagement_stats(user)
        serializer = UserEngagementStatsSerializer(stats)
        return Response(serializer.data)

    @action(detail=False, methods=["post"])
    def calculate_analytics(self, request):
        """Trigger analytics calculation"""
        date_str = request.data.get("date")
        if date_str:
            try:
                date = datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                return Response(
                    {"error": "Invalid date format. Use YYYY-MM-DD"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            date = timezone.now().date()

        analytics = CommunicationAnalyticsService.calculate_daily_analytics(date)
        serializer = CommunicationAnalyticsSerializer(analytics)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def channel_performance(self, request):
        """Get performance metrics by communication channel"""
        days = int(request.query_params.get("days", 30))
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)

        analytics = CommunicationAnalytics.objects.filter(
            date__gte=start_date, date__lte=end_date
        )

        performance = {
            "email": {
                "total_sent": analytics.aggregate(total=Count("total_emails_sent"))[
                    "total"
                ]
                or 0,
                "avg_delivery_rate": analytics.aggregate(
                    avg=Avg("email_delivery_rate")
                )["avg"]
                or 0,
                "avg_open_rate": analytics.aggregate(avg=Avg("email_open_rate"))["avg"]
                or 0,
                "avg_click_rate": analytics.aggregate(avg=Avg("email_click_rate"))[
                    "avg"
                ]
                or 0,
            },
            "sms": {
                "total_sent": analytics.aggregate(total=Count("total_sms_sent"))[
                    "total"
                ]
                or 0,
                "avg_delivery_rate": analytics.aggregate(avg=Avg("sms_delivery_rate"))[
                    "avg"
                ]
                or 0,
            },
            "push": {
                "total_sent": analytics.aggregate(total=Count("total_push_sent"))[
                    "total"
                ]
                or 0,
                "avg_delivery_rate": analytics.aggregate(avg=Avg("push_delivery_rate"))[
                    "avg"
                ]
                or 0,
            },
        }

        return Response(performance)


class CommunicationLogViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for communication logs"""

    queryset = CommunicationLog.objects.all()
    serializer_class = CommunicationLogSerializer
    permission_classes = [permissions.IsAuthenticated]  # Add admin permissions
    pagination_class = StandardResultPagination
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["event_type", "channel", "status"]

    def get_queryset(self):
        """Filter logs based on user permissions"""
        queryset = super().get_queryset()

        # For non-admin users, only show their own communications
        if not self.request.user.is_staff:
            queryset = queryset.filter(
                Q(sender=self.request.user) | Q(recipient=self.request.user)
            )

        return queryset.order_by("-timestamp")

    @action(detail=False, methods=["get"])
    def my_logs(self, request):
        """Get communication logs for current user"""
        logs = CommunicationLog.objects.filter(
            Q(sender=request.user) | Q(recipient=request.user)
        ).order_by("-timestamp")

        page = self.paginate_queryset(logs)
        if page is not None:
            serializer = CommunicationLogSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = CommunicationLogSerializer(logs, many=True)
        return Response(serializer.data)


# Additional utility views
class CommunicationUtilityViewSet(viewsets.ViewSet):
    """Utility endpoints for communication features"""

    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=["post"])
    def bulk_notification(self, request):
        """Send bulk notifications"""
        serializer = BulkNotificationSerializer(data=request.data)
        if serializer.is_valid():
            data = serializer.validated_data

            # Determine target users
            if data.get("user_ids"):
                users = User.objects.filter(id__in=data["user_ids"])
            elif data.get("target_audience"):
                # Implement audience-based targeting logic
                users = self._get_users_by_audience(
                    data["target_audience"], data.get("target_filters", {})
                )
            else:
                return Response(
                    {"error": "No target users specified"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if data.get("scheduled_at"):
                # Schedule for later
                from ..tasks import send_bulk_notification_task

                send_bulk_notification_task.apply_async(
                    args=[
                        [u.id for u in users],
                        data["title"],
                        data["content"],
                        data["notification_type"],
                        data["priority"],
                        data["channels"],
                    ],
                    eta=data["scheduled_at"],
                )
                return Response(
                    {
                        "message": f'Bulk notification scheduled for {data["scheduled_at"]}',
                        "target_count": len(users),
                    }
                )
            else:
                # Send immediately
                notifications = NotificationService.bulk_create_notifications(
                    users=users,
                    title=data["title"],
                    content=data["content"],
                    notification_type=data["notification_type"],
                    priority=data["priority"],
                    channels=data["channels"],
                )

                return Response(
                    {
                        "message": f"Successfully sent {len(notifications)} notifications",
                        "notification_count": len(notifications),
                    }
                )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=["get"])
    def unread_counts(self, request):
        """Get all unread counts for current user"""
        return Response(
            {
                "notifications": NotificationService.get_unread_count(request.user),
                "messages": MessagingService.get_unread_message_count(request.user),
                "total": NotificationService.get_unread_count(request.user)
                + MessagingService.get_unread_message_count(request.user),
            }
        )

    def _get_users_by_audience(self, audience, filters):
        """Get users based on target audience and filters"""
        # Implement audience targeting logic based on your role system
        query = Q(is_active=True)

        if audience == TargetAudience.STUDENTS:
            query &= Q(userroleassignment__role__name="Student")
        elif audience == TargetAudience.TEACHERS:
            query &= Q(userroleassignment__role__name="Teacher")
        elif audience == TargetAudience.PARENTS:
            query &= Q(userroleassignment__role__name="Parent")
        elif audience == TargetAudience.STAFF:
            query &= Q(userroleassignment__role__name="Staff")

        # Apply additional filters
        if filters.get("sections"):
            query &= Q(
                student__current_class__grade__section__id__in=filters["sections"]
            )

        if filters.get("grades"):
            query &= Q(student__current_class__grade__id__in=filters["grades"])

        if filters.get("classes"):
            query &= Q(student__current_class__id__in=filters["classes"])

        return User.objects.filter(query).distinct()
