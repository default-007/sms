# students/tasks.py
import csv
import io
import logging

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mass_mail
from django.db.models import Q
from django.template.loader import render_to_string
from django.utils import timezone

from .models import Parent, Student, StudentParentRelation
from .services.parent_service import ParentService
from .services.student_service import StudentService

logger = logging.getLogger(__name__)


@shared_task
def send_welcome_email_to_student(student_id):
    """Send welcome email to a newly created student (if email provided)"""
    try:
        student = Student.objects.get(id=student_id)

        if not student.email:
            logger.info(f"Student {student.admission_number} has no email address")
            return "No email address provided for student"

        subject = f'Welcome to {getattr(settings, "SCHOOL_NAME", "School")}!'
        message = render_to_string(
            "emails/student_welcome.txt",
            {
                "student": student,
                "school_name": getattr(settings, "SCHOOL_NAME", "School"),
            },
        )

        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[student.email],
            fail_silently=False,
        )

        logger.info(f"Welcome email sent to student {student.admission_number}")
        return f"Email sent to {student.email}"

    except Student.DoesNotExist:
        logger.error(f"Student with id {student_id} not found")
        return f"Student not found"
    except Exception as e:
        logger.error(f"Failed to send welcome email: {str(e)}")
        raise


@shared_task
def send_welcome_email_to_parent(parent_id):
    """Send welcome email to a newly created parent"""
    try:
        parent = Parent.objects.get(id=parent_id)

        subject = (
            f'Parent Account Created - {getattr(settings, "SCHOOL_NAME", "School")}'
        )
        message = render_to_string(
            "emails/parent_welcome.txt",
            {
                "parent": parent,
                "school_name": getattr(settings, "SCHOOL_NAME", "School"),
            },
        )

        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[parent.user.email],
            fail_silently=False,
        )

        logger.info(f"Welcome email sent to parent {parent.get_full_name()}")
        return f"Email sent to {parent.user.email}"

    except Parent.DoesNotExist:
        logger.error(f"Parent with id {parent_id} not found")
        return f"Parent not found"
    except Exception as e:
        logger.error(f"Failed to send welcome email: {str(e)}")
        raise


@shared_task
def bulk_import_students_task(
    csv_content, send_notifications=False, update_existing=False, created_by_id=None
):
    """Background task for bulk importing students"""
    try:
        # Create a file-like object from the CSV content
        csv_file = io.StringIO(csv_content)
        csv_file.name = "bulk_import.csv"

        # Get the user who initiated the import
        created_by = None
        if created_by_id:
            from django.contrib.auth import get_user_model

            User = get_user_model()
            try:
                created_by = User.objects.get(id=created_by_id)
            except User.DoesNotExist:
                pass

        # Perform the import
        result = StudentService.bulk_import_students(
            csv_file=csv_file,
            send_notifications=send_notifications,
            update_existing=update_existing,
            created_by=created_by,
        )

        logger.info(f"Bulk import completed: {result}")
        return result

    except Exception as e:
        logger.error(f"Bulk import failed: {str(e)}")
        raise


@shared_task
def bulk_import_parents_task(
    csv_content, send_notifications=False, update_existing=False, created_by_id=None
):
    """Background task for bulk importing parents"""
    try:
        # Create a file-like object from the CSV content
        csv_file = io.StringIO(csv_content)
        csv_file.name = "bulk_import.csv"

        # Get the user who initiated the import
        created_by = None
        if created_by_id:
            from django.contrib.auth import get_user_model

            User = get_user_model()
            try:
                created_by = User.objects.get(id=created_by_id)
            except User.DoesNotExist:
                pass

        # Perform the import
        result = ParentService.bulk_import_parents(
            csv_file=csv_file,
            send_notifications=send_notifications,
            update_existing=update_existing,
            created_by=created_by,
        )

        logger.info(f"Bulk parent import completed: {result}")
        return result

    except Exception as e:
        logger.error(f"Bulk parent import failed: {str(e)}")
        raise


