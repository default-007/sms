from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from src.courses.models import AcademicYear, Grade


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


import uuid
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

User = get_user_model()


class FeeCategory(models.Model):
    """Categories for different types of fees."""

    FREQUENCY_CHOICES = [
        ("monthly", "Monthly"),
        ("termly", "Termly"),
        ("annually", "Annually"),
        ("one_time", "One Time"),
    ]

    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    is_recurring = models.BooleanField(default=True)
    frequency = models.CharField(
        max_length=20, choices=FREQUENCY_CHOICES, default="termly"
    )
    is_mandatory = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Fee Categories"
        ordering = ["name"]

    def __str__(self):
        return self.name


class FeeStructure(models.Model):
    """Base fee structure for sections, grades, and classes."""

    academic_year = models.ForeignKey(
        "academics.AcademicYear", on_delete=models.CASCADE
    )
    term = models.ForeignKey("academics.Term", on_delete=models.CASCADE)
    section = models.ForeignKey(
        "academics.Section", on_delete=models.CASCADE, null=True, blank=True
    )
    grade = models.ForeignKey(
        "academics.Grade", on_delete=models.CASCADE, null=True, blank=True
    )
    fee_category = models.ForeignKey(FeeCategory, on_delete=models.CASCADE)

    amount = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(0)]
    )
    due_date = models.DateField()
    late_fee_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    grace_period_days = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    class Meta:
        unique_together = [
            ["academic_year", "term", "section", "grade", "fee_category"]
        ]
        ordering = ["academic_year", "term", "fee_category"]

    def __str__(self):
        level = self.grade or self.section
        return f"{self.fee_category.name} - {level} - {self.term}"

    @property
    def applicable_level(self):
        """Return the most specific level this fee applies to."""
        return self.grade or self.section


class SpecialFee(models.Model):
    """Special fees that can be applied to specific classes or students."""

    FEE_TYPE_CHOICES = [
        ("class_based", "Class-based"),
        ("student_specific", "Student-specific"),
    ]

    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    fee_category = models.ForeignKey(FeeCategory, on_delete=models.CASCADE)
    amount = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(0)]
    )
    fee_type = models.CharField(max_length=20, choices=FEE_TYPE_CHOICES)

    # Optional foreign keys based on fee_type
    class_obj = models.ForeignKey(
        "academics.Class", on_delete=models.CASCADE, null=True, blank=True
    )
    student = models.ForeignKey(
        "students.Student", on_delete=models.CASCADE, null=True, blank=True
    )
    term = models.ForeignKey("academics.Term", on_delete=models.CASCADE)

    due_date = models.DateField()
    reason = models.TextField()
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        target = self.class_obj or self.student
        return f"{self.name} - {target} - {self.term}"

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.fee_type == "class_based" and not self.class_obj:
            raise ValidationError("Class is required for class-based fees")
        if self.fee_type == "student_specific" and not self.student:
            raise ValidationError("Student is required for student-specific fees")


class Scholarship(models.Model):
    """Scholarship and discount schemes."""

    DISCOUNT_TYPE_CHOICES = [
        ("percentage", "Percentage"),
        ("fixed_amount", "Fixed Amount"),
    ]

    CRITERIA_CHOICES = [
        ("merit", "Merit-based"),
        ("need", "Need-based"),
        ("sports", "Sports Excellence"),
        ("arts", "Arts Excellence"),
        ("sibling", "Sibling Discount"),
        ("staff", "Staff Discount"),
        ("other", "Other"),
    ]

    name = models.CharField(max_length=100)
    description = models.TextField()
    discount_type = models.CharField(max_length=20, choices=DISCOUNT_TYPE_CHOICES)
    discount_value = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(0)]
    )
    criteria = models.CharField(max_length=20, choices=CRITERIA_CHOICES)

    academic_year = models.ForeignKey(
        "academics.AcademicYear", on_delete=models.CASCADE
    )
    applicable_terms = models.JSONField(default=list)  # List of term IDs
    applicable_categories = models.ManyToManyField(FeeCategory, blank=True)

    max_recipients = models.PositiveIntegerField(null=True, blank=True)
    current_recipients = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.academic_year})"

    @property
    def is_percentage_discount(self):
        return self.discount_type == "percentage"

    @property
    def has_available_slots(self):
        if self.max_recipients is None:
            return True
        return self.current_recipients < self.max_recipients


