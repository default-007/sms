"""
Finance module constants and configuration.
"""

from decimal import Decimal


# Fee Category Frequencies
class FeeFrequency:
    MONTHLY = "monthly"
    TERMLY = "termly"
    ANNUALLY = "annually"
    ONE_TIME = "one_time"

    CHOICES = [
        (MONTHLY, "Monthly"),
        (TERMLY, "Termly"),
        (ANNUALLY, "Annually"),
        (ONE_TIME, "One Time"),
    ]


# Special Fee Types
class SpecialFeeType:
    CLASS_BASED = "class_based"
    STUDENT_SPECIFIC = "student_specific"

    CHOICES = [
        (CLASS_BASED, "Class-based"),
        (STUDENT_SPECIFIC, "Student-specific"),
    ]


# Scholarship Discount Types
class ScholarshipDiscountType:
    PERCENTAGE = "percentage"
    FIXED_AMOUNT = "fixed_amount"

    CHOICES = [
        (PERCENTAGE, "Percentage"),
        (FIXED_AMOUNT, "Fixed Amount"),
    ]


# Scholarship Criteria
class ScholarshipCriteria:
    MERIT = "merit"
    NEED = "need"
    SPORTS = "sports"
    ARTS = "arts"
    SIBLING = "sibling"
    STAFF = "staff"
    OTHER = "other"

    CHOICES = [
        (MERIT, "Merit-based"),
        (NEED, "Need-based"),
        (SPORTS, "Sports Excellence"),
        (ARTS, "Arts Excellence"),
        (SIBLING, "Sibling Discount"),
        (STAFF, "Staff Discount"),
        (OTHER, "Other"),
    ]


# Student Scholarship Status
class StudentScholarshipStatus:
    APPROVED = "approved"
    SUSPENDED = "suspended"
    TERMINATED = "terminated"
    PENDING = "pending"

    CHOICES = [
        (APPROVED, "Approved"),
        (SUSPENDED, "Suspended"),
        (TERMINATED, "Terminated"),
        (PENDING, "Pending"),
    ]


# Invoice Status
class InvoiceStatus:
    UNPAID = "unpaid"
    PARTIALLY_PAID = "partially_paid"
    PAID = "paid"
    OVERDUE = "overdue"
    CANCELLED = "cancelled"

    CHOICES = [
        (UNPAID, "Unpaid"),
        (PARTIALLY_PAID, "Partially Paid"),
        (PAID, "Paid"),
        (OVERDUE, "Overdue"),
        (CANCELLED, "Cancelled"),
    ]


# Payment Methods
class PaymentMethod:
    CASH = "cash"
    BANK_TRANSFER = "bank_transfer"
    CREDIT_CARD = "credit_card"
    DEBIT_CARD = "debit_card"
    MOBILE_PAYMENT = "mobile_payment"
    CHEQUE = "cheque"
    ONLINE = "online"

    CHOICES = [
        (CASH, "Cash"),
        (BANK_TRANSFER, "Bank Transfer"),
        (CREDIT_CARD, "Credit Card"),
        (DEBIT_CARD, "Debit Card"),
        (MOBILE_PAYMENT, "Mobile Payment"),
        (CHEQUE, "Cheque"),
        (ONLINE, "Online Payment"),
    ]


# Payment Status
class PaymentStatus:
    COMPLETED = "completed"
    PENDING = "pending"
    FAILED = "failed"
    REFUNDED = "refunded"

    CHOICES = [
        (COMPLETED, "Completed"),
        (PENDING, "Pending"),
        (FAILED, "Failed"),
        (REFUNDED, "Refunded"),
    ]


# Fee Waiver Types
class FeeWaiverType:
    FULL = "full"
    PARTIAL = "partial"

    CHOICES = [
        (FULL, "Full Waiver"),
        (PARTIAL, "Partial Waiver"),
    ]


# Fee Waiver Status
class FeeWaiverStatus:
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"

    CHOICES = [
        (PENDING, "Pending"),
        (APPROVED, "Approved"),
        (REJECTED, "Rejected"),
    ]


