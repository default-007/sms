# Scheduling Module Documentation

## Overview

The Scheduling module is a comprehensive timetable management system designed for educational institutions. It provides automated timetable generation, conflict resolution, room management, substitute teacher assignments, and detailed analytics.

## Features

### 🗓️ Timetable Management

- **Automated Generation**: AI-powered timetable optimization using genetic algorithms
- **Manual Creation**: Fine-grained control over individual timetable entries
- **Conflict Detection**: Real-time identification and resolution of scheduling conflicts
- **Bulk Operations**: Mass creation, updates, and copying between terms
- **Template System**: Reusable timetable templates for different grades

### 🏫 Resource Management

- **Room Management**: Comprehensive room tracking with utilization analytics
- **Time Slot Configuration**: Flexible period definitions with break management
- **Equipment Tracking**: Room equipment and suitability matching
- **Capacity Management**: Student count vs. room capacity optimization

### 👨‍🏫 Teacher Management

- **Workload Analysis**: Balanced distribution of teaching loads
- **Availability Tracking**: Real-time teacher availability checking
- **Substitute Management**: Automated substitute teacher assignments
- **Performance Analytics**: Teaching effectiveness correlation

### 📊 Analytics & Reporting

- **Optimization Scoring**: Multi-dimensional timetable quality assessment
- **Utilization Reports**: Room, teacher, and resource utilization analytics
- **Conflict Analysis**: Comprehensive conflict detection and reporting
- **Performance Insights**: Data-driven scheduling improvements

### 🔧 Advanced Features

- **Constraint Engine**: Customizable scheduling rules and preferences
- **Multi-algorithm Support**: Genetic algorithm and greedy scheduling
- **Real-time Notifications**: Automated alerts for conflicts and changes
- **Export Capabilities**: Multiple format support (CSV, JSON, PDF)

## Architecture

### Models

#### Core Models

- **TimeSlot**: Period definitions with day, time, and duration
- **Room**: Physical spaces with capacity and equipment
- **Timetable**: Core scheduling entries linking classes, subjects, teachers
- **TimetableGeneration**: Optimization session tracking

#### Supporting Models

- **SubstituteTeacher**: Substitute assignments and approvals
- **SchedulingConstraint**: Customizable scheduling rules
- **TimetableTemplate**: Reusable scheduling patterns

### Services

#### TimetableService

Core timetable operations including creation, conflict checking, and bulk operations.

```python
from scheduling.services.timetable_service import TimetableService

# Create timetable entry
timetable = TimetableService.create_timetable_entry(
    class_assigned=class_obj,
    subject=subject,
    teacher=teacher,
    time_slot=time_slot,
    term=term,
    room=room
)

# Check for conflicts
conflicts = TimetableService.check_conflicts(
    teacher=teacher,
    time_slot=time_slot,
    date_range=(start_date, end_date)
)

# Get class timetable
timetable_data = TimetableService.get_class_timetable(class_obj, term)
```

#### OptimizationService

Advanced timetable generation using optimization algorithms.

```python
from scheduling.services.optimization_service import OptimizationService

optimizer = OptimizationService(term)
result = optimizer.generate_optimized_timetable(
    grades=grades,
    algorithm='genetic',
    population_size=50,
    generations=100
)
```

#### AnalyticsService

Comprehensive analytics and reporting functionality.

```python
from scheduling.services.analytics_service import SchedulingAnalyticsService

# Teacher workload analytics
workload = SchedulingAnalyticsService.get_teacher_workload_analytics(term)

# Room utilization
utilization = SchedulingAnalyticsService.get_room_utilization_analytics(term)

# Optimization score
score = SchedulingAnalyticsService.get_timetable_optimization_score(term)
```

### API Endpoints

#### Timetable Management

```
GET    /api/scheduling/timetables/                    # List timetables
POST   /api/scheduling/timetables/                    # Create timetable
GET    /api/scheduling/timetables/{id}/               # Get timetable
PUT    /api/scheduling/timetables/{id}/               # Update timetable
DELETE /api/scheduling/timetables/{id}/               # Delete timetable

GET    /api/scheduling/timetables/class/{class_id}/   # Class timetable
GET    /api/scheduling/timetables/teacher/{teacher_id}/ # Teacher timetable
POST   /api/scheduling/timetables/bulk-create/        # Bulk create
POST   /api/scheduling/timetables/check-conflicts/    # Check conflicts
```

