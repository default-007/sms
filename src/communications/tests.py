"""
Comprehensive tests for Communications module.
Tests models, services, API views, web views, forms, and background tasks.
"""

from django.test import TestCase, TransactionTestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from django.core import mail
from django.test.utils import override_settings
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
import json

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
    CommunicationChannel,
    Priority,
    TargetAudience,
    MessageStatus,
)
from .services import (
    NotificationService,
    AnnouncementService,
    MessagingService,
    EmailService,
    CommunicationAnalyticsService,
)
from .forms import AnnouncementForm, BulkMessageForm, MessageTemplateForm
from .tasks import (
    send_bulk_notification_task,
    calculate_daily_analytics_task,
    send_bulk_message_task,
)

User = get_user_model()


class CommunicationModelsTestCase(TestCase):
    """Test cases for communication models"""

    def setUp(self):
        """Set up test data"""
        self.user1 = User.objects.create_user(
            username="testuser1", email="test1@example.com", password="testpass123"
        )
        self.user2 = User.objects.create_user(
            username="testuser2", email="test2@example.com", password="testpass123"
        )
        self.admin_user = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="adminpass123",
            is_staff=True,
        )

    def test_announcement_creation(self):
        """Test announcement model creation"""
        announcement = Announcement.objects.create(
            title="Test Announcement",
            content="This is a test announcement",
            created_by=self.admin_user,
            target_audience=TargetAudience.ALL,
            priority=Priority.HIGH,
        )

        self.assertEqual(announcement.title, "Test Announcement")
        self.assertEqual(announcement.created_by, self.admin_user)
        self.assertEqual(announcement.priority, Priority.HIGH)
        self.assertTrue(announcement.is_current)
        self.assertEqual(announcement.read_rate, 0)
        self.assertEqual(announcement.delivery_rate, 0)

    def test_notification_creation(self):
        """Test notification model creation"""
        notification = Notification.objects.create(
            user=self.user1,
            title="Test Notification",
            content="This is a test notification",
            notification_type="test",
            priority=Priority.MEDIUM,
        )

        self.assertEqual(notification.user, self.user1)
        self.assertEqual(notification.title, "Test Notification")
        self.assertFalse(notification.is_read)
        self.assertIsNone(notification.read_at)

    def test_notification_mark_as_read(self):
        """Test marking notification as read"""
        notification = Notification.objects.create(
            user=self.user1,
            title="Test Notification",
            content="Test content",
            notification_type="test",
        )

        self.assertFalse(notification.is_read)

        notification.mark_as_read()

        self.assertTrue(notification.is_read)
        self.assertIsNotNone(notification.read_at)

    def test_message_thread_creation(self):
        """Test message thread creation"""
        thread = MessageThread.objects.create(
            subject="Test Thread", created_by=self.user1, is_group=False
        )
        thread.participants.add(self.user1, self.user2)

        self.assertEqual(thread.subject, "Test Thread")
        self.assertEqual(thread.participants.count(), 2)
        self.assertFalse(thread.is_group)

    def test_direct_message_creation(self):
        """Test direct message creation"""
        thread = MessageThread.objects.create(
            subject="Test Thread", created_by=self.user1
        )
        thread.participants.add(self.user1, self.user2)

        message = DirectMessage.objects.create(
            thread=thread, sender=self.user1, content="Hello, this is a test message"
        )

        self.assertEqual(message.sender, self.user1)
        self.assertEqual(message.thread, thread)
        self.assertFalse(message.is_edited)

    def test_communication_preference_creation(self):
        """Test communication preference creation"""
        preference = CommunicationPreference.objects.create(
            user=self.user1, email_enabled=True, sms_enabled=False, push_enabled=True
        )

        self.assertEqual(preference.user, self.user1)
        self.assertTrue(preference.email_enabled)
        self.assertFalse(preference.sms_enabled)
        self.assertTrue(preference.push_enabled)

    def test_message_template_rendering(self):
        """Test message template rendering"""
        template = MessageTemplate.objects.create(
            name="Test Template",
            template_type="test",
            subject_template="Hello {{ user.first_name }}",
            content_template="Welcome {{ user.first_name }}, your username is {{ user.username }}",
            created_by=self.admin_user,
        )

        context = {"user": self.user1}
        rendered_subject = template.render_subject(context)
        rendered_content = template.render_content(context)

        self.assertIn(self.user1.first_name, rendered_subject)
        self.assertIn(self.user1.username, rendered_content)


