# src/accounts/utils.py

import hashlib
import re
import secrets
import string
import user_agents
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
import phonenumbers
from phonenumbers import NumberParseException

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.core.validators import validate_email
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.text import slugify

User = get_user_model()


def generate_secure_password(
    length: int = 12,
    include_symbols: bool = True,
    ensure_complexity: bool = True,
    exclude_ambiguous: bool = True,
) -> str:
    """
    Generate a secure password with specified criteria.

    Args:
        length: Password length (minimum 8)
        include_symbols: Whether to include special characters
        ensure_complexity: Ensure password meets complexity requirements
        exclude_ambiguous: Exclude ambiguous characters (0, O, l, 1, etc.)

    Returns:
        Generated password string
    """
    if length < 8:
        raise ValueError("Password length must be at least 8 characters")

    # Character sets
    lowercase = string.ascii_lowercase
    uppercase = string.ascii_uppercase
    digits = string.digits
    symbols = "!@#$%^&*()_+-=[]{}|;:,.<>?" if include_symbols else ""

    # Remove ambiguous characters if requested
    if exclude_ambiguous:
        lowercase = lowercase.replace("l", "").replace("o", "")
        uppercase = uppercase.replace("I", "").replace("O", "")
        digits = digits.replace("0", "").replace("1", "")
        symbols = symbols.replace("|", "").replace("l", "")

    # Ensure at least one character from each required set
    password = []
    if ensure_complexity:
        password.append(secrets.choice(lowercase))
        password.append(secrets.choice(uppercase))
        password.append(secrets.choice(digits))
        if include_symbols:
            password.append(secrets.choice(symbols))

    # Fill remaining length with random characters
    all_chars = lowercase + uppercase + digits + symbols
    remaining_length = length - len(password)

    for _ in range(remaining_length):
        password.append(secrets.choice(all_chars))

    # Shuffle the password to randomize character positions
    secrets.SystemRandom().shuffle(password)

    return "".join(password)


def validate_password_strength(password: str) -> Dict[str, Any]:
    """
    Validate password strength and return detailed feedback.

    Args:
        password: Password to validate

    Returns:
        Dictionary with validation results
    """
    result = {
        "is_valid": True,
        "score": 0,
        "feedback": [],
        "requirements": {
            "length": False,
            "uppercase": False,
            "lowercase": False,
            "digits": False,
            "symbols": False,
            "no_common": False,
            "no_personal": False,
        },
        "strength_level": "weak",
    }

    # Check length
    if len(password) >= 8:
        result["requirements"]["length"] = True
        result["score"] += 20
    else:
        result["is_valid"] = False
        result["feedback"].append("Password must be at least 8 characters long")

    # Check for uppercase letters
    if any(c.isupper() for c in password):
        result["requirements"]["uppercase"] = True
        result["score"] += 15
    else:
        result["feedback"].append(
            "Password should contain at least one uppercase letter"
        )

    # Check for lowercase letters
    if any(c.islower() for c in password):
        result["requirements"]["lowercase"] = True
        result["score"] += 15
    else:
        result["feedback"].append(
            "Password should contain at least one lowercase letter"
        )

    # Check for digits
    if any(c.isdigit() for c in password):
        result["requirements"]["digits"] = True
        result["score"] += 15
    else:
        result["feedback"].append("Password should contain at least one digit")

    # Check for symbols
    if any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
        result["requirements"]["symbols"] = True
        result["score"] += 15
    else:
        result["feedback"].append(
            "Password should contain at least one special character"
        )

    # Bonus points for length
    if len(password) >= 12:
        result["score"] += 10
    if len(password) >= 16:
        result["score"] += 10

    # Check for common passwords
    common_passwords = [
        "password",
        "123456",
        "123456789",
        "qwerty",
        "abc123",
        "password123",
        "admin",
        "letmein",
        "welcome",
        "monkey",
    ]

    if password.lower() not in common_passwords:
        result["requirements"]["no_common"] = True
        result["score"] += 10
    else:
        result["is_valid"] = False
        result["score"] = 0
        result["feedback"] = ["Password is too common"]

    # Check for sequential patterns
    sequential_patterns = ["123456", "abcdef", "qwerty", "asdfgh", "zxcvbn"]

    if not any(pattern in password.lower() for pattern in sequential_patterns):
        result["requirements"]["no_personal"] = True
        result["score"] += 10
    else:
        result["feedback"].append("Avoid sequential patterns")

    # Determine strength level
    if result["score"] >= 90:
        result["strength_level"] = "very_strong"
    elif result["score"] >= 75:
        result["strength_level"] = "strong"
    elif result["score"] >= 60:
        result["strength_level"] = "medium"
    elif result["score"] >= 40:
        result["strength_level"] = "weak"
    else:
        result["strength_level"] = "very_weak"

    # Set minimum score for validity
    if result["score"] < 60:
        result["is_valid"] = False

    return result