#### Resource Management

```
GET    /api/scheduling/rooms/                         # List rooms
POST   /api/scheduling/rooms/                         # Create room
GET    /api/scheduling/rooms/{id}/utilization/        # Room utilization
POST   /api/scheduling/rooms/suggest-optimal/         # Room suggestions

GET    /api/scheduling/time-slots/                    # List time slots
POST   /api/scheduling/time-slots/bulk-create/        # Bulk create slots
```

#### Optimization

```
POST   /api/scheduling/generations/                   # Start generation
GET    /api/scheduling/generations/                   # List generations
GET    /api/scheduling/generations/{id}/              # Generation status
POST   /api/scheduling/generations/{id}/cancel/       # Cancel generation
```

#### Analytics

```
GET    /api/scheduling/analytics/teacher-workload/    # Teacher analytics
GET    /api/scheduling/analytics/room-utilization/    # Room analytics
GET    /api/scheduling/analytics/conflicts/           # Conflict analytics
GET    /api/scheduling/analytics/optimization-score/  # Optimization score
```

## Installation & Setup

### 1. Add to INSTALLED_APPS

```python
INSTALLED_APPS = [
    # ... other apps
    'scheduling',
    'academics',  # Required dependency
    'subjects',   # Required dependency
    'teachers',   # Required dependency
]
```

### 2. Database Migration

```bash
python manage.py makemigrations scheduling
python manage.py migrate
```

### 3. Create Time Slots

```bash
# Generate standard time slots
python manage.py generate_time_slots

# Or create custom time slots
python manage.py generate_time_slots \
    --start-time 08:00 \
    --end-time 15:30 \
    --period-duration 45 \
    --break-duration 15 \
    --lunch-duration 45
```

### 4. Create Sample Data (Optional)

```bash
python manage.py generate_sample_scheduling_data \
    --sections 3 \
    --grades-per-section 4 \
    --classes-per-grade 2 \
    --teachers 20 \
    --subjects 10 \
    --rooms 25 \
    --create-timetables \
    --create-substitutes
```

## Usage Guide

### Basic Timetable Creation

#### 1. Manual Creation

```python
from scheduling.models import Timetable
from scheduling.services.timetable_service import TimetableService

# Create individual timetable entry
timetable = TimetableService.create_timetable_entry(
    class_assigned=Class.objects.get(name='Grade 1 A'),
    subject=Subject.objects.get(name='Mathematics'),
    teacher=Teacher.objects.get(employee_id='T001'),
    time_slot=TimeSlot.objects.get(day_of_week=0, period_number=1),
    term=Term.objects.get(is_current=True),
    room=Room.objects.get(number='101')
)
```

#### 2. Bulk Creation

```python
# Prepare bulk data
updates = [
    {
        'class_assigned': class1,
        'subject': subject1,
        'teacher': teacher1,
        'time_slot': slot1,
        'room': room1,
        'effective_from_date': term.start_date,
        'effective_to_date': term.end_date
    },
    # ... more entries
]

# Bulk create
result = TimetableService.bulk_update_timetable(term, updates, user)
```

### Automated Timetable Generation

#### 1. Using Management Command

```bash
# Basic optimization
python manage.py optimize_timetable --term-id <term_id>

# Advanced options
python manage.py optimize_timetable \
    --term-id <term_id> \
    --grade-ids <grade1_id> <grade2_id> \
    --algorithm genetic \
    --population-size 100 \
    --generations 200 \
    --mutation-rate 0.15 \
    --clear-existing \
    --verbose
```

#### 2. Using Service

```python
from scheduling.services.optimization_service import OptimizationService

optimizer = OptimizationService(term)
result = optimizer.generate_optimized_timetable(
    grades=Grade.objects.filter(section__name='Primary'),
    algorithm='genetic',
    population_size=50,
    generations=100,
    mutation_rate=0.1
)

if result.success:
    optimizer.save_schedule_to_database(result, user)
```

#### 3. Asynchronous Generation

```python
from scheduling.tasks import generate_optimized_timetable

# Start async generation
task = generate_optimized_timetable.delay(
    generation_id=generation.id,
    algorithm='genetic',
    population_size=50,
    generations=100
)
```

