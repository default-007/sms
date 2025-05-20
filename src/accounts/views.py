from django.conf import settings
from django.db.models import Q, Count, Prefetch
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.urls import reverse_lazy, reverse
from django.views.generic import (
    ListView,
    DetailView,
    CreateView,
    UpdateView,
    DeleteView,
)
from django.utils.decorators import method_decorator
from django.contrib.auth.views import (
    LoginView,
    LogoutView,
    PasswordChangeView,
    PasswordResetView,
    PasswordResetConfirmView,
)
from django.db import transaction
from django.http import JsonResponse, HttpResponse
from django.core.paginator import Paginator
from django.utils import timezone
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
import json
import csv
from io import StringIO

from .models import User, UserProfile, UserRole, UserRoleAssignment, UserAuditLog
from .forms import (
    CustomAuthenticationForm,
    CustomUserCreationForm,
    UserProfileForm,
    CustomPasswordChangeForm,
    CustomPasswordResetForm,
    CustomSetPasswordForm,
    UserRoleForm,
)
from .services import RoleService, AuthenticationService
from .decorators import admin_required, permission_required
from .utils import (
    generate_secure_password,
    send_notification_email,
    get_client_info,
    format_file_size,
)


class CustomLoginView(LoginView):
    """Enhanced login view with security features."""

    template_name = "accounts/login.html"
    form_class = CustomAuthenticationForm
    redirect_authenticated_user = True

    def dispatch(self, request, *args, **kwargs):
        # Handle locked account message
        if request.GET.get("locked"):
            messages.error(
                request,
                "Your account has been locked due to multiple failed login attempts.",
            )

        # Handle expired session message
        if request.GET.get("expired"):
            messages.warning(request, "Your session has expired. Please log in again.")

        # Handle security violation message
        if request.GET.get("security"):
            messages.error(request, "Security violation detected. Please log in again.")

        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        """Enhanced form validation with security checks."""
        user = form.get_user()

        # Check if account is locked
        if user.is_account_locked():
            messages.error(
                self.request, "Account is locked due to multiple failed login attempts."
            )
            return self.form_invalid(form)

        # Reset failed login attempts on successful login
        if user.failed_login_attempts > 0:
            user.reset_failed_login_attempts()

        # Create audit log for successful login
        client_info = get_client_info(self.request)
        UserAuditLog.objects.create(
            user=user,
            action="login",
            description="Successful login",
            ip_address=client_info["ip_address"],
            user_agent=client_info["user_agent"],
            extra_data=client_info,
        )

        # Update last login time
        AuthenticationService.update_last_login(user)

        response = super().form_valid(form)

        # Send login notification if enabled
        if (
            hasattr(settings, "SEND_LOGIN_NOTIFICATIONS")
            and settings.SEND_LOGIN_NOTIFICATIONS
        ):
            send_notification_email(
                user,
                "New Login Detected",
                "accounts/emails/login_notification.html",
                {"client_info": client_info},
            )

        return response

    def form_invalid(self, form):
        """Handle invalid login attempts."""
        username = form.cleaned_data.get("username")

        if username:
            try:
                user = User.objects.get(Q(username=username) | Q(email=username))
                user.increment_failed_login_attempts()

                # Create audit log for failed login
                client_info = get_client_info(self.request)
                UserAuditLog.objects.create(
                    user=user,
                    action="login",
                    description=f"Failed login attempt (attempt #{user.failed_login_attempts})",
                    ip_address=client_info["ip_address"],
                    user_agent=client_info["user_agent"],
                    extra_data=client_info,
                )

                # Check if account should be locked
                if user.failed_login_attempts >= 5:
                    messages.error(
                        self.request,
                        "Account has been locked due to too many failed login attempts. "
                        "Please try again later or contact support.",
                    )
                else:
                    remaining = 5 - user.failed_login_attempts
                    messages.warning(
                        self.request,
                        f"Invalid credentials. {remaining} attempt(s) remaining before account lockout.",
                    )
            except User.DoesNotExist:
                pass

        return super().form_invalid(form)


