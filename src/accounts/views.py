# src/accounts/views.py

import csv
import json
import logging
from datetime import timedelta
from io import StringIO
from typing import Any, Dict

from django.contrib import messages
from django.contrib.auth import get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import (
    LoginView,
    LogoutView,
    PasswordChangeView,
    PasswordResetConfirmView,
    PasswordResetView,
)
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_POST
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    UpdateView,
)

from .decorators import admin_required, permission_required
from .forms import (
    BulkUserImportForm,
    CustomAuthenticationForm,
    CustomPasswordChangeForm,
    CustomPasswordResetForm,
    CustomSetPasswordForm,
    EnhancedUserCreationForm,
    ProfileForm,
    UserFilterForm,
    UserRoleForm,
    UserUpdateForm,
)
from .models import UserAuditLog, UserRole, UserRoleAssignment, UserSession
from .services import AuthenticationService, RoleService
from .services.analytics_service import UserAnalyticsService
from .tasks import bulk_user_import
from .utils import get_client_info

logger = logging.getLogger(__name__)
User = get_user_model()


# Authentication Views
class CustomLoginView(LoginView):
    """Enhanced login view with email/phone support and analytics."""

    form_class = CustomAuthenticationForm
    template_name = "accounts/login.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "page_title": "Login",
                "show_remember_me": True,
                "allow_registration": True,
                "allow_password_reset": True,
                "login_help_text": "Students can use their admission number to log in",
            }
        )
        return context

    def form_valid(self, form):
        """Handle successful login with enhanced logging."""
        user = form.get_user()
        client_info = get_client_info(self.request)

        # Log successful login
        UserAuditLog.objects.create(
            user=user,
            action="login",
            description="Successful web login",
            ip_address=client_info.get("ip_address"),
            user_agent=client_info.get("user_agent"),
            extra_data=client_info,
        )

        # Handle remember me
        if form.cleaned_data.get("remember_me"):
            self.request.session.set_expiry(1209600)  # 2 weeks
        else:
            self.request.session.set_expiry(0)  # Browser close

        # Call parent form_valid
        response = super().form_valid(form)

        messages.success(self.request, f"Welcome back, {user.get_display_name()}!")
        return response

    def form_invalid(self, form):
        """Handle failed login attempts."""
        identifier = form.cleaned_data.get("identifier", "")
        client_info = get_client_info(self.request)

        # Log failed attempt
        UserAuditLog.objects.create(
            action="login",
            description=f"Failed login attempt for identifier: {identifier}",
            ip_address=client_info.get("ip_address"),
            user_agent=client_info.get("user_agent"),
            extra_data=client_info,
            severity="medium",
        )

        messages.error(self.request, "Invalid login credentials. Please try again.")
        return super().form_invalid(form)


class CustomLogoutView(LogoutView):
    """Enhanced logout view with logging."""

    template_name = "accounts/logout.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            # Log logout
            AuthenticationService.logout_user(request.user, request)
            messages.success(request, "You have been logged out successfully.")

        return super().dispatch(request, *args, **kwargs)


class CustomPasswordChangeView(PasswordChangeView):
    """Enhanced password change view."""

    form_class = CustomPasswordChangeForm
    template_name = "accounts/password_change.html"
    success_url = reverse_lazy("accounts:profile")

    def form_valid(self, form):
        messages.success(self.request, "Your password has been changed successfully!")
        return super().form_valid(form)


class CustomPasswordResetView(PasswordResetView):
    """Enhanced password reset view with email/username support."""

    form_class = CustomPasswordResetForm
    template_name = "accounts/password_reset.html"
    success_url = reverse_lazy("accounts:password_reset_done")
    email_template_name = "accounts/emails/password_reset.html"
    subject_template_name = "accounts/emails/password_reset_subject.txt"


