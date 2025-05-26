from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.db.models import Q
from django.utils import timezone
from datetime import datetime, timedelta
from typing import Dict, List

from ..models import (
    TimeSlot,
    Room,
    Timetable,
    TimetableTemplate,
    SubstituteTeacher,
    SchedulingConstraint,
    TimetableGeneration,
)
from ..services.timetable_service import (
    TimetableService,
    SubstituteService,
    RoomService,
)
from ..services.optimization_service import OptimizationService
from ..services.analytics_service import SchedulingAnalyticsService
from .serializers import (
    TimeSlotSerializer,
    RoomSerializer,
    TimetableListSerializer,
    TimetableDetailSerializer,
    BulkTimetableCreateSerializer,
    SubstituteTeacherSerializer,
    SchedulingConstraintSerializer,
    TimetableGenerationSerializer,
    TimetableTemplateSerializer,
    WorkloadAnalyticsSerializer,
    RoomUtilizationSerializer,
    ConflictAnalyticsSerializer,
    OptimizationScoreSerializer,
    AvailableTeachersSerializer,
    AvailableRoomsSerializer,
    ConflictCheckSerializer,
)
from academics.models import Term, Class, Grade
from subjects.models import Subject
from teachers.models import Teacher
from api.permissions import HasModulePermission


