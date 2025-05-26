from datetime import date, datetime, time, timedelta

from django.db.models import Count, Q
from django.utils import timezone

from src.courses.models import AcademicYear, Class, Subject, TimeSlot, Timetable


class TimetableService:
    @staticmethod
    def get_teacher_timetable(teacher, day=None, academic_year=None):
        """Get the timetable for a specific teacher."""
        query = Q(teacher=teacher, is_active=True)

        if academic_year:
            query &= Q(class_obj__academic_year=academic_year)
        else:
            current_year = AcademicYear.objects.filter(is_current=True).first()
            if current_year:
                query &= Q(class_obj__academic_year=current_year)

        timetable_entries = Timetable.objects.filter(query).select_related(
            "class_obj",
            "subject",
            "time_slot",
            "class_obj__grade",
            "class_obj__section",
        )

        if day is not None:
            timetable_entries = timetable_entries.filter(time_slot__day_of_week=day)

        return timetable_entries.order_by(
            "time_slot__day_of_week", "time_slot__start_time"
        )

    @staticmethod
    def check_teacher_availability(teacher, time_slot, exclude_id=None):
        """Check if a teacher is available during a specific time slot."""
        query = Timetable.objects.filter(
            teacher=teacher, time_slot=time_slot, is_active=True
        )

        if exclude_id:
            query = query.exclude(id=exclude_id)

        return not query.exists()

    @staticmethod
    def create_timetable_entry(
        class_obj,
        subject,
        teacher,
        time_slot,
        room,
        effective_from=None,
        effective_to=None,
    ):
        """Create a new timetable entry."""
        if not effective_from:
            effective_from = date.today()

        # Check for clashes
        teacher_clash = not TimetableService.check_teacher_availability(
            teacher, time_slot
        )
        room_clash = (
            False
            if not room
            else not TimetableService.check_room_availability(room, time_slot)
        )
        class_clash = not TimetableService.check_class_availability(
            class_obj, time_slot
        )

        # Only create if there are no clashes
        if not (teacher_clash or room_clash or class_clash):
            entry = Timetable.objects.create(
                class_obj=class_obj,
                subject=subject,
                teacher=teacher,
                time_slot=time_slot,
                room=room,
                effective_from_date=effective_from,
                effective_to_date=effective_to,
                is_active=True,
            )
            return entry
        return None

    @staticmethod
    def check_room_availability(room, time_slot, exclude_id=None):
        """Check if a room is available during a specific time slot."""
        if not room:  # If no room specified, consider it available
            return True

        query = Timetable.objects.filter(room=room, time_slot=time_slot, is_active=True)

        if exclude_id:
            query = query.exclude(id=exclude_id)

        return not query.exists()

    @staticmethod
    def check_class_availability(class_obj, time_slot, exclude_id=None):
        """Check if a class is available during a specific time slot."""
        query = Timetable.objects.filter(
            class_obj=class_obj, time_slot=time_slot, is_active=True
        )

        if exclude_id:
            query = query.exclude(id=exclude_id)

        return not query.exists()

    @staticmethod
    def get_timetable_clashes():
        """Get all timetable clashes (same teacher/room/class at same time)."""
        clashes = []

        # Get all active time slots with timetable entries
        active_timeslots = TimeSlot.objects.filter(
            timetable_entries__is_active=True
        ).distinct()

        for timeslot in active_timeslots:
            # Check for teacher clashes
            teacher_clashes = (
                Timetable.objects.filter(time_slot=timeslot, is_active=True)
                .values("teacher")
                .annotate(count=Count("id"))
                .filter(count__gt=1)
            )

            # Check for room clashes
            room_clashes = (
                Timetable.objects.filter(time_slot=timeslot, is_active=True)
                .exclude(room="")  # Exclude empty rooms
                .values("room")
                .annotate(count=Count("id"))
                .filter(count__gt=1)
            )

            # Check for class clashes
            class_clashes = (
                Timetable.objects.filter(time_slot=timeslot, is_active=True)
                .values("class_obj")
                .annotate(count=Count("id"))
                .filter(count__gt=1)
            )

            if (
                teacher_clashes.exists()
                or room_clashes.exists()
                or class_clashes.exists()
            ):
                clashes.append(
                    {
                        "time_slot": timeslot,
                        "teacher_clashes": teacher_clashes,
                        "room_clashes": room_clashes,
                        "class_clashes": class_clashes,
                    }
                )

        return clashes

    @staticmethod
    def get_free_rooms(time_slot):
        """Get all rooms that are free during a specific time slot."""
        # Get all rooms that are used in the timetable
        all_rooms = set(
            Timetable.objects.exclude(room="").values_list("room", flat=True).distinct()
        )

        # Get rooms that are occupied during this time slot
        occupied_rooms = set(
            Timetable.objects.filter(time_slot=time_slot, is_active=True)
            .exclude(room="")
            .values_list("room", flat=True)
            .distinct()
        )

        # Return the difference
        return all_rooms - occupied_rooms

    @staticmethod
    def get_free_teachers(time_slot, department=None, subject=None):
        """Get all teachers that are free during a specific time slot."""
        from src.teachers.models import Teacher

        # Get all active teachers
        teachers = Teacher.objects.filter(status="Active")

        if department:
            teachers = teachers.filter(department=department)

        if subject:
            # Prioritize teachers from the subject's department
            teachers = teachers.filter(department=subject.department)

        # Get teachers that are occupied during this time slot
        occupied_teachers = (
            Timetable.objects.filter(time_slot=time_slot, is_active=True)
            .values_list("teacher", flat=True)
            .distinct()
        )

        # Return the free teachers
        return teachers.exclude(id__in=occupied_teachers)

    @staticmethod
    def generate_timetable_suggestions(class_obj, subjects):
        """Generate timetable suggestions based on available teachers and rooms."""
        suggestions = []

        # Get all time slots
        time_slots = TimeSlot.objects.all()

        for subject in subjects:
            # Get teachers specialized in this subject
            qualified_teachers = subject.department.teachers.filter(status="Active")

            for time_slot in time_slots:
                # Check if class is available at this time
                if TimetableService.check_class_availability(class_obj, time_slot):
                    # Get available teachers
                    available_teachers = [
                        teacher
                        for teacher in qualified_teachers
                        if TimetableService.check_teacher_availability(
                            teacher, time_slot
                        )
                    ]

                    # Get available rooms
                    available_rooms = TimetableService.get_free_rooms(time_slot)

                    if available_teachers and available_rooms:
                        suggestions.append(
                            {
                                "class_obj": class_obj,
                                "subject": subject,
                                "time_slot": time_slot,
                                "available_teachers": available_teachers,
                                "available_rooms": available_rooms,
                            }
                        )

        return suggestions

    @staticmethod
    def get_teacher_workload(teacher, academic_year=None):
        """Calculate the workload for a teacher."""
        if not academic_year:
            academic_year = AcademicYear.objects.filter(is_current=True).first()

        timetable_entries = Timetable.objects.filter(
            teacher=teacher, class_obj__academic_year=academic_year, is_active=True
        )

        # Get total periods per week
        periods_per_week = timetable_entries.count()

        # Calculate total time (in minutes) per week
        total_minutes = sum(
            [entry.time_slot.duration_minutes for entry in timetable_entries]
        )

        # Get distinct classes and subjects
        distinct_classes = (
            timetable_entries.values_list("class_obj", flat=True).distinct().count()
        )
        distinct_subjects = (
            timetable_entries.values_list("subject", flat=True).distinct().count()
        )

        # Calculate daily distribution
        daily_load = {}
        for day in range(7):
            day_entries = timetable_entries.filter(time_slot__day_of_week=day)
            daily_load[day] = {
                "periods": day_entries.count(),
                "minutes": sum(
                    [entry.time_slot.duration_minutes for entry in day_entries]
                ),
            }

        return {
            "teacher": teacher,
            "academic_year": academic_year,
            "periods_per_week": periods_per_week,
            "hours_per_week": total_minutes / 60,
            "distinct_classes": distinct_classes,
            "distinct_subjects": distinct_subjects,
            "daily_load": daily_load,
        }

    @staticmethod
    def get_class_timetable_matrix(class_obj, day=None):
        """Convert timetable entries into a matrix format for easier display."""
        timetable_entries = Timetable.objects.filter(
            class_obj=class_obj, is_active=True
        ).select_related("subject", "teacher", "time_slot", "teacher__user")

        if day is not None:
            timetable_entries = timetable_entries.filter(time_slot__day_of_week=day)

        # Create a matrix of days and time slots
        timetable_matrix = {}

        for entry in timetable_entries:
            day = entry.time_slot.day_of_week
            time_slot_id = entry.time_slot.id

            if day not in timetable_matrix:
                timetable_matrix[day] = {}

            timetable_matrix[day][time_slot_id] = entry

        return timetable_matrix

    @staticmethod
    def calculate_subject_hours(timetable_entries):
        """Calculate hours per subject from timetable entries."""
        subject_hours = {}

        for entry in timetable_entries:
            subject_name = entry.subject.name
            hours = entry.time_slot.duration_minutes / 60

            if subject_name in subject_hours:
                subject_hours[subject_name] += hours
            else:
                subject_hours[subject_name] = hours

        return subject_hours