def validate_phone_number(
    phone_number: str, country_code: str = None
) -> Dict[str, Any]:
    """
    Validate and format phone number using phonenumbers library.

    Args:
        phone_number: Phone number to validate
        country_code: ISO country code (e.g., 'US', 'GB')

    Returns:
        Dictionary with validation results
    """
    result = {
        "is_valid": False,
        "formatted": "",
        "international": "",
        "national": "",
        "country_code": "",
        "error": "",
    }

    try:
        # Parse phone number
        parsed = phonenumbers.parse(phone_number, country_code)

        # Validate
        if phonenumbers.is_valid_number(parsed):
            result["is_valid"] = True
            result["formatted"] = phonenumbers.format_number(
                parsed, phonenumbers.PhoneNumberFormat.E164
            )
            result["international"] = phonenumbers.format_number(
                parsed, phonenumbers.PhoneNumberFormat.INTERNATIONAL
            )
            result["national"] = phonenumbers.format_number(
                parsed, phonenumbers.PhoneNumberFormat.NATIONAL
            )
            result["country_code"] = phonenumbers.region_code_for_number(parsed)
        else:
            result["error"] = "Invalid phone number"

    except NumberParseException as e:
        result["error"] = f"Phone number parsing error: {e}"
    except Exception as e:
        result["error"] = f"Unexpected error: {e}"

    return result


def send_notification_email(user, subject: str, template: str, context: Dict = None):
    """
    Send notification email to user.

    Args:
        user: User object
        subject: Email subject
        template: Template name
        context: Additional context for template
    """
    try:
        if not user.email:
            logger.warning(f"No email address for user {user.id}")
            return False

        context = context or {}
        context.update(
            {
                "user": user,
                "site_name": getattr(settings, "SITE_NAME", "School Management System"),
            }
        )

        message = render_to_string(template, context)

        send_mail(
            subject=subject,
            message="",
            html_message=message,
            from_email=None,  # Use default
            recipient_list=[user.email],
            fail_silently=False,
        )

        logger.info(f"Notification email sent to user {user.id}")
        return True

    except Exception as e:
        logger.error(f"Failed to send notification email to user {user.id}: {str(e)}")
        return False


def get_device_fingerprint(request) -> str:
    """
    Generate a device fingerprint for security tracking.

    Args:
        request: Django HTTP request object

    Returns:
        Device fingerprint hash
    """
    import hashlib

    client_info = get_client_info(request)

    # Components for fingerprinting
    components = [
        client_info.get("user_agent", ""),
        client_info.get("accept_language", ""),
        client_info.get("accept_encoding", ""),
        str(client_info.get("is_mobile", False)),
        str(client_info.get("is_tablet", False)),
    ]

    # Create hash
    fingerprint_string = "|".join(components)
    return hashlib.sha256(fingerprint_string.encode()).hexdigest()[:16]