### Conflict Management

#### 1. Checking Conflicts

```python
conflicts = TimetableService.check_conflicts(
    teacher=teacher,
    room=room,
    class_obj=class_obj,
    time_slot=time_slot,
    date_range=(start_date, end_date)
)

for conflict in conflicts:
    print(f"Conflict: {conflict['type']} - {conflict['message']}")
```

#### 2. Resolving Conflicts

```python
from scheduling.utils import ConflictResolver

# Find alternative slots
alternatives = ConflictResolver.find_alternative_slots(
    teacher=teacher,
    subject=subject,
    class_obj=class_obj,
    term=term,
    preferred_days=[0, 1, 2, 3, 4]  # Monday to Friday
)

# Suggest alternative rooms
room_alternatives = ConflictResolver.suggest_room_alternatives(
    time_slot=time_slot,
    term=term,
    subject=subject,
    min_capacity=30
)
```

### Substitute Teacher Management

#### 1. Creating Substitute Assignment

```python
from scheduling.services.timetable_service import SubstituteService

substitute = SubstituteService.create_substitute_assignment(
    original_timetable=timetable,
    substitute_teacher=substitute_teacher,
    date=date.today(),
    reason='Sick leave',
    created_by=user
)
```

#### 2. Getting Substitute Suggestions

```python
suggestions = SubstituteService.get_substitute_suggestions(
    original_timetable=timetable,
    date=date.today()
)

for suggestion in suggestions:
    teacher = suggestion['teacher']
    score = suggestion['compatibility_score']
    print(f"Suggested: {teacher.user.get_full_name()} (Score: {score})")
```

### Analytics and Reporting

#### 1. Teacher Workload Analysis

```python
analytics = SchedulingAnalyticsService.get_teacher_workload_analytics(term)

print(f"Total Teachers: {analytics['summary']['total_teachers']}")
print(f"Average Periods: {analytics['summary']['average_periods_per_teacher']}")

for teacher_data in analytics['teacher_workloads']:
    print(f"{teacher_data['teacher__first_name']}: {teacher_data['total_periods']} periods")
```

#### 2. Room Utilization

```python
utilization = SchedulingAnalyticsService.get_room_utilization_analytics(term)

for room_data in utilization['room_utilization']:
    print(f"Room {room_data['room__number']}: {room_data['utilization_rate']:.1f}% utilized")
```

#### 3. Optimization Score

```python
score_data = SchedulingAnalyticsService.get_timetable_optimization_score(term)

print(f"Overall Score: {score_data['overall_score']:.1f}% (Grade: {score_data['grade']})")
print("Breakdown:")
for category, score in score_data['breakdown'].items():
    print(f"  {category}: {score:.1f}")

print("Recommendations:")
for recommendation in score_data['recommendations']:
    print(f"  - {recommendation}")
```

## Configuration

### Scheduling Constraints

Create custom scheduling constraints to fit your institution's needs:

```python
from scheduling.models import SchedulingConstraint

# Core subjects in morning
constraint = SchedulingConstraint.objects.create(
    name='Core Subjects Morning Preference',
    constraint_type='time_preference',
    parameters={
        'subjects': ['Mathematics', 'English', 'Science'],
        'preferred_periods': [1, 2, 3, 4],
        'weight': 0.8
    },
    priority=8,
    is_hard_constraint=False,
    is_active=True
)
```

### Celery Configuration

Add scheduling tasks to your Celery beat schedule:

```python
CELERY_BEAT_SCHEDULE = {
    'daily-schedule-validation': {
        'task': 'scheduling.tasks.daily_schedule_validation',
        'schedule': '0 6 * * *',  # Every day at 6 AM
    },
    'substitute-reminders': {
        'task': 'scheduling.tasks.send_substitute_reminders',
        'schedule': '0 18 * * *',  # Every day at 6 PM
    },
    'weekly-analytics-report': {
        'task': 'scheduling.tasks.weekly_analytics_report',
        'schedule': '0 8 * * 1',  # Every Monday at 8 AM
    },
}
```

### Permissions

Set up proper permissions for different user roles:

```python
from django.contrib.auth.models import Group, Permission

# Create scheduling group
scheduling_group = Group.objects.create(name='Scheduling Administrators')

# Add permissions
permissions = [
    'scheduling.view_timetable_analytics',
    'scheduling.generate_timetable',
    'scheduling.optimize_timetable',
    'scheduling.manage_rooms',
    'scheduling.assign_substitute_teacher',
]

for perm_codename in permissions:
    perm = Permission.objects.get(codename=perm_codename)
    scheduling_group.permissions.add(perm)
```

## Best Practices

### 1. Data Organization

- **Academic Structure**: Ensure proper Section → Grade → Class hierarchy
- **Teacher Assignments**: Create TeacherClassAssignment records before timetabling
- **Subject Requirements**: Define credit hours and room requirements for subjects
- **Time Slots**: Create consistent time slots across all days

### 2. Optimization Tips

- **Start Small**: Begin with fewer grades and expand gradually
- **Room Capacity**: Ensure adequate room capacity for all classes
- **Teacher Load**: Balance teacher workloads across the week
- **Constraints**: Use soft constraints for preferences, hard constraints for requirements

### 3. Conflict Resolution

- **Proactive Checking**: Always check conflicts before creating timetables
- **Regular Validation**: Run daily validation to catch issues early
- **Alternative Planning**: Maintain backup options for critical assignments
- **Documentation**: Keep detailed logs of all changes and conflicts

### 4. Performance Optimization

- **Database Indexes**: Ensure proper indexing on frequently queried fields
- **Caching**: Use Redis caching for analytics data
- **Async Processing**: Use Celery for long-running optimization tasks
- **Batch Operations**: Use bulk operations for large data sets

## Troubleshooting

### Common Issues

#### 1. Optimization Fails

```bash
# Check data completeness
python manage.py analyze_timetable --term-id <term_id> --detailed

# Verify constraints
python manage.py shell
>>> from scheduling.models import SchedulingConstraint
>>> constraints = SchedulingConstraint.objects.filter(is_active=True)
>>> for c in constraints: print(f"{c.name}: {c.constraint_type}")
```

#### 2. High Conflict Count

```python
# Analyze conflicts
from scheduling.utils import ScheduleValidator

validation = ScheduleValidator.validate_term_schedule(term)
print(f"Issues: {validation['total_issues']}")
print(f"Warnings: {validation['total_warnings']}")

for issue in validation['issues']:
    print(f"- {issue}")
```

#### 3. Poor Optimization Score

```python
# Check individual components
score_data = SchedulingAnalyticsService.get_timetable_optimization_score(term)

for category, score in score_data['breakdown'].items():
    if score < 15:  # Low score threshold
        print(f"Low score in {category}: {score}")
```

### Debug Mode

Enable verbose logging for detailed debugging:

```python
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'scheduling_file': {
            'level': 'DEBUG',
            'class': 'logging.FileHandler',
            'filename': 'scheduling_debug.log',
        },
    },
    'loggers': {
        'scheduling': {
            'handlers': ['scheduling_file'],
            'level': 'DEBUG',
            'propagate': True,
        },
    },
}
```

## Advanced Usage

### Custom Optimization Algorithms

Extend the optimization service with custom algorithms:

```python
from scheduling.services.optimization_service import OptimizationService

class CustomOptimizationService(OptimizationService):
    def custom_algorithm(self, required_slots):
        # Implement your custom algorithm
        # Return SchedulingResult object
        pass
```

### Custom Analytics

Create custom analytics for specific needs:

```python
from scheduling.services.analytics_service import SchedulingAnalyticsService

class CustomAnalyticsService(SchedulingAnalyticsService):
    @staticmethod
    def get_subject_popularity_analytics(term):
        # Custom analytics implementation
        pass
```

### Integration with External Systems

```python
# Export to external calendar systems
from scheduling.utils import ScheduleExporter

csv_data = ScheduleExporter.export_class_schedule_csv(class_obj, term)
json_data = ScheduleExporter.export_teacher_schedule_json(teacher, term)

# Send to external system
external_system.import_schedule(csv_data)
```

## Support

For issues, questions, or contributions:

1. **Documentation**: Check this README and inline code documentation
2. **Issues**: Report bugs and feature requests via GitHub issues
3. **Community**: Join our community discussions
4. **Support**: Contact support team for enterprise assistance

## License

This module is part of the School Management System and follows the same licensing terms.
