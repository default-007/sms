import random

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone
from faker import Faker

from src.courses.models import AcademicYear, Class, Department, Grade, Section
from src.students.models import Parent, Student, StudentParentRelation

User = get_user_model()
fake = Faker()


class Command(BaseCommand):
    help = "Generate sample students, parents, and relationships for testing"

    def add_arguments(self, parser):
        parser.add_argument(
            "--students", type=int, default=50, help="Number of students to create"
        )
        parser.add_argument(
            "--parents-per-student",
            type=int,
            default=2,
            help="Average number of parents per student",
        )
        parser.add_argument(
            "--classes", type=int, default=5, help="Number of classes to create"
        )
        parser.add_argument(
            "--clean",
            action="store_true",
            help="Clean existing sample data before creating new",
        )
        parser.add_argument(
            "--admin-email",
            type=str,
            default=None,
            help="Email of admin user to set as created_by (uses first superuser if not specified)",
        )

    def handle(self, *args, **options):
        # Get admin user for created_by field
        admin_email = options.get("admin_email")
        self.admin_user = self.get_admin_user(admin_email)
        if not self.admin_user:
            self.stdout.write(
                self.style.WARNING(
                    "No admin user found. Records will be created without created_by set."
                )
            )

        if options["clean"]:
            self.stdout.write(self.style.WARNING("Cleaning existing sample data..."))
            self.clean_sample_data()

        num_students = options["students"]
        parents_per_student = options["parents_per_student"]
        num_classes = options["classes"]

        self.stdout.write(f"Creating {num_students} sample students...")

        # Create academic structure if needed
        academic_year = self.get_or_create_academic_year()
        classes = self.get_or_create_classes(num_classes, academic_year)

        # Generate students
        students = self.create_students(num_students, classes)

        # Generate parents and relationships
        self.create_parents_and_relationships(students, parents_per_student)

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully created {num_students} students with their parents and relationships!"
            )
        )

    def get_admin_user(self, email=None):
        """Get admin user for created_by field"""
        if email:
            try:
                return User.objects.get(email=email, is_staff=True)
            except User.DoesNotExist:
                self.stdout.write(
                    self.style.WARNING(f"Admin user with email {email} not found")
                )

        # Try to get first superuser
        return User.objects.filter(is_superuser=True).first()

    def clean_sample_data(self):
        """Remove existing sample data"""
        # Delete students (will cascade to relationships)
        sample_students = Student.objects.filter(admission_number__startswith="SAMPLE-")
        sample_students.delete()

        # Delete sample parents
        sample_parents = Parent.objects.filter(user__email__contains="sample.parent")
        for parent in sample_parents:
            parent.user.delete()

    def get_or_create_academic_year(self):
        """Get or create current academic year"""
        current_year = AcademicYear.objects.filter(is_current=True).first()

        if not current_year:
            # Create a new academic year
            current_year = AcademicYear.objects.create(
                name="2024-2025",
                start_date=timezone.now().date().replace(month=4, day=1),
                end_date=timezone.now()
                .date()
                .replace(year=timezone.now().year + 1, month=3, day=31),
                is_current=True,
            )
            self.stdout.write(f"Created academic year: {current_year.name}")

        return current_year

    def get_or_create_classes(self, num_classes, academic_year):
        """Get or create classes for the academic year"""
        classes = list(Class.objects.filter(academic_year=academic_year))

        if len(classes) < num_classes:
            # Create department if needed
            department, created = Department.objects.get_or_create(
                name="General Studies",
                defaults={"description": "General academic department"},
            )

            # Create grades and sections
            grade_names = [
                "Grade 1",
                "Grade 2",
                "Grade 3",
                "Grade 4",
                "Grade 5",
                "Grade 6",
                "Grade 7",
                "Grade 8",
                "Grade 9",
                "Grade 10",
            ]
            section_names = ["A", "B", "C", "D"]

            created_count = 0
            for i in range(len(classes), num_classes):
                grade_name = random.choice(grade_names)
                section_name = random.choice(section_names)

                # Get or create grade
                grade, _ = Grade.objects.get_or_create(
                    name=grade_name, defaults={"department": department}
                )

                # Get or create section
                section, _ = Section.objects.get_or_create(name=section_name)

                # Create class if it doesn't exist
                class_obj, created = Class.objects.get_or_create(
                    grade=grade,
                    section=section,
                    academic_year=academic_year,
                    defaults={
                        "room_number": f"Room-{i+1}",
                        "capacity": random.randint(25, 40),
                    },
                )

                if created:
                    classes.append(class_obj)
                    created_count += 1

            self.stdout.write(f"Created {created_count} new classes")

        return classes

    def create_students(self, num_students, classes):
        """Create sample students"""
        students = []
        blood_groups = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]
        statuses = ["Active"] * 8 + ["Inactive"] * 1 + ["Graduated"] * 1

        for i in range(num_students):
            # Generate user data
            first_name = fake.first_name()
            last_name = fake.last_name()
            email = f"{first_name.lower()}.{last_name.lower()}.sample@example.com"

            # Create user
            user = User.objects.create_user(
                username=email,
                email=email,
                first_name=first_name,
                last_name=last_name,
                password="samplepass123",
                phone_number=fake.phone_number()[:15],
                date_of_birth=fake.date_of_birth(minimum_age=5, maximum_age=18),
            )

            # Create student using model's create method
            student_kwargs = {
                "user": user,
                "admission_number": f"SAMPLE-{str(i+1).zfill(4)}",
                "admission_date": fake.date_between(start_date="-2y", end_date="today"),
                "current_class": random.choice(classes),
                "roll_number": str(random.randint(1, 100)),
                "blood_group": random.choice(blood_groups),
                "status": random.choice(statuses),
                "nationality": fake.country(),
                "religion": random.choice(
                    ["Hindu", "Muslim", "Christian", "Sikh", "Other"]
                ),
                "address": fake.address(),
                "city": fake.city(),
                "state": fake.state(),
                "postal_code": fake.postcode(),
                "country": "India",
                "emergency_contact_name": fake.name(),
                "emergency_contact_number": fake.phone_number()[:15],
                "medical_conditions": (
                    fake.text(max_nb_chars=100) if random.choice([True, False]) else ""
                ),
                "previous_school": (
                    fake.company() if random.choice([True, False]) else ""
                ),
            }

            # Add created_by if admin user is available
            if self.admin_user:
                student_kwargs["created_by"] = self.admin_user

            # Create student without explicitly setting the ID field
            student = Student.objects.create(**student_kwargs)
            students.append(student)

            if (i + 1) % 10 == 0:
                self.stdout.write(f"Created {i + 1} students...")

        return students

    def create_parents_and_relationships(self, students, parents_per_student):
        """Create parents and link them to students"""
        relations = ["Father", "Mother", "Guardian", "Grandparent"]
        occupations = [
            "Teacher",
            "Engineer",
            "Doctor",
            "Businessman",
            "Lawyer",
            "Accountant",
            "Sales Manager",
            "Software Developer",
            "Nurse",
            "Government Officer",
            "Farmer",
            "Homemaker",
        ]

        for student in students:
            # Determine number of parents for this student
            num_parents = random.randint(1, min(parents_per_student + 1, 3))

            # Create parents
            for j in range(num_parents):
                # Generate parent data
                first_name = fake.first_name()
                last_name = student.last_name  # Use student's last name
                email = f"{first_name.lower()}.{last_name.lower()}.sample.parent{j}@example.com"

                # Create parent user
                parent_user = User.objects.create_user(
                    username=email,
                    email=email,
                    first_name=first_name,
                    last_name=last_name,
                    password="parentpass123",
                    phone_number=fake.phone_number()[:15],
                    date_of_birth=fake.date_of_birth(minimum_age=25, maximum_age=55),
                )

                # Create parent
                parent_kwargs = {
                    "user": parent_user,
                    "relation_with_student": (
                        relations[j] if j < len(relations) else "Guardian"
                    ),
                    "occupation": random.choice(occupations),
                    "annual_income": random.randint(20000, 200000),
                    "education": random.choice(
                        ["High School", "Bachelor's", "Master's", "PhD"]
                    ),
                    "workplace": fake.company(),
                    "work_address": fake.address(),
                    "work_phone": fake.phone_number()[:15],
                    "emergency_contact": random.choice([True, False]),
                }

                # Add created_by if admin user is available
                if self.admin_user:
                    parent_kwargs["created_by"] = self.admin_user

                # Create parent without explicitly setting the ID field
                parent = Parent.objects.create(**parent_kwargs)

                # Create relationship
                relation_kwargs = {
                    "student": student,
                    "parent": parent,
                    "is_primary_contact": (j == 0),  # First parent is primary
                    "can_pickup": random.choice([True, False]),
                    "emergency_contact_priority": j + 1,
                    "financial_responsibility": random.choice([True, False]),
                    "access_to_grades": True,
                    "access_to_attendance": True,
                    "access_to_financial_info": random.choice([True, False]),
                    "receive_sms": random.choice([True, False]),
                    "receive_email": True,
                    "receive_push_notifications": random.choice([True, False]),
                }

                # Add created_by if admin user is available
                if self.admin_user:
                    relation_kwargs["created_by"] = self.admin_user

                # Create relationship
                StudentParentRelation.objects.create(**relation_kwargs)

        self.stdout.write(
            f"Created parents and relationships for {len(students)} students"
        )

    def create_student_with_minimal_data(self, admission_number, class_obj):
        """Create a student with minimal required data"""
        first_name = fake.first_name()
        last_name = fake.last_name()
        email = f"{first_name.lower()}.{last_name.lower()}.minimal@example.com"

        user = User.objects.create_user(
            username=email,
            email=email,
            first_name=first_name,
            last_name=last_name,
            password="minimal123",
        )

        student_kwargs = {
            "user": user,
            "admission_number": admission_number,
            "admission_date": timezone.now().date(),
            "current_class": class_obj,
            "emergency_contact_name": fake.name(),
            "emergency_contact_number": fake.phone_number()[:15],
        }

        # Add created_by if admin user is available
        if self.admin_user:
            student_kwargs["created_by"] = self.admin_user

        # Create student without explicitly setting the ID field
        student = Student.objects.create(**student_kwargs)

        return student
