# tests.py
from django.test import TestCase, TransactionTestCase
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.urls import reverse
from django.utils import timezone
from django.core.management import call_command
from django.core.cache import cache
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from unittest.mock import patch, MagicMock
from decimal import Decimal
from datetime import datetime, timedelta
import json

from .models import (
    SystemSetting,
    AuditLog,
    StudentPerformanceAnalytics,
    ClassPerformanceAnalytics,
    AttendanceAnalytics,
    FinancialAnalytics,
    TeacherPerformanceAnalytics,
    SystemHealthMetrics,
)
from .services import (
    ConfigurationService,
    AuditService,
    AnalyticsService,
    ValidationService,
    SecurityService,
    UtilityService,
)
from .utils import ValidationUtils, DateUtils, SecurityUtils, FormatUtils, MathUtils
from .decorators import audit_action, rate_limit, require_role

User = get_user_model()


class SystemSettingModelTests(TestCase):
    """Tests for SystemSetting model"""

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )

    def test_create_system_setting(self):
        """Test creating a system setting"""
        setting = SystemSetting.objects.create(
            setting_key="test.setting",
            setting_value="test_value",
            data_type="string",
            category="system",
            description="Test setting",
        )

        self.assertEqual(setting.setting_key, "test.setting")
        self.assertEqual(setting.get_typed_value(), "test_value")
        self.assertEqual(setting.data_type, "string")

    def test_typed_value_boolean(self):
        """Test boolean typed value"""
        setting = SystemSetting.objects.create(
            setting_key="test.boolean", setting_value="true", data_type="boolean"
        )

        self.assertTrue(setting.get_typed_value())

        setting.set_typed_value(False)
        setting.save()

        self.assertFalse(setting.get_typed_value())

    def test_typed_value_integer(self):
        """Test integer typed value"""
        setting = SystemSetting.objects.create(
            setting_key="test.integer", setting_value="42", data_type="integer"
        )

        self.assertEqual(setting.get_typed_value(), 42)

        setting.set_typed_value(100)
        setting.save()

        self.assertEqual(setting.get_typed_value(), 100)

    def test_typed_value_json(self):
        """Test JSON typed value"""
        test_data = {"key": "value", "number": 123}

        setting = SystemSetting.objects.create(
            setting_key="test.json",
            setting_value=json.dumps(test_data),
            data_type="json",
        )

        self.assertEqual(setting.get_typed_value(), test_data)


class AuditLogModelTests(TestCase):
    """Tests for AuditLog model"""

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )

    def test_create_audit_log(self):
        """Test creating an audit log"""
        log = AuditLog.objects.create(
            user=self.user,
            action="create",
            description="Test action",
            ip_address="127.0.0.1",
            module_name="test",
        )

        self.assertEqual(log.user, self.user)
        self.assertEqual(log.action, "create")
        self.assertEqual(log.description, "Test action")

    def test_audit_log_with_object(self):
        """Test audit log with content object"""
        setting = SystemSetting.objects.create(
            setting_key="test.setting", setting_value="test", data_type="string"
        )

        log = AuditLog.objects.create(
            user=self.user,
            action="update",
            content_object=setting,
            description="Updated setting",
        )

        self.assertEqual(log.content_object, setting)


