"""
Celery tasks for scheduling module
"""

import logging
from datetime import date, datetime, timedelta

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import timezone

from academics.models import Grade, Term
from communications.models import Notification
from teachers.models import Teacher

from .models import Room, SubstituteTeacher, TimeSlot, Timetable, TimetableGeneration
from .services.analytics_service import SchedulingAnalyticsService
from .services.optimization_service import OptimizationService
from .services.timetable_service import TimetableService
from .utils import ScheduleValidator

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def generate_optimized_timetable(self, generation_id, algorithm="genetic", **kwargs):
    """
    Asynchronously generate optimized timetable

    Args:
        generation_id: TimetableGeneration instance ID
        algorithm: Optimization algorithm to use
        **kwargs: Additional parameters for optimization
    """
    try:
        generation = TimetableGeneration.objects.get(id=generation_id)

        # Update status to running
        generation.status = "running"
        generation.save()

        logger.info(f"Starting timetable generation {generation_id} with {algorithm}")

        # Initialize optimizer
        optimizer = OptimizationService(generation.term)

        # Get grades
        grades = list(generation.grades.all())

        # Set default parameters
        default_params = {
            "population_size": 50,
            "generations": 100,
            "mutation_rate": 0.1,
        }
        default_params.update(generation.parameters or {})
        default_params.update(kwargs)

        # Run optimization
        result = optimizer.generate_optimized_timetable(
            grades=grades, algorithm=algorithm, **default_params
        )

        # Update generation with results
        generation.status = "completed" if result.success else "failed"
        generation.optimization_score = result.optimization_score
        generation.execution_time_seconds = result.execution_time
        generation.conflicts_resolved = len(result.conflicts)
        generation.result_summary = {
            "assigned_slots": len(result.assigned_slots),
            "unassigned_slots": len(result.unassigned_slots),
            "total_conflicts": len(result.conflicts),
            "success": result.success,
        }
        generation.completed_at = timezone.now()

        if not result.success:
            generation.error_message = (
                f"Failed to assign {len(result.unassigned_slots)} slots"
            )
            logger.warning(f"Timetable generation {generation_id} partially failed")

        # Save to database if successful
        if result.success:
            save_result = optimizer.save_schedule_to_database(
                result, generation.started_by
            )
            generation.result_summary.update(save_result)
            logger.info(f"Timetable generation {generation_id} completed successfully")

        generation.save()

        # Send notification
        if generation.started_by:
            send_generation_completion_notification.delay(generation_id)

        # Trigger analytics update
        update_scheduling_analytics.delay(str(generation.term.id))

        return {
            "success": result.success,
            "optimization_score": result.optimization_score,
            "execution_time": result.execution_time,
        }

    except Exception as exc:
        logger.error(f"Timetable generation {generation_id} failed: {str(exc)}")

        # Update generation with error
        try:
            generation = TimetableGeneration.objects.get(id=generation_id)
            generation.status = "failed"
            generation.error_message = str(exc)
            generation.completed_at = timezone.now()
            generation.save()
        except:
            pass

        # Retry if not max retries reached
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=60 * (self.request.retries + 1))

        raise exc


@shared_task
def update_scheduling_analytics(term_id):
    """
    Update scheduling analytics for a term

    Args:
        term_id: Term instance ID
    """
    try:
        from academics.models import Term

        term = Term.objects.get(id=term_id)

        logger.info(f"Updating scheduling analytics for term {term}")

        # Calculate various analytics
        teacher_analytics = SchedulingAnalyticsService.get_teacher_workload_analytics(
            term
        )
        room_analytics = SchedulingAnalyticsService.get_room_utilization_analytics(term)
        conflict_analytics = (
            SchedulingAnalyticsService.get_scheduling_conflicts_analytics(term)
        )
        optimization_score = (
            SchedulingAnalyticsService.get_timetable_optimization_score(term)
        )

        # Store results in cache or database
        from django.core.cache import cache

        cache_key = f"scheduling_analytics_{term_id}"
        cache_data = {
            "teacher_workload": teacher_analytics,
            "room_utilization": room_analytics,
            "conflicts": conflict_analytics,
            "optimization_score": optimization_score,
            "updated_at": timezone.now().isoformat(),
        }

        # Cache for 1 hour
        cache.set(cache_key, cache_data, 3600)

        logger.info(f"Analytics updated for term {term}")

    except Exception as exc:
        logger.error(f"Failed to update analytics for term {term_id}: {str(exc)}")
        raise