# Default Fee Categories
DEFAULT_FEE_CATEGORIES = [
    {
        "name": "Tuition",
        "description": "Basic tuition fees for academic instruction",
        "is_mandatory": True,
        "is_recurring": True,
        "frequency": FeeFrequency.TERMLY,
    },
    {
        "name": "Transport",
        "description": "School transportation fees",
        "is_mandatory": False,
        "is_recurring": True,
        "frequency": FeeFrequency.TERMLY,
    },
    {
        "name": "Library",
        "description": "Library usage and maintenance fees",
        "is_mandatory": True,
        "is_recurring": True,
        "frequency": FeeFrequency.ANNUALLY,
    },
    {
        "name": "Laboratory",
        "description": "Science laboratory fees",
        "is_mandatory": False,
        "is_recurring": True,
        "frequency": FeeFrequency.TERMLY,
    },
    {
        "name": "Sports",
        "description": "Sports and physical education fees",
        "is_mandatory": False,
        "is_recurring": True,
        "frequency": FeeFrequency.ANNUALLY,
    },
    {
        "name": "Examination",
        "description": "Examination and assessment fees",
        "is_mandatory": True,
        "is_recurring": True,
        "frequency": FeeFrequency.TERMLY,
    },
    {
        "name": "Development",
        "description": "School development and infrastructure fees",
        "is_mandatory": True,
        "is_recurring": True,
        "frequency": FeeFrequency.ANNUALLY,
    },
    {
        "name": "Late Fee",
        "description": "Late payment charges",
        "is_mandatory": False,
        "is_recurring": False,
        "frequency": FeeFrequency.ONE_TIME,
    },
    {
        "name": "Miscellaneous",
        "description": "Other miscellaneous fees",
        "is_mandatory": False,
        "is_recurring": False,
        "frequency": FeeFrequency.ONE_TIME,
    },
]


# Financial Configuration
class FinanceConfig:
    # Currency settings
    CURRENCY_SYMBOL = "$"
    CURRENCY_CODE = "USD"
    DECIMAL_PLACES = 2

    # Invoice settings
    INVOICE_NUMBER_PREFIX = "INV"
    INVOICE_NUMBER_LENGTH = 10

    # Receipt settings
    RECEIPT_NUMBER_PREFIX = "RCP"
    RECEIPT_NUMBER_LENGTH = 10

    # Payment settings
    MINIMUM_PAYMENT_AMOUNT = Decimal("0.01")
    MAXIMUM_PAYMENT_AMOUNT = Decimal("999999.99")

    # Late fee settings
    DEFAULT_LATE_FEE_PERCENTAGE = Decimal("5.00")  # 5%
    DEFAULT_GRACE_PERIOD_DAYS = 7
    LATE_FEE_CALCULATION_METHOD = "simple"  # 'simple' or 'compound'

    # Scholarship settings
    MAXIMUM_SCHOLARSHIP_PERCENTAGE = Decimal("100.00")
    DEFAULT_SCHOLARSHIP_DURATION_MONTHS = 12

    # Analytics settings
    ANALYTICS_RETENTION_DAYS = 365
    REPORT_CACHE_TIMEOUT = 3600  # 1 hour

    # Pagination
    DEFAULT_PAGE_SIZE = 20
    MAX_PAGE_SIZE = 100

    # File uploads
    MAX_ATTACHMENT_SIZE_MB = 10
    ALLOWED_ATTACHMENT_TYPES = [
        "pdf",
        "doc",
        "docx",
        "xls",
        "xlsx",
        "jpg",
        "jpeg",
        "png",
        "gif",
    ]


# Business Rules
class BusinessRules:
    # Fee structure rules
    ALLOW_OVERLAPPING_FEE_STRUCTURES = False
    REQUIRE_FEE_APPROVAL = True
    ALLOW_RETROACTIVE_FEE_CHANGES = False

    # Payment rules
    ALLOW_OVERPAYMENT = True
    ALLOW_PARTIAL_PAYMENTS = True
    REQUIRE_PAYMENT_APPROVAL = False
    AUTO_ALLOCATE_ADVANCE_PAYMENTS = True

    # Invoice rules
    AUTO_GENERATE_INVOICES = False
    ALLOW_INVOICE_MODIFICATION = True
    REQUIRE_INVOICE_APPROVAL = False
    AUTO_SEND_INVOICE_REMINDERS = True

    # Scholarship rules
    ALLOW_MULTIPLE_SCHOLARSHIPS = True
    REQUIRE_SCHOLARSHIP_APPROVAL = True
    AUTO_APPLY_SIBLING_DISCOUNTS = True

    # Waiver rules
    REQUIRE_WAIVER_APPROVAL = True
    ALLOW_WAIVER_MODIFICATION = False
    WAIVER_EXPIRY_DAYS = 30