def is_suspicious_login(user, request) -> Dict[str, Any]:
    """
    Check for suspicious login patterns.

    Args:
        user: User object
        request: HTTP request

    Returns:
        Dict with suspicion analysis
    """
    suspicion_factors = []
    risk_score = 0

    client_info = get_client_info(request)

    # Check for unusual IP
    from .models import UserAuditLog

    recent_ips = (
        UserAuditLog.objects.filter(
            user=user, action="login", description__icontains="Successful"
        )
        .values_list("ip_address", flat=True)
        .distinct()[:10]
    )

    current_ip = client_info.get("ip_address")
    if current_ip not in recent_ips:
        suspicion_factors.append("New IP address")
        risk_score += 2

    # Check for unusual user agent
    recent_agents = (
        UserAuditLog.objects.filter(
            user=user, action="login", description__icontains="Successful"
        )
        .values_list("user_agent", flat=True)
        .distinct()[:5]
    )

    current_agent = client_info.get("user_agent")
    if current_agent not in recent_agents:
        suspicion_factors.append("New device/browser")
        risk_score += 1

    # Check login frequency
    from django.utils import timezone
    from datetime import timedelta

    recent_logins = UserAuditLog.objects.filter(
        user=user, action="login", timestamp__gte=timezone.now() - timedelta(hours=1)
    ).count()

    if recent_logins > 5:
        suspicion_factors.append("Frequent login attempts")
        risk_score += 3

    return {
        "is_suspicious": risk_score >= 3,
        "risk_score": risk_score,
        "factors": suspicion_factors,
        "recommendation": (
            "require_2fa"
            if risk_score >= 5
            else "monitor" if risk_score >= 3 else "allow"
        ),
    }


def generate_otp(length: int = 6) -> str:
    """
    Generate a random OTP.

    Args:
        length: Length of OTP

    Returns:
        OTP string
    """
    import secrets

    return "".join([str(secrets.randbelow(10)) for _ in range(length)])


def mask_identifier(identifier: str, identifier_type: str) -> str:
    """
    Mask identifier for display purposes (privacy).

    Args:
        identifier: Identifier to mask
        identifier_type: Type of identifier

    Returns:
        Masked identifier
    """
    if not identifier:
        return identifier

    if identifier_type == "email":
        username, domain = identifier.split("@", 1)
        if len(username) <= 2:
            masked_username = "*" * len(username)
        else:
            masked_username = username[0] + "*" * (len(username) - 2) + username[-1]
        return f"{masked_username}@{domain}"

    elif identifier_type == "phone":
        if len(identifier) <= 4:
            return "*" * len(identifier)
        return identifier[:2] + "*" * (len(identifier) - 4) + identifier[-2:]

    elif identifier_type == "admission_number":
        if len(identifier) <= 4:
            return identifier[:2] + "*" * (len(identifier) - 2)
        return identifier[:3] + "*" * (len(identifier) - 6) + identifier[-3:]

    elif identifier_type == "username":
        if len(identifier) <= 4:
            return identifier[0] + "*" * (len(identifier) - 1)
        return identifier[:2] + "*" * (len(identifier) - 4) + identifier[-2:]

    return identifier


def generate_verification_token() -> str:
    """
    Generate a secure verification token.

    Returns:
        Generated token
    """
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """
    Hash a token for secure storage.

    Args:
        token: Token to hash

    Returns:
        Hashed token
    """
    return hashlib.sha256(token.encode()).hexdigest()


def generate_api_key() -> str:
    """
    Generate a secure API key.

    Returns:
        Generated API key
    """
    return secrets.token_urlsafe(32)


def mask_email(email: str) -> str:
    """
    Mask email address for privacy.

    Args:
        email: Email to mask

    Returns:
        Masked email
    """
    if "@" not in email:
        return email

    local, domain = email.split("@", 1)

    if len(local) <= 2:
        masked_local = local[0] + "*"
    else:
        masked_local = local[0] + "*" * (len(local) - 2) + local[-1]

    return f"{masked_local}@{domain}"


