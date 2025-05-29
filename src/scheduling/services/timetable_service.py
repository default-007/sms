import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Avg, Count, Q
from django.utils import timezone

from src.academics.models import Class, Grade, Term
from src.subjects.models import Subject
from src.teachers.models import Teacher, TeacherClassAssignment

from ..models import (
    Room,
    SchedulingConstraint,
    SubstituteTeacher,
    TimeSlot,
    Timetable,
    TimetableGeneration,
    TimetableTemplate,
)


class TimetableService:
    """Core timetable management service"""

    @staticmethod
    def create_timetable_entry(
        class_assigned: Class,
        subject: Subject,
        teacher: Teacher,
        time_slot: TimeSlot,
        term: Term,
        room: Optional[Room] = None,
        effective_from: Optional[datetime.date] = None,
        effective_to: Optional[datetime.date] = None,
        **kwargs,
    ) -> Timetable:
        """Create a single timetable entry with validation"""

        if not effective_from:
            effective_from = term.start_date
        if not effective_to:
            effective_to = term.end_date

        # Validate teacher assignment
        teacher_assignment = TeacherClassAssignment.objects.filter(
            teacher=teacher,
            class_assigned=class_assigned,
            subject=subject,
            term=term,
            is_active=True,
        ).first()

        if not teacher_assignment:
            raise ValidationError(
                f"Teacher {teacher} is not assigned to teach {subject} for class {class_assigned} in {term}"
            )

        # Create timetable entry
        timetable = Timetable(
            class_assigned=class_assigned,
            subject=subject,
            teacher=teacher,
            time_slot=time_slot,
            room=room,
            term=term,
            effective_from_date=effective_from,
            effective_to_date=effective_to,
            **kwargs,
        )

        # Validation will occur in model's clean method
        timetable.save()
        return timetable

    @staticmethod
    def get_class_timetable(
        class_obj: Class, term: Term, date: Optional[datetime.date] = None
    ) -> Dict[str, List[Timetable]]:
        """Get organized timetable for a class"""

        query = Timetable.objects.filter(
            class_assigned=class_obj, term=term, is_active=True
        ).select_related("subject", "teacher", "time_slot", "room")

        if date:
            query = query.filter(
                effective_from_date__lte=date, effective_to_date__gte=date
            )

        timetable_entries = query.order_by(
            "time_slot__day_of_week", "time_slot__period_number"
        )

        # Organize by day
        organized = {}
        for entry in timetable_entries:
            day = entry.time_slot.get_day_of_week_display()
            if day not in organized:
                organized[day] = []
            organized[day].append(entry)

        return organized

    @staticmethod
    def get_teacher_timetable(
        teacher: Teacher, term: Term, date: Optional[datetime.date] = None
    ) -> Dict[str, List[Timetable]]:
        """Get organized timetable for a teacher"""

        query = Timetable.objects.filter(
            teacher=teacher, term=term, is_active=True
        ).select_related("class_assigned", "subject", "time_slot", "room")

        if date:
            query = query.filter(
                effective_from_date__lte=date, effective_to_date__gte=date
            )

        timetable_entries = query.order_by(
            "time_slot__day_of_week", "time_slot__period_number"
        )

        # Organize by day
        organized = {}
        for entry in timetable_entries:
            day = entry.time_slot.get_day_of_week_display()
            if day not in organized:
                organized[day] = []
            organized[day].append(entry)

        return organized

    @staticmethod
    def check_conflicts(
        teacher: Teacher = None,
        room: Room = None,
        class_obj: Class = None,
        time_slot: TimeSlot = None,
        date_range: Tuple[datetime.date, datetime.date] = None,
        exclude_timetable: Timetable = None,
    ) -> List[Dict]:
        """Check for scheduling conflicts"""

        conflicts = []

        if not any([teacher, room, class_obj]):
            return conflicts

        query = Timetable.objects.filter(is_active=True)

        if time_slot:
            query = query.filter(time_slot=time_slot)

        if date_range:
            start_date, end_date = date_range
            query = query.filter(
                effective_from_date__lte=end_date, effective_to_date__gte=start_date
            )

        if exclude_timetable:
            query = query.exclude(pk=exclude_timetable.pk)

        # Teacher conflicts
        if teacher:
            teacher_conflicts = query.filter(teacher=teacher)
            for conflict in teacher_conflicts:
                conflicts.append(
                    {
                        "type": "teacher",
                        "message": f"Teacher {teacher} already scheduled",
                        "timetable": conflict,
                        "severity": "high",
                    }
                )

        # Room conflicts
        if room:
            room_conflicts = query.filter(room=room)
            for conflict in room_conflicts:
                conflicts.append(
                    {
                        "type": "room",
                        "message": f"Room {room} already booked",
                        "timetable": conflict,
                        "severity": "high",
                    }
                )

        # Class conflicts
        if class_obj:
            class_conflicts = query.filter(class_assigned=class_obj)
            for conflict in class_conflicts:
                conflicts.append(
                    {
                        "type": "class",
                        "message": f"Class {class_obj} already has a subject scheduled",
                        "timetable": conflict,
                        "severity": "high",
                    }
                )

        return conflicts

    @staticmethod
    def get_available_teachers(
        time_slot: TimeSlot,
        subject: Subject,
        date: datetime.date,
        class_obj: Class = None,
    ) -> List[Teacher]:
        """Get teachers available for a specific time slot"""

        # Get teachers who can teach this subject
        qualified_teachers = Teacher.objects.filter(
            teacher_assignments__subject=subject,
            teacher_assignments__term__start_date__lte=date,
            teacher_assignments__term__end_date__gte=date,
            status="active",
        ).distinct()

        if class_obj:
            qualified_teachers = qualified_teachers.filter(
                teacher_assignments__class_assigned=class_obj
            )

        # Exclude teachers who are already scheduled
        scheduled_teachers = Timetable.objects.filter(
            time_slot=time_slot,
            effective_from_date__lte=date,
            effective_to_date__gte=date,
            is_active=True,
        ).values_list("teacher_id", flat=True)

        available_teachers = qualified_teachers.exclude(id__in=scheduled_teachers)

        return list(available_teachers)

    @staticmethod
    def get_available_rooms(
        time_slot: TimeSlot,
        date: datetime.date,
        room_type: str = None,
        min_capacity: int = None,
    ) -> List[Room]:
        """Get rooms available for a specific time slot"""

        query = Room.objects.filter(is_available=True)

        if room_type:
            query = query.filter(room_type=room_type)

        if min_capacity:
            query = query.filter(capacity__gte=min_capacity)

        # Exclude rooms that are already booked
        booked_rooms = Timetable.objects.filter(
            time_slot=time_slot,
            effective_from_date__lte=date,
            effective_to_date__gte=date,
            is_active=True,
        ).values_list("room_id", flat=True)

        available_rooms = query.exclude(id__in=booked_rooms)

        return list(available_rooms)

    @staticmethod
    @transaction.atomic
    def bulk_update_timetable(
        term: Term, updates: List[Dict], created_by: "User" = None
    ) -> Dict[str, int]:
        """Bulk update timetable entries"""

        created_count = 0
        updated_count = 0
        errors = []

        for update_data in updates:
            try:
                timetable_id = update_data.pop("id", None)

                if timetable_id:
                    # Update existing
                    timetable = Timetable.objects.get(id=timetable_id, term=term)
                    for field, value in update_data.items():
                        setattr(timetable, field, value)
                    timetable.save()
                    updated_count += 1
                else:
                    # Create new
                    update_data["term"] = term
                    if created_by:
                        update_data["created_by"] = created_by

                    timetable = Timetable.objects.create(**update_data)
                    created_count += 1

            except Exception as e:
                errors.append(f"Error processing update {update_data}: {str(e)}")

        return {"created": created_count, "updated": updated_count, "errors": errors}

    @staticmethod
    def get_teacher_workload(teacher: Teacher, term: Term) -> Dict[str, int]:
        """Calculate teacher's workload for a term"""

        timetable_entries = Timetable.objects.filter(
            teacher=teacher, term=term, is_active=True
        )

        total_periods = timetable_entries.count()
        unique_classes = timetable_entries.values("class_assigned").distinct().count()
        unique_subjects = timetable_entries.values("subject").distinct().count()

        # Calculate periods per day
        periods_per_day = {}
        for entry in timetable_entries:
            day = entry.time_slot.get_day_of_week_display()
            periods_per_day[day] = periods_per_day.get(day, 0) + 1

        return {
            "total_periods": total_periods,
            "classes_taught": unique_classes,
            "subjects_taught": unique_subjects,
            "periods_per_day": periods_per_day,
            "average_periods_per_day": total_periods / 5 if total_periods > 0 else 0,
        }

    @staticmethod
    def copy_timetable_to_term(
        source_term: Term,
        target_term: Term,
        grades: List[Grade] = None,
        created_by: "User" = None,
    ) -> Dict[str, int]:
        """Copy timetable from one term to another"""

        query = Timetable.objects.filter(term=source_term, is_active=True)

        if grades:
            query = query.filter(class_assigned__grade__in=grades)

        copied_count = 0
        errors = []

        with transaction.atomic():
            for timetable in query:
                try:
                    # Create new timetable entry for target term
                    new_timetable = Timetable(
                        class_assigned=timetable.class_assigned,
                        subject=timetable.subject,
                        teacher=timetable.teacher,
                        time_slot=timetable.time_slot,
                        room=timetable.room,
                        term=target_term,
                        effective_from_date=target_term.start_date,
                        effective_to_date=target_term.end_date,
                        notes=timetable.notes,
                        created_by=created_by,
                    )
                    new_timetable.save()
                    copied_count += 1

                except Exception as e:
                    errors.append(f"Error copying {timetable}: {str(e)}")

        return {"copied": copied_count, "errors": errors}


