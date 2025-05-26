# Communications Module

A comprehensive communication system for the School Management System, providing multi-channel messaging, notifications, announcements, and analytics capabilities.

## 🌟 Features

### Core Communication Features

- **Multi-channel Notifications**: In-app, Email, SMS, Push notifications
- **Announcements**: School-wide or targeted announcements
- **Direct Messaging**: User-to-user private messaging
- **Bulk Messaging**: Mass communication campaigns
- **Message Templates**: Reusable message templates with variables
- **User Preferences**: Granular communication preferences per user

### Advanced Features

- **Real-time Analytics**: Communication delivery and engagement metrics
- **Background Processing**: Celery-powered bulk operations
- **Smart Targeting**: Role-based and criteria-based user targeting
- **Template Engine**: Django template system for dynamic content
- **Audit Logging**: Complete communication activity tracking
- **Mobile API**: RESTful API for mobile applications

### Analytics & Reporting

- **Delivery Metrics**: Track message delivery rates across channels
- **Engagement Analytics**: Open rates, click rates, read receipts
- **User Engagement**: Individual user communication statistics
- **Performance Dashboards**: Visual analytics for administrators
- **Historical Reporting**: Long-term communication trends

## 📋 Requirements

### System Requirements

- Python 3.10+
- Django 4.2+
- PostgreSQL 14+ (recommended)
- Redis 6+ (for caching and Celery)

### Python Dependencies

```txt
django>=4.2.0
djangorestframework>=3.14.0
celery>=5.3.0
redis>=4.5.0
django-filter>=23.0
psycopg2-binary>=2.9.0
```

### Optional Dependencies

```txt
# For SMS functionality
twilio>=8.0.0

# For push notifications
pyfcm>=1.5.4

# For advanced email features
sendgrid>=6.10.0

# For message queuing alternatives
django-rq>=2.8.0
```

## 🚀 Installation

### 1. Add to Django Settings

```python
# settings.py

INSTALLED_APPS = [
    # ... your other apps
    'src.communications',
    'rest_framework',
    'django_filters',
]

# Communication Settings
COMMUNICATION_SETTINGS = {
    'DEFAULT_CHANNELS': ['in_app'],
    'BATCH_SIZE': 100,
    'RATE_LIMIT_PER_HOUR': 1000,
    'ANALYTICS_RETENTION_DAYS': 365,
    'CLEANUP_DAYS': 90,
}

# Email Configuration
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'your-email@gmail.com'
EMAIL_HOST_PASSWORD = 'your-app-password'
DEFAULT_FROM_EMAIL = 'School Management System <noreply@yourschool.com>'

# Celery Configuration (for background tasks)
CELERY_BROKER_URL = 'redis://localhost:6379/0'
CELERY_RESULT_BACKEND = 'redis://localhost:6379/0'

# Optional: SMS Configuration (Twilio)
TWILIO_ACCOUNT_SID = 'your-account-sid'
TWILIO_AUTH_TOKEN = 'your-auth-token'
TWILIO_PHONE_NUMBER = '+1234567890'

# Optional: Push Notification Configuration
FCM_SERVER_KEY = 'your-fcm-server-key'
```

### 2. URL Configuration

```python
# urls.py
from django.urls import path, include

urlpatterns = [
    # ... your other URL patterns
    path('communications/', include('src.communications.urls')),
    path('api/communications/', include('src.communications.api.urls')),
]
```

### 3. Database Migration

```bash
python manage.py makemigrations communications
python manage.py migrate communications
```

### 4. Create Default Templates (Optional)

```python
# Run in Django shell
python manage.py shell

>>> from src.communications import setup_default_templates
>>> setup_default_templates()
```

### 5. Start Celery Workers (For Background Tasks)

```bash
# Start Celery worker
celery -A your_project worker -l info

# Start Celery beat (for scheduled tasks)
celery -A your_project beat -l info
```

## 📖 Usage Examples

### Basic Notifications

```python
from src.communications.services import NotificationService
from src.communications.models import Priority, CommunicationChannel

# Send a simple notification
notification = NotificationService.create_notification(
    user=user,
    title="Welcome to the System",
    content="Your account has been created successfully!",
    notification_type="welcome",
    priority=Priority.HIGH
)

# Send multi-channel notification
notification = NotificationService.create_notification(
    user=user,
    title="Fee Payment Reminder",
    content="Your fee payment is due tomorrow.",
    notification_type="financial",
    priority=Priority.MEDIUM,
    channels=[
        CommunicationChannel.EMAIL,
        CommunicationChannel.SMS,
        CommunicationChannel.IN_APP
    ]
)

# Bulk notifications
users = User.objects.filter(is_active=True)
notifications = NotificationService.bulk_create_notifications(
    users=users,
    title="System Maintenance Notice",
    content="The system will be under maintenance tonight.",
    notification_type="system",
    priority=Priority.HIGH
)
```

