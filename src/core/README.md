# Core Module - Complete Documentation

## Overview

The Core module serves as the foundation of the School Management System, providing essential services, utilities, and infrastructure that other modules depend on. It handles system configuration, audit logging, analytics, security, and cross-cutting concerns.

## Architecture

```
core/
├── models.py              # Core data models
├── services.py           # Business logic services
├── api/                  # REST API endpoints
│   ├── views.py
│   ├── serializers.py
│   └── urls.py
├── management/commands/  # Management commands
├── middleware.py         # Custom middleware
├── tasks.py             # Celery background tasks
├── utils.py             # Utility functions
├── decorators.py        # Custom decorators
├── tests.py             # Comprehensive tests
└── templates/           # Web interface templates
```

## Key Features

### 1. System Configuration Management

- **Dynamic Settings**: Runtime-configurable system settings
- **Type Safety**: Strongly typed configuration values
- **Caching**: Automatic caching for performance
- **Audit Trail**: Track all configuration changes

### 2. Comprehensive Audit Logging

- **Automatic Tracking**: Middleware-based audit logging
- **Detailed Context**: IP addresses, user agents, session info
- **Content Tracking**: Before/after state for model changes
- **Performance Metrics**: Request duration tracking

### 3. Advanced Analytics Engine

- **Student Performance**: Individual and aggregate analytics
- **Class Performance**: Comparative analysis and rankings
- **Attendance Analytics**: Pattern recognition and trends
- **Financial Analytics**: Revenue tracking and collection rates
- **Teacher Performance**: Effectiveness metrics
- **Predictive Insights**: Early warning systems

### 4. Security Framework

- **Rate Limiting**: Configurable rate limiting
- **Security Events**: Comprehensive security logging
- **File Validation**: Secure file upload handling
- **Permission System**: Role-based access control

### 5. Background Task Processing

- **Analytics Calculation**: Automated analytics computation
- **System Maintenance**: Cleanup and optimization tasks
- **Backup Operations**: Automated database backups
- **Health Monitoring**: System health metrics collection

## Installation & Setup

### 1. Basic Installation

```bash
# Install required packages
pip install -r requirements/core.txt

# Add to Django settings
INSTALLED_APPS = [
    # ... other apps
    'core',
    # ... rest of apps
]

# Add middleware
MIDDLEWARE = [
    # ... existing middleware
    'core.middleware.AuditMiddleware',
    'core.middleware.MaintenanceModeMiddleware',
    'core.middleware.SecurityMiddleware',
    'core.middleware.PerformanceMiddleware',
]
```

### 2. Database Setup

```bash
# Run migrations
python manage.py migrate

# Create default settings
python manage.py shell
>>> from core.services import ConfigurationService
>>> ConfigurationService.initialize_default_settings()
```

### 3. Celery Configuration

```python
# settings.py
from core.settings.core_settings import CELERY_BEAT_SCHEDULE_CORE

CELERY_BEAT_SCHEDULE.update(CELERY_BEAT_SCHEDULE_CORE)
```

### 4. Initial Setup Command

```bash
# Setup academic year
python manage.py setup_academic_year \
    --year "2024-2025" \
    --start-date "2024-07-01" \
    --terms 3 \
    --create-sections \
    --create-sample-grades \
    --make-current
```

## API Reference

### System Settings API

```http
GET /api/core/settings/
POST /api/core/settings/
PATCH /api/core/settings/{id}/update_value/
GET /api/core/settings/by_category/?category=academic
POST /api/core/settings/bulk_update/
```

### Analytics API

```http
GET /api/core/analytics/student-performance/
GET /api/core/analytics/class-performance/
GET /api/core/analytics/attendance/
GET /api/core/analytics/financial/
GET /api/core/analytics/teacher-performance/
POST /api/core/analytics/calculate/
```

### Dashboard API

```http
GET /api/core/dashboard/
GET /api/core/system/metrics/
```

