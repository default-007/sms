from django.contrib import admin
from .models import Student, Parent, StudentParentRelation


class StudentParentRelationInline(admin.TabularInline):
    model = StudentParentRelation
    extra = 1


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = (
        "admission_number",
        "get_full_name",
        "current_class",
        "status",
        "admission_date",
    )
    list_filter = ("status", "current_class", "admission_date")
    search_fields = (
        "admission_number",
        "user__first_name",
        "user__last_name",
        "user__email",
    )
    date_hierarchy = "admission_date"
    inlines = [StudentParentRelationInline]

    def get_full_name(self, obj):
        return obj.get_full_name()

    get_full_name.short_description = "Full Name"


@admin.register(Parent)
class ParentAdmin(admin.ModelAdmin):
    list_display = ("get_full_name", "relation_with_student", "occupation")
    list_filter = ("relation_with_student",)
    search_fields = ("user__first_name", "user__last_name", "user__email", "occupation")
    inlines = [StudentParentRelationInline]

    def get_full_name(self, obj):
        return f"{obj.user.first_name} {obj.user.last_name}"

    get_full_name.short_description = "Full Name"
