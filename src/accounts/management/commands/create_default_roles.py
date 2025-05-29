from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from ...models import UserRole, UserRoleAssignment
from ...services import RoleService

User = get_user_model()


class Command(BaseCommand):
    help = "Create default roles for the school management system"

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Force recreation of existing roles",
        )
        parser.add_argument(
            "--verbose",
            action="store_true",
            help="Verbose output",
        )

    def handle(self, *args, **options):
        force = options["force"]
        verbose = options["verbose"]

        try:
            with transaction.atomic():
                if force:
                    # Delete existing system roles if force flag is used
                    UserRole.objects.filter(is_system_role=True).delete()
                    if verbose:
                        self.stdout.write(
                            self.style.WARNING("Deleted existing system roles.")
                        )

                # Create default roles
                created_roles = RoleService.create_default_roles()

                # Summary
                total_created = sum(
                    1 for role, created in created_roles.values() if created
                )
                total_existing = len(created_roles) - total_created

                self.stdout.write(
                    self.style.SUCCESS(
                        f"Successfully processed {len(created_roles)} roles:"
                    )
                )
                self.stdout.write(f"  - Created: {total_created}")
                self.stdout.write(f"  - Already existed: {total_existing}")

                if verbose:
                    self.stdout.write("\nRole details:")
                    for role_name, (role, created) in created_roles.items():
                        status = "CREATED" if created else "EXISTS"
                        permission_count = role.get_permission_count()
                        self.stdout.write(
                            f"  - {role_name}: {status} ({permission_count} permissions)"
                        )

        except Exception as e:
            raise CommandError(f"Error creating default roles: {str(e)}")
