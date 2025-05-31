# src/accounts/exceptions.py

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


class AccountsBaseException(Exception):
    """Base exception for accounts module."""

    def __init__(self, message: str = None, code: str = None, extra_data: dict = None):
        self.message = message or "An error occurred in the accounts module"
        self.code = code or "ACCOUNTS_ERROR"
        self.extra_data = extra_data or {}
        super().__init__(self.message)


class AuthenticationError(AccountsBaseException):
    """Raised when authentication fails."""

    def __init__(self, message: str = None, code: str = None, **kwargs):
        super().__init__(
            message or _("Authentication failed"),
            code or "AUTHENTICATION_ERROR",
            kwargs,
        )


class InvalidCredentialsError(AuthenticationError):
    """Raised when login credentials are invalid."""

    def __init__(self, identifier: str = None, **kwargs):
        message = _("Invalid credentials provided")
        if identifier:
            message = _("Invalid credentials for {}").format(identifier)

        super().__init__(
            message, "INVALID_CREDENTIALS", identifier=identifier, **kwargs
        )


class AccountLockedError(AuthenticationError):
    """Raised when account is locked due to multiple failed attempts."""

    def __init__(self, username: str = None, lockout_duration: int = None, **kwargs):
        if username and lockout_duration:
            message = _("Account {} is locked for {} minutes").format(
                username, lockout_duration
            )
        elif username:
            message = _("Account {} is locked").format(username)
        else:
            message = _("Account is locked")

        super().__init__(
            message,
            "ACCOUNT_LOCKED",
            username=username,
            lockout_duration=lockout_duration,
            **kwargs,
        )


class AccountInactiveError(AuthenticationError):
    """Raised when account is inactive."""

    def __init__(self, username: str = None, **kwargs):
        message = _("Account is inactive")
        if username:
            message = _("Account {} is inactive").format(username)

        super().__init__(message, "ACCOUNT_INACTIVE", username=username, **kwargs)


class UserNotFoundError(AuthenticationError):
    """Raised when user is not found."""

    def __init__(self, identifier: str = None, **kwargs):
        message = _("User not found")
        if identifier:
            message = _("User not found: {}").format(identifier)

        super().__init__(message, "USER_NOT_FOUND", identifier=identifier, **kwargs)


class PasswordError(AccountsBaseException):
    """Base class for password-related errors."""

    pass


class WeakPasswordError(PasswordError):
    """Raised when password doesn't meet strength requirements."""

    def __init__(self, feedback: list = None, score: int = None, **kwargs):
        message = _("Password is too weak")
        if feedback:
            message = _("Password is too weak: {}").format("; ".join(feedback))

        super().__init__(
            message, "WEAK_PASSWORD", feedback=feedback, score=score, **kwargs
        )


class PasswordExpiredError(PasswordError):
    """Raised when password has expired."""

    def __init__(self, expiry_date=None, **kwargs):
        message = _("Password has expired")
        if expiry_date:
            message = _("Password expired on {}").format(
                expiry_date.strftime("%Y-%m-%d")
            )

        super().__init__(message, "PASSWORD_EXPIRED", expiry_date=expiry_date, **kwargs)


class PasswordRecentlyUsedError(PasswordError):
    """Raised when user tries to reuse a recent password."""

    def __init__(self, **kwargs):
        super().__init__(
            _("This password has been used recently"),
            "PASSWORD_RECENTLY_USED",
            **kwargs,
        )


class RoleError(AccountsBaseException):
    """Base class for role-related errors."""

    pass


class RoleNotFoundError(RoleError):
    """Raised when role is not found."""

    def __init__(self, role_name: str = None, **kwargs):
        message = _("Role not found")
        if role_name:
            message = _("Role not found: {}").format(role_name)

        super().__init__(message, "ROLE_NOT_FOUND", role_name=role_name, **kwargs)


class RoleAssignmentError(RoleError):
    """Raised when role assignment fails."""

    def __init__(
        self, username: str = None, role_name: str = None, reason: str = None, **kwargs
    ):
        message = _("Role assignment failed")
        if username and role_name:
            message = _("Failed to assign role {} to user {}").format(
                role_name, username
            )

        if reason:
            message = f"{message}: {reason}"

        super().__init__(
            message,
            "ROLE_ASSIGNMENT_ERROR",
            username=username,
            role_name=role_name,
            reason=reason,
            **kwargs,
        )


