import unittest
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase, TransactionTestCase

from ..constants import DEFAULT_ROLES
from ..models import UserAuditLog, UserProfile, UserRole, UserRoleAssignment
from ..services import AuthenticationService, RoleService

User = get_user_model()


class UserModelTest(TestCase):
    """Test cases for the User model."""

    def setUp(self):
        self.user_data = {
            "username": "testuser",
            "email": "test@example.com",
            "first_name": "Test",
            "last_name": "User",
            "phone_number": "+1234567890",
        }

    def test_user_creation(self):
        """Test user creation with valid data."""
        user = User.objects.create_user(**self.user_data, password="testpass123")
        self.assertEqual(user.username, "testuser")
        self.assertEqual(user.email, "test@example.com")
        self.assertTrue(user.check_password("testpass123"))
        self.assertTrue(user.is_active)
        self.assertFalse(user.is_staff)

    def test_superuser_creation(self):
        """Test superuser creation."""
        user = User.objects.create_superuser(
            username="admin", email="admin@example.com", password="adminpass123"
        )
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.is_active)

    def test_user_full_name(self):
        """Test get_full_name method."""
        user = User(**self.user_data)
        self.assertEqual(user.get_full_name(), "Test User")

        user.first_name = ""
        user.last_name = ""
        self.assertEqual(user.get_full_name(), "testuser")

    def test_user_initials(self):
        """Test get_initials method."""
        user = User(**self.user_data)
        self.assertEqual(user.get_initials(), "TU")

        user.first_name = ""
        self.assertEqual(user.get_initials(), "T")

    def test_user_age_calculation(self):
        """Test age calculation."""
        from datetime import date

        user = User(**self.user_data)
        user.date_of_birth = date(1990, 1, 1)

        age = user.get_age()
        self.assertIsInstance(age, int)
        self.assertGreater(age, 0)

    def test_phone_number_validation(self):
        """Test phone number validation."""
        user = User(**self.user_data)
        user.full_clean()  # Should not raise

        user.phone_number = "invalid"
        with self.assertRaises(ValidationError):
            user.full_clean()

    def test_email_uniqueness(self):
        """Test email uniqueness constraint."""
        User.objects.create_user(**self.user_data, password="pass123")

        with self.assertRaises(IntegrityError):
            User.objects.create_user(
                username="testuser2",
                email="test@example.com",  # Duplicate email
                password="pass123",
            )

    def test_username_uniqueness(self):
        """Test username uniqueness constraint."""
        User.objects.create_user(**self.user_data, password="pass123")

        with self.assertRaises(IntegrityError):
            User.objects.create_user(
                username="testuser",  # Duplicate username
                email="test2@example.com",
                password="pass123",
            )

    def test_failed_login_tracking(self):
        """Test failed login attempt tracking."""
        user = User.objects.create_user(**self.user_data, password="pass123")

        # Test initial state
        self.assertEqual(user.failed_login_attempts, 0)
        self.assertFalse(user.is_account_locked())

        # Increment failed attempts
        for i in range(5):
            user.increment_failed_login_attempts()

        self.assertEqual(user.failed_login_attempts, 5)
        self.assertTrue(user.is_account_locked())

        # Reset attempts
        user.reset_failed_login_attempts()
        self.assertEqual(user.failed_login_attempts, 0)
        self.assertFalse(user.is_account_locked())


class UserRoleModelTest(TestCase):
    """Test cases for the UserRole model."""

    def setUp(self):
        self.role_data = {
            "name": "Test Role",
            "description": "A test role",
            "permissions": {"users": ["view", "add"], "courses": ["view"]},
        }

    def test_role_creation(self):
        """Test role creation."""
        role = UserRole.objects.create(**self.role_data)
        self.assertEqual(role.name, "Test Role")
        self.assertEqual(role.description, "A test role")
        self.assertEqual(role.permissions, self.role_data["permissions"])

    def test_role_permission_count(self):
        """Test permission count calculation."""
        role = UserRole.objects.create(**self.role_data)
        self.assertEqual(role.get_permission_count(), 3)  # 2 + 1

    def test_role_has_permission(self):
        """Test permission checking."""
        role = UserRole.objects.create(**self.role_data)
        self.assertTrue(role.has_permission("users", "view"))
        self.assertTrue(role.has_permission("users", "add"))
        self.assertFalse(role.has_permission("users", "delete"))
        self.assertFalse(role.has_permission("nonexistent", "view"))

    def test_role_name_uniqueness(self):
        """Test role name uniqueness."""
        UserRole.objects.create(**self.role_data)

        with self.assertRaises(IntegrityError):
            UserRole.objects.create(name="Test Role")  # Duplicate name