### Audit Logs API

```http
GET /api/core/audit-logs/
GET /api/core/audit-logs/user_activity/?user_id=1
GET /api/core/audit-logs/content_types/
```

## Service Layer

### ConfigurationService

```python
from core.services import ConfigurationService

# Get setting with default
value = ConfigurationService.get_setting('academic.terms_per_year', 3)

# Set setting
ConfigurationService.set_setting(
    'academic.terms_per_year',
    4,
    user=request.user,
    data_type='integer'
)

# Get settings by category
academic_settings = ConfigurationService.get_settings_by_category('academic')
```

### AuditService

```python
from core.services import AuditService

# Log action
AuditService.log_action(
    user=request.user,
    action='create',
    content_object=student,
    description='Created new student record',
    ip_address=request.META.get('REMOTE_ADDR')
)

# Get user activity
activity = AuditService.get_user_activity(user, days=30)

# Cleanup old logs
deleted_count = AuditService.cleanup_old_logs(days=365)
```

### AnalyticsService

```python
from core.services import AnalyticsService

# Calculate student analytics
AnalyticsService.calculate_student_performance(
    academic_year=academic_year,
    term=term,
    force_recalculate=True
)

# Calculate all analytics
AnalyticsService.calculate_class_performance()
AnalyticsService.calculate_attendance_analytics()
AnalyticsService.calculate_financial_analytics()
```

### SecurityService

```python
from core.services import SecurityService

# Check rate limit
allowed = SecurityService.check_rate_limit('user_123', 'login_attempt', 5, 15)

# Log security event
SecurityService.log_security_event(
    'failed_login_attempt',
    user=user,
    ip_address='192.168.1.1',
    details={'attempts': 3}
)

# Validate file upload
errors = SecurityService.validate_file_upload(
    file,
    allowed_extensions=['pdf', 'doc'],
    max_size_mb=5
)
```

## Utility Functions

### ValidationUtils

```python
from core.utils import ValidationUtils

# Validate phone number
is_valid = ValidationUtils.validate_phone_number('+1234567890')

# Validate admission number
is_valid = ValidationUtils.validate_admission_number('STU123456')

# Validate percentage
is_valid = ValidationUtils.validate_percentage(85.5)

# Validate marks
is_valid = ValidationUtils.validate_marks(75, max_marks=100)
```

### DateUtils

```python
from core.utils import DateUtils

# Get academic year
academic_year = DateUtils.get_academic_year_from_date(datetime.now())

# Calculate age
age = DateUtils.calculate_age(birth_date)

# Get working days
working_days = DateUtils.get_working_days(start_date, end_date)
```

### FormatUtils

```python
from core.utils import FormatUtils

# Format currency
formatted = FormatUtils.format_currency(1234.56, 'USD')  # $1,234.56

# Format percentage
formatted = FormatUtils.format_percentage(85.5)  # 85.5%

# Format phone number
formatted = FormatUtils.format_phone_number('1234567890')
```

## Decorators

### Authentication & Authorization

```python
from core.decorators import require_role, system_admin_required

@require_role('teacher', 'admin')
def teacher_view(request):
    pass

@system_admin_required
def admin_only_view(request):
    pass
```

### Audit Logging

```python
from core.decorators import audit_action

@audit_action(action='create', description='Created student record')
def create_student(request):
    pass
```

### Rate Limiting

```python
from core.decorators import rate_limit

@rate_limit(max_attempts=5, window_minutes=15)
def sensitive_operation(request):
    pass
```

## Background Tasks

### Manual Task Execution

```python
from core.tasks import calculate_all_analytics, backup_database

# Queue analytics calculation
task = calculate_all_analytics.delay(
    academic_year_id=1,
    term_id=1,
    force_recalculate=True
)

# Queue database backup
backup_task = backup_database.delay(compress=True)
```

### Scheduled Tasks

Tasks are automatically scheduled via Celery Beat:

