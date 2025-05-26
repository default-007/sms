"""
Finance module settings configuration.
Add these settings to your main Django settings file.
"""

from celery.schedules import crontab
from decimal import Decimal

# =============================================================================
# FINANCE MODULE SETTINGS
# =============================================================================

# Basic finance configuration
FINANCE_CONFIG = {
    # Currency settings
    "CURRENCY_SYMBOL": "$",
    "CURRENCY_CODE": "USD",
    "DECIMAL_PLACES": 2,
    # Invoice settings
    "INVOICE_NUMBER_PREFIX": "INV",
    "INVOICE_NUMBER_LENGTH": 10,
    "AUTO_GENERATE_INVOICES": False,
    "ALLOW_INVOICE_MODIFICATION": True,
    "REQUIRE_INVOICE_APPROVAL": False,
    # Receipt settings
    "RECEIPT_NUMBER_PREFIX": "RCP",
    "RECEIPT_NUMBER_LENGTH": 10,
    # Payment settings
    "MINIMUM_PAYMENT_AMOUNT": Decimal("0.01"),
    "MAXIMUM_PAYMENT_AMOUNT": Decimal("999999.99"),
    "ALLOW_OVERPAYMENT": True,
    "ALLOW_PARTIAL_PAYMENTS": True,
    "REQUIRE_PAYMENT_APPROVAL": False,
    "AUTO_ALLOCATE_ADVANCE_PAYMENTS": True,
    # Late fee settings
    "DEFAULT_LATE_FEE_PERCENTAGE": Decimal("5.00"),  # 5%
    "DEFAULT_GRACE_PERIOD_DAYS": 7,
    "LATE_FEE_CALCULATION_METHOD": "simple",  # 'simple' or 'compound'
    "AUTO_CALCULATE_LATE_FEES": True,
    # Scholarship settings
    "MAXIMUM_SCHOLARSHIP_PERCENTAGE": Decimal("100.00"),
    "DEFAULT_SCHOLARSHIP_DURATION_MONTHS": 12,
    "ALLOW_MULTIPLE_SCHOLARSHIPS": True,
    "REQUIRE_SCHOLARSHIP_APPROVAL": True,
    "AUTO_APPLY_SIBLING_DISCOUNTS": True,
    # Fee structure settings
    "ALLOW_OVERLAPPING_FEE_STRUCTURES": False,
    "REQUIRE_FEE_APPROVAL": True,
    "ALLOW_RETROACTIVE_FEE_CHANGES": False,
    # Waiver settings
    "REQUIRE_WAIVER_APPROVAL": True,
    "ALLOW_WAIVER_MODIFICATION": False,
    "WAIVER_EXPIRY_DAYS": 30,
    # Analytics settings
    "ANALYTICS_RETENTION_DAYS": 365,
    "REPORT_CACHE_TIMEOUT": 3600,  # 1 hour
    "ENABLE_ADVANCED_ANALYTICS": True,
    # Notification settings
    "ENABLE_EMAIL_NOTIFICATIONS": True,
    "ENABLE_SMS_NOTIFICATIONS": False,
    "AUTO_SEND_INVOICE_REMINDERS": True,
    "SEND_PAYMENT_RECEIPTS": True,
}

# Payment gateway settings
PAYMENT_GATEWAY_CONFIG = {
    "ENABLED": False,
    "PROVIDER": "stripe",  # 'stripe', 'razorpay', 'paypal', 'square'
    "SANDBOX_MODE": True,
    "WEBHOOK_ENDPOINT": "/api/finance/payments/webhook/",
    # Provider-specific settings (add your keys)
    "STRIPE": {
        "PUBLIC_KEY": "pk_test_...",
        "SECRET_KEY": "sk_test_...",
        "WEBHOOK_SECRET": "whsec_...",
    },
    "RAZORPAY": {
        "KEY_ID": "rzp_test_...",
        "KEY_SECRET": "...",
        "WEBHOOK_SECRET": "...",
    },
    "PAYPAL": {
        "CLIENT_ID": "...",
        "CLIENT_SECRET": "...",
    },
}

# SMS gateway settings
SMS_GATEWAY_CONFIG = {
    "ENABLED": False,
    "PROVIDER": "twilio",  # 'twilio', 'textlocal', 'msg91'
    "TWILIO": {
        "ACCOUNT_SID": "...",
        "AUTH_TOKEN": "...",
        "PHONE_NUMBER": "+1234567890",
    },
    "TEXTLOCAL": {
        "API_KEY": "...",
        "SENDER": "SCHOOL",
    },
}

# Email templates for notifications
FINANCE_EMAIL_TEMPLATES = {
    "INVOICE_GENERATED": {
        "subject": "New Invoice Generated - {invoice_number}",
        "template": "finance/emails/invoice_generated.html",
    },
    "PAYMENT_RECEIVED": {
        "subject": "Payment Received - Receipt {receipt_number}",
        "template": "finance/emails/payment_received.html",
    },
    "PAYMENT_REMINDER": {
        "subject": "Payment Reminder - Invoice {invoice_number}",
        "template": "finance/emails/payment_reminder.html",
    },
    "SCHOLARSHIP_APPROVED": {
        "subject": "Scholarship Approved - {scholarship_name}",
        "template": "finance/emails/scholarship_approved.html",
    },
    "FEE_WAIVER_APPROVED": {
        "subject": "Fee Waiver Approved",
        "template": "finance/emails/fee_waiver_approved.html",
    },
}