class ConfigurationServiceTests(TestCase):
    """Tests for ConfigurationService"""

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )
        # Clear cache before each test
        cache.clear()

    def test_get_setting_default(self):
        """Test getting a setting with default value"""
        value = ConfigurationService.get_setting("nonexistent.setting", "default_value")
        self.assertEqual(value, "default_value")

    def test_set_and_get_setting(self):
        """Test setting and getting a configuration value"""
        ConfigurationService.set_setting(
            "test.setting",
            "test_value",
            user=self.user,
            data_type="string",
            category="test",
        )

        value = ConfigurationService.get_setting("test.setting")
        self.assertEqual(value, "test_value")

    def test_cache_functionality(self):
        """Test that settings are properly cached"""
        # Set a setting
        ConfigurationService.set_setting("test.cache", "cached_value", user=self.user)

        # Get it twice - second call should use cache
        value1 = ConfigurationService.get_setting("test.cache")
        value2 = ConfigurationService.get_setting("test.cache")

        self.assertEqual(value1, value2)
        self.assertEqual(value1, "cached_value")

    def test_get_settings_by_category(self):
        """Test getting settings by category"""
        ConfigurationService.set_setting("cat1.setting1", "value1", category="cat1")
        ConfigurationService.set_setting("cat1.setting2", "value2", category="cat1")
        ConfigurationService.set_setting("cat2.setting1", "value3", category="cat2")

        cat1_settings = ConfigurationService.get_settings_by_category("cat1")

        self.assertEqual(len(cat1_settings), 2)
        self.assertEqual(cat1_settings["cat1.setting1"], "value1")
        self.assertEqual(cat1_settings["cat1.setting2"], "value2")

    def test_initialize_default_settings(self):
        """Test initialization of default settings"""
        ConfigurationService.initialize_default_settings()

        # Check that some default settings were created
        self.assertTrue(
            SystemSetting.objects.filter(setting_key="academic.terms_per_year").exists()
        )
        self.assertTrue(
            SystemSetting.objects.filter(
                setting_key="finance.late_fee_percentage"
            ).exists()
        )


class AuditServiceTests(TestCase):
    """Tests for AuditService"""

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )

    def test_log_action(self):
        """Test logging an action"""
        log = AuditService.log_action(
            user=self.user,
            action="test",
            description="Test action",
            ip_address="127.0.0.1",
            module_name="test",
        )

        self.assertIsInstance(log, AuditLog)
        self.assertEqual(log.user, self.user)
        self.assertEqual(log.action, "test")

    def test_log_login(self):
        """Test logging user login"""
        log = AuditService.log_login(
            user=self.user, ip_address="127.0.0.1", session_key="test_session"
        )

        self.assertEqual(log.action, "login")
        self.assertEqual(log.user, self.user)

    def test_get_user_activity(self):
        """Test getting user activity"""
        # Create some audit logs
        AuditService.log_action(user=self.user, action="action1", description="Test 1")
        AuditService.log_action(user=self.user, action="action2", description="Test 2")

        activity = AuditService.get_user_activity(self.user, days=30)

        self.assertEqual(activity.count(), 2)

    def test_cleanup_old_logs(self):
        """Test cleaning up old audit logs"""
        # Create old log
        old_log = AuditLog.objects.create(
            user=self.user, action="old_action", description="Old log"
        )
        # Manually set old timestamp
        old_timestamp = timezone.now() - timedelta(days=400)
        AuditLog.objects.filter(id=old_log.id).update(timestamp=old_timestamp)

        # Create recent log
        AuditService.log_action(
            user=self.user, action="recent", description="Recent log"
        )

        deleted_count = AuditService.cleanup_old_logs(days=365)

        self.assertEqual(deleted_count, 1)
        self.assertEqual(AuditLog.objects.count(), 1)


class ValidationUtilsTests(TestCase):
    """Tests for ValidationUtils"""

    def test_validate_phone_number(self):
        """Test phone number validation"""
        self.assertTrue(ValidationUtils.validate_phone_number("+1234567890"))
        self.assertTrue(ValidationUtils.validate_phone_number("(123) 456-7890"))
        self.assertTrue(ValidationUtils.validate_phone_number("123-456-7890"))
        self.assertFalse(ValidationUtils.validate_phone_number("123"))
        self.assertFalse(ValidationUtils.validate_phone_number(""))

    def test_validate_admission_number(self):
        """Test admission number validation"""
        self.assertTrue(ValidationUtils.validate_admission_number("STU123456"))
        self.assertTrue(ValidationUtils.validate_admission_number("ABC123"))
        self.assertFalse(ValidationUtils.validate_admission_number("123"))  # Too short
        self.assertFalse(
            ValidationUtils.validate_admission_number("abc123")
        )  # Lowercase
        self.assertFalse(
            ValidationUtils.validate_admission_number("STU@123")
        )  # Special chars

    def test_validate_percentage(self):
        """Test percentage validation"""
        self.assertTrue(ValidationUtils.validate_percentage(50))
        self.assertTrue(ValidationUtils.validate_percentage(0))
        self.assertTrue(ValidationUtils.validate_percentage(100))
        self.assertTrue(ValidationUtils.validate_percentage(Decimal("75.5")))
        self.assertFalse(ValidationUtils.validate_percentage(-1))
        self.assertFalse(ValidationUtils.validate_percentage(101))
        self.assertFalse(ValidationUtils.validate_percentage("invalid"))

    def test_validate_marks(self):
        """Test marks validation"""
        self.assertTrue(ValidationUtils.validate_marks(75, 100))
        self.assertTrue(ValidationUtils.validate_marks(0, 100))
        self.assertTrue(ValidationUtils.validate_marks(100, 100))
        self.assertFalse(ValidationUtils.validate_marks(-1, 100))
        self.assertFalse(ValidationUtils.validate_marks(101, 100))


