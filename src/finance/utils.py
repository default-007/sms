import re
from datetime import datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Dict, List, Optional, Tuple

from django.core.exceptions import ValidationError
from django.db.models import Avg, Count, Q, Sum
from django.utils import timezone


class FinanceUtils:
    """Utility functions for finance operations."""

    @staticmethod
    def round_currency(amount: Decimal, places: int = 2) -> Decimal:
        """Round currency amount to specified decimal places."""
        if not isinstance(amount, Decimal):
            amount = Decimal(str(amount))

        return amount.quantize(Decimal(f'0.{"0" * places}'), rounding=ROUND_HALF_UP)

    @staticmethod
    def format_currency(amount: Decimal, currency_symbol: str = "$") -> str:
        """Format amount as currency string."""
        rounded_amount = FinanceUtils.round_currency(amount)
        return f"{currency_symbol}{rounded_amount:,.2f}"

    @staticmethod
    def calculate_percentage(part: Decimal, whole: Decimal) -> Decimal:
        """Calculate percentage with safe division."""
        if whole == 0:
            return Decimal("0.00")

        return FinanceUtils.round_currency((part / whole) * 100)

    @staticmethod
    def generate_reference_number(prefix: str = "REF", length: int = 10) -> str:
        """Generate a random reference number."""
        import random
        import string

        timestamp = str(int(timezone.now().timestamp()))[-6:]
        random_part = "".join(
            random.choices(string.ascii_uppercase + string.digits, k=length - 6)
        )

        return f"{prefix}{timestamp}{random_part}"

    @staticmethod
    def validate_payment_method(payment_method: str, additional_data: Dict) -> bool:
        """Validate payment method and required fields."""
        required_fields = {
            "credit_card": ["transaction_id"],
            "debit_card": ["transaction_id"],
            "bank_transfer": ["reference_number"],
            "cheque": ["reference_number"],
            "online": ["transaction_id"],
            "mobile_payment": ["transaction_id"],
        }

        if payment_method in required_fields:
            for field in required_fields[payment_method]:
                if not additional_data.get(field):
                    return False

        return True

    @staticmethod
    def calculate_compound_late_fee(
        principal: Decimal,
        rate: Decimal,
        days_overdue: int,
        compound_frequency: int = 30,
    ) -> Decimal:
        """Calculate compound late fee."""
        if days_overdue <= 0 or rate <= 0:
            return Decimal("0.00")

        # Convert percentage to decimal
        rate_decimal = rate / 100

        # Calculate compound periods
        periods = days_overdue / compound_frequency

        # Compound formula: A = P(1 + r)^t - P
        compound_amount = principal * ((1 + rate_decimal) ** periods)
        late_fee = compound_amount - principal

        return FinanceUtils.round_currency(late_fee)

    @staticmethod
    def calculate_simple_late_fee(
        principal: Decimal, rate: Decimal, days_overdue: int
    ) -> Decimal:
        """Calculate simple late fee."""
        if days_overdue <= 0 or rate <= 0:
            return Decimal("0.00")

        # Convert percentage to decimal and calculate daily rate
        daily_rate = (rate / 100) / 365

        late_fee = principal * daily_rate * days_overdue
        return FinanceUtils.round_currency(late_fee)

    @staticmethod
    def get_payment_due_dates(
        start_date: datetime.date, frequency: str, count: int = 12
    ) -> List[datetime.date]:
        """Generate payment due dates based on frequency."""
        due_dates = []
        current_date = start_date

        for i in range(count):
            due_dates.append(current_date)

            if frequency == "monthly":
                # Add one month
                if current_date.month == 12:
                    current_date = current_date.replace(
                        year=current_date.year + 1, month=1
                    )
                else:
                    current_date = current_date.replace(month=current_date.month + 1)

            elif frequency == "quarterly":
                # Add three months
                month = current_date.month + 3
                year = current_date.year
                if month > 12:
                    month -= 12
                    year += 1
                current_date = current_date.replace(year=year, month=month)

            elif frequency == "annually":
                current_date = current_date.replace(year=current_date.year + 1)

            elif frequency == "termly":
                # Add 4 months (approximate term length)
                month = current_date.month + 4
                year = current_date.year
                if month > 12:
                    month -= 12
                    year += 1
                current_date = current_date.replace(year=year, month=month)

        return due_dates

    @staticmethod
    def validate_iban(iban: str) -> bool:
        """Validate International Bank Account Number."""
        # Remove spaces and convert to uppercase
        iban = iban.replace(" ", "").upper()

        # Check length (varies by country, but generally 15-34 characters)
        if len(iban) < 15 or len(iban) > 34:
            return False

        # Check format (2 letters + 2 digits + alphanumeric)
        if not re.match(r"^[A-Z]{2}[0-9]{2}[A-Z0-9]+$", iban):
            return False

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

    @staticmethod
    def validate_account_number(account_number: str, country_code: str = "US") -> bool:
        """Validate bank account number based on country."""
        account_number = account_number.replace("-", "").replace(" ", "")

        if country_code == "US":
            # US account numbers are typically 6-12 digits
            return account_number.isdigit() and 6 <= len(account_number) <= 12

        elif country_code == "UK":
            # UK account numbers are typically 8 digits
            return account_number.isdigit() and len(account_number) == 8

        elif country_code == "CA":
            # Canadian account numbers vary but are typically 7-12 digits
            return account_number.isdigit() and 7 <= len(account_number) <= 12

        else:
            # Generic validation - at least 4 digits
            return account_number.isdigit() and len(account_number) >= 4