# File upload settings
FINANCE_FILE_UPLOADS = {
    "MAX_ATTACHMENT_SIZE_MB": 10,
    "ALLOWED_ATTACHMENT_TYPES": [
        "pdf",
        "doc",
        "docx",
        "xls",
        "xlsx",
        "jpg",
        "jpeg",
        "png",
        "gif",
    ],
    "UPLOAD_PATH": "finance/attachments/%Y/%m/",
}

# API settings
FINANCE_API_CONFIG = {
    "DEFAULT_PAGE_SIZE": 20,
    "MAX_PAGE_SIZE": 100,
    "ENABLE_API_DOCS": True,
    "API_THROTTLING": {
        "anon": "100/hour",
        "user": "1000/hour",
        "finance_manager": "5000/hour",
    },
}

# Security settings
FINANCE_SECURITY = {
    "ENCRYPT_SENSITIVE_DATA": True,
    "LOG_ALL_TRANSACTIONS": True,
    "REQUIRE_2FA_FOR_PAYMENTS": False,
    "SESSION_TIMEOUT_MINUTES": 30,
    "MAX_LOGIN_ATTEMPTS": 5,
}

# Integration settings
FINANCE_INTEGRATIONS = {
    # Accounting software integration
    "ACCOUNTING_SOFTWARE": {
        "ENABLED": False,
        "PROVIDER": "quickbooks",  # 'quickbooks', 'xero', 'sage'
        "AUTO_SYNC": False,
        "SYNC_INTERVAL_HOURS": 24,
    },
    # Bank integration
    "BANK_INTEGRATION": {
        "ENABLED": False,
        "PROVIDER": "plaid",  # 'plaid', 'yodlee'
        "AUTO_RECONCILE": False,
    },
    # Student information system integration
    "SIS_INTEGRATION": {
        "AUTO_UPDATE_STUDENT_DATA": True,
        "SYNC_CLASS_CHANGES": True,
        "HANDLE_WITHDRAWALS": True,
    },
}

# =============================================================================
# CELERY CONFIGURATION FOR FINANCE TASKS
# =============================================================================

# Add these to your main CELERY_BEAT_SCHEDULE
FINANCE_CELERY_TASKS = {
    # Daily tasks
    "finance-daily-report": {
        "task": "finance.tasks.generate_daily_financial_report_task",
        "schedule": crontab(hour=2, minute=0),  # 2 AM daily
    },
    "finance-update-analytics": {
        "task": "finance.tasks.update_financial_summary_task",
        "schedule": crontab(hour=1, minute=0),  # 1 AM daily
    },
    # Weekly tasks
    "finance-payment-reminders": {
        "task": "finance.tasks.send_payment_reminders_task",
        "schedule": crontab(hour=9, minute=0, day_of_week=1),  # Monday 9 AM
        "kwargs": {"days_overdue": 7, "limit": 500},
    },
    # Monthly tasks
    "finance-late-fees": {
        "task": "finance.tasks.calculate_late_fees_task",
        "schedule": crontab(hour=3, minute=0, day_of_month=1),  # 1st of month, 3 AM
    },
    "finance-sibling-discounts": {
        "task": "finance.tasks.auto_assign_sibling_discounts_task",
        "schedule": crontab(hour=4, minute=0, day_of_month=1),  # 1st of month, 4 AM
    },
    # Quarterly tasks
    "finance-cleanup-analytics": {
        "task": "finance.tasks.cleanup_old_analytics_task",
        "schedule": crontab(hour=5, minute=0, day_of_month=1, month_of_year="1,4,7,10"),
        "kwargs": {"days_to_keep": 180},
    },
}

# =============================================================================
# DJANGO SETTINGS INTEGRATION
# =============================================================================

# Add to INSTALLED_APPS
FINANCE_INSTALLED_APPS = [
    "finance",
]

# Add to MIDDLEWARE (if custom middleware is needed)
FINANCE_MIDDLEWARE = [
    # Add any custom finance middleware here
]

# Database settings (if using separate finance database)
FINANCE_DATABASE_CONFIG = {
    "finance": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "school_finance",
        "USER": "finance_user",
        "PASSWORD": "your_password",
        "HOST": "localhost",
        "PORT": "5432",
    }
}

# Cache settings for finance
FINANCE_CACHE_CONFIG = {
    "finance": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": "redis://127.0.0.1:6379/2",
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        },
        "KEY_PREFIX": "finance",
        "TIMEOUT": 3600,
    }
}

