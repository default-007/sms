from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal

from .models import (
    FeeCategory,
    FeeStructure,
    SpecialFee,
    Scholarship,
    StudentScholarship,
    Invoice,
    Payment,
    FeeWaiver,
)
from students.models import Student
from academics.models import AcademicYear, Term, Section, Grade, Class


class FeeCategoryForm(forms.ModelForm):
    """Form for creating/editing fee categories."""

    class Meta:
        model = FeeCategory
        fields = ["name", "description", "is_mandatory", "is_recurring", "frequency"]
        widgets = {
            "name": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Enter category name"}
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": "Enter description",
                }
            ),
            "is_mandatory": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "is_recurring": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "frequency": forms.Select(attrs={"class": "form-control"}),
        }


class FeeStructureForm(forms.ModelForm):
    """Form for creating/editing fee structures."""

    class Meta:
        model = FeeStructure
        fields = [
            "academic_year",
            "term",
            "section",
            "grade",
            "fee_category",
            "amount",
            "due_date",
            "late_fee_percentage",
            "grace_period_days",
            "is_active",
        ]
        widgets = {
            "academic_year": forms.Select(attrs={"class": "form-control"}),
            "term": forms.Select(attrs={"class": "form-control"}),
            "section": forms.Select(attrs={"class": "form-control"}),
            "grade": forms.Select(attrs={"class": "form-control"}),
            "fee_category": forms.Select(attrs={"class": "form-control"}),
            "amount": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01", "min": "0"}
            ),
            "due_date": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}
            ),
            "late_fee_percentage": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "step": "0.01",
                    "min": "0",
                    "max": "100",
                }
            ),
            "grace_period_days": forms.NumberInput(
                attrs={"class": "form-control", "min": "0"}
            ),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Make section and grade optional (one of them is required)
        self.fields["section"].required = False
        self.fields["grade"].required = False

        # Set empty label for optional fields
        self.fields["section"].empty_label = "Select Section (optional)"
        self.fields["grade"].empty_label = "Select Grade (optional)"

    def clean(self):
        """Validate that either section or grade is provided."""
        cleaned_data = super().clean()
        section = cleaned_data.get("section")
        grade = cleaned_data.get("grade")

        if not section and not grade:
            raise ValidationError("Either section or grade must be specified")

        # Check for duplicate fee structures
        academic_year = cleaned_data.get("academic_year")
        term = cleaned_data.get("term")
        fee_category = cleaned_data.get("fee_category")

        if academic_year and term and fee_category:
            existing = FeeStructure.objects.filter(
                academic_year=academic_year,
                term=term,
                section=section,
                grade=grade,
                fee_category=fee_category,
            )

            if self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)

            if existing.exists():
                raise ValidationError(
                    "Fee structure already exists for this combination"
                )

        return cleaned_data


class SpecialFeeForm(forms.ModelForm):
    """Form for creating/editing special fees."""

    class Meta:
        model = SpecialFee
        fields = [
            "name",
            "description",
            "fee_category",
            "amount",
            "fee_type",
            "class_obj",
            "student",
            "term",
            "due_date",
            "reason",
            "is_active",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "fee_category": forms.Select(attrs={"class": "form-control"}),
            "amount": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01", "min": "0"}
            ),
            "fee_type": forms.Select(attrs={"class": "form-control"}),
            "class_obj": forms.Select(attrs={"class": "form-control"}),
            "student": forms.Select(attrs={"class": "form-control"}),
            "term": forms.Select(attrs={"class": "form-control"}),
            "due_date": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}
            ),
            "reason": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Make class and student optional based on fee_type
        self.fields["class_obj"].required = False
        self.fields["student"].required = False

        self.fields["class_obj"].empty_label = "Select Class"
        self.fields["student"].empty_label = "Select Student"

    def clean(self):
        """Validate based on fee type."""
        cleaned_data = super().clean()
        fee_type = cleaned_data.get("fee_type")
        class_obj = cleaned_data.get("class_obj")
        student = cleaned_data.get("student")

        if fee_type == "class_based" and not class_obj:
            raise ValidationError("Class is required for class-based fees")
        elif fee_type == "student_specific" and not student:
            raise ValidationError("Student is required for student-specific fees")

        return cleaned_data


class ScholarshipForm(forms.ModelForm):
    """Form for creating/editing scholarships."""

    class Meta:
        model = Scholarship
        fields = [
            "name",
            "description",
            "discount_type",
            "discount_value",
            "criteria",
            "academic_year",
            "applicable_terms",
            "max_recipients",
            "is_active",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
            "discount_type": forms.Select(attrs={"class": "form-control"}),
            "discount_value": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01", "min": "0"}
            ),
            "criteria": forms.Select(attrs={"class": "form-control"}),
            "academic_year": forms.Select(attrs={"class": "form-control"}),
            "applicable_terms": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Enter term IDs separated by commas",
                }
            ),
            "max_recipients": forms.NumberInput(
                attrs={"class": "form-control", "min": "1"}
            ),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def clean_discount_value(self):
        """Validate discount value."""
        discount_value = self.cleaned_data.get("discount_value")
        discount_type = self.cleaned_data.get("discount_type")

        if discount_value is not None:
            if discount_value <= 0:
                raise ValidationError("Discount value must be positive")

            if discount_type == "percentage" and discount_value > 100:
                raise ValidationError("Percentage discount cannot exceed 100%")

        return discount_value


