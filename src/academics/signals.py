"""
Django Signals for Academics Module

This module contains signal handlers for maintaining data consistency
and automatic updates in the academics module.
"""

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models.signals import post_delete, post_save, pre_delete, pre_save
from django.dispatch import receiver

from .models import AcademicYear, Class, Department, Grade, Section, Term


@receiver(pre_save, sender=AcademicYear)
def validate_academic_year_before_save(sender, instance, **kwargs):
    """Validate academic year before saving"""
    # Ensure only one current academic year
    if instance.is_current:
        existing_current = AcademicYear.objects.filter(is_current=True).exclude(
            pk=instance.pk
        )

        if existing_current.exists():
            # This will be handled in the model's save method
            pass


@receiver(post_save, sender=AcademicYear)
def academic_year_post_save(sender, instance, created, **kwargs):
    """Handle post-save actions for academic year"""
    if created:
        # Log creation
        try:
            from core.models import AuditLog

            AuditLog.objects.create(
                action="Create",
                entity_type="AcademicYear",
                entity_id=instance.id,
                data_after={
                    "name": instance.name,
                    "start_date": instance.start_date.isoformat(),
                    "end_date": instance.end_date.isoformat(),
                    "is_current": instance.is_current,
                },
            )
        except ImportError:
            pass  # AuditLog not available


@receiver(pre_save, sender=Term)
def validate_term_before_save(sender, instance, **kwargs):
    """Validate term before saving"""
    # Ensure only one current term per academic year
    if instance.is_current:
        existing_current = Term.objects.filter(
            academic_year=instance.academic_year, is_current=True
        ).exclude(pk=instance.pk)

        if existing_current.exists():
            # This will be handled in the model's save method
            pass


@receiver(post_save, sender=Term)
def term_post_save(sender, instance, created, **kwargs):
    """Handle post-save actions for term"""
    if created:
        # Update analytics if analytics module is available
        try:
            from analytics.tasks import update_term_analytics

            transaction.on_commit(lambda: update_term_analytics.delay(instance.id))
        except ImportError:
            pass


@receiver(pre_save, sender=Class)
def validate_class_before_save(sender, instance, **kwargs):
    """Validate class before saving"""
    # Auto-set section from grade
    if instance.grade and not instance.section:
        instance.section = instance.grade.section

    # Validate section matches grade's section
    if instance.grade and instance.section:
        if instance.grade.section != instance.section:
            raise ValidationError("Section must match the grade's section")


@receiver(post_save, sender=Class)
def class_post_save(sender, instance, created, **kwargs):
    """Handle post-save actions for class"""
    if created:
        # Create default fee structure if finance module is available
        try:
            from finance._services import FeeService

            current_term = instance.academic_year.get_current_term()
            if current_term:
                transaction.on_commit(
                    lambda: FeeService.create_default_fee_structure_for_class(
                        instance.id, current_term.id
                    )
                )
        except ImportError:
            pass

        # Log creation
        try:
            from core.models import AuditLog

            AuditLog.objects.create(
                action="Create",
                entity_type="Class",
                entity_id=instance.id,
                data_after={
                    "name": instance.name,
                    "display_name": instance.display_name,
                    "grade_id": instance.grade.id,
                    "section_id": instance.section.id,
                    "academic_year_id": instance.academic_year.id,
                    "capacity": instance.capacity,
                },
            )
        except ImportError:
            pass


@receiver(pre_delete, sender=Class)
def validate_class_before_delete(sender, instance, **kwargs):
    """Validate class before deletion"""
    # Check if class has enrolled students
    student_count = instance.get_students_count()
    if student_count > 0:
        raise ValidationError(
            f"Cannot delete class with {student_count} enrolled students"
        )


@receiver(post_delete, sender=Class)
def class_post_delete(sender, instance, **kwargs):
    """Handle post-delete actions for class"""
    # Log deletion
    try:
        from core.models import AuditLog

        AuditLog.objects.create(
            action="Delete",
            entity_type="Class",
            entity_id=instance.id,
            data_before={
                "name": instance.name,
                "display_name": instance.display_name,
                "grade_id": instance.grade.id if instance.grade else None,
                "section_id": instance.section.id if instance.section else None,
            },
        )
    except ImportError:
        pass


@receiver(post_save, sender=Grade)
def grade_post_save(sender, instance, created, **kwargs):
    """Handle post-save actions for grade"""
    if created:
        # Create default subjects for grade if subjects module is available
        try:
            from subjects.services import SubjectService

            transaction.on_commit(
                lambda: SubjectService.create_default_subjects_for_grade(instance.id)
            )
        except ImportError:
            pass


@receiver(pre_delete, sender=Grade)
def validate_grade_before_delete(sender, instance, **kwargs):
    """Validate grade before deletion"""
    # Check if grade has active classes
    active_classes = instance.classes.filter(is_active=True).count()
    if active_classes > 0:
        raise ValidationError(
            f"Cannot delete grade with {active_classes} active classes"
        )


@receiver(pre_delete, sender=Section)
def validate_section_before_delete(sender, instance, **kwargs):
    """Validate section before deletion"""
    # Check if section has active grades
    active_grades = instance.grades.filter(is_active=True).count()
    if active_grades > 0:
        raise ValidationError(
            f"Cannot delete section with {active_grades} active grades"
        )