- **Daily Analytics**: 2 AM daily
- **System Health**: Every 15 minutes
- **Audit Cleanup**: Weekly on Sundays
- **Database Backup**: Weekly on Saturdays
- **System Monitoring**: Every 30 minutes

## Management Commands

### Setup Commands

```bash
# Setup academic year with structure
python manage.py setup_academic_year \
    --year "2024-2025" \
    --start-date "2024-07-01" \
    --terms 3 \
    --create-sections \
    --create-sample-grades \
    --make-current

# Generate sample data for testing
python manage.py generate_sample_data \
    --students 100 \
    --teachers 20 \
    --classes 15 \
    --subjects 10
```

### Analytics Commands

```bash
# Calculate specific analytics type
python manage.py calculate_analytics \
    --type student \
    --academic-year "2024-2025" \
    --term "First Term" \
    --force

# Calculate all analytics
python manage.py calculate_analytics --type all --force
```

### Maintenance Commands

```bash
# Backup database
python manage.py backup_database \
    --output /path/to/backup.sql.gz \
    --compress \
    --clean-old 30

# Clean old audit logs
python manage.py shell
>>> from core.tasks import cleanup_old_audit_logs
>>> cleanup_old_audit_logs.delay(days=365)
```

## Web Interface

### Dashboard Features

- **Role-based Dashboards**: Customized for different user types
- **Real-time Analytics**: Live performance metrics
- **Quick Actions**: Role-specific shortcuts
- **System Health**: Status indicators and alerts

### Admin Interface

- **System Settings**: Web-based configuration management
- **Audit Logs**: Searchable and filterable log viewer
- **User Management**: User administration tools
- **System Health**: Monitoring dashboard

### Templates Structure

```
templates/core/
├── base.html              # Base template with navigation
├── dashboard.html         # Main dashboard
├── system_admin.html      # System administration
├── system_settings.html   # Settings management
├── audit_logs.html        # Audit log viewer
├── system_health.html     # Health monitoring
└── partials/
    ├── navbar.html        # Navigation bar
    ├── sidebar.html       # Sidebar navigation
    └── footer.html        # Footer
```

## Security Considerations

### Authentication

- JWT token support
- Session-based authentication
- Multi-factor authentication ready
- OAuth integration support

### Authorization

- Role-based access control
- Permission-based restrictions
- Object-level permissions
- API rate limiting

### Data Protection

- Input validation and sanitization
- SQL injection prevention
- XSS protection
- CSRF protection
- Secure file upload handling

### Audit Trail

- Complete activity logging
- Security event tracking
- Failed login monitoring
- Permission change logging

## Performance Optimization

### Caching Strategy

- **System Settings**: 1-hour cache
- **Analytics Data**: 30-minute cache
- **Dashboard Data**: 15-minute cache
- **User Sessions**: Redis-based

### Database Optimization

- Optimized queries with select_related/prefetch_related
- Database indexing for frequent lookups
- Query result caching
- Connection pooling

### Background Processing

- Async analytics calculation
- Queue-based task processing
- Task result caching
- Failure retry mechanisms

## Monitoring & Alerting

### System Health Metrics

- Database performance
- Cache hit rates
- Response times
- Error rates
- Storage usage
- Active users

### Alerts Configuration

```python
# Configure alerts in settings
CORE_ALERTS = {
    'disk_usage_threshold': 85,  # Percentage
    'response_time_threshold': 2000,  # Milliseconds
    'error_rate_threshold': 5,  # Percentage
    'cache_hit_rate_threshold': 70,  # Percentage
}
```

### Health Check Endpoints

```http
GET /api/core/system/health/
GET /api/core/system/metrics/
```

## Testing

### Running Tests

```bash
# Run all core tests
python manage.py test core

# Run specific test classes
python manage.py test core.tests.ConfigurationServiceTests

# Run with coverage
coverage run --source='.' manage.py test core
coverage report
coverage html
```

### Test Categories

