from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.urls import reverse_lazy
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

from .models import User, UserRole, UserRoleAssignment
from .forms import (
    CustomAuthenticationForm,
    CustomUserCreationForm,
    UserProfileForm,
    CustomPasswordChangeForm,
    CustomPasswordResetForm,
    CustomSetPasswordForm,
    UserRoleForm,
)
from .services import RoleService
from .decorators import admin_required, permission_required


class CustomLoginView(LoginView):
    """Custom login view with our form."""

    template_name = "accounts/login.html"
    form_class = CustomAuthenticationForm
    redirect_authenticated_user = True


class CustomLogoutView(LogoutView):
    """Custom logout view."""

    next_page = "login"


class CustomPasswordChangeView(PasswordChangeView):
    """Custom password change view with our form."""

    form_class = CustomPasswordChangeForm
    template_name = "accounts/password_change.html"
    success_url = reverse_lazy("profile")

    def form_valid(self, form):
        messages.success(self.request, "Your password has been updated successfully!")
        return super().form_valid(form)


class CustomPasswordResetView(PasswordResetView):
    """Custom password reset view with our form."""

    form_class = CustomPasswordResetForm
    template_name = "accounts/password_reset.html"
    email_template_name = "accounts/password_reset_email.html"
    success_url = reverse_lazy("password_reset_done")


class CustomPasswordResetConfirmView(PasswordResetConfirmView):
    """Custom password reset confirm view with our form."""

    form_class = CustomSetPasswordForm
    template_name = "accounts/password_reset_confirm.html"
    success_url = reverse_lazy("password_reset_complete")


@method_decorator(login_required, name="dispatch")
class UserListView(ListView):
    """View for listing users."""

    model = User
    template_name = "accounts/user_list.html"
    context_object_name = "users"
    paginate_by = 10

    def get_queryset(self):
        """Filter users based on search query."""
        queryset = super().get_queryset()
        search_query = self.request.GET.get("search", "")
        role_filter = self.request.GET.get("role", "")

        if search_query:
            queryset = queryset.filter(
                models.Q(username__icontains=search_query)
                | models.Q(email__icontains=search_query)
                | models.Q(first_name__icontains=search_query)
                | models.Q(last_name__icontains=search_query)
            )

        if role_filter:
            queryset = queryset.filter(role_assignments__role__name=role_filter)

        return queryset

    def get_context_data(self, **kwargs):
        """Add roles to context."""
        context = super().get_context_data(**kwargs)
        context["roles"] = UserRole.objects.all()
        context["selected_role"] = self.request.GET.get("role", "")
        context["search_query"] = self.request.GET.get("search", "")
        return context


@method_decorator(login_required, name="dispatch")
class UserDetailView(DetailView):
    """View for displaying user details."""

    model = User
    template_name = "accounts/user_detail.html"
    context_object_name = "user_obj"

    def get_context_data(self, **kwargs):
        """Add user roles to context."""
        context = super().get_context_data(**kwargs)
        context["user_roles"] = self.object.role_assignments.all()
        return context


@method_decorator(admin_required, name="dispatch")
class UserCreateView(CreateView):
    """View for creating a new user."""

    model = User
    form_class = CustomUserCreationForm
    template_name = "accounts/user_form.html"
    success_url = reverse_lazy("user_list")

    def get_context_data(self, **kwargs):
        """Add roles to context."""
        context = super().get_context_data(**kwargs)
        context["roles"] = UserRole.objects.all()
        return context

    @transaction.atomic
    def form_valid(self, form):
        """Process the form and assign roles."""
        # Create the user
        user = form.save()

        # Assign roles
        roles = form.cleaned_data.get("roles", [])
        for role in roles:
            UserRoleAssignment.objects.create(
                user=user, role=role, assigned_by=self.request.user
            )

        messages.success(
            self.request, f"User {user.username} has been created successfully!"
        )
        return super().form_valid(form)


@method_decorator(login_required, name="dispatch")
class UserUpdateView(UpdateView):
    """View for updating a user."""

    model = User
    form_class = UserProfileForm
    template_name = "accounts/user_form.html"
    success_url = reverse_lazy("user_list")

    def get_context_data(self, **kwargs):
        """Add roles to context."""
        context = super().get_context_data(**kwargs)
        context["roles"] = UserRole.objects.all()
        context["user_roles"] = self.object.role_assignments.all().values_list(
            "role__id", flat=True
        )
        return context

    def dispatch(self, request, *args, **kwargs):
        """Check permissions."""
        user = self.get_object()
        # Allow users to edit their own profile
        if user == request.user:
            return super().dispatch(request, *args, **kwargs)

        # For other users, check if the current user has permission
        if RoleService.check_permission(request.user, "users", "change"):
            return super().dispatch(request, *args, **kwargs)

        messages.error(request, "You do not have permission to edit this user.")
        return redirect("user_list")

    @transaction.atomic
    def form_valid(self, form):
        """Process the form and update roles if provided."""
        # Update the user
        user = form.save()

        # Update roles if provided in POST data
        roles = self.request.POST.getlist("roles", [])
        if roles:
            # Clear existing roles
            user.role_assignments.all().delete()

            # Assign new roles
            for role_id in roles:
                role = UserRole.objects.get(id=role_id)
                UserRoleAssignment.objects.create(
                    user=user, role=role, assigned_by=self.request.user
                )

        messages.success(
            self.request, f"User {user.username} has been updated successfully!"
        )
        return super().form_valid(form)


