# src/accounts/views.py

import csv
import json
import logging
from datetime import timedelta
from io import StringIO
from typing import Any, Dict
from django.conf import settings
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
from .services import RoleService
from .services.authentication_service import UnifiedAuthenticationService
from .services.analytics_service import UserAnalyticsService
from .tasks import bulk_user_import
from .utils import get_client_info

AuthenticationService = UnifiedAuthenticationService
logger = logging.getLogger(__name__)
User = get_user_model()


# Authentication Views
class EnhancedLoginView(LoginView):
    """
    Enhanced login view supporting unified authentication with:
    - Email, phone, username, and admission number login
    - Rate limiting protection
    - Detailed logging and analytics
    - Remember me functionality
    - Better user experience with helpful error messages
    """

    form_class = CustomAuthenticationForm
    template_name = "accounts/login.html"
    redirect_authenticated_user = True
    success_url = reverse_lazy("core:dashboard")

    def get_context_data(self, **kwargs):
        """Add context for enhanced login experience."""
        context = super().get_context_data(**kwargs)

        # Get authentication settings safely
        auth_settings = getattr(settings, "UNIFIED_AUTH_SETTINGS", {})
        feature_flags = getattr(settings, "AUTH_FEATURE_FLAGS", {})

        context.update(
            {
                "page_title": "Login to Your Account",
                "show_remember_me": feature_flags.get("REMEMBER_ME", True),
                "allow_registration": True,
                "allow_password_reset": True,
                "login_help_text": self._get_login_help_text(),
                "supported_identifiers": self._get_supported_identifiers(),
                "branding": {
                    "site_name": getattr(
                        settings, "SITE_NAME", "School Management System"
                    ),
                    "logo_url": getattr(settings, "LOGIN_LOGO_URL", None),
                    "background_url": getattr(settings, "LOGIN_BACKGROUND_URL", None),
                },
                "security_notice": self._get_security_notice(),
            }
        )

        return context

    def form_valid(self, form):
        """Handle successful login with enhanced features."""
        try:
            user = form.get_user()
            if not user:
                messages.error(self.request, "Authentication failed. Please try again.")
                return self.form_invalid(form)

            client_info = get_client_info(self.request)

            # Check rate limiting
            if self._is_rate_limited():
                messages.error(
                    self.request, "Too many login attempts. Please try again later."
                )
                return self.form_invalid(form)

            # Handle remember me functionality
            remember_me = form.cleaned_data.get("remember_me", False)
            if remember_me:
                # Extend session duration
                remember_duration = getattr(
                    settings, "REMEMBER_ME_DURATION", 1209600
                )  # 2 weeks
                self.request.session.set_expiry(remember_duration)
            else:
                # Session expires when browser closes
                self.request.session.set_expiry(0)

            # Log successful login with identifier type
            try:
                identifier_type = form.get_identifier_type_display()
                UserAuditLog.objects.create(
                    user=user,
                    action="login",
                    description=f"Successful web login using {identifier_type or 'identifier'}",
                    ip_address=client_info.get("ip_address"),
                    user_agent=client_info.get("user_agent"),
                    extra_data={
                        **client_info,
                        "identifier_type": form._detect_identifier_type(
                            form.cleaned_data.get("identifier", "")
                        ),
                        "remember_me": remember_me,
                        "login_method": "web_form",
                    },
                )
            except Exception as e:
                logger.error(f"Failed to log successful login: {str(e)}")

            # Clear any rate limiting for successful login
            self._clear_rate_limit()

            # Perform login
            login(self.request, user)

            # Add success message with personalization
            welcome_message = self._get_welcome_message(user, identifier_type)
            messages.success(self.request, welcome_message)

            # Check for any security alerts
            self._check_security_alerts(user)

            # Redirect to success URL
            return self.get_success_url_redirect()

        except Exception as e:
            logger.error(f"Error in form_valid: {str(e)}")
            messages.error(
                self.request, "Login failed due to an error. Please try again."
            )
            return self.form_invalid(form)

    def form_invalid(self, form):
        """Handle failed login attempts with enhanced security."""
        try:
            identifier = form.data.get("identifier", "")
            client_info = get_client_info(self.request)

            # Increment rate limiting counter
            self._increment_rate_limit()

            # Log failed attempt with more details
            try:
                UserAuditLog.objects.create(
                    action="login",
                    description=f"Failed login attempt for identifier: {identifier}",
                    ip_address=client_info.get("ip_address"),
                    user_agent=client_info.get("user_agent"),
                    extra_data={
                        **client_info,
                        "identifier_provided": identifier,
                        "identifier_type": (
                            form._detect_identifier_type(identifier)
                            if identifier
                            else "unknown"
                        ),
                        "form_errors": (
                            dict(form.errors) if hasattr(form, "errors") else {}
                        ),
                        "login_method": "web_form",
                    },
                    severity="medium",
                )
            except Exception as e:
                logger.error(f"Failed to log failed login attempt: {str(e)}")

            # Add contextual error message
            error_message = self._get_contextual_error_message(form, identifier)
            messages.error(self.request, error_message)

        except Exception as e:
            logger.error(f"Error in form_invalid: {str(e)}")
            messages.error(
                self.request,
                "Login failed. Please check your credentials and try again.",
            )

        return super().form_invalid(form)

    def get_success_url_redirect(self):
        """Get redirect response after successful login."""
        next_url = self.request.GET.get("next")
        if next_url:
            return self.redirect_to_success_url(next_url)
        return self.redirect_to_success_url(self.get_success_url())

    def redirect_to_success_url(self, url):
        """Redirect to success URL."""
        from django.http import HttpResponseRedirect

        return HttpResponseRedirect(url)

    def get_success_url(self):
        """Get the success URL."""
        return str(self.success_url) if self.success_url else "/"

    def _get_login_help_text(self):
        """Generate helpful login instructions."""
        feature_flags = getattr(settings, "AUTH_FEATURE_FLAGS", {})
        help_parts = []

        if feature_flags.get("EMAIL_LOGIN", True):
            help_parts.append("your email address")
        if feature_flags.get("PHONE_LOGIN", True):
            help_parts.append("your phone number")
        if feature_flags.get("USERNAME_LOGIN", True):
            help_parts.append("your username")
        if feature_flags.get("ADMISSION_LOGIN", True):
            help_parts.append("your admission number (for students)")

        if len(help_parts) > 1:
            return f"You can login using {', '.join(help_parts[:-1])}, or {help_parts[-1]}."
        elif help_parts:
            return f"Login using {help_parts[0]}."
        else:
            return "Enter your login credentials."

    def _get_supported_identifiers(self):
        """Get list of supported identifier types for frontend."""
        feature_flags = getattr(settings, "AUTH_FEATURE_FLAGS", {})
        return {
            "email": feature_flags.get("EMAIL_LOGIN", True),
            "phone": feature_flags.get("PHONE_LOGIN", True),
            "username": feature_flags.get("USERNAME_LOGIN", True),
            "admission": feature_flags.get("ADMISSION_LOGIN", True),
        }

    def _get_security_notice(self):
        """Get security notice for login page."""
        return (
            "For your security, your session will automatically expire after "
            "a period of inactivity. Never share your login credentials."
        )

    def _get_welcome_message(self, user, identifier_type):
        """Generate personalized welcome message."""
        base_message = f"Welcome back, {user.get_full_name() or user.username}!"

        if identifier_type:
            base_message += f" (logged in using {identifier_type})"

        # Add role-specific message
        try:
            if hasattr(user, "is_student") and user.is_student:
                base_message += " Ready to learn?"
            elif hasattr(user, "is_teacher") and user.is_teacher:
                base_message += " Ready to teach?"
            elif user.is_staff or user.is_superuser:
                base_message += " Ready to manage?"
        except:
            pass

        return base_message

    def _get_contextual_error_message(self, form, identifier):
        """Generate contextual error message based on identifier type."""
        if not identifier:
            return "Please enter your login credentials."

        try:
            identifier_type = form._detect_identifier_type(identifier)

            # Customize message based on identifier type
            type_messages = {
                "email": "Please check your email address and password.",
                "phone": "Please check your phone number and password.",
                "admission": "Please check your admission number and password. Students should use their admission number as provided by the school.",
                "username": "Please check your username and password.",
            }

            return type_messages.get(
                identifier_type, "Please check your credentials and try again."
            )
        except:
            return "Please check your credentials and try again."

    def _check_security_alerts(self, user):
        """Check for any security alerts to show user."""
        try:
            # Check for suspicious login patterns
            recent_attempts = UserAuditLog.objects.filter(
                user=user,
                action="login",
                timestamp__gte=timezone.now() - timezone.timedelta(hours=24),
            ).count()

            if recent_attempts > 10:
                messages.warning(
                    self.request,
                    "We noticed several login attempts on your account in the last 24 hours. "
                    "If this wasn't you, please change your password immediately.",
                )
        except Exception as e:
            logger.error(f"Error checking security alerts: {str(e)}")

    def _is_rate_limited(self):
        """Check if current IP is rate limited."""
        try:
            client_ip = get_client_info(self.request).get("ip_address", "unknown")
            rate_limit_key = f"login_attempts:{client_ip}"

            attempts = cache.get(rate_limit_key, 0)
            max_attempts = (
                getattr(settings, "RATE_LIMITING", {})
                .get("LOGIN_ATTEMPTS", {})
                .get("RATE", "10/hour")
            )

            try:
                max_count = int(max_attempts.split("/")[0])
                return attempts >= max_count
            except (ValueError, IndexError):
                return False
        except Exception as e:
            logger.error(f"Error checking rate limit: {str(e)}")
            return False

    def _increment_rate_limit(self):
        """Increment rate limiting counter."""
        try:
            client_ip = get_client_info(self.request).get("ip_address", "unknown")
            rate_limit_key = f"login_attempts:{client_ip}"

            current = cache.get(rate_limit_key, 0)
            cache.set(rate_limit_key, current + 1, timeout=3600)  # 1 hour
        except Exception as e:
            logger.error(f"Error incrementing rate limit: {str(e)}")

    def _clear_rate_limit(self):
        """Clear rate limiting for successful login."""
        try:
            client_ip = get_client_info(self.request).get("ip_address", "unknown")
            rate_limit_key = f"login_attempts:{client_ip}"
            cache.delete(rate_limit_key)
        except Exception as e:
            logger.error(f"Error clearing rate limit: {str(e)}")


