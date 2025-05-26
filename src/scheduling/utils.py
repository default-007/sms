"""
Utility functions for the scheduling module
"""

from datetime import datetime, time, timedelta, date
from typing import List, Dict, Tuple, Optional, Any
from django.db.models import Q, Count, Sum
from django.utils import timezone
import calendar
import json

from .models import TimeSlot, Timetable, Room
from academics.models import Term, Class, Grade
from teachers.models import Teacher
from subjects.models import Subject


class TimetableGenerator:
    """Utility class for generating timetable templates and structures"""

    @staticmethod
    def generate_standard_time_slots(
        start_time: time = time(8, 0),
        end_time: time = time(15, 30),
        period_duration: int = 45,
        break_duration: int = 15,
        lunch_duration: int = 45,
        lunch_after_period: int = 4,
        days: List[int] = None,
    ) -> List[Dict]:
        """
        Generate standard time slots for a school

        Args:
            start_time: School start time
            end_time: School end time
            period_duration: Duration of each period in minutes
            break_duration: Duration of breaks in minutes
            lunch_duration: Duration of lunch break in minutes
            lunch_after_period: Lunch break after which period
            days: List of days (0=Monday, 6=Sunday)

        Returns:
            List of time slot data dictionaries
        """
        if days is None:
            days = [0, 1, 2, 3, 4]  # Monday to Friday

        slots = []

        for day in days:
            current_time = start_time
            period_number = 1

            while True:
                # Calculate period end time
                period_end = TimetableGenerator._add_minutes_to_time(
                    current_time, period_duration
                )

                if period_end > end_time:
                    break

                # Add period
                slots.append(
                    {
                        "day_of_week": day,
                        "start_time": current_time,
                        "end_time": period_end,
                        "duration_minutes": period_duration,
                        "period_number": period_number,
                        "name": f"Period {period_number}",
                        "is_break": False,
                    }
                )

                current_time = period_end

                # Add break
                if period_number == lunch_after_period:
                    # Lunch break
                    break_end = TimetableGenerator._add_minutes_to_time(
                        current_time, lunch_duration
                    )
                    if break_end <= end_time:
                        slots.append(
                            {
                                "day_of_week": day,
                                "start_time": current_time,
                                "end_time": break_end,
                                "duration_minutes": lunch_duration,
                                "period_number": period_number,
                                "name": "Lunch Break",
                                "is_break": True,
                            }
                        )
                        current_time = break_end
                else:
                    # Regular break
                    break_end = TimetableGenerator._add_minutes_to_time(
                        current_time, break_duration
                    )
                    if break_end <= end_time:
                        slots.append(
                            {
                                "day_of_week": day,
                                "start_time": current_time,
                                "end_time": break_end,
                                "duration_minutes": break_duration,
                                "period_number": period_number,
                                "name": f"Break {period_number}",
                                "is_break": True,
                            }
                        )
                        current_time = break_end

                period_number += 1

                # Safety check
                if period_number > 20:
                    break

        return slots

    @staticmethod
    def _add_minutes_to_time(time_obj: time, minutes: int) -> time:
        """Add minutes to a time object"""
        dt = datetime.combine(date.today(), time_obj)
        dt += timedelta(minutes=minutes)
        return dt.time()

    @staticmethod
    def create_class_timetable_template(
        grade: Grade, subjects: List[Subject], periods_per_week: Dict[str, int] = None
    ) -> Dict:
        """
        Create a timetable template for a class/grade

        Args:
            grade: Grade object
            subjects: List of subjects to include
            periods_per_week: Dictionary mapping subject names to periods per week

        Returns:
            Timetable template dictionary
        """
        if periods_per_week is None:
            periods_per_week = {
                "Mathematics": 6,
                "English": 5,
                "Science": 5,
                "Social Studies": 4,
                "Physical Education": 3,
                "Art": 2,
                "Music": 2,
            }

        template = {
            "grade": str(grade),
            "subjects": [],
            "total_periods_per_week": 0,
            "distribution": {},
        }

        for subject in subjects:
            periods = periods_per_week.get(subject.name, 4)
            template["subjects"].append(
                {
                    "subject": subject.name,
                    "periods_per_week": periods,
                    "credit_hours": getattr(subject, "credit_hours", periods),
                }
            )
            template["total_periods_per_week"] += periods

        # Suggest distribution across days
        total_periods = template["total_periods_per_week"]
        periods_per_day = total_periods // 5  # 5 working days
        remainder = total_periods % 5

        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
        for i, day in enumerate(days):
            daily_periods = periods_per_day + (1 if i < remainder else 0)
            template["distribution"][day] = daily_periods

        return template