class SubstituteService:
    """Substitute teacher management service"""

    @staticmethod
    def create_substitute_assignment(
        original_timetable: Timetable,
        substitute_teacher: Teacher,
        date: datetime.date,
        reason: str,
        created_by: "User" = None,
        **kwargs,
    ) -> SubstituteTeacher:
        """Create substitute teacher assignment"""

        substitute = SubstituteTeacher(
            original_timetable=original_timetable,
            substitute_teacher=substitute_teacher,
            date=date,
            reason=reason,
            created_by=created_by,
            **kwargs,
        )

        substitute.save()
        return substitute

    @staticmethod
    def get_substitute_suggestions(
        original_timetable: Timetable, date: datetime.date
    ) -> List[Dict]:
        """Get suggested substitute teachers"""

        suggestions = []

        # Get teachers who can teach the same subject
        qualified_teachers = Teacher.objects.filter(
            teacher_assignments__subject=original_timetable.subject, status="active"
        ).exclude(id=original_timetable.teacher.id)

        for teacher in qualified_teachers:
            # Check availability
            conflicts = TimetableService.check_conflicts(
                teacher=teacher,
                time_slot=original_timetable.time_slot,
                date_range=(date, date),
            )

            # Calculate compatibility score
            score = 100
            if conflicts:
                score -= 50  # Penalty for conflicts

            # Check if teacher has taught this class before
            has_taught_class = TeacherClassAssignment.objects.filter(
                teacher=teacher, class_assigned=original_timetable.class_assigned
            ).exists()

            if has_taught_class:
                score += 20

            suggestions.append(
                {
                    "teacher": teacher,
                    "conflicts": conflicts,
                    "compatibility_score": score,
                    "has_taught_class": has_taught_class,
                }
            )

        # Sort by compatibility score
        suggestions.sort(key=lambda x: x["compatibility_score"], reverse=True)

        return suggestions

    @staticmethod
    def get_substitute_history(
        teacher: Teacher = None, date_range: Tuple[datetime.date, datetime.date] = None
    ) -> List[SubstituteTeacher]:
        """Get substitute assignment history"""

        query = SubstituteTeacher.objects.select_related(
            "original_timetable",
            "substitute_teacher",
            "original_timetable__class_assigned",
            "original_timetable__subject",
        )

        if teacher:
            query = query.filter(substitute_teacher=teacher)

        if date_range:
            start_date, end_date = date_range
            query = query.filter(date__range=[start_date, end_date])

        return query.order_by("-date")