- **Unit Tests**: Service layer testing
- **Integration Tests**: API endpoint testing
- **Model Tests**: Database model testing
- **Utility Tests**: Helper function testing
- **Security Tests**: Permission and validation testing

## Troubleshooting

### Common Issues

#### Analytics Not Calculating

```bash
# Check Celery workers
celery -A config inspect active

# Manually trigger calculation
python manage.py calculate_analytics --type all --force

# Check for data issues
python manage.py shell
>>> from core.services import AnalyticsService
>>> # Debug analytics calculation
```

#### Settings Not Loading

```bash
# Clear cache
python manage.py shell
>>> from django.core.cache import cache
>>> cache.clear()

# Reinitialize settings
>>> from core.services import ConfigurationService
>>> ConfigurationService.initialize_default_settings()
```

#### Audit Logs Not Working

```bash
# Check middleware configuration
# Ensure AuditMiddleware is in MIDDLEWARE setting

# Check excluded paths
# Verify path not in AUDIT_EXCLUDED_PATHS

# Test manually
python manage.py shell
>>> from core.services import AuditService
>>> AuditService.log_action(action='test', description='Test log')
```

#### Performance Issues

```bash
# Check slow queries
# Enable Django debug toolbar in development

# Check cache status
python manage.py shell
>>> from django.core.cache import cache
>>> cache._cache.info()  # Redis info

# Monitor Celery tasks
celery -A config flower
```

### Log Files

```bash
# Check log files
tail -f logs/core.log
tail -f logs/audit.log
tail -f logs/security.log

# Django logs
tail -f logs/django.log
```

### Database Issues

```bash
# Check database connections
python manage.py dbshell
\l  # List databases
\dt  # List tables

# Check migrations
python manage.py showmigrations core

# Reset migrations (development only)
python manage.py migrate core zero
python manage.py migrate core
```

## Deployment

### Production Setup

1. **Environment Configuration**

```bash
# Set production environment variables
export DJANGO_SETTINGS_MODULE=config.settings.production
export DEBUG=False
export DATABASE_URL=postgres://user:pass@host:port/db
export REDIS_URL=redis://host:port/db
```

2. **Static Files**

```bash
# Collect static files
python manage.py collectstatic --noinput

# Configure Nginx for static file serving
# See nginx configuration in core_settings.py
```

3. **Background Services**

```bash
# Start Celery worker
celery -A config worker -l info

# Start Celery beat
celery -A config beat -l info

# Start Celery flower (monitoring)
celery -A config flower --port=5555
```

4. **Database Setup**

```bash
# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Initialize system
python manage.py setup_academic_year --year "2024-2025" --make-current
```

### Docker Deployment

```bash
# Build and start services
docker-compose -f docker-compose.prod.yml up -d

# Run migrations in container
docker-compose exec web python manage.py migrate

# Create superuser
docker-compose exec web python manage.py createsuperuser
```

### Health Checks

```bash
# Application health
curl http://localhost:8000/api/core/system/health/

# Database health
python manage.py check --database default

# Celery health
celery -A config inspect ping
```

## Contributing

### Code Style

- Follow PEP 8 guidelines
- Use Black for code formatting
- Use isort for import sorting
- Add type hints where applicable
- Write comprehensive docstrings

### Testing Requirements

- Maintain 90%+ test coverage
- Write tests for all new features
- Include integration tests for APIs
- Test error conditions and edge cases

### Documentation

- Update this README for new features
- Add docstrings to all functions/classes
- Include usage examples
- Document breaking changes

## License

This core module is part of the School Management System and is licensed under the MIT License. See the main project LICENSE file for details.

## Support

For support and questions:

- Check the troubleshooting section above
- Review the test cases for usage examples
- Submit issues via the project's issue tracker
- Contact the development team

---

**Core Module Version**: 1.0.0  
**Last Updated**: December 2024  
**Django Version**: 4.2+  
**Python Version**: 3.10+