class ConflictResolver:
    """Utility class for resolving scheduling conflicts"""

    @staticmethod
    def find_alternative_slots(
        teacher: Teacher,
        subject: Subject,
        class_obj: Class,
        term: Term,
        preferred_days: List[int] = None,
        exclude_periods: List[int] = None,
    ) -> List[TimeSlot]:
        """
        Find alternative time slots for a conflicting assignment

        Args:
            teacher: Teacher object
            subject: Subject object
            class_obj: Class object
            term: Term object
            preferred_days: Preferred days of week
            exclude_periods: Periods to exclude

        Returns:
            List of available time slots
        """
        available_slots = []

        # Get all active time slots
        query = TimeSlot.objects.filter(is_active=True, is_break=False)

        if preferred_days:
            query = query.filter(day_of_week__in=preferred_days)

        if exclude_periods:
            query = query.exclude(period_number__in=exclude_periods)

        for slot in query:
            # Check if slot is available for teacher
            teacher_conflict = Timetable.objects.filter(
                teacher=teacher, time_slot=slot, term=term, is_active=True
            ).exists()

            # Check if slot is available for class
            class_conflict = Timetable.objects.filter(
                class_assigned=class_obj, time_slot=slot, term=term, is_active=True
            ).exists()

            if not teacher_conflict and not class_conflict:
                available_slots.append(slot)

        return available_slots

    @staticmethod
    def suggest_room_alternatives(
        time_slot: TimeSlot, term: Term, subject: Subject, min_capacity: int = None
    ) -> List[Room]:
        """
        Suggest alternative rooms for a time slot

        Args:
            time_slot: TimeSlot object
            term: Term object
            subject: Subject object
            min_capacity: Minimum room capacity required

        Returns:
            List of available rooms
        """
        # Room type preferences by subject
        subject_room_preferences = {
            "physics": ["laboratory", "classroom"],
            "chemistry": ["laboratory", "classroom"],
            "biology": ["laboratory", "classroom"],
            "computer": ["computer_lab", "classroom"],
            "physical education": ["gymnasium", "outdoor"],
            "music": ["music_room", "classroom"],
            "art": ["art_room", "classroom"],
        }

        subject_lower = subject.name.lower()
        preferred_types = ["classroom"]  # Default

        for key, types in subject_room_preferences.items():
            if key in subject_lower:
                preferred_types = types
                break

        # Find available rooms
        available_rooms = Room.objects.filter(is_available=True)

        if min_capacity:
            available_rooms = available_rooms.filter(capacity__gte=min_capacity)

        # Exclude rooms already booked at this time
        booked_rooms = Timetable.objects.filter(
            time_slot=time_slot, term=term, is_active=True, room__isnull=False
        ).values_list("room_id", flat=True)

        available_rooms = available_rooms.exclude(id__in=booked_rooms)

        # Sort by preference
        preferred_rooms = available_rooms.filter(room_type__in=preferred_types)
        other_rooms = available_rooms.exclude(room_type__in=preferred_types)

        return list(preferred_rooms) + list(other_rooms)


