import csv
import json
from datetime import datetime, timedelta
from io import StringIO

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Avg, Count, Q
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    FormView,
    ListView,
    TemplateView,
    UpdateView,
    View,
)

from academics.models import Class, Grade, Term
from core.mixins import ModulePermissionMixin
from subjects.models import Subject
from teachers.models import Teacher

from .forms import (
    BulkTimetableForm,
    ConflictAnalysisForm,
    RoomForm,
    SchedulingConstraintForm,
    SubstituteTeacherForm,
    TimeSlotForm,
    TimetableFilterForm,
    TimetableForm,
    TimetableGenerationForm,
    TimetableTemplateForm,
)
from .models import (
    Room,
    SchedulingConstraint,
    SubstituteTeacher,
    TimeSlot,
    Timetable,
    TimetableGeneration,
    TimetableTemplate,
)
from .services.analytics_service import SchedulingAnalyticsService
from .services.optimization_service import OptimizationService
from .services.timetable_service import RoomService, SubstituteService, TimetableService


class SchedulingDashboardView(LoginRequiredMixin, ModulePermissionMixin, TemplateView):
    """Main scheduling dashboard"""

    template_name = "scheduling/dashboard.html"
    module_name = "scheduling"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get current term
        current_term = Term.objects.filter(is_current=True).first()

        if current_term:
            # Quick stats
            context["stats"] = {
                "total_timetable_entries": Timetable.objects.filter(
                    term=current_term, is_active=True
                ).count(),
                "total_teachers": Teacher.objects.filter(status="active").count(),
                "total_rooms": Room.objects.filter(is_available=True).count(),
                "pending_substitutes": SubstituteTeacher.objects.filter(
                    original_timetable__term=current_term, approved_by__isnull=True
                ).count(),
            }

            # Recent activities
            context["recent_generations"] = TimetableGeneration.objects.filter(
                term=current_term
            ).order_by("-started_at")[:5]

            # Optimization score
            context["optimization_score"] = (
                SchedulingAnalyticsService.get_timetable_optimization_score(
                    current_term
                )
            )

            # Conflicts summary
            context["conflicts"] = (
                SchedulingAnalyticsService.get_scheduling_conflicts_analytics(
                    current_term
                )
            )

        context["current_term"] = current_term
        return context


# Timetable Views
class TimetableListView(LoginRequiredMixin, ModulePermissionMixin, ListView):
    """List all timetable entries"""

    model = Timetable
    template_name = "scheduling/timetable_list.html"
    context_object_name = "timetables"
    paginate_by = 25
    module_name = "scheduling"

    def get_queryset(self):
        queryset = Timetable.objects.select_related(
            "class_assigned", "subject", "teacher", "time_slot", "room", "term"
        ).filter(is_active=True)

        # Apply filters
        form = TimetableFilterForm(self.request.GET)
        if form.is_valid():
            if form.cleaned_data.get("term"):
                queryset = queryset.filter(term=form.cleaned_data["term"])
            if form.cleaned_data.get("grade"):
                queryset = queryset.filter(
                    class_assigned__grade=form.cleaned_data["grade"]
                )
            if form.cleaned_data.get("class_assigned"):
                queryset = queryset.filter(
                    class_assigned=form.cleaned_data["class_assigned"]
                )
            if form.cleaned_data.get("teacher"):
                queryset = queryset.filter(teacher=form.cleaned_data["teacher"])
            if form.cleaned_data.get("subject"):
                queryset = queryset.filter(subject=form.cleaned_data["subject"])
            if form.cleaned_data.get("day_of_week"):
                queryset = queryset.filter(
                    time_slot__day_of_week=form.cleaned_data["day_of_week"]
                )

        return queryset.order_by("time_slot__day_of_week", "time_slot__period_number")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["filter_form"] = TimetableFilterForm(self.request.GET)
        return context


class TimetableDetailView(LoginRequiredMixin, ModulePermissionMixin, DetailView):
    """Detailed view of a timetable entry"""

    model = Timetable
    template_name = "scheduling/timetable_detail.html"
    context_object_name = "timetable"
    module_name = "scheduling"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Check for conflicts
        timetable = self.get_object()
        conflicts = TimetableService.check_conflicts(
            teacher=timetable.teacher,
            room=timetable.room,
            class_obj=timetable.class_assigned,
            time_slot=timetable.time_slot,
            date_range=(timetable.effective_from_date, timetable.effective_to_date),
            exclude_timetable=timetable,
        )

        context["conflicts"] = conflicts

        # Substitute history
        context["substitutes"] = SubstituteTeacher.objects.filter(
            original_timetable=timetable
        ).order_by("-date")[:10]

        return context


