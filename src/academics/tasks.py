"""
Background Tasks for Academics Module

This module contains Celery tasks for processing academic data,
generating reports, and performing maintenance operations.
"""

from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from django.db import transaction
from datetime import datetime, timedelta
import logging

from .models import AcademicYear, Term, Section, Grade, Class, Department
from .services import AcademicYearService, SectionService, GradeService, ClassService
from .utils import validate_academic_structure_integrity, clear_academics_cache

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def calculate_section_analytics(self, section_id):
    """
    Calculate and update analytics for a section

    Args:
        section_id: ID of the section to process
    """
    try:
        logger.info(f"Starting analytics calculation for section {section_id}")

        # Get section analytics
        analytics = SectionService.get_section_analytics(section_id)

        # Store analytics in database if analytics module is available
        try:
            from analytics.models import SectionAnalytics
            from analytics.services import AnalyticsService

            AnalyticsService.store_section_analytics(section_id, analytics)
            logger.info(f"Stored analytics for section {section_id}")

        except ImportError:
            logger.warning("Analytics module not available, skipping storage")

        # Clear related cache
        from django.core.cache import cache

        cache.delete(f"section_analytics_{section_id}")

        logger.info(f"Completed analytics calculation for section {section_id}")
        return {"success": True, "section_id": section_id}

    except Exception as exc:
        logger.error(
            f"Error calculating analytics for section {section_id}: {str(exc)}"
        )
        # Retry with exponential backoff
        raise self.retry(exc=exc, countdown=60 * (2**self.request.retries))


@shared_task(bind=True, max_retries=3)
def calculate_grade_analytics(self, grade_id):
    """
    Calculate and update analytics for a grade

    Args:
        grade_id: ID of the grade to process
    """
    try:
        logger.info(f"Starting analytics calculation for grade {grade_id}")

        # Get grade details and analytics
        details = GradeService.get_grade_details(grade_id)

        # Store analytics if module available
        try:
            from analytics.models import GradeAnalytics
            from analytics.services import AnalyticsService

            AnalyticsService.store_grade_analytics(grade_id, details)
            logger.info(f"Stored analytics for grade {grade_id}")

        except ImportError:
            logger.warning("Analytics module not available, skipping storage")

        # Clear related cache
        from django.core.cache import cache

        cache.delete(f"grade_details_{grade_id}")

        logger.info(f"Completed analytics calculation for grade {grade_id}")
        return {"success": True, "grade_id": grade_id}

    except Exception as exc:
        logger.error(f"Error calculating analytics for grade {grade_id}: {str(exc)}")
        raise self.retry(exc=exc, countdown=60 * (2**self.request.retries))


@shared_task(bind=True, max_retries=3)
def calculate_class_analytics(self, class_id):
    """
    Calculate and update analytics for a class

    Args:
        class_id: ID of the class to process
    """
    try:
        logger.info(f"Starting analytics calculation for class {class_id}")

        # Get class analytics
        analytics = ClassService.get_class_analytics(class_id)

        # Store analytics if module available
        try:
            from analytics.models import ClassAnalytics
            from analytics.services import AnalyticsService

            AnalyticsService.store_class_analytics(class_id, analytics)
            logger.info(f"Stored analytics for class {class_id}")

        except ImportError:
            logger.warning("Analytics module not available, skipping storage")

        # Check for capacity warnings
        if analytics["enrollment"]["utilization_rate"] > 95:
            send_capacity_warning.delay(class_id, "over_capacity")

        logger.info(f"Completed analytics calculation for class {class_id}")
        return {"success": True, "class_id": class_id}

    except Exception as exc:
        logger.error(f"Error calculating analytics for class {class_id}: {str(exc)}")
        raise self.retry(exc=exc, countdown=60 * (2**self.request.retries))


@shared_task
def daily_academic_maintenance():
    """
    Daily maintenance task for academic data
    """
    logger.info("Starting daily academic maintenance")

    try:
        # Validate academic structure integrity
        validation_results = validate_academic_structure_integrity()

        if not validation_results["is_valid"]:
            # Send alert to administrators
            send_structure_integrity_alert.delay(validation_results)

        # Update term status based on current date
        update_term_status.delay()

        # Calculate analytics for all active sections
        active_sections = Section.objects.filter(is_active=True)
        for section in active_sections:
            calculate_section_analytics.delay(section.id)

        # Clear old cache entries
        clear_academics_cache()

        logger.info("Completed daily academic maintenance")
        return {"success": True, "processed_sections": active_sections.count()}

    except Exception as e:
        logger.error(f"Error in daily academic maintenance: {str(e)}")
        return {"success": False, "error": str(e)}


