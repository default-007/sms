from django.contrib import admin
from django.utils.html import format_html
from .models import SystemSetting, AuditLog, Document


@admin.register(SystemSetting)
class SystemSettingAdmin(admin.ModelAdmin):
    list_display = (
        "setting_key",
        "setting_value_display",
        "data_type",
        "is_editable",
        "updated_at",
    )
    list_filter = ("data_type", "is_editable")
    search_fields = ("setting_key", "setting_value", "description")
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        (
            None,
            {"fields": ("setting_key", "setting_value", "data_type", "description")},
        ),
        ("Options", {"fields": ("is_editable", "created_at", "updated_at")}),
    )

    def setting_value_display(self, obj):
        if obj.data_type == "json":
            return "<JSON Data>"
        elif len(obj.setting_value) > 50:
            return f"{obj.setting_value[:50]}..."
        return obj.setting_value

    setting_value_display.short_description = "Setting Value"


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = (
        "timestamp",
        "user",
        "action",
        "entity_type",
        "entity_id",
        "ip_address",
    )
    list_filter = ("action", "entity_type", "timestamp")
    search_fields = ("user__username", "entity_type", "entity_id", "ip_address")
    readonly_fields = (
        "timestamp",
        "user",
        "action",
        "entity_type",
        "entity_id",
        "data_before",
        "data_after",
        "ip_address",
        "user_agent",
    )
    date_hierarchy = "timestamp"

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
        "file_link",
    )
    list_filter = ("category", "file_type", "is_public", "upload_date")
    search_fields = ("title", "description", "uploaded_by__username")
    readonly_fields = ("upload_date", "file_type")
    date_hierarchy = "upload_date"

    def file_link(self, obj):
        if obj.file_path:
            return format_html(
                '<a href="{}" target="_blank">View File</a>', obj.file_path.url
            )
        return "-"

    file_link.short_description = "File"
