# src/teachers/tasks.py
from celery import shared_task
from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Avg, Count, Q
from datetime import datetime, timedelta, date
import logging
import json
import csv
import io
from typing import List, Dict, Any

from src.teachers.models import Teacher, TeacherEvaluation, TeacherClassAssignment
from src.teachers.services.analytics_service import TeacherAnalyticsService
from src.communications.models import Notification
from src.courses.models import AcademicYear, Department
from src.core.models import AuditLog

User = get_user_model()
logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def calculate_daily_teacher_analytics(self, academic_year_id=None, department_id=None):
    """Calculate daily teacher analytics and update cached values."""
    try:
        logger.info("Starting daily teacher analytics calculation")

        # Get academic year
        if academic_year_id:
            academic_year = AcademicYear.objects.get(id=academic_year_id)
        else:
            academic_year = AcademicYear.objects.filter(is_current=True).first()

        if not academic_year:
            logger.warning("No academic year found for analytics calculation")
            return {"status": "warning", "message": "No academic year found"}

        # Calculate various analytics
        performance_data = TeacherAnalyticsService.get_performance_overview(
            academic_year=academic_year, department_id=department_id
        )

        workload_data = TeacherAnalyticsService.get_workload_analysis(
            academic_year=academic_year
        )

        trends_data = TeacherAnalyticsService.get_evaluation_trends(
            months=12, department_id=department_id
        )

        dept_comparison = TeacherAnalyticsService.get_departmental_comparison()

        retention_data = TeacherAnalyticsService.get_retention_analysis()

        # Create audit log
        AuditLog.objects.create(
            user=None,  # System task
            action="CALCULATE",
            entity_type="TeacherAnalytics",
            entity_id=academic_year.id if academic_year else None,
            data_after={
                "calculation_date": timezone.now().isoformat(),
                "academic_year": academic_year.name if academic_year else None,
                "department_id": department_id,
                "total_teachers": performance_data.get("base_stats", {}).get(
                    "total_teachers", 0
                ),
            },
        )

        logger.info(
            f"Daily teacher analytics calculated successfully for {academic_year.name if academic_year else 'all years'}"
        )

        return {
            "status": "success",
            "message": "Analytics calculated successfully",
            "academic_year": academic_year.name if academic_year else None,
            "calculation_time": timezone.now().isoformat(),
            "metrics": performance_data.get("base_stats", {}),
        }

    except Exception as exc:
        logger.error(f"Error calculating daily teacher analytics: {str(exc)}")
        self.retry(countdown=60 * 5, exc=exc)  # Retry after 5 minutes


@shared_task(bind=True, max_retries=3)
def send_evaluation_reminders(self):
    """Send reminders for overdue teacher evaluations."""
    try:
        logger.info("Starting evaluation reminder process")

        # Find teachers who haven't been evaluated in the last 6 months
        six_months_ago = timezone.now().date() - timedelta(days=180)

        teachers_needing_evaluation = (
            Teacher.objects.filter(status="Active")
            .exclude(evaluations__evaluation_date__gte=six_months_ago)
            .select_related("user", "department")
        )

        # Find department heads and administrators to notify
        department_heads = Teacher.objects.filter(
            department__head__isnull=False, status="Active"
        ).select_related("user", "department")

        admins = User.objects.filter(
            Q(is_staff=True) | Q(groups__name__in=["Admin", "Principal"])
        ).distinct()

        notifications_sent = 0
        emails_sent = 0

        for teacher in teachers_needing_evaluation:
            # Create notification for department head
            if teacher.department and teacher.department.head:
                Notification.objects.create(
                    user=teacher.department.head.user,
                    title="Teacher Evaluation Reminder",
                    content=f"{teacher.get_full_name()} requires evaluation. Last evaluation was over 6 months ago.",
                    notification_type="Evaluation",
                    reference_id=teacher.id,
                    priority="Medium",
                )
                notifications_sent += 1

            # Send email to department head if configured
            if (
                teacher.department
                and teacher.department.head
                and hasattr(settings, "EMAIL_EVALUATION_REMINDERS")
                and settings.EMAIL_EVALUATION_REMINDERS
            ):

                try:
                    context = {
                        "teacher": teacher,
                        "department_head": teacher.department.head,
                        "last_evaluation": teacher.get_latest_evaluation(),
                        "site_name": getattr(
                            settings, "SITE_NAME", "School Management System"
                        ),
                    }

                    subject = f"Evaluation Reminder: {teacher.get_full_name()}"

                    html_content = render_to_string(
                        "teachers/emails/evaluation_reminder.html", context
                    )
                    text_content = render_to_string(
                        "teachers/emails/evaluation_reminder.txt", context
                    )

                    email = EmailMultiAlternatives(
                        subject=subject,
                        body=text_content,
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        to=[teacher.department.head.user.email],
                    )
                    email.attach_alternative(html_content, "text/html")
                    email.send()
                    emails_sent += 1

                except Exception as e:
                    logger.error(f"Failed to send evaluation reminder email: {str(e)}")

        # Notify administrators about overall evaluation status
        for admin in admins:
            if teachers_needing_evaluation.count() > 0:
                Notification.objects.create(
                    user=admin,
                    title="Teacher Evaluations Status",
                    content=f"{teachers_needing_evaluation.count()} teachers require evaluation.",
                    notification_type="System",
                    priority="Low",
                )

        logger.info(
            f"Evaluation reminders completed: {notifications_sent} notifications, {emails_sent} emails sent"
        )

        return {
            "status": "success",
            "teachers_needing_evaluation": teachers_needing_evaluation.count(),
            "notifications_sent": notifications_sent,
            "emails_sent": emails_sent,
        }

    except Exception as exc:
        logger.error(f"Error sending evaluation reminders: {str(exc)}")
        self.retry(countdown=60 * 10, exc=exc)  # Retry after 10 minutes


