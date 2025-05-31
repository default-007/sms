# src/accounts/constants/settings.py

from django.conf import settings
from django.utils.translation import gettext_lazy as _

# Security settings
SECURITY_SETTINGS = {
    "MAX_LOGIN_ATTEMPTS": getattr(settings, "MAX_LOGIN_ATTEMPTS", 5),
    "LOCKOUT_DURATION_MINUTES": getattr(settings, "LOCKOUT_DURATION_MINUTES", 30),
    "PASSWORD_EXPIRY_DAYS": getattr(settings, "PASSWORD_EXPIRY_DAYS", 90),
    "PASSWORD_HISTORY_COUNT": getattr(settings, "PASSWORD_HISTORY_COUNT", 5),
    "PASSWORD_MIN_LENGTH": getattr(settings, "PASSWORD_MIN_LENGTH", 8),
    "PASSWORD_REQUIRE_UPPERCASE": getattr(settings, "PASSWORD_REQUIRE_UPPERCASE", True),
    "PASSWORD_REQUIRE_LOWERCASE": getattr(settings, "PASSWORD_REQUIRE_LOWERCASE", True),
    "PASSWORD_REQUIRE_DIGITS": getattr(settings, "PASSWORD_REQUIRE_DIGITS", True),
    "PASSWORD_REQUIRE_SYMBOLS": getattr(settings, "PASSWORD_REQUIRE_SYMBOLS", True),
    "TWO_FACTOR_ENABLED": getattr(settings, "TWO_FACTOR_ENABLED", True),
    "BACKUP_CODES_COUNT": getattr(settings, "BACKUP_CODES_COUNT", 10),
    "SECURITY_TOKEN_EXPIRY_MINUTES": getattr(
        settings, "SECURITY_TOKEN_EXPIRY_MINUTES", 15
    ),
    "SUSPICIOUS_ACTIVITY_THRESHOLD": getattr(
        settings, "SUSPICIOUS_ACTIVITY_THRESHOLD", 10
    ),
    "IP_WHITELIST_ENABLED": getattr(settings, "IP_WHITELIST_ENABLED", False),
    "IP_BLACKLIST_ENABLED": getattr(settings, "IP_BLACKLIST_ENABLED", True),
    "ENFORCE_HTTPS": getattr(settings, "ENFORCE_HTTPS", True),
    "SESSION_SECURITY_ENABLED": getattr(settings, "SESSION_SECURITY_ENABLED", True),
    "RATE_LIMITING_ENABLED": getattr(settings, "RATE_LIMITING_ENABLED", True),
}

# Authentication settings
AUTHENTICATION_SETTINGS = {
    "ALLOW_EMAIL_LOGIN": getattr(settings, "ALLOW_EMAIL_LOGIN", True),
    "ALLOW_PHONE_LOGIN": getattr(settings, "ALLOW_PHONE_LOGIN", True),
    "ALLOW_USERNAME_LOGIN": getattr(settings, "ALLOW_USERNAME_LOGIN", False),
    "REQUIRE_EMAIL_VERIFICATION": getattr(settings, "REQUIRE_EMAIL_VERIFICATION", True),
    "REQUIRE_PHONE_VERIFICATION": getattr(
        settings, "REQUIRE_PHONE_VERIFICATION", False
    ),
    "AUTO_LOGIN_AFTER_REGISTRATION": getattr(
        settings, "AUTO_LOGIN_AFTER_REGISTRATION", False
    ),
    "LOGIN_REDIRECT_URL": getattr(settings, "LOGIN_REDIRECT_URL", "/dashboard/"),
    "LOGOUT_REDIRECT_URL": getattr(settings, "LOGOUT_REDIRECT_URL", "/"),
    "LOGIN_URL": getattr(settings, "LOGIN_URL", "/accounts/login/"),
    "PASSWORD_RESET_TIMEOUT": getattr(
        settings, "PASSWORD_RESET_TIMEOUT", 3600
    ),  # 1 hour
    "EMAIL_VERIFICATION_REQUIRED_FOR_LOGIN": getattr(
        settings, "EMAIL_VERIFICATION_REQUIRED_FOR_LOGIN", False
    ),
    "PHONE_VERIFICATION_REQUIRED_FOR_LOGIN": getattr(
        settings, "PHONE_VERIFICATION_REQUIRED_FOR_LOGIN", False
    ),
    "SOCIAL_LOGIN_ENABLED": getattr(settings, "SOCIAL_LOGIN_ENABLED", False),
    "SSO_ENABLED": getattr(settings, "SSO_ENABLED", False),
    "API_AUTHENTICATION_ENABLED": getattr(settings, "API_AUTHENTICATION_ENABLED", True),
    "JWT_ACCESS_TOKEN_LIFETIME_MINUTES": getattr(
        settings, "JWT_ACCESS_TOKEN_LIFETIME_MINUTES", 60
    ),
    "JWT_REFRESH_TOKEN_LIFETIME_DAYS": getattr(
        settings, "JWT_REFRESH_TOKEN_LIFETIME_DAYS", 7
    ),
}

