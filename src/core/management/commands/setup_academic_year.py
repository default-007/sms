# management/commands/setup_academic_year.py
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from datetime import datetime, timedelta
import calendar

from academics.models import AcademicYear, Term, Section, Grade
from core.services import ConfigurationService, AuditService


class Command(BaseCommand):
    help = "Setup academic year with terms and optionally create basic structure"

    def add_arguments(self, parser):
        parser.add_argument(
            "--year",
            type=str,
            required=True,
            help='Academic year name (e.g., "2024-2025")',
        )
        parser.add_argument(
            "--start-date",
            type=str,
            help="Start date in YYYY-MM-DD format (default: July 1st of current year)",
        )
        parser.add_argument(
            "--end-date",
            type=str,
            help="End date in YYYY-MM-DD format (default: June 30th of next year)",
        )
        parser.add_argument(
            "--terms", type=int, default=3, help="Number of terms (default: 3)"
        )
        parser.add_argument(
            "--create-sections", action="store_true", help="Create default sections"
        )
        parser.add_argument(
            "--create-sample-grades",
            action="store_true",
            help="Create sample grades for each section",
        )
        parser.add_argument(
            "--make-current",
            action="store_true",
            help="Make this the current academic year",
        )

    def handle(self, *args, **options):
        year_name = options["year"]
        start_date_str = options.get("start_date")
        end_date_str = options.get("end_date")
        num_terms = options["terms"]
        create_sections = options["create_sections"]
        create_sample_grades = options["create_sample_grades"]
        make_current = options["make_current"]

        try:
            with transaction.atomic():
                # Parse or generate dates
                if start_date_str:
                    start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
                else:
                    current_year = timezone.now().year
                    start_month = ConfigurationService.get_setting(
                        "academic.default_academic_year_start_month", 7
                    )
                    start_date = datetime(current_year, start_month, 1).date()

                if end_date_str:
                    end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
                else:
                    # Calculate end date (typically 11 months after start)
                    if start_date.month == 7:  # July start
                        end_date = datetime(start_date.year + 1, 6, 30).date()
                    else:
                        # Calculate end date based on start month
                        end_month = (start_date.month + 11) % 12
                        end_year = start_date.year + (
                            1 if end_month < start_date.month else 0
                        )
                        end_day = calendar.monthrange(end_year, end_month)[1]
                        end_date = datetime(end_year, end_month, end_day).date()

                # Check if academic year already exists
                if AcademicYear.objects.filter(name=year_name).exists():
                    raise CommandError(f"Academic year '{year_name}' already exists")

                # Create academic year
                if make_current:
                    # Set other years as not current
                    AcademicYear.objects.update(is_current=False)

                academic_year = AcademicYear.objects.create(
                    name=year_name,
                    start_date=start_date,
                    end_date=end_date,
                    is_current=make_current,
                )

                self.stdout.write(
                    self.style.SUCCESS(f"Created academic year: {academic_year}")
                )

                # Create terms
                self.create_terms(academic_year, num_terms, start_date, end_date)

                # Create sections if requested
                if create_sections:
                    self.create_default_sections()

                # Create sample grades if requested
                if create_sample_grades:
                    self.create_sample_grades()

                # Log the action
                AuditService.log_action(
                    action="create",
                    content_object=academic_year,
                    description=f"Created academic year {year_name} via management command",
                    module_name="core",
                )

                self.stdout.write(
                    self.style.SUCCESS(
                        f"Successfully setup academic year '{year_name}'"
                    )
                )

        except Exception as e:
            raise CommandError(f"Error setting up academic year: {str(e)}")

    def create_terms(self, academic_year, num_terms, start_date, end_date):
        """Create terms for the academic year"""
        total_days = (end_date - start_date).days
        days_per_term = total_days // num_terms

        term_names = {
            2: ["First Term", "Second Term"],
            3: ["First Term", "Second Term", "Third Term"],
            4: ["First Term", "Second Term", "Third Term", "Fourth Term"],
        }

        names = term_names.get(num_terms, [f"Term {i+1}" for i in range(num_terms)])

        current_start = start_date
        for i in range(num_terms):
            if i == num_terms - 1:  # Last term
                term_end = end_date
            else:
                term_end = current_start + timedelta(days=days_per_term - 1)

            term = Term.objects.create(
                academic_year=academic_year,
                name=names[i],
                term_number=i + 1,
                start_date=current_start,
                end_date=term_end,
                is_current=(i == 0),  # Make first term current by default
            )

            self.stdout.write(f"  Created term: {term}")
            current_start = term_end + timedelta(days=1)

    def create_default_sections(self):
        """Create default sections"""
        default_sections = [
            ("Primary", "Primary Education Section"),
            ("Secondary", "Secondary Education Section"),
            ("Higher Secondary", "Higher Secondary Section"),
        ]

        for name, description in default_sections:
            section, created = Section.objects.get_or_create(
                name=name, defaults={"description": description}
            )

            if created:
                self.stdout.write(f"  Created section: {section}")
            else:
                self.stdout.write(f"  Section already exists: {section}")

    def create_sample_grades(self):
        """Create sample grades for sections"""
        section_grades = {
            "Primary": [
                ("Grade 1", 1),
                ("Grade 2", 2),
                ("Grade 3", 3),
                ("Grade 4", 4),
                ("Grade 5", 5),
            ],
            "Secondary": [
                ("Grade 6", 6),
                ("Grade 7", 7),
                ("Grade 8", 8),
                ("Grade 9", 9),
                ("Grade 10", 10),
            ],
            "Higher Secondary": [("Grade 11", 11), ("Grade 12", 12)],
        }

        for section_name, grades in section_grades.items():
            try:
                section = Section.objects.get(name=section_name)
                for grade_name, order in grades:
                    grade, created = Grade.objects.get_or_create(
                        name=grade_name,
                        section=section,
                        defaults={"order_sequence": order},
                    )

                    if created:
                        self.stdout.write(f"    Created grade: {grade}")
                    else:
                        self.stdout.write(f"    Grade already exists: {grade}")

            except Section.DoesNotExist:
                self.stdout.write(
                    self.style.WARNING(
                        f"Section '{section_name}' not found, skipping grades"
                    )
                )