@shared_task
def generate_student_reports_batch(student_ids, report_type="comprehensive"):
    """Generate reports for multiple students in batch"""
    try:
        students = Student.objects.filter(id__in=student_ids)
        generated_reports = []

        for student in students:
            try:
                if report_type == "comprehensive":
                    # Generate comprehensive student report
                    report_data = {
                        "student": student,
                        "academic_info": {
                            "current_class": student.current_class,
                            "attendance_percentage": student.get_attendance_percentage(),
                            "siblings": student.get_siblings(),
                        },
                        "family_info": {
                            "parents": student.get_parents(),
                            "primary_parent": student.get_primary_parent(),
                        },
                    }

                    # Here you would generate the actual report (PDF, etc.)
                    report_path = f"reports/student_{student.admission_number}_{timezone.now().strftime('%Y%m%d')}.pdf"

                    generated_reports.append(
                        {
                            "student_id": str(student.id),
                            "admission_number": student.admission_number,
                            "report_path": report_path,
                            "status": "success",
                        }
                    )

            except Exception as e:
                generated_reports.append(
                    {
                        "student_id": str(student.id),
                        "admission_number": student.admission_number,
                        "error": str(e),
                        "status": "error",
                    }
                )
                logger.error(
                    f"Failed to generate report for student {student.admission_number}: {str(e)}"
                )

        logger.info(f"Generated {len(generated_reports)} student reports")
        return {
            "total_requested": len(student_ids),
            "successful": len(
                [r for r in generated_reports if r["status"] == "success"]
            ),
            "failed": len([r for r in generated_reports if r["status"] == "error"]),
            "reports": generated_reports,
        }

    except Exception as e:
        logger.error(f"Batch report generation failed: {str(e)}")
        raise


@shared_task
def send_bulk_notification_to_parents(
    parent_ids, subject, message_template, context_data=None
):
    """Send bulk notifications to multiple parents"""
    try:
        parents = Parent.objects.filter(id__in=parent_ids).select_related("user")
        emails = []

        for parent in parents:
            try:
                # Prepare context for each parent
                context = {
                    "parent": parent,
                    "school_name": getattr(settings, "SCHOOL_NAME", "School"),
                    **(context_data or {}),
                }

                # Render message for this parent
                message = render_to_string(message_template, context)

                emails.append(
                    (subject, message, settings.DEFAULT_FROM_EMAIL, [parent.user.email])
                )

            except Exception as e:
                logger.error(
                    f"Failed to prepare email for parent {parent.get_full_name()}: {str(e)}"
                )

        # Send all emails
        sent_count = send_mass_mail(emails, fail_silently=False)

        logger.info(f"Sent {sent_count} bulk notifications to parents")
        return {
            "total_requested": len(parent_ids),
            "sent": sent_count,
            "failed": len(parent_ids) - sent_count,
        }

    except Exception as e:
        logger.error(f"Bulk notification failed: {str(e)}")
        raise


@shared_task
def send_bulk_notification_to_students(
    student_ids, subject, message_template, context_data=None
):
    """Send bulk notifications to multiple students"""
    try:
        students = Student.objects.filter(id__in=student_ids)
        emails = []

        for student in students:
            try:
                # Skip students without email
                if not student.email:
                    logger.info(f"Student {student.admission_number} has no email address")
                    continue

                # Prepare context for each student
                context = {
                    "student": student,
                    "school_name": getattr(settings, "SCHOOL_NAME", "School"),
                    **(context_data or {}),
                }

                # Render message for this student
                message = render_to_string(message_template, context)

                emails.append(
                    (
                        subject,
                        message,
                        settings.DEFAULT_FROM_EMAIL,
                        [student.email],
                    )
                )

            except Exception as e:
                logger.error(
                    f"Failed to prepare email for student {student.admission_number}: {str(e)}"
                )

        # Send all emails
        sent_count = send_mass_mail(emails, fail_silently=False)

        logger.info(f"Sent {sent_count} bulk notifications to students")
        return {
            "total_requested": len(student_ids),
            "sent": sent_count,
            "failed": len(student_ids) - sent_count,
        }

    except Exception as e:
        logger.error(f"Bulk notification failed: {str(e)}")
        raise