class CustomLogoutView(LogoutView):
    """Enhanced logout view with audit logging."""

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            # Create audit log
            client_info = get_client_info(request)
            UserAuditLog.objects.create(
                user=request.user,
                action="logout",
                description="User logged out",
                ip_address=client_info["ip_address"],
                user_agent=client_info["user_agent"],
            )

            # Deactivate user session
            if hasattr(request, "session") and request.session.session_key:
                from .models import UserSession

                UserSession.objects.filter(
                    session_key=request.session.session_key
                ).update(is_active=False)

        return super().dispatch(request, *args, **kwargs)

    def get_next_page(self):
        messages.success(self.request, "You have been successfully logged out.")
        return super().get_next_page()


class CustomPasswordChangeView(PasswordChangeView):
    """Enhanced password change view."""

    form_class = CustomPasswordChangeForm
    template_name = "accounts/password_change.html"
    success_url = reverse_lazy("accounts:profile")

    def form_valid(self, form):
        """Handle successful password change."""
        # Update password changed timestamp
        self.request.user.password_changed_at = timezone.now()
        self.request.user.requires_password_change = False
        self.request.user.save(
            update_fields=["password_changed_at", "requires_password_change"]
        )

        # Create audit log
        client_info = get_client_info(self.request)
        UserAuditLog.objects.create(
            user=self.request.user,
            action="password_change",
            description="Password changed successfully",
            ip_address=client_info["ip_address"],
            user_agent=client_info["user_agent"],
        )

        # Send notification email
        send_notification_email(
            self.request.user,
            "Password Changed Successfully",
            "accounts/emails/password_changed.html",
            {"client_info": client_info},
        )

        messages.success(self.request, "Your password has been changed successfully!")
        return super().form_valid(form)


class CustomPasswordResetView(PasswordResetView):
    """Enhanced password reset view."""

    form_class = CustomPasswordResetForm
    template_name = "accounts/password_reset.html"
    email_template_name = "accounts/password_reset_email.html"
    success_url = reverse_lazy("accounts:password_reset_done")

    def form_valid(self, form):
        """Handle password reset request."""
        # Create audit log for password reset request
        email = form.cleaned_data["email"]
        try:
            user = User.objects.get(email=email)
            client_info = get_client_info(self.request)
            UserAuditLog.objects.create(
                user=user,
                action="password_reset",
                description="Password reset requested",
                ip_address=client_info["ip_address"],
                user_agent=client_info["user_agent"],
            )
        except User.DoesNotExist:
            pass

        return super().form_valid(form)


class CustomPasswordResetConfirmView(PasswordResetConfirmView):
    """Enhanced password reset confirm view."""

    form_class = CustomSetPasswordForm
    template_name = "accounts/password_reset_confirm.html"
    success_url = reverse_lazy("accounts:password_reset_complete")

    def form_valid(self, form):
        """Handle password reset completion."""
        user = form.user

        # Update password changed timestamp
        user.password_changed_at = timezone.now()
        user.requires_password_change = False
        user.failed_login_attempts = 0
        user.last_failed_login = None
        user.save(
            update_fields=[
                "password_changed_at",
                "requires_password_change",
                "failed_login_attempts",
                "last_failed_login",
            ]
        )

        # Create audit log
        client_info = get_client_info(self.request)
        UserAuditLog.objects.create(
            user=user,
            action="password_change",
            description="Password reset via email verification",
            ip_address=client_info["ip_address"],
            user_agent=client_info["user_agent"],
        )

        return super().form_valid(form)