class StudentScholarship(models.Model):
    """Scholarship assignments to students."""

    STATUS_CHOICES = [
        ("approved", "Approved"),
        ("suspended", "Suspended"),
        ("terminated", "Terminated"),
        ("pending", "Pending"),
    ]

    student = models.ForeignKey("students.Student", on_delete=models.CASCADE)
    scholarship = models.ForeignKey(Scholarship, on_delete=models.CASCADE)
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    approval_date = models.DateTimeField(auto_now_add=True)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    remarks = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ["student", "scholarship"]
        ordering = ["-approval_date"]

    def __str__(self):
        return f"{self.student} - {self.scholarship.name}"


class Invoice(models.Model):
    """Student fee invoices."""

    STATUS_CHOICES = [
        ("unpaid", "Unpaid"),
        ("partially_paid", "Partially Paid"),
        ("paid", "Paid"),
        ("overdue", "Overdue"),
        ("cancelled", "Cancelled"),
    ]

    student = models.ForeignKey("students.Student", on_delete=models.CASCADE)
    academic_year = models.ForeignKey(
        "academics.AcademicYear", on_delete=models.CASCADE
    )
    term = models.ForeignKey("academics.Term", on_delete=models.CASCADE)

    invoice_number = models.CharField(max_length=50, unique=True)
    issue_date = models.DateField(auto_now_add=True)
    due_date = models.DateField()

    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    net_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    paid_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="unpaid")
    remarks = models.TextField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ["student", "academic_year", "term"]
        ordering = ["-created_at"]

    def __str__(self):
        return f"Invoice {self.invoice_number} - {self.student}"

    @property
    def outstanding_amount(self):
        return self.net_amount - self.paid_amount

    @property
    def is_overdue(self):
        from django.utils import timezone

        return self.due_date < timezone.now().date() and self.status != "paid"

    def save(self, *args, **kwargs):
        if not self.invoice_number:
            self.invoice_number = self.generate_invoice_number()
        super().save(*args, **kwargs)

    def generate_invoice_number(self):
        """Generate unique invoice number."""
        from django.utils import timezone

        year = timezone.now().year
        count = Invoice.objects.filter(created_at__year=year).count() + 1
        return f"INV{year}{count:06d}"


class InvoiceItem(models.Model):
    """Individual items within an invoice."""

    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="items")
    fee_structure = models.ForeignKey(
        FeeStructure, on_delete=models.SET_NULL, null=True, blank=True
    )
    special_fee = models.ForeignKey(
        SpecialFee, on_delete=models.SET_NULL, null=True, blank=True
    )

    description = models.CharField(max_length=200)
    amount = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(0)]
    )
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    net_amount = models.DecimalField(max_digits=10, decimal_places=2)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"{self.description} - {self.net_amount}"

    def save(self, *args, **kwargs):
        self.net_amount = self.amount - self.discount_amount
        super().save(*args, **kwargs)


