# Assignments Module

A comprehensive assignment management system for the School Management System that handles the complete assignment lifecycle from creation to grading and analytics.

## Table of Contents

- [Features](#features)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [API Documentation](#api-documentation)
- [Models](#models)
- [Services](#services)
- [Middleware](#middleware)
- [Template Tags](#template-tags)
- [Testing](#testing)
- [Contributing](#contributing)

## Features

### Core Assignment Management

- **Assignment Creation**: Teachers can create assignments with detailed instructions, file attachments, and custom settings
- **Status Management**: Draft, Published, Closed, and Archived statuses with automated workflow
- **Deadline Management**: Due date tracking with automated reminders and overdue detection
- **File Attachments**: Support for multiple file types with size and format validation
- **Difficulty Levels**: Easy, Medium, and Hard difficulty classification

### Submission System

- **Student Submissions**: Online text submissions and file uploads
- **Late Submission Handling**: Configurable late penalties and grace periods
- **Revision Tracking**: Multiple submission attempts with revision history
- **Submission Methods**: Online, Physical, or Both submission types
- **File Validation**: Automatic file type and size validation based on assignment settings

### Advanced Grading

- **Rubric-Based Grading**: Create detailed rubrics with weighted criteria
- **Bulk Grading**: Grade multiple submissions simultaneously via CSV import
- **Grade Calculation**: Automatic percentage and letter grade calculation
- **Feedback System**: Structured feedback with strengths and improvement areas
- **Grade Analytics**: Performance statistics and trend analysis

### Plagiarism Detection

- **Content Similarity**: Automatic detection of similar content between submissions
- **Batch Processing**: Check all submissions for an assignment simultaneously
- **Threshold Configuration**: Customizable similarity thresholds for flagging
- **Detailed Reports**: Comprehensive similarity analysis with matched content

### Analytics and Reporting

- **Student Analytics**: Individual performance tracking and trend analysis
- **Teacher Analytics**: Assignment effectiveness and grading efficiency metrics
- **Class Analytics**: Class-wide performance comparisons and rankings
- **System Analytics**: Institution-wide assignment statistics and insights

### Communication Features

- **Comment System**: Discussion threads on assignments with reply functionality
- **Notifications**: Email and in-app notifications for key events
- **Deadline Reminders**: Automated reminders before assignment due dates
- **Grade Notifications**: Instant notifications when grades are available

### Administrative Tools

- **Bulk Operations**: Mass publish, close, or delete assignments
- **Data Export**: Export assignment and submission data in multiple formats
- **Template System**: Save and reuse assignment templates
- **Calendar Integration**: Assignment deadlines in calendar views

## Installation

### Prerequisites

- Django 4.2+
- Python 3.10+
- PostgreSQL 14+ (recommended)
- Redis 6+ (for caching and tasks)
- Celery (for background tasks)

### Required Packages

```bash
pip install django djangorestframework
pip install django-filter django-cors-headers
pip install celery redis
pip install Pillow  # For image processing
pip install pandas openpyxl  # For Excel export
pip install python-docx  # For document processing
```

### Installation Steps

1. **Add to INSTALLED_APPS**:

```python
INSTALLED_APPS = [
    # ... other apps
    'assignments',
    'rest_framework',
    'django_filters',
    'corsheaders',
]
```

2. **Configure Database**:

```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'school_management',
        'USER': 'your_user',
        'PASSWORD': 'your_password',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}
```

3. **Configure Cache** (Redis):

```python
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': 'redis://127.0.0.1:6379/1',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        }
    }
}
```

4. **Configure Celery**:

```python
# celery.py
import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
app = Celery('school_management')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

# settings.py
CELERY_BROKER_URL = 'redis://localhost:6379/0'
CELERY_RESULT_BACKEND = 'redis://localhost:6379/0'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
```

5. **Add Middleware**:

```python
MIDDLEWARE = [
    # ... other middleware
    'assignments.middleware.AssignmentDeadlineNotificationMiddleware',
    'assignments.middleware.AssignmentAccessControlMiddleware',
    'assignments.middleware.AssignmentActivityTrackingMiddleware',
]
```

6. **Run Migrations**:

```bash
python manage.py makemigrations assignments
python manage.py migrate
```

7. **Load Initial Data** (optional):

```bash
python manage.py assignment_management --generate-sample-data --count 10
```

## Configuration

### Assignment Settings

```python
# settings.py
ASSIGNMENTS_SETTINGS = {
    'MAX_FILE_SIZE_MB': 50,
    'ALLOWED_FILE_TYPES': ['pdf', 'doc', 'docx', 'txt', 'jpg', 'jpeg', 'png'],
    'DEFAULT_LATE_PENALTY': 10,  # Percentage
    'PLAGIARISM_THRESHOLD': 30,  # Percentage
    'AUTO_GRADE_ENABLED': False,
    'PEER_REVIEW_ENABLED': True,
    'NOTIFICATION_DAYS_BEFORE': 2,
    'BATCH_SIZE': 100,
}
```

### Email Configuration

```python
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'your-email@gmail.com'
EMAIL_HOST_PASSWORD = 'your-app-password'
DEFAULT_FROM_EMAIL = 'School Management System <noreply@yourschool.edu>'
```

### File Storage Configuration

```python
# For production, use cloud storage
DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
AWS_ACCESS_KEY_ID = 'your-access-key'
AWS_SECRET_ACCESS_KEY = 'your-secret-key'
AWS_STORAGE_BUCKET_NAME = 'your-bucket'
AWS_S3_REGION_NAME = 'us-east-1'
```

## Usage

### For Teachers

#### Creating Assignments

```python
from assignments.services import AssignmentService

# Create assignment
assignment_data = {
    'title': 'Math Quiz Chapter 5',
    'description': 'Quiz covering algebra basics',
    'class_id': class_object,
    'subject': subject_object,
    'term': term_object,
    'due_date': timezone.now() + timedelta(days=7),
    'total_marks': 100,
    'passing_marks': 60,
    'submission_type': 'online',
    'difficulty_level': 'medium'
}

assignment = AssignmentService.create_assignment(teacher, assignment_data)
```

#### Publishing Assignments

```python
# Publish assignment (sends notifications to students)
AssignmentService.publish_assignment(assignment.id)
```

#### Grading Submissions

```python
from assignments.services import GradingService

grading_data = {
    'marks_obtained': 85,
    'teacher_remarks': 'Excellent work on problem solving!',
    'strengths': 'Clear methodology and correct calculations',
    'improvements': 'Work on showing more detailed steps'
}

graded_submission = GradingService.grade_submission(
    submission_id, teacher, grading_data
)
```

### For Students

#### Submitting Assignments

```python
from assignments.services import SubmissionService

submission_data = {
    'content': 'My assignment solution text...',
    'submission_method': 'online',
    'student_remarks': 'I had trouble with question 3'
}

submission = SubmissionService.create_submission(
    student, assignment_id, submission_data
)
```

### For Administrators

#### Analytics and Reporting

```python
from assignments.services.analytics_service import AssignmentAnalyticsService

# Get system-wide analytics
system_analytics = AssignmentAnalyticsService.get_system_wide_analytics()

# Get teacher performance
teacher_analytics = AssignmentAnalyticsService.get_teacher_analytics(teacher_id)

# Get student performance
student_analytics = AssignmentAnalyticsService.get_student_performance_analytics(student_id)
```

#### Management Commands

```bash
# Check overdue assignments
python manage.py assignment_management --check-overdue

# Send deadline reminders
python manage.py assignment_management --send-reminders --days-ahead 2

# Calculate analytics
python manage.py assignment_management --calculate-analytics

# Bulk grade from CSV
python manage.py assignment_management --bulk-grade --assignment-id 123 --csv-file grades.csv

# Export data
python manage.py assignment_management --export-data --format csv --output assignments.csv

# Run plagiarism check
python manage.py assignment_management --plagiarism-check --assignment-id 123

# Clean up old files
python manage.py assignment_management --cleanup-files --days-old 30
```

## API Documentation

The assignments module provides a comprehensive REST API:

### Authentication

All API endpoints require authentication. Include JWT token in headers:

```
Authorization: Bearer <your-jwt-token>
```

### Core Endpoints

#### Assignments

- `GET /api/assignments/` - List assignments
- `POST /api/assignments/` - Create assignment
- `GET /api/assignments/{id}/` - Get assignment details
- `PUT /api/assignments/{id}/` - Update assignment
- `DELETE /api/assignments/{id}/` - Delete assignment
- `POST /api/assignments/{id}/publish/` - Publish assignment
- `GET /api/assignments/{id}/analytics/` - Get assignment analytics

#### Submissions

- `GET /api/submissions/` - List submissions
- `POST /api/submissions/` - Create submission
- `GET /api/submissions/{id}/` - Get submission details
- `POST /api/submissions/{id}/grade/` - Grade submission
- `POST /api/submissions/{id}/check_plagiarism/` - Check plagiarism

#### Analytics

- `GET /api/teacher-analytics/` - Teacher analytics dashboard
- `GET /api/student-analytics/` - Student analytics dashboard

### Example API Usage

#### Create Assignment

```python
import requests

data = {
    'title': 'Science Project',
    'description': 'Research project on renewable energy',
    'class_id': 1,
    'subject': 2,
    'term': 1,
    'due_date': '2024-12-31T23:59:59Z',
    'total_marks': 100,
    'submission_type': 'online'
}

response = requests.post(
    'http://localhost:8000/assignments/api/assignments/',
    json=data,
    headers={'Authorization': 'Bearer your-token'}
)
```

#### Grade Submission

```python
grading_data = {
    'marks_obtained': 85,
    'teacher_remarks': 'Good work!',
    'strengths': 'Well researched',
    'improvements': 'Add more examples'
}

response = requests.post(
    f'http://localhost:8000/assignments/api/submissions/{submission_id}/grade/',
    json=grading_data,
    headers={'Authorization': 'Bearer your-token'}
)
```

## Models

### Core Models

#### Assignment

The main assignment model with fields for title, description, deadlines, grading criteria, and settings.

```python
class Assignment(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField()
    class_id = models.ForeignKey('academics.Class', on_delete=models.CASCADE)
    subject = models.ForeignKey('subjects.Subject', on_delete=models.CASCADE)
    teacher = models.ForeignKey('teachers.Teacher', on_delete=models.CASCADE)
    due_date = models.DateTimeField()
    total_marks = models.PositiveIntegerField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES)
    # ... additional fields
```

#### AssignmentSubmission

Student submissions with content, attachments, and grading information.

```python
class AssignmentSubmission(models.Model):
    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE)
    student = models.ForeignKey('students.Student', on_delete=models.CASCADE)
    content = models.TextField(blank=True)
    attachment = models.FileField(upload_to=submission_attachment_path)
    marks_obtained = models.PositiveIntegerField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES)
    # ... additional fields
```

#### AssignmentRubric

Rubric criteria for structured grading.

```python
class AssignmentRubric(models.Model):
    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE)
    criteria_name = models.CharField(max_length=100)
    max_points = models.PositiveIntegerField()
    weight_percentage = models.PositiveIntegerField()
    # ... additional fields
```

## Services

The module follows a service-oriented architecture with dedicated service classes:

### AssignmentService

- Assignment creation, updating, and publishing
- Assignment analytics and statistics
- Template management

### SubmissionService

- Submission creation and management
- File validation and processing
- Student submission analytics

### GradingService

- Individual and bulk grading
- Rubric-based grading
- Grade calculations and analytics

### PlagiarismService

- Content similarity detection
- Batch plagiarism checking
- Detailed analysis reports

### DeadlineService

- Deadline tracking and notifications
- Overdue assignment management
- Reminder scheduling

### RubricService

- Rubric creation and management
- Score calculations
- Performance analysis

## Middleware

### AssignmentDeadlineNotificationMiddleware

Automatically shows deadline notifications to users based on upcoming assignments and grading deadlines.

### AssignmentAccessControlMiddleware

Enforces role-based access control for assignments and submissions.

### AssignmentActivityTrackingMiddleware

Tracks user activity for analytics and audit purposes.

### AssignmentSubmissionValidationMiddleware

Validates submission attempts against assignment rules and deadlines.

### AssignmentCacheMiddleware

Manages caching for improved performance.

### AssignmentSecurityMiddleware

Provides security checks for file uploads and request validation.

## Template Tags

The module includes comprehensive template tags for easy integration:

### Status and Display Tags

- `assignment_status_badge` - Display colored status badges
- `submission_status_badge` - Show submission status with icons
- `grade_badge` - Display grade with color coding
- `assignment_difficulty_icon` - Show difficulty level icons

### Progress and Analytics Tags

- `progress_bar` - Generic progress bar component
- `assignment_completion_bar` - Assignment completion progress
- `grade_distribution_chart` - Grade distribution visualization
- `assignment_timeline` - Timeline of assignment events

### Utility Tags

- `file_icon` - File type icons
- `file_size_human` - Human-readable file sizes
- `time_until_deadline` - Countdown to deadline
- `assignment_permissions` - Check user permissions

### Inclusion Tags

- `assignment_card` - Complete assignment card component
- `submission_summary` - Submission statistics summary

## Testing

### Running Tests

```bash
# Run all assignment tests
python manage.py test assignments

# Run specific test cases
python manage.py test assignments.tests.AssignmentModelTestCase
python manage.py test assignments.tests.AssignmentServiceTestCase

# Run with coverage
coverage run --source='.' manage.py test assignments
coverage report
coverage html
```

### Test Categories

- **Model Tests**: Test model validation, relationships, and methods
- **Service Tests**: Test business logic and service functions
- **View Tests**: Test view functionality and permissions
- **API Tests**: Test REST API endpoints and responses
- **Integration Tests**: Test complete workflows

### Example Test

```python
class AssignmentServiceTestCase(TestCase):
    def test_create_assignment_success(self):
        assignment_data = {
            'title': 'Test Assignment',
            'class_id': self.class_obj,
            'subject': self.subject,
            'term': self.term,
            'due_date': timezone.now() + timedelta(days=7),
            'total_marks': 100
        }

        assignment = AssignmentService.create_assignment(self.teacher, assignment_data)

        self.assertEqual(assignment.title, 'Test Assignment')
        self.assertEqual(assignment.status, 'draft')
```

## Performance Optimization

### Caching Strategy

- Assignment list views cached for 5 minutes
- Assignment details cached for 15 minutes
- Analytics cached for 30 minutes
- User-specific data cached appropriately

### Database Optimization

- Proper indexing on frequently queried fields
- Select/prefetch related objects to avoid N+1 queries
- Pagination for large datasets
- Database connection pooling

### Background Tasks

- Email notifications sent asynchronously
- Analytics calculations performed in background
- File processing handled by workers
- Bulk operations queued for processing

## Security Features

### File Upload Security

- File type validation based on extension and MIME type
- File size limits configurable per assignment
- Malicious file detection and blocking
- Secure file storage with proper permissions

### Access Control

- Role-based permissions at every level
- Object-level permissions for assignments and submissions
- Middleware-enforced access control
- Audit logging for sensitive operations

### Data Protection

- Input validation and sanitization
- SQL injection prevention
- XSS protection in templates
- CSRF protection on all forms

## Contributing

### Development Setup

1. Fork the repository
2. Create a feature branch
3. Make changes following coding standards
4. Add comprehensive tests
5. Update documentation
6. Submit pull request

### Coding Standards

- Follow PEP 8 style guidelines
- Write docstrings for all functions and classes
- Add type hints where applicable
- Maintain test coverage above 90%
- Use meaningful variable and function names

### Commit Guidelines

- Use conventional commit messages
- Include issue numbers in commit messages
- Keep commits atomic and focused
- Write clear commit descriptions

## Troubleshooting

### Common Issues

#### File Upload Problems

```python
# Check file size limits
ASSIGNMENTS_SETTINGS['MAX_FILE_SIZE_MB'] = 50

# Verify allowed file types
ASSIGNMENTS_SETTINGS['ALLOWED_FILE_TYPES'] = ['pdf', 'doc', 'docx']

# Check storage configuration
DEFAULT_FILE_STORAGE = 'django.core.files.storage.FileSystemStorage'
MEDIA_ROOT = '/path/to/media/files'
```

#### Notification Issues

```python
# Verify email configuration
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'your-smtp-server.com'

# Check Celery status
celery -A your_project worker --loglevel=info
celery -A your_project beat --loglevel=info
```

#### Performance Issues

```python
# Enable query logging
LOGGING = {
    'loggers': {
        'django.db.backends': {
            'level': 'DEBUG',
            'handlers': ['console'],
        }
    }
}

# Monitor cache usage
CACHES['default']['OPTIONS']['CLIENT_CLASS'] = 'django_redis.client.DefaultClient'
```

## License

This module is part of the School Management System and follows the same license terms as the main project.

## Support

For support and questions:

- Create an issue in the repository
- Check the documentation wiki
- Contact the development team
- Join the community discussions

---

**Version**: 1.0.0  
**Last Updated**: December 2024  
**Maintainers**: School Management System Team
