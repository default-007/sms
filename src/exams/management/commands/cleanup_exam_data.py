"""
School Management System - Exam Cleanup Command
File: src/exams/management/commands/cleanup_exam_data.py
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta

from exams.models import Exam, ExamSchedule, StudentOnlineExamAttempt, StudentExamResult


class Command(BaseCommand):
    help = "Cleanup old exam data and optimize database"

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=365,
            help="Delete data older than specified days",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be deleted without actually deleting",
        )
        parser.add_argument(
            "--cleanup-attempts",
            action="store_true",
            help="Cleanup incomplete online exam attempts",
        )

    def handle(self, *args, **options):
        cutoff_date = timezone.now() - timedelta(days=options["days"])
        dry_run = options["dry_run"]

        self.stdout.write(f"Cleaning up exam data older than {options['days']} days")
        self.stdout.write(f"Cutoff date: {cutoff_date.date()}")

        if dry_run:
            self.stdout.write(
                self.style.WARNING("DRY RUN MODE - No data will be deleted")
            )

        # Cleanup old exam attempts
        if options["cleanup_attempts"]:
            self._cleanup_exam_attempts(dry_run)

        # Cleanup old exams
        old_exams = Exam.objects.filter(
            created_at__lt=cutoff_date, status__in=["COMPLETED", "CANCELLED"]
        )

        self.stdout.write(f"Found {old_exams.count()} old exams to cleanup")

        if not dry_run:
            deleted_count = old_exams.delete()[0]
            self.stdout.write(
                self.style.SUCCESS(f"Deleted {deleted_count} old exam records")
            )

        self.stdout.write("Cleanup completed")

    def _cleanup_exam_attempts(self, dry_run):
        """Cleanup incomplete online exam attempts"""
        # Find attempts older than 24 hours that are still in progress
        cutoff_time = timezone.now() - timedelta(hours=24)

        stale_attempts = StudentOnlineExamAttempt.objects.filter(
            start_time__lt=cutoff_time, status="IN_PROGRESS"
        )

        self.stdout.write(f"Found {stale_attempts.count()} stale exam attempts")

        if not dry_run:
            # Mark as timed out instead of deleting
            updated = stale_attempts.update(
                status="TIMED_OUT", submit_time=timezone.now()
            )
            self.stdout.write(f"Updated {updated} stale attempts to TIMED_OUT")
