from datetime import datetime, timedelta
from decimal import Decimal

from celery import shared_task
from django.db import models, transaction
from django.utils import timezone

from .models import (
    FeeStructure,
    FinancialAnalytics,
    FinancialSummary,
    Invoice,
    Payment,
    StudentScholarship,
)
from .services.analytics_service import FinancialAnalyticsService
from .services.invoice_service import InvoiceService
from .services.payment_service import PaymentService
from .services.scholarship_service import ScholarshipService


@shared_task(bind=True, max_retries=3)
def update_financial_summary_task(self, academic_year_id, term_id=None):
    """Update financial summary for a specific period."""

    try:
        from academics.models import AcademicYear, Term

        academic_year = AcademicYear.objects.get(id=academic_year_id)
        term = Term.objects.get(id=term_id) if term_id else None

        # Calculate summary data
        invoices = Invoice.objects.filter(academic_year=academic_year)
        if term:
            invoices = invoices.filter(term=term)

        payments = Payment.objects.filter(
            invoice__academic_year=academic_year, status="completed"
        )
        if term:
            payments = payments.filter(invoice__term=term)

        # Calculate totals
        total_fees_due = invoices.aggregate(total=models.Sum("net_amount"))[
            "total"
        ] or Decimal("0.00")

        total_fees_collected = payments.aggregate(total=models.Sum("amount"))[
            "total"
        ] or Decimal("0.00")

        total_outstanding = total_fees_due - total_fees_collected

        # Calculate scholarships given
        scholarships_given = invoices.aggregate(total=models.Sum("discount_amount"))[
            "total"
        ] or Decimal("0.00")

        # Update or create summary
        current_date = timezone.now().date()

        summary, created = FinancialSummary.objects.update_or_create(
            academic_year=academic_year,
            term=term,
            month=current_date.month,
            year=current_date.year,
            defaults={
                "total_fees_due": total_fees_due,
                "total_fees_collected": total_fees_collected,
                "total_outstanding": total_outstanding,
                "total_scholarships_given": scholarships_given,
                "net_income": total_fees_collected,  # Simplified calculation
            },
        )

        return {"success": True, "summary_id": summary.id, "created": created}

    except Exception as exc:
        # Retry the task
        self.retry(countdown=60, exc=exc)


@shared_task(bind=True)
def update_payment_analytics_task(self, academic_year_id, term_id=None):
    """Update payment analytics for a specific period."""

    try:
        from academics.models import AcademicYear, Term

        academic_year = AcademicYear.objects.get(id=academic_year_id)
        term = Term.objects.get(id=term_id) if term_id else None

        # Update financial analytics
        FinancialAnalyticsService.update_financial_analytics(academic_year, term)

        return {"success": True}

    except Exception as exc:
        return {"success": False, "error": str(exc)}


@shared_task(bind=True)
def generate_bulk_invoices_task(
    self, student_ids, academic_year_id, term_id, created_by_id=None
):
    """Generate invoices for multiple students in background."""

    try:
        from academics.models import AcademicYear, Term
        from accounts.models import User
        from students.models import Student

        students = Student.objects.filter(id__in=student_ids)
        academic_year = AcademicYear.objects.get(id=academic_year_id)
        term = Term.objects.get(id=term_id)
        created_by = User.objects.get(id=created_by_id) if created_by_id else None

        results = InvoiceService.bulk_generate_invoices(
            list(students), academic_year, term, created_by
        )

        return {
            "success": True,
            "created_count": len(results["created"]),
            "skipped_count": len(results["skipped"]),
            "error_count": len(results["errors"]),
        }

    except Exception as exc:
        return {"success": False, "error": str(exc)}


