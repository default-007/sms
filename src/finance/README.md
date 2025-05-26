# Finance Module Documentation

## Overview

The Finance module is a comprehensive financial management system for educational institutions. It provides complete fee management, payment processing, scholarship administration, and financial analytics capabilities.

## Features

### 🏗️ Hierarchical Fee Structure

- **Multi-level fee assignment**: Section → Grade → Class → Student
- **Flexible fee categories**: Tuition, Transport, Library, Lab, Sports, etc.
- **Special fees**: Class-specific and student-specific charges
- **Automatic fee calculation**: Based on student's academic placement

### 💰 Payment Processing

- **Multiple payment methods**: Cash, Bank Transfer, Credit/Debit Cards, Mobile Payments
- **Payment validation**: Built-in validators for different payment types
- **Receipt generation**: Automatic receipt numbering and tracking
- **Overpayment handling**: Advance payment allocation system

### 🎓 Scholarship Management

- **Flexible discounts**: Percentage or fixed amount scholarships
- **Multiple criteria**: Merit, Need, Sports, Arts, Sibling, Staff discounts
- **Automatic assignment**: Sibling discounts and other rule-based scholarships
- **Approval workflow**: Multi-stage scholarship approval process

### 📊 Advanced Analytics

- **Collection metrics**: Real-time collection rates and trends
- **Defaulter analysis**: Risk assessment and early warning systems
- **Payment trends**: Method analysis and peak time identification
- **Revenue forecasting**: Predictive analytics for financial planning

### 📋 Invoice Management

- **Automated generation**: Bulk invoice creation for terms
- **Status tracking**: Unpaid, Partially Paid, Paid, Overdue statuses
- **PDF generation**: Professional invoice and receipt formats
- **Payment reminders**: Automated reminder system

### 🎯 Fee Waivers

- **Flexible waivers**: Full or partial fee waivers
- **Approval workflow**: Request, review, and approval process
- **Audit trail**: Complete waiver history and justifications

## Architecture

### Database Schema

```
finance/
├── FeeCategory (Tuition, Transport, etc.)
├── FeeStructure (Section/Grade-based fees)
├── SpecialFee (Class/Student-specific fees)
├── Scholarship (Discount schemes)
├── StudentScholarship (Student assignments)
├── Invoice (Student billing)
├── InvoiceItem (Fee breakdown)
├── Payment (Payment records)
├── FeeWaiver (Waiver requests)
└── FinancialAnalytics (Metrics and reports)
```

### Service Layer

- **FeeService**: Fee calculation and structure management
- **InvoiceService**: Invoice generation and management
- **PaymentService**: Payment processing and reconciliation
- **ScholarshipService**: Scholarship assignment and management
- **AnalyticsService**: Financial metrics and reporting

## Installation & Setup

### 1. Add to Django Settings

```python
# settings.py
INSTALLED_APPS = [
    # ... other apps
    'finance',
]

# Celery configuration for background tasks
CELERY_BEAT_SCHEDULE = {
    'daily-financial-report': {
        'task': 'finance.tasks.generate_daily_financial_report_task',
        'schedule': 60.0 * 60.0 * 24.0,  # Daily
    },
    'weekly-payment-reminders': {
        'task': 'finance.tasks.send_payment_reminders_task',
        'schedule': 60.0 * 60.0 * 24.0 * 7.0,  # Weekly
    },
}
```

### 2. Run Migrations

```bash
python manage.py makemigrations finance
python manage.py migrate
```

### 3. Create Fee Categories

```bash
python manage.py shell
```

```python
from finance.models import FeeCategory
from finance.constants import DEFAULT_FEE_CATEGORIES

# Create default fee categories
for category_data in DEFAULT_FEE_CATEGORIES:
    FeeCategory.objects.get_or_create(**category_data)
```

### 4. Set Up Permissions

```python
from finance.permissions import create_finance_permissions, create_finance_groups

# Create custom permissions
create_finance_permissions()

# Create user groups
create_finance_groups()
```

## Usage Examples

### Fee Structure Setup

```python
from finance.models import FeeStructure, FeeCategory
from academics.models import AcademicYear, Term, Section, Grade

# Create section-level base fee
academic_year = AcademicYear.objects.get(is_current=True)
term = Term.objects.get(is_current=True)
primary_section = Section.objects.get(name='Primary')
tuition_category = FeeCategory.objects.get(name='Tuition')

FeeStructure.objects.create(
    academic_year=academic_year,
    term=term,
    section=primary_section,
    fee_category=tuition_category,
    amount=5000.00,
    due_date=term.start_date + timedelta(days=30)
)

# Create grade-specific additional fee
grade5 = Grade.objects.get(name='Grade 5', section=primary_section)
lab_category = FeeCategory.objects.get(name='Laboratory')

FeeStructure.objects.create(
    academic_year=academic_year,
    term=term,
    grade=grade5,
    fee_category=lab_category,
    amount=500.00,
    due_date=term.start_date + timedelta(days=30)
)
```

### Fee Calculation

