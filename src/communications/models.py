from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _


class Announcement(models.Model):
    """Model for school-wide announcements."""

    title = models.CharField(_("Title"), max_length=255)
    content = models.TextField(_("Content"))
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="announcements_created",
        verbose_name=_("Created By"),
    )
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)

    # Target audience settings
    TARGET_CHOICES = (
        ("all", _("All")),
        ("students", _("Students")),
        ("teachers", _("Teachers")),
        ("parents", _("Parents")),
        ("staff", _("Staff")),
    )
    target_audience = models.CharField(
        _("Target Audience"), max_length=20, choices=TARGET_CHOICES, default="all"
    )
    target_classes = models.JSONField(
        _("Target Classes"),
        blank=True,
        null=True,
        help_text=_("JSON array of class IDs"),
    )

    # Scheduling and status
    start_date = models.DateField(_("Start Date"))
    end_date = models.DateField(_("End Date"), blank=True, null=True)
    is_active = models.BooleanField(_("Is Active"), default=True)

    # Attachments
    attachment = models.FileField(
        _("Attachment"), upload_to="announcements/", blank=True, null=True
    )

    class Meta:
        verbose_name = _("Announcement")
        verbose_name_plural = _("Announcements")
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class Message(models.Model):
    """Model for direct messages between users."""

    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="messages_sent",
        verbose_name=_("Sender"),
    )
    receiver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="messages_received",
        verbose_name=_("Receiver"),
    )
    subject = models.CharField(_("Subject"), max_length=255)
    content = models.TextField(_("Content"))
    sent_at = models.DateTimeField(_("Sent At"), auto_now_add=True)
    read_at = models.DateTimeField(_("Read At"), blank=True, null=True)
    is_read = models.BooleanField(_("Is Read"), default=False)

    # Attachments and threading
    attachment = models.FileField(
        _("Attachment"), upload_to="messages/", blank=True, null=True
    )
    parent_message = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="replies",
        verbose_name=_("Parent Message"),
    )

    class Meta:
        verbose_name = _("Message")
        verbose_name_plural = _("Messages")
        ordering = ["-sent_at"]

    def __str__(self):
        return f"{self.subject} ({self.sender} to {self.receiver})"


class Notification(models.Model):
    """Model for system notifications to users."""

    NOTIFICATION_TYPES = (
        ("system", _("System")),
        ("attendance", _("Attendance")),
        ("fee", _("Fee")),
        ("exam", _("Exam")),
        ("assignment", _("Assignment")),
        ("message", _("Message")),
        ("event", _("Event")),
    )

    PRIORITY_LEVELS = (
        ("high", _("High")),
        ("medium", _("Medium")),
        ("low", _("Low")),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
        verbose_name=_("User"),
    )
    title = models.CharField(_("Title"), max_length=255)
    content = models.TextField(_("Content"))
    notification_type = models.CharField(
        _("Notification Type"), max_length=20, choices=NOTIFICATION_TYPES
    )
    reference_id = models.CharField(
        _("Reference ID"), max_length=100, blank=True, null=True
    )
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    is_read = models.BooleanField(_("Is Read"), default=False)
    read_at = models.DateTimeField(_("Read At"), blank=True, null=True)
    priority = models.CharField(
        _("Priority"), max_length=10, choices=PRIORITY_LEVELS, default="medium"
    )

    class Meta:
        verbose_name = _("Notification")
        verbose_name_plural = _("Notifications")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} ({self.user})"


class SMSLog(models.Model):
    """Log of SMS messages sent by the system."""

    STATUS_CHOICES = (
        ("sent", _("Sent")),
        ("failed", _("Failed")),
        ("pending", _("Pending")),
    )

    recipient_number = models.CharField(_("Recipient Number"), max_length=20)
    recipient_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sms_logs",
        verbose_name=_("Recipient User"),
    )
    content = models.TextField(_("Content"))
    sent_at = models.DateTimeField(_("Sent At"), auto_now_add=True)
    status = models.CharField(
        _("Status"), max_length=10, choices=STATUS_CHOICES, default="pending"
    )
    error_message = models.TextField(_("Error Message"), blank=True, null=True)
    sender = models.CharField(_("Sender"), max_length=100, blank=True)
    message_id = models.CharField(
        _("Message ID"), max_length=100, blank=True, null=True
    )

    class Meta:
        verbose_name = _("SMS Log")
        verbose_name_plural = _("SMS Logs")
        ordering = ["-sent_at"]

    def __str__(self):
        return f"SMS to {self.recipient_number} at {self.sent_at}"


class EmailLog(models.Model):
    """Log of emails sent by the system."""

    STATUS_CHOICES = (
        ("sent", _("Sent")),
        ("failed", _("Failed")),
        ("pending", _("Pending")),
    )

    recipient_email = models.EmailField(_("Recipient Email"))
    recipient_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="email_logs",
        verbose_name=_("Recipient User"),
    )
    subject = models.CharField(_("Subject"), max_length=255)
    content = models.TextField(_("Content"))
    sent_at = models.DateTimeField(_("Sent At"), auto_now_add=True)
    status = models.CharField(
        _("Status"), max_length=10, choices=STATUS_CHOICES, default="pending"
    )
    error_message = models.TextField(_("Error Message"), blank=True, null=True)
    attachment = models.FileField(
        _("Attachment"), upload_to="email_attachments/", blank=True, null=True
    )

    class Meta:
        verbose_name = _("Email Log")
        verbose_name_plural = _("Email Logs")
        ordering = ["-sent_at"]

    def __str__(self):
        return f"Email to {self.recipient_email} at {self.sent_at}"
