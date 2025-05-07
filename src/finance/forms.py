from django import forms
from django.utils import timezone
from .models import (
    FeeCategory,
    FeeStructure,
    Scholarship,
    StudentScholarship,
    Invoice,
    InvoiceItem,
    Payment,
    Expense,
)
from src.students.models import Student


class FeeCategoryForm(forms.ModelForm):
    class Meta:
        model = FeeCategory
        fields = ["name", "description", "is_recurring", "frequency"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
        }

    def clean(self):
        cleaned_data = super().clean()
        is_recurring = cleaned_data.get("is_recurring")
        frequency = cleaned_data.get("frequency")

        if is_recurring and not frequency:
            raise forms.ValidationError(
                "Frequency must be specified for recurring fees."
            )

        return cleaned_data


class FeeStructureForm(forms.ModelForm):
    class Meta:
        model = FeeStructure
        fields = [
            "academic_year",
            "grade",
            "fee_category",
            "amount",
            "due_day_of_month",
            "late_fee_percentage",
            "grace_period_days",
        ]

    def clean(self):
        cleaned_data = super().clean()
        due_day = cleaned_data.get("due_day_of_month")

        if due_day and (due_day < 1 or due_day > 31):
            raise forms.ValidationError("Due day must be between 1 and 31.")

        return cleaned_data


class ScholarshipForm(forms.ModelForm):
    class Meta:
        model = Scholarship
        fields = [
            "name",
            "description",
            "discount_type",
            "discount_value",
            "criteria",
            "academic_year",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
        }

    def clean(self):
        cleaned_data = super().clean()
        discount_type = cleaned_data.get("discount_type")
        discount_value = cleaned_data.get("discount_value")

        if discount_type == "percentage" and discount_value > 100:
            raise forms.ValidationError("Percentage discount cannot exceed 100%.")

        if discount_value <= 0:
            raise forms.ValidationError("Discount value must be greater than zero.")

        return cleaned_data


class StudentScholarshipForm(forms.ModelForm):
    class Meta:
        model = StudentScholarship
        fields = [
            "student",
            "scholarship",
            "start_date",
            "end_date",
            "remarks",
            "status",
        ]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
            "remarks": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get("start_date")
        end_date = cleaned_data.get("end_date")

        if start_date and end_date and start_date > end_date:
            raise forms.ValidationError("End date must be after start date.")

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.user and not instance.approved_by:
            instance.approved_by = self.user

        if commit:
            instance.save()
        return instance


class InvoiceForm(forms.ModelForm):
    class Meta:
        model = Invoice
        fields = ["student", "academic_year", "issue_date", "due_date", "remarks"]
        widgets = {
            "issue_date": forms.DateInput(attrs={"type": "date"}),
            "due_date": forms.DateInput(attrs={"type": "date"}),
            "remarks": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

        # Set default dates
        if not self.instance.pk:
            self.fields["issue_date"].initial = timezone.now().date()
            self.fields["due_date"].initial = (
                timezone.now() + timezone.timedelta(days=15)
            ).date()

    def clean(self):
        cleaned_data = super().clean()
        issue_date = cleaned_data.get("issue_date")
        due_date = cleaned_data.get("due_date")

        if issue_date and due_date and issue_date > due_date:
            raise forms.ValidationError("Due date must be after issue date.")

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)

        if self.user and not instance.created_by:
            instance.created_by = self.user

        if commit:
            instance.save()
        return instance


class InvoiceItemForm(forms.ModelForm):
    class Meta:
        model = InvoiceItem
        fields = ["fee_structure", "description", "amount", "discount_amount"]

    def clean(self):
        cleaned_data = super().clean()
        amount = cleaned_data.get("amount")
        discount_amount = cleaned_data.get("discount_amount")

        if amount and discount_amount and discount_amount > amount:
            raise forms.ValidationError("Discount cannot exceed the amount.")

        return cleaned_data


class InvoiceItemFormSet(forms.BaseInlineFormSet):
    def clean(self):
        super().clean()

        # Ensure at least one invoice item exists
        if any(self.errors):
            return

        if not any(
            form.cleaned_data and not form.cleaned_data.get("DELETE", False)
            for form in self.forms
        ):
            raise forms.ValidationError("At least one invoice item is required.")


class BulkInvoiceGenerationForm(forms.Form):
    academic_year = forms.ModelChoiceField(queryset=None, label="Academic Year")
    grade = forms.ModelChoiceField(queryset=None, label="Grade", required=False)
    fee_category = forms.ModelChoiceField(queryset=None, label="Fee Category")
    issue_date = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date"}), initial=timezone.now().date()
    )
    due_date = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date"}),
        initial=(timezone.now() + timezone.timedelta(days=15)).date(),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from src.courses.models import Grade, AcademicYear

        # Initialize querysets
        self.fields["academic_year"].queryset = AcademicYear.objects.all().order_by(
            "-is_current", "-start_date"
        )
        self.fields["grade"].queryset = Grade.objects.all()
        self.fields["fee_category"].queryset = FeeCategory.objects.all()

    def clean(self):
        cleaned_data = super().clean()
        issue_date = cleaned_data.get("issue_date")
        due_date = cleaned_data.get("due_date")

        if issue_date and due_date and issue_date > due_date:
            raise forms.ValidationError("Due date must be after issue date.")

        return cleaned_data


class PaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = [
            "invoice",
            "payment_date",
            "amount",
            "payment_method",
            "transaction_id",
            "remarks",
        ]
        widgets = {
            "payment_date": forms.DateInput(attrs={"type": "date"}),
            "remarks": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        invoice_id = kwargs.pop("invoice_id", None)
        super().__init__(*args, **kwargs)

        # If invoice_id is provided, filter and preselect it
        if invoice_id:
            self.fields["invoice"].queryset = Invoice.objects.filter(id=invoice_id)
            self.fields["invoice"].initial = invoice_id
            self.fields["invoice"].widget.attrs["readonly"] = True

            # Set the max amount to the due amount
            try:
                invoice = Invoice.objects.get(id=invoice_id)
                self.fields["amount"].widget.attrs["max"] = invoice.get_due_amount()
            except Invoice.DoesNotExist:
                pass

    def clean_amount(self):
        amount = self.cleaned_data.get("amount")
        invoice = self.cleaned_data.get("invoice")

        if amount <= 0:
            raise forms.ValidationError("Payment amount must be greater than zero.")

        if invoice and amount > invoice.get_due_amount():
            raise forms.ValidationError(
                f"Payment amount cannot exceed the due amount ({invoice.get_due_amount()})."
            )

        return amount

    def save(self, commit=True):
        instance = super().save(commit=False)

        if self.user and not instance.received_by:
            instance.received_by = self.user

        if commit:
            instance.save()
        return instance


class ExpenseForm(forms.ModelForm):
    class Meta:
        model = Expense
        fields = [
            "expense_category",
            "amount",
            "expense_date",
            "description",
            "payment_method",
            "paid_to",
            "receipt_attachment",
            "remarks",
        ]
        widgets = {
            "expense_date": forms.DateInput(attrs={"type": "date"}),
            "description": forms.Textarea(attrs={"rows": 3}),
            "remarks": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

    def save(self, commit=True):
        instance = super().save(commit=False)

        if self.user and not instance.approved_by:
            instance.approved_by = self.user

        if commit:
            instance.save()
        return instance
