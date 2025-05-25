# src/teachers/management/commands/calculate_teacher_analytics.py
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.db.models import Avg, Count
from datetime import datetime, timedelta

from src.teachers.models import Teacher, TeacherEvaluation
from src.teachers.services.analytics_service import TeacherAnalyticsService
from src.courses.models import AcademicYear, Department


class Command(BaseCommand):
    help = "Calculate and update teacher analytics data"

    def add_arguments(self, parser):
        parser.add_argument(
            "--academic-year",
            type=str,
            help="Specific academic year ID to calculate analytics for",
        )
        parser.add_argument(
            "--department",
            type=str,
            help="Specific department ID to calculate analytics for",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Force recalculation even if data exists",
        )
        parser.add_argument("--verbose", action="store_true", help="Verbose output")

    def handle(self, *args, **options):
        start_time = timezone.now()

        academic_year_id = options.get("academic_year")
        department_id = options.get("department")
        force_recalc = options.get("force", False)
        verbose = options.get("verbose", False)

        try:
            # Get academic year
            if academic_year_id:
                try:
                    academic_year = AcademicYear.objects.get(id=academic_year_id)
                except AcademicYear.DoesNotExist:
                    raise CommandError(
                        f"Academic year with ID {academic_year_id} does not exist"
                    )
            else:
                academic_year = AcademicYear.objects.filter(is_current=True).first()
                if not academic_year:
                    raise CommandError("No current academic year found")

            # Get department if specified
            department = None
            if department_id:
                try:
                    department = Department.objects.get(id=department_id)
                except Department.DoesNotExist:
                    raise CommandError(
                        f"Department with ID {department_id} does not exist"
                    )

            self.stdout.write(
                self.style.SUCCESS(
                    f"Starting analytics calculation for {academic_year.name}"
                )
            )

            if department:
                self.stdout.write(f"Department: {department.name}")

            # Calculate performance overview
            if verbose:
                self.stdout.write("Calculating performance overview...")

            performance_data = TeacherAnalyticsService.get_performance_overview(
                academic_year=academic_year, department_id=department_id
            )

            # Calculate workload analysis
            if verbose:
                self.stdout.write("Calculating workload analysis...")

            workload_data = TeacherAnalyticsService.get_workload_analysis(
                academic_year=academic_year
            )

            # Calculate evaluation trends
            if verbose:
                self.stdout.write("Calculating evaluation trends...")

            trends_data = TeacherAnalyticsService.get_evaluation_trends(
                months=12, department_id=department_id
            )

            # Calculate departmental comparison
            if verbose:
                self.stdout.write("Calculating departmental comparison...")

            dept_comparison = TeacherAnalyticsService.get_departmental_comparison()

            # Calculate retention analysis
            if verbose:
                self.stdout.write("Calculating retention analysis...")

            retention_data = TeacherAnalyticsService.get_retention_analysis()

            # Calculate hiring analysis
            if verbose:
                self.stdout.write("Calculating hiring analysis...")

            hiring_data = TeacherAnalyticsService.get_hiring_analysis()

            # Output summary
            end_time = timezone.now()
            execution_time = (end_time - start_time).total_seconds()

            self.stdout.write(
                self.style.SUCCESS(f"\nAnalytics calculation completed successfully!")
            )

            self.stdout.write(f"Execution time: {execution_time:.2f} seconds")
            self.stdout.write(f"Academic year: {academic_year.name}")

            if department:
                self.stdout.write(f"Department: {department.name}")

            # Display key metrics
            base_stats = performance_data.get("base_stats", {})
            self.stdout.write("\n--- Key Metrics ---")
            self.stdout.write(f"Total teachers: {base_stats.get('total_teachers', 0)}")
            self.stdout.write(
                f"Average experience: {base_stats.get('avg_experience', 0):.1f} years"
            )
            self.stdout.write(
                f"Average evaluation score: {base_stats.get('avg_evaluation_score', 0):.1f}%"
            )
            self.stdout.write(
                f"High performers: {base_stats.get('high_performers', 0)}"
            )
            self.stdout.write(
                f"Need improvement: {base_stats.get('needs_improvement', 0)}"
            )

            workload_stats = workload_data.get("workload_stats", {})
            self.stdout.write("\n--- Workload Distribution ---")
            self.stdout.write(f"Overloaded: {workload_stats.get('overloaded', 0)}")
            self.stdout.write(f"Balanced: {workload_stats.get('balanced', 0)}")
            self.stdout.write(
                f"Underutilized: {workload_stats.get('underutilized', 0)}"
            )

        except Exception as e:
            raise CommandError(f"Error calculating analytics: {str(e)}")