@shared_task(bind=True, max_retries=3)
def send_followup_notifications(self):
    """Send notifications for overdue evaluation followups."""
    try:
        logger.info("Starting followup notification process")

        # Find evaluations with overdue followups
        overdue_followups = TeacherEvaluation.objects.filter(
            followup_date__lt=timezone.now().date(),
            status__in=["submitted", "reviewed"],
            score__lt=70,
        ).select_related("teacher", "teacher__user", "evaluator")

        notifications_sent = 0

        for evaluation in overdue_followups:
            # Notify evaluator
            Notification.objects.create(
                user=evaluation.evaluator,
                title="Overdue Evaluation Followup",
                content=f"Followup for {evaluation.teacher.get_full_name()} evaluation is overdue.",
                notification_type="Evaluation",
                reference_id=evaluation.id,
                priority="High",
            )

            # Notify department head if different from evaluator
            if (
                evaluation.teacher.department
                and evaluation.teacher.department.head
                and evaluation.teacher.department.head.user != evaluation.evaluator
            ):

                Notification.objects.create(
                    user=evaluation.teacher.department.head.user,
                    title="Overdue Evaluation Followup",
                    content=f"Followup for {evaluation.teacher.get_full_name()} evaluation is overdue.",
                    notification_type="Evaluation",
                    reference_id=evaluation.id,
                    priority="High",
                )

            notifications_sent += 1

        logger.info(
            f"Followup notifications completed: {notifications_sent} notifications sent"
        )

        return {
            "status": "success",
            "overdue_followups": overdue_followups.count(),
            "notifications_sent": notifications_sent,
        }

    except Exception as exc:
        logger.error(f"Error sending followup notifications: {str(exc)}")
        self.retry(countdown=60 * 10, exc=exc)