def mask_phone(phone: str) -> str:
    """
    Mask phone number for privacy.

    Args:
        phone: Phone number to mask

    Returns:
        Masked phone number
    """
    if len(phone) <= 4:
        return phone

    return phone[:2] + "*" * (len(phone) - 4) + phone[-2:]


def get_user_display_name(user: User, include_admission: bool = False) -> str:
    """
    Get appropriate display name for user.

    Args:
        user: User object
        include_admission: Whether to include admission number for students

    Returns:
        Display name
    """
    display_name = ""

    if user.first_name and user.last_name:
        display_name = f"{user.first_name} {user.last_name}"
    elif user.first_name:
        display_name = user.first_name
    elif user.last_name:
        display_name = user.last_name
    else:
        display_name = user.username

    # Add admission number for students if requested
    if include_admission and user.is_student:
        try:
            from src.students.models import Student

            student = Student.objects.filter(user=user).first()
            if student and student.admission_number:
                display_name += f" ({student.admission_number})"
        except ImportError:
            pass

    return display_name


def calculate_password_expiry(days: int = 90) -> datetime:
    """
    Calculate password expiry date.

    Args:
        days: Number of days until expiry

    Returns:
        Expiry datetime
    """
    return timezone.now() + timedelta(days=days)


def is_password_expired(user: User, max_age_days: int = 90) -> bool:
    """
    Check if user's password has expired.

    Args:
        user: User to check
        max_age_days: Maximum password age in days

    Returns:
        True if password is expired
    """
    if not hasattr(user, "password_changed_at") or not user.password_changed_at:
        return True

    expiry_date = user.password_changed_at + timedelta(days=max_age_days)
    return timezone.now() > expiry_date


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename for safe storage.

    Args:
        filename: Original filename

    Returns:
        Sanitized filename
    """
    # Remove path components
    filename = filename.split("/")[-1].split("\\")[-1]

    # Replace unsafe characters
    unsafe_chars = '<>:"/\\|?*'
    for char in unsafe_chars:
        filename = filename.replace(char, "_")

    # Limit length
    name, ext = filename.rsplit(".", 1) if "." in filename else (filename, "")
    if len(name) > 100:
        name = name[:100]

    return f"{name}.{ext}" if ext else name


def get_client_info(request):
    """
    Simple version of get_client_info to avoid errors.
    Extract basic client information from request.
    """
    if not request:
        return {
            "ip_address": "unknown",
            "user_agent": "unknown",
            "browser": "unknown",
            "os": "unknown",
            "is_mobile": False,
            "is_tablet": False,
            "is_pc": True,
        }

    try:
        # Get IP address
        ip_address = get_client_ip(request)

        # Get user agent
        user_agent = request.META.get("HTTP_USER_AGENT", "unknown")

        return {
            "ip_address": ip_address,
            "user_agent": user_agent,
            "browser": "unknown",
            "os": "unknown",
            "is_mobile": False,
            "is_tablet": False,
            "is_pc": True,
            "forwarded_for": request.META.get("HTTP_X_FORWARDED_FOR", ""),
            "host": request.META.get("HTTP_HOST", ""),
            "referer": request.META.get("HTTP_REFERER", ""),
            "session_key": getattr(request.session, "session_key", None),
            "request_method": request.method,
            "request_path": request.path,
            "is_secure": request.is_secure(),
        }
    except Exception as e:
        logger.error(f"Error getting client info: {str(e)}")
        return {
            "ip_address": "unknown",
            "user_agent": "unknown",
            "browser": "unknown",
            "os": "unknown",
            "is_mobile": False,
        }


def get_client_ip(request):
    """
    Simple version to get client IP address.
    """
    try:
        # Check for IP in various headers (proxy environments)
        ip_headers = [
            "HTTP_X_FORWARDED_FOR",
            "HTTP_X_REAL_IP",
            "REMOTE_ADDR",
        ]

        for header in ip_headers:
            ip = request.META.get(header)
            if ip:
                # Handle comma-separated IPs (X-Forwarded-For)
                if "," in ip:
                    ip = ip.split(",")[0].strip()

                # Basic validation
                if ip and ip != "unknown":
                    return ip

        return "unknown"
    except Exception as e:
        logger.error(f"Error getting client IP: {str(e)}")
        return "unknown"


def is_valid_ip(ip: str) -> bool:
    """
    Basic IP address validation.

    Args:
        ip: IP address string to validate

    Returns:
        True if valid IP, False otherwise
    """
    if not ip or ip in ["unknown", "localhost", "127.0.0.1"]:
        return False

    # IPv4 pattern
    ipv4_pattern = r"^(\d{1,3}\.){3}\d{1,3}$"
    if re.match(ipv4_pattern, ip):
        parts = ip.split(".")
        return all(0 <= int(part) <= 255 for part in parts)

    # IPv6 basic check
    if ":" in ip and len(ip) > 2:
        return True

    return False


def normalize_identifier(identifier: str, identifier_type: str) -> str:
    """
    Normalize identifier based on its type.

    Args:
        identifier: The identifier to normalize
        identifier_type: Type of identifier ('email', 'phone', 'username', 'admission_number')

    Returns:
        Normalized identifier
    """
    if not identifier:
        return identifier

    identifier = identifier.strip()

    if identifier_type == "email":
        return identifier.lower()
    elif identifier_type == "phone":
        return normalize_phone_number(identifier)
    elif identifier_type == "admission_number":
        return identifier.upper()
    elif identifier_type == "username":
        return identifier.lower()

    return identifier


def normalize_phone_number(phone: str) -> str:
    """
    Normalize phone number for consistent storage and comparison.

    Args:
        phone: Phone number to normalize

    Returns:
        Normalized phone number
    """
    if not phone:
        return phone

    # Remove all non-digit characters except +
    clean_phone = re.sub(r"[^\d\+]", "", phone)

    # Get phone settings
    phone_settings = getattr(settings, "UNIFIED_AUTH_SETTINGS", {}).get(
        "PHONE_NUMBER_SETTINGS", {}
    )
    default_country_code = phone_settings.get("DEFAULT_COUNTRY_CODE", "+1")

    # Handle different formats
    if clean_phone.startswith("+"):
        return clean_phone
    elif clean_phone.startswith("0") and len(clean_phone) == 11:
        # Convert local format to international
        return f"{default_country_code}{clean_phone[1:]}"
    elif len(clean_phone) == 10:
        # Add country code for 10-digit numbers
        return f"{default_country_code}{clean_phone}"

    return clean_phone


def validate_identifier_format(identifier: str, identifier_type: str) -> Dict[str, Any]:
    """
    Validate identifier format and provide feedback.

    Args:
        identifier: Identifier to validate
        identifier_type: Type of identifier

    Returns:
        Dict with validation results
    """
    from .services.authentication_service import UnifiedAuthenticationService

    result = {"valid": False, "message": "", "suggestions": []}

    if not identifier:
        result["message"] = "Identifier cannot be empty"
        return result

    if identifier_type == "email":
        from django.core.validators import validate_email
        from django.core.exceptions import ValidationError

        try:
            validate_email(identifier)
            result["valid"] = True
            result["message"] = "Valid email format"
        except ValidationError:
            result["message"] = "Invalid email format"
            result["suggestions"] = [
                "Check for typos",
                "Ensure @ symbol is present",
                "Include domain extension",
            ]

    elif identifier_type == "phone":
        if UnifiedAuthenticationService._is_phone_number(identifier):
            result["valid"] = True
            result["message"] = "Valid phone number format"
        else:
            result["message"] = "Invalid phone number format"
            result["suggestions"] = [
                "Use 10-15 digits",
                "Include country code if international",
                "Remove letters and symbols",
            ]

    elif identifier_type == "admission_number":
        if UnifiedAuthenticationService._is_admission_number(identifier):
            result["valid"] = True
            result["message"] = "Valid admission number format"
        else:
            result["message"] = "Invalid admission number format"
            result["suggestions"] = [
                "Check with school administration",
                "Ensure correct format (e.g., STU-2024-123)",
            ]

    elif identifier_type == "username":
        if len(identifier) >= 3 and re.match(r"^[a-zA-Z0-9_]+$", identifier):
            result["valid"] = True
            result["message"] = "Valid username format"
        else:
            result["message"] = "Invalid username format"
            result["suggestions"] = [
                "Use only letters, numbers, and underscores",
                "Minimum 3 characters",
            ]

    return result


def parse_user_agent(user_agent: str) -> Dict[str, str]:
    """
    Parse user agent string to extract browser, OS, and device information.

    Args:
        user_agent: User agent string

    Returns:
        Dictionary with parsed info
    """
    user_agent = user_agent.lower()

    # Detect browser
    browser = "Unknown"
    browser_version = ""

    if "edg" in user_agent:
        browser = "Edge"
        match = re.search(r"edg/([\d.]+)", user_agent)
        browser_version = match.group(1) if match else ""
    elif "chrome" in user_agent:
        browser = "Chrome"
        match = re.search(r"chrome/([\d.]+)", user_agent)
        browser_version = match.group(1) if match else ""
    elif "firefox" in user_agent:
        browser = "Firefox"
        match = re.search(r"firefox/([\d.]+)", user_agent)
        browser_version = match.group(1) if match else ""
    elif "safari" in user_agent and "chrome" not in user_agent:
        browser = "Safari"
        match = re.search(r"version/([\d.]+)", user_agent)
        browser_version = match.group(1) if match else ""
    elif "opera" in user_agent:
        browser = "Opera"
        match = re.search(r"opera/([\d.]+)", user_agent)
        browser_version = match.group(1) if match else ""

    # Detect OS
    os_name = "Unknown"
    os_version = ""

    if "windows nt" in user_agent:
        os_name = "Windows"
        match = re.search(r"windows nt ([\d.]+)", user_agent)
        if match:
            version_map = {
                "10.0": "10",
                "6.3": "8.1",
                "6.2": "8",
                "6.1": "7",
                "6.0": "Vista",
                "5.1": "XP",
            }
            os_version = version_map.get(match.group(1), match.group(1))
    elif "macintosh" in user_agent or "mac os" in user_agent:
        os_name = "macOS"
        match = re.search(r"mac os x ([\d_]+)", user_agent)
        os_version = match.group(1).replace("_", ".") if match else ""
    elif "linux" in user_agent:
        os_name = "Linux"
    elif "android" in user_agent:
        os_name = "Android"
        match = re.search(r"android ([\d.]+)", user_agent)
        os_version = match.group(1) if match else ""
    elif "iphone" in user_agent or "ipad" in user_agent:
        os_name = "iOS"
        match = re.search(r"os ([\d_]+)", user_agent)
        os_version = match.group(1).replace("_", ".") if match else ""

    # Detect device type
    device_type = "desktop"
    if any(mobile in user_agent for mobile in ["mobile", "android", "iphone"]):
        device_type = "mobile"
    elif "ipad" in user_agent or "tablet" in user_agent:
        device_type = "tablet"

    return {
        "browser": browser,
        "browser_version": browser_version,
        "os": os_name,
        "os_version": os_version,
        "device_type": device_type,
    }


def get_geographic_info(ip_address: str) -> Dict[str, str]:
    """
    Get geographic information from IP address.
    This is a placeholder - you would integrate with a service like GeoIP2.

    Args:
        ip_address: IP address to lookup

    Returns:
        Dictionary with geographic info
    """
    # Placeholder implementation
    # In a real implementation, you would use a service like:
    # - MaxMind GeoIP2
    # - ipapi.co
    # - ipgeolocation.io

    return {
        "country": "",
        "city": "",
        "timezone": "",
        "latitude": "",
        "longitude": "",
    }


def format_file_size(size_bytes: int) -> str:
    """
    Format file size in human-readable format.

    Args:
        size_bytes: Size in bytes

    Returns:
        Formatted size string
    """
    if size_bytes == 0:
        return "0 B"

    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    size = float(size_bytes)

    while size >= 1024 and i < len(size_names) - 1:
        size /= 1024
        i += 1

    return f"{size:.1f} {size_names[i]}"


def validate_file_upload(
    file,
    max_size_mb: int = 10,
    allowed_types: List[str] = None,
    allowed_extensions: List[str] = None,
) -> Dict[str, Any]:
    """
    Validate uploaded file with comprehensive checks.

    Args:
        file: Uploaded file object
        max_size_mb: Maximum file size in MB
        allowed_types: List of allowed MIME types
        allowed_extensions: List of allowed file extensions

    Returns:
        Validation result dictionary
    """
    result = {
        "is_valid": True,
        "errors": [],
        "warnings": [],
        "file_info": {
            "name": file.name,
            "size": file.size,
            "content_type": getattr(file, "content_type", "unknown"),
            "extension": "",
        },
    }

    # Get file extension
    if "." in file.name:
        extension = file.name.split(".")[-1].lower()
        result["file_info"]["extension"] = extension

    # Check file size
    max_size_bytes = max_size_mb * 1024 * 1024
    if file.size > max_size_bytes:
        result["is_valid"] = False
        result["errors"].append(
            f"File size ({format_file_size(file.size)}) exceeds maximum allowed size ({max_size_mb} MB)"
        )

    # Check MIME type
    if allowed_types:
        content_type = getattr(file, "content_type", "")
        if content_type not in allowed_types:
            result["is_valid"] = False
            result["errors"].append(
                f'File type "{content_type}" is not allowed. Allowed types: {", ".join(allowed_types)}'
            )

    # Check file extension
    if allowed_extensions:
        file_extension = result["file_info"]["extension"]
        if file_extension not in allowed_extensions:
            result["is_valid"] = False
            result["errors"].append(
                f'File extension ".{file_extension}" is not allowed. Allowed extensions: {", ".join(allowed_extensions)}'
            )

    # Additional security checks
    if file.name:
        # Check for potentially dangerous file names
        dangerous_patterns = [r"\.\.", r'[<>:"/\\|?*]', r"^\.|^CON$|^PRN$|^AUX$|^NUL$"]

        for pattern in dangerous_patterns:
            if re.search(pattern, file.name, re.IGNORECASE):
                result["warnings"].append(
                    "File name contains potentially unsafe characters"
                )
                break

    return result


def generate_unique_id(prefix: str = "", length: int = 8) -> str:
    """
    Generate a unique identifier.

    Args:
        prefix: Optional prefix for the ID
        length: Length of the random part

    Returns:
        Generated unique ID
    """
    random_part = "".join(
        secrets.choice(string.ascii_uppercase + string.digits) for _ in range(length)
    )
    return f"{prefix}{random_part}" if prefix else random_part


def time_since(dt: datetime) -> str:
    """
    Return human-readable time since the given datetime.

    Args:
        dt: Datetime object

    Returns:
        Human-readable time difference
    """
    now = timezone.now()
    diff = now - dt

    if diff.days > 365:
        years = diff.days // 365
        return f"{years} year{'s' if years != 1 else ''} ago"
    elif diff.days > 30:
        months = diff.days // 30
        return f"{months} month{'s' if months != 1 else ''} ago"
    elif diff.days > 0:
        return f"{diff.days} day{'s' if diff.days != 1 else ''} ago"
    elif diff.seconds > 3600:
        hours = diff.seconds // 3600
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    elif diff.seconds > 60:
        minutes = diff.seconds // 60
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    else:
        return "Just now"


def cache_key_user_permissions(user_id: int) -> str:
    """Generate cache key for user permissions."""
    return f"user_permissions_{user_id}"


def cache_key_user_roles(user_id: int) -> str:
    """Generate cache key for user roles."""
    return f"user_roles_{user_id}"


def cache_key_otp(user_id: int, purpose: str) -> str:
    """Generate cache key for OTP."""
    return f"otp_{user_id}_{purpose}"


def generate_username_suggestions(
    email: str, first_name: str = "", last_name: str = ""
) -> List[str]:
    """
    Generate username suggestions based on email and name.

    Args:
        email: User's email address
        first_name: User's first name
        last_name: User's last name

    Returns:
        List of username suggestions
    """
    suggestions = []

    # Base from email
    if email:
        email_base = email.split("@")[0]
        suggestions.append(email_base)

    # Base from names
    if first_name and last_name:
        suggestions.extend(
            [
                f"{first_name.lower()}.{last_name.lower()}",
                f"{first_name.lower()}{last_name.lower()}",
                f"{first_name[0].lower()}{last_name.lower()}",
                f"{first_name.lower()}{last_name[0].lower()}",
            ]
        )
    elif first_name:
        suggestions.append(first_name.lower())
    elif last_name:
        suggestions.append(last_name.lower())

    # Clean and filter suggestions
    clean_suggestions = []
    for suggestion in suggestions:
        # Remove special characters
        clean = re.sub(r"[^a-zA-Z0-9_]", "", suggestion)
        if len(clean) >= 3 and clean not in clean_suggestions:
            clean_suggestions.append(clean)

    # Add numbered variations if original suggestions are taken
    final_suggestions = []
    for suggestion in clean_suggestions[:3]:  # Limit to top 3 base suggestions
        if not User.objects.filter(username=suggestion).exists():
            final_suggestions.append(suggestion)
        else:
            # Try numbered variations
            for i in range(1, 100):
                numbered = f"{suggestion}{i}"
                if not User.objects.filter(username=numbered).exists():
                    final_suggestions.append(numbered)
                    break

        if len(final_suggestions) >= 5:  # Limit total suggestions
            break

    return final_suggestions


def check_password_breach(password: str) -> bool:
    """
    Check if password has been found in data breaches.
    This is a placeholder - you would integrate with a service like HaveIBeenPwned.

    Args:
        password: Password to check

    Returns:
        True if password is breached, False otherwise
    """
    # Placeholder implementation
    # In a real implementation, you would use HaveIBeenPwned API:
    # https://haveibeenpwned.com/API/v3#PwnedPasswords

    # Hash the password with SHA-1
    sha1_hash = hashlib.sha1(password.encode()).hexdigest().upper()

    # In practice, you would send first 5 characters to the API
    # and check if the remaining hash is in the response

    return False  # Placeholder return


def generate_backup_codes(count: int = 10) -> List[str]:
    """
    Generate backup codes for two-factor authentication.

    Args:
        count: Number of backup codes to generate

    Returns:
        List of backup codes
    """
    codes = []
    for _ in range(count):
        # Generate 8-character alphanumeric codes
        code = "".join(
            secrets.choice(string.ascii_uppercase + string.digits) for _ in range(8)
        )
        # Format as XXXX-XXXX for readability
        formatted_code = f"{code[:4]}-{code[4:]}"
        codes.append(formatted_code)

    return codes


def validate_backup_code(code: str, stored_codes: List[str]) -> Tuple[bool, List[str]]:
    """
    Validate backup code and remove it from the list.

    Args:
        code: Code to validate
        stored_codes: List of stored backup codes

    Returns:
        Tuple of (is_valid, remaining_codes)
    """
    # Normalize the code
    normalized_code = code.upper().replace("-", "").replace(" ", "")

    for i, stored_code in enumerate(stored_codes):
        normalized_stored = stored_code.upper().replace("-", "").replace(" ", "")
        if normalized_code == normalized_stored:
            # Remove the used code
            remaining_codes = stored_codes.copy()
            remaining_codes.pop(i)
            return True, remaining_codes

    return False, stored_codes