class CustomPasswordResetConfirmView(PasswordResetConfirmView):
    """Enhanced password reset confirm view."""

    form_class = CustomSetPasswordForm
    template_name = "accounts/password_reset_confirm.html"
    success_url = reverse_lazy("accounts:password_reset_complete")


# User Management Views
class UserListView(LoginRequiredMixin, ListView):
    """Enhanced user list view with filtering and analytics."""

    model = User
    template_name = "accounts/user_list.html"
    context_object_name = "users"
    paginate_by = 25

    @method_decorator(permission_required("users", "view"))
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def get_queryset(self):
        queryset = (
            User.objects.select_related("profile")
            .prefetch_related("role_assignments__role")
            .annotate(
                role_count=Count(
                    "role_assignments", filter=Q(role_assignments__is_active=True)
                )
            )
        )

        # Apply filters
        form = UserFilterForm(self.request.GET)
        if form.is_valid():
            if form.cleaned_data.get("search"):
                queryset = queryset.search(form.cleaned_data["search"])

            if form.cleaned_data.get("role"):
                queryset = queryset.filter(
                    role_assignments__role=form.cleaned_data["role"],
                    role_assignments__is_active=True,
                )

            if form.cleaned_data.get("status"):
                status = form.cleaned_data["status"]
                if status == "active":
                    queryset = queryset.filter(is_active=True)
                elif status == "inactive":
                    queryset = queryset.filter(is_active=False)
                elif status == "locked":
                    queryset = queryset.filter(failed_login_attempts__gte=5)
                elif status == "password_change":
                    queryset = queryset.filter(requires_password_change=True)
                elif status == "email_unverified":
                    queryset = queryset.filter(email_verified=False)
                elif status == "phone_unverified":
                    queryset = queryset.filter(phone_verified=False)

            if form.cleaned_data.get("date_joined_from"):
                queryset = queryset.filter(
                    date_joined__gte=form.cleaned_data["date_joined_from"]
                )

            if form.cleaned_data.get("date_joined_to"):
                queryset = queryset.filter(
                    date_joined__lte=form.cleaned_data["date_joined_to"]
                )

        return queryset.order_by("-date_joined")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Add filter form
        context["filter_form"] = UserFilterForm(self.request.GET)

        # Add analytics
        context["user_stats"] = User.objects.get_statistics()
        context["activity_stats"] = User.objects.get_activity_statistics()

        # Add roles for filtering
        context["roles"] = UserRole.objects.filter(is_active=True)

        # Add bulk action capabilities
        context["can_bulk_actions"] = self.request.user.has_permission(
            "users", "change"
        )

        return context


class UserDetailView(LoginRequiredMixin, DetailView):
    """Enhanced user detail view with comprehensive information."""

    model = User
    template_name = "accounts/user_detail.html"
    context_object_name = "user_obj"

    @method_decorator(permission_required("users", "view"))
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user_obj = self.get_object()

        # User analytics
        context["user_performance"] = UserAnalyticsService.get_user_performance_metrics(
            user_obj, days=30
        )

        # Role assignments
        context["role_assignments"] = user_obj.role_assignments.select_related(
            "role"
        ).filter(is_active=True)

        # Recent activity
        context["recent_activity"] = UserAuditLog.objects.filter(
            user=user_obj
        ).order_by("-timestamp")[:10]

        # Active sessions
        context["active_sessions"] = UserSession.objects.filter(
            user=user_obj, is_active=True
        ).order_by("-last_activity")

        # Login statistics
        context["login_stats"] = AuthenticationService.get_login_statistics(
            user_obj, days=30
        )

        # Security information
        context["security_info"] = {
            "is_locked": user_obj.is_account_locked(),
            "failed_attempts": user_obj.failed_login_attempts,
            "requires_password_change": user_obj.requires_password_change,
            "email_verified": user_obj.email_verified,
            "phone_verified": user_obj.phone_verified,
            "two_factor_enabled": user_obj.two_factor_enabled,
            "security_score": user_obj.get_security_score(),
        }

        # Permissions
        context["can_edit"] = (
            self.request.user.has_permission("users", "change")
            or self.request.user == user_obj
        )
        context["can_delete"] = self.request.user.has_permission("users", "delete")
        context["can_reset_password"] = self.request.user.has_permission(
            "users", "change"
        )

        return context


