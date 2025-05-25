# School Management System (SMS)

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://python.org)
[![Django](https://img.shields.io/badge/Django-4.2+-green.svg)](https://djangoproject.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-14+-blue.svg)](https://postgresql.org)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A comprehensive, modular web application for managing educational institutions with advanced analytics, flexible fee management, and term-based academics.

## 🎯 Overview

This School Management System provides a complete solution for educational institutions ranging from primary schools to secondary colleges. Built with modern technologies and best practices, it offers role-based access control, comprehensive analytics, and flexible academic management.

### Key Differentiators

- 📊 **Real-time Analytics Engine**: Performance, attendance, and financial insights
- 📱 **Progressive Web App**: Mobile-first design with offline capabilities
- 🔧 **Modular Architecture**: Highly maintainable and scalable codebase
- 🌍 **Multi-language Support**: Internationalization ready

## 🏗️ Academic Structure

### Academic Structure

```
Independent Hierarchies:

Academic Structure:
Section (e.g., "Lower Primary", "Upper Primary")
└── Grade (e.g., "Grade 1", "Grade 2", "Grade 3")
    └── Class (e.g., "North", "Blue", "Alpha")
        └── Students

Departmental Structure:
Department (Subject/Activity-based)
├── English Department → English Teachers, Literature, Grammar
├── Mathematics Department → Math Teachers, Algebra, Geometry
├── Sports Department → Coaches, Sports Activities, Equipment
├── Arts Department → Art Teachers, Music, Drama
└── Science Department → Lab Teachers, Physics, Chemistry
```

## 🚀 Core Features

### 👥 User Management

- **Role-based Access Control**: Admin, Teachers, Parents, Students, Staff
- **Secure Authentication**: JWT, OAuth, 2FA support
- **Profile Management**: Comprehensive user profiles with document uploads
- **Audit Logging**: Complete activity tracking for compliance

### 🎓 Academic Management

- **Section-based Organization**: Natural educational progression
- **Descriptive Class Names**: Color/direction-based for easy identification
- **Term-based Academics**: Flexible terms (2-4 per academic year)
- **Subject & Curriculum**: Term-wise syllabus planning and tracking

### 👨‍🎓 Student Management

- **Comprehensive Profiles**: Personal, academic, and medical information
- **Parent Relationships**: Multi-parent support with primary contact designation
- **Academic Tracking**: Term-wise performance monitoring and analytics
- **Attendance Management**: Real-time tracking with automated alerts

### 👨‍🏫 Teacher Management

- **Professional Profiles**: Qualifications, experience, specializations
- **Class Assignments**: Multi-class, multi-subject teaching support
- **Performance Analytics**: Student success correlation and evaluation tracking
- **Workload Management**: Automated scheduling and conflict resolution

### 💰 Advanced Fee Management

#### Features

- **Multi-level Assignment**: Section, grade, class, or student-specific
- **Special Fee Types**: Laboratory, sports, events, transportation
- **Flexible Billing**: Term-wise, monthly, or custom cycles
- **Scholarship Management**: Merit-based and need-based discounts
- **Payment Tracking**: Multiple payment methods with receipt generation
- **Automated Alerts**: Due date reminders and overdue notifications

### 📊 Analytics & Insights

#### Student Performance Analytics

- **Term-wise Trends**: Performance tracking across terms
- **Subject Analysis**: Strengths and improvement areas identification
- **Ranking Systems**: Class and grade-level positioning
- **Predictive Insights**: Early warning for at-risk students
- **Parent Dashboards**: Comprehensive progress reports

#### Class & Section Analytics

- **Comparative Analysis**: Performance between classes and sections
- **Teacher Effectiveness**: Class performance correlation
- **Resource Optimization**: Utilization and requirement analysis
- **Trend Analysis**: Historical performance patterns

#### Financial Analytics

- **Revenue Tracking**: Collection rates and outstanding analysis
- **Fee Structure Optimization**: Pricing strategy insights
- **Scholarship Impact**: Financial aid effectiveness
- **Forecasting**: Budget planning and revenue prediction

#### Attendance Analytics

- **Pattern Recognition**: Chronic absenteeism identification
- **Section Comparisons**: Attendance rate analysis
- **Intervention Triggers**: Automated alert systems
- **Reporting**: Compliance and administrative reports

### 📚 Academic Operations

#### Scheduling System

- **Intelligent Timetabling**: Automated schedule generation
- **Conflict Resolution**: Teacher and room availability optimization
- **Resource Management**: Lab and equipment booking
- **Substitute Management**: Automatic replacement scheduling

#### Assignment Management

- **Digital Workflow**: Creation, submission, and grading
- **Plagiarism Detection**: Integrated checking systems
- **Progress Tracking**: Completion rates and performance analytics
- **Parent Visibility**: Assignment status and grades

#### Examination System

- **Flexible Exam Types**: Term exams, assessments, online quizzes
- **Automated Scheduling**: Conflict-free exam timetables
- **Result Processing**: Grade calculation and report generation
- **Performance Analytics**: Subject and student analysis

### 📖 Library Management

- **Digital Catalog**: ISBN tracking and search capabilities
- **Automated Operations**: Issue/return with barcode scanning
- **Fine Management**: Automated calculation and payment tracking
- **Usage Analytics**: Popular books and reading patterns
- **Reservation System**: Book holding and notification system

### 🚌 Transport Management

- **Route Optimization**: Efficient path planning and scheduling
- **Student Tracking**: Real-time location and safety monitoring
- **Driver Management**: Licenses, evaluations, and assignments
- **Parent Notifications**: Pickup/drop alerts and delays

### 💬 Communication Hub

- **Multi-channel Messaging**: Email, SMS, push notifications
- **Targeted Broadcasting**: Section, grade, class, or individual messaging
- **Event Management**: Announcements, reminders, and RSVP tracking
- **Parent-Teacher Communication**: Direct messaging and meeting scheduling

## 🛠️ Technical Architecture

### Technology Stack

```yaml
Backend:
  - Python 3.10+
  - Django 4.2+ (Web Framework)
  - Django REST Framework (API)
  - PostgreSQL 14+ (Database)
  - Redis 6+ (Caching & Task Queue)
  - Celery (Background Tasks)

Frontend:
  - Django Templates
  - Bootstrap 5 (UI Framework)
  - Chart.js (Data Visualization)
  - Progressive Web App (PWA)

Infrastructure:
  - Docker & Docker Compose
  - Nginx (Reverse Proxy)
  - Gunicorn (WSGI Server)
  - GitHub Actions (CI/CD)
```

### Modular Architecture

```
src/
├── accounts/          # User authentication & profiles
├── departments/       # Subject/Activity-based departments
├── academics/         # Section → Grade → Class hierarchy
├── subjects/          # Subject & syllabus management
├── scheduling/        # Timetable & resource booking
├── assignments/       # Assignment lifecycle
├── students/          # Student management & analytics
├── teachers/          # Teacher management & evaluation
├── attendance/        # Attendance tracking & analytics
├── exams/            # Examination & assessment system
├── finance/          # Fee management & payments
├── analytics/        # Cross-system analytics engine
├── library/          # Library operations
├── transport/        # Transportation management
├── communications/   # Messaging & notifications
├── reports/          # Dashboards & report generation
├── api/              # Common API utilities (no endpoints)
└── core/             # Shared utilities & base classes
```

### API Architecture

- **Centralized Utilities**: Authentication, pagination, filters in `api/`
- **Modular Endpoints**: Each app manages its own API endpoints
- **RESTful Design**: Standard HTTP methods and status codes
- **Comprehensive Documentation**: Auto-generated with Swagger/OpenAPI

## 🚀 Installation & Setup

### Prerequisites

```bash
# System Requirements
Python 3.10+
PostgreSQL 14+
Redis 6+
Node.js 16+ (for frontend assets)
Git

# Optional
Docker & Docker Compose
```

### Quick Start (Development)

1. **Clone & Setup Environment**

```bash
git clone https://github.com/yourusername/school-management-system.git
cd school-management-system

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements/development.txt
```

2. **Database Configuration**

```bash
# Create PostgreSQL database
createdb school_management_db

# Configure environment
cp .env.example .env
# Edit .env with your database credentials
```

3. **Initialize System**

```bash
# Run migrations
python manage.py migrate

# Create academic structure
python manage.py setup_academic_year

# Create superuser
python manage.py createsuperuser

# Load sample data (optional)
python manage.py generate_sample_data
```

4. **Start Services**

```bash
# Terminal 1: Redis
redis-server

# Terminal 2: Celery Worker
celery -A config worker -l info

# Terminal 3: Celery Beat (scheduled tasks)
celery -A config beat -l info

# Terminal 4: Django Development Server
python manage.py runserver
```

### Docker Deployment

1. **Production Setup**

```bash
# Clone repository
git clone https://github.com/yourusername/school-management-system.git
cd school-management-system

# Configure environment
cp .env.example .env
# Edit .env for production settings

# Build and start services
docker-compose -f docker-compose.prod.yml up -d

# Initialize database
docker-compose exec web python manage.py migrate
docker-compose exec web python manage.py setup_academic_year
docker-compose exec web python manage.py createsuperuser
```

2. **SSL Configuration**

```bash
# Place SSL certificates in nginx/ssl/
nginx/
├── conf.d/
│   └── default.conf
└── ssl/
    ├── certificate.crt
    └── private.key
```

## ⚙️ Configuration

### Environment Variables

```bash
# Core Settings
DEBUG=False
SECRET_KEY=your-super-secret-key
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com

# Database
DATABASE_URL=postgres://user:password@localhost:5432/school_db

# Cache & Queue
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0

# Email Configuration
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
EMAIL_USE_TLS=True

# SMS Configuration
SMS_PROVIDER=twilio
TWILIO_ACCOUNT_SID=your-sid
TWILIO_AUTH_TOKEN=your-token
TWILIO_PHONE_NUMBER=+1234567890

# File Storage (AWS S3)
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_STORAGE_BUCKET_NAME=your-bucket
AWS_S3_REGION_NAME=us-east-1

# Payment Gateway
STRIPE_PUBLIC_KEY=pk_test_...
STRIPE_SECRET_KEY=sk_test_...
RAZORPAY_KEY_ID=rzp_test_...
RAZORPAY_KEY_SECRET=your-secret
```

### Academic Year Setup

```python
# Custom management command
python manage.py setup_academic_year \
    --year "2024-2025" \
    --start-date "2024-04-01" \
    --terms 3 \
    --create-sections \
    --create-sample-grades
```

### Analytics Configuration

```python
# Automated analytics calculation
CELERY_BEAT_SCHEDULE = {
    'calculate-daily-analytics': {
        'task': 'analytics.tasks.calculate_daily_analytics',
        'schedule': crontab(hour=2, minute=0),  # 2 AM daily
    },
    'generate-weekly-reports': {
        'task': 'reports.tasks.generate_weekly_reports',
        'schedule': crontab(hour=6, minute=0, day_of_week=1),  # Monday 6 AM
    },
}
```

## 📊 Usage Examples

### Academic Structure Setup

```python
# Create sections
primary = Section.objects.create(
    name="Primary Section",
    department=primary_dept
)

# Create grades
grade1 = Grade.objects.create(
    name="Grade 1",
    section=primary,
    order_sequence=1
)

# Create classes with descriptive names
grade1_north = Class.objects.create(
    name="North",
    grade=grade1,
    academic_year=current_year,
    room_number="101"
)
# Display name auto-computed as "Grade 1 North"
```

### Fee Structure Configuration

```python
# Section-level base fee
FeeStructure.objects.create(
    academic_year=current_year,
    term=term1,
    section=primary_section,
    fee_category=tuition_category,
    amount=4000.00
)

# Grade-specific additional fee
FeeStructure.objects.create(
    academic_year=current_year,
    term=term1,
    grade=grade10,
    fee_category=board_exam_category,
    amount=1000.00
)

# Special class fee
SpecialFee.objects.create(
    name="Computer Lab Fee",
    class=grade5_computer,
    amount=500.00,
    fee_category=lab_category,
    term=term1
)
```

### Analytics Queries

```python
# Student performance across terms
student_analytics = StudentPerformanceAnalytics.objects.filter(
    student=student,
    academic_year=current_year
).order_by('term__term_number')

# Section comparison
section_performance = ClassPerformanceAnalytics.objects.filter(
    academic_year=current_year,
    term=current_term
).select_related('class__grade__section')

# Financial collection rates
collection_rates = FinancialAnalytics.objects.filter(
    academic_year=current_year
).aggregate(
    total_expected=Sum('total_expected_revenue'),
    total_collected=Sum('total_collected_revenue')
)
```

## 🔌 API Reference

### Authentication

```http
POST /api/auth/login/
POST /api/auth/logout/
POST /api/auth/refresh/
POST /api/auth/password/reset/
```

### Academic Endpoints

```http
GET    /api/academics/sections/
POST   /api/academics/sections/
GET    /api/academics/grades/?section_id=1
GET    /api/academics/classes/?grade_id=1
```

### Student Management

```http
GET    /api/students/
POST   /api/students/
GET    /api/students/{id}/
PUT    /api/students/{id}/
GET    /api/students/{id}/performance/
GET    /api/students/{id}/attendance/
```

### Fee Management

```http
GET    /api/finance/fee-structures/
POST   /api/finance/invoices/
GET    /api/finance/payments/
POST   /api/finance/payments/
GET    /api/finance/analytics/collection-rates/
```

### Analytics

```http
GET    /api/analytics/student-performance/?student_id=1
GET    /api/analytics/class-performance/?class_id=1
GET    /api/analytics/attendance-summary/
GET    /api/analytics/financial-overview/
```

## 🧪 Testing

### Running Tests

```bash
# All tests
python manage.py test

# Specific app tests
python manage.py test src.students.tests

# Coverage report
coverage run --source='.' manage.py test
coverage report
coverage html
```

### Test Structure

```
tests/
├── integration/
│   ├── test_academic_workflow.py
│   ├── test_fee_processing.py
│   └── test_analytics_calculation.py
├── unit/
│   ├── test_models.py
│   ├── test_services.py
│   └── test_api.py
└── fixtures/
    ├── users.json
    ├── academic_data.json
    └── financial_data.json
```

## 📈 Performance & Scaling

### Database Optimization

- **Indexes**: Optimized for frequent queries
- **Query Optimization**: Select/prefetch related objects
- **Pagination**: Large dataset handling
- **Connection Pooling**: Efficient database connections

### Caching Strategy

```python
# Redis caching for frequent queries
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': 'redis://127.0.0.1:6379/1',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        }
    }
}

# Cache expensive analytics calculations
@cache_page(60 * 15)  # 15 minutes
def student_performance_view(request):
    pass
```

### Background Processing

- **Celery Tasks**: Analytics calculations, report generation
- **Scheduled Jobs**: Daily attendance summaries, weekly reports
- **Email Queue**: Bulk notification processing

## 🔒 Security Features

### Authentication & Authorization

- **JWT Tokens**: Stateless authentication
- **Role-based Permissions**: Granular access control
- **Two-factor Authentication**: Enhanced security
- **Session Management**: Secure session handling

### Data Protection

- **Input Validation**: SQL injection prevention
- **CSRF Protection**: Cross-site request forgery prevention
- **XSS Protection**: Cross-site scripting prevention
- **Data Encryption**: Sensitive data encryption at rest

### Compliance

- **GDPR Ready**: Data privacy and user rights
- **Audit Logging**: Complete activity tracking
- **Backup Systems**: Automated data backup
- **Access Logs**: Security monitoring

## 🌍 Internationalization

### Supported Languages

- English (default)
- Spanish
- French

### Configuration

```python
# settings.py
USE_I18N = True
USE_L10N = True
USE_TZ = True

LANGUAGES = [
    ('en', 'English'),
    ('es', 'Español'),
    ('fr', 'Français'),
]

LOCALE_PATHS = [
    BASE_DIR / 'locale',
]
```

## 📱 Mobile Support

### Progressive Web App (PWA)

- **Offline Functionality**: Critical data access without internet
- **Push Notifications**: Real-time alerts and updates
- **App-like Experience**: Installation on mobile devices
- **Responsive Design**: Optimized for all screen sizes

### Mobile API

- **Lightweight Endpoints**: Optimized for mobile bandwidth
- **Offline Sync**: Data synchronization when connection restored
- **Compressed Responses**: Reduced data usage

## 🔧 Development Tools

### Code Quality

```bash
# Code formatting
black .
isort .

# Linting
flake8 .
pylint src/

# Type checking
mypy src/
```

### Database Tools

```bash
# Create migration
python manage.py makemigrations

# Show migration SQL
python manage.py sqlmigrate students 0001

# Database shell
python manage.py dbshell
```

### Debugging

```bash
# Django shell
python manage.py shell

# Debug toolbar (development)
pip install django-debug-toolbar
```

## 📋 Management Commands

### Custom Commands

```bash
# Academic year setup
python manage.py setup_academic_year --year "2024-25"

# Generate sample data
python manage.py generate_sample_data --students 100

# Calculate analytics
python manage.py calculate_analytics --date 2024-01-01

# Backup database
python manage.py backup_database --output backup.sql

# Send bulk notifications
python manage.py send_notifications --type fee_reminder
```

## 🚀 Deployment

### Production Checklist

- [ ] Set `DEBUG=False`
- [ ] Configure allowed hosts
- [ ] Set up SSL certificates
- [ ] Configure email backend
- [ ] Set up file storage (AWS S3/local)
- [ ] Configure Redis for production
- [ ] Set up monitoring (Sentry, etc.)
- [ ] Database backup strategy
- [ ] Load testing
- [ ] Security audit

### Performance Monitoring

```python
# Sentry integration
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration

sentry_sdk.init(
    dsn="your-sentry-dsn",
    integrations=[DjangoIntegration()],
    traces_sample_rate=1.0,
)
```

## 🤝 Contributing

### Development Workflow

1. Fork the repository
2. Create feature branch: `git checkout -b feature/amazing-feature`
3. Make changes following coding standards
4. Add tests for new functionality
5. Run test suite: `python manage.py test`
6. Commit changes: `git commit -m 'Add amazing feature'`
7. Push to branch: `git push origin feature/amazing-feature`
8. Open Pull Request

### Coding Standards

- Follow PEP 8 style guidelines
- Write comprehensive docstrings
- Add type hints where applicable
- Maintain test coverage above 90%
- Update documentation for new features

## 📞 Support & Community

### Documentation

- **User Guides**: `/docs/user/`
- **API Documentation**: `/api/docs/`
- **Developer Docs**: `/docs/development/`

### Getting Help

- **GitHub Issues**: Bug reports and feature requests
- **Discussions**: Community Q&A and discussions
- **Email Support**: support@schoolsms.com
- **Documentation**: Comprehensive guides and tutorials

### Community

- **Contributors**: Open source contributors welcome
- **Feature Requests**: Community-driven development
- **Feedback**: User experience improvements

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Django and Python communities
- PostgreSQL development team
- Bootstrap and Chart.js contributors
- All open source libraries used
- Beta testers and early adopters

---

**School Management System** - Empowering Education Through Technology

**Version**: 2.0.0  
**Last Updated**: December 2024  
**Maintainers**: [Brian Otieno-Default]