# Verification settings
VERIFICATION_SETTINGS = {
    "EMAIL_VERIFICATION_ENABLED": getattr(settings, "EMAIL_VERIFICATION_ENABLED", True),
    "PHONE_VERIFICATION_ENABLED": getattr(settings, "PHONE_VERIFICATION_ENABLED", True),
    "OTP_LENGTH": getattr(settings, "OTP_LENGTH", 6),
    "OTP_EXPIRY_MINUTES": getattr(settings, "OTP_EXPIRY_MINUTES", 10),
    "MAX_VERIFICATION_ATTEMPTS": getattr(settings, "MAX_VERIFICATION_ATTEMPTS", 5),
    "VERIFICATION_COOLDOWN_MINUTES": getattr(
        settings, "VERIFICATION_COOLDOWN_MINUTES", 5
    ),
    "DAILY_EMAIL_VERIFICATION_LIMIT": getattr(
        settings, "DAILY_EMAIL_VERIFICATION_LIMIT", 10
    ),
    "DAILY_SMS_VERIFICATION_LIMIT": getattr(
        settings, "DAILY_SMS_VERIFICATION_LIMIT", 5
    ),
    "EMAIL_VERIFICATION_TEMPLATE": getattr(
        settings,
        "EMAIL_VERIFICATION_TEMPLATE",
        "accounts/emails/email_verification.html",
    ),
    "PHONE_VERIFICATION_TEMPLATE": getattr(
        settings,
        "PHONE_VERIFICATION_TEMPLATE",
        "accounts/emails/phone_verification.html",
    ),
    "AUTO_VERIFY_ADMIN_EMAILS": getattr(settings, "AUTO_VERIFY_ADMIN_EMAILS", True),
    "VERIFICATION_SUCCESS_REDIRECT": getattr(
        settings, "VERIFICATION_SUCCESS_REDIRECT", "/accounts/profile/"
    ),
}

# Session settings
SESSION_SETTINGS = {
    "SESSION_TIMEOUT_MINUTES": getattr(settings, "SESSION_TIMEOUT_MINUTES", 30),
    "SESSION_TRACKING_ENABLED": getattr(settings, "SESSION_TRACKING_ENABLED", True),
    "MAX_CONCURRENT_SESSIONS": getattr(settings, "MAX_CONCURRENT_SESSIONS", 5),
    "SESSION_SECURITY_CHECKS": getattr(settings, "SESSION_SECURITY_CHECKS", True),
    "TRACK_SESSION_ACTIVITY": getattr(settings, "TRACK_SESSION_ACTIVITY", True),
    "SESSION_GEO_TRACKING": getattr(settings, "SESSION_GEO_TRACKING", True),
    "SESSION_DEVICE_TRACKING": getattr(settings, "SESSION_DEVICE_TRACKING", True),
    "CONCURRENT_SESSION_POLICY": getattr(
        settings, "CONCURRENT_SESSION_POLICY", "terminate_oldest"
    ),  # options: terminate_oldest, deny_new, allow_all
    "SESSION_WARNING_MINUTES": getattr(settings, "SESSION_WARNING_MINUTES", 5),
    "REMEMBER_ME_DURATION_DAYS": getattr(settings, "REMEMBER_ME_DURATION_DAYS", 14),
    "SESSION_CLEANUP_DAYS": getattr(settings, "SESSION_CLEANUP_DAYS", 30),
}

