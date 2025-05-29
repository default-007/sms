# src/teachers/management/commands/optimize_teacher_database.py
import time

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import connection, transaction


class Command(BaseCommand):
    help = "Optimize teacher database performance"

    def add_arguments(self, parser):
        parser.add_argument(
            "--analyze-only",
            action="store_true",
            help="Only analyze performance without making changes",
        )
        parser.add_argument(
            "--vacuum", action="store_true", help="Run database vacuum operation"
        )

    def handle(self, *args, **options):
        if options["analyze_only"]:
            self.analyze_performance()
        else:
            self.optimize_database(options)

    def analyze_performance(self):
        """Analyze database performance for teacher tables."""
        self.stdout.write("Analyzing teacher database performance...")

        with connection.cursor() as cursor:
            # Analyze query performance
            queries = [
                (
                    "Teacher count by status",
                    "SELECT status, COUNT(*) FROM teachers_teacher GROUP BY status",
                ),
                (
                    "Average evaluation score",
                    "SELECT AVG(score) FROM teachers_teacherevaluation",
                ),
                (
                    "Teachers by department",
                    "SELECT d.name, COUNT(t.id) FROM teachers_teacher t LEFT JOIN courses_department d ON t.department_id = d.id GROUP BY d.name",
                ),
                (
                    "Assignment distribution",
                    "SELECT COUNT(*) as assignments, teacher_id FROM teachers_teacherclassassignment GROUP BY teacher_id ORDER BY assignments DESC LIMIT 10",
                ),
            ]

            for description, query in queries:
                start_time = time.time()
                cursor.execute(query)
                results = cursor.fetchall()
                execution_time = time.time() - start_time

                self.stdout.write(
                    f"{description}: {execution_time:.3f}s ({len(results)} rows)"
                )

        # Check index usage
        self.check_index_usage()

    def optimize_database(self, options):
        """Optimize database for better performance."""
        self.stdout.write("Optimizing teacher database...")

        with connection.cursor() as cursor:
            # Update table statistics
            self.stdout.write("Updating table statistics...")
            cursor.execute("ANALYZE teachers_teacher")
            cursor.execute("ANALYZE teachers_teacherevaluation")
            cursor.execute("ANALYZE teachers_teacherclassassignment")

            # Vacuum if requested
            if options.get("vacuum"):
                self.stdout.write("Running vacuum operation...")
                cursor.execute("VACUUM ANALYZE teachers_teacher")
                cursor.execute("VACUUM ANALYZE teachers_teacherevaluation")
                cursor.execute("VACUUM ANALYZE teachers_teacherclassassignment")

        self.stdout.write(self.style.SUCCESS("Database optimization completed"))

    def check_index_usage(self):
        """Check index usage statistics."""
        if "postgresql" in settings.DATABASES["default"]["ENGINE"]:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT schemaname, tablename, indexname, idx_tup_read, idx_tup_fetch
                    FROM pg_stat_user_indexes 
                    WHERE schemaname = 'public' AND tablename LIKE 'teachers_%'
                    ORDER BY idx_tup_read DESC
                """
                )

                results = cursor.fetchall()

                self.stdout.write("\nIndex Usage Statistics:")
                for schema, table, index, reads, fetches in results:
                    self.stdout.write(
                        f"  {table}.{index}: {reads} reads, {fetches} fetches"
                    )
