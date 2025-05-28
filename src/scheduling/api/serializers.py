from datetime import datetime
from typing import Dict, List

from django.db import transaction
from rest_framework import serializers

from src.academics.models import Class, Grade, Term
from src.accounts.models import User
from src.subjects.models import Subject
from src.teachers.models import Teacher

from ..models import (
    Room,
    SchedulingConstraint,
    SubstituteTeacher,
    TimeSlot,
    Timetable,
    TimetableGeneration,
    TimetableTemplate,
)


class TimeSlotSerializer(serializers.ModelSerializer):
    """Time slot serializer"""

    day_display = serializers.CharField(
        source="get_day_of_week_display", read_only=True
    )

    class Meta:
        model = TimeSlot
        fields = [
            "id",
            "day_of_week",
            "day_display",
            "start_time",
            "end_time",
            "duration_minutes",
            "period_number",
            "name",
            "is_break",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate(self, data):
        if data["start_time"] >= data["end_time"]:
            raise serializers.ValidationError("Start time must be before end time")

        # Calculate expected duration
        start_datetime = datetime.combine(datetime.today(), data["start_time"])
        end_datetime = datetime.combine(datetime.today(), data["end_time"])
        calculated_duration = int((end_datetime - start_datetime).total_seconds() / 60)

        if abs(data["duration_minutes"] - calculated_duration) > 1:
            raise serializers.ValidationError(
                "Duration doesn't match start and end times"
            )

        return data


class RoomSerializer(serializers.ModelSerializer):
    """Room serializer"""

    current_occupancy = serializers.SerializerMethodField()

    class Meta:
        model = Room
        fields = [
            "id",
            "number",
            "name",
            "room_type",
            "building",
            "floor",
            "capacity",
            "equipment",
            "is_available",
            "maintenance_notes",
            "current_occupancy",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "current_occupancy"]

    def get_current_occupancy(self, obj):
        """Get current timetable entries for this room"""
        current_term = getattr(self.context.get("request"), "current_term", None)
        if current_term:
            return obj.timetable_entries.filter(
                term=current_term, is_active=True
            ).count()
        return 0


class TimetableListSerializer(serializers.ModelSerializer):
    """Simplified timetable serializer for list views"""

    class_name = serializers.CharField(source="class_assigned.name", read_only=True)
    grade_name = serializers.CharField(
        source="class_assigned.grade.name", read_only=True
    )
    subject_name = serializers.CharField(source="subject.name", read_only=True)
    teacher_name = serializers.CharField(
        source="teacher.user.get_full_name", read_only=True
    )
    room_number = serializers.CharField(source="room.number", read_only=True)
    time_slot_display = serializers.CharField(
        source="time_slot.__str__", read_only=True
    )
    day_of_week = serializers.IntegerField(
        source="time_slot.day_of_week", read_only=True
    )
    period_number = serializers.IntegerField(
        source="time_slot.period_number", read_only=True
    )

    class Meta:
        model = Timetable
        fields = [
            "id",
            "class_name",
            "grade_name",
            "subject_name",
            "teacher_name",
            "room_number",
            "time_slot_display",
            "day_of_week",
            "period_number",
            "effective_from_date",
            "effective_to_date",
            "is_active",
        ]


class TimetableDetailSerializer(serializers.ModelSerializer):
    """Detailed timetable serializer"""

    class_assigned = serializers.StringRelatedField(read_only=True)
    subject = serializers.StringRelatedField(read_only=True)
    teacher = serializers.StringRelatedField(read_only=True)
    room = serializers.StringRelatedField(read_only=True)
    time_slot = TimeSlotSerializer(read_only=True)
    term = serializers.StringRelatedField(read_only=True)
    created_by = serializers.StringRelatedField(read_only=True)

    # For write operations
    class_assigned_id = serializers.UUIDField(write_only=True)
    subject_id = serializers.UUIDField(write_only=True)
    teacher_id = serializers.UUIDField(write_only=True)
    time_slot_id = serializers.UUIDField(write_only=True)
    room_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)
    term_id = serializers.UUIDField(write_only=True)

    class Meta:
        model = Timetable
        fields = [
            "id",
            "class_assigned",
            "subject",
            "teacher",
            "room",
            "time_slot",
            "term",
            "effective_from_date",
            "effective_to_date",
            "is_active",
            "notes",
            "created_by",
            "created_at",
            "updated_at",
            # Write-only fields
            "class_assigned_id",
            "subject_id",
            "teacher_id",
            "time_slot_id",
            "room_id",
            "term_id",
        ]
        read_only_fields = ["id", "created_by", "created_at", "updated_at"]

    def create(self, validated_data):
        """Create timetable entry with validation"""
        # Extract IDs
        class_assigned = Class.objects.get(id=validated_data.pop("class_assigned_id"))
        subject = Subject.objects.get(id=validated_data.pop("subject_id"))
        teacher = Teacher.objects.get(id=validated_data.pop("teacher_id"))
        time_slot = TimeSlot.objects.get(id=validated_data.pop("time_slot_id"))
        term = Term.objects.get(id=validated_data.pop("term_id"))

        room = None
        if validated_data.get("room_id"):
            room = Room.objects.get(id=validated_data.pop("room_id"))
        else:
            validated_data.pop("room_id", None)

        # Create timetable entry
        timetable = Timetable.objects.create(
            class_assigned=class_assigned,
            subject=subject,
            teacher=teacher,
            time_slot=time_slot,
            room=room,
            term=term,
            created_by=self.context["request"].user,
            **validated_data,
        )

        return timetable

    def update(self, instance, validated_data):
        """Update timetable entry"""
        # Handle foreign key updates
        if "class_assigned_id" in validated_data:
            instance.class_assigned = Class.objects.get(
                id=validated_data.pop("class_assigned_id")
            )

        if "subject_id" in validated_data:
            instance.subject = Subject.objects.get(id=validated_data.pop("subject_id"))

        if "teacher_id" in validated_data:
            instance.teacher = Teacher.objects.get(id=validated_data.pop("teacher_id"))

        if "time_slot_id" in validated_data:
            instance.time_slot = TimeSlot.objects.get(
                id=validated_data.pop("time_slot_id")
            )

        if "term_id" in validated_data:
            instance.term = Term.objects.get(id=validated_data.pop("term_id"))

        if "room_id" in validated_data:
            room_id = validated_data.pop("room_id")
            instance.room = Room.objects.get(id=room_id) if room_id else None

        # Update other fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()
        return instance


