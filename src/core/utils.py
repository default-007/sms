# utils.py
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.utils import timezone
from django.conf import settings
from decimal import Decimal, InvalidOperation
from datetime import datetime, timedelta
import re
import hashlib
import secrets
import string
from typing import Any, Dict, List, Optional, Union
import logging

logger = logging.getLogger(__name__)


class ValidationUtils:
    """Utility class for common validation functions"""

    @staticmethod
    def validate_phone_number(phone: str) -> bool:
        """Validate phone number format"""
        # Remove all non-digit characters
        phone_digits = re.sub(r"\D", "", phone)

        # Check if it's between 10-15 digits
        return len(phone_digits) >= 10 and len(phone_digits) <= 15

    @staticmethod
    def validate_admission_number(admission_number: str) -> bool:
        """Validate admission number format"""
        # Should be alphanumeric and 6-12 characters
        pattern = r"^[A-Z0-9]{6,12}$"
        return bool(re.match(pattern, admission_number.upper()))

    @staticmethod
    def validate_employee_id(employee_id: str) -> bool:
        """Validate employee ID format"""
        # Should be alphanumeric and 4-10 characters
        pattern = r"^[A-Z0-9]{4,10}$"
        return bool(re.match(pattern, employee_id.upper()))

    @staticmethod
    def validate_percentage(value: Union[int, float, Decimal]) -> bool:
        """Validate percentage value (0-100)"""
        try:
            num_value = float(value)
            return 0 <= num_value <= 100
        except (ValueError, TypeError):
            return False

    @staticmethod
    def validate_grade_point(value: Union[int, float, Decimal]) -> bool:
        """Validate grade point (typically 0-4 or 0-10 scale)"""
        try:
            num_value = float(value)
            return 0 <= num_value <= 10  # Assuming 10-point scale
        except (ValueError, TypeError):
            return False

    @staticmethod
    def validate_marks(
        value: Union[int, float, Decimal], max_marks: Union[int, float, Decimal] = 100
    ) -> bool:
        """Validate marks value"""
        try:
            marks = float(value)
            max_val = float(max_marks)
            return 0 <= marks <= max_val
        except (ValueError, TypeError):
            return False


class DateUtils:
    """Utility class for date-related functions"""

    @staticmethod
    def get_academic_year_from_date(date: datetime) -> str:
        """Get academic year string from date"""
        if date.month >= 7:  # July onwards
            return f"{date.year}-{date.year + 1}"
        else:
            return f"{date.year - 1}-{date.year}"

    @staticmethod
    def get_current_academic_year() -> str:
        """Get current academic year"""
        return DateUtils.get_academic_year_from_date(timezone.now())

    @staticmethod
    def calculate_age(birth_date: datetime) -> int:
        """Calculate age from birth date"""
        today = timezone.now().date()
        if isinstance(birth_date, datetime):
            birth_date = birth_date.date()

        age = today.year - birth_date.year
        if today.month < birth_date.month or (
            today.month == birth_date.month and today.day < birth_date.day
        ):
            age -= 1
        return age

    @staticmethod
    def get_term_from_date(date: datetime) -> int:
        """Get term number from date (assuming 3-term system)"""
        month = date.month
        if 7 <= month <= 10:  # July to October
            return 1
        elif 11 <= month <= 2:  # November to February
            return 2
        else:  # March to June
            return 3

    @staticmethod
    def get_working_days(
        start_date: datetime, end_date: datetime, exclude_weekends: bool = True
    ) -> int:
        """Calculate working days between two dates"""
        if start_date > end_date:
            return 0

        total_days = (end_date - start_date).days + 1

        if not exclude_weekends:
            return total_days

        # Count weekends
        current_date = start_date
        weekend_days = 0

        while current_date <= end_date:
            if current_date.weekday() >= 5:  # Saturday = 5, Sunday = 6
                weekend_days += 1
            current_date += timedelta(days=1)

        return total_days - weekend_days


class SecurityUtils:
    """Utility class for security-related functions"""

    @staticmethod
    def generate_random_password(length: int = 12) -> str:
        """Generate a random password"""
        alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
        password = "".join(secrets.choice(alphabet) for _ in range(length))
        return password

    @staticmethod
    def hash_sensitive_data(data: str) -> str:
        """Hash sensitive data using SHA-256"""
        return hashlib.sha256(data.encode()).hexdigest()

    @staticmethod
    def generate_unique_token(length: int = 32) -> str:
        """Generate a unique token"""
        return secrets.token_urlsafe(length)

    @staticmethod
    def mask_sensitive_info(
        info: str, mask_char: str = "*", visible_chars: int = 4
    ) -> str:
        """Mask sensitive information like phone numbers, emails"""
        if len(info) <= visible_chars:
            return mask_char * len(info)

        if "@" in info:  # Email
            username, domain = info.split("@", 1)
            masked_username = username[:2] + mask_char * (len(username) - 2)
            return f"{masked_username}@{domain}"
        else:  # Phone or other
            return info[:visible_chars] + mask_char * (len(info) - visible_chars)