class CustomLogoutView(LogoutView):
    """Enhanced logout view with logging."""

    template_name = "accounts/logout.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            # Log logout using unified service
            UnifiedAuthenticationService.logout_user(request.user, request)
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
    """Enhanced user detail view with analytics and security info."""

    model = User
    template_name = "accounts/user_detail.html"
    context_object_name = "user_obj"

    @method_decorator(permission_required("users", "view"))
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user_obj = self.get_object()

        try:
            # User analytics (if available)
            if hasattr(UserAnalyticsService, "get_user_performance_metrics"):
                context["user_performance"] = (
                    UserAnalyticsService.get_user_performance_metrics(user_obj, days=30)
                )

            # Role assignments
            if hasattr(user_obj, "role_assignments"):
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

            # Login statistics using unified service
            context["login_stats"] = UnifiedAuthenticationService.get_login_statistics(
                user_obj, days=30
            )

            # Security information
            context["security_info"] = {
                "is_locked": getattr(user_obj, "is_account_locked", lambda: False)(),
                "failed_attempts": getattr(user_obj, "failed_login_attempts", 0),
                "requires_password_change": getattr(
                    user_obj, "requires_password_change", False
                ),
                "email_verified": getattr(user_obj, "email_verified", False),
                "phone_verified": getattr(user_obj, "phone_verified", False),
                "two_factor_enabled": getattr(user_obj, "two_factor_enabled", False),
                "security_score": getattr(user_obj, "get_security_score", lambda: 75)(),
            }

            # Permissions
            context["can_edit"] = (
                self.request.user.has_perm("accounts.change_user")
                or self.request.user == user_obj
            )
            context["can_delete"] = self.request.user.has_perm("accounts.delete_user")
            context["can_reset_password"] = self.request.user.has_perm(
                "accounts.change_user"
            )

        except Exception as e:
            logger.error(f"Error loading user detail context: {str(e)}")
            # Provide basic context if there are errors
            context["login_stats"] = {}
            context["security_info"] = {}

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
    """Toggle user active status with enhanced logging."""
    try:
        user_obj = get_object_or_404(User, id=user_id)

        if user_obj == request.user:
            return JsonResponse({"error": "Cannot change your own status"}, status=400)

        old_status = user_obj.is_active
        user_obj.is_active = not user_obj.is_active
        user_obj.save()

        # Log status change using unified service
        action = "activated" if user_obj.is_active else "deactivated"
        UserAuditLog.objects.create(
            user=user_obj,
            action="status_change",
            description=f"User {action} by {request.user.username}",
            performed_by=request.user,
            extra_data={
                "old_status": old_status,
                "new_status": user_obj.is_active,
                "changed_by": request.user.id,
            },
        )

        return JsonResponse(
            {
                "success": True,
                "is_active": user_obj.is_active,
                "message": f"User {action} successfully",
            }
        )

    except Exception as e:
        logger.error(f"Error toggling user status: {str(e)}")
        return JsonResponse({"error": "Failed to change user status"}, status=500)


