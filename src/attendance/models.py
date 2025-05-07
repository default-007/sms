from django.db import models
from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from src.students.models import Student
from src.courses.models import Class


class AttendanceRecord(models.Model):
    """Model for storing daily attendance records for a class"""

    class_obj = models.ForeignKey(
        Class,
        on_delete=models.CASCADE,
        related_name="attendance_records",
        verbose_name=_("class"),
    )
    date = models.DateField(_("date"), default=timezone.now)
    marked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="marked_attendance",
        verbose_name=_("marked by"),
    )
    marked_at = models.DateTimeField(_("marked at"), auto_now_add=True)
    remarks = models.TextField(_("remarks"), blank=True)

    class Meta:
        verbose_name = _("attendance record")
        verbose_name_plural = _("attendance records")
        unique_together = ["class_obj", "date"]
        ordering = ["-date"]

    def __str__(self):
        return f"Attendance for {self.class_obj} on {self.date}"


class StudentAttendance(models.Model):
    """Model for storing individual student attendance"""

    STATUS_CHOICES = (
        ("present", _("Present")),
        ("absent", _("Absent")),
        ("late", _("Late")),
        ("excused", _("Excused")),
    )

    attendance_record = models.ForeignKey(
        AttendanceRecord,
        on_delete=models.CASCADE,
        related_name="student_attendances",
        verbose_name=_("attendance record"),
    )
    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="attendance_records",
        verbose_name=_("student"),
    )
    status = models.CharField(
        _("status"), max_length=10, choices=STATUS_CHOICES, default="present"
    )
    remarks = models.CharField(_("remarks"), max_length=255, blank=True)

    class Meta:
        verbose_name = _("student attendance")
        verbose_name_plural = _("student attendances")
        unique_together = ["attendance_record", "student"]

    def __str__(self):
        return f"{self.student} - {self.get_status_display()} on {self.attendance_record.date}"
