"""
Celery tasks for the subjects module.

This module contains background tasks for analytics calculation,
notifications, data processing, and other asynchronous operations.
"""

import logging
from datetime import date, datetime, timedelta

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.db.models import Avg, Count, Q, Sum
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from academics.models import AcademicYear, Department, Grade, Term
from analytics.models import (
    AttendanceAnalytics,
    ClassPerformanceAnalytics,
    FinancialAnalytics,
    StudentPerformanceAnalytics,
)
from communications.models import Notification

from .models import Subject, SubjectAssignment, Syllabus, TopicProgress
from .services import CurriculumService, SubjectAnalyticsService, SyllabusService
from .utils import CacheManager, calculate_risk_assessment

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def recalculate_curriculum_analytics(self, academic_year_id, department_id=None):
    """
    Recalculate curriculum analytics for an academic year.

    Args:
        academic_year_id: ID of the academic year
        department_id: Optional department ID for filtering
    """
    try:
        logger.info(
            f"Starting curriculum analytics calculation for academic year {academic_year_id}"
        )

        # Get analytics data
        analytics_data = CurriculumService.get_curriculum_analytics(
            academic_year_id, department_id=department_id
        )

        # Cache the results
        CacheManager.cache_curriculum_analytics(
            academic_year_id, department_id, analytics_data
        )

        logger.info(
            f"Completed curriculum analytics calculation for academic year {academic_year_id}"
        )

        return {
            "status": "success",
            "academic_year_id": academic_year_id,
            "department_id": department_id,
            "total_syllabi": analytics_data.get("overview", {}).get("total_syllabi", 0),
        }

    except Exception as exc:
        logger.error(f"Error calculating curriculum analytics: {str(exc)}")

        # Retry the task
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=60 * (self.request.retries + 1), exc=exc)

        return {
            "status": "error",
            "error": str(exc),
            "academic_year_id": academic_year_id,
            "department_id": department_id,
        }


@shared_task(bind=True, max_retries=3)
def update_syllabus_completion_percentages(self):
    """
    Update completion percentages for all active syllabi.
    This task should be run periodically to ensure data consistency.
    """
    try:
        logger.info("Starting syllabus completion percentage update")

        updated_count = 0
        syllabi = Syllabus.objects.filter(is_active=True).select_related(
            "subject", "grade"
        )

        for syllabus in syllabi:
            old_percentage = syllabus.completion_percentage
            syllabus.update_completion_percentage()

            if abs(old_percentage - syllabus.completion_percentage) > 0.01:
                updated_count += 1

                # Clear related cache
                CacheManager.clear_related_caches(syllabus)

        logger.info(f"Updated completion percentages for {updated_count} syllabi")

        return {
            "status": "success",
            "updated_count": updated_count,
            "total_syllabi": syllabi.count(),
        }

    except Exception as exc:
        logger.error(f"Error updating completion percentages: {str(exc)}")

        if self.request.retries < self.max_retries:
            raise self.retry(countdown=60 * (self.request.retries + 1), exc=exc)

        return {"status": "error", "error": str(exc)}


@shared_task(bind=True, max_retries=3)
def send_syllabus_deadline_alerts(self):
    """
    Send alerts for syllabi that are behind schedule or approaching deadlines.
    """
    try:
        logger.info("Starting syllabus deadline alert check")

        current_date = date.today()
        alerts_sent = 0

        # Get active syllabi in current terms
        current_terms = Term.objects.filter(
            start_date__lte=current_date, end_date__gte=current_date
        )

        syllabi = Syllabus.objects.filter(
            term__in=current_terms, is_active=True
        ).select_related("subject", "grade", "term", "academic_year")

        for syllabus in syllabi:
            risk_assessment = calculate_risk_assessment(syllabus)

            # Send alerts for high and medium risk syllabi
            if risk_assessment["risk_level"] in ["high", "medium"]:
                alert_sent = send_individual_syllabus_alert.delay(
                    syllabus.id, risk_assessment
                )
                if alert_sent:
                    alerts_sent += 1

        logger.info(f"Processed {syllabi.count()} syllabi, sent {alerts_sent} alerts")

        return {
            "status": "success",
            "syllabi_processed": syllabi.count(),
            "alerts_sent": alerts_sent,
        }

    except Exception as exc:
        logger.error(f"Error checking syllabus deadlines: {str(exc)}")

        if self.request.retries < self.max_retries:
            raise self.retry(countdown=60 * (self.request.retries + 1), exc=exc)

        return {"status": "error", "error": str(exc)}