@require_POST
@permission_required("users", "change")
def reset_user_password(request, user_id):
    """Reset user password (admin action)."""
    user_obj = get_object_or_404(User, id=user_id)

    if user_obj == request.user:
        return JsonResponse({"error": "Cannot reset your own password"}, status=400)

    try:
        new_password = UnifiedAuthenticationService.reset_password(
            user_obj, reset_by=request.user, request=request
        )

        return JsonResponse(
            {
                "success": True,
                "message": "Password reset successfully",
                "temporary_password": new_password,
            }
        )
    except Exception as e:
        logger.error(f"Error resetting password for user {user_id}: {str(e)}")
        return JsonResponse({"error": "Failed to reset password"}, status=500)


@require_POST
@permission_required("users", "change")
def bulk_user_action(request):
    """Handle bulk actions on users with enhanced logging."""
    action = request.POST.get("action")
    user_ids = request.POST.getlist("user_ids")

    if not user_ids:
        return JsonResponse({"error": "No users selected"}, status=400)

    try:
        users = User.objects.filter(id__in=user_ids)
        count = users.count()

        if count == 0:
            return JsonResponse({"error": "No valid users found"}, status=400)

        if action == "activate":
            users.update(is_active=True)
            message = f"{count} users activated successfully"

        elif action == "deactivate":
            # Don't deactivate current user
            users.exclude(id=request.user.id).update(is_active=False)
            actual_count = users.exclude(id=request.user.id).count()
            message = f"{actual_count} users deactivated successfully"

        elif action == "require_password_change":
            users.update(requires_password_change=True)
            message = f"{count} users will be required to change password"

        elif action == "unlock_accounts":
            # Use the unified service for unlocking accounts
            unlocked_count = 0
            for user in users:
                if UnifiedAuthenticationService.unlock_account(
                    user, request.user, request
                ):
                    unlocked_count += 1
            message = f"{unlocked_count} user accounts unlocked"

        elif action == "reset_passwords":
            # Bulk password reset
            reset_count = 0
            for user in users:
                try:
                    UnifiedAuthenticationService.reset_password(
                        user, reset_by=request.user, request=request
                    )
                    reset_count += 1
                except Exception as e:
                    logger.error(
                        f"Failed to reset password for user {user.id}: {str(e)}"
                    )
            message = f"{reset_count} passwords reset successfully"

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

    except Exception as e:
        logger.error(f"Error in bulk user action: {str(e)}")
        return JsonResponse({"error": "Operation failed"}, status=500)


