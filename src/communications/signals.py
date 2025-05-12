from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from django.utils import timezone

from .models import Announcement, Message, Notification
from .services import NotificationService


@receiver(post_save, sender=Message)
def create_message_notification(sender, instance, created, **kwargs):
    """Create a notification when a new message is sent."""
    if created:
        NotificationService.create_message_notification(instance)


@receiver(post_save, sender=Announcement)
def handle_announcement_notifications(sender, instance, created, **kwargs):
    """Create notifications for new announcements."""
    if created:
        NotificationService.create_announcement_notifications(instance)


@receiver(post_save, sender=Notification)
def handle_notification_read_status(sender, instance, **kwargs):
    """Handle logic when a notification is marked as read."""
    if instance.is_read and not instance.read_at:
        instance.read_at = timezone.now()
        # Use update to avoid triggering another post_save signal
        Notification.objects.filter(id=instance.id).update(read_at=timezone.now())
