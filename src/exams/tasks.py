"""
School Management System - Exam Celery Tasks
File: src/exams/tasks.py
"""

import logging
from typing import Dict, List

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.template.loader import render_to_string
from django.utils import timezone

from academics.models import AcademicYear, Term
from communications.models import Notification
from students.models import Student

from .models import (
    Exam,
    ExamSchedule,
    OnlineExam,
    ReportCard,
    StudentExamResult,
    StudentOnlineExamAttempt,
)
from .services.analytics_service import ExamAnalyticsService
from .services.exam_service import ExamService, ResultService

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def calculate_exam_rankings(self, exam_schedule_id: str):
    """Calculate rankings for an exam schedule"""
    try:
        exam_schedule = ExamSchedule.objects.get(id=exam_schedule_id)

        with transaction.atomic():
            # Calculate class rankings
            results = StudentExamResult.objects.filter(
                exam_schedule=exam_schedule, is_absent=False
            ).order_by("-percentage")

            for i, result in enumerate(results, 1):
                result.class_rank = i
                result.save(update_fields=["class_rank"])

            # Calculate grade rankings
            grade_results = StudentExamResult.objects.filter(
                exam_schedule__exam=exam_schedule.exam,
                student__current_class__grade=exam_schedule.class_obj.grade,
                is_absent=False,
            ).order_by("-percentage")

            for i, result in enumerate(grade_results, 1):
                result.grade_rank = i
                result.save(update_fields=["grade_rank"])

        logger.info(f"Rankings calculated for exam schedule {exam_schedule_id}")
        return f"Rankings calculated successfully for {len(results)} students"

    except ExamSchedule.DoesNotExist:
        logger.error(f"ExamSchedule {exam_schedule_id} not found")
        raise
    except Exception as exc:
        logger.error(f"Error calculating rankings for {exam_schedule_id}: {exc}")
        self.retry(countdown=60, exc=exc)


@shared_task(bind=True, max_retries=3)
def auto_grade_online_exam(self, attempt_id: str):
    """Automatically grade objective questions in online exam"""
    try:
        attempt = StudentOnlineExamAttempt.objects.get(id=attempt_id)

        if attempt.status != "SUBMITTED":
            logger.warning(f"Attempt {attempt_id} is not submitted")
            return "Attempt not submitted"

        online_exam = attempt.online_exam
        auto_graded_marks = 0

        # Get questions and their correct answers
        exam_questions = online_exam.onlineexamquestion_set.all().select_related(
            "question"
        )

        for exam_question in exam_questions:
            question = exam_question.question
            question_id = str(question.id)

            if question_id in attempt.responses:
                student_answer = attempt.responses[question_id]
                correct_answer = question.correct_answer

                # Auto-grade objective questions
                if question.question_type in ["MCQ", "TF", "FB"]:
                    if (
                        str(student_answer).strip().lower()
                        == str(correct_answer).strip().lower()
                    ):
                        auto_graded_marks += exam_question.marks

                # Update question usage count
                question.usage_count += 1
                question.save(update_fields=["usage_count"])

        # Update attempt with auto-graded marks
        attempt.auto_graded_marks = auto_graded_marks
        attempt.marks_obtained = (
            auto_graded_marks  # Will be updated when manual grading is done
        )
        attempt.is_graded = True if auto_graded_marks == attempt.total_marks else False
        attempt.save()

        logger.info(f"Auto-grading completed for attempt {attempt_id}")
        return f"Auto-graded {auto_graded_marks} marks out of {attempt.total_marks}"

    except StudentOnlineExamAttempt.DoesNotExist:
        logger.error(f"Online exam attempt {attempt_id} not found")
        raise
    except Exception as exc:
        logger.error(f"Error auto-grading attempt {attempt_id}: {exc}")
        self.retry(countdown=60, exc=exc)


@shared_task(bind=True, max_retries=3)
def generate_bulk_report_cards(self, term_id: str, class_ids: List[str] = None):
    """Generate report cards for a term in bulk"""
    try:
        term = Term.objects.get(id=term_id)

        with transaction.atomic():
            report_cards = ResultService.generate_report_cards(term_id, class_ids)

        logger.info(f"Generated {len(report_cards)} report cards for term {term.name}")

        # Send notifications to parents about report card generation
        send_report_card_notifications.delay([str(rc.id) for rc in report_cards])

        return f"Generated {len(report_cards)} report cards successfully"

    except Term.DoesNotExist:
        logger.error(f"Term {term_id} not found")
        raise
    except Exception as exc:
        logger.error(f"Error generating report cards for term {term_id}: {exc}")
        self.retry(countdown=60, exc=exc)


