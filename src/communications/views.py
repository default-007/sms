"""
Django views for Communications module.
Handles web interface for notifications, announcements, messaging, and analytics.
"""

import json
from datetime import datetime, timedelta

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.db.models import Avg, Count, Q
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    UpdateView,
)

from .forms import (
    AnnouncementForm,
    BulkMessageForm,
    BulkNotificationForm,
    CommunicationPreferenceForm,
    CommunicationSearchForm,
    DirectMessageForm,
    MessageTemplateForm,
    MessageThreadForm,
    QuickNotificationForm,
)
from .models import (
    Announcement,
    BulkMessage,
    CommunicationAnalytics,
    CommunicationChannel,
    CommunicationLog,
    CommunicationPreference,
    DirectMessage,
    MessageStatus,
    MessageTemplate,
    MessageThread,
    Notification,
    Priority,
    TargetAudience,
)
from .services import (
    AnnouncementService,
    CommunicationAnalyticsService,
    MessagingService,
    NotificationService,
)

User = get_user_model()


# Dashboard and Overview Views


@login_required
def communications_dashboard(request):
    """Main communications dashboard"""

    context = {
        "title": "Communications Dashboard",
        "unread_notifications": NotificationService.get_unread_count(request.user),
        "unread_messages": MessagingService.get_unread_message_count(request.user),
        "recent_announcements": AnnouncementService.get_active_announcements(
            request.user
        )[:5],
        "recent_notifications": NotificationService.get_user_notifications(
            request.user, limit=10
        ),
    }

    # Add analytics for staff/admin users
    if request.user.is_staff:
        summary = CommunicationAnalyticsService.get_communication_summary(days=7)
        context["analytics_summary"] = summary

    return render(request, "communications/dashboard.html", context)


@login_required
def notifications_overview(request):
    """Notifications overview page"""

    notifications = NotificationService.get_user_notifications(request.user, limit=50)
    unread_count = NotificationService.get_unread_count(request.user)

    # Pagination
    paginator = Paginator(notifications, 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "title": "My Notifications",
        "notifications": page_obj,
        "unread_count": unread_count,
        "page_obj": page_obj,
    }

    return render(request, "communications/notifications/overview.html", context)


# Announcement Views


class AnnouncementListView(LoginRequiredMixin, ListView):
    """List view for announcements"""

    model = Announcement
    template_name = "communications/announcements/list.html"
    context_object_name = "announcements"
    paginate_by = 20

    def get_queryset(self):
        queryset = Announcement.objects.all().order_by("-created_at")

        # Filter by search query
        search = self.request.GET.get("search")
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) | Q(content__icontains=search)
            )

        # Filter by status
        status = self.request.GET.get("status")
        if status == "active":
            queryset = queryset.filter(is_active=True)
        elif status == "inactive":
            queryset = queryset.filter(is_active=False)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Announcements"
        context["search_query"] = self.request.GET.get("search", "")
        context["status_filter"] = self.request.GET.get("status", "")
        return context


class AnnouncementDetailView(LoginRequiredMixin, DetailView):
    """Detail view for announcements"""

    model = Announcement
    template_name = "communications/announcements/detail.html"
    context_object_name = "announcement"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = self.object.title

        # Add analytics if user is staff
        if self.request.user.is_staff:
            context["can_edit"] = True
            context["notifications"] = self.object.notifications.all()[:10]

        return context


class AnnouncementCreateView(LoginRequiredMixin, CreateView):
    """Create view for announcements"""

    model = Announcement
    form_class = AnnouncementForm
    template_name = "communications/announcements/form.html"
    success_url = reverse_lazy("communications:announcement_list")

    def form_valid(self, form):
        """Handle valid form submission"""

        # Use service to create announcement
        announcement = AnnouncementService.create_announcement(
            title=form.cleaned_data["title"],
            content=form.cleaned_data["content"],
            created_by=self.request.user,
            target_audience=form.cleaned_data.get(
                "target_audience", TargetAudience.ALL
            ),
            target_grades=form.cleaned_data.get("target_grades"),
            target_classes=form.cleaned_data.get("target_classes"),
            target_sections=form.cleaned_data.get("target_sections"),
            priority=form.cleaned_data.get("priority", Priority.MEDIUM),
            channels=form.cleaned_data.get("channels", [CommunicationChannel.IN_APP]),
            start_date=form.cleaned_data.get("start_date"),
            end_date=form.cleaned_data.get("end_date"),
            attachment=form.cleaned_data.get("attachment"),
        )

        messages.success(
            self.request,
            f'Announcement "{announcement.title}" created and sent to {announcement.total_recipients} recipients.',
        )

        return redirect(self.success_url)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Create Announcement"
        context["form_action"] = "Create"
        return context


