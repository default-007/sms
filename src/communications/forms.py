"""
Django forms for Communications module.
Provides form classes for creating and managing communications through web interface.
"""

import json

from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.forms.widgets import CheckboxSelectMultiple
from django.utils import timezone

from .models import (
    Announcement,
    BulkMessage,
    CommunicationChannel,
    CommunicationPreference,
    DirectMessage,
    MessageStatus,
    MessageTemplate,
    MessageThread,
    Priority,
    TargetAudience,
)

User = get_user_model()


class AnnouncementForm(forms.ModelForm):
    """Form for creating and editing announcements"""

    target_users = forms.ModelMultipleChoiceField(
        queryset=User.objects.filter(is_active=True),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        help_text="Select specific users (optional, used with Custom audience)",
    )

    channels = forms.MultipleChoiceField(
        choices=CommunicationChannel.choices,
        widget=CheckboxSelectMultiple,
        initial=[CommunicationChannel.IN_APP],
        help_text="Select communication channels",
    )

    class Meta:
        model = Announcement
        fields = [
            "title",
            "content",
            "target_audience",
            "target_sections",
            "target_grades",
            "target_classes",
            "target_users",
            "start_date",
            "end_date",
            "priority",
            "channels",
            "attachment",
        ]
        widgets = {
            "title": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Enter announcement title",
                }
            ),
            "content": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 6,
                    "placeholder": "Enter announcement content",
                }
            ),
            "target_audience": forms.Select(attrs={"class": "form-control"}),
            "priority": forms.Select(attrs={"class": "form-control"}),
            "start_date": forms.DateTimeInput(
                attrs={"class": "form-control", "type": "datetime-local"}
            ),
            "end_date": forms.DateTimeInput(
                attrs={"class": "form-control", "type": "datetime-local"}
            ),
            "attachment": forms.FileInput(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Set default start date to now
        if not self.instance.pk:
            self.fields["start_date"].initial = timezone.now()

        # Make end_date optional
        self.fields["end_date"].required = False

        # Dynamic querysets for targeting fields
        try:
            from src.academics.models import Class, Grade, Section

            self.fields["target_sections"] = forms.ModelMultipleChoiceField(
                queryset=Section.objects.all(),
                widget=CheckboxSelectMultiple,
                required=False,
                help_text="Select sections",
            )

            self.fields["target_grades"] = forms.ModelMultipleChoiceField(
                queryset=Grade.objects.all(),
                widget=CheckboxSelectMultiple,
                required=False,
                help_text="Select grades",
            )

            self.fields["target_classes"] = forms.ModelMultipleChoiceField(
                queryset=Class.objects.all(),
                widget=CheckboxSelectMultiple,
                required=False,
                help_text="Select classes",
            )
        except ImportError:
            # Handle case where academics models aren't available
            pass

    def clean(self):
        """Custom validation for announcement form"""
        cleaned_data = super().clean()

        start_date = cleaned_data.get("start_date")
        end_date = cleaned_data.get("end_date")
        target_audience = cleaned_data.get("target_audience")

        # Validate date range
        if start_date and end_date:
            if end_date <= start_date:
                raise ValidationError("End date must be after start date")

        # Validate targeting for custom audience
        if target_audience == TargetAudience.CUSTOM:
            has_targeting = any(
                [
                    cleaned_data.get("target_sections"),
                    cleaned_data.get("target_grades"),
                    cleaned_data.get("target_classes"),
                    cleaned_data.get("target_users"),
                ]
            )

            if not has_targeting:
                raise ValidationError(
                    "Custom audience requires at least one targeting option"
                )

        return cleaned_data


class BulkMessageForm(forms.ModelForm):
    """Form for creating bulk messages"""

    channels = forms.MultipleChoiceField(
        choices=CommunicationChannel.choices,
        widget=CheckboxSelectMultiple,
        initial=[CommunicationChannel.EMAIL],
        help_text="Select communication channels",
    )

    target_filters = forms.CharField(
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 3,
                "placeholder": '{"sections": [1, 2], "grades": [3, 4]}',
            }
        ),
        required=False,
        help_text="JSON object with additional filters",
    )

    class Meta:
        model = BulkMessage
        fields = [
            "name",
            "description",
            "subject",
            "content",
            "template",
            "target_audience",
            "target_filters",
            "scheduled_at",
            "channels",
            "priority",
        ]
        widgets = {
            "name": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Campaign name"}
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": "Campaign description",
                }
            ),
            "subject": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Message subject"}
            ),
            "content": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 8,
                    "placeholder": "Message content",
                }
            ),
            "template": forms.Select(attrs={"class": "form-control"}),
            "target_audience": forms.Select(attrs={"class": "form-control"}),
            "scheduled_at": forms.DateTimeInput(
                attrs={"class": "form-control", "type": "datetime-local"}
            ),
            "priority": forms.Select(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Filter templates to only active ones
        self.fields["template"].queryset = MessageTemplate.objects.filter(
            is_active=True
        )
        self.fields["template"].required = False
        self.fields["scheduled_at"].required = False

    def clean_target_filters(self):
        """Validate JSON format for target filters"""
        target_filters = self.cleaned_data.get("target_filters")

        if target_filters:
            try:
                filters = json.loads(target_filters)
                if not isinstance(filters, dict):
                    raise ValidationError("Target filters must be a JSON object")
                return filters
            except json.JSONDecodeError:
                raise ValidationError("Invalid JSON format in target filters")

        return {}

    def clean_scheduled_at(self):
        """Validate scheduled date is in the future"""
        scheduled_at = self.cleaned_data.get("scheduled_at")

        if scheduled_at and scheduled_at <= timezone.now():
            raise ValidationError("Scheduled time must be in the future")

        return scheduled_at


class MessageTemplateForm(forms.ModelForm):
    """Form for creating and editing message templates"""

    supported_channels = forms.MultipleChoiceField(
        choices=CommunicationChannel.choices,
        widget=CheckboxSelectMultiple,
        initial=[CommunicationChannel.EMAIL],
        help_text="Select supported communication channels",
    )

    variables = forms.CharField(
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 4,
                "placeholder": '{"student_name": "Student full name", "due_date": "Payment due date"}',
            }
        ),
        required=False,
        help_text="JSON object defining available template variables",
    )

    class Meta:
        model = MessageTemplate
        fields = [
            "name",
            "description",
            "template_type",
            "subject_template",
            "content_template",
            "supported_channels",
            "variables",
            "is_active",
        ]
        widgets = {
            "name": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Template name"}
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": "Template description",
                }
            ),
            "template_type": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "e.g., financial, academic, general",
                }
            ),
            "subject_template": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Subject line template with variables",
                }
            ),
            "content_template": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 10,
                    "placeholder": "Message content template with variables",
                }
            ),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def clean_variables(self):
        """Validate JSON format for variables"""
        variables = self.cleaned_data.get("variables")

        if variables:
            try:
                vars_dict = json.loads(variables)
                if not isinstance(vars_dict, dict):
                    raise ValidationError("Variables must be a JSON object")
                return vars_dict
            except json.JSONDecodeError:
                raise ValidationError("Invalid JSON format in variables")

        return {}