class UserRoleAssignmentTest(TestCase):
    """Test cases for UserRoleAssignment model."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="pass123"
        )
        self.role = UserRole.objects.create(
            name="Test Role", permissions={"users": ["view"]}
        )

    def test_role_assignment_creation(self):
        """Test role assignment creation."""
        assignment = UserRoleAssignment.objects.create(user=self.user, role=self.role)
        self.assertEqual(assignment.user, self.user)
        self.assertEqual(assignment.role, self.role)
        self.assertTrue(assignment.is_active)

    def test_unique_assignment_constraint(self):
        """Test unique constraint on user-role combination."""
        UserRoleAssignment.objects.create(user=self.user, role=self.role)

        with self.assertRaises(IntegrityError):
            UserRoleAssignment.objects.create(user=self.user, role=self.role)

    def test_assignment_expiry(self):
        """Test assignment expiry checking."""
        from datetime import timedelta

        from django.utils import timezone

        # Non-expiring assignment
        assignment = UserRoleAssignment.objects.create(user=self.user, role=self.role)
        self.assertFalse(assignment.is_expired())

        # Expired assignment
        assignment.expires_at = timezone.now() - timedelta(days=1)
        assignment.save()
        self.assertTrue(assignment.is_expired())

        # Future expiry
        assignment.expires_at = timezone.now() + timedelta(days=1)
        assignment.save()
        self.assertFalse(assignment.is_expired())


class RoleServiceTest(TestCase):
    """Test cases for RoleService."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="pass123"
        )
        self.admin_user = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="pass123",
            is_superuser=True,
        )

    def test_create_default_roles(self):
        """Test creation of default roles."""
        created_roles = RoleService.create_default_roles()

        self.assertEqual(len(created_roles), len(DEFAULT_ROLES))
        for role_data in DEFAULT_ROLES:
            self.assertIn(role_data["name"], created_roles)
            role, created = created_roles[role_data["name"]]
            self.assertTrue(created)
            self.assertEqual(role.name, role_data["name"])

    def test_assign_role_to_user(self):
        """Test role assignment to user."""
        RoleService.create_default_roles()

        assignment, created = RoleService.assign_role_to_user(
            self.user, "Student", assigned_by=self.admin_user
        )

        self.assertTrue(created)
        self.assertEqual(assignment.user, self.user)
        self.assertEqual(assignment.role.name, "Student")
        self.assertEqual(assignment.assigned_by, self.admin_user)

    def test_assign_nonexistent_role(self):
        """Test assigning non-existent role raises error."""
        with self.assertRaises(ValueError):
            RoleService.assign_role_to_user(self.user, "NonExistentRole")

    def test_remove_role_from_user(self):
        """Test role removal from user."""
        RoleService.create_default_roles()
        RoleService.assign_role_to_user(self.user, "Student")

        removed = RoleService.remove_role_from_user(self.user, "Student")
        self.assertTrue(removed)

        # Try removing again
        removed = RoleService.remove_role_from_user(self.user, "Student")
        self.assertFalse(removed)

    def test_get_user_permissions(self):
        """Test getting user permissions."""
        RoleService.create_default_roles()
        RoleService.assign_role_to_user(self.user, "Student")

        permissions = RoleService.get_user_permissions(self.user)
        self.assertIsInstance(permissions, dict)

        # Student should have some permissions
        self.assertIn("courses", permissions)

    def test_check_permission(self):
        """Test permission checking."""
        RoleService.create_default_roles()

        # Superuser has all permissions
        self.assertTrue(
            RoleService.check_permission(self.admin_user, "users", "delete")
        )

        # Regular user without role has no permissions
        self.assertFalse(RoleService.check_permission(self.user, "users", "delete"))

        # Assign role and check
        RoleService.assign_role_to_user(self.user, "Student")
        self.assertTrue(RoleService.check_permission(self.user, "courses", "view"))
        self.assertFalse(RoleService.check_permission(self.user, "users", "delete"))

    @patch("django.core.cache.cache")
    def test_permissions_caching(self, mock_cache):
        """Test that permissions are cached."""
        mock_cache.get.return_value = None
        mock_cache.set = MagicMock()

        RoleService.create_default_roles()
        RoleService.assign_role_to_user(self.user, "Student")

        # First call should set cache
        permissions = RoleService.get_user_permissions(self.user)
        mock_cache.set.assert_called()

        # Subsequent calls should use cache
        mock_cache.get.return_value = permissions
        RoleService.get_user_permissions(self.user)
        mock_cache.get.assert_called()

    def test_bulk_assign_roles(self):
        """Test bulk role assignment."""
        users = [
            User.objects.create_user(f"user{i}", f"user{i}@example.com", "pass123")
            for i in range(3)
        ]

        RoleService.create_default_roles()

        assignments_created = RoleService.bulk_assign_roles(
            users, ["Student", "Parent"], assigned_by=self.admin_user
        )

        self.assertEqual(assignments_created, 6)  # 3 users * 2 roles

        for user in users:
            self.assertTrue(user.has_role("Student"))
            self.assertTrue(user.has_role("Parent"))


