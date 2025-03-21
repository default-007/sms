from django.db import transaction
from ..models import UserRole, UserRoleAssignment
from ..constants import SYSTEM_ROLES, PERMISSION_SCOPES


class RoleService:
    """
    Service for managing user roles and permissions.
    """

    @staticmethod
    @transaction.atomic
    def create_default_roles():
        """Create default system roles if they don't exist."""
        # Admin role with all permissions
        admin_permissions = {}
        for resource, actions in PERMISSION_SCOPES.items():
            admin_permissions[resource] = actions

        admin_role, created = UserRole.objects.get_or_create(
            name="Admin",
            defaults={
                "description": "Administrator with full access to all system features",
                "permissions": admin_permissions,
            },
        )

        # Teacher role with limited permissions
        teacher_permissions = {
            "students": ["view"],
            "attendance": ["view", "add", "change"],
            "exams": ["view", "add", "change"],
            "grades": ["view", "add", "change"],
            "courses": ["view"],
            "classes": ["view"],
            "communications": ["view", "add"],
            "reports": ["view", "generate"],
        }

        teacher_role, created = UserRole.objects.get_or_create(
            name="Teacher",
            defaults={
                "description": "Teacher with access to student data, attendance, grades, etc.",
                "permissions": teacher_permissions,
            },
        )

        # Parent role with limited permissions
        parent_permissions = {
            "students": ["view"],
            "attendance": ["view"],
            "exams": ["view"],
            "grades": ["view"],
            "courses": ["view"],
            "fees": ["view"],
            "communications": ["view", "add"],
            "reports": ["view"],
        }

        parent_role, created = UserRole.objects.get_or_create(
            name="Parent",
            defaults={
                "description": "Parent with access to their children's data",
                "permissions": parent_permissions,
            },
        )

        # Staff role with administrative permissions
        staff_permissions = {
            "students": ["view", "add", "change"],
            "teachers": ["view", "add", "change"],
            "attendance": ["view", "add", "change"],
            "courses": ["view", "add", "change"],
            "classes": ["view", "add", "change"],
            "fees": ["view", "add", "change"],
            "library": ["view", "add", "change"],
            "transport": ["view", "add", "change"],
            "communications": ["view", "add"],
            "reports": ["view", "generate"],
        }

        staff_role, created = UserRole.objects.get_or_create(
            name="Staff",
            defaults={
                "description": "Administrative staff with access to most system features",
                "permissions": staff_permissions,
            },
        )

        # Student role with limited permissions
        student_permissions = {
            "attendance": ["view"],
            "exams": ["view"],
            "grades": ["view"],
            "courses": ["view"],
            "classes": ["view"],
            "fees": ["view"],
            "library": ["view"],
            "communications": ["view", "add"],
        }

        student_role, created = UserRole.objects.get_or_create(
            name="Student",
            defaults={
                "description": "Student with access to their own data",
                "permissions": student_permissions,
            },
        )

        return {
            "Admin": admin_role,
            "Teacher": teacher_role,
            "Parent": parent_role,
            "Staff": staff_role,
            "Student": student_role,
        }

    @staticmethod
    def assign_role_to_user(user, role_name, assigned_by=None):
        """
        Assign a role to a user.

        Args:
            user: User instance
            role_name: Name of the role to assign
            assigned_by: User who is assigning the role (optional)

        Returns:
            UserRoleAssignment: The created assignment
        """
        try:
            role = UserRole.objects.get(name=role_name)
            assignment, created = UserRoleAssignment.objects.get_or_create(
                user=user, role=role, defaults={"assigned_by": assigned_by}
            )
            return assignment
        except UserRole.DoesNotExist:
            raise ValueError(f"Role '{role_name}' does not exist")

    @staticmethod
    def remove_role_from_user(user, role_name):
        """
        Remove a role from a user.

        Args:
            user: User instance
            role_name: Name of the role to remove

        Returns:
            bool: True if the role was removed, False otherwise
        """
        try:
            role = UserRole.objects.get(name=role_name)
            deleted, _ = UserRoleAssignment.objects.filter(
                user=user, role=role
            ).delete()
            return deleted > 0
        except UserRole.DoesNotExist:
            return False

    @staticmethod
    def get_user_permissions(user):
        """
        Get all permissions for a user based on their roles.

        Args:
            user: User instance

        Returns:
            dict: Combined permissions from all user roles
        """
        combined_permissions = {}

        # Get all user roles
        role_assignments = UserRoleAssignment.objects.filter(user=user).select_related(
            "role"
        )

        # Combine permissions from all roles
        for assignment in role_assignments:
            role_permissions = assignment.role.permissions

            for resource, actions in role_permissions.items():
                if resource not in combined_permissions:
                    combined_permissions[resource] = []

                # Add new actions without duplicates
                for action in actions:
                    if action not in combined_permissions[resource]:
                        combined_permissions[resource].append(action)

        return combined_permissions

    @staticmethod
    def check_permission(user, resource, action):
        """
        Check if a user has a specific permission.

        Args:
            user: User instance
            resource: Resource name (e.g., 'users', 'students')
            action: Action name (e.g., 'view', 'add', 'change', 'delete')

        Returns:
            bool: True if the user has the permission, False otherwise
        """
        # Superusers and admins have all permissions
        if user.is_superuser or user.has_role("Admin"):
            return True

        # Get user permissions
        permissions = RoleService.get_user_permissions(user)

        # Check if the user has the specific permission
        return resource in permissions and action in permissions[resource]