### Announcements

```python
from src.communications.services import AnnouncementService
from src.communications.models import TargetAudience

# Create school-wide announcement
announcement = AnnouncementService.create_announcement(
    title="School Holiday Notice",
    content="School will be closed for the summer holidays from June 1-15.",
    created_by=admin_user,
    target_audience=TargetAudience.ALL,
    priority=Priority.HIGH,
    channels=[CommunicationChannel.EMAIL, CommunicationChannel.IN_APP]
)

# Targeted announcement for students only
announcement = AnnouncementService.create_announcement(
    title="Exam Schedule Released",
    content="The final exam schedule has been published. Please check your timetable.",
    created_by=admin_user,
    target_audience=TargetAudience.STUDENTS,
    target_grades=[9, 10, 11, 12],  # Specific grades
    priority=Priority.MEDIUM
)
```

### Direct Messaging

```python
from src.communications.services import MessagingService

# Create a conversation
thread = MessagingService.create_thread(
    subject="Regarding Assignment Submission",
    participants=[teacher, student],
    created_by=teacher,
    is_group=False
)

# Send a message
message = MessagingService.send_message(
    thread=thread,
    sender=teacher,
    content="Please submit your assignment by Friday."
)

# Mark message as read
MessagingService.mark_message_as_read(message, student)
```

### Message Templates

```python
from src.communications.models import MessageTemplate

# Create a template
template = MessageTemplate.objects.create(
    name="Fee Reminder Template",
    template_type="financial",
    subject_template="Fee Payment Reminder - {{ student_name }}",
    content_template="""
    Dear {{ parent_name }},

    This is a reminder that the fee payment for {{ student_name }}
    (Class: {{ class_name }}) is due on {{ due_date }}.

    Amount Due: {{ amount }}

    Please ensure payment is made by the due date.

    Thank you,
    {{ school_name }} Administration
    """,
    supported_channels=['email', 'sms'],
    created_by=admin_user
)

# Use template to send personalized messages
context = {
    'parent_name': 'John Doe',
    'student_name': 'Jane Doe',
    'class_name': 'Grade 5 North',
    'due_date': '2024-06-15',
    'amount': '$500.00',
    'school_name': 'ABC School'
}

rendered_content = template.render_content(context)
rendered_subject = template.render_subject(context)
```

### Analytics

```python
from src.communications.services import CommunicationAnalyticsService

# Get communication summary
summary = CommunicationAnalyticsService.get_communication_summary(days=30)
print(f"Total emails sent: {summary['total_emails']}")
print(f"Average delivery rate: {summary['avg_email_delivery_rate']}%")

# Calculate daily analytics
analytics = CommunicationAnalyticsService.calculate_daily_analytics()

# Get user engagement stats
user_stats = CommunicationAnalyticsService.get_user_engagement_stats(user)
print(f"User read rate: {user_stats['read_rate']}%")
```

## 🔧 API Usage

### Authentication

All API endpoints require authentication. Include the authorization header:

```http
Authorization: Bearer your-jwt-token
```

### Notification Endpoints

```bash
# Get user notifications
GET /api/communications/notifications/

# Create notification
POST /api/communications/notifications/create_notification/
{
    "user_ids": [1, 2, 3],
    "title": "Test Notification",
    "content": "This is a test notification",
    "notification_type": "test",
    "priority": "medium",
    "channels": ["in_app", "email"]
}

# Mark notification as read
POST /api/communications/notifications/{id}/mark_as_read/

# Get unread count
GET /api/communications/notifications/unread_count/
```

### Announcement Endpoints

```bash
# List announcements
GET /api/communications/announcements/

# Create announcement
POST /api/communications/announcements/
{
    "title": "School Event",
    "content": "Annual sports day on Friday",
    "target_audience": "students",
    "priority": "high",
    "channels": ["in_app", "email"]
}

# Get active announcements
GET /api/communications/announcements/active/
```

### Messaging Endpoints

```bash
# List message threads
GET /api/communications/threads/

# Create new thread
POST /api/communications/threads/create_thread/
{
    "subject": "Question about homework",
    "participant_ids": [2, 3],
    "initial_message": "I have a question about today's homework."
}

# Send message in thread
POST /api/communications/threads/{id}/send_message/
{
    "content": "Thank you for your help!"
}

# Get messages in thread
GET /api/communications/threads/{id}/messages/
```

### Analytics Endpoints

