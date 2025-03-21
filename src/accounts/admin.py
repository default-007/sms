from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _

from .models import User, UserRole, UserRoleAssignment
from .forms import CustomUserCreationForm


class UserRoleAssignmentInline(admin.TabularInline):
    """Inline admin for user role assignments."""

    model = UserRoleAssignment
    extra = 1
    fk_name = "user"
    autocomplete_fields = ["role", "assigned_by"]


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Admin configuration for User model."""

    add_form = CustomUserCreationForm
    list_display = (
        "username",
        "email",
        "first_name",
        "last_name",
        "is_staff",
        "is_active",
    )
    list_filter = ("is_staff", "is_active", "role_assignments__role")
    fieldsets = (
        (None, {"fields": ("username", "password")}),
        (
            _("Personal info"),
            {
                "fields": (
                    "first_name",
                    "last_name",
                    "email",
                    "phone_number",
                    "address",
                    "date_of_birth",
                    "gender",
                    "profile_picture",
                )
            },
        ),
        (
            _("Permissions"),
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        (_("Important dates"), {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("username", "email", "password1", "password2"),
            },
        ),
    )
    search_fields = ("username", "email", "first_name", "last_name")
    ordering = ("username",)
    inlines = [UserRoleAssignmentInline]


@admin.register(UserRole)
class UserRoleAdmin(admin.ModelAdmin):
    """Admin configuration for UserRole model."""

    list_display = ("name", "description")
    search_fields = ("name", "description")
    ordering = ("name",)


@admin.register(UserRoleAssignment)
class UserRoleAssignmentAdmin(admin.ModelAdmin):
    """Admin configuration for UserRoleAssignment model."""

    list_display = ("user", "role", "assigned_date", "assigned_by")
    list_filter = ("role", "assigned_date")
    search_fields = ("user__username", "user__email", "role__name")
    ordering = ("-assigned_date",)
    autocomplete_fields = ["user", "role", "assigned_by"]