# Analytics settings
ANALYTICS_SETTINGS = {
    "ANALYTICS_ENABLED": getattr(settings, "ANALYTICS_ENABLED", True),
    "REAL_TIME_ANALYTICS": getattr(settings, "REAL_TIME_ANALYTICS", True),
    "ANALYTICS_RETENTION_DAYS": getattr(settings, "ANALYTICS_RETENTION_DAYS", 365),
    "DETAILED_USER_TRACKING": getattr(settings, "DETAILED_USER_TRACKING", True),
    "PERFORMANCE_MONITORING": getattr(settings, "PERFORMANCE_MONITORING", True),
    "SECURITY_ANALYTICS": getattr(settings, "SECURITY_ANALYTICS", True),
    "BEHAVIORAL_ANALYTICS": getattr(settings, "BEHAVIORAL_ANALYTICS", False),
    "ANONYMIZE_ANALYTICS_DATA": getattr(settings, "ANONYMIZE_ANALYTICS_DATA", False),
    "ANALYTICS_SAMPLING_RATE": getattr(settings, "ANALYTICS_SAMPLING_RATE", 1.0),
    "ENABLE_PREDICTIVE_ANALYTICS": getattr(
        settings, "ENABLE_PREDICTIVE_ANALYTICS", False
    ),
    "ANALYTICS_EXPORT_FORMATS": getattr(
        settings, "ANALYTICS_EXPORT_FORMATS", ["csv", "xlsx", "json", "pdf"]
    ),
    "DASHBOARD_REFRESH_INTERVAL": getattr(
        settings, "DASHBOARD_REFRESH_INTERVAL", 300
    ),  # seconds
}

# Notification settings
NOTIFICATION_SETTINGS = {
    "EMAIL_NOTIFICATIONS_ENABLED": getattr(
        settings, "EMAIL_NOTIFICATIONS_ENABLED", True
    ),
    "SMS_NOTIFICATIONS_ENABLED": getattr(settings, "SMS_NOTIFICATIONS_ENABLED", True),
    "PUSH_NOTIFICATIONS_ENABLED": getattr(
        settings, "PUSH_NOTIFICATIONS_ENABLED", False
    ),
    "IN_APP_NOTIFICATIONS_ENABLED": getattr(
        settings, "IN_APP_NOTIFICATIONS_ENABLED", True
    ),
    "DEFAULT_EMAIL_NOTIFICATIONS": getattr(
        settings, "DEFAULT_EMAIL_NOTIFICATIONS", True
    ),
    "DEFAULT_SMS_NOTIFICATIONS": getattr(settings, "DEFAULT_SMS_NOTIFICATIONS", False),
    "NOTIFICATION_RETRY_ATTEMPTS": getattr(settings, "NOTIFICATION_RETRY_ATTEMPTS", 3),
    "NOTIFICATION_QUEUE_ENABLED": getattr(settings, "NOTIFICATION_QUEUE_ENABLED", True),
    "BULK_NOTIFICATION_BATCH_SIZE": getattr(
        settings, "BULK_NOTIFICATION_BATCH_SIZE", 50
    ),
    "EMAIL_TEMPLATE_DIR": getattr(settings, "EMAIL_TEMPLATE_DIR", "accounts/emails/"),
    "SMS_PROVIDER": getattr(settings, "SMS_PROVIDER", "twilio"),
    "PUSH_NOTIFICATION_PROVIDER": getattr(
        settings, "PUSH_NOTIFICATION_PROVIDER", "fcm"
    ),
    "NOTIFICATION_RATE_LIMIT": getattr(
        settings, "NOTIFICATION_RATE_LIMIT", 100
    ),  # per hour
    "SEND_WELCOME_EMAILS": getattr(settings, "SEND_WELCOME_EMAILS", True),
    "SEND_ROLE_NOTIFICATIONS": getattr(settings, "SEND_ROLE_NOTIFICATIONS", True),
    "SEND_SECURITY_ALERTS": getattr(settings, "SEND_SECURITY_ALERTS", True),
}