```bash
# Get analytics summary
GET /api/communications/analytics/summary/?days=30

# Get user engagement stats
GET /api/communications/analytics/user_engagement/?user_id=1

# Get channel performance
GET /api/communications/analytics/channel_performance/?days=7
```

## 🎛️ Management Commands

### Send Bulk Notifications

```bash
python manage.py send_bulk_notification \
    --title "System Maintenance" \
    --content "The system will be down for maintenance tonight." \
    --audience students \
    --priority high \
    --channels in_app email
```

### Calculate Analytics

```bash
# Calculate for specific date
python manage.py calculate_communication_analytics --date 2024-06-01

# Calculate for date range
python manage.py calculate_communication_analytics \
    --start-date 2024-06-01 \
    --end-date 2024-06-30

# Calculate for last 30 days
python manage.py calculate_communication_analytics --days 30
```

### Cleanup Old Records

```bash
# Clean up records older than 90 days
python manage.py cleanup_communications --days 90

# Dry run to see what would be deleted
python manage.py cleanup_communications --days 90 --dry-run

# Clean up only communication logs
python manage.py cleanup_communications --days 90 --logs-only
```

### Send Test Notification

```bash
python manage.py send_test_notification \
    --user admin \
    --channels in_app email sms
```

## 📊 Background Tasks

### Celery Task Configuration

```python
# celery.py
from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    # Calculate daily analytics at 2 AM
    'calculate-daily-communication-analytics': {
        'task': 'src.communications.tasks.calculate_daily_analytics_task',
        'schedule': crontab(hour=2, minute=0),
    },

    # Send scheduled announcements every 5 minutes
    'send-scheduled-announcements': {
        'task': 'src.communications.tasks.send_scheduled_announcements_task',
        'schedule': crontab(minute='*/5'),
    },

    # Send digest notifications at 8 AM
    'send-digest-notifications': {
        'task': 'src.communications.tasks.send_digest_notifications_task',
        'schedule': crontab(hour=8, minute=0),
    },

    # Cleanup old communications weekly
    'cleanup-old-communications': {
        'task': 'src.communications.tasks.cleanup_old_communications_task',
        'schedule': crontab(hour=3, minute=0, day_of_week=1),  # Monday 3 AM
        'kwargs': {'days': 90}
    },
}
```

### Running Background Tasks

```bash
# Send bulk notifications (background)
from src.communications.tasks import send_bulk_notification_task

task = send_bulk_notification_task.delay(
    user_ids=[1, 2, 3],
    title="Background Test",
    content="This notification was sent via background task",
    notification_type="test"
)

# Check task status
print(f"Task ID: {task.id}")
print(f"Task Status: {task.status}")
print(f"Task Result: {task.result}")
```

## 🔧 Configuration Options

### Communication Preferences

Users can configure their communication preferences:

```python
from src.communications.models import CommunicationPreference

# Set user preferences
preference, created = CommunicationPreference.objects.get_or_create(
    user=user,
    defaults={
        'email_enabled': True,
        'sms_enabled': False,
        'push_enabled': True,
        'academic_notifications': True,
        'financial_notifications': True,
        'quiet_hours_start': '22:00',
        'quiet_hours_end': '08:00',
        'digest_frequency': 'daily'
    }
)
```

### Channel Configuration

Configure communication channels in settings:

```python
# settings.py
COMMUNICATION_CHANNELS = {
    'email': {
        'enabled': True,
        'rate_limit': 1000,  # per hour
        'retry_attempts': 3,
        'retry_delay': 300,  # seconds
    },
    'sms': {
        'enabled': True,
        'rate_limit': 100,  # per hour
        'max_length': 160,
        'provider': 'twilio'
    },
    'push': {
        'enabled': True,
        'rate_limit': 5000,  # per hour
        'provider': 'fcm'
    }
}
```

## 🛠️ Customization

### Custom Notification Types

Create custom notification types:

```python
# In your app's models.py
from src.communications.services import NotificationService

def send_grade_notification(student, grade, subject):
    """Send notification when a grade is posted"""
    return NotificationService.create_notification(
        user=student.user,
        title=f"New Grade Posted - {subject}",
        content=f"Your grade for {subject} is {grade}",
        notification_type="grade_posted",
        reference_id=str(grade.id),
        reference_type="grade",
        channels=['in_app', 'email']
    )
```

### Custom Email Templates

Create custom email templates:

```html
<!-- templates/emails/custom_notification.html -->
<!DOCTYPE html>
<html>
	<head>
		<title>{{ notification.title }}</title>
	</head>
	<body>
		<h1>{{ school_name }}</h1>
		<h2>{{ notification.title }}</h2>
		<p>{{ notification.content|linebreaks }}</p>

		<p>
			Best regards,<br />
			{{ school_name }} Team
		</p>
	</body>
</html>
```

