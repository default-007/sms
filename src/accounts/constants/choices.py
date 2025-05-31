# src/accounts/constants/choices.py

from django.utils.translation import gettext_lazy as _

# Gender choices
GENDER_CHOICES = (
    ("M", _("Male")),
    ("F", _("Female")),
    ("O", _("Other")),
    ("P", _("Prefer not to say")),
)

# Account status choices
ACCOUNT_STATUS_CHOICES = (
    ("active", _("Active")),
    ("inactive", _("Inactive")),
    ("pending", _("Pending")),
    ("suspended", _("Suspended")),
    ("locked", _("Locked")),
    ("expired", _("Expired")),
)

# User statuses
USER_STATUS = (
    ("active", _("Active")),
    ("inactive", _("Inactive")),
    ("suspended", _("Suspended")),
    ("locked", _("Locked")),
    ("pending_verification", _("Pending Verification")),
)

# Timezone choices (common ones)
TIMEZONE_CHOICES = (
    ("UTC", _("UTC")),
    ("America/New_York", _("Eastern Time (US & Canada)")),
    ("America/Chicago", _("Central Time (US & Canada)")),
    ("America/Denver", _("Mountain Time (US & Canada)")),
    ("America/Los_Angeles", _("Pacific Time (US & Canada)")),
    ("Europe/London", _("London")),
    ("Europe/Paris", _("Paris")),
    ("Europe/Berlin", _("Berlin")),
    ("Asia/Tokyo", _("Tokyo")),
    ("Asia/Shanghai", _("Shanghai")),
    ("Asia/Kolkata", _("Kolkata")),
    ("Australia/Sydney", _("Sydney")),
)

# Language choices
LANGUAGE_CHOICES = (
    ("en", _("English")),
    ("es", _("Spanish")),
    ("fr", _("French")),
    ("de", _("German")),
    ("it", _("Italian")),
    ("pt", _("Portuguese")),
    ("ru", _("Russian")),
    ("zh", _("Chinese (Simplified)")),
    ("ja", _("Japanese")),
    ("ko", _("Korean")),
    ("ar", _("Arabic")),
    ("hi", _("Hindi")),
)

# Notification types
NOTIFICATION_TYPES = (
    ("email", _("Email")),
    ("sms", _("SMS")),
    ("push", _("Push Notification")),
    ("in_app", _("In-App Notification")),
)

# Audit action choices
AUDIT_ACTION_CHOICES = (
    # Authentication actions
    ("login", _("Login")),
    ("logout", _("Logout")),
    ("login_failed", _("Login Failed")),
    # Account actions
    ("create", _("Create")),
    ("update", _("Update")),
    ("delete", _("Delete")),
    ("activate", _("Activate")),
    ("deactivate", _("Deactivate")),
    ("suspend", _("Suspend")),
    ("unsuspend", _("Unsuspend")),
    # Password actions
    ("password_change", _("Password Change")),
    ("password_reset", _("Password Reset")),
    ("password_expired", _("Password Expired")),
    # Role actions
    ("role_assign", _("Role Assigned")),
    ("role_remove", _("Role Removed")),
    ("role_create", _("Role Created")),
    ("role_update", _("Role Updated")),
    ("role_delete", _("Role Deleted")),
    # Security actions
    ("account_lock", _("Account Locked")),
    ("account_unlock", _("Account Unlocked")),
    ("2fa_enable", _("Two-Factor Enabled")),
    ("2fa_disable", _("Two-Factor Disabled")),
    ("2fa_verified", _("Two-Factor Verified")),
    ("2fa_backup_used", _("Two-Factor Backup Used")),
    # Verification actions
    ("email_verification_send", _("Email Verification Sent")),
    ("email_verified", _("Email Verified")),
    ("email_verification_failed", _("Email Verification Failed")),
    ("phone_verification_send", _("Phone Verification Sent")),
    ("phone_verified", _("Phone Verified")),
    ("phone_verification_failed", _("Phone Verification Failed")),
    # Session actions
    ("session_created", _("Session Created")),
    ("session_terminated", _("Session Terminated")),
    ("session_expired", _("Session Expired")),
    ("session_ip_change", _("Session IP Changed")),
    ("session_ua_change", _("Session User Agent Changed")),
    # Communication actions
    ("email_send", _("Email Sent")),
    ("email_send_failed", _("Email Send Failed")),
    ("sms_send", _("SMS Sent")),
    ("sms_send_failed", _("SMS Send Failed")),
    ("push_send", _("Push Notification Sent")),
    ("notification_preferences_update", _("Notification Preferences Updated")),
    # Data actions
    ("export", _("Data Export")),
    ("import", _("Data Import")),
    ("bulk_action", _("Bulk Action")),
    ("profile_update", _("Profile Update")),
    ("profile_view", _("Profile View")),
    # Security monitoring
    ("security_alert", _("Security Alert")),
    ("suspicious_activity", _("Suspicious Activity")),
    ("rate_limit_exceeded", _("Rate Limit Exceeded")),
    # Administrative actions
    ("system_maintenance", _("System Maintenance")),
    ("backup_created", _("Backup Created")),
    ("backup_restored", _("Backup Restored")),
)

# Verification types
VERIFICATION_TYPES = (
    ("email", _("Email Verification")),
    ("phone", _("Phone Verification")),
    ("email_change", _("Email Change Verification")),
    ("phone_change", _("Phone Change Verification")),
    ("password_reset", _("Password Reset Verification")),
    ("account_activation", _("Account Activation")),
    ("two_factor_setup", _("Two-Factor Setup")),
)