@shared_task(bind=True, max_retries=3)
def send_individual_syllabus_alert(self, syllabus_id, risk_assessment):
    """
    Send alert for individual syllabus that is behind schedule.

    Args:
        syllabus_id: ID of the syllabus
        risk_assessment: Risk assessment data
    """
    try:
        syllabus = Syllabus.objects.select_related(
            "subject", "grade", "term", "academic_year"
        ).get(id=syllabus_id)

        # Get assigned teachers
        assignments = SubjectAssignment.objects.filter(
            subject=syllabus.subject,
            class_assigned__grade=syllabus.grade,
            academic_year=syllabus.academic_year,
            term=syllabus.term,
            is_active=True,
        ).select_related("teacher__user")

        priority = "high" if risk_assessment["risk_level"] == "high" else "medium"

        for assignment in assignments:
            # Create notification
            message = _(
                "Alert: {subject} - {grade} syllabus is {status}. "
                "Completion: {completion}%, Time Progress: {time_progress}%"
            ).format(
                subject=syllabus.subject.name,
                grade=syllabus.grade.name,
                status=risk_assessment["message"],
                completion=risk_assessment["completion_progress"],
                time_progress=risk_assessment["time_progress"],
            )

            Notification.objects.create(
                user=assignment.teacher.user,
                title=_("Syllabus Progress Alert"),
                content=message,
                notification_type="alert",
                reference_id=syllabus.id,
                reference_type="Syllabus",
                priority=priority,
            )

            # Send email if enabled
            if getattr(settings, "SEND_SYLLABUS_ALERTS_EMAIL", True):
                send_syllabus_alert_email.delay(
                    assignment.teacher.user.email,
                    assignment.teacher.user.get_full_name(),
                    syllabus.id,
                    risk_assessment,
                )

        logger.info(
            f"Sent alerts for syllabus {syllabus_id} to {assignments.count()} teachers"
        )

        return {
            "status": "success",
            "syllabus_id": syllabus_id,
            "teachers_notified": assignments.count(),
        }

    except Syllabus.DoesNotExist:
        logger.error(f"Syllabus {syllabus_id} not found")
        return {"status": "error", "error": "Syllabus not found"}

    except Exception as exc:
        logger.error(f"Error sending syllabus alert: {str(exc)}")

        if self.request.retries < self.max_retries:
            raise self.retry(countdown=60 * (self.request.retries + 1), exc=exc)

        return {"status": "error", "error": str(exc), "syllabus_id": syllabus_id}


@shared_task(bind=True, max_retries=3)
def send_syllabus_alert_email(self, email, teacher_name, syllabus_id, risk_assessment):
    """
    Send email alert for syllabus progress.

    Args:
        email: Teacher's email address
        teacher_name: Teacher's name
        syllabus_id: ID of the syllabus
        risk_assessment: Risk assessment data
    """
    try:
        syllabus = Syllabus.objects.select_related("subject", "grade", "term").get(
            id=syllabus_id
        )

        subject = _("Syllabus Progress Alert - {}").format(syllabus.subject.name)

        message = _(
            "Dear {teacher_name},\n\n"
            "This is an alert regarding the progress of your syllabus:\n\n"
            "Subject: {subject_name}\n"
            "Grade: {grade_name}\n"
            "Term: {term_name}\n"
            "Current Status: {status}\n"
            "Completion Progress: {completion}%\n"
            "Time Progress: {time_progress}%\n"
            "Days Remaining: {remaining_days}\n\n"
            "Recommendations:\n{recommendations}\n\n"
            "Please log into the system to review and update your syllabus progress.\n\n"
            "Best regards,\n"
            "Academic Management System"
        ).format(
            teacher_name=teacher_name,
            subject_name=syllabus.subject.name,
            grade_name=syllabus.grade.name,
            term_name=syllabus.term.name,
            status=risk_assessment["message"],
            completion=risk_assessment["completion_progress"],
            time_progress=risk_assessment["time_progress"],
            remaining_days=risk_assessment["remaining_days"],
            recommendations="\n".join(
                f"• {rec}" for rec in risk_assessment["recommendations"]
            ),
        )

        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False,
        )

        logger.info(f"Sent syllabus alert email to {email}")

        return {"status": "success", "email": email, "syllabus_id": syllabus_id}

    except Exception as exc:
        logger.error(f"Error sending syllabus alert email: {str(exc)}")

        if self.request.retries < self.max_retries:
            raise self.retry(countdown=60 * (self.request.retries + 1), exc=exc)

        return {"status": "error", "error": str(exc), "email": email}