class TimetableCreateSerializer(serializers.Serializer):
    """Serializer for creating multiple timetable entries"""

    class_assigned_id = serializers.UUIDField()
    subject_id = serializers.UUIDField()
    teacher_id = serializers.UUIDField()
    time_slot_id = serializers.UUIDField()
    room_id = serializers.UUIDField(required=False, allow_null=True)
    term_id = serializers.UUIDField()
    effective_from_date = serializers.DateField(required=False)
    effective_to_date = serializers.DateField(required=False)
    notes = serializers.CharField(required=False, allow_blank=True)


class BulkTimetableCreateSerializer(serializers.Serializer):
    """Serializer for bulk timetable creation"""

    entries = TimetableCreateSerializer(many=True)

    def validate_entries(self, entries):
        """Validate bulk entries for conflicts"""
        if not entries:
            raise serializers.ValidationError("At least one entry is required")

        # Check for internal conflicts
        seen_combinations = set()

        for entry in entries:
            # Teacher-time combination
            teacher_time = (entry["teacher_id"], entry["time_slot_id"])
            if teacher_time in seen_combinations:
                raise serializers.ValidationError(
                    f"Teacher conflict detected in bulk data for time slot {entry['time_slot_id']}"
                )
            seen_combinations.add(teacher_time)

            # Room-time combination (if room specified)
            if entry.get("room_id"):
                room_time = (entry["room_id"], entry["time_slot_id"])
                if room_time in seen_combinations:
                    raise serializers.ValidationError(
                        f"Room conflict detected in bulk data for time slot {entry['time_slot_id']}"
                    )
                seen_combinations.add(room_time)

        return entries

    @transaction.atomic
    def create(self, validated_data):
        """Create multiple timetable entries"""
        entries_data = validated_data["entries"]
        created_entries = []
        errors = []

        for entry_data in entries_data:
            try:
                # Get objects
                class_assigned = Class.objects.get(id=entry_data["class_assigned_id"])
                subject = Subject.objects.get(id=entry_data["subject_id"])
                teacher = Teacher.objects.get(id=entry_data["teacher_id"])
                time_slot = TimeSlot.objects.get(id=entry_data["time_slot_id"])
                term = Term.objects.get(id=entry_data["term_id"])

                room = None
                if entry_data.get("room_id"):
                    room = Room.objects.get(id=entry_data["room_id"])

                # Set defaults
                if not entry_data.get("effective_from_date"):
                    entry_data["effective_from_date"] = term.start_date
                if not entry_data.get("effective_to_date"):
                    entry_data["effective_to_date"] = term.end_date

                # Create entry
                timetable = Timetable.objects.create(
                    class_assigned=class_assigned,
                    subject=subject,
                    teacher=teacher,
                    time_slot=time_slot,
                    room=room,
                    term=term,
                    effective_from_date=entry_data["effective_from_date"],
                    effective_to_date=entry_data["effective_to_date"],
                    notes=entry_data.get("notes", ""),
                    created_by=self.context["request"].user,
                )

                created_entries.append(timetable)

            except Exception as e:
                errors.append(f"Error creating entry: {str(e)}")

        return {
            "created_entries": created_entries,
            "errors": errors,
            "success_count": len(created_entries),
            "error_count": len(errors),
        }