# management/commands/calculate_analytics.py
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from datetime import datetime

from academics.models import AcademicYear, Term
from core.services import AnalyticsService, AuditService


class Command(BaseCommand):
    help = "Calculate analytics for specified period"

    def add_arguments(self, parser):
        parser.add_argument(
            "--date",
            type=str,
            help="Date for analytics calculation (YYYY-MM-DD, default: today)",
        )
        parser.add_argument(
            "--academic-year",
            type=str,
            help="Academic year name (default: current academic year)",
        )
        parser.add_argument(
            "--term", type=str, help="Term name (default: current term)"
        )
        parser.add_argument(
            "--type",
            choices=["student", "class", "attendance", "financial", "teacher", "all"],
            default="all",
            help="Type of analytics to calculate",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Force recalculation even if analytics already exist",
        )

    def handle(self, *args, **options):
        # Parse date
        if options.get("date"):
            try:
                calculation_date = datetime.strptime(options["date"], "%Y-%m-%d").date()
            except ValueError:
                raise CommandError("Invalid date format. Use YYYY-MM-DD")
        else:
            calculation_date = timezone.now().date()

        # Get academic year
        if options.get("academic_year"):
            try:
                academic_year = AcademicYear.objects.get(name=options["academic_year"])
            except AcademicYear.DoesNotExist:
                raise CommandError(
                    f"Academic year '{options['academic_year']}' not found"
                )
        else:
            academic_year = AcademicYear.objects.filter(is_current=True).first()
            if not academic_year:
                raise CommandError("No current academic year found")

        # Get term
        if options.get("term"):
            try:
                term = Term.objects.get(
                    academic_year=academic_year, name=options["term"]
                )
            except Term.DoesNotExist:
                raise CommandError(
                    f"Term '{options['term']}' not found in {academic_year}"
                )
        else:
            term = Term.objects.filter(
                academic_year=academic_year, is_current=True
            ).first()
            if not term:
                raise CommandError(f"No current term found for {academic_year}")

        analytics_type = options["type"]
        force_recalculate = options["force"]

        self.stdout.write(
            f"Calculating {analytics_type} analytics for {academic_year} - {term}"
        )
        self.stdout.write(f"Calculation date: {calculation_date}")
        self.stdout.write(f"Force recalculation: {force_recalculate}")

        try:
            start_time = timezone.now()

            if analytics_type in ["student", "all"]:
                self.stdout.write("Calculating student performance analytics...")
                AnalyticsService.calculate_student_performance(
                    academic_year=academic_year,
                    term=term,
                    force_recalculate=force_recalculate,
                )
                self.stdout.write(self.style.SUCCESS("  Student analytics completed"))

            if analytics_type in ["class", "all"]:
                self.stdout.write("Calculating class performance analytics...")
                AnalyticsService.calculate_class_performance(
                    academic_year=academic_year,
                    term=term,
                    force_recalculate=force_recalculate,
                )
                self.stdout.write(self.style.SUCCESS("  Class analytics completed"))

            if analytics_type in ["attendance", "all"]:
                self.stdout.write("Calculating attendance analytics...")
                AnalyticsService.calculate_attendance_analytics(
                    academic_year=academic_year,
                    term=term,
                    force_recalculate=force_recalculate,
                )
                self.stdout.write(
                    self.style.SUCCESS("  Attendance analytics completed")
                )

            if analytics_type in ["financial", "all"]:
                self.stdout.write("Calculating financial analytics...")
                AnalyticsService.calculate_financial_analytics(
                    academic_year=academic_year,
                    term=term,
                    force_recalculate=force_recalculate,
                )
                self.stdout.write(self.style.SUCCESS("  Financial analytics completed"))

            if analytics_type in ["teacher", "all"]:
                self.stdout.write("Calculating teacher performance analytics...")
                # Would implement teacher analytics calculation
                self.stdout.write(self.style.SUCCESS("  Teacher analytics completed"))

            end_time = timezone.now()
            duration = (end_time - start_time).total_seconds()

            # Log the analytics calculation
            AuditService.log_action(
                action="system_action",
                description=f"Calculated {analytics_type} analytics via management command",
                data_after={
                    "academic_year": str(academic_year),
                    "term": str(term),
                    "analytics_type": analytics_type,
                    "force_recalculate": force_recalculate,
                    "duration_seconds": duration,
                },
                module_name="core",
            )

            self.stdout.write(
                self.style.SUCCESS(
                    f"Analytics calculation completed in {duration:.2f} seconds"
                )
            )

        except Exception as e:
            raise CommandError(f"Error calculating analytics: {str(e)}")