@shared_task(bind=True, max_retries=3)
def generate_weekly_curriculum_report(self):
    """
    Generate weekly curriculum progress report for administrators.
    """
    try:
        logger.info("Starting weekly curriculum report generation")

        # Get current academic year and term
        current_year = AcademicYear.objects.filter(is_current=True).first()
        if not current_year:
            logger.warning("No current academic year found")
            return {"status": "warning", "message": "No current academic year"}

        current_term = Term.objects.filter(
            academic_year=current_year, is_current=True
        ).first()

        # Get overall analytics
        analytics = CurriculumService.get_curriculum_analytics(current_year.id)

        # Get syllabi with issues
        problem_syllabi = []
        syllabi = Syllabus.objects.filter(
            academic_year=current_year, is_active=True
        ).select_related("subject", "grade", "term")

        for syllabus in syllabi:
            risk_assessment = calculate_risk_assessment(syllabus)
            if risk_assessment["risk_level"] in ["high", "medium"]:
                problem_syllabi.append({"syllabus": syllabus, "risk": risk_assessment})

        # Send report to administrators
        send_weekly_report_email.delay(
            current_year.id,
            analytics,
            problem_syllabi,
            current_term.id if current_term else None,
        )

        logger.info(
            f"Generated weekly report with {len(problem_syllabi)} problem syllabi"
        )

        return {
            "status": "success",
            "academic_year_id": current_year.id,
            "total_syllabi": analytics.get("overview", {}).get("total_syllabi", 0),
            "problem_syllabi": len(problem_syllabi),
        }

    except Exception as exc:
        logger.error(f"Error generating weekly report: {str(exc)}")

        if self.request.retries < self.max_retries:
            raise self.retry(countdown=60 * (self.request.retries + 1), exc=exc)

        return {"status": "error", "error": str(exc)}


@shared_task(bind=True, max_retries=3)
def send_weekly_report_email(
    self, academic_year_id, analytics, problem_syllabi, term_id=None
):
    """
    Send weekly curriculum report email to administrators.
    """
    try:
        from django.contrib.auth import get_user_model

        User = get_user_model()

        # Get administrators
        admin_emails = list(
            User.objects.filter(
                is_staff=True, is_active=True, email__isnull=False
            ).values_list("email", flat=True)
        )

        if not admin_emails:
            logger.warning("No administrator emails found")
            return {"status": "warning", "message": "No administrators to notify"}

        academic_year = AcademicYear.objects.get(id=academic_year_id)
        overview = analytics.get("overview", {})

        subject = _("Weekly Curriculum Progress Report - {}").format(academic_year.name)

        message = _(
            "Weekly Curriculum Progress Report\n"
            "Academic Year: {academic_year}\n"
            "Report Date: {report_date}\n\n"
            "OVERVIEW:\n"
            "• Total Syllabi: {total_syllabi}\n"
            "• Average Completion: {avg_completion:.1f}%\n"
            "• Completed Syllabi: {completed_syllabi}\n"
            "• In Progress: {in_progress_syllabi}\n"
            "• Not Started: {not_started_syllabi}\n"
            "• Completion Rate: {completion_rate:.1f}%\n\n"
            "ISSUES REQUIRING ATTENTION:\n"
            "{problem_summary}\n\n"
            "Please log into the system for detailed analytics and reports.\n\n"
            "Best regards,\n"
            "Academic Management System"
        ).format(
            academic_year=academic_year.name,
            report_date=date.today().strftime("%Y-%m-%d"),
            total_syllabi=overview.get("total_syllabi", 0),
            avg_completion=overview.get("average_completion", 0),
            completed_syllabi=overview.get("completed_syllabi", 0),
            in_progress_syllabi=overview.get("in_progress_syllabi", 0),
            not_started_syllabi=overview.get("not_started_syllabi", 0),
            completion_rate=overview.get("completion_rate", 0),
            problem_summary=_format_problem_summary(problem_syllabi),
        )

        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=admin_emails,
            fail_silently=False,
        )

        logger.info(f"Sent weekly report to {len(admin_emails)} administrators")

        return {
            "status": "success",
            "recipients": len(admin_emails),
            "academic_year_id": academic_year_id,
        }

    except Exception as exc:
        logger.error(f"Error sending weekly report email: {str(exc)}")

        if self.request.retries < self.max_retries:
            raise self.retry(countdown=60 * (self.request.retries + 1), exc=exc)

        return {"status": "error", "error": str(exc)}


@shared_task(bind=True, max_retries=3)
def cleanup_old_analytics_cache(self):
    """
    Clean up old analytics cache entries to free up memory.
    """
    try:
        logger.info("Starting analytics cache cleanup")

        # This is a placeholder for cache cleanup logic
        # Implementation would depend on your cache backend
        # For Redis, you could use pattern matching to find old keys

        # For now, we'll just clear some specific old cache patterns
        from django.core.cache import cache

        # Get academic years older than 2 years
        cutoff_date = date.today() - timedelta(days=730)
        old_years = AcademicYear.objects.filter(end_date__lt=cutoff_date).values_list(
            "id", flat=True
        )

        keys_cleared = 0
        for year_id in old_years:
            cache_keys = [
                f"subjects:analytics:{year_id}:all",
                f"subjects:curriculum_structure:{year_id}",
            ]

            # Add department-specific keys
            departments = Department.objects.values_list("id", flat=True)
            for dept_id in departments:
                cache_keys.append(f"subjects:analytics:{year_id}:{dept_id}")

            cache.delete_many(cache_keys)
            keys_cleared += len(cache_keys)

        logger.info(f"Cleared {keys_cleared} old cache entries")

        return {
            "status": "success",
            "keys_cleared": keys_cleared,
            "old_years_processed": len(old_years),
        }

    except Exception as exc:
        logger.error(f"Error cleaning up cache: {str(exc)}")

        if self.request.retries < self.max_retries:
            raise self.retry(countdown=60 * (self.request.retries + 1), exc=exc)

        return {"status": "error", "error": str(exc)}