# Notification Templates
class NotificationTemplates:
    INVOICE_GENERATED = {
        "subject": "New Invoice Generated - {invoice_number}",
        "message": "A new invoice has been generated for {student_name}. Amount: {amount}. Due date: {due_date}.",
    }

    PAYMENT_RECEIVED = {
        "subject": "Payment Received - Receipt {receipt_number}",
        "message": "Payment of {amount} received for invoice {invoice_number}. Thank you!",
    }

    PAYMENT_REMINDER = {
        "subject": "Payment Reminder - Invoice {invoice_number}",
        "message": "Your payment of {amount} is due on {due_date}. Please make payment to avoid late fees.",
    }

    SCHOLARSHIP_APPROVED = {
        "subject": "Scholarship Approved - {scholarship_name}",
        "message": "Congratulations! Your scholarship application for {scholarship_name} has been approved.",
    }

    FEE_WAIVER_APPROVED = {
        "subject": "Fee Waiver Approved",
        "message": "Your fee waiver request for {amount} has been approved.",
    }


# Report Types
class ReportType:
    COLLECTION_SUMMARY = "collection_summary"
    DEFAULTER_REPORT = "defaulter_report"
    SCHOLARSHIP_REPORT = "scholarship_report"
    FINANCIAL_SUMMARY = "financial_summary"
    PAYMENT_ANALYSIS = "payment_analysis"
    FEE_STRUCTURE_REPORT = "fee_structure_report"

    CHOICES = [
        (COLLECTION_SUMMARY, "Collection Summary"),
        (DEFAULTER_REPORT, "Defaulter Report"),
        (SCHOLARSHIP_REPORT, "Scholarship Report"),
        (FINANCIAL_SUMMARY, "Financial Summary"),
        (PAYMENT_ANALYSIS, "Payment Analysis"),
        (FEE_STRUCTURE_REPORT, "Fee Structure Report"),
    ]


# Analytics Metrics
class AnalyticsMetrics:
    COLLECTION_RATE = "collection_rate"
    OUTSTANDING_AMOUNT = "outstanding_amount"
    PAYMENT_TRENDS = "payment_trends"
    SCHOLARSHIP_IMPACT = "scholarship_impact"
    DEFAULTER_ANALYSIS = "defaulter_analysis"
    REVENUE_FORECAST = "revenue_forecast"


# Export Formats
class ExportFormat:
    PDF = "pdf"
    EXCEL = "excel"
    CSV = "csv"
    JSON = "json"

    CHOICES = [
        (PDF, "PDF"),
        (EXCEL, "Excel"),
        (CSV, "CSV"),
        (JSON, "JSON"),
    ]


# API Response Codes
class APIResponseCode:
    SUCCESS = 200
    CREATED = 201
    BAD_REQUEST = 400
    UNAUTHORIZED = 401
    FORBIDDEN = 403
    NOT_FOUND = 404
    CONFLICT = 409
    INTERNAL_ERROR = 500


# Error Messages
class ErrorMessages:
    INVALID_AMOUNT = "Amount must be a positive number"
    DUPLICATE_INVOICE = "Invoice already exists for this student in this term"
    INSUFFICIENT_PERMISSIONS = "You don't have permission to perform this action"
    INVALID_PAYMENT_METHOD = "Invalid payment method selected"
    SCHOLARSHIP_QUOTA_EXCEEDED = "Scholarship quota has been exceeded"
    INVOICE_ALREADY_PAID = "Invoice is already fully paid"
    INVALID_DATE_RANGE = "Invalid date range specified"
    STUDENT_NOT_FOUND = "Student not found"
    ACADEMIC_YEAR_NOT_ACTIVE = "Academic year is not active"
    TERM_NOT_ACTIVE = "Term is not active"


