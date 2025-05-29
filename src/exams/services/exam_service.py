"""
School Management System - Exam Services
File: src/exams/services/exam_service.py
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Avg, Count, F, Max, Min, Q, Sum
from django.utils import timezone

from src.academics.models import AcademicYear, Class, Term
from src.students.models import Student
from src.teachers.models import Teacher

from ..models import (
    Exam,
    ExamQuestion,
    ExamSchedule,
    ExamType,
    GradingSystem,
    OnlineExam,
    ReportCard,
    StudentExamResult,
)


class ExamService:
    """Service class for exam management operations"""

    @staticmethod
    def create_exam(exam_data: Dict) -> Exam:
        """Create a new exam with validation"""
        with transaction.atomic():
            exam = Exam.objects.create(**exam_data)
            exam.total_students = ExamService._calculate_total_students(exam)
            exam.save()
            return exam

    @staticmethod
    def _calculate_total_students(exam: Exam) -> int:
        """Calculate total students for an exam across all classes"""
        return Student.objects.filter(
            current_class__academic_year=exam.academic_year, status="ACTIVE"
        ).count()

    @staticmethod
    def schedule_exam_for_classes(
        exam: Exam, schedule_data: List[Dict]
    ) -> List[ExamSchedule]:
        """Create exam schedules for multiple classes and subjects"""
        schedules = []

        with transaction.atomic():
            for data in schedule_data:
                # Validate no conflicts
                if ExamService._has_scheduling_conflict(data):
                    raise ValidationError(
                        f"Scheduling conflict for {data['subject']} on {data['date']}"
                    )

                schedule = ExamSchedule.objects.create(exam=exam, **data)
                schedules.append(schedule)

        return schedules

    @staticmethod
    def _has_scheduling_conflict(schedule_data: Dict) -> bool:
        """Check for scheduling conflicts"""
        overlapping = ExamSchedule.objects.filter(
            Q(supervisor=schedule_data.get("supervisor"))
            | Q(room=schedule_data.get("room"))
            | Q(class_obj=schedule_data.get("class_obj")),
            date=schedule_data["date"],
            start_time__lt=schedule_data["end_time"],
            end_time__gt=schedule_data["start_time"],
            is_active=True,
        ).exists()

        return overlapping

    @staticmethod
    def publish_exam(exam_id: str) -> Exam:
        """Publish exam to make it visible to students"""
        exam = Exam.objects.get(id=exam_id)
        exam.is_published = True
        exam.status = "SCHEDULED"
        exam.save()
        return exam

    @staticmethod
    def get_exam_analytics(exam_id: str) -> Dict:
        """Get comprehensive analytics for an exam"""
        exam = Exam.objects.get(id=exam_id)

        results = StudentExamResult.objects.filter(
            exam_schedule__exam=exam
        ).select_related("student", "exam_schedule__subject")

        analytics = {
            "exam_info": {
                "name": exam.name,
                "total_students": exam.total_students,
                "completed_count": exam.completed_count,
                "completion_rate": exam.completion_rate,
                "status": exam.status,
            },
            "performance_summary": ExamService._calculate_performance_summary(results),
            "subject_wise_analysis": ExamService._get_subject_wise_analysis(results),
            "grade_distribution": ExamService._get_grade_distribution(results),
            "class_comparison": ExamService._get_class_comparison(exam),
            "top_performers": ExamService._get_top_performers(results),
            "improvement_areas": ExamService._identify_improvement_areas(results),
        }

        return analytics

    @staticmethod
    def _calculate_performance_summary(results) -> Dict:
        """Calculate overall performance summary"""
        if not results.exists():
            return {}

        summary = results.aggregate(
            avg_percentage=Avg("percentage"),
            highest_percentage=Max("percentage"),
            lowest_percentage=Min("percentage"),
            pass_count=Count("id", filter=Q(is_pass=True)),
            total_count=Count("id"),
        )

        summary["pass_rate"] = (
            (summary["pass_count"] / summary["total_count"] * 100)
            if summary["total_count"] > 0
            else 0
        )

        return summary

    @staticmethod
    def _get_subject_wise_analysis(results) -> List[Dict]:
        """Analyze performance by subject"""
        subject_analysis = []

        subjects = (
            results.values("exam_schedule__subject__name")
            .annotate(
                avg_marks=Avg("marks_obtained"),
                avg_percentage=Avg("percentage"),
                total_marks=F("exam_schedule__total_marks"),
                pass_count=Count("id", filter=Q(is_pass=True)),
                total_attempts=Count("id"),
                highest_marks=Max("marks_obtained"),
                lowest_marks=Min("marks_obtained"),
            )
            .order_by("-avg_percentage")
        )

        for subject in subjects:
            subject["pass_rate"] = (
                (subject["pass_count"] / subject["total_attempts"] * 100)
                if subject["total_attempts"] > 0
                else 0
            )
            subject_analysis.append(subject)

        return subject_analysis

    @staticmethod
    def _get_grade_distribution(results) -> Dict:
        """Get distribution of grades"""
        distribution = (
            results.values("grade").annotate(count=Count("id")).order_by("grade")
        )

        return {item["grade"]: item["count"] for item in distribution}

    @staticmethod
    def _get_class_comparison(exam: Exam) -> List[Dict]:
        """Compare performance across classes"""
        class_performance = []

        classes = ExamSchedule.objects.filter(exam=exam).values("class_obj").distinct()

        for class_data in classes:
            class_obj = Class.objects.get(id=class_data["class_obj"])
            class_results = StudentExamResult.objects.filter(
                exam_schedule__exam=exam, exam_schedule__class_obj=class_obj
            )

            if class_results.exists():
                performance = class_results.aggregate(
                    avg_percentage=Avg("percentage"),
                    pass_rate=Count("id", filter=Q(is_pass=True)) * 100.0 / Count("id"),
                    student_count=Count("student", distinct=True),
                )

                performance["class_name"] = str(class_obj)
                class_performance.append(performance)

        return sorted(
            class_performance, key=lambda x: x["avg_percentage"], reverse=True
        )

    @staticmethod
    def _get_top_performers(results, limit: int = 10) -> List[Dict]:
        """Get top performing students"""
        top_performers = (
            results.values(
                "student__user__first_name",
                "student__user__last_name",
                "student__admission_number",
                "exam_schedule__class_obj__name",
            )
            .annotate(
                avg_percentage=Avg("percentage"),
                total_marks_obtained=Sum("marks_obtained"),
                subjects_count=Count("exam_schedule__subject", distinct=True),
            )
            .order_by("-avg_percentage")[:limit]
        )

        return list(top_performers)

    @staticmethod
    def _identify_improvement_areas(results) -> List[Dict]:
        """Identify subjects/areas needing improvement"""
        poor_performance = (
            results.filter(percentage__lt=50)
            .values("exam_schedule__subject__name")
            .annotate(poor_count=Count("id"), avg_percentage=Avg("percentage"))
            .order_by("avg_percentage")
        )

        return list(poor_performance)


class ResultService:
    """Service for managing exam results"""

    @staticmethod
    def enter_results(
        exam_schedule_id: str, results_data: List[Dict], entered_by
    ) -> List[StudentExamResult]:
        """Bulk entry of exam results"""
        results = []

        with transaction.atomic():
            exam_schedule = ExamSchedule.objects.get(id=exam_schedule_id)

            for data in results_data:
                student = Student.objects.get(id=data["student_id"])

                result, created = StudentExamResult.objects.update_or_create(
                    student=student,
                    exam_schedule=exam_schedule,
                    defaults={
                        "marks_obtained": data["marks_obtained"],
                        "is_absent": data.get("is_absent", False),
                        "remarks": data.get("remarks", ""),
                        "entered_by": entered_by,
                        "term": exam_schedule.exam.term,
                    },
                )
                results.append(result)

            # Update completion count
            ResultService._update_exam_completion_count(exam_schedule.exam)

            # Calculate rankings
            ResultService._calculate_rankings(exam_schedule)

        return results

    @staticmethod
    def _update_exam_completion_count(exam: Exam):
        """Update exam completion statistics"""
        total_schedules = exam.schedules.count()
        completed_schedules = exam.schedules.filter(is_completed=True).count()

        if total_schedules > 0:
            exam.completed_count = int(
                (completed_schedules / total_schedules) * exam.total_students
            )
            exam.save()

    @staticmethod
    def _calculate_rankings(exam_schedule: ExamSchedule):
        """Calculate rankings for an exam schedule"""
        results = StudentExamResult.objects.filter(
            exam_schedule=exam_schedule, is_absent=False
        ).order_by("-percentage")

        # Class rankings
        for i, result in enumerate(results, 1):
            result.class_rank = i
            result.save(update_fields=["class_rank"])

        # Grade rankings
        grade_results = StudentExamResult.objects.filter(
            exam_schedule__exam=exam_schedule.exam,
            student__current_class__grade=exam_schedule.class_obj.grade,
            is_absent=False,
        ).order_by("-percentage")

        for i, result in enumerate(grade_results, 1):
            result.grade_rank = i
            result.save(update_fields=["grade_rank"])

    @staticmethod
    def generate_report_cards(
        term_id: str, class_ids: List[str] = None
    ) -> List[ReportCard]:
        """Generate report cards for a term"""
        term = Term.objects.get(id=term_id)

        if class_ids:
            classes = Class.objects.filter(id__in=class_ids)
        else:
            classes = Class.objects.filter(academic_year=term.academic_year)

        report_cards = []

        with transaction.atomic():
            for class_obj in classes:
                students = Student.objects.filter(
                    current_class=class_obj, status="ACTIVE"
                )

                for student in students:
                    report_card = ResultService._generate_student_report_card(
                        student, term, class_obj
                    )
                    if report_card:
                        report_cards.append(report_card)

        return report_cards

    @staticmethod
    def _generate_student_report_card(
        student: Student, term: Term, class_obj: Class
    ) -> Optional[ReportCard]:
        """Generate report card for individual student"""
        results = StudentExamResult.objects.filter(
            student=student, term=term, exam_schedule__class_obj=class_obj
        )

        if not results.exists():
            return None

        # Calculate aggregates
        totals = results.aggregate(
            total_marks=Sum("exam_schedule__total_marks"),
            marks_obtained=Sum("marks_obtained"),
            avg_percentage=Avg("percentage"),
        )

        # Get attendance data
        attendance_data = ResultService._get_attendance_data(student, term)

        # Calculate rankings
        rankings = ResultService._calculate_student_rankings(student, term, class_obj)

        report_card, created = ReportCard.objects.update_or_create(
            student=student,
            class_obj=class_obj,
            academic_year=term.academic_year,
            term=term,
            defaults={
                "total_marks": totals["total_marks"] or 0,
                "marks_obtained": totals["marks_obtained"] or 0,
                "percentage": totals["avg_percentage"] or 0,
                "grade": ResultService._calculate_overall_grade(
                    totals["avg_percentage"]
                ),
                "grade_point_average": ResultService._calculate_gpa(results),
                "class_rank": rankings["class_rank"],
                "class_size": rankings["class_size"],
                "grade_rank": rankings.get("grade_rank"),
                "grade_size": rankings.get("grade_size"),
                "attendance_percentage": attendance_data["percentage"],
                "days_present": attendance_data["present"],
                "days_absent": attendance_data["absent"],
                "total_days": attendance_data["total"],
                "status": "PUBLISHED",
            },
        )

        return report_card

    @staticmethod
    def _get_attendance_data(student: Student, term: Term) -> Dict:
        """Get attendance data for student in term"""
        from attendance.models import Attendance

        attendance_records = Attendance.objects.filter(student=student, term=term)

        total_days = attendance_records.count()
        present_days = attendance_records.filter(status="PRESENT").count()
        absent_days = total_days - present_days

        percentage = (present_days / total_days * 100) if total_days > 0 else 100

        return {
            "total": total_days,
            "present": present_days,
            "absent": absent_days,
            "percentage": round(percentage, 2),
        }

    @staticmethod
    def _calculate_student_rankings(
        student: Student, term: Term, class_obj: Class
    ) -> Dict:
        """Calculate student rankings in class and grade"""
        # Class ranking
        class_averages = (
            ReportCard.objects.filter(class_obj=class_obj, term=term)
            .order_by("-percentage")
            .values_list("percentage", flat=True)
        )

        student_percentage = ReportCard.objects.filter(
            student=student, term=term
        ).first()

        if student_percentage:
            class_rank = list(class_averages).index(student_percentage.percentage) + 1
        else:
            class_rank = len(class_averages) + 1

        rankings = {"class_rank": class_rank, "class_size": len(class_averages)}

        # Grade ranking
        grade_averages = (
            ReportCard.objects.filter(class_obj__grade=class_obj.grade, term=term)
            .order_by("-percentage")
            .values_list("percentage", flat=True)
        )

        if student_percentage:
            grade_rank = list(grade_averages).index(student_percentage.percentage) + 1
            rankings.update(
                {"grade_rank": grade_rank, "grade_size": len(grade_averages)}
            )

        return rankings

    @staticmethod
    def _calculate_overall_grade(percentage: Optional[float]) -> str:
        """Calculate overall letter grade"""
        if not percentage:
            return "F"

        if percentage >= 90:
            return "A+"
        elif percentage >= 80:
            return "A"
        elif percentage >= 70:
            return "B+"
        elif percentage >= 60:
            return "B"
        elif percentage >= 50:
            return "C+"
        elif percentage >= 40:
            return "C"
        elif percentage >= 30:
            return "D"
        else:
            return "F"

    @staticmethod
    def _calculate_gpa(results) -> Decimal:
        """Calculate GPA based on grade points"""
        grade_points = {
            "A+": 4.0,
            "A": 3.7,
            "B+": 3.3,
            "B": 3.0,
            "C+": 2.7,
            "C": 2.3,
            "D": 2.0,
            "F": 0.0,
        }

        total_points = 0
        total_subjects = 0

        for result in results:
            points = grade_points.get(result.grade, 0.0)
            total_points += points
            total_subjects += 1

        return (
            Decimal(str(total_points / total_subjects))
            if total_subjects > 0
            else Decimal("0.0")
        )


class OnlineExamService:
    """Service for online exam management"""

    @staticmethod
    def create_online_exam(exam_schedule_id: str, config_data: Dict) -> OnlineExam:
        """Create online exam configuration"""
        exam_schedule = ExamSchedule.objects.get(id=exam_schedule_id)

        online_exam = OnlineExam.objects.create(
            exam_schedule=exam_schedule, **config_data
        )

        return online_exam

    @staticmethod
    def add_questions_to_exam(
        online_exam_id: str, question_configs: List[Dict]
    ) -> OnlineExam:
        """Add questions to online exam"""
        from ..models import OnlineExamQuestion

        online_exam = OnlineExam.objects.get(id=online_exam_id)

        with transaction.atomic():
            # Clear existing questions
            OnlineExamQuestion.objects.filter(online_exam=online_exam).delete()

            for config in question_configs:
                OnlineExamQuestion.objects.create(
                    online_exam=online_exam,
                    question_id=config["question_id"],
                    order=config["order"],
                    marks=config.get("marks", config["question"].marks),
                )

        return online_exam

    @staticmethod
    def auto_select_questions(
        online_exam_id: str, criteria: Dict
    ) -> List[ExamQuestion]:
        """Auto-select questions based on criteria"""
        online_exam = OnlineExam.objects.get(id=online_exam_id)
        subject = online_exam.exam_schedule.subject
        grade = online_exam.exam_schedule.class_obj.grade

        questions = ExamQuestion.objects.filter(
            subject=subject, grade=grade, is_active=True
        )

        # Apply filters from criteria
        if "difficulty_distribution" in criteria:
            selected_questions = []
            for difficulty, count in criteria["difficulty_distribution"].items():
                difficulty_questions = questions.filter(
                    difficulty_level=difficulty.upper()
                ).order_by("?")[:count]
                selected_questions.extend(difficulty_questions)

        elif "total_questions" in criteria:
            selected_questions = questions.order_by("?")[: criteria["total_questions"]]

        else:
            selected_questions = list(
                questions.order_by("?")[:20]
            )  # Default 20 questions

        # Create question assignments
        question_configs = []
        for i, question in enumerate(selected_questions, 1):
            question_configs.append(
                {"question_id": question.id, "order": i, "marks": question.marks}
            )

        OnlineExamService.add_questions_to_exam(online_exam_id, question_configs)

        return selected_questions
