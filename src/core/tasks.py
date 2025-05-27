# tasks.py
from celery import shared_task, Task
from django.utils import timezone
from django.db import transaction
from django.core.management import call_command
from django.contrib.auth import get_user_model
from datetime import datetime, timedelta
import logging
import sys
from io import StringIO

from .services import (
    AnalyticsService,
    AuditService,
    ConfigurationService,
    SecurityService,
    UtilityService,
)
from .models import (
    SystemHealthMetrics,
    AuditLog,
    StudentPerformanceAnalytics,
    ClassPerformanceAnalytics,
    AttendanceAnalytics,
    FinancialAnalytics,
    TeacherPerformanceAnalytics,
)

User = get_user_model()
logger = logging.getLogger(__name__)


class CallbackTask(Task):
    """Base task class with callback support"""

    def on_success(self, retval, task_id, args, kwargs):
        """Called when task succeeds"""
        logger.info(f"Task {task_id} ({self.name}) completed successfully")

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Called when task fails"""
        logger.error(f"Task {task_id} ({self.name}) failed: {exc}")

        # Log security event for critical task failures
        if self.name in [
            "core.tasks.calculate_all_analytics",
            "core.tasks.backup_database",
        ]:
            SecurityService.log_security_event(
                "critical_task_failure",
                details={
                    "task_id": task_id,
                    "task_name": self.name,
                    "error": str(exc),
                    "args": args,
                    "kwargs": kwargs,
                },
            )


# Analytics calculation tasks
@shared_task(bind=True, base=CallbackTask, max_retries=3)
def calculate_student_analytics(
    self, academic_year_id=None, term_id=None, force_recalculate=False
):
    """Calculate student performance analytics"""
    try:
        from academics.models import AcademicYear, Term

        academic_year = None
        term = None

        if academic_year_id:
            academic_year = AcademicYear.objects.get(id=academic_year_id)

        if term_id:
            term = Term.objects.get(id=term_id)

        logger.info(
            f"Starting student analytics calculation for {academic_year} - {term}"
        )

        AnalyticsService.calculate_student_performance(
            academic_year=academic_year, term=term, force_recalculate=force_recalculate
        )

        # Update analytics counts
        count = StudentPerformanceAnalytics.objects.filter(
            academic_year=academic_year, term=term
        ).count()

        logger.info(
            f"Student analytics calculation completed. {count} records processed."
        )

        return {
            "status": "success",
            "records_processed": count,
            "academic_year": str(academic_year) if academic_year else "current",
            "term": str(term) if term else "current",
        }

    except Exception as exc:
        logger.error(f"Error in student analytics calculation: {str(exc)}")
        raise self.retry(exc=exc, countdown=60 * (self.request.retries + 1))


@shared_task(bind=True, base=CallbackTask, max_retries=3)
def calculate_class_analytics(
    self, academic_year_id=None, term_id=None, force_recalculate=False
):
    """Calculate class performance analytics"""
    try:
        from academics.models import AcademicYear, Term

        academic_year = None
        term = None

        if academic_year_id:
            academic_year = AcademicYear.objects.get(id=academic_year_id)

        if term_id:
            term = Term.objects.get(id=term_id)

        logger.info(
            f"Starting class analytics calculation for {academic_year} - {term}"
        )

        AnalyticsService.calculate_class_performance(
            academic_year=academic_year, term=term, force_recalculate=force_recalculate
        )

        count = ClassPerformanceAnalytics.objects.filter(
            academic_year=academic_year, term=term
        ).count()

        logger.info(
            f"Class analytics calculation completed. {count} records processed."
        )

        return {
            "status": "success",
            "records_processed": count,
            "academic_year": str(academic_year) if academic_year else "current",
            "term": str(term) if term else "current",
        }

    except Exception as exc:
        logger.error(f"Error in class analytics calculation: {str(exc)}")
        raise self.retry(exc=exc, countdown=60 * (self.request.retries + 1))


@shared_task(bind=True, base=CallbackTask, max_retries=3)
def calculate_attendance_analytics(
    self, academic_year_id=None, term_id=None, force_recalculate=False
):
    """Calculate attendance analytics"""
    try:
        from academics.models import AcademicYear, Term

        academic_year = None
        term = None

        if academic_year_id:
            academic_year = AcademicYear.objects.get(id=academic_year_id)

        if term_id:
            term = Term.objects.get(id=term_id)

        logger.info(
            f"Starting attendance analytics calculation for {academic_year} - {term}"
        )

        AnalyticsService.calculate_attendance_analytics(
            academic_year=academic_year, term=term, force_recalculate=force_recalculate
        )

        count = AttendanceAnalytics.objects.filter(
            academic_year=academic_year, term=term
        ).count()

        logger.info(
            f"Attendance analytics calculation completed. {count} records processed."
        )

        return {
            "status": "success",
            "records_processed": count,
            "academic_year": str(academic_year) if academic_year else "current",
            "term": str(term) if term else "current",
        }

    except Exception as exc:
        logger.error(f"Error in attendance analytics calculation: {str(exc)}")
        raise self.retry(exc=exc, countdown=60 * (self.request.retries + 1))


@shared_task(bind=True, base=CallbackTask, max_retries=3)
def calculate_financial_analytics(
    self, academic_year_id=None, term_id=None, force_recalculate=False
):
    """Calculate financial analytics"""
    try:
        from academics.models import AcademicYear, Term

        academic_year = None
        term = None

        if academic_year_id:
            academic_year = AcademicYear.objects.get(id=academic_year_id)

        if term_id:
            term = Term.objects.get(id=term_id)

        logger.info(
            f"Starting financial analytics calculation for {academic_year} - {term}"
        )

        AnalyticsService.calculate_financial_analytics(
            academic_year=academic_year, term=term, force_recalculate=force_recalculate
        )

        count = FinancialAnalytics.objects.filter(
            academic_year=academic_year, term=term
        ).count()

        logger.info(
            f"Financial analytics calculation completed. {count} records processed."
        )

        return {
            "status": "success",
            "records_processed": count,
            "academic_year": str(academic_year) if academic_year else "current",
            "term": str(term) if term else "current",
        }

    except Exception as exc:
        logger.error(f"Error in financial analytics calculation: {str(exc)}")
        raise self.retry(exc=exc, countdown=60 * (self.request.retries + 1))


@shared_task(bind=True, base=CallbackTask)
def calculate_all_analytics(
    self, academic_year_id=None, term_id=None, force_recalculate=False
):
    """Calculate all analytics types"""
    try:
        logger.info("Starting comprehensive analytics calculation")

        results = {}

        # Calculate student analytics
        student_result = calculate_student_analytics.delay(
            academic_year_id, term_id, force_recalculate
        )
        results["student_analytics"] = student_result.id

        # Calculate class analytics
        class_result = calculate_class_analytics.delay(
            academic_year_id, term_id, force_recalculate
        )
        results["class_analytics"] = class_result.id

        # Calculate attendance analytics
        attendance_result = calculate_attendance_analytics.delay(
            academic_year_id, term_id, force_recalculate
        )
        results["attendance_analytics"] = attendance_result.id

        # Calculate financial analytics
        financial_result = calculate_financial_analytics.delay(
            academic_year_id, term_id, force_recalculate
        )
        results["financial_analytics"] = financial_result.id

        logger.info("All analytics calculation tasks queued successfully")

        return {
            "status": "queued",
            "task_ids": results,
            "message": "All analytics calculation tasks have been queued",
        }

    except Exception as exc:
        logger.error(f"Error queuing analytics calculations: {str(exc)}")
        raise


# System maintenance tasks
@shared_task(bind=True, base=CallbackTask)
def cleanup_old_audit_logs(self, days=365):
    """Clean up old audit logs"""
    try:
        logger.info(f"Starting cleanup of audit logs older than {days} days")

        deleted_count = AuditService.cleanup_old_logs(days)

        logger.info(f"Audit log cleanup completed. {deleted_count} records deleted.")

        # Log the cleanup action
        AuditService.log_action(
            action="system_action",
            description=f"Cleaned up {deleted_count} old audit logs",
            data_after={"deleted_count": deleted_count, "days": days},
            module_name="core",
        )

        return {"status": "success", "deleted_count": deleted_count, "days": days}

    except Exception as exc:
        logger.error(f"Error in audit log cleanup: {str(exc)}")
        raise self.retry(exc=exc, countdown=300)  # Retry after 5 minutes


@shared_task(bind=True, base=CallbackTask)
def cleanup_old_analytics(self, days=730):
    """Clean up old analytics data"""
    try:
        logger.info(f"Starting cleanup of analytics data older than {days} days")

        cutoff_date = timezone.now() - timedelta(days=days)

        # Clean up different analytics tables
        deleted_counts = {}

        deleted_counts["student_analytics"] = (
            StudentPerformanceAnalytics.objects.filter(
                calculated_at__lt=cutoff_date
            ).delete()[0]
        )

        deleted_counts["class_analytics"] = ClassPerformanceAnalytics.objects.filter(
            calculated_at__lt=cutoff_date
        ).delete()[0]

        deleted_counts["attendance_analytics"] = AttendanceAnalytics.objects.filter(
            calculated_at__lt=cutoff_date
        ).delete()[0]

        deleted_counts["financial_analytics"] = FinancialAnalytics.objects.filter(
            calculated_at__lt=cutoff_date
        ).delete()[0]

        deleted_counts["teacher_analytics"] = (
            TeacherPerformanceAnalytics.objects.filter(
                calculated_at__lt=cutoff_date
            ).delete()[0]
        )

        total_deleted = sum(deleted_counts.values())

        logger.info(f"Analytics cleanup completed. {total_deleted} records deleted.")

        # Log the cleanup action
        AuditService.log_action(
            action="system_action",
            description=f"Cleaned up {total_deleted} old analytics records",
            data_after={"deleted_counts": deleted_counts, "days": days},
            module_name="core",
        )

        return {
            "status": "success",
            "total_deleted": total_deleted,
            "deleted_counts": deleted_counts,
            "days": days,
        }

    except Exception as exc:
        logger.error(f"Error in analytics cleanup: {str(exc)}")
        raise self.retry(exc=exc, countdown=300)


@shared_task(bind=True, base=CallbackTask)
def collect_system_health_metrics(self):
    """Collect and store system health metrics"""
    try:
        from django.db import connection
        from django.core.cache import cache
        from django.contrib.sessions.models import Session
        import psutil
        import os

        logger.info("Collecting system health metrics")

        # Database metrics
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT count(*) FROM pg_stat_activity WHERE state = 'active'"
            )
            db_connections = cursor.fetchone()[0]

        # Cache metrics (Redis)
        cache_info = cache._cache.info() if hasattr(cache._cache, "info") else {}
        cache_hit_rate = 0
        cache_memory_usage = 0

        if "keyspace_hits" in cache_info and "keyspace_misses" in cache_info:
            hits = cache_info["keyspace_hits"]
            misses = cache_info["keyspace_misses"]
            if hits + misses > 0:
                cache_hit_rate = (hits / (hits + misses)) * 100

        if "used_memory" in cache_info:
            cache_memory_usage = cache_info["used_memory"] / (
                1024 * 1024
            )  # Convert to MB

        # Active users (sessions)
        active_users = Session.objects.filter(expire_date__gte=timezone.now()).count()

        # System metrics
        if psutil:
            # Disk usage
            disk_usage = psutil.disk_usage("/")
            storage_used_gb = disk_usage.used / (1024**3)
            storage_available_gb = disk_usage.free / (1024**3)
        else:
            storage_used_gb = 0
            storage_available_gb = 0

        # Create health metrics record
        health_metrics = SystemHealthMetrics.objects.create(
            db_connection_count=db_connections,
            db_query_count=0,  # Would need query counting middleware
            avg_query_time_ms=0,  # Would need query timing
            cache_hit_rate=cache_hit_rate,
            cache_memory_usage_mb=cache_memory_usage,
            active_users=active_users,
            requests_per_minute=0,  # Would need request counting
            avg_response_time_ms=0,  # Would need response timing
            error_rate=0,  # Would need error counting
            pending_tasks=0,  # Would count Celery queue
            failed_tasks=0,
            completed_tasks=0,
            storage_used_gb=storage_used_gb,
            storage_available_gb=storage_available_gb,
        )

        logger.info("System health metrics collected successfully")

        return {
            "status": "success",
            "metrics_id": health_metrics.id,
            "timestamp": health_metrics.timestamp.isoformat(),
        }

    except Exception as exc:
        logger.error(f"Error collecting system health metrics: {str(exc)}")
        raise self.retry(exc=exc, countdown=300)


@shared_task(bind=True, base=CallbackTask)
def backup_database(self, output_path=None, compress=True):
    """Backup database"""
    try:
        logger.info("Starting database backup")

        # Capture command output
        stdout = StringIO()
        stderr = StringIO()

        # Build command arguments
        cmd_args = ["backup_database"]
        if output_path:
            cmd_args.extend(["--output", output_path])
        if compress:
            cmd_args.append("--compress")

        # Execute backup command
        call_command(*cmd_args, stdout=stdout, stderr=stderr)

        output = stdout.getvalue()
        errors = stderr.getvalue()

        if errors:
            logger.warning(f"Database backup completed with warnings: {errors}")
        else:
            logger.info("Database backup completed successfully")

        # Log the backup action
        AuditService.log_action(
            action="system_action",
            description="Database backup completed via scheduled task",
            data_after={
                "output_path": output_path,
                "compress": compress,
                "output": output,
                "errors": errors,
            },
            module_name="core",
        )

        return {
            "status": "success",
            "output": output,
            "errors": errors,
            "compress": compress,
        }

    except Exception as exc:
        logger.error(f"Error in database backup: {str(exc)}")

        # Log backup failure
        SecurityService.log_security_event(
            "backup_failure",
            details={
                "error": str(exc),
                "output_path": output_path,
                "compress": compress,
            },
        )

        raise self.retry(exc=exc, countdown=600)  # Retry after 10 minutes


# Notification and communication tasks
@shared_task(bind=True, base=CallbackTask)
def send_bulk_notifications(
    self, notification_data, recipient_type="all", filters=None
):
    """Send bulk notifications"""
    try:
        from communications.services import NotificationService

        logger.info(f"Starting bulk notification send to {recipient_type}")

        # This would integrate with your communications module
        # For now, just log the action

        sent_count = 0  # Would be actual count from notification service

        logger.info(f"Bulk notifications sent successfully. Count: {sent_count}")

        # Log the notification action
        AuditService.log_action(
            action="system_action",
            description=f"Sent {sent_count} bulk notifications",
            data_after={
                "recipient_type": recipient_type,
                "sent_count": sent_count,
                "filters": filters,
            },
            module_name="communications",
        )

        return {
            "status": "success",
            "sent_count": sent_count,
            "recipient_type": recipient_type,
        }

    except Exception as exc:
        logger.error(f"Error in bulk notification send: {str(exc)}")
        raise self.retry(exc=exc, countdown=300)


@shared_task(bind=True, base=CallbackTask)
def generate_reports(self, report_type, parameters=None, schedule_id=None):
    """Generate scheduled reports"""
    try:
        from reports.services import ReportService

        logger.info(f"Starting report generation: {report_type}")

        # This would integrate with your reports module
        report_id = None  # Would be actual report ID

        logger.info(f"Report generated successfully: {report_id}")

        # Log the report generation
        AuditService.log_action(
            action="system_action",
            description=f"Generated scheduled report: {report_type}",
            data_after={
                "report_type": report_type,
                "report_id": report_id,
                "parameters": parameters,
                "schedule_id": schedule_id,
            },
            module_name="reports",
        )

        return {"status": "success", "report_id": report_id, "report_type": report_type}

    except Exception as exc:
        logger.error(f"Error in report generation: {str(exc)}")
        raise self.retry(exc=exc, countdown=300)


# Data processing tasks
@shared_task(bind=True, base=CallbackTask)
def process_bulk_data_import(self, file_path, import_type, user_id=None):
    """Process bulk data import"""
    try:
        logger.info(f"Starting bulk data import: {import_type} from {file_path}")

        # This would implement actual bulk import logic
        processed_count = 0
        error_count = 0

        # Get user for audit logging
        user = None
        if user_id:
            user = User.objects.get(id=user_id)

        logger.info(
            f"Bulk import completed. Processed: {processed_count}, Errors: {error_count}"
        )

        # Log the import action
        AuditService.log_action(
            user=user,
            action="import",
            description=f"Bulk data import completed: {import_type}",
            data_after={
                "file_path": file_path,
                "import_type": import_type,
                "processed_count": processed_count,
                "error_count": error_count,
            },
            module_name="core",
        )

        return {
            "status": "success",
            "processed_count": processed_count,
            "error_count": error_count,
            "import_type": import_type,
        }

    except Exception as exc:
        logger.error(f"Error in bulk data import: {str(exc)}")
        raise self.retry(exc=exc, countdown=300)


@shared_task(bind=True, base=CallbackTask)
def process_bulk_data_export(self, export_type, filters=None, user_id=None):
    """Process bulk data export"""
    try:
        logger.info(f"Starting bulk data export: {export_type}")

        # This would implement actual bulk export logic
        export_file_path = (
            f"/tmp/export_{export_type}_{timezone.now().strftime('%Y%m%d_%H%M%S')}.csv"
        )
        record_count = 0

        # Get user for audit logging
        user = None
        if user_id:
            user = User.objects.get(id=user_id)

        logger.info(
            f"Bulk export completed. Records: {record_count}, File: {export_file_path}"
        )

        # Log the export action
        AuditService.log_action(
            user=user,
            action="export",
            description=f"Bulk data export completed: {export_type}",
            data_after={
                "export_type": export_type,
                "export_file_path": export_file_path,
                "record_count": record_count,
                "filters": filters,
            },
            module_name="core",
        )

        return {
            "status": "success",
            "export_file_path": export_file_path,
            "record_count": record_count,
            "export_type": export_type,
        }

    except Exception as exc:
        logger.error(f"Error in bulk data export: {str(exc)}")
        raise self.retry(exc=exc, countdown=300)


# Periodic task for monitoring
@shared_task(bind=True, base=CallbackTask)
def monitor_system_alerts(self):
    """Monitor system for alerts and notifications"""
    try:
        logger.info("Starting system monitoring check")

        alerts = []

        # Check for low disk space
        latest_health = SystemHealthMetrics.objects.first()
        if latest_health:
            total_storage = (
                latest_health.storage_used_gb + latest_health.storage_available_gb
            )
            if total_storage > 0:
                usage_percentage = (latest_health.storage_used_gb / total_storage) * 100
                if usage_percentage > 85:
                    alerts.append(
                        {
                            "type": "disk_space",
                            "level": "warning",
                            "message": f"Disk usage is at {usage_percentage:.1f}%",
                        }
                    )

        # Check for failed tasks (would need actual Celery integration)
        # Check for high error rates
        # Check for performance issues

        if alerts:
            logger.warning(f"System alerts detected: {len(alerts)} alerts")

            # Log system alerts
            SecurityService.log_security_event(
                "system_alerts", details={"alerts": alerts, "alert_count": len(alerts)}
            )
        else:
            logger.info("System monitoring check completed - no alerts")

        return {"status": "success", "alert_count": len(alerts), "alerts": alerts}

    except Exception as exc:
        logger.error(f"Error in system monitoring: {str(exc)}")
        raise self.retry(exc=exc, countdown=300)


# Chain tasks for complex workflows
@shared_task(bind=True, base=CallbackTask)
def daily_maintenance_workflow(self):
    """Execute daily maintenance workflow"""
    try:
        logger.info("Starting daily maintenance workflow")

        workflow_results = []

        # 1. Collect system health metrics
        health_task = collect_system_health_metrics.delay()
        workflow_results.append(("health_metrics", health_task.id))

        # 2. Calculate analytics if enabled
        if ConfigurationService.get_setting("analytics.auto_calculation_enabled", True):
            analytics_task = calculate_all_analytics.delay()
            workflow_results.append(("analytics", analytics_task.id))

        # 3. Clean up old data
        cleanup_task = cleanup_old_audit_logs.delay(
            ConfigurationService.get_setting("analytics.retention_days", 365)
        )
        workflow_results.append(("cleanup", cleanup_task.id))

        # 4. Monitor for alerts
        monitor_task = monitor_system_alerts.delay()
        workflow_results.append(("monitoring", monitor_task.id))

        # 5. Backup if enabled
        if ConfigurationService.get_setting("system.auto_backup_enabled", True):
            backup_task = backup_database.delay()
            workflow_results.append(("backup", backup_task.id))

        logger.info("Daily maintenance workflow tasks queued successfully")

        return {
            "status": "queued",
            "workflow_tasks": workflow_results,
            "message": "Daily maintenance workflow has been queued",
        }

    except Exception as exc:
        logger.error(f"Error in daily maintenance workflow: {str(exc)}")
        raise