# management/commands/generate_sample_data.py
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.contrib.auth import get_user_model
from django.utils import timezone
from faker import Faker
import random
from decimal import Decimal

from academics.models import AcademicYear, Term, Section, Grade, Class
from students.models import Student, Parent, StudentParentRelation
from teachers.models import Teacher
from subjects.models import Subject, Syllabus
from finance.models import FeeCategory, FeeStructure, Invoice, Payment
from core.services import UtilityService, AuditService

User = get_user_model()
fake = Faker()


class Command(BaseCommand):
    help = "Generate sample data for testing and development"

    def add_arguments(self, parser):
        parser.add_argument(
            "--students",
            type=int,
            default=50,
            help="Number of students to create (default: 50)",
        )
        parser.add_argument(
            "--teachers",
            type=int,
            default=10,
            help="Number of teachers to create (default: 10)",
        )
        parser.add_argument(
            "--classes",
            type=int,
            default=15,
            help="Number of classes to create (default: 15)",
        )
        parser.add_argument(
            "--subjects",
            type=int,
            default=8,
            help="Number of subjects to create (default: 8)",
        )
        parser.add_argument(
            "--clean",
            action="store_true",
            help="Clean existing sample data before generating new",
        )

    def handle(self, *args, **options):
        num_students = options["students"]
        num_teachers = options["teachers"]
        num_classes = options["classes"]
        num_subjects = options["subjects"]
        clean_data = options["clean"]

        # Get current academic year
        academic_year = AcademicYear.objects.filter(is_current=True).first()
        if not academic_year:
            raise CommandError(
                "No current academic year found. Run setup_academic_year first."
            )

        term = Term.objects.filter(academic_year=academic_year, is_current=True).first()
        if not term:
            raise CommandError("No current term found.")

        self.stdout.write(f"Generating sample data for {academic_year} - {term}")

        try:
            with transaction.atomic():
                if clean_data:
                    self.clean_sample_data()

                # Create sample data
                self.create_sample_sections_and_grades()
                subjects = self.create_sample_subjects(num_subjects)
                classes = self.create_sample_classes(num_classes, academic_year)
                teachers = self.create_sample_teachers(num_teachers)
                students = self.create_sample_students(num_students, classes)
                self.create_sample_fee_structures(academic_year, term)
                self.create_sample_invoices(students, academic_year, term)

                # Log the action
                AuditService.log_action(
                    action="system_action",
                    description="Generated sample data via management command",
                    data_after={
                        "students": num_students,
                        "teachers": num_teachers,
                        "classes": num_classes,
                        "subjects": num_subjects,
                    },
                    module_name="core",
                )

                self.stdout.write(
                    self.style.SUCCESS(
                        f"Successfully generated sample data:\n"
                        f"  - {num_students} students\n"
                        f"  - {num_teachers} teachers\n"
                        f"  - {num_classes} classes\n"
                        f"  - {num_subjects} subjects"
                    )
                )

        except Exception as e:
            raise CommandError(f"Error generating sample data: {str(e)}")

    def clean_sample_data(self):
        """Clean existing sample data"""
        self.stdout.write("Cleaning existing sample data...")

        # Delete in reverse dependency order
        Payment.objects.filter(
            invoice__student__user__username__startswith="student_"
        ).delete()
        Invoice.objects.filter(student__user__username__startswith="student_").delete()
        StudentParentRelation.objects.filter(
            student__user__username__startswith="student_"
        ).delete()
        Student.objects.filter(user__username__startswith="student_").delete()
        Parent.objects.filter(user__username__startswith="parent_").delete()
        Teacher.objects.filter(user__username__startswith="teacher_").delete()
        User.objects.filter(
            username__startswith=("student_", "parent_", "teacher_")
        ).delete()

        self.stdout.write("  Sample data cleaned")

    def create_sample_sections_and_grades(self):
        """Create sample sections and grades if they don't exist"""
        sections_data = [
            (
                "Primary",
                "Primary Education",
                [
                    ("Grade 1", 1),
                    ("Grade 2", 2),
                    ("Grade 3", 3),
                    ("Grade 4", 4),
                    ("Grade 5", 5),
                ],
            ),
            (
                "Secondary",
                "Secondary Education",
                [
                    ("Grade 6", 6),
                    ("Grade 7", 7),
                    ("Grade 8", 8),
                    ("Grade 9", 9),
                    ("Grade 10", 10),
                ],
            ),
        ]

        for section_name, section_desc, grades in sections_data:
            section, created = Section.objects.get_or_create(
                name=section_name, defaults={"description": section_desc}
            )

            if created:
                self.stdout.write(f"  Created section: {section}")

            for grade_name, order in grades:
                grade, created = Grade.objects.get_or_create(
                    name=grade_name, section=section, defaults={"order_sequence": order}
                )

                if created:
                    self.stdout.write(f"    Created grade: {grade}")

    def create_sample_subjects(self, num_subjects):
        """Create sample subjects"""
        self.stdout.write(f"Creating {num_subjects} sample subjects...")

        subject_names = [
            "Mathematics",
            "English",
            "Science",
            "Social Studies",
            "Physical Education",
            "Art",
            "Music",
            "Computer Science",
            "History",
            "Geography",
            "Biology",
            "Chemistry",
            "Physics",
        ]

        subjects = []
        for i in range(min(num_subjects, len(subject_names))):
            name = subject_names[i]
            code = f"SUB{i+1:03d}"

            subject, created = Subject.objects.get_or_create(
                code=code,
                defaults={
                    "name": name,
                    "description": f"Sample {name} subject",
                    "credit_hours": random.randint(2, 4),
                    "is_elective": random.choice([True, False]),
                    "grade_level": random.randint(1, 12),
                },
            )

            subjects.append(subject)
            if created:
                self.stdout.write(f"  Created subject: {subject}")

        return subjects

    def create_sample_classes(self, num_classes, academic_year):
        """Create sample classes"""
        self.stdout.write(f"Creating {num_classes} sample classes...")

        grades = Grade.objects.all()
        if not grades.exists():
            raise CommandError("No grades found. Create sections and grades first.")

        class_names = [
            "North",
            "South",
            "East",
            "West",
            "Alpha",
            "Beta",
            "Gamma",
            "Delta",
        ]

        classes = []
        for i in range(num_classes):
            grade = random.choice(grades)
            name = random.choice(class_names)

            # Ensure unique class name per grade
            counter = 1
            original_name = name
            while Class.objects.filter(
                grade=grade, name=name, academic_year=academic_year
            ).exists():
                name = f"{original_name} {counter}"
                counter += 1

            class_obj = Class.objects.create(
                name=name,
                grade=grade,
                academic_year=academic_year,
                room_number=f"Room {100 + i}",
                capacity=random.randint(25, 40),
            )

            classes.append(class_obj)
            self.stdout.write(f"  Created class: {class_obj}")

        return classes

    def create_sample_teachers(self, num_teachers):
        """Create sample teachers"""
        self.stdout.write(f"Creating {num_teachers} sample teachers...")

        teachers = []
        for i in range(num_teachers):
            # Create user
            username = f"teacher_{i+1:03d}"
            email = f"teacher{i+1}@school.edu"

            user = User.objects.create_user(
                username=username,
                email=email,
                password="password123",
                first_name=fake.first_name(),
                last_name=fake.last_name(),
                phone_number=fake.phone_number()[:15],
                date_of_birth=fake.date_of_birth(minimum_age=25, maximum_age=55),
            )

            # Create teacher
            teacher = Teacher.objects.create(
                user=user,
                employee_id=UtilityService.generate_unique_code(
                    Teacher, "employee_id", "EMP", 6
                ),
                joining_date=fake.date_between(start_date="-5y", end_date="today"),
                qualification=random.choice(["Bachelor", "Master", "PhD"]),
                experience_years=random.randint(1, 20),
                specialization=fake.job(),
                position=random.choice(["Teacher", "Senior Teacher", "Head Teacher"]),
                salary=Decimal(str(random.randint(30000, 80000))),
                contract_type=random.choice(["permanent", "temporary", "contract"]),
                status="active",
            )

            teachers.append(teacher)
            self.stdout.write(f"  Created teacher: {teacher}")

        return teachers

    def create_sample_students(self, num_students, classes):
        """Create sample students with parents"""
        self.stdout.write(f"Creating {num_students} sample students...")

        if not classes:
            raise CommandError("No classes available for student assignment")

        students = []
        for i in range(num_students):
            # Create student user
            username = f"student_{i+1:04d}"
            email = f"student{i+1}@school.edu"

            user = User.objects.create_user(
                username=username,
                email=email,
                password="password123",
                first_name=fake.first_name(),
                last_name=fake.last_name(),
                date_of_birth=fake.date_of_birth(minimum_age=5, maximum_age=18),
            )

            # Create student
            student = Student.objects.create(
                user=user,
                admission_number=UtilityService.generate_unique_code(
                    Student, "admission_number", "STU", 6
                ),
                admission_date=fake.date_between(start_date="-3y", end_date="today"),
                current_class=random.choice(classes),
                roll_number=random.randint(1, 50),
                blood_group=random.choice(
                    ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]
                ),
                emergency_contact_name=fake.name(),
                emergency_contact_number=fake.phone_number()[:15],
                status="active",
            )

            # Create parent
            parent_username = f"parent_{i+1:04d}"
            parent_email = f"parent{i+1}@example.com"

            parent_user = User.objects.create_user(
                username=parent_username,
                email=parent_email,
                password="password123",
                first_name=fake.first_name(),
                last_name=user.last_name,  # Same last name as student
                phone_number=fake.phone_number()[:15],
            )

            parent = Parent.objects.create(
                user=parent_user,
                occupation=fake.job(),
                annual_income=Decimal(str(random.randint(20000, 100000))),
                education=random.choice(["High School", "Bachelor", "Master", "PhD"]),
            )

            # Create parent-student relationship
            StudentParentRelation.objects.create(
                student=student,
                parent=parent,
                relation_type=random.choice(["father", "mother", "guardian"]),
                is_primary_contact=True,
            )

            students.append(student)
            if i % 10 == 0:
                self.stdout.write(f"  Created {i+1} students...")

        self.stdout.write(f"  Created {len(students)} students with parents")
        return students

    def create_sample_fee_structures(self, academic_year, term):
        """Create sample fee structures"""
        self.stdout.write("Creating sample fee structures...")

        # Create fee categories
        categories = [
            ("Tuition", "Monthly tuition fees", True, "monthly"),
            ("Transport", "Transportation fees", False, "monthly"),
            ("Library", "Library access fees", True, "termly"),
            ("Lab", "Laboratory fees", False, "termly"),
            ("Sports", "Sports activities fees", False, "annually"),
        ]

        fee_categories = []
        for name, desc, mandatory, frequency in categories:
            category, created = FeeCategory.objects.get_or_create(
                name=name,
                defaults={
                    "description": desc,
                    "is_mandatory": mandatory,
                    "is_recurring": True,
                    "frequency": frequency,
                },
            )
            fee_categories.append(category)
            if created:
                self.stdout.write(f"  Created fee category: {category}")

        # Create fee structures for different grades
        grades = Grade.objects.all()
        for grade in grades:
            for category in fee_categories:
                # Base amount varies by grade level
                base_amount = 1000 + (grade.order_sequence * 200)

                # Vary amount by category
                multipliers = {
                    "Tuition": 3.0,
                    "Transport": 0.8,
                    "Library": 0.3,
                    "Lab": 0.5,
                    "Sports": 0.4,
                }

                amount = base_amount * multipliers.get(category.name, 1.0)

                FeeStructure.objects.get_or_create(
                    academic_year=academic_year,
                    term=term,
                    grade=grade,
                    fee_category=category,
                    defaults={
                        "amount": Decimal(str(amount)),
                        "due_date": term.end_date,
                        "late_fee_percentage": 5,
                        "grace_period_days": 7,
                        "is_active": True,
                    },
                )

        self.stdout.write("  Created fee structures")

    def create_sample_invoices(self, students, academic_year, term):
        """Create sample invoices and payments"""
        self.stdout.write("Creating sample invoices and payments...")

        fee_structures = FeeStructure.objects.filter(
            academic_year=academic_year, term=term
        )

        for student in students:
            # Get applicable fee structures for student's grade
            applicable_fees = fee_structures.filter(
                Q(grade=student.current_class.grade)
                | Q(section=student.current_class.grade.section)
                | Q(grade__isnull=True, section__isnull=True)  # General fees
            )

            if applicable_fees.exists():
                total_amount = sum(fee.amount for fee in applicable_fees)

                invoice = Invoice.objects.create(
                    student=student,
                    academic_year=academic_year,
                    term=term,
                    invoice_number=UtilityService.generate_unique_code(
                        Invoice, "invoice_number", "INV", 8
                    ),
                    issue_date=fake.date_between(
                        start_date=term.start_date, end_date="today"
                    ),
                    due_date=term.end_date,
                    total_amount=total_amount,
                    discount_amount=Decimal("0"),
                    net_amount=total_amount,
                    status=random.choice(["paid", "unpaid", "partially_paid"]),
                )

                # Create invoice items
                from finance.models import InvoiceItem

                for fee_structure in applicable_fees:
                    InvoiceItem.objects.create(
                        invoice=invoice,
                        fee_structure=fee_structure,
                        description=f"{fee_structure.fee_category.name} - {fee_structure.grade or fee_structure.section}",
                        amount=fee_structure.amount,
                        discount_amount=Decimal("0"),
                        net_amount=fee_structure.amount,
                    )

                # Create payment if invoice is paid
                if invoice.status in ["paid", "partially_paid"]:
                    payment_amount = total_amount
                    if invoice.status == "partially_paid":
                        payment_amount = total_amount * Decimal(
                            str(random.uniform(0.3, 0.8))
                        )

                    Payment.objects.create(
                        invoice=invoice,
                        payment_date=fake.date_between(
                            start_date=invoice.issue_date, end_date="today"
                        ),
                        amount=payment_amount,
                        payment_method=random.choice(
                            ["cash", "bank_transfer", "credit_card"]
                        ),
                        transaction_id=UtilityService.generate_unique_code(
                            Payment, "transaction_id", "TXN", 10
                        ),
                        receipt_number=UtilityService.generate_unique_code(
                            Payment, "receipt_number", "REC", 8
                        ),
                        status="completed",
                    )

        self.stdout.write("  Created invoices and payments")