@shared_task
def update_term_status():
    """
    Update term status based on current date
    """
    logger.info("Starting term status update")

    try:
        today = timezone.now().date()

        # Get current academic year
        current_year = AcademicYearService.get_current_academic_year()
        if not current_year:
            logger.warning("No current academic year found")
            return {"success": False, "error": "No current academic year"}

        # Check if we need to transition to next term
        current_term = current_year.get_current_term()

        if current_term and today > current_term.end_date:
            # Current term has ended, find next term
            next_term = Term.objects.filter(
                academic_year=current_year, term_number=current_term.term_number + 1
            ).first()

            if next_term:
                # Transition to next term
                with transaction.atomic():
                    current_term.is_current = False
                    current_term.save()

                    next_term.is_current = True
                    next_term.save()

                logger.info(
                    f"Transitioned from {current_term.name} to {next_term.name}"
                )

                # Send notification to administrators
                send_term_transition_notification.delay(current_term.id, next_term.id)

                return {
                    "success": True,
                    "transitioned": True,
                    "from_term": current_term.name,
                    "to_term": next_term.name,
                }

        elif not current_term:
            # No current term set, set the appropriate one
            today = timezone.now().date()
            appropriate_term = Term.objects.filter(
                academic_year=current_year, start_date__lte=today, end_date__gte=today
            ).first()

            if appropriate_term:
                appropriate_term.is_current = True
                appropriate_term.save()

                logger.info(f"Set {appropriate_term.name} as current term")
                return {"success": True, "set_current_term": appropriate_term.name}

        logger.info("Term status update completed - no changes needed")
        return {"success": True, "transitioned": False}

    except Exception as e:
        logger.error(f"Error updating term status: {str(e)}")
        return {"success": False, "error": str(e)}


@shared_task
def send_capacity_warning(class_id, warning_type):
    """
    Send capacity warning notification

    Args:
        class_id: ID of the class
        warning_type: Type of warning ('over_capacity', 'near_capacity')
    """
    try:
        cls = Class.objects.get(id=class_id)
        student_count = cls.get_students_count()

        subject = f"Class Capacity Warning: {cls.display_name}"

        if warning_type == "over_capacity":
            message = f"""
            Class {cls.display_name} is over capacity.
            
            Current enrollment: {student_count} students
            Class capacity: {cls.capacity} students
            Over capacity by: {student_count - cls.capacity} students
            
            Please take appropriate action to address this issue.
            """
        else:
            message = f"""
            Class {cls.display_name} is near capacity.
            
            Current enrollment: {student_count} students
            Class capacity: {cls.capacity} students
            Available spots: {cls.get_available_capacity()} students
            
            Please monitor enrollment for this class.
            """

        # Get admin emails
        admin_emails = get_admin_emails()

        if admin_emails:
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=admin_emails,
                fail_silently=False,
            )

            logger.info(f"Sent capacity warning for class {class_id}")

        return {"success": True, "class_id": class_id, "warning_type": warning_type}

    except Exception as e:
        logger.error(f"Error sending capacity warning for class {class_id}: {str(e)}")
        return {"success": False, "error": str(e)}


@shared_task
def send_structure_integrity_alert(validation_results):
    """
    Send academic structure integrity alert

    Args:
        validation_results: Results from structure validation
    """
    try:
        subject = "Academic Structure Integrity Alert"

        message = f"""
        Academic structure integrity check has found issues:
        
        Issues ({validation_results['total_issues']}):
        """

        for issue in validation_results["issues"]:
            message += f"- {issue}\n"

        if validation_results["warnings"]:
            message += f"\nWarnings ({validation_results['total_warnings']}):\n"
            for warning in validation_results["warnings"]:
                message += f"- {warning}\n"

        message += "\nPlease review and address these issues promptly."

        # Get admin emails
        admin_emails = get_admin_emails()

        if admin_emails:
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=admin_emails,
                fail_silently=False,
            )

            logger.info("Sent structure integrity alert")

        return {"success": True}

    except Exception as e:
        logger.error(f"Error sending structure integrity alert: {str(e)}")
        return {"success": False, "error": str(e)}


@shared_task
def send_term_transition_notification(from_term_id, to_term_id):
    """
    Send term transition notification

    Args:
        from_term_id: ID of previous term
        to_term_id: ID of new current term
    """
    try:
        from_term = Term.objects.get(id=from_term_id)
        to_term = Term.objects.get(id=to_term_id)

        subject = f"Academic Term Transition: {to_term.name}"

        message = f"""
        The academic term has been automatically transitioned:
        
        Previous term: {from_term.name}
        Current term: {to_term.name}
        Academic Year: {to_term.academic_year.name}
        
        Term Details:
        - Start Date: {to_term.start_date}
        - End Date: {to_term.end_date}
        - Duration: {to_term.get_duration_days()} days
        
        Please ensure all relevant staff are informed of this transition.
        """

        # Get admin and academic staff emails
        recipient_emails = get_academic_staff_emails()

        if recipient_emails:
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=recipient_emails,
                fail_silently=False,
            )

            logger.info(
                f"Sent term transition notification from {from_term.name} to {to_term.name}"
            )

        return {"success": True, "from_term": from_term.name, "to_term": to_term.name}

    except Exception as e:
        logger.error(f"Error sending term transition notification: {str(e)}")
        return {"success": False, "error": str(e)}


