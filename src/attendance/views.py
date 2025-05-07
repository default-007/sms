from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import (
    ListView,
    DetailView,
    CreateView,
    UpdateView,
    DeleteView,
)
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q

from .models import AttendanceRecord, StudentAttendance
from .forms import AttendanceRecordForm, StudentAttendanceFormSet, AttendanceFilterForm
from .services import AttendanceService
from src.courses.models import Class
from src.students.models import Student
from src.core.decorators import audit_log


class AttendanceRecordListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = AttendanceRecord
    permission_required = "attendance.view_attendancerecord"
    context_object_name = "attendance_records"
    template_name = "attendance/attendance_record_list.html"
    paginate_by = 20

    def get_queryset(self):
        queryset = super().get_queryset().select_related("class_obj", "marked_by")

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
@permission_required("attendance.add_attendancerecord")
@audit_log("create", "attendance_record")
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

    if status:
        student_attendances = student_attendances.filter(status=status)

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
