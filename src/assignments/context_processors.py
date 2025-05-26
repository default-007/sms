from django.utils import timezone
from django.db.models import Q, Count, Avg, Sum
from django.core.cache import cache
from datetime import datetime, timedelta
import logging

from .models import Assignment, AssignmentSubmission
from .services import AssignmentService, SubmissionService, DeadlineService
from .services.analytics_service import AssignmentAnalyticsService

logger = logging.getLogger(__name__)


def teacher_assignments(request):
    """
    Context processor for teacher assignment dashboard widget
    """
    try:
        if not hasattr(request.user, "teacher"):
            return {}

        teacher = request.user.teacher
        cache_key = f"teacher_assignments_widget_{teacher.id}"
        cached_data = cache.get(cache_key)

        if cached_data:
            return cached_data

        # Get teacher assignments summary
        assignments = Assignment.objects.filter(teacher=teacher)

        # Basic counts
        total_assignments = assignments.count()
        draft_assignments = assignments.filter(status="draft").count()
        published_assignments = assignments.filter(status="published").count()
        closed_assignments = assignments.filter(status="closed").count()

        # Overdue assignments
        overdue_assignments = assignments.filter(
            status="published", due_date__lt=timezone.now()
        ).count()

        # Recent assignments (last 5)
        recent_assignments = assignments.select_related(
            "class_id__grade__section", "subject"
        ).order_by("-created_at")[:5]

        # Due soon assignments (next 7 days)
        due_soon_date = timezone.now() + timedelta(days=7)
        due_soon = assignments.filter(
            status="published", due_date__range=[timezone.now(), due_soon_date]
        ).order_by("due_date")[:5]

        context_data = {
            "teacher_assignment_stats": {
                "total": total_assignments,
                "draft": draft_assignments,
                "published": published_assignments,
                "closed": closed_assignments,
                "overdue": overdue_assignments,
            },
            "teacher_recent_assignments": recent_assignments,
            "teacher_due_soon_assignments": due_soon,
        }

        # Cache for 15 minutes
        cache.set(cache_key, context_data, 900)
        return context_data

    except Exception as e:
        logger.error(f"Error in teacher_assignments context processor: {str(e)}")
        return {}


def pending_grading(request):
    """
    Context processor for pending grading widget
    """
    try:
        if not hasattr(request.user, "teacher"):
            return {}

        teacher = request.user.teacher
        cache_key = f"pending_grading_widget_{teacher.id}"
        cached_data = cache.get(cache_key)

        if cached_data:
            return cached_data

        # Get pending submissions
        pending_submissions = (
            AssignmentSubmission.objects.filter(
                assignment__teacher=teacher, status="submitted"
            )
            .select_related("assignment", "student__user")
            .order_by("-submission_date")
        )

        total_pending = pending_submissions.count()

        # Get grading statistics
        all_submissions = AssignmentSubmission.objects.filter(
            assignment__teacher=teacher
        )

        total_submissions = all_submissions.count()
        graded_submissions = all_submissions.filter(status="graded").count()
        grading_rate = (
            (graded_submissions / total_submissions * 100)
            if total_submissions > 0
            else 0
        )

        # Recent pending submissions (last 10)
        recent_pending = pending_submissions[:10]

        # Late submissions
        late_submissions = pending_submissions.filter(is_late=True).count()

        # Oldest pending submission
        oldest_pending = pending_submissions.order_by("submission_date").first()

        context_data = {
            "pending_grading_stats": {
                "total_pending": total_pending,
                "total_submissions": total_submissions,
                "graded_submissions": graded_submissions,
                "grading_rate": round(grading_rate, 1),
                "late_submissions": late_submissions,
            },
            "recent_pending_submissions": recent_pending,
            "oldest_pending_submission": oldest_pending,
        }

        # Cache for 10 minutes
        cache.set(cache_key, context_data, 600)
        return context_data

    except Exception as e:
        logger.error(f"Error in pending_grading context processor: {str(e)}")
        return {}