# Logging configuration for finance
FINANCE_LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "finance_detailed": {
            "format": "{levelname} {asctime} {module} {process:d} {thread:d} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "finance_file": {
            "level": "INFO",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": "logs/finance.log",
            "maxBytes": 1024 * 1024 * 15,  # 15MB
            "backupCount": 10,
            "formatter": "finance_detailed",
        },
        "finance_error_file": {
            "level": "ERROR",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": "logs/finance_errors.log",
            "maxBytes": 1024 * 1024 * 15,  # 15MB
            "backupCount": 10,
            "formatter": "finance_detailed",
        },
    },
    "loggers": {
        "finance": {
            "handlers": ["finance_file"],
            "level": "INFO",
            "propagate": True,
        },
        "finance.payments": {
            "handlers": ["finance_file", "finance_error_file"],
            "level": "INFO",
            "propagate": False,
        },
        "finance.invoices": {
            "handlers": ["finance_file"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

# =============================================================================
# SAMPLE SETTINGS.PY CONFIGURATION
# =============================================================================

SAMPLE_SETTINGS_INTEGRATION = """
# Add to your main settings.py file:

# 1. Add to INSTALLED_APPS
INSTALLED_APPS = [
    # ... your existing apps
    'finance',
]

# 2. Import and merge finance settings
from finance.settings import (
    FINANCE_CONFIG, PAYMENT_GATEWAY_CONFIG, FINANCE_EMAIL_TEMPLATES,
    FINANCE_CELERY_TASKS, FINANCE_CACHE_CONFIG
)

# 3. Add finance-specific settings
FINANCE = FINANCE_CONFIG
PAYMENT_GATEWAY = PAYMENT_GATEWAY_CONFIG
EMAIL_TEMPLATES = FINANCE_EMAIL_TEMPLATES

# 4. Update CELERY_BEAT_SCHEDULE
CELERY_BEAT_SCHEDULE = {
    **CELERY_BEAT_SCHEDULE,  # your existing tasks
    **FINANCE_CELERY_TASKS,
}

# 5. Update CACHES (optional, for better performance)
CACHES = {
    **CACHES,  # your existing cache config
    **FINANCE_CACHE_CONFIG,
}

# 6. Add to REST_FRAMEWORK settings
REST_FRAMEWORK = {
    # ... your existing DRF settings
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
}

# 7. Add finance permissions to groups (optional)
# This can be done in a data migration or management command
"""

# =============================================================================
# URL CONFIGURATION
# =============================================================================

SAMPLE_URL_INTEGRATION = """
# Add to your main urls.py file:

from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    # ... your existing URLs
    path('finance/', include('finance.urls')),
    path('api/finance/', include('finance.api.urls')),
]
"""

# =============================================================================
# ENVIRONMENT VARIABLES
# =============================================================================

SAMPLE_ENV_VARIABLES = """
# Add to your .env file:

# Finance Configuration
FINANCE_CURRENCY_SYMBOL=$
FINANCE_CURRENCY_CODE=USD
FINANCE_AUTO_LATE_FEES=True
FINANCE_PAYMENT_APPROVAL_REQUIRED=False

# Payment Gateway (Stripe example)
STRIPE_PUBLIC_KEY=pk_test_your_stripe_public_key
STRIPE_SECRET_KEY=sk_test_your_stripe_secret_key
STRIPE_WEBHOOK_SECRET=whsec_your_webhook_secret

# SMS Gateway (Twilio example)
TWILIO_ACCOUNT_SID=your_twilio_account_sid
TWILIO_AUTH_TOKEN=your_twilio_auth_token
TWILIO_PHONE_NUMBER=+1234567890

# Email Settings
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
EMAIL_USE_TLS=True
"""

# =============================================================================
# TESTING CONFIGURATION
# =============================================================================

FINANCE_TEST_SETTINGS = {
    "USE_MOCK_PAYMENTS": True,
    "DISABLE_EMAIL_NOTIFICATIONS": True,
    "DISABLE_SMS_NOTIFICATIONS": True,
    "SKIP_EXTERNAL_API_CALLS": True,
    "TEST_DATA_SIZE": "small",  # 'small', 'medium', 'large'
}

# =============================================================================
# PRODUCTION CHECKLIST
# =============================================================================

PRODUCTION_CHECKLIST = """
Finance Module Production Checklist:

☐ Security:
  - Set strong SECRET_KEY
  - Enable HTTPS/SSL
  - Configure proper CORS settings
  - Set up rate limiting
  - Enable audit logging

☐ Database:
  - Set up database backups
  - Configure connection pooling
  - Add database indexes
  - Set up monitoring

☐ Payments:
  - Configure payment gateway in production mode
  - Set up webhook endpoints
  - Test payment flows
  - Set up fraud monitoring

☐ Notifications:
  - Configure email SMTP settings
  - Set up SMS gateway
  - Test notification delivery
  - Set up monitoring for failed notifications

☐ Performance:
  - Configure Redis for caching
  - Set up Celery workers
  - Configure load balancing
  - Monitor performance metrics

☐ Monitoring:
  - Set up error tracking (Sentry)
  - Configure log aggregation
  - Set up uptime monitoring
  - Create alerting rules

☐ Compliance:
  - Review data privacy settings
  - Set up audit trails
  - Configure data retention policies
  - Test backup and recovery procedures
"""
