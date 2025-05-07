from django.db import models
from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from src.courses.models import Grade, AcademicYear


class FeeCategory(models.Model):
    """Model for different fee categories like tuition, transport, etc."""

    name = models.CharField(_("Name"), max_length=100)
    description = models.TextField(_("Description"), blank=True)
    is_recurring = models.BooleanField(_("Is Recurring"), default=False)
    FREQUENCY_CHOICES = (
        ("monthly", _("Monthly")),
        ("quarterly", _("Quarterly")),
        ("annually", _("Annually")),
    )
    frequency = models.CharField(
        _("Frequency"), max_length=20, choices=FREQUENCY_CHOICES, blank=True, null=True
    )
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)

    class Meta:
        verbose_name = _("Fee Category")
        verbose_name_plural = _("Fee Categories")
        ordering = ["name"]

    def __str__(self):
        return self.name


class FeeStructure(models.Model):
    """Model for fee structures by grade and academic year."""

    academic_year = models.ForeignKey(
        AcademicYear,
        on_delete=models.CASCADE,
        related_name="fee_structures",
        verbose_name=_("Academic Year"),
    )
    grade = models.ForeignKey(
        Grade,
        on_delete=models.CASCADE,
        related_name="fee_structures",
        verbose_name=_("Grade"),
    )
    fee_category = models.ForeignKey(
        FeeCategory,
        on_delete=models.CASCADE,
        related_name="fee_structures",
        verbose_name=_("Fee Category"),
    )
    amount = models.DecimalField(_("Amount"), max_digits=10, decimal_places=2)
    due_day_of_month = models.PositiveSmallIntegerField(
        _("Due Day of Month"), default=5, help_text=_("Day of month when fee is due")
    )
    late_fee_percentage = models.DecimalField(
        _("Late Fee Percentage"),
        max_digits=5,
        decimal_places=2,
        default=0,
        help_text=_("Percentage of fee charged as late fee"),
    )
    grace_period_days = models.PositiveSmallIntegerField(
        _("Grace Period (Days)"),
        default=0,
        help_text=_("Number of days after due date before late fee applies"),
    )
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)

    class Meta:
        verbose_name = _("Fee Structure")
        verbose_name_plural = _("Fee Structures")
        unique_together = ["academic_year", "grade", "fee_category"]
        ordering = ["academic_year", "grade", "fee_category"]

    def __str__(self):
        return (
            f"{self.fee_category.name} - {self.grade.name} ({self.academic_year.name})"
        )


class Scholarship(models.Model):
    """Model for different types of scholarships."""

    name = models.CharField(_("Name"), max_length=100)
    description = models.TextField(_("Description"), blank=True)
    DISCOUNT_TYPE_CHOICES = (
        ("percentage", _("Percentage")),
        ("fixed", _("Fixed Amount")),
    )
    discount_type = models.CharField(
        _("Discount Type"), max_length=20, choices=DISCOUNT_TYPE_CHOICES
    )
    discount_value = models.DecimalField(
        _("Discount Value"), max_digits=10, decimal_places=2
    )
    CRITERIA_CHOICES = (
        ("merit", _("Merit Based")),
        ("need", _("Need Based")),
        ("sports", _("Sports Quota")),
        ("other", _("Other")),
    )
    criteria = models.CharField(_("Criteria"), max_length=20, choices=CRITERIA_CHOICES)
    academic_year = models.ForeignKey(
        AcademicYear,
        on_delete=models.CASCADE,
        related_name="scholarships",
        verbose_name=_("Academic Year"),
    )
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)

    class Meta:
        verbose_name = _("Scholarship")
        verbose_name_plural = _("Scholarships")
        ordering = ["name"]

    def __str__(self):
        return self.name


