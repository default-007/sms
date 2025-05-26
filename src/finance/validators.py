from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from decimal import Decimal, InvalidOperation
import re
from datetime import datetime, date
from typing import Any, Dict, List


class AmountValidator:
    """Validator for monetary amounts."""

    def __init__(self, min_amount=None, max_amount=None):
        self.min_amount = min_amount or Decimal("0.01")
        self.max_amount = max_amount or Decimal("999999.99")

    def __call__(self, value):
        try:
            amount = Decimal(str(value))
        except (InvalidOperation, ValueError):
            raise ValidationError(_("Enter a valid amount."))

        if amount < self.min_amount:
            raise ValidationError(
                _("Amount must be at least %(min_amount)s."),
                params={"min_amount": self.min_amount},
            )

        if amount > self.max_amount:
            raise ValidationError(
                _("Amount cannot exceed %(max_amount)s."),
                params={"max_amount": self.max_amount},
            )


class PercentageValidator:
    """Validator for percentage values."""

    def __init__(self, min_percentage=0, max_percentage=100):
        self.min_percentage = Decimal(str(min_percentage))
        self.max_percentage = Decimal(str(max_percentage))

    def __call__(self, value):
        try:
            percentage = Decimal(str(value))
        except (InvalidOperation, ValueError):
            raise ValidationError(_("Enter a valid percentage."))

        if percentage < self.min_percentage:
            raise ValidationError(
                _("Percentage must be at least %(min_percentage)s%%."),
                params={"min_percentage": self.min_percentage},
            )

        if percentage > self.max_percentage:
            raise ValidationError(
                _("Percentage cannot exceed %(max_percentage)s%%."),
                params={"max_percentage": self.max_percentage},
            )


class InvoiceNumberValidator:
    """Validator for invoice numbers."""

    def __init__(self, prefix="INV", min_length=6, max_length=20):
        self.prefix = prefix
        self.min_length = min_length
        self.max_length = max_length

    def __call__(self, value):
        if not isinstance(value, str):
            raise ValidationError(_("Invoice number must be a string."))

        if len(value) < self.min_length:
            raise ValidationError(
                _("Invoice number must be at least %(min_length)d characters."),
                params={"min_length": self.min_length},
            )

        if len(value) > self.max_length:
            raise ValidationError(
                _("Invoice number cannot exceed %(max_length)d characters."),
                params={"max_length": self.max_length},
            )

        if self.prefix and not value.startswith(self.prefix):
            raise ValidationError(
                _('Invoice number must start with "%(prefix)s".'),
                params={"prefix": self.prefix},
            )

        # Check if it contains only alphanumeric characters after prefix
        alphanumeric_part = value[len(self.prefix) :] if self.prefix else value
        if not alphanumeric_part.isalnum():
            raise ValidationError(
                _("Invoice number must contain only letters and numbers.")
            )


class PaymentMethodValidator:
    """Validator for payment method specific requirements."""

    REQUIRED_FIELDS = {
        "credit_card": ["transaction_id"],
        "debit_card": ["transaction_id"],
        "bank_transfer": ["reference_number"],
        "cheque": ["reference_number"],
        "online": ["transaction_id"],
        "mobile_payment": ["transaction_id"],
    }

    def __init__(self, payment_method, additional_data=None):
        self.payment_method = payment_method
        self.additional_data = additional_data or {}

    def __call__(self, value=None):
        if self.payment_method in self.REQUIRED_FIELDS:
            required_fields = self.REQUIRED_FIELDS[self.payment_method]

            for field in required_fields:
                if not self.additional_data.get(field):
                    raise ValidationError(
                        _("%(field)s is required for %(payment_method)s payments."),
                        params={
                            "field": field.replace("_", " ").title(),
                            "payment_method": self.payment_method.replace(
                                "_", " "
                            ).title(),
                        },
                    )