@shared_task(bind=True)
def send_payment_reminders_task(self, days_overdue=7, limit=100):
    """Send payment reminders for overdue invoices."""

    try:
        overdue_invoices = InvoiceService.get_overdue_invoices(days_overdue)[:limit]

        sent_count = 0
        failed_count = 0

        for invoice in overdue_invoices:
            try:
                InvoiceService.send_payment_reminder(invoice)
                sent_count += 1
            except Exception:
                failed_count += 1

        return {"success": True, "sent_count": sent_count, "failed_count": failed_count}

    except Exception as exc:
        return {"success": False, "error": str(exc)}


@shared_task(bind=True)
def update_collection_metrics_task(self, academic_year_id, term_id=None):
    """Update collection metrics for dashboard."""

    try:
        from academics.models import AcademicYear, Term

        academic_year = AcademicYear.objects.get(id=academic_year_id)
        term = Term.objects.get(id=term_id) if term_id else None

        # Calculate comprehensive metrics
        metrics = FinancialAnalyticsService.calculate_collection_metrics(
            academic_year, term
        )

        # Store in cache for quick dashboard access
        from django.core.cache import cache

        cache_key = f"collection_metrics_{academic_year_id}_{term_id or 'all'}"
        cache.set(cache_key, metrics, timeout=3600)  # Cache for 1 hour

        return {"success": True, "cache_key": cache_key}

    except Exception as exc:
        return {"success": False, "error": str(exc)}


@shared_task(bind=True)
def calculate_late_fees_task(self):
    """Calculate and apply late fees for overdue invoices."""

    try:
        today = timezone.now().date()

        # Get overdue invoices
        overdue_invoices = Invoice.objects.filter(
            due_date__lt=today, status__in=["unpaid", "partially_paid"]
        ).select_related("student")

        late_fees_applied = 0
        total_late_fees = Decimal("0.00")

        for invoice in overdue_invoices:
            try:
                with transaction.atomic():
                    late_fee = InvoiceService.calculate_late_fees(invoice)

                    if late_fee > 0:
                        # Create special fee for late charges
                        from .models import FeeCategory, SpecialFee

                        late_fee_category, _ = FeeCategory.objects.get_or_create(
                            name="Late Fee",
                            defaults={
                                "description": "Late payment charges",
                                "is_mandatory": True,
                                "frequency": "one_time",
                            },
                        )

                        SpecialFee.objects.create(
                            name=f"Late Fee - Invoice {invoice.invoice_number}",
                            fee_category=late_fee_category,
                            amount=late_fee,
                            fee_type="student_specific",
                            student=invoice.student,
                            term=invoice.term,
                            due_date=today,
                            reason=f"Late payment charges for invoice {invoice.invoice_number}",
                        )

                        late_fees_applied += 1
                        total_late_fees += late_fee

            except Exception:
                continue

        return {
            "success": True,
            "late_fees_applied": late_fees_applied,
            "total_late_fees": float(total_late_fees),
        }

    except Exception as exc:
        return {"success": False, "error": str(exc)}


@shared_task(bind=True)
def auto_assign_sibling_discounts_task(self, academic_year_id):
    """Automatically assign sibling discounts."""

    try:
        from academics.models import AcademicYear

        academic_year = AcademicYear.objects.get(id=academic_year_id)

        results = ScholarshipService.auto_assign_sibling_discount(academic_year)

        return {
            "success": True,
            "families_processed": results["families_processed"],
            "students_assigned": results["students_assigned"],
        }

    except Exception as exc:
        return {"success": False, "error": str(exc)}


@shared_task(bind=True)
def generate_daily_financial_report_task(self, date_str=None):
    """Generate daily financial report."""

    try:
        if date_str:
            report_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        else:
            report_date = timezone.now().date()

        # Calculate daily metrics
        daily_payments = Payment.objects.filter(
            payment_date__date=report_date, status="completed"
        )

        daily_total = daily_payments.aggregate(total=models.Sum("amount"))[
            "total"
        ] or Decimal("0.00")

        payment_count = daily_payments.count()

        # Payment method breakdown
        method_breakdown = daily_payments.values("payment_method").annotate(
            count=models.Count("id"), total=models.Sum("amount")
        )

        # Generate report data
        report_data = {
            "date": report_date.isoformat(),
            "total_collections": float(daily_total),
            "payment_count": payment_count,
            "method_breakdown": list(method_breakdown),
            "generated_at": timezone.now().isoformat(),
        }

        # Store report in cache and/or database
        from django.core.cache import cache

        cache_key = f"daily_report_{report_date.isoformat()}"
        cache.set(cache_key, report_data, timeout=86400)  # Cache for 24 hours

        return {"success": True, "report_data": report_data}

    except Exception as exc:
        return {"success": False, "error": str(exc)}