class StudentScholarshipForm(forms.ModelForm):
    """Form for assigning scholarships to students."""

    class Meta:
        model = StudentScholarship
        fields = ["student", "scholarship", "start_date", "end_date", "remarks"]
        widgets = {
            "student": forms.Select(attrs={"class": "form-control"}),
            "scholarship": forms.Select(attrs={"class": "form-control"}),
            "start_date": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}
            ),
            "end_date": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}
            ),
            "remarks": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["end_date"].required = False

        # Set default start date to today
        if not self.instance.pk:
            self.fields["start_date"].initial = timezone.now().date()

    def clean(self):
        """Validate scholarship assignment."""
        cleaned_data = super().clean()
        student = cleaned_data.get("student")
        scholarship = cleaned_data.get("scholarship")

        if student and scholarship:
            # Check if student already has this scholarship
            existing = StudentScholarship.objects.filter(
                student=student,
                scholarship=scholarship,
                status__in=["approved", "pending"],
            )

            if self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)

            if existing.exists():
                raise ValidationError("Student already has this scholarship")

            # Check scholarship availability
            if not scholarship.has_available_slots:
                raise ValidationError("No available slots for this scholarship")

        return cleaned_data


class PaymentForm(forms.ModelForm):
    """Form for processing payments."""

    class Meta:
        model = Payment
        fields = [
            "invoice",
            "amount",
            "payment_method",
            "transaction_id",
            "reference_number",
            "remarks",
        ]
        widgets = {
            "invoice": forms.Select(attrs={"class": "form-control"}),
            "amount": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01", "min": "0.01"}
            ),
            "payment_method": forms.Select(attrs={"class": "form-control"}),
            "transaction_id": forms.TextInput(attrs={"class": "form-control"}),
            "reference_number": forms.TextInput(attrs={"class": "form-control"}),
            "remarks": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Make optional fields not required
        self.fields["transaction_id"].required = False
        self.fields["reference_number"].required = False
        self.fields["remarks"].required = False

        # Filter invoices to show only unpaid/partially paid
        self.fields["invoice"].queryset = Invoice.objects.filter(
            status__in=["unpaid", "partially_paid"]
        ).select_related("student")

    def clean_amount(self):
        """Validate payment amount."""
        amount = self.cleaned_data.get("amount")

        if amount is not None and amount <= 0:
            raise ValidationError("Payment amount must be positive")

        return amount

    def clean(self):
        """Validate payment against invoice."""
        cleaned_data = super().clean()
        invoice = cleaned_data.get("invoice")
        amount = cleaned_data.get("amount")

        if invoice and amount:
            outstanding = invoice.outstanding_amount
            if outstanding <= 0:
                raise ValidationError("Invoice is already fully paid")

            # Allow overpayment (will be treated as advance)
            # if amount > outstanding:
            #     raise ValidationError(f"Payment amount exceeds outstanding balance of {outstanding}")

        return cleaned_data


class FeeWaiverForm(forms.ModelForm):
    """Form for requesting fee waivers."""

    class Meta:
        model = FeeWaiver
        fields = ["student", "invoice", "waiver_type", "amount", "reason"]
        widgets = {
            "student": forms.Select(attrs={"class": "form-control"}),
            "invoice": forms.Select(attrs={"class": "form-control"}),
            "waiver_type": forms.Select(attrs={"class": "form-control"}),
            "amount": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01", "min": "0.01"}
            ),
            "reason": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 4,
                    "placeholder": "Provide detailed justification for the waiver",
                }
            ),
        }

    def clean(self):
        """Validate waiver request."""
        cleaned_data = super().clean()
        invoice = cleaned_data.get("invoice")
        amount = cleaned_data.get("amount")

        if invoice and amount:
            outstanding = invoice.outstanding_amount
            if amount > outstanding:
                raise ValidationError(
                    f"Waiver amount exceeds outstanding balance of {outstanding}"
                )

        return cleaned_data


# Additional forms for bulk operations and filtering


class BulkInvoiceGenerationForm(forms.Form):
    """Form for bulk invoice generation."""

    academic_year = forms.ModelChoiceField(
        queryset=AcademicYear.objects.all(),
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    term = forms.ModelChoiceField(
        queryset=Term.objects.all(),
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    section = forms.ModelChoiceField(
        queryset=Section.objects.all(),
        required=False,
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    grade = forms.ModelChoiceField(
        queryset=Grade.objects.all(),
        required=False,
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    class_obj = forms.ModelChoiceField(
        queryset=Class.objects.all(),
        required=False,
        widget=forms.Select(attrs={"class": "form-control"}),
    )


class FinancialReportFilterForm(forms.Form):
    """Form for filtering financial reports."""

    academic_year = forms.ModelChoiceField(
        queryset=AcademicYear.objects.all(),
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    term = forms.ModelChoiceField(
        queryset=Term.objects.all(),
        required=False,
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    section = forms.ModelChoiceField(
        queryset=Section.objects.all(),
        required=False,
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    grade = forms.ModelChoiceField(
        queryset=Grade.objects.all(),
        required=False,
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    fee_category = forms.ModelChoiceField(
        queryset=FeeCategory.objects.all(),
        required=False,
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
    )
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
    )


class PaymentMethodAnalysisForm(forms.Form):
    """Form for payment method analysis."""

    date_from = forms.DateField(
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"})
    )
    date_to = forms.DateField(
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"})
    )
    payment_method = forms.ChoiceField(
        choices=[("", "All Methods")] + Payment.PAYMENT_METHOD_CHOICES,
        required=False,
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    group_by = forms.ChoiceField(
        choices=[
            ("day", "Daily"),
            ("month", "Monthly"),
            ("method", "By Payment Method"),
        ],
        widget=forms.Select(attrs={"class": "form-control"}),
    )