```python
from finance.services.fee_service import FeeService
from students.models import Student

student = Student.objects.get(admission_number='STU001')
academic_year = AcademicYear.objects.get(is_current=True)
term = Term.objects.get(is_current=True)

# Calculate total fees for student
fee_breakdown = FeeService.calculate_student_fees(student, academic_year, term)

print(f"Total Amount: {fee_breakdown['total_amount']}")
print(f"Discount Amount: {fee_breakdown['discount_amount']}")
print(f"Net Amount: {fee_breakdown['net_amount']}")
print(f"Base Fees: {len(fee_breakdown['base_fees'])}")
print(f"Special Fees: {len(fee_breakdown['special_fees'])}")
```

### Invoice Generation

```python
from finance.services.invoice_service import InvoiceService

# Generate single invoice
invoice = InvoiceService.generate_invoice(student, academic_year, term, created_by=request.user)

# Generate bulk invoices for a class
from academics.models import Class
class_obj = Class.objects.get(name='5A')
students = class_obj.student_set.filter(status='active')

results = InvoiceService.bulk_generate_invoices(
    list(students), academic_year, term, created_by=request.user
)

print(f"Created: {len(results['created'])}")
print(f"Skipped: {len(results['skipped'])}")
print(f"Errors: {len(results['errors'])}")
```

### Payment Processing

```python
from finance.services.payment_service import PaymentService

# Process payment
payment = PaymentService.process_single_payment(
    invoice_id=invoice.id,
    amount=2000.00,
    payment_method='cash',
    received_by=request.user,
    remarks='Partial payment'
)

print(f"Payment Receipt: {payment.receipt_number}")
print(f"Invoice Status: {invoice.status}")
print(f"Outstanding: {invoice.outstanding_amount}")
```

### Scholarship Management

```python
from finance.services.scholarship_service import ScholarshipService
from finance.models import Scholarship

# Create scholarship
scholarship = Scholarship.objects.create(
    name='Merit Scholarship',
    description='For academic excellence',
    discount_type='percentage',
    discount_value=10.00,
    criteria='merit',
    academic_year=academic_year,
    max_recipients=50
)

# Assign to student
student_scholarship = ScholarshipService.assign_scholarship(
    student=student,
    scholarship=scholarship,
    approved_by=request.user,
    remarks='Excellent academic performance'
)

# Get eligible students
eligible_students = ScholarshipService.get_eligible_students(scholarship)
```

### Financial Analytics

```python
from finance.services.analytics_service import FinancialAnalyticsService

# Collection metrics
metrics = FinancialAnalyticsService.calculate_collection_metrics(
    academic_year, term
)

print(f"Collection Rate: {metrics['collection_summary']['collection_rate']}%")
print(f"Total Outstanding: {metrics['collection_summary']['total_outstanding']}")

# Payment trends
trends = FinancialAnalyticsService.generate_payment_trends(academic_year, days=30)
print(f"Daily Trends: {len(trends['daily_trends'])}")

# Defaulter analysis
defaulters = FinancialAnalyticsService.analyze_defaulters(academic_year, term)
print(f"Total Defaulters: {defaulters['total_defaulters']}")
```

## API Endpoints

### Fee Management

```
GET    /api/finance/fee-categories/
POST   /api/finance/fee-categories/
GET    /api/finance/fee-structures/
POST   /api/finance/fee-structures/
POST   /api/finance/fee-structures/bulk_create/
GET    /api/finance/special-fees/
POST   /api/finance/special-fees/bulk_apply/
```

### Scholarship Management

```
GET    /api/finance/scholarships/
POST   /api/finance/scholarships/
GET    /api/finance/scholarships/{id}/eligible_students/
POST   /api/finance/scholarships/{id}/assign_to_students/
GET    /api/finance/student-scholarships/
POST   /api/finance/student-scholarships/{id}/approve/
```

### Invoice & Payment

```
GET    /api/finance/invoices/
POST   /api/finance/invoices/calculate_fees/
POST   /api/finance/invoices/bulk_generate/
GET    /api/finance/invoices/overdue/
GET    /api/finance/payments/
POST   /api/finance/payments/process_payment/
GET    /api/finance/payments/collection_summary/
```

### Analytics

```
GET    /api/finance/analytics/collection_metrics/
GET    /api/finance/analytics/payment_trends/
GET    /api/finance/analytics/defaulter_analysis/
GET    /api/finance/analytics/scholarship_impact/
```

## Management Commands

### Financial Analytics

```bash
# Calculate analytics for current year
python manage.py calculate_financial_analytics

# Calculate for specific year
python manage.py calculate_financial_analytics --academic-year 1

# Calculate for all years
python manage.py calculate_financial_analytics --all-years
```

### Bulk Operations

```bash
# Generate bulk invoices
python manage.py generate_bulk_invoices --academic-year 1 --term 1 --section 1

# Send payment reminders
python manage.py send_payment_reminders --days-overdue 7

# Process sibling discounts
python manage.py process_sibling_discounts --academic-year 1
```