class TimetableCreateView(LoginRequiredMixin, ModulePermissionMixin, CreateView):
    """Create new timetable entry"""

    model = Timetable
    form_class = TimetableForm
    template_name = "scheduling/timetable_form.html"
    module_name = "scheduling"
    permission_required = "scheduling.add_timetable"

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, "Timetable entry created successfully.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("scheduling:timetable_detail", kwargs={"pk": self.object.pk})


class TimetableUpdateView(LoginRequiredMixin, ModulePermissionMixin, UpdateView):
    """Update timetable entry"""

    model = Timetable
    form_class = TimetableForm
    template_name = "scheduling/timetable_form.html"
    module_name = "scheduling"
    permission_required = "scheduling.change_timetable"

    def form_valid(self, form):
        messages.success(self.request, "Timetable entry updated successfully.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("scheduling:timetable_detail", kwargs={"pk": self.object.pk})


class TimetableDeleteView(LoginRequiredMixin, ModulePermissionMixin, DeleteView):
    """Delete timetable entry"""

    model = Timetable
    template_name = "scheduling/timetable_confirm_delete.html"
    module_name = "scheduling"
    permission_required = "scheduling.delete_timetable"
    success_url = reverse_lazy("scheduling:timetable_list")

    def delete(self, request, *args, **kwargs):
        messages.success(request, "Timetable entry deleted successfully.")
        return super().delete(request, *args, **kwargs)


class ClassTimetableView(LoginRequiredMixin, ModulePermissionMixin, TemplateView):
    """View timetable for a specific class"""

    template_name = "scheduling/class_timetable.html"
    module_name = "scheduling"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        class_obj = get_object_or_404(Class, id=kwargs["class_id"])
        term_id = self.request.GET.get("term_id")

        if term_id:
            term = get_object_or_404(Term, id=term_id)
        else:
            term = Term.objects.filter(is_current=True).first()

        if term:
            timetable_data = TimetableService.get_class_timetable(class_obj, term)
            context["timetable_data"] = timetable_data

        context["class_obj"] = class_obj
        context["term"] = term
        context["available_terms"] = Term.objects.all().order_by("-start_date")

        return context


class TeacherTimetableView(LoginRequiredMixin, ModulePermissionMixin, TemplateView):
    """View timetable for a specific teacher"""

    template_name = "scheduling/teacher_timetable.html"
    module_name = "scheduling"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        teacher = get_object_or_404(Teacher, id=kwargs["teacher_id"])
        term_id = self.request.GET.get("term_id")

        if term_id:
            term = get_object_or_404(Term, id=term_id)
        else:
            term = Term.objects.filter(is_current=True).first()

        if term:
            timetable_data = TimetableService.get_teacher_timetable(teacher, term)
            workload_data = TimetableService.get_teacher_workload(teacher, term)

            context["timetable_data"] = timetable_data
            context["workload_data"] = workload_data

        context["teacher"] = teacher
        context["term"] = term
        context["available_terms"] = Term.objects.all().order_by("-start_date")

        return context


class BulkTimetableCreateView(LoginRequiredMixin, ModulePermissionMixin, FormView):
    """Bulk create timetable entries"""

    form_class = BulkTimetableForm
    template_name = "scheduling/bulk_timetable_create.html"
    module_name = "scheduling"
    permission_required = "scheduling.bulk_edit_timetable"

    def form_valid(self, form):
        term = form.cleaned_data["term"]
        grades = form.cleaned_data["grades"]
        copy_from_term = form.cleaned_data.get("copy_from_term")

        if copy_from_term:
            # Copy from existing term
            result = TimetableService.copy_timetable_to_term(
                copy_from_term, term, list(grades), self.request.user
            )
        else:
            # Create new timetables (this would need additional logic)
            result = {"copied": 0, "errors": ["Manual creation not implemented"]}

        if result["errors"]:
            for error in result["errors"]:
                messages.error(self.request, error)

        if result.get("copied", 0) > 0:
            messages.success(
                self.request,
                f"Successfully created {result['copied']} timetable entries.",
            )

        return redirect("scheduling:timetable_list")


# Time Slot Views
class TimeSlotListView(LoginRequiredMixin, ModulePermissionMixin, ListView):
    """List all time slots"""

    model = TimeSlot
    template_name = "scheduling/timeslot_list.html"
    context_object_name = "timeslots"
    module_name = "scheduling"
    ordering = ["day_of_week", "period_number"]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Group by day of week
        timeslots_by_day = {}
        for timeslot in context["timeslots"]:
            day = timeslot.get_day_of_week_display()
            if day not in timeslots_by_day:
                timeslots_by_day[day] = []
            timeslots_by_day[day].append(timeslot)

        context["timeslots_by_day"] = timeslots_by_day
        return context


class TimeSlotCreateView(LoginRequiredMixin, ModulePermissionMixin, CreateView):
    """Create new time slot"""

    model = TimeSlot
    form_class = TimeSlotForm
    template_name = "scheduling/timeslot_form.html"
    module_name = "scheduling"
    permission_required = "scheduling.create_time_slots"
    success_url = reverse_lazy("scheduling:timeslot_list")

    def form_valid(self, form):
        messages.success(self.request, "Time slot created successfully.")
        return super().form_valid(form)


# Room Views
class RoomListView(LoginRequiredMixin, ModulePermissionMixin, ListView):
    """List all rooms"""

    model = Room
    template_name = "scheduling/room_list.html"
    context_object_name = "rooms"
    module_name = "scheduling"
    paginate_by = 20
    ordering = ["building", "number"]

    def get_queryset(self):
        queryset = super().get_queryset()

        # Filter by room type
        room_type = self.request.GET.get("room_type")
        if room_type:
            queryset = queryset.filter(room_type=room_type)

        # Filter by building
        building = self.request.GET.get("building")
        if building:
            queryset = queryset.filter(building=building)

        # Search
        search = self.request.GET.get("search")
        if search:
            queryset = queryset.filter(
                Q(number__icontains=search) | Q(name__icontains=search)
            )

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["room_types"] = Room.objects.values_list(
            "room_type", flat=True
        ).distinct()
        context["buildings"] = Room.objects.values_list(
            "building", flat=True
        ).distinct()
        return context


class RoomUtilizationView(LoginRequiredMixin, ModulePermissionMixin, DetailView):
    """Room utilization analytics"""

    model = Room
    template_name = "scheduling/room_utilization.html"
    context_object_name = "room"
    module_name = "scheduling"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        room = self.get_object()
        term_id = self.request.GET.get("term_id")

        if term_id:
            term = get_object_or_404(Term, id=term_id)
        else:
            term = Term.objects.filter(is_current=True).first()

        if term:
            utilization_data = RoomService.get_room_utilization(room, term)
            calendar_data = RoomService.get_room_booking_calendar(room, term)

            context["utilization_data"] = utilization_data
            context["calendar_data"] = calendar_data

        context["term"] = term
        context["available_terms"] = Term.objects.all().order_by("-start_date")

        return context


# Substitute Teacher Views
class SubstituteTeacherListView(LoginRequiredMixin, ModulePermissionMixin, ListView):
    """List substitute teacher assignments"""

    model = SubstituteTeacher
    template_name = "scheduling/substitute_list.html"
    context_object_name = "substitutes"
    module_name = "scheduling"
    paginate_by = 20
    ordering = ["-date", "-created_at"]

    def get_queryset(self):
        queryset = (
            super()
            .get_queryset()
            .select_related("original_timetable", "substitute_teacher", "approved_by")
        )

        # Filter by approval status
        status = self.request.GET.get("status")
        if status == "pending":
            queryset = queryset.filter(approved_by__isnull=True)
        elif status == "approved":
            queryset = queryset.filter(approved_by__isnull=False)

        # Filter by date range
        start_date = self.request.GET.get("start_date")
        end_date = self.request.GET.get("end_date")

        if start_date:
            queryset = queryset.filter(date__gte=start_date)
        if end_date:
            queryset = queryset.filter(date__lte=end_date)

        return queryset


class SubstituteTeacherCreateView(
    LoginRequiredMixin, ModulePermissionMixin, CreateView
):
    """Create substitute teacher assignment"""

    model = SubstituteTeacher
    form_class = SubstituteTeacherForm
    template_name = "scheduling/substitute_form.html"
    module_name = "scheduling"
    permission_required = "scheduling.assign_substitute_teacher"

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, "Substitute teacher assigned successfully.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("scheduling:substitute_detail", kwargs={"pk": self.object.pk})


class ApproveSubstituteView(LoginRequiredMixin, ModulePermissionMixin, View):
    """Approve substitute teacher assignment"""

    module_name = "scheduling"
    permission_required = "scheduling.approve_substitutions"

    def post(self, request, pk):
        substitute = get_object_or_404(SubstituteTeacher, pk=pk)
        substitute.approved_by = request.user
        substitute.save()

        messages.success(request, "Substitute assignment approved.")
        return redirect("scheduling:substitute_detail", pk=pk)


# Timetable Generation Views
class TimetableGenerationView(LoginRequiredMixin, ModulePermissionMixin, FormView):
    """Timetable generation interface"""

    form_class = TimetableGenerationForm
    template_name = "scheduling/timetable_generation.html"
    module_name = "scheduling"
    permission_required = "scheduling.generate_timetable"

    def form_valid(self, form):
        # This would typically be handled asynchronously
        generation = form.save(commit=False)
        generation.started_by = self.request.user
        generation.save()

        # Set grades relationship
        grades = form.cleaned_data["grades"]
        generation.grades.set(grades)

        messages.success(
            self.request,
            "Timetable generation started. Check the generation history for progress.",
        )

        return redirect("scheduling:generation_detail", pk=generation.pk)


class GenerationHistoryView(LoginRequiredMixin, ModulePermissionMixin, ListView):
    """List timetable generation history"""

    model = TimetableGeneration
    template_name = "scheduling/generation_history.html"
    context_object_name = "generations"
    module_name = "scheduling"
    paginate_by = 20
    ordering = ["-started_at"]


# Analytics Views
class SchedulingAnalyticsView(LoginRequiredMixin, ModulePermissionMixin, TemplateView):
    """Main scheduling analytics dashboard"""

    template_name = "scheduling/analytics.html"
    module_name = "scheduling"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        term_id = self.request.GET.get("term_id")
        if term_id:
            term = get_object_or_404(Term, id=term_id)
        else:
            term = Term.objects.filter(is_current=True).first()

        if term:
            context["teacher_workload"] = (
                SchedulingAnalyticsService.get_teacher_workload_analytics(term)
            )
            context["room_utilization"] = (
                SchedulingAnalyticsService.get_room_utilization_analytics(term)
            )
            context["conflicts"] = (
                SchedulingAnalyticsService.get_scheduling_conflicts_analytics(term)
            )
            context["optimization_score"] = (
                SchedulingAnalyticsService.get_timetable_optimization_score(term)
            )

        context["term"] = term
        context["available_terms"] = Term.objects.all().order_by("-start_date")

        return context


# AJAX Views
class AvailableTeachersAjaxView(LoginRequiredMixin, ModulePermissionMixin, View):
    """AJAX endpoint for available teachers"""

    module_name = "scheduling"

    def get(self, request):
        time_slot_id = request.GET.get("time_slot_id")
        subject_id = request.GET.get("subject_id")
        date = request.GET.get("date")
        class_id = request.GET.get("class_id")

        if not all([time_slot_id, subject_id, date]):
            return JsonResponse({"error": "Missing required parameters"}, status=400)

        try:
            time_slot = TimeSlot.objects.get(id=time_slot_id)
            subject = Subject.objects.get(id=subject_id)
            date_obj = datetime.strptime(date, "%Y-%m-%d").date()
            class_obj = Class.objects.get(id=class_id) if class_id else None

            teachers = TimetableService.get_available_teachers(
                time_slot, subject, date_obj, class_obj
            )

            teacher_data = [
                {
                    "id": str(teacher.id),
                    "name": teacher.user.get_full_name(),
                    "employee_id": teacher.employee_id,
                }
                for teacher in teachers
            ]

            return JsonResponse({"teachers": teacher_data})

        except Exception as e:
            return JsonResponse({"error": str(e)}, status=400)


class AvailableRoomsAjaxView(LoginRequiredMixin, ModulePermissionMixin, View):
    """AJAX endpoint for available rooms"""

    module_name = "scheduling"

    def get(self, request):
        time_slot_id = request.GET.get("time_slot_id")
        date = request.GET.get("date")
        room_type = request.GET.get("room_type")
        min_capacity = request.GET.get("min_capacity")

        if not all([time_slot_id, date]):
            return JsonResponse({"error": "Missing required parameters"}, status=400)

        try:
            time_slot = TimeSlot.objects.get(id=time_slot_id)
            date_obj = datetime.strptime(date, "%Y-%m-%d").date()
            min_capacity_int = int(min_capacity) if min_capacity else None

            rooms = TimetableService.get_available_rooms(
                time_slot, date_obj, room_type, min_capacity_int
            )

            room_data = [
                {
                    "id": str(room.id),
                    "number": room.number,
                    "name": room.name,
                    "capacity": room.capacity,
                    "room_type": room.room_type,
                }
                for room in rooms
            ]

            return JsonResponse({"rooms": room_data})

        except Exception as e:
            return JsonResponse({"error": str(e)}, status=400)


class CheckConflictsAjaxView(LoginRequiredMixin, ModulePermissionMixin, View):
    """AJAX endpoint for conflict checking"""

    module_name = "scheduling"

    def post(self, request):
        data = json.loads(request.body)

        teacher_id = data.get("teacher_id")
        room_id = data.get("room_id")
        class_id = data.get("class_id")
        time_slot_id = data.get("time_slot_id")
        start_date = data.get("start_date")
        end_date = data.get("end_date")
        exclude_id = data.get("exclude_id")

        try:
            teacher = Teacher.objects.get(id=teacher_id) if teacher_id else None
            room = Room.objects.get(id=room_id) if room_id else None
            class_obj = Class.objects.get(id=class_id) if class_id else None
            time_slot = TimeSlot.objects.get(id=time_slot_id) if time_slot_id else None
            exclude_timetable = (
                Timetable.objects.get(id=exclude_id) if exclude_id else None
            )

            date_range = None
            if start_date and end_date:
                start_date_obj = datetime.strptime(start_date, "%Y-%m-%d").date()
                end_date_obj = datetime.strptime(end_date, "%Y-%m-%d").date()
                date_range = (start_date_obj, end_date_obj)

            conflicts = TimetableService.check_conflicts(
                teacher=teacher,
                room=room,
                class_obj=class_obj,
                time_slot=time_slot,
                date_range=date_range,
                exclude_timetable=exclude_timetable,
            )

            return JsonResponse({"conflicts": conflicts})

        except Exception as e:
            return JsonResponse({"error": str(e)}, status=400)


# Export Views
class ExportClassTimetableView(LoginRequiredMixin, ModulePermissionMixin, View):
    """Export class timetable to CSV"""

    module_name = "scheduling"
    permission_required = "scheduling.export_timetables"

    def get(self, request, class_id):
        class_obj = get_object_or_404(Class, id=class_id)
        term_id = request.GET.get("term_id")

        if term_id:
            term = get_object_or_404(Term, id=term_id)
        else:
            term = Term.objects.filter(is_current=True).first()

        if not term:
            raise Http404("No term available")

        timetable_data = TimetableService.get_class_timetable(class_obj, term)

        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = (
            f'attachment; filename="{class_obj}_timetable_{term}.csv"'
        )

        writer = csv.writer(response)
        writer.writerow(["Day", "Period", "Time", "Subject", "Teacher", "Room"])

        for day, entries in timetable_data.items():
            for entry in entries:
                writer.writerow(
                    [
                        day,
                        entry.time_slot.period_number,
                        f"{entry.time_slot.start_time} - {entry.time_slot.end_time}",
                        entry.subject.name,
                        entry.teacher.user.get_full_name(),
                        entry.room.number if entry.room else "TBD",
                    ]
                )

        return response


# Additional utility views would go here...
class ConflictManagementView(LoginRequiredMixin, ModulePermissionMixin, TemplateView):
    """Conflict management interface"""

    template_name = "scheduling/conflict_management.html"
    module_name = "scheduling"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get current conflicts
        term = Term.objects.filter(is_current=True).first()
        if term:
            context["conflicts"] = (
                SchedulingAnalyticsService.get_scheduling_conflicts_analytics(term)
            )

        return context


class SchedulingSettingsView(LoginRequiredMixin, ModulePermissionMixin, TemplateView):
    """Scheduling module settings"""

    template_name = "scheduling/settings.html"
    module_name = "scheduling"
    permission_required = "scheduling.manage_constraints"


class SchedulingHelpView(LoginRequiredMixin, TemplateView):
    """Scheduling help and documentation"""

    template_name = "scheduling/help.html"
