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

from src.academics.models import Class, Grade, Term
from src.core.mixins import ModulePermissionMixin
from src.subjects.models import Subject
from src.teachers.models import Teacher

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


# Grade Timetable View
class GradeTimetableView(LoginRequiredMixin, ModulePermissionMixin, TemplateView):
    """View timetable for a specific grade"""

    template_name = "scheduling/grade_timetable.html"
    module_name = "scheduling"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        grade = get_object_or_404(Grade, id=kwargs["grade_id"])
        term_id = self.request.GET.get("term_id")

        if term_id:
            term = get_object_or_404(Term, id=term_id)
        else:
            term = Term.objects.filter(is_current=True).first()

        if term:
            # Get all classes in this grade
            classes = Class.objects.filter(
                grade=grade, academic_year=term.academic_year
            )
            timetable_data = {}

            for class_obj in classes:
                timetable_data[class_obj] = TimetableService.get_class_timetable(
                    class_obj, term
                )

        context["grade"] = grade
        context["term"] = term
        context["classes"] = classes
        context["timetable_data"] = timetable_data
        context["available_terms"] = Term.objects.all().order_by("-start_date")

        return context


# Time Slot Detail/Update/Delete Views
class TimeSlotDetailView(LoginRequiredMixin, ModulePermissionMixin, DetailView):
    """Detailed view of a time slot"""

    model = TimeSlot
    template_name = "scheduling/timeslot_detail.html"
    context_object_name = "timeslot"
    module_name = "scheduling"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get timetable entries using this time slot
        context["timetable_entries"] = Timetable.objects.filter(
            time_slot=self.get_object(), is_active=True
        ).select_related("class_assigned", "subject", "teacher", "room")[:20]

        return context


class TimeSlotUpdateView(LoginRequiredMixin, ModulePermissionMixin, UpdateView):
    """Update time slot"""

    model = TimeSlot
    form_class = TimeSlotForm
    template_name = "scheduling/timeslot_form.html"
    module_name = "scheduling"
    permission_required = "scheduling.change_timeslot"
    success_url = reverse_lazy("scheduling:timeslot_list")

    def form_valid(self, form):
        messages.success(self.request, "Time slot updated successfully.")
        return super().form_valid(form)


class TimeSlotDeleteView(LoginRequiredMixin, ModulePermissionMixin, DeleteView):
    """Delete time slot"""

    model = TimeSlot
    template_name = "scheduling/timeslot_confirm_delete.html"
    module_name = "scheduling"
    permission_required = "scheduling.delete_timeslot"
    success_url = reverse_lazy("scheduling:timeslot_list")

    def delete(self, request, *args, **kwargs):
        messages.success(request, "Time slot deleted successfully.")
        return super().delete(request, *args, **kwargs)


class BulkTimeSlotCreateView(LoginRequiredMixin, ModulePermissionMixin, FormView):
    """Bulk create time slots"""

    template_name = "scheduling/bulk_timeslot_create.html"
    module_name = "scheduling"
    permission_required = "scheduling.bulk_create_timeslots"

    def get(self, request, *args, **kwargs):
        # This would render a form for bulk time slot creation
        context = {
            "days_of_week": TimeSlot.DAY_CHOICES,  # Assuming you have day choices
        }
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        # Process bulk creation
        created_count = 0

        try:
            # Example bulk creation logic - adjust based on your form data
            days = request.POST.getlist("days")
            periods = int(request.POST.get("periods", 8))
            start_time = request.POST.get("start_time", "08:00")
            duration = int(request.POST.get("duration", 45))
            break_duration = int(request.POST.get("break_duration", 5))

            # Create time slots for each day
            for day in days:
                for period in range(1, periods + 1):
                    # Calculate start and end times based on period number
                    # This is simplified - you'd want more sophisticated time calculation
                    TimeSlot.objects.create(
                        day_of_week=int(day),
                        period_number=period,
                        start_time=start_time,  # Calculate actual time
                        end_time=start_time,  # Calculate actual time
                        duration_minutes=duration,
                    )
                    created_count += 1

            messages.success(
                request, f"Successfully created {created_count} time slots."
            )

        except Exception as e:
            messages.error(request, f"Error creating time slots: {str(e)}")

        return redirect("scheduling:timeslot_list")