def assignment_analytics(request):
    """
    Context processor for assignment analytics widget
    """
    try:
        if not hasattr(request.user, "teacher"):
            return {}

        teacher = request.user.teacher
        cache_key = f"assignment_analytics_widget_{teacher.id}"
        cached_data = cache.get(cache_key)

        if cached_data:
            return cached_data

        # Get analytics data
        analytics = AssignmentAnalyticsService.get_teacher_analytics(teacher.id)

        # Get subject performance
        subject_performance = []
        for subject_data in analytics.get("subject_performance", []):
            subject_performance.append(
                {
                    "name": subject_data["subject__name"],
                    "assignment_count": subject_data["assignment_count"],
                    "average_score": subject_data["average_score"] or 0,
                    "completion_rate": subject_data["completion_rate"] or 0,
                }
            )

        # Get recent trends (last 30 days)
        recent_assignments = Assignment.objects.filter(
            teacher=teacher, created_at__gte=timezone.now() - timedelta(days=30)
        ).select_related("subject")

        trends = []
        for assignment in recent_assignments:
            submission_count = assignment.submissions.count()
            graded_count = assignment.submissions.filter(status="graded").count()

            trends.append(
                {
                    "title": assignment.title,
                    "subject": assignment.subject.name,
                    "submission_count": submission_count,
                    "completion_rate": assignment.completion_rate,
                    "average_score": assignment.average_score,
                }
            )

        context_data = {
            "assignment_analytics_summary": {
                "total_assignments": analytics["assignment_stats"]["total_assignments"],
                "total_submissions": analytics["grading_stats"]["total_submissions"],
                "grading_rate": analytics["grading_stats"].get("grading_rate", 0),
                "most_common_grades": analytics["grading_stats"].get(
                    "most_common_grades", {}
                ),
            },
            "subject_performance": subject_performance[:5],  # Top 5 subjects
            "recent_trends": trends[:10],  # Last 10 assignments
        }

        # Cache for 30 minutes
        cache.set(cache_key, context_data, 1800)
        return context_data

    except Exception as e:
        logger.error(f"Error in assignment_analytics context processor: {str(e)}")
        return {}


def student_assignments(request):
    """
    Context processor for student assignment dashboard widget
    """
    try:
        if not hasattr(request.user, "student"):
            return {}

        student = request.user.student
        cache_key = f"student_assignments_widget_{student.id}"
        cached_data = cache.get(cache_key)

        if cached_data:
            return cached_data

        # Get student's class assignments
        class_assignments = Assignment.objects.filter(
            class_id=student.current_class_id, status="published"
        ).select_related("subject")

        total_assignments = class_assignments.count()

        # Get submission status
        student_submissions = AssignmentSubmission.objects.filter(
            student=student
        ).values_list("assignment_id", flat=True)

        submitted_count = len(student_submissions)
        pending_count = total_assignments - submitted_count

        # Get graded submissions
        graded_submissions = AssignmentSubmission.objects.filter(
            student=student, status="graded"
        )
        graded_count = graded_submissions.count()

        # Calculate average performance
        average_percentage = (
            graded_submissions.aggregate(avg_percentage=Avg("percentage"))[
                "avg_percentage"
            ]
            or 0
        )

        # Recent assignments (last 5)
        recent_assignments = class_assignments.order_by("-created_at")[:5]

        # Upcoming deadlines (next 7 days)
        upcoming_deadline_date = timezone.now() + timedelta(days=7)
        upcoming_assignments = (
            class_assignments.filter(
                due_date__range=[timezone.now(), upcoming_deadline_date]
            )
            .exclude(id__in=student_submissions)
            .order_by("due_date")[:5]
        )

        # Recent grades
        recent_grades = graded_submissions.select_related(
            "assignment__subject"
        ).order_by("-graded_at")[:5]

        context_data = {
            "student_assignment_stats": {
                "total": total_assignments,
                "submitted": submitted_count,
                "pending": pending_count,
                "graded": graded_count,
                "average_percentage": round(average_percentage, 1),
            },
            "student_recent_assignments": recent_assignments,
            "student_upcoming_assignments": upcoming_assignments,
            "student_recent_grades": recent_grades,
        }

        # Cache for 15 minutes
        cache.set(cache_key, context_data, 900)
        return context_data

    except Exception as e:
        logger.error(f"Error in student_assignments context processor: {str(e)}")
        return {}


