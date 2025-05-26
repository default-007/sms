"""
School Management System - Exam Management Commands
File: src/exams/management/commands/generate_exam_statistics.py
"""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from academics.models import AcademicYear, Term
from exams.services.analytics_service import ExamAnalyticsService


class Command(BaseCommand):
    help = "Generate comprehensive exam statistics for reporting"

    def add_arguments(self, parser):
        parser.add_argument(
            "--academic-year",
            type=str,
            help="Academic year ID to generate statistics for",
        )
        parser.add_argument(
            "--term", type=str, help="Term ID to generate statistics for"
        )
        parser.add_argument(
            "--output",
            type=str,
            default="exam_statistics.json",
            help="Output file name",
        )

    def handle(self, *args, **options):
        academic_year_id = options["academic_year"]
        term_id = options["term"]
        output_file = options["output"]

        if not academic_year_id:
            # Use current academic year
            current_year = AcademicYear.objects.filter(is_current=True).first()
            if current_year:
                academic_year_id = str(current_year.id)
            else:
                self.stdout.write(self.style.ERROR("No current academic year found"))
                return

        try:
            # Generate dashboard analytics
            dashboard = ExamAnalyticsService.get_academic_performance_dashboard(
                academic_year_id, term_id
            )

            # Export to file
            import json

            with open(output_file, "w") as f:
                json.dump(dashboard, f, indent=2, default=str)

            self.stdout.write(
                self.style.SUCCESS(
                    f"Exam statistics generated successfully: {output_file}"
                )
            )

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error generating statistics: {e}"))
