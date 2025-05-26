from django.db import models
from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.db.models import F
from django.utils import timezone

from .models import (
    Payment,
    Invoice,
    InvoiceItem,
    StudentScholarship,
    Scholarship,
    FinancialSummary,
)


@receiver(post_save, sender=Payment)
def update_invoice_on_payment(sender, instance, created, **kwargs):
    """Update invoice status and amounts when payment is created/updated."""

    if created and instance.status == "completed":
        # Update invoice paid amount
        invoice = instance.invoice

        # Recalculate total paid amount from all payments
        total_paid = (
            invoice.payments.filter(status="completed").aggregate(
                total=models.Sum("amount")
            )["total"]
            or 0
        )

        invoice.paid_amount = total_paid

        # Update invoice status
        if invoice.paid_amount >= invoice.net_amount:
            invoice.status = "paid"
        elif invoice.paid_amount > 0:
            invoice.status = "partially_paid"
        elif invoice.is_overdue:
            invoice.status = "overdue"
        else:
            invoice.status = "unpaid"

        invoice.save()


@receiver(post_delete, sender=Payment)
def update_invoice_on_payment_deletion(sender, instance, **kwargs):
    """Update invoice status when payment is deleted."""

    if instance.status == "completed":
        invoice = instance.invoice

        # Recalculate total paid amount
        total_paid = (
            invoice.payments.filter(status="completed").aggregate(
                total=models.Sum("amount")
            )["total"]
            or 0
        )

        invoice.paid_amount = total_paid

        # Update status
        if invoice.paid_amount >= invoice.net_amount:
            invoice.status = "paid"
        elif invoice.paid_amount > 0:
            invoice.status = "partially_paid"
        elif invoice.is_overdue:
            invoice.status = "overdue"
        else:
            invoice.status = "unpaid"

        invoice.save()


@receiver(post_save, sender=InvoiceItem)
def update_invoice_totals_on_item_change(sender, instance, created, **kwargs):
    """Update invoice totals when items are added/modified."""

    invoice = instance.invoice

    # Recalculate totals from all items
    items_aggregate = invoice.items.aggregate(
        total_amount=models.Sum("amount"),
        total_discount=models.Sum("discount_amount"),
        total_net=models.Sum("net_amount"),
    )

    invoice.total_amount = items_aggregate["total_amount"] or 0
    invoice.discount_amount = items_aggregate["total_discount"] or 0
    invoice.net_amount = items_aggregate["total_net"] or 0

    # Update status if needed
    if invoice.paid_amount >= invoice.net_amount and invoice.net_amount > 0:
        invoice.status = "paid"
    elif invoice.paid_amount > 0:
        invoice.status = "partially_paid"

    invoice.save()


@receiver(post_delete, sender=InvoiceItem)
def update_invoice_totals_on_item_deletion(sender, instance, **kwargs):
    """Update invoice totals when items are deleted."""

    invoice = instance.invoice

    # Recalculate totals
    items_aggregate = invoice.items.aggregate(
        total_amount=models.Sum("amount"),
        total_discount=models.Sum("discount_amount"),
        total_net=models.Sum("net_amount"),
    )

    invoice.total_amount = items_aggregate["total_amount"] or 0
    invoice.discount_amount = items_aggregate["total_discount"] or 0
    invoice.net_amount = items_aggregate["total_net"] or 0

    invoice.save()


@receiver(post_save, sender=StudentScholarship)
def update_scholarship_recipient_count(sender, instance, created, **kwargs):
    """Update scholarship recipient count when assignments change."""

    scholarship = instance.scholarship

    # Count current approved recipients
    approved_count = scholarship.studentscholarship_set.filter(
        status="approved"
    ).count()

    scholarship.current_recipients = approved_count
    scholarship.save()


@receiver(post_delete, sender=StudentScholarship)
def update_scholarship_count_on_deletion(sender, instance, **kwargs):
    """Update scholarship count when assignment is deleted."""

    scholarship = instance.scholarship

    # Count remaining approved recipients
    approved_count = scholarship.studentscholarship_set.filter(
        status="approved"
    ).count()

    scholarship.current_recipients = approved_count
    scholarship.save()