@login_required
@permission_required("users", "add")
def bulk_import_users(request):
    """Bulk import users from CSV with enhanced validation."""
    if request.method == "POST":
        form = BulkUserImportForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                csv_file = form.cleaned_data["csv_file"]

                # Validate file size and type
                if csv_file.size > 5 * 1024 * 1024:  # 5MB limit
                    messages.error(request, "File size too large. Maximum 5MB allowed.")
                    return render(request, "accounts/bulk_import.html", {"form": form})

                if not csv_file.name.lower().endswith(".csv"):
                    messages.error(request, "Please upload a CSV file.")
                    return render(request, "accounts/bulk_import.html", {"form": form})

                # Read CSV content
                csv_content = csv_file.read().decode("utf-8")

                # Start async import task if available, otherwise process synchronously
                try:
                    from .tasks import bulk_user_import

                    task = bulk_user_import.delay(
                        csv_data=csv_content,
                        default_password=form.cleaned_data["default_password"],
                        default_roles=[
                            role.name
                            for role in form.cleaned_data.get("default_roles", [])
                        ],
                        created_by_id=request.user.id,
                        send_emails=form.cleaned_data.get("send_welcome_emails", False),
                        update_existing=form.cleaned_data.get("update_existing", False),
                    )

                    messages.success(
                        request,
                        "Bulk import started. You will receive an email when it completes.",
                    )
                except ImportError:
                    # Celery not available, process synchronously
                    result = _process_csv_import_sync(
                        csv_content, form.cleaned_data, request.user
                    )

                    if result["success"]:
                        messages.success(
                            request,
                            f"Import completed! {result['created']} users created, {result['updated']} updated.",
                        )
                    else:
                        messages.error(request, f"Import failed: {result['error']}")

                return redirect("accounts:user_list")

            except Exception as e:
                logger.error(f"Error in bulk import: {str(e)}")
                messages.error(
                    request, "Import failed due to an error. Please try again."
                )

    else:
        form = BulkUserImportForm()

    context = {
        "form": form,
        "page_title": "Bulk Import Users",
        "help_text": "Upload a CSV file with user data. Required columns: username, email, first_name, last_name",
    }

    return render(request, "accounts/bulk_import.html", context)