# Session status choices
SESSION_STATUS_CHOICES = (
    ("active", _("Active")),
    ("inactive", _("Inactive")),
    ("expired", _("Expired")),
    ("terminated", _("Terminated")),
    ("suspicious", _("Suspicious")),
)

# Device type choices
DEVICE_TYPE_CHOICES = (
    ("desktop", _("Desktop")),
    ("mobile", _("Mobile")),
    ("tablet", _("Tablet")),
    ("unknown", _("Unknown")),
)

# Browser choices
BROWSER_CHOICES = (
    ("chrome", _("Chrome")),
    ("firefox", _("Firefox")),
    ("safari", _("Safari")),
    ("edge", _("Edge")),
    ("opera", _("Opera")),
    ("ie", _("Internet Explorer")),
    ("other", _("Other")),
)

# Operating system choices
OS_CHOICES = (
    ("windows", _("Windows")),
    ("macos", _("macOS")),
    ("linux", _("Linux")),
    ("android", _("Android")),
    ("ios", _("iOS")),
    ("other", _("Other")),
)

# Security severity levels
SEVERITY_CHOICES = (
    ("low", _("Low")),
    ("medium", _("Medium")),
    ("high", _("High")),
    ("critical", _("Critical")),
)

# Risk levels
RISK_LEVEL_CHOICES = (
    ("minimal", _("Minimal")),
    ("low", _("Low")),
    ("medium", _("Medium")),
    ("high", _("High")),
    ("critical", _("Critical")),
)

# Authentication methods
AUTH_METHOD_CHOICES = (
    ("password", _("Password")),
    ("two_factor", _("Two-Factor Authentication")),
    ("social_login", _("Social Login")),
    ("sso", _("Single Sign-On")),
    ("api_key", _("API Key")),
)

# Notification priority levels
NOTIFICATION_PRIORITY_CHOICES = (
    ("low", _("Low")),
    ("normal", _("Normal")),
    ("high", _("High")),
    ("urgent", _("Urgent")),
)

# Analytics time periods
TIME_PERIOD_CHOICES = (
    ("1h", _("Last Hour")),
    ("24h", _("Last 24 Hours")),
    ("7d", _("Last 7 Days")),
    ("30d", _("Last 30 Days")),
    ("90d", _("Last 90 Days")),
    ("1y", _("Last Year")),
    ("custom", _("Custom Range")),
)

# Report types
REPORT_TYPE_CHOICES = (
    ("user_activity", _("User Activity")),
    ("security_audit", _("Security Audit")),
    ("login_analytics", _("Login Analytics")),
    ("role_distribution", _("Role Distribution")),
    ("verification_stats", _("Verification Statistics")),
    ("session_analytics", _("Session Analytics")),
    ("performance_metrics", _("Performance Metrics")),
)

# Education levels
EDUCATION_LEVEL_CHOICES = (
    ("high_school", _("High School")),
    ("bachelor", _("Bachelor's Degree")),
    ("master", _("Master's Degree")),
    ("phd", _("PhD")),
    ("certificate", _("Certificate")),
    ("diploma", _("Diploma")),
    ("other", _("Other")),
)

# Relationship types (for emergency contacts, parent relations, etc.)
RELATIONSHIP_CHOICES = (
    ("parent", _("Parent")),
    ("guardian", _("Guardian")),
    ("spouse", _("Spouse")),
    ("sibling", _("Sibling")),
    ("friend", _("Friend")),
    ("colleague", _("Colleague")),
    ("other", _("Other")),
)

# File type choices for uploads
FILE_TYPE_CHOICES = (
    ("image", _("Image")),
    ("document", _("Document")),
    ("video", _("Video")),
    ("audio", _("Audio")),
    ("archive", _("Archive")),
    ("other", _("Other")),
)

# Import/Export formats
IMPORT_EXPORT_FORMAT_CHOICES = (
    ("csv", _("CSV")),
    ("xlsx", _("Excel")),
    ("json", _("JSON")),
    ("xml", _("XML")),
    ("pdf", _("PDF")),
)

# Cache keys (for consistency)
CACHE_KEY_PATTERNS = {
    "user_permissions": "user_permissions_{user_id}",
    "user_roles": "user_roles_{user_id}",
    "user_stats": "user_stats_{user_id}",
    "role_stats": "role_stats_{role_id}",
    "session_data": "session_data_{session_key}",
    "security_token": "security_token_{token_hash}",
    "otp": "otp_{user_id}_{purpose}",
    "rate_limit": "rate_limit_{identifier}_{action}",
    "verification_cooldown": "{type}_verification_cooldown_{user_id}",
    "analytics": "analytics_{report_type}_{params_hash}",
}

# Default values
DEFAULT_VALUES = {
    "password_length": 12,
    "otp_length": 6,
    "session_timeout": 30,  # minutes
    "lockout_duration": 30,  # minutes
    "max_login_attempts": 5,
    "password_expiry_days": 90,
    "verification_expiry_minutes": 10,
    "rate_limit_window": 300,  # seconds
    "cache_timeout": 3600,  # seconds
    "backup_codes_count": 10,
    "max_concurrent_sessions": 5,
    "analytics_retention_days": 365,
    "audit_log_retention_days": 730,
}