class AuthenticationServiceTest(TestCase):
    """Test cases for AuthenticationService."""

    def setUp(self):
        self.user_data = {
            "username": "testuser",
            "email": "test@example.com",
            "first_name": "Test",
            "last_name": "User",
        }

    def test_authenticate_user(self):
        """Test user authentication."""
        user = User.objects.create_user(**self.user_data, password="testpass123")

        # Valid credentials
        authenticated_user = AuthenticationService.authenticate_user(
            "testuser", "testpass123"
        )
        self.assertEqual(authenticated_user, user)

        # Invalid password
        authenticated_user = AuthenticationService.authenticate_user(
            "testuser", "wrongpass"
        )
        self.assertIsNone(authenticated_user)

        # Non-existent user
        authenticated_user = AuthenticationService.authenticate_user(
            "nonexistent", "pass"
        )
        self.assertIsNone(authenticated_user)

    def test_register_user(self):
        """Test user registration."""
        user_data = self.user_data.copy()
        user_data["password"] = "testpass123"

        user = AuthenticationService.register_user(user_data, role_names=["Student"])

        self.assertEqual(user.username, "testuser")
        self.assertEqual(user.email, "test@example.com")
        self.assertTrue(user.check_password("testpass123"))
        self.assertTrue(user.has_role("Student"))

    def test_generate_tokens(self):
        """Test JWT token generation."""
        user = User.objects.create_user(**self.user_data, password="testpass123")

        tokens = AuthenticationService.generate_tokens_for_user(user)

        self.assertIn("access", tokens)
        self.assertIn("refresh", tokens)
        self.assertIsInstance(tokens["access"], str)
        self.assertIsInstance(tokens["refresh"], str)


class UserAuditLogTest(TestCase):
    """Test cases for UserAuditLog model."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="pass123"
        )
        self.admin = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="pass123",
            is_superuser=True,
        )

    def test_audit_log_creation(self):
        """Test creating audit log entries."""
        log = UserAuditLog.objects.create(
            user=self.user,
            action="login",
            description="User logged in",
            performed_by=self.user,
            ip_address="127.0.0.1",
        )

        self.assertEqual(log.user, self.user)
        self.assertEqual(log.action, "login")
        self.assertEqual(log.performed_by, self.user)
        self.assertEqual(log.ip_address, "127.0.0.1")

    def test_audit_log_with_extra_data(self):
        """Test audit log with extra data."""
        extra_data = {"role_name": "Student", "expires_at": None}

        log = UserAuditLog.objects.create(
            user=self.user,
            action="role_assign",
            description="Role assigned",
            performed_by=self.admin,
            extra_data=extra_data,
        )

        self.assertEqual(log.extra_data, extra_data)


# Integration tests
class UserRoleIntegrationTest(TransactionTestCase):
    """Integration tests for user role functionality."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="pass123"
        )

    def test_role_assignment_with_audit(self):
        """Test complete role assignment flow with audit logging."""
        RoleService.create_default_roles()

        # Assign role
        assignment, created = RoleService.assign_role_to_user(self.user, "Student")
        self.assertTrue(created)

        # Check user has role
        self.assertTrue(self.user.has_role("Student"))

        # Check permissions
        self.assertTrue(self.user.has_permission("courses", "view"))

        # Check audit log
        audit_logs = UserAuditLog.objects.filter(user=self.user, action="role_assign")
        self.assertEqual(audit_logs.count(), 1)

        # Remove role
        removed = RoleService.remove_role_from_user(self.user, "Student")
        self.assertTrue(removed)

        # Check role removed
        self.assertFalse(self.user.has_role("Student"))

        # Check audit log for removal
        audit_logs = UserAuditLog.objects.filter(user=self.user, action="role_remove")
        self.assertEqual(audit_logs.count(), 1)

    def test_expired_role_cleanup(self):
        """Test cleanup of expired role assignments."""
        from datetime import timedelta

        from django.utils import timezone

        RoleService.create_default_roles()

        # Create expired assignment
        assignment = UserRoleAssignment.objects.create(
            user=self.user,
            role=UserRole.objects.get(name="Student"),
            expires_at=timezone.now() - timedelta(days=1),
        )

        # Run cleanup
        expired_count = RoleService.expire_role_assignments()
        self.assertEqual(expired_count, 1)

        # Check assignment is deactivated
        assignment.refresh_from_db()
        self.assertFalse(assignment.is_active)
