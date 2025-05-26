"""
School Management System - Exam Analytics Service
File: src/exams/services/analytics_service.py
"""

from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from django.db.models import (
    Q,
    Avg,
    Sum,
    Count,
    Max,
    Min,
    F,
    Case,
    When,
    Value,
    FloatField,
)
from django.forms import CharField
from django.utils import timezone
from decimal import Decimal
import numpy as np
from collections import defaultdict

from ..models import (
    Exam,
    ExamSchedule,
    StudentExamResult,
    ReportCard,
    ExamType,
    OnlineExam,
    StudentOnlineExamAttempt,
)
from academics.models import Class, Grade, Section, Term, AcademicYear
from students.models import Student
from teachers.models import Teacher


class ExamAnalyticsService:
    """Comprehensive analytics service for exam data"""

    @staticmethod
    def get_academic_performance_dashboard(
        academic_year_id: str, term_id: str = None
    ) -> Dict:
        """Get comprehensive academic performance dashboard"""

        filters = {"academic_year_id": academic_year_id}
        if term_id:
            filters["term_id"] = term_id

        # Get all relevant data
        results = StudentExamResult.objects.filter(**filters).select_related(
            "student", "exam_schedule__subject", "exam_schedule__class_obj"
        )

        dashboard = {
            "overview": ExamAnalyticsService._get_performance_overview(results),
            "subject_analysis": ExamAnalyticsService._get_subject_performance_analysis(
                results
            ),
            "class_comparison": ExamAnalyticsService._get_class_performance_comparison(
                results
            ),
            "grade_trends": ExamAnalyticsService._get_grade_performance_trends(results),
            "student_insights": ExamAnalyticsService._get_student_performance_insights(
                results
            ),
            "teacher_effectiveness": ExamAnalyticsService._get_teacher_effectiveness_metrics(
                results
            ),
            "improvement_recommendations": ExamAnalyticsService._get_improvement_recommendations(
                results
            ),
        }

        return dashboard

    @staticmethod
    def _get_performance_overview(results) -> Dict:
        """Get overall performance metrics"""
        if not results.exists():
            return {}

        total_results = results.count()
        pass_count = results.filter(is_pass=True, is_absent=False).count()
        absent_count = results.filter(is_absent=True).count()

        overview = results.aggregate(
            avg_percentage=Avg("percentage", filter=Q(is_absent=False)),
            highest_percentage=Max("percentage"),
            lowest_percentage=Min("percentage"),
            total_students=Count("student", distinct=True),
            total_subjects=Count("exam_schedule__subject", distinct=True),
            total_exams=Count("exam_schedule__exam", distinct=True),
        )

        overview.update(
            {
                "total_results": total_results,
                "pass_rate": (
                    (pass_count / (total_results - absent_count) * 100)
                    if (total_results - absent_count) > 0
                    else 0
                ),
                "attendance_rate": (
                    ((total_results - absent_count) / total_results * 100)
                    if total_results > 0
                    else 0
                ),
                "grade_distribution": ExamAnalyticsService._calculate_grade_distribution(
                    results
                ),
            }
        )

        return overview

    @staticmethod
    def _calculate_grade_distribution(results) -> Dict:
        """Calculate distribution of grades"""
        distribution = (
            results.filter(is_absent=False)
            .values("grade")
            .annotate(count=Count("id"))
            .order_by("grade")
        )

        total = sum(item["count"] for item in distribution)

        return {
            item["grade"]: {
                "count": item["count"],
                "percentage": (item["count"] / total * 100) if total > 0 else 0,
            }
            for item in distribution
        }

    @staticmethod
    def _get_subject_performance_analysis(results) -> List[Dict]:
        """Analyze performance by subject"""
        subject_data = (
            results.filter(is_absent=False)
            .values("exam_schedule__subject__name", "exam_schedule__subject__id")
            .annotate(
                avg_percentage=Avg("percentage"),
                total_students=Count("student", distinct=True),
                pass_count=Count("id", filter=Q(is_pass=True)),
                total_attempts=Count("id"),
                highest_score=Max("percentage"),
                lowest_score=Min("percentage"),
                std_deviation=Case(
                    When(
                        total_attempts__gt=1, then=F("avg_percentage")
                    ),  # Simplified calculation
                    default=Value(0.0),
                    output_field=FloatField(),
                ),
            )
            .order_by("-avg_percentage")
        )

        analysis = []
        for subject in subject_data:
            pass_rate = (
                (subject["pass_count"] / subject["total_attempts"] * 100)
                if subject["total_attempts"] > 0
                else 0
            )

            # Determine performance level
            avg_pct = subject["avg_percentage"] or 0
            if avg_pct >= 80:
                performance_level = "Excellent"
            elif avg_pct >= 65:
                performance_level = "Good"
            elif avg_pct >= 50:
                performance_level = "Average"
            else:
                performance_level = "Below Average"

            analysis.append(
                {
                    "subject_name": subject["exam_schedule__subject__name"],
                    "subject_id": subject["exam_schedule__subject__id"],
                    "avg_percentage": round(avg_pct, 2),
                    "total_students": subject["total_students"],
                    "pass_rate": round(pass_rate, 2),
                    "highest_score": subject["highest_score"],
                    "lowest_score": subject["lowest_score"],
                    "performance_level": performance_level,
                    "difficulty_index": ExamAnalyticsService._calculate_difficulty_index(
                        avg_pct, pass_rate
                    ),
                }
            )

        return analysis

    @staticmethod
    def _calculate_difficulty_index(avg_percentage: float, pass_rate: float) -> str:
        """Calculate subject difficulty index"""
        combined_score = (avg_percentage + pass_rate) / 2

        if combined_score >= 75:
            return "Easy"
        elif combined_score >= 50:
            return "Moderate"
        else:
            return "Difficult"

    @staticmethod
    def _get_class_performance_comparison(results) -> List[Dict]:
        """Compare performance across classes"""
        class_data = (
            results.filter(is_absent=False)
            .values(
                "exam_schedule__class_obj__id",
                "exam_schedule__class_obj__grade__name",
                "exam_schedule__class_obj__name",
            )
            .annotate(
                avg_percentage=Avg("percentage"),
                total_students=Count("student", distinct=True),
                pass_count=Count("id", filter=Q(is_pass=True)),
                total_results=Count("id"),
                highest_score=Max("percentage"),
                lowest_score=Min("percentage"),
            )
            .order_by("-avg_percentage")
        )

        comparison = []
        for class_info in class_data:
            pass_rate = (
                (class_info["pass_count"] / class_info["total_results"] * 100)
                if class_info["total_results"] > 0
                else 0
            )

            comparison.append(
                {
                    "class_id": class_info["exam_schedule__class_obj__id"],
                    "class_name": f"{class_info['exam_schedule__class_obj__grade__name']} {class_info['exam_schedule__class_obj__name']}",
                    "avg_percentage": round(class_info["avg_percentage"] or 0, 2),
                    "pass_rate": round(pass_rate, 2),
                    "total_students": class_info["total_students"],
                    "highest_score": class_info["highest_score"],
                    "lowest_score": class_info["lowest_score"],
                    "performance_variance": (
                        class_info["highest_score"] - class_info["lowest_score"]
                        if class_info["highest_score"] and class_info["lowest_score"]
                        else 0
                    ),
                }
            )

        return comparison

    @staticmethod
    def _get_grade_performance_trends(results) -> List[Dict]:
        """Analyze performance trends by grade level"""
        grade_data = (
            results.filter(is_absent=False)
            .values(
                "exam_schedule__class_obj__grade__id",
                "exam_schedule__class_obj__grade__name",
                "exam_schedule__class_obj__grade__order_sequence",
            )
            .annotate(
                avg_percentage=Avg("percentage"),
                total_students=Count("student", distinct=True),
                pass_rate=Count("id", filter=Q(is_pass=True)) * 100.0 / Count("id"),
                total_classes=Count("exam_schedule__class_obj", distinct=True),
            )
            .order_by("exam_schedule__class_obj__grade__order_sequence")
        )

        trends = []
        for grade in grade_data:
            trends.append(
                {
                    "grade_id": grade["exam_schedule__class_obj__grade__id"],
                    "grade_name": grade["exam_schedule__class_obj__grade__name"],
                    "order_sequence": grade[
                        "exam_schedule__class_obj__grade__order_sequence"
                    ],
                    "avg_percentage": round(grade["avg_percentage"] or 0, 2),
                    "pass_rate": round(grade["pass_rate"] or 0, 2),
                    "total_students": grade["total_students"],
                    "total_classes": grade["total_classes"],
                }
            )

        return trends

    @staticmethod
    def _get_student_performance_insights(results) -> Dict:
        """Get insights about student performance patterns"""
        if not results.exists():
            return {}

        # Top performers
        top_performers = (
            results.filter(is_absent=False)
            .values(
                "student__id",
                "student__user__first_name",
                "student__user__last_name",
                "student__admission_number",
            )
            .annotate(
                avg_percentage=Avg("percentage"),
                total_subjects=Count("exam_schedule__subject", distinct=True),
                pass_count=Count("id", filter=Q(is_pass=True)),
            )
            .filter(avg_percentage__gte=80)
            .order_by("-avg_percentage")[:10]
        )

        # Students needing attention
        struggling_students = (
            results.filter(is_absent=False)
            .values(
                "student__id",
                "student__user__first_name",
                "student__user__last_name",
                "student__admission_number",
            )
            .annotate(
                avg_percentage=Avg("percentage"),
                total_subjects=Count("exam_schedule__subject", distinct=True),
                fail_count=Count("id", filter=Q(is_pass=False)),
            )
            .filter(Q(avg_percentage__lt=40) | Q(fail_count__gte=2))
            .order_by("avg_percentage")[:20]
        )

        # Performance distribution
        performance_bands = {
            "excellent": results.filter(percentage__gte=90, is_absent=False).count(),
            "good": results.filter(
                percentage__gte=70, percentage__lt=90, is_absent=False
            ).count(),
            "average": results.filter(
                percentage__gte=50, percentage__lt=70, is_absent=False
            ).count(),
            "below_average": results.filter(percentage__lt=50, is_absent=False).count(),
        }

        return {
            "top_performers": list(top_performers),
            "struggling_students": list(struggling_students),
            "performance_bands": performance_bands,
            "total_analyzed": sum(performance_bands.values()),
        }

    @staticmethod
    def _get_teacher_effectiveness_metrics(results) -> List[Dict]:
        """Analyze teacher effectiveness based on student results"""
        # Get teacher assignments and their students' performance
        teacher_data = (
            results.filter(is_absent=False)
            .values(
                "exam_schedule__supervisor__id",
                "exam_schedule__supervisor__user__first_name",
                "exam_schedule__supervisor__user__last_name",
                "exam_schedule__supervisor__employee_id",
            )
            .annotate(
                avg_student_performance=Avg("percentage"),
                total_students=Count("student", distinct=True),
                subjects_taught=Count("exam_schedule__subject", distinct=True),
                pass_rate=Count("id", filter=Q(is_pass=True)) * 100.0 / Count("id"),
            )
            .order_by("-avg_student_performance")
        )

        effectiveness = []
        for teacher in teacher_data:
            if teacher[
                "exam_schedule__supervisor__id"
            ]:  # Only include if supervisor exists
                effectiveness.append(
                    {
                        "teacher_id": teacher["exam_schedule__supervisor__id"],
                        "teacher_name": f"{teacher['exam_schedule__supervisor__user__first_name']} {teacher['exam_schedule__supervisor__user__last_name']}",
                        "employee_id": teacher[
                            "exam_schedule__supervisor__employee_id"
                        ],
                        "avg_student_performance": round(
                            teacher["avg_student_performance"] or 0, 2
                        ),
                        "pass_rate": round(teacher["pass_rate"] or 0, 2),
                        "total_students": teacher["total_students"],
                        "subjects_taught": teacher["subjects_taught"],
                    }
                )

        return effectiveness

    @staticmethod
    def _get_improvement_recommendations(results) -> List[Dict]:
        """Generate improvement recommendations based on analysis"""
        recommendations = []

        # Subject-wise recommendations
        subject_analysis = ExamAnalyticsService._get_subject_performance_analysis(
            results
        )

        for subject in subject_analysis:
            if subject["avg_percentage"] < 50:
                recommendations.append(
                    {
                        "type": "Subject Improvement",
                        "priority": "High",
                        "area": subject["subject_name"],
                        "issue": f"Low average performance ({subject['avg_percentage']:.1f}%)",
                        "recommendation": f"Consider reviewing teaching methods, providing additional support materials, and conducting remedial classes for {subject['subject_name']}",
                    }
                )

            if subject["pass_rate"] < 60:
                recommendations.append(
                    {
                        "type": "Pass Rate Enhancement",
                        "priority": "Medium",
                        "area": subject["subject_name"],
                        "issue": f"Low pass rate ({subject['pass_rate']:.1f}%)",
                        "recommendation": f"Implement targeted interventions and additional practice sessions for {subject['subject_name']}",
                    }
                )

        # Class-wise recommendations
        class_comparison = ExamAnalyticsService._get_class_performance_comparison(
            results
        )

        if class_comparison:
            avg_class_performance = sum(
                c["avg_percentage"] for c in class_comparison
            ) / len(class_comparison)

            for class_info in class_comparison:
                if class_info["avg_percentage"] < avg_class_performance - 10:
                    recommendations.append(
                        {
                            "type": "Class Performance",
                            "priority": "Medium",
                            "area": class_info["class_name"],
                            "issue": f"Performance below average ({class_info['avg_percentage']:.1f}% vs {avg_class_performance:.1f}%)",
                            "recommendation": f"Provide additional support and resources for {class_info['class_name']}",
                        }
                    )

        return recommendations

    @staticmethod
    def get_student_progress_report(student_id: str, academic_year_id: str) -> Dict:
        """Get comprehensive progress report for a specific student"""
        results = (
            StudentExamResult.objects.filter(
                student_id=student_id,
                exam_schedule__exam__academic_year_id=academic_year_id,
                is_absent=False,
            )
            .select_related("exam_schedule__subject", "exam_schedule__exam", "term")
            .order_by("exam_schedule__exam__start_date")
        )

        if not results.exists():
            return {}

        # Term-wise performance
        term_performance = (
            results.values("term__name", "term__term_number")
            .annotate(
                avg_percentage=Avg("percentage"),
                total_subjects=Count("exam_schedule__subject", distinct=True),
                pass_count=Count("id", filter=Q(is_pass=True)),
            )
            .order_by("term__term_number")
        )

        # Subject-wise performance
        subject_performance = (
            results.values("exam_schedule__subject__name")
            .annotate(
                avg_percentage=Avg("percentage"),
                highest_score=Max("percentage"),
                lowest_score=Min("percentage"),
                total_exams=Count("id"),
                pass_count=Count("id", filter=Q(is_pass=True)),
            )
            .order_by("-avg_percentage")
        )

        # Performance trend analysis
        trend_data = []
        for result in results:
            trend_data.append(
                {
                    "date": result.exam_schedule.exam.start_date,
                    "exam_name": result.exam_schedule.exam.name,
                    "subject": result.exam_schedule.subject.name,
                    "percentage": float(result.percentage),
                    "grade": result.grade,
                    "class_rank": result.class_rank,
                }
            )

        # Calculate improvement areas
        improvement_areas = []
        for subject in subject_performance:
            if subject["avg_percentage"] < 60:
                improvement_areas.append(
                    {
                        "subject": subject["exam_schedule__subject__name"],
                        "avg_score": subject["avg_percentage"],
                        "recommendation": "Focus on fundamental concepts and practice more exercises",
                    }
                )

        return {
            "student_id": student_id,
            "academic_year_id": academic_year_id,
            "overall_average": results.aggregate(avg=Avg("percentage"))["avg"],
            "total_exams": results.count(),
            "pass_rate": (results.filter(is_pass=True).count() / results.count() * 100),
            "term_performance": list(term_performance),
            "subject_performance": list(subject_performance),
            "performance_trend": trend_data,
            "improvement_areas": improvement_areas,
            "strengths": [
                s["exam_schedule__subject__name"]
                for s in subject_performance
                if s["avg_percentage"] >= 80
            ][:5],
        }

    @staticmethod
    def get_online_exam_analytics(online_exam_id: str) -> Dict:
        """Get analytics for online exam performance"""
        attempts = StudentOnlineExamAttempt.objects.filter(
            online_exam_id=online_exam_id, status="SUBMITTED"
        ).select_related("student__user")

        if not attempts.exists():
            return {}

        # Basic statistics
        total_attempts = attempts.count()
        unique_students = attempts.values("student").distinct().count()

        attempt_stats = attempts.aggregate(
            avg_score=Avg("marks_obtained"),
            highest_score=Max("marks_obtained"),
            lowest_score=Min("marks_obtained"),
            avg_time=Avg("time_remaining_seconds"),
            avg_violations=Avg("violation_count"),
        )

        # Score distribution
        score_ranges = {
            "90-100%": attempts.filter(
                marks_obtained__gte=F("total_marks") * 0.9
            ).count(),
            "80-89%": attempts.filter(
                marks_obtained__gte=F("total_marks") * 0.8,
                marks_obtained__lt=F("total_marks") * 0.9,
            ).count(),
            "70-79%": attempts.filter(
                marks_obtained__gte=F("total_marks") * 0.7,
                marks_obtained__lt=F("total_marks") * 0.8,
            ).count(),
            "60-69%": attempts.filter(
                marks_obtained__gte=F("total_marks") * 0.6,
                marks_obtained__lt=F("total_marks") * 0.7,
            ).count(),
            "Below 60%": attempts.filter(
                marks_obtained__lt=F("total_marks") * 0.6
            ).count(),
        }

        # Time analysis
        time_stats = []
        for attempt in attempts:
            online_exam = attempt.online_exam
            if attempt.submit_time and attempt.start_time:
                time_taken = (
                    attempt.submit_time - attempt.start_time
                ).total_seconds() / 60
                time_stats.append(
                    {
                        "student_id": attempt.student.id,
                        "time_taken_minutes": time_taken,
                        "time_efficiency": (time_taken / online_exam.time_limit_minutes)
                        * 100,
                    }
                )

        return {
            "total_attempts": total_attempts,
            "unique_students": unique_students,
            "completion_rate": (
                (total_attempts / unique_students * 100) if unique_students > 0 else 0
            ),
            "average_score": round(attempt_stats["avg_score"] or 0, 2),
            "highest_score": attempt_stats["highest_score"],
            "lowest_score": attempt_stats["lowest_score"],
            "score_distribution": score_ranges,
            "average_violations": round(attempt_stats["avg_violations"] or 0, 2),
            "time_analysis": time_stats,
            "question_analysis": ExamAnalyticsService._analyze_question_performance(
                online_exam_id
            ),
        }

    @staticmethod
    def _analyze_question_performance(online_exam_id: str) -> List[Dict]:
        """Analyze performance on individual questions"""
        attempts = StudentOnlineExamAttempt.objects.filter(
            online_exam_id=online_exam_id, status="SUBMITTED"
        )

        question_stats = []

        # This would require analyzing the responses JSON field
        # Implementation depends on how responses are structured
        # For now, returning placeholder structure

        return question_stats

    @staticmethod
    def generate_comparative_report(
        academic_year_id: str,
        comparison_type: str = "term",
        entity_ids: List[str] = None,
    ) -> Dict:
        """Generate comparative analysis reports"""

        base_filter = {
            "exam_schedule__exam__academic_year_id": academic_year_id,
            "is_absent": False,
        }
        results = StudentExamResult.objects.filter(**base_filter)

        if comparison_type == "term":
            return ExamAnalyticsService._compare_by_terms(results, entity_ids)
        elif comparison_type == "class":
            return ExamAnalyticsService._compare_by_classes(results, entity_ids)
        elif comparison_type == "subject":
            return ExamAnalyticsService._compare_by_subjects(results, entity_ids)
        elif comparison_type == "grade":
            return ExamAnalyticsService._compare_by_grades(results, entity_ids)
        else:
            return {}

    @staticmethod
    def _compare_by_terms(results, term_ids: List[str] = None) -> Dict:
        """Compare performance across terms"""
        if term_ids:
            results = results.filter(term_id__in=term_ids)

        term_comparison = (
            results.values("term__name", "term__term_number")
            .annotate(
                avg_percentage=Avg("percentage"),
                pass_rate=Count("id", filter=Q(is_pass=True)) * 100.0 / Count("id"),
                total_students=Count("student", distinct=True),
                total_results=Count("id"),
            )
            .order_by("term__term_number")
        )

        return {
            "comparison_type": "term",
            "data": list(term_comparison),
            "insights": ExamAnalyticsService._generate_term_insights(
                list(term_comparison)
            ),
        }

    @staticmethod
    def _generate_term_insights(term_data: List[Dict]) -> List[str]:
        """Generate insights from term comparison"""
        insights = []

        if len(term_data) >= 2:
            # Compare first and last terms
            first_term = term_data[0]
            last_term = term_data[-1]

            avg_change = last_term["avg_percentage"] - first_term["avg_percentage"]

            if avg_change > 5:
                insights.append(
                    f"Overall performance improved by {avg_change:.1f}% from {first_term['term__name']} to {last_term['term__name']}"
                )
            elif avg_change < -5:
                insights.append(
                    f"Overall performance declined by {abs(avg_change):.1f}% from {first_term['term__name']} to {last_term['term__name']}"
                )
            else:
                insights.append("Performance remained relatively stable across terms")

        return insights

    @staticmethod
    def _compare_by_classes(results, class_ids: List[str] = None) -> Dict:
        """Compare performance across classes"""
        if class_ids:
            results = results.filter(exam_schedule__class_obj_id__in=class_ids)

        class_comparison = (
            results.values(
                "exam_schedule__class_obj__id",
                "exam_schedule__class_obj__grade__name",
                "exam_schedule__class_obj__name",
            )
            .annotate(
                avg_percentage=Avg("percentage"),
                pass_rate=Count("id", filter=Q(is_pass=True)) * 100.0 / Count("id"),
                total_students=Count("student", distinct=True),
            )
            .order_by("-avg_percentage")
        )

        return {"comparison_type": "class", "data": list(class_comparison)}

    @staticmethod
    def _compare_by_subjects(results, subject_ids: List[str] = None) -> Dict:
        """Compare performance across subjects"""
        if subject_ids:
            results = results.filter(exam_schedule__subject_id__in=subject_ids)

        subject_comparison = (
            results.values("exam_schedule__subject__id", "exam_schedule__subject__name")
            .annotate(
                avg_percentage=Avg("percentage"),
                pass_rate=Count("id", filter=Q(is_pass=True)) * 100.0 / Count("id"),
                total_attempts=Count("id"),
                difficulty_index=Case(
                    When(avg_percentage__gte=75, then=Value("Easy")),
                    When(avg_percentage__gte=50, then=Value("Moderate")),
                    default=Value("Difficult"),
                    output_field=CharField(max_length=20),
                ),
            )
            .order_by("-avg_percentage")
        )

        return {"comparison_type": "subject", "data": list(subject_comparison)}

    @staticmethod
    def _compare_by_grades(results, grade_ids: List[str] = None) -> Dict:
        """Compare performance across grades"""
        if grade_ids:
            results = results.filter(exam_schedule__class_obj__grade_id__in=grade_ids)

        grade_comparison = (
            results.values(
                "exam_schedule__class_obj__grade__id",
                "exam_schedule__class_obj__grade__name",
                "exam_schedule__class_obj__grade__order_sequence",
            )
            .annotate(
                avg_percentage=Avg("percentage"),
                pass_rate=Count("id", filter=Q(is_pass=True)) * 100.0 / Count("id"),
                total_students=Count("student", distinct=True),
            )
            .order_by("exam_schedule__class_obj__grade__order_sequence")
        )

        return {"comparison_type": "grade", "data": list(grade_comparison)}