# Cache settings
CACHE_SETTINGS = {
    "CACHE_ENABLED": getattr(settings, "CACHE_ENABLED", True),
    "USER_PERMISSIONS_CACHE_TIMEOUT": getattr(
        settings, "USER_PERMISSIONS_CACHE_TIMEOUT", 3600
    ),  # 1 hour
    "USER_ROLES_CACHE_TIMEOUT": getattr(settings, "USER_ROLES_CACHE_TIMEOUT", 3600),
    "USER_STATS_CACHE_TIMEOUT": getattr(
        settings, "USER_STATS_CACHE_TIMEOUT", 300
    ),  # 5 minutes
    "ANALYTICS_CACHE_TIMEOUT": getattr(
        settings, "ANALYTICS_CACHE_TIMEOUT", 900
    ),  # 15 minutes
    "SESSION_DATA_CACHE_TIMEOUT": getattr(
        settings, "SESSION_DATA_CACHE_TIMEOUT", 1800
    ),  # 30 minutes
    "OTP_CACHE_TIMEOUT": getattr(settings, "OTP_CACHE_TIMEOUT", 600),  # 10 minutes
    "SECURITY_TOKEN_CACHE_TIMEOUT": getattr(
        settings, "SECURITY_TOKEN_CACHE_TIMEOUT", 900
    ),  # 15 minutes
    "RATE_LIMIT_CACHE_TIMEOUT": getattr(settings, "RATE_LIMIT_CACHE_TIMEOUT", 3600),
    "WARM_CACHE_ON_STARTUP": getattr(settings, "WARM_CACHE_ON_STARTUP", True),
    "CACHE_CLEANUP_INTERVAL": getattr(
        settings, "CACHE_CLEANUP_INTERVAL", 86400
    ),  # 24 hours
    "DISTRIBUTED_CACHE_ENABLED": getattr(settings, "DISTRIBUTED_CACHE_ENABLED", False),
    "CACHE_COMPRESSION_ENABLED": getattr(settings, "CACHE_COMPRESSION_ENABLED", False),
}

# File upload settings
FILE_UPLOAD_SETTINGS = {
    "PROFILE_PICTURE_MAX_SIZE": getattr(
        settings, "PROFILE_PICTURE_MAX_SIZE", 2 * 1024 * 1024
    ),  # 2MB
    "DOCUMENT_MAX_SIZE": getattr(
        settings, "DOCUMENT_MAX_SIZE", 10 * 1024 * 1024
    ),  # 10MB
    "ALLOWED_IMAGE_TYPES": getattr(
        settings, "ALLOWED_IMAGE_TYPES", ["image/jpeg", "image/png", "image/gif"]
    ),
    "ALLOWED_DOCUMENT_TYPES": getattr(
        settings,
        "ALLOWED_DOCUMENT_TYPES",
        ["application/pdf", "application/msword", "text/plain"],
    ),
    "UPLOAD_VIRUS_SCANNING": getattr(settings, "UPLOAD_VIRUS_SCANNING", False),
    "IMAGE_OPTIMIZATION": getattr(settings, "IMAGE_OPTIMIZATION", True),
    "GENERATE_THUMBNAILS": getattr(settings, "GENERATE_THUMBNAILS", True),
}

