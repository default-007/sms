from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import Invoice, InvoiceItem, Payment
from src.communications.models import Notification


@receiver(post_save, sender=Invoice)
def update_invoice_totals(sender, instance, created, **kwargs):
    """Update invoice totals when saved."""
    if not created:  # Skip for new invoices as items aren't created yet
        # Recalculate totals based on items
        total_amount = sum(item.amount for item in instance.items.all())
        net_amount = sum(item.net_amount for item in instance.items.all())
        discount_amount = total_amount - net_amount

        # Update only if values have changed
        if (
            instance.total_amount != total_amount
            or instance.net_amount != net_amount
            or instance.discount_amount != discount_amount
        ):

            Invoice.objects.filter(id=instance.id).update(
                total_amount=total_amount,
                discount_amount=discount_amount,
                net_amount=net_amount,
            )


@receiver(post_save, sender=Invoice)
def notify_invoice_creation(sender, instance, created, **kwargs):
    """Notify student when an invoice is created."""
    if created and hasattr(instance.student, "user"):
        # Create notification for student
        Notification.objects.create(
            user=instance.student.user,
            title="New Invoice Generated",
            content=f"A new invoice ({instance.invoice_number}) has been generated for {instance.total_amount}.",
            notification_type="Finance",
            reference_id=instance.id,
            priority="Medium",
        )

        # Also notify parents
        for relation in instance.student.student_parent_relations.filter(
            is_primary_contact=True
        ):
            if hasattr(relation.parent, "user"):
                Notification.objects.create(
                    user=relation.parent.user,
                    title="New Invoice Generated",
                    content=f"A new invoice ({instance.invoice_number}) has been generated for your child {instance.student.get_full_name()}.",
                    notification_type="Finance",
                    reference_id=instance.id,
                    priority="Medium",
                )


@receiver(post_save, sender=InvoiceItem)
def update_invoice_on_item_change(sender, instance, created, **kwargs):
    """Update invoice when an item is added, updated or deleted."""
    # Trigger invoice update
    instance.invoice.save()


@receiver(post_delete, sender=InvoiceItem)
def update_invoice_on_item_delete(sender, instance, **kwargs):
    """Update invoice when an item is deleted."""
    # Check if invoice still exists before updating
    try:
        instance.invoice.save()
    except Invoice.DoesNotExist:
        pass


@receiver(post_save, sender=Payment)
def notify_payment_receipt(sender, instance, created, **kwargs):
    """Notify student when a payment is recorded."""
    if created and hasattr(instance.invoice.student, "user"):
        # Create notification for student
        Notification.objects.create(
            user=instance.invoice.student.user,
            title="Payment Received",
            content=f"Your payment of {instance.amount} has been received. Receipt: {instance.receipt_number}",
            notification_type="Finance",
            reference_id=instance.id,
            priority="Medium",
        )

        # Also notify parents
        for relation in instance.invoice.student.student_parent_relations.filter(
            is_primary_contact=True
        ):
            if hasattr(relation.parent, "user"):
                Notification.objects.create(
                    user=relation.parent.user,
                    title="Payment Received",
                    content=f"Payment of {instance.amount} for {instance.invoice.student.get_full_name()} has been received.",
                    notification_type="Finance",
                    reference_id=instance.id,
                    priority="Medium",
                )