@shared_task(bind=True, max_retries=3)
def sync_topic_progress_with_content(self, syllabus_id):
    """
    Sync topic progress entries with syllabus content.

    Args:
        syllabus_id: ID of the syllabus to sync
    """
    try:
        syllabus = Syllabus.objects.get(id=syllabus_id, is_active=True)

        topics = syllabus.content.get("topics", []) if syllabus.content else []

        # Get existing topic progress entries
        existing_progress = {
            tp.topic_index: tp for tp in TopicProgress.objects.filter(syllabus=syllabus)
        }

        synced_count = 0

        # Update or create progress entries
        for index, topic in enumerate(topics):
            if index in existing_progress:
                # Update existing
                progress = existing_progress[index]
                progress.topic_name = topic.get("name", f"Topic {index + 1}")
                progress.is_completed = topic.get("completed", False)
                progress.save()
            else:
                # Create new
                TopicProgress.objects.create(
                    syllabus=syllabus,
                    topic_index=index,
                    topic_name=topic.get("name", f"Topic {index + 1}"),
                    is_completed=topic.get("completed", False),
                )

            synced_count += 1

        # Remove excess progress entries
        TopicProgress.objects.filter(
            syllabus=syllabus, topic_index__gte=len(topics)
        ).delete()

        # Update completion percentage
        syllabus.update_completion_percentage()

        # Clear related cache
        CacheManager.clear_related_caches(syllabus)

        logger.info(f"Synced {synced_count} topics for syllabus {syllabus_id}")

        return {
            "status": "success",
            "syllabus_id": syllabus_id,
            "topics_synced": synced_count,
        }

    except Syllabus.DoesNotExist:
        logger.error(f"Syllabus {syllabus_id} not found")
        return {"status": "error", "error": "Syllabus not found"}

    except Exception as exc:
        logger.error(f"Error syncing topic progress: {str(exc)}")

        if self.request.retries < self.max_retries:
            raise self.retry(countdown=60 * (self.request.retries + 1), exc=exc)

        return {"status": "error", "error": str(exc), "syllabus_id": syllabus_id}


def _format_problem_summary(problem_syllabi):
    """Format problem syllabi summary for email."""
    if not problem_syllabi:
        return _("No major issues found. All syllabi are progressing well.")

    summary_lines = []
    high_risk_count = 0
    medium_risk_count = 0

    for item in problem_syllabi:
        syllabus = item["syllabus"]
        risk = item["risk"]

        if risk["risk_level"] == "high":
            high_risk_count += 1
        else:
            medium_risk_count += 1

        summary_lines.append(
            f"• {syllabus.subject.name} - {syllabus.grade.name}: "
            f"{risk['message']} (Completion: {risk['completion_progress']}%)"
        )

    header = _(
        "Found {total} syllabi requiring attention "
        "({high} high risk, {medium} medium risk):\n"
    ).format(total=len(problem_syllabi), high=high_risk_count, medium=medium_risk_count)

    return header + "\n".join(summary_lines[:10])  # Limit to first 10 items


# Periodic task scheduling (to be added to CELERY_BEAT_SCHEDULE in settings)
"""
Add these to your CELERY_BEAT_SCHEDULE in settings:

'update-syllabus-completion': {
    'task': 'subjects.tasks.update_syllabus_completion_percentages',
    'schedule': crontab(hour=2, minute=0),  # Daily at 2 AM
},
'check-syllabus-deadlines': {
    'task': 'subjects.tasks.send_syllabus_deadline_alerts',
    'schedule': crontab(hour=8, minute=0),  # Daily at 8 AM
},
'weekly-curriculum-report': {
    'task': 'subjects.tasks.generate_weekly_curriculum_report',
    'schedule': crontab(hour=6, minute=0, day_of_week=1),  # Monday at 6 AM
},
'cleanup-analytics-cache': {
    'task': 'subjects.tasks.cleanup_old_analytics_cache',
    'schedule': crontab(hour=3, minute=0, day_of_week=0),  # Sunday at 3 AM
},
"""