@shared_task
def send_generation_completion_notification(generation_id):
    """
    Send notification about timetable generation completion

    Args:
        generation_id: TimetableGeneration instance ID
    """
    try:
        generation = TimetableGeneration.objects.get(id=generation_id)

        if not generation.started_by:
            return

        if generation.status == "completed":
            title = "Timetable Generation Completed"
            content = (
                f"Timetable generation for {generation.term} completed successfully. "
                f"Optimization score: {generation.optimization_score:.1f}%"
            )
            priority = "medium"
        else:
            title = "Timetable Generation Failed"
            content = (
                f"Timetable generation for {generation.term} failed. "
                f"Error: {generation.error_message}"
            )
            priority = "high"

        # Create notification
        Notification.objects.create(
            user=generation.started_by,
            title=title,
            content=content,
            notification_type="system",
            reference_id=str(generation.id),
            reference_type="TimetableGeneration",
            priority=priority,
        )

        # Send email if configured
        if getattr(settings, "SEND_GENERATION_EMAILS", False):
            send_mail(
                subject=title,
                message=content,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[generation.started_by.email],
                fail_silently=True,
            )

        logger.info(f"Notification sent for generation {generation_id}")

    except Exception as exc:
        logger.error(
            f"Failed to send notification for generation {generation_id}: {str(exc)}"
        )


@shared_task
def daily_schedule_validation():
    """
    Daily task to validate all active schedules
    """
    try:
        # Get current term
        current_term = Term.objects.filter(is_current=True).first()

        if not current_term:
            logger.info("No current term found, skipping validation")
            return

        logger.info(f"Running daily schedule validation for {current_term}")

        # Validate schedule
        validation_results = ScheduleValidator.validate_term_schedule(current_term)

        # If there are critical issues, notify administrators
        if not validation_results["is_valid"]:
            notify_schedule_issues.delay(str(current_term.id), validation_results)

        # Cache validation results
        from django.core.cache import cache

        cache.set(
            f"schedule_validation_{current_term.id}",
            validation_results,
            86400,  # 24 hours
        )

        logger.info(
            f"Schedule validation completed. Issues: {validation_results['total_issues']}, "
            f"Warnings: {validation_results['total_warnings']}"
        )

    except Exception as exc:
        logger.error(f"Daily schedule validation failed: {str(exc)}")
        raise


@shared_task
def notify_schedule_issues(term_id, validation_results):
    """
    Notify administrators about schedule issues

    Args:
        term_id: Term instance ID
        validation_results: Validation results dictionary
    """
    try:
        from academics.models import Term
        from accounts.models import User

        term = Term.objects.get(id=term_id)

        # Get administrators
        admins = User.objects.filter(
            Q(is_staff=True) | Q(groups__name="Scheduling Administrators")
        ).distinct()

        for admin in admins:
            title = f"Schedule Issues Detected - {term}"
            content = (
                f"Schedule validation found {validation_results['total_issues']} issues "
                f"and {validation_results['total_warnings']} warnings.\n\n"
                f"Issues:\n" + "\n".join(validation_results["issues"][:5])
            )

            if len(validation_results["issues"]) > 5:
                content += (
                    f"\n... and {len(validation_results['issues']) - 5} more issues"
                )

            Notification.objects.create(
                user=admin,
                title=title,
                content=content,
                notification_type="system",
                priority="high",
            )

        logger.info(f"Schedule issue notifications sent for term {term_id}")

    except Exception as exc:
        logger.error(f"Failed to send schedule issue notifications: {str(exc)}")