@shared_task(bind=True)
def recalculate_affected_invoices_task(self, academic_year_id, term_id):
    """Recalculate invoices affected by fee structure changes."""

    try:
        from academics.models import AcademicYear, Term

        academic_year = AcademicYear.objects.get(id=academic_year_id)
        term = Term.objects.get(id=term_id)

        # Get invoices that might be affected
        affected_invoices = Invoice.objects.filter(
            academic_year=academic_year,
            term=term,
            status__in=["unpaid", "partially_paid"],
        )

        recalculated_count = 0

        for invoice in affected_invoices:
            try:
                with transaction.atomic():
                    # Recalculate fees for this student
                    from .services.fee_service import FeeService

                    fee_breakdown = FeeService.calculate_student_fees(
                        invoice.student, academic_year, term
                    )

                    # Update invoice if amounts changed
                    if (
                        invoice.total_amount != fee_breakdown["total_amount"]
                        or invoice.discount_amount != fee_breakdown["discount_amount"]
                    ):

                        invoice.total_amount = fee_breakdown["total_amount"]
                        invoice.discount_amount = fee_breakdown["discount_amount"]
                        invoice.net_amount = fee_breakdown["net_amount"]
                        invoice.save()

                        # Update invoice items if needed
                        # (This is a simplified approach - in practice, you might want
                        # more sophisticated handling of existing items)

                        recalculated_count += 1

            except Exception:
                continue

        return {"success": True, "recalculated_count": recalculated_count}

    except Exception as exc:
        return {"success": False, "error": str(exc)}


@shared_task(bind=True)
def cleanup_old_analytics_task(self, days_to_keep=90):
    """Clean up old analytics data."""

    try:
        cutoff_date = timezone.now() - timedelta(days=days_to_keep)

        # Clean up old financial analytics
        deleted_analytics = FinancialAnalytics.objects.filter(
            calculated_at__lt=cutoff_date
        ).delete()

        # Clean up old financial summaries (keep monthly summaries)
        deleted_summaries = FinancialSummary.objects.filter(
            generated_at__lt=cutoff_date,
            term__isnull=False,  # Only delete term-specific summaries
        ).delete()

        return {
            "success": True,
            "deleted_analytics": deleted_analytics[0],
            "deleted_summaries": deleted_summaries[0],
        }

    except Exception as exc:
        return {"success": False, "error": str(exc)}


# Periodic tasks setup (add to CELERY_BEAT_SCHEDULE in settings)
PERIODIC_TASKS = {
    "daily-financial-report": {
        "task": "finance.tasks.generate_daily_financial_report_task",
        "schedule": 60.0 * 60.0 * 24.0,  # Daily at midnight
    },
    "weekly-payment-reminders": {
        "task": "finance.tasks.send_payment_reminders_task",
        "schedule": 60.0 * 60.0 * 24.0 * 7.0,  # Weekly
        "kwargs": {"days_overdue": 7, "limit": 500},
    },
    "monthly-late-fees": {
        "task": "finance.tasks.calculate_late_fees_task",
        "schedule": 60.0 * 60.0 * 24.0 * 30.0,  # Monthly
    },
    "quarterly-analytics-cleanup": {
        "task": "finance.tasks.cleanup_old_analytics_task",
        "schedule": 60.0 * 60.0 * 24.0 * 90.0,  # Quarterly
        "kwargs": {"days_to_keep": 180},
    },
}