### Payment Reconciliation

```bash
# Reconcile payments for today
python manage.py reconcile_payments

# Reconcile for specific date
python manage.py reconcile_payments --date 2024-01-15 --expected-cash 5000.00
```

## Configuration

### Settings

```python
# finance/constants.py

# Currency settings
CURRENCY_SYMBOL = '$'
CURRENCY_CODE = 'USD'

# Invoice settings
INVOICE_NUMBER_PREFIX = 'INV'
RECEIPT_NUMBER_PREFIX = 'RCP'

# Late fee settings
DEFAULT_LATE_FEE_PERCENTAGE = 5.00
DEFAULT_GRACE_PERIOD_DAYS = 7

# Business rules
ALLOW_OVERPAYMENT = True
ALLOW_PARTIAL_PAYMENTS = True
AUTO_ALLOCATE_ADVANCE_PAYMENTS = True
```

### Permissions

```python
# Custom permission groups
FINANCE_GROUPS = [
    'Finance Manager',  # Full access
    'Accountant',       # View and limited edit
    'Cashier',          # Payment processing
    'Finance Clerk',    # Basic data entry
    'Principal',        # Oversight and approval
]
```

## Background Tasks

### Scheduled Tasks

- **Daily Financial Report**: Generate daily collection summary
- **Weekly Payment Reminders**: Send reminders for overdue invoices
- **Monthly Late Fees**: Calculate and apply late charges
- **Quarterly Analytics Cleanup**: Remove old analytics data

### Async Operations

- **Bulk Invoice Generation**: Process large batches in background
- **Payment Processing**: Handle high-volume payment processing
- **Analytics Calculation**: Update metrics without blocking UI

## Security & Compliance

### Data Protection

- **Encrypted sensitive data**: Payment card information
- **Audit trail**: Complete activity logging
- **Role-based access**: Granular permission system
- **GDPR compliance**: User data rights and privacy

### Payment Security

- **PCI DSS compliance**: Credit card data handling
- **Secure transmission**: Encrypted payment processing
- **Fraud detection**: Unusual transaction monitoring
- **Access controls**: Payment authorization workflows

## Testing

### Unit Tests

```bash
# Run all finance tests
python manage.py test finance

# Run specific test categories
python manage.py test finance.tests.test_services
python manage.py test finance.tests.test_models
python manage.py test finance.tests.test_api
```

### Test Coverage

```bash
coverage run --source='finance' manage.py test finance
coverage report
coverage html
```

## Performance Optimization

### Database Optimization

- **Indexes**: Optimized for frequent queries
- **Query optimization**: Select/prefetch related objects
- **Pagination**: Large dataset handling
- **Connection pooling**: Efficient database connections

### Caching Strategy

- **Redis caching**: Frequent analytics queries
- **Cache invalidation**: Smart cache management
- **Query caching**: Expensive calculation results

### Background Processing

- **Celery integration**: Async task processing
- **Bulk operations**: Efficient batch processing
- **Queue management**: Priority-based task execution

## Troubleshooting

### Common Issues

**1. Duplicate Invoice Error**

```python
# Check existing invoices
Invoice.objects.filter(student=student, academic_year=year, term=term)

# Solution: Update existing invoice or use different term
```

**2. Payment Validation Errors**

```python
# Check invoice outstanding amount
invoice.outstanding_amount

# Validate payment method requirements
PaymentService.validate_payment_method(method, additional_data)
```

**3. Scholarship Assignment Failures**

```python
# Check scholarship availability
scholarship.has_available_slots

# Verify student eligibility
ScholarshipService.get_eligible_students(scholarship)
```

### Error Handling

```python
try:
    invoice = InvoiceService.generate_invoice(student, year, term)
except ValidationError as e:
    print(f"Validation error: {e}")
except Exception as e:
    print(f"Unexpected error: {e}")
    # Log error for debugging
```

## Migration Guide

### From Legacy System

1. **Export data**: Fee structures, student payments, outstanding balances
2. **Create fee categories**: Map legacy categories to new structure
3. **Import fee structures**: Use bulk creation APIs
4. **Import payment history**: Create payment records
5. **Generate invoices**: For current outstanding amounts
6. **Verify balances**: Reconcile imported vs calculated amounts

### Version Updates

- **Database migrations**: Run automatically with Django migrations
- **Data migrations**: Custom management commands for data updates
- **API changes**: Backward compatibility maintained where possible

## Support & Documentation

### Additional Resources

- **API Documentation**: `/api/docs/` (when enabled)
- **Admin Interface**: Django admin for data management
- **User Guides**: End-user documentation in `/docs/user/`
- **Developer Docs**: Technical documentation in `/docs/development/`

### Community

- **GitHub Issues**: Bug reports and feature requests
- **Discussions**: Community Q&A
- **Contributing**: Open source contribution guidelines

## License

This finance module is part of the School Management System and is licensed under the MIT License.

---

**Version**: 1.0.0  
**Last Updated**: December 2024  
**Maintainer**: Finance Module Team