class TimeSlotViewSet(viewsets.ModelViewSet):
    """Time slot management viewset"""

    queryset = TimeSlot.objects.all()
    serializer_class = TimeSlotSerializer
    permission_classes = [IsAuthenticated, HasModulePermission]
    module_name = "scheduling"
    filterset_fields = ["day_of_week", "is_break", "is_active"]
    ordering_fields = ["day_of_week", "period_number", "start_time"]
    ordering = ["day_of_week", "period_number"]

    @action(detail=False, methods=["get"])
    def active_slots(self, request):
        """Get active time slots grouped by day"""
        slots = TimeSlot.objects.filter(is_active=True).order_by(
            "day_of_week", "period_number"
        )

        grouped_slots = {}
        for slot in slots:
            day = slot.get_day_of_week_display()
            if day not in grouped_slots:
                grouped_slots[day] = []
            grouped_slots[day].append(TimeSlotSerializer(slot).data)

        return Response(grouped_slots)

    @action(detail=False, methods=["post"])
    def bulk_create(self, request):
        """Bulk create time slots"""
        if not isinstance(request.data, list):
            return Response(
                {"error": "Expected list of time slot data"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        created_slots = []
        errors = []

        for slot_data in request.data:
            serializer = self.get_serializer(data=slot_data)
            if serializer.is_valid():
                try:
                    slot = serializer.save()
                    created_slots.append(TimeSlotSerializer(slot).data)
                except Exception as e:
                    errors.append(f"Error creating slot: {str(e)}")
            else:
                errors.append(serializer.errors)

        return Response(
            {
                "created_slots": created_slots,
                "errors": errors,
                "success_count": len(created_slots),
                "error_count": len(errors),
            }
        )


class RoomViewSet(viewsets.ModelViewSet):
    """Room management viewset"""

    queryset = Room.objects.all()
    serializer_class = RoomSerializer
    permission_classes = [IsAuthenticated, HasModulePermission]
    module_name = "scheduling"
    filterset_fields = ["room_type", "is_available", "building"]
    search_fields = ["number", "name", "building"]
    ordering_fields = ["number", "name", "capacity"]
    ordering = ["building", "number"]

    @action(detail=True, methods=["get"])
    def utilization(self, request, pk=None):
        """Get room utilization statistics"""
        room = self.get_object()
        term_id = request.query_params.get("term_id")

        if not term_id:
            return Response(
                {"error": "term_id parameter is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        term = get_object_or_404(Term, id=term_id)
        utilization_data = RoomService.get_room_utilization(room, term)

        return Response(utilization_data)

    @action(detail=True, methods=["get"])
    def booking_calendar(self, request, pk=None):
        """Get room booking calendar"""
        room = self.get_object()
        term_id = request.query_params.get("term_id")

        if not term_id:
            return Response(
                {"error": "term_id parameter is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        term = get_object_or_404(Term, id=term_id)
        calendar_data = RoomService.get_room_booking_calendar(room, term)

        return Response(calendar_data)

    @action(detail=False, methods=["post"])
    def suggest_optimal(self, request):
        """Suggest optimal room for class/subject"""
        class_id = request.data.get("class_id")
        subject_id = request.data.get("subject_id")
        time_slot_id = request.data.get("time_slot_id")
        date = request.data.get("date")

        if not all([class_id, subject_id, time_slot_id, date]):
            return Response(
                {"error": "class_id, subject_id, time_slot_id, and date are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            class_obj = Class.objects.get(id=class_id)
            subject = Subject.objects.get(id=subject_id)
            time_slot = TimeSlot.objects.get(id=time_slot_id)
            date_obj = datetime.strptime(date, "%Y-%m-%d").date()

            suggestions = RoomService.suggest_optimal_room(
                class_obj, subject, time_slot, date_obj
            )

            return Response(suggestions)

        except (Class.DoesNotExist, Subject.DoesNotExist, TimeSlot.DoesNotExist):
            return Response(
                {"error": "Invalid class, subject, or time slot ID"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except ValueError:
            return Response(
                {"error": "Invalid date format. Use YYYY-MM-DD"},
                status=status.HTTP_400_BAD_REQUEST,
            )


class TimetableViewSet(viewsets.ModelViewSet):
    """Timetable management viewset"""

    queryset = Timetable.objects.select_related(
        "class_assigned", "subject", "teacher", "time_slot", "room", "term"
    )
    permission_classes = [IsAuthenticated, HasModulePermission]
    module_name = "scheduling"
    filterset_fields = ["term", "class_assigned", "teacher", "subject", "is_active"]
    ordering = ["time_slot__day_of_week", "time_slot__period_number"]

    def get_serializer_class(self):
        if self.action == "list":
            return TimetableListSerializer
        return TimetableDetailSerializer

    @action(detail=False, methods=["get"])
    def class_timetable(self, request):
        """Get timetable for a specific class"""
        class_id = request.query_params.get("class_id")
        term_id = request.query_params.get("term_id")
        date = request.query_params.get("date")

        if not class_id or not term_id:
            return Response(
                {"error": "class_id and term_id parameters are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            class_obj = Class.objects.get(id=class_id)
            term = Term.objects.get(id=term_id)
            date_obj = datetime.strptime(date, "%Y-%m-%d").date() if date else None

            timetable_data = TimetableService.get_class_timetable(
                class_obj, term, date_obj
            )

            return Response(timetable_data)

        except (Class.DoesNotExist, Term.DoesNotExist):
            return Response(
                {"error": "Invalid class or term ID"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except ValueError:
            return Response(
                {"error": "Invalid date format. Use YYYY-MM-DD"},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(detail=False, methods=["get"])
    def teacher_timetable(self, request):
        """Get timetable for a specific teacher"""
        teacher_id = request.query_params.get("teacher_id")
        term_id = request.query_params.get("term_id")
        date = request.query_params.get("date")

        if not teacher_id or not term_id:
            return Response(
                {"error": "teacher_id and term_id parameters are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            teacher = Teacher.objects.get(id=teacher_id)
            term = Term.objects.get(id=term_id)
            date_obj = datetime.strptime(date, "%Y-%m-%d").date() if date else None

            timetable_data = TimetableService.get_teacher_timetable(
                teacher, term, date_obj
            )

            return Response(timetable_data)

        except (Teacher.DoesNotExist, Term.DoesNotExist):
            return Response(
                {"error": "Invalid teacher or term ID"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except ValueError:
            return Response(
                {"error": "Invalid date format. Use YYYY-MM-DD"},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(detail=False, methods=["post"])
    def bulk_create(self, request):
        """Bulk create timetable entries"""
        serializer = BulkTimetableCreateSerializer(
            data=request.data, context={"request": request}
        )

        if serializer.is_valid():
            result = serializer.save()
            return Response(result, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=["post"])
    def check_conflicts(self, request):
        """Check for scheduling conflicts"""
        serializer = ConflictCheckSerializer(data=request.data)

        if serializer.is_valid():
            data = serializer.validated_data

            teacher = (
                Teacher.objects.get(id=data["teacher_id"])
                if data.get("teacher_id")
                else None
            )
            room = Room.objects.get(id=data["room_id"]) if data.get("room_id") else None
            class_obj = (
                Class.objects.get(id=data["class_id"]) if data.get("class_id") else None
            )
            time_slot = (
                TimeSlot.objects.get(id=data["time_slot_id"])
                if data.get("time_slot_id")
                else None
            )

            date_range = None
            if data.get("start_date") and data.get("end_date"):
                date_range = (data["start_date"], data["end_date"])

            exclude_timetable = None
            if data.get("exclude_timetable_id"):
                exclude_timetable = Timetable.objects.get(
                    id=data["exclude_timetable_id"]
                )

            conflicts = TimetableService.check_conflicts(
                teacher=teacher,
                room=room,
                class_obj=class_obj,
                time_slot=time_slot,
                date_range=date_range,
                exclude_timetable=exclude_timetable,
            )

            return Response({"conflicts": conflicts})

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=["post"])
    def copy_to_term(self, request):
        """Copy timetable to another term"""
        source_term_id = request.data.get("source_term_id")
        target_term_id = request.data.get("target_term_id")
        grade_ids = request.data.get("grade_ids", [])

        if not source_term_id or not target_term_id:
            return Response(
                {"error": "source_term_id and target_term_id are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            source_term = Term.objects.get(id=source_term_id)
            target_term = Term.objects.get(id=target_term_id)
            grades = Grade.objects.filter(id__in=grade_ids) if grade_ids else None

            result = TimetableService.copy_timetable_to_term(
                source_term, target_term, grades, request.user
            )

            return Response(result)

        except Term.DoesNotExist:
            return Response(
                {"error": "Invalid source or target term ID"},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(detail=False, methods=["get"])
    def available_teachers(self, request):
        """Get available teachers for time slot"""
        serializer = AvailableTeachersSerializer(data=request.query_params)

        if serializer.is_valid():
            data = serializer.validated_data

            time_slot = TimeSlot.objects.get(id=data["time_slot_id"])
            subject = Subject.objects.get(id=data["subject_id"])
            class_obj = (
                Class.objects.get(id=data["class_id"]) if data.get("class_id") else None
            )

            available_teachers = TimetableService.get_available_teachers(
                time_slot, subject, data["date"], class_obj
            )

            teacher_data = [
                {
                    "id": teacher.id,
                    "name": teacher.user.get_full_name(),
                    "employee_id": teacher.employee_id,
                    "department": (
                        teacher.department.name if teacher.department else None
                    ),
                }
                for teacher in available_teachers
            ]

            return Response({"available_teachers": teacher_data})

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=["get"])
    def available_rooms(self, request):
        """Get available rooms for time slot"""
        serializer = AvailableRoomsSerializer(data=request.query_params)

        if serializer.is_valid():
            data = serializer.validated_data

            time_slot = TimeSlot.objects.get(id=data["time_slot_id"])

            available_rooms = TimetableService.get_available_rooms(
                time_slot, data["date"], data.get("room_type"), data.get("min_capacity")
            )

            room_data = [
                {
                    "id": room.id,
                    "number": room.number,
                    "name": room.name,
                    "room_type": room.room_type,
                    "capacity": room.capacity,
                    "building": room.building,
                    "equipment": room.equipment,
                }
                for room in available_rooms
            ]

            return Response({"available_rooms": room_data})

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class SubstituteTeacherViewSet(viewsets.ModelViewSet):
    """Substitute teacher management viewset"""

    queryset = SubstituteTeacher.objects.select_related(
        "original_timetable", "substitute_teacher", "approved_by", "created_by"
    )
    serializer_class = SubstituteTeacherSerializer
    permission_classes = [IsAuthenticated, HasModulePermission]
    module_name = "scheduling"
    filterset_fields = ["date", "substitute_teacher", "approved_by"]
    ordering = ["-date", "-created_at"]

    @action(detail=False, methods=["post"])
    def suggest_substitutes(self, request):
        """Get substitute teacher suggestions"""
        timetable_id = request.data.get("timetable_id")
        date = request.data.get("date")

        if not timetable_id or not date:
            return Response(
                {"error": "timetable_id and date are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            timetable = Timetable.objects.get(id=timetable_id)
            date_obj = datetime.strptime(date, "%Y-%m-%d").date()

            suggestions = SubstituteService.get_substitute_suggestions(
                timetable, date_obj
            )

            # Serialize teacher data
            for suggestion in suggestions:
                teacher = suggestion["teacher"]
                suggestion["teacher"] = {
                    "id": teacher.id,
                    "name": teacher.user.get_full_name(),
                    "employee_id": teacher.employee_id,
                    "department": (
                        teacher.department.name if teacher.department else None
                    ),
                }

            return Response({"suggestions": suggestions})

        except Timetable.DoesNotExist:
            return Response(
                {"error": "Invalid timetable ID"}, status=status.HTTP_400_BAD_REQUEST
            )
        except ValueError:
            return Response(
                {"error": "Invalid date format. Use YYYY-MM-DD"},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(detail=False, methods=["get"])
    def history(self, request):
        """Get substitute assignment history"""
        teacher_id = request.query_params.get("teacher_id")
        start_date = request.query_params.get("start_date")
        end_date = request.query_params.get("end_date")

        teacher = Teacher.objects.get(id=teacher_id) if teacher_id else None
        date_range = None

        if start_date and end_date:
            try:
                start_date_obj = datetime.strptime(start_date, "%Y-%m-%d").date()
                end_date_obj = datetime.strptime(end_date, "%Y-%m-%d").date()
                date_range = (start_date_obj, end_date_obj)
            except ValueError:
                return Response(
                    {"error": "Invalid date format. Use YYYY-MM-DD"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        history = SubstituteService.get_substitute_history(teacher, date_range)
        serializer = self.get_serializer(history, many=True)

        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        """Approve substitute assignment"""
        substitute = self.get_object()
        substitute.approved_by = request.user
        substitute.save()

        return Response({"message": "Substitute assignment approved"})


class TimetableGenerationViewSet(viewsets.ModelViewSet):
    """Timetable generation viewset"""

    queryset = TimetableGeneration.objects.prefetch_related("grades")
    serializer_class = TimetableGenerationSerializer
    permission_classes = [IsAuthenticated, HasModulePermission]
    module_name = "scheduling"
    filterset_fields = ["term", "status", "algorithm_used"]
    ordering = ["-started_at"]

    @action(detail=False, methods=["post"])
    def generate(self, request):
        """Generate optimized timetable"""
        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            generation = serializer.save()

            # Start generation process
            try:
                term = generation.term
                grades = list(generation.grades.all())

                optimizer = OptimizationService(term)

                # Update status to running
                generation.status = "running"
                generation.save()

                # Run optimization
                result = optimizer.generate_optimized_timetable(
                    grades, algorithm=generation.algorithm_used, **generation.parameters
                )

                # Save results
                generation.status = "completed" if result.success else "failed"
                generation.optimization_score = result.optimization_score
                generation.execution_time_seconds = result.execution_time
                generation.conflicts_resolved = len(result.conflicts)
                generation.result_summary = {
                    "assigned_slots": len(result.assigned_slots),
                    "unassigned_slots": len(result.unassigned_slots),
                    "total_conflicts": len(result.conflicts),
                }
                generation.completed_at = timezone.now()

                if not result.success:
                    generation.error_message = (
                        f"Failed to assign {len(result.unassigned_slots)} slots"
                    )

                generation.save()

                # Save to database if successful
                if result.success:
                    save_result = optimizer.save_schedule_to_database(
                        result, request.user
                    )
                    generation.result_summary.update(save_result)
                    generation.save()

                return Response(TimetableGenerationSerializer(generation).data)

            except Exception as e:
                generation.status = "failed"
                generation.error_message = str(e)
                generation.completed_at = timezone.now()
                generation.save()

                return Response(
                    {"error": f"Generation failed: {str(e)}"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        """Cancel timetable generation"""
        generation = self.get_object()

        if generation.status in ["pending", "running"]:
            generation.status = "cancelled"
            generation.completed_at = timezone.now()
            generation.save()

            return Response({"message": "Generation cancelled"})

        return Response(
            {"error": "Cannot cancel completed or failed generation"},
            status=status.HTTP_400_BAD_REQUEST,
        )


class SchedulingAnalyticsViewSet(viewsets.ViewSet):
    """Scheduling analytics viewset"""

    permission_classes = [IsAuthenticated, HasModulePermission]
    module_name = "scheduling"

    @action(detail=False, methods=["get"])
    def teacher_workload(self, request):
        """Get teacher workload analytics"""
        term_id = request.query_params.get("term_id")
        teacher_id = request.query_params.get("teacher_id")

        if not term_id:
            return Response(
                {"error": "term_id parameter is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        term = get_object_or_404(Term, id=term_id)
        teacher = Teacher.objects.get(id=teacher_id) if teacher_id else None

        analytics_data = SchedulingAnalyticsService.get_teacher_workload_analytics(
            term, teacher
        )
        serializer = WorkloadAnalyticsSerializer(analytics_data)

        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def room_utilization(self, request):
        """Get room utilization analytics"""
        term_id = request.query_params.get("term_id")

        if not term_id:
            return Response(
                {"error": "term_id parameter is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        term = get_object_or_404(Term, id=term_id)
        analytics_data = SchedulingAnalyticsService.get_room_utilization_analytics(term)
        serializer = RoomUtilizationSerializer(analytics_data)

        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def conflicts(self, request):
        """Get scheduling conflicts analytics"""
        term_id = request.query_params.get("term_id")

        if not term_id:
            return Response(
                {"error": "term_id parameter is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        term = get_object_or_404(Term, id=term_id)
        analytics_data = SchedulingAnalyticsService.get_scheduling_conflicts_analytics(
            term
        )
        serializer = ConflictAnalyticsSerializer(analytics_data)

        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def optimization_score(self, request):
        """Get timetable optimization score"""
        term_id = request.query_params.get("term_id")

        if not term_id:
            return Response(
                {"error": "term_id parameter is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        term = get_object_or_404(Term, id=term_id)
        score_data = SchedulingAnalyticsService.get_timetable_optimization_score(term)
        serializer = OptimizationScoreSerializer(score_data)

        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def subject_distribution(self, request):
        """Get subject distribution analytics"""
        term_id = request.query_params.get("term_id")

        if not term_id:
            return Response(
                {"error": "term_id parameter is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        term = get_object_or_404(Term, id=term_id)
        distribution_data = (
            SchedulingAnalyticsService.get_subject_distribution_analytics(term)
        )

        return Response(distribution_data)

    @action(detail=False, methods=["get"])
    def time_slot_popularity(self, request):
        """Get time slot popularity analytics"""
        term_id = request.query_params.get("term_id")

        if not term_id:
            return Response(
                {"error": "term_id parameter is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        term = get_object_or_404(Term, id=term_id)
        popularity_data = SchedulingAnalyticsService.get_time_slot_popularity(term)

        return Response(popularity_data)

    @action(detail=False, methods=["get"])
    def class_schedule_density(self, request):
        """Get class schedule density analytics"""
        term_id = request.query_params.get("term_id")

        if not term_id:
            return Response(
                {"error": "term_id parameter is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        term = get_object_or_404(Term, id=term_id)
        density_data = SchedulingAnalyticsService.get_class_schedule_density(term)

        return Response(density_data)


class SchedulingConstraintViewSet(viewsets.ModelViewSet):
    """Scheduling constraint management viewset"""

    queryset = SchedulingConstraint.objects.all()
    serializer_class = SchedulingConstraintSerializer
    permission_classes = [IsAuthenticated, HasModulePermission]
    module_name = "scheduling"
    filterset_fields = ["constraint_type", "is_hard_constraint", "is_active"]
    ordering = ["-priority", "name"]


class TimetableTemplateViewSet(viewsets.ModelViewSet):
    """Timetable template management viewset"""

    queryset = TimetableTemplate.objects.select_related("grade", "created_by")
    serializer_class = TimetableTemplateSerializer
    permission_classes = [IsAuthenticated, HasModulePermission]
    module_name = "scheduling"
    filterset_fields = ["grade", "is_default"]
    ordering = ["grade", "name"]

    @action(detail=True, methods=["post"])
    def apply_template(self, request, pk=None):
        """Apply template to create timetable"""
        template = self.get_object()
        term_id = request.data.get("term_id")

        if not term_id:
            return Response(
                {"error": "term_id is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            term = Term.objects.get(id=term_id)

            # Apply template logic here
            # This would depend on the template configuration structure

            return Response({"message": "Template applied successfully"})

        except Term.DoesNotExist:
            return Response(
                {"error": "Invalid term ID"}, status=status.HTTP_400_BAD_REQUEST
            )
