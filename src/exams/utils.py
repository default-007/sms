"""
School Management System - Exam Utilities
File: src/exams/utils.py
"""

from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from django.utils import timezone
from django.db.models import Q
import uuid
import random
import string

from .models import (
    ExamSchedule,
    StudentExamResult,
    ExamQuestion,
    OnlineExam,
    StudentOnlineExamAttempt,
)


class ExamUtils:
    """Utility functions for exam operations"""

    @staticmethod
    def generate_exam_code(length: int = 8) -> str:
        """Generate unique exam access code"""
        while True:
            code = "".join(
                random.choices(string.ascii_uppercase + string.digits, k=length)
            )
            if not OnlineExam.objects.filter(access_code=code).exists():
                return code

    @staticmethod
    def check_exam_conflicts(
        date: datetime.date,
        start_time: datetime.time,
        end_time: datetime.time,
        teacher_id: Optional[str] = None,
        room: Optional[str] = None,
        class_id: Optional[str] = None,
        exclude_schedule_id: Optional[str] = None,
    ) -> List[Dict]:
        """Check for exam scheduling conflicts"""
        conflicts = []

        # Base query for overlapping time slots
        conflicting_schedules = ExamSchedule.objects.filter(
            date=date, start_time__lt=end_time, end_time__gt=start_time, is_active=True
        )

        if exclude_schedule_id:
            conflicting_schedules = conflicting_schedules.exclude(
                id=exclude_schedule_id
            )

        # Check teacher conflicts
        if teacher_id:
            teacher_conflicts = conflicting_schedules.filter(
                Q(supervisor_id=teacher_id) | Q(additional_supervisors__id=teacher_id)
            )

            for conflict in teacher_conflicts:
                conflicts.append(
                    {
                        "type": "teacher",
                        "message": f"Teacher has another exam: {conflict.exam.name} - {conflict.subject.name}",
                        "schedule_id": str(conflict.id),
                    }
                )

        # Check room conflicts
        if room:
            room_conflicts = conflicting_schedules.filter(room=room)

            for conflict in room_conflicts:
                conflicts.append(
                    {
                        "type": "room",
                        "message": f"Room {room} is occupied: {conflict.exam.name} - {conflict.subject.name}",
                        "schedule_id": str(conflict.id),
                    }
                )

        # Check class conflicts
        if class_id:
            class_conflicts = conflicting_schedules.filter(class_obj_id=class_id)

            for conflict in class_conflicts:
                conflicts.append(
                    {
                        "type": "class",
                        "message": f"Class has another exam: {conflict.exam.name} - {conflict.subject.name}",
                        "schedule_id": str(conflict.id),
                    }
                )

        return conflicts

    @staticmethod
    def calculate_grade_statistics(results_queryset) -> Dict:
        """Calculate comprehensive grade statistics"""
        if not results_queryset.exists():
            return {}

        total_results = results_queryset.count()
        results_list = list(results_queryset.values_list("percentage", flat=True))

        # Basic statistics
        mean_percentage = sum(results_list) / len(results_list)
        sorted_results = sorted(results_list)

        # Median
        n = len(sorted_results)
        median = (sorted_results[n // 2] + sorted_results[(n - 1) // 2]) / 2

        # Standard deviation
        variance = sum((x - mean_percentage) ** 2 for x in results_list) / len(
            results_list
        )
        std_deviation = variance**0.5

        # Quartiles
        q1_index = n // 4
        q3_index = 3 * n // 4
        q1 = sorted_results[q1_index] if q1_index < n else sorted_results[-1]
        q3 = sorted_results[q3_index] if q3_index < n else sorted_results[-1]

        return {
            "total_count": total_results,
            "mean": round(mean_percentage, 2),
            "median": round(median, 2),
            "std_deviation": round(std_deviation, 2),
            "min_score": min(results_list),
            "max_score": max(results_list),
            "q1": round(q1, 2),
            "q3": round(q3, 2),
            "iqr": round(q3 - q1, 2),
        }

    @staticmethod
    def generate_difficulty_analysis(subject_id: str, grade_id: str) -> Dict:
        """Analyze question difficulty based on student performance"""
        questions = ExamQuestion.objects.filter(
            subject_id=subject_id, grade_id=grade_id, is_active=True
        )

        analysis = {}

        for question in questions:
            # This would require analyzing actual student responses
            # For now, providing structure for implementation
            analysis[str(question.id)] = {
                "question_text": question.question_text[:100],
                "marked_difficulty": question.difficulty_level,
                "actual_difficulty": "MODERATE",  # Would be calculated from responses
                "success_rate": 0.0,  # Would be calculated from correct responses
                "discrimination_index": 0.0,  # Ability to discriminate between high/low performers
                "usage_count": question.usage_count,
            }

        return analysis

    @staticmethod
    def optimize_exam_schedule(
        exam_id: str,
        preferred_dates: List[datetime.date],
        time_slots: List[Tuple[datetime.time, datetime.time]],
        constraints: Dict,
    ) -> List[Dict]:
        """Optimize exam scheduling based on constraints"""
        from .models import Exam

        exam = Exam.objects.get(id=exam_id)
        suggested_schedules = []

        # Get all required class-subject combinations
        required_schedules = constraints.get("required_schedules", [])

        for schedule_req in required_schedules:
            class_id = schedule_req["class_id"]
            subject_id = schedule_req["subject_id"]

            # Find optimal time slot
            for date in preferred_dates:
                for start_time, end_time in time_slots:
                    conflicts = ExamUtils.check_exam_conflicts(
                        date=date,
                        start_time=start_time,
                        end_time=end_time,
                        class_id=class_id,
                    )

                    if not conflicts:
                        suggested_schedules.append(
                            {
                                "class_id": class_id,
                                "subject_id": subject_id,
                                "date": date,
                                "start_time": start_time,
                                "end_time": end_time,
                                "conflicts": [],
                            }
                        )
                        break

                if suggested_schedules:
                    break

        return suggested_schedules

    @staticmethod
    def validate_online_exam_configuration(config: Dict) -> Tuple[bool, List[str]]:
        """Validate online exam configuration"""
        errors = []

        # Check required fields
        required_fields = ["time_limit_minutes", "max_attempts"]
        for field in required_fields:
            if field not in config or config[field] is None:
                errors.append(f"Missing required field: {field}")

        # Validate time limit
        if "time_limit_minutes" in config:
            time_limit = config["time_limit_minutes"]
            if not isinstance(time_limit, int) or time_limit <= 0:
                errors.append("Time limit must be a positive integer")
            elif time_limit > 300:  # 5 hours max
                errors.append("Time limit cannot exceed 5 hours (300 minutes)")

        # Validate max attempts
        if "max_attempts" in config:
            max_attempts = config["max_attempts"]
            if not isinstance(max_attempts, int) or max_attempts <= 0:
                errors.append("Max attempts must be a positive integer")
            elif max_attempts > 5:
                errors.append("Max attempts cannot exceed 5")

        # Validate IP restrictions format
        if "ip_restrictions" in config and config["ip_restrictions"]:
            ip_list = config["ip_restrictions"].split(",")
            for ip in ip_list:
                ip = ip.strip()
                # Basic IP validation (simplified)
                parts = ip.split(".")
                if len(parts) != 4:
                    errors.append(f"Invalid IP address format: {ip}")
                else:
                    try:
                        for part in parts:
                            if not 0 <= int(part) <= 255:
                                errors.append(f"Invalid IP address: {ip}")
                                break
                    except ValueError:
                        errors.append(f"Invalid IP address: {ip}")

        return len(errors) == 0, errors

    @staticmethod
    def calculate_exam_completion_time(
        start_time: datetime, end_time: datetime
    ) -> Dict:
        """Calculate time-related metrics for exam completion"""
        if not end_time or not start_time:
            return {}

        duration = end_time - start_time
        total_seconds = duration.total_seconds()

        return {
            "total_seconds": int(total_seconds),
            "total_minutes": int(total_seconds / 60),
            "hours": int(total_seconds // 3600),
            "minutes": int((total_seconds % 3600) // 60),
            "formatted_duration": f"{int(total_seconds // 3600):02d}:{int((total_seconds % 3600) // 60):02d}:{int(total_seconds % 60):02d}",
        }

    @staticmethod
    def generate_exam_summary_report(exam_id: str) -> Dict:
        """Generate comprehensive exam summary report"""
        from .models import Exam
        from .services.analytics_service import ExamAnalyticsService

        exam = Exam.objects.get(id=exam_id)
        analytics = ExamAnalyticsService.get_exam_analytics(exam_id)

        # Get additional summary data
        schedules = exam.schedules.all().select_related("subject", "class_obj")
        total_students = sum(
            schedule.class_obj.students.filter(status="ACTIVE").count()
            for schedule in schedules
        )

        results = StudentExamResult.objects.filter(exam_schedule__exam=exam)

        summary = {
            "exam_details": {
                "name": exam.name,
                "type": exam.exam_type.name,
                "academic_year": exam.academic_year.name,
                "term": exam.term.name,
                "duration": f"{exam.start_date} to {exam.end_date}",
                "status": exam.status,
            },
            "participation": {
                "total_eligible_students": total_students,
                "total_attempts": results.count(),
                "attendance_rate": (
                    (
                        (results.count() - results.filter(is_absent=True).count())
                        / results.count()
                        * 100
                    )
                    if results.count() > 0
                    else 0
                ),
            },
            "performance_overview": analytics.get("performance_summary", {}),
            "subject_breakdown": analytics.get("subject_wise_analysis", []),
            "recommendations": analytics.get("improvement_recommendations", []),
        }

        return summary