def _process_csv_import_sync(csv_content, form_data, created_by):
    """Process CSV import synchronously when Celery is not available."""
    import csv
    import io

    try:
        csv_reader = csv.DictReader(io.StringIO(csv_content))
        created_count = 0
        updated_count = 0
        errors = []

        for row_num, row in enumerate(csv_reader, 1):
            try:
                # Basic validation
                if not all([row.get("username"), row.get("email")]):
                    errors.append(f"Row {row_num}: Missing required fields")
                    continue

                # Check if user exists
                existing_user = User.objects.filter(
                    models.Q(username=row["username"]) | models.Q(email=row["email"])
                ).first()

                if existing_user and not form_data.get("update_existing"):
                    errors.append(f"Row {row_num}: User already exists")
                    continue

                if existing_user:
                    # Update existing user
                    for field in ["first_name", "last_name", "email"]:
                        if row.get(field):
                            setattr(existing_user, field, row[field])
                    existing_user.save()
                    updated_count += 1
                else:
                    # Create new user
                    user_data = {
                        "username": row["username"],
                        "email": row["email"],
                        "first_name": row.get("first_name", ""),
                        "last_name": row.get("last_name", ""),
                        "password": form_data.get("default_password", "temppass123"),
                        "is_active": True,
                        "requires_password_change": True,
                    }

                    User.objects.create_user(**user_data)
                    created_count += 1

            except Exception as e:
                errors.append(f"Row {row_num}: {str(e)}")

        return {
            "success": True,
            "created": created_count,
            "updated": updated_count,
            "errors": errors,
        }

    except Exception as e:
        return {"success": False, "error": str(e)}


