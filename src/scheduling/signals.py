from django.db.models.signals import post_save, post_delete, pre_save, pre_delete
from django.dispatch import receiver
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.utils import timezone
from datetime import datetime, timedelta

from .models import Timetable, SubstituteTeacher, TimetableGeneration, TimeSlot, Room
from communications.models import Notification
from analytics.models import SchedulingAnalytics
from teachers.models import Teacher
from academics.models import Term


@receiver(post_save, sender=Timetable)
def timetable_created_handler(sender, instance, created, **kwargs):
    """Handle timetable creation and updates"""

    if created:
        # Send notification to relevant users
        _notify_timetable_assignment(instance)

        # Log activity
        _log_timetable_activity(instance, "created")

        # Update analytics
        _update_scheduling_analytics(instance.term)

    else:
        # Handle updates
        _log_timetable_activity(instance, "updated")
        _update_scheduling_analytics(instance.term)


@receiver(post_delete, sender=Timetable)
def timetable_deleted_handler(sender, instance, **kwargs):
    """Handle timetable deletion"""

    # Log activity
    _log_timetable_activity(instance, "deleted")

    # Update analytics
    _update_scheduling_analytics(instance.term)

    # Notify about deletion
    _notify_timetable_deletion(instance)


@receiver(post_save, sender=SubstituteTeacher)
def substitute_teacher_handler(sender, instance, created, **kwargs):
    """Handle substitute teacher assignments"""

    if created:
        # Notify original teacher
        _notify_substitute_assignment(instance)

        # Notify substitute teacher
        _notify_substitute_teacher(instance)

        # Notify class students/parents (if configured)
        if getattr(settings, "NOTIFY_PARENTS_OF_SUBSTITUTES", False):
            _notify_students_parents_substitute(instance)

    # Check for approval
    if instance.approved_by and not created:
        _notify_substitute_approval(instance)


@receiver(post_save, sender=TimetableGeneration)
def timetable_generation_handler(sender, instance, created, **kwargs):
    """Handle timetable generation status changes"""

    if not created and instance.status in ["completed", "failed"]:
        # Notify the user who started the generation
        _notify_generation_completion(instance)

        # If successful, notify relevant stakeholders
        if instance.status == "completed":
            _notify_timetable_regeneration(instance)


@receiver(pre_save, sender=Timetable)
def timetable_conflict_check(sender, instance, **kwargs):
    """Check for conflicts before saving timetable"""

    # Skip conflict checking during bulk operations or if explicitly disabled
    if getattr(instance, "_skip_conflict_check", False):
        return

    # This would run the conflict checking logic
    # For now, we'll just log that checking occurred
    from .services.timetable_service import TimetableService

    try:
        conflicts = TimetableService.check_conflicts(
            teacher=instance.teacher,
            room=instance.room,
            class_obj=instance.class_assigned,
            time_slot=instance.time_slot,
            date_range=(instance.effective_from_date, instance.effective_to_date),
            exclude_timetable=instance if instance.pk else None,
        )

        if conflicts:
            # Log conflicts (don't raise exception as validation should handle this)
            import logging

            logger = logging.getLogger("scheduling.conflicts")
            logger.warning(f"Timetable conflicts detected for {instance}: {conflicts}")

    except Exception as e:
        # Don't break the save process
        import logging

        logger = logging.getLogger("scheduling.signals")
        logger.error(f"Error checking conflicts for {instance}: {str(e)}")


@receiver(post_save, sender=TimeSlot)
def time_slot_changed_handler(sender, instance, created, **kwargs):
    """Handle time slot changes"""

    if not created:
        # If time slot was modified, check affected timetables
        affected_timetables = Timetable.objects.filter(
            time_slot=instance, is_active=True
        )

        if affected_timetables.exists():
            _notify_time_slot_change(instance, affected_timetables)


@receiver(post_save, sender=Room)
def room_status_changed_handler(sender, instance, created, **kwargs):
    """Handle room availability changes"""

    if not created and not instance.is_available:
        # Room became unavailable, check current bookings
        current_bookings = Timetable.objects.filter(
            room=instance,
            is_active=True,
            effective_from_date__lte=timezone.now().date(),
            effective_to_date__gte=timezone.now().date(),
        )

        if current_bookings.exists():
            _notify_room_unavailable(instance, current_bookings)