class SubstituteTeacherSerializer(serializers.ModelSerializer):
    """Substitute teacher serializer"""

    original_timetable = TimetableListSerializer(read_only=True)
    substitute_teacher = serializers.StringRelatedField(read_only=True)
    approved_by = serializers.StringRelatedField(read_only=True)
    created_by = serializers.StringRelatedField(read_only=True)

    # Write-only fields
    original_timetable_id = serializers.UUIDField(write_only=True)
    substitute_teacher_id = serializers.UUIDField(write_only=True)

    class Meta:
        model = SubstituteTeacher
        fields = [
            "id",
            "original_timetable",
            "substitute_teacher",
            "date",
            "reason",
            "notes",
            "approved_by",
            "created_by",
            "created_at",
            # Write-only fields
            "original_timetable_id",
            "substitute_teacher_id",
        ]
        read_only_fields = ["id", "approved_by", "created_by", "created_at"]

    def create(self, validated_data):
        original_timetable = Timetable.objects.get(
            id=validated_data.pop("original_timetable_id")
        )
        substitute_teacher = Teacher.objects.get(
            id=validated_data.pop("substitute_teacher_id")
        )

        return SubstituteTeacher.objects.create(
            original_timetable=original_timetable,
            substitute_teacher=substitute_teacher,
            created_by=self.context["request"].user,
            **validated_data,
        )