@permission_required("users", "view")
def export_users(request):
    """Export users to CSV."""
    try:
        # Get query parameters
        format_type = request.GET.get("format", "csv")
        include_inactive = request.GET.get("include_inactive", False)

        # Build queryset
        queryset = User.objects.all()
        if not include_inactive:
            queryset = queryset.filter(is_active=True)

        # Create response
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = (
            f'attachment; filename="users_export_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv"'
        )

        # Write CSV data
        writer = csv.writer(response)

        # Headers
        headers = [
            "Username",
            "Email",
            "First Name",
            "Last Name",
            "Is Active",
            "Date Joined",
            "Last Login",
            "Phone Number",
        ]
        writer.writerow(headers)

        # Data rows
        for user in queryset.select_related():
            writer.writerow(
                [
                    user.username,
                    user.email,
                    user.first_name,
                    user.last_name,
                    "Yes" if user.is_active else "No",
                    user.date_joined.strftime("%Y-%m-%d") if user.date_joined else "",
                    (
                        user.last_login.strftime("%Y-%m-%d %H:%M:%S")
                        if user.last_login
                        else ""
                    ),
                    getattr(user, "phone_number", ""),
                ]
            )

        # Log export
        UserAuditLog.objects.create(
            user=request.user,
            action="data_export",
            description=f"Users exported by {request.user.username}",
            extra_data={
                "export_type": "users",
                "format": format_type,
                "record_count": queryset.count(),
                "include_inactive": include_inactive,
            },
        )

        return response

    except Exception as e:
        logger.error(f"Error exporting users: {str(e)}")
        messages.error(request, "Failed to export users. Please try again.")
        return redirect("accounts:user_list")


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


# AJAX Login View for API/Mobile support
@method_decorator(csrf_exempt, name="dispatch")
class AjaxLoginView(EnhancedLoginView):
    """AJAX login view for API/mobile app support."""

    def form_valid(self, form):
        """Return JSON response for successful login."""
        user = form.get_user()
        login(self.request, user)

        # Generate API tokens if needed
        tokens = UnifiedAuthenticationService.generate_tokens_for_user(user)

        return JsonResponse(
            {
                "success": True,
                "message": f"Welcome back, {user.get_display_name()}!",
                "user_id": user.id,
                "username": user.username,
                "email": user.email,
                "full_name": user.get_full_name(),
                "role": user.get_role_display(),
                "tokens": tokens,
                "redirect_url": str(self.get_success_url()),
            }
        )

    def form_invalid(self, form):
        """Return JSON response for failed login."""
        errors = {}
        for field, error_list in form.errors.items():
            errors[field] = [str(error) for error in error_list]

        return JsonResponse(
            {
                "success": False,
                "message": "Login failed. Please check your credentials.",
                "errors": errors,
            },
            status=400,
        )


@require_http_methods(["POST"])
def validate_identifier(request):
    """
    AJAX endpoint to validate identifier and provide helpful feedback.
    """
    identifier = request.POST.get("identifier", "").strip()

    if not identifier:
        return JsonResponse({"valid": False, "message": "Please enter an identifier."})

    # Check if user exists
    user = UnifiedAuthenticationService._find_user_by_identifier(identifier)
    identifier_type = UnifiedAuthenticationService._get_identifier_type(identifier)

    response_data = {
        "valid": user is not None,
        "identifier_type": identifier_type,
        "message": "",
    }

    if user:
        # User found - provide positive feedback
        type_labels = {
            "email": "email address",
            "phone": "phone number",
            "admission_number": "admission number",
            "username": "username",
        }

        response_data["message"] = (
            f"Account found for this {type_labels.get(identifier_type, 'identifier')}."
        )
        response_data["user_type"] = "student" if user.is_student else "staff"

    else:
        # User not found - provide helpful message
        if identifier_type == "admission_number":
            response_data["message"] = (
                "No student found with this admission number. Please check and try again."
            )
        else:
            response_data["message"] = (
                f"No account found with this {identifier_type}. Please check and try again."
            )

    return JsonResponse(response_data)
