import io
import json
import os
import zipfile
from datetime import datetime, timedelta

from django.apps import apps
from django.conf import settings
from django.core.mail import EmailMultiAlternatives, send_mail
from django.db.models import Q
from django.template.loader import render_to_string

from .models import AuditLog, Document, SystemSetting
from .utils import get_system_setting


class SystemSettingService:
    """Service class for managing system settings."""

    @staticmethod
    def initialize_default_settings():
        """Initialize default system settings if they don't exist."""
        default_settings = [
            {
                "setting_key": "site_name",
                "setting_value": "School Management System",
                "data_type": "string",
                "description": "Name of the school/institution",
                "is_editable": True,
            },
            {
                "setting_key": "school_address",
                "setting_value": "123 Education St, Knowledge City",
                "data_type": "string",
                "description": "Physical address of the school",
                "is_editable": True,
            },
            {
                "setting_key": "school_phone",
                "setting_value": "+1 (555) 123-4567",
                "data_type": "string",
                "description": "Contact phone number",
                "is_editable": True,
            },
            {
                "setting_key": "school_email",
                "setting_value": "info@school.example.com",
                "data_type": "string",
                "description": "Contact email address",
                "is_editable": True,
            },
            {
                "setting_key": "enable_notifications",
                "setting_value": "true",
                "data_type": "boolean",
                "description": "Enable system notifications",
                "is_editable": True,
            },
            {
                "setting_key": "maintenance_mode",
                "setting_value": "false",
                "data_type": "boolean",
                "description": "Put the system in maintenance mode",
                "is_editable": True,
            },
        ]

        for setting in default_settings:
            SystemSetting.objects.get_or_create(
                setting_key=setting["setting_key"], defaults=setting
            )

    @staticmethod
    def get_all_settings():
        """Get all system settings as a dictionary."""
        settings_dict = {}
        for setting in SystemSetting.objects.all():
            # Convert value based on data type
            if setting.data_type == "boolean":
                value = setting.setting_value.lower() in ("true", "yes", "1")
            elif setting.data_type == "number":
                value = float(setting.setting_value)
            elif setting.data_type == "json":
                value = json.loads(setting.setting_value)
            else:
                value = setting.setting_value

            settings_dict[setting.setting_key] = value

        return settings_dict

    @staticmethod
    def update_setting(key, value):
        """Update a system setting."""
        try:
            setting = SystemSetting.objects.get(setting_key=key)

            # Check if the setting is editable
            if not setting.is_editable:
                return False, "This setting cannot be modified"

            # Convert value based on data type
            if setting.data_type == "boolean":
                if isinstance(value, bool):
                    setting_value = str(value).lower()
                else:
                    setting_value = value.lower()
            elif setting.data_type == "json":
                if isinstance(value, str):
                    # Validate JSON string
                    json.loads(value)
                    setting_value = value
                else:
                    # Convert to JSON string
                    setting_value = json.dumps(value)
            else:
                setting_value = str(value)

            setting.setting_value = setting_value
            setting.save()

            return True, "Setting updated successfully"
        except SystemSetting.DoesNotExist:
            return False, "Setting not found"
        except json.JSONDecodeError:
            return False, "Invalid JSON format"
        except Exception as e:
            return False, str(e)


class DocumentService:
    """Service class for managing documents."""

    @staticmethod
    def create_document(
        file,
        title,
        description,
        category,
        uploaded_by,
        related_to_type=None,
        related_to_id=None,
        is_public=False,
    ):
        """Create a document record."""
        # Determine file type
        _, ext = os.path.splitext(file.name)
        file_type = ext.lstrip(".").lower()

        # Create the document
        document = Document.objects.create(
            title=title,
            description=description,
            file_path=file,
            file_type=file_type,
            uploaded_by=uploaded_by,
            category=category,
            related_to_type=related_to_type,
            related_to_id=related_to_id,
            is_public=is_public,
        )

        return document

    @staticmethod
    def get_documents_for_entity(entity_type, entity_id):
        """Get documents related to a specific entity."""
        return Document.objects.filter(
            related_to_type=entity_type, related_to_id=entity_id
        )

    @staticmethod
    def get_recent_public_documents(limit=10):
        """Get recent public documents."""
        return Document.objects.filter(is_public=True).order_by("-upload_date")[:limit]

    # Add this method to DocumentService class


@staticmethod
def get_documents_by_category(category, limit=None, user=None):
    """Get documents by category with optional user-based filtering."""
    queryset = Document.objects.filter(category=category)

    # If user is provided and not staff, limit to public and own documents
    if user and not user.is_staff:
        queryset = queryset.filter(Q(is_public=True) | Q(uploaded_by=user))

    # Apply limit if provided
    if limit is not None:
        queryset = queryset[:limit]

    return queryset.order_by("-upload_date")


@staticmethod
def archive_documents(document_ids, archive_name=None):
    """Create a ZIP archive of selected documents."""
    if not archive_name:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        archive_name = f"documents_archive_{timestamp}.zip"

    # Get the documents
    documents = Document.objects.filter(id__in=document_ids)

    # Create in-memory zip file
    zip_io = io.BytesIO()
    with zipfile.ZipFile(zip_io, "w") as zip_file:
        for document in documents:
            # Only include if file exists
            if document.file_path and os.path.exists(document.file_path.path):
                # Get file name (without path)
                file_name = os.path.basename(document.file_path.name)

                # Add to zip with original file name
                zip_file.write(document.file_path.path, file_name)

    # Reset pointer to start of buffer
    zip_io.seek(0)
    return zip_io, archive_name


# Create a notification service for the core module
class NotificationService:
    """Service for sending system notifications."""

    @staticmethod
    def send_email_notification(
        recipients, subject, template_name, context, attachments=None
    ):
        """Send email notification using a template."""
        # Get From email from settings
        from_email = get_system_setting("school_email", settings.DEFAULT_FROM_EMAIL)

        # Prepare HTML content
        html_content = render_to_string(template_name, context)

        # Create message
        msg = EmailMultiAlternatives(
            subject, strip_tags(html_content), from_email, recipients
        )
        msg.attach_alternative(html_content, "text/html")

        # Add attachments if provided
        if attachments:
            for attachment in attachments:
                name, content, mimetype = attachment
                msg.attach(name, content, mimetype)

        # Send the email
        msg.send()

    @staticmethod
    def send_system_notification(
        user_ids,
        title,
        content,
        notification_type,
        reference_id=None,
        priority="Medium",
    ):
        """Send in-app notification to multiple users."""
        # Import Notification model dynamically to avoid circular imports
        try:
            Notification = apps.get_model("communications", "Notification")
            User = apps.get_model("auth", "User")

            # Get users
            users = User.objects.filter(id__in=user_ids)

            # Create notifications
            notifications = []
            for user in users:
                notifications.append(
                    Notification(
                        user=user,
                        title=title,
                        content=content,
                        notification_type=notification_type,
                        reference_id=reference_id,
                        priority=priority,
                    )
                )

            # Bulk create
            if notifications:
                Notification.objects.bulk_create(notifications)

            return True, len(notifications)
        except Exception as e:
            return False, str(e)