class InsufficientPermissionsError(RoleError):
    """Raised when user lacks required permissions."""

    def __init__(self, required_permission: str = None, **kwargs):
        message = _("Insufficient permissions")
        if required_permission:
            message = _("Insufficient permissions: {} required").format(
                required_permission
            )

        super().__init__(
            message,
            "INSUFFICIENT_PERMISSIONS",
            required_permission=required_permission,
            **kwargs,
        )


class SystemRoleError(RoleError):
    """Raised when attempting to modify system roles inappropriately."""

    def __init__(self, role_name: str = None, operation: str = None, **kwargs):
        message = _("Cannot modify system role")
        if role_name and operation:
            message = _("Cannot {} system role {}").format(operation, role_name)

        super().__init__(
            message,
            "SYSTEM_ROLE_ERROR",
            role_name=role_name,
            operation=operation,
            **kwargs,
        )


class VerificationError(AccountsBaseException):
    """Base class for verification-related errors."""

    pass


class VerificationCodeExpiredError(VerificationError):
    """Raised when verification code has expired."""

    def __init__(self, verification_type: str = None, **kwargs):
        message = _("Verification code has expired")
        if verification_type:
            message = _("{} verification code has expired").format(
                verification_type.title()
            )

        super().__init__(
            message,
            "VERIFICATION_CODE_EXPIRED",
            verification_type=verification_type,
            **kwargs,
        )


class InvalidVerificationCodeError(VerificationError):
    """Raised when verification code is invalid."""

    def __init__(
        self, verification_type: str = None, attempts_remaining: int = None, **kwargs
    ):
        message = _("Invalid verification code")
        if verification_type:
            message = _("Invalid {} verification code").format(verification_type)

        super().__init__(
            message,
            "INVALID_VERIFICATION_CODE",
            verification_type=verification_type,
            attempts_remaining=attempts_remaining,
            **kwargs,
        )


class TooManyVerificationAttemptsError(VerificationError):
    """Raised when too many verification attempts are made."""

    def __init__(
        self, verification_type: str = None, cooldown_seconds: int = None, **kwargs
    ):
        message = _("Too many verification attempts")
        if verification_type and cooldown_seconds:
            message = _(
                "Too many {} verification attempts. Try again in {} seconds"
            ).format(verification_type, cooldown_seconds)

        super().__init__(
            message,
            "TOO_MANY_VERIFICATION_ATTEMPTS",
            verification_type=verification_type,
            cooldown_seconds=cooldown_seconds,
            **kwargs,
        )


class VerificationSendError(VerificationError):
    """Raised when verification code cannot be sent."""

    def __init__(self, verification_type: str = None, reason: str = None, **kwargs):
        message = _("Failed to send verification code")
        if verification_type:
            message = _("Failed to send {} verification code").format(verification_type)

        if reason:
            message = f"{message}: {reason}"

        super().__init__(
            message,
            "VERIFICATION_SEND_ERROR",
            verification_type=verification_type,
            reason=reason,
            **kwargs,
        )


class SessionError(AccountsBaseException):
    """Base class for session-related errors."""

    pass


class SessionExpiredError(SessionError):
    """Raised when session has expired."""

    def __init__(self, **kwargs):
        super().__init__(_("Session has expired"), "SESSION_EXPIRED", **kwargs)


class SessionSecurityError(SessionError):
    """Raised when session security is compromised."""

    def __init__(self, reason: str = None, **kwargs):
        message = _("Session security violation")
        if reason:
            message = _("Session security violation: {}").format(reason)

        super().__init__(message, "SESSION_SECURITY_ERROR", reason=reason, **kwargs)


class ConcurrentSessionLimitError(SessionError):
    """Raised when concurrent session limit is exceeded."""

    def __init__(self, limit: int = None, **kwargs):
        message = _("Concurrent session limit exceeded")
        if limit:
            message = _("Maximum {} concurrent sessions allowed").format(limit)

        super().__init__(message, "CONCURRENT_SESSION_LIMIT", limit=limit, **kwargs)