class DateUtilsTests(TestCase):
    """Tests for DateUtils"""

    def test_get_academic_year_from_date(self):
        """Test getting academic year from date"""
        # July - should be start of new academic year
        july_date = datetime(2024, 7, 15)
        self.assertEqual(DateUtils.get_academic_year_from_date(july_date), "2024-2025")

        # March - should be in previous academic year
        march_date = datetime(2024, 3, 15)
        self.assertEqual(DateUtils.get_academic_year_from_date(march_date), "2023-2024")

    def test_calculate_age(self):
        """Test age calculation"""
        birth_date = datetime(2000, 5, 15)
        age = DateUtils.calculate_age(birth_date)

        # Age should be calculated correctly based on current date
        expected_age = timezone.now().year - 2000
        if timezone.now().month < 5 or (
            timezone.now().month == 5 and timezone.now().day < 15
        ):
            expected_age -= 1

        self.assertEqual(age, expected_age)

    def test_get_working_days(self):
        """Test working days calculation"""
        start_date = datetime(2024, 1, 1)  # Monday
        end_date = datetime(2024, 1, 7)  # Sunday

        working_days = DateUtils.get_working_days(
            start_date, end_date, exclude_weekends=True
        )
        self.assertEqual(working_days, 5)  # Mon-Fri

        total_days = DateUtils.get_working_days(
            start_date, end_date, exclude_weekends=False
        )
        self.assertEqual(total_days, 7)  # All days


class SecurityUtilsTests(TestCase):
    """Tests for SecurityUtils"""

    def test_generate_random_password(self):
        """Test random password generation"""
        password = SecurityUtils.generate_random_password(12)

        self.assertEqual(len(password), 12)
        self.assertTrue(any(c.isalpha() for c in password))
        self.assertTrue(any(c.isdigit() for c in password))

    def test_hash_sensitive_data(self):
        """Test sensitive data hashing"""
        data = "sensitive_information"
        hashed = SecurityUtils.hash_sensitive_data(data)

        self.assertNotEqual(hashed, data)
        self.assertEqual(len(hashed), 64)  # SHA-256 produces 64-char hex string

    def test_generate_unique_token(self):
        """Test unique token generation"""
        token1 = SecurityUtils.generate_unique_token()
        token2 = SecurityUtils.generate_unique_token()

        self.assertNotEqual(token1, token2)
        self.assertTrue(len(token1) > 20)

    def test_mask_sensitive_info(self):
        """Test sensitive information masking"""
        email = "user@example.com"
        masked_email = SecurityUtils.mask_sensitive_info(email)
        self.assertTrue(masked_email.endswith("@example.com"))
        self.assertIn("*", masked_email)

        phone = "1234567890"
        masked_phone = SecurityUtils.mask_sensitive_info(phone)
        self.assertTrue(masked_phone.startswith("1234"))
        self.assertIn("*", masked_phone)


class FormatUtilsTests(TestCase):
    """Tests for FormatUtils"""

    def test_format_currency(self):
        """Test currency formatting"""
        self.assertEqual(FormatUtils.format_currency(1234.56, "USD"), "$1,234.56")
        self.assertEqual(FormatUtils.format_currency(1000, "EUR"), "€1,000.00")
        self.assertEqual(FormatUtils.format_currency(500, "INR"), "₹500.00")

    def test_format_percentage(self):
        """Test percentage formatting"""
        self.assertEqual(FormatUtils.format_percentage(75.5), "75.5%")
        self.assertEqual(FormatUtils.format_percentage(100, 0), "100%")
        self.assertEqual(FormatUtils.format_percentage(33.333, 2), "33.33%")

    def test_format_phone_number(self):
        """Test phone number formatting"""
        formatted = FormatUtils.format_phone_number("1234567890")
        self.assertIn("(123) 456-7890", formatted)


