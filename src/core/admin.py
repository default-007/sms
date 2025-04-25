from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from .models import SystemSetting, AuditLog, Document


@admin.register(SystemSetting)
class SystemSettingAdmin(admin.ModelAdmin):
    list_display = ("setting_key", "data_type", "is_editable", "updated_at")
    list_filter = ("data_type", "is_editable")
    search_fields = ("setting_key", "description")
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        (
            None,
            {"fields": ("setting_key", "setting_value", "data_type", "description")},
        ),
        (_("Metadata"), {"fields": ("is_editable", "created_at", "updated_at")}),
    )


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = (
        "action",
        "entity_type",
        "entity_id",
        "user",
        "timestamp",
        "ip_address",
    )
    list_filter = ("action", "entity_type", "timestamp")
    search_fields = ("entity_type", "entity_id", "user__username", "ip_address")
    readonly_fields = (
        "user",
        "action",
        "entity_type",
        "entity_id",
        "data_before",
        "data_after",
        "ip_address",
        "user_agent",
        "timestamp",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "category",
        "file_type",
        "uploaded_by",
        "upload_date",
        "is_public",
    )
    list_filter = ("category", "file_type", "is_public", "upload_date")
    search_fields = ("title", "description", "uploaded_by__username")
    readonly_fields = ("upload_date",)
    fieldsets = (
        (
            None,
            {"fields": ("title", "description", "file_path", "file_type", "category")},
        ),
        (_("Relationship"), {"fields": ("related_to_type", "related_to_id")}),
        (_("Metadata"), {"fields": ("uploaded_by", "upload_date", "is_public")}),
    )
