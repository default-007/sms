from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management.base import BaseCommand
from django.db import transaction

from students.models import Parent, Student, StudentParentRelation

User = get_user_model()


class Command(BaseCommand):
    help = "Clean up student data - remove duplicates, orphaned records, etc."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be cleaned without making changes",
        )
        parser.add_argument(
            "--clean-duplicates",
            action="store_true",
            help="Remove duplicate student records",
        )
        parser.add_argument(
            "--clean-orphaned",
            action="store_true",
            help="Remove orphaned user accounts",
        )
        parser.add_argument(
            "--fix-relationships",
            action="store_true",
            help="Fix inconsistent parent-student relationships",
        )
        parser.add_argument(
            "--clear-cache", action="store_true", help="Clear all student-related cache"
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        if dry_run:
            self.stdout.write(
                self.style.WARNING("DRY RUN MODE - No changes will be made")
            )

        if options["clean_duplicates"]:
            self.clean_duplicate_students(dry_run)

        if options["clean_orphaned"]:
            self.clean_orphaned_users(dry_run)

        if options["fix_relationships"]:
            self.fix_relationships(dry_run)

        if options["clear_cache"]:
            self.clear_student_cache(dry_run)

        self.stdout.write(self.style.SUCCESS("Cleanup completed!"))

    def clean_duplicate_students(self, dry_run=False):
        """Find and remove duplicate student records"""
        self.stdout.write("Checking for duplicate students...")

        # Find students with same admission number
        admission_duplicates = {}
        for student in Student.objects.all():
            if student.admission_number in admission_duplicates:
                admission_duplicates[student.admission_number].append(student)
            else:
                admission_duplicates[student.admission_number] = [student]

        duplicates_found = {k: v for k, v in admission_duplicates.items() if len(v) > 1}

        if duplicates_found:
            self.stdout.write(
                f"Found {len(duplicates_found)} duplicate admission numbers:"
            )
            for admission_number, students in duplicates_found.items():
                self.stdout.write(f"  {admission_number}: {len(students)} records")

                if not dry_run:
                    # Keep the oldest record, remove others
                    oldest_student = min(students, key=lambda x: x.created_at)
                    students_to_delete = [
                        s for s in students if s.id != oldest_student.id
                    ]

                    for student in students_to_delete:
                        # Transfer relationships to oldest student
                        for relation in student.student_parent_relations.all():
                            # Check if relationship already exists
                            existing = StudentParentRelation.objects.filter(
                                student=oldest_student, parent=relation.parent
                            ).first()

                            if not existing:
                                relation.student = oldest_student
                                relation.save()
                            else:
                                relation.delete()

                        # Delete the duplicate
                        student.user.delete()  # This will cascade delete the student

                    self.stdout.write(
                        f"    Kept oldest record, removed {len(students_to_delete)} duplicates"
                    )
        else:
            self.stdout.write("No duplicate admission numbers found")

        # Find students with same email
        email_duplicates = {}
        for student in Student.objects.select_related("user"):
            email = student.user.email
            if email in email_duplicates:
                email_duplicates[email].append(student)
            else:
                email_duplicates[email] = [student]

        email_duplicates_found = {
            k: v for k, v in email_duplicates.items() if len(v) > 1
        }

        if email_duplicates_found:
            self.stdout.write(f"Found {len(email_duplicates_found)} duplicate emails:")
            for email, students in email_duplicates_found.items():
                self.stdout.write(f"  {email}: {len(students)} records")
                # Manual review required for email duplicates
                if not dry_run:
                    self.stdout.write(
                        f"    Please manually review duplicates for {email}"
                    )

    def clean_orphaned_users(self, dry_run=False):
        """Remove user accounts without corresponding student/parent profiles"""
        self.stdout.write("Checking for orphaned user accounts...")

        orphaned_users = []
        for user in User.objects.filter(is_staff=False, is_superuser=False):
            has_student = hasattr(user, "student_profile")
            has_parent = hasattr(user, "parent_profile")
            has_teacher = hasattr(user, "teacher_profile")

            if not (has_student or has_parent or has_teacher):
                orphaned_users.append(user)

        if orphaned_users:
            self.stdout.write(f"Found {len(orphaned_users)} orphaned user accounts")
            if not dry_run:
                count = 0
                for user in orphaned_users:
                    user.delete()
                    count += 1
                self.stdout.write(f"Deleted {count} orphaned user accounts")
        else:
            self.stdout.write("No orphaned user accounts found")

    def fix_relationships(self, dry_run=False):
        """Fix inconsistent parent-student relationships"""
        self.stdout.write("Checking for relationship inconsistencies...")

        issues_fixed = 0

        # Fix students with multiple primary parent contacts
        for student in Student.objects.prefetch_related("student_parent_relations"):
            primary_relations = student.student_parent_relations.filter(
                is_primary_contact=True
            )

            if primary_relations.count() > 1:
                self.stdout.write(
                    f"Student {student.admission_number} has multiple primary contacts"
                )
                if not dry_run:
                    # Keep the first one, make others non-primary
                    primary_relations.exclude(id=primary_relations.first().id).update(
                        is_primary_contact=False
                    )
                    issues_fixed += 1

        # Fix students with no primary parent contact (if they have parents)
        for student in Student.objects.prefetch_related("student_parent_relations"):
            relations = student.student_parent_relations.all()
            primary_relations = relations.filter(is_primary_contact=True)

            if relations.exists() and not primary_relations.exists():
                self.stdout.write(
                    f"Student {student.admission_number} has no primary contact"
                )
                if not dry_run:
                    # Make the first parent primary
                    first_relation = relations.first()
                    first_relation.is_primary_contact = True
                    first_relation.save()
                    issues_fixed += 1

        # Fix invalid emergency contact priorities
        for student in Student.objects.prefetch_related("student_parent_relations"):
            relations = student.student_parent_relations.all().order_by(
                "emergency_contact_priority"
            )

            # Check if priorities are sequential starting from 1
            expected_priority = 1
            for relation in relations:
                if relation.emergency_contact_priority != expected_priority:
                    self.stdout.write(
                        f"Fixing emergency priority for {student.admission_number}"
                    )
                    if not dry_run:
                        relation.emergency_contact_priority = expected_priority
                        relation.save()
                        issues_fixed += 1
                expected_priority += 1

        if issues_fixed > 0:
            self.stdout.write(f"Fixed {issues_fixed} relationship issues")
        else:
            self.stdout.write("No relationship issues found")

    def clear_student_cache(self, dry_run=False):
        """Clear all student-related cache entries"""
        self.stdout.write("Clearing student-related cache...")

        if not dry_run:
            # Get all students to clear their specific cache
            students = Student.objects.all()
            cache_keys = []

            for student in students:
                cache_keys.extend(
                    [
                        f"student_attendance_percentage_{student.id}",
                        f"student_siblings_{student.id}",
                        f"student_parents_{student.id}",
                    ]
                )

            # Clear all student cache keys
            cache.delete_many(cache_keys)

            # Clear any pattern-based cache
            cache.clear()

            self.stdout.write(f"Cleared cache for {len(students)} students")
        else:
            students_count = Student.objects.count()
            self.stdout.write(f"Would clear cache for {students_count} students")

    def validate_data_integrity(self):
        """Validate overall data integrity"""
        self.stdout.write("Validating data integrity...")

        issues = []

        # Check for students without users
        students_without_users = Student.objects.filter(user__isnull=True).count()
        if students_without_users > 0:
            issues.append(f"{students_without_users} students without user accounts")

        # Check for parents without users
        parents_without_users = Parent.objects.filter(user__isnull=True).count()
        if parents_without_users > 0:
            issues.append(f"{parents_without_users} parents without user accounts")

        # Check for relationships without valid students or parents
        invalid_relationships = StudentParentRelation.objects.filter(
            models.Q(student__isnull=True) | models.Q(parent__isnull=True)
        ).count()
        if invalid_relationships > 0:
            issues.append(f"{invalid_relationships} invalid relationships")

        # Check for students with invalid class assignments
        students_with_invalid_class = Student.objects.filter(
            current_class__isnull=False, current_class__academic_year__isnull=True
        ).count()
        if students_with_invalid_class > 0:
            issues.append(
                f"{students_with_invalid_class} students with invalid class assignments"
            )

        if issues:
            self.stdout.write(self.style.ERROR("Data integrity issues found:"))
            for issue in issues:
                self.stdout.write(f"  - {issue}")
        else:
            self.stdout.write(self.style.SUCCESS("No data integrity issues found"))

    def generate_statistics(self):
        """Generate statistics about the current data"""
        self.stdout.write("\nCurrent statistics:")
        self.stdout.write(f"Total students: {Student.objects.count()}")
        self.stdout.write(
            f'Active students: {Student.objects.filter(status="Active").count()}'
        )
        self.stdout.write(f"Total parents: {Parent.objects.count()}")
        self.stdout.write(
            f"Total relationships: {StudentParentRelation.objects.count()}"
        )
        self.stdout.write(
            f'Students with photos: {Student.objects.exclude(photo="").count()}'
        )
        self.stdout.write(
            f'Parents with workplace info: {Parent.objects.exclude(workplace="").count()}'
        )