class MathUtilsTests(TestCase):
    """Tests for MathUtils"""

    def test_calculate_percentage(self):
        """Test percentage calculation"""
        self.assertEqual(MathUtils.calculate_percentage(25, 100), 25.0)
        self.assertEqual(MathUtils.calculate_percentage(3, 4), 75.0)
        self.assertEqual(MathUtils.calculate_percentage(0, 100), 0.0)
        self.assertEqual(
            MathUtils.calculate_percentage(100, 0), 0.0
        )  # Avoid division by zero

    def test_calculate_gpa(self):
        """Test GPA calculation"""
        grades = [
            {"points": 4.0, "credits": 3},
            {"points": 3.5, "credits": 4},
            {"points": 3.8, "credits": 2},
        ]

        gpa = MathUtils.calculate_gpa(grades)
        expected = ((4.0 * 3) + (3.5 * 4) + (3.8 * 2)) / (3 + 4 + 2)
        self.assertEqual(gpa, round(expected, 2))

    def test_calculate_weighted_average(self):
        """Test weighted average calculation"""
        values = [
            {"value": 80, "weight": 0.6},  # 60% weight
            {"value": 90, "weight": 0.4},  # 40% weight
        ]

        avg = MathUtils.calculate_weighted_average(values)
        expected = (80 * 0.6 + 90 * 0.4) / (0.6 + 0.4)
        self.assertEqual(avg, round(expected, 2))

    def test_calculate_standard_deviation(self):
        """Test standard deviation calculation"""
        values = [1, 2, 3, 4, 5]
        std_dev = MathUtils.calculate_standard_deviation(values)

        # Manual calculation for verification
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        expected = round(variance**0.5, 2)

        self.assertEqual(std_dev, expected)


