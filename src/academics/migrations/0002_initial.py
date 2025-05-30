# Generated by Django 5.2.1 on 2025-05-29 14:07

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('academics', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='academicyear',
            name='created_by',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_academic_years', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='class',
            name='academic_year',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='classes', to='academics.academicyear'),
        ),
    ]
