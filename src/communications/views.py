from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import (
    ListView,
    DetailView,
    CreateView,
    UpdateView,
    DeleteView,
)
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.auth.decorators import login_required, permission_required
from django.urls import reverse_lazy
from django.contrib import messages
from django.db.models import Q
from django.utils import timezone
from django.http import JsonResponse

from .models import Announcement, Message, Notification, SMSLog, EmailLog
from .forms import (
    AnnouncementForm,
    MessageForm,
    BulkMessageForm,
    NotificationFilterForm,
)
from .services import NotificationService, MessageService, CommunicationService


class AnnouncementListView(LoginRequiredMixin, ListView):
    """View for listing announcements."""

    model = Announcement
    template_name = "communications/announcement_list.html"
    context_object_name = "announcements"
    paginate_by = 10

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        today = timezone.now().date()

        # Base filter: only active announcements
        queryset = queryset.filter(is_active=True, start_date__lte=today)

        # Add end_date filter if specified
        queryset = queryset.filter(Q(end_date__isnull=True) | Q(end_date__gte=today))

        # Filter by audience
        user_type = None
        if hasattr(user, "student_profile"):
            user_type = "students"
        elif hasattr(user, "teacher_profile"):
            user_type = "teachers"
        elif hasattr(user, "parent_profile"):
            user_type = "parents"
        elif user.is_staff:
            user_type = "staff"

        # Apply audience filter
        if user_type:
            queryset = queryset.filter(
                Q(target_audience="all") | Q(target_audience=user_type)
            )

        # Filter by class if user is a student
        if user_type == "students" and hasattr(user, "student_profile"):
            current_class = user.student_profile.current_class
            if current_class:
                queryset = queryset.filter(
                    Q(target_classes__isnull=True)
                    | Q(target_classes__contains=[current_class.id])
                )

        # Search functionality
        search_query = self.request.GET.get("search")
        if search_query:
            queryset = queryset.filter(
                Q(title__icontains=search_query) | Q(content__icontains=search_query)
            )

        return queryset


class AnnouncementDetailView(LoginRequiredMixin, DetailView):
    """View for viewing a single announcement."""

    model = Announcement
    template_name = "communications/announcement_detail.html"
    context_object_name = "announcement"


class AnnouncementCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    """View for creating a new announcement."""

    model = Announcement
    form_class = AnnouncementForm
    template_name = "communications/announcement_form.html"
    success_url = reverse_lazy("announcement-list")
    permission_required = "communications.add_announcement"

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        response = super().form_valid(form)

        # Create notifications for target users
        NotificationService.create_announcement_notifications(self.object)

        messages.success(self.request, "Announcement created successfully.")
        return response


class AnnouncementUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    """View for updating an announcement."""

    model = Announcement
    form_class = AnnouncementForm
    template_name = "communications/announcement_form.html"
    success_url = reverse_lazy("announcement-list")
    permission_required = "communications.change_announcement"

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Announcement updated successfully.")
        return response


class AnnouncementDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    """View for deleting an announcement."""

    model = Announcement
    template_name = "communications/announcement_confirm_delete.html"
    success_url = reverse_lazy("announcement-list")
    permission_required = "communications.delete_announcement"

    def delete(self, request, *args, **kwargs):
        messages.success(request, "Announcement deleted successfully.")
        return super().delete(request, *args, **kwargs)


class MessageListView(LoginRequiredMixin, ListView):
    """View for listing messages."""

    model = Message
    template_name = "communications/message_list.html"
    context_object_name = "messages"
    paginate_by = 15

    def get_queryset(self):
        queryset = Message.objects.filter(
            Q(sender=self.request.user) | Q(receiver=self.request.user)
        ).select_related("sender", "receiver")

        # Filter by inbox/sent
        view_type = self.request.GET.get("type", "inbox")
        if view_type == "inbox":
            queryset = queryset.filter(receiver=self.request.user)
        elif view_type == "sent":
            queryset = queryset.filter(sender=self.request.user)

        # Filter by read status
        read_status = self.request.GET.get("read")
        if read_status == "read":
            queryset = queryset.filter(is_read=True)
        elif read_status == "unread":
            queryset = queryset.filter(is_read=False)

        # Search functionality
        search_query = self.request.GET.get("search")
        if search_query:
            queryset = queryset.filter(
                Q(subject__icontains=search_query)
                | Q(content__icontains=search_query)
                | Q(sender__first_name__icontains=search_query)
                | Q(sender__last_name__icontains=search_query)
                | Q(receiver__first_name__icontains=search_query)
                | Q(receiver__last_name__icontains=search_query)
            )

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["view_type"] = self.request.GET.get("type", "inbox")
        context["unread_count"] = Message.objects.filter(
            receiver=self.request.user, is_read=False
        ).count()
        return context