class TwoFactorError(AccountsBaseException):
    """Base class for two-factor authentication errors."""

    pass


class TwoFactorSetupError(TwoFactorError):
    """Raised when 2FA setup fails."""

    def __init__(self, reason: str = None, **kwargs):
        message = _("Two-factor authentication setup failed")
        if reason:
            message = f"{message}: {reason}"

        super().__init__(message, "TWO_FACTOR_SETUP_ERROR", reason=reason, **kwargs)


class InvalidTwoFactorCodeError(TwoFactorError):
    """Raised when 2FA code is invalid."""

    def __init__(self, **kwargs):
        super().__init__(
            _("Invalid two-factor authentication code"),
            "INVALID_TWO_FACTOR_CODE",
            **kwargs,
        )


class TwoFactorRequiredError(TwoFactorError):
    """Raised when 2FA is required but not provided."""

    def __init__(self, **kwargs):
        super().__init__(
            _("Two-factor authentication is required"), "TWO_FACTOR_REQUIRED", **kwargs
        )


class BackupCodeError(TwoFactorError):
    """Raised when backup code operation fails."""

    def __init__(self, reason: str = None, **kwargs):
        message = _("Backup code error")
        if reason:
            message = f"{message}: {reason}"

        super().__init__(message, "BACKUP_CODE_ERROR", reason=reason, **kwargs)


class SecurityError(AccountsBaseException):
    """Base class for security-related errors."""

    pass


class SecurityTokenError(SecurityError):
    """Raised when security token is invalid or expired."""

    def __init__(self, token_type: str = None, reason: str = None, **kwargs):
        message = _("Invalid security token")
        if token_type:
            message = _("Invalid {} token").format(token_type)

        if reason:
            message = f"{message}: {reason}"

        super().__init__(
            message,
            "SECURITY_TOKEN_ERROR",
            token_type=token_type,
            reason=reason,
            **kwargs,
        )


class SuspiciousActivityError(SecurityError):
    """Raised when suspicious activity is detected."""

    def __init__(self, activity_type: str = None, details: dict = None, **kwargs):
        message = _("Suspicious activity detected")
        if activity_type:
            message = _("Suspicious activity detected: {}").format(activity_type)

        super().__init__(
            message,
            "SUSPICIOUS_ACTIVITY",
            activity_type=activity_type,
            details=details or {},
            **kwargs,
        )


class RateLimitError(SecurityError):
    """Raised when rate limit is exceeded."""

    def __init__(self, resource: str = None, reset_time: int = None, **kwargs):
        message = _("Rate limit exceeded")
        if resource:
            message = _("Rate limit exceeded for {}").format(resource)

        if reset_time:
            message = f"{message}. Try again in {reset_time} seconds"

        super().__init__(
            message,
            "RATE_LIMIT_EXCEEDED",
            resource=resource,
            reset_time=reset_time,
            **kwargs,
        )


class ValidationError(AccountsBaseException):
    """Enhanced validation error with additional context."""

    def __init__(self, field: str = None, value=None, message: str = None, **kwargs):
        if not message:
            message = _("Validation failed")
            if field:
                message = _("Validation failed for field: {}").format(field)

        super().__init__(
            message, "VALIDATION_ERROR", field=field, value=value, **kwargs
        )


class ImportError(AccountsBaseException):
    """Base class for import-related errors."""

    pass


class BulkImportError(ImportError):
    """Raised when bulk import fails."""

    def __init__(self, errors: list = None, warnings: list = None, **kwargs):
        message = _("Bulk import failed")
        if errors:
            message = _("Bulk import failed with {} errors").format(len(errors))

        super().__init__(
            message,
            "BULK_IMPORT_ERROR",
            errors=errors or [],
            warnings=warnings or [],
            **kwargs,
        )