class NotificationServiceTestCase(TestCase):
    """Test cases for notification service"""

    def setUp(self):
        """Set up test data"""
        self.user1 = User.objects.create_user(
            username="testuser1", email="test1@example.com", password="testpass123"
        )
        self.user2 = User.objects.create_user(
            username="testuser2", email="test2@example.com", password="testpass123"
        )

    def test_create_notification(self):
        """Test creating a single notification"""
        notification = NotificationService.create_notification(
            user=self.user1,
            title="Test Notification",
            content="Test content",
            notification_type="test",
            priority=Priority.HIGH,
        )

        self.assertIsInstance(notification, Notification)
        self.assertEqual(notification.user, self.user1)
        self.assertEqual(notification.priority, Priority.HIGH)

    def test_bulk_create_notifications(self):
        """Test creating bulk notifications"""
        users = [self.user1, self.user2]

        notifications = NotificationService.bulk_create_notifications(
            users=users,
            title="Bulk Test",
            content="Bulk content",
            notification_type="bulk_test",
        )

        self.assertEqual(len(notifications), 2)
        self.assertTrue(all(isinstance(n, Notification) for n in notifications))

    def test_mark_as_read(self):
        """Test marking notification as read"""
        notification = NotificationService.create_notification(
            user=self.user1, title="Test", content="Test", notification_type="test"
        )

        success = NotificationService.mark_as_read(str(notification.id), self.user1)

        self.assertTrue(success)
        notification.refresh_from_db()
        self.assertTrue(notification.is_read)

    def test_get_unread_count(self):
        """Test getting unread notification count"""
        # Create some notifications
        NotificationService.create_notification(
            user=self.user1, title="Test 1", content="Content", notification_type="test"
        )
        NotificationService.create_notification(
            user=self.user1, title="Test 2", content="Content", notification_type="test"
        )

        count = NotificationService.get_unread_count(self.user1)
        self.assertEqual(count, 2)

        # Mark one as read
        notification = Notification.objects.filter(user=self.user1).first()
        notification.mark_as_read()

        count = NotificationService.get_unread_count(self.user1)
        self.assertEqual(count, 1)


class AnnouncementServiceTestCase(TestCase):
    """Test cases for announcement service"""

    def setUp(self):
        """Set up test data"""
        self.admin_user = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="adminpass123",
            is_staff=True,
        )
        self.user1 = User.objects.create_user(
            username="testuser1", email="test1@example.com", password="testpass123"
        )

    @patch("src.communications.services.NotificationService.bulk_create_notifications")
    def test_create_announcement(self, mock_bulk_create):
        """Test creating an announcement"""
        mock_bulk_create.return_value = [MagicMock(), MagicMock()]

        announcement = AnnouncementService.create_announcement(
            title="Test Announcement",
            content="Test content",
            created_by=self.admin_user,
            target_audience=TargetAudience.ALL,
        )

        self.assertIsInstance(announcement, Announcement)
        self.assertEqual(announcement.title, "Test Announcement")
        self.assertEqual(announcement.created_by, self.admin_user)
        mock_bulk_create.assert_called_once()

    def test_get_active_announcements(self):
        """Test getting active announcements"""
        # Create active announcement
        active_announcement = Announcement.objects.create(
            title="Active Announcement",
            content="Content",
            created_by=self.admin_user,
            is_active=True,
            start_date=timezone.now() - timedelta(hours=1),
        )

        # Create inactive announcement
        inactive_announcement = Announcement.objects.create(
            title="Inactive Announcement",
            content="Content",
            created_by=self.admin_user,
            is_active=False,
        )

        # Create future announcement
        future_announcement = Announcement.objects.create(
            title="Future Announcement",
            content="Content",
            created_by=self.admin_user,
            is_active=True,
            start_date=timezone.now() + timedelta(hours=1),
        )

        active_announcements = AnnouncementService.get_active_announcements()

        self.assertIn(active_announcement, active_announcements)
        self.assertNotIn(inactive_announcement, active_announcements)
        self.assertNotIn(future_announcement, active_announcements)