class CommunicationPreferenceForm(forms.ModelForm):
    """Form for user communication preferences"""

    class Meta:
        model = CommunicationPreference
        fields = [
            "email_enabled",
            "sms_enabled",
            "push_enabled",
            "whatsapp_enabled",
            "academic_notifications",
            "financial_notifications",
            "attendance_notifications",
            "general_announcements",
            "marketing_messages",
            "quiet_hours_start",
            "quiet_hours_end",
            "weekend_notifications",
            "preferred_language",
            "digest_frequency",
        ]
        widgets = {
            "email_enabled": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "sms_enabled": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "push_enabled": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "whatsapp_enabled": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),
            "academic_notifications": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),
            "financial_notifications": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),
            "attendance_notifications": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),
            "general_announcements": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),
            "marketing_messages": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),
            "weekend_notifications": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),
            "quiet_hours_start": forms.TimeInput(
                attrs={"class": "form-control", "type": "time"}
            ),
            "quiet_hours_end": forms.TimeInput(
                attrs={"class": "form-control", "type": "time"}
            ),
            "preferred_language": forms.Select(attrs={"class": "form-control"}),
            "digest_frequency": forms.Select(attrs={"class": "form-control"}),
        }


class MessageThreadForm(forms.ModelForm):
    """Form for creating message threads"""

    participants = forms.ModelMultipleChoiceField(
        queryset=User.objects.filter(is_active=True),
        widget=forms.CheckboxSelectMultiple,
        help_text="Select participants for this conversation",
    )

    initial_message = forms.CharField(
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 4,
                "placeholder": "Type your message here...",
            }
        ),
        required=False,
        help_text="Optional initial message to start the conversation",
    )

    class Meta:
        model = MessageThread
        fields = ["subject", "participants", "is_group", "thread_type"]
        widgets = {
            "subject": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Conversation subject"}
            ),
            "is_group": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "thread_type": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "e.g., general, academic, administrative",
                }
            ),
        }

    def clean_participants(self):
        """Validate participants selection"""
        participants = self.cleaned_data.get("participants")

        if not participants:
            raise ValidationError("At least one participant must be selected")

        return participants