class SchedulingConstraintSerializer(serializers.ModelSerializer):
    """Scheduling constraint serializer"""

    constraint_type_display = serializers.CharField(
        source="get_constraint_type_display", read_only=True
    )

    class Meta:
        model = SchedulingConstraint
        fields = [
            "id",
            "name",
            "constraint_type",
            "constraint_type_display",
            "parameters",
            "priority",
            "is_hard_constraint",
            "is_active",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class TimetableGenerationSerializer(serializers.ModelSerializer):
    """Timetable generation serializer"""

    term = serializers.StringRelatedField(read_only=True)
    grades = serializers.StringRelatedField(many=True, read_only=True)
    started_by = serializers.StringRelatedField(read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    # Write-only fields
    term_id = serializers.UUIDField(write_only=True)
    grade_ids = serializers.ListField(child=serializers.UUIDField(), write_only=True)

    class Meta:
        model = TimetableGeneration
        fields = [
            "id",
            "term",
            "grades",
            "status",
            "status_display",
            "algorithm_used",
            "parameters",
            "result_summary",
            "conflicts_resolved",
            "optimization_score",
            "execution_time_seconds",
            "error_message",
            "started_by",
            "started_at",
            "completed_at",
            # Write-only fields
            "term_id",
            "grade_ids",
        ]
        read_only_fields = [
            "id",
            "status",
            "result_summary",
            "conflicts_resolved",
            "optimization_score",
            "execution_time_seconds",
            "error_message",
            "started_by",
            "started_at",
            "completed_at",
        ]

    def create(self, validated_data):
        term = Term.objects.get(id=validated_data.pop("term_id"))
        grade_ids = validated_data.pop("grade_ids")
        grades = Grade.objects.filter(id__in=grade_ids)

        generation = TimetableGeneration.objects.create(
            term=term, started_by=self.context["request"].user, **validated_data
        )

        generation.grades.set(grades)
        return generation


class TimetableTemplateSerializer(serializers.ModelSerializer):
    """Timetable template serializer"""

    grade = serializers.StringRelatedField(read_only=True)
    created_by = serializers.StringRelatedField(read_only=True)

    # Write-only field
    grade_id = serializers.UUIDField(write_only=True)

    class Meta:
        model = TimetableTemplate
        fields = [
            "id",
            "name",
            "description",
            "grade",
            "is_default",
            "configuration",
            "created_by",
            "created_at",
            "updated_at",
            # Write-only field
            "grade_id",
        ]
        read_only_fields = ["id", "created_by", "created_at", "updated_at"]

    def create(self, validated_data):
        grade = Grade.objects.get(id=validated_data.pop("grade_id"))

        return TimetableTemplate.objects.create(
            grade=grade, created_by=self.context["request"].user, **validated_data
        )


# Analytics Serializers
class WorkloadAnalyticsSerializer(serializers.Serializer):
    """Teacher workload analytics serializer"""

    teacher_workloads = serializers.ListField(child=serializers.DictField())
    summary = serializers.DictField()


class RoomUtilizationSerializer(serializers.Serializer):
    """Room utilization analytics serializer"""

    room_utilization = serializers.ListField(child=serializers.DictField())
    room_type_analysis = serializers.ListField(child=serializers.DictField())
    peak_usage_times = serializers.ListField(child=serializers.DictField())
    summary = serializers.DictField()


class ConflictAnalyticsSerializer(serializers.Serializer):
    """Scheduling conflicts analytics serializer"""

    teacher_conflicts = serializers.IntegerField()
    room_conflicts = serializers.IntegerField()
    unassigned_rooms = serializers.IntegerField()
    substitute_frequency = serializers.ListField(child=serializers.DictField())
    conflict_details = serializers.DictField()


class OptimizationScoreSerializer(serializers.Serializer):
    """Optimization score serializer"""

    overall_score = serializers.FloatField()
    grade = serializers.CharField()
    breakdown = serializers.DictField()
    recommendations = serializers.ListField(child=serializers.CharField())


# Utility Serializers
class AvailableTeachersSerializer(serializers.Serializer):
    """Available teachers for time slot"""

    time_slot_id = serializers.UUIDField()
    subject_id = serializers.UUIDField()
    date = serializers.DateField()
    class_id = serializers.UUIDField(required=False)


class AvailableRoomsSerializer(serializers.Serializer):
    """Available rooms for time slot"""

    time_slot_id = serializers.UUIDField()
    date = serializers.DateField()
    room_type = serializers.CharField(required=False)
    min_capacity = serializers.IntegerField(required=False)


class ConflictCheckSerializer(serializers.Serializer):
    """Conflict checking serializer"""

    teacher_id = serializers.UUIDField(required=False)
    room_id = serializers.UUIDField(required=False)
    class_id = serializers.UUIDField(required=False)
    time_slot_id = serializers.UUIDField(required=False)
    start_date = serializers.DateField(required=False)
    end_date = serializers.DateField(required=False)
    exclude_timetable_id = serializers.UUIDField(required=False)