class UserCreateView(LoginRequiredMixin, CreateView):
    """Enhanced user creation view."""

    model = User
    form_class = EnhancedUserCreationForm
    template_name = "accounts/user_form.html"
    success_url = reverse_lazy("accounts:user_list")

    @method_decorator(permission_required("users", "add"))
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["created_by"] = self.request.user
        return kwargs

    def form_valid(self, form):
        response = super().form_valid(form)

        # Log user creation
        UserAuditLog.objects.create(
            user=self.object,
            action="create",
            description=f"User created by {self.request.user.username}",
            performed_by=self.request.user,
        )

        messages.success(
            self.request, f"User {self.object.username} created successfully!"
        )
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Create User"
        context["form_action"] = "Create"
        return context


class UserUpdateView(LoginRequiredMixin, UpdateView):
    """Enhanced user update view."""

    model = User
    form_class = UserUpdateForm
    template_name = "accounts/user_form.html"

    @method_decorator(permission_required("users", "change"))
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def get_success_url(self):
        return reverse("accounts:user_detail", kwargs={"pk": self.object.pk})

    def form_valid(self, form):
        response = super().form_valid(form)

        # Log user update
        UserAuditLog.objects.create(
            user=self.object,
            action="update",
            description=f"User updated by {self.request.user.username}",
            performed_by=self.request.user,
        )

        messages.success(self.request, "User updated successfully!")
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = f"Edit {self.object.username}"
        context["form_action"] = "Update"
        return context


class UserDeleteView(LoginRequiredMixin, DeleteView):
    """Enhanced user deletion view."""

    model = User
    template_name = "accounts/user_confirm_delete.html"
    success_url = reverse_lazy("accounts:user_list")

    @method_decorator(permission_required("users", "delete"))
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def delete(self, request, *args, **kwargs):
        user_obj = self.get_object()

        # Don't allow deletion of superusers or self
        if user_obj.is_superuser or user_obj == request.user:
            messages.error(request, "Cannot delete this user.")
            return redirect("accounts:user_detail", pk=user_obj.pk)

        # Log deletion
        UserAuditLog.objects.create(
            user=user_obj,
            action="delete",
            description=f"User deleted by {request.user.username}",
            performed_by=request.user,
        )

        messages.success(request, f"User {user_obj.username} deleted successfully.")
        return super().delete(request, *args, **kwargs)


# Role Management Views
class RoleListView(LoginRequiredMixin, ListView):
    """Role list view with statistics."""

    model = UserRole
    template_name = "accounts/role_list.html"
    context_object_name = "roles"

    @method_decorator(permission_required("roles", "view"))
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def get_queryset(self):
        return UserRole.objects.with_user_counts().order_by("name")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["role_stats"] = RoleService.get_role_statistics()
        context["role_distribution"] = (
            UserAnalyticsService.get_role_distribution_analytics()
        )
        return context


class RoleDetailView(LoginRequiredMixin, DetailView):
    """Role detail view with user assignments."""

    model = UserRole
    template_name = "accounts/role_detail.html"
    context_object_name = "role"

    @method_decorator(permission_required("roles", "view"))
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        role = self.get_object()

        # Users with this role
        context["users_with_role"] = User.objects.filter(
            role_assignments__role=role, role_assignments__is_active=True
        ).select_related("profile")

        # Role assignments
        context["role_assignments"] = (
            UserRoleAssignment.objects.filter(role=role, is_active=True)
            .select_related("user", "assigned_by")
            .order_by("-assigned_date")
        )

        # Permission details
        context["permission_details"] = role.get_all_permissions()
        context["inherited_permissions"] = role.get_inherited_permissions()

        return context


