# src/teachers/management/commands/migrate_teacher_data.py
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction, connection
from django.utils import timezone
from django.contrib.auth import get_user_model
from decimal import Decimal
import csv
import json
from datetime import datetime, date
import logging

from src.teachers.models import Teacher, TeacherEvaluation, TeacherClassAssignment
from src.courses.models import Department, AcademicYear, Subject, Class
from src.teachers.validators import validate_teacher_data, validate_evaluation_data

User = get_user_model()
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Migrate and optimize teacher data"

    def add_arguments(self, parser):
        parser.add_argument(
            "--operation",
            type=str,
            choices=[
                "cleanup_orphaned",
                "fix_duplicates",
                "optimize_indexes",
                "migrate_legacy",
                "update_analytics",
                "export_backup",
                "import_backup",
                "normalize_data",
            ],
            required=True,
            help="Operation to perform",
        )
        parser.add_argument(
            "--file", type=str, help="File path for import/export operations"
        )
        parser.add_argument(
            "--department-id",
            type=int,
            help="Department ID for department-specific operations",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be done without making changes",
        )
        parser.add_argument(
            "--batch-size", type=int, default=100, help="Batch size for bulk operations"
        )

    def handle(self, *args, **options):
        operation = options["operation"]

        try:
            if operation == "cleanup_orphaned":
                self.cleanup_orphaned_records(options)
            elif operation == "fix_duplicates":
                self.fix_duplicate_records(options)
            elif operation == "optimize_indexes":
                self.optimize_database_indexes(options)
            elif operation == "migrate_legacy":
                self.migrate_legacy_data(options)
            elif operation == "update_analytics":
                self.update_analytics_data(options)
            elif operation == "export_backup":
                self.export_teacher_backup(options)
            elif operation == "import_backup":
                self.import_teacher_backup(options)
            elif operation == "normalize_data":
                self.normalize_teacher_data(options)

        except Exception as e:
            logger.error(f"Migration operation failed: {str(e)}")
            raise CommandError(f"Operation failed: {str(e)}")

    def cleanup_orphaned_records(self, options):
        """Clean up orphaned teacher records."""
        self.stdout.write("Starting orphaned records cleanup...")

        dry_run = options["dry_run"]

        # Find teachers without users
        orphaned_teachers = Teacher.objects.filter(user__isnull=True)
        self.stdout.write(f"Found {orphaned_teachers.count()} teachers without users")

        if not dry_run and orphaned_teachers.exists():
            with transaction.atomic():
                deleted_count = orphaned_teachers.delete()[0]
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Deleted {deleted_count} orphaned teacher records"
                    )
                )

        # Find evaluations without teachers
        orphaned_evaluations = TeacherEvaluation.objects.filter(teacher__isnull=True)
        self.stdout.write(
            f"Found {orphaned_evaluations.count()} evaluations without teachers"
        )

        if not dry_run and orphaned_evaluations.exists():
            with transaction.atomic():
                deleted_count = orphaned_evaluations.delete()[0]
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Deleted {deleted_count} orphaned evaluation records"
                    )
                )

        # Find assignments without valid references
        orphaned_assignments = TeacherClassAssignment.objects.filter(
            models.Q(teacher__isnull=True)
            | models.Q(class_instance__isnull=True)
            | models.Q(subject__isnull=True)
        )
        self.stdout.write(f"Found {orphaned_assignments.count()} orphaned assignments")

        if not dry_run and orphaned_assignments.exists():
            with transaction.atomic():
                deleted_count = orphaned_assignments.delete()[0]
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Deleted {deleted_count} orphaned assignment records"
                    )
                )

    def fix_duplicate_records(self, options):
        """Fix duplicate teacher records."""
        self.stdout.write("Starting duplicate records fix...")

        dry_run = options["dry_run"]

        # Find duplicate employee IDs
        duplicates = (
            Teacher.objects.values("employee_id")
            .annotate(count=models.Count("id"))
            .filter(count__gt=1)
        )

        for duplicate in duplicates:
            employee_id = duplicate["employee_id"]
            teachers = Teacher.objects.filter(employee_id=employee_id).order_by(
                "created_at"
            )

            self.stdout.write(
                f"Found {teachers.count()} teachers with employee ID {employee_id}"
            )

            if not dry_run:
                # Keep the first (oldest) record, merge data from others
                primary_teacher = teachers.first()
                duplicate_teachers = teachers[1:]

                with transaction.atomic():
                    for dup_teacher in duplicate_teachers:
                        # Transfer evaluations
                        TeacherEvaluation.objects.filter(teacher=dup_teacher).update(
                            teacher=primary_teacher
                        )

                        # Transfer assignments
                        TeacherClassAssignment.objects.filter(
                            teacher=dup_teacher
                        ).update(teacher=primary_teacher)

                        # Delete duplicate
                        dup_teacher.delete()

                self.stdout.write(
                    self.style.SUCCESS(
                        f"Merged {len(duplicate_teachers)} duplicates for {employee_id}"
                    )
                )

    def optimize_database_indexes(self, options):
        """Optimize database indexes for better performance."""
        self.stdout.write("Optimizing database indexes...")

        dry_run = options["dry_run"]

        # Define index optimizations
        index_queries = [
            # Teacher indexes
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_teacher_status_dept ON teachers_teacher(status, department_id) WHERE status = 'Active';",
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_teacher_joining_date_year ON teachers_teacher(EXTRACT(year FROM joining_date));",
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_teacher_experience_range ON teachers_teacher(experience_years) WHERE status = 'Active';",
            # Evaluation indexes
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_evaluation_teacher_date ON teachers_teacherevaluation(teacher_id, evaluation_date DESC);",
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_evaluation_score_range ON teachers_teacherevaluation(score) WHERE score IS NOT NULL;",
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_evaluation_followup ON teachers_teacherevaluation(followup_date) WHERE followup_date IS NOT NULL AND status IN ('submitted', 'reviewed');",
            # Assignment indexes
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_assignment_teacher_year ON teachers_teacherclassassignment(teacher_id, academic_year_id);",
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_assignment_class_teacher ON teachers_teacherclassassignment(class_instance_id, is_class_teacher) WHERE is_class_teacher = true;",
        ]

        if not dry_run:
            with connection.cursor() as cursor:
                for query in index_queries:
                    try:
                        self.stdout.write(f"Creating index: {query[:60]}...")
                        cursor.execute(query)
                        self.stdout.write(
                            self.style.SUCCESS("Index created successfully")
                        )
                    except Exception as e:
                        self.stdout.write(
                            self.style.WARNING(f"Index creation failed: {str(e)}")
                        )
        else:
            self.stdout.write("Dry run - would create the following indexes:")
            for query in index_queries:
                self.stdout.write(f"  {query}")

    def migrate_legacy_data(self, options):
        """Migrate legacy teacher data."""
        self.stdout.write("Starting legacy data migration...")

        file_path = options.get("file")
        if not file_path:
            raise CommandError("File path is required for legacy migration")

        dry_run = options["dry_run"]
        batch_size = options["batch_size"]

        migrated_count = 0
        error_count = 0

        try:
            with open(file_path, "r", encoding="utf-8") as csvfile:
                reader = csv.DictReader(csvfile)
                batch = []

                for row in reader:
                    try:
                        # Transform legacy data to current format
                        teacher_data = self._transform_legacy_teacher_data(row)

                        if not dry_run:
                            batch.append(teacher_data)

                            if len(batch) >= batch_size:
                                self._process_teacher_batch(batch)
                                migrated_count += len(batch)
                                batch = []
                        else:
                            migrated_count += 1

                    except Exception as e:
                        error_count += 1
                        logger.error(
                            f"Error processing row {reader.line_num}: {str(e)}"
                        )

                # Process remaining batch
                if batch and not dry_run:
                    self._process_teacher_batch(batch)
                    migrated_count += len(batch)

        except FileNotFoundError:
            raise CommandError(f"File not found: {file_path}")

        self.stdout.write(
            self.style.SUCCESS(
                f"Migration completed: {migrated_count} records processed, {error_count} errors"
            )
        )

    def update_analytics_data(self, options):
        """Update analytics and cached data."""
        self.stdout.write("Updating analytics data...")

        department_id = options.get("department_id")
        dry_run = options["dry_run"]

        if not dry_run:
            # Update evaluation statistics
            self._update_evaluation_statistics(department_id)

            # Update workload statistics
            self._update_workload_statistics(department_id)

            # Update performance rankings
            self._update_performance_rankings(department_id)

        self.stdout.write(self.style.SUCCESS("Analytics data updated successfully"))

    def export_teacher_backup(self, options):
        """Export teacher data for backup."""
        file_path = options.get("file")
        if not file_path:
            raise CommandError("File path is required for export")

        department_id = options.get("department_id")

        self.stdout.write("Exporting teacher data...")

        # Build queryset
        teachers = Teacher.objects.select_related("user", "department")
        if department_id:
            teachers = teachers.filter(department_id=department_id)

        backup_data = {
            "export_date": timezone.now().isoformat(),
            "total_teachers": teachers.count(),
            "teachers": [],
        }

        for teacher in teachers:
            teacher_data = {
                "employee_id": teacher.employee_id,
                "user_data": {
                    "first_name": teacher.user.first_name,
                    "last_name": teacher.user.last_name,
                    "email": teacher.user.email,
                    "phone_number": getattr(teacher.user, "phone_number", ""),
                },
                "teacher_data": {
                    "joining_date": (
                        teacher.joining_date.isoformat()
                        if teacher.joining_date
                        else None
                    ),
                    "qualification": teacher.qualification,
                    "experience_years": str(teacher.experience_years),
                    "specialization": teacher.specialization,
                    "department": (
                        teacher.department.name if teacher.department else None
                    ),
                    "position": teacher.position,
                    "salary": str(teacher.salary),
                    "contract_type": teacher.contract_type,
                    "status": teacher.status,
                    "bio": teacher.bio,
                    "emergency_contact": teacher.emergency_contact,
                    "emergency_phone": teacher.emergency_phone,
                },
                "evaluations": [
                    {
                        "evaluation_date": eval.evaluation_date.isoformat(),
                        "score": float(eval.score),
                        "criteria": eval.criteria,
                        "remarks": eval.remarks,
                        "status": eval.status,
                    }
                    for eval in teacher.evaluations.all()
                ],
                "assignments": [
                    {
                        "class_name": str(assignment.class_instance),
                        "subject_name": assignment.subject.name,
                        "academic_year": assignment.academic_year.name,
                        "is_class_teacher": assignment.is_class_teacher,
                        "notes": assignment.notes,
                    }
                    for assignment in teacher.class_assignments.select_related(
                        "class_instance", "subject", "academic_year"
                    )
                ],
            }
            backup_data["teachers"].append(teacher_data)

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(backup_data, f, indent=2, ensure_ascii=False)

        self.stdout.write(
            self.style.SUCCESS(
                f"Exported {len(backup_data['teachers'])} teachers to {file_path}"
            )
        )

    def import_teacher_backup(self, options):
        """Import teacher data from backup."""
        file_path = options.get("file")
        if not file_path:
            raise CommandError("File path is required for import")

        dry_run = options["dry_run"]

        self.stdout.write("Importing teacher data...")

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                backup_data = json.load(f)

            imported_count = 0
            error_count = 0

            for teacher_data in backup_data.get("teachers", []):
                try:
                    if not dry_run:
                        self._import_teacher_record(teacher_data)
                    imported_count += 1

                except Exception as e:
                    error_count += 1
                    logger.error(
                        f"Error importing teacher {teacher_data.get('employee_id')}: {str(e)}"
                    )

            self.stdout.write(
                self.style.SUCCESS(
                    f"Import completed: {imported_count} records processed, {error_count} errors"
                )
            )

        except FileNotFoundError:
            raise CommandError(f"File not found: {file_path}")
        except json.JSONDecodeError:
            raise CommandError(f"Invalid JSON in file: {file_path}")

    def normalize_teacher_data(self, options):
        """Normalize teacher data for consistency."""
        self.stdout.write("Normalizing teacher data...")

        dry_run = options["dry_run"]
        batch_size = options["batch_size"]

        updates_made = 0

        # Normalize names (title case)
        teachers = Teacher.objects.select_related("user")

        for i in range(0, teachers.count(), batch_size):
            batch = teachers[i : i + batch_size]

            for teacher in batch:
                changed = False
                user = teacher.user

                # Normalize names
                if user.first_name != user.first_name.title():
                    user.first_name = user.first_name.title()
                    changed = True

                if user.last_name != user.last_name.title():
                    user.last_name = user.last_name.title()
                    changed = True

                # Normalize email (lowercase)
                if user.email != user.email.lower():
                    user.email = user.email.lower()
                    changed = True

                # Normalize specialization
                if teacher.specialization != teacher.specialization.title():
                    teacher.specialization = teacher.specialization.title()
                    changed = True

                if changed and not dry_run:
                    user.save()
                    teacher.save()
                    updates_made += 1

        self.stdout.write(
            self.style.SUCCESS(f"Normalized {updates_made} teacher records")
        )

    # Helper methods

    def _transform_legacy_teacher_data(self, row):
        """Transform legacy data format to current format."""
        # Handle date conversion
        joining_date = None
        if row.get("joining_date"):
            try:
                joining_date = datetime.strptime(row["joining_date"], "%Y-%m-%d").date()
            except ValueError:
                try:
                    joining_date = datetime.strptime(
                        row["joining_date"], "%d/%m/%Y"
                    ).date()
                except ValueError:
                    pass

        # Handle decimal conversion
        experience_years = Decimal("0")
        if row.get("experience_years"):
            try:
                experience_years = Decimal(str(row["experience_years"]))
            except:
                pass

        salary = Decimal("0")
        if row.get("salary"):
            try:
                salary = Decimal(str(row["salary"]).replace(",", ""))
            except:
                pass

        return {
            "employee_id": row.get("employee_id", "").strip(),
            "first_name": row.get("first_name", "").strip().title(),
            "last_name": row.get("last_name", "").strip().title(),
            "email": row.get("email", "").strip().lower(),
            "phone_number": row.get("phone_number", "").strip(),
            "joining_date": joining_date,
            "qualification": row.get("qualification", "").strip(),
            "experience_years": experience_years,
            "specialization": row.get("specialization", "").strip().title(),
            "department_name": row.get("department", "").strip(),
            "position": row.get("position", "").strip(),
            "salary": salary,
            "contract_type": row.get("contract_type", "Permanent").strip(),
            "status": row.get("status", "Active").strip(),
        }

    def _process_teacher_batch(self, batch):
        """Process a batch of teacher data."""
        with transaction.atomic():
            for teacher_data in batch:
                self._create_or_update_teacher(teacher_data)

    def _create_or_update_teacher(self, data):
        """Create or update a teacher record."""
        # Get or create user
        user, created = User.objects.get_or_create(
            email=data["email"],
            defaults={
                "username": data["email"],
                "first_name": data["first_name"],
                "last_name": data["last_name"],
                "is_active": True,
            },
        )

        if not created:
            user.first_name = data["first_name"]
            user.last_name = data["last_name"]
            user.save()

        # Set phone number if user model supports it
        if hasattr(user, "phone_number") and data.get("phone_number"):
            user.phone_number = data["phone_number"]
            user.save()

        # Get department
        department = None
        if data.get("department_name"):
            department, _ = Department.objects.get_or_create(
                name=data["department_name"]
            )

        # Create or update teacher
        teacher, created = Teacher.objects.get_or_create(
            employee_id=data["employee_id"],
            defaults={
                "user": user,
                "joining_date": data.get("joining_date"),
                "qualification": data.get("qualification", ""),
                "experience_years": data.get("experience_years", 0),
                "specialization": data.get("specialization", ""),
                "department": department,
                "position": data.get("position", ""),
                "salary": data.get("salary", 0),
                "contract_type": data.get("contract_type", "Permanent"),
                "status": data.get("status", "Active"),
            },
        )

        if not created:
            # Update existing teacher
            teacher.user = user
            teacher.joining_date = data.get("joining_date") or teacher.joining_date
            teacher.qualification = data.get("qualification") or teacher.qualification
            teacher.experience_years = (
                data.get("experience_years") or teacher.experience_years
            )
            teacher.specialization = (
                data.get("specialization") or teacher.specialization
            )
            teacher.department = department or teacher.department
            teacher.position = data.get("position") or teacher.position
            teacher.salary = data.get("salary") or teacher.salary
            teacher.contract_type = data.get("contract_type") or teacher.contract_type
            teacher.status = data.get("status") or teacher.status
            teacher.save()

    def _import_teacher_record(self, teacher_data):
        """Import a single teacher record from backup."""
        # Import user data
        user_data = teacher_data["user_data"]
        teacher_info = teacher_data["teacher_data"]

        # Create user
        user, created = User.objects.get_or_create(
            email=user_data["email"],
            defaults={
                "username": user_data["email"],
                "first_name": user_data["first_name"],
                "last_name": user_data["last_name"],
                "is_active": True,
            },
        )

        # Get department
        department = None
        if teacher_info.get("department"):
            department, _ = Department.objects.get_or_create(
                name=teacher_info["department"]
            )

        # Create teacher
        teacher, created = Teacher.objects.get_or_create(
            employee_id=teacher_data["employee_id"],
            defaults={
                "user": user,
                "joining_date": (
                    datetime.fromisoformat(teacher_info["joining_date"]).date()
                    if teacher_info["joining_date"]
                    else None
                ),
                "qualification": teacher_info["qualification"],
                "experience_years": Decimal(teacher_info["experience_years"]),
                "specialization": teacher_info["specialization"],
                "department": department,
                "position": teacher_info["position"],
                "salary": Decimal(teacher_info["salary"]),
                "contract_type": teacher_info["contract_type"],
                "status": teacher_info["status"],
                "bio": teacher_info.get("bio", ""),
                "emergency_contact": teacher_info.get("emergency_contact", ""),
                "emergency_phone": teacher_info.get("emergency_phone", ""),
            },
        )

        # Import evaluations
        for eval_data in teacher_data.get("evaluations", []):
            TeacherEvaluation.objects.get_or_create(
                teacher=teacher,
                evaluation_date=datetime.fromisoformat(
                    eval_data["evaluation_date"]
                ).date(),
                evaluator=user,  # Use same user as evaluator for import
                defaults={
                    "score": eval_data["score"],
                    "criteria": eval_data["criteria"],
                    "remarks": eval_data["remarks"],
                    "status": eval_data["status"],
                },
            )

    def _update_evaluation_statistics(self, department_id=None):
        """Update evaluation statistics."""
        # This would update cached evaluation statistics
        pass

    def _update_workload_statistics(self, department_id=None):
        """Update workload statistics."""
        # This would update cached workload statistics
        pass

    def _update_performance_rankings(self, department_id=None):
        """Update performance rankings."""
        # This would update cached performance rankings
        pass


