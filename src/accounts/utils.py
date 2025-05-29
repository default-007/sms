import hashlib
import secrets
import string
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.text import slugify

User = get_user_model()


def generate_secure_password(
    length: int = 12, include_symbols: bool = True, ensure_complexity: bool = True
) -> str:
    """
    Generate a secure password with specified criteria.

    Args:
        length: Password length (minimum 8)
        include_symbols: Whether to include special characters
        ensure_complexity: Ensure password meets complexity requirements

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


def generate_username(first_name: str, last_name: str, email: str = None) -> str:
    """
    Generate a unique username based on name or email.

    Args:
        first_name: User's first name
        last_name: User's last name
        email: User's email (optional)

    Returns:
        Generated username
    """
    # Try different username formats
    base_usernames = []

    if first_name and last_name:
        base_usernames.extend(
            [
                f"{first_name.lower()}.{last_name.lower()}",
                f"{first_name.lower()}{last_name.lower()}",
                f"{first_name[0].lower()}{last_name.lower()}",
                f"{first_name.lower()}{last_name[0].lower()}",
            ]
        )

    if email:
        email_base = email.split("@")[0]
        base_usernames.append(email_base.lower())

    # Clean usernames (remove special characters)
    clean_usernames = []
    for username in base_usernames:
        clean = slugify(username).replace("-", "")
        if clean and len(clean) >= 3:
            clean_usernames.append(clean)

    # Find available username
    for base in clean_usernames:
        if not User.objects.filter(username=base).exists():
            return base

        # Try with numbers
        for i in range(1, 100):
            candidate = f"{base}{i}"
            if not User.objects.filter(username=candidate).exists():
                return candidate

    # Fallback: generate random username
    random_suffix = "".join(secrets.choice(string.digits) for _ in range(6))
    return f"user{random_suffix}"


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
        },
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
        result["score"] += 20
    else:
        result["feedback"].append(
            "Password should contain at least one uppercase letter"
        )

    # Check for lowercase letters
    if any(c.islower() for c in password):
        result["requirements"]["lowercase"] = True
        result["score"] += 20
    else:
        result["feedback"].append(
            "Password should contain at least one lowercase letter"
        )

    # Check for digits
    if any(c.isdigit() for c in password):
        result["requirements"]["digits"] = True
        result["score"] += 20
    else:
        result["feedback"].append("Password should contain at least one digit")

    # Check for symbols
    if any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
        result["requirements"]["symbols"] = True
        result["score"] += 20
    else:
        result["feedback"].append(
            "Password should contain at least one special character"
        )

    # Additional strength checks
    if len(password) >= 12:
        result["score"] += 10
    if len(password) >= 16:
        result["score"] += 10

    # Check for common patterns
    if password.lower() in ["password", "123456", "qwerty", "abc123"]:
        result["is_valid"] = False
        result["score"] = 0
        result["feedback"] = ["Password is too common"]

    # Set minimum score for validity
    if result["score"] < 60:
        result["is_valid"] = False

    return result


def send_notification_email(
    user: User, subject: str, template_name: str, context: Dict[str, Any] = None
) -> bool:
    """
    Send notification email to user.

    Args:
        user: User to send email to
        subject: Email subject
        template_name: Email template name
        context: Template context

    Returns:
        True if sent successfully, False otherwise
    """
    try:
        context = context or {}
        context.update(
            {
                "user": user,
                "site_name": getattr(settings, "SITE_NAME", "School Management System"),
            }
        )

        html_message = render_to_string(template_name, context)

        send_mail(
            subject=subject,
            message="",  # Plain text version
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )
        return True
    except Exception as e:
        import logging

        logger = logging.getLogger(__name__)
        logger.error(f"Failed to send email to {user.email}: {str(e)}")
        return False


def generate_otp(length: int = 6) -> str:
    """
    Generate a random OTP (One-Time Password).

    Args:
        length: OTP length

    Returns:
        Generated OTP
    """
    return "".join(secrets.choice(string.digits) for _ in range(length))


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


def get_user_display_name(user: User) -> str:
    """
    Get appropriate display name for user.

    Args:
        user: User object

    Returns:
        Display name
    """
    if user.first_name and user.last_name:
        return f"{user.first_name} {user.last_name}"
    elif user.first_name:
        return user.first_name
    elif user.last_name:
        return user.last_name
    else:
        return user.username


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


def get_client_info(request) -> Dict[str, str]:
    """
    Extract client information from request.

    Args:
        request: Django request object

    Returns:
        Dictionary with client info
    """
    # Get IP address
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        ip_address = x_forwarded_for.split(",")[0].strip()
    else:
        ip_address = request.META.get("REMOTE_ADDR", "")

    # Get user agent
    user_agent = request.META.get("HTTP_USER_AGENT", "")

    # Parse user agent for browser and OS info
    browser_info = parse_user_agent(user_agent)

    return {
        "ip_address": ip_address,
        "user_agent": user_agent,
        "browser": browser_info.get("browser", "Unknown"),
        "os": browser_info.get("os", "Unknown"),
    }


def parse_user_agent(user_agent: str) -> Dict[str, str]:
    """
    Parse user agent string to extract browser and OS information.

    Args:
        user_agent: User agent string

    Returns:
        Dictionary with browser and OS info
    """
    user_agent = user_agent.lower()

    # Detect browser
    browser = "Unknown"
    if "chrome" in user_agent and "edg" not in user_agent:
        browser = "Chrome"
    elif "firefox" in user_agent:
        browser = "Firefox"
    elif "safari" in user_agent and "chrome" not in user_agent:
        browser = "Safari"
    elif "edg" in user_agent:
        browser = "Edge"
    elif "opera" in user_agent:
        browser = "Opera"

    # Detect OS
    os_name = "Unknown"
    if "windows" in user_agent:
        os_name = "Windows"
    elif "macintosh" in user_agent or "mac os" in user_agent:
        os_name = "macOS"
    elif "linux" in user_agent:
        os_name = "Linux"
    elif "android" in user_agent:
        os_name = "Android"
    elif "iphone" in user_agent or "ipad" in user_agent:
        os_name = "iOS"

    return {
        "browser": browser,
        "os": os_name,
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
    file, max_size_mb: int = 10, allowed_types: List[str] = None
) -> Dict[str, Any]:
    """
    Validate uploaded file.

    Args:
        file: Uploaded file object
        max_size_mb: Maximum file size in MB
        allowed_types: List of allowed file types

    Returns:
        Validation result dictionary
    """
    result = {
        "is_valid": True,
        "errors": [],
        "file_info": {
            "name": file.name,
            "size": file.size,
            "content_type": getattr(file, "content_type", "unknown"),
        },
    }

    # Check file size
    max_size_bytes = max_size_mb * 1024 * 1024
    if file.size > max_size_bytes:
        result["is_valid"] = False
        result["errors"].append(
            f"File size ({format_file_size(file.size)}) exceeds maximum allowed size ({max_size_mb} MB)"
        )

    # Check file type
    if allowed_types:
        file_extension = file.name.split(".")[-1].lower() if "." in file.name else ""
        if file_extension not in allowed_types:
            result["is_valid"] = False
            result["errors"].append(
                f'File type ".{file_extension}" is not allowed. Allowed types: {", ".join(allowed_types)}'
            )

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

    if diff.days > 0:
        return f"{diff.days} day{'s' if diff.days != 1 else ''} ago"
    elif diff.seconds > 3600:
        hours = diff.seconds // 3600
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    elif diff.seconds > 60:
        minutes = diff.seconds // 60
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    else:
        return "Just now"