class MessageDetailView(LoginRequiredMixin, DetailView):
    """View for viewing a single message."""

    model = Message
    template_name = "communications/message_detail.html"
    context_object_name = "message"

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)

        # Check if user has permission to view this message
        if obj.sender != self.request.user and obj.receiver != self.request.user:
            raise PermissionDenied("You don't have permission to view this message.")

        # Mark as read if the user is the receiver
        if obj.receiver == self.request.user and not obj.is_read:
            obj.is_read = True
            obj.read_at = timezone.now()
            obj.save()

            # Also mark related notification as read
            Notification.objects.filter(
                user=self.request.user,
                notification_type="message",
                reference_id=str(obj.id),
            ).update(is_read=True, read_at=timezone.now())

        return obj

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["reply_form"] = MessageForm(
            user=self.request.user, initial={"receiver": self.object.sender}
        )
        # Get the conversation thread
        if self.object.parent_message:
            # This is a reply, get the original message and all replies
            original = self.object
            while original.parent_message:
                original = original.parent_message

            context["thread"] = Message.objects.filter(
                Q(id=original.id) | Q(parent_message=original)
            ).order_by("sent_at")
        else:
            # This is an original message, get all replies
            context["thread"] = Message.objects.filter(
                Q(id=self.object.id) | Q(parent_message=self.object)
            ).order_by("sent_at")

        return context


class MessageCreateView(LoginRequiredMixin, CreateView):
    """View for creating a new message."""

    model = Message
    form_class = MessageForm
    template_name = "communications/message_form.html"
    success_url = reverse_lazy("message-list")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user

        # If this is a reply to another message
        parent_id = self.request.GET.get("reply_to")
        if parent_id:
            try:
                parent = Message.objects.get(id=parent_id)
                if (
                    parent.sender == self.request.user
                    or parent.receiver == self.request.user
                ):
                    kwargs["parent_message_id"] = parent_id
            except Message.DoesNotExist:
                pass

        return kwargs

    def form_valid(self, form):
        form.instance.sender = self.request.user

        # If this is a reply to another message
        parent_id = self.request.GET.get("reply_to")
        if parent_id:
            try:
                parent = Message.objects.get(id=parent_id)
                if (
                    parent.sender == self.request.user
                    or parent.receiver == self.request.user
                ):
                    form.instance.parent_message = parent
            except Message.DoesNotExist:
                pass

        response = super().form_valid(form)

        # Create a notification for the recipient
        NotificationService.create_message_notification(self.object)

        messages.success(self.request, "Message sent successfully.")
        return response


@login_required
@permission_required("communications.add_message")
def bulk_message_view(request):
    """View for sending messages to multiple recipients."""
    if request.method == "POST":
        form = BulkMessageForm(request.POST, request.FILES)
        if form.is_valid():
            # Process the form and send messages
            recipient_type = form.cleaned_data["recipient_type"]
            subject = form.cleaned_data["subject"]
            content = form.cleaned_data["content"]
            attachment = form.cleaned_data.get("attachment")

            # Get recipients based on the selected type
            recipients = MessageService.get_recipients_by_type(
                recipient_type,
                form.cleaned_data.get("class_id"),
                form.cleaned_data.get("custom_recipients"),
            )

            # Send messages to all recipients
            message_count = MessageService.send_bulk_messages(
                request.user, recipients, subject, content, attachment
            )

            messages.success(request, f"Sent {message_count} messages successfully.")
            return redirect("message-list")
    else:
        form = BulkMessageForm()

    return render(request, "communications/bulk_message_form.html", {"form": form})


