# settings/core_settings.py
"""
Core module specific settings that should be included in your main settings file
"""

# Core module configuration
CORE_SETTINGS = {
    # Analytics settings
    "ANALYTICS_AUTO_CALCULATION": True,
    "ANALYTICS_CALCULATION_FREQUENCY_HOURS": 24,
    "ANALYTICS_RETENTION_DAYS": 365,
    # Audit settings
    "AUDIT_LOG_RETENTION_DAYS": 730,
    "AUDIT_EXCLUDED_PATHS": [
        "/admin/jsi18n/",
        "/static/",
        "/media/",
        "/favicon.ico",
        "/api/health/",
    ],
    "AUDIT_LOGGED_METHODS": ["POST", "PUT", "PATCH", "DELETE"],
    # Security settings
    "RATE_LIMIT_DEFAULT_MAX_ATTEMPTS": 5,
    "RATE_LIMIT_DEFAULT_WINDOW_MINUTES": 15,
    "SLOW_REQUEST_THRESHOLD_MS": 1000,
    "MAX_FILE_UPLOAD_MB": 10,
    # Cache settings
    "CACHE_TIMEOUT_SYSTEM_SETTINGS": 3600,
    "CACHE_TIMEOUT_ANALYTICS": 1800,
    "CACHE_TIMEOUT_DASHBOARD": 900,
    # Backup settings
    "AUTO_BACKUP_ENABLED": True,
    "BACKUP_RETENTION_DAYS": 30,
    "BACKUP_COMPRESSION": True,
}

# Celery configuration for core tasks
CELERY_BEAT_SCHEDULE_CORE = {
    # Daily analytics calculation
    "calculate-daily-analytics": {
        "task": "core.tasks.calculate_all_analytics",
        "schedule": crontab(hour=2, minute=0),  # 2 AM daily
        "options": {"expires": 3600},  # Task expires after 1 hour
    },
    # System health metrics collection
    "collect-system-health": {
        "task": "core.tasks.collect_system_health_metrics",
        "schedule": crontab(minute="*/15"),  # Every 15 minutes
        "options": {"expires": 300},  # Task expires after 5 minutes
    },
    # Daily maintenance workflow
    "daily-maintenance": {
        "task": "core.tasks.daily_maintenance_workflow",
        "schedule": crontab(hour=1, minute=0),  # 1 AM daily
        "options": {"expires": 7200},  # Task expires after 2 hours
    },
    # Weekly audit log cleanup
    "cleanup-audit-logs": {
        "task": "core.tasks.cleanup_old_audit_logs",
        "schedule": crontab(hour=3, minute=0, day_of_week=0),  # Sunday 3 AM
        "kwargs": {"days": 365},
        "options": {"expires": 3600},
    },
    # Monthly analytics cleanup
    "cleanup-old-analytics": {
        "task": "core.tasks.cleanup_old_analytics",
        "schedule": crontab(hour=4, minute=0, day_of_month=1),  # 1st of month 4 AM
        "kwargs": {"days": 730},
        "options": {"expires": 3600},
    },
    # Weekly database backup
    "weekly-backup": {
        "task": "core.tasks.backup_database",
        "schedule": crontab(hour=23, minute=30, day_of_week=6),  # Saturday 11:30 PM
        "options": {"expires": 3600},
    },
    # System monitoring alerts
    "system-monitoring": {
        "task": "core.tasks.monitor_system_alerts",
        "schedule": crontab(minute="*/30"),  # Every 30 minutes
        "options": {"expires": 900},  # Task expires after 15 minutes
    },
}

# Logging configuration for core module
LOGGING_CONFIG_CORE = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {process:d} {thread:d} {message}",
            "style": "{",
        },
        "simple": {
            "format": "{levelname} {message}",
            "style": "{",
        },
        "audit": {
            "format": "[AUDIT] {asctime} {levelname} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "core_file": {
            "level": "INFO",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": "logs/core.log",
            "maxBytes": 1024 * 1024 * 10,  # 10MB
            "backupCount": 5,
            "formatter": "verbose",
        },
        "audit_file": {
            "level": "INFO",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": "logs/audit.log",
            "maxBytes": 1024 * 1024 * 10,  # 10MB
            "backupCount": 10,
            "formatter": "audit",
        },
        "security_file": {
            "level": "WARNING",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": "logs/security.log",
            "maxBytes": 1024 * 1024 * 5,  # 5MB
            "backupCount": 10,
            "formatter": "verbose",
        },
        "console": {
            "level": "INFO",
            "class": "logging.StreamHandler",
            "formatter": "simple",
        },
    },
    "loggers": {
        "core": {
            "handlers": ["core_file", "console"],
            "level": "INFO",
            "propagate": True,
        },
        "core.services.audit": {
            "handlers": ["audit_file"],
            "level": "INFO",
            "propagate": False,
        },
        "core.services.security": {
            "handlers": ["security_file", "console"],
            "level": "WARNING",
            "propagate": False,
        },
        "core.tasks": {
            "handlers": ["core_file", "console"],
            "level": "INFO",
            "propagate": True,
        },
    },
}