# Helper functions for notifications and activities


def _notify_timetable_assignment(timetable):
    """Notify relevant users about new timetable assignment"""

    # Notify teacher
    try:
        Notification.objects.create(
            user=timetable.teacher.user,
            title="New Class Assignment",
            content=f"You have been assigned to teach {timetable.subject.name} "
            f"for {timetable.class_assigned} at {timetable.time_slot}",
            notification_type="timetable",
            reference_id=str(timetable.id),
            reference_type="Timetable",
        )
    except Exception:
        pass  # Handle if communications module not available

    # Notify class teacher if different
    if (
        hasattr(timetable.class_assigned, "class_teacher")
        and timetable.class_assigned.class_teacher
        and timetable.class_assigned.class_teacher != timetable.teacher
    ):

        try:
            Notification.objects.create(
                user=timetable.class_assigned.class_teacher.user,
                title="Class Timetable Updated",
                content=f"New subject assignment: {timetable.subject.name} "
                f"with {timetable.teacher.user.get_full_name()}",
                notification_type="timetable",
                reference_id=str(timetable.id),
                reference_type="Timetable",
            )
        except Exception:
            pass


def _notify_timetable_deletion(timetable):
    """Notify about timetable deletion"""

    try:
        Notification.objects.create(
            user=timetable.teacher.user,
            title="Class Assignment Removed",
            content=f"Your assignment to teach {timetable.subject.name} "
            f"for {timetable.class_assigned} has been removed",
            notification_type="timetable",
            priority="high",
        )
    except Exception:
        pass


def _notify_substitute_assignment(substitute):
    """Notify original teacher about substitute assignment"""

    original_teacher = substitute.original_timetable.teacher

    try:
        Notification.objects.create(
            user=original_teacher.user,
            title="Substitute Teacher Assigned",
            content=f"A substitute teacher ({substitute.substitute_teacher.user.get_full_name()}) "
            f"has been assigned for your {substitute.original_timetable.subject.name} "
            f"class on {substitute.date}. Reason: {substitute.reason}",
            notification_type="substitute",
            reference_id=str(substitute.id),
            reference_type="SubstituteTeacher",
        )

        # Send email if configured
        if getattr(settings, "SEND_SUBSTITUTE_EMAILS", False):
            send_mail(
                subject="Substitute Teacher Assigned",
                message=f"A substitute has been arranged for your class on {substitute.date}.",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[original_teacher.user.email],
                fail_silently=True,
            )

    except Exception:
        pass


def _notify_substitute_teacher(substitute):
    """Notify substitute teacher about assignment"""

    try:
        Notification.objects.create(
            user=substitute.substitute_teacher.user,
            title="Substitute Assignment",
            content=f"You have been assigned as substitute teacher for "
            f"{substitute.original_timetable.subject.name} - "
            f"{substitute.original_timetable.class_assigned} on {substitute.date}. "
            f"Time: {substitute.original_timetable.time_slot}",
            notification_type="substitute",
            reference_id=str(substitute.id),
            reference_type="SubstituteTeacher",
            priority="high",
        )
    except Exception:
        pass


def _notify_students_parents_substitute(substitute):
    """Notify students and parents about substitute teacher"""

    # This would integrate with the students and communications modules
    # to notify parents about substitute teachers
    pass


def _notify_substitute_approval(substitute):
    """Notify about substitute approval"""

    try:
        # Notify substitute teacher
        Notification.objects.create(
            user=substitute.substitute_teacher.user,
            title="Substitute Assignment Approved",
            content=f"Your substitute assignment for {substitute.date} has been approved.",
            notification_type="substitute",
        )

        # Notify original teacher
        Notification.objects.create(
            user=substitute.original_timetable.teacher.user,
            title="Substitute Assignment Approved",
            content=f"The substitute assignment for {substitute.date} has been approved.",
            notification_type="substitute",
        )
    except Exception:
        pass


def _notify_generation_completion(generation):
    """Notify user about timetable generation completion"""

    if not generation.started_by:
        return

    try:
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

        Notification.objects.create(
            user=generation.started_by,
            title=title,
            content=content,
            notification_type="system",
            reference_id=str(generation.id),
            reference_type="TimetableGeneration",
            priority=priority,
        )
    except Exception:
        pass


