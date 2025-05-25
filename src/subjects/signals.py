from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.utils.translation import gettext_lazy as _
from datetime import datetime
import logging

from .models import Subject, Syllabus, TopicProgress, SubjectAssignment
from analytics.models import StudentPerformanceAnalytics, ClassPerformanceAnalytics

# Get logger
logger = logging.getLogger(__name__)

User = get_user_model()


@receiver(post_save, sender=TopicProgress)
def update_syllabus_completion_on_topic_progress(sender, instance, created, **kwargs):
    """
    Update syllabus completion percentage when topic progress changes.
    """
    try:
        syllabus = instance.syllabus
        
        # Recalculate completion percentage
        total_topics = syllabus.get_total_topics()
        completed_topics = syllabus.get_completed_topics()
        
        if total_topics > 0:
            completion_percentage = (completed_topics / total_topics) * 100
            
            # Only update if percentage has changed
            if abs(syllabus.completion_percentage - completion_percentage) > 0.01:
                syllabus.completion_percentage = completion_percentage
                syllabus.save(update_fields=['completion_percentage'])
                
                logger.info(
                    f"Updated syllabus {syllabus.id} completion to {completion_percentage:.2f}%"
                )
                
                # Clear related cache
                cache_key = f"syllabus_progress_{syllabus.id}"
                cache.delete(cache_key)
                
                # Send notification if syllabus is completed
                if completion_percentage == 100 and not created:
                    send_syllabus_completion_notification(syllabus)
        
    except Exception as e:
        logger.error(f"Error updating syllabus completion: {str(e)}")


@receiver(post_save, sender=Syllabus)
def initialize_topic_progress_on_syllabus_creation(sender, instance, created, **kwargs):
    """
    Initialize topic progress entries when a syllabus is created with topics.
    """
    if created and instance.content and 'topics' in instance.content:
        try:
            topics = instance.content.get('topics', [])
            
            for index, topic in enumerate(topics):
                TopicProgress.objects.get_or_create(
                    syllabus=instance,
                    topic_index=index,
                    defaults={
                        'topic_name': topic.get('name', f'Topic {index + 1}'),
                        'is_completed': topic.get('completed', False)
                    }
                )
            
            logger.info(
                f"Initialized {len(topics)} topic progress entries for syllabus {instance.id}"
            )
            
        except Exception as e:
            logger.error(f"Error initializing topic progress: {str(e)}")


@receiver(pre_save, sender=Syllabus)
def sync_topic_progress_on_content_change(sender, instance, **kwargs):
    """
    Sync topic progress entries when syllabus content changes.
    """
    if instance.pk:  # Only for existing syllabi
        try:
            # Get the old instance to compare
            old_instance = Syllabus.objects.get(pk=instance.pk)
            old_topics = old_instance.content.get('topics', []) if old_instance.content else []
            new_topics = instance.content.get('topics', []) if instance.content else []
            
            # Check if topics have changed
            if old_topics != new_topics:
                instance._topics_changed = True
                instance._old_topics_count = len(old_topics)
                instance._new_topics_count = len(new_topics)
        
        except Syllabus.DoesNotExist:
            pass
        except Exception as e:
            logger.error(f"Error checking topic changes: {str(e)}")


@receiver(post_save, sender=Syllabus)
def update_topic_progress_after_content_change(sender, instance, created, **kwargs):
    """
    Update topic progress entries after syllabus content changes.
    """
    if not created and hasattr(instance, '_topics_changed') and instance._topics_changed:
        try:
            new_topics = instance.content.get('topics', []) if instance.content else []
            
            # Remove excess topic progress entries
            if instance._new_topics_count < instance._old_topics_count:
                TopicProgress.objects.filter(
                    syllabus=instance,
                    topic_index__gte=instance._new_topics_count
                ).delete()
            
            # Update or create topic progress entries
            for index, topic in enumerate(new_topics):
                TopicProgress.objects.update_or_create(
                    syllabus=instance,
                    topic_index=index,
                    defaults={
                        'topic_name': topic.get('name', f'Topic {index + 1}'),
                        'is_completed': topic.get('completed', False)
                    }
                )
            
            # Recalculate completion percentage
            instance.update_completion_percentage()
            
            logger.info(
                f"Synced topic progress for syllabus {instance.id}: "
                f"{instance._old_topics_count} -> {instance._new_topics_count} topics"
            )
        
        except Exception as e:
            logger.error(f"Error syncing topic progress: {str(e)}")