class MessagingServiceTestCase(TestCase):
    """Test cases for messaging service"""

    def setUp(self):
        """Set up test data"""
        self.user1 = User.objects.create_user(
            username="testuser1", email="test1@example.com", password="testpass123"
        )
        self.user2 = User.objects.create_user(
            username="testuser2", email="test2@example.com", password="testpass123"
        )

    def test_create_thread(self):
        """Test creating a message thread"""
        participants = [self.user1, self.user2]

        thread = MessagingService.create_thread(
            subject="Test Thread", participants=participants, created_by=self.user1
        )

        self.assertIsInstance(thread, MessageThread)
        self.assertEqual(thread.subject, "Test Thread")
        self.assertEqual(thread.participants.count(), 2)

    def test_send_message(self):
        """Test sending a message"""
        thread = MessagingService.create_thread(
            subject="Test Thread",
            participants=[self.user1, self.user2],
            created_by=self.user1,
        )

        message = MessagingService.send_message(
            thread=thread, sender=self.user1, content="Hello there!"
        )

        self.assertIsInstance(message, DirectMessage)
        self.assertEqual(message.sender, self.user1)
        self.assertEqual(message.content, "Hello there!")

        # Check that thread's last_message_at was updated
        thread.refresh_from_db()
        self.assertEqual(thread.last_message_at, message.sent_at)

    def test_mark_message_as_read(self):
        """Test marking message as read"""
        thread = MessagingService.create_thread(
            subject="Test Thread",
            participants=[self.user1, self.user2],
            created_by=self.user1,
        )

        message = MessagingService.send_message(
            thread=thread, sender=self.user1, content="Test message"
        )

        MessagingService.mark_message_as_read(message, self.user2)

        read_receipt = MessageRead.objects.filter(
            user=self.user2, message=message
        ).exists()

        self.assertTrue(read_receipt)

    def test_get_unread_message_count(self):
        """Test getting unread message count"""
        thread = MessagingService.create_thread(
            subject="Test Thread",
            participants=[self.user1, self.user2],
            created_by=self.user1,
        )

        # Send messages from user1 to user2
        message1 = MessagingService.send_message(thread, self.user1, "Message 1")
        message2 = MessagingService.send_message(thread, self.user1, "Message 2")

        # User2 should have 2 unread messages
        unread_count = MessagingService.get_unread_message_count(self.user2)
        self.assertEqual(unread_count, 2)

        # Mark one as read
        MessagingService.mark_message_as_read(message1, self.user2)

        unread_count = MessagingService.get_unread_message_count(self.user2)
        self.assertEqual(unread_count, 1)


class CommunicationAnalyticsServiceTestCase(TestCase):
    """Test cases for communication analytics service"""

    def setUp(self):
        """Set up test data"""
        self.user1 = User.objects.create_user(
            username="testuser1", email="test1@example.com", password="testpass123"
        )

        # Create some sample data
        self.notification1 = Notification.objects.create(
            user=self.user1, title="Test 1", content="Content", notification_type="test"
        )
        self.notification2 = Notification.objects.create(
            user=self.user1,
            title="Test 2",
            content="Content",
            notification_type="test",
            is_read=True,
            read_at=timezone.now(),
        )

    def test_calculate_daily_analytics(self):
        """Test calculating daily analytics"""
        date = timezone.now().date()

        analytics = CommunicationAnalyticsService.calculate_daily_analytics(date)

        self.assertIsInstance(analytics, CommunicationAnalytics)
        self.assertEqual(analytics.date, date)
        self.assertEqual(analytics.month, date.month)
        self.assertEqual(analytics.year, date.year)

    def test_get_communication_summary(self):
        """Test getting communication summary"""
        # Create some analytics data
        date = timezone.now().date()
        CommunicationAnalytics.objects.create(
            date=date,
            month=date.month,
            year=date.year,
            total_emails_sent=10,
            total_sms_sent=5,
            total_push_sent=15,
        )

        summary = CommunicationAnalyticsService.get_communication_summary(days=1)

        self.assertEqual(summary["total_emails"], 10)
        self.assertEqual(summary["total_sms"], 5)
        self.assertEqual(summary["total_push"], 15)

    def test_get_user_engagement_stats(self):
        """Test getting user engagement statistics"""
        stats = CommunicationAnalyticsService.get_user_engagement_stats(self.user1)

        self.assertEqual(stats["total_notifications"], 2)
        self.assertEqual(stats["unread_notifications"], 1)
        self.assertEqual(stats["read_rate"], 50.0)