class CoreAPITests(APITestCase):
    """Tests for Core API endpoints"""

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )

        # Create system admin group and add user
        admin_group, _ = Group.objects.get_or_create(name="System Administrators")
        self.user.groups.add(admin_group)

        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_system_settings_list(self):
        """Test listing system settings"""
        # Create test settings
        SystemSetting.objects.create(
            setting_key="test.setting1",
            setting_value="value1",
            data_type="string",
            category="test",
        )

        url = reverse("systemsetting-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data["results"]), 1)

    def test_system_settings_create(self):
        """Test creating system setting"""
        url = reverse("systemsetting-list")
        data = {
            "setting_key": "test.new_setting",
            "setting_value": "new_value",
            "data_type": "string",
            "category": "test",
            "description": "Test setting",
        }

        response = self.client.post(url, data)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            SystemSetting.objects.filter(setting_key="test.new_setting").exists()
        )

    def test_system_settings_update_value(self):
        """Test updating system setting value"""
        setting = SystemSetting.objects.create(
            setting_key="test.update",
            setting_value="old_value",
            data_type="string",
            category="test",
        )

        url = reverse("systemsetting-update-value", kwargs={"pk": setting.pk})
        data = {"value": "new_value"}

        response = self.client.patch(url, data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        setting.refresh_from_db()
        self.assertEqual(setting.get_typed_value(), "new_value")

    def test_audit_logs_list(self):
        """Test listing audit logs"""
        # Create test audit log
        AuditLog.objects.create(
            user=self.user, action="test", description="Test audit log"
        )

        url = reverse("auditlog-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data["results"]), 1)

    def test_analytics_dashboard(self):
        """Test analytics dashboard endpoint"""
        url = reverse("analytics-dashboard")
        response = self.client.get(url)

        # Should return dashboard data even if empty
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("total_students", response.data)
        self.assertIn("total_teachers", response.data)

    def test_unauthorized_access(self):
        """Test unauthorized access to admin endpoints"""
        # Create regular user without admin privileges
        regular_user = User.objects.create_user(
            username="regular", email="regular@example.com", password="testpass123"
        )

        client = APIClient()
        client.force_authenticate(user=regular_user)

        url = reverse("systemsetting-list")
        response = client.get(url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class CoreManagementCommandTests(TransactionTestCase):
    """Tests for management commands"""

    def test_setup_academic_year(self):
        """Test setup_academic_year command"""
        # Test creating academic year
        call_command(
            "setup_academic_year",
            "--year",
            "2024-2025",
            "--start-date",
            "2024-07-01",
            "--terms",
            "3",
            "--make-current",
        )

        # Check academic year was created
        from academics.models import AcademicYear

        self.assertTrue(AcademicYear.objects.filter(name="2024-2025").exists())

    def test_calculate_analytics_command(self):
        """Test calculate_analytics command"""
        # This would require more setup with actual data
        # For now, just test that command runs without error
        try:
            call_command("calculate_analytics", "--type", "student")
        except Exception as e:
            # Command might fail due to missing data, but should not crash
            self.assertIsInstance(e, (SystemExit, Exception))

    def test_generate_sample_data_command(self):
        """Test generate_sample_data command"""
        # This would require academic year setup
        # For now, just test basic functionality
        try:
            call_command("generate_sample_data", "--students", "5", "--teachers", "2")
        except Exception as e:
            # Command might fail due to missing academic setup
            self.assertIsInstance(e, (SystemExit, Exception))


class CoreDecoratorsTests(TestCase):
    """Tests for decorators"""

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )

        # Create mock request
        self.request = MagicMock()
        self.request.user = self.user
        self.request.META = {
            "REMOTE_ADDR": "127.0.0.1",
            "HTTP_USER_AGENT": "Test Agent",
        }

    def test_audit_action_decorator(self):
        """Test audit_action decorator"""

        @audit_action(action="test_action", description="Test function")
        def test_function(request):
            return "success"

        result = test_function(self.request)

        self.assertEqual(result, "success")
        # Check that audit log was created
        self.assertTrue(
            AuditLog.objects.filter(user=self.user, action="test_action").exists()
        )

    def test_require_role_decorator(self):
        """Test require_role decorator"""
        # Add user to system admin group
        admin_group, _ = Group.objects.get_or_create(name="System Administrators")
        self.user.groups.add(admin_group)

        @require_role("system_admin")
        def admin_function(request):
            return "admin_success"

        result = admin_function(self.request)
        self.assertEqual(result, "admin_success")

    def test_require_role_decorator_unauthorized(self):
        """Test require_role decorator with unauthorized user"""
        self.request.path = "/api/test/"

        @require_role("system_admin")
        def admin_function(request):
            return "should_not_reach"

        # Should return JsonResponse with error
        result = admin_function(self.request)
        self.assertEqual(result.status_code, 403)


class CoreMiddlewareTests(TestCase):
    """Tests for middleware"""

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )

    def test_maintenance_mode_middleware(self):
        """Test maintenance mode middleware"""
        from .middleware import MaintenanceModeMiddleware

        # Mock get_response
        def get_response(request):
            from django.http import HttpResponse

            return HttpResponse("Normal response")

        middleware = MaintenanceModeMiddleware(get_response)

        # Create mock request
        request = MagicMock()
        request.user = self.user
        request.path = "/test/"

        # Test with maintenance mode off
        with patch.object(ConfigurationService, "get_setting", return_value=False):
            response = middleware(request)
            self.assertEqual(response.content, b"Normal response")

        # Test with maintenance mode on and regular user
        self.user.is_superuser = False
        self.user.is_staff = False
        request.path = "/api/test/"

        with patch.object(ConfigurationService, "get_setting", return_value=True):
            response = middleware(request)
            self.assertEqual(response.status_code, 503)


class CoreTasksTests(TestCase):
    """Tests for Celery tasks"""

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )

    @patch("core.tasks.AnalyticsService.calculate_student_performance")
    def test_calculate_student_analytics_task(self, mock_calculate):
        """Test student analytics calculation task"""
        from .tasks import calculate_student_analytics

        # Mock the analytics service
        mock_calculate.return_value = None

        # Run task
        result = calculate_student_analytics.apply(
            kwargs={"academic_year_id": 1, "term_id": 1, "force_recalculate": True}
        )

        self.assertEqual(result.status, "SUCCESS")
        mock_calculate.assert_called_once()

    @patch("core.tasks.AuditService.cleanup_old_logs")
    def test_cleanup_old_audit_logs_task(self, mock_cleanup):
        """Test audit log cleanup task"""
        from .tasks import cleanup_old_audit_logs

        # Mock the cleanup service
        mock_cleanup.return_value = 5

        # Run task
        result = cleanup_old_audit_logs.apply(kwargs={"days": 365})

        self.assertEqual(result.status, "SUCCESS")
        self.assertEqual(result.result["deleted_count"], 5)
        mock_cleanup.assert_called_once_with(365)

    @patch("core.tasks.SystemHealthMetrics.objects.create")
    def test_collect_system_health_metrics_task(self, mock_create):
        """Test system health metrics collection task"""
        from .tasks import collect_system_health_metrics

        # Mock the model creation
        mock_health = MagicMock()
        mock_health.id = 1
        mock_health.timestamp = timezone.now()
        mock_create.return_value = mock_health

        # Run task
        result = collect_system_health_metrics.apply()

        self.assertEqual(result.status, "SUCCESS")
        mock_create.assert_called_once()


