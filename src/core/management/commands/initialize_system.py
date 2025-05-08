# management/commands/initialize_system.py
from django.core.management.base import BaseCommand
from src.core.services import SystemSettingService
from django.contrib.auth.models import Group, Permission
from django.contrib.auth import get_user_model
from django.db import transaction

User = get_user_model()


class Command(BaseCommand):
    help = "Initialize system with default settings and basic roles"

    def handle(self, *args, **kwargs):
        self.stdout.write("Initializing system settings...")

        # Initialize system settings
        SystemSettingService.initialize_default_settings()
        self.stdout.write(self.style.SUCCESS("✓ System settings initialized"))

        # Create default groups/roles if they don't exist
        self.create_default_groups()
        self.stdout.write(self.style.SUCCESS("✓ Default roles created"))

        self.stdout.write(
            self.style.SUCCESS("System initialization completed successfully!")
        )

    @transaction.atomic
    def create_default_groups(self):
        # Default roles
        default_groups = ["Admin", "Teacher", "Student", "Parent", "Staff"]

        for group_name in default_groups:
            group, created = Group.objects.get_or_create(name=group_name)

            if created:
                self.stdout.write(f"Created group: {group_name}")

                # Assign appropriate permissions to each group
                if group_name == "Admin":
                    # Admin gets all permissions
                    permissions = Permission.objects.all()
                    group.permissions.set(permissions)

                elif group_name == "Teacher":
                    # Assign teacher-specific permissions
                    teacher_permissions = [
                        "view_student",
                        "view_attendance",
                        "add_attendance",
                        "change_attendance",
                        "view_assignment",
                        "add_assignment",
                        "change_assignment",
                        "delete_assignment",
                        "view_examschedule",
                        "view_examresult",
                        "add_examresult",
                        "change_examresult",
                    ]
                    permissions = Permission.objects.filter(
                        codename__in=teacher_permissions
                    )
                    group.permissions.set(permissions)

                elif group_name == "Student":
                    # Assign student-specific permissions
                    student_permissions = [
                        "view_assignment",
                        "view_examschedule",
                        "view_examresult",
                    ]
                    permissions = Permission.objects.filter(
                        codename__in=student_permissions
                    )
                    group.permissions.set(permissions)

                elif group_name == "Parent":
                    # Assign parent-specific permissions
                    parent_permissions = [
                        "view_student",
                        "view_attendance",
                        "view_examresult",
                    ]
                    permissions = Permission.objects.filter(
                        codename__in=parent_permissions
                    )
                    group.permissions.set(permissions)
