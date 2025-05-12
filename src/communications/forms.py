from django import forms
from django.utils.translation import gettext_lazy as _
from .models import Announcement, Message, Notification
from src.courses.models import Class


class AnnouncementForm(forms.ModelForm):
    """Form for creating and editing announcements."""

    class Meta:
        model = Announcement
        fields = [
            "title",
            "content",
            "target_audience",
            "target_classes",
            "start_date",
            "end_date",
            "is_active",
            "attachment",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control"}),
            "content": forms.Textarea(attrs={"class": "form-control", "rows": 5}),
            "target_audience": forms.Select(attrs={"class": "form-control"}),
            "start_date": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}
            ),
            "end_date": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}
            ),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "attachment": forms.FileInput(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Convert target_classes JSONField to a multiple select field
        self.fields["target_classes"] = forms.ModelMultipleChoiceField(
            queryset=Class.objects.all(),
            required=False,
            widget=forms.SelectMultiple(attrs={"class": "form-control"}),
            label=_("Target Classes"),
        )

        # If editing an existing announcement with target classes
        if self.instance.pk and self.instance.target_classes:
            self.fields["target_classes"].initial = Class.objects.filter(
                id__in=self.instance.target_classes
            )

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get("start_date")
        end_date = cleaned_data.get("end_date")

        if start_date and end_date and start_date > end_date:
            raise forms.ValidationError(_("End date must be after start date."))

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)

        # Convert selected Classes to a list of IDs for JSON storage
        target_classes = self.cleaned_data.get("target_classes")
        if target_classes:
            instance.target_classes = [cls.id for cls in target_classes]
        else:
            instance.target_classes = []

        if commit:
            instance.save()

        return instance


class MessageForm(forms.ModelForm):
    """Form for sending messages."""

    class Meta:
        model = Message
        fields = ["receiver", "subject", "content", "attachment"]
        widgets = {
            "receiver": forms.Select(attrs={"class": "form-control"}),
            "subject": forms.TextInput(attrs={"class": "form-control"}),
            "content": forms.Textarea(attrs={"class": "form-control", "rows": 5}),
            "attachment": forms.FileInput(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

        # If this is a reply to another message
        parent_message_id = kwargs.pop("parent_message_id", None)
        if parent_message_id:
            try:
                parent_message = Message.objects.get(id=parent_message_id)
                self.fields["subject"].initial = f"Re: {parent_message.subject}"
                self.fields["receiver"].initial = parent_message.sender
            except Message.DoesNotExist:
                pass


class BulkMessageForm(forms.Form):
    """Form for sending messages to multiple recipients."""

    RECIPIENT_CHOICES = (
        ("all_students", _("All Students")),
        ("all_teachers", _("All Teachers")),
        ("all_parents", _("All Parents")),
        ("class", _("Specific Class")),
        ("custom", _("Custom Recipients")),
    )

    recipient_type = forms.ChoiceField(
        choices=RECIPIENT_CHOICES,
        widget=forms.RadioSelect(attrs={"class": "form-check-input"}),
        initial="all_students",
        label=_("Recipient Type"),
    )

    class_id = forms.ModelChoiceField(
        queryset=Class.objects.all(),
        required=False,
        widget=forms.Select(attrs={"class": "form-control"}),
        label=_("Class"),
    )

    custom_recipients = forms.ModelMultipleChoiceField(
        queryset=None,  # Will be set in __init__
        required=False,
        widget=forms.SelectMultiple(attrs={"class": "form-control"}),
        label=_("Custom Recipients"),
    )

    subject = forms.CharField(
        max_length=255,
        widget=forms.TextInput(attrs={"class": "form-control"}),
        label=_("Subject"),
    )

    content = forms.CharField(
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 5}),
        label=_("Content"),
    )

    attachment = forms.FileField(
        required=False,
        widget=forms.FileInput(attrs={"class": "form-control"}),
        label=_("Attachment"),
    )

    def __init__(self, *args, **kwargs):
        from django.contrib.auth import get_user_model

        User = get_user_model()

        super().__init__(*args, **kwargs)

        # Set queryset for custom_recipients
        self.fields["custom_recipients"].queryset = User.objects.all()

    def clean(self):
        cleaned_data = super().clean()
        recipient_type = cleaned_data.get("recipient_type")

        if recipient_type == "class" and not cleaned_data.get("class_id"):
            raise forms.ValidationError(_("Please select a class."))

        if recipient_type == "custom" and not cleaned_data.get("custom_recipients"):
            raise forms.ValidationError(_("Please select at least one recipient."))

        return cleaned_data


class NotificationFilterForm(forms.Form):
    """Form for filtering notifications."""

    type_filter = forms.ChoiceField(
        choices=[("", _("All Types"))] + list(Notification.NOTIFICATION_TYPES),
        required=False,
        widget=forms.Select(attrs={"class": "form-control"}),
        label=_("Type"),
    )

    read_status = forms.ChoiceField(
        choices=[
            ("", _("All")),
            ("read", _("Read")),
            ("unread", _("Unread")),
        ],
        required=False,
        widget=forms.Select(attrs={"class": "form-control"}),
        label=_("Status"),
    )

    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
        label=_("From Date"),
    )

    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
        label=_("To Date"),
    )