# Data privacy settings
PRIVACY_SETTINGS = {
    "GDPR_COMPLIANCE": getattr(settings, "GDPR_COMPLIANCE", True),
    "DATA_RETENTION_DAYS": getattr(settings, "DATA_RETENTION_DAYS", 2555),  # 7 years
    "AUDIT_LOG_RETENTION_DAYS": getattr(
        settings, "AUDIT_LOG_RETENTION_DAYS", 730
    ),  # 2 years
    "ANONYMIZE_DELETED_USERS": getattr(settings, "ANONYMIZE_DELETED_USERS", True),
    "ALLOW_DATA_EXPORT": getattr(settings, "ALLOW_DATA_EXPORT", True),
    "ALLOW_DATA_DELETION": getattr(settings, "ALLOW_DATA_DELETION", True),
    "CONSENT_REQUIRED": getattr(settings, "CONSENT_REQUIRED", False),
    "PRIVACY_POLICY_VERSION": getattr(settings, "PRIVACY_POLICY_VERSION", "1.0"),
    "TERMS_OF_SERVICE_VERSION": getattr(settings, "TERMS_OF_SERVICE_VERSION", "1.0"),
}

# Integration settings
INTEGRATION_SETTINGS = {
    "LDAP_ENABLED": getattr(settings, "LDAP_ENABLED", False),
    "ACTIVE_DIRECTORY_ENABLED": getattr(settings, "ACTIVE_DIRECTORY_ENABLED", False),
    "SAML_ENABLED": getattr(settings, "SAML_ENABLED", False),
    "OAUTH_ENABLED": getattr(settings, "OAUTH_ENABLED", False),
    "WEBHOOK_NOTIFICATIONS": getattr(settings, "WEBHOOK_NOTIFICATIONS", False),
    "API_RATE_LIMITING": getattr(settings, "API_RATE_LIMITING", True),
    "API_VERSIONING": getattr(settings, "API_VERSIONING", True),
    "THIRD_PARTY_ANALYTICS": getattr(settings, "THIRD_PARTY_ANALYTICS", False),
}

# Development and debugging settings
DEBUG_SETTINGS = {
    "DEBUG_AUTHENTICATION": getattr(settings, "DEBUG_AUTHENTICATION", False),
    "LOG_SECURITY_EVENTS": getattr(settings, "LOG_SECURITY_EVENTS", True),
    "LOG_USER_ACTIVITIES": getattr(settings, "LOG_USER_ACTIVITIES", True),
    "VERBOSE_LOGGING": getattr(settings, "VERBOSE_LOGGING", False),
    "PERFORMANCE_PROFILING": getattr(settings, "PERFORMANCE_PROFILING", False),
    "MOCK_EXTERNAL_SERVICES": getattr(settings, "MOCK_EXTERNAL_SERVICES", False),
    "ENABLE_TEST_USERS": getattr(settings, "ENABLE_TEST_USERS", False),
}

# Backup and recovery settings
BACKUP_SETTINGS = {
    "AUTO_BACKUP_ENABLED": getattr(settings, "AUTO_BACKUP_ENABLED", True),
    "BACKUP_FREQUENCY": getattr(
        settings, "BACKUP_FREQUENCY", "daily"
    ),  # daily, weekly, monthly
    "BACKUP_RETENTION_DAYS": getattr(settings, "BACKUP_RETENTION_DAYS", 30),
    "BACKUP_ENCRYPTION": getattr(settings, "BACKUP_ENCRYPTION", True),
    "BACKUP_COMPRESSION": getattr(settings, "BACKUP_COMPRESSION", True),
    "INCLUDE_USER_DATA": getattr(settings, "INCLUDE_USER_DATA", True),
    "INCLUDE_AUDIT_LOGS": getattr(settings, "INCLUDE_AUDIT_LOGS", True),
    "BACKUP_VERIFICATION": getattr(settings, "BACKUP_VERIFICATION", True),
}

# Feature flags
FEATURE_FLAGS = {
    "ADVANCED_ANALYTICS": getattr(settings, "FEATURE_ADVANCED_ANALYTICS", True),
    "BULK_OPERATIONS": getattr(settings, "FEATURE_BULK_OPERATIONS", True),
    "USER_IMPERSONATION": getattr(settings, "FEATURE_USER_IMPERSONATION", False),
    "AUDIT_TRAIL": getattr(settings, "FEATURE_AUDIT_TRAIL", True),
    "ROLE_HIERARCHY": getattr(settings, "FEATURE_ROLE_HIERARCHY", True),
    "CUSTOM_FIELDS": getattr(settings, "FEATURE_CUSTOM_FIELDS", False),
    "WORKFLOW_APPROVAL": getattr(settings, "FEATURE_WORKFLOW_APPROVAL", False),
    "MULTI_TENANCY": getattr(settings, "FEATURE_MULTI_TENANCY", False),
    "ADVANCED_SEARCH": getattr(settings, "FEATURE_ADVANCED_SEARCH", True),
    "REAL_TIME_NOTIFICATIONS": getattr(
        settings, "FEATURE_REAL_TIME_NOTIFICATIONS", False
    ),
}