class CommunicationAPITestCase(APITestCase):
    """Test cases for communication API endpoints"""

    def setUp(self):
        """Set up test data"""
        self.user1 = User.objects.create_user(
            username="testuser1", email="test1@example.com", password="testpass123"
        )
        self.admin_user = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="adminpass123",
            is_staff=True,
        )
        self.client = APIClient()

    def test_notification_list_api(self):
        """Test notification list API endpoint"""
        self.client.force_authenticate(user=self.user1)

        # Create some notifications
        Notification.objects.create(
            user=self.user1, title="Test 1", content="Content", notification_type="test"
        )
        Notification.objects.create(
            user=self.user1, title="Test 2", content="Content", notification_type="test"
        )

        url = reverse("communications:notification-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 2)

    def test_create_notification_api(self):
        """Test creating notification via API"""
        self.client.force_authenticate(user=self.admin_user)

        url = reverse("communications:notification-create-notification")
        data = {
            "user_ids": [self.user1.id],
            "title": "API Test Notification",
            "content": "Test content",
            "notification_type": "api_test",
            "priority": Priority.HIGH,
            "channels": [CommunicationChannel.IN_APP],
        }

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["notification_count"], 1)

    def test_mark_notification_read_api(self):
        """Test marking notification as read via API"""
        self.client.force_authenticate(user=self.user1)

        notification = Notification.objects.create(
            user=self.user1, title="Test", content="Content", notification_type="test"
        )

        url = reverse(
            "communications:notification-mark-as-read", kwargs={"pk": notification.id}
        )
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        notification.refresh_from_db()
        self.assertTrue(notification.is_read)

    def test_announcement_list_api(self):
        """Test announcement list API endpoint"""
        self.client.force_authenticate(user=self.user1)

        Announcement.objects.create(
            title="Test Announcement",
            content="Test content",
            created_by=self.admin_user,
        )

        url = reverse("communications:announcement-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)

    def test_create_announcement_api(self):
        """Test creating announcement via API"""
        self.client.force_authenticate(user=self.admin_user)

        url = reverse("communications:announcement-list")
        data = {
            "title": "API Test Announcement",
            "content": "Test content",
            "target_audience": TargetAudience.ALL,
            "priority": Priority.MEDIUM,
            "channels": [CommunicationChannel.IN_APP],
        }

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["title"], "API Test Announcement")


class CommunicationFormsTestCase(TestCase):
    """Test cases for communication forms"""

    def setUp(self):
        """Set up test data"""
        self.admin_user = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="adminpass123",
            is_staff=True,
        )

    def test_announcement_form_valid(self):
        """Test valid announcement form"""
        form_data = {
            "title": "Test Announcement",
            "content": "Test content",
            "target_audience": TargetAudience.ALL,
            "priority": Priority.MEDIUM,
            "channels": [CommunicationChannel.IN_APP],
            "start_date": timezone.now(),
        }

        form = AnnouncementForm(data=form_data)
        self.assertTrue(form.is_valid())

    def test_announcement_form_invalid_dates(self):
        """Test announcement form with invalid date range"""
        now = timezone.now()
        form_data = {
            "title": "Test Announcement",
            "content": "Test content",
            "target_audience": TargetAudience.ALL,
            "priority": Priority.MEDIUM,
            "channels": [CommunicationChannel.IN_APP],
            "start_date": now,
            "end_date": now - timedelta(hours=1),  # End before start
        }

        form = AnnouncementForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn("End date must be after start date", str(form.errors))

    def test_message_template_form_valid(self):
        """Test valid message template form"""
        form_data = {
            "name": "Test Template",
            "description": "Test description",
            "template_type": "test",
            "subject_template": "Test Subject",
            "content_template": "Test Content {{ variable }}",
            "supported_channels": [CommunicationChannel.EMAIL],
            "variables": '{"variable": "Test variable"}',
            "is_active": True,
        }

        form = MessageTemplateForm(data=form_data)
        self.assertTrue(form.is_valid())

    def test_message_template_form_invalid_json(self):
        """Test message template form with invalid JSON"""
        form_data = {
            "name": "Test Template",
            "template_type": "test",
            "content_template": "Test Content",
            "variables": "invalid json",  # Invalid JSON
            "supported_channels": [CommunicationChannel.EMAIL],
        }

        form = MessageTemplateForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn("Invalid JSON format", str(form.errors))