class RoomService:
    """Room management service"""

    @staticmethod
    def get_room_utilization(room: Room, term: Term) -> Dict[str, float]:
        """Calculate room utilization statistics"""

        total_periods = (
            TimeSlot.objects.filter(is_active=True, is_break=False).count() * 5
        )  # 5 working days

        used_periods = Timetable.objects.filter(
            room=room, term=term, is_active=True
        ).count()

        utilization_rate = (
            (used_periods / total_periods * 100) if total_periods > 0 else 0
        )

        return {
            "total_available_periods": total_periods,
            "used_periods": used_periods,
            "utilization_rate": round(utilization_rate, 2),
            "free_periods": total_periods - used_periods,
        }

    @staticmethod
    def get_room_booking_calendar(room: Room, term: Term) -> Dict[str, List[Dict]]:
        """Get room booking calendar"""

        bookings = Timetable.objects.filter(
            room=room, term=term, is_active=True
        ).select_related("class_assigned", "subject", "teacher", "time_slot")

        calendar = {}
        for booking in bookings:
            day = booking.time_slot.get_day_of_week_display()
            if day not in calendar:
                calendar[day] = []

            calendar[day].append(
                {
                    "time_slot": booking.time_slot,
                    "class": booking.class_assigned,
                    "subject": booking.subject,
                    "teacher": booking.teacher,
                    "period": booking.time_slot.period_number,
                }
            )

        # Sort by period number
        for day in calendar:
            calendar[day].sort(key=lambda x: x["period"])

        return calendar

    @staticmethod
    def suggest_optimal_room(
        class_obj: Class, subject: Subject, time_slot: TimeSlot, date: datetime.date
    ) -> List[Dict]:
        """Suggest optimal rooms for a class/subject"""

        suggestions = []
        available_rooms = TimetableService.get_available_rooms(time_slot, date)

        for room in available_rooms:
            score = 0

            # Capacity matching
            if room.capacity >= class_obj.student_set.count():
                score += 30
                if room.capacity <= class_obj.student_set.count() * 1.2:
                    score += 20  # Perfect size match
            else:
                score -= 50  # Too small

            # Subject-specific requirements
            subject_requirements = {
                "science": ["laboratory", "computer_lab"],
                "computer": ["computer_lab"],
                "physical_education": ["gymnasium", "outdoor"],
                "music": ["music_room"],
                "art": ["art_room"],
            }

            subject_name_lower = subject.name.lower()
            for key, preferred_types in subject_requirements.items():
                if key in subject_name_lower and room.room_type in preferred_types:
                    score += 40

            # Equipment match
            if hasattr(subject, "required_equipment"):
                equipment_match = set(room.equipment or []) & set(
                    subject.required_equipment or []
                )
                score += len(equipment_match) * 10

            suggestions.append(
                {
                    "room": room,
                    "suitability_score": score,
                    "capacity_match": room.capacity >= class_obj.student_set.count(),
                    "room_type_match": room.room_type
                    in subject_requirements.get(subject_name_lower, []),
                }
            )

        suggestions.sort(key=lambda x: x["suitability_score"], reverse=True)
        return suggestions
