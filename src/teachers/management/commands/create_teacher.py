# teachers/management/commands/create_teacher.py

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.db import transaction

from src.accounts.services import AuthenticationService
from teachers.models import Teacher
from teachers.views import create_teacher_with_defaults

User = get_user_model()


class Command(BaseCommand):
    help = "Create a new teacher with auto-generated credentials"

    def add_arguments(self, parser):
        # Required arguments
        parser.add_argument("first_name", type=str, help="Teacher first name")
        parser.add_argument("last_name", type=str, help="Teacher last name")
        parser.add_argument("email", type=str, help="Teacher email address")

        # Optional arguments
        parser.add_argument("--phone", type=str, help="Teacher phone number")
        parser.add_argument(
            "--username",
            type=str,
            help="Custom username (auto-generated if not provided)",
        )
        parser.add_argument(
            "--password",
            type=str,
            help="Custom password (auto-generated if not provided)",
        )
        parser.add_argument(
            "--employee-id",
            type=str,
            help="Custom employee ID (auto-generated if not provided)",
        )
        parser.add_argument(
            "--qualification", type=str, default="", help="Teacher qualification"
        )
        parser.add_argument(
            "--experience", type=float, default=0, help="Years of experience"
        )
        parser.add_argument(
            "--specialization",
            type=str,
            default="",
            help="Teacher specialization/subject area",
        )
        parser.add_argument(
            "--position", type=str, default="Teacher", help="Teacher position"
        )
        parser.add_argument("--salary", type=float, default=0, help="Teacher salary")
        parser.add_argument(
            "--contract-type",
            type=str,
            default="Permanent",
            choices=["Permanent", "Temporary", "Contract"],
            help="Contract type",
        )
        parser.add_argument("--department", type=str, help="Department name")
        parser.add_argument(
            "--no-email", action="store_true", help="Do not send welcome email"
        )
        parser.add_argument(
            "--bulk-file", type=str, help="CSV file path for bulk teacher creation"
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be created without actually creating",
        )

    def handle(self, *args, **options):
        """Handle the command execution"""

        if options["bulk_file"]:
            self.handle_bulk_creation(options["bulk_file"], options)
        else:
            self.handle_single_creation(options)

    def handle_single_creation(self, options):
        """Create a single teacher"""

        if options["dry_run"]:
            self.stdout.write(
                self.style.WARNING("DRY RUN - No actual changes will be made")
            )

        try:
            # Get department if specified
            department = None
            if options.get("department"):
                from src.academics.models import Department

                try:
                    department = Department.objects.get(name=options["department"])
                except Department.DoesNotExist:
                    raise CommandError(
                        f"Department '{options['department']}' not found"
                    )

            # Prepare teacher data
            teacher_data = {
                "qualification": options["qualification"],
                "experience_years": options["experience"],
                "specialization": options["specialization"],
                "position": options["position"],
                "salary": options["salary"],
                "contract_type": options["contract_type"],
                "department": department,
                "send_welcome_email": not options["no_email"],
            }

            # Add custom fields if provided
            if options.get("employee_id"):
                teacher_data["employee_id"] = options["employee_id"]

            if options["dry_run"]:
                self.show_dry_run_info(options, teacher_data)
                return

            with transaction.atomic():
                # Create teacher using utility function
                teacher = create_teacher_with_defaults(
                    first_name=options["first_name"],
                    last_name=options["last_name"],
                    email=options["email"],
                    phone_number=options.get("phone"),
                    **teacher_data,
                )

                # Output results
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Successfully created teacher: {teacher.user.get_full_name()}"
                    )
                )
                self.stdout.write(f"Username: {teacher.user.username}")
                self.stdout.write(f"Employee ID: {teacher.employee_id}")
                self.stdout.write(f"Email: {teacher.user.email}")

                if not options["no_email"]:
                    self.stdout.write(
                        self.style.WARNING("Welcome email sent with login credentials!")
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING(
                            "No email sent. Make sure to provide login credentials manually."
                        )
                    )

        except Exception as e:
            raise CommandError(f"Error creating teacher: {e}")

    def handle_bulk_creation(self, file_path, options):
        """Create multiple teachers from CSV file"""

        import csv

        if options["dry_run"]:
            self.stdout.write(
                self.style.WARNING("DRY RUN - No actual changes will be made")
            )

        try:
            with open(file_path, "r", encoding="utf-8") as csvfile:
                reader = csv.DictReader(csvfile)

                created_count = 0
                errors = []
                teachers_to_create = []

                # First pass: validate all data
                for row_num, row in enumerate(reader, start=2):
                    try:
                        # Validate required fields
                        required_fields = ["first_name", "last_name", "email"]
                        missing_fields = [
                            f for f in required_fields if not row.get(f, "").strip()
                        ]

                        if missing_fields:
                            errors.append(
                                f"Row {row_num}: Missing required fields: {', '.join(missing_fields)}"
                            )
                            continue

                        # Prepare teacher data
                        teacher_data = {
                            "first_name": row["first_name"].strip(),
                            "last_name": row["last_name"].strip(),
                            "email": row["email"].strip(),
                            "phone_number": row.get("phone_number", "").strip(),
                            "qualification": row.get("qualification", ""),
                            "experience_years": float(
                                row.get("experience_years", 0) or 0
                            ),
                            "specialization": row.get("specialization", ""),
                            "position": row.get("position", "Teacher"),
                            "salary": float(row.get("salary", 0) or 0),
                            "contract_type": row.get("contract_type", "Permanent"),
                            "send_welcome_email": not options["no_email"],
                        }

                        teachers_to_create.append((row_num, teacher_data))

                    except Exception as e:
                        errors.append(f"Row {row_num}: {str(e)}")
                        continue

                if options["dry_run"]:
                    self.stdout.write(
                        f"Would create {len(teachers_to_create)} teachers:"
                    )
                    for row_num, data in teachers_to_create[:5]:  # Show first 5
                        self.stdout.write(
                            f"  - {data['first_name']} {data['last_name']} ({data['email']})"
                        )
                    if len(teachers_to_create) > 5:
                        self.stdout.write(
                            f"  ... and {len(teachers_to_create) - 5} more"
                        )
                    return

                # Second pass: create teachers
                with transaction.atomic():
                    for row_num, teacher_data in teachers_to_create:
                        try:
                            teacher = create_teacher_with_defaults(**teacher_data)
                            created_count += 1

                            self.stdout.write(
                                f"Created: {teacher.user.get_full_name()} (Username: {teacher.user.username}, ID: {teacher.employee_id})"
                            )

                        except Exception as e:
                            errors.append(f"Row {row_num}: {str(e)}")
                            continue

                # Output results
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Successfully created {created_count} teacher(s)"
                    )
                )

                if errors:
                    self.stdout.write(
                        self.style.ERROR(f"Encountered {len(errors)} error(s):")
                    )
                    for error in errors:
                        self.stdout.write(self.style.ERROR(f"  - {error}"))

        except FileNotFoundError:
            raise CommandError(f"CSV file not found: {file_path}")
        except Exception as e:
            raise CommandError(f"Error processing CSV file: {e}")

    def show_dry_run_info(self, options, teacher_data):
        """Show what would be created in dry run mode"""
        self.stdout.write("Would create teacher with:")
        self.stdout.write(f'  Name: {options["first_name"]} {options["last_name"]}')
        self.stdout.write(f'  Email: {options["email"]}')

        if options.get("phone"):
            self.stdout.write(f'  Phone: {options["phone"]}')

        # Show what would be auto-generated
        self.stdout.write("Auto-generated:")

        if not options.get("username"):
            base_username = (
                f"{options['first_name'].lower()}.{options['last_name'].lower()}"
            )
            base_username = "".join(c for c in base_username if c.isalnum() or c == "_")
            self.stdout.write(f"  Username: {base_username} (or similar if taken)")
        else:
            self.stdout.write(f'  Username: {options["username"]} (custom)')

        if not options.get("employee_id"):
            import datetime

            current_year = datetime.datetime.now().year
            self.stdout.write(f"  Employee ID: TCH{current_year}XXXX (auto-numbered)")
        else:
            self.stdout.write(f'  Employee ID: {options["employee_id"]} (custom)')

        if not options.get("password"):
            self.stdout.write("  Password: Auto-generated secure password")
        else:
            self.stdout.write("  Password: Custom password provided")

        self.stdout.write(f'  Send email: {not options["no_email"]}')


