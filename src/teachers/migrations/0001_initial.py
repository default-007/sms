# Generated by Django 5.2.1 on 2025-05-19 18:47

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('courses', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Teacher',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('employee_id', models.CharField(max_length=20, unique=True)),
                ('joining_date', models.DateField()),
                ('qualification', models.CharField(max_length=200)),
                ('experience_years', models.DecimalField(decimal_places=1, default=0, max_digits=4)),
                ('specialization', models.CharField(max_length=200)),
                ('position', models.CharField(max_length=100)),
                ('salary', models.DecimalField(decimal_places=2, max_digits=12)),
                ('contract_type', models.CharField(choices=[('Permanent', 'Permanent'), ('Temporary', 'Temporary'), ('Contract', 'Contract')], max_length=20)),
                ('status', models.CharField(choices=[('Active', 'Active'), ('On Leave', 'On Leave'), ('Terminated', 'Terminated')], default='Active', max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('department', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='teachers', to='courses.department')),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='teacher_profile', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['employee_id'],
                'permissions': [('view_teacher_details', 'Can view detailed teacher information'), ('assign_classes', 'Can assign classes to teachers')],
            },
        ),
        migrations.CreateModel(
            name='TeacherEvaluation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('evaluation_date', models.DateField()),
                ('criteria', models.JSONField()),
                ('score', models.DecimalField(decimal_places=2, max_digits=5)),
                ('remarks', models.TextField()),
                ('followup_actions', models.TextField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('evaluator', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='teacher_evaluations', to=settings.AUTH_USER_MODEL)),
                ('teacher', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='evaluations', to='teachers.teacher')),
            ],
            options={
                'ordering': ['-evaluation_date'],
            },
        ),
        migrations.CreateModel(
            name='TeacherClassAssignment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('is_class_teacher', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('academic_year', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='courses.academicyear')),
                ('class_instance', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='teacher_assignments', to='courses.class')),
                ('subject', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='teacher_assignments', to='courses.subject')),
                ('teacher', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='class_assignments', to='teachers.teacher')),
            ],
            options={
                'unique_together': {('teacher', 'class_instance', 'subject', 'academic_year')},
            },
        ),
    ]