class StudentScholarship(models.Model):
    """Model to track scholarships granted to students."""

    student = models.ForeignKey(
        "students.Student",
        on_delete=models.CASCADE,
        related_name="scholarships",
        verbose_name=_("Student"),
    )
    scholarship = models.ForeignKey(
        Scholarship,
        on_delete=models.CASCADE,
        related_name="student_scholarships",
        verbose_name=_("Scholarship"),
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="approved_scholarships",
        verbose_name=_("Approved By"),
    )
    approval_date = models.DateField(_("Approval Date"), default=timezone.now)
    start_date = models.DateField(_("Start Date"))
    end_date = models.DateField(_("End Date"), null=True, blank=True)
    remarks = models.TextField(_("Remarks"), blank=True)
    STATUS_CHOICES = (
        ("approved", _("Approved")),
        ("suspended", _("Suspended")),
        ("terminated", _("Terminated")),
    )
    status = models.CharField(
        _("Status"), max_length=20, choices=STATUS_CHOICES, default="approved"
    )
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)

    class Meta:
        verbose_name = _("Student Scholarship")
        verbose_name_plural = _("Student Scholarships")
        ordering = ["-approval_date"]

    def __str__(self):
        return f"{self.student} - {self.scholarship}"


class Invoice(models.Model):
    """Model for student fee invoices."""

    student = models.ForeignKey(
        "students.Student",
        on_delete=models.CASCADE,
        related_name="invoices",
        verbose_name=_("Student"),
    )
    academic_year = models.ForeignKey(
        AcademicYear,
        on_delete=models.CASCADE,
        related_name="invoices",
        verbose_name=_("Academic Year"),
    )
    invoice_number = models.CharField(_("Invoice Number"), max_length=20, unique=True)
    issue_date = models.DateField(_("Issue Date"), default=timezone.now)
    due_date = models.DateField(_("Due Date"))
    total_amount = models.DecimalField(
        _("Total Amount"), max_digits=10, decimal_places=2
    )
    discount_amount = models.DecimalField(
        _("Discount Amount"), max_digits=10, decimal_places=2, default=0
    )
    net_amount = models.DecimalField(_("Net Amount"), max_digits=10, decimal_places=2)
    STATUS_CHOICES = (
        ("unpaid", _("Unpaid")),
        ("partially_paid", _("Partially Paid")),
        ("paid", _("Paid")),
        ("overdue", _("Overdue")),
        ("cancelled", _("Cancelled")),
    )
    status = models.CharField(
        _("Status"), max_length=20, choices=STATUS_CHOICES, default="unpaid"
    )
    remarks = models.TextField(_("Remarks"), blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_invoices",
        verbose_name=_("Created By"),
    )
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)

    class Meta:
        verbose_name = _("Invoice")
        verbose_name_plural = _("Invoices")
        ordering = ["-issue_date"]

    def __str__(self):
        return f"INV-{self.invoice_number} - {self.student}"

    def save(self, *args, **kwargs):
        # Calculate net amount
        self.net_amount = self.total_amount - self.discount_amount

        # Auto-generate invoice number if not provided
        if not self.invoice_number:
            from src.core.utils import generate_unique_id

            self.invoice_number = generate_unique_id("INV")

        super().save(*args, **kwargs)

    def get_paid_amount(self):
        """Get total paid amount for this invoice."""
        return sum(payment.amount for payment in self.payments.all())

    def get_due_amount(self):
        """Get remaining amount to be paid."""
        return self.net_amount - self.get_paid_amount()

    def update_status(self):
        """Update invoice status based on payments."""
        paid_amount = self.get_paid_amount()

        if self.status == "cancelled":
            return

        if paid_amount >= self.net_amount:
            self.status = "paid"
        elif paid_amount > 0:
            self.status = "partially_paid"
        elif timezone.now().date() > self.due_date:
            self.status = "overdue"
        else:
            self.status = "unpaid"

        self.save(update_fields=["status"])


class InvoiceItem(models.Model):
    """Model for individual items in an invoice."""

    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.CASCADE,
        related_name="items",
        verbose_name=_("Invoice"),
    )
    fee_structure = models.ForeignKey(
        FeeStructure,
        on_delete=models.SET_NULL,
        null=True,
        related_name="invoice_items",
        verbose_name=_("Fee Structure"),
    )
    description = models.CharField(_("Description"), max_length=200)
    amount = models.DecimalField(_("Amount"), max_digits=10, decimal_places=2)
    discount_amount = models.DecimalField(
        _("Discount Amount"), max_digits=10, decimal_places=2, default=0
    )
    net_amount = models.DecimalField(_("Net Amount"), max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)

    class Meta:
        verbose_name = _("Invoice Item")
        verbose_name_plural = _("Invoice Items")

    def __str__(self):
        return f"{self.description} - {self.invoice.invoice_number}"

    def save(self, *args, **kwargs):
        # Calculate net amount
        self.net_amount = self.amount - self.discount_amount
        super().save(*args, **kwargs)