class ScheduleAnalyzer:
    """Utility class for analyzing schedules"""

    @staticmethod
    def analyze_teacher_schedule_balance(teacher: Teacher, term: Term) -> Dict:
        """
        Analyze teacher's schedule balance

        Args:
            teacher: Teacher object
            term: Term object

        Returns:
            Dictionary with balance analysis
        """
        timetables = Timetable.objects.filter(
            teacher=teacher, term=term, is_active=True
        )

        # Count periods per day
        daily_counts = {}
        for day in range(7):  # 0-6 for Monday-Sunday
            count = timetables.filter(time_slot__day_of_week=day).count()
            if count > 0:
                day_name = calendar.day_name[day]
                daily_counts[day_name] = count

        if not daily_counts:
            return {
                "total_periods": 0,
                "working_days": 0,
                "balance_score": 1.0,
                "recommendation": "No schedule assigned",
            }

        total_periods = sum(daily_counts.values())
        working_days = len(daily_counts)
        avg_periods_per_day = total_periods / working_days

        # Calculate balance score (1.0 = perfect balance, 0.0 = very unbalanced)
        max_periods = max(daily_counts.values())
        min_periods = min(daily_counts.values())

        if max_periods == 0:
            balance_score = 1.0
        else:
            balance_score = 1.0 - ((max_periods - min_periods) / max_periods)

        # Generate recommendation
        if balance_score >= 0.8:
            recommendation = "Well balanced schedule"
        elif balance_score >= 0.6:
            recommendation = "Moderately balanced, minor adjustments possible"
        else:
            recommendation = "Unbalanced schedule, consider redistribution"

        return {
            "total_periods": total_periods,
            "working_days": working_days,
            "avg_periods_per_day": round(avg_periods_per_day, 1),
            "daily_counts": daily_counts,
            "balance_score": round(balance_score, 2),
            "recommendation": recommendation,
        }

    @staticmethod
    def find_schedule_gaps(class_obj: Class, term: Term) -> List[Dict]:
        """
        Find gaps in class schedule

        Args:
            class_obj: Class object
            term: Term object

        Returns:
            List of schedule gaps
        """
        gaps = []

        # Get all time slots grouped by day
        for day in range(5):  # Monday to Friday
            day_slots = TimeSlot.objects.filter(
                day_of_week=day, is_active=True, is_break=False
            ).order_by("period_number")

            scheduled_periods = set(
                Timetable.objects.filter(
                    class_assigned=class_obj,
                    term=term,
                    time_slot__day_of_week=day,
                    is_active=True,
                ).values_list("time_slot__period_number", flat=True)
            )

            for slot in day_slots:
                if slot.period_number not in scheduled_periods:
                    gaps.append(
                        {
                            "day": calendar.day_name[day],
                            "day_of_week": day,
                            "period_number": slot.period_number,
                            "time_slot": slot,
                            "time_range": f"{slot.start_time} - {slot.end_time}",
                        }
                    )

        return gaps

    @staticmethod
    def calculate_utilization_metrics(term: Term) -> Dict:
        """
        Calculate overall utilization metrics for a term

        Args:
            term: Term object

        Returns:
            Dictionary with utilization metrics
        """
        # Total possible time slots
        total_time_slots = TimeSlot.objects.filter(
            is_active=True, is_break=False
        ).count()

        # Total classes
        total_classes = Class.objects.filter(academic_year=term.academic_year).count()

        # Total possible assignments
        total_possible = total_time_slots * total_classes

        # Actual assignments
        actual_assignments = Timetable.objects.filter(term=term, is_active=True).count()

        # Room utilization
        total_rooms = Room.objects.filter(is_available=True).count()
        room_assignments = Timetable.objects.filter(
            term=term, is_active=True, room__isnull=False
        ).count()

        # Teacher utilization
        active_teachers = Teacher.objects.filter(status="active").count()
        teaching_assignments = (
            Timetable.objects.filter(term=term, is_active=True)
            .values("teacher")
            .distinct()
            .count()
        )

        return {
            "schedule_utilization": {
                "total_possible_assignments": total_possible,
                "actual_assignments": actual_assignments,
                "utilization_percentage": round(
                    (
                        (actual_assignments / total_possible * 100)
                        if total_possible > 0
                        else 0
                    ),
                    1,
                ),
            },
            "room_utilization": {
                "total_rooms": total_rooms,
                "rooms_in_use": room_assignments,
                "utilization_percentage": round(
                    (room_assignments / total_rooms * 100) if total_rooms > 0 else 0, 1
                ),
            },
            "teacher_utilization": {
                "total_teachers": active_teachers,
                "teachers_assigned": teaching_assignments,
                "utilization_percentage": round(
                    (
                        (teaching_assignments / active_teachers * 100)
                        if active_teachers > 0
                        else 0
                    ),
                    1,
                ),
            },
        }