# Success Messages
class SuccessMessages:
    INVOICE_GENERATED = "Invoice generated successfully"
    PAYMENT_PROCESSED = "Payment processed successfully"
    SCHOLARSHIP_ASSIGNED = "Scholarship assigned successfully"
    FEE_STRUCTURE_CREATED = "Fee structure created successfully"
    WAIVER_APPROVED = "Fee waiver approved successfully"
    BULK_OPERATION_COMPLETED = "Bulk operation completed successfully"


# Cache Keys
class CacheKeys:
    COLLECTION_METRICS = "finance:collection_metrics:{academic_year}:{term}"
    PAYMENT_TRENDS = "finance:payment_trends:{academic_year}:{days}"
    DEFAULTER_REPORT = "finance:defaulter_report:{academic_year}:{term}"
    SCHOLARSHIP_SUMMARY = "finance:scholarship_summary:{academic_year}"
    FINANCIAL_ANALYTICS = "finance:analytics:{academic_year}:{term}:{level}"


# Task Names (for Celery)
class TaskNames:
    UPDATE_FINANCIAL_SUMMARY = "finance.tasks.update_financial_summary_task"
    GENERATE_BULK_INVOICES = "finance.tasks.generate_bulk_invoices_task"
    SEND_PAYMENT_REMINDERS = "finance.tasks.send_payment_reminders_task"
    CALCULATE_LATE_FEES = "finance.tasks.calculate_late_fees_task"
    AUTO_ASSIGN_SIBLING_DISCOUNTS = "finance.tasks.auto_assign_sibling_discounts_task"
    GENERATE_DAILY_REPORT = "finance.tasks.generate_daily_financial_report_task"
    CLEANUP_OLD_ANALYTICS = "finance.tasks.cleanup_old_analytics_task"


# Database Constraints
class DatabaseConstraints:
    MAX_AMOUNT_DIGITS = 10
    AMOUNT_DECIMAL_PLACES = 2
    MAX_PERCENTAGE_DIGITS = 5
    PERCENTAGE_DECIMAL_PLACES = 2
    MAX_STRING_LENGTH = 200
    MAX_TEXT_LENGTH = 1000
    MAX_DESCRIPTION_LENGTH = 500


# Validation Rules
class ValidationRules:
    MIN_AMOUNT = Decimal("0.01")
    MAX_AMOUNT = Decimal("999999.99")
    MIN_PERCENTAGE = Decimal("0.00")
    MAX_PERCENTAGE = Decimal("100.00")
    MIN_GRACE_PERIOD_DAYS = 0
    MAX_GRACE_PERIOD_DAYS = 365
    MIN_LATE_FEE_PERCENTAGE = Decimal("0.00")
    MAX_LATE_FEE_PERCENTAGE = Decimal("50.00")


# Feature Flags
class FeatureFlags:
    ENABLE_ONLINE_PAYMENTS = True
    ENABLE_MOBILE_PAYMENTS = True
    ENABLE_AUTOMATIC_LATE_FEES = True
    ENABLE_SCHOLARSHIP_AUTO_ASSIGNMENT = True
    ENABLE_INVOICE_EMAIL_NOTIFICATIONS = True
    ENABLE_PAYMENT_RECEIPTS = True
    ENABLE_ADVANCED_ANALYTICS = True
    ENABLE_BULK_OPERATIONS = True
    ENABLE_FEE_WAIVERS = True
    ENABLE_MULTI_CURRENCY = False  # Future feature


# Integration Settings
class IntegrationSettings:
    # Payment gateway settings
    PAYMENT_GATEWAY_ENABLED = False
    PAYMENT_GATEWAY_PROVIDER = "stripe"  # 'stripe', 'razorpay', 'paypal'

    # SMS gateway settings
    SMS_GATEWAY_ENABLED = False
    SMS_GATEWAY_PROVIDER = "twilio"

    # Email settings
    EMAIL_NOTIFICATIONS_ENABLED = True
    EMAIL_PROVIDER = "smtp"

    # Accounting software integration
    ACCOUNTING_INTEGRATION_ENABLED = False
    ACCOUNTING_SOFTWARE = "quickbooks"  # 'quickbooks', 'xero', 'sage'