class FileUtils:
    """Utility class for file-related functions"""

    @staticmethod
    def get_file_extension(filename: str) -> str:
        """Get file extension from filename"""
        return filename.split(".")[-1].lower() if "." in filename else ""

    @staticmethod
    def is_allowed_file_type(filename: str, allowed_types: List[str]) -> bool:
        """Check if file type is allowed"""
        extension = FileUtils.get_file_extension(filename)
        return extension in [ext.lower() for ext in allowed_types]

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """Sanitize filename for safe storage"""
        # Remove or replace unsafe characters
        filename = re.sub(r'[<>:"/\\|?*]', "_", filename)
        filename = filename.strip(". ")

        # Limit length
        if len(filename) > 255:
            name, ext = filename.rsplit(".", 1) if "." in filename else (filename, "")
            filename = name[: 255 - len(ext) - 1] + "." + ext if ext else name[:255]

        return filename

    @staticmethod
    def format_file_size(size_bytes: int) -> str:
        """Format file size in human-readable format"""
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} PB"


class FormatUtils:
    """Utility class for formatting functions"""

    @staticmethod
    def format_currency(
        amount: Union[int, float, Decimal], currency_code: str = "USD"
    ) -> str:
        """Format amount as currency"""
        currency_symbols = {
            "USD": "$",
            "EUR": "€",
            "GBP": "£",
            "INR": "₹",
            "JPY": "¥",
            "CNY": "¥",
        }

        symbol = currency_symbols.get(currency_code.upper(), currency_code)

        try:
            amount = float(amount)
            return f"{symbol}{amount:,.2f}"
        except (ValueError, TypeError):
            return f"{symbol}0.00"

    @staticmethod
    def format_percentage(
        value: Union[int, float, Decimal], decimal_places: int = 1
    ) -> str:
        """Format value as percentage"""
        try:
            percentage = float(value)
            return f"{percentage:.{decimal_places}f}%"
        except (ValueError, TypeError):
            return "0.0%"

    @staticmethod
    def format_grade_point(value: Union[int, float, Decimal], scale: int = 4) -> str:
        """Format grade point"""
        try:
            gpa = float(value)
            return f"{gpa:.2f}/{scale}"
        except (ValueError, TypeError):
            return f"0.00/{scale}"

    @staticmethod
    def format_phone_number(phone: str, country_code: str = "+1") -> str:
        """Format phone number"""
        # Remove all non-digit characters
        digits = re.sub(r"\D", "", phone)

        if len(digits) == 10:  # US format
            return f"{country_code} ({digits[:3]}) {digits[3:6]}-{digits[6:]}"
        elif len(digits) == 11 and digits[0] == "1":  # US with country code
            return f"+{digits[0]} ({digits[1:4]}) {digits[4:7]}-{digits[7:]}"
        else:
            return phone  # Return as-is if format not recognized


class MathUtils:
    """Utility class for mathematical functions"""

    @staticmethod
    def calculate_percentage(
        part: Union[int, float], total: Union[int, float]
    ) -> float:
        """Calculate percentage"""
        try:
            if total == 0:
                return 0.0
            return (float(part) / float(total)) * 100
        except (ValueError, TypeError, ZeroDivisionError):
            return 0.0

    @staticmethod
    def calculate_gpa(
        grades: List[Dict[str, Union[float, int]]], scale: int = 4
    ) -> float:
        """Calculate GPA from list of grades with credit hours"""
        total_points = 0
        total_credits = 0

        for grade in grades:
            points = float(grade.get("points", 0))
            credits = float(grade.get("credits", 0))
            total_points += points * credits
            total_credits += credits

        if total_credits == 0:
            return 0.0

        return round(total_points / total_credits, 2)

    @staticmethod
    def calculate_weighted_average(values: List[Dict[str, Union[float, int]]]) -> float:
        """Calculate weighted average"""
        total_weighted = 0
        total_weights = 0

        for item in values:
            value = float(item.get("value", 0))
            weight = float(item.get("weight", 1))
            total_weighted += value * weight
            total_weights += weight

        if total_weights == 0:
            return 0.0

        return round(total_weighted / total_weights, 2)

    @staticmethod
    def calculate_standard_deviation(values: List[Union[int, float]]) -> float:
        """Calculate standard deviation"""
        if not values:
            return 0.0

        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        return round(variance**0.5, 2)


class CacheUtils:
    """Utility class for cache-related functions"""

    @staticmethod
    def generate_cache_key(prefix: str, *args, **kwargs) -> str:
        """Generate a cache key from prefix and arguments"""
        key_parts = [prefix]

        # Add positional arguments
        for arg in args:
            key_parts.append(str(arg))

        # Add keyword arguments
        for key, value in sorted(kwargs.items()):
            key_parts.append(f"{key}:{value}")

        return ":".join(key_parts)

    @staticmethod
    def get_cache_timeout(cache_type: str) -> int:
        """Get cache timeout for different types of data"""
        timeouts = {
            "user_session": 3600,  # 1 hour
            "system_settings": 3600,  # 1 hour
            "analytics_data": 1800,  # 30 minutes
            "dashboard_data": 900,  # 15 minutes
            "static_data": 86400,  # 24 hours
        }
        return timeouts.get(cache_type, 3600)  # Default 1 hour
