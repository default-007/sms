# Academics Module

A comprehensive Django app for managing academic structure and operations in educational institutions.

## Overview

The Academics module provides a flexible and scalable system for managing the academic structure of educational institutions, from pre-primary to senior secondary levels. It supports complex hierarchical organizations and provides comprehensive analytics and reporting capabilities.

## Features

### 🏫 Academic Structure Management

- **Hierarchical Organization**: Section → Grade → Class structure
- **Flexible Naming**: Support for descriptive class names (North, Blue, Alpha, etc.)
- **Department Management**: Subject and activity-based department organization
- **Capacity Management**: Class capacity tracking and optimization
- **Teacher Assignments**: Class teacher and subject teacher management

### 📅 Academic Calendar

- **Academic Years**: Multi-year support with flexible date ranges
- **Term Management**: 2-4 terms per academic year with customizable dates
- **Current Tracking**: Automatic current academic year and term management
- **Transition Support**: Seamless academic year transitions

### 📊 Analytics & Reporting

- **Real-time Analytics**: Student enrollment, capacity utilization, performance tracking
- **Comprehensive Reports**: Section, grade, and class-level insights
- **Optimization Suggestions**: Class distribution and capacity recommendations
- **Predictive Analysis**: Trend identification and early warning systems

### 🔐 Security & Permissions

- **Role-based Access**: Granular permissions for different user types
- **Object-level Security**: Fine-grained access control for specific entities
- **Audit Trail**: Complete activity logging and compliance tracking

## Installation

1. **Add to INSTALLED_APPS**:

   ```python
   INSTALLED_APPS = [
       # ... other apps
       'academics',
       # ... other apps
   ]
   ```

2. **Run Migrations**:

   ```bash
   python manage.py migrate academics
   ```

3. **Set up Academic Structure**:
   ```bash
   python manage.py setup_academic_structure --sample-data
   ```

## Quick Start

### 1. Create Academic Year with Terms

```python
from academics.services import AcademicYearService
from datetime import datetime

# Create academic year with 3 terms
academic_year = AcademicYearService.setup_academic_year_with_terms(
    name='2024-2025',
    start_date=datetime(2024, 4, 1).date(),
    end_date=datetime(2025, 3, 31).date(),
    num_terms=3,
    user=request.user,
    is_current=True
)
```

### 2. Create Academic Structure

```python
from academics.services import SectionService, GradeService, ClassService

# Create section
section = SectionService.create_section(
    name='Lower Primary',
    description='Grades 1-3',
    order_sequence=1
)

# Create grade
grade = GradeService.create_grade(
    name='Grade 1',
    section_id=section.id,
    minimum_age=6,
    maximum_age=7
)

# Create classes
class_configs = [
    {'name': 'North', 'capacity': 25, 'room_number': '101'},
    {'name': 'South', 'capacity': 25, 'room_number': '102'},
    {'name': 'East', 'capacity': 25, 'room_number': '103'}
]

classes = ClassService.bulk_create_classes(
    grade_id=grade.id,
    academic_year_id=academic_year.id,
    class_configs=class_configs
)
```

### 3. Get Analytics

```python
# Section analytics
section_analytics = SectionService.get_section_analytics(section.id)

# Class analytics
class_analytics = ClassService.get_class_analytics(class_id)

# Grade progression analysis
progression = GradeService.get_grade_progression_analysis(grade.id)
```

## API Usage

### REST API Endpoints

The module provides comprehensive REST API endpoints:

```bash
# Academic Years
GET    /api/academics/academic-years/
POST   /api/academics/academic-years/
GET    /api/academics/academic-years/{id}/
GET    /api/academics/academic-years/current/
POST   /api/academics/academic-years/{id}/set_current/

# Sections
GET    /api/academics/sections/
POST   /api/academics/sections/
GET    /api/academics/sections/{id}/hierarchy/
GET    /api/academics/sections/{id}/analytics/

# Grades
GET    /api/academics/grades/
POST   /api/academics/grades/
GET    /api/academics/grades/by_section/?section_id=1
POST   /api/academics/grades/validate_student_age/

# Classes
GET    /api/academics/classes/
POST   /api/academics/classes/
POST   /api/academics/classes/bulk_create/
GET    /api/academics/classes/{id}/analytics/
POST   /api/academics/classes/optimize_distribution/

# Terms
GET    /api/academics/terms/
POST   /api/academics/terms/
GET    /api/academics/terms/current/
POST   /api/academics/terms/auto_generate/

# Utility Endpoints
GET    /api/academics/structure/
GET    /api/academics/calendar/
POST   /api/academics/validate/
GET    /api/academics/quick-stats/
```

### API Examples

**Create Academic Year with Terms**:

```bash
curl -X POST http://localhost:8000/api/academics/academic-years/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "name": "2024-2025",
    "start_date": "2024-04-01",
    "end_date": "2025-03-31",
    "is_current": true,
    "terms_data": [
      {"name": "First Term"},
      {"name": "Second Term"},
      {"name": "Third Term"}
    ]
  }'
```