@receiver(post_save, sender=Department)
def department_post_save(sender, instance, created, **kwargs):
    """Handle post-save actions for department"""
    if created:
        # Create default subjects for department if subjects module is available
        try:
            from subjects.services import SubjectService

            transaction.on_commit(
                lambda: SubjectService.create_default_subjects_for_department(
                    instance.id
                )
            )
        except ImportError:
            pass


# Student enrollment signals


def student_enrolled_in_class(sender, instance, created, **kwargs):
    """Handle student enrollment in class"""
    if created and hasattr(instance, "current_class"):
        # Update class analytics
        try:
            from analytics.tasks import update_class_analytics

            transaction.on_commit(
                lambda: update_class_analytics.delay(instance.current_class.id)
            )
        except ImportError:
            pass

        # Check class capacity
        cls = instance.current_class
        if cls.get_students_count() > cls.capacity:
            # Send notification to administrators
            try:
                from communications.services import NotificationService

                transaction.on_commit(
                    lambda: NotificationService.send_capacity_warning(
                        cls.id, "Class exceeds capacity"
                    )
                )
            except ImportError:
                pass


def student_transferred_between_classes(sender, instance, **kwargs):
    """Handle student transfer between classes"""
    if hasattr(instance, "_state") and instance._state.adding is False:
        # Get old values
        try:
            old_instance = sender.objects.get(pk=instance.pk)
            if (
                hasattr(old_instance, "current_class")
                and hasattr(instance, "current_class")
                and old_instance.current_class != instance.current_class
            ):

                # Update analytics for both classes
                try:
                    from analytics.tasks import update_class_analytics

                    if old_instance.current_class:
                        transaction.on_commit(
                            lambda: update_class_analytics.delay(
                                old_instance.current_class.id
                            )
                        )
                    if instance.current_class:
                        transaction.on_commit(
                            lambda: update_class_analytics.delay(
                                instance.current_class.id
                            )
                        )
                except ImportError:
                    pass

                # Log transfer
                try:
                    from core.models import AuditLog

                    AuditLog.objects.create(
                        action="Transfer",
                        entity_type="Student",
                        entity_id=instance.id,
                        data_before={
                            "class_id": (
                                old_instance.current_class.id
                                if old_instance.current_class
                                else None
                            ),
                            "class_name": (
                                old_instance.current_class.display_name
                                if old_instance.current_class
                                else None
                            ),
                        },
                        data_after={
                            "class_id": (
                                instance.current_class.id
                                if instance.current_class
                                else None
                            ),
                            "class_name": (
                                instance.current_class.display_name
                                if instance.current_class
                                else None
                            ),
                        },
                    )
                except ImportError:
                    pass

        except sender.DoesNotExist:
            pass


# Connect student signals if students app is available
try:
    from students.models import Student

    post_save.connect(student_enrolled_in_class, sender=Student)
    pre_save.connect(student_transferred_between_classes, sender=Student)
except ImportError:
    pass


# Academic year transition signals


@receiver(post_save, sender=AcademicYear)
def handle_academic_year_transition(sender, instance, **kwargs):
    """Handle academic year transition"""
    if instance.is_current:
        # Check if this is a transition from another academic year
        previous_years = AcademicYear.objects.filter(
            is_current=False, end_date__lt=instance.start_date
        ).order_by("-end_date")

        if previous_years.exists():
            previous_year = previous_years.first()

            # Trigger academic year transition tasks
            try:
                from analytics.tasks import process_academic_year_transition

                transaction.on_commit(
                    lambda: process_academic_year_transition.delay(
                        previous_year.id, instance.id
                    )
                )
            except ImportError:
                pass


# Analytics update signals


def update_section_analytics(section_id):
    """Update section analytics"""
    try:
        from analytics.tasks import update_section_analytics_task

        transaction.on_commit(lambda: update_section_analytics_task.delay(section_id))
    except ImportError:
        pass


def update_grade_analytics(grade_id):
    """Update grade analytics"""
    try:
        from analytics.tasks import update_grade_analytics_task

        transaction.on_commit(lambda: update_grade_analytics_task.delay(grade_id))
    except ImportError:
        pass


# Connect analytics update signals
@receiver(post_save, sender=Class)
def trigger_analytics_update_on_class_save(sender, instance, **kwargs):
    """Trigger analytics updates when class is saved"""
    update_section_analytics(instance.section.id)
    update_grade_analytics(instance.grade.id)


@receiver(post_delete, sender=Class)
def trigger_analytics_update_on_class_delete(sender, instance, **kwargs):
    """Trigger analytics updates when class is deleted"""
    update_section_analytics(instance.section.id)
    update_grade_analytics(instance.grade.id)


# Performance optimization signals


@receiver(post_save, sender=Class)
def invalidate_section_cache(sender, instance, **kwargs):
    """Invalidate section-related caches"""
    try:
        from django.core.cache import cache

        cache_keys = [
            f"section_hierarchy_{instance.section.id}",
            f"section_analytics_{instance.section.id}",
            f"grade_details_{instance.grade.id}",
            "sections_summary",
        ]
        cache.delete_many(cache_keys)
    except ImportError:
        pass


@receiver(post_save, sender=AcademicYear)
def invalidate_academic_year_cache(sender, instance, **kwargs):
    """Invalidate academic year related caches"""
    try:
        from django.core.cache import cache

        cache_keys = [
            f"academic_year_summary_{instance.id}",
            "current_academic_year",
            "active_academic_years",
        ]
        cache.delete_many(cache_keys)
    except ImportError:
        pass