class CreditCardValidator:
    """Validator for credit card numbers using Luhn algorithm."""

    def __call__(self, value):
        if not value:
            return

        # Remove spaces and non-digits
        card_number = re.sub(r"\D", "", str(value))

        # Check length
        if len(card_number) < 13 or len(card_number) > 19:
            raise ValidationError(
                _("Credit card number must be between 13 and 19 digits.")
            )

        # Luhn algorithm validation
        if not self._luhn_check(card_number):
            raise ValidationError(_("Invalid credit card number."))

    def _luhn_check(self, card_number):
        """Implement Luhn algorithm for credit card validation."""

        def digits_of(n):
            return [int(d) for d in str(n)]

        digits = digits_of(card_number)
        odd_digits = digits[-1::-2]
        even_digits = digits[-2::-2]
        checksum = sum(odd_digits)

        for digit in even_digits:
            checksum += sum(digits_of(digit * 2))

        return checksum % 10 == 0


class ExpiryDateValidator:
    """Validator for credit card expiry dates."""

    def __call__(self, value):
        if not value:
            return

        try:
            # Handle different formats: MM/YY, MM/YYYY, MMYY, MMYYYY
            if "/" in value:
                month_str, year_str = value.split("/")
            elif len(value) == 4:  # MMYY
                month_str = value[:2]
                year_str = value[2:]
            elif len(value) == 6:  # MMYYYY
                month_str = value[:2]
                year_str = value[2:]
            else:
                raise ValidationError(
                    _("Invalid expiry date format. Use MM/YY or MM/YYYY.")
                )

            month = int(month_str)
            year = int(year_str)

            # Validate month
            if month < 1 or month > 12:
                raise ValidationError(_("Invalid month. Must be between 01 and 12."))

            # Convert 2-digit year to 4-digit
            if year < 100:
                current_year = datetime.now().year
                century = (current_year // 100) * 100
                year += century

                # If year is in the past, assume next century
                if year < current_year:
                    year += 100

            # Check if date is in the future
            expiry_date = datetime(year, month, 1)
            if expiry_date <= datetime.now():
                raise ValidationError(_("Expiry date must be in the future."))

        except (ValueError, IndexError):
            raise ValidationError(_("Invalid expiry date format."))


class CVVValidator:
    """Validator for CVV/CVC codes."""

    def __init__(self, card_type="default"):
        self.card_type = card_type.lower()

    def __call__(self, value):
        if not value:
            return

        cvv_str = str(value).strip()

        if not cvv_str.isdigit():
            raise ValidationError(_("CVV must contain only digits."))

        # American Express uses 4 digits, others use 3
        if self.card_type in ["amex", "american express"]:
            if len(cvv_str) != 4:
                raise ValidationError(_("CVV for American Express must be 4 digits."))
        else:
            if len(cvv_str) != 3:
                raise ValidationError(_("CVV must be 3 digits."))


class IBANValidator:
    """Validator for International Bank Account Numbers."""

    def __call__(self, value):
        if not value:
            return

        # Remove spaces and convert to uppercase
        iban = value.replace(" ", "").upper()

        # Check length
        if len(iban) < 15 or len(iban) > 34:
            raise ValidationError(_("IBAN must be between 15 and 34 characters."))

        # Check format (2 letters + 2 digits + alphanumeric)
        if not re.match(r"^[A-Z]{2}[0-9]{2}[A-Z0-9]+$", iban):
            raise ValidationError(_("Invalid IBAN format."))

        # IBAN checksum validation
        if not self._validate_iban_checksum(iban):
            raise ValidationError(_("Invalid IBAN checksum."))

    def _validate_iban_checksum(self, iban):
        """Validate IBAN using mod 97 algorithm."""
        # Move first 4 characters to end
        rearranged = iban[4:] + iban[:4]

        # Replace letters with numbers (A=10, B=11, ..., Z=35)
        numeric_string = ""
        for char in rearranged:
            if char.isalpha():
                numeric_string += str(ord(char) - ord("A") + 10)
            else:
                numeric_string += char

        # Check mod 97
        return int(numeric_string) % 97 == 1


class AccountNumberValidator:
    """Validator for bank account numbers."""

    def __init__(self, country_code="US"):
        self.country_code = country_code.upper()

    def __call__(self, value):
        if not value:
            return

        account_number = str(value).replace("-", "").replace(" ", "")

        if self.country_code == "US":
            # US account numbers are typically 6-12 digits
            if not account_number.isdigit() or not (6 <= len(account_number) <= 12):
                raise ValidationError(_("US account number must be 6-12 digits."))

        elif self.country_code == "UK":
            # UK account numbers are typically 8 digits
            if not account_number.isdigit() or len(account_number) != 8:
                raise ValidationError(_("UK account number must be 8 digits."))

        elif self.country_code == "CA":
            # Canadian account numbers vary but are typically 7-12 digits
            if not account_number.isdigit() or not (7 <= len(account_number) <= 12):
                raise ValidationError(_("Canadian account number must be 7-12 digits."))

        else:
            # Generic validation - at least 4 digits
            if not account_number.isdigit() or len(account_number) < 4:
                raise ValidationError(_("Account number must be at least 4 digits."))


class FeeStructureValidator:
    """Validator for fee structure business rules."""

    def __init__(self, instance=None):
        self.instance = instance

    def __call__(self, data):
        errors = {}

        # Check that either section or grade is specified
        if not data.get("section") and not data.get("grade"):
            errors["non_field_errors"] = [
                _("Either section or grade must be specified.")
            ]

        # Check for duplicate fee structures
        from .models import FeeStructure

        existing = FeeStructure.objects.filter(
            academic_year=data.get("academic_year"),
            term=data.get("term"),
            section=data.get("section"),
            grade=data.get("grade"),
            fee_category=data.get("fee_category"),
        )

        if self.instance:
            existing = existing.exclude(pk=self.instance.pk)

        if existing.exists():
            errors["non_field_errors"] = [
                _("Fee structure already exists for this combination.")
            ]

        # Validate due date is within the term
        term = data.get("term")
        due_date = data.get("due_date")

        if term and due_date:
            if not (term.start_date <= due_date <= term.end_date):
                errors["due_date"] = [_("Due date must be within the term period.")]

        if errors:
            raise ValidationError(errors)


class ScholarshipValidator:
    """Validator for scholarship business rules."""

    def __call__(self, data):
        errors = {}

        # Validate discount value based on type
        discount_type = data.get("discount_type")
        discount_value = data.get("discount_value")

        if discount_type == "percentage" and discount_value:
            if discount_value > 100:
                errors["discount_value"] = [
                    _("Percentage discount cannot exceed 100%.")
                ]

        if discount_value is not None and discount_value <= 0:
            errors["discount_value"] = [_("Discount value must be positive.")]

        # Validate applicable terms format
        applicable_terms = data.get("applicable_terms")
        if applicable_terms:
            if not isinstance(applicable_terms, list):
                errors["applicable_terms"] = [
                    _("Applicable terms must be a list of term IDs.")
                ]
            else:
                # Validate that all term IDs exist
                from academics.models import Term

                valid_term_ids = Term.objects.filter(
                    id__in=applicable_terms
                ).values_list("id", flat=True)

                invalid_terms = set(applicable_terms) - set(valid_term_ids)
                if invalid_terms:
                    errors["applicable_terms"] = [
                        _("Invalid term IDs: %(terms)s")
                        % {"terms": ", ".join(map(str, invalid_terms))}
                    ]

        if errors:
            raise ValidationError(errors)


class PaymentAmountValidator:
    """Validator for payment amounts against invoice outstanding."""

    def __init__(self, invoice):
        self.invoice = invoice

    def __call__(self, amount):
        if amount <= 0:
            raise ValidationError(_("Payment amount must be positive."))

        # Note: We allow overpayments as they can be treated as advance payments
        # If you want to restrict overpayments, uncomment the following:

        # outstanding = self.invoice.outstanding_amount
        # if amount > outstanding:
        #     raise ValidationError(
        #         _('Payment amount cannot exceed outstanding balance of %(outstanding)s.'),
        #         params={'outstanding': outstanding}
        #     )


class DateRangeValidator:
    """Validator for date ranges."""

    def __init__(self, start_date_field="start_date", end_date_field="end_date"):
        self.start_date_field = start_date_field
        self.end_date_field = end_date_field

    def __call__(self, data):
        start_date = data.get(self.start_date_field)
        end_date = data.get(self.end_date_field)

        if start_date and end_date:
            if start_date > end_date:
                raise ValidationError(
                    {self.end_date_field: [_("End date must be after start date.")]}
                )


class JSONFieldValidator:
    """Validator for JSON fields with specific structure requirements."""

    def __init__(self, required_keys=None, allowed_keys=None):
        self.required_keys = required_keys or []
        self.allowed_keys = allowed_keys

    def __call__(self, value):
        if not isinstance(value, (dict, list)):
            raise ValidationError(_("Value must be a valid JSON object or array."))

        if isinstance(value, dict):
            # Check required keys
            missing_keys = set(self.required_keys) - set(value.keys())
            if missing_keys:
                raise ValidationError(
                    _("Missing required keys: %(keys)s")
                    % {"keys": ", ".join(missing_keys)}
                )

            # Check allowed keys
            if self.allowed_keys:
                invalid_keys = set(value.keys()) - set(self.allowed_keys)
                if invalid_keys:
                    raise ValidationError(
                        _("Invalid keys: %(keys)s") % {"keys": ", ".join(invalid_keys)}
                    )


def validate_positive_decimal(value):
    """Simple validator for positive decimal values."""
    if value <= 0:
        raise ValidationError(_("Value must be positive."))


def validate_non_negative_decimal(value):
    """Simple validator for non-negative decimal values."""
    if value < 0:
        raise ValidationError(_("Value cannot be negative."))


def validate_percentage_range(value):
    """Simple validator for percentage values (0-100)."""
    if not (0 <= value <= 100):
        raise ValidationError(_("Percentage must be between 0 and 100."))


def validate_future_date(value):
    """Validator to ensure date is in the future."""
    if isinstance(value, datetime):
        value = value.date()

    if value <= date.today():
        raise ValidationError(_("Date must be in the future."))


def validate_academic_year_format(value):
    """Validator for academic year format (e.g., "2023-2024")."""
    pattern = r"^\d{4}-\d{4}$"
    if not re.match(pattern, value):
        raise ValidationError(_('Academic year must be in format "YYYY-YYYY".'))

    start_year, end_year = value.split("-")
    if int(end_year) != int(start_year) + 1:
        raise ValidationError(_("Academic year end must be one year after start."))


# Composite validators for complex validation scenarios
class InvoiceValidator:
    """Comprehensive validator for invoice data."""

    @staticmethod
    def validate_invoice_data(data, instance=None):
        """Validate complete invoice data."""
        errors = {}

        # Check for duplicate invoice
        from .models import Invoice

        existing = Invoice.objects.filter(
            student=data.get("student"),
            academic_year=data.get("academic_year"),
            term=data.get("term"),
        )

        if instance:
            existing = existing.exclude(pk=instance.pk)

        if existing.exists():
            errors["non_field_errors"] = [
                _("Invoice already exists for this student in this term.")
            ]

        # Validate amounts
        total_amount = data.get("total_amount", 0)
        discount_amount = data.get("discount_amount", 0)
        net_amount = data.get("net_amount", 0)

        if discount_amount > total_amount:
            errors["discount_amount"] = [
                _("Discount amount cannot exceed total amount.")
            ]

        expected_net = total_amount - discount_amount
        if abs(net_amount - expected_net) > Decimal("0.01"):  # Allow for rounding
            errors["net_amount"] = [
                _("Net amount should be total amount minus discount amount.")
            ]

        if errors:
            raise ValidationError(errors)


class PaymentValidator:
    """Comprehensive validator for payment data."""

    @staticmethod
    def validate_payment_data(data):
        """Validate complete payment data."""
        errors = {}

        invoice = data.get("invoice")
        amount = data.get("amount")
        payment_method = data.get("payment_method")

        if invoice and amount:
            # Validate payment amount
            try:
                PaymentAmountValidator(invoice)(amount)
            except ValidationError as e:
                errors["amount"] = e.messages

        # Validate payment method requirements
        if payment_method:
            try:
                PaymentMethodValidator(
                    payment_method,
                    {
                        "transaction_id": data.get("transaction_id"),
                        "reference_number": data.get("reference_number"),
                    },
                )()
            except ValidationError as e:
                errors["payment_method"] = e.messages

        if errors:
            raise ValidationError(errors)