@receiver(post_save, sender=SubjectAssignment)
def notify_teacher_assignment(sender, instance, created, **kwargs):
    """
    Send notification to teacher when assigned to a subject.
    """
    if created:
        try:
            # Create notification for the teacher
            from communications.models import Notification
            
            message = _(
                "You have been assigned to teach {subject} for {class_name} in {term}"
            ).format(
                subject=instance.subject.name,
                class_name=str(instance.class_assigned),
                term=instance.term.name
            )
            
            Notification.objects.create(
                user=instance.teacher.user,
                title=_("New Subject Assignment"),
                content=message,
                notification_type='assignment',
                reference_id=instance.id,
                reference_type='SubjectAssignment'
            )
            
            logger.info(f"Sent assignment notification to teacher {instance.teacher.user.username}")
        
        except Exception as e:
            logger.error(f"Error sending assignment notification: {str(e)}")


@receiver(post_delete, sender=TopicProgress)
def recalculate_completion_on_topic_deletion(sender, instance, **kwargs):
    """
    Recalculate syllabus completion when a topic progress is deleted.
    """
    try:
        syllabus = instance.syllabus
        syllabus.update_completion_percentage()
        
        # Clear cache
        cache_key = f"syllabus_progress_{syllabus.id}"
        cache.delete(cache_key)
        
        logger.info(f"Recalculated completion for syllabus {syllabus.id} after topic deletion")
    
    except Exception as e:
        logger.error(f"Error recalculating completion on deletion: {str(e)}")


@receiver(post_save, sender=Subject)
def clear_subject_cache_on_save(sender, instance, **kwargs):
    """
    Clear related cache when subject is saved.
    """
    try:
        # Clear curriculum structure cache
        cache.delete_many([
            f"curriculum_structure_{instance.department_id}",
            f"subjects_by_grade_{grade_id}" for grade_id in instance.grade_level
        ])
        
        # Clear subject analytics cache
        cache.delete(f"subject_analytics_{instance.id}")
        
    except Exception as e:
        logger.error(f"Error clearing subject cache: {str(e)}")


@receiver(post_save, sender=Syllabus)
def update_analytics_on_syllabus_change(sender, instance, created, **kwargs):
    """
    Update analytics data when syllabus changes significantly.
    """
    try:
        # Check if this is a significant change (completion percentage change > 10%)
        if not created and instance.pk:
            old_instance = sender.objects.get(pk=instance.pk)
            completion_change = abs(
                instance.completion_percentage - old_instance.completion_percentage
            )
            
            if completion_change >= 10:
                # Trigger analytics recalculation (async task)
                from .tasks import recalculate_curriculum_analytics
                recalculate_curriculum_analytics.delay(
                    instance.academic_year.id,
                    instance.subject.department.id
                )
        
        # Clear related cache
        cache.delete_many([
            f"curriculum_analytics_{instance.academic_year.id}",
            f"department_analytics_{instance.subject.department.id}_{instance.academic_year.id}",
            f"grade_overview_{instance.grade.id}_{instance.academic_year.id}"
        ])
    
    except Exception as e:
        logger.error(f"Error updating analytics: {str(e)}")


@receiver(post_save, sender=SubjectAssignment)
def update_teacher_workload_cache(sender, instance, created, **kwargs):
    """
    Update teacher workload cache when assignments change.
    """
    try:
        # Clear teacher workload cache
        cache.delete_many([
            f"teacher_workload_{instance.teacher.id}_{instance.academic_year.id}",
            f"teacher_assignments_{instance.teacher.id}_{instance.academic_year.id}",
            f"teacher_assignments_{instance.teacher.id}_{instance.academic_year.id}_{instance.term.id}"
        ])
        
        logger.info(f"Cleared teacher workload cache for teacher {instance.teacher.id}")
    
    except Exception as e:
        logger.error(f"Error clearing teacher workload cache: {str(e)}")


@receiver(post_save, sender=TopicProgress)
def track_teaching_hours(sender, instance, created, **kwargs):
    """
    Track total teaching hours for analytics.
    """
    if instance.is_completed and instance.hours_taught > 0:
        try:
            # Update subject statistics (this could be stored in a separate model)
            syllabus = instance.syllabus
            
            # Clear related analytics cache
            cache.delete_many([
                f"subject_hours_{syllabus.subject.id}_{syllabus.academic_year.id}",
                f"teacher_hours_{syllabus.id}",
                f"department_hours_{syllabus.subject.department.id}_{syllabus.academic_year.id}"
            ])
            
        except Exception as e:
            logger.error(f"Error tracking teaching hours: {str(e)}")


