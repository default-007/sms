import json
from datetime import datetime, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db.models import Avg, Case, Count, F, IntegerField, Q, When
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    UpdateView,
)

from src.academics.models import Class
from src.core.decorators import audit_action
from src.students.models import Student

from .forms import AttendanceFilterForm, AttendanceRecordForm, StudentAttendanceFormSet
from .models import AttendanceRecord, StudentAttendance
from .services import AttendanceService


class AttendanceRecordListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = AttendanceRecord
    permission_required = "attendance.view_attendancerecord"
    context_object_name = "attendance_records"
    template_name = "attendance/attendance_record_list.html"
    paginate_by = 20

    def get_queryset(self):
        queryset = (
            super()
            .get_queryset()
            .select_related("class_obj", "marked_by")
            .prefetch_related("student_attendances")
        )

        # Apply class filter
        class_id = self.request.GET.get("class_id")
        if class_id:
            queryset = queryset.filter(class_obj_id=class_id)

        # Apply date range filter
        start_date = self.request.GET.get("start_date")
        end_date = self.request.GET.get("end_date")

        if start_date:
            queryset = queryset.filter(date__gte=start_date)
        if end_date:
            queryset = queryset.filter(date__lte=end_date)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["classes"] = Class.objects.all()
        return context


class AttendanceRecordDetailView(
    LoginRequiredMixin, PermissionRequiredMixin, DetailView
):
    model = AttendanceRecord
    permission_required = "attendance.view_attendancerecord"
    context_object_name = "attendance_record"
    template_name = "attendance/attendance_record_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get all student attendance for this record
        attendance_record = self.get_object()
        student_attendances = StudentAttendance.objects.filter(
            attendance_record=attendance_record
        ).select_related("student", "student__user")

        context["student_attendances"] = student_attendances
        return context


@login_required
@permission_required("attendance.view_attendancerecord")
def attendance_dashboard_view(request):
    """Enhanced dashboard view with analytics"""

    # Get time range from request (default: 30 days)
    days = int(request.GET.get("days", 30))
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=days)

    # Basic statistics
    total_students = Student.objects.filter(status="active").count()

    # Today's attendance statistics
    today_attendance = StudentAttendance.objects.filter(
        attendance_record__date=end_date
    ).aggregate(
        total=Count("id"),
        present=Count("id", filter=Q(status__in=["present", "late"])),
        absent=Count("id", filter=Q(status="absent")),
    )

    classes_marked_today = AttendanceRecord.objects.filter(date=end_date).count()

    # Average attendance calculation
    attendance_records = StudentAttendance.objects.filter(
        attendance_record__date__gte=start_date, attendance_record__date__lte=end_date
    )

    avg_attendance = 0
    if attendance_records.exists():
        total_records = attendance_records.count()
        present_records = attendance_records.filter(
            status__in=["present", "late"]
        ).count()
        avg_attendance = (
            (present_records / total_records * 100) if total_records > 0 else 0
        )

    # Trend data for chart
    trend_data = []
    trend_dates = []

    for i in range(days):
        current_date = end_date - timedelta(days=i)
        daily_attendance = StudentAttendance.objects.filter(
            attendance_record__date=current_date
        ).aggregate(
            total=Count("id"),
            present=Count("id", filter=Q(status__in=["present", "late"])),
        )

        percentage = 0
        if daily_attendance["total"] > 0:
            percentage = (daily_attendance["present"] / daily_attendance["total"]) * 100

        trend_data.insert(0, round(percentage, 1))
        trend_dates.insert(0, current_date.strftime("%Y-%m-%d"))

    # Class-wise attendance data
    class_data = Class.objects.annotate(
        total_attendance=Count("attendance_records__student_attendances"),
        present_attendance=Count(
            "attendance_records__student_attendances",
            filter=Q(
                attendance_records__student_attendances__status__in=["present", "late"]
            ),
        ),
    ).filter(
        attendance_records__date__gte=start_date, attendance_records__date__lte=end_date
    )

    class_labels = []
    class_percentages = []

    for class_obj in class_data:
        if class_obj.total_attendance > 0:
            percentage = (
                class_obj.present_attendance / class_obj.total_attendance
            ) * 100
            class_labels.append(str(class_obj))
            class_percentages.append(round(percentage, 1))

    # Status distribution
    status_distribution = attendance_records.values("status").annotate(
        count=Count("status")
    )

    status_data = {"present": 0, "absent": 0, "late": 0, "excused": 0}
    for item in status_distribution:
        status_data[item["status"]] = item["count"]

    # Low attendance students
    low_attendance_students = []
    students = Student.objects.filter(status="active").select_related(
        "user", "current_class"
    )

    for student in students:
        summary = AttendanceService.get_student_attendance_summary(
            student, start_date, end_date
        )
        if summary["total_days"] > 0 and summary["attendance_percentage"] < 80:
            low_attendance_students.append(
                {
                    "id": student.id,
                    "name": student.user.get_full_name(),
                    "class_name": (
                        str(student.current_class) if student.current_class else "N/A"
                    ),
                    "attendance_percentage": summary["attendance_percentage"],
                    "total_days": summary["total_days"],
                    "present_days": summary["present"] + summary["late"],
                    "absent_days": summary["absent"],
                }
            )

    # Sort by attendance percentage
    low_attendance_students.sort(key=lambda x: x["attendance_percentage"])

    context = {
        "stats": {
            "total_students": total_students,
            "average_attendance": round(avg_attendance, 1),
            "total_absent": today_attendance["absent"] or 0,
            "classes_marked_today": classes_marked_today,
        },
        "trend_data": {
            "dates": json.dumps(trend_dates),
            "percentages": json.dumps(trend_data),
        },
        "class_data": {
            "labels": json.dumps(class_labels),
            "percentages": json.dumps(class_percentages),
        },
        "status_data": {
            "values": json.dumps(
                [
                    status_data["present"],
                    status_data["absent"],
                    status_data["late"],
                    status_data["excused"],
                ]
            )
        },
        "low_attendance_students": low_attendance_students[:10],  # Top 10
    }

    return render(request, "attendance/attendance_dashboard.html", context)