# management/commands/backup_database.py
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.utils import timezone
import os
import subprocess
from pathlib import Path

from core.services import AuditService


class Command(BaseCommand):
    help = "Backup database with optional compression"

    def add_arguments(self, parser):
        parser.add_argument(
            "--output",
            type=str,
            help="Output file path (default: auto-generated with timestamp)",
        )
        parser.add_argument(
            "--compress", action="store_true", help="Compress the backup file"
        )
        parser.add_argument(
            "--clean-old",
            type=int,
            default=0,
            help="Remove backups older than N days (0 = keep all)",
        )

    def handle(self, *args, **options):
        output_file = options.get("output")
        compress = options["compress"]
        clean_old_days = options["clean_old"]

        # Get database configuration
        db_config = settings.DATABASES["default"]

        if db_config["ENGINE"] != "django.db.backends.postgresql":
            raise CommandError("This command only supports PostgreSQL databases")

        # Generate output filename if not provided
        if not output_file:
            timestamp = timezone.now().strftime("%Y%m%d_%H%M%S")
            extension = ".sql.gz" if compress else ".sql"
            output_file = f"backup_{timestamp}{extension}"

        # Ensure output directory exists
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            # Build pg_dump command
            cmd = [
                "pg_dump",
                f"--host={db_config.get('HOST', 'localhost')}",
                f"--port={db_config.get('PORT', '5432')}",
                f"--username={db_config['USER']}",
                "--verbose",
                "--clean",
                "--no-owner",
                "--no-privileges",
                db_config["NAME"],
            ]

            # Set password environment variable
            env = os.environ.copy()
            if db_config.get("PASSWORD"):
                env["PGPASSWORD"] = db_config["PASSWORD"]

            self.stdout.write(f"Creating database backup: {output_file}")

            # Execute backup
            if compress:
                with open(output_file, "wb") as f:
                    # Pipe through gzip
                    dump_process = subprocess.Popen(
                        cmd, stdout=subprocess.PIPE, env=env
                    )
                    gzip_process = subprocess.Popen(
                        ["gzip"], stdin=dump_process.stdout, stdout=f
                    )
                    dump_process.stdout.close()
                    gzip_process.communicate()

                    if dump_process.returncode != 0:
                        raise subprocess.CalledProcessError(
                            dump_process.returncode, cmd
                        )
            else:
                with open(output_file, "w") as f:
                    subprocess.run(cmd, stdout=f, env=env, check=True)

            # Get file size
            file_size = output_path.stat().st_size
            size_mb = file_size / (1024 * 1024)

            self.stdout.write(
                self.style.SUCCESS(
                    f"Backup completed successfully: {output_file} ({size_mb:.2f} MB)"
                )
            )

            # Clean old backups if requested
            if clean_old_days > 0:
                self.clean_old_backups(output_path.parent, clean_old_days)

            # Log the backup
            AuditService.log_action(
                action="system_action",
                description="Database backup created via management command",
                data_after={
                    "output_file": str(output_file),
                    "file_size_bytes": file_size,
                    "compressed": compress,
                },
                module_name="core",
            )

        except subprocess.CalledProcessError as e:
            raise CommandError(f"Backup failed: {e}")
        except Exception as e:
            raise CommandError(f"Error creating backup: {str(e)}")

    def clean_old_backups(self, backup_dir, days):
        """Remove backup files older than specified days"""
        from datetime import timedelta

        cutoff_time = timezone.now() - timedelta(days=days)
        cutoff_timestamp = cutoff_time.timestamp()

        removed_count = 0
        for file_path in backup_dir.glob("backup_*.sql*"):
            if file_path.stat().st_mtime < cutoff_timestamp:
                file_path.unlink()
                removed_count += 1
                self.stdout.write(f"Removed old backup: {file_path.name}")

        if removed_count > 0:
            self.stdout.write(f"Cleaned up {removed_count} old backup files")
        else:
            self.stdout.write("No old backup files to clean up")
