from src.courses.models import Timetable, TimeSlot, Class, Subject
from django.db.models import Q
from datetime import date


class TimetableService:
    @staticmethod
    def get_teacher_timetable(teacher, day=None, academic_year=None):
        """Get the timetable for a specific teacher"""
        query = Q(teacher=teacher, is_active=True)

        if academic_year:
            query &= Q(class_obj__academic_year=academic_year)
        else:
            # Default to current academic year
            from src.courses.models import AcademicYear

            current_year = AcademicYear.objects.filter(is_current=True).first()
            if current_year:
                query &= Q(class_obj__academic_year=current_year)

        timetable_entries = Timetable.objects.filter(query).select_related(
            "class_obj", "subject", "time_slot"
        )

        if day is not None:
            timetable_entries = timetable_entries.filter(time_slot__day_of_week=day)

        return timetable_entries.order_by(
            "time_slot__day_of_week", "time_slot__start_time"
        )

    @staticmethod
    def check_teacher_availability(teacher, time_slot, exclude_id=None):
        """Check if a teacher is available during a specific time slot"""
        query = Timetable.objects.filter(
            teacher=teacher, time_slot=time_slot, is_active=True
        )

        if exclude_id:
            query = query.exclude(id=exclude_id)

        return not query.exists()

    @staticmethod
    def create_timetable_entry(
        class_obj, subject, teacher, time_slot, room, effective_from=None
    ):
        """Create a new timetable entry"""
        if not effective_from:
            effective_from = date.today()

        # Ensure no clashes
        if TimetableService.check_teacher_availability(
            teacher, time_slot
        ) and not Class.objects.check_timetable_clash(class_obj, time_slot):
            timetable = Timetable.objects.create(
                class_obj=class_obj,
                subject=subject,
                teacher=teacher,
                time_slot=time_slot,
                room=room,
                effective_from_date=effective_from,
                is_active=True,
            )
            return timetable
        return None