@shared_task
def generate_academic_summary_report(academic_year_id):
    """
    Generate comprehensive academic summary report

    Args:
        academic_year_id: ID of academic year to report on
    """
    try:
        logger.info(f"Generating academic summary report for year {academic_year_id}")

        # Get academic year summary
        summary = AcademicYearService.get_academic_year_summary(academic_year_id)

        # Generate detailed report
        report_data = {
            "generated_at": timezone.now(),
            "academic_year": summary["academic_year"],
            "statistics": summary["statistics"],
            "terms": summary["terms"],
            "sections": [],
        }

        # Add section details
        active_sections = Section.objects.filter(is_active=True)
        for section in active_sections:
            section_analytics = SectionService.get_section_analytics(
                section.id, academic_year_id
            )
            report_data["sections"].append(section_analytics)

        # Store report if reports module is available
        try:
            from reports.models import GeneratedReport
            from reports.services import ReportService

            ReportService.store_academic_summary_report(academic_year_id, report_data)
            logger.info(f"Stored academic summary report for year {academic_year_id}")

        except ImportError:
            logger.warning("Reports module not available, skipping storage")

        logger.info(f"Completed academic summary report for year {academic_year_id}")
        return {"success": True, "academic_year_id": academic_year_id}

    except Exception as e:
        logger.error(f"Error generating academic summary report: {str(e)}")
        return {"success": False, "error": str(e)}


@shared_task
def bulk_update_class_analytics():
    """
    Update analytics for all active classes
    """
    logger.info("Starting bulk class analytics update")

    try:
        current_year = AcademicYearService.get_current_academic_year()
        if not current_year:
            logger.warning("No current academic year found")
            return {"success": False, "error": "No current academic year"}

        active_classes = Class.objects.filter(
            academic_year=current_year, is_active=True
        )

        # Queue analytics calculation for each class
        for cls in active_classes:
            calculate_class_analytics.delay(cls.id)

        logger.info(
            f"Queued analytics calculation for {active_classes.count()} classes"
        )
        return {"success": True, "classes_queued": active_classes.count()}

    except Exception as e:
        logger.error(f"Error in bulk class analytics update: {str(e)}")
        return {"success": False, "error": str(e)}


@shared_task
def process_academic_year_transition(from_year_id, to_year_id):
    """
    Process academic year transition

    Args:
        from_year_id: ID of previous academic year
        to_year_id: ID of new academic year
    """
    logger.info(
        f"Processing academic year transition from {from_year_id} to {to_year_id}"
    )

    try:
        from_year = AcademicYear.objects.get(id=from_year_id)
        to_year = AcademicYear.objects.get(id=to_year_id)

        with transaction.atomic():
            # Archive previous year's data if needed
            archive_academic_year_data.delay(from_year_id)

            # Initialize new year's structure if needed
            initialize_academic_year_structure.delay(to_year_id)

            # Generate transition report
            generate_academic_transition_report.delay(from_year_id, to_year_id)

        logger.info(f"Completed academic year transition processing")
        return {"success": True, "from_year": from_year.name, "to_year": to_year.name}

    except Exception as e:
        logger.error(f"Error processing academic year transition: {str(e)}")
        return {"success": False, "error": str(e)}


# Helper functions


def get_admin_emails():
    """Get email addresses of system administrators"""
    try:
        from django.contrib.auth import get_user_model

        User = get_user_model()

        admin_users = User.objects.filter(
            is_superuser=True, is_active=True, email__isnull=False
        ).exclude(email="")

        return list(admin_users.values_list("email", flat=True))

    except Exception:
        return []


def get_academic_staff_emails():
    """Get email addresses of academic staff"""
    try:
        from django.contrib.auth import get_user_model
        from django.contrib.auth.models import Group

        User = get_user_model()

        academic_groups = Group.objects.filter(
            name__in=["Academic Admin", "Principal", "Academic Coordinator"]
        )

        staff_users = (
            User.objects.filter(
                groups__in=academic_groups, is_active=True, email__isnull=False
            )
            .exclude(email="")
            .distinct()
        )

        return list(staff_users.values_list("email", flat=True))

    except Exception:
        return get_admin_emails()  # Fallback to admin emails


@shared_task
def archive_academic_year_data(academic_year_id):
    """
    Archive data for an academic year

    Args:
        academic_year_id: ID of academic year to archive
    """
    # Implementation would depend on archival strategy
    logger.info(f"Archiving data for academic year {academic_year_id}")
    # Placeholder for archival logic
    return {"success": True, "academic_year_id": academic_year_id}


@shared_task
def initialize_academic_year_structure(academic_year_id):
    """
    Initialize structure for a new academic year

    Args:
        academic_year_id: ID of academic year to initialize
    """
    # Implementation would create default classes, fee structures, etc.
    logger.info(f"Initializing structure for academic year {academic_year_id}")
    # Placeholder for initialization logic
    return {"success": True, "academic_year_id": academic_year_id}


@shared_task
def generate_academic_transition_report(from_year_id, to_year_id):
    """
    Generate report for academic year transition

    Args:
        from_year_id: ID of previous academic year
        to_year_id: ID of new academic year
    """
    logger.info(
        f"Generating transition report from year {from_year_id} to {to_year_id}"
    )
    # Placeholder for report generation logic
    return {"success": True, "from_year_id": from_year_id, "to_year_id": to_year_id}