class NotificationListView(LoginRequiredMixin, ListView):
    """View for listing notifications."""

    model = Notification
    template_name = "communications/notification_list.html"
    context_object_name = "notifications"
    paginate_by = 20

    def get_queryset(self):
        queryset = Notification.objects.filter(user=self.request.user)

        # Apply filters from form
        form = NotificationFilterForm(self.request.GET)
        if form.is_valid():
            # Filter by notification type
            if form.cleaned_data.get("type_filter"):
                queryset = queryset.filter(
                    notification_type=form.cleaned_data["type_filter"]
                )

            # Filter by read status
            if form.cleaned_data.get("read_status"):
                if form.cleaned_data["read_status"] == "read":
                    queryset = queryset.filter(is_read=True)
                elif form.cleaned_data["read_status"] == "unread":
                    queryset = queryset.filter(is_read=False)

            # Filter by date range
            if form.cleaned_data.get("date_from"):
                queryset = queryset.filter(
                    created_at__date__gte=form.cleaned_data["date_from"]
                )
            if form.cleaned_data.get("date_to"):
                queryset = queryset.filter(
                    created_at__date__lte=form.cleaned_data["date_to"]
                )

        # Search functionality
        search_query = self.request.GET.get("search")
        if search_query:
            queryset = queryset.filter(
                Q(title__icontains=search_query) | Q(content__icontains=search_query)
            )

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["filter_form"] = NotificationFilterForm(self.request.GET)
        context["unread_count"] = Notification.objects.filter(
            user=self.request.user, is_read=False
        ).count()
        return context


@login_required
def mark_notification_read(request, pk):
    """View for marking a notification as read."""
    notification = get_object_or_404(Notification, pk=pk, user=request.user)

    if not notification.is_read:
        notification.is_read = True
        notification.read_at = timezone.now()
        notification.save()

    # If AJAX request, return JSON response
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({"status": "success"})

    # Otherwise redirect to the referer or notification list
    return redirect(request.META.get("HTTP_REFERER", "notification-list"))


@login_required
def mark_all_notifications_read(request):
    """View for marking all notifications as read."""
    now = timezone.now()
    updated = Notification.objects.filter(user=request.user, is_read=False).update(
        is_read=True, read_at=now
    )

    # If AJAX request, return JSON response
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({"status": "success", "count": updated})

    messages.success(request, f"Marked {updated} notifications as read.")
    return redirect("notification-list")


@login_required
@permission_required("communications.view_smslog")
def sms_log_list_view(request):
    """View for listing SMS logs."""
    # Only staff should access this
    if not request.user.is_staff:
        raise PermissionDenied

    logs = SMSLog.objects.all().order_by("-sent_at")

    # Apply filters
    status_filter = request.GET.get("status")
    if status_filter:
        logs = logs.filter(status=status_filter)

    # Date range filter
    date_from = request.GET.get("date_from")
    date_to = request.GET.get("date_to")
    if date_from:
        logs = logs.filter(sent_at__date__gte=date_from)
    if date_to:
        logs = logs.filter(sent_at__date__lte=date_to)

    # Search by recipient
    search = request.GET.get("search")
    if search:
        logs = logs.filter(
            Q(recipient_number__icontains=search)
            | Q(recipient_user__username__icontains=search)
            | Q(recipient_user__email__icontains=search)
            | Q(recipient_user__first_name__icontains=search)
            | Q(recipient_user__last_name__icontains=search)
        )

    return render(
        request,
        "communications/sms_log_list.html",
        {
            "logs": logs,
            "status_choices": SMSLog.STATUS_CHOICES,
        },
    )


@login_required
@permission_required("communications.view_emaillog")
def email_log_list_view(request):
    """View for listing email logs."""
    # Only staff should access this
    if not request.user.is_staff:
        raise PermissionDenied

    logs = EmailLog.objects.all().order_by("-sent_at")

    # Apply filters
    status_filter = request.GET.get("status")
    if status_filter:
        logs = logs.filter(status=status_filter)

    # Date range filter
    date_from = request.GET.get("date_from")
    date_to = request.GET.get("date_to")
    if date_from:
        logs = logs.filter(sent_at__date__gte=date_from)
    if date_to:
        logs = logs.filter(sent_at__date__lte=date_to)

    # Search by recipient or subject
    search = request.GET.get("search")
    if search:
        logs = logs.filter(
            Q(recipient_email__icontains=search)
            | Q(subject__icontains=search)
            | Q(recipient_user__username__icontains=search)
            | Q(recipient_user__email__icontains=search)
            | Q(recipient_user__first_name__icontains=search)
            | Q(recipient_user__last_name__icontains=search)
        )

    return render(
        request,
        "communications/email_log_list.html",
        {
            "logs": logs,
            "status_choices": EmailLog.STATUS_CHOICES,
        },
    )