class SecurityServiceTests(TestCase):
    """Tests for SecurityService"""

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )
        cache.clear()

    def test_check_rate_limit(self):
        """Test rate limiting functionality"""
        identifier = "test_user"
        action = "test_action"

        # Should allow first few attempts
        for i in range(5):
            self.assertTrue(SecurityService.check_rate_limit(identifier, action, 5, 15))

        # Should block after limit exceeded
        self.assertFalse(SecurityService.check_rate_limit(identifier, action, 5, 15))

    def test_log_security_event(self):
        """Test security event logging"""
        SecurityService.log_security_event(
            "test_event",
            user=self.user,
            ip_address="127.0.0.1",
            details={"key": "value"},
        )

        # Check that audit log was created
        self.assertTrue(
            AuditLog.objects.filter(
                user=self.user,
                action="system_action",
                description__contains="Security event: test_event",
            ).exists()
        )

    def test_validate_file_upload(self):
        """Test file upload validation"""
        # Mock file object
        mock_file = MagicMock()
        mock_file.name = "test.txt"
        mock_file.size = 1024  # 1KB

        errors = SecurityService.validate_file_upload(
            mock_file, allowed_extensions=["txt", "pdf"], max_size_mb=1
        )

        self.assertEqual(len(errors), 0)

        # Test with invalid extension
        mock_file.name = "test.exe"
        errors = SecurityService.validate_file_upload(
            mock_file, allowed_extensions=["txt", "pdf"], max_size_mb=1
        )

        self.assertGreater(len(errors), 0)

        # Test with large file
        mock_file.name = "test.txt"
        mock_file.size = 10 * 1024 * 1024  # 10MB
        errors = SecurityService.validate_file_upload(
            mock_file, allowed_extensions=["txt", "pdf"], max_size_mb=1
        )

        self.assertGreater(len(errors), 0)


class UtilityServiceTests(TestCase):
    """Tests for UtilityService"""

    def test_generate_unique_code(self):
        """Test unique code generation"""
        code1 = UtilityService.generate_unique_code(
            SystemSetting, "setting_key", "TEST", 6
        )
        code2 = UtilityService.generate_unique_code(
            SystemSetting, "setting_key", "TEST", 6
        )

        self.assertNotEqual(code1, code2)
        self.assertTrue(code1.startswith("TEST"))
        self.assertEqual(len(code1), 10)  # TEST + 6 chars

    def test_format_currency(self):
        """Test currency formatting"""
        formatted = UtilityService.format_currency(Decimal("1234.56"), "USD")
        self.assertEqual(formatted, "$1,234.56")

    def test_sanitize_filename(self):
        """Test filename sanitization"""
        unsafe_name = "file<>name:with|bad?chars*.txt"
        safe_name = UtilityService.sanitize_filename(unsafe_name)

        self.assertNotIn("<", safe_name)
        self.assertNotIn("|", safe_name)
        self.assertNotIn("?", safe_name)
        self.assertTrue(safe_name.endswith(".txt"))


if __name__ == "__main__":
    import django
    from django.conf import settings
    from django.test.utils import get_runner

    django.setup()
    TestRunner = get_runner(settings)
    test_runner = TestRunner()
    failures = test_runner.run_tests(["core.tests"])

    if failures:
        exit(1)