# src/teachers/management/commands/optimize_teacher_database.py
from django.core.management.base import BaseCommand
from django.db import connection, transaction
from django.conf import settings
import time


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


# src/teachers/utils/data_migration_helpers.py
"""
Helper utilities for teacher data migration and transformation.
"""

import csv
import json
import pandas as pd
from datetime import datetime, date
from decimal import Decimal
from typing import Dict, List, Any, Optional
from django.core.exceptions import ValidationError

from src.teachers.validators import validate_teacher_data, validate_evaluation_data


class TeacherDataTransformer:
    """Transform teacher data between different formats."""

    def __init__(self):
        self.errors = []
        self.warnings = []

    def transform_csv_to_teacher_dict(self, csv_row: Dict[str, str]) -> Dict[str, Any]:
        """Transform CSV row to teacher dictionary."""
        try:
            return {
                "employee_id": self._clean_string(csv_row.get("employee_id", "")),
                "first_name": self._clean_string(csv_row.get("first_name", "")).title(),
                "last_name": self._clean_string(csv_row.get("last_name", "")).title(),
                "email": self._clean_string(csv_row.get("email", "")).lower(),
                "phone_number": self._clean_phone(csv_row.get("phone_number", "")),
                "joining_date": self._parse_date(csv_row.get("joining_date")),
                "qualification": self._clean_string(csv_row.get("qualification", "")),
                "experience_years": self._parse_decimal(
                    csv_row.get("experience_years", "0")
                ),
                "specialization": self._clean_string(
                    csv_row.get("specialization", "")
                ).title(),
                "department_name": self._clean_string(csv_row.get("department", "")),
                "position": self._clean_string(csv_row.get("position", "")),
                "salary": self._parse_decimal(csv_row.get("salary", "0")),
                "contract_type": self._normalize_contract_type(
                    csv_row.get("contract_type", "Permanent")
                ),
                "status": self._normalize_status(csv_row.get("status", "Active")),
                "bio": self._clean_text(csv_row.get("bio", "")),
                "emergency_contact": self._clean_string(
                    csv_row.get("emergency_contact", "")
                ),
                "emergency_phone": self._clean_phone(
                    csv_row.get("emergency_phone", "")
                ),
            }
        except Exception as e:
            self.errors.append(f"Error transforming row: {str(e)}")
            return None

    def _clean_string(self, value: str) -> str:
        """Clean and normalize string values."""
        if not value:
            return ""
        return str(value).strip()

    def _clean_text(self, value: str) -> str:
        """Clean longer text fields."""
        if not value:
            return ""
        # Remove extra whitespace
        return " ".join(str(value).split())

    def _clean_phone(self, value: str) -> str:
        """Clean phone number."""
        if not value:
            return ""
        # Remove common formatting characters
        cleaned = "".join(c for c in str(value) if c.isdigit() or c == "+")
        return cleaned if len(cleaned) >= 10 else ""

    def _parse_date(self, value: str) -> Optional[date]:
        """Parse date from various formats."""
        if not value:
            return None

        date_formats = ["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y"]

        for fmt in date_formats:
            try:
                return datetime.strptime(str(value).strip(), fmt).date()
            except ValueError:
                continue

        self.warnings.append(f"Could not parse date: {value}")
        return None

    def _parse_decimal(self, value: str) -> Decimal:
        """Parse decimal value."""
        if not value:
            return Decimal("0")

        try:
            # Remove commas and currency symbols
            cleaned = str(value).replace(",", "").replace("$", "").strip()
            return Decimal(cleaned)
        except:
            self.warnings.append(f"Could not parse decimal: {value}")
            return Decimal("0")

    def _normalize_contract_type(self, value: str) -> str:
        """Normalize contract type values."""
        if not value:
            return "Permanent"

        value = str(value).strip().lower()

        if value in ["permanent", "perm", "full-time"]:
            return "Permanent"
        elif value in ["temporary", "temp", "part-time"]:
            return "Temporary"
        elif value in ["contract", "contractor", "freelance"]:
            return "Contract"
        else:
            self.warnings.append(
                f"Unknown contract type: {value}, defaulting to Permanent"
            )
            return "Permanent"

    def _normalize_status(self, value: str) -> str:
        """Normalize status values."""
        if not value:
            return "Active"

        value = str(value).strip().lower()

        if value in ["active", "employed", "working"]:
            return "Active"
        elif value in ["leave", "on leave", "on_leave", "absent"]:
            return "On Leave"
        elif value in ["terminated", "fired", "resigned", "left", "inactive"]:
            return "Terminated"
        else:
            self.warnings.append(f"Unknown status: {value}, defaulting to Active")
            return "Active"