@method_decorator(login_required, name="dispatch")
class UserListView(ListView):
    """Enhanced view for listing users with advanced filtering."""

    model = User
    template_name = "accounts/user_list.html"
    context_object_name = "users"
    paginate_by = 25

    def get_queryset(self):
        """Enhanced queryset with optimizations and filtering."""
        queryset = (
            User.objects.select_related("profile")
            .prefetch_related(
                Prefetch(
                    "role_assignments",
                    queryset=UserRoleAssignment.objects.select_related("role").filter(
                        is_active=True
                    ),
                    to_attr="active_roles",
                )
            )
            .order_by("-date_joined")
        )

        # Search functionality
        search_query = self.request.GET.get("search", "").strip()
        if search_query:
            queryset = queryset.filter(
                Q(username__icontains=search_query)
                | Q(email__icontains=search_query)
                | Q(first_name__icontains=search_query)
                | Q(last_name__icontains=search_query)
            )

        # Role filtering
        role_filter = self.request.GET.get("role", "").strip()
        if role_filter:
            queryset = queryset.filter(
                role_assignments__role__name=role_filter,
                role_assignments__is_active=True,
            ).distinct()

        # Status filtering
        status_filter = self.request.GET.get("status", "").strip()
        if status_filter == "active":
            queryset = queryset.filter(is_active=True)
        elif status_filter == "inactive":
            queryset = queryset.filter(is_active=False)
        elif status_filter == "locked":
            queryset = queryset.filter(failed_login_attempts__gte=5)
        elif status_filter == "password_change":
            queryset = queryset.filter(requires_password_change=True)

        return queryset

    def get_context_data(self, **kwargs):
        """Add additional context data."""
        context = super().get_context_data(**kwargs)

        # Get all roles for filter dropdown
        context["roles"] = UserRole.objects.all().order_by("name")

        # Search and filter parameters
        context["search_query"] = self.request.GET.get("search", "")
        context["selected_role"] = self.request.GET.get("role", "")
        context["selected_status"] = self.request.GET.get("status", "")

        # User statistics
        context["active_users_count"] = User.objects.filter(is_active=True).count()
        context["inactive_users_count"] = User.objects.filter(is_active=False).count()
        context["new_users_count"] = User.objects.filter(
            date_joined__gte=timezone.now() - timezone.timedelta(days=30)
        ).count()

        return context


@method_decorator(login_required, name="dispatch")
class UserDetailView(DetailView):
    """Enhanced view for displaying user details."""

    model = User
    template_name = "accounts/user_detail.html"
    context_object_name = "user_obj"

    def get_queryset(self):
        """Optimize queryset with prefetch."""
        return User.objects.select_related("profile").prefetch_related(
            "role_assignments__role", "audit_logs"
        )

    def get_context_data(self, **kwargs):
        """Add additional context data."""
        context = super().get_context_data(**kwargs)
        user = self.object

        # User roles
        context["user_roles"] = user.role_assignments.filter(
            is_active=True
        ).select_related("role")

        # Recent activity
        context["recent_activity"] = user.audit_logs.order_by("-timestamp")[:10]

        # User statistics
        context["user_stats"] = {
            "total_logins": user.audit_logs.filter(action="login").count(),
            "last_login": user.last_login,
            "failed_attempts": user.failed_login_attempts,
            "is_locked": user.is_account_locked(),
            "requires_password_change": user.requires_password_change,
        }

        # Active sessions
        context["active_sessions"] = user.sessions.filter(is_active=True)

        return context


@method_decorator(admin_required, name="dispatch")
class UserCreateView(CreateView):
    """Enhanced view for creating new users."""

    model = User
    form_class = CustomUserCreationForm
    template_name = "accounts/user_form.html"
    success_url = reverse_lazy("accounts:user_list")

    def get_context_data(self, **kwargs):
        """Add roles to context."""
        context = super().get_context_data(**kwargs)
        context["roles"] = UserRole.objects.all().order_by("name")
        context["is_create"] = True
        return context

    @transaction.atomic
    def form_valid(self, form):
        """Process form and assign roles."""
        # Create user
        user = form.save()

        # Generate secure password if not provided
        if not form.cleaned_data.get("password1"):
            password = generate_secure_password()
            user.set_password(password)
            user.requires_password_change = True
            user.save()

            # Send password to user via email
            send_notification_email(
                user,
                "Account Created - Temporary Password",
                "accounts/emails/account_created.html",
                {"temporary_password": password},
            )

        # Assign roles
        roles = form.cleaned_data.get("roles", [])
        for role in roles:
            RoleService.assign_role_to_user(
                user, role.name, assigned_by=self.request.user
            )

        # Create audit log
        client_info = get_client_info(self.request)
        UserAuditLog.objects.create(
            user=user,
            action="create",
            description=f"User account created by {self.request.user.username}",
            performed_by=self.request.user,
            ip_address=client_info["ip_address"],
            user_agent=client_info["user_agent"],
            extra_data={"roles": [role.name for role in roles]},
        )

        messages.success(
            self.request, f'User "{user.username}" has been created successfully!'
        )
        return super().form_valid(form)


