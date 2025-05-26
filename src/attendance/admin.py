# Register your models here.
from django.contrib import admin
from django.db.models import Count, Q
from django.urls import reverse
from django.utils.html import format_html

from .models import AttendanceRecord, StudentAttendance


@admin.register(AttendanceRecord)
class AttendanceRecordAdmin(admin.ModelAdmin):
    list_display = [
        "class_obj",
        "date",
        "total_students",
        "present_count",
        "absent_count",
        "attendance_percentage",
        "marked_by",
        "marked_at",
    ]
    list_filter = ["date", "class_obj__grade", "class_obj", "marked_by"]
    search_fields = ["class_obj__grade__name", "class_obj__section__name", "remarks"]
    date_hierarchy = "date"
    readonly_fields = ["marked_by", "marked_at"]

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related(
                "class_obj", "class_obj__grade", "class_obj__section", "marked_by"
            )
            .prefetch_related("student_attendances")
        )

    def total_students(self, obj):
        return obj.student_attendances.count()

    total_students.short_description = "Total Students"

    def present_count(self, obj):
        count = obj.student_attendances.filter(
            Q(status="present") | Q(status="late")
        ).count()
        return format_html('<span style="color: green;">{}</span>', count)

    present_count.short_description = "Present"

    def absent_count(self, obj):
        count = obj.student_attendances.filter(status="absent").count()
        return format_html('<span style="color: red;">{}</span>', count)

    absent_count.short_description = "Absent"

    def attendance_percentage(self, obj):
        total = obj.student_attendances.count()
        if total == 0:
            return "0%"
        present = obj.student_attendances.filter(
            Q(status="present") | Q(status="late")
        ).count()
        percentage = (present / total) * 100
        color = "green" if percentage >= 80 else "orange" if percentage >= 60 else "red"
        return format_html('<span style="color: {};">{:.1f}%</span>', color, percentage)

    attendance_percentage.short_description = "Attendance %"


@admin.register(StudentAttendance)
class StudentAttendanceAdmin(admin.ModelAdmin):
    list_display = ["student", "attendance_record", "status", "remarks"]
    list_filter = [
        "status",
        "attendance_record__date",
        "attendance_record__class_obj",
        "student__current_class",
    ]
    search_fields = [
        "student__user__first_name",
        "student__user__last_name",
        "student__admission_number",
        "remarks",
    ]
    date_hierarchy = "attendance_record__date"

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related(
                "student",
                "student__user",
                "attendance_record",
                "attendance_record__class_obj",
            )
        )