@shared_task(bind=True, max_retries=3)
def generate_teacher_performance_report(
    self, department_id=None, academic_year_id=None, email_to=None
):
    """Generate comprehensive teacher performance report."""
    try:
        logger.info(
            f"Starting teacher performance report generation for department {department_id}"
        )

        # Get academic year
        if academic_year_id:
            academic_year = AcademicYear.objects.get(id=academic_year_id)
        else:
            academic_year = AcademicYear.objects.filter(is_current=True).first()

        # Get department if specified
        department = None
        if department_id:
            department = Department.objects.get(id=department_id)

        # Generate analytics data
        performance_data = TeacherAnalyticsService.get_performance_overview(
            academic_year=academic_year, department_id=department_id
        )

        workload_data = TeacherAnalyticsService.get_workload_analysis(
            academic_year=academic_year
        )

        criteria_analysis = TeacherAnalyticsService.get_evaluation_criteria_analysis(
            department_id=department_id,
            year=(
                academic_year.start_date.year if academic_year else timezone.now().year
            ),
        )

        # Create report data structure
        report_data = {
            "generation_date": timezone.now().isoformat(),
            "academic_year": academic_year.name if academic_year else None,
            "department": department.name if department else "All Departments",
            "performance_overview": performance_data,
            "workload_analysis": workload_data,
            "criteria_analysis": criteria_analysis,
            "summary": {
                "total_teachers": performance_data.get("base_stats", {}).get(
                    "total_teachers", 0
                ),
                "avg_score": performance_data.get("base_stats", {}).get(
                    "avg_evaluation_score", 0
                ),
                "high_performers": performance_data.get("base_stats", {}).get(
                    "high_performers", 0
                ),
                "needs_improvement": performance_data.get("base_stats", {}).get(
                    "needs_improvement", 0
                ),
            },
        }

        # Generate CSV report
        csv_content = generate_csv_report(report_data)

        # Send email if requested
        if email_to:
            send_performance_report_email(email_to, report_data, csv_content)

        # Create audit log
        AuditLog.objects.create(
            user=None,  # System task
            action="GENERATE",
            entity_type="PerformanceReport",
            entity_id=department_id,
            data_after={
                "generation_date": timezone.now().isoformat(),
                "department": department.name if department else "All",
                "academic_year": academic_year.name if academic_year else None,
                "total_teachers": report_data["summary"]["total_teachers"],
            },
        )

        logger.info("Teacher performance report generated successfully")

        return {
            "status": "success",
            "report_data": report_data,
            "csv_generated": bool(csv_content),
            "email_sent": bool(email_to),
        }

    except Exception as exc:
        logger.error(f"Error generating teacher performance report: {str(exc)}")
        self.retry(countdown=60 * 5, exc=exc)


@shared_task(bind=True, max_retries=3)
def process_bulk_teacher_assignments(
    self, assignments_data: List[Dict], created_by_id: int
):
    """Process bulk teacher class assignments."""
    try:
        logger.info(
            f"Starting bulk assignment processing for {len(assignments_data)} assignments"
        )

        created_by = User.objects.get(id=created_by_id)

        created_assignments = []
        errors = []

        for assignment_data in assignments_data:
            try:
                # Validate required fields
                required_fields = [
                    "teacher_id",
                    "class_instance_id",
                    "subject_id",
                    "academic_year_id",
                ]
                if not all(field in assignment_data for field in required_fields):
                    errors.append(
                        {"data": assignment_data, "error": "Missing required fields"}
                    )
                    continue

                # Check if assignment already exists
                existing = TeacherClassAssignment.objects.filter(
                    teacher_id=assignment_data["teacher_id"],
                    class_instance_id=assignment_data["class_instance_id"],
                    subject_id=assignment_data["subject_id"],
                    academic_year_id=assignment_data["academic_year_id"],
                ).exists()

                if existing:
                    errors.append(
                        {"data": assignment_data, "error": "Assignment already exists"}
                    )
                    continue

                # Create assignment
                assignment = TeacherClassAssignment.objects.create(
                    teacher_id=assignment_data["teacher_id"],
                    class_instance_id=assignment_data["class_instance_id"],
                    subject_id=assignment_data["subject_id"],
                    academic_year_id=assignment_data["academic_year_id"],
                    is_class_teacher=assignment_data.get("is_class_teacher", False),
                    notes=assignment_data.get("notes", ""),
                )

                created_assignments.append(assignment.id)

                # Create notification for teacher
                teacher = assignment.teacher
                Notification.objects.create(
                    user=teacher.user,
                    title="New Class Assignment",
                    content=f"You have been assigned to teach {assignment.subject.name} for {assignment.class_instance}.",
                    notification_type="Assignment",
                    reference_id=assignment.id,
                    priority="Medium",
                )

            except Exception as e:
                errors.append({"data": assignment_data, "error": str(e)})

        # Create audit log
        AuditLog.objects.create(
            user=created_by,
            action="BULK_CREATE",
            entity_type="TeacherClassAssignment",
            entity_id=None,
            data_after={
                "total_processed": len(assignments_data),
                "created_count": len(created_assignments),
                "error_count": len(errors),
                "created_assignments": created_assignments[:10],  # Limit for storage
            },
        )

        logger.info(
            f"Bulk assignment processing completed: {len(created_assignments)} created, {len(errors)} errors"
        )

        return {
            "status": "success",
            "created_count": len(created_assignments),
            "error_count": len(errors),
            "created_assignments": created_assignments,
            "errors": errors,
        }

    except Exception as exc:
        logger.error(f"Error processing bulk teacher assignments: {str(exc)}")
        self.retry(countdown=60 * 5, exc=exc)


