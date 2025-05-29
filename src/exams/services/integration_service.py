"""
School Management System - Exam Integration Services
File: src/exams/services/integration_service.py
"""

from decimal import Decimal
from typing import Any, Dict, List, Optional

from django.db.models import Avg, Count, Q, Sum
from django.utils import timezone

from academics.models import AcademicYear, Class, Term
from attendance.models import Attendance
from finance.models import FeeStructure, Invoice
from students.models import Student
from teachers.models import Teacher

from ..models import (
    Exam,
    ExamQuestion,
    ExamSchedule,
    OnlineExam,
    ReportCard,
    StudentExamResult,
)


class ExamIntegrationService:
    """Service for integrating exam data with other modules"""

    @staticmethod
    def get_student_academic_profile(student_id: str) -> Dict:
        """Get comprehensive academic profile for a student"""
        student = Student.objects.get(id=student_id)

        # Get all exam results
        results = StudentExamResult.objects.filter(student=student).select_related(
            "exam_schedule__subject", "exam_schedule__exam", "term"
        )

        # Get report cards
        report_cards = ReportCard.objects.filter(student=student).order_by(
            "-academic_year__start_date", "-term__term_number"
        )

        # Calculate academic metrics
        total_results = results.count()
        if total_results > 0:
            avg_percentage = results.aggregate(avg=Avg("percentage"))["avg"]
            pass_rate = (results.filter(is_pass=True).count() / total_results) * 100
        else:
            avg_percentage = 0
            pass_rate = 0

        # Subject-wise performance
        subject_performance = (
            results.values("exam_schedule__subject__name")
            .annotate(
                avg_marks=Avg("marks_obtained"),
                avg_percentage=Avg("percentage"),
                total_exams=Count("id"),
                pass_count=Count("id", filter=Q(is_pass=True)),
            )
            .order_by("-avg_percentage")
        )

        # Term-wise progression
        term_progression = (
            results.values(
                "term__name", "term__term_number", "term__academic_year__name"
            )
            .annotate(
                avg_percentage=Avg("percentage"),
                total_subjects=Count("exam_schedule__subject", distinct=True),
            )
            .order_by("term__academic_year__start_date", "term__term_number")
        )

        return {
            "student_info": {
                "id": student.id,
                "name": student.user.get_full_name(),
                "admission_number": student.admission_number,
                "current_class": str(student.current_class),
                "status": student.status,
            },
            "academic_summary": {
                "total_exams": total_results,
                "average_percentage": round(avg_percentage or 0, 2),
                "pass_rate": round(pass_rate, 2),
                "total_report_cards": report_cards.count(),
            },
            "subject_performance": list(subject_performance),
            "term_progression": list(term_progression),
            "recent_results": ExamIntegrationService._get_recent_results(student, 5),
            "achievements": ExamIntegrationService._get_student_achievements(student),
            "improvement_areas": ExamIntegrationService._get_improvement_areas(student),
        }

    @staticmethod
    def _get_recent_results(student: Student, limit: int = 5) -> List[Dict]:
        """Get recent exam results for student"""
        recent_results = (
            StudentExamResult.objects.filter(student=student)
            .select_related("exam_schedule__exam", "exam_schedule__subject")
            .order_by("-entry_date")[:limit]
        )

        return [
            {
                "exam_name": result.exam_schedule.exam.name,
                "subject": result.exam_schedule.subject.name,
                "marks_obtained": float(result.marks_obtained),
                "total_marks": result.exam_schedule.total_marks,
                "percentage": float(result.percentage),
                "grade": result.grade,
                "date": result.entry_date.date(),
            }
            for result in recent_results
        ]

    @staticmethod
    def _get_student_achievements(student: Student) -> List[Dict]:
        """Get student achievements and recognitions"""
        achievements = []

        # Top ranks in exams
        top_ranks = StudentExamResult.objects.filter(
            student=student, class_rank__lte=3, is_absent=False
        ).select_related("exam_schedule__exam", "exam_schedule__subject")

        for result in top_ranks:
            achievements.append(
                {
                    "type": "academic_rank",
                    "title": f"Rank {result.class_rank} in {result.exam_schedule.subject.name}",
                    "description": f"{result.exam_schedule.exam.name} - {result.percentage:.1f}%",
                    "date": result.entry_date.date(),
                }
            )

        # High percentage achievements
        high_scores = StudentExamResult.objects.filter(
            student=student, percentage__gte=90, is_absent=False
        ).select_related("exam_schedule__exam", "exam_schedule__subject")

        for result in high_scores:
            achievements.append(
                {
                    "type": "high_score",
                    "title": f"Excellent Performance in {result.exam_schedule.subject.name}",
                    "description": f"Scored {result.percentage:.1f}% in {result.exam_schedule.exam.name}",
                    "date": result.entry_date.date(),
                }
            )

        return sorted(achievements, key=lambda x: x["date"], reverse=True)[:10]

    @staticmethod
    def _get_improvement_areas(student: Student) -> List[Dict]:
        """Identify areas where student needs improvement"""
        improvement_areas = []

        # Subjects with low average performance
        subject_averages = (
            StudentExamResult.objects.filter(student=student, is_absent=False)
            .values("exam_schedule__subject__name")
            .annotate(
                avg_percentage=Avg("percentage"),
                total_exams=Count("id"),
                fail_count=Count("id", filter=Q(is_pass=False)),
            )
            .filter(avg_percentage__lt=60)
        )

        for subject_data in subject_averages:
            improvement_areas.append(
                {
                    "area": "subject_performance",
                    "subject": subject_data["exam_schedule__subject__name"],
                    "average": round(subject_data["avg_percentage"], 2),
                    "recommendation": f"Focus on improving {subject_data['exam_schedule__subject__name']} fundamentals",
                }
            )

        # Declining performance trend
        recent_results = StudentExamResult.objects.filter(
            student=student, is_absent=False
        ).order_by("-entry_date")[:6]

        if len(recent_results) >= 4:
            recent_avg = sum(r.percentage for r in recent_results[:3]) / 3
            older_avg = sum(r.percentage for r in recent_results[3:6]) / 3

            if recent_avg < older_avg - 5:  # 5% decline
                improvement_areas.append(
                    {
                        "area": "performance_trend",
                        "trend": "declining",
                        "change": round(recent_avg - older_avg, 2),
                        "recommendation": "Recent performance shows declining trend. Consider additional support.",
                    }
                )

        return improvement_areas

    @staticmethod
    def get_teacher_exam_workload(
        teacher_id: str, academic_year_id: str = None
    ) -> Dict:
        """Get teacher's exam-related workload and performance"""
        teacher = Teacher.objects.get(id=teacher_id)

        # Filter by academic year if provided
        schedules_filter = {"supervisor": teacher}
        if academic_year_id:
            schedules_filter["exam__academic_year_id"] = academic_year_id

        # Get supervised exam schedules
        schedules = ExamSchedule.objects.filter(**schedules_filter).select_related(
            "exam", "subject", "class_obj"
        )

        # Get results for supervised exams
        results = StudentExamResult.objects.filter(exam_schedule__supervisor=teacher)

        if academic_year_id:
            results = results.filter(
                exam_schedule__exam__academic_year_id=academic_year_id
            )

        # Calculate performance metrics
        total_students = results.count()
        if total_students > 0:
            avg_performance = results.aggregate(avg=Avg("percentage"))["avg"]
            pass_rate = (results.filter(is_pass=True).count() / total_students) * 100
        else:
            avg_performance = 0
            pass_rate = 0

        # Subject-wise analysis
        subject_analysis = (
            results.values("exam_schedule__subject__name")
            .annotate(
                student_count=Count("student", distinct=True),
                avg_performance=Avg("percentage"),
                pass_rate=Count("id", filter=Q(is_pass=True)) * 100.0 / Count("id"),
            )
            .order_by("-avg_performance")
        )

        # Exam schedule summary
        schedule_summary = schedules.values("exam__name", "exam__status").annotate(
            total_schedules=Count("id"),
            completed_schedules=Count("id", filter=Q(is_completed=True)),
        )

        return {
            "teacher_info": {
                "id": teacher.id,
                "name": teacher.user.get_full_name(),
                "employee_id": teacher.employee_id,
            },
            "workload_summary": {
                "total_exams_supervised": schedules.values("exam").distinct().count(),
                "total_schedules": schedules.count(),
                "completed_schedules": schedules.filter(is_completed=True).count(),
                "students_assessed": total_students,
                "subjects_taught": schedules.values("subject").distinct().count(),
            },
            "performance_metrics": {
                "average_student_performance": round(avg_performance or 0, 2),
                "pass_rate": round(pass_rate, 2),
                "effectiveness_score": ExamIntegrationService._calculate_teacher_effectiveness(
                    teacher, results
                ),
            },
            "subject_analysis": list(subject_analysis),
            "schedule_summary": list(schedule_summary),
        }

    @staticmethod
    def _calculate_teacher_effectiveness(teacher: Teacher, results) -> float:
        """Calculate teacher effectiveness score based on student results"""
        if not results.exists():
            return 0.0

        # Factors for effectiveness:
        # 1. Average student performance (40%)
        # 2. Pass rate (30%)
        # 3. Improvement in student performance (20%)
        # 4. Consistency across subjects (10%)

        avg_performance = results.aggregate(avg=Avg("percentage"))["avg"] or 0
        pass_rate = (results.filter(is_pass=True).count() / results.count()) * 100

        # Simplified effectiveness calculation
        performance_score = min(avg_performance / 100, 1.0) * 40
        pass_rate_score = min(pass_rate / 100, 1.0) * 30

        # For now, assuming neutral improvement and consistency scores
        improvement_score = 15  # 20% * 0.75 (assumed average)
        consistency_score = 7.5  # 10% * 0.75 (assumed average)

        total_score = (
            performance_score + pass_rate_score + improvement_score + consistency_score
        )
        return round(total_score, 2)

    @staticmethod
    def get_class_academic_dashboard(class_id: str, term_id: str = None) -> Dict:
        """Get comprehensive academic dashboard for a class"""
        class_obj = Class.objects.get(id=class_id)

        # Filter results by term if provided
        results_filter = {"exam_schedule__class_obj": class_obj}
        if term_id:
            results_filter["term_id"] = term_id

        results = StudentExamResult.objects.filter(**results_filter)
        students = class_obj.students.filter(status="ACTIVE")

        # Performance metrics
        total_results = results.count()
        if total_results > 0:
            avg_performance = results.aggregate(avg=Avg("percentage"))["avg"]
            pass_rate = (results.filter(is_pass=True).count() / total_results) * 100
        else:
            avg_performance = 0
            pass_rate = 0

        # Subject-wise performance
        subject_performance = (
            results.values("exam_schedule__subject__name")
            .annotate(
                avg_percentage=Avg("percentage"),
                total_students=Count("student", distinct=True),
                pass_count=Count("id", filter=Q(is_pass=True)),
                total_attempts=Count("id"),
            )
            .order_by("-avg_percentage")
        )

        # Student rankings
        student_rankings = (
            results.values(
                "student__user__first_name",
                "student__user__last_name",
                "student__admission_number",
            )
            .annotate(
                avg_percentage=Avg("percentage"),
                total_exams=Count("id"),
                pass_count=Count("id", filter=Q(is_pass=True)),
            )
            .order_by("-avg_percentage")[:10]
        )

        # Attendance integration
        attendance_data = ExamIntegrationService._get_class_attendance_summary(
            class_obj, term_id
        )

        return {
            "class_info": {
                "id": class_obj.id,
                "name": str(class_obj),
                "grade": class_obj.grade.name,
                "section": class_obj.grade.section.name,
                "class_teacher": (
                    class_obj.class_teacher.user.get_full_name()
                    if class_obj.class_teacher
                    else None
                ),
                "total_students": students.count(),
            },
            "performance_summary": {
                "average_performance": round(avg_performance or 0, 2),
                "pass_rate": round(pass_rate, 2),
                "total_exams": results.values("exam_schedule__exam").distinct().count(),
                "total_results": total_results,
            },
            "subject_performance": list(subject_performance),
            "top_performers": list(student_rankings),
            "attendance_summary": attendance_data,
            "improvement_recommendations": ExamIntegrationService._get_class_recommendations(
                class_obj, results
            ),
        }

    @staticmethod
    def _get_class_attendance_summary(class_obj: Class, term_id: str = None) -> Dict:
        """Get attendance summary for class"""
        try:
            attendance_filter = {"student__current_class": class_obj}
            if term_id:
                attendance_filter["term_id"] = term_id

            attendance_records = Attendance.objects.filter(**attendance_filter)

            if attendance_records.exists():
                total_days = attendance_records.values("date").distinct().count()
                present_count = attendance_records.filter(status="PRESENT").count()
                total_records = attendance_records.count()

                attendance_rate = (
                    (present_count / total_records * 100) if total_records > 0 else 0
                )

                return {
                    "total_days": total_days,
                    "attendance_rate": round(attendance_rate, 2),
                    "total_records": total_records,
                }
        except:
            pass

        return {"total_days": 0, "attendance_rate": 0, "total_records": 0}

    @staticmethod
    def _get_class_recommendations(class_obj: Class, results) -> List[Dict]:
        """Generate recommendations for class improvement"""
        recommendations = []

        if not results.exists():
            return recommendations

        # Low performing subjects
        subject_performance = (
            results.values("exam_schedule__subject__name")
            .annotate(avg_percentage=Avg("percentage"))
            .filter(avg_percentage__lt=60)
        )

        for subject in subject_performance:
            recommendations.append(
                {
                    "type": "subject_improvement",
                    "priority": "high",
                    "area": subject["exam_schedule__subject__name"],
                    "issue": f"Low average performance ({subject['avg_percentage']:.1f}%)",
                    "recommendation": f"Focus on {subject['exam_schedule__subject__name']} fundamentals and provide additional practice",
                }
            )

        # Low pass rate
        overall_pass_rate = (
            results.filter(is_pass=True).count() / results.count()
        ) * 100
        if overall_pass_rate < 70:
            recommendations.append(
                {
                    "type": "pass_rate",
                    "priority": "high",
                    "area": "Overall Performance",
                    "issue": f"Low class pass rate ({overall_pass_rate:.1f}%)",
                    "recommendation": "Implement remedial classes and individual student support programs",
                }
            )

        return recommendations

    @staticmethod
    def sync_with_finance_module(student_id: str, academic_year_id: str) -> Dict:
        """Sync exam performance with finance module for scholarship eligibility"""
        try:
            student = Student.objects.get(id=student_id)

            # Get student's academic performance
            results = StudentExamResult.objects.filter(
                student=student,
                exam_schedule__exam__academic_year_id=academic_year_id,
                is_absent=False,
            )

            if not results.exists():
                return {
                    "eligible_for_scholarship": False,
                    "reason": "No exam results found",
                }

            avg_percentage = results.aggregate(avg=Avg("percentage"))["avg"]

            # Check scholarship eligibility based on performance
            scholarship_eligible = False
            scholarship_type = None

            if avg_percentage >= 95:
                scholarship_eligible = True
                scholarship_type = "Excellence Scholarship"
            elif avg_percentage >= 85:
                scholarship_eligible = True
                scholarship_type = "Merit Scholarship"
            elif avg_percentage >= 75:
                # Check for improvement-based scholarship
                prev_year_results = StudentExamResult.objects.filter(
                    student=student,
                    exam_schedule__exam__academic_year__start_date__lt=timezone.now().date()
                    - timezone.timedelta(days=365),
                    is_absent=False,
                )

                if prev_year_results.exists():
                    prev_avg = prev_year_results.aggregate(avg=Avg("percentage"))["avg"]
                    if avg_percentage > prev_avg + 10:  # 10% improvement
                        scholarship_eligible = True
                        scholarship_type = "Improvement Scholarship"

            return {
                "eligible_for_scholarship": scholarship_eligible,
                "scholarship_type": scholarship_type,
                "current_average": round(avg_percentage, 2),
                "total_exams": results.count(),
                "academic_year_id": academic_year_id,
            }

        except Exception as e:
            return {"error": str(e)}

    @staticmethod
    def get_exam_question_analytics(
        subject_id: str = None, grade_id: str = None
    ) -> Dict:
        """Get analytics for exam questions to optimize question bank"""
        questions_filter = {"is_active": True}
        if subject_id:
            questions_filter["subject_id"] = subject_id
        if grade_id:
            questions_filter["grade_id"] = grade_id

        questions = ExamQuestion.objects.filter(**questions_filter)

        # Question type distribution
        type_distribution = (
            questions.values("question_type")
            .annotate(count=Count("id"))
            .order_by("-count")
        )

        # Difficulty distribution
        difficulty_distribution = (
            questions.values("difficulty_level")
            .annotate(count=Count("id"))
            .order_by("-count")
        )

        # Usage statistics
        usage_stats = questions.aggregate(
            total_questions=Count("id"),
            avg_usage=Avg("usage_count"),
            max_usage=Count("usage_count"),
            unused_questions=Count("id", filter=Q(usage_count=0)),
        )

        # Most used questions
        popular_questions = (
            questions.filter(usage_count__gt=0)
            .order_by("-usage_count")[:10]
            .values(
                "id",
                "question_text",
                "subject__name",
                "difficulty_level",
                "usage_count",
            )
        )

        return {
            "summary": usage_stats,
            "type_distribution": list(type_distribution),
            "difficulty_distribution": list(difficulty_distribution),
            "popular_questions": list(popular_questions),
            "recommendations": ExamIntegrationService._get_question_bank_recommendations(
                questions
            ),
        }

    @staticmethod
    def _get_question_bank_recommendations(questions) -> List[str]:
        """Generate recommendations for question bank optimization"""
        recommendations = []

        total_questions = questions.count()
        unused_questions = questions.filter(usage_count=0).count()

        if unused_questions > total_questions * 0.3:  # More than 30% unused
            recommendations.append(
                f"Review and update {unused_questions} unused questions to improve relevance"
            )

        # Check difficulty balance
        difficulty_counts = questions.values("difficulty_level").annotate(
            count=Count("id")
        )
        difficulty_dict = {
            item["difficulty_level"]: item["count"] for item in difficulty_counts
        }

        easy_pct = (
            (difficulty_dict.get("EASY", 0) / total_questions * 100)
            if total_questions > 0
            else 0
        )
        medium_pct = (
            (difficulty_dict.get("MEDIUM", 0) / total_questions * 100)
            if total_questions > 0
            else 0
        )
        hard_pct = (
            (difficulty_dict.get("HARD", 0) / total_questions * 100)
            if total_questions > 0
            else 0
        )

        if easy_pct < 20:
            recommendations.append(
                "Add more EASY level questions for better assessment balance"
            )
        if medium_pct < 50:
            recommendations.append(
                "Add more MEDIUM level questions - they should form the majority"
            )
        if hard_pct < 15:
            recommendations.append(
                "Add more HARD level questions for advanced assessment"
            )

        return recommendations