class Payment(models.Model):
    """Model to track fee payments."""

    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.CASCADE,
        related_name="payments",
        verbose_name=_("Invoice"),
    )
    payment_date = models.DateField(_("Payment Date"), default=timezone.now)
    amount = models.DecimalField(_("Amount"), max_digits=10, decimal_places=2)
    PAYMENT_METHOD_CHOICES = (
        ("cash", _("Cash")),
        ("bank_transfer", _("Bank Transfer")),
        ("credit_card", _("Credit Card")),
        ("debit_card", _("Debit Card")),
        ("cheque", _("Cheque")),
        ("online", _("Online Payment")),
    )
    payment_method = models.CharField(
        _("Payment Method"), max_length=20, choices=PAYMENT_METHOD_CHOICES
    )
    transaction_id = models.CharField(_("Transaction ID"), max_length=100, blank=True)
    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="received_payments",
        verbose_name=_("Received By"),
    )
    receipt_number = models.CharField(_("Receipt Number"), max_length=20, unique=True)
    remarks = models.TextField(_("Remarks"), blank=True)
    STATUS_CHOICES = (
        ("completed", _("Completed")),
        ("pending", _("Pending")),
        ("failed", _("Failed")),
    )
    status = models.CharField(
        _("Status"), max_length=20, choices=STATUS_CHOICES, default="completed"
    )
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)

    class Meta:
        verbose_name = _("Payment")
        verbose_name_plural = _("Payments")
        ordering = ["-payment_date"]

    def __str__(self):
        return f"Receipt-{self.receipt_number} - {self.invoice.student}"

    def save(self, *args, **kwargs):
        # Auto-generate receipt number if not provided
        if not self.receipt_number:
            from src.core.utils import generate_unique_id

            self.receipt_number = generate_unique_id("RCPT")

        super().save(*args, **kwargs)

        # Update invoice status
        self.invoice.update_status()


class Expense(models.Model):
    """Model to track school expenses."""

    EXPENSE_CATEGORY_CHOICES = (
        ("salary", _("Salary")),
        ("maintenance", _("Maintenance")),
        ("utilities", _("Utilities")),
        ("supplies", _("Supplies")),
        ("transport", _("Transport")),
        ("events", _("Events")),
        ("miscellaneous", _("Miscellaneous")),
    )
    expense_category = models.CharField(
        _("Expense Category"), max_length=20, choices=EXPENSE_CATEGORY_CHOICES
    )
    amount = models.DecimalField(_("Amount"), max_digits=10, decimal_places=2)
    expense_date = models.DateField(_("Expense Date"), default=timezone.now)
    description = models.TextField(_("Description"))
    PAYMENT_METHOD_CHOICES = (
        ("cash", _("Cash")),
        ("bank_transfer", _("Bank Transfer")),
        ("credit_card", _("Credit Card")),
        ("cheque", _("Cheque")),
    )
    payment_method = models.CharField(
        _("Payment Method"), max_length=20, choices=PAYMENT_METHOD_CHOICES
    )
    paid_to = models.CharField(_("Paid To"), max_length=100)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="approved_expenses",
        verbose_name=_("Approved By"),
    )
    receipt_attachment = models.FileField(
        _("Receipt Attachment"), upload_to="expense_receipts/", null=True, blank=True
    )
    remarks = models.TextField(_("Remarks"), blank=True)
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)

    class Meta:
        verbose_name = _("Expense")
        verbose_name_plural = _("Expenses")
        ordering = ["-expense_date"]

    def __str__(self):
        return f"{self.expense_category} - {self.amount} ({self.expense_date})"