# Django settings to include in your main settings.py
DJANGO_SETTINGS_CORE = """
# Add to your main settings.py file

# Import core settings
from core.settings.core_settings import (
    CORE_SETTINGS, CELERY_BEAT_SCHEDULE_CORE, LOGGING_CONFIG_CORE
)

# Add core to installed apps
INSTALLED_APPS = [
    # ... your other apps
    'core',
    # ... rest of your apps
]

# Middleware configuration
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    
    # Core middleware
    'core.middleware.AuditMiddleware',
    'core.middleware.MaintenanceModeMiddleware',
    'core.middleware.SecurityMiddleware',
    'core.middleware.PerformanceMiddleware',
]

# Context processors
TEMPLATES = [
    {
        # ... your template configuration
        'OPTIONS': {
            'context_processors': [
                # ... your existing context processors
                'core.context_processors.system_settings',
                'core.context_processors.user_permissions',
                'core.context_processors.navigation_context',
            ],
        },
    },
]

# Cache configuration (Redis recommended)
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': 'redis://127.0.0.1:6379/1',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        }
    }
}

# Celery configuration
CELERY_BEAT_SCHEDULE.update(CELERY_BEAT_SCHEDULE_CORE)

# Task routing for core tasks
CELERY_TASK_ROUTES = {
    'core.tasks.*': {'queue': 'core'},
    'core.tasks.calculate_*': {'queue': 'analytics'},
    'core.tasks.backup_*': {'queue': 'maintenance'},
}

# Logging configuration
LOGGING = LOGGING_CONFIG_CORE

# Core module settings
CORE_CONFIG = CORE_SETTINGS

# Session configuration
SESSION_COOKIE_AGE = 3600  # 1 hour
SESSION_SAVE_EVERY_REQUEST = True

# Security settings
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

# File upload settings
FILE_UPLOAD_MAX_MEMORY_SIZE = CORE_SETTINGS['MAX_FILE_UPLOAD_MB'] * 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = FILE_UPLOAD_MAX_MEMORY_SIZE

# Internationalization
USE_I18N = True
USE_L10N = True
USE_TZ = True
TIME_ZONE = 'UTC'  # Set to your timezone

# Static files configuration
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'static'),
]

# Media files configuration
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# REST Framework configuration
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.TokenAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle'
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/hour',
        'user': '1000/hour'
    },
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
    ],
}
"""

# requirements/core.txt - Dependencies for core module
CORE_REQUIREMENTS = """
# Core dependencies for the core module

# Django and extensions
Django>=4.2,<5.0
djangorestframework>=3.14.0
django-filter>=22.1
django-cors-headers>=4.0.0

# Database
psycopg2-binary>=2.9.0  # PostgreSQL adapter

# Cache and messaging
redis>=4.5.0
django-redis>=5.2.0

# Background tasks
celery>=5.2.0
celery[redis]>=5.2.0

# Data processing
pandas>=1.5.0
numpy>=1.24.0

# File handling
openpyxl>=3.1.0  # Excel files
python-docx>=0.8.11  # Word documents
Pillow>=9.5.0  # Image processing

# Utilities
python-dateutil>=2.8.0
pytz>=2023.3
faker>=18.0.0  # For sample data generation

# Security
cryptography>=40.0.0
django-ratelimit>=3.0.0

# Monitoring and logging
sentry-sdk>=1.25.0
django-debug-toolbar>=4.1.0  # Development only

# Testing
pytest>=7.3.0
pytest-django>=4.5.0
pytest-cov>=4.1.0
factory-boy>=3.2.0

# Documentation
sphinx>=7.0.0
sphinx-rtd-theme>=1.2.0

# Development tools
black>=23.3.0
isort>=5.12.0
flake8>=6.0.0
mypy>=1.3.0

# System monitoring (optional)
psutil>=5.9.0  # System metrics
"""