class FeeCalculationHelper:
    """Helper class for fee calculations."""

    @staticmethod
    def distribute_amount_proportionally(
        total_amount: Decimal, proportions: List[Decimal]
    ) -> List[Decimal]:
        """Distribute amount proportionally among multiple parts."""
        if not proportions or sum(proportions) == 0:
            return [Decimal("0.00")] * len(proportions)

        total_proportion = sum(proportions)
        distributed_amounts = []

        for proportion in proportions:
            amount = (total_amount * proportion) / total_proportion
            distributed_amounts.append(FinanceUtils.round_currency(amount))

        # Adjust for rounding differences
        total_distributed = sum(distributed_amounts)
        difference = total_amount - total_distributed

        if difference != 0:
            # Add difference to the largest amount
            max_index = distributed_amounts.index(max(distributed_amounts))
            distributed_amounts[max_index] += difference

        return distributed_amounts

    @staticmethod
    def calculate_tiered_discount(amount: Decimal, tiers: List[Dict]) -> Decimal:
        """Calculate discount based on tiered structure.

        Args:
            amount: Amount to calculate discount for
            tiers: List of dicts with 'min_amount', 'max_amount', 'discount_rate'
        """
        total_discount = Decimal("0.00")
        remaining_amount = amount

        # Sort tiers by min_amount
        sorted_tiers = sorted(tiers, key=lambda x: x["min_amount"])

        for tier in sorted_tiers:
            min_amount = Decimal(str(tier["min_amount"]))
            max_amount = Decimal(str(tier.get("max_amount", float("inf"))))
            discount_rate = Decimal(str(tier["discount_rate"])) / 100

            if remaining_amount <= 0:
                break

            if amount >= min_amount:
                # Calculate amount in this tier
                tier_amount = min(remaining_amount, max_amount - min_amount + 1)
                tier_discount = tier_amount * discount_rate
                total_discount += tier_discount
                remaining_amount -= tier_amount

        return FinanceUtils.round_currency(total_discount)

    @staticmethod
    def apply_family_discount(
        amounts: List[Decimal], discount_structure: Dict
    ) -> List[Decimal]:
        """Apply family discount based on number of children."""
        child_count = len(amounts)

        if child_count <= 1:
            return amounts

        # Get discount rate for child count
        discount_rate = Decimal("0.00")
        for threshold, rate in discount_structure.items():
            if child_count >= int(threshold):
                discount_rate = Decimal(str(rate)) / 100

        if discount_rate == 0:
            return amounts

        # Apply discount to all children except the first (highest fee)
        sorted_amounts = sorted(amounts, reverse=True)
        discounted_amounts = []

        for i, amount in enumerate(sorted_amounts):
            if i == 0:  # First child pays full amount
                discounted_amounts.append(amount)
            else:  # Subsequent children get discount
                discount = amount * discount_rate
                discounted_amounts.append(amount - discount)

        return [FinanceUtils.round_currency(amt) for amt in discounted_amounts]


class PaymentValidators:
    """Validators for payment-related fields."""

    @staticmethod
    def validate_credit_card_number(card_number: str) -> bool:
        """Validate credit card number using Luhn algorithm."""
        # Remove spaces and non-digits
        card_number = re.sub(r"\D", "", card_number)

        # Check length
        if len(card_number) < 13 or len(card_number) > 19:
            return False

        # Luhn algorithm
        def luhn_check(card_num):
            def digits_of(n):
                return [int(d) for d in str(n)]

            digits = digits_of(card_num)
            odd_digits = digits[-1::-2]
            even_digits = digits[-2::-2]
            checksum = sum(odd_digits)

            for digit in even_digits:
                checksum += sum(digits_of(digit * 2))

            return checksum % 10 == 0

        return luhn_check(card_number)

    @staticmethod
    def validate_expiry_date(expiry_str: str) -> bool:
        """Validate credit card expiry date (MM/YY or MM/YYYY format)."""
        try:
            # Handle both MM/YY and MM/YYYY formats
            if "/" in expiry_str:
                month_str, year_str = expiry_str.split("/")
            else:
                # Assume MMYY format
                month_str = expiry_str[:2]
                year_str = expiry_str[2:]

            month = int(month_str)
            year = int(year_str)

            # Validate month
            if month < 1 or month > 12:
                return False

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
            return expiry_date > datetime.now()

        except (ValueError, IndexError):
            return False

    @staticmethod
    def validate_cvv(cvv: str, card_type: str = "default") -> bool:
        """Validate CVV/CVC code."""
        if not cvv.isdigit():
            return False

        # American Express uses 4 digits, others use 3
        if card_type.lower() in ["amex", "american express"]:
            return len(cvv) == 4
        else:
            return len(cvv) == 3