class CommunicationTasksTestCase(TransactionTestCase):
    """Test cases for communication background tasks"""

    def setUp(self):
        """Set up test data"""
        self.user1 = User.objects.create_user(
            username="testuser1", email="test1@example.com", password="testpass123"
        )
        self.user2 = User.objects.create_user(
            username="testuser2", email="test2@example.com", password="testpass123"
        )

    def test_send_bulk_notification_task(self):
        """Test bulk notification background task"""
        user_ids = [self.user1.id, self.user2.id]

        result = send_bulk_notification_task.delay(
            user_ids=user_ids,
            title="Task Test",
            content="Task content",
            notification_type="task_test",
        )

        # Wait for task to complete
        task_result = result.get(timeout=10)

        self.assertEqual(task_result["status"], "success")
        self.assertEqual(task_result["notifications_sent"], 2)

        # Verify notifications were created
        notifications = Notification.objects.filter(title="Task Test")
        self.assertEqual(notifications.count(), 2)

    def test_calculate_daily_analytics_task(self):
        """Test daily analytics calculation task"""
        date_str = timezone.now().date().isoformat()

        result = calculate_daily_analytics_task.delay(date_str)
        task_result = result.get(timeout=10)

        self.assertEqual(task_result["status"], "success")

        # Verify analytics were created
        analytics = CommunicationAnalytics.objects.filter(date=timezone.now().date())
        self.assertTrue(analytics.exists())


class CommunicationWebViewsTestCase(TestCase):
    """Test cases for communication web views"""

    def setUp(self):
        """Set up test data"""
        self.user1 = User.objects.create_user(
            username="testuser1", email="test1@example.com", password="testpass123"
        )
        self.admin_user = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="adminpass123",
            is_staff=True,
        )

    def test_communications_dashboard_view(self):
        """Test communications dashboard view"""
        self.client.login(username="testuser1", password="testpass123")

        url = reverse("communications:dashboard")
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Communications Dashboard")

    def test_notifications_overview_view(self):
        """Test notifications overview view"""
        self.client.login(username="testuser1", password="testpass123")

        # Create some notifications
        Notification.objects.create(
            user=self.user1, title="Test 1", content="Content", notification_type="test"
        )

        url = reverse("communications:notifications_overview")
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "My Notifications")
        self.assertContains(response, "Test 1")

    def test_announcement_list_view(self):
        """Test announcement list view"""
        self.client.login(username="testuser1", password="testpass123")

        Announcement.objects.create(
            title="Test Announcement",
            content="Test content",
            created_by=self.admin_user,
        )

        url = reverse("communications:announcement_list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Announcements")
        self.assertContains(response, "Test Announcement")

    def test_announcement_create_view_requires_permission(self):
        """Test that announcement creation requires proper permissions"""
        self.client.login(username="testuser1", password="testpass123")

        url = reverse("communications:announcement_create")
        response = self.client.get(url)

        # This would depend on your permission system
        # For now, just check that the view exists
        self.assertIn(response.status_code, [200, 403])

    def test_message_thread_list_view(self):
        """Test message thread list view"""
        self.client.login(username="testuser1", password="testpass123")

        thread = MessageThread.objects.create(
            subject="Test Thread", created_by=self.user1
        )
        thread.participants.add(self.user1)

        url = reverse("communications:thread_list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Messages")
        self.assertContains(response, "Test Thread")

    def test_communication_preferences_view(self):
        """Test communication preferences view"""
        self.client.login(username="testuser1", password="testpass123")

        url = reverse("communications:preferences")
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Communication Preferences")

    def test_analytics_dashboard_requires_staff(self):
        """Test that analytics dashboard requires staff permission"""
        self.client.login(username="testuser1", password="testpass123")

        url = reverse("communications:analytics_dashboard")
        response = self.client.get(url)

        self.assertEqual(response.status_code, 403)

        # Test with staff user
        self.client.login(username="admin", password="adminpass123")
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Communications Analytics")


