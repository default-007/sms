# Generated by Django 5.2.1 on 2025-07-10 07:44

import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0002_remove_userprofile_birth_date_and_more'),
    ]

    operations = [
        migrations.RemoveIndex(
            model_name='user',
            name='accounts_us_phone_n_613c4a_idx',
        ),
        migrations.RemoveIndex(
            model_name='user',
            name='accounts_us_email_v_262863_idx',
        ),
        migrations.RemoveIndex(
            model_name='userauditlog',
            name='accounts_us_severit_bf052a_idx',
        ),
        migrations.RemoveIndex(
            model_name='userauditlog',
            name='accounts_us_ip_addr_c78954_idx',
        ),
        migrations.RemoveIndex(
            model_name='userrole',
            name='accounts_us_is_acti_2b136f_idx',
        ),
        migrations.RemoveIndex(
            model_name='userroleassignment',
            name='accounts_us_require_51dcfd_idx',
        ),
        migrations.RemoveIndex(
            model_name='usersession',
            name='accounts_us_ip_addr_0fc6b1_idx',
        ),
        migrations.RemoveField(
            model_name='user',
            name='backup_codes',
        ),
        migrations.RemoveField(
            model_name='user',
            name='email_notifications',
        ),
        migrations.RemoveField(
            model_name='user',
            name='email_verified',
        ),
        migrations.RemoveField(
            model_name='user',
            name='language_preference',
        ),
        migrations.RemoveField(
            model_name='user',
            name='phone_verified',
        ),
        migrations.RemoveField(
            model_name='user',
            name='sms_notifications',
        ),
        migrations.RemoveField(
            model_name='user',
            name='timezone_preference',
        ),
        migrations.RemoveField(
            model_name='user',
            name='two_factor_enabled',
        ),
        migrations.RemoveField(
            model_name='userauditlog',
            name='session_key',
        ),
        migrations.RemoveField(
            model_name='userauditlog',
            name='severity',
        ),
        migrations.RemoveField(
            model_name='userauditlog',
            name='tags',
        ),
        migrations.RemoveField(
            model_name='userprofile',
            name='department',
        ),
        migrations.RemoveField(
            model_name='userprofile',
            name='education_level',
        ),
        migrations.RemoveField(
            model_name='userprofile',
            name='emergency_contact_name',
        ),
        migrations.RemoveField(
            model_name='userprofile',
            name='emergency_contact_phone',
        ),
        migrations.RemoveField(
            model_name='userprofile',
            name='emergency_contact_relationship',
        ),
        migrations.RemoveField(
            model_name='userprofile',
            name='employee_id',
        ),
        migrations.RemoveField(
            model_name='userprofile',
            name='institution',
        ),
        migrations.RemoveField(
            model_name='userprofile',
            name='last_profile_update',
        ),
        migrations.RemoveField(
            model_name='userprofile',
            name='occupation',
        ),
        migrations.RemoveField(
            model_name='userprofile',
            name='profile_views',
        ),
        migrations.RemoveField(
            model_name='userrole',
            name='color_code',
        ),
        migrations.RemoveField(
            model_name='userrole',
            name='is_active',
        ),
        migrations.RemoveField(
            model_name='userrole',
            name='parent_role',
        ),
        migrations.RemoveField(
            model_name='userroleassignment',
            name='approved_at',
        ),
        migrations.RemoveField(
            model_name='userroleassignment',
            name='approved_by',
        ),
        migrations.RemoveField(
            model_name='userroleassignment',
            name='assignment_reason',
        ),
        migrations.RemoveField(
            model_name='userroleassignment',
            name='requires_approval',
        ),
        migrations.RemoveField(
            model_name='usersession',
            name='browser',
        ),
        migrations.RemoveField(
            model_name='usersession',
            name='city',
        ),
        migrations.RemoveField(
            model_name='usersession',
            name='country',
        ),
        migrations.RemoveField(
            model_name='usersession',
            name='device_type',
        ),
        migrations.RemoveField(
            model_name='usersession',
            name='logout_reason',
        ),
        migrations.RemoveField(
            model_name='usersession',
            name='os',
        ),
        migrations.AddField(
            model_name='userprofile',
            name='birth_date',
            field=models.DateField(blank=True, null=True, verbose_name='birth date'),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='email_notifications',
            field=models.BooleanField(default=True, verbose_name='email notifications'),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='language',
            field=models.CharField(default='en', max_length=10, verbose_name='language'),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='sms_notifications',
            field=models.BooleanField(default=False, verbose_name='SMS notifications'),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='timezone',
            field=models.CharField(default='UTC', max_length=50, verbose_name='timezone'),
        ),
        migrations.AlterField(
            model_name='user',
            name='email',
            field=models.EmailField(max_length=254, unique=True, verbose_name='email address'),
        ),
        migrations.AlterField(
            model_name='user',
            name='phone_number',
            field=models.CharField(blank=True, max_length=20, null=True, validators=[django.core.validators.RegexValidator('^\\+?1?\\d{9,15}$', 'Phone number must be entered in the format: "+999999999". Up to 15 digits allowed.')], verbose_name='phone number'),
        ),
        migrations.AlterField(
            model_name='user',
            name='profile_picture',
            field=models.ImageField(blank=True, null=True, upload_to='profile_pictures/%Y/%m/', verbose_name='profile picture'),
        ),
        migrations.AlterField(
            model_name='userauditlog',
            name='action',
            field=models.CharField(choices=[('create', 'Create'), ('update', 'Update'), ('delete', 'Delete'), ('login', 'Login'), ('logout', 'Logout'), ('password_change', 'Password Change'), ('role_assign', 'Role Assigned'), ('role_remove', 'Role Removed'), ('account_lock', 'Account Locked'), ('account_unlock', 'Account Unlocked')], max_length=20, verbose_name='action'),
        ),
        migrations.AlterField(
            model_name='userauditlog',
            name='user',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='user_audit_logs', to=settings.AUTH_USER_MODEL, verbose_name='user'),
        ),
    ]
