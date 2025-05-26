# src/accounts/management/commands/import_users.py

import csv

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q

from ...services import RoleService

User = get_user_model()


class Command(BaseCommand):
    help = "Import users from CSV file"

    def add_arguments(self, parser):
        parser.add_argument("csv_file", help="Path to CSV file")
        parser.add_argument(
            "--default-password",
            default="changeme123",
            help="Default password for imported users",
        )
        parser.add_argument(
            "--default-roles",
            nargs="+",
            default=[],
            help="Default roles to assign to imported users",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Perform a dry run without creating users",
        )
        parser.add_argument(
            "--update-existing",
            action="store_true",
            help="Update existing users instead of skipping",
        )

    def handle(self, *args, **options):
        csv_file = options["csv_file"]
        default_password = options["default_password"]
        default_roles = options["default_roles"]
        dry_run = options["dry_run"]
        update_existing = options["update_existing"]

        try:
            # Ensure default roles exist
            RoleService.create_default_roles()

            created_count = 0
            updated_count = 0
            skipped_count = 0
            error_count = 0

            with open(csv_file, "r", encoding="utf-8") as file:
                reader = csv.DictReader(file)

                required_fields = ["username", "email"]
                if not all(field in reader.fieldnames for field in required_fields):
                    raise CommandError(
                        f'CSV must contain columns: {", ".join(required_fields)}'
                    )

                with transaction.atomic():
                    for row_num, row in enumerate(reader, start=2):
                        try:
                            username = row["username"].strip()
                            email = row["email"].strip()

                            if not username or not email:
                                self.stdout.write(
                                    self.style.WARNING(
                                        f"Row {row_num}: Missing username or email, skipping."
                                    )
                                )
                                skipped_count += 1
                                continue

                            if dry_run:
                                self.stdout.write(
                                    f"Would process: {username} ({email})"
                                )
                                continue

                            # Check if user exists
                            existing_user = User.objects.filter(
                                Q(username=username) | Q(email=email)
                            ).first()

                            if existing_user:
                                if update_existing:
                                    # Update existing user
                                    existing_user.first_name = row.get(
                                        "first_name", existing_user.first_name
                                    )
                                    existing_user.last_name = row.get(
                                        "last_name", existing_user.last_name
                                    )
                                    existing_user.phone_number = row.get(
                                        "phone_number", existing_user.phone_number
                                    )
                                    existing_user.save()
                                    updated_count += 1
                                    self.stdout.write(f"Updated: {username}")
                                else:
                                    skipped_count += 1
                                    self.stdout.write(f"Skipped existing: {username}")
                                continue

                            # Create new user
                            user_data = {
                                "username": username,
                                "email": email,
                                "first_name": row.get("first_name", ""),
                                "last_name": row.get("last_name", ""),
                                "phone_number": row.get("phone_number", ""),
                            }

                            user = User.objects.create_user(
                                **user_data, password=default_password
                            )
                            user.requires_password_change = True
                            user.save()

                            # Assign roles
                            user_roles = (
                                row.get("roles", "").split(",")
                                if row.get("roles")
                                else default_roles
                            )
                            for role_name in user_roles:
                                role_name = role_name.strip()
                                if role_name:
                                    try:
                                        RoleService.assign_role_to_user(user, role_name)
                                    except ValueError:
                                        self.stdout.write(
                                            self.style.WARNING(
                                                f'Invalid role "{role_name}" for user {username}'
                                            )
                                        )

                            created_count += 1
                            self.stdout.write(f"Created: {username}")

                        except Exception as e:
                            error_count += 1
                            self.stdout.write(
                                self.style.ERROR(
                                    f'Row {row_num}: Error processing {row.get("username", "unknown")}: {str(e)}'
                                )
                            )

            # Summary
            if dry_run:
                self.stdout.write(self.style.SUCCESS("Dry run completed."))
            else:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Import completed: {created_count} created, {updated_count} updated, "
                        f"{skipped_count} skipped, {error_count} errors."
                    )
                )

        except FileNotFoundError:
            raise CommandError(f"CSV file not found: {csv_file}")
        except Exception as e:
            raise CommandError(f"Error importing users: {str(e)}")