class ScheduleExporter:
    """Utility class for exporting schedules in various formats"""

    @staticmethod
    def export_class_schedule_csv(class_obj: Class, term: Term) -> str:
        """
        Export class schedule as CSV string

        Args:
            class_obj: Class object
            term: Term object

        Returns:
            CSV string
        """
        from io import StringIO
        import csv

        output = StringIO()
        writer = csv.writer(output)

        # Header
        writer.writerow(
            ["Day", "Period", "Start Time", "End Time", "Subject", "Teacher", "Room"]
        )

        # Get timetable data
        timetables = (
            Timetable.objects.filter(
                class_assigned=class_obj, term=term, is_active=True
            )
            .select_related("time_slot", "subject", "teacher", "room")
            .order_by("time_slot__day_of_week", "time_slot__period_number")
        )

        for timetable in timetables:
            writer.writerow(
                [
                    calendar.day_name[timetable.time_slot.day_of_week],
                    timetable.time_slot.period_number,
                    timetable.time_slot.start_time,
                    timetable.time_slot.end_time,
                    timetable.subject.name,
                    timetable.teacher.user.get_full_name(),
                    timetable.room.number if timetable.room else "TBD",
                ]
            )

        return output.getvalue()

    @staticmethod
    def export_teacher_schedule_json(teacher: Teacher, term: Term) -> str:
        """
        Export teacher schedule as JSON string

        Args:
            teacher: Teacher object
            term: Term object

        Returns:
            JSON string
        """
        timetables = (
            Timetable.objects.filter(teacher=teacher, term=term, is_active=True)
            .select_related("time_slot", "subject", "class_assigned", "room")
            .order_by("time_slot__day_of_week", "time_slot__period_number")
        )

        schedule_data = {
            "teacher": {
                "name": teacher.user.get_full_name(),
                "employee_id": teacher.employee_id,
            },
            "term": str(term),
            "schedule": [],
        }

        for timetable in timetables:
            schedule_data["schedule"].append(
                {
                    "day": calendar.day_name[timetable.time_slot.day_of_week],
                    "day_of_week": timetable.time_slot.day_of_week,
                    "period": timetable.time_slot.period_number,
                    "start_time": str(timetable.time_slot.start_time),
                    "end_time": str(timetable.time_slot.end_time),
                    "subject": timetable.subject.name,
                    "class": str(timetable.class_assigned),
                    "room": timetable.room.number if timetable.room else None,
                }
            )

        return json.dumps(schedule_data, indent=2)


