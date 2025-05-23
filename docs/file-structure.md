# School Management System - Updated File Structure

```
school_management_system/
│
├── .github/                       # GitHub workflows and configuration
│   └── workflows/
│       ├── ci.yml                 # Continuous Integration workflow
│       └── deploy.yml             # Deployment workflow
│
├── config/                        # Project configuration
│   ├── settings/
│   │   ├── __init__.py
│   │   ├── base.py                # Base settings shared across environments
│   │   ├── development.py         # Development-specific settings
│   │   ├── production.py          # Production-specific settings
│   │   └── testing.py             # Testing-specific settings
│   ├── urls.py                    # Main URL configuration
│   └── wsgi.py                    # WSGI configuration
│
├── docs/                          # Project documentation
│   ├── api/                       # API documentation
│   ├── deployment/                # Deployment guides
│   └── user/                      # User documentation
│
├── requirements/                  # Dependencies
│   ├── base.txt                   # Base dependencies
│   ├── development.txt            # Development dependencies
│   ├── production.txt             # Production dependencies
│   └── testing.txt                # Testing dependencies
│
├── scripts/                       # Utility scripts
│   ├── db_backup.py               # Database backup script
│   ├── generate_sample_data.py    # Sample data generation script
│   ├── analytics_processor.py     # Analytics calculation script
│   └── deployment/                # Deployment scripts
│
├── src/                           # Source code
│   ├── accounts/                  # User accounts app
│   │   ├── migrations/            # Database migrations
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── serializers.py
│   │   │   ├── views.py
│   │   │   └── urls.py
│   │   ├── templates/
│   │   │   └── accounts/
│   │   ├── __init__.py
│   │   ├── admin.py               # Django admin configuration
│   │   ├── apps.py                # App configuration
│   │   ├── forms.py               # Forms
│   │   ├── managers.py            # Custom managers
│   │   ├── models.py              # Database models
│   │   ├── permissions.py         # Custom permissions
│   │   ├── services.py            # Business logic
│   │   ├── signals.py             # Django signals
│   │   ├── tests.py               # Tests
│   │   ├── urls.py                # URL patterns
│   │   └── views.py               # Views
│   │
│   ├── api/                       # API utilities (NO endpoints)
│   │   ├── __init__.py
│   │   ├── apps.py                # App configuration
│   │   ├── authentication.py      # Custom authentication
│   │   ├── exceptions.py          # Global API exceptions
│   │   ├── filters.py             # Common API filters
│   │   ├── middleware.py          # API middleware
│   │   ├── paginations.py         # Custom pagination classes
│   │   ├── permissions.py         # Common API permissions
│   │   ├── throttling.py          # Rate limiting
│   │   ├── documentation.py       # API docs configuration
│   │   └── urls.py                # Main API URL router only
│   │
│   ├── students/                  # Students app
│   │   ├── migrations/            # Database migrations
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── serializers.py
│   │   │   ├── views.py
│   │   │   └── urls.py
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── enrollment_service.py
│   │   │   ├── performance_service.py
│   │   │   └── analytics_service.py
│   │   ├── templates/
│   │   │   └── students/
│   │   ├── __init__.py
│   │   ├── admin.py               # Django admin configuration
│   │   ├── apps.py                # App configuration
│   │   ├── forms.py               # Forms
│   │   ├── models.py              # Database models
│   │   ├── tests.py               # Tests
│   │   ├── urls.py                # URL patterns
│   │   └── views.py               # Views
│   │
│   ├── teachers/                  # Teachers app
│   │   ├── migrations/            # Database migrations
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── serializers.py
│   │   │   ├── views.py
│   │   │   └── urls.py
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── assignment_service.py
│   │   │   ├── evaluation_service.py
│   │   │   └── performance_service.py
│   │   ├── templates/
│   │   │   └── teachers/
│   │   ├── __init__.py
│   │   ├── admin.py               # Django admin configuration
│   │   ├── apps.py                # App configuration
│   │   ├── forms.py               # Forms
│   │   ├── models.py              # Database models
│   │   ├── tests.py               # Tests
│   │   ├── urls.py                # URL patterns
│   │   └── views.py               # Views
│   │
│   ├── academics/                 # Academic structure (Section → Grade → Class hierarchy)
│   │   ├── migrations/            # Database migrations
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── serializers.py
│   │   │   ├── views.py
│   │   │   └── urls.py
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── section_service.py
│   │   │   ├── grade_service.py
│   │   │   ├── class_service.py
│   │   │   ├── term_service.py
│   │   │   └── academic_year_service.py
│   │   ├── templates/
│   │   │   └── academics/
│   │   ├── __init__.py
│   │   ├── admin.py               # Django admin configuration
│   │   ├── apps.py                # App configuration
│   │   ├── forms.py               # Forms
│   │   ├── models.py              # Database models (Section, Grade, Class, Term, AcademicYear)
│   │   ├── tests.py               # Tests
│   │   ├── urls.py                # URL patterns
│   │   └── views.py               # Views
│   │
│   ├── subjects/                  # Subjects and syllabus
│   │   ├── migrations/            # Database migrations
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── serializers.py
│   │   │   ├── views.py
│   │   │   └── urls.py
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── syllabus_service.py
│   │   │   └── curriculum_service.py
│   │   ├── templates/
│   │   │   └── subjects/
│   │   ├── __init__.py
│   │   ├── admin.py               # Django admin configuration
│   │   ├── apps.py                # App configuration
│   │   ├── forms.py               # Forms
│   │   ├── models.py              # Database models
│   │   ├── tests.py               # Tests
│   │   ├── urls.py                # URL patterns
│   │   └── views.py               # Views
│   │
│   ├── scheduling/                # Timetable and scheduling
│   │   ├── migrations/            # Database migrations
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── serializers.py
│   │   │   ├── views.py
│   │   │   └── urls.py
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── timetable_service.py
│   │   │   ├── scheduling_algorithm.py
│   │   │   └── conflict_resolver.py
│   │   ├── templates/
│   │   │   └── scheduling/
│   │   ├── __init__.py
│   │   ├── admin.py               # Django admin configuration
│   │   ├── apps.py                # App configuration
│   │   ├── forms.py               # Forms
│   │   ├── models.py              # Database models
│   │   ├── tests.py               # Tests
│   │   ├── urls.py                # URL patterns
│   │   └── views.py               # Views
│   │
│   ├── assignments/               # Assignment management
│   │   ├── migrations/            # Database migrations
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── serializers.py
│   │   │   ├── views.py
│   │   │   └── urls.py
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── assignment_service.py
│   │   │   ├── submission_service.py
│   │   │   └── grading_service.py
│   │   ├── templates/
│   │   │   └── assignments/
│   │   ├── __init__.py
│   │   ├── admin.py               # Django admin configuration
│   │   ├── apps.py                # App configuration
│   │   ├── forms.py               # Forms
│   │   ├── models.py              # Database models
│   │   ├── tests.py               # Tests
│   │   ├── urls.py                # URL patterns
│   │   └── views.py               # Views
│   │
│   ├── exams/                     # Exams and assessments app
│   │   ├── migrations/            # Database migrations
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── serializers.py
│   │   │   ├── views.py
│   │   │   └── urls.py
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── exam_service.py
│   │   │   ├── result_service.py
│   │   │   └── grading_service.py
│   │   ├── templates/
│   │   │   └── exams/
│   │   ├── __init__.py
│   │   ├── admin.py               # Django admin configuration
│   │   ├── apps.py                # App configuration
│   │   ├── forms.py               # Forms
│   │   ├── models.py              # Database models
│   │   ├── tests.py               # Tests
│   │   ├── urls.py                # URL patterns
│   │   └── views.py               # Views
│   │
│   ├── attendance/                # Attendance app
│   │   ├── migrations/            # Database migrations
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── serializers.py
│   │   │   ├── views.py
│   │   │   └── urls.py
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── attendance_service.py
│   │   │   └── analytics_service.py
│   │   ├── templates/
│   │   │   └── attendance/
│   │   ├── __init__.py
│   │   ├── admin.py               # Django admin configuration
│   │   ├── apps.py                # App configuration
│   │   ├── forms.py               # Forms
│   │   ├── models.py              # Database models
│   │   ├── tests.py               # Tests
│   │   ├── urls.py                # URL patterns
│   │   └── views.py               # Views
│   │
│   ├── finance/                   # Enhanced finance app
│   │   ├── migrations/            # Database migrations
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── serializers.py
│   │   │   ├── views.py
│   │   │   └── urls.py
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── fee_service.py
│   │   │   ├── invoice_service.py
│   │   │   ├── payment_service.py
│   │   │   ├── scholarship_service.py
│   │   │   └── analytics_service.py
│   │   ├── templates/
│   │   │   └── finance/
│   │   ├── __init__.py
│   │   ├── admin.py               # Django admin configuration
│   │   ├── apps.py                # App configuration
│   │   ├── forms.py               # Forms
│   │   ├── models.py              # Database models
│   │   ├── tests.py               # Tests
│   │   ├── urls.py                # URL patterns
│   │   └── views.py               # Views
│   │
│   ├── library/                   # Library app
│   │   ├── migrations/            # Database migrations
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── serializers.py
│   │   │   ├── views.py
│   │   │   └── urls.py
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── book_service.py
│   │   │   ├── issue_service.py
│   │   │   └── analytics_service.py
│   │   ├── templates/
│   │   │   └── library/
│   │   ├── __init__.py
│   │   ├── admin.py               # Django admin configuration
│   │   ├── apps.py                # App configuration
│   │   ├── forms.py               # Forms
│   │   ├── models.py              # Database models
│   │   ├── tests.py               # Tests
│   │   ├── urls.py                # URL patterns
│   │   └── views.py               # Views
│   │
│   ├── transport/                 # Transport app
│   │   ├── migrations/            # Database migrations
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── serializers.py
│   │   │   ├── views.py
│   │   │   └── urls.py
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── route_service.py
│   │   │   └── assignment_service.py
│   │   ├── templates/
│   │   │   └── transport/
│   │   ├── __init__.py
│   │   ├── admin.py               # Django admin configuration
│   │   ├── apps.py                # App configuration
│   │   ├── forms.py               # Forms
│   │   ├── models.py              # Database models
│   │   ├── tests.py               # Tests
│   │   ├── urls.py                # URL patterns
│   │   └── views.py               # Views
│   │
│   ├── communications/            # Communications app
│   │   ├── migrations/            # Database migrations
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── serializers.py
│   │   │   ├── views.py
│   │   │   └── urls.py
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── notification_service.py
│   │   │   ├── email_service.py
│   │   │   └── sms_service.py
│   │   ├── templates/
│   │   │   └── communications/
│   │   ├── __init__.py
│   │   ├── admin.py               # Django admin configuration
│   │   ├── apps.py                # App configuration
│   │   ├── forms.py               # Forms
│   │   ├── models.py              # Database models
│   │   ├── tests.py               # Tests
│   │   ├── urls.py                # URL patterns
│   │   └── views.py               # Views
│   │
│   ├── analytics/                 # New analytics app
│   │   ├── migrations/            # Database migrations
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── serializers.py
│   │   │   ├── views.py
│   │   │   └── urls.py
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── student_analytics_service.py
│   │   │   ├── class_analytics_service.py
│   │   │   ├── financial_analytics_service.py
│   │   │   ├── teacher_analytics_service.py
│   │   │   └── attendance_analytics_service.py
│   │   ├── tasks/                 # Celery tasks for analytics
│   │   │   ├── __init__.py
│   │   │   ├── performance_calculation.py
│   │   │   ├── attendance_calculation.py
│   │   │   └── financial_calculation.py
│   │   ├── templates/
│   │   │   └── analytics/
│   │   ├── __init__.py
│   │   ├── admin.py               # Django admin configuration
│   │   ├── apps.py                # App configuration
│   │   ├── forms.py               # Forms
│   │   ├── models.py              # Database models
│   │   ├── tests.py               # Tests
│   │   ├── urls.py                # URL patterns
│   │   └── views.py               # Views
│   │
│   ├── reports/                   # Reports and dashboards app
│   │   ├── migrations/            # Database migrations
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── serializers.py
│   │   │   ├── views.py
│   │   │   └── urls.py
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── report_service.py
│   │   │   ├── dashboard_service.py
│   │   │   └── export_service.py
│   │   ├── templates/
│   │   │   └── reports/
│   │   │       ├── dashboard.html
│   │   │       ├── student_report.html
│   │   │       ├── financial_report.html
│   │   │       └── attendance_report.html
│   │   ├── __init__.py
│   │   ├── admin.py               # Django admin configuration
│   │   ├── apps.py                # App configuration
│   │   ├── forms.py               # Forms
│   │   ├── models.py              # Database models
│   │   ├── tests.py               # Tests
│   │   ├── urls.py                # URL patterns
│   │   └── views.py               # Views
│   │
│   ├── core/                      # Core functionality
│   │   ├── migrations/            # Database migrations
│   │   ├── management/            # Custom management commands
│   │   │   └── commands/
│   │   │       ├── __init__.py
│   │   │       ├── generate_sample_data.py
│   │   │       ├── calculate_analytics.py
│   │   │       └── setup_academic_year.py
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── base_service.py
│   │   │   └── utility_service.py
│   │   ├── templates/
│   │   │   ├── core/
│   │   │   ├── base.html          # Base template
│   │   │   ├── dashboard.html     # Dashboard template
│   │   │   └── partials/          # Reusable template parts
│   │   ├── __init__.py
│   │   ├── admin.py               # Django admin configuration
│   │   ├── apps.py                # App configuration
│   │   ├── context_processors.py  # Template context processors
│   │   ├── decorators.py          # Custom decorators
│   │   ├── middleware.py          # Custom middleware
│   │   ├── models.py              # Database models
│   │   ├── permissions.py         # Custom permissions
│   │   ├── signals.py             # Django signals
│   │   ├── tests.py               # Tests
│   │   ├── urls.py                # URL patterns
│   │   ├── utils.py               # Utility functions
│   │   └── views.py               # Views
│   │
│   └── templates/                 # Global templates
│       ├── 400.html               # Bad request template
│       ├── 403.html               # Permission denied template
│       ├── 404.html               # Page not found template
│       ├── 500.html               # Server error template
│       └── emails/                # Email templates
│           ├── fee_reminder.html
│           ├── exam_notification.html
│           └── password_reset.html
│
├── static/                        # Static files
│   ├── css/                       # CSS files
│   │   ├── base.css
│   │   ├── dashboard.css
│   │   └── charts.css
│   ├── js/                        # JavaScript files
│   │   ├── base.js
│   │   ├── dashboard.js
│   │   ├── charts.js
│   │   └── analytics.js
│   ├── images/                    # Image files
│   └── vendors/                   # Third-party libraries
│       ├── bootstrap/
│       ├── chartjs/
│       └── jquery/
│
├── media/                         # User uploaded files
│   ├── profile_pictures/          # User profile pictures
│   ├── documents/                 # Document uploads
│   ├── assignments/               # Assignment files
│   ├── books/                     # Book covers
│   └── attachments/               # Other attachments
│
├── locale/                        # Internationalization
│   ├── en/                        # English translations
│   └── fr/                        # French translations
│
├── tests/                         # Test suite
│   ├── integration/               # Integration tests
│   │   ├── test_academic_workflow.py
│   │   ├── test_fee_processing.py
│   │   └── test_analytics_calculation.py
│   ├── unit/                      # Unit tests
│   │   ├── test_models.py
│   │   ├── test_services.py
│   │   └── test_api.py
│   └── fixtures/                  # Test fixtures
│       ├── users.json
│       ├── academic_data.json
│       └── financial_data.json
│
├── .dockerignore                  # Docker ignore file
├── .env.example                   # Example environment variables
├── .gitignore                     # Git ignore file
├── docker-compose.yml             # Docker Compose configuration
├── Dockerfile                     # Docker configuration
├── LICENSE                        # Project license
├── manage.py                      # Django management script
├── celery.py                      # Celery configuration
└── README.md                      # Project README
```