class RoleCreateView(LoginRequiredMixin, CreateView):
    """Role creation view."""

    model = UserRole
    form_class = UserRoleForm
    template_name = "accounts/role_form.html"
    success_url = reverse_lazy("accounts:role_list")

    @method_decorator(permission_required("roles", "add"))
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        response = super().form_valid(form)

        messages.success(self.request, f"Role {self.object.name} created successfully!")
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Create Role"
        context["form_action"] = "Create"
        return context


class RoleUpdateView(LoginRequiredMixin, UpdateView):
    """Role update view."""

    model = UserRole
    form_class = UserRoleForm
    template_name = "accounts/role_form.html"

    @method_decorator(permission_required("roles", "change"))
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def get_success_url(self):
        return reverse("accounts:role_detail", kwargs={"pk": self.object.pk})

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Role updated successfully!")
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = f"Edit {self.object.name}"
        context["form_action"] = "Update"
        return context


class RoleDeleteView(LoginRequiredMixin, DeleteView):
    """Role deletion view."""

    model = UserRole
    template_name = "accounts/role_confirm_delete.html"
    success_url = reverse_lazy("accounts:role_list")

    @method_decorator(permission_required("roles", "delete"))
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def delete(self, request, *args, **kwargs):
        role = self.get_object()

        # Don't allow deletion of system roles
        if role.is_system_role:
            messages.error(request, "Cannot delete system roles.")
            return redirect("accounts:role_detail", pk=role.pk)

        messages.success(request, f"Role {role.name} deleted successfully.")
        return super().delete(request, *args, **kwargs)


# Function-based Views
@login_required
def profile_view(request):
    """User profile view and edit."""
    user = request.user

    if request.method == "POST":
        form = ProfileForm(request.POST, request.FILES, instance=user)
        if form.is_valid():
            form.save()

            # Log profile update
            UserAuditLog.objects.create(
                user=user,
                action="profile_update",
                description="Profile updated by user",
                ip_address=get_client_info(request).get("ip_address"),
            )

            messages.success(request, "Profile updated successfully!")
            return redirect("accounts:profile")
    else:
        form = ProfileForm(instance=user)

    # Get user analytics
    user_performance = UserAnalyticsService.get_user_performance_metrics(user, days=30)

    # Get recent activity
    recent_activity = UserAuditLog.objects.filter(user=user).order_by("-timestamp")[:5]

    # Get active sessions
    active_sessions = UserSession.objects.filter(user=user, is_active=True)

    context = {
        "form": form,
        "user_performance": user_performance,
        "recent_activity": recent_activity,
        "active_sessions": active_sessions,
        "security_score": user.get_security_score(),
        "profile_completion": user.get_profile_completion_percentage(),
    }

    return render(request, "accounts/profile.html", context)


@require_POST
@permission_required("users", "change")
def toggle_user_status(request, user_id):
    """Toggle user active status."""
    user_obj = get_object_or_404(User, id=user_id)

    if user_obj == request.user:
        return JsonResponse({"error": "Cannot change your own status"}, status=400)

    user_obj.is_active = not user_obj.is_active
    user_obj.save()

    # Log status change
    UserAuditLog.objects.create(
        user=user_obj,
        action="status_change",
        description=f'User {"activated" if user_obj.is_active else "deactivated"} by {request.user.username}',
        performed_by=request.user,
    )

    return JsonResponse(
        {
            "success": True,
            "is_active": user_obj.is_active,
            "message": f'User {"activated" if user_obj.is_active else "deactivated"} successfully',
        }
    )


@require_POST
@permission_required("users", "change")
def reset_user_password(request, user_id):
    """Reset user password (admin action)."""
    user_obj = get_object_or_404(User, id=user_id)

    new_password = AuthenticationService.reset_password(
        user_obj, reset_by=request.user, request=request
    )

    return JsonResponse(
        {
            "success": True,
            "message": "Password reset successfully",
            "temporary_password": new_password,
        }
    )