@shared_task(bind=True, max_retries=3)
def update_teacher_performance_metrics(self, teacher_id=None):
    """Update cached performance metrics for teachers."""
    try:
        logger.info(
            f"Updating performance metrics for teacher {teacher_id if teacher_id else 'all'}"
        )

        if teacher_id:
            teachers = Teacher.objects.filter(id=teacher_id)
        else:
            teachers = Teacher.objects.filter(status="Active")

        updated_count = 0

        for teacher in teachers:
            # Calculate latest performance metrics
            growth_data = TeacherAnalyticsService.get_teacher_growth_analysis(
                teacher_id=teacher.id, months=12
            )

            if growth_data and "growth_metrics" in growth_data:
                metrics = growth_data["growth_metrics"]

                # Update teacher's cached metrics (if you have such fields)
                # This would require additional fields in the Teacher model
                # For now, we'll just log the calculation

                updated_count += 1

                # Create notification if performance is declining
                if metrics.get("improvement_trend") == "Declining":
                    if teacher.department and teacher.department.head:
                        Notification.objects.create(
                            user=teacher.department.head.user,
                            title="Performance Alert",
                            content=f"{teacher.get_full_name()} shows declining performance trend.",
                            notification_type="Performance",
                            reference_id=teacher.id,
                            priority="Medium",
                        )

        logger.info(f"Performance metrics updated for {updated_count} teachers")

        return {
            "status": "success",
            "updated_count": updated_count,
            "teacher_id": teacher_id,
        }

    except Exception as exc:
        logger.error(f"Error updating teacher performance metrics: {str(exc)}")
        self.retry(countdown=60 * 5, exc=exc)


@shared_task(bind=True, max_retries=3)
def send_birthday_notifications(self):
    """Send birthday notifications for teachers."""
    try:
        logger.info("Checking for teacher birthdays")

        today = timezone.now().date()

        # Find teachers with birthdays today
        birthday_teachers = Teacher.objects.filter(
            user__date_of_birth__month=today.month,
            user__date_of_birth__day=today.day,
            status="Active",
        ).select_related("user", "department")

        notifications_sent = 0

        for teacher in birthday_teachers:
            # Notify department colleagues
            if teacher.department:
                dept_teachers = Teacher.objects.filter(
                    department=teacher.department, status="Active"
                ).exclude(id=teacher.id)

                for colleague in dept_teachers:
                    Notification.objects.create(
                        user=colleague.user,
                        title="Birthday Reminder",
                        content=f"Today is {teacher.get_full_name()}'s birthday!",
                        notification_type="Birthday",
                        reference_id=teacher.id,
                        priority="Low",
                    )
                    notifications_sent += 1

            # Notify administrators
            admins = User.objects.filter(
                Q(is_staff=True) | Q(groups__name__in=["Admin", "Principal"])
            ).distinct()

            for admin in admins:
                Notification.objects.create(
                    user=admin,
                    title="Teacher Birthday",
                    content=f"Today is {teacher.get_full_name()}'s birthday!",
                    notification_type="Birthday",
                    reference_id=teacher.id,
                    priority="Low",
                )

        logger.info(
            f"Birthday notifications sent: {notifications_sent} notifications for {birthday_teachers.count()} teachers"
        )

        return {
            "status": "success",
            "birthday_teachers": birthday_teachers.count(),
            "notifications_sent": notifications_sent,
        }

    except Exception as exc:
        logger.error(f"Error sending birthday notifications: {str(exc)}")
        self.retry(countdown=60 * 10, exc=exc)