# src/teachers/management/commands/generate_teacher_sample_data.py
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.utils import timezone
from faker import Faker
import random
from datetime import date, timedelta

from src.teachers.models import Teacher, TeacherEvaluation, TeacherClassAssignment
from src.courses.models import Department, Subject, Class, AcademicYear
from src.accounts.models import UserRole, UserRoleAssignment

User = get_user_model()
fake = Faker()


class Command(BaseCommand):
    help = "Generate sample teacher data for testing and development"

    def add_arguments(self, parser):
        parser.add_argument(
            "--count",
            type=int,
            default=50,
            help="Number of teachers to create (default: 50)",
        )
        parser.add_argument(
            "--with-evaluations",
            action="store_true",
            help="Generate evaluations for teachers",
        )
        parser.add_argument(
            "--with-assignments",
            action="store_true",
            help="Generate class assignments for teachers",
        )
        parser.add_argument(
            "--clear-existing",
            action="store_true",
            help="Clear existing teacher data before generating new data",
        )

    def handle(self, *args, **options):
        count = options["count"]
        with_evaluations = options["with_evaluations"]
        with_assignments = options["with_assignments"]
        clear_existing = options["clear_existing"]

        if clear_existing:
            self.stdout.write("Clearing existing teacher data...")
            Teacher.objects.all().delete()
            self.stdout.write(self.style.WARNING("Existing teacher data cleared"))

        # Ensure we have departments
        if not Department.objects.exists():
            self.create_sample_departments()

        # Get teacher role
        teacher_role, created = UserRole.objects.get_or_create(
            name="Teacher",
            defaults={"description": "Teaching staff with classroom responsibilities"},
        )

        self.stdout.write(f"Generating {count} teachers...")

        teachers_created = 0
        evaluations_created = 0
        assignments_created = 0

        for i in range(count):
            try:
                # Create user
                user = User.objects.create_user(
                    username=fake.unique.email(),
                    email=fake.unique.email(),
                    first_name=fake.first_name(),
                    last_name=fake.last_name(),
                    is_active=True,
                )

                # Add phone number if User model supports it
                if hasattr(user, "phone_number"):
                    user.phone_number = fake.phone_number()
                    user.save()

                # Create teacher
                teacher = Teacher.objects.create(
                    user=user,
                    employee_id=f"T{fake.unique.random_number(digits=6):06d}",
                    joining_date=fake.date_between(start_date="-10y", end_date="today"),
                    qualification=fake.random_element(
                        [
                            "Bachelor of Education",
                            "Master of Education",
                            "PhD in Education",
                            "Bachelor of Arts",
                            "Master of Arts",
                            "Bachelor of Science",
                            "Master of Science",
                            "Professional Teaching Certificate",
                        ]
                    ),
                    experience_years=fake.random_int(min=0, max=30),
                    specialization=fake.random_element(
                        [
                            "Mathematics",
                            "Science",
                            "English",
                            "History",
                            "Geography",
                            "Physics",
                            "Chemistry",
                            "Biology",
                            "Computer Science",
                            "Art",
                            "Music",
                            "Physical Education",
                            "Language Arts",
                        ]
                    ),
                    department=fake.random_element(Department.objects.all()),
                    position=fake.random_element(
                        [
                            "Teacher",
                            "Senior Teacher",
                            "Subject Coordinator",
                            "Department Head",
                            "Assistant Principal",
                        ]
                    ),
                    salary=fake.random_int(min=30000, max=80000),
                    contract_type=fake.random_element(
                        ["Permanent", "Temporary", "Contract"]
                    ),
                    status=fake.random_element(
                        elements=("Active", "Active", "Active", "On Leave"),
                        weights=(85, 85, 85, 15),
                    ),
                    bio=(
                        fake.text(max_nb_chars=500)
                        if fake.boolean(chance_of_getting_true=60)
                        else ""
                    ),
                    emergency_contact=(
                        fake.name() if fake.boolean(chance_of_getting_true=80) else ""
                    ),
                    emergency_phone=(
                        fake.phone_number()
                        if fake.boolean(chance_of_getting_true=80)
                        else ""
                    ),
                )

                # Assign teacher role
                UserRoleAssignment.objects.create(
                    user=user,
                    role=teacher_role,
                    assigned_by=User.objects.filter(is_staff=True).first() or user,
                    assigned_date=timezone.now().date(),
                )

                teachers_created += 1

                # Generate evaluations if requested
                if with_evaluations:
                    eval_count = fake.random_int(min=1, max=5)
                    for _ in range(eval_count):
                        evaluation = self.create_teacher_evaluation(teacher)
                        if evaluation:
                            evaluations_created += 1

                # Generate assignments if requested
                if with_assignments:
                    assignment_count = fake.random_int(min=1, max=4)
                    for _ in range(assignment_count):
                        assignment = self.create_teacher_assignment(teacher)
                        if assignment:
                            assignments_created += 1

                if (i + 1) % 10 == 0:
                    self.stdout.write(f"Created {i + 1} teachers...")

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"Error creating teacher {i + 1}: {str(e)}")
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"\nSample data generation completed!\n"
                f"Teachers created: {teachers_created}\n"
                f"Evaluations created: {evaluations_created}\n"
                f"Assignments created: {assignments_created}"
            )
        )

    def create_sample_departments(self):
        """Create sample departments if none exist."""
        departments = [
            {
                "name": "Mathematics",
                "description": "Mathematics and Statistics Department",
            },
            {"name": "Science", "description": "Natural Sciences Department"},
            {
                "name": "English",
                "description": "English Language and Literature Department",
            },
            {
                "name": "Social Studies",
                "description": "History, Geography, and Social Sciences",
            },
            {"name": "Arts", "description": "Visual and Performing Arts Department"},
            {
                "name": "Physical Education",
                "description": "Sports and Physical Education",
            },
            {"name": "Technology", "description": "Computer Science and Technology"},
        ]

        for dept_data in departments:
            Department.objects.get_or_create(**dept_data)

        self.stdout.write("Created sample departments")

    def create_teacher_evaluation(self, teacher):
        """Create a sample evaluation for a teacher."""
        try:
            # Random evaluation date within the last 2 years
            eval_date = fake.date_between(start_date="-2y", end_date="today")

            # Generate criteria scores
            criteria = {}
            total_score = 0
            max_total = 0

            for criterion in TeacherEvaluation.EVALUATION_CATEGORIES:
                max_score = 10
                score = fake.random_int(min=5, max=10)  # Generally positive scores

                criteria[criterion] = {
                    "score": score,
                    "max_score": max_score,
                    "comments": (
                        fake.text(max_nb_chars=100)
                        if fake.boolean(chance_of_getting_true=60)
                        else ""
                    ),
                }

                total_score += score
                max_total += max_score

            # Calculate percentage
            percentage_score = (total_score / max_total * 100) if max_total > 0 else 0

            # Create evaluator (random admin user or create one)
            evaluators = User.objects.filter(is_staff=True)
            if not evaluators.exists():
                evaluator = User.objects.create_user(
                    username="admin_evaluator",
                    email="admin@school.edu",
                    first_name="Admin",
                    last_name="Evaluator",
                    is_staff=True,
                )
            else:
                evaluator = fake.random_element(evaluators)

            evaluation = TeacherEvaluation.objects.create(
                teacher=teacher,
                evaluator=evaluator,
                evaluation_date=eval_date,
                criteria=criteria,
                score=percentage_score,
                remarks=fake.text(max_nb_chars=300),
                followup_actions=(
                    fake.text(max_nb_chars=200) if percentage_score < 70 else ""
                ),
                status=fake.random_element(["submitted", "reviewed", "closed"]),
                followup_date=(
                    eval_date + timedelta(days=30) if percentage_score < 70 else None
                ),
            )

            return evaluation

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"Error creating evaluation for {teacher}: {str(e)}")
            )
            return None

    def create_teacher_assignment(self, teacher):
        """Create a sample class assignment for a teacher."""
        try:
            # Get current academic year or create one
            academic_year = AcademicYear.objects.filter(is_current=True).first()
            if not academic_year:
                academic_year = AcademicYear.objects.create(
                    name="2024-2025",
                    start_date=date(2024, 9, 1),
                    end_date=date(2025, 6, 30),
                    is_current=True,
                )

            # Get or create subjects and classes
            if not Subject.objects.exists():
                self.create_sample_subjects()

            if not Class.objects.exists():
                self.create_sample_classes(academic_year)

            subject = fake.random_element(Subject.objects.all())
            class_instance = fake.random_element(
                Class.objects.filter(academic_year=academic_year)
            )

            # Check if assignment already exists
            if TeacherClassAssignment.objects.filter(
                teacher=teacher,
                class_instance=class_instance,
                subject=subject,
                academic_year=academic_year,
            ).exists():
                return None

            assignment = TeacherClassAssignment.objects.create(
                teacher=teacher,
                class_instance=class_instance,
                subject=subject,
                academic_year=academic_year,
                is_class_teacher=fake.boolean(
                    chance_of_getting_true=20
                ),  # 20% chance of being class teacher
                notes=(
                    fake.text(max_nb_chars=100)
                    if fake.boolean(chance_of_getting_true=30)
                    else ""
                ),
            )

            return assignment

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"Error creating assignment for {teacher}: {str(e)}")
            )
            return None

    def create_sample_subjects(self):
        """Create sample subjects."""
        subjects = [
            {"name": "Mathematics", "code": "MATH001"},
            {"name": "English", "code": "ENG001"},
            {"name": "Science", "code": "SCI001"},
            {"name": "History", "code": "HIST001"},
            {"name": "Geography", "code": "GEO001"},
            {"name": "Physics", "code": "PHY001"},
            {"name": "Chemistry", "code": "CHEM001"},
            {"name": "Biology", "code": "BIO001"},
            {"name": "Computer Science", "code": "CS001"},
            {"name": "Art", "code": "ART001"},
            {"name": "Music", "code": "MUS001"},
            {"name": "Physical Education", "code": "PE001"},
        ]

        department = Department.objects.first()
        for subject_data in subjects:
            Subject.objects.get_or_create(
                **subject_data, defaults={"department": department}
            )

    def create_sample_classes(self, academic_year):
        """Create sample classes."""
        from src.courses.models import Grade, Section

        # Create sections if they don't exist
        if not Section.objects.exists():
            sections = [
                {"name": "Primary", "description": "Primary School"},
                {"name": "Secondary", "description": "Secondary School"},
            ]
            for section_data in sections:
                Section.objects.get_or_create(**section_data)

        # Create grades if they don't exist
        if not Grade.objects.exists():
            primary_section = Section.objects.get(name="Primary")
            secondary_section = Section.objects.get(name="Secondary")

            grades = [
                {"name": "Grade 1", "section": primary_section, "order_sequence": 1},
                {"name": "Grade 2", "section": primary_section, "order_sequence": 2},
                {"name": "Grade 3", "section": primary_section, "order_sequence": 3},
                {"name": "Grade 4", "section": primary_section, "order_sequence": 4},
                {"name": "Grade 5", "section": primary_section, "order_sequence": 5},
                {"name": "Grade 6", "section": secondary_section, "order_sequence": 6},
                {"name": "Grade 7", "section": secondary_section, "order_sequence": 7},
                {"name": "Grade 8", "section": secondary_section, "order_sequence": 8},
            ]

            for grade_data in grades:
                Grade.objects.get_or_create(**grade_data)

        # Create classes
        class_names = ["A", "B", "C", "D"]
        grades = Grade.objects.all()

        for grade in grades:
            for class_name in class_names:
                Class.objects.get_or_create(
                    grade=grade,
                    name=class_name,
                    academic_year=academic_year,
                    defaults={
                        "room_number": f"{grade.order_sequence}{class_name}1",
                        "capacity": fake.random_int(min=25, max=35),
                    },
                )