@receiver(pre_save, sender=StudentScholarship)
def track_scholarship_status_changes(sender, instance, **kwargs):
    """Track changes in scholarship status."""

    if instance.pk:  # Existing instance
        try:
            old_instance = StudentScholarship.objects.get(pk=instance.pk)

            # If status changed from approved to something else
            if old_instance.status == "approved" and instance.status != "approved":
                # Decrease count (will be handled by post_save signal)
                pass

            # If status changed to approved from something else
            elif old_instance.status != "approved" and instance.status == "approved":
                # Check if scholarship has available slots
                scholarship = instance.scholarship
                if not scholarship.has_available_slots:
                    from django.core.exceptions import ValidationError

                    raise ValidationError("No available slots for this scholarship")

        except StudentScholarship.DoesNotExist:
            pass


@receiver(post_save, sender=Invoice)
def create_financial_summary_entry(sender, instance, created, **kwargs):
    """Update financial summary when invoices are created/updated."""

    if created:
        # Trigger financial summary update for the period
        from .tasks import update_financial_summary_task

        # Schedule task to update summary (using Celery if available)
        try:
            update_financial_summary_task.delay(
                instance.academic_year.id, instance.term.id if instance.term else None
            )
        except Exception:
            # If Celery is not available, update directly
            from .services.analytics_service import FinancialAnalyticsService

            FinancialAnalyticsService.update_financial_analytics(
                instance.academic_year, instance.term
            )


@receiver(post_save, sender=Payment)
def trigger_analytics_update(sender, instance, created, **kwargs):
    """Trigger analytics update when payments are made."""

    if created and instance.status == "completed":
        # Schedule analytics update
        from .tasks import update_payment_analytics_task

        try:
            update_payment_analytics_task.delay(
                instance.invoice.academic_year.id,
                instance.invoice.term.id if instance.invoice.term else None,
            )
        except Exception:
            # Direct update if Celery not available
            pass


# Custom signal for fee structure changes
from django.dispatch import Signal

fee_structure_changed = Signal()
scholarship_assigned = Signal()
payment_received = Signal()


@receiver(fee_structure_changed)
def handle_fee_structure_change(sender, **kwargs):
    """Handle fee structure changes."""

    academic_year = kwargs.get("academic_year")
    term = kwargs.get("term")

    if academic_year and term:
        # Trigger recalculation of existing invoices if needed
        from .tasks import recalculate_affected_invoices_task

        try:
            recalculate_affected_invoices_task.delay(academic_year.id, term.id)
        except Exception:
            pass


@receiver(scholarship_assigned)
def handle_scholarship_assignment(sender, **kwargs):
    """Handle scholarship assignment notifications."""

    student_scholarship = kwargs.get("student_scholarship")

    if student_scholarship:
        # Send notification to student/parent
        from communications.tasks import send_scholarship_notification_task

        try:
            send_scholarship_notification_task.delay(student_scholarship.id)
        except Exception:
            pass


@receiver(payment_received)
def handle_payment_received(sender, **kwargs):
    """Handle payment received notifications and updates."""

    payment = kwargs.get("payment")

    if payment:
        # Send receipt notification
        from communications.tasks import send_payment_receipt_task

        try:
            send_payment_receipt_task.delay(payment.id)
        except Exception:
            pass

        # Update any related analytics
        from .tasks import update_collection_metrics_task

        try:
            update_collection_metrics_task.delay(
                payment.invoice.academic_year.id,
                payment.invoice.term.id if payment.invoice.term else None,
            )
        except Exception:
            pass


# Helper function to manually trigger signals
def trigger_fee_structure_change(academic_year, term, fee_structure=None):
    """Manually trigger fee structure change signal."""
    fee_structure_changed.send(
        sender=None, academic_year=academic_year, term=term, fee_structure=fee_structure
    )


def trigger_scholarship_assignment(student_scholarship):
    """Manually trigger scholarship assignment signal."""
    scholarship_assigned.send(sender=None, student_scholarship=student_scholarship)


def trigger_payment_received(payment):
    """Manually trigger payment received signal."""
    payment_received.send(sender=None, payment=payment)