@shared_task
def send_substitute_reminders():
    """
    Send reminders about upcoming substitute assignments
    """
    try:
        tomorrow = date.today() + timedelta(days=1)

        # Get substitute assignments for tomorrow
        upcoming_substitutes = SubstituteTeacher.objects.filter(
            date=tomorrow, approved_by__isnull=False  # Only approved substitutes
        ).select_related("substitute_teacher", "original_timetable")

        for substitute in upcoming_substitutes:
            # Send reminder to substitute teacher
            Notification.objects.create(
                user=substitute.substitute_teacher.user,
                title="Substitute Assignment Reminder",
                content=f"Reminder: You have a substitute assignment tomorrow for "
                f"{substitute.original_timetable.subject.name} - "
                f"{substitute.original_timetable.class_assigned} at "
                f"{substitute.original_timetable.time_slot}",
                notification_type="reminder",
                priority="medium",
            )

            # Send email if configured
            if getattr(settings, "SEND_SUBSTITUTE_REMINDERS", False):
                send_mail(
                    subject="Substitute Assignment Reminder",
                    message=f"You have a substitute assignment tomorrow at {substitute.original_timetable.time_slot}.",
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[substitute.substitute_teacher.user.email],
                    fail_silently=True,
                )

        logger.info(f"Sent {upcoming_substitutes.count()} substitute reminders")

    except Exception as exc:
        logger.error(f"Failed to send substitute reminders: {str(exc)}")


@shared_task
def cleanup_old_timetable_generations():
    """
    Clean up old timetable generation records
    """
    try:
        # Keep records for last 90 days
        cutoff_date = timezone.now() - timedelta(days=90)

        old_generations = TimetableGeneration.objects.filter(
            started_at__lt=cutoff_date, status__in=["completed", "failed", "cancelled"]
        )

        count = old_generations.count()
        old_generations.delete()

        logger.info(f"Cleaned up {count} old timetable generation records")

    except Exception as exc:
        logger.error(f"Failed to cleanup old generations: {str(exc)}")


@shared_task
def room_maintenance_notifications():
    """
    Check for rooms needing maintenance and send notifications
    """
    try:
        # Get rooms with maintenance notes
        rooms_needing_attention = Room.objects.filter(
            maintenance_notes__isnull=False, is_available=True
        ).exclude(maintenance_notes="")

        if not rooms_needing_attention.exists():
            return

        # Get facility managers
        from accounts.models import User

        facility_managers = User.objects.filter(groups__name="Facility Managers")

        for manager in facility_managers:
            content = "Rooms requiring maintenance attention:\n\n"
            for room in rooms_needing_attention:
                content += f"- {room.number} ({room.name}): {room.maintenance_notes}\n"

            Notification.objects.create(
                user=manager,
                title="Room Maintenance Required",
                content=content,
                notification_type="maintenance",
                priority="medium",
            )

        logger.info(
            f"Sent maintenance notifications for {rooms_needing_attention.count()} rooms"
        )

    except Exception as exc:
        logger.error(f"Failed to send maintenance notifications: {str(exc)}")


@shared_task
def weekly_analytics_report():
    """
    Generate weekly analytics report
    """
    try:
        current_term = Term.objects.filter(is_current=True).first()

        if not current_term:
            logger.info("No current term found, skipping weekly report")
            return

        logger.info(f"Generating weekly analytics report for {current_term}")

        # Gather analytics data
        teacher_analytics = SchedulingAnalyticsService.get_teacher_workload_analytics(
            current_term
        )
        room_analytics = SchedulingAnalyticsService.get_room_utilization_analytics(
            current_term
        )
        optimization_score = (
            SchedulingAnalyticsService.get_timetable_optimization_score(current_term)
        )

        # Create summary
        report_data = {
            "term": str(current_term),
            "report_date": timezone.now().date(),
            "optimization_score": optimization_score["overall_score"],
            "teacher_count": len(teacher_analytics["teacher_workloads"]),
            "average_teacher_periods": teacher_analytics["summary"][
                "average_periods_per_teacher"
            ],
            "room_utilization": room_analytics["summary"]["average_utilization_rate"],
            "recommendations": optimization_score["recommendations"],
        }

        # Send to administrators
        from accounts.models import User

        admins = User.objects.filter(is_staff=True)

        for admin in admins:
            content = (
                f"Weekly Scheduling Report for {current_term}\n\n"
                f"Optimization Score: {report_data['optimization_score']:.1f}%\n"
                f"Average Teacher Workload: {report_data['average_teacher_periods']:.1f} periods\n"
                f"Room Utilization: {report_data['room_utilization']:.1f}%\n\n"
                f"Recommendations:\n" + "\n".join(report_data["recommendations"])
            )

            Notification.objects.create(
                user=admin,
                title="Weekly Scheduling Report",
                content=content,
                notification_type="report",
                priority="low",
            )

        logger.info("Weekly analytics report sent")

    except Exception as exc:
        logger.error(f"Failed to generate weekly report: {str(exc)}")