@require_POST
@permission_required("users", "change")
def bulk_user_action(request):
    """Handle bulk actions on users."""
    action = request.POST.get("action")
    user_ids = request.POST.getlist("user_ids")

    if not user_ids:
        return JsonResponse({"error": "No users selected"}, status=400)

    users = User.objects.filter(id__in=user_ids)
    count = users.count()

    if action == "activate":
        users.update(is_active=True)
        message = f"{count} users activated successfully"

    elif action == "deactivate":
        # Don't deactivate current user
        users.exclude(id=request.user.id).update(is_active=False)
        message = f"{count} users deactivated successfully"

    elif action == "require_password_change":
        users.update(requires_password_change=True)
        message = f"{count} users will be required to change password"

    elif action == "unlock_accounts":
        users.update(failed_login_attempts=0, last_failed_login=None)
        message = f"{count} user accounts unlocked"

    else:
        return JsonResponse({"error": "Invalid action"}, status=400)

    # Log bulk action
    UserAuditLog.objects.create(
        action="bulk_action",
        description=f'Bulk action "{action}" performed on {count} users by {request.user.username}',
        performed_by=request.user,
        extra_data={"action": action, "user_count": count, "user_ids": user_ids},
    )

    return JsonResponse({"success": True, "message": message})


@permission_required("users", "view")
def export_users(request):
    """Export users to CSV."""
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="users_export.csv"'

    writer = csv.writer(response)
    writer.writerow(
        [
            "Username",
            "Email",
            "First Name",
            "Last Name",
            "Phone",
            "Date Joined",
            "Last Login",
            "Is Active",
            "Roles",
        ]
    )

    users = User.objects.select_related("profile").prefetch_related(
        "role_assignments__role"
    )

    for user in users:
        roles = ", ".join(
            [
                assignment.role.name
                for assignment in user.role_assignments.filter(is_active=True)
            ]
        )

        writer.writerow(
            [
                user.username,
                user.email,
                user.first_name,
                user.last_name,
                user.phone_number,
                user.date_joined.strftime("%Y-%m-%d") if user.date_joined else "",
                user.last_login.strftime("%Y-%m-%d %H:%M") if user.last_login else "",
                "Yes" if user.is_active else "No",
                roles,
            ]
        )

    # Log export
    UserAuditLog.objects.create(
        action="export",
        description=f"User data exported by {request.user.username}",
        performed_by=request.user,
    )

    return response


# Analytics Views
@login_required
@method_decorator(cache_page(60 * 15), name="dispatch")  # Cache for 15 minutes
def analytics_dashboard(request):
    """Analytics dashboard view."""
    if not request.user.has_permission("reports", "view"):
        raise PermissionDenied

    days = int(request.GET.get("days", 30))

    # Get comprehensive analytics
    analytics_data = UserAnalyticsService.generate_comprehensive_report(days)

    context = {
        "analytics_data": analytics_data,
        "days": days,
        "page_title": "User Analytics Dashboard",
    }

    return render(request, "accounts/analytics_dashboard.html", context)


@login_required
def security_dashboard(request):
    """Security analytics dashboard."""
    if not request.user.has_permission("reports", "view"):
        raise PermissionDenied

    days = int(request.GET.get("days", 30))

    # Get security analytics
    security_data = UserAnalyticsService.get_security_analytics(days)

    # Get recent security events
    security_events = UserAuditLog.objects.filter(
        timestamp__gte=timezone.now() - timedelta(days=days),
        severity__in=["high", "critical"],
    ).order_by("-timestamp")[:20]

    context = {
        "security_data": security_data,
        "security_events": security_events,
        "days": days,
        "page_title": "Security Dashboard",
    }

    return render(request, "accounts/security_dashboard.html", context)