@shared_task
def send_exam_reminders():
    """Send exam reminders to students and parents"""
    try:
        # Get exams starting in the next 3 days
        upcoming_date = timezone.now().date() + timezone.timedelta(days=3)

        upcoming_schedules = ExamSchedule.objects.filter(
            date__lte=upcoming_date,
            date__gte=timezone.now().date(),
            is_active=True,
            exam__is_published=True,
        ).select_related("exam", "class_obj", "subject")

        notifications_sent = 0

        for schedule in upcoming_schedules:
            students = Student.objects.filter(
                current_class=schedule.class_obj, status="ACTIVE"
            ).select_related("user")

            for student in students:
                # Create notification for student
                Notification.objects.create(
                    user=student.user,
                    title=f"Exam Reminder: {schedule.subject.name}",
                    content=f"Your {schedule.subject.name} exam is scheduled for {schedule.date} at {schedule.start_time}. Please be prepared.",
                    notification_type="EXAM",
                    reference_id=str(schedule.id),
                    reference_type="ExamSchedule",
                )

                # Send notification to parents
                for parent_relation in student.parent_relations.filter(
                    is_primary_contact=True
                ):
                    Notification.objects.create(
                        user=parent_relation.parent.user,
                        title=f"Exam Reminder: {student.user.get_full_name()}",
                        content=f"{student.user.get_full_name()} has a {schedule.subject.name} exam on {schedule.date} at {schedule.start_time}.",
                        notification_type="EXAM",
                        reference_id=str(schedule.id),
                        reference_type="ExamSchedule",
                    )

                notifications_sent += 2  # Student + Parent

        logger.info(f"Sent {notifications_sent} exam reminder notifications")
        return f"Sent {notifications_sent} exam reminders"

    except Exception as exc:
        logger.error(f"Error sending exam reminders: {exc}")
        raise


@shared_task
def send_result_notifications(result_ids: List[str]):
    """Send result notifications to students and parents"""
    try:
        results = StudentExamResult.objects.filter(id__in=result_ids).select_related(
            "student__user", "exam_schedule__subject", "exam_schedule__exam"
        )

        notifications_sent = 0

        for result in results:
            student = result.student
            exam_name = result.exam_schedule.exam.name
            subject_name = result.exam_schedule.subject.name

            # Notification for student
            Notification.objects.create(
                user=student.user,
                title=f"Exam Result Published: {subject_name}",
                content=f"Your result for {subject_name} in {exam_name} has been published. Score: {result.marks_obtained}/{result.exam_schedule.total_marks} ({result.percentage:.1f}%)",
                notification_type="EXAM",
                reference_id=str(result.id),
                reference_type="StudentExamResult",
            )

            # Notification for parents
            for parent_relation in student.parent_relations.filter(
                is_primary_contact=True
            ):
                Notification.objects.create(
                    user=parent_relation.parent.user,
                    title=f"Exam Result: {student.user.get_full_name()}",
                    content=f"{student.user.get_full_name()}'s result for {subject_name} in {exam_name} is available. Score: {result.marks_obtained}/{result.exam_schedule.total_marks} ({result.percentage:.1f}%)",
                    notification_type="EXAM",
                    reference_id=str(result.id),
                    reference_type="StudentExamResult",
                )

            notifications_sent += 2

        logger.info(f"Sent {notifications_sent} result notifications")
        return f"Sent {notifications_sent} result notifications"

    except Exception as exc:
        logger.error(f"Error sending result notifications: {exc}")
        raise


