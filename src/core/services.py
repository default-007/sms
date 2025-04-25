import os
import json
from datetime import datetime, timedelta
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.apps import apps
from .models import SystemSetting, Document
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