@shared_task(bind=True, max_retries=3)
def cleanup_old_evaluations(self, days_old=2555):  # ~7 years
    """Clean up old evaluation data based on retention policy."""
    try:
        logger.info(f"Starting cleanup of evaluations older than {days_old} days")

        cutoff_date = timezone.now().date() - timedelta(days=days_old)

        # Find old evaluations
        old_evaluations = TeacherEvaluation.objects.filter(
            evaluation_date__lt=cutoff_date, status="closed"
        )

        count = old_evaluations.count()

        # Archive before deleting (optional)
        if (
            hasattr(settings, "ARCHIVE_OLD_EVALUATIONS")
            and settings.ARCHIVE_OLD_EVALUATIONS
        ):
            # Create archive entries or export to external storage
            pass

        # Delete old evaluations
        old_evaluations.delete()

        # Create audit log
        AuditLog.objects.create(
            user=None,  # System task
            action="CLEANUP",
            entity_type="TeacherEvaluation",
            entity_id=None,
            data_after={
                "cleanup_date": timezone.now().isoformat(),
                "cutoff_date": cutoff_date.isoformat(),
                "deleted_count": count,
            },
        )

        logger.info(f"Cleanup completed: {count} old evaluations removed")

        return {
            "status": "success",
            "deleted_count": count,
            "cutoff_date": cutoff_date.isoformat(),
        }

    except Exception as exc:
        logger.error(f"Error during evaluation cleanup: {str(exc)}")
        self.retry(countdown=60 * 30, exc=exc)  # Retry after 30 minutes


# Helper functions


def generate_csv_report(report_data: Dict) -> str:
    """Generate CSV content from report data."""
    output = io.StringIO()
    writer = csv.writer(output)

    # Write header
    writer.writerow(["Teacher Performance Report"])
    writer.writerow(["Generated:", report_data["generation_date"]])
    writer.writerow(["Academic Year:", report_data["academic_year"]])
    writer.writerow(["Department:", report_data["department"]])
    writer.writerow([])

    # Write summary
    writer.writerow(["Summary"])
    summary = report_data["summary"]
    for key, value in summary.items():
        writer.writerow([key.replace("_", " ").title(), value])

    writer.writerow([])

    # Write performance distribution
    writer.writerow(["Performance Distribution"])
    writer.writerow(["Level", "Count", "Percentage"])

    for item in report_data["performance_overview"]["performance_distribution"]:
        writer.writerow([item["range"], item["count"], f"{item['percentage']}%"])

    return output.getvalue()


def send_performance_report_email(email_to: str, report_data: Dict, csv_content: str):
    """Send performance report via email."""
    try:
        context = {
            "report_data": report_data,
            "site_name": getattr(settings, "SITE_NAME", "School Management System"),
        }

        subject = f"Teacher Performance Report - {report_data['department']}"

        html_content = render_to_string(
            "teachers/emails/performance_report.html", context
        )
        text_content = render_to_string(
            "teachers/emails/performance_report.txt", context
        )

        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[email_to],
        )
        email.attach_alternative(html_content, "text/html")

        # Attach CSV report
        email.attach(
            f"teacher_performance_report_{timezone.now().strftime('%Y%m%d')}.csv",
            csv_content,
            "text/csv",
        )

        email.send()

    except Exception as e:
        logger.error(f"Failed to send performance report email: {str(e)}")
        raise


# Periodic task configurations (to be added to settings.py)
"""
CELERY_BEAT_SCHEDULE = {
    'calculate-daily-teacher-analytics': {
        'task': 'src.teachers.tasks.calculate_daily_teacher_analytics',
        'schedule': crontab(hour=2, minute=0),  # Daily at 2 AM
    },
    'send-evaluation-reminders': {
        'task': 'src.teachers.tasks.send_evaluation_reminders',
        'schedule': crontab(hour=8, minute=0, day_of_week=1),  # Monday at 8 AM
    },
    'send-followup-notifications': {
        'task': 'src.teachers.tasks.send_followup_notifications',
        'schedule': crontab(hour=9, minute=0),  # Daily at 9 AM
    },
    'update-teacher-performance-metrics': {
        'task': 'src.teachers.tasks.update_teacher_performance_metrics',
        'schedule': crontab(hour=3, minute=0, day_of_week=0),  # Sunday at 3 AM
    },
    'send-birthday-notifications': {
        'task': 'src.teachers.tasks.send_birthday_notifications',
        'schedule': crontab(hour=7, minute=0),  # Daily at 7 AM
    },
    'cleanup-old-evaluations': {
        'task': 'src.teachers.tasks.cleanup_old_evaluations',
        'schedule': crontab(hour=1, minute=0, day_of_month=1),  # First day of month at 1 AM
    },
}
"""
