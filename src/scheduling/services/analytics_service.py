from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from django.db.models import Avg, Count, F, Q
from django.db.models.functions import TruncDate

from academics.models import Class, Grade, Term
from subjects.models import Subject
from teachers.models import Teacher

from ..models import Room, SubstituteTeacher, TimeSlot, Timetable


class SchedulingAnalyticsService:
    """Analytics service for scheduling module"""

    @staticmethod
    def get_teacher_workload_analytics(term: Term, teacher: Teacher = None) -> Dict:
        """Analyze teacher workload distribution"""

        query = Timetable.objects.filter(term=term, is_active=True)
        if teacher:
            query = query.filter(teacher=teacher)

        # Basic workload stats
        workload_data = (
            query.values(
                "teacher__id", "teacher__user__first_name", "teacher__user__last_name"
            )
            .annotate(
                total_periods=Count("id"),
                unique_classes=Count("class_assigned", distinct=True),
                unique_subjects=Count("subject", distinct=True),
            )
            .order_by("-total_periods")
        )

        # Calculate periods per day for each teacher
        teacher_daily_load = {}
        for entry in query.select_related("teacher", "time_slot"):
            teacher_id = entry.teacher.id
            day = entry.time_slot.day_of_week

            if teacher_id not in teacher_daily_load:
                teacher_daily_load[teacher_id] = defaultdict(int)
            teacher_daily_load[teacher_id][day] += 1

        # Calculate balance metrics
        for teacher_data in workload_data:
            teacher_id = teacher_data["teacher__id"]
            daily_loads = list(teacher_daily_load.get(teacher_id, {}).values())

            if daily_loads:
                teacher_data["max_daily_periods"] = max(daily_loads)
                teacher_data["min_daily_periods"] = min(daily_loads)
                teacher_data["avg_daily_periods"] = sum(daily_loads) / len(daily_loads)
                teacher_data["workload_balance"] = (
                    1 - ((max(daily_loads) - min(daily_loads)) / max(daily_loads))
                    if max(daily_loads) > 0
                    else 1
                )
            else:
                teacher_data.update(
                    {
                        "max_daily_periods": 0,
                        "min_daily_periods": 0,
                        "avg_daily_periods": 0,
                        "workload_balance": 1,
                    }
                )

        # Overall statistics
        total_teachers = len(workload_data)
        avg_periods_per_teacher = (
            sum(t["total_periods"] for t in workload_data) / total_teachers
            if total_teachers > 0
            else 0
        )
        workload_variance = (
            sum(
                (t["total_periods"] - avg_periods_per_teacher) ** 2
                for t in workload_data
            )
            / total_teachers
            if total_teachers > 0
            else 0
        )

        return {
            "teacher_workloads": list(workload_data),
            "summary": {
                "total_teachers": total_teachers,
                "average_periods_per_teacher": round(avg_periods_per_teacher, 2),
                "workload_variance": round(workload_variance, 2),
                "most_loaded_teacher": (
                    max(workload_data, key=lambda x: x["total_periods"])
                    if workload_data
                    else None
                ),
                "least_loaded_teacher": (
                    min(workload_data, key=lambda x: x["total_periods"])
                    if workload_data
                    else None
                ),
            },
        }

    @staticmethod
    def get_room_utilization_analytics(term: Term) -> Dict:
        """Analyze room utilization patterns"""

        # Total available periods per week
        total_time_slots = TimeSlot.objects.filter(
            is_active=True, is_break=False
        ).count()

        # Room utilization data
        room_usage = (
            Timetable.objects.filter(term=term, is_active=True)
            .values(
                "room__id",
                "room__number",
                "room__name",
                "room__room_type",
                "room__capacity",
            )
            .annotate(
                periods_used=Count("id"),
                unique_classes=Count("class_assigned", distinct=True),
                unique_subjects=Count("subject", distinct=True),
            )
            .order_by("-periods_used")
        )

        # Calculate utilization percentages
        for room_data in room_usage:
            utilization_rate = (
                (room_data["periods_used"] / total_time_slots * 100)
                if total_time_slots > 0
                else 0
            )
            room_data["utilization_rate"] = round(utilization_rate, 2)
            room_data["free_periods"] = total_time_slots - room_data["periods_used"]

        # Room type analysis
        room_type_usage = (
            Timetable.objects.filter(term=term, is_active=True)
            .values("room__room_type")
            .annotate(total_usage=Count("id"), avg_utilization=Avg("room__capacity"))
            .order_by("-total_usage")
        )

        # Peak usage times
        peak_usage = (
            Timetable.objects.filter(term=term, is_active=True)
            .values("time_slot__day_of_week", "time_slot__period_number")
            .annotate(rooms_used=Count("room", distinct=True))
            .order_by("-rooms_used")
        )

        return {
            "room_utilization": list(room_usage),
            "room_type_analysis": list(room_type_usage),
            "peak_usage_times": list(peak_usage),
            "summary": {
                "total_rooms_in_use": len(room_usage),
                "average_utilization_rate": (
                    sum(r["utilization_rate"] for r in room_usage) / len(room_usage)
                    if room_usage
                    else 0
                ),
                "most_used_room": (
                    max(room_usage, key=lambda x: x["periods_used"])
                    if room_usage
                    else None
                ),
                "least_used_room": (
                    min(room_usage, key=lambda x: x["periods_used"])
                    if room_usage
                    else None
                ),
            },
        }

    @staticmethod
    def get_scheduling_conflicts_analytics(term: Term) -> Dict:
        """Analyze scheduling conflicts and issues"""

        # Teacher double bookings
        teacher_conflicts = (
            Timetable.objects.filter(term=term, is_active=True)
            .values("teacher", "time_slot__day_of_week", "time_slot__period_number")
            .annotate(conflict_count=Count("id"))
            .filter(conflict_count__gt=1)
            .select_related("teacher")
        )

        # Room double bookings
        room_conflicts = (
            Timetable.objects.filter(term=term, is_active=True, room__isnull=False)
            .values("room", "time_slot__day_of_week", "time_slot__period_number")
            .annotate(conflict_count=Count("id"))
            .filter(conflict_count__gt=1)
        )

        # Classes without rooms
        unassigned_rooms = Timetable.objects.filter(
            term=term, is_active=True, room__isnull=True
        ).count()

        # Substitute teacher frequency
        substitute_frequency = (
            SubstituteTeacher.objects.filter(
                original_timetable__term=term,
                date__gte=term.start_date,
                date__lte=term.end_date,
            )
            .values(
                "substitute_teacher__user__first_name",
                "substitute_teacher__user__last_name",
            )
            .annotate(substitute_count=Count("id"))
            .order_by("-substitute_count")
        )

        return {
            "teacher_conflicts": len(teacher_conflicts),
            "room_conflicts": len(room_conflicts),
            "unassigned_rooms": unassigned_rooms,
            "substitute_frequency": list(substitute_frequency),
            "conflict_details": {
                "teacher_double_bookings": list(teacher_conflicts),
                "room_double_bookings": list(room_conflicts),
            },
        }

    @staticmethod
    def get_subject_distribution_analytics(term: Term) -> Dict:
        """Analyze subject distribution across time slots"""

        # Subject scheduling patterns
        subject_timing = (
            Timetable.objects.filter(term=term, is_active=True)
            .values("subject__name", "time_slot__period_number")
            .annotate(frequency=Count("id"))
            .order_by("subject__name", "time_slot__period_number")
        )

        # Organize by subject
        subject_patterns = defaultdict(dict)
        for entry in subject_timing:
            subject_name = entry["subject__name"]
            period = entry["time_slot__period_number"]
            frequency = entry["frequency"]
            subject_patterns[subject_name][f"period_{period}"] = frequency

        # Daily distribution
        daily_distribution = (
            Timetable.objects.filter(term=term, is_active=True)
            .values("time_slot__day_of_week", "subject__name")
            .annotate(count=Count("id"))
            .order_by("time_slot__day_of_week")
        )

        # Subject load per grade
        grade_subject_load = (
            Timetable.objects.filter(term=term, is_active=True)
            .values("class_assigned__grade__name", "subject__name")
            .annotate(periods_per_week=Count("id"))
            .order_by("class_assigned__grade__name", "-periods_per_week")
        )

        return {
            "subject_timing_patterns": dict(subject_patterns),
            "daily_distribution": list(daily_distribution),
            "grade_subject_distribution": list(grade_subject_load),
            "summary": {
                "total_subjects": len(subject_patterns),
                "most_scheduled_periods": (
                    max(sum(periods.values()) for periods in subject_patterns.values())
                    if subject_patterns
                    else 0
                ),
            },
        }

    @staticmethod
    def get_timetable_optimization_score(term: Term) -> Dict:
        """Calculate overall timetable optimization score"""

        total_score = 0
        max_score = 0
        breakdown = {}

        # 1. Workload balance (25 points)
        workload_analytics = SchedulingAnalyticsService.get_teacher_workload_analytics(
            term
        )
        avg_balance = (
            sum(
                t.get("workload_balance", 0)
                for t in workload_analytics["teacher_workloads"]
            )
            / len(workload_analytics["teacher_workloads"])
            if workload_analytics["teacher_workloads"]
            else 0
        )

        workload_score = avg_balance * 25
        total_score += workload_score
        max_score += 25
        breakdown["workload_balance"] = round(workload_score, 2)

        # 2. Room utilization efficiency (20 points)
        room_analytics = SchedulingAnalyticsService.get_room_utilization_analytics(term)
        avg_utilization = room_analytics["summary"]["average_utilization_rate"]
        # Optimal utilization is around 70-85%
        if 70 <= avg_utilization <= 85:
            utilization_score = 20
        elif avg_utilization > 85:
            utilization_score = 20 - ((avg_utilization - 85) * 0.5)
        else:
            utilization_score = (avg_utilization / 70) * 20

        total_score += utilization_score
        max_score += 20
        breakdown["room_utilization"] = round(utilization_score, 2)

        # 3. Conflict minimization (25 points)
        conflict_analytics = (
            SchedulingAnalyticsService.get_scheduling_conflicts_analytics(term)
        )
        total_conflicts = (
            conflict_analytics["teacher_conflicts"]
            + conflict_analytics["room_conflicts"]
        )
        total_timetable_entries = Timetable.objects.filter(
            term=term, is_active=True
        ).count()

        if total_timetable_entries > 0:
            conflict_rate = total_conflicts / total_timetable_entries
            conflict_score = max(0, 25 - (conflict_rate * 100))
        else:
            conflict_score = 25

        total_score += conflict_score
        max_score += 25
        breakdown["conflict_minimization"] = round(conflict_score, 2)

        # 4. Subject distribution (15 points)
        subject_analytics = (
            SchedulingAnalyticsService.get_subject_distribution_analytics(term)
        )
        # Calculate how well core subjects are distributed in morning periods
        morning_periods = [1, 2, 3]
        core_subjects = ["mathematics", "english", "science"]

        core_morning_count = (
            Timetable.objects.filter(
                term=term, is_active=True, time_slot__period_number__in=morning_periods
            )
            .filter(
                Q(subject__name__icontains="math")
                | Q(subject__name__icontains="english")
                | Q(subject__name__icontains="science")
            )
            .count()
        )

        total_core_periods = (
            Timetable.objects.filter(term=term, is_active=True)
            .filter(
                Q(subject__name__icontains="math")
                | Q(subject__name__icontains="english")
                | Q(subject__name__icontains="science")
            )
            .count()
        )

        if total_core_periods > 0:
            morning_ratio = core_morning_count / total_core_periods
            distribution_score = morning_ratio * 15
        else:
            distribution_score = 15

        total_score += distribution_score
        max_score += 15
        breakdown["subject_distribution"] = round(distribution_score, 2)

        # 5. Room assignment completeness (15 points)
        total_entries = Timetable.objects.filter(term=term, is_active=True).count()
        assigned_rooms = Timetable.objects.filter(
            term=term, is_active=True, room__isnull=False
        ).count()

        if total_entries > 0:
            room_assignment_rate = assigned_rooms / total_entries
            room_assignment_score = room_assignment_rate * 15
        else:
            room_assignment_score = 15

        total_score += room_assignment_score
        max_score += 15
        breakdown["room_assignment"] = round(room_assignment_score, 2)

        # Calculate final score
        optimization_score = (total_score / max_score * 100) if max_score > 0 else 0

        return {
            "overall_score": round(optimization_score, 2),
            "grade": SchedulingAnalyticsService._get_grade_from_score(
                optimization_score
            ),
            "breakdown": breakdown,
            "recommendations": SchedulingAnalyticsService._generate_recommendations(
                breakdown
            ),
        }

    @staticmethod
    def _get_grade_from_score(score: float) -> str:
        """Convert numeric score to letter grade"""
        if score >= 90:
            return "A"
        elif score >= 80:
            return "B"
        elif score >= 70:
            return "C"
        elif score >= 60:
            return "D"
        else:
            return "F"

    @staticmethod
    def _generate_recommendations(breakdown: Dict) -> List[str]:
        """Generate recommendations based on score breakdown"""
        recommendations = []

        if breakdown["workload_balance"] < 20:
            recommendations.append(
                "Consider redistributing teaching load more evenly across teachers"
            )

        if breakdown["room_utilization"] < 15:
            recommendations.append(
                "Optimize room usage - some rooms may be underutilized while others are overcrowded"
            )

        if breakdown["conflict_minimization"] < 20:
            recommendations.append(
                "Address scheduling conflicts - multiple teachers or rooms double-booked"
            )

        if breakdown["subject_distribution"] < 12:
            recommendations.append(
                "Schedule core subjects (Math, English, Science) in morning periods for better learning"
            )

        if breakdown["room_assignment"] < 12:
            recommendations.append(
                "Assign rooms to all timetable entries to avoid confusion"
            )

        return recommendations

    @staticmethod
    def get_time_slot_popularity(term: Term) -> Dict:
        """Analyze which time slots are most/least popular"""

        slot_usage = (
            Timetable.objects.filter(term=term, is_active=True)
            .values(
                "time_slot__day_of_week",
                "time_slot__period_number",
                "time_slot__start_time",
                "time_slot__end_time",
            )
            .annotate(
                usage_count=Count("id"),
                unique_teachers=Count("teacher", distinct=True),
                unique_subjects=Count("subject", distinct=True),
            )
            .order_by("time_slot__day_of_week", "time_slot__period_number")
        )

        # Add day names
        day_names = [
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday",
            "Saturday",
            "Sunday",
        ]
        for slot in slot_usage:
            slot["day_name"] = day_names[slot["time_slot__day_of_week"]]

        return {
            "time_slot_usage": list(slot_usage),
            "most_popular_slot": (
                max(slot_usage, key=lambda x: x["usage_count"]) if slot_usage else None
            ),
            "least_popular_slot": (
                min(slot_usage, key=lambda x: x["usage_count"]) if slot_usage else None
            ),
        }

    @staticmethod
    def get_class_schedule_density(term: Term) -> Dict:
        """Analyze schedule density for each class"""

        class_density = (
            Timetable.objects.filter(term=term, is_active=True)
            .values(
                "class_assigned__id",
                "class_assigned__grade__name",
                "class_assigned__name",
            )
            .annotate(
                total_periods=Count("id"),
                free_periods=Count("time_slot") - Count("id"),
                unique_subjects=Count("subject", distinct=True),
            )
            .order_by("-total_periods")
        )

        # Calculate periods per day for each class
        for class_data in class_density:
            class_id = class_data["class_assigned__id"]
            daily_periods = (
                Timetable.objects.filter(
                    term=term, is_active=True, class_assigned__id=class_id
                )
                .values("time_slot__day_of_week")
                .annotate(periods_per_day=Count("id"))
                .values_list("periods_per_day", flat=True)
            )

            if daily_periods:
                class_data["max_daily_periods"] = max(daily_periods)
                class_data["min_daily_periods"] = min(daily_periods)
                class_data["avg_daily_periods"] = sum(daily_periods) / len(
                    daily_periods
                )
            else:
                class_data.update(
                    {
                        "max_daily_periods": 0,
                        "min_daily_periods": 0,
                        "avg_daily_periods": 0,
                    }
                )

        return {
            "class_schedule_density": list(class_density),
            "busiest_class": (
                max(class_density, key=lambda x: x["total_periods"])
                if class_density
                else None
            ),
            "lightest_class": (
                min(class_density, key=lambda x: x["total_periods"])
                if class_density
                else None
            ),
        }