def _notify_timetable_regeneration(generation):
    """Notify stakeholders about timetable regeneration"""

    # This would notify administrators, teachers, etc. about new timetables
    # Implementation would depend on notification preferences
    pass


def _notify_time_slot_change(time_slot, affected_timetables):
    """Notify about time slot changes affecting existing timetables"""

    affected_teachers = set()
    for timetable in affected_timetables:
        affected_teachers.add(timetable.teacher.user)

    for teacher in affected_teachers:
        try:
            Notification.objects.create(
                user=teacher,
                title="Schedule Time Change",
                content=f"The time for {time_slot.name} has been modified. "
                f"Please check your updated schedule.",
                notification_type="schedule_change",
                priority="high",
            )
        except Exception:
            pass


def _notify_room_unavailable(room, affected_bookings):
    """Notify about room becoming unavailable"""

    affected_teachers = set()
    for booking in affected_bookings:
        affected_teachers.add(booking.teacher.user)

    for teacher in affected_teachers:
        try:
            Notification.objects.create(
                user=teacher,
                title="Room Unavailable",
                content=f"Room {room.number} - {room.name} is no longer available. "
                f"Please contact administration for alternative arrangements.",
                notification_type="room_change",
                priority="high",
            )
        except Exception:
            pass


def _log_timetable_activity(timetable, action):
    """Log timetable activity for audit purposes"""

    try:
        from core.models import AuditLog

        AuditLog.objects.create(
            user=getattr(timetable, "created_by", None),
            action=action,
            entity_type="Timetable",
            entity_id=str(timetable.id) if timetable.id else None,
            data_after={
                "class": str(timetable.class_assigned),
                "subject": str(timetable.subject),
                "teacher": str(timetable.teacher),
                "time_slot": str(timetable.time_slot),
                "room": str(timetable.room) if timetable.room else None,
            },
        )
    except Exception:
        pass  # Handle if audit logging not available


def _update_scheduling_analytics(term):
    """Update scheduling analytics after timetable changes"""

    # This would trigger analytics recalculation
    # Could be done asynchronously with Celery

    try:
        from .services.analytics_service import SchedulingAnalyticsService

        # Schedule analytics update (could be async)
        # For now, just mark that an update is needed
        pass

    except Exception:
        pass


# Signal to handle cascade deletions and maintain data integrity


@receiver(pre_delete, sender=Teacher)
def teacher_deletion_handler(sender, instance, **kwargs):
    """Handle teacher deletion - reassign or deactivate timetables"""

    active_timetables = Timetable.objects.filter(
        teacher=instance, is_active=True, effective_to_date__gte=timezone.now().date()
    )

    if active_timetables.exists():
        # Deactivate future timetables instead of deleting
        active_timetables.update(is_active=False)

        # Notify administrators
        try:
            from accounts.models import User

            admins = User.objects.filter(is_staff=True)

            for admin in admins:
                Notification.objects.create(
                    user=admin,
                    title="Teacher Removed - Timetables Affected",
                    content=f"Teacher {instance.user.get_full_name()} has been removed. "
                    f"{active_timetables.count()} timetable entries have been deactivated.",
                    notification_type="system",
                    priority="high",
                )
        except Exception:
            pass


@receiver(pre_delete, sender=Room)
def room_deletion_handler(sender, instance, **kwargs):
    """Handle room deletion - clear room assignments"""

    active_timetables = Timetable.objects.filter(
        room=instance, is_active=True, effective_to_date__gte=timezone.now().date()
    )

    if active_timetables.exists():
        # Clear room assignments instead of deleting timetables
        active_timetables.update(room=None)

        # This would trigger room reassignment logic if available


# Performance optimization signals


@receiver(post_save, sender=Timetable)
def invalidate_timetable_cache(sender, instance, **kwargs):
    """Invalidate relevant caches when timetable changes"""

    try:
        from django.core.cache import cache

        # Invalidate class timetable cache
        cache_keys = [
            f"class_timetable_{instance.class_assigned.id}_{instance.term.id}",
            f"teacher_timetable_{instance.teacher.id}_{instance.term.id}",
            (
                f"room_schedule_{instance.room.id}_{instance.term.id}"
                if instance.room
                else None
            ),
        ]

        for key in cache_keys:
            if key:
                cache.delete(key)

    except Exception:
        pass
