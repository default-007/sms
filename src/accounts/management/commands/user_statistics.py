# src/accounts/management/commands/user_statistics.py

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.utils import timezone
from ...models import UserRole, UserAuditLog
import json
import csv
import io

User = get_user_model()


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
        output = io.StringIO()
        writer = csv.writer(output)

        # User statistics
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
