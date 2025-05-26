import sys

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from academics.models import Grade, Term
from accounts.models import User
from scheduling.models import TimetableGeneration
from scheduling.services.analytics_service import SchedulingAnalyticsService
from scheduling.services.optimization_service import OptimizationService


class Command(BaseCommand):
    """Management command to optimize timetables"""

    help = "Optimize timetable for a given term"

    def add_arguments(self, parser):
        parser.add_argument(
            "--term-id",
            type=str,
            required=True,
            help="Term ID to optimize timetable for",
        )

        parser.add_argument(
            "--grade-ids",
            nargs="+",
            type=str,
            help="Grade IDs to include in optimization (all if not specified)",
        )

        parser.add_argument(
            "--algorithm",
            type=str,
            choices=["genetic", "greedy"],
            default="genetic",
            help="Optimization algorithm to use (default: genetic)",
        )

        parser.add_argument(
            "--population-size",
            type=int,
            default=50,
            help="Population size for genetic algorithm (default: 50)",
        )

        parser.add_argument(
            "--generations",
            type=int,
            default=100,
            help="Number of generations for genetic algorithm (default: 100)",
        )

        parser.add_argument(
            "--mutation-rate",
            type=float,
            default=0.1,
            help="Mutation rate for genetic algorithm (default: 0.1)",
        )

        parser.add_argument(
            "--clear-existing",
            action="store_true",
            help="Clear existing timetable before optimization",
        )

        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Run optimization without saving results",
        )

        parser.add_argument(
            "--verbose", action="store_true", help="Show detailed optimization progress"
        )

        parser.add_argument(
            "--save-generation",
            action="store_true",
            help="Save generation record for tracking",
        )

    def handle(self, *args, **options):
        """Handle the command execution"""

        try:
            # Get term
            term = Term.objects.get(id=options["term_id"])
            self.stdout.write(f"Optimizing timetable for term: {term}")

            # Get grades
            if options["grade_ids"]:
                grades = Grade.objects.filter(id__in=options["grade_ids"])
                if not grades.exists():
                    raise CommandError("No grades found with provided IDs")
            else:
                grades = Grade.objects.all()

            self.stdout.write(f"Including {grades.count()} grades in optimization")

            # Show current timetable status
            current_entries = term.timetable_entries.filter(is_active=True).count()
            self.stdout.write(f"Current timetable entries: {current_entries}")

            # Clear existing if requested
            if options["clear_existing"]:
                if not options["dry_run"]:
                    confirm = input(
                        "This will delete all existing timetable entries. Continue? (y/N): "
                    )
                    if confirm.lower() != "y":
                        self.stdout.write("Operation cancelled.")
                        return

                    deleted_count = term.timetable_entries.all().delete()[0]
                    self.stdout.write(
                        self.style.WARNING(
                            f"Deleted {deleted_count} existing timetable entries"
                        )
                    )
                else:
                    self.stdout.write(
                        "DRY RUN: Would delete existing timetable entries"
                    )

            # Create generation record if requested
            generation = None
            if options["save_generation"]:
                admin_user = User.objects.filter(is_superuser=True).first()
                generation = TimetableGeneration.objects.create(
                    term=term,
                    algorithm_used=options["algorithm"],
                    parameters={
                        "population_size": options["population_size"],
                        "generations": options["generations"],
                        "mutation_rate": options["mutation_rate"],
                    },
                    started_by=admin_user,
                    status="running",
                )
                generation.grades.set(grades)
                self.stdout.write(f"Created generation record: {generation.id}")

            # Initialize optimizer
            optimizer = OptimizationService(term)

            # Run optimization
            self.stdout.write("Starting optimization...")
            start_time = timezone.now()

            try:
                result = optimizer.generate_optimized_timetable(
                    grades=list(grades),
                    algorithm=options["algorithm"],
                    population_size=options["population_size"],
                    generations=options["generations"],
                    mutation_rate=options["mutation_rate"],
                )

                end_time = timezone.now()
                execution_time = (end_time - start_time).total_seconds()

                # Display results
                self._display_results(result, execution_time, options["verbose"])

                # Save results if not dry run
                if not options["dry_run"] and result.success:
                    save_result = optimizer.save_schedule_to_database(result)
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Saved {save_result['created']} timetable entries to database"
                        )
                    )

                    if save_result["errors"]:
                        self.stdout.write(
                            self.style.WARNING(
                                f"Errors during save: {len(save_result['errors'])}"
                            )
                        )
                        for error in save_result["errors"][:5]:  # Show first 5 errors
                            self.stdout.write(f"  - {error}")

                # Update generation record
                if generation:
                    generation.status = "completed" if result.success else "failed"
                    generation.optimization_score = result.optimization_score
                    generation.execution_time_seconds = execution_time
                    generation.conflicts_resolved = len(result.conflicts)
                    generation.result_summary = {
                        "assigned_slots": len(result.assigned_slots),
                        "unassigned_slots": len(result.unassigned_slots),
                        "total_conflicts": len(result.conflicts),
                    }
                    generation.completed_at = timezone.now()

                    if not result.success:
                        generation.error_message = (
                            f"Failed to assign {len(result.unassigned_slots)} slots"
                        )

                    generation.save()

                # Show analytics
                if not options["dry_run"] and result.success:
                    self._show_analytics(term)

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Optimization failed: {str(e)}"))

                if generation:
                    generation.status = "failed"
                    generation.error_message = str(e)
                    generation.completed_at = timezone.now()
                    generation.save()

                raise CommandError(f"Optimization failed: {str(e)}")

        except Term.DoesNotExist:
            raise CommandError(f"Term with ID {options['term_id']} not found")
        except Exception as e:
            raise CommandError(f"Command failed: {str(e)}")

    def _display_results(self, result, execution_time, verbose):
        """Display optimization results"""

        self.stdout.write("\n" + "=" * 50)
        self.stdout.write("OPTIMIZATION RESULTS")
        self.stdout.write("=" * 50)

        self.stdout.write(f"Success: {result.success}")
        self.stdout.write(f"Execution Time: {execution_time:.2f} seconds")
        self.stdout.write(f"Optimization Score: {result.optimization_score:.2f}")
        self.stdout.write(f"Assigned Slots: {len(result.assigned_slots)}")
        self.stdout.write(f"Unassigned Slots: {len(result.unassigned_slots)}")
        self.stdout.write(f"Conflicts: {len(result.conflicts)}")

        if result.unassigned_slots and verbose:
            self.stdout.write("\nUNASSIGNED SLOTS:")
            for i, slot in enumerate(result.unassigned_slots[:10]):  # Show first 10
                self.stdout.write(
                    f"  {i+1}. {slot.class_obj} - {slot.subject} - {slot.teacher}"
                )

            if len(result.unassigned_slots) > 10:
                self.stdout.write(f"  ... and {len(result.unassigned_slots) - 10} more")

        if result.conflicts and verbose:
            self.stdout.write("\nCONFLICTS:")
            for i, conflict in enumerate(result.conflicts[:10]):  # Show first 10
                self.stdout.write(f"  {i+1}. {conflict['type']}: {conflict}")

            if len(result.conflicts) > 10:
                self.stdout.write(f"  ... and {len(result.conflicts) - 10} more")

        # Recommendations
        if result.success:
            self.stdout.write(
                "\n" + self.style.SUCCESS("Optimization completed successfully!")
            )
        else:
            self.stdout.write(
                "\n" + self.style.WARNING("Optimization completed with issues.")
            )
            self.stdout.write("Consider:")
            self.stdout.write("  - Adding more time slots")
            self.stdout.write("  - Adding more rooms")
            self.stdout.write("  - Reducing subject hours")
            self.stdout.write("  - Checking teacher assignments")

    def _show_analytics(self, term):
        """Show analytics after optimization"""

        self.stdout.write("\n" + "=" * 50)
        self.stdout.write("ANALYTICS")
        self.stdout.write("=" * 50)

        try:
            # Get optimization score
            score_data = SchedulingAnalyticsService.get_timetable_optimization_score(
                term
            )

            self.stdout.write(
                f"Overall Score: {score_data['overall_score']:.1f}% (Grade: {score_data['grade']})"
            )

            self.stdout.write("\nBreakdown:")
            for category, score in score_data["breakdown"].items():
                self.stdout.write(
                    f"  {category.replace('_', ' ').title()}: {score:.1f}"
                )

            if score_data["recommendations"]:
                self.stdout.write("\nRecommendations:")
                for recommendation in score_data["recommendations"]:
                    self.stdout.write(f"  - {recommendation}")

            # Teacher workload summary
            teacher_analytics = (
                SchedulingAnalyticsService.get_teacher_workload_analytics(term)
            )
            summary = teacher_analytics["summary"]

            self.stdout.write(f"\nTeacher Workload:")
            self.stdout.write(f"  Total Teachers: {summary['total_teachers']}")
            self.stdout.write(
                f"  Average Periods per Teacher: {summary['average_periods_per_teacher']:.1f}"
            )

            # Room utilization summary
            room_analytics = SchedulingAnalyticsService.get_room_utilization_analytics(
                term
            )
            room_summary = room_analytics["summary"]

            self.stdout.write(f"\nRoom Utilization:")
            self.stdout.write(f"  Rooms in Use: {room_summary['total_rooms_in_use']}")
            self.stdout.write(
                f"  Average Utilization: {room_summary['average_utilization_rate']:.1f}%"
            )

        except Exception as e:
            self.stdout.write(
                self.style.WARNING(f"Could not generate analytics: {str(e)}")
            )