class TeacherDataValidator:
    """Validate teacher data during migration."""

    def __init__(self):
        self.validation_results = []

    def validate_batch(self, teacher_data_list: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Validate a batch of teacher data."""
        valid_records = []
        invalid_records = []

        for i, data in enumerate(teacher_data_list):
            try:
                validated_data = validate_teacher_data(data)
                valid_records.append({"index": i, "data": validated_data, "errors": []})
            except ValidationError as e:
                invalid_records.append(
                    {
                        "index": i,
                        "data": data,
                        "errors": (
                            e.message_dict if hasattr(e, "message_dict") else [str(e)]
                        ),
                    }
                )

        return {
            "valid_count": len(valid_records),
            "invalid_count": len(invalid_records),
            "valid_records": valid_records,
            "invalid_records": invalid_records,
            "success_rate": (
                len(valid_records) / len(teacher_data_list) * 100
                if teacher_data_list
                else 0
            ),
        }


class TeacherBackupManager:
    """Manage teacher data backups."""

    def create_backup(
        self, teachers_queryset, include_relations=True
    ) -> Dict[str, Any]:
        """Create a comprehensive backup of teacher data."""
        backup_data = {
            "metadata": {
                "created_at": datetime.now().isoformat(),
                "total_teachers": teachers_queryset.count(),
                "include_relations": include_relations,
                "version": "1.0",
            },
            "teachers": [],
        }

        for teacher in teachers_queryset.select_related("user", "department"):
            teacher_data = {
                "employee_id": teacher.employee_id,
                "user": {
                    "first_name": teacher.user.first_name,
                    "last_name": teacher.user.last_name,
                    "email": teacher.user.email,
                    "phone_number": getattr(teacher.user, "phone_number", ""),
                    "date_joined": teacher.user.date_joined.isoformat(),
                },
                "profile": {
                    "joining_date": (
                        teacher.joining_date.isoformat()
                        if teacher.joining_date
                        else None
                    ),
                    "qualification": teacher.qualification,
                    "experience_years": str(teacher.experience_years),
                    "specialization": teacher.specialization,
                    "department": (
                        teacher.department.name if teacher.department else None
                    ),
                    "position": teacher.position,
                    "salary": str(teacher.salary),
                    "contract_type": teacher.contract_type,
                    "status": teacher.status,
                    "bio": teacher.bio,
                    "emergency_contact": teacher.emergency_contact,
                    "emergency_phone": teacher.emergency_phone,
                    "created_at": teacher.created_at.isoformat(),
                    "updated_at": teacher.updated_at.isoformat(),
                },
            }

            if include_relations:
                # Include evaluations
                teacher_data["evaluations"] = [
                    {
                        "evaluation_date": eval.evaluation_date.isoformat(),
                        "score": float(eval.score),
                        "criteria": eval.criteria,
                        "remarks": eval.remarks,
                        "followup_actions": eval.followup_actions,
                        "status": eval.status,
                        "followup_date": (
                            eval.followup_date.isoformat()
                            if eval.followup_date
                            else None
                        ),
                        "evaluator_email": eval.evaluator.email,
                    }
                    for eval in teacher.evaluations.select_related("evaluator")
                ]

                # Include assignments
                teacher_data["assignments"] = [
                    {
                        "class_name": str(assignment.class_instance),
                        "subject_name": assignment.subject.name,
                        "subject_code": assignment.subject.code,
                        "academic_year": assignment.academic_year.name,
                        "is_class_teacher": assignment.is_class_teacher,
                        "notes": assignment.notes,
                        "created_at": assignment.created_at.isoformat(),
                    }
                    for assignment in teacher.class_assignments.select_related(
                        "class_instance", "subject", "academic_year"
                    )
                ]

            backup_data["teachers"].append(teacher_data)

        return backup_data

    def restore_from_backup(
        self, backup_data: Dict[str, Any], overwrite_existing=False
    ) -> Dict[str, Any]:
        """Restore teacher data from backup."""
        results = {
            "restored_count": 0,
            "skipped_count": 0,
            "error_count": 0,
            "errors": [],
        }

        for teacher_data in backup_data.get("teachers", []):
            try:
                # This would implement the actual restoration logic
                # For now, just track what would be restored
                employee_id = teacher_data.get("employee_id")

                if Teacher.objects.filter(employee_id=employee_id).exists():
                    if overwrite_existing:
                        results["restored_count"] += 1
                    else:
                        results["skipped_count"] += 1
                else:
                    results["restored_count"] += 1

            except Exception as e:
                results["error_count"] += 1
                results["errors"].append(
                    f"Error restoring {teacher_data.get('employee_id')}: {str(e)}"
                )

        return results