class CSVFormatError(ImportError):
    """Raised when CSV format is invalid."""

    def __init__(self, line_number: int = None, error_details: str = None, **kwargs):
        message = _("Invalid CSV format")
        if line_number:
            message = _("Invalid CSV format at line {}").format(line_number)

        if error_details:
            message = f"{message}: {error_details}"

        super().__init__(
            message,
            "CSV_FORMAT_ERROR",
            line_number=line_number,
            error_details=error_details,
            **kwargs,
        )


class ConfigurationError(AccountsBaseException):
    """Raised when configuration is invalid or missing."""

    def __init__(self, setting: str = None, **kwargs):
        message = _("Configuration error")
        if setting:
            message = _("Configuration error: missing or invalid setting '{}'").format(
                setting
            )

        super().__init__(message, "CONFIGURATION_ERROR", setting=setting, **kwargs)


class ServiceUnavailableError(AccountsBaseException):
    """Raised when external service is unavailable."""

    def __init__(self, service: str = None, **kwargs):
        message = _("Service unavailable")
        if service:
            message = _("Service unavailable: {}").format(service)

        super().__init__(message, "SERVICE_UNAVAILABLE", service=service, **kwargs)


# Exception handling utilities
def handle_accounts_exception(exception: Exception) -> dict:
    """
    Convert exception to standardized error response.

    Args:
        exception: Exception to handle

    Returns:
        Dictionary with error information
    """
    if isinstance(exception, AccountsBaseException):
        return {
            "error": True,
            "code": exception.code,
            "message": str(exception.message),
            "extra_data": exception.extra_data,
        }

    # Handle Django validation errors
    elif isinstance(exception, ValidationError):
        return {
            "error": True,
            "code": "VALIDATION_ERROR",
            "message": str(exception),
            "extra_data": {"django_validation_error": True},
        }

    # Handle generic exceptions
    else:
        return {
            "error": True,
            "code": "INTERNAL_ERROR",
            "message": "An unexpected error occurred",
            "extra_data": {"exception_type": type(exception).__name__},
        }


def raise_for_status(response: dict):
    """
    Raise appropriate exception based on response status.

    Args:
        response: Response dictionary with error information

    Raises:
        Appropriate AccountsBaseException subclass
    """
    if not response.get("error"):
        return

    code = response.get("code", "UNKNOWN_ERROR")
    message = response.get("message", "An error occurred")
    extra_data = response.get("extra_data", {})

    # Map error codes to exceptions
    exception_map = {
        "AUTHENTICATION_ERROR": AuthenticationError,
        "INVALID_CREDENTIALS": InvalidCredentialsError,
        "ACCOUNT_LOCKED": AccountLockedError,
        "ACCOUNT_INACTIVE": AccountInactiveError,
        "USER_NOT_FOUND": UserNotFoundError,
        "WEAK_PASSWORD": WeakPasswordError,
        "PASSWORD_EXPIRED": PasswordExpiredError,
        "ROLE_NOT_FOUND": RoleNotFoundError,
        "INSUFFICIENT_PERMISSIONS": InsufficientPermissionsError,
        "VERIFICATION_CODE_EXPIRED": VerificationCodeExpiredError,
        "INVALID_VERIFICATION_CODE": InvalidVerificationCodeError,
        "SESSION_EXPIRED": SessionExpiredError,
        "RATE_LIMIT_EXCEEDED": RateLimitError,
        "VALIDATION_ERROR": ValidationError,
    }

    exception_class = exception_map.get(code, AccountsBaseException)
    raise exception_class(message, code, **extra_data)


# Custom exception middleware helper
class ExceptionHandler:
    """Helper class for handling exceptions in views and services."""

    @staticmethod
    def safe_execute(func, *args, **kwargs):
        """
        Safely execute a function and return standardized response.

        Args:
            func: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments

        Returns:
            Dictionary with result or error information
        """
        try:
            result = func(*args, **kwargs)
            return {"success": True, "result": result}
        except AccountsBaseException as e:
            return handle_accounts_exception(e)
        except Exception as e:
            return handle_accounts_exception(e)

    @staticmethod
    def require_success(response: dict):
        """
        Require response to be successful, raise exception if not.

        Args:
            response: Response dictionary

        Raises:
            Appropriate exception if response indicates error
        """
        if response.get("error"):
            raise_for_status(response)

        return response.get("result")