# Additional utility command for timetable analysis
class AnalyzeCommand(BaseCommand):
    """Command to analyze existing timetable"""

    help = "Analyze existing timetable for issues and optimization opportunities"

    def add_arguments(self, parser):
        parser.add_argument(
            "--term-id", type=str, required=True, help="Term ID to analyze"
        )

        parser.add_argument(
            "--detailed", action="store_true", help="Show detailed analysis"
        )

        parser.add_argument("--export", type=str, help="Export analysis to file")

    def handle(self, *args, **options):
        """Handle analysis command"""

        try:
            term = Term.objects.get(id=options["term_id"])

            self.stdout.write(f"Analyzing timetable for term: {term}")

            # Basic statistics
            total_entries = term.timetable_entries.filter(is_active=True).count()
            self.stdout.write(f"Total timetable entries: {total_entries}")

            if total_entries == 0:
                self.stdout.write("No timetable entries found for analysis.")
                return

            # Get analytics
            teacher_analytics = (
                SchedulingAnalyticsService.get_teacher_workload_analytics(term)
            )
            room_analytics = SchedulingAnalyticsService.get_room_utilization_analytics(
                term
            )
            conflicts = SchedulingAnalyticsService.get_scheduling_conflicts_analytics(
                term
            )
            score = SchedulingAnalyticsService.get_timetable_optimization_score(term)

            # Display results
            self._display_analysis(
                teacher_analytics, room_analytics, conflicts, score, options["detailed"]
            )

            # Export if requested
            if options["export"]:
                self._export_analysis(
                    options["export"],
                    {
                        "term": str(term),
                        "teacher_analytics": teacher_analytics,
                        "room_analytics": room_analytics,
                        "conflicts": conflicts,
                        "score": score,
                    },
                )

        except Term.DoesNotExist:
            raise CommandError(f"Term with ID {options['term_id']} not found")
        except Exception as e:
            raise CommandError(f"Analysis failed: {str(e)}")

    def _display_analysis(
        self, teacher_analytics, room_analytics, conflicts, score, detailed
    ):
        """Display analysis results"""

        self.stdout.write("\n" + "=" * 50)
        self.stdout.write("TIMETABLE ANALYSIS")
        self.stdout.write("=" * 50)

        # Overall score
        self.stdout.write(
            f"Optimization Score: {score['overall_score']:.1f}% (Grade: {score['grade']})"
        )

        # Conflicts
        self.stdout.write(f"\nConflicts:")
        self.stdout.write(f"  Teacher Conflicts: {conflicts['teacher_conflicts']}")
        self.stdout.write(f"  Room Conflicts: {conflicts['room_conflicts']}")
        self.stdout.write(f"  Unassigned Rooms: {conflicts['unassigned_rooms']}")

        # Teacher workload
        teacher_summary = teacher_analytics["summary"]
        self.stdout.write(f"\nTeacher Workload:")
        self.stdout.write(f"  Total Teachers: {teacher_summary['total_teachers']}")
        self.stdout.write(
            f"  Average Periods: {teacher_summary['average_periods_per_teacher']:.1f}"
        )

        if detailed and teacher_analytics["teacher_workloads"]:
            self.stdout.write("  Top 5 Most Loaded Teachers:")
            sorted_teachers = sorted(
                teacher_analytics["teacher_workloads"],
                key=lambda x: x["total_periods"],
                reverse=True,
            )[:5]

            for teacher in sorted_teachers:
                self.stdout.write(
                    f"    {teacher['teacher__first_name']} {teacher['teacher__last_name']}: "
                    f"{teacher['total_periods']} periods"
                )

        # Room utilization
        room_summary = room_analytics["summary"]
        self.stdout.write(f"\nRoom Utilization:")
        self.stdout.write(f"  Rooms in Use: {room_summary['total_rooms_in_use']}")
        self.stdout.write(
            f"  Average Utilization: {room_summary['average_utilization_rate']:.1f}%"
        )

        # Recommendations
        if score["recommendations"]:
            self.stdout.write("\nRecommendations:")
            for recommendation in score["recommendations"]:
                self.stdout.write(f"  - {recommendation}")

    def _export_analysis(self, filename, data):
        """Export analysis to file"""

        import json

        try:
            with open(filename, "w") as f:
                json.dump(data, f, indent=2, default=str)

            self.stdout.write(f"Analysis exported to: {filename}")

        except Exception as e:
            self.stdout.write(self.style.WARNING(f"Export failed: {str(e)}"))