class AnnouncementUpdateView(LoginRequiredMixin, UpdateView):
    """Update view for announcements"""

    model = Announcement
    form_class = AnnouncementForm
    template_name = "communications/announcements/form.html"

    def get_success_url(self):
        return reverse(
            "communications:announcement_detail", kwargs={"pk": self.object.pk}
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = f"Edit Announcement: {self.object.title}"
        context["form_action"] = "Update"
        return context


# Messaging Views


class MessageThreadListView(LoginRequiredMixin, ListView):
    """List view for message threads"""

    model = MessageThread
    template_name = "communications/messages/thread_list.html"
    context_object_name = "threads"
    paginate_by = 20

    def get_queryset(self):
        return MessageThread.objects.filter(
            participants=self.request.user, is_active=True
        ).order_by("-last_message_at")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Messages"
        context["unread_count"] = MessagingService.get_unread_message_count(
            self.request.user
        )
        return context


class MessageThreadDetailView(LoginRequiredMixin, DetailView):
    """Detail view for message threads"""

    model = MessageThread
    template_name = "communications/messages/thread_detail.html"
    context_object_name = "thread"

    def get_queryset(self):
        return MessageThread.objects.filter(participants=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = self.object.subject

        # Get messages with pagination
        messages_list = self.object.messages.all().order_by("sent_at")
        paginator = Paginator(messages_list, 50)
        page_number = self.request.GET.get("page")
        context["messages"] = paginator.get_page(page_number)

        # Form for new messages
        context["message_form"] = DirectMessageForm()

        # Mark messages as read
        for message in messages_list.exclude(sender=self.request.user):
            MessagingService.mark_message_as_read(message, self.request.user)

        return context

    def post(self, request, *args, **kwargs):
        """Handle message posting"""
        self.object = self.get_object()
        form = DirectMessageForm(request.POST, request.FILES)

        if form.is_valid():
            message = MessagingService.send_message(
                thread=self.object,
                sender=request.user,
                content=form.cleaned_data["content"],
                attachment=form.cleaned_data.get("attachment"),
            )

            # Mark as read by sender
            MessagingService.mark_message_as_read(message, request.user)

            messages.success(request, "Message sent successfully.")
            return redirect("communications:thread_detail", pk=self.object.pk)

        # If form is invalid, redisplay with errors
        context = self.get_context_data()
        context["message_form"] = form
        return render(request, self.template_name, context)


class MessageThreadCreateView(LoginRequiredMixin, CreateView):
    """Create view for message threads"""

    model = MessageThread
    form_class = MessageThreadForm
    template_name = "communications/messages/thread_form.html"

    def form_valid(self, form):
        """Handle valid form submission"""

        participants = list(form.cleaned_data["participants"])
        if self.request.user not in participants:
            participants.append(self.request.user)

        # Create thread using service
        thread = MessagingService.create_thread(
            subject=form.cleaned_data["subject"],
            participants=participants,
            created_by=self.request.user,
            is_group=form.cleaned_data["is_group"],
            thread_type=form.cleaned_data.get("thread_type", "general"),
        )

        # Send initial message if provided
        initial_message = form.cleaned_data.get("initial_message")
        if initial_message:
            MessagingService.send_message(
                thread=thread, sender=self.request.user, content=initial_message
            )

        messages.success(self.request, "Conversation started successfully.")
        return redirect("communications:thread_detail", pk=thread.pk)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Start New Conversation"
        return context


# Template Management Views


class MessageTemplateListView(LoginRequiredMixin, ListView):
    """List view for message templates"""

    model = MessageTemplate
    template_name = "communications/templates/list.html"
    context_object_name = "templates"
    paginate_by = 20

    def get_queryset(self):
        queryset = MessageTemplate.objects.filter(is_active=True).order_by("name")

        # Filter by template type
        template_type = self.request.GET.get("type")
        if template_type:
            queryset = queryset.filter(template_type=template_type)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Message Templates"
        context["template_types"] = MessageTemplate.objects.values_list(
            "template_type", flat=True
        ).distinct()
        return context


class MessageTemplateCreateView(LoginRequiredMixin, CreateView):
    """Create view for message templates"""

    model = MessageTemplate
    form_class = MessageTemplateForm
    template_name = "communications/templates/form.html"
    success_url = reverse_lazy("communications:template_list")

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, "Template created successfully.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Create Message Template"
        context["form_action"] = "Create"
        return context


# Bulk Messaging Views


class BulkMessageListView(LoginRequiredMixin, ListView):
    """List view for bulk messages"""

    model = BulkMessage
    template_name = "communications/bulk/list.html"
    context_object_name = "bulk_messages"
    paginate_by = 20

    def get_queryset(self):
        return BulkMessage.objects.all().order_by("-created_at")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Bulk Messages"
        return context


class BulkMessageCreateView(LoginRequiredMixin, CreateView):
    """Create view for bulk messages"""

    model = BulkMessage
    form_class = BulkMessageForm
    template_name = "communications/bulk/form.html"
    success_url = reverse_lazy("communications:bulk_message_list")

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, "Bulk message created successfully.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Create Bulk Message"
        return context


# Quick Actions Views


@login_required
def quick_notification(request):
    """Quick notification sending form"""

    if request.method == "POST":
        form = QuickNotificationForm(request.POST)
        if form.is_valid():
            notifications = NotificationService.bulk_create_notifications(
                users=form.cleaned_data["recipients"],
                title=form.cleaned_data["title"],
                content=form.cleaned_data["content"],
                notification_type=form.cleaned_data["notification_type"],
                priority=form.cleaned_data["priority"],
                channels=form.cleaned_data["channels"],
            )

            messages.success(
                request, f"Successfully sent {len(notifications)} notifications."
            )
            return redirect("communications:dashboard")
    else:
        form = QuickNotificationForm()

    context = {"title": "Send Quick Notification", "form": form}

    return render(request, "communications/quick/notification.html", context)


@login_required
def bulk_notification(request):
    """Bulk notification sending form"""

    if request.method == "POST":
        form = BulkNotificationForm(request.POST)
        if form.is_valid():
            # Handle bulk notification sending
            # This could be queued as a background task

            messages.success(request, "Bulk notification queued for sending.")
            return redirect("communications:dashboard")
    else:
        form = BulkNotificationForm()

    context = {"title": "Send Bulk Notification", "form": form}

    return render(request, "communications/quick/bulk_notification.html", context)


# Preferences Views


@login_required
def communication_preferences(request):
    """User communication preferences"""

    preference, created = CommunicationPreference.objects.get_or_create(
        user=request.user
    )

    if request.method == "POST":
        form = CommunicationPreferenceForm(request.POST, instance=preference)
        if form.is_valid():
            form.save()
            messages.success(request, "Communication preferences updated successfully.")
            return redirect("communications:preferences")
    else:
        form = CommunicationPreferenceForm(instance=preference)

    context = {
        "title": "Communication Preferences",
        "form": form,
        "preference": preference,
    }

    return render(request, "communications/preferences.html", context)


# Analytics Views


@login_required
def analytics_dashboard(request):
    """Communications analytics dashboard"""

    if not request.user.is_staff:
        return HttpResponseForbidden("Access denied")

    days = int(request.GET.get("days", 30))
    summary = CommunicationAnalyticsService.get_communication_summary(days)

    # Get recent analytics
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=days)

    analytics = CommunicationAnalytics.objects.filter(
        date__gte=start_date, date__lte=end_date
    ).order_by("date")

    context = {
        "title": "Communications Analytics",
        "summary": summary,
        "analytics": analytics,
        "days": days,
        "date_range": f"{start_date} to {end_date}",
    }

    return render(request, "communications/analytics/dashboard.html", context)


# AJAX Views


@login_required
def mark_notification_read(request, notification_id):
    """AJAX view to mark notification as read"""

    if request.method == "POST":
        success = NotificationService.mark_as_read(notification_id, request.user)
        return JsonResponse({"success": success})

    return JsonResponse({"success": False})


@login_required
def mark_all_notifications_read(request):
    """AJAX view to mark all notifications as read"""

    if request.method == "POST":
        notifications = Notification.objects.filter(user=request.user, is_read=False)

        count = 0
        for notification in notifications:
            notification.mark_as_read()
            count += 1

        return JsonResponse({"success": True, "count": count})

    return JsonResponse({"success": False})


@login_required
def get_unread_counts(request):
    """AJAX view to get unread counts"""

    return JsonResponse(
        {
            "notifications": NotificationService.get_unread_count(request.user),
            "messages": MessagingService.get_unread_message_count(request.user),
        }
    )


@login_required
def search_users(request):
    """AJAX view to search users for messaging"""

    query = request.GET.get("q", "")
    if len(query) < 2:
        return JsonResponse({"users": []})

    users = User.objects.filter(
        Q(username__icontains=query)
        | Q(first_name__icontains=query)
        | Q(last_name__icontains=query)
        | Q(email__icontains=query),
        is_active=True,
    ).exclude(id=request.user.id)[:10]

    user_data = []
    for user in users:
        user_data.append(
            {
                "id": user.id,
                "username": user.username,
                "full_name": user.get_full_name(),
                "email": user.email,
            }
        )

    return JsonResponse({"users": user_data})


@login_required
def template_preview(request, template_id):
    """AJAX view to preview message template"""

    template = get_object_or_404(MessageTemplate, id=template_id)

    # Sample context for preview
    sample_context = {
        "user": request.user,
        "student_name": "John Doe",
        "parent_name": "Jane Doe",
        "school_name": "Sample School",
        "amount": "$500.00",
        "due_date": timezone.now().date(),
        "class_name": "Grade 5 North",
    }

    try:
        rendered_subject = template.render_subject(sample_context)
        rendered_content = template.render_content(sample_context)

        return JsonResponse(
            {"success": True, "subject": rendered_subject, "content": rendered_content}
        )
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})