class Payment(models.Model):
    """Payment records."""

    PAYMENT_METHOD_CHOICES = [
        ("cash", "Cash"),
        ("bank_transfer", "Bank Transfer"),
        ("credit_card", "Credit Card"),
        ("debit_card", "Debit Card"),
        ("mobile_payment", "Mobile Payment"),
        ("cheque", "Cheque"),
        ("online", "Online Payment"),
    ]

    STATUS_CHOICES = [
        ("completed", "Completed"),
        ("pending", "Pending"),
        ("failed", "Failed"),
        ("refunded", "Refunded"),
    ]

    invoice = models.ForeignKey(
        Invoice, on_delete=models.CASCADE, related_name="payments"
    )
    payment_date = models.DateTimeField(auto_now_add=True)
    amount = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(0.01)]
    )
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES)

    transaction_id = models.CharField(max_length=100, blank=True)
    reference_number = models.CharField(max_length=100, blank=True)
    received_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    receipt_number = models.CharField(max_length=50, unique=True)

    remarks = models.TextField(blank=True)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="completed"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-payment_date"]

    def __str__(self):
        return f"Payment {self.receipt_number} - {self.amount}"

    def save(self, *args, **kwargs):
        if not self.receipt_number:
            self.receipt_number = self.generate_receipt_number()
        super().save(*args, **kwargs)

    def generate_receipt_number(self):
        """Generate unique receipt number."""
        from django.utils import timezone

        year = timezone.now().year
        count = Payment.objects.filter(created_at__year=year).count() + 1
        return f"RCP{year}{count:06d}"


class FinancialSummary(models.Model):
    """Monthly/term-wise financial summaries."""

    academic_year = models.ForeignKey(
        "academics.AcademicYear", on_delete=models.CASCADE
    )
    term = models.ForeignKey(
        "academics.Term", on_delete=models.CASCADE, null=True, blank=True
    )
    month = models.PositiveIntegerField(
        null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(12)]
    )
    year = models.PositiveIntegerField()

    total_fees_due = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_fees_collected = models.DecimalField(
        max_digits=12, decimal_places=2, default=0
    )
    total_outstanding = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_scholarships_given = models.DecimalField(
        max_digits=12, decimal_places=2, default=0
    )
    total_expenses = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    net_income = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    generated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ["academic_year", "term", "month", "year"]
        ordering = ["-year", "-month"]

    def __str__(self):
        period = f"{self.term}" if self.term else f"{self.month}/{self.year}"
        return f"Financial Summary - {period}"


class FinancialAnalytics(models.Model):
    """Financial analytics for different levels."""

    academic_year = models.ForeignKey(
        "academics.AcademicYear", on_delete=models.CASCADE
    )
    term = models.ForeignKey(
        "academics.Term", on_delete=models.CASCADE, null=True, blank=True
    )
    section = models.ForeignKey(
        "academics.Section", on_delete=models.CASCADE, null=True, blank=True
    )
    grade = models.ForeignKey(
        "academics.Grade", on_delete=models.CASCADE, null=True, blank=True
    )
    fee_category = models.ForeignKey(
        FeeCategory, on_delete=models.CASCADE, null=True, blank=True
    )

    total_expected_revenue = models.DecimalField(
        max_digits=12, decimal_places=2, default=0
    )
    total_collected_revenue = models.DecimalField(
        max_digits=12, decimal_places=2, default=0
    )
    collection_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=0
    )  # Percentage
    total_outstanding = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    number_of_defaulters = models.PositiveIntegerField(default=0)

    calculated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ["academic_year", "term", "section", "grade", "fee_category"]
        ordering = ["-calculated_at"]

    def __str__(self):
        level = self.grade or self.section or "Overall"
        category = f" - {self.fee_category}" if self.fee_category else ""
        return f"Analytics: {level}{category} ({self.term or self.academic_year})"


class FeeWaiver(models.Model):
    """Fee waivers for specific situations."""

    WAIVER_TYPE_CHOICES = [
        ("full", "Full Waiver"),
        ("partial", "Partial Waiver"),
    ]

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]

    student = models.ForeignKey("students.Student", on_delete=models.CASCADE)
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE)
    waiver_type = models.CharField(max_length=20, choices=WAIVER_TYPE_CHOICES)
    amount = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(0)]
    )
    reason = models.TextField()

    requested_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="requested_waivers"
    )
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_waivers",
    )

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    remarks = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Waiver: {self.student} - {self.amount}"