# Docker configuration for core module
DOCKER_CONFIG = """
# docker-compose.core.yml
# Additional services needed for core module

version: '3.8'

services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    command: redis-server --appendonly yes
    networks:
      - school_network

  celery_worker:
    build: .
    command: celery -A config worker -l info -Q core,analytics,maintenance
    volumes:
      - .:/app
      - media_volume:/app/media
      - logs_volume:/app/logs
    depends_on:
      - db
      - redis
    environment:
      - DEBUG=0
      - DATABASE_URL=postgres://user:password@db:5432/school_db
      - REDIS_URL=redis://redis:6379/0
      - CELERY_BROKER_URL=redis://redis:6379/0
    networks:
      - school_network

  celery_beat:
    build: .
    command: celery -A config beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
    volumes:
      - .:/app
      - logs_volume:/app/logs
    depends_on:
      - db
      - redis
    environment:
      - DEBUG=0
      - DATABASE_URL=postgres://user:password@db:5432/school_db
      - REDIS_URL=redis://redis:6379/0
      - CELERY_BROKER_URL=redis://redis:6379/0
    networks:
      - school_network

  celery_flower:
    build: .
    command: celery -A config flower --port=5555
    ports:
      - "5555:5555"
    volumes:
      - .:/app
    depends_on:
      - redis
    environment:
      - CELERY_BROKER_URL=redis://redis:6379/0
    networks:
      - school_network

volumes:
  redis_data:
  logs_volume:
  media_volume:

networks:
  school_network:
    external: true
"""

# Environment variables template
ENV_TEMPLATE = """
# .env.example - Environment variables for core module

# Database
DATABASE_URL=postgres://user:password@localhost:5432/school_db

# Redis
REDIS_URL=redis://localhost:6379/0

# Celery
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# Security
SECRET_KEY=your-secret-key-here
DEBUG=False
ALLOWED_HOSTS=localhost,127.0.0.1,your-domain.com

# Email (for notifications)
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
EMAIL_USE_TLS=True
DEFAULT_FROM_EMAIL=your-email@gmail.com

# SMS (optional - for notifications)
SMS_PROVIDER=twilio
TWILIO_ACCOUNT_SID=your-twilio-sid
TWILIO_AUTH_TOKEN=your-twilio-token
TWILIO_PHONE_NUMBER=+1234567890

# File Storage (AWS S3 - optional)
USE_S3=False
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_STORAGE_BUCKET_NAME=your-bucket
AWS_S3_REGION_NAME=us-east-1

# Monitoring (Sentry - optional)
SENTRY_DSN=your-sentry-dsn

# Core module specific settings
CORE_ANALYTICS_AUTO_CALCULATION=True
CORE_AUDIT_RETENTION_DAYS=730
CORE_BACKUP_ENABLED=True
CORE_MAX_FILE_UPLOAD_MB=10

# Academic settings
ACADEMIC_YEAR_START_MONTH=7
ACADEMIC_TERMS_PER_YEAR=3
ACADEMIC_PASSING_PERCENTAGE=40

# Financial settings
FINANCE_CURRENCY_CODE=USD
FINANCE_LATE_FEE_PERCENTAGE=5
FINANCE_GRACE_PERIOD_DAYS=7

# Security settings
RATE_LIMIT_MAX_ATTEMPTS=5
RATE_LIMIT_WINDOW_MINUTES=15
SESSION_TIMEOUT_MINUTES=60
"""

# Nginx configuration for static files and security
NGINX_CONFIG = """
# nginx/sites-available/school-management
# Nginx configuration for School Management System

server {
    listen 80;
    server_name your-domain.com www.your-domain.com;
    
    # Redirect HTTP to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com www.your-domain.com;
    
    # SSL configuration
    ssl_certificate /path/to/your/certificate.crt;
    ssl_certificate_key /path/to/your/private.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    
    # Security headers
    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:;" always;
    
    # File upload limits
    client_max_body_size 100M;
    
    # Static files
    location /static/ {
        alias /app/staticfiles/;
        expires 1y;
        add_header Cache-Control "public, immutable";
        
        # Gzip compression
        gzip on;
        gzip_vary on;
        gzip_types
            text/css
            text/javascript
            text/xml
            text/plain
            application/javascript
            application/xml+rss
            application/json;
    }
    
    # Media files
    location /media/ {
        alias /app/media/;
        expires 30d;
        add_header Cache-Control "public";
        
        # Security for uploads
        location ~* \.(php|php3|php4|php5|phtml|pl|py|jsp|asp|sh|cgi)$ {
            deny all;
        }
    }
    
    # API endpoints
    location /api/ {
        proxy_pass http://web:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Rate limiting for API
        limit_req zone=api burst=20 nodelay;
    }
    
    # Admin interface
    location /admin/ {
        proxy_pass http://web:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Additional security for admin
        limit_req zone=admin burst=5 nodelay;
    }
    
    # Main application
    location / {
        proxy_pass http://web:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Timeout settings
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
    
    # Celery Flower (monitoring) - restrict access
    location /flower/ {
        proxy_pass http://celery_flower:5555;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Restrict access to admin users only
        auth_basic "Restricted Access";
        auth_basic_user_file /etc/nginx/.htpasswd;
    }
}

# Rate limiting zones
http {
    limit_req_zone $binary_remote_addr zone=api:10m rate=100r/m;
    limit_req_zone $binary_remote_addr zone=admin:10m rate=20r/m;
    limit_req_zone $binary_remote_addr zone=general:10m rate=200r/m;
}
"""