# Room CRUD Views
class RoomCreateView(LoginRequiredMixin, ModulePermissionMixin, CreateView):
    """Create new room"""

    model = Room
    form_class = RoomForm
    template_name = "scheduling/room_form.html"
    module_name = "scheduling"
    permission_required = "scheduling.add_room"
    success_url = reverse_lazy("scheduling:room_list")

    def form_valid(self, form):
        messages.success(self.request, "Room created successfully.")
        return super().form_valid(form)


class RoomDetailView(LoginRequiredMixin, ModulePermissionMixin, DetailView):
    """Detailed view of a room"""

    model = Room
    template_name = "scheduling/room_detail.html"
    context_object_name = "room"
    module_name = "scheduling"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get current bookings
        term = Term.objects.filter(is_current=True).first()
        if term:
            context["current_bookings"] = Timetable.objects.filter(
                room=self.get_object(), term=term, is_active=True
            ).select_related("class_assigned", "subject", "teacher", "time_slot")

        return context


class RoomUpdateView(LoginRequiredMixin, ModulePermissionMixin, UpdateView):
    """Update room"""

    model = Room
    form_class = RoomForm
    template_name = "scheduling/room_form.html"
    module_name = "scheduling"
    permission_required = "scheduling.change_room"

    def form_valid(self, form):
        messages.success(self.request, "Room updated successfully.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("scheduling:room_detail", kwargs={"pk": self.object.pk})


class RoomDeleteView(LoginRequiredMixin, ModulePermissionMixin, DeleteView):
    """Delete room"""

    model = Room
    template_name = "scheduling/room_confirm_delete.html"
    module_name = "scheduling"
    permission_required = "scheduling.delete_room"
    success_url = reverse_lazy("scheduling:room_list")

    def delete(self, request, *args, **kwargs):
        messages.success(request, "Room deleted successfully.")
        return super().delete(request, *args, **kwargs)


class RoomCalendarView(LoginRequiredMixin, ModulePermissionMixin, DetailView):
    """Room calendar view"""

    model = Room
    template_name = "scheduling/room_calendar.html"
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
            calendar_data = RoomService.get_room_booking_calendar(room, term)
            context["calendar_data"] = calendar_data

        context["term"] = term
        context["available_terms"] = Term.objects.all().order_by("-start_date")

        return context


# Substitute Teacher Views
class SubstituteTeacherDetailView(
    LoginRequiredMixin, ModulePermissionMixin, DetailView
):
    """Detailed view of substitute teacher assignment"""

    model = SubstituteTeacher
    template_name = "scheduling/substitute_detail.html"
    context_object_name = "substitute"
    module_name = "scheduling"


class SubstituteTeacherUpdateView(
    LoginRequiredMixin, ModulePermissionMixin, UpdateView
):
    """Update substitute teacher assignment"""

    model = SubstituteTeacher
    form_class = SubstituteTeacherForm
    template_name = "scheduling/substitute_form.html"
    module_name = "scheduling"
    permission_required = "scheduling.change_substitute"

    def form_valid(self, form):
        messages.success(self.request, "Substitute assignment updated successfully.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("scheduling:substitute_detail", kwargs={"pk": self.object.pk})


class SubstituteTeacherDeleteView(
    LoginRequiredMixin, ModulePermissionMixin, DeleteView
):
    """Delete substitute teacher assignment"""

    model = SubstituteTeacher
    template_name = "scheduling/substitute_confirm_delete.html"
    module_name = "scheduling"
    permission_required = "scheduling.delete_substitute"
    success_url = reverse_lazy("scheduling:substitute_list")

    def delete(self, request, *args, **kwargs):
        messages.success(request, "Substitute assignment deleted successfully.")
        return super().delete(request, *args, **kwargs)


class SubstituteSuggestionsView(LoginRequiredMixin, ModulePermissionMixin, View):
    """Get substitute teacher suggestions"""

    module_name = "scheduling"

    def get(self, request):
        timetable_id = request.GET.get("timetable_id")
        date = request.GET.get("date")

        if not timetable_id or not date:
            return JsonResponse({"error": "Missing required parameters"}, status=400)

        try:
            timetable = Timetable.objects.get(id=timetable_id)
            date_obj = datetime.strptime(date, "%Y-%m-%d").date()

            suggestions = SubstituteService.get_substitute_suggestions(
                timetable, date_obj
            )

            suggestion_data = [
                {
                    "id": str(teacher.id),
                    "name": teacher.user.get_full_name(),
                    "employee_id": teacher.employee_id,
                    "qualification": teacher.qualification,
                    "score": suggestion.get("score", 0),  # If you have scoring logic
                }
                for teacher in suggestions
            ]

            return JsonResponse({"suggestions": suggestion_data})

        except Exception as e:
            return JsonResponse({"error": str(e)}, status=400)


# Generation Detail View
class GenerationDetailView(LoginRequiredMixin, ModulePermissionMixin, DetailView):
    """Detailed view of timetable generation"""

    model = TimetableGeneration
    template_name = "scheduling/generation_detail.html"
    context_object_name = "generation"
    module_name = "scheduling"


# Optimization View
class OptimizationView(LoginRequiredMixin, ModulePermissionMixin, TemplateView):
    """Timetable optimization interface"""

    template_name = "scheduling/optimization.html"
    module_name = "scheduling"
    permission_required = "scheduling.optimize_timetable"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        term = Term.objects.filter(is_current=True).first()
        if term:
            context["optimization_score"] = (
                OptimizationService.calculate_optimization_score(term)
            )
            context["optimization_suggestions"] = (
                OptimizationService.get_optimization_suggestions(term)
            )

        context["term"] = term
        return context

    def post(self, request, *args, **kwargs):
        """Run optimization"""
        term_id = request.POST.get("term_id")

        if term_id:
            term = get_object_or_404(Term, id=term_id)
            # Run optimization logic
            result = OptimizationService.optimize_timetable(term)

            if result.get("success"):
                messages.success(
                    request,
                    f"Optimization completed. Score improved by {result.get('improvement', 0)}%",
                )
            else:
                messages.error(request, "Optimization failed. Please try again.")

        return redirect("scheduling:optimization")


# Template Views
class TimetableTemplateListView(LoginRequiredMixin, ModulePermissionMixin, ListView):
    """List timetable templates"""

    model = TimetableTemplate
    template_name = "scheduling/template_list.html"
    context_object_name = "templates"
    module_name = "scheduling"
    paginate_by = 20
    ordering = ["-created_at"]


class TimetableTemplateCreateView(
    LoginRequiredMixin, ModulePermissionMixin, CreateView
):
    """Create timetable template"""

    model = TimetableTemplate
    form_class = TimetableTemplateForm
    template_name = "scheduling/template_form.html"
    module_name = "scheduling"
    permission_required = "scheduling.add_template"

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, "Template created successfully.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("scheduling:template_detail", kwargs={"pk": self.object.pk})


class TimetableTemplateDetailView(
    LoginRequiredMixin, ModulePermissionMixin, DetailView
):
    """Detailed view of timetable template"""

    model = TimetableTemplate
    template_name = "scheduling/template_detail.html"
    context_object_name = "template"
    module_name = "scheduling"


class TimetableTemplateUpdateView(
    LoginRequiredMixin, ModulePermissionMixin, UpdateView
):
    """Update timetable template"""

    model = TimetableTemplate
    form_class = TimetableTemplateForm
    template_name = "scheduling/template_form.html"
    module_name = "scheduling"
    permission_required = "scheduling.change_template"

    def form_valid(self, form):
        messages.success(self.request, "Template updated successfully.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("scheduling:template_detail", kwargs={"pk": self.object.pk})


class TimetableTemplateDeleteView(
    LoginRequiredMixin, ModulePermissionMixin, DeleteView
):
    """Delete timetable template"""

    model = TimetableTemplate
    template_name = "scheduling/template_confirm_delete.html"
    module_name = "scheduling"
    permission_required = "scheduling.delete_template"
    success_url = reverse_lazy("scheduling:template_list")

    def delete(self, request, *args, **kwargs):
        messages.success(request, "Template deleted successfully.")
        return super().delete(request, *args, **kwargs)


class ApplyTemplateView(LoginRequiredMixin, ModulePermissionMixin, View):
    """Apply timetable template"""

    module_name = "scheduling"
    permission_required = "scheduling.apply_template"

    def post(self, request, pk):
        template = get_object_or_404(TimetableTemplate, pk=pk)
        term_id = request.POST.get("term_id")

        if not term_id:
            messages.error(request, "Please select a term.")
            return redirect("scheduling:template_detail", pk=pk)

        term = get_object_or_404(Term, id=term_id)

        try:
            # Apply template logic would go here
            result = TimetableService.apply_template(template, term, request.user)

            if result.get("success"):
                messages.success(
                    request,
                    f"Template applied successfully. Created {result.get('created', 0)} timetable entries.",
                )
            else:
                messages.error(
                    request,
                    f"Failed to apply template: {result.get('error', 'Unknown error')}",
                )

        except Exception as e:
            messages.error(request, f"Error applying template: {str(e)}")

        return redirect("scheduling:template_detail", pk=pk)


# Constraint Views
class SchedulingConstraintListView(LoginRequiredMixin, ModulePermissionMixin, ListView):
    """List scheduling constraints"""

    model = SchedulingConstraint
    template_name = "scheduling/constraint_list.html"
    context_object_name = "constraints"
    module_name = "scheduling"
    paginate_by = 20
    ordering = ["-created_at"]


class SchedulingConstraintCreateView(
    LoginRequiredMixin, ModulePermissionMixin, CreateView
):
    """Create scheduling constraint"""

    model = SchedulingConstraint
    form_class = SchedulingConstraintForm
    template_name = "scheduling/constraint_form.html"
    module_name = "scheduling"
    permission_required = "scheduling.add_constraint"

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, "Constraint created successfully.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("scheduling:constraint_detail", kwargs={"pk": self.object.pk})


class SchedulingConstraintDetailView(
    LoginRequiredMixin, ModulePermissionMixin, DetailView
):
    """Detailed view of scheduling constraint"""

    model = SchedulingConstraint
    template_name = "scheduling/constraint_detail.html"
    context_object_name = "constraint"
    module_name = "scheduling"


class SchedulingConstraintUpdateView(
    LoginRequiredMixin, ModulePermissionMixin, UpdateView
):
    """Update scheduling constraint"""

    model = SchedulingConstraint
    form_class = SchedulingConstraintForm
    template_name = "scheduling/constraint_form.html"
    module_name = "scheduling"
    permission_required = "scheduling.change_constraint"

    def form_valid(self, form):
        messages.success(self.request, "Constraint updated successfully.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("scheduling:constraint_detail", kwargs={"pk": self.object.pk})


class SchedulingConstraintDeleteView(
    LoginRequiredMixin, ModulePermissionMixin, DeleteView
):
    """Delete scheduling constraint"""

    model = SchedulingConstraint
    template_name = "scheduling/constraint_confirm_delete.html"
    module_name = "scheduling"
    permission_required = "scheduling.delete_constraint"
    success_url = reverse_lazy("scheduling:constraint_list")

    def delete(self, request, *args, **kwargs):
        messages.success(request, "Constraint deleted successfully.")
        return super().delete(request, *args, **kwargs)


# Analytics Views
class TeacherWorkloadAnalyticsView(
    LoginRequiredMixin, ModulePermissionMixin, TemplateView
):
    """Teacher workload analytics"""

    template_name = "scheduling/teacher_workload_analytics.html"
    module_name = "scheduling"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        term_id = self.request.GET.get("term_id")
        if term_id:
            term = get_object_or_404(Term, id=term_id)
        else:
            term = Term.objects.filter(is_current=True).first()

        if term:
            context["workload_data"] = (
                SchedulingAnalyticsService.get_teacher_workload_analytics(term)
            )

        context["term"] = term
        context["available_terms"] = Term.objects.all().order_by("-start_date")
        return context


class RoomUtilizationAnalyticsView(
    LoginRequiredMixin, ModulePermissionMixin, TemplateView
):
    """Room utilization analytics"""

    template_name = "scheduling/room_utilization_analytics.html"
    module_name = "scheduling"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        term_id = self.request.GET.get("term_id")
        if term_id:
            term = get_object_or_404(Term, id=term_id)
        else:
            term = Term.objects.filter(is_current=True).first()

        if term:
            context["utilization_data"] = (
                SchedulingAnalyticsService.get_room_utilization_analytics(term)
            )

        context["term"] = term
        context["available_terms"] = Term.objects.all().order_by("-start_date")
        return context


class ConflictAnalyticsView(LoginRequiredMixin, ModulePermissionMixin, TemplateView):
    """Conflict analytics"""

    template_name = "scheduling/conflict_analytics.html"
    module_name = "scheduling"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        term_id = self.request.GET.get("term_id")
        if term_id:
            term = get_object_or_404(Term, id=term_id)
        else:
            term = Term.objects.filter(is_current=True).first()

        if term:
            context["conflict_data"] = (
                SchedulingAnalyticsService.get_scheduling_conflicts_analytics(term)
            )

        context["term"] = term
        context["available_terms"] = Term.objects.all().order_by("-start_date")
        return context


class OptimizationScoreView(LoginRequiredMixin, ModulePermissionMixin, TemplateView):
    """Optimization score analytics"""

    template_name = "scheduling/optimization_score.html"
    module_name = "scheduling"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        term_id = self.request.GET.get("term_id")
        if term_id:
            term = get_object_or_404(Term, id=term_id)
        else:
            term = Term.objects.filter(is_current=True).first()

        if term:
            context["optimization_score"] = (
                SchedulingAnalyticsService.get_timetable_optimization_score(term)
            )
            context["score_breakdown"] = OptimizationService.get_score_breakdown(term)

        context["term"] = term
        context["available_terms"] = Term.objects.all().order_by("-start_date")
        return context


class SubjectDistributionView(LoginRequiredMixin, ModulePermissionMixin, TemplateView):
    """Subject distribution analytics"""

    template_name = "scheduling/subject_distribution.html"
    module_name = "scheduling"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        term_id = self.request.GET.get("term_id")
        if term_id:
            term = get_object_or_404(Term, id=term_id)
        else:
            term = Term.objects.filter(is_current=True).first()

        if term:
            context["distribution_data"] = (
                SchedulingAnalyticsService.get_subject_distribution_analytics(term)
            )

        context["term"] = term
        context["available_terms"] = Term.objects.all().order_by("-start_date")
        return context


# Report Views
class SchedulingReportsView(LoginRequiredMixin, ModulePermissionMixin, TemplateView):
    """Main scheduling reports page"""

    template_name = "scheduling/reports.html"
    module_name = "scheduling"


class TimetableReportView(LoginRequiredMixin, ModulePermissionMixin, TemplateView):
    """Timetable reports"""

    template_name = "scheduling/timetable_report.html"
    module_name = "scheduling"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        term_id = self.request.GET.get("term_id")
        class_id = self.request.GET.get("class_id")

        if term_id:
            term = get_object_or_404(Term, id=term_id)
        else:
            term = Term.objects.filter(is_current=True).first()

        if class_id and term:
            class_obj = get_object_or_404(Class, id=class_id)
            context["timetable_data"] = TimetableService.get_class_timetable(
                class_obj, term
            )
            context["class_obj"] = class_obj

        context["term"] = term
        context["available_terms"] = Term.objects.all().order_by("-start_date")
        context["available_classes"] = Class.objects.all() if term else []

        return context


class TeacherScheduleReportView(
    LoginRequiredMixin, ModulePermissionMixin, TemplateView
):
    """Teacher schedule reports"""

    template_name = "scheduling/teacher_schedule_report.html"
    module_name = "scheduling"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        term_id = self.request.GET.get("term_id")
        teacher_id = self.request.GET.get("teacher_id")

        if term_id:
            term = get_object_or_404(Term, id=term_id)
        else:
            term = Term.objects.filter(is_current=True).first()

        if teacher_id and term:
            teacher = get_object_or_404(Teacher, id=teacher_id)
            context["schedule_data"] = TimetableService.get_teacher_timetable(
                teacher, term
            )
            context["workload_data"] = TimetableService.get_teacher_workload(
                teacher, term
            )
            context["teacher"] = teacher

        context["term"] = term
        context["available_terms"] = Term.objects.all().order_by("-start_date")
        context["available_teachers"] = Teacher.objects.filter(status="active")

        return context


class RoomUsageReportView(LoginRequiredMixin, ModulePermissionMixin, TemplateView):
    """Room usage reports"""

    template_name = "scheduling/room_usage_report.html"
    module_name = "scheduling"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        term_id = self.request.GET.get("term_id")

        if term_id:
            term = get_object_or_404(Term, id=term_id)
        else:
            term = Term.objects.filter(is_current=True).first()

        if term:
            context["usage_data"] = (
                SchedulingAnalyticsService.get_room_utilization_analytics(term)
            )

        context["term"] = term
        context["available_terms"] = Term.objects.all().order_by("-start_date")

        return context


class ConflictReportView(LoginRequiredMixin, ModulePermissionMixin, TemplateView):
    """Conflict reports"""

    template_name = "scheduling/conflict_report.html"
    module_name = "scheduling"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        term_id = self.request.GET.get("term_id")

        if term_id:
            term = get_object_or_404(Term, id=term_id)
        else:
            term = Term.objects.filter(is_current=True).first()

        if term:
            context["conflict_data"] = (
                SchedulingAnalyticsService.get_scheduling_conflicts_analytics(term)
            )

        context["term"] = term
        context["available_terms"] = Term.objects.all().order_by("-start_date")

        return context


# Export Views
class ExportTeacherScheduleView(LoginRequiredMixin, ModulePermissionMixin, View):
    """Export teacher schedule to CSV"""

    module_name = "scheduling"
    permission_required = "scheduling.export_timetables"

    def get(self, request, teacher_id):
        teacher = get_object_or_404(Teacher, id=teacher_id)
        term_id = request.GET.get("term_id")

        if term_id:
            term = get_object_or_404(Term, id=term_id)
        else:
            term = Term.objects.filter(is_current=True).first()

        if not term:
            raise Http404("No term available")

        schedule_data = TimetableService.get_teacher_timetable(teacher, term)

        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = (
            f'attachment; filename="{teacher.user.get_full_name()}_schedule_{term}.csv"'
        )

        writer = csv.writer(response)
        writer.writerow(["Day", "Period", "Time", "Class", "Subject", "Room"])

        for day, entries in schedule_data.items():
            for entry in entries:
                writer.writerow(
                    [
                        day,
                        entry.time_slot.period_number,
                        f"{entry.time_slot.start_time} - {entry.time_slot.end_time}",
                        str(entry.class_assigned),
                        entry.subject.name,
                        entry.room.number if entry.room else "TBD",
                    ]
                )

        return response


class ExportRoomUtilizationView(LoginRequiredMixin, ModulePermissionMixin, View):
    """Export room utilization to CSV"""

    module_name = "scheduling"
    permission_required = "scheduling.export_timetables"

    def get(self, request):
        term_id = request.GET.get("term_id")

        if term_id:
            term = get_object_or_404(Term, id=term_id)
        else:
            term = Term.objects.filter(is_current=True).first()

        if not term:
            raise Http404("No term available")

        utilization_data = SchedulingAnalyticsService.get_room_utilization_analytics(
            term
        )

        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = (
            f'attachment; filename="room_utilization_{term}.csv"'
        )

        writer = csv.writer(response)
        writer.writerow(
            [
                "Room",
                "Building",
                "Capacity",
                "Total Hours",
                "Used Hours",
                "Utilization %",
            ]
        )

        for room_data in utilization_data.get("rooms", []):
            writer.writerow(
                [
                    room_data.get("room_number", ""),
                    room_data.get("building", ""),
                    room_data.get("capacity", ""),
                    room_data.get("total_hours", ""),
                    room_data.get("used_hours", ""),
                    room_data.get("utilization_percentage", ""),
                ]
            )

        return response


class ExportMasterTimetableView(LoginRequiredMixin, ModulePermissionMixin, View):
    """Export master timetable to CSV"""

    module_name = "scheduling"
    permission_required = "scheduling.export_timetables"

    def get(self, request):
        term_id = request.GET.get("term_id")

        if term_id:
            term = get_object_or_404(Term, id=term_id)
        else:
            term = Term.objects.filter(is_current=True).first()

        if not term:
            raise Http404("No term available")

        timetables = (
            Timetable.objects.filter(term=term, is_active=True)
            .select_related("class_assigned", "subject", "teacher", "time_slot", "room")
            .order_by(
                "time_slot__day_of_week",
                "time_slot__period_number",
                "class_assigned__grade__name",
            )
        )

        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = (
            f'attachment; filename="master_timetable_{term}.csv"'
        )

        writer = csv.writer(response)
        writer.writerow(
            [
                "Day",
                "Period",
                "Time",
                "Class",
                "Subject",
                "Teacher",
                "Room",
                "Start Date",
                "End Date",
            ]
        )

        for timetable in timetables:
            writer.writerow(
                [
                    timetable.time_slot.get_day_of_week_display(),
                    timetable.time_slot.period_number,
                    f"{timetable.time_slot.start_time} - {timetable.time_slot.end_time}",
                    str(timetable.class_assigned),
                    timetable.subject.name,
                    timetable.teacher.user.get_full_name(),
                    timetable.room.number if timetable.room else "TBD",
                    timetable.effective_from_date,
                    timetable.effective_to_date,
                ]
            )

        return response


# Additional AJAX Views
class TeacherSubjectsAjaxView(LoginRequiredMixin, ModulePermissionMixin, View):
    """AJAX endpoint for teacher subjects"""

    module_name = "scheduling"

    def get(self, request):
        teacher_id = request.GET.get("teacher_id")

        if not teacher_id:
            return JsonResponse({"error": "Missing teacher_id parameter"}, status=400)

        try:
            teacher = Teacher.objects.get(id=teacher_id)

            # Get subjects this teacher can teach
            # This assumes you have a relationship between teachers and subjects
            # You might need to adjust based on your actual model structure
            subjects = Subject.objects.filter(
                # Add your filter logic here
                # For example: teacherassignment__teacher=teacher
            ).distinct()

            subject_data = [
                {"id": str(subject.id), "name": subject.name, "code": subject.code}
                for subject in subjects
            ]

            return JsonResponse({"subjects": subject_data})

        except Teacher.DoesNotExist:
            return JsonResponse({"error": "Teacher not found"}, status=404)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=400)


class ClassStudentsAjaxView(LoginRequiredMixin, ModulePermissionMixin, View):
    """AJAX endpoint for class students"""

    module_name = "scheduling"

    def get(self, request):
        class_id = request.GET.get("class_id")

        if not class_id:
            return JsonResponse({"error": "Missing class_id parameter"}, status=400)

        try:
            class_obj = Class.objects.get(id=class_id)

            # Get students in this class
            students = (
                class_obj.students.all()
            )  # Adjust based on your model relationship

            student_data = [
                {
                    "id": str(student.id),
                    "name": student.user.get_full_name(),
                    "admission_number": student.admission_number,
                }
                for student in students
            ]

            return JsonResponse(
                {"students": student_data, "total_count": len(student_data)}
            )

        except Class.DoesNotExist:
            return JsonResponse({"error": "Class not found"}, status=404)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=400)