@method_decorator(admin_required, name="dispatch")
class UserDeleteView(DeleteView):
    """View for deleting a user."""

    model = User
    template_name = "accounts/user_confirm_delete.html"
    success_url = reverse_lazy("user_list")
    context_object_name = "user_obj"

    def delete(self, request, *args, **kwargs):
        """Delete the user and show a success message."""
        user = self.get_object()
        messages.success(
            request, f"User {user.username} has been deleted successfully!"
        )
        return super().delete(request, *args, **kwargs)


@method_decorator(permission_required("roles", "view"), name="dispatch")
class RoleListView(ListView):
    """View for listing user roles."""

    model = UserRole
    template_name = "accounts/role_list.html"
    context_object_name = "roles"
    paginate_by = 10


@method_decorator(permission_required("roles", "view"), name="dispatch")
class RoleDetailView(DetailView):
    """View for displaying role details."""

    model = UserRole
    template_name = "accounts/role_detail.html"
    context_object_name = "role"

    def get_context_data(self, **kwargs):
        """Add role users to context."""
        context = super().get_context_data(**kwargs)
        context["role_users"] = self.object.user_assignments.all()
        context["permissions"] = self.object.permissions
        return context


@method_decorator(admin_required, name="dispatch")
class RoleCreateView(CreateView):
    """View for creating a new role."""

    model = UserRole
    form_class = UserRoleForm
    template_name = "accounts/role_form.html"
    success_url = reverse_lazy("role_list")

    def get_context_data(self, **kwargs):
        """Add permission scopes to context."""
        from .constants import PERMISSION_SCOPES

        context = super().get_context_data(**kwargs)
        context["permission_scopes"] = PERMISSION_SCOPES
        return context

    @transaction.atomic
    def form_valid(self, form):
        """Process the form and add permissions."""
        # Create the role
        role = form.save(commit=False)

        # Process permissions from form data
        permissions = {}
        for resource, actions in self.request.POST.items():
            if resource.startswith("perm_"):
                resource_name = resource.replace("perm_", "")
                permissions[resource_name] = self.request.POST.getlist(resource)

        role.permissions = permissions
        role.save()

        messages.success(
            self.request, f"Role {role.name} has been created successfully!"
        )
        return super().form_valid(form)


@method_decorator(admin_required, name="dispatch")
class RoleUpdateView(UpdateView):
    """View for updating a role."""

    model = UserRole
    form_class = UserRoleForm
    template_name = "accounts/role_form.html"
    success_url = reverse_lazy("role_list")

    def get_context_data(self, **kwargs):
        """Add permission scopes and current permissions to context."""
        from .constants import PERMISSION_SCOPES

        context = super().get_context_data(**kwargs)
        context["permission_scopes"] = PERMISSION_SCOPES
        context["current_permissions"] = self.object.permissions
        return context

    @transaction.atomic
    def form_valid(self, form):
        """Process the form and update permissions."""
        # Update the role
        role = form.save(commit=False)

        # Process permissions from form data
        permissions = {}
        for resource, actions in self.request.POST.items():
            if resource.startswith("perm_"):
                resource_name = resource.replace("perm_", "")
                permissions[resource_name] = self.request.POST.getlist(resource)

        role.permissions = permissions
        role.save()

        messages.success(
            self.request, f"Role {role.name} has been updated successfully!"
        )
        return super().form_valid(form)


@method_decorator(admin_required, name="dispatch")
class RoleDeleteView(DeleteView):
    """View for deleting a role."""

    model = UserRole
    template_name = "accounts/role_confirm_delete.html"
    success_url = reverse_lazy("role_list")
    context_object_name = "role"

    def delete(self, request, *args, **kwargs):
        """Delete the role and show a success message."""
        role = self.get_object()
        messages.success(request, f"Role {role.name} has been deleted successfully!")
        return super().delete(request, *args, **kwargs)


@login_required
def profile_view(request):
    """View for displaying and updating user profile."""
    if request.method == "POST":
        form = UserProfileForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Your profile has been updated successfully!")
            return redirect("profile")
    else:
        form = UserProfileForm(instance=request.user)

    return render(
        request,
        "accounts/profile.html",
        {"form": form, "user_roles": request.user.role_assignments.all()},
    )
