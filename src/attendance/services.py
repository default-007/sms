from datetime import datetime, timedelta

from django.db.models import Avg, Case, Count, F, IntegerField, Q, When
from django.db.models.functions import Extract
from django.utils import timezone

from .models import AttendanceRecord, StudentAttendance


class AttendanceService:
    """Enhanced service class for attendance-related business logic"""

    @staticmethod
    def mark_attendance(
        class_obj, date, marked_by, student_attendance_data, remarks=""
    ):
        """Mark attendance for a class on a specific date"""
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
        """Get comprehensive attendance summary for a student"""
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
        """Get attendance summary for a class on a specific date"""
        if not date:
            date = timezone.now().date()

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
            total_students = class_obj.students.count()
            return {
                "record_exists": False,
                "total_students": total_students,
                "status_counts": {"present": 0, "absent": 0, "late": 0, "excused": 0},
                "attendance_percentage": 0,
                "marked_by": None,
                "marked_at": None,
            }

    @staticmethod
    def get_attendance_trends(class_obj=None, days=30):
        """Get attendance trends over specified number of days"""
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)

        query = StudentAttendance.objects.filter(
            attendance_record__date__gte=start_date,
            attendance_record__date__lte=end_date,
        )

        if class_obj:
            query = query.filter(attendance_record__class_obj=class_obj)

        # Group by date and calculate percentages
        trends = (
            query.values("attendance_record__date")
            .annotate(
                total=Count("id"),
                present=Count("id", filter=Q(status__in=["present", "late"])),
                absent=Count("id", filter=Q(status="absent")),
            )
            .order_by("attendance_record__date")
        )

        trend_data = []
        for trend in trends:
            date = trend["attendance_record__date"]
            total = trend["total"]
            present = trend["present"]
            percentage = (present / total * 100) if total > 0 else 0

            trend_data.append(
                {
                    "date": date,
                    "percentage": round(percentage, 2),
                    "total": total,
                    "present": present,
                    "absent": trend["absent"],
                }
            )

        return trend_data

    @staticmethod
    def get_monthly_attendance_stats(year=None, month=None):
        """Get detailed monthly attendance statistics"""
        if not year:
            year = timezone.now().year
        if not month:
            month = timezone.now().month

        # Get all attendance records for the month
        attendance_records = StudentAttendance.objects.filter(
            attendance_record__date__year=year, attendance_record__date__month=month
        )

        # Overall statistics
        total_records = attendance_records.count()
        present_records = attendance_records.filter(
            status__in=["present", "late"]
        ).count()
        absent_records = attendance_records.filter(status="absent").count()
        late_records = attendance_records.filter(status="late").count()
        excused_records = attendance_records.filter(status="excused").count()

        overall_percentage = (
            (present_records / total_records * 100) if total_records > 0 else 0
        )

        # Day-wise breakdown
        day_wise = (
            attendance_records.values("attendance_record__date")
            .annotate(
                total=Count("id"),
                present=Count("id", filter=Q(status__in=["present", "late"])),
                absent=Count("id", filter=Q(status="absent")),
                late=Count("id", filter=Q(status="late")),
                excused=Count("id", filter=Q(status="excused")),
            )
            .order_by("attendance_record__date")
        )

        # Class-wise breakdown
        class_wise = (
            attendance_records.values(
                "attendance_record__class_obj__grade__name",
                "attendance_record__class_obj__section__name",
            )
            .annotate(
                total=Count("id"),
                present=Count("id", filter=Q(status__in=["present", "late"])),
                absent=Count("id", filter=Q(status="absent")),
            )
            .order_by("attendance_record__class_obj__grade__name")
        )

        return {
            "overall": {
                "total_records": total_records,
                "present_records": present_records,
                "absent_records": absent_records,
                "late_records": late_records,
                "excused_records": excused_records,
                "attendance_percentage": round(overall_percentage, 2),
            },
            "day_wise": list(day_wise),
            "class_wise": list(class_wise),
        }

    @staticmethod
    def get_low_attendance_students(threshold=75, days=30):
        """Get students with attendance below threshold"""
        from src.students.models import Student

        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)

        low_attendance = []
        students = Student.objects.filter(status="active").select_related(
            "user", "current_class"
        )

        for student in students:
            summary = AttendanceService.get_student_attendance_summary(
                student, start_date, end_date
            )

            if (
                summary["total_days"] > 0
                and summary["attendance_percentage"] < threshold
            ):
                low_attendance.append(
                    {
                        "student": student,
                        "summary": summary,
                        "percentage": summary["attendance_percentage"],
                    }
                )

        # Sort by attendance percentage
        low_attendance.sort(key=lambda x: x["percentage"])
        return low_attendance

    @staticmethod
    def get_attendance_analytics_dashboard(days=30):
        """Get comprehensive analytics for dashboard"""
        from src.courses.models import Class
        from src.students.models import Student

        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)

        # Basic counts
        total_students = Student.objects.filter(status="active").count()
        total_classes = Class.objects.count()

        # Today's attendance
        today_attendance = StudentAttendance.objects.filter(
            attendance_record__date=end_date
        ).aggregate(
            total=Count("id"),
            present=Count("id", filter=Q(status__in=["present", "late"])),
            absent=Count("id", filter=Q(status="absent")),
            late=Count("id", filter=Q(status="late")),
            excused=Count("id", filter=Q(status="excused")),
        )

        # Classes marked today
        classes_marked_today = AttendanceRecord.objects.filter(date=end_date).count()

        # Average attendance over period
        period_attendance = StudentAttendance.objects.filter(
            attendance_record__date__gte=start_date,
            attendance_record__date__lte=end_date,
        ).aggregate(
            total=Count("id"),
            present=Count("id", filter=Q(status__in=["present", "late"])),
        )

        avg_attendance = 0
        if period_attendance["total"] > 0:
            avg_attendance = (
                period_attendance["present"] / period_attendance["total"]
            ) * 100

        # Trend data
        trends = AttendanceService.get_attendance_trends(days=days)

        # Low attendance students
        low_attendance = AttendanceService.get_low_attendance_students(
            threshold=80, days=days
        )

        return {
            "basic_stats": {
                "total_students": total_students,
                "total_classes": total_classes,
                "classes_marked_today": classes_marked_today,
                "average_attendance": round(avg_attendance, 1),
            },
            "today_stats": today_attendance,
            "trends": trends,
            "low_attendance_students": low_attendance[:10],  # Top 10
        }

    @staticmethod
    def generate_attendance_report(class_obj, start_date, end_date):
        """Generate comprehensive attendance report for a class"""
        # Get all attendance records for the period
        attendance_records = AttendanceRecord.objects.filter(
            class_obj=class_obj, date__gte=start_date, date__lte=end_date
        ).order_by("date")

        # Get all students in the class
        students = class_obj.students.select_related("user").all()

        # Build report data
        report_data = {
            "class_info": {
                "name": str(class_obj),
                "total_students": students.count(),
                "period": f"{start_date} to {end_date}",
                "total_days": attendance_records.count(),
            },
            "summary": {},
            "student_details": [],
            "daily_summary": [],
        }

        # Calculate overall summary
        all_attendance = StudentAttendance.objects.filter(
            attendance_record__in=attendance_records
        )

        total_possible = students.count() * attendance_records.count()
        if total_possible > 0:
            present_count = all_attendance.filter(
                status__in=["present", "late"]
            ).count()
            report_data["summary"] = {
                "total_possible_attendance": total_possible,
                "total_present": present_count,
                "total_absent": all_attendance.filter(status="absent").count(),
                "total_late": all_attendance.filter(status="late").count(),
                "total_excused": all_attendance.filter(status="excused").count(),
                "overall_percentage": round((present_count / total_possible) * 100, 2),
            }

        # Student-wise details
        for student in students:
            student_summary = AttendanceService.get_student_attendance_summary(
                student, start_date, end_date
            )

            report_data["student_details"].append(
                {
                    "student_name": student.user.get_full_name(),
                    "roll_number": student.roll_number,
                    "summary": student_summary,
                }
            )

        # Daily summary
        for record in attendance_records:
            daily_summary = AttendanceService.get_class_attendance_summary(
                class_obj, record.date
            )
            report_data["daily_summary"].append(
                {"date": record.date, "summary": daily_summary}
            )

        return report_data
