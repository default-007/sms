# students/management/commands/student_operations.py
import csv
import logging
import os

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from students.models import Parent, Student, StudentParentRelation
from students.services.analytics_service import StudentAnalyticsService
from students.services.parent_service import ParentService
from students.services.student_service import StudentService

User = get_user_model()
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Comprehensive student operations management command"

    def add_arguments(self, parser):
        subparsers = parser.add_subparsers(
            dest="operation", help="Available operations"
        )

        # Analytics operations
        analytics_parser = subparsers.add_parser(
            "analytics", help="Analytics operations"
        )
        analytics_parser.add_argument(
            "--type",
            choices=["enrollment", "demographics", "performance"],
            default="enrollment",
            help="Type of analytics to generate",
        )
        analytics_parser.add_argument(
            "--output-file", help="Output file for analytics data"
        )
        analytics_parser.add_argument(
            "--clear-cache", action="store_true", help="Clear analytics cache"
        )

        # Data validation operations
        validate_parser = subparsers.add_parser(
            "validate", help="Data validation operations"
        )
        validate_parser.add_argument(
            "--fix-issues", action="store_true", help="Fix found issues automatically"
        )
        validate_parser.add_argument(
            "--report-file", help="Output validation report to file"
        )

        # Bulk operations
        bulk_parser = subparsers.add_parser("bulk", help="Bulk operations")
        bulk_parser.add_argument(
            "--action",
            choices=["promote", "graduate", "activate", "deactivate"],
            required=True,
            help="Bulk action to perform",
        )
        bulk_parser.add_argument(
            "--student-ids", nargs="+", help="Student IDs to operate on"
        )
        bulk_parser.add_argument("--filter-status", help="Filter students by status")
        bulk_parser.add_argument("--filter-class", help="Filter students by class ID")
        bulk_parser.add_argument("--target-class", help="Target class for promotion")
        bulk_parser.add_argument(
            "--send-notifications", action="store_true", help="Send notifications"
        )

        # Import/Export operations
        import_parser = subparsers.add_parser(
            "import", help="Import students from file"
        )
        import_parser.add_argument("--file", required=True, help="CSV file to import")
        import_parser.add_argument(
            "--type",
            choices=["students", "parents"],
            default="students",
            help="Type of data to import",
        )
        import_parser.add_argument(
            "--update-existing", action="store_true", help="Update existing records"
        )
        import_parser.add_argument(
            "--send-notifications", action="store_true", help="Send welcome emails"
        )

        export_parser = subparsers.add_parser("export", help="Export student data")
        export_parser.add_argument(
            "--output-file", required=True, help="Output file path"
        )
        export_parser.add_argument(
            "--format", choices=["csv", "json"], default="csv", help="Export format"
        )
        export_parser.add_argument("--filter-status", help="Filter by status")
        export_parser.add_argument("--filter-class", help="Filter by class ID")

        # Maintenance operations
        maintenance_parser = subparsers.add_parser(
            "maintenance", help="Database maintenance"
        )
        maintenance_parser.add_argument(
            "--action",
            choices=["cleanup", "optimize", "reindex"],
            required=True,
            help="Maintenance action",
        )
        maintenance_parser.add_argument(
            "--dry-run", action="store_true", help="Show what would be done"
        )

        # Communication operations
        comm_parser = subparsers.add_parser("communicate", help="Send communications")
        comm_parser.add_argument(
            "--type",
            choices=["welcome", "reminder", "announcement"],
            required=True,
            help="Communication type",
        )
        comm_parser.add_argument(
            "--recipient-type",
            choices=["students", "parents", "both"],
            default="both",
            help="Recipients",
        )
        comm_parser.add_argument("--message-file", help="File containing message text")
        comm_parser.add_argument("--subject", help="Message subject")

    def handle(self, *args, **options):
        operation = options["operation"]

        if operation == "analytics":
            self.handle_analytics(options)
        elif operation == "validate":
            self.handle_validation(options)
        elif operation == "bulk":
            self.handle_bulk_operations(options)
        elif operation == "import":
            self.handle_import(options)
        elif operation == "export":
            self.handle_export(options)
        elif operation == "maintenance":
            self.handle_maintenance(options)
        elif operation == "communicate":
            self.handle_communication(options)
        else:
            self.stdout.write(self.style.ERROR("Invalid operation"))

    def handle_analytics(self, options):
        """Handle analytics operations"""
        if options["clear_cache"]:
            StudentAnalyticsService.clear_analytics_cache()
            self.stdout.write(self.style.SUCCESS("Analytics cache cleared"))
            return

        analytics_type = options["type"]
        output_file = options.get("output_file")

        self.stdout.write(f"Generating {analytics_type} analytics...")

        try:
            if analytics_type == "enrollment":
                data = StudentAnalyticsService.get_enrollment_trends()
            elif analytics_type == "demographics":
                data = StudentAnalyticsService.get_demographics_analysis()
            elif analytics_type == "performance":
                data = StudentAnalyticsService.get_performance_trends()

            if output_file:
                import json

                with open(output_file, "w") as f:
                    json.dump(data, f, indent=2, default=str)
                self.stdout.write(
                    self.style.SUCCESS(f"Analytics saved to {output_file}")
                )
            else:
                self.stdout.write(str(data))

        except Exception as e:
            raise CommandError(f"Analytics generation failed: {str(e)}")

    def handle_validation(self, options):
        """Handle data validation operations"""
        fix_issues = options["fix_issues"]
        report_file = options.get("report_file")

        self.stdout.write("Starting data validation...")

        issues = []
        fixed_count = 0

        try:
            # Validate students without users
            orphaned_students = Student.objects.filter(user__isnull=True)
            if orphaned_students.exists():
                issue = (
                    f"Found {orphaned_students.count()} students without user accounts"
                )
                issues.append(issue)
                if fix_issues:
                    orphaned_students.delete()
                    fixed_count += orphaned_students.count()

            # Validate students without emergency contacts
            no_emergency = Student.objects.filter(
                emergency_contact_name__isnull=True
            ) | Student.objects.filter(emergency_contact_name="")

            if no_emergency.exists():
                issue = (
                    f"Found {no_emergency.count()} students without emergency contacts"
                )
                issues.append(issue)

            # Validate duplicate admission numbers
            from django.db.models import Count

            duplicates = (
                Student.objects.values("admission_number")
                .annotate(count=Count("admission_number"))
                .filter(count__gt=1)
            )

            if duplicates.exists():
                issue = f"Found {duplicates.count()} duplicate admission numbers"
                issues.append(issue)

            # Validate parent relationships
            students_without_parents = Student.objects.filter(
                student_parent_relations__isnull=True, status="Active"
            )

            if students_without_parents.exists():
                issue = f"Found {students_without_parents.count()} active students without parents"
                issues.append(issue)

            # Multiple primary contacts
            from django.db.models import Count

            multiple_primary = Student.objects.annotate(
                primary_count=Count(
                    "student_parent_relations",
                    filter=Q(student_parent_relations__is_primary_contact=True),
                )
            ).filter(primary_count__gt=1)

            if multiple_primary.exists():
                issue = f"Found {multiple_primary.count()} students with multiple primary contacts"
                issues.append(issue)
                if fix_issues:
                    for student in multiple_primary:
                        # Keep first primary, make others non-primary
                        primaries = student.student_parent_relations.filter(
                            is_primary_contact=True
                        )
                        primaries.exclude(id=primaries.first().id).update(
                            is_primary_contact=False
                        )
                        fixed_count += primaries.count() - 1

            # Report results
            if issues:
                self.stdout.write(
                    self.style.WARNING(f"Found {len(issues)} validation issues:")
                )
                for issue in issues:
                    self.stdout.write(f"  - {issue}")

                if fix_issues:
                    self.stdout.write(self.style.SUCCESS(f"Fixed {fixed_count} issues"))
            else:
                self.stdout.write(self.style.SUCCESS("No validation issues found"))

            # Save report if requested
            if report_file:
                with open(report_file, "w") as f:
                    f.write(f"Student Data Validation Report - {timezone.now()}\n")
                    f.write("=" * 50 + "\n\n")
                    for issue in issues:
                        f.write(f"- {issue}\n")
                    if fix_issues:
                        f.write(f"\nFixed {fixed_count} issues\n")

        except Exception as e:
            raise CommandError(f"Validation failed: {str(e)}")

    def handle_bulk_operations(self, options):
        """Handle bulk operations on students"""
        action = options["action"]
        student_ids = options.get("student_ids", [])
        filter_status = options.get("filter_status")
        filter_class = options.get("filter_class")
        target_class = options.get("target_class")
        send_notifications = options.get("send_notifications", False)

        # Build queryset
        queryset = Student.objects.all()

        if student_ids:
            queryset = queryset.filter(id__in=student_ids)
        if filter_status:
            queryset = queryset.filter(status=filter_status)
        if filter_class:
            queryset = queryset.filter(current_class_id=filter_class)

        student_count = queryset.count()

        if student_count == 0:
            self.stdout.write(self.style.WARNING("No students match the criteria"))
            return

        self.stdout.write(f"Performing {action} on {student_count} students...")

        try:
            with transaction.atomic():
                if action == "promote":
                    if not target_class:
                        raise CommandError("Target class required for promotion")

                    from src.academics.models import Class

                    target_class_obj = Class.objects.get(id=target_class)
                    result = StudentService.promote_students(
                        queryset, target_class_obj, send_notifications
                    )
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Promoted {result['promoted']} students, {result['errors']} errors"
                        )
                    )

                elif action == "graduate":
                    result = StudentService.graduate_students(
                        queryset, send_notifications
                    )
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Graduated {result['graduated']} students, {result['errors']} errors"
                        )
                    )

                elif action == "activate":
                    updated = queryset.update(status="Active")
                    self.stdout.write(
                        self.style.SUCCESS(f"Activated {updated} students")
                    )

                elif action == "deactivate":
                    updated = queryset.update(status="Inactive")
                    self.stdout.write(
                        self.style.SUCCESS(f"Deactivated {updated} students")
                    )

        except Exception as e:
            raise CommandError(f"Bulk operation failed: {str(e)}")

    def handle_import(self, options):
        """Handle import operations"""
        file_path = options["file"]
        data_type = options["type"]
        update_existing = options["update_existing"]
        send_notifications = options["send_notifications"]

        if not os.path.exists(file_path):
            raise CommandError(f"File not found: {file_path}")

        self.stdout.write(f"Importing {data_type} from {file_path}...")

        try:
            with open(file_path, "rb") as f:
                if data_type == "students":
                    result = StudentService.bulk_import_students(
                        f, send_notifications, update_existing
                    )
                elif data_type == "parents":
                    result = ParentService.bulk_import_parents(
                        f, send_notifications, update_existing
                    )

            if result["success"]:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Import completed: Created {result['created']}, "
                        f"Updated {result['updated']}, Errors {result['errors']}"
                    )
                )
            else:
                self.stdout.write(self.style.ERROR(f"Import failed: {result['error']}"))

        except Exception as e:
            raise CommandError(f"Import failed: {str(e)}")

    def handle_export(self, options):
        """Handle export operations"""
        output_file = options["output_file"]
        export_format = options["format"]
        filter_status = options.get("filter_status")
        filter_class = options.get("filter_class")

        # Build queryset
        queryset = Student.objects.with_related()

        if filter_status:
            queryset = queryset.filter(status=filter_status)
        if filter_class:
            queryset = queryset.filter(current_class_id=filter_class)

        self.stdout.write(f"Exporting {queryset.count()} students to {output_file}...")

        try:
            if export_format == "csv":
                content = StudentService.export_students_to_csv(queryset)
            elif export_format == "json":
                from students.services.search_service import StudentSearchService

                content = StudentSearchService.export_search_results(queryset, "json")

            with open(output_file, "w") as f:
                f.write(content)

            self.stdout.write(self.style.SUCCESS(f"Export completed: {output_file}"))

        except Exception as e:
            raise CommandError(f"Export failed: {str(e)}")

    def handle_maintenance(self, options):
        """Handle database maintenance operations"""
        action = options["action"]
        dry_run = options["dry_run"]

        if dry_run:
            self.stdout.write(
                self.style.WARNING("DRY RUN MODE - No changes will be made")
            )

        try:
            if action == "cleanup":
                self._perform_cleanup(dry_run)
            elif action == "optimize":
                self._perform_optimization(dry_run)
            elif action == "reindex":
                self._perform_reindex(dry_run)

        except Exception as e:
            raise CommandError(f"Maintenance failed: {str(e)}")

    def _perform_cleanup(self, dry_run):
        """Perform database cleanup"""
        self.stdout.write("Performing database cleanup...")

        # Clean orphaned records
        orphaned_relations = StudentParentRelation.objects.filter(
            Q(student__isnull=True) | Q(parent__isnull=True)
        )

        if orphaned_relations.exists():
            count = orphaned_relations.count()
            if not dry_run:
                orphaned_relations.delete()
            self.stdout.write(f"Cleaned {count} orphaned relationships")

        # Clear old cache entries
        if not dry_run:
            cache.clear()
            self.stdout.write("Cleared cache")

    def _perform_optimization(self, dry_run):
        """Perform database optimization"""
        self.stdout.write("Performing database optimization...")

        if not dry_run:
            # Analyze query patterns and suggest indexes
            # This would be database-specific
            pass

    def _perform_reindex(self, dry_run):
        """Rebuild database indexes"""
        self.stdout.write("Rebuilding database indexes...")

        if not dry_run:
            # This would be database-specific
            from django.core.management import call_command

            call_command("dbshell", verbosity=0)

    def handle_communication(self, options):
        """Handle communication operations"""
        comm_type = options["type"]
        recipient_type = options["recipient_type"]
        message_file = options.get("message_file")
        subject = options.get("subject")

        if comm_type in ["reminder", "announcement"] and not (message_file or subject):
            raise CommandError(
                "Message file or subject required for this communication type"
            )

        try:
            if comm_type == "welcome":
                self._send_welcome_messages(recipient_type)
            elif comm_type == "reminder":
                self._send_reminder_messages(recipient_type, message_file, subject)
            elif comm_type == "announcement":
                self._send_announcement(recipient_type, message_file, subject)

        except Exception as e:
            raise CommandError(f"Communication failed: {str(e)}")

    def _send_welcome_messages(self, recipient_type):
        """Send welcome messages to new users"""
        # Implementation for welcome messages
        self.stdout.write("Sending welcome messages...")

    def _send_reminder_messages(self, recipient_type, message_file, subject):
        """Send reminder messages"""
        # Implementation for reminder messages
        self.stdout.write("Sending reminder messages...")

    def _send_announcement(self, recipient_type, message_file, subject):
        """Send announcement messages"""
        # Implementation for announcements
        self.stdout.write("Sending announcements...")
