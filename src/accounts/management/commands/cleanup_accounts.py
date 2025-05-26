from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from ...models import UserAuditLog, UserSession
from ...services import RoleService


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