class ScheduleValidator:
    """Utility class for validating schedules"""

    @staticmethod
    def validate_term_schedule(term: Term) -> Dict:
        """
        Validate entire term schedule

        Args:
            term: Term object

        Returns:
            Validation results dictionary
        """
        issues = []
        warnings = []

        # Check for conflicts
        teacher_conflicts = ScheduleValidator._check_teacher_conflicts(term)
        room_conflicts = ScheduleValidator._check_room_conflicts(term)

        issues.extend(teacher_conflicts)
        issues.extend(room_conflicts)

        # Check for unassigned rooms
        unassigned_rooms = Timetable.objects.filter(
            term=term, is_active=True, room__isnull=True
        ).count()

        if unassigned_rooms > 0:
            warnings.append(
                f"{unassigned_rooms} timetable entries without room assignments"
            )

        # Check teacher workload balance
        workload_issues = ScheduleValidator._check_workload_balance(term)
        warnings.extend(workload_issues)

        return {
            "is_valid": len(issues) == 0,
            "issues": issues,
            "warnings": warnings,
            "total_issues": len(issues),
            "total_warnings": len(warnings),
        }

    @staticmethod
    def _check_teacher_conflicts(term: Term) -> List[str]:
        """Check for teacher double bookings"""
        conflicts = []

        # Find teacher conflicts by grouping by teacher and time slot
        from django.db.models import Count

        conflict_entries = (
            Timetable.objects.filter(term=term, is_active=True)
            .values("teacher", "time_slot")
            .annotate(count=Count("id"))
            .filter(count__gt=1)
        )

        for entry in conflict_entries:
            teacher = Teacher.objects.get(id=entry["teacher"])
            time_slot = TimeSlot.objects.get(id=entry["time_slot"])
            conflicts.append(
                f"Teacher {teacher.user.get_full_name()} has {entry['count']} "
                f"assignments at {time_slot}"
            )

        return conflicts

    @staticmethod
    def _check_room_conflicts(term: Term) -> List[str]:
        """Check for room double bookings"""
        conflicts = []

        from django.db.models import Count

        conflict_entries = (
            Timetable.objects.filter(term=term, is_active=True, room__isnull=False)
            .values("room", "time_slot")
            .annotate(count=Count("id"))
            .filter(count__gt=1)
        )

        for entry in conflict_entries:
            room = Room.objects.get(id=entry["room"])
            time_slot = TimeSlot.objects.get(id=entry["time_slot"])
            conflicts.append(
                f"Room {room.number} has {entry['count']} " f"bookings at {time_slot}"
            )

        return conflicts

    @staticmethod
    def _check_workload_balance(term: Term) -> List[str]:
        """Check for workload imbalances"""
        warnings = []

        # Calculate average periods per teacher
        teacher_workloads = {}

        for timetable in Timetable.objects.filter(term=term, is_active=True):
            teacher_id = timetable.teacher.id
            if teacher_id not in teacher_workloads:
                teacher_workloads[teacher_id] = {
                    "teacher": timetable.teacher,
                    "periods": 0,
                }
            teacher_workloads[teacher_id]["periods"] += 1

        if not teacher_workloads:
            return warnings

        # Calculate statistics
        periods_list = [data["periods"] for data in teacher_workloads.values()]
        avg_periods = sum(periods_list) / len(periods_list)
        max_periods = max(periods_list)
        min_periods = min(periods_list)

        # Flag extreme imbalances
        threshold = avg_periods * 0.5  # 50% deviation

        for data in teacher_workloads.values():
            if abs(data["periods"] - avg_periods) > threshold:
                if data["periods"] > avg_periods:
                    warnings.append(
                        f"Teacher {data['teacher'].user.get_full_name()} "
                        f"has high workload: {data['periods']} periods "
                        f"(average: {avg_periods:.1f})"
                    )
                else:
                    warnings.append(
                        f"Teacher {data['teacher'].user.get_full_name()} "
                        f"has low workload: {data['periods']} periods "
                        f"(average: {avg_periods:.1f})"
                    )

        return warnings


# Utility functions for common operations
def get_working_days_in_term(term: Term) -> int:
    """Calculate number of working days in a term"""
    start_date = term.start_date
    end_date = term.end_date

    working_days = 0
    current_date = start_date

    while current_date <= end_date:
        # Assuming Monday-Friday are working days (0-4)
        if current_date.weekday() < 5:
            working_days += 1
        current_date += timedelta(days=1)

    return working_days


def format_time_range(start_time: time, end_time: time) -> str:
    """Format time range as string"""
    return f"{start_time.strftime('%H:%M')} - {end_time.strftime('%H:%M')}"


def calculate_period_overlap(
    period1: Tuple[time, time], period2: Tuple[time, time]
) -> bool:
    """Check if two time periods overlap"""
    start1, end1 = period1
    start2, end2 = period2

    return start1 < end2 and start2 < end1


def get_next_available_period(
    time_slot: TimeSlot, duration: int = 45
) -> Optional[TimeSlot]:
    """Get the next available period after a given time slot"""
    next_period = (
        TimeSlot.objects.filter(
            day_of_week=time_slot.day_of_week,
            period_number__gt=time_slot.period_number,
            is_active=True,
        )
        .order_by("period_number")
        .first()
    )

    return next_period
