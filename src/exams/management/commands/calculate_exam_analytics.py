"""
School Management System - Exam Management Commands
File: src/exams/management/commands/calculate_exam_analytics.py
"""

from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from academics.models import AcademicYear, Term
from exams.models import Exam
from exams.services.analytics_service import ExamAnalyticsService


class Command(BaseCommand):
    help = "Calculate and update exam analytics for specified period"

    def add_arguments(self, parser):
        parser.add_argument("--academic-year", type=str, help="Academic year ID")
        parser.add_argument("--term", type=str, help="Term ID")
        parser.add_argument(
            "--exam-id", type=str, help="Specific exam ID to calculate analytics for"
        )
        parser.add_argument(
            "--all",
            action="store_true",
            help="Calculate analytics for all active academic years",
        )
        parser.add_argument(
            "--output-format",
            choices=["json", "csv", "console"],
            default="console",
            help="Output format for analytics data",
        )

    def handle(self, *args, **options):
        if options["exam_id"]:
            self._calculate_exam_analytics(options["exam_id"], options["output_format"])
        elif options["all"]:
            self._calculate_all_analytics(options["output_format"])
        elif options["academic_year"]:
            self._calculate_year_analytics(
                options["academic_year"], options.get("term"), options["output_format"]
            )
        else:
            raise CommandError("Please specify --exam-id, --academic-year, or --all")

    def _calculate_exam_analytics(self, exam_id, output_format):
        """Calculate analytics for a specific exam"""
        try:
            exam = Exam.objects.get(id=exam_id)
            self.stdout.write(f"Calculating analytics for exam: {exam.name}")

            analytics = ExamAnalyticsService.get_exam_analytics(exam_id)

            if output_format == "console":
                self._display_exam_analytics(analytics)
            elif output_format == "json":
                self._export_json(analytics, f"exam_{exam_id}_analytics.json")
            elif output_format == "csv":
                self._export_csv(analytics, f"exam_{exam_id}_analytics.csv")

            self.stdout.write(
                self.style.SUCCESS(
                    f"Analytics calculated successfully for exam: {exam.name}"
                )
            )

        except Exam.DoesNotExist:
            raise CommandError(f"Exam with ID {exam_id} not found")
        except Exception as e:
            raise CommandError(f"Error calculating analytics: {e}")

    def _calculate_all_analytics(self, output_format):
        """Calculate analytics for all active academic years"""
        active_years = AcademicYear.objects.filter(is_current=True)

        if not active_years.exists():
            self.stdout.write(self.style.WARNING("No active academic years found"))
            return

        for year in active_years:
            self.stdout.write(f"Processing academic year: {year.name}")

            current_term = year.terms.filter(is_current=True).first()
            if current_term:
                self._calculate_year_analytics(
                    str(year.id), str(current_term.id), output_format
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f"No current term found for {year.name}")
                )

    def _calculate_year_analytics(self, academic_year_id, term_id, output_format):
        """Calculate analytics for academic year/term"""
        try:
            dashboard = ExamAnalyticsService.get_academic_performance_dashboard(
                academic_year_id, term_id
            )

            if output_format == "console":
                self._display_dashboard_analytics(dashboard)
            elif output_format == "json":
                filename = (
                    f'dashboard_{academic_year_id}_{term_id or "all"}_analytics.json'
                )
                self._export_json(dashboard, filename)
            elif output_format == "csv":
                filename = (
                    f'dashboard_{academic_year_id}_{term_id or "all"}_analytics.csv'
                )
                self._export_csv(dashboard, filename)

        except Exception as e:
            raise CommandError(f"Error calculating year analytics: {e}")

    def _display_exam_analytics(self, analytics):
        """Display exam analytics in console"""
        exam_info = analytics.get("exam_info", {})
        performance = analytics.get("performance_summary", {})

        self.stdout.write(self.style.SUCCESS("\n=== EXAM ANALYTICS ==="))
        self.stdout.write(f"Exam: {exam_info.get('name', 'N/A')}")
        self.stdout.write(f"Status: {exam_info.get('status', 'N/A')}")
        self.stdout.write(
            f"Completion Rate: {exam_info.get('completion_rate', 0):.1f}%"
        )

        self.stdout.write(self.style.SUCCESS("\n--- Performance Summary ---"))
        self.stdout.write(
            f"Average Percentage: {performance.get('avg_percentage', 0):.2f}%"
        )
        self.stdout.write(f"Pass Rate: {performance.get('pass_rate', 0):.2f}%")
        self.stdout.write(f"Total Students: {performance.get('total_count', 0)}")
        self.stdout.write(
            f"Highest Score: {performance.get('highest_percentage', 0):.2f}%"
        )
        self.stdout.write(
            f"Lowest Score: {performance.get('lowest_percentage', 0):.2f}%"
        )

    def _display_dashboard_analytics(self, dashboard):
        """Display dashboard analytics in console"""
        overview = dashboard.get("overview", {})

        self.stdout.write(self.style.SUCCESS("\n=== ACADEMIC DASHBOARD ==="))
        self.stdout.write(f"Total Students: {overview.get('total_students', 0)}")
        self.stdout.write(f"Total Subjects: {overview.get('total_subjects', 0)}")
        self.stdout.write(
            f"Average Performance: {overview.get('avg_percentage', 0):.2f}%"
        )
        self.stdout.write(f"Overall Pass Rate: {overview.get('pass_rate', 0):.2f}%")
        self.stdout.write(f"Attendance Rate: {overview.get('attendance_rate', 0):.2f}%")

    def _export_json(self, data, filename):
        """Export analytics data to JSON"""
        import json

        with open(filename, "w") as f:
            json.dump(data, f, indent=2, default=str)

        self.stdout.write(f"Analytics exported to: {filename}")

    def _export_csv(self, data, filename):
        """Export analytics data to CSV"""
        import csv

        # Simplified CSV export - can be enhanced based on needs
        with open(filename, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["Metric", "Value"])

            if "overview" in data:
                overview = data["overview"]
                for key, value in overview.items():
                    writer.writerow([key, value])

        self.stdout.write(f"Analytics exported to: {filename}")