# Bulk Import Views
@login_required
@permission_required("users", "add")
def bulk_import_users(request):
    """Bulk import users from CSV."""
    if request.method == "POST":
        form = BulkUserImportForm(request.POST, request.FILES)
        if form.is_valid():
            csv_file = form.cleaned_data["csv_file"]

            # Read CSV content
            csv_content = csv_file.read().decode("utf-8")

            # Start async import task
            task = bulk_user_import.delay(
                csv_data=csv_content,
                default_password=form.cleaned_data["default_password"],
                default_roles=[
                    role.name for role in form.cleaned_data["default_roles"]
                ],
                created_by_id=request.user.id,
                send_emails=form.cleaned_data["send_welcome_emails"],
                update_existing=form.cleaned_data["update_existing"],
            )

            messages.success(
                request,
                "Bulk import started. You will receive an email when it completes.",
            )

            return redirect("accounts:user_list")
    else:
        form = BulkUserImportForm()

    context = {"form": form, "page_title": "Bulk Import Users"}

    return render(request, "accounts/bulk_import.html", context)


# API-like views for AJAX requests
@require_http_methods(["GET"])
@login_required
def user_search_api(request):
    """Search users via AJAX."""
    query = request.GET.get("q", "")
    limit = int(request.GET.get("limit", 10))

    if len(query) < 2:
        return JsonResponse({"results": []})

    users = User.objects.search(query).values(
        "id", "username", "email", "first_name", "last_name"
    )[:limit]

    results = []
    for user in users:
        results.append(
            {
                "id": user["id"],
                "text": f"{user['first_name']} {user['last_name']} ({user['username']})",
                "email": user["email"],
            }
        )

    return JsonResponse({"results": results})


@require_http_methods(["GET"])
@login_required
def role_assignments_api(request, user_id):
    """Get role assignments for a user via AJAX."""
    user = get_object_or_404(User, id=user_id)

    assignments = user.role_assignments.filter(is_active=True).select_related("role")

    data = []
    for assignment in assignments:
        data.append(
            {
                "id": assignment.id,
                "role_name": assignment.role.name,
                "role_description": assignment.role.description,
                "assigned_date": assignment.assigned_date.isoformat(),
                "expires_at": (
                    assignment.expires_at.isoformat() if assignment.expires_at else None
                ),
                "is_expired": assignment.is_expired(),
            }
        )

    return JsonResponse({"assignments": data})


@require_POST
@permission_required("roles", "change")
@csrf_exempt
def assign_role_api(request):
    """Assign role to user via AJAX."""
    try:
        data = json.loads(request.body)
        user_id = data.get("user_id")
        role_name = data.get("role_name")

        user = get_object_or_404(User, id=user_id)

        assignment, created = RoleService.assign_role_to_user(
            user, role_name, assigned_by=request.user
        )

        return JsonResponse(
            {
                "success": True,
                "created": created,
                "message": f'Role {role_name} {"assigned" if created else "already assigned"} to user',
            }
        )

    except ValueError as e:
        return JsonResponse({"success": False, "error": str(e)}, status=400)
    except Exception as e:
        logger.error(f"Error assigning role: {e}")
        return JsonResponse({"success": False, "error": "Internal error"}, status=500)


@require_POST
@permission_required("roles", "change")
@csrf_exempt
def remove_role_api(request):
    """Remove role from user via AJAX."""
    try:
        data = json.loads(request.body)
        user_id = data.get("user_id")
        role_name = data.get("role_name")

        user = get_object_or_404(User, id=user_id)

        removed = RoleService.remove_role_from_user(
            user, role_name, removed_by=request.user
        )

        return JsonResponse(
            {
                "success": True,
                "removed": removed,
                "message": f'Role {role_name} {"removed" if removed else "was not assigned"} from user',
            }
        )

    except Exception as e:
        logger.error(f"Error removing role: {e}")
        return JsonResponse({"success": False, "error": "Internal error"}, status=500)