@method_decorator(login_required, name="dispatch")
class UserUpdateView(UpdateView):
    """Enhanced view for updating users."""

    model = User
    form_class = UserProfileForm
    template_name = "accounts/user_form.html"
    success_url = reverse_lazy("accounts:user_list")

    def get_queryset(self):
        """Optimize queryset."""
        return User.objects.select_related("profile").prefetch_related(
            "role_assignments__role"
        )

    def dispatch(self, request, *args, **kwargs):
        """Check permissions."""
        user = self.get_object()

        # Allow users to edit their own profile
        if user == request.user:
            return super().dispatch(request, *args, **kwargs)

        # Check if current user has permission to edit other users
        if not RoleService.check_permission(request.user, "users", "change"):
            messages.error(request, "You do not have permission to edit this user.")
            return redirect("accounts:user_list")

        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        """Add additional context."""
        context = super().get_context_data(**kwargs)
        context["roles"] = UserRole.objects.all().order_by("name")
        context["user_roles"] = self.object.role_assignments.filter(
            is_active=True
        ).values_list("role__id", flat=True)
        context["is_create"] = False
        context["can_change_roles"] = RoleService.check_permission(
            self.request.user, "roles", "change"
        )
        return context

    @transaction.atomic
    def form_valid(self, form):
        """Process form and update roles if provided."""
        user = form.save()

        # Update roles if user has permission and roles are provided
        if (
            RoleService.check_permission(self.request.user, "roles", "change")
            and "roles" in self.request.POST
        ):

            role_ids = self.request.POST.getlist("roles")
            # Deactivate current role assignments
            user.role_assignments.update(is_active=False)

            # Assign new roles
            for role_id in role_ids:
                try:
                    role = UserRole.objects.get(id=role_id)
                    RoleService.assign_role_to_user(
                        user, role.name, assigned_by=self.request.user
                    )
                except UserRole.DoesNotExist:
                    pass

        # Create audit log
        client_info = get_client_info(self.request)
        UserAuditLog.objects.create(
            user=user,
            action="update",
            description=f"User profile updated by {self.request.user.username}",
            performed_by=self.request.user,
            ip_address=client_info["ip_address"],
            user_agent=client_info["user_agent"],
        )

        messages.success(
            self.request, f'User "{user.username}" has been updated successfully!'
        )
        return super().form_valid(form)


@method_decorator(admin_required, name="dispatch")
class UserDeleteView(DeleteView):
    """Enhanced view for deleting users (soft delete)."""

    model = User
    template_name = "accounts/user_confirm_delete.html"
    success_url = reverse_lazy("accounts:user_list")
    context_object_name = "user_obj"

    def delete(self, request, *args, **kwargs):
        """Perform soft delete instead of hard delete."""
        user = self.get_object()

        # Soft delete - deactivate user
        user.is_active = False
        user.save()

        # Deactivate all role assignments
        user.role_assignments.update(is_active=False)

        # Deactivate all sessions
        user.sessions.update(is_active=False)

        # Create audit log
        client_info = get_client_info(request)
        UserAuditLog.objects.create(
            user=user,
            action="delete",
            description=f"User deactivated by {request.user.username}",
            performed_by=request.user,
            ip_address=client_info["ip_address"],
            user_agent=client_info["user_agent"],
        )

        messages.success(
            request, f'User "{user.username}" has been deactivated successfully!'
        )

        return redirect(self.success_url)


# AJAX Views
@login_required
@require_http_methods(["POST"])
def toggle_user_status(request, user_id):
    """Toggle user active status via AJAX."""
    try:
        user = get_object_or_404(User, id=user_id)

        # Check permissions
        if not RoleService.check_permission(request.user, "users", "change"):
            return JsonResponse({"success": False, "message": "Permission denied"})

        # Parse request data
        data = json.loads(request.body)
        activate = data.get("activate", False)

        user.is_active = activate
        user.save()

        # Create audit log
        action = "account_unlock" if activate else "account_lock"
        description = f'User {"activated" if activate else "deactivated"} by {request.user.username}'

        client_info = get_client_info(request)
        UserAuditLog.objects.create(
            user=user,
            action=action,
            description=description,
            performed_by=request.user,
            ip_address=client_info["ip_address"],
            user_agent=client_info["user_agent"],
        )

        return JsonResponse(
            {
                "success": True,
                "message": f'User {"activated" if activate else "deactivated"} successfully',
            }
        )

    except Exception as e:
        return JsonResponse({"success": False, "message": str(e)})