def upcoming_deadlines(request):
    """
    Context processor for upcoming deadlines widget
    """
    try:
        user = request.user
        cache_key = f"upcoming_deadlines_widget_{user.id}"
        cached_data = cache.get(cache_key)

        if cached_data:
            return cached_data

        deadlines = []

        if hasattr(user, "student"):
            deadlines = DeadlineService.get_upcoming_deadlines(
                "student", user.student.id, 14
            )
        elif hasattr(user, "teacher"):
            deadlines = DeadlineService.get_upcoming_deadlines(
                "teacher", user.teacher.id, 14
            )

        # Categorize deadlines
        urgent_deadlines = [d for d in deadlines if d["days_until_due"] <= 2]
        soon_deadlines = [d for d in deadlines if 2 < d["days_until_due"] <= 7]
        later_deadlines = [d for d in deadlines if d["days_until_due"] > 7]

        context_data = {
            "upcoming_deadlines": {
                "urgent": urgent_deadlines[:5],
                "soon": soon_deadlines[:5],
                "later": later_deadlines[:5],
                "total_count": len(deadlines),
            }
        }

        # Cache for 30 minutes
        cache.set(cache_key, context_data, 1800)
        return context_data

    except Exception as e:
        logger.error(f"Error in upcoming_deadlines context processor: {str(e)}")
        return {}


def student_performance(request):
    """
    Context processor for student performance widget
    """
    try:
        if not hasattr(request.user, "student"):
            return {}

        student = request.user.student
        cache_key = f"student_performance_widget_{student.id}"
        cached_data = cache.get(cache_key)

        if cached_data:
            return cached_data

        # Get detailed analytics
        analytics = AssignmentAnalyticsService.get_student_performance_analytics(
            student.id
        )

        # Extract key performance indicators
        performance_stats = analytics.get("performance_stats", {})
        subject_performance = analytics.get("subject_performance", [])

        # Calculate grade distribution percentages
        grade_distribution = analytics.get("grade_distribution", {})
        total_graded = sum(grade_distribution.values())

        grade_percentages = {}
        if total_graded > 0:
            for grade, count in grade_distribution.items():
                grade_percentages[grade] = round((count / total_graded) * 100, 1)

        # Get improvement trend (last 5 assignments)
        recent_trend = analytics.get("recent_trend", [])[:5]

        # Calculate performance indicators
        performance_indicators = {
            "overall_grade": (
                "A"
                if performance_stats.get("average_percentage", 0) >= 85
                else (
                    "B"
                    if performance_stats.get("average_percentage", 0) >= 75
                    else (
                        "C"
                        if performance_stats.get("average_percentage", 0) >= 65
                        else (
                            "D"
                            if performance_stats.get("average_percentage", 0) >= 50
                            else "F"
                        )
                    )
                )
            ),
            "consistency": (
                "High"
                if performance_stats.get("std_deviation", 100) < 10
                else (
                    "Medium"
                    if performance_stats.get("std_deviation", 100) < 20
                    else "Low"
                )
            ),
            "improvement_trend": calculate_improvement_trend(recent_trend),
        }

        context_data = {
            "student_performance_summary": {
                "average_percentage": round(
                    performance_stats.get("average_percentage", 0), 1
                ),
                "total_assignments": analytics["basic_stats"]["total_assignments"],
                "graded_assignments": analytics["basic_stats"]["graded_assignments"],
                "submission_rate": round(
                    analytics["basic_stats"]["submission_rate"], 1
                ),
            },
            "grade_distribution": grade_percentages,
            "subject_performance": subject_performance[:5],  # Top 5 subjects
            "recent_trend": recent_trend,
            "performance_indicators": performance_indicators,
            "strengths_weaknesses": analytics.get("strengths_weaknesses", {}),
        }

        # Cache for 20 minutes
        cache.set(cache_key, context_data, 1200)
        return context_data

    except Exception as e:
        logger.error(f"Error in student_performance context processor: {str(e)}")
        return {}


