from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class SystemSetting(models.Model):
    """System-wide settings and configurations."""

    SETTING_TYPES = (
        ("string", "String"),
        ("number", "Number"),
        ("boolean", "Boolean"),
        ("json", "JSON"),
    )

    setting_key = models.CharField(_("Setting Key"), max_length=100, unique=True)
    setting_value = models.TextField(_("Setting Value"))
    data_type = models.CharField(_("Data Type"), max_length=20, choices=SETTING_TYPES)
    description = models.TextField(_("Description"), blank=True)
    is_editable = models.BooleanField(_("Is Editable"), default=True)
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)

    class Meta:
        verbose_name = _("System Setting")
        verbose_name_plural = _("System Settings")
        ordering = ["setting_key"]

    def __str__(self):
        return self.setting_key


class AuditLog(models.Model):
    """Audit trail for system activities."""

    ACTION_TYPES = (
        ("create", "Create"),
        ("update", "Update"),
        ("delete", "Delete"),
        ("login", "Login"),
        ("logout", "Logout"),
        ("view", "View"),
        ("download", "Download"),
        ("other", "Other"),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="audit_logs",
    )
    action = models.CharField(_("Action"), max_length=20, choices=ACTION_TYPES)
    entity_type = models.CharField(_("Entity Type"), max_length=100)
    entity_id = models.CharField(_("Entity ID"), max_length=100, blank=True, null=True)
    data_before = models.JSONField(
        _("Data Before"), null=True, blank=True
    )  # Changed from django.contrib.postgres.fields.JSONField
    data_after = models.JSONField(
        _("Data After"), null=True, blank=True
    )  # Changed from django.contrib.postgres.fields.JSONField
    ip_address = models.GenericIPAddressField(_("IP Address"), null=True, blank=True)
    user_agent = models.TextField(_("User Agent"), blank=True)
    timestamp = models.DateTimeField(_("Timestamp"), auto_now_add=True)

    class Meta:
        verbose_name = _("Audit Log")
        verbose_name_plural = _("Audit Logs")
        ordering = ["-timestamp"]

    def __str__(self):
        return f"{self.action} {self.entity_type} by {self.user} at {self.timestamp}"


class Document(models.Model):
    """Generic document storage for the system."""

    title = models.CharField(_("Title"), max_length=255)
    description = models.TextField(_("Description"), blank=True)
    file_path = models.FileField(_("File Path"), upload_to="documents/")
    file_type = models.CharField(_("File Type"), max_length=50)
    upload_date = models.DateTimeField(_("Upload Date"), auto_now_add=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="uploaded_documents",
    )
    category = models.CharField(_("Category"), max_length=100)
    related_to_id = models.CharField(
        _("Related To ID"), max_length=100, blank=True, null=True
    )
    related_to_type = models.CharField(
        _("Related To Type"), max_length=100, blank=True, null=True
    )
    is_public = models.BooleanField(_("Is Public"), default=False)

    class Meta:
        verbose_name = _("Document")
        verbose_name_plural = _("Documents")
        ordering = ["-upload_date"]

    def __str__(self):
        return self.title
