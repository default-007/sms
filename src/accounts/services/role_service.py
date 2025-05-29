import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.mail import send_mail
from django.db import transaction
from django.template.loader import render_to_string
from django.utils import timezone

from ..constants import DEFAULT_ROLES, PERMISSION_SCOPES
from ..models import UserAuditLog, UserRole, UserRoleAssignment

logger = logging.getLogger(__name__)
User = get_user_model()


class RoleService:
    """Enhanced service for managing user roles and permissions."""

    @staticmethod
    @transaction.atomic
    def create_default_roles():
        """Create default system roles if they don't exist."""
        created_roles = {}

        for role_data in DEFAULT_ROLES:
            role, created = UserRole.objects.get_or_create(
                name=role_data["name"],
                defaults={
                    "description": role_data["description"],
                    "permissions": role_data["permissions"],
                    "is_system_role": True,
                },
            )
            created_roles[role_data["name"]] = (role, created)

            if created:
                logger.info(f"Created default role: {role.name}")

        return created_roles

    @staticmethod
    @transaction.atomic
    def assign_role_to_user(
        user, role_name, assigned_by=None, expires_at=None, notes=""
    ):
        """Assign a role to a user with enhanced options."""
        try:
            role = UserRole.objects.get(name=role_name)
            assignment, created = UserRoleAssignment.objects.get_or_create(
                user=user,
                role=role,
                defaults={
                    "assigned_by": assigned_by,
                    "expires_at": expires_at,
                    "notes": notes,
                },
            )

            if created:
                # Create audit log
                UserAuditLog.objects.create(
                    user=user,
                    action="role_assign",
                    description=f"Role '{role_name}' assigned to user",
                    performed_by=assigned_by,
                    extra_data={"role_name": role_name},
                )

                # Clear user cache
                cache.delete(f"user_permissions_{user.pk}")
                cache.delete(f"user_roles_{user.pk}")

                # Send notification if enabled
                if (
                    hasattr(settings, "SEND_ROLE_NOTIFICATIONS")
                    and settings.SEND_ROLE_NOTIFICATIONS
                ):
                    RoleService._send_role_notification(user, role, "assigned")

                logger.info(f"Role '{role_name}' assigned to user '{user.username}'")

            return assignment, created
        except UserRole.DoesNotExist:
            raise ValueError(f"Role '{role_name}' does not exist")

    @staticmethod
    @transaction.atomic
    def remove_role_from_user(user, role_name, removed_by=None):
        """Remove a role from a user."""
        try:
            role = UserRole.objects.get(name=role_name)
            deleted, _ = UserRoleAssignment.objects.filter(
                user=user, role=role
            ).delete()

            if deleted > 0:
                # Create audit log
                UserAuditLog.objects.create(
                    user=user,
                    action="role_remove",
                    description=f"Role '{role_name}' removed from user",
                    performed_by=removed_by,
                    extra_data={"role_name": role_name},
                )

                # Clear user cache
                cache.delete(f"user_permissions_{user.pk}")
                cache.delete(f"user_roles_{user.pk}")

                # Send notification if enabled
                if (
                    hasattr(settings, "SEND_ROLE_NOTIFICATIONS")
                    and settings.SEND_ROLE_NOTIFICATIONS
                ):
                    RoleService._send_role_notification(user, role, "removed")

                logger.info(f"Role '{role_name}' removed from user '{user.username}'")

            return deleted > 0
        except UserRole.DoesNotExist:
            return False

    @staticmethod
    def get_user_permissions(user):
        """Get all permissions for a user based on their roles with caching."""
        cache_key = f"user_permissions_{user.pk}"
        combined_permissions = cache.get(cache_key)

        if combined_permissions is None:
            combined_permissions = {}

            # Get all active, non-expired role assignments
            role_assignments = UserRoleAssignment.objects.filter(
                user=user, is_active=True
            ).select_related("role")

            # Filter out expired assignments
            active_assignments = []
            for assignment in role_assignments:
                if not assignment.is_expired():
                    active_assignments.append(assignment)
                else:
                    # Deactivate expired assignments
                    assignment.is_active = False
                    assignment.save()

            # Combine permissions from all active roles
            for assignment in active_assignments:
                role_permissions = assignment.role.permissions

                for resource, actions in role_permissions.items():
                    if resource not in combined_permissions:
                        combined_permissions[resource] = set()

                    # Add actions to the set (avoids duplicates)
                    if isinstance(actions, list):
                        combined_permissions[resource].update(actions)

            # Convert sets back to lists for JSON serialization
            for resource in combined_permissions:
                combined_permissions[resource] = list(combined_permissions[resource])

            # Cache for 1 hour
            cache.set(cache_key, combined_permissions, 3600)

        return combined_permissions

    @staticmethod
    def check_permission(user, resource, action):
        """Check if a user has a specific permission with optimization."""
        # Superusers have all permissions
        if user.is_superuser:
            return True

        # Admin role has all permissions
        if user.has_role("Admin"):
            return True

        # Check specific permission
        permissions = RoleService.get_user_permissions(user)
        return resource in permissions and action in permissions[resource]

    @staticmethod
    def get_users_with_role(role_name):
        """Get all users assigned to a specific role."""
        try:
            role = UserRole.objects.get(name=role_name)
            return User.objects.filter(
                role_assignments__role=role,
                role_assignments__is_active=True,
                is_active=True,
            ).distinct()
        except UserRole.DoesNotExist:
            return User.objects.none()

    @staticmethod
    def get_role_statistics():
        """Get statistics about role assignments."""
        stats = {}

        for role in UserRole.objects.all():
            active_assignments = UserRoleAssignment.objects.filter(
                role=role, is_active=True
            ).count()

            stats[role.name] = {
                "total_assignments": active_assignments,
                "permission_count": role.get_permission_count(),
                "is_system_role": role.is_system_role,
            }

        return stats

    @staticmethod
    def expire_role_assignments():
        """Batch job to deactivate expired role assignments."""
        expired_count = UserRoleAssignment.objects.filter(
            expires_at__lt=timezone.now(), is_active=True
        ).update(is_active=False)

        if expired_count > 0:
            logger.info(f"Deactivated {expired_count} expired role assignments")

            # Clear cache for affected users
            expired_assignments = UserRoleAssignment.objects.filter(
                expires_at__lt=timezone.now(), is_active=False
            ).select_related("user")

            for assignment in expired_assignments:
                cache.delete(f"user_permissions_{assignment.user.pk}")
                cache.delete(f"user_roles_{assignment.user.pk}")

        return expired_count

    @staticmethod
    def _send_role_notification(user, role, action):
        """Send email notification about role changes."""
        try:
            subject = f"Role {action.title()}: {role.name}"
            template = "accounts/emails/role_notification.html"

            context = {
                "user": user,
                "role": role,
                "action": action,
                "site_name": getattr(settings, "SITE_NAME", "School Management System"),
            }

            html_message = render_to_string(template, context)

            send_mail(
                subject=subject,
                message="",  # Plain text version can be added if needed
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                html_message=html_message,
                fail_silently=True,
            )
        except Exception as e:
            logger.error(f"Failed to send role notification: {e}")

    @staticmethod
    def validate_permissions(permissions):
        """Validate permission structure against available scopes."""
        if not isinstance(permissions, dict):
            return False, "Permissions must be a dictionary"

        for resource, actions in permissions.items():
            if resource not in PERMISSION_SCOPES:
                return False, f"Invalid resource: {resource}"

            if not isinstance(actions, list):
                return False, f"Actions for resource '{resource}' must be a list"

            available_actions = list(PERMISSION_SCOPES[resource].keys())
            for action in actions:
                if action not in available_actions:
                    return False, f"Invalid action '{action}' for resource '{resource}'"

        return True, "Valid"

    @staticmethod
    def bulk_assign_roles(users, role_names, assigned_by=None):
        """Bulk assign multiple roles to multiple users."""
        assignments_created = 0

        with transaction.atomic():
            roles = UserRole.objects.filter(name__in=role_names)

            for user in users:
                for role in roles:
                    _, created = UserRoleAssignment.objects.get_or_create(
                        user=user, role=role, defaults={"assigned_by": assigned_by}
                    )
                    if created:
                        assignments_created += 1
                        # Clear user cache
                        cache.delete(f"user_permissions_{user.pk}")
                        cache.delete(f"user_roles_{user.pk}")

        return assignments_created