# Communication Search


@login_required
def communication_search(request):
    """Search across all communications"""

    form = CommunicationSearchForm(request.GET)
    results = []

    if form.is_valid():
        search_type = form.cleaned_data.get("search_type", "all")
        query = form.cleaned_data.get("query", "")
        date_from = form.cleaned_data.get("date_from")
        date_to = form.cleaned_data.get("date_to")
        priority = form.cleaned_data.get("priority")
        status = form.cleaned_data.get("status")

        # Build base filters
        base_filters = {}
        if date_from:
            base_filters["created_at__gte"] = date_from
        if date_to:
            base_filters["created_at__lte"] = date_to
        if priority:
            base_filters["priority"] = priority

        # Search based on type
        if search_type in ["all", "announcements"]:
            announcements = Announcement.objects.filter(**base_filters)
            if query:
                announcements = announcements.filter(
                    Q(title__icontains=query) | Q(content__icontains=query)
                )

            for announcement in announcements[:20]:
                results.append(
                    {
                        "type": "announcement",
                        "title": announcement.title,
                        "content": announcement.content[:200],
                        "created_at": announcement.created_at,
                        "url": reverse(
                            "communications:announcement_detail",
                            kwargs={"pk": announcement.pk},
                        ),
                    }
                )

        if search_type in ["all", "notifications"]:
            notifications = Notification.objects.filter(
                user=request.user, **base_filters
            )
            if query:
                notifications = notifications.filter(
                    Q(title__icontains=query) | Q(content__icontains=query)
                )
            if status:
                if status == "read":
                    notifications = notifications.filter(is_read=True)
                elif status == "unread":
                    notifications = notifications.filter(is_read=False)

            for notification in notifications[:20]:
                results.append(
                    {
                        "type": "notification",
                        "title": notification.title,
                        "content": notification.content[:200],
                        "created_at": notification.created_at,
                        "is_read": notification.is_read,
                    }
                )

    # Pagination
    paginator = Paginator(results, 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "title": "Search Communications",
        "form": form,
        "results": page_obj,
        "page_obj": page_obj,
        "total_results": len(results),
    }

    return render(request, "communications/search.html", context)


# Export Views


@login_required
def export_analytics(request):
    """Export analytics data"""

    if not request.user.is_staff:
        return HttpResponseForbidden("Access denied")

    # This would implement CSV/Excel export functionality
    # For now, just redirect back
    messages.info(request, "Export functionality coming soon.")
    return redirect("communications:analytics_dashboard")