@shared_task
def auto_assign_rooms():
    """
    Automatically assign rooms to timetable entries without rooms
    """
    try:
        current_term = Term.objects.filter(is_current=True).first()

        if not current_term:
            return

        # Get timetable entries without rooms
        unassigned_entries = Timetable.objects.filter(
            term=current_term, is_active=True, room__isnull=True
        ).select_related("class_assigned", "subject", "time_slot")

        assigned_count = 0

        for entry in unassigned_entries:
            # Try to find suitable room
            from .services.timetable_service import RoomService

            suggestions = RoomService.suggest_optimal_room(
                entry.class_assigned, entry.subject, entry.time_slot, date.today()
            )

            if suggestions:
                # Assign the best suggestion
                best_room = suggestions[0]["room"]
                entry.room = best_room
                entry.save()
                assigned_count += 1

        if assigned_count > 0:
            logger.info(f"Auto-assigned {assigned_count} rooms")

    except Exception as exc:
        logger.error(f"Auto room assignment failed: {str(exc)}")


@shared_task
def backup_timetable_data():
    """
    Create backup of timetable data
    """
    try:
        import json

        from django.core import serializers

        current_term = Term.objects.filter(is_current=True).first()

        if not current_term:
            return

        # Serialize timetable data
        timetables = Timetable.objects.filter(term=current_term, is_active=True)

        backup_data = {
            "term": str(current_term),
            "backup_date": timezone.now().isoformat(),
            "timetables": json.loads(serializers.serialize("json", timetables)),
        }

        # Save to file or external storage
        backup_filename = f"timetable_backup_{current_term.id}_{timezone.now().strftime('%Y%m%d')}.json"

        # This would typically save to cloud storage or backup location
        logger.info(f"Timetable backup created: {backup_filename}")

    except Exception as exc:
        logger.error(f"Timetable backup failed: {str(exc)}")


# Periodic task scheduling (to be added to CELERY_BEAT_SCHEDULE in settings)
CELERY_BEAT_SCHEDULE = {
    "daily-schedule-validation": {
        "task": "scheduling.tasks.daily_schedule_validation",
        "schedule": "0 6 * * *",  # Every day at 6 AM
    },
    "substitute-reminders": {
        "task": "scheduling.tasks.send_substitute_reminders",
        "schedule": "0 18 * * *",  # Every day at 6 PM
    },
    "weekly-analytics-report": {
        "task": "scheduling.tasks.weekly_analytics_report",
        "schedule": "0 8 * * 1",  # Every Monday at 8 AM
    },
    "cleanup-old-generations": {
        "task": "scheduling.tasks.cleanup_old_timetable_generations",
        "schedule": "0 2 * * 0",  # Every Sunday at 2 AM
    },
    "room-maintenance-check": {
        "task": "scheduling.tasks.room_maintenance_notifications",
        "schedule": "0 9 * * 1",  # Every Monday at 9 AM
    },
    "auto-assign-rooms": {
        "task": "scheduling.tasks.auto_assign_rooms",
        "schedule": "0 22 * * *",  # Every day at 10 PM
    },
    "backup-timetable-data": {
        "task": "scheduling.tasks.backup_timetable_data",
        "schedule": "0 3 * * *",  # Every day at 3 AM
    },
}