@login_required
@permission_required("attendance.add_attendancerecord")
@audit_action("create", "attendance_record")
def mark_attendance_view(request, class_id=None):
    """View for marking attendance for a class"""

    # Get class if class_id is provided
    initial_class = None
    if class_id:
        initial_class = get_object_or_404(Class, id=class_id)

    if request.method == "POST":
        form = AttendanceRecordForm(request.POST)

        if form.is_valid():
            # Create attendance record
            attendance_record = form.save(commit=False)
            attendance_record.marked_by = request.user
            attendance_record.save()

            # Process student attendance data
            formset = StudentAttendanceFormSet(request.POST)

            if formset.is_valid():
                student_attendance_data = []

                for form_data in formset.cleaned_data:
                    if form_data:
                        student_attendance_data.append(
                            {
                                "student_id": form_data["student_id"],
                                "status": form_data["status"],
                                "remarks": form_data["remarks"],
                            }
                        )

                # Mark attendance using service
                AttendanceService.mark_attendance(
                    attendance_record.class_obj,
                    attendance_record.date,
                    request.user,
                    student_attendance_data,
                    attendance_record.remarks,
                )

                messages.success(request, "Attendance marked successfully!")
                return redirect("attendance:record-detail", pk=attendance_record.id)
            else:
                messages.error(
                    request, "There was an error with the student attendance data."
                )
        else:
            messages.error(request, "There was an error with the form.")
    else:
        # Initialize form with class if provided
        initial = {}
        if initial_class:
            initial["class_obj"] = initial_class

        initial["date"] = timezone.now().date()
        form = AttendanceRecordForm(initial=initial)

        # Initialize empty formset
        formset = StudentAttendanceFormSet()

    # Get students for the selected class
    selected_class = initial_class
    students = []

    if request.method == "POST" and form.is_valid():
        selected_class = form.cleaned_data["class_obj"]

    if selected_class:
        students = selected_class.students.select_related("user").all()

        # If formset is not bound or not valid, initialize it with student data
        if request.method != "POST" or not formset.is_valid():
            initial_data = [
                {
                    "student_id": student.id,
                    "student_name": f"{student.user.first_name} {student.user.last_name}",
                    "status": "present",
                    "remarks": "",
                }
                for student in students
            ]
            formset = StudentAttendanceFormSet(initial=initial_data)

    return render(
        request,
        "attendance/mark_attendance.html",
        {
            "form": form,
            "formset": formset,
            "students": students,
            "selected_class": selected_class,
        },
    )


@login_required
@permission_required("attendance.view_studentattendance")
def student_attendance_report_view(request, student_id):
    """View for displaying attendance report for a specific student"""

    student = get_object_or_404(Student, id=student_id)

    # Process filter form
    form = AttendanceFilterForm(request.GET)
    start_date = None
    end_date = None

    if form.is_valid():
        start_date = form.cleaned_data.get("start_date")
        end_date = form.cleaned_data.get("end_date")
        status = form.cleaned_data.get("status")

    # Get attendance records
    student_attendances = (
        StudentAttendance.objects.filter(student=student)
        .select_related("attendance_record")
        .order_by("-attendance_record__date")
    )

    if start_date:
        student_attendances = student_attendances.filter(
            attendance_record__date__gte=start_date
        )

    if end_date:
        student_attendances = student_attendances.filter(
            attendance_record__date__lte=end_date
        )

    if form.is_valid() and form.cleaned_data.get("status"):
        student_attendances = student_attendances.filter(
            status=form.cleaned_data.get("status")
        )

    # Get attendance summary
    attendance_summary = AttendanceService.get_student_attendance_summary(
        student, start_date, end_date
    )

    return render(
        request,
        "attendance/student_attendance_report.html",
        {
            "student": student,
            "student_attendances": student_attendances,
            "attendance_summary": attendance_summary,
            "form": form,
        },
    )


@login_required
@permission_required("attendance.view_attendancerecord")
def class_attendance_report_view(request, class_id):
    """View for displaying attendance report for a specific class"""

    class_obj = get_object_or_404(Class, id=class_id)

    # Process filter form
    form = AttendanceFilterForm(request.GET)
    start_date = None
    end_date = None

    if form.is_valid():
        start_date = form.cleaned_data.get("start_date")
        end_date = form.cleaned_data.get("end_date")

    # Get attendance records
    attendance_records = AttendanceRecord.objects.filter(class_obj=class_obj).order_by(
        "-date"
    )

    if start_date:
        attendance_records = attendance_records.filter(date__gte=start_date)

    if end_date:
        attendance_records = attendance_records.filter(date__lte=end_date)

    # Calculate statistics for each date
    attendance_stats = []

    for record in attendance_records:
        summary = AttendanceService.get_class_attendance_summary(class_obj, record.date)
        attendance_stats.append(
            {"date": record.date, "record": record, "summary": summary}
        )

    return render(
        request,
        "attendance/class_attendance_report.html",
        {"class_obj": class_obj, "attendance_stats": attendance_stats, "form": form},
    )
