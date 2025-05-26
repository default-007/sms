import json
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from django.db.models import Avg, Case, Count, F, Q, QuerySet, Sum, Value, When
from django.db.models.functions import Coalesce, Round
from django.utils.translation import gettext_lazy as _

from academics.models import AcademicYear, Class, Department, Grade, Term
from teachers.models import Teacher

from ..models import Subject, SubjectAssignment, Syllabus, TopicProgress


class SubjectAnalyticsService:
    """
    Advanced analytics service for subjects module providing comprehensive
    insights, trends, and performance metrics.
    """

    @staticmethod
    def get_department_performance_analytics(
        department_id: int, academic_year_id: int, term_id: Optional[int] = None
    ) -> Dict:
        """
        Get comprehensive performance analytics for a department.

        Args:
            department_id: ID of the department
            academic_year_id: ID of the academic year
            term_id: Optional specific term

        Returns:
            Dictionary containing department performance data
        """
        filters = {
            "subject__department_id": department_id,
            "academic_year_id": academic_year_id,
            "is_active": True,
        }

        if term_id:
            filters["term_id"] = term_id

        syllabi = (
            Syllabus.objects.filter(**filters)
            .select_related("subject", "grade", "term")
            .annotate(
                total_topics=Count("topic_progress"),
                completed_topics=Count(
                    "topic_progress", filter=Q(topic_progress__is_completed=True)
                ),
                total_hours_taught=Coalesce(Sum("topic_progress__hours_taught"), 0),
            )
        )

        # Basic statistics
        total_syllabi = syllabi.count()
        if total_syllabi == 0:
            return {
                "department_id": department_id,
                "academic_year_id": academic_year_id,
                "term_id": term_id,
                "message": "No syllabi found for the given criteria",
            }

        # Completion statistics
        completion_stats = syllabi.aggregate(
            avg_completion=Avg("completion_percentage"),
            min_completion=models.Min("completion_percentage"),
            max_completion=models.Max("completion_percentage"),
            total_topics=Sum("total_topics"),
            total_completed_topics=Sum("completed_topics"),
            total_hours_taught=Sum("total_hours_taught"),
        )

        # Grade-wise performance
        grade_performance = {}
        for syllabus in syllabi:
            grade_name = syllabus.grade.name
            if grade_name not in grade_performance:
                grade_performance[grade_name] = {
                    "syllabi_count": 0,
                    "total_completion": 0,
                    "total_topics": 0,
                    "completed_topics": 0,
                    "subjects": set(),
                }

            grade_data = grade_performance[grade_name]
            grade_data["syllabi_count"] += 1
            grade_data["total_completion"] += syllabus.completion_percentage
            grade_data["total_topics"] += syllabus.total_topics
            grade_data["completed_topics"] += syllabus.completed_topics
            grade_data["subjects"].add(syllabus.subject.name)

        # Calculate averages and convert sets
        for grade_data in grade_performance.values():
            if grade_data["syllabi_count"] > 0:
                grade_data["avg_completion"] = (
                    grade_data["total_completion"] / grade_data["syllabi_count"]
                )
            grade_data["unique_subjects"] = len(grade_data["subjects"])
            grade_data["subjects"] = list(grade_data["subjects"])

        # Subject-wise performance
        subject_performance = {}
        for syllabus in syllabi:
            subject_name = syllabus.subject.name
            if subject_name not in subject_performance:
                subject_performance[subject_name] = {
                    "code": syllabus.subject.code,
                    "syllabi_count": 0,
                    "total_completion": 0,
                    "grades": set(),
                    "difficulty_levels": [],
                }

            subject_data = subject_performance[subject_name]
            subject_data["syllabi_count"] += 1
            subject_data["total_completion"] += syllabus.completion_percentage
            subject_data["grades"].add(syllabus.grade.name)
            subject_data["difficulty_levels"].append(syllabus.difficulty_level)

        # Calculate subject averages
        for subject_data in subject_performance.values():
            if subject_data["syllabi_count"] > 0:
                subject_data["avg_completion"] = (
                    subject_data["total_completion"] / subject_data["syllabi_count"]
                )
            subject_data["grades"] = list(subject_data["grades"])

        # Progress distribution
        progress_distribution = {
            "not_started": syllabi.filter(completion_percentage=0).count(),
            "in_progress": syllabi.filter(
                completion_percentage__gt=0, completion_percentage__lt=100
            ).count(),
            "completed": syllabi.filter(completion_percentage=100).count(),
        }

        return {
            "department_id": department_id,
            "academic_year_id": academic_year_id,
            "term_id": term_id,
            "overview": {
                "total_syllabi": total_syllabi,
                "unique_subjects": syllabi.values("subject").distinct().count(),
                "unique_grades": syllabi.values("grade").distinct().count(),
                "average_completion": round(completion_stats["avg_completion"] or 0, 2),
                "completion_range": {
                    "min": completion_stats["min_completion"] or 0,
                    "max": completion_stats["max_completion"] or 0,
                },
                "total_topics": completion_stats["total_topics"] or 0,
                "total_completed_topics": completion_stats["total_completed_topics"]
                or 0,
                "total_hours_taught": completion_stats["total_hours_taught"] or 0,
            },
            "by_grade": grade_performance,
            "by_subject": subject_performance,
            "progress_distribution": progress_distribution,
            "completion_rate": (
                round((progress_distribution["completed"] / total_syllabi * 100), 2)
                if total_syllabi > 0
                else 0
            ),
        }

    @staticmethod
    def get_teacher_performance_analytics(
        teacher_id: int, academic_year_id: int, include_historical: bool = False
    ) -> Dict:
        """
        Get comprehensive performance analytics for a teacher.

        Args:
            teacher_id: ID of the teacher
            academic_year_id: ID of the academic year
            include_historical: Whether to include historical data

        Returns:
            Dictionary containing teacher performance data
        """
        # Get teacher assignments
        assignments = SubjectAssignment.objects.filter(
            teacher_id=teacher_id, academic_year_id=academic_year_id, is_active=True
        ).select_related("subject", "class_assigned", "term")

        if not assignments.exists():
            return {
                "teacher_id": teacher_id,
                "academic_year_id": academic_year_id,
                "message": "No assignments found for this teacher",
            }

        # Get corresponding syllabi
        syllabus_filters = []
        for assignment in assignments:
            syllabus_filters.append(
                Q(subject=assignment.subject)
                & Q(grade=assignment.class_assigned.grade)
                & Q(academic_year=assignment.academic_year)
                & Q(term=assignment.term)
                & Q(is_active=True)
            )

        if syllabus_filters:
            import operator
            from functools import reduce

            combined_filter = reduce(operator.or_, syllabus_filters)
            syllabi = Syllabus.objects.filter(combined_filter).annotate(
                total_topics=Count("topic_progress"),
                completed_topics=Count(
                    "topic_progress", filter=Q(topic_progress__is_completed=True)
                ),
                total_hours_taught=Coalesce(Sum("topic_progress__hours_taught"), 0),
            )
        else:
            syllabi = Syllabus.objects.none()

        # Calculate performance metrics
        performance_metrics = {
            "total_assignments": assignments.count(),
            "primary_assignments": assignments.filter(is_primary_teacher=True).count(),
            "secondary_assignments": assignments.filter(
                is_primary_teacher=False
            ).count(),
            "unique_subjects": assignments.values("subject").distinct().count(),
            "unique_classes": assignments.values("class_assigned").distinct().count(),
            "total_credit_hours": sum(a.subject.credit_hours for a in assignments),
        }

        # Syllabus performance
        if syllabi.exists():
            syllabus_stats = syllabi.aggregate(
                avg_completion=Avg("completion_percentage"),
                total_syllabi=Count("id"),
                completed_syllabi=Count("id", filter=Q(completion_percentage=100)),
                total_topics=Sum("total_topics"),
                completed_topics=Sum("completed_topics"),
                total_hours_taught=Sum("total_hours_taught"),
            )

            performance_metrics.update(
                {
                    "syllabus_performance": {
                        "total_syllabi": syllabus_stats["total_syllabi"],
                        "average_completion": round(
                            syllabus_stats["avg_completion"] or 0, 2
                        ),
                        "completed_syllabi": syllabus_stats["completed_syllabi"],
                        "completion_rate": (
                            round(
                                (
                                    syllabus_stats["completed_syllabi"]
                                    / syllabus_stats["total_syllabi"]
                                    * 100
                                ),
                                2,
                            )
                            if syllabus_stats["total_syllabi"] > 0
                            else 0
                        ),
                        "total_topics": syllabus_stats["total_topics"] or 0,
                        "completed_topics": syllabus_stats["completed_topics"] or 0,
                        "topic_completion_rate": (
                            round(
                                (
                                    syllabus_stats["completed_topics"]
                                    / syllabus_stats["total_topics"]
                                    * 100
                                ),
                                2,
                            )
                            if syllabus_stats["total_topics"] > 0
                            else 0
                        ),
                        "total_hours_taught": syllabus_stats["total_hours_taught"] or 0,
                    }
                }
            )

        # Subject-wise breakdown
        subject_breakdown = {}
        for assignment in assignments:
            subject_name = assignment.subject.name
            if subject_name not in subject_breakdown:
                subject_breakdown[subject_name] = {
                    "code": assignment.subject.code,
                    "assignments_count": 0,
                    "classes": [],
                    "terms": set(),
                    "is_primary_count": 0,
                    "credit_hours": assignment.subject.credit_hours,
                }

            subject_data = subject_breakdown[subject_name]
            subject_data["assignments_count"] += 1
            subject_data["classes"].append(str(assignment.class_assigned))
            subject_data["terms"].add(assignment.term.name)
            if assignment.is_primary_teacher:
                subject_data["is_primary_count"] += 1

        # Convert sets to lists for JSON serialization
        for subject_data in subject_breakdown.values():
            subject_data["terms"] = list(subject_data["terms"])

        # Historical data if requested
        historical_data = None
        if include_historical:
            historical_data = SubjectAnalyticsService._get_teacher_historical_data(
                teacher_id
            )

        return {
            "teacher_id": teacher_id,
            "academic_year_id": academic_year_id,
            "performance_metrics": performance_metrics,
            "subject_breakdown": subject_breakdown,
            "historical_data": historical_data,
        }

    @staticmethod
    def get_curriculum_trends(
        academic_year_id: int,
        department_id: Optional[int] = None,
        compare_previous_year: bool = True,
    ) -> Dict:
        """
        Get curriculum trends and comparative analysis.

        Args:
            academic_year_id: ID of the current academic year
            department_id: Optional department filter
            compare_previous_year: Whether to include previous year comparison

        Returns:
            Dictionary containing trend analysis
        """
        filters = {"academic_year_id": academic_year_id, "is_active": True}
        if department_id:
            filters["subject__department_id"] = department_id

        current_syllabi = (
            Syllabus.objects.filter(**filters)
            .select_related("subject", "grade", "term")
            .annotate(
                total_topics=Count("topic_progress"),
                completed_topics=Count(
                    "topic_progress", filter=Q(topic_progress__is_completed=True)
                ),
            )
        )

        # Current year analysis
        current_analysis = SubjectAnalyticsService._analyze_syllabus_data(
            current_syllabi
        )

        result = {
            "academic_year_id": academic_year_id,
            "department_id": department_id,
            "current_year": current_analysis,
            "trends": {},
        }

        # Previous year comparison if requested
        if compare_previous_year:
            try:
                current_year = AcademicYear.objects.get(id=academic_year_id)
                previous_year = (
                    AcademicYear.objects.filter(start_date__lt=current_year.start_date)
                    .order_by("-start_date")
                    .first()
                )

                if previous_year:
                    prev_filters = {"academic_year": previous_year, "is_active": True}
                    if department_id:
                        prev_filters["subject__department_id"] = department_id

                    previous_syllabi = Syllabus.objects.filter(**prev_filters).annotate(
                        total_topics=Count("topic_progress"),
                        completed_topics=Count(
                            "topic_progress",
                            filter=Q(topic_progress__is_completed=True),
                        ),
                    )

                    previous_analysis = SubjectAnalyticsService._analyze_syllabus_data(
                        previous_syllabi
                    )

                    # Calculate trends
                    trends = SubjectAnalyticsService._calculate_trends(
                        current_analysis, previous_analysis
                    )

                    result["previous_year"] = previous_analysis
                    result["trends"] = trends

            except AcademicYear.DoesNotExist:
                pass

        return result

    @staticmethod
    def get_completion_forecasting(
        academic_year_id: int, term_id: Optional[int] = None
    ) -> Dict:
        """
        Generate completion forecasting based on current progress.

        Args:
            academic_year_id: ID of the academic year
            term_id: Optional specific term

        Returns:
            Dictionary containing forecasting data
        """
        filters = {"academic_year_id": academic_year_id, "is_active": True}
        if term_id:
            filters["term_id"] = term_id

        syllabi = (
            Syllabus.objects.filter(**filters)
            .select_related("term")
            .annotate(
                total_topics=Count("topic_progress"),
                completed_topics=Count(
                    "topic_progress", filter=Q(topic_progress__is_completed=True)
                ),
                total_hours_taught=Coalesce(Sum("topic_progress__hours_taught"), 0),
            )
        )

        forecasting_data = {
            "academic_year_id": academic_year_id,
            "term_id": term_id,
            "forecasts": {},
            "recommendations": [],
        }

        # Get current date and term information
        current_date = date.today()

        for syllabus in syllabi:
            term = syllabus.term

            # Calculate days elapsed and remaining in term
            if term.start_date <= current_date <= term.end_date:
                total_days = (term.end_date - term.start_date).days
                elapsed_days = (current_date - term.start_date).days
                remaining_days = (term.end_date - current_date).days

                progress_rate = elapsed_days / total_days if total_days > 0 else 0
                completion_rate = syllabus.completion_percentage / 100

                # Simple linear projection
                if progress_rate > 0:
                    projected_completion = min(
                        100, (completion_rate / progress_rate) * 100
                    )
                else:
                    projected_completion = syllabus.completion_percentage

                forecast = {
                    "syllabus_id": syllabus.id,
                    "current_completion": syllabus.completion_percentage,
                    "projected_completion": round(projected_completion, 2),
                    "days_remaining": remaining_days,
                    "completion_velocity": (
                        round(completion_rate / progress_rate, 2)
                        if progress_rate > 0
                        else 0
                    ),
                    "risk_level": SubjectAnalyticsService._calculate_risk_level(
                        syllabus.completion_percentage,
                        projected_completion,
                        remaining_days,
                    ),
                }

                forecasting_data["forecasts"][
                    f"{syllabus.subject.code}_{syllabus.grade.name}"
                ] = forecast

                # Generate recommendations
                if forecast["risk_level"] == "high":
                    forecasting_data["recommendations"].append(
                        {
                            "syllabus": f"{syllabus.subject.name} - {syllabus.grade.name}",
                            "recommendation": "Immediate attention required - significantly behind schedule",
                            "priority": "high",
                        }
                    )
                elif forecast["risk_level"] == "medium":
                    forecasting_data["recommendations"].append(
                        {
                            "syllabus": f"{syllabus.subject.name} - {syllabus.grade.name}",
                            "recommendation": "Monitor closely - may fall behind schedule",
                            "priority": "medium",
                        }
                    )

        return forecasting_data

    @staticmethod
    def _analyze_syllabus_data(syllabi: QuerySet) -> Dict:
        """Analyze syllabus data and return metrics."""
        if not syllabi.exists():
            return {
                "total_syllabi": 0,
                "average_completion": 0,
                "completion_distribution": {
                    "not_started": 0,
                    "in_progress": 0,
                    "completed": 0,
                },
            }

        stats = syllabi.aggregate(
            total_count=Count("id"),
            avg_completion=Avg("completion_percentage"),
            total_topics=Sum("total_topics"),
            completed_topics=Sum("completed_topics"),
        )

        distribution = {
            "not_started": syllabi.filter(completion_percentage=0).count(),
            "in_progress": syllabi.filter(
                completion_percentage__gt=0, completion_percentage__lt=100
            ).count(),
            "completed": syllabi.filter(completion_percentage=100).count(),
        }

        return {
            "total_syllabi": stats["total_count"],
            "average_completion": round(stats["avg_completion"] or 0, 2),
            "total_topics": stats["total_topics"] or 0,
            "completed_topics": stats["completed_topics"] or 0,
            "completion_distribution": distribution,
        }

    @staticmethod
    def _calculate_trends(current: Dict, previous: Dict) -> Dict:
        """Calculate trends between current and previous periods."""
        trends = {}

        # Calculate percentage changes
        for key in [
            "total_syllabi",
            "average_completion",
            "total_topics",
            "completed_topics",
        ]:
            if key in current and key in previous:
                current_val = current[key]
                previous_val = previous[key]

                if previous_val > 0:
                    change = ((current_val - previous_val) / previous_val) * 100
                    trends[f"{key}_change"] = round(change, 2)
                else:
                    trends[f"{key}_change"] = 0

        return trends

    @staticmethod
    def _calculate_risk_level(
        current_completion: float, projected_completion: float, days_remaining: int
    ) -> str:
        """Calculate risk level based on completion projections."""
        if projected_completion < 70 or (
            current_completion < 30 and days_remaining < 30
        ):
            return "high"
        elif projected_completion < 85 or (
            current_completion < 50 and days_remaining < 60
        ):
            return "medium"
        else:
            return "low"

    @staticmethod
    def _get_teacher_historical_data(teacher_id: int) -> List[Dict]:
        """Get historical performance data for a teacher."""
        # This would fetch historical data from previous academic years
        # Implementation depends on available historical data structure
        return []