# Default role assignments based on email patterns
DEFAULT_ROLE_ASSIGNMENTS = {
    "email_patterns": {
        r".*@.*\.edu$": ["Student"],
        r"teacher.*@.*": ["Teacher"],
        r"admin.*@.*": ["Admin"],
        r"principal.*@.*": ["Principal"],
        r"staff.*@.*": ["Staff"],
    },
    "domain_patterns": {
        "admin.example.com": ["Admin"],
        "teachers.example.com": ["Teacher"],
        "students.example.com": ["Student"],
    },
    "default_role": "Student",
}

# System limits
SYSTEM_LIMITS = {
    "MAX_USERS": getattr(settings, "MAX_USERS", 10000),
    "MAX_ROLES": getattr(settings, "MAX_ROLES", 100),
    "MAX_PERMISSIONS_PER_ROLE": getattr(settings, "MAX_PERMISSIONS_PER_ROLE", 50),
    "MAX_ROLES_PER_USER": getattr(settings, "MAX_ROLES_PER_USER", 10),
    "MAX_SESSION_DURATION_HOURS": getattr(settings, "MAX_SESSION_DURATION_HOURS", 24),
    "MAX_FILE_UPLOAD_SIZE": getattr(
        settings, "MAX_FILE_UPLOAD_SIZE", 50 * 1024 * 1024
    ),  # 50MB
    "MAX_BULK_OPERATIONS": getattr(settings, "MAX_BULK_OPERATIONS", 1000),
    "MAX_EXPORT_RECORDS": getattr(settings, "MAX_EXPORT_RECORDS", 10000),
}

# Performance settings
PERFORMANCE_SETTINGS = {
    "ENABLE_QUERY_OPTIMIZATION": getattr(settings, "ENABLE_QUERY_OPTIMIZATION", True),
    "USE_DATABASE_INDEXING": getattr(settings, "USE_DATABASE_INDEXING", True),
    "ENABLE_LAZY_LOADING": getattr(settings, "ENABLE_LAZY_LOADING", True),
    "USE_PAGINATION": getattr(settings, "USE_PAGINATION", True),
    "DEFAULT_PAGE_SIZE": getattr(settings, "DEFAULT_PAGE_SIZE", 25),
    "MAX_PAGE_SIZE": getattr(settings, "MAX_PAGE_SIZE", 100),
    "ENABLE_SEARCH_INDEXING": getattr(settings, "ENABLE_SEARCH_INDEXING", False),
    "ASYNC_OPERATIONS": getattr(settings, "ASYNC_OPERATIONS", True),
}

# All settings combined for easy access
ALL_SETTINGS = {
    "SECURITY": SECURITY_SETTINGS,
    "AUTHENTICATION": AUTHENTICATION_SETTINGS,
    "VERIFICATION": VERIFICATION_SETTINGS,
    "SESSION": SESSION_SETTINGS,
    "ANALYTICS": ANALYTICS_SETTINGS,
    "NOTIFICATION": NOTIFICATION_SETTINGS,
    "CACHE": CACHE_SETTINGS,
    "FILE_UPLOAD": FILE_UPLOAD_SETTINGS,
    "PRIVACY": PRIVACY_SETTINGS,
    "INTEGRATION": INTEGRATION_SETTINGS,
    "DEBUG": DEBUG_SETTINGS,
    "BACKUP": BACKUP_SETTINGS,
    "FEATURE_FLAGS": FEATURE_FLAGS,
    "SYSTEM_LIMITS": SYSTEM_LIMITS,
    "PERFORMANCE": PERFORMANCE_SETTINGS,
}