class ReportGenerator:
    """Helper class for generating financial reports."""

    @staticmethod
    def generate_collection_efficiency_report(invoices_queryset) -> Dict:
        """Generate collection efficiency metrics."""
        total_invoices = invoices_queryset.count()

        if total_invoices == 0:
            return {"total_invoices": 0, "collection_rate": 0, "efficiency_score": 0}

        # Calculate metrics
        paid_invoices = invoices_queryset.filter(status="paid").count()
        partially_paid = invoices_queryset.filter(status="partially_paid").count()

        total_amounts = invoices_queryset.aggregate(
            total_due=Sum("net_amount"), total_collected=Sum("paid_amount")
        )

        collection_rate = 0
        if total_amounts["total_due"]:
            collection_rate = (
                total_amounts["total_collected"] / total_amounts["total_due"]
            ) * 100

        # Calculate efficiency score (weighted metric)
        full_payment_weight = 1.0
        partial_payment_weight = 0.5

        efficiency_score = (
            (
                paid_invoices * full_payment_weight
                + partially_paid * partial_payment_weight
            )
            / total_invoices
            * 100
        )

        return {
            "total_invoices": total_invoices,
            "paid_invoices": paid_invoices,
            "partially_paid_invoices": partially_paid,
            "unpaid_invoices": total_invoices - paid_invoices - partially_paid,
            "collection_rate": round(collection_rate, 2),
            "efficiency_score": round(efficiency_score, 2),
            "total_due": total_amounts["total_due"] or Decimal("0.00"),
            "total_collected": total_amounts["total_collected"] or Decimal("0.00"),
            "outstanding_amount": (total_amounts["total_due"] or Decimal("0.00"))
            - (total_amounts["total_collected"] or Decimal("0.00")),
        }

    @staticmethod
    def generate_payment_method_analysis(payments_queryset) -> Dict:
        """Analyze payment methods distribution."""
        method_stats = (
            payments_queryset.values("payment_method")
            .annotate(
                count=Count("id"), total_amount=Sum("amount"), avg_amount=Avg("amount")
            )
            .order_by("-total_amount")
        )

        total_amount = payments_queryset.aggregate(total=Sum("amount"))[
            "total"
        ] or Decimal("0.00")

        # Add percentage for each method
        for method in method_stats:
            if total_amount > 0:
                method["percentage"] = round(
                    (method["total_amount"] / total_amount) * 100, 2
                )
            else:
                method["percentage"] = 0

        return {
            "total_payments": payments_queryset.count(),
            "total_amount": total_amount,
            "method_breakdown": list(method_stats),
            "most_popular_method": (
                method_stats[0]["payment_method"] if method_stats else None
            ),
            "highest_value_method": (
                method_stats[0]["payment_method"] if method_stats else None
            ),
        }


class AuditLogger:
    """Helper for logging financial transactions for audit purposes."""

    @staticmethod
    def log_payment_transaction(payment, action="CREATE", user=None, details=None):
        """Log payment transaction for audit trail."""
        from core.models import AuditLog

        audit_data = {
            "payment_id": payment.id,
            "invoice_id": payment.invoice.id,
            "student_id": payment.invoice.student.id,
            "amount": str(payment.amount),
            "payment_method": payment.payment_method,
            "status": payment.status,
            "action": action,
            "timestamp": timezone.now().isoformat(),
        }

        if details:
            audit_data.update(details)

        try:
            AuditLog.objects.create(
                user=user,
                action=f"PAYMENT_{action}",
                entity_type="Payment",
                entity_id=payment.id,
                data_after=audit_data,
                ip_address=getattr(user, "last_login_ip", None) if user else None,
            )
        except Exception:
            # Fail silently to avoid disrupting main transaction
            pass

    @staticmethod
    def log_fee_structure_change(
        fee_structure, action="CREATE", user=None, old_data=None
    ):
        """Log fee structure changes."""
        from core.models import AuditLog

        new_data = {
            "fee_structure_id": fee_structure.id,
            "fee_category": fee_structure.fee_category.name,
            "amount": str(fee_structure.amount),
            "academic_year": str(fee_structure.academic_year),
            "term": str(fee_structure.term),
            "is_active": fee_structure.is_active,
            "action": action,
            "timestamp": timezone.now().isoformat(),
        }

        try:
            AuditLog.objects.create(
                user=user,
                action=f"FEE_STRUCTURE_{action}",
                entity_type="FeeStructure",
                entity_id=fee_structure.id,
                data_before=old_data,
                data_after=new_data,
            )
        except Exception:
            pass