@shared_task
def send_report_card_notifications(report_card_ids: List[str]):
    """Send report card notifications to students and parents"""
    try:
        report_cards = ReportCard.objects.filter(id__in=report_card_ids).select_related(
            "student__user", "term"
        )

        notifications_sent = 0

        for report_card in report_cards:
            student = report_card.student
            term_name = report_card.term.name

            # Notification for student
            Notification.objects.create(
                user=student.user,
                title=f"Report Card Available: {term_name}",
                content=f"Your report card for {term_name} is now available. Overall percentage: {report_card.percentage:.1f}%, Rank: {report_card.rank_suffix}",
                notification_type="EXAM",
                reference_id=str(report_card.id),
                reference_type="ReportCard",
            )

            # Notification for parents
            for parent_relation in student.parent_relations.filter(
                is_primary_contact=True
            ):
                Notification.objects.create(
                    user=parent_relation.parent.user,
                    title=f"Report Card: {student.user.get_full_name()}",
                    content=f"{student.user.get_full_name()}'s report card for {term_name} is available. Overall: {report_card.percentage:.1f}%, Rank: {report_card.rank_suffix} of {report_card.class_size}",
                    notification_type="EXAM",
                    reference_id=str(report_card.id),
                    reference_type="ReportCard",
                )

            notifications_sent += 2

        logger.info(f"Sent {notifications_sent} report card notifications")
        return f"Sent {notifications_sent} report card notifications"

    except Exception as exc:
        logger.error(f"Error sending report card notifications: {exc}")
        raise


@shared_task
def calculate_daily_analytics():
    """Calculate daily analytics for all active academic years"""
    try:
        active_years = AcademicYear.objects.filter(is_current=True)
        analytics_calculated = 0

        for year in active_years:
            # Get current term
            current_term = year.terms.filter(is_current=True).first()

            if current_term:
                # Calculate analytics for the current term
                analytics_data = (
                    ExamAnalyticsService.get_academic_performance_dashboard(
                        str(year.id), str(current_term.id)
                    )
                )

                # Store or process analytics data as needed
                # This could involve updating analytics tables or generating reports

                analytics_calculated += 1

        logger.info(f"Calculated analytics for {analytics_calculated} academic years")
        return f"Analytics calculated for {analytics_calculated} academic years"

    except Exception as exc:
        logger.error(f"Error calculating daily analytics: {exc}")
        raise


@shared_task
def cleanup_expired_online_exam_attempts():
    """Clean up expired online exam attempts"""
    try:
        # Find attempts that have exceeded time limit and mark as timed out
        current_time = timezone.now()

        expired_attempts = StudentOnlineExamAttempt.objects.filter(
            status="IN_PROGRESS"
        ).select_related("online_exam")

        expired_count = 0

        for attempt in expired_attempts:
            time_limit_seconds = attempt.online_exam.time_limit_minutes * 60
            if (current_time - attempt.start_time).total_seconds() > time_limit_seconds:
                attempt.status = "TIMED_OUT"
                attempt.submit_time = current_time
                attempt.save()
                expired_count += 1

        logger.info(f"Marked {expired_count} online exam attempts as timed out")
        return f"Processed {expired_count} expired attempts"

    except Exception as exc:
        logger.error(f"Error cleaning up expired attempts: {exc}")
        raise


@shared_task
def send_low_performance_alerts():
    """Send alerts for students with consistently low performance"""
    try:
        # Get current academic year and term
        current_year = AcademicYear.objects.filter(is_current=True).first()
        if not current_year:
            return "No current academic year found"

        current_term = current_year.terms.filter(is_current=True).first()
        if not current_term:
            return "No current term found"

        # Find students with low performance (less than 40% average)
        low_performers = (
            StudentExamResult.objects.filter(
                exam_schedule__exam__academic_year=current_year,
                term=current_term,
                is_absent=False,
            )
            .values("student")
            .annotate(
                avg_percentage=models.Avg("percentage"),
                fail_count=models.Count("id", filter=models.Q(is_pass=False)),
            )
            .filter(models.Q(avg_percentage__lt=40) | models.Q(fail_count__gte=3))
        )

        alerts_sent = 0

        for performer in low_performers:
            student = Student.objects.get(id=performer["student"])

            # Alert to class teacher
            if student.current_class.class_teacher:
                Notification.objects.create(
                    user=student.current_class.class_teacher.user,
                    title=f"Low Performance Alert: {student.user.get_full_name()}",
                    content=f"{student.user.get_full_name()} is showing low academic performance with {performer['avg_percentage']:.1f}% average. Intervention may be needed.",
                    notification_type="SYSTEM",
                    priority="HIGH",
                    reference_id=str(student.id),
                    reference_type="Student",
                )
                alerts_sent += 1

            # Alert to parents
            for parent_relation in student.parent_relations.filter(
                is_primary_contact=True
            ):
                Notification.objects.create(
                    user=parent_relation.parent.user,
                    title=f"Academic Performance Alert: {student.user.get_full_name()}",
                    content=f"We noticed that {student.user.get_full_name()} may need additional academic support. Please schedule a meeting with the class teacher.",
                    notification_type="SYSTEM",
                    priority="MEDIUM",
                    reference_id=str(student.id),
                    reference_type="Student",
                )
                alerts_sent += 1

        logger.info(f"Sent {alerts_sent} low performance alerts")
        return f"Sent {alerts_sent} low performance alerts"

    except Exception as exc:
        logger.error(f"Error sending low performance alerts: {exc}")
        raise