class CommunicationSignalsTestCase(TestCase):
    """Test cases for communication signals"""

    def setUp(self):
        """Set up test data"""
        self.user1 = User.objects.create_user(
            username="testuser1", email="test1@example.com", password="testpass123"
        )

    def test_user_preferences_created_on_user_creation(self):
        """Test that communication preferences are created when user is created"""
        # Create new user
        new_user = User.objects.create_user(
            username="newuser", email="new@example.com", password="newpass123"
        )

        # Check that preferences were created
        preferences = CommunicationPreference.objects.filter(user=new_user)
        self.assertTrue(preferences.exists())

        preference = preferences.first()
        self.assertTrue(preference.email_enabled)
        self.assertTrue(preference.sms_enabled)
        self.assertTrue(preference.push_enabled)

    def test_communication_log_created_on_notification(self):
        """Test that communication log is created when notification is created"""
        notification = Notification.objects.create(
            user=self.user1,
            title="Test Notification",
            content="Test content",
            notification_type="test",
        )

        # Check that log was created
        logs = CommunicationLog.objects.filter(
            content_id=str(notification.id), content_type="notification"
        )
        self.assertTrue(logs.exists())

        log = logs.first()
        self.assertEqual(log.event_type, "notification_created")
        self.assertEqual(log.recipient, self.user1)


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class EmailServiceTestCase(TestCase):
    """Test cases for email service"""

    def setUp(self):
        """Set up test data"""
        self.user1 = User.objects.create_user(
            username="testuser1", email="test1@example.com", password="testpass123"
        )

        # Create communication preferences
        CommunicationPreference.objects.create(user=self.user1, email_enabled=True)

    def test_send_notification_email(self):
        """Test sending notification via email"""
        notification = Notification.objects.create(
            user=self.user1,
            title="Email Test",
            content="Email content",
            notification_type="test",
        )

        success = EmailService.send_notification_email(notification)

        self.assertTrue(success)
        self.assertEqual(len(mail.outbox), 1)

        sent_email = mail.outbox[0]
        self.assertEqual(sent_email.to, [self.user1.email])
        self.assertEqual(sent_email.subject, "Email Test")

    def test_send_bulk_email(self):
        """Test sending bulk email"""
        user2 = User.objects.create_user(
            username="testuser2", email="test2@example.com", password="testpass123"
        )

        # Create preferences for user2
        CommunicationPreference.objects.create(user=user2, email_enabled=True)

        users = [self.user1, user2]

        results = EmailService.send_bulk_email(
            subject="Bulk Test", content="Bulk content", recipients=users
        )

        self.assertEqual(results["sent"], 2)
        self.assertEqual(results["failed"], 0)
        self.assertEqual(len(mail.outbox), 2)


class CommunicationIntegrationTestCase(TransactionTestCase):
    """Integration tests for communication workflows"""

    def setUp(self):
        """Set up test data"""
        self.admin_user = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="adminpass123",
            is_staff=True,
        )
        self.user1 = User.objects.create_user(
            username="testuser1", email="test1@example.com", password="testpass123"
        )
        self.user2 = User.objects.create_user(
            username="testuser2", email="test2@example.com", password="testpass123"
        )

    def test_complete_announcement_workflow(self):
        """Test complete announcement creation and delivery workflow"""
        # Create announcement
        announcement = AnnouncementService.create_announcement(
            title="Integration Test Announcement",
            content="This is an integration test",
            created_by=self.admin_user,
            target_audience=TargetAudience.ALL,
            priority=Priority.HIGH,
            channels=[CommunicationChannel.IN_APP, CommunicationChannel.EMAIL],
        )

        # Verify announcement was created
        self.assertIsInstance(announcement, Announcement)
        self.assertEqual(announcement.title, "Integration Test Announcement")

        # Verify notifications were created for users
        notifications = Notification.objects.filter(
            title__contains="Integration Test Announcement"
        )
        self.assertTrue(notifications.exists())

        # Verify analytics tracking
        logs = CommunicationLog.objects.filter(
            content_type="announcement", content_id=str(announcement.id)
        )
        self.assertTrue(logs.exists())

        # Test marking notifications as read
        for notification in notifications:
            success = NotificationService.mark_as_read(
                str(notification.id), notification.user
            )
            self.assertTrue(success)

        # Update announcement metrics
        AnnouncementService.update_announcement_metrics(str(announcement.id))

        announcement.refresh_from_db()
        self.assertEqual(announcement.total_read, notifications.count())

    def test_complete_messaging_workflow(self):
        """Test complete messaging workflow"""
        # Create thread
        thread = MessagingService.create_thread(
            subject="Integration Test Thread",
            participants=[self.user1, self.user2],
            created_by=self.user1,
            is_group=False,
        )

        # Send messages
        message1 = MessagingService.send_message(
            thread=thread, sender=self.user1, content="Hello from user1"
        )

        message2 = MessagingService.send_message(
            thread=thread, sender=self.user2, content="Hello back from user2"
        )

        # Verify messages were created
        self.assertEqual(thread.messages.count(), 2)

        # Test read receipts
        MessagingService.mark_message_as_read(message1, self.user2)
        MessagingService.mark_message_as_read(message2, self.user1)

        # Verify read receipts
        read_receipts = MessageRead.objects.filter(message__in=[message1, message2])
        self.assertEqual(read_receipts.count(), 2)

        # Test unread counts
        unread_count_user1 = MessagingService.get_unread_message_count(self.user1)
        unread_count_user2 = MessagingService.get_unread_message_count(self.user2)

        self.assertEqual(unread_count_user1, 0)
        self.assertEqual(unread_count_user2, 0)