def parent_assignments(request):
    """
    Context processor for parent assignment overview widget
    """
    try:
        if not hasattr(request.user, "parent"):
            return {}

        parent = request.user.parent
        cache_key = f"parent_assignments_widget_{parent.id}"
        cached_data = cache.get(cache_key)

        if cached_data:
            return cached_data

        # Get all children
        children = parent.children.filter(status="active")

        children_data = []
        for child in children:
            # Get child's assignments
            class_assignments = Assignment.objects.filter(
                class_id=child.current_class_id, status="published"
            )

            # Get submission status
            submitted_assignments = AssignmentSubmission.objects.filter(
                student=child
            ).values_list("assignment_id", flat=True)

            # Get recent grades
            recent_grades = (
                AssignmentSubmission.objects.filter(student=child, status="graded")
                .select_related("assignment__subject")
                .order_by("-graded_at")[:3]
            )

            # Calculate average performance
            graded_submissions = AssignmentSubmission.objects.filter(
                student=child, status="graded"
            )

            average_percentage = (
                graded_submissions.aggregate(avg_percentage=Avg("percentage"))[
                    "avg_percentage"
                ]
                or 0
            )

            # Upcoming deadlines
            upcoming_deadline_date = timezone.now() + timedelta(days=7)
            upcoming_assignments = (
                class_assignments.filter(
                    due_date__range=[timezone.now(), upcoming_deadline_date]
                )
                .exclude(id__in=submitted_assignments)
                .order_by("due_date")[:3]
            )

            children_data.append(
                {
                    "child": child,
                    "stats": {
                        "total_assignments": class_assignments.count(),
                        "submitted": len(submitted_assignments),
                        "pending": class_assignments.count()
                        - len(submitted_assignments),
                        "average_percentage": round(average_percentage, 1),
                    },
                    "recent_grades": recent_grades,
                    "upcoming_assignments": upcoming_assignments,
                }
            )

        context_data = {
            "parent_children_data": children_data,
            "total_children": children.count(),
        }

        # Cache for 20 minutes
        cache.set(cache_key, context_data, 1200)
        return context_data

    except Exception as e:
        logger.error(f"Error in parent_assignments context processor: {str(e)}")
        return {}