@login_required
@require_http_methods(["POST"])
def reset_user_password(request, user_id):
    """Reset user password via AJAX."""
    try:
        user = get_object_or_404(User, id=user_id)

        # Check permissions
        if not RoleService.check_permission(request.user, "users", "change"):
            return JsonResponse({"success": False, "message": "Permission denied"})

        # Generate new password
        new_password = generate_secure_password()
        user.set_password(new_password)
        user.requires_password_change = True
        user.password_changed_at = timezone.now()
        user.failed_login_attempts = 0
        user.last_failed_login = None
        user.save()

        # Send password via email
        send_notification_email(
            user,
            "Password Reset - New Temporary Password",
            "accounts/emails/password_reset_by_admin.html",
            {
                "temporary_password": new_password,
                "reset_by": request.user.get_full_name(),
            },
        )

        # Create audit log
        client_info = get_client_info(request)
        UserAuditLog.objects.create(
            user=user,
            action="password_change",
            description=f"Password reset by admin {request.user.username}",
            performed_by=request.user,
            ip_address=client_info["ip_address"],
            user_agent=client_info["user_agent"],
        )

        return JsonResponse(
            {
                "success": True,
                "message": "Password reset successfully. Email sent to user.",
            }
        )

    except Exception as e:
        return JsonResponse({"success": False, "message": str(e)})


@login_required
@require_http_methods(["POST"])
def bulk_user_action(request):
    """Handle bulk actions on users."""
    try:
        # Check permissions
        if not RoleService.check_permission(request.user, "users", "change"):
            return JsonResponse({"success": False, "message": "Permission denied"})

        data = json.loads(request.body)
        user_ids = data.get("user_ids", [])
        action = data.get("action")
        roles = data.get("roles", [])

        if not user_ids or not action:
            return JsonResponse({"success": False, "message": "Invalid data"})

        users = User.objects.filter(id__in=user_ids)
        affected_count = 0

        with transaction.atomic():
            if action == "activate":
                affected_count = users.update(is_active=True)
            elif action == "deactivate":
                affected_count = users.update(is_active=False)
            elif action == "require_password_change":
                affected_count = users.update(requires_password_change=True)
            elif action == "assign_roles":
                for user in users:
                    for role_name in roles:
                        try:
                            RoleService.assign_role_to_user(
                                user, role_name, assigned_by=request.user
                            )
                        except ValueError:
                            pass
                affected_count = users.count()
            elif action == "remove_roles":
                for user in users:
                    for role_name in roles:
                        RoleService.remove_role_from_user(
                            user, role_name, removed_by=request.user
                        )
                affected_count = users.count()

            # Create audit logs
            client_info = get_client_info(request)
            for user in users:
                UserAuditLog.objects.create(
                    user=user,
                    action=action,
                    description=f"Bulk action: {action} by {request.user.username}",
                    performed_by=request.user,
                    ip_address=client_info["ip_address"],
                    user_agent=client_info["user_agent"],
                    extra_data={"action": action, "roles": roles},
                )

        return JsonResponse(
            {
                "success": True,
                "message": f'{action.replace("_", " ").title()} applied to {affected_count} users',
            }
        )

    except Exception as e:
        return JsonResponse({"success": False, "message": str(e)})


@login_required
def export_users(request):
    """Export users to CSV or Excel."""
    # Check permissions
    if not RoleService.check_permission(request.user, "users", "view"):
        messages.error(request, "Permission denied")
        return redirect("accounts:user_list")

    export_format = request.GET.get("format", "csv")

    # Get filtered queryset
    users = User.objects.select_related("profile").prefetch_related(
        "role_assignments__role"
    )

    # Apply same filters as list view
    search_query = request.GET.get("search", "")
    if search_query:
        users = users.filter(
            Q(username__icontains=search_query)
            | Q(email__icontains=search_query)
            | Q(first_name__icontains=search_query)
            | Q(last_name__icontains=search_query)
        )

    role_filter = request.GET.get("role", "")
    if role_filter:
        users = users.filter(
            role_assignments__role__name=role_filter, role_assignments__is_active=True
        ).distinct()

    if export_format == "csv":
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = (
            f'attachment; filename="users_{timezone.now().date()}.csv"'
        )

        writer = csv.writer(response)
        writer.writerow(
            [
                "Username",
                "Email",
                "First Name",
                "Last Name",
                "Phone",
                "Status",
                "Roles",
                "Date Joined",
                "Last Login",
            ]
        )

        for user in users:
            roles = ", ".join(
                [ra.role.name for ra in user.role_assignments.filter(is_active=True)]
            )
            writer.writerow(
                [
                    user.username,
                    user.email,
                    user.first_name,
                    user.last_name,
                    user.phone_number,
                    "Active" if user.is_active else "Inactive",
                    roles,
                    user.date_joined.strftime("%Y-%m-%d"),
                    (
                        user.last_login.strftime("%Y-%m-%d %H:%M")
                        if user.last_login
                        else "Never"
                    ),
                ]
            )

        return response

    # If not CSV, could add Excel export here
    messages.error(request, "Export format not supported")
    return redirect("accounts:user_list")