@shared_task
def generate_weekly_exam_summary():
    """Generate weekly exam summary reports"""
    try:
        # Get the past week's exam activities
        week_ago = timezone.now().date() - timezone.timedelta(days=7)

        # Exams conducted this week
        conducted_exams = ExamSchedule.objects.filter(
            date__gte=week_ago, date__lte=timezone.now().date(), is_completed=True
        ).select_related("exam", "subject", "class_obj")

        # Results entered this week
        new_results = StudentExamResult.objects.filter(entry_date__gte=week_ago).count()

        # Report cards generated this week
        new_report_cards = ReportCard.objects.filter(
            generation_date__gte=week_ago
        ).count()

        summary = {
            "week_ending": timezone.now().date(),
            "exams_conducted": conducted_exams.count(),
            "results_entered": new_results,
            "report_cards_generated": new_report_cards,
            "exam_details": [
                {
                    "exam_name": schedule.exam.name,
                    "subject": schedule.subject.name,
                    "class": str(schedule.class_obj),
                    "date": schedule.date,
                }
                for schedule in conducted_exams
            ],
        }

        # This could be expanded to send email reports to administrators
        logger.info(f"Weekly exam summary generated: {summary}")
        return f"Weekly summary: {conducted_exams.count()} exams, {new_results} results, {new_report_cards} report cards"

    except Exception as exc:
        logger.error(f"Error generating weekly exam summary: {exc}")
        raise


@shared_task
def backup_exam_data():
    """Backup critical exam data"""
    try:
        import os
        from datetime import datetime

        from django.core.management import call_command

        # Generate backup filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = f"exam_backup_{timestamp}.json"
        backup_path = os.path.join(settings.BACKUP_ROOT, backup_file)

        # Create backup directory if it doesn't exist
        os.makedirs(os.path.dirname(backup_path), exist_ok=True)

        # Backup exam-related models
        models_to_backup = [
            "exams.exam",
            "exams.examschedule",
            "exams.studentexamresult",
            "exams.reportcard",
            "exams.examquestion",
            "exams.onlineexam",
        ]

        with open(backup_path, "w") as f:
            call_command("dumpdata", *models_to_backup, stdout=f, indent=2)

        logger.info(f"Exam data backed up to {backup_path}")
        return f"Backup created: {backup_file}"

    except Exception as exc:
        logger.error(f"Error backing up exam data: {exc}")
        raise


# Periodic task configurations for celery beat
"""
Add these to your CELERY_BEAT_SCHEDULE in settings:

CELERY_BEAT_SCHEDULE = {
    'send-exam-reminders': {
        'task': 'exams.tasks.send_exam_reminders',
        'schedule': crontab(hour=8, minute=0),  # Daily at 8 AM
    },
    'cleanup-expired-attempts': {
        'task': 'exams.tasks.cleanup_expired_online_exam_attempts',
        'schedule': crontab(minute='*/30'),  # Every 30 minutes
    },
    'calculate-daily-analytics': {
        'task': 'exams.tasks.calculate_daily_analytics',
        'schedule': crontab(hour=2, minute=0),  # Daily at 2 AM
    },
    'send-low-performance-alerts': {
        'task': 'exams.tasks.send_low_performance_alerts',
        'schedule': crontab(hour=9, minute=0, day_of_week=1),  # Weekly on Monday
    },
    'generate-weekly-summary': {
        'task': 'exams.tasks.generate_weekly_exam_summary',
        'schedule': crontab(hour=18, minute=0, day_of_week=5),  # Friday evening
    },
    'backup-exam-data': {
        'task': 'exams.tasks.backup_exam_data',
        'schedule': crontab(hour=1, minute=0),  # Daily at 1 AM
    },
}
"""