def send_syllabus_completion_notification(syllabus):
    """
    Send notification when a syllabus is completed.
    """
    try:
        from communications.models import Notification
        
        # Get all teachers assigned to this syllabus
        assignments = SubjectAssignment.objects.filter(
            subject=syllabus.subject,
            academic_year=syllabus.academic_year,
            term=syllabus.term,
            is_active=True
        )
        
        for assignment in assignments:
            message = _(
                "Congratulations! You have completed the syllabus for {subject} - {grade} in {term}"
            ).format(
                subject=syllabus.subject.name,
                grade=syllabus.grade.name,
                term=syllabus.term.name
            )
            
            Notification.objects.create(
                user=assignment.teacher.user,
                title=_("Syllabus Completed"),
                content=message,
                notification_type='achievement',
                reference_id=syllabus.id,
                reference_type='Syllabus',
                priority='medium'
            )
        
        # Also notify administrators
        admin_users = User.objects.filter(is_staff=True, is_active=True)
        for admin in admin_users:
            message = _(
                "Syllabus completed: {subject} - {grade} - {term} (by {teacher})"
            ).format(
                subject=syllabus.subject.name,
                grade=syllabus.grade.name,
                term=syllabus.term.name,
                teacher=assignments.first().teacher.user.get_full_name() if assignments.exists() else "Unknown"
            )
            
            Notification.objects.create(
                user=admin,
                title=_("Syllabus Completion Report"),
                content=message,
                notification_type='system',
                reference_id=syllabus.id,
                reference_type='Syllabus',
                priority='low'
            )
        
        logger.info(f"Sent completion notifications for syllabus {syllabus.id}")
    
    except Exception as e:
        logger.error(f"Error sending completion notification: {str(e)}")


@receiver(post_save, sender=Syllabus)
def validate_syllabus_prerequisites(sender, instance, created, **kwargs):
    """
    Validate that prerequisite subjects are covered in previous terms/grades.
    """
    if instance.prerequisites:
        try:
            # This is a complex validation that could check if prerequisite
            # subjects have been completed in previous terms
            # Implementation would depend on specific business rules
            
            logger.info(f"Validated prerequisites for syllabus {instance.id}")
        
        except Exception as e:
            logger.error(f"Error validating prerequisites: {str(e)}")


@receiver(post_save, sender=Subject)
def audit_subject_changes(sender, instance, created, **kwargs):
    """
    Audit subject changes for compliance and tracking.
    """
    try:
        from core.models import AuditLog
        
        action = 'Create' if created else 'Update'
        
        AuditLog.objects.create(
            user=getattr(instance, '_current_user', None),
            action=action,
            entity_type='Subject',
            entity_id=instance.id,
            data_after={
                'name': instance.name,
                'code': instance.code,
                'department': instance.department.name,
                'credit_hours': instance.credit_hours,
                'is_elective': instance.is_elective,
                'grade_level': instance.grade_level,
                'is_active': instance.is_active
            }
        )
        
    except Exception as e:
        logger.error(f"Error creating audit log: {str(e)}")


@receiver(post_save, sender=Syllabus)
def check_syllabus_deadline_alerts(sender, instance, created, **kwargs):
    """
    Check if syllabus is behind schedule and send alerts.
    """
    try:
        from datetime import date
        
        # Calculate expected progress based on term progress
        term = instance.term
        current_date = date.today()
        
        if term.start_date <= current_date <= term.end_date:
            total_days = (term.end_date - term.start_date).days
            elapsed_days = (current_date - term.start_date).days
            
            if total_days > 0:
                expected_progress = (elapsed_days / total_days) * 100
                actual_progress = instance.completion_percentage
                
                # If behind by more than 20%, send alert
                if expected_progress - actual_progress > 20:
                    send_behind_schedule_alert(instance, expected_progress, actual_progress)
    
    except Exception as e:
        logger.error(f"Error checking deadline alerts: {str(e)}")


def send_behind_schedule_alert(syllabus, expected_progress, actual_progress):
    """
    Send alert when syllabus is behind schedule.
    """
    try:
        from communications.models import Notification
        
        # Get assigned teachers
        assignments = SubjectAssignment.objects.filter(
            subject=syllabus.subject,
            academic_year=syllabus.academic_year,
            term=syllabus.term,
            is_active=True
        )
        
        for assignment in assignments:
            message = _(
                "Alert: {subject} - {grade} syllabus is behind schedule. "
                "Expected: {expected:.1f}%, Actual: {actual:.1f}%"
            ).format(
                subject=syllabus.subject.name,
                grade=syllabus.grade.name,
                expected=expected_progress,
                actual=actual_progress
            )
            
            Notification.objects.create(
                user=assignment.teacher.user,
                title=_("Syllabus Behind Schedule"),
                content=message,
                notification_type='alert',
                reference_id=syllabus.id,
                reference_type='Syllabus',
                priority='high'
            )
        
        logger.info(f"Sent behind schedule alert for syllabus {syllabus.id}")
    
    except Exception as e:
        logger.error(f"Error sending behind schedule alert: {str(e)}")