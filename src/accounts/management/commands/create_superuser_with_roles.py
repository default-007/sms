from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from ...services import RoleService

User = get_user_model()


class Command(BaseCommand):
    help = "Create a superuser with specific roles"

    def add_arguments(self, parser):
        parser.add_argument(
            "--username", required=True, help="Username for the superuser"
        )
        parser.add_argument("--email", required=True, help="Email for the superuser")
        parser.add_argument(
            "--password",
            help="Password for the superuser (will prompt if not provided)",
        )
        parser.add_argument("--first-name", help="First name")
        parser.add_argument("--last-name", help="Last name")
        parser.add_argument(
            "--roles", nargs="+", default=["Admin"], help="Roles to assign"
        )

    def handle(self, *args, **options):
        username = options["username"]
        email = options["email"]
        password = options["password"]
        first_name = options.get("first_name", "")
        last_name = options.get("last_name", "")
        roles = options["roles"]

        try:
            # Check if user already exists
            if User.objects.filter(Q(username=username) | Q(email=email)).exists():
                raise CommandError(
                    f'User with username "{username}" or email "{email}" already exists.'
                )

            # Prompt for password if not provided
            if not password:
                import getpass

                password = getpass.getpass("Password: ")
                password_confirm = getpass.getpass("Password (again): ")

                if password != password_confirm:
                    raise CommandError("Passwords do not match.")

            # Create superuser
            with transaction.atomic():
                user = User.objects.create_superuser(
                    username=username,
                    email=email,
                    password=password,
                    first_name=first_name,
                    last_name=last_name,
                )

                # Ensure default roles exist
                RoleService.create_default_roles()

                # Assign roles
                for role_name in roles:
                    try:
                        RoleService.assign_role_to_user(user, role_name)
                        self.stdout.write(f"Assigned role: {role_name}")
                    except ValueError as e:
                        self.stdout.write(
                            self.style.WARNING(
                                f'Could not assign role "{role_name}": {str(e)}'
                            )
                        )

            self.stdout.write(
                self.style.SUCCESS(
                    f'Successfully created superuser "{username}" with {len(roles)} role(s).'
                )
            )

        except Exception as e:
            raise CommandError(f"Error creating superuser: {str(e)}")