def assignment_notifications(request):
    """
    Context processor for assignment-related notifications
    """
    try:
        user = request.user
        cache_key = f"assignment_notifications_{user.id}"
        cached_data = cache.get(cache_key)

        if cached_data:
            return cached_data

        notifications = []

        if hasattr(user, "teacher"):
            teacher = user.teacher

            # Pending grading notifications
            pending_count = AssignmentSubmission.objects.filter(
                assignment__teacher=teacher, status="submitted"
            ).count()

            if pending_count > 0:
                notifications.append(
                    {
                        "type": "pending_grading",
                        "message": f"You have {pending_count} submissions pending grading",
                        "count": pending_count,
                        "priority": "medium",
                    }
                )

            # Overdue assignments
            overdue_count = Assignment.objects.filter(
                teacher=teacher, status="published", due_date__lt=timezone.now()
            ).count()

            if overdue_count > 0:
                notifications.append(
                    {
                        "type": "overdue_assignments",
                        "message": f"You have {overdue_count} overdue assignments",
                        "count": overdue_count,
                        "priority": "high",
                    }
                )

        elif hasattr(user, "student"):
            student = user.student

            # Upcoming deadlines
            upcoming_deadline_date = timezone.now() + timedelta(days=2)
            upcoming_assignments = Assignment.objects.filter(
                class_id=student.current_class_id,
                status="published",
                due_date__range=[timezone.now(), upcoming_deadline_date],
            ).exclude(submissions__student=student)

            upcoming_count = upcoming_assignments.count()
            if upcoming_count > 0:
                notifications.append(
                    {
                        "type": "upcoming_deadlines",
                        "message": f"You have {upcoming_count} assignments due soon",
                        "count": upcoming_count,
                        "priority": "high",
                    }
                )

            # New grades available
            new_grades_count = AssignmentSubmission.objects.filter(
                student=student,
                status="graded",
                graded_at__gte=timezone.now() - timedelta(days=7),
            ).count()

            if new_grades_count > 0:
                notifications.append(
                    {
                        "type": "new_grades",
                        "message": f"You have {new_grades_count} new grades available",
                        "count": new_grades_count,
                        "priority": "low",
                    }
                )

        context_data = {
            "assignment_notifications": notifications,
            "notification_count": len(notifications),
        }

        # Cache for 5 minutes
        cache.set(cache_key, context_data, 300)
        return context_data

    except Exception as e:
        logger.error(f"Error in assignment_notifications context processor: {str(e)}")
        return {}


def global_assignment_stats(request):
    """
    Global assignment statistics for admin dashboard
    """
    try:
        if not request.user.is_staff:
            return {}

        cache_key = "global_assignment_stats"
        cached_data = cache.get(cache_key)

        if cached_data:
            return cached_data

        # Get system-wide statistics
        total_assignments = Assignment.objects.count()
        total_submissions = AssignmentSubmission.objects.count()
        pending_grading = AssignmentSubmission.objects.filter(
            status="submitted"
        ).count()

        # Today's activity
        today = timezone.now().date()
        today_assignments = Assignment.objects.filter(created_at__date=today).count()
        today_submissions = AssignmentSubmission.objects.filter(
            submission_date__date=today
        ).count()

        # This week's stats
        week_start = timezone.now() - timedelta(days=7)
        week_assignments = Assignment.objects.filter(created_at__gte=week_start).count()
        week_submissions = AssignmentSubmission.objects.filter(
            submission_date__gte=week_start
        ).count()

        context_data = {
            "global_assignment_stats": {
                "total_assignments": total_assignments,
                "total_submissions": total_submissions,
                "pending_grading": pending_grading,
                "today_assignments": today_assignments,
                "today_submissions": today_submissions,
                "week_assignments": week_assignments,
                "week_submissions": week_submissions,
            }
        }

        # Cache for 1 hour
        cache.set(cache_key, context_data, 3600)
        return context_data

    except Exception as e:
        logger.error(f"Error in global_assignment_stats context processor: {str(e)}")
        return {}


def calculate_improvement_trend(recent_submissions):
    """
    Calculate improvement trend from recent submissions
    """
    try:
        if len(recent_submissions) < 2:
            return "Insufficient Data"

        # Calculate trend based on last 3 vs previous submissions
        if len(recent_submissions) >= 3:
            recent_avg = sum(s["percentage"] for s in recent_submissions[:3]) / 3
            older_avg = sum(s["percentage"] for s in recent_submissions[3:]) / len(
                recent_submissions[3:]
            )
        else:
            recent_avg = recent_submissions[0]["percentage"]
            older_avg = recent_submissions[1]["percentage"]

        if recent_avg > older_avg + 5:
            return "Improving"
        elif recent_avg < older_avg - 5:
            return "Declining"
        else:
            return "Stable"

    except Exception as e:
        logger.error(f"Error calculating improvement trend: {str(e)}")
        return "Unknown"