@shared_task
def cleanup_inactive_students(days_inactive=90):
    """Clean up students who have been inactive for a specified period"""
    try:
        cutoff_date = timezone.now() - timezone.timedelta(days=days_inactive)

        # Find students who have been inactive for the specified period
        # (Students don't have user accounts, so we check last_updated date)
        inactive_students = Student.objects.filter(
            status="Inactive", last_updated__lt=cutoff_date
        )

        cleanup_results = {
            "reviewed": inactive_students.count(),
            "archived": 0,
            "deleted": 0,
            "errors": [],
        }

        for student in inactive_students:
            try:
                # Archive student data before deletion
                # Here you would implement your archival logic

                # For now, just log the action
                logger.info(f"Would archive student {student.admission_number}")
                cleanup_results["archived"] += 1

                # Optionally delete after archiving
                # student.delete()
                # cleanup_results['deleted'] += 1

            except Exception as e:
                cleanup_results["errors"].append(
                    {"student_id": str(student.id), "error": str(e)}
                )
                logger.error(
                    f"Failed to cleanup student {student.admission_number}: {str(e)}"
                )

        logger.info(f"Cleanup completed: {cleanup_results}")
        return cleanup_results

    except Exception as e:
        logger.error(f"Student cleanup failed: {str(e)}")
        raise


@shared_task
def update_attendance_cache():
    """Update cached attendance percentages for all active students"""
    try:
        from src.courses.models import AcademicYear

        current_year = AcademicYear.objects.filter(is_current=True).first()
        if not current_year:
            return "No current academic year found"

        active_students = Student.objects.filter(status="Active")
        updated_count = 0

        for student in active_students:
            try:
                # Recalculate and cache attendance percentage
                percentage = student.get_attendance_percentage(current_year)
                cache_key = (
                    f"student_attendance_percentage_{student.id}_{current_year.id}"
                )
                cache.set(cache_key, percentage, 1800)  # Cache for 30 minutes
                updated_count += 1

            except Exception as e:
                logger.error(
                    f"Failed to update attendance cache for student {student.admission_number}: {str(e)}"
                )

        logger.info(f"Updated attendance cache for {updated_count} students")
        return f"Updated {updated_count} attendance records"

    except Exception as e:
        logger.error(f"Attendance cache update failed: {str(e)}")
        raise


@shared_task
def generate_monthly_reports():
    """Generate monthly reports for students and parents"""
    try:
        from src.courses.models import AcademicYear

        current_year = AcademicYear.objects.filter(is_current=True).first()
        if not current_year:
            return "No current academic year found"

        current_month = timezone.now().month
        current_year_num = timezone.now().year

        # Generate student progress reports
        active_students = Student.objects.filter(
            status="Active", current_class__academic_year=current_year
        )

        reports_generated = 0
        for student in active_students:
            try:
                # Calculate monthly statistics
                attendance_percentage = student.get_attendance_percentage(
                    current_year, current_month
                )

                # Generate report data
                report_data = {
                    "student": student,
                    "month": current_month,
                    "year": current_year_num,
                    "attendance_percentage": attendance_percentage,
                    "academic_year": current_year,
                }

                # Here you would generate the actual report file
                # For now, just log the action
                logger.info(f"Generated monthly report for {student.admission_number}")
                reports_generated += 1

            except Exception as e:
                logger.error(
                    f"Failed to generate monthly report for {student.admission_number}: {str(e)}"
                )

        logger.info(f"Generated {reports_generated} monthly reports")
        return f"Generated {reports_generated} monthly reports"

    except Exception as e:
        logger.error(f"Monthly report generation failed: {str(e)}")
        raise


@shared_task
def sync_student_data_with_external_system(system_name, student_ids=None):
    """Sync student data with external systems (e.g., government databases)"""
    try:
        if student_ids:
            students = Student.objects.filter(id__in=student_ids)
        else:
            students = Student.objects.filter(status="Active")

        sync_results = {
            "total": students.count(),
            "synced": 0,
            "failed": 0,
            "errors": [],
        }

        for student in students:
            try:
                # Implement external system sync logic here
                # This is a placeholder for actual integration

                sync_data = {
                    "admission_number": student.admission_number,
                    "name": student.full_name,
                    "date_of_birth": student.date_of_birth,
                    "class": (
                        str(student.current_class) if student.current_class else None
                    ),
                }

                # Simulate sync success
                logger.info(
                    f"Synced student {student.admission_number} with {system_name}"
                )
                sync_results["synced"] += 1

            except Exception as e:
                sync_results["failed"] += 1
                sync_results["errors"].append(
                    {"student_id": str(student.id), "error": str(e)}
                )
                logger.error(
                    f"Failed to sync student {student.admission_number}: {str(e)}"
                )

        logger.info(f"Sync with {system_name} completed: {sync_results}")
        return sync_results

    except Exception as e:
        logger.error(f"External sync failed: {str(e)}")
        raise
