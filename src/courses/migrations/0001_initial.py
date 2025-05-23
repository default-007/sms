# Generated by Django 5.2.1 on 2025-05-19 18:47

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='AcademicYear',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=50)),
                ('start_date', models.DateField()),
                ('end_date', models.DateField()),
                ('is_current', models.BooleanField(default=False)),
            ],
        ),
        migrations.CreateModel(
            name='Assignment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=200)),
                ('description', models.TextField()),
                ('assigned_date', models.DateField(auto_now_add=True)),
                ('due_date', models.DateField()),
                ('total_marks', models.PositiveIntegerField()),
                ('attachment', models.FileField(blank=True, null=True, upload_to='assignments/')),
                ('submission_type', models.CharField(choices=[('online', 'Online'), ('physical', 'Physical')], default='online', max_length=10)),
                ('status', models.CharField(choices=[('draft', 'Draft'), ('published', 'Published'), ('closed', 'Closed')], default='draft', max_length=10)),
            ],
        ),
        migrations.CreateModel(
            name='AssignmentSubmission',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('submission_date', models.DateTimeField(auto_now_add=True)),
                ('content', models.TextField(blank=True)),
                ('file', models.FileField(blank=True, null=True, upload_to='assignment_submissions/')),
                ('remarks', models.TextField(blank=True)),
                ('marks_obtained', models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True)),
                ('status', models.CharField(choices=[('submitted', 'Submitted'), ('late', 'Late'), ('graded', 'Graded')], default='submitted', max_length=10)),
                ('graded_at', models.DateTimeField(blank=True, null=True)),
            ],
        ),
        migrations.CreateModel(
            name='Class',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('room_number', models.CharField(blank=True, max_length=20)),
                ('capacity', models.PositiveIntegerField(default=30)),
            ],
            options={
                'verbose_name_plural': 'Classes',
            },
        ),
        migrations.CreateModel(
            name='Department',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('description', models.TextField(blank=True)),
                ('creation_date', models.DateField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name='Grade',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=50)),
                ('description', models.TextField(blank=True)),
            ],
        ),
        migrations.CreateModel(
            name='Section',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=20)),
                ('description', models.TextField(blank=True)),
            ],
        ),
        migrations.CreateModel(
            name='Subject',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('code', models.CharField(max_length=20, unique=True)),
                ('description', models.TextField(blank=True)),
                ('credit_hours', models.DecimalField(decimal_places=1, default=1.0, max_digits=3)),
                ('is_elective', models.BooleanField(default=False)),
            ],
        ),
        migrations.CreateModel(
            name='Syllabus',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=200)),
                ('description', models.TextField(blank=True)),
                ('content', models.JSONField(default=dict)),
                ('last_updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name_plural': 'Syllabi',
            },
        ),
        migrations.CreateModel(
            name='TimeSlot',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('day_of_week', models.IntegerField(choices=[(0, 'Monday'), (1, 'Tuesday'), (2, 'Wednesday'), (3, 'Thursday'), (4, 'Friday'), (5, 'Saturday'), (6, 'Sunday')])),
                ('start_time', models.TimeField()),
                ('end_time', models.TimeField()),
                ('duration_minutes', models.PositiveIntegerField()),
            ],
        ),
        migrations.CreateModel(
            name='Timetable',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('room', models.CharField(blank=True, max_length=20)),
                ('effective_from_date', models.DateField()),
                ('effective_to_date', models.DateField(blank=True, null=True)),
                ('is_active', models.BooleanField(default=True)),
            ],
        ),
    ]