class DirectMessageForm(forms.ModelForm):
    """Form for sending direct messages"""

    class Meta:
        model = DirectMessage
        fields = ["content", "attachment"]
        widgets = {
            "content": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 4,
                    "placeholder": "Type your message here...",
                }
            ),
            "attachment": forms.FileInput(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["attachment"].required = False


class QuickNotificationForm(forms.Form):
    """Quick form for sending simple notifications"""

    recipients = forms.ModelMultipleChoiceField(
        queryset=User.objects.filter(is_active=True),
        widget=forms.CheckboxSelectMultiple,
        help_text="Select recipients",
    )

    title = forms.CharField(
        max_length=200,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Notification title"}
        ),
    )

    content = forms.CharField(
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 4,
                "placeholder": "Notification content",
            }
        )
    )

    notification_type = forms.CharField(
        max_length=50,
        initial="general",
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "e.g., general, urgent, reminder",
            }
        ),
    )

    priority = forms.ChoiceField(
        choices=Priority.choices,
        initial=Priority.MEDIUM,
        widget=forms.Select(attrs={"class": "form-control"}),
    )

    channels = forms.MultipleChoiceField(
        choices=CommunicationChannel.choices,
        widget=CheckboxSelectMultiple,
        initial=[CommunicationChannel.IN_APP],
        help_text="Select communication channels",
    )

    def clean_recipients(self):
        """Validate recipients selection"""
        recipients = self.cleaned_data.get("recipients")

        if not recipients:
            raise ValidationError("At least one recipient must be selected")

        return recipients


class BulkNotificationForm(forms.Form):
    """Form for sending bulk notifications with audience targeting"""

    title = forms.CharField(
        max_length=200,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Notification title"}
        ),
    )

    content = forms.CharField(
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 6,
                "placeholder": "Notification content",
            }
        )
    )

    target_audience = forms.ChoiceField(
        choices=TargetAudience.choices,
        widget=forms.Select(attrs={"class": "form-control"}),
        help_text="Select target audience",
    )

    notification_type = forms.CharField(
        max_length=50,
        initial="general",
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "e.g., general, academic, financial",
            }
        ),
    )

    priority = forms.ChoiceField(
        choices=Priority.choices,
        initial=Priority.MEDIUM,
        widget=forms.Select(attrs={"class": "form-control"}),
    )

    channels = forms.MultipleChoiceField(
        choices=CommunicationChannel.choices,
        widget=CheckboxSelectMultiple,
        initial=[CommunicationChannel.IN_APP],
        help_text="Select communication channels",
    )

    scheduled_at = forms.DateTimeField(
        widget=forms.DateTimeInput(
            attrs={"class": "form-control", "type": "datetime-local"}
        ),
        required=False,
        help_text="Optional: Schedule for later sending",
    )

    additional_filters = forms.CharField(
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 3,
                "placeholder": '{"sections": [1, 2], "grades": [3, 4]}',
            }
        ),
        required=False,
        help_text="JSON object with additional targeting filters",
    )

    def clean_additional_filters(self):
        """Validate JSON format for additional filters"""
        filters = self.cleaned_data.get("additional_filters")

        if filters:
            try:
                filters_dict = json.loads(filters)
                if not isinstance(filters_dict, dict):
                    raise ValidationError("Additional filters must be a JSON object")
                return filters_dict
            except json.JSONDecodeError:
                raise ValidationError("Invalid JSON format in additional filters")

        return {}

    def clean_scheduled_at(self):
        """Validate scheduled date is in the future"""
        scheduled_at = self.cleaned_data.get("scheduled_at")

        if scheduled_at and scheduled_at <= timezone.now():
            raise ValidationError("Scheduled time must be in the future")

        return scheduled_at


class CommunicationSearchForm(forms.Form):
    """Form for searching communications"""

    search_type = forms.ChoiceField(
        choices=[
            ("all", "All Communications"),
            ("announcements", "Announcements"),
            ("notifications", "Notifications"),
            ("messages", "Direct Messages"),
            ("bulk_messages", "Bulk Messages"),
        ],
        widget=forms.Select(attrs={"class": "form-control"}),
        initial="all",
    )

    query = forms.CharField(
        max_length=200,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Search communications..."}
        ),
        required=False,
    )

    date_from = forms.DateField(
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
        required=False,
    )

    date_to = forms.DateField(
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
        required=False,
    )

    priority = forms.ChoiceField(
        choices=[("", "Any Priority")] + Priority.choices,
        widget=forms.Select(attrs={"class": "form-control"}),
        required=False,
    )

    status = forms.ChoiceField(
        choices=[("", "Any Status")]
        + [
            ("read", "Read"),
            ("unread", "Unread"),
            ("sent", "Sent"),
            ("failed", "Failed"),
        ],
        widget=forms.Select(attrs={"class": "form-control"}),
        required=False,
    )

    def clean(self):
        """Validate date range"""
        cleaned_data = super().clean()
        date_from = cleaned_data.get("date_from")
        date_to = cleaned_data.get("date_to")

        if date_from and date_to and date_from > date_to:
            raise ValidationError("Start date must be before end date")

        return cleaned_data
