from datetime import datetime, timedelta
from django.db.models import Count, Q, Case, When, IntegerField, F
from django.utils import timezone
from .models import AttendanceRecord, StudentAttendance


class AttendanceService:
    """Service class for attendance-related business logic"""

    @staticmethod
    def mark_attendance(
        class_obj, date, marked_by, student_attendance_data, remarks=""
    ):
        """
        Mark attendance for a class on a specific date

        Args:
            class_obj: Class object
            date: Date of attendance
            marked_by: User who is marking attendance
            student_attendance_data: List of dictionaries with student_id, status, remarks
            remarks: Optional remarks for the attendance record

        Returns:
            AttendanceRecord object
        """
        # Create or update attendance record
        attendance_record, created = AttendanceRecord.objects.update_or_create(
            class_obj=class_obj,
            date=date,
            defaults={"marked_by": marked_by, "remarks": remarks},
        )

        # Record individual student attendance
        for attendance_data in student_attendance_data:
            student_id = attendance_data.get("student_id")
            status = attendance_data.get("status", "present")
            student_remarks = attendance_data.get("remarks", "")

            StudentAttendance.objects.update_or_create(
                attendance_record=attendance_record,
                student_id=student_id,
                defaults={"status": status, "remarks": student_remarks},
            )

        return attendance_record

    @staticmethod
    def get_student_attendance_summary(student, start_date=None, end_date=None):
        """
        Get attendance summary for a student within a date range

        Args:
            student: Student object
            start_date: Start date for filtering (optional)
            end_date: End date for filtering (optional)

        Returns:
            Dictionary with attendance statistics
        """
        # Set default date range if not provided
        if not end_date:
            end_date = timezone.now().date()
        if not start_date:
            start_date = end_date - timedelta(days=30)

        # Query student attendance
        attendance_queryset = StudentAttendance.objects.filter(
            student=student,
            attendance_record__date__gte=start_date,
            attendance_record__date__lte=end_date,
        )

        # Count by status
        status_counts = attendance_queryset.values("status").annotate(
            count=Count("status")
        )

        # Convert to dictionary
        attendance_summary = {
            "present": 0,
            "absent": 0,
            "late": 0,
            "excused": 0,
            "total_days": 0,
            "attendance_percentage": 0,
        }

        for item in status_counts:
            attendance_summary[item["status"]] = item["count"]

        # Calculate total days and attendance percentage
        attendance_summary["total_days"] = sum(attendance_summary.values())

        if attendance_summary["total_days"] > 0:
            present_count = attendance_summary["present"] + attendance_summary["late"]
            attendance_summary["attendance_percentage"] = (
                present_count / attendance_summary["total_days"]
            ) * 100

        return attendance_summary

    @staticmethod
    def get_class_attendance_summary(class_obj, date=None):
        """
        Get attendance summary for a class on a specific date

        Args:
            class_obj: Class object
            date: Date for which to get attendance (default: today)

        Returns:
            Dictionary with attendance statistics
        """
        if not date:
            date = timezone.now().date()

        # Try to find attendance record for the date
        try:
            attendance_record = AttendanceRecord.objects.get(
                class_obj=class_obj, date=date
            )
            student_attendance = StudentAttendance.objects.filter(
                attendance_record=attendance_record
            )

            # Count by status
            status_counts = {
                "present": student_attendance.filter(status="present").count(),
                "absent": student_attendance.filter(status="absent").count(),
                "late": student_attendance.filter(status="late").count(),
                "excused": student_attendance.filter(status="excused").count(),
            }

            total_students = sum(status_counts.values())

            # Calculate attendance percentage
            if total_students > 0:
                present_count = status_counts["present"] + status_counts["late"]
                attendance_percentage = (present_count / total_students) * 100
            else:
                attendance_percentage = 0

            return {
                "record_exists": True,
                "total_students": total_students,
                "status_counts": status_counts,
                "attendance_percentage": attendance_percentage,
                "marked_by": attendance_record.marked_by,
                "marked_at": attendance_record.marked_at,
            }

        except AttendanceRecord.DoesNotExist:
            # No attendance record exists for this date
            total_students = class_obj.students.count()

            return {
                "record_exists": False,
                "total_students": total_students,
                "status_counts": {"present": 0, "absent": 0, "late": 0, "excused": 0},
                "attendance_percentage": 0,
                "marked_by": None,
                "marked_at": None,
            }