"""
Usage Examples:

1. Create a single teacher with auto-generated credentials:
   python manage.py create_teacher "John" "Smith" "john.smith@school.edu" --phone "+1234567890"

2. Create a teacher with custom details:
   python manage.py create_teacher "Jane" "Doe" "jane.doe@school.edu" \
     --qualification "M.Ed Mathematics" \
     --experience 5 \
     --specialization "Mathematics" \
     --salary 50000 \
     --department "Mathematics"

3. Dry run to see what would be created:
   python manage.py create_teacher "Test" "User" "test@school.edu" --dry-run

4. Create without sending email:
   python manage.py create_teacher "Bob" "Wilson" "bob@school.edu" --no-email

5. Bulk create from CSV:
   python manage.py create_teacher dummy dummy dummy --bulk-file teachers.csv

6. Bulk create dry run:
   python manage.py create_teacher dummy dummy dummy --bulk-file teachers.csv --dry-run

CSV format for bulk creation:
first_name,last_name,email,phone_number,qualification,experience_years,specialization,position,salary,contract_type
John,Smith,john.smith@school.edu,+1234567890,B.Ed Science,3,Physics,Teacher,45000,Permanent
Jane,Doe,jane.doe@school.edu,+1987654321,M.Ed Mathematics,5,Mathematics,Senior Teacher,55000,Permanent
Bob,Wilson,bob.wilson@school.edu,+1122334455,B.A English,2,English Literature,Teacher,40000,Temporary
"""