# Profile Views
@login_required
def profile_view(request):
    """Enhanced view for user profile management."""
    if request.method == "POST":
        form = UserProfileForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()

            # Create audit log
            client_info = get_client_info(request)
            UserAuditLog.objects.create(
                user=request.user,
                action="update",
                description="Profile updated",
                performed_by=request.user,
                ip_address=client_info["ip_address"],
                user_agent=client_info["user_agent"],
            )

            messages.success(request, "Your profile has been updated successfully!")
            return redirect("accounts:profile")
    else:
        form = UserProfileForm(instance=request.user)

    # Additional context
    context = {
        "form": form,
        "user_roles": request.user.role_assignments.filter(is_active=True),
        "active_sessions": request.user.sessions.filter(is_active=True),
        "recent_activity": request.user.audit_logs.order_by("-timestamp")[:5],
    }

    return render(request, "accounts/profile.html", context)


# Role Management Views
@method_decorator(admin_required, name="dispatch")
class RoleListView(ListView):
    """View for listing user roles."""

    model = UserRole
    template_name = "accounts/role_list.html"
    context_object_name = "roles"
    paginate_by = 12

    def get_queryset(self):
        return UserRole.objects.annotate(
            user_count=Count(
                "user_assignments", filter=Q(user_assignments__is_active=True)
            )
        ).order_by("name")


@method_decorator(admin_required, name="dispatch")
class RoleDetailView(DetailView):
    """View for displaying role details."""

    model = UserRole
    template_name = "accounts/role_detail.html"
    context_object_name = "role"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["role_users"] = self.object.user_assignments.filter(
            is_active=True
        ).select_related("user")
        context["permissions"] = self.object.permissions
        return context


@method_decorator(admin_required, name="dispatch")
class RoleCreateView(CreateView):
    """View for creating new roles."""

    model = UserRole
    template_name = "accounts/role_form.html"
    fields = ["name", "description", "permissions"]
    success_url = reverse_lazy("accounts:role_list")

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(
            self.request, f'Role "{form.instance.name}" created successfully!'
        )
        return super().form_valid(form)


@method_decorator(admin_required, name="dispatch")
class RoleUpdateView(UpdateView):
    """View for updating roles."""

    model = UserRole
    template_name = "accounts/role_form.html"
    fields = ["name", "description", "permissions"]
    success_url = reverse_lazy("accounts:role_list")

    def dispatch(self, request, *args, **kwargs):
        role = self.get_object()
        if role.is_system_role:
            messages.error(request, "System roles cannot be modified.")
            return redirect("accounts:role_list")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        messages.success(
            self.request, f'Role "{form.instance.name}" updated successfully!'
        )
        return super().form_valid(form)


@method_decorator(admin_required, name="dispatch")
class RoleDeleteView(DeleteView):
    """View for deleting roles."""

    model = UserRole
    template_name = "accounts/role_confirm_delete.html"
    success_url = reverse_lazy("accounts:role_list")
    context_object_name = "role"

    def dispatch(self, request, *args, **kwargs):
        role = self.get_object()
        if role.is_system_role:
            messages.error(request, "System roles cannot be deleted.")
            return redirect("accounts:role_list")
        return super().dispatch(request, *args, **kwargs)

    def delete(self, request, *args, **kwargs):
        role = self.get_object()
        role_name = role.name
        response = super().delete(request, *args, **kwargs)
        messages.success(request, f'Role "{role_name}" deleted successfully!')
        return response
