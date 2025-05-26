from django.db.models import (
    Q,
    Count,
    Avg,
    Sum,
    Max,
    Min,
    StdDev,
    Case,
    When,
    IntegerField,
    FloatField,
    DateTrunc,
    F,
    Value,
    CharField,
)
from django.db.models.functions import Coalesce, Round
from django.utils import timezone
from django.core.cache import cache
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import logging
from collections import defaultdict

from ..models import Assignment, AssignmentSubmission, SubmissionGrade
from students.models import Student
from teachers.models import Teacher
from academics.models import Class, Term, AcademicYear

logger = logging.getLogger(__name__)


class AssignmentAnalyticsService:
    """
    Comprehensive analytics service for assignment module
    """

    @staticmethod
    def get_student_performance_analytics(
        student_id: int, filters: Dict = None
    ) -> Dict:
        """
        Get detailed performance analytics for a student
        """
        try:
            cache_key = f"student_analytics_{student_id}_{hash(str(filters))}"
            cached_result = cache.get(cache_key)
            if cached_result:
                return cached_result

            student = Student.objects.get(id=student_id)
            submissions = AssignmentSubmission.objects.filter(student=student)

            # Apply filters
            if filters:
                if filters.get("term"):
                    submissions = submissions.filter(assignment__term=filters["term"])
                if filters.get("subject"):
                    submissions = submissions.filter(
                        assignment__subject=filters["subject"]
                    )
                if filters.get("academic_year"):
                    submissions = submissions.filter(
                        assignment__term__academic_year=filters["academic_year"]
                    )

            # Basic statistics
            total_assignments = submissions.count()
            graded_submissions = submissions.filter(
                status="graded", marks_obtained__isnull=False
            )

            basic_stats = {
                "total_assignments": total_assignments,
                "submitted_assignments": submissions.filter(
                    status__in=["submitted", "graded"]
                ).count(),
                "graded_assignments": graded_submissions.count(),
                "pending_assignments": submissions.filter(status="submitted").count(),
                "late_submissions": submissions.filter(is_late=True).count(),
                "submission_rate": (
                    (submissions.count() / total_assignments * 100)
                    if total_assignments > 0
                    else 0
                ),
            }

            # Performance metrics
            if graded_submissions.exists():
                performance_stats = graded_submissions.aggregate(
                    average_score=Avg("marks_obtained"),
                    average_percentage=Avg("percentage"),
                    highest_score=Max("marks_obtained"),
                    lowest_score=Min("marks_obtained"),
                    total_marks_possible=Sum("assignment__total_marks"),
                    total_marks_obtained=Sum("marks_obtained"),
                    std_deviation=StdDev("percentage"),
                )

                # Grade distribution
                grade_distribution = {}
                for submission in graded_submissions:
                    grade = submission.calculate_grade()
                    grade_distribution[grade] = grade_distribution.get(grade, 0) + 1
            else:
                performance_stats = {
                    "average_score": 0,
                    "average_percentage": 0,
                    "highest_score": 0,
                    "lowest_score": 0,
                    "total_marks_possible": 0,
                    "total_marks_obtained": 0,
                    "std_deviation": 0,
                }
                grade_distribution = {}

            # Subject-wise performance
            subject_performance = (
                submissions.filter(status="graded", marks_obtained__isnull=False)
                .values("assignment__subject__name", "assignment__subject__code")
                .annotate(
                    assignment_count=Count("id"),
                    average_score=Avg("marks_obtained"),
                    average_percentage=Avg("percentage"),
                    total_marks=Sum("assignment__total_marks"),
                    obtained_marks=Sum("marks_obtained"),
                )
                .order_by("assignment__subject__name")
            )

            # Monthly trend analysis
            monthly_trends = (
                submissions.filter(status="graded", graded_at__isnull=False)
                .extra(select={"month": "DATE_TRUNC('month', graded_at)"})
                .values("month")
                .annotate(
                    assignment_count=Count("id"),
                    average_percentage=Avg("percentage"),
                    average_score=Avg("marks_obtained"),
                )
                .order_by("month")
            )

            # Difficulty level analysis
            difficulty_analysis = (
                submissions.filter(status="graded")
                .values("assignment__difficulty_level")
                .annotate(
                    assignment_count=Count("id"),
                    average_percentage=Avg("percentage"),
                    pass_rate=Avg(
                        Case(
                            When(
                                marks_obtained__gte=F("assignment__passing_marks"),
                                then=Value(1),
                            ),
                            default=Value(0),
                            output_field=FloatField(),
                        )
                    )
                    * 100,
                )
            )

            # Recent performance trend (last 10 assignments)
            recent_submissions = graded_submissions.order_by("-graded_at")[:10]
            recent_trend = [
                {
                    "assignment_title": sub.assignment.title,
                    "subject": sub.assignment.subject.name,
                    "percentage": float(sub.percentage) if sub.percentage else 0,
                    "grade": sub.calculate_grade(),
                    "graded_date": sub.graded_at,
                }
                for sub in recent_submissions
            ]

            # Strengths and weaknesses analysis
            strengths_weaknesses = (
                AssignmentAnalyticsService._analyze_strengths_weaknesses(
                    graded_submissions
                )
            )

            analytics = {
                "student_info": {
                    "id": student.id,
                    "name": student.user.get_full_name(),
                    "admission_number": student.admission_number,
                    "class": (
                        str(student.current_class_id)
                        if student.current_class_id
                        else None
                    ),
                },
                "basic_stats": basic_stats,
                "performance_stats": performance_stats,
                "grade_distribution": grade_distribution,
                "subject_performance": list(subject_performance),
                "monthly_trends": list(monthly_trends),
                "difficulty_analysis": list(difficulty_analysis),
                "recent_trend": recent_trend,
                "strengths_weaknesses": strengths_weaknesses,
                "recommendations": AssignmentAnalyticsService._generate_student_recommendations(
                    basic_stats, performance_stats, subject_performance
                ),
            }

            # Cache for 1 hour
            cache.set(cache_key, analytics, 3600)
            return analytics

        except Student.DoesNotExist:
            raise ValueError("Student not found")
        except Exception as e:
            logger.error(f"Error getting student analytics: {str(e)}")
            raise

    @staticmethod
    def get_teacher_analytics(teacher_id: int, filters: Dict = None) -> Dict:
        """
        Get comprehensive analytics for a teacher
        """
        try:
            cache_key = f"teacher_analytics_{teacher_id}_{hash(str(filters))}"
            cached_result = cache.get(cache_key)
            if cached_result:
                return cached_result

            teacher = Teacher.objects.get(id=teacher_id)
            assignments = Assignment.objects.filter(teacher=teacher)

            # Apply filters
            if filters:
                if filters.get("term"):
                    assignments = assignments.filter(term=filters["term"])
                if filters.get("subject"):
                    assignments = assignments.filter(subject=filters["subject"])
                if filters.get("class_id"):
                    assignments = assignments.filter(class_id=filters["class_id"])

            # Assignment statistics
            assignment_stats = {
                "total_assignments": assignments.count(),
                "published_assignments": assignments.filter(status="published").count(),
                "draft_assignments": assignments.filter(status="draft").count(),
                "closed_assignments": assignments.filter(status="closed").count(),
                "overdue_assignments": assignments.filter(
                    status="published", due_date__lt=timezone.now()
                ).count(),
            }

            # Submission and grading statistics
            all_submissions = AssignmentSubmission.objects.filter(
                assignment__teacher=teacher
            )
            if filters:
                if filters.get("term"):
                    all_submissions = all_submissions.filter(
                        assignment__term=filters["term"]
                    )
                if filters.get("subject"):
                    all_submissions = all_submissions.filter(
                        assignment__subject=filters["subject"]
                    )
                if filters.get("class_id"):
                    all_submissions = all_submissions.filter(
                        assignment__class_id=filters["class_id"]
                    )

            grading_stats = {
                "total_submissions": all_submissions.count(),
                "graded_submissions": all_submissions.filter(status="graded").count(),
                "pending_submissions": all_submissions.filter(
                    status="submitted"
                ).count(),
                "late_submissions": all_submissions.filter(is_late=True).count(),
                "average_grading_time": AssignmentAnalyticsService._calculate_average_grading_time(
                    all_submissions
                ),
            }

            # Class performance analysis
            class_performance = (
                assignments.values(
                    "class_id__id",
                    "class_id__name",
                    "class_id__grade__name",
                    "class_id__grade__section__name",
                )
                .annotate(
                    assignment_count=Count("id"),
                    total_submissions=Count("submissions"),
                    graded_submissions=Count(
                        "submissions", filter=Q(submissions__status="graded")
                    ),
                    average_score=Avg(
                        "submissions__marks_obtained",
                        filter=Q(submissions__status="graded"),
                    ),
                    completion_rate=Count("submissions")
                    * 100.0
                    / Count("class_id__students", distinct=True),
                )
                .order_by("class_id__grade__section__name", "class_id__grade__name")
            )

            # Subject performance analysis
            subject_performance = (
                assignments.values("subject__id", "subject__name", "subject__code")
                .annotate(
                    assignment_count=Count("id"),
                    average_score=Avg(
                        "submissions__marks_obtained",
                        filter=Q(submissions__status="graded"),
                    ),
                    completion_rate=Avg(
                        Case(
                            When(submissions__isnull=False, then=Value(1)),
                            default=Value(0),
                            output_field=FloatField(),
                        )
                    )
                    * 100,
                )
                .order_by("subject__name")
            )

            # Difficulty level effectiveness
            difficulty_effectiveness = assignments.values("difficulty_level").annotate(
                assignment_count=Count("id"),
                average_score=Avg(
                    "submissions__marks_obtained",
                    filter=Q(submissions__status="graded"),
                ),
                completion_rate=Count("submissions")
                * 100.0
                / (Count("id") * F("class_id__students")),
                student_satisfaction=Value(
                    0
                ),  # Would be calculated from feedback if available
            )

            # Grading distribution analysis
            grading_distribution = (
                all_submissions.filter(status="graded", marks_obtained__isnull=False)
                .extra(
                    select={
                        "grade": """
                        CASE 
                            WHEN (marks_obtained::float / assignment.total_marks * 100) >= 90 THEN 'A+'
                            WHEN (marks_obtained::float / assignment.total_marks * 100) >= 85 THEN 'A'
                            WHEN (marks_obtained::float / assignment.total_marks * 100) >= 80 THEN 'A-'
                            WHEN (marks_obtained::float / assignment.total_marks * 100) >= 75 THEN 'B+'
                            WHEN (marks_obtained::float / assignment.total_marks * 100) >= 70 THEN 'B'
                            WHEN (marks_obtained::float / assignment.total_marks * 100) >= 65 THEN 'B-'
                            WHEN (marks_obtained::float / assignment.total_marks * 100) >= 60 THEN 'C+'
                            WHEN (marks_obtained::float / assignment.total_marks * 100) >= 55 THEN 'C'
                            WHEN (marks_obtained::float / assignment.total_marks * 100) >= 50 THEN 'C-'
                            WHEN (marks_obtained::float / assignment.total_marks * 100) >= 45 THEN 'D'
                            ELSE 'F'
                        END
                    """
                    },
                    tables=["assignments_assignment"],
                )
                .values("grade")
                .annotate(count=Count("id"))
                .order_by("grade")
            )

            # Recent activity timeline
            recent_activity = AssignmentAnalyticsService._get_teacher_recent_activity(
                teacher, limit=20
            )

            analytics = {
                "teacher_info": {
                    "id": teacher.id,
                    "name": teacher.user.get_full_name(),
                    "employee_id": teacher.employee_id,
                    "department": (
                        teacher.department.name if teacher.department else None
                    ),
                },
                "assignment_stats": assignment_stats,
                "grading_stats": grading_stats,
                "class_performance": list(class_performance),
                "subject_performance": list(subject_performance),
                "difficulty_effectiveness": list(difficulty_effectiveness),
                "grading_distribution": list(grading_distribution),
                "recent_activity": recent_activity,
                "recommendations": AssignmentAnalyticsService._generate_teacher_recommendations(
                    assignment_stats, grading_stats, class_performance
                ),
            }

            # Cache for 30 minutes
            cache.set(cache_key, analytics, 1800)
            return analytics

        except Teacher.DoesNotExist:
            raise ValueError("Teacher not found")
        except Exception as e:
            logger.error(f"Error getting teacher analytics: {str(e)}")
            raise

    @staticmethod
    def get_class_analytics(class_id: int, filters: Dict = None) -> Dict:
        """
        Get comprehensive analytics for a class
        """
        try:
            cache_key = f"class_analytics_{class_id}_{hash(str(filters))}"
            cached_result = cache.get(cache_key)
            if cached_result:
                return cached_result

            from academics.models import Class

            class_obj = Class.objects.get(id=class_id)
            assignments = Assignment.objects.filter(class_id=class_obj)

            # Apply filters
            if filters:
                if filters.get("term"):
                    assignments = assignments.filter(term=filters["term"])
                if filters.get("subject"):
                    assignments = assignments.filter(subject=filters["subject"])
                if filters.get("teacher"):
                    assignments = assignments.filter(teacher=filters["teacher"])

            students = class_obj.students.filter(status="active")
            total_students = students.count()

            # Assignment overview
            assignment_overview = {
                "total_assignments": assignments.count(),
                "published_assignments": assignments.filter(status="published").count(),
                "total_students": total_students,
                "assignments_per_student": (
                    assignments.count() * total_students if total_students > 0 else 0
                ),
            }

            # Overall class performance
            all_submissions = AssignmentSubmission.objects.filter(
                assignment__class_id=class_obj,
                status="graded",
                marks_obtained__isnull=False,
            )

            if filters:
                if filters.get("term"):
                    all_submissions = all_submissions.filter(
                        assignment__term=filters["term"]
                    )
                if filters.get("subject"):
                    all_submissions = all_submissions.filter(
                        assignment__subject=filters["subject"]
                    )

            class_performance = all_submissions.aggregate(
                average_score=Avg("marks_obtained"),
                average_percentage=Avg("percentage"),
                highest_score=Max("marks_obtained"),
                lowest_score=Min("marks_obtained"),
                std_deviation=StdDev("percentage"),
            )

            # Student ranking
            student_rankings = (
                students.annotate(
                    assignment_count=Count(
                        "assignment_submissions",
                        filter=Q(
                            assignment_submissions__assignment__class_id=class_obj,
                            assignment_submissions__status="graded",
                        ),
                    ),
                    average_score=Avg(
                        "assignment_submissions__marks_obtained",
                        filter=Q(
                            assignment_submissions__assignment__class_id=class_obj,
                            assignment_submissions__status="graded",
                        ),
                    ),
                    average_percentage=Avg(
                        "assignment_submissions__percentage",
                        filter=Q(
                            assignment_submissions__assignment__class_id=class_obj,
                            assignment_submissions__status="graded",
                        ),
                    ),
                    total_marks=Sum(
                        "assignment_submissions__marks_obtained",
                        filter=Q(
                            assignment_submissions__assignment__class_id=class_obj,
                            assignment_submissions__status="graded",
                        ),
                    ),
                )
                .filter(assignment_count__gt=0)
                .order_by("-average_percentage")[:10]
            )

            # Subject-wise performance
            subject_performance = (
                assignments.values("subject__name", "subject__code")
                .annotate(
                    assignment_count=Count("id"),
                    submission_count=Count("submissions"),
                    graded_count=Count(
                        "submissions", filter=Q(submissions__status="graded")
                    ),
                    average_score=Avg(
                        "submissions__marks_obtained",
                        filter=Q(submissions__status="graded"),
                    ),
                    completion_rate=(
                        Count("submissions") * 100.0 / (Count("id") * total_students)
                        if total_students > 0
                        else 0
                    ),
                )
                .order_by("subject__name")
            )

            # Assignment difficulty vs performance
            difficulty_analysis = assignments.values("difficulty_level").annotate(
                assignment_count=Count("id"),
                average_score=Avg(
                    "submissions__marks_obtained",
                    filter=Q(submissions__status="graded"),
                ),
                completion_rate=(
                    Count("submissions") * 100.0 / (Count("id") * total_students)
                    if total_students > 0
                    else 0
                ),
                late_submission_rate=Count(
                    "submissions", filter=Q(submissions__is_late=True)
                )
                * 100.0
                / Count("submissions"),
            )

            # Time-based trends
            monthly_trends = (
                all_submissions.extra(
                    select={"month": "DATE_TRUNC('month', graded_at)"}
                )
                .values("month")
                .annotate(
                    assignment_count=Count("assignment", distinct=True),
                    submission_count=Count("id"),
                    average_percentage=Avg("percentage"),
                )
                .order_by("month")
            )

            # Top and bottom performers
            top_performers = list(student_rankings[:5])
            bottom_performers = list(
                student_rankings.order_by("average_percentage")[:5]
            )

            analytics = {
                "class_info": {
                    "id": class_obj.id,
                    "name": str(class_obj),
                    "grade": class_obj.grade.name,
                    "section": class_obj.grade.section.name,
                    "total_students": total_students,
                },
                "assignment_overview": assignment_overview,
                "class_performance": class_performance,
                "student_rankings": [
                    {
                        "student_id": student.id,
                        "name": student.user.get_full_name(),
                        "admission_number": student.admission_number,
                        "assignment_count": student.assignment_count,
                        "average_percentage": (
                            float(student.average_percentage)
                            if student.average_percentage
                            else 0
                        ),
                        "total_marks": student.total_marks or 0,
                    }
                    for student in student_rankings
                ],
                "subject_performance": list(subject_performance),
                "difficulty_analysis": list(difficulty_analysis),
                "monthly_trends": list(monthly_trends),
                "top_performers": [
                    {
                        "name": student.user.get_full_name(),
                        "average_percentage": (
                            float(student.average_percentage)
                            if student.average_percentage
                            else 0
                        ),
                    }
                    for student in top_performers
                ],
                "bottom_performers": [
                    {
                        "name": student.user.get_full_name(),
                        "average_percentage": (
                            float(student.average_percentage)
                            if student.average_percentage
                            else 0
                        ),
                    }
                    for student in bottom_performers
                ],
                "recommendations": AssignmentAnalyticsService._generate_class_recommendations(
                    assignment_overview, class_performance, subject_performance
                ),
            }

            # Cache for 45 minutes
            cache.set(cache_key, analytics, 2700)
            return analytics

        except Exception as e:
            logger.error(f"Error getting class analytics: {str(e)}")
            raise

    @staticmethod
    def get_system_wide_analytics(filters: Dict = None) -> Dict:
        """
        Get system-wide assignment analytics
        """
        try:
            cache_key = f"system_analytics_{hash(str(filters))}"
            cached_result = cache.get(cache_key)
            if cached_result:
                return cached_result

            # Base querysets
            assignments = Assignment.objects.all()
            submissions = AssignmentSubmission.objects.all()

            # Apply filters
            if filters:
                if filters.get("academic_year"):
                    assignments = assignments.filter(
                        term__academic_year=filters["academic_year"]
                    )
                    submissions = submissions.filter(
                        assignment__term__academic_year=filters["academic_year"]
                    )
                if filters.get("term"):
                    assignments = assignments.filter(term=filters["term"])
                    submissions = submissions.filter(assignment__term=filters["term"])
                if filters.get("date_from"):
                    assignments = assignments.filter(
                        created_at__gte=filters["date_from"]
                    )
                    submissions = submissions.filter(
                        submission_date__gte=filters["date_from"]
                    )
                if filters.get("date_to"):
                    assignments = assignments.filter(created_at__lte=filters["date_to"])
                    submissions = submissions.filter(
                        submission_date__lte=filters["date_to"]
                    )

            # Overall statistics
            overall_stats = {
                "total_assignments": assignments.count(),
                "total_submissions": submissions.count(),
                "total_teachers": assignments.values("teacher").distinct().count(),
                "total_students": submissions.values("student").distinct().count(),
                "total_classes": assignments.values("class_id").distinct().count(),
                "total_subjects": assignments.values("subject").distinct().count(),
            }

            # Assignment status distribution
            status_distribution = (
                assignments.values("status")
                .annotate(count=Count("id"))
                .order_by("status")
            )

            # Submission status distribution
            submission_status = (
                submissions.values("status")
                .annotate(count=Count("id"))
                .order_by("status")
            )

            # Performance metrics
            graded_submissions = submissions.filter(
                status="graded", marks_obtained__isnull=False
            )
            performance_metrics = graded_submissions.aggregate(
                average_score=Avg("marks_obtained"),
                average_percentage=Avg("percentage"),
                total_marks_possible=Sum("assignment__total_marks"),
                total_marks_obtained=Sum("marks_obtained"),
            )

            # Section-wise analysis
            section_analysis = (
                assignments.values("class_id__grade__section__name")
                .annotate(
                    assignment_count=Count("id"),
                    student_count=Count("class_id__students", distinct=True),
                    submission_count=Count("submissions"),
                    average_score=Avg(
                        "submissions__marks_obtained",
                        filter=Q(submissions__status="graded"),
                    ),
                )
                .order_by("class_id__grade__section__name")
            )

            # Subject popularity and performance
            subject_analysis = (
                assignments.values("subject__name", "subject__code")
                .annotate(
                    assignment_count=Count("id"),
                    teacher_count=Count("teacher", distinct=True),
                    submission_count=Count("submissions"),
                    average_score=Avg(
                        "submissions__marks_obtained",
                        filter=Q(submissions__status="graded"),
                    ),
                    completion_rate=Count("submissions") * 100.0 / Count("id"),
                )
                .order_by("-assignment_count")
            )

            # Monthly trends
            monthly_trends = (
                assignments.extra(select={"month": "DATE_TRUNC('month', created_at)"})
                .values("month")
                .annotate(
                    assignment_count=Count("id"),
                    submission_count=Count("submissions"),
                    teacher_count=Count("teacher", distinct=True),
                )
                .order_by("month")
            )

            # Teacher activity analysis
            teacher_activity = (
                assignments.values(
                    "teacher__user__first_name",
                    "teacher__user__last_name",
                    "teacher__employee_id",
                )
                .annotate(
                    assignment_count=Count("id"),
                    submission_count=Count("submissions"),
                    graded_count=Count(
                        "submissions", filter=Q(submissions__status="graded")
                    ),
                    average_grading_time=Avg(
                        F("submissions__graded_at") - F("submissions__submission_date"),
                        filter=Q(submissions__status="graded"),
                    ),
                )
                .order_by("-assignment_count")[:20]
            )

            # Late submission analysis
            late_submission_stats = {
                "total_late_submissions": submissions.filter(is_late=True).count(),
                "late_submission_rate": (
                    submissions.filter(is_late=True).count()
                    * 100.0
                    / submissions.count()
                    if submissions.count() > 0
                    else 0
                ),
                "average_days_late": submissions.filter(is_late=True).aggregate(
                    avg_days=Avg(
                        (F("submission_date") - F("assignment__due_date"))
                        .resolve_expression()
                        .source_expressions[0]
                    )
                )["avg_days"]
                or 0,
            }

            analytics = {
                "overall_stats": overall_stats,
                "status_distribution": list(status_distribution),
                "submission_status": list(submission_status),
                "performance_metrics": performance_metrics,
                "section_analysis": list(section_analysis),
                "subject_analysis": list(subject_analysis),
                "monthly_trends": list(monthly_trends),
                "teacher_activity": list(teacher_activity),
                "late_submission_stats": late_submission_stats,
                "recommendations": AssignmentAnalyticsService._generate_system_recommendations(
                    overall_stats, performance_metrics, late_submission_stats
                ),
            }

            # Cache for 1 hour
            cache.set(cache_key, analytics, 3600)
            return analytics

        except Exception as e:
            logger.error(f"Error getting system analytics: {str(e)}")
            raise

    @staticmethod
    def _analyze_strengths_weaknesses(submissions):
        """
        Analyze student strengths and weaknesses based on submissions
        """
        try:
            subject_performance = defaultdict(list)
            difficulty_performance = defaultdict(list)

            for submission in submissions:
                if submission.percentage:
                    subject_performance[submission.assignment.subject.name].append(
                        submission.percentage
                    )
                    difficulty_performance[
                        submission.assignment.difficulty_level
                    ].append(submission.percentage)

            # Calculate averages
            subject_averages = {
                subject: sum(scores) / len(scores)
                for subject, scores in subject_performance.items()
            }

            difficulty_averages = {
                difficulty: sum(scores) / len(scores)
                for difficulty, scores in difficulty_performance.items()
            }

            # Identify strengths (above average) and weaknesses (below average)
            overall_average = (
                sum(subject_averages.values()) / len(subject_averages)
                if subject_averages
                else 0
            )

            strengths = [
                subject
                for subject, avg in subject_averages.items()
                if avg > overall_average + 5  # 5% above average
            ]

            weaknesses = [
                subject
                for subject, avg in subject_averages.items()
                if avg < overall_average - 5  # 5% below average
            ]

            return {
                "subject_averages": subject_averages,
                "difficulty_averages": difficulty_averages,
                "overall_average": overall_average,
                "strengths": strengths,
                "weaknesses": weaknesses,
            }

        except Exception as e:
            logger.error(f"Error analyzing strengths and weaknesses: {str(e)}")
            return {"strengths": [], "weaknesses": [], "subject_averages": {}}

    @staticmethod
    def _calculate_average_grading_time(submissions):
        """
        Calculate average time taken to grade submissions
        """
        try:
            graded_submissions = submissions.filter(
                status="graded", graded_at__isnull=False, submission_date__isnull=False
            )

            if not graded_submissions.exists():
                return 0

            total_time = timedelta()
            count = 0

            for submission in graded_submissions:
                time_diff = submission.graded_at - submission.submission_date
                total_time += time_diff
                count += 1

            if count > 0:
                average_time = total_time / count
                return average_time.total_seconds() / 3600  # Return hours

            return 0

        except Exception as e:
            logger.error(f"Error calculating average grading time: {str(e)}")
            return 0

    @staticmethod
    def _get_teacher_recent_activity(teacher, limit=20):
        """
        Get recent activity for a teacher
        """
        try:
            activities = []

            # Recent assignments
            recent_assignments = Assignment.objects.filter(teacher=teacher).order_by(
                "-created_at"
            )[: limit // 2]

            for assignment in recent_assignments:
                activities.append(
                    {
                        "type": "assignment_created",
                        "timestamp": assignment.created_at,
                        "description": f"Created assignment: {assignment.title}",
                        "entity_id": assignment.id,
                    }
                )

            # Recent grading
            recent_grading = AssignmentSubmission.objects.filter(
                assignment__teacher=teacher, graded_by=teacher, graded_at__isnull=False
            ).order_by("-graded_at")[: limit // 2]

            for submission in recent_grading:
                activities.append(
                    {
                        "type": "submission_graded",
                        "timestamp": submission.graded_at,
                        "description": f"Graded submission for: {submission.assignment.title}",
                        "entity_id": submission.id,
                    }
                )

            # Sort by timestamp and limit
            activities.sort(key=lambda x: x["timestamp"], reverse=True)
            return activities[:limit]

        except Exception as e:
            logger.error(f"Error getting teacher activity: {str(e)}")
            return []

    @staticmethod
    def _generate_student_recommendations(
        basic_stats, performance_stats, subject_performance
    ):
        """
        Generate recommendations for student improvement
        """
        recommendations = []

        try:
            # Submission rate recommendations
            if basic_stats["submission_rate"] < 80:
                recommendations.append(
                    {
                        "type": "improvement",
                        "category": "submission_rate",
                        "message": "Focus on submitting assignments on time to improve your academic performance.",
                        "priority": "high",
                    }
                )

            # Performance recommendations
            if performance_stats["average_percentage"] < 60:
                recommendations.append(
                    {
                        "type": "improvement",
                        "category": "performance",
                        "message": "Consider seeking additional help or tutoring to improve your grades.",
                        "priority": "high",
                    }
                )
            elif performance_stats["average_percentage"] > 85:
                recommendations.append(
                    {
                        "type": "praise",
                        "category": "performance",
                        "message": "Excellent work! Keep maintaining your high performance.",
                        "priority": "low",
                    }
                )

            # Subject-specific recommendations
            if subject_performance:
                subject_list = list(subject_performance)
                if len(subject_list) > 1:
                    weakest_subject = min(
                        subject_list, key=lambda x: x["average_percentage"]
                    )
                    if weakest_subject["average_percentage"] < 70:
                        recommendations.append(
                            {
                                "type": "improvement",
                                "category": "subject_focus",
                                "message": f"Focus more attention on {weakest_subject['assignment__subject__name']} assignments.",
                                "priority": "medium",
                            }
                        )

            # Late submission recommendations
            if (
                basic_stats["late_submissions"]
                > basic_stats["submitted_assignments"] * 0.2
            ):
                recommendations.append(
                    {
                        "type": "improvement",
                        "category": "time_management",
                        "message": "Work on time management skills to reduce late submissions.",
                        "priority": "medium",
                    }
                )

        except Exception as e:
            logger.error(f"Error generating student recommendations: {str(e)}")

        return recommendations

    @staticmethod
    def _generate_teacher_recommendations(
        assignment_stats, grading_stats, class_performance
    ):
        """
        Generate recommendations for teacher improvement
        """
        recommendations = []

        try:
            # Grading efficiency recommendations
            grading_rate = (
                (
                    grading_stats["graded_submissions"]
                    / grading_stats["total_submissions"]
                    * 100
                )
                if grading_stats["total_submissions"] > 0
                else 0
            )

            if grading_rate < 80:
                recommendations.append(
                    {
                        "type": "improvement",
                        "category": "grading_efficiency",
                        "message": "Consider speeding up grading process to provide timely feedback.",
                        "priority": "medium",
                    }
                )

            # Assignment frequency recommendations
            if assignment_stats["total_assignments"] < 5:
                recommendations.append(
                    {
                        "type": "suggestion",
                        "category": "assignment_frequency",
                        "message": "Consider creating more assignments for better assessment coverage.",
                        "priority": "low",
                    }
                )

            # Class performance recommendations
            if class_performance:
                avg_completion = sum(
                    cls["completion_rate"] for cls in class_performance
                ) / len(class_performance)
                if avg_completion < 70:
                    recommendations.append(
                        {
                            "type": "improvement",
                            "category": "engagement",
                            "message": "Low completion rates suggest need for more engaging assignments.",
                            "priority": "high",
                        }
                    )

        except Exception as e:
            logger.error(f"Error generating teacher recommendations: {str(e)}")

        return recommendations

    @staticmethod
    def _generate_class_recommendations(
        assignment_overview, class_performance, subject_performance
    ):
        """
        Generate recommendations for class improvement
        """
        recommendations = []

        try:
            # Overall performance recommendations
            if class_performance.get("average_percentage", 0) < 70:
                recommendations.append(
                    {
                        "type": "intervention",
                        "category": "class_performance",
                        "message": "Class performance is below average. Consider additional support measures.",
                        "priority": "high",
                    }
                )

            # Subject-specific recommendations
            if subject_performance:
                weak_subjects = [
                    subject
                    for subject in subject_performance
                    if subject["average_score"] and subject["average_score"] < 60
                ]

                if weak_subjects:
                    recommendations.append(
                        {
                            "type": "focus",
                            "category": "subject_support",
                            "message": f"Provide additional support for: {', '.join([s['subject__name'] for s in weak_subjects])}",
                            "priority": "medium",
                        }
                    )

        except Exception as e:
            logger.error(f"Error generating class recommendations: {str(e)}")

        return recommendations

    @staticmethod
    def _generate_system_recommendations(
        overall_stats, performance_metrics, late_submission_stats
    ):
        """
        Generate system-wide recommendations
        """
        recommendations = []

        try:
            # Late submission recommendations
            if late_submission_stats["late_submission_rate"] > 20:
                recommendations.append(
                    {
                        "type": "policy",
                        "category": "deadline_management",
                        "message": "High late submission rate suggests need for better deadline management policies.",
                        "priority": "medium",
                    }
                )

            # Performance recommendations
            if performance_metrics.get("average_percentage", 0) < 70:
                recommendations.append(
                    {
                        "type": "system_improvement",
                        "category": "academic_support",
                        "message": "System-wide performance below target. Consider academic support programs.",
                        "priority": "high",
                    }
                )

            # Teacher activity recommendations
            avg_assignments_per_teacher = (
                overall_stats["total_assignments"] / overall_stats["total_teachers"]
                if overall_stats["total_teachers"] > 0
                else 0
            )
            if avg_assignments_per_teacher < 3:
                recommendations.append(
                    {
                        "type": "training",
                        "category": "teacher_engagement",
                        "message": "Low average assignments per teacher. Consider training on assignment creation.",
                        "priority": "low",
                    }
                )

        except Exception as e:
            logger.error(f"Error generating system recommendations: {str(e)}")

        return recommendations
