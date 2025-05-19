from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from ...services import RoleService
from ...models import UserRole, UserRoleAssignment

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
            if User.objects.filter(username=username).exists():
                raise CommandError(f'User "{username}" already exists.')

            if User.objects.filter(email=email).exists():
                raise CommandError(f'Email "{email}" is already in use.')

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


class Command(BaseCommand):
    help = "Clean up expired role assignments and old audit logs"

    def add_arguments(self, parser):
        parser.add_argument(
            "--role-assignments",
            action="store_true",
            help="Clean up expired role assignments",
        )
        parser.add_argument(
            "--audit-logs",
            action="store_true",
            help="Clean up old audit logs",
        )
        parser.add_argument(
            "--sessions",
            action="store_true",
            help="Clean up old user sessions",
        )
        parser.add_argument(
            "--all",
            action="store_true",
            help="Run all cleanup tasks",
        )
        parser.add_argument(
            "--audit-retention-days",
            type=int,
            default=365,
            help="Number of days to retain audit logs (default: 365)",
        )
        parser.add_argument(
            "--session-retention-days",
            type=int,
            default=30,
            help="Number of days to retain old sessions (default: 30)",
        )

    def handle(self, *args, **options):
        run_all = options["all"]
        role_assignments = options["role_assignments"] or run_all
        audit_logs = options["audit_logs"] or run_all
        sessions = options["sessions"] or run_all

        audit_retention_days = options["audit_retention_days"]
        session_retention_days = options["session_retention_days"]

        total_cleaned = 0

        try:
            if role_assignments:
                self.stdout.write("Cleaning up expired role assignments...")
                expired_count = RoleService.expire_role_assignments()
                total_cleaned += expired_count
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  Deactivated {expired_count} expired role assignments."
                    )
                )

            if audit_logs:
                self.stdout.write(
                    f"Cleaning up audit logs older than {audit_retention_days} days..."
                )
                from ...models import UserAuditLog

                deleted_count = UserAuditLog.objects.cleanup_old_logs(
                    audit_retention_days
                )
                total_cleaned += deleted_count
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  Deleted {deleted_count} old audit log entries."
                    )
                )

            if sessions:
                self.stdout.write(
                    f"Cleaning up sessions older than {session_retention_days} days..."
                )
                from ...models import UserSession

                deleted_count = UserSession.objects.cleanup_old_sessions(
                    session_retention_days
                )
                total_cleaned += deleted_count
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  Deleted {deleted_count} old session records."
                    )
                )

            if total_cleaned > 0:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"\nCleanup completed. Total items processed: {total_cleaned}"
                    )
                )
            else:
                self.stdout.write("No items needed cleanup.")

        except Exception as e:
            raise CommandError(f"Error during cleanup: {str(e)}")


class Command(BaseCommand):
    help = "Generate user statistics report"

    def add_arguments(self, parser):
        parser.add_argument(
            "--format",
            choices=["text", "json", "csv"],
            default="text",
            help="Output format (default: text)",
        )
        parser.add_argument(
            "--output",
            help="Output file path (optional)",
        )
        parser.add_argument(
            "--include-roles",
            action="store_true",
            help="Include role statistics",
        )
        parser.add_argument(
            "--include-activity",
            action="store_true",
            help="Include activity statistics",
        )

    def handle(self, *args, **options):
        output_format = options["format"]
        output_file = options["output"]
        include_roles = options["include_roles"]
        include_activity = options["include_activity"]

        try:
            # Get user statistics
            user_stats = User.objects.get_statistics()

            # Get role statistics if requested
            role_stats = None
            if include_roles:
                role_stats = UserRole.objects.get_role_statistics()

            # Get activity statistics if requested
            activity_stats = None
            if include_activity:
                from ...models import UserAuditLog

                activity_stats = UserAuditLog.objects.get_activity_summary()

            # Generate report based on format
            if output_format == "text":
                report = self._generate_text_report(
                    user_stats, role_stats, activity_stats
                )
            elif output_format == "json":
                report = self._generate_json_report(
                    user_stats, role_stats, activity_stats
                )
            elif output_format == "csv":
                report = self._generate_csv_report(
                    user_stats, role_stats, activity_stats
                )

            # Output report
            if output_file:
                with open(output_file, "w") as f:
                    f.write(report)
                self.stdout.write(self.style.SUCCESS(f"Report saved to {output_file}"))
            else:
                self.stdout.write(report)

        except Exception as e:
            raise CommandError(f"Error generating report: {str(e)}")

    def _generate_text_report(self, user_stats, role_stats, activity_stats):
        report = []
        report.append("User Statistics Report")
        report.append("=" * 50)
        report.append(f"Generated on: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("")

        # User statistics
        report.append("User Statistics:")
        report.append(f"  Total Users: {user_stats['total']}")
        report.append(f"  Active Users: {user_stats['active']}")
        report.append(f"  Inactive Users: {user_stats['inactive']}")
        report.append(
            f"  Recent Registrations (30 days): {user_stats['recent_registrations']}"
        )
        report.append(
            f"  Requiring Password Change: {user_stats['requiring_password_change']}"
        )
        report.append(f"  Locked Accounts: {user_stats['locked_accounts']}")
        report.append("")

        # Role statistics
        if role_stats:
            report.append("Role Statistics:")
            for role in role_stats:
                role_type = "System" if role["is_system_role"] else "Custom"
                report.append(
                    f"  {role['name']} ({role_type}): {role['user_count']} users"
                )
            report.append("")

        # Activity statistics
        if activity_stats:
            report.append("Activity Statistics (Last 30 days):")
            for activity in activity_stats:
                action_name = activity["action"].replace("_", " ").title()
                report.append(f"  {action_name}: {activity['count']} times")
            report.append("")

        return "\n".join(report)

    def _generate_json_report(self, user_stats, role_stats, activity_stats):
        import json

        data = {
            "generated_at": timezone.now().isoformat(),
            "user_statistics": user_stats,
        }

        if role_stats:
            data["role_statistics"] = list(role_stats)

        if activity_stats:
            data["activity_statistics"] = list(activity_stats)

        return json.dumps(data, indent=2)

    def _generate_csv_report(self, user_stats, role_stats, activity_stats):
        import csv
        import io

        output = io.StringIO()

        # User statistics
        writer = csv.writer(output)
        writer.writerow(["User Statistics"])
        writer.writerow(["Metric", "Value"])
        for key, value in user_stats.items():
            writer.writerow([key.replace("_", " ").title(), value])
        writer.writerow([])

        # Role statistics
        if role_stats:
            writer.writerow(["Role Statistics"])
            writer.writerow(["Role Name", "Type", "User Count"])
            for role in role_stats:
                role_type = "System" if role["is_system_role"] else "Custom"
                writer.writerow([role["name"], role_type, role["user_count"]])
            writer.writerow([])

        # Activity statistics
        if activity_stats:
            writer.writerow(["Activity Statistics"])
            writer.writerow(["Action", "Count"])
            for activity in activity_stats:
                action_name = activity["action"].replace("_", " ").title()
                writer.writerow([action_name, activity["count"]])

        return output.getvalue()


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
            import csv

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