**Get Academic Structure**:

```bash
curl -X GET http://localhost:8000/api/academics/structure/ \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Create Multiple Classes**:

```bash
curl -X POST http://localhost:8000/api/academics/classes/bulk_create/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "grade": 1,
    "academic_year": 1,
    "classes": [
      {"name": "A", "capacity": 30, "room_number": "101"},
      {"name": "B", "capacity": 30, "room_number": "102"}
    ]
  }'
```

## Models

### Core Models

#### Department

```python
class Department(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    head = models.OneToOneField('teachers.Teacher', ...)
    is_active = models.BooleanField(default=True)
```

#### AcademicYear

```python
class AcademicYear(models.Model):
    name = models.CharField(max_length=20, unique=True)
    start_date = models.DateField()
    end_date = models.DateField()
    is_current = models.BooleanField(default=False)
```

#### Section

```python
class Section(models.Model):
    name = models.CharField(max_length=100, unique=True)
    department = models.ForeignKey(Department, ...)
    order_sequence = models.PositiveIntegerField()
```

#### Grade

```python
class Grade(models.Model):
    name = models.CharField(max_length=50)
    section = models.ForeignKey(Section, ...)
    minimum_age = models.PositiveIntegerField(null=True)
    maximum_age = models.PositiveIntegerField(null=True)
```

#### Class

```python
class Class(models.Model):
    name = models.CharField(max_length=50)
    grade = models.ForeignKey(Grade, ...)
    academic_year = models.ForeignKey(AcademicYear, ...)
    capacity = models.PositiveIntegerField(default=30)
    class_teacher = models.ForeignKey('teachers.Teacher', ...)
```

## Services

### AcademicYearService

- `create_academic_year()` - Create new academic year
- `setup_academic_year_with_terms()` - Create year with terms
- `get_current_academic_year()` - Get current year
- `get_academic_year_summary()` - Comprehensive summary
- `transition_to_next_term()` - Term transitions

### SectionService

- `create_section()` - Create new section
- `get_section_hierarchy()` - Complete hierarchy
- `get_section_analytics()` - Section analytics
- `get_sections_summary()` - All sections summary

### GradeService

- `create_grade()` - Create new grade
- `get_grade_details()` - Detailed information
- `get_grade_progression_analysis()` - Progression paths
- `validate_student_age_for_grade()` - Age validation

### ClassService

- `create_class()` - Create new class
- `bulk_create_classes()` - Multiple classes
- `get_class_analytics()` - Class analytics
- `optimize_class_distribution()` - Optimization suggestions
- `transfer_student_between_classes()` - Student transfers

### TermService

- `create_term()` - Create new term
- `auto_generate_terms()` - Generate multiple terms
- `get_term_calendar()` - Calendar view
- `validate_term_structure()` - Structure validation

## Management Commands

### setup_academic_structure

Set up basic academic structure:

```bash
# Basic setup
python manage.py setup_academic_structure

# With options
python manage.py setup_academic_structure \
  --year "2024-2025" \
  --start-date "2024-04-01" \
  --end-date "2025-03-31" \
  --terms 3 \
  --sample-data

# Full setup
python manage.py setup_academic_structure \
  --create-departments \
  --create-sections \
  --create-grades \
  --create-classes \
  --force
```

## Background Tasks

The module includes Celery tasks for background processing:

### Analytics Tasks

```python
# Calculate section analytics
calculate_section_analytics.delay(section_id)

# Calculate grade analytics
calculate_grade_analytics.delay(grade_id)

# Calculate class analytics
calculate_class_analytics.delay(class_id)
```

### Maintenance Tasks

```python
# Daily maintenance
daily_academic_maintenance.delay()

# Update term status
update_term_status.delay()

# Bulk analytics update
bulk_update_class_analytics.delay()
```

### Notification Tasks

```python
# Capacity warnings
send_capacity_warning.delay(class_id, 'over_capacity')

# Structure integrity alerts
send_structure_integrity_alert.delay(validation_results)

# Term transition notifications
send_term_transition_notification.delay(from_term_id, to_term_id)
```

## Permissions

### Built-in Permission Classes

- `IsAcademicAdmin` - Academic administrators
- `IsAcademicStaff` - Academic staff members
- `CanManageDepartment` - Department management
- `CanManageAcademicStructure` - Structure management
- `CanManageClass` - Class-specific permissions
- `IsClassTeacher` - Class teacher permissions
- `IsDepartmentHead` - Department head permissions

### Usage Example

```python
from academics.permissions import CanManageClass

class ClassViewSet(viewsets.ModelViewSet):
    permission_classes = [CanManageClass]
    # ... rest of viewset
```

## Forms

### Available Forms

- `AcademicYearForm` - Academic year creation/editing
- `SectionForm` - Section management
- `GradeForm` - Grade management
- `ClassForm` - Class management
- `BulkClassCreateForm` - Multiple class creation
- `AcademicYearTransitionForm` - Year transitions
- `StudentAgeValidationForm` - Age validation

### Usage Example

```python
from academics.forms import ClassForm

def create_class(request):
    if request.method == 'POST':
        form = ClassForm(request.POST)
        if form.is_valid():
            class_instance = form.save()
            # ... handle success
    else:
        form = ClassForm()

    return render(request, 'create_class.html', {'form': form})
```

## Utilities

### Helper Functions

```python
from academics.utils import (
    get_current_academic_context,
    calculate_academic_year_progress,
    generate_class_name_suggestions,
    calculate_optimal_class_size,
    validate_academic_structure_integrity
)

# Get current context
context = get_current_academic_context()

# Generate class names
suggestions = generate_class_name_suggestions(grade)

# Calculate optimal class size
optimization = calculate_optimal_class_size(grade, total_students=75)

# Validate structure
validation = validate_academic_structure_integrity()
```

## Testing

### Run Tests

```bash
# Run all academics tests
python manage.py test academics

# Run specific test cases
python manage.py test academics.tests.AcademicsModelTestCase
python manage.py test academics.tests.AcademicYearServiceTestCase

# Run with coverage
coverage run --source='.' manage.py test academics
coverage report
```

### Test Categories

- **Model Tests**: Basic model functionality and validation
- **Service Tests**: Business logic and service methods
- **API Tests**: REST API endpoints and responses
- **Integration Tests**: Complete workflow testing
- **Permission Tests**: Access control verification

## Configuration

### Settings

```python
# Optional: Custom academic year naming
ACADEMICS_YEAR_FORMAT = '{start_year}-{end_year}'

# Optional: Default class capacity
ACADEMICS_DEFAULT_CLASS_CAPACITY = 30

# Optional: Enable analytics caching
ACADEMICS_ENABLE_ANALYTICS_CACHE = True

# Optional: Analytics cache timeout (seconds)
ACADEMICS_ANALYTICS_CACHE_TIMEOUT = 3600
```

### Cache Configuration

```python
# Redis cache for analytics
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

## Integration

### With Other Modules

#### Students Module

```python
# Student enrollment in classes
from students.models import Student

student = Student.objects.get(id=1)
class_instance = Class.objects.get(id=1)

# Assign student to class
student.current_class = class_instance
student.save()
```

#### Finance Module

```python
# Fee structure based on academic structure
from finance.services import FeeService

# Create fee structure for a class
FeeService.create_fee_structure_for_class(
    class_id=class_instance.id,
    term_id=current_term.id
)
```

#### Analytics Module

```python
# Store analytics data
from analytics.services import AnalyticsService

analytics_data = SectionService.get_section_analytics(section_id)
AnalyticsService.store_section_analytics(section_id, analytics_data)
```

## Best Practices

### 1. Academic Structure Setup

- Create departments first, then sections
- Define sections by educational level (Pre-Primary, Primary, etc.)
- Use descriptive grade names (Grade 1, Grade 2, etc.)
- Use meaningful class names (North, South, A, B, etc.)

### 2. Capacity Management

- Set realistic class capacities based on facility constraints
- Monitor utilization rates regularly
- Use optimization suggestions for efficient distribution

### 3. Academic Year Management

- Plan academic years in advance
- Set up terms with appropriate date ranges
- Use transition validation before switching years

### 4. Permissions and Security

- Assign appropriate roles to users
- Use object-level permissions for sensitive operations
- Regularly audit user access levels

### 5. Performance Optimization

- Use select_related() for foreign key queries
- Implement caching for frequently accessed data
- Use background tasks for heavy analytics calculations

## Troubleshooting

### Common Issues

**Issue**: Multiple current academic years

```python
# Fix: Ensure only one current year
AcademicYear.objects.filter(is_current=True).update(is_current=False)
current_year.is_current = True
current_year.save()
```

**Issue**: Class over capacity

```python
# Check capacity
class_instance = Class.objects.get(id=class_id)
if class_instance.is_full():
    # Increase capacity or create new class
    class_instance.capacity += 5
    class_instance.save()
```

**Issue**: No current term set

```python
# Set appropriate current term
from academics.services import TermService
current_year = AcademicYearService.get_current_academic_year()
if current_year:
    appropriate_term = current_year.terms.filter(
        start_date__lte=timezone.now().date(),
        end_date__gte=timezone.now().date()
    ).first()
    if appropriate_term:
        TermService.set_current_term(appropriate_term.id)
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Ensure all tests pass
6. Submit a pull request

## License

This module is part of the School Management System and is licensed under the MIT License.

## Support

For support and questions:

- Check the documentation
- Review the test cases for usage examples
- Create an issue on the project repository
- Contact the development team

## Changelog

### Version 1.0.0

- Initial release
- Complete academic structure management
- REST API endpoints
- Comprehensive analytics
- Background task support
- Permission system
- Management commands