### Custom Message Processors

Create custom message processors:

```python
from src.communications.utils import ContentFormatter

class CustomContentFormatter(ContentFormatter):
    @staticmethod
    def format_for_mobile_app(content: str) -> dict:
        """Format content specifically for mobile app"""
        return {
            'text': strip_tags(content),
            'html': content,
            'preview': content[:100] + '...' if len(content) > 100 else content
        }
```

## 🐛 Troubleshooting

### Common Issues

#### 1. Emails Not Sending

```bash
# Check email configuration
python manage.py shell
>>> from django.core.mail import send_mail
>>> send_mail('Test', 'Test message', 'from@example.com', ['to@example.com'])
```

#### 2. Background Tasks Not Running

```bash
# Check Celery worker status
celery -A your_project inspect active

# Check Redis connection
redis-cli ping
```

#### 3. High Memory Usage

```python
# Adjust batch sizes in settings
COMMUNICATION_SETTINGS = {
    'BATCH_SIZE': 50,  # Reduce from default 100
    'RATE_LIMIT_PER_HOUR': 500,  # Reduce rate limit
}
```

#### 4. Database Performance

```sql
-- Add database indexes for better performance
CREATE INDEX CONCURRENTLY idx_notifications_user_unread
ON communications_notification(user_id)
WHERE is_read = false;

CREATE INDEX CONCURRENTLY idx_communications_log_timestamp
ON communications_communicationlog(timestamp DESC);
```

### Debugging

Enable debug logging:

```python
# settings.py
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'file': {
            'level': 'DEBUG',
            'class': 'logging.FileHandler',
            'filename': 'communications.log',
        },
    },
    'loggers': {
        'src.communications': {
            'handlers': ['file'],
            'level': 'DEBUG',
            'propagate': True,
        },
    },
}
```

### Performance Monitoring

Monitor communication performance:

```python
from src.communications.utils import get_communication_health_status

# Check system health
health = get_communication_health_status()
print(f"System Status: {health['status']}")
print(f"Failure Rate: {health['failure_rate']}%")
```

## 📈 Performance Optimization

### Database Optimization

1. **Indexes**: Ensure proper indexing on frequently queried fields
2. **Pagination**: Use pagination for large datasets
3. **Query Optimization**: Use select_related and prefetch_related
4. **Archiving**: Regularly archive old communication records

### Caching

```python
# Use Redis for caching frequent queries
from django.core.cache import cache

def get_user_unread_count(user_id):
    cache_key = f"unread_count_{user_id}"
    count = cache.get(cache_key)

    if count is None:
        count = Notification.objects.filter(
            user_id=user_id,
            is_read=False
        ).count()
        cache.set(cache_key, count, 300)  # Cache for 5 minutes

    return count
```

### Background Processing

```python
# Use Celery for heavy operations
from src.communications.tasks import send_bulk_notification_task

# Instead of synchronous processing
notifications = NotificationService.bulk_create_notifications(users, ...)

# Use asynchronous task
task = send_bulk_notification_task.delay(user_ids, title, content, ...)
```

## 🧪 Testing

### Running Tests

```bash
# Run all communication tests
python manage.py test src.communications

# Run specific test cases
python manage.py test src.communications.tests.CommunicationModelsTestCase

# Run with coverage
coverage run --source='src.communications' manage.py test src.communications
coverage report
```

### Test Data Setup

```python
# Create test data
from django.test import TestCase
from src.communications.models import *

class CommunicationTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com'
        )

        self.notification = Notification.objects.create(
            user=self.user,
            title="Test Notification",
            content="Test content",
            notification_type="test"
        )
```

## 📚 Additional Resources

### Related Documentation

- [Django REST Framework Documentation](https://www.django-rest-framework.org/)
- [Celery Documentation](https://docs.celeryproject.org/)
- [Redis Documentation](https://redis.io/documentation)

### Integration Examples

- [Email Provider Integration](examples/email_providers.md)
- [SMS Provider Integration](examples/sms_providers.md)
- [Push Notification Setup](examples/push_notifications.md)

### Best Practices

- [Communication Security](docs/security.md)
- [Performance Guidelines](docs/performance.md)
- [Monitoring Setup](docs/monitoring.md)

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Ensure all tests pass
6. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

For support and questions:

- Create an issue on GitHub
- Check the troubleshooting guide above
- Review the test cases for usage examples
- Contact the development team

---

**Communications Module v1.0.0** - Built with ❤️ for School Management System
