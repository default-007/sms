from django.core.management.base import BaseCommand, CommandError
from django.utils.translation import gettext as _
from django.db import transaction
from datetime import datetime
import json

from subjects.models import Syllabus, Subject, TopicProgress
from subjects.services import SubjectAnalyticsService, CurriculumService
from academics.models import AcademicYear, Department


class Command(BaseCommand):
    """
    Management command to calculate and display curriculum analytics.

    This command provides various analytics operations including:
    - Department performance analysis
    - Teacher performance metrics
    - Curriculum trends analysis
    - Completion forecasting
    """

    help = "Calculate and display curriculum analytics"

    def add_arguments(self, parser):
        """Add command line arguments."""
        parser.add_argument(
            "--academic-year", type=int, help="Academic year ID for analysis"
        )

        parser.add_argument(
            "--department",
            type=int,
            help="Department ID for department-specific analysis",
        )

        parser.add_argument(
            "--teacher", type=int, help="Teacher ID for teacher-specific analysis"
        )

        parser.add_argument(
            "--operation",
            type=str,
            default="overview",
            choices=["overview", "department", "teacher", "trends", "forecast"],
            help="Type of analytics operation to perform",
        )

        parser.add_argument(
            "--output-format",
            type=str,
            default="table",
            choices=["table", "json", "csv"],
            help="Output format for results",
        )

        parser.add_argument(
            "--include-historical",
            action="store_true",
            help="Include historical data in analysis",
        )

        parser.add_argument(
            "--export-file", type=str, help="Export results to specified file"
        )

    def handle(self, *args, **options):
        """Main command handler."""
        try:
            # Get current academic year if not specified
            academic_year_id = options.get("academic_year")
            if not academic_year_id:
                try:
                    current_year = AcademicYear.objects.filter(is_current=True).first()
                    if not current_year:
                        current_year = AcademicYear.objects.order_by(
                            "-start_date"
                        ).first()

                    if not current_year:
                        raise CommandError(
                            "No academic year found. Please create an academic year first."
                        )

                    academic_year_id = current_year.id
                    self.stdout.write(
                        self.style.WARNING(f"Using academic year: {current_year.name}")
                    )
                except Exception as e:
                    raise CommandError(f"Error getting academic year: {str(e)}")

            # Execute the requested operation
            operation = options["operation"]

            if operation == "overview":
                self.handle_overview(academic_year_id, options)
            elif operation == "department":
                self.handle_department_analysis(academic_year_id, options)
            elif operation == "teacher":
                self.handle_teacher_analysis(academic_year_id, options)
            elif operation == "trends":
                self.handle_trends_analysis(academic_year_id, options)
            elif operation == "forecast":
                self.handle_forecast_analysis(academic_year_id, options)

        except Exception as e:
            raise CommandError(f"Error executing analytics command: {str(e)}")

    def handle_overview(self, academic_year_id, options):
        """Handle overview analytics."""
        self.stdout.write(self.style.HTTP_INFO(f"\n{'='*60}"))
        self.stdout.write(self.style.HTTP_INFO("CURRICULUM ANALYTICS OVERVIEW"))
        self.stdout.write(self.style.HTTP_INFO(f"{'='*60}"))

        try:
            # Get curriculum analytics
            analytics = CurriculumService.get_curriculum_analytics(
                academic_year_id, options.get("department")
            )

            self.display_overview_analytics(analytics, options)

        except Exception as e:
            raise CommandError(f"Error generating overview: {str(e)}")

    def handle_department_analysis(self, academic_year_id, options):
        """Handle department-specific analysis."""
        department_id = options.get("department")
        if not department_id:
            # Show analysis for all departments
            departments = Department.objects.all()
            for dept in departments:
                self.analyze_single_department(dept.id, academic_year_id, options)
        else:
            self.analyze_single_department(department_id, academic_year_id, options)

    def analyze_single_department(self, department_id, academic_year_id, options):
        """Analyze a single department."""
        try:
            department = Department.objects.get(id=department_id)

            self.stdout.write(self.style.HTTP_INFO(f"\n{'='*60}"))
            self.stdout.write(
                self.style.HTTP_INFO(f"DEPARTMENT ANALYSIS: {department.name}")
            )
            self.stdout.write(self.style.HTTP_INFO(f"{'='*60}"))

            analytics = SubjectAnalyticsService.get_department_performance_analytics(
                department_id, academic_year_id
            )

            self.display_department_analytics(analytics, options)

        except Department.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f"Department with ID {department_id} not found.")
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(
                    f"Error analyzing department {department_id}: {str(e)}"
                )
            )

    def handle_teacher_analysis(self, academic_year_id, options):
        """Handle teacher-specific analysis."""
        teacher_id = options.get("teacher")
        if not teacher_id:
            raise CommandError(
                "Teacher ID is required for teacher analysis. Use --teacher option."
            )

        try:
            self.stdout.write(self.style.HTTP_INFO(f"\n{'='*60}"))
            self.stdout.write(self.style.HTTP_INFO(f"TEACHER PERFORMANCE ANALYSIS"))
            self.stdout.write(self.style.HTTP_INFO(f"{'='*60}"))

            analytics = SubjectAnalyticsService.get_teacher_performance_analytics(
                teacher_id, academic_year_id, options.get("include_historical", False)
            )

            self.display_teacher_analytics(analytics, options)

        except Exception as e:
            raise CommandError(f"Error analyzing teacher {teacher_id}: {str(e)}")

    def handle_trends_analysis(self, academic_year_id, options):
        """Handle trends analysis."""
        try:
            self.stdout.write(self.style.HTTP_INFO(f"\n{'='*60}"))
            self.stdout.write(self.style.HTTP_INFO("CURRICULUM TRENDS ANALYSIS"))
            self.stdout.write(self.style.HTTP_INFO(f"{'='*60}"))

            trends = SubjectAnalyticsService.get_curriculum_trends(
                academic_year_id, options.get("department"), compare_previous_year=True
            )

            self.display_trends_analytics(trends, options)

        except Exception as e:
            raise CommandError(f"Error generating trends analysis: {str(e)}")

    def handle_forecast_analysis(self, academic_year_id, options):
        """Handle completion forecasting."""
        try:
            self.stdout.write(self.style.HTTP_INFO(f"\n{'='*60}"))
            self.stdout.write(self.style.HTTP_INFO("COMPLETION FORECASTING"))
            self.stdout.write(self.style.HTTP_INFO(f"{'='*60}"))

            forecast = SubjectAnalyticsService.get_completion_forecasting(
                academic_year_id
            )

            self.display_forecast_analytics(forecast, options)

        except Exception as e:
            raise CommandError(f"Error generating forecast: {str(e)}")

    def display_overview_analytics(self, analytics, options):
        """Display overview analytics in specified format."""
        if options["output_format"] == "json":
            self.stdout.write(json.dumps(analytics, indent=2, default=str))
            return

        overview = analytics.get("overview", {})

        self.stdout.write(f"Total Syllabi: {overview.get('total_syllabi', 0)}")
        self.stdout.write(
            f"Average Completion: {overview.get('average_completion', 0):.2f}%"
        )
        self.stdout.write(f"Completed Syllabi: {overview.get('completed_syllabi', 0)}")
        self.stdout.write(f"In Progress: {overview.get('in_progress_syllabi', 0)}")
        self.stdout.write(f"Not Started: {overview.get('not_started_syllabi', 0)}")
        self.stdout.write(f"Completion Rate: {overview.get('completion_rate', 0):.2f}%")

        # Department breakdown
        by_department = analytics.get("by_department", {})
        if by_department:
            self.stdout.write(f"\n{'-'*40}")
            self.stdout.write("DEPARTMENT BREAKDOWN:")
            self.stdout.write(f"{'-'*40}")

            for dept_name, dept_data in by_department.items():
                self.stdout.write(f"\n{dept_name}:")
                self.stdout.write(f"  Subjects: {dept_data.get('total_subjects', 0)}")
                self.stdout.write(f"  Syllabi: {dept_data.get('total_syllabi', 0)}")
                self.stdout.write(
                    f"  Avg Completion: {dept_data.get('avg_completion', 0):.2f}%"
                )

    def display_department_analytics(self, analytics, options):
        """Display department analytics."""
        if options["output_format"] == "json":
            self.stdout.write(json.dumps(analytics, indent=2, default=str))
            return

        if "message" in analytics:
            self.stdout.write(self.style.WARNING(analytics["message"]))
            return

        overview = analytics.get("overview", {})

        self.stdout.write(f"Total Syllabi: {overview.get('total_syllabi', 0)}")
        self.stdout.write(f"Unique Subjects: {overview.get('unique_subjects', 0)}")
        self.stdout.write(f"Unique Grades: {overview.get('unique_grades', 0)}")
        self.stdout.write(
            f"Average Completion: {overview.get('average_completion', 0):.2f}%"
        )
        self.stdout.write(f"Total Topics: {overview.get('total_topics', 0)}")
        self.stdout.write(
            f"Completed Topics: {overview.get('total_completed_topics', 0)}"
        )
        self.stdout.write(f"Hours Taught: {overview.get('total_hours_taught', 0)}")

        # Grade performance
        by_grade = analytics.get("by_grade", {})
        if by_grade:
            self.stdout.write(f"\n{'-'*40}")
            self.stdout.write("GRADE PERFORMANCE:")
            self.stdout.write(f"{'-'*40}")

            for grade_name, grade_data in by_grade.items():
                self.stdout.write(f"\n{grade_name}:")
                self.stdout.write(f"  Syllabi: {grade_data.get('syllabi_count', 0)}")
                self.stdout.write(
                    f"  Avg Completion: {grade_data.get('avg_completion', 0):.2f}%"
                )
                self.stdout.write(
                    f"  Unique Subjects: {grade_data.get('unique_subjects', 0)}"
                )

    def display_teacher_analytics(self, analytics, options):
        """Display teacher analytics."""
        if options["output_format"] == "json":
            self.stdout.write(json.dumps(analytics, indent=2, default=str))
            return

        if "message" in analytics:
            self.stdout.write(self.style.WARNING(analytics["message"]))
            return

        metrics = analytics.get("performance_metrics", {})

        self.stdout.write(f"Total Assignments: {metrics.get('total_assignments', 0)}")
        self.stdout.write(
            f"Primary Assignments: {metrics.get('primary_assignments', 0)}"
        )
        self.stdout.write(
            f"Secondary Assignments: {metrics.get('secondary_assignments', 0)}"
        )
        self.stdout.write(f"Unique Subjects: {metrics.get('unique_subjects', 0)}")
        self.stdout.write(f"Unique Classes: {metrics.get('unique_classes', 0)}")
        self.stdout.write(f"Total Credit Hours: {metrics.get('total_credit_hours', 0)}")

        # Syllabus performance
        syllabus_perf = metrics.get("syllabus_performance", {})
        if syllabus_perf:
            self.stdout.write(f"\nSYLLABUS PERFORMANCE:")
            self.stdout.write(f"Total Syllabi: {syllabus_perf.get('total_syllabi', 0)}")
            self.stdout.write(
                f"Average Completion: {syllabus_perf.get('average_completion', 0):.2f}%"
            )
            self.stdout.write(
                f"Completion Rate: {syllabus_perf.get('completion_rate', 0):.2f}%"
            )

    def display_trends_analytics(self, trends, options):
        """Display trends analytics."""
        if options["output_format"] == "json":
            self.stdout.write(json.dumps(trends, indent=2, default=str))
            return

        current = trends.get("current_year", {})
        previous = trends.get("previous_year", {})
        trend_data = trends.get("trends", {})

        self.stdout.write(f"Current Year Syllabi: {current.get('total_syllabi', 0)}")
        self.stdout.write(
            f"Current Year Avg Completion: {current.get('average_completion', 0):.2f}%"
        )

        if previous:
            self.stdout.write(
                f"\nPrevious Year Syllabi: {previous.get('total_syllabi', 0)}"
            )
            self.stdout.write(
                f"Previous Year Avg Completion: {previous.get('average_completion', 0):.2f}%"
            )

        if trend_data:
            self.stdout.write(f"\nTREND ANALYSIS:")
            for key, value in trend_data.items():
                direction = "↑" if value > 0 else "↓" if value < 0 else "→"
                self.stdout.write(f"{key}: {direction} {value:.2f}%")

    def display_forecast_analytics(self, forecast, options):
        """Display forecast analytics."""
        if options["output_format"] == "json":
            self.stdout.write(json.dumps(forecast, indent=2, default=str))
            return

        forecasts = forecast.get("forecasts", {})
        recommendations = forecast.get("recommendations", [])

        if forecasts:
            self.stdout.write(f"COMPLETION FORECASTS:")
            self.stdout.write(f"{'-'*60}")

            for syllabus_key, forecast_data in forecasts.items():
                self.stdout.write(f"\n{syllabus_key}:")
                self.stdout.write(
                    f"  Current: {forecast_data['current_completion']:.1f}%"
                )
                self.stdout.write(
                    f"  Projected: {forecast_data['projected_completion']:.1f}%"
                )
                self.stdout.write(f"  Risk Level: {forecast_data['risk_level']}")
                self.stdout.write(
                    f"  Days Remaining: {forecast_data['days_remaining']}"
                )

        if recommendations:
            self.stdout.write(f"\nRECOMMENDATIONS:")
            self.stdout.write(f"{'-'*60}")

            for rec in recommendations:
                priority_style = (
                    self.style.ERROR
                    if rec["priority"] == "high"
                    else self.style.WARNING
                )
                self.stdout.write(
                    priority_style(f"[{rec['priority'].upper()}] {rec['syllabus']}")
                )
                self.stdout.write(f"  {rec['recommendation']}")

    def export_results(self, data, filename, format_type):
        """Export results to file."""
        try:
            if format_type == "json":
                with open(filename, "w") as f:
                    json.dump(data, f, indent=2, default=str)
            elif format_type == "csv":
                # Implementation for CSV export
                pass

            self.stdout.write(self.style.SUCCESS(f"Results exported to {filename}"))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error exporting results: {str(e)}"))
