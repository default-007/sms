import random
import string
from datetime import date, datetime, time, timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from academics.models import AcademicYear, Class, Grade, Section, Term
from scheduling.models import (
    Room,
    SchedulingConstraint,
    SubstituteTeacher,
    TimeSlot,
    Timetable,
    TimetableTemplate,
)
from scheduling.services.timetable_service import TimetableService
from subjects.models import Subject
from teachers.models import Teacher, TeacherClassAssignment

User = get_user_model()


class Command(BaseCommand):
    """Generate comprehensive sample data for scheduling module"""

    help = "Generate sample scheduling data for testing and demonstration"

    def add_arguments(self, parser):
        parser.add_argument(
            "--academic-year",
            type=str,
            default="2024-2025",
            help="Academic year name (default: 2024-2025)",
        )

        parser.add_argument(
            "--sections",
            type=int,
            default=3,
            help="Number of sections to create (default: 3)",
        )

        parser.add_argument(
            "--grades-per-section",
            type=int,
            default=4,
            help="Number of grades per section (default: 4)",
        )

        parser.add_argument(
            "--classes-per-grade",
            type=int,
            default=2,
            help="Number of classes per grade (default: 2)",
        )

        parser.add_argument(
            "--teachers",
            type=int,
            default=20,
            help="Number of teachers to create (default: 20)",
        )

        parser.add_argument(
            "--subjects",
            type=int,
            default=10,
            help="Number of subjects to create (default: 10)",
        )

        parser.add_argument(
            "--rooms",
            type=int,
            default=25,
            help="Number of rooms to create (default: 25)",
        )

        parser.add_argument(
            "--create-timetables",
            action="store_true",
            help="Create sample timetable entries",
        )

        parser.add_argument(
            "--create-substitutes",
            action="store_true",
            help="Create sample substitute assignments",
        )

        parser.add_argument(
            "--clear-existing",
            action="store_true",
            help="Clear existing scheduling data before creating new",
        )

        parser.add_argument(
            "--verbose", action="store_true", help="Show detailed creation progress"
        )

    def handle(self, *args, **options):
        """Handle the command execution"""

        self.verbose = options["verbose"]

        try:
            with transaction.atomic():
                # Clear existing data if requested
                if options["clear_existing"]:
                    self._clear_existing_data()

                # Create academic structure
                academic_year, term = self._create_academic_structure(
                    options["academic_year"]
                )

                # Create sections, grades, and classes
                sections, grades, classes = self._create_academic_hierarchy(
                    academic_year,
                    options["sections"],
                    options["grades_per_section"],
                    options["classes_per_grade"],
                )

                # Create subjects
                subjects = self._create_subjects(options["subjects"])

                # Create teachers
                teachers = self._create_teachers(options["teachers"])

                # Create time slots
                time_slots = self._create_time_slots()

                # Create rooms
                rooms = self._create_rooms(options["rooms"])

                # Create teacher assignments
                teacher_assignments = self._create_teacher_assignments(
                    teachers, classes, subjects, term
                )

                # Create timetables if requested
                if options["create_timetables"]:
                    timetables = self._create_timetables(
                        classes, subjects, teachers, time_slots, rooms, term
                    )

                    # Create substitutes if requested
                    if options["create_substitutes"]:
                        self._create_substitute_assignments(timetables, teachers)

                # Create scheduling constraints
                self._create_scheduling_constraints()

                # Create timetable templates
                self._create_timetable_templates(grades)

                # Summary
                self._print_summary(
                    sections,
                    grades,
                    classes,
                    subjects,
                    teachers,
                    time_slots,
                    rooms,
                    teacher_assignments,
                )

        except Exception as e:
            raise CommandError(f"Data generation failed: {str(e)}")

    def _clear_existing_data(self):
        """Clear existing scheduling data"""

        self.stdout.write("Clearing existing scheduling data...")

        # Clear scheduling data
        Timetable.objects.all().delete()
        SubstituteTeacher.objects.all().delete()
        TimetableTemplate.objects.all().delete()
        TeacherClassAssignment.objects.all().delete()

        # Clear model data
        TimeSlot.objects.all().delete()
        Room.objects.all().delete()

        # Clear academic data (be careful with this)
        Class.objects.all().delete()
        Grade.objects.all().delete()
        Section.objects.all().delete()
        Term.objects.all().delete()
        AcademicYear.objects.all().delete()

        # Clear subjects and teachers
        Subject.objects.all().delete()
        Teacher.objects.all().delete()

        # Clear users (only sample users)
        User.objects.filter(username__startswith="teacher_").delete()

        self.stdout.write(self.style.WARNING("Existing data cleared"))

    def _create_academic_structure(self, year_name):
        """Create academic year and terms"""

        if self.verbose:
            self.stdout.write("Creating academic structure...")

        # Create academic year
        academic_year, created = AcademicYear.objects.get_or_create(
            name=year_name,
            defaults={
                "start_date": date(2024, 4, 1),
                "end_date": date(2025, 3, 31),
                "is_current": True,
            },
        )

        # Create terms
        terms_data = [
            ("First Term", 1, date(2024, 4, 1), date(2024, 7, 31)),
            ("Second Term", 2, date(2024, 8, 1), date(2024, 11, 30)),
            ("Third Term", 3, date(2024, 12, 1), date(2025, 3, 31)),
        ]

        terms = []
        for name, number, start_date, end_date in terms_data:
            term, created = Term.objects.get_or_create(
                academic_year=academic_year,
                term_number=number,
                defaults={
                    "name": name,
                    "start_date": start_date,
                    "end_date": end_date,
                    "is_current": (number == 1),
                },
            )
            terms.append(term)

        return academic_year, terms[0]  # Return first term as current

    def _create_academic_hierarchy(
        self, academic_year, num_sections, grades_per_section, classes_per_grade
    ):
        """Create sections, grades, and classes"""

        if self.verbose:
            self.stdout.write("Creating academic hierarchy...")

        section_names = ["Primary", "Middle School", "High School"]
        class_names = [
            "Alpha",
            "Beta",
            "Gamma",
            "Delta",
            "North",
            "South",
            "East",
            "West",
        ]

        sections = []
        grades = []
        classes = []

        for i in range(num_sections):
            # Create section
            section = Section.objects.create(
                name=section_names[i % len(section_names)],
                description=f"{section_names[i % len(section_names)]} Section",
            )
            sections.append(section)

            # Create grades for this section
            for j in range(grades_per_section):
                grade_number = (i * grades_per_section) + j + 1
                grade = Grade.objects.create(
                    name=f"Grade {grade_number}",
                    section=section,
                    order_sequence=grade_number,
                )
                grades.append(grade)

                # Create classes for this grade
                for k in range(classes_per_grade):
                    class_name = class_names[k % len(class_names)]
                    class_obj = Class.objects.create(
                        name=class_name,
                        grade=grade,
                        academic_year=academic_year,
                        room_number=f"{grade_number}{k+1:02d}",
                        capacity=random.randint(25, 35),
                    )
                    classes.append(class_obj)

        return sections, grades, classes

    def _create_subjects(self, num_subjects):
        """Create sample subjects"""

        if self.verbose:
            self.stdout.write("Creating subjects...")

        subject_data = [
            ("Mathematics", "MATH", 6),
            ("English Language", "ENG", 5),
            ("Science", "SCI", 5),
            ("Social Studies", "SS", 4),
            ("Physical Education", "PE", 3),
            ("Computer Science", "CS", 3),
            ("Art & Craft", "ART", 2),
            ("Music", "MUS", 2),
            ("Physics", "PHY", 4),
            ("Chemistry", "CHEM", 4),
            ("Biology", "BIO", 4),
            ("History", "HIST", 3),
            ("Geography", "GEO", 3),
            ("Literature", "LIT", 3),
            ("Foreign Language", "FL", 3),
        ]

        subjects = []
        for i in range(min(num_subjects, len(subject_data))):
            name, code, credit_hours = subject_data[i]
            subject = Subject.objects.create(
                name=name,
                code=f"{code}{i+1:03d}",
                description=f"{name} curriculum",
                credit_hours=credit_hours,
                is_elective=(i > 7),  # Mark later subjects as elective
            )
            subjects.append(subject)

        return subjects

    def _create_teachers(self, num_teachers):
        """Create sample teachers"""

        if self.verbose:
            self.stdout.write("Creating teachers...")

        first_names = [
            "John",
            "Jane",
            "Michael",
            "Sarah",
            "David",
            "Emily",
            "Robert",
            "Lisa",
            "William",
            "Jennifer",
            "James",
            "Jessica",
            "Christopher",
            "Ashley",
            "Daniel",
            "Amanda",
            "Matthew",
            "Stephanie",
            "Anthony",
            "Nicole",
        ]

        last_names = [
            "Smith",
            "Johnson",
            "Williams",
            "Brown",
            "Jones",
            "Garcia",
            "Miller",
            "Davis",
            "Rodriguez",
            "Martinez",
            "Hernandez",
            "Lopez",
            "Gonzalez",
            "Wilson",
            "Anderson",
            "Thomas",
            "Taylor",
            "Moore",
            "Jackson",
            "Martin",
        ]

        teachers = []
        for i in range(num_teachers):
            first_name = random.choice(first_names)
            last_name = random.choice(last_names)
            username = f"teacher_{i+1:03d}"

            # Create user
            user = User.objects.create_user(
                username=username,
                email=f"{username}@school.edu",
                password="password123",
                first_name=first_name,
                last_name=last_name,
            )

            # Create teacher
            teacher = Teacher.objects.create(
                user=user,
                employee_id=f"T{i+1:04d}",
                joining_date=date(2023, random.randint(1, 12), random.randint(1, 28)),
                qualification=random.choice(["B.Ed", "M.Ed", "M.A.", "M.Sc.", "Ph.D."]),
                experience_years=random.randint(1, 20),
                specialization=random.choice(
                    [
                        "Mathematics",
                        "Science",
                        "English",
                        "Social Studies",
                        "Physical Education",
                        "Arts",
                        "Computer Science",
                    ]
                ),
                status="active",
            )
            teachers.append(teacher)

        return teachers

    def _create_time_slots(self):
        """Create standard time slots"""

        if self.verbose:
            self.stdout.write("Creating time slots...")

        time_slots = []

        # Monday to Friday
        for day in range(5):
            # 8 periods per day
            for period in range(1, 9):
                # Calculate time
                if period <= 4:
                    # Morning periods: 8:00 AM to 12:00 PM
                    start_hour = 8 + (period - 1)
                else:
                    # Afternoon periods: 1:00 PM to 5:00 PM (after lunch)
                    start_hour = 13 + (period - 5)

                start_time = time(start_hour, 0)
                end_time = time(start_hour, 45)

                time_slot = TimeSlot.objects.create(
                    day_of_week=day,
                    start_time=start_time,
                    end_time=end_time,
                    duration_minutes=45,
                    period_number=period,
                    name=f"Period {period}",
                    is_break=False,
                    is_active=True,
                )
                time_slots.append(time_slot)

                # Add breaks
                if period == 2:  # Morning break after period 2
                    break_slot = TimeSlot.objects.create(
                        day_of_week=day,
                        start_time=time(start_hour, 45),
                        end_time=time(start_hour + 1, 0),
                        duration_minutes=15,
                        period_number=period,
                        name="Morning Break",
                        is_break=True,
                        is_active=True,
                    )
                    time_slots.append(break_slot)

                elif period == 4:  # Lunch break after period 4
                    lunch_slot = TimeSlot.objects.create(
                        day_of_week=day,
                        start_time=time(12, 0),
                        end_time=time(13, 0),
                        duration_minutes=60,
                        period_number=period,
                        name="Lunch Break",
                        is_break=True,
                        is_active=True,
                    )
                    time_slots.append(lunch_slot)

        return time_slots

    def _create_rooms(self, num_rooms):
        """Create sample rooms"""

        if self.verbose:
            self.stdout.write("Creating rooms...")

        room_types = [
            ("classroom", "Regular Classroom", 30),
            ("laboratory", "Science Laboratory", 25),
            ("computer_lab", "Computer Laboratory", 25),
            ("library", "Library", 50),
            ("gymnasium", "Gymnasium", 100),
            ("auditorium", "Auditorium", 200),
            ("music_room", "Music Room", 20),
            ("art_room", "Art Room", 25),
        ]

        buildings = ["Main Building", "Science Block", "Arts Block", "Sports Complex"]

        rooms = []
        for i in range(num_rooms):
            room_type, room_name, capacity = random.choice(room_types)

            # Mostly classrooms, fewer special rooms
            if i > num_rooms * 0.7:  # 30% special rooms
                room_type, room_name, capacity = room_types[0]  # Regular classroom

            room = Room.objects.create(
                number=f"{random.randint(1, 5)}{i+1:02d}",
                name=f"{room_name} {i+1}",
                room_type=room_type,
                building=random.choice(buildings),
                floor=str(random.randint(1, 3)),
                capacity=capacity + random.randint(-5, 5),
                equipment=self._get_room_equipment(room_type),
                is_available=True,
            )
            rooms.append(room)

        return rooms

    def _get_room_equipment(self, room_type):
        """Get equipment list based on room type"""

        equipment_map = {
            "classroom": ["whiteboard", "projector"],
            "laboratory": ["laboratory_equipment", "safety_equipment", "projector"],
            "computer_lab": ["computers", "projector", "air_conditioning"],
            "library": ["computers", "projector"],
            "gymnasium": ["sports_equipment", "sound_system"],
            "auditorium": ["sound_system", "projector", "microphone"],
            "music_room": ["piano", "sound_system", "instruments"],
            "art_room": ["art_supplies", "easels", "storage"],
        }

        return equipment_map.get(room_type, ["whiteboard"])

    def _create_teacher_assignments(self, teachers, classes, subjects, term):
        """Create teacher-class-subject assignments"""

        if self.verbose:
            self.stdout.write("Creating teacher assignments...")

        assignments = []

        # Each class needs assignments for each subject
        for class_obj in classes:
            # Assign class teacher (first assignment)
            class_teacher_assigned = False

            for subject in subjects[:8]:  # Assign 8 subjects per class
                # Randomly assign a teacher
                teacher = random.choice(teachers)

                assignment = TeacherClassAssignment.objects.create(
                    teacher=teacher,
                    class_assigned=class_obj,
                    subject=subject,
                    term=term,
                    is_class_teacher=(not class_teacher_assigned),
                )
                assignments.append(assignment)

                if not class_teacher_assigned:
                    class_teacher_assigned = True
                    class_obj.class_teacher = teacher
                    class_obj.save()

        return assignments

    def _create_timetables(self, classes, subjects, teachers, time_slots, rooms, term):
        """Create sample timetable entries"""

        if self.verbose:
            self.stdout.write("Creating timetable entries...")

        timetables = []

        # Get non-break time slots
        regular_slots = [slot for slot in time_slots if not slot.is_break]

        for class_obj in classes:
            # Get teacher assignments for this class
            assignments = TeacherClassAssignment.objects.filter(
                class_assigned=class_obj, term=term
            )

            # Create timetable entries
            assigned_slots = set()

            for assignment in assignments:
                # Assign 3-5 periods per subject per week
                periods_per_week = random.randint(3, 5)

                for _ in range(periods_per_week):
                    # Find available slot
                    available_slots = [
                        slot
                        for slot in regular_slots
                        if (slot.day_of_week, slot.period_number) not in assigned_slots
                    ]

                    if not available_slots:
                        break

                    time_slot = random.choice(available_slots)
                    room = random.choice(rooms)

                    try:
                        timetable = TimetableService.create_timetable_entry(
                            class_assigned=class_obj,
                            subject=assignment.subject,
                            teacher=assignment.teacher,
                            time_slot=time_slot,
                            term=term,
                            room=room,
                        )
                        timetables.append(timetable)
                        assigned_slots.add(
                            (time_slot.day_of_week, time_slot.period_number)
                        )

                    except Exception as e:
                        # Skip conflicts for sample data
                        if self.verbose:
                            self.stdout.write(f"Skipped conflict: {str(e)}")
                        continue

        return timetables

    def _create_substitute_assignments(self, timetables, teachers):
        """Create sample substitute assignments"""

        if self.verbose:
            self.stdout.write("Creating substitute assignments...")

        # Create 10-15 substitute assignments
        num_substitutes = random.randint(10, 15)

        for _ in range(num_substitutes):
            timetable = random.choice(timetables)
            substitute_teacher = random.choice(
                [t for t in teachers if t != timetable.teacher]
            )

            # Random date in the next 30 days
            substitute_date = date.today() + timedelta(days=random.randint(1, 30))

            reasons = [
                "Sick leave",
                "Personal leave",
                "Training",
                "Conference",
                "Emergency",
                "Vacation",
            ]

            try:
                SubstituteTeacher.objects.create(
                    original_timetable=timetable,
                    substitute_teacher=substitute_teacher,
                    date=substitute_date,
                    reason=random.choice(reasons),
                    notes=f"Sample substitute assignment for {substitute_date}",
                )
            except Exception:
                # Skip conflicts
                continue

    def _create_scheduling_constraints(self):
        """Create sample scheduling constraints"""

        if self.verbose:
            self.stdout.write("Creating scheduling constraints...")

        constraints_data = [
            {
                "name": "Core Subjects Morning Priority",
                "constraint_type": "time_preference",
                "parameters": {
                    "subjects": ["Mathematics", "English", "Science"],
                    "preferred_periods": [1, 2, 3, 4],
                    "weight": 0.8,
                },
                "priority": 8,
                "is_hard_constraint": False,
            },
            {
                "name": "Laboratory Double Periods",
                "constraint_type": "consecutive_periods",
                "parameters": {
                    "subjects": ["Physics", "Chemistry", "Biology", "Computer Science"],
                    "require_consecutive": True,
                    "min_periods": 2,
                },
                "priority": 7,
                "is_hard_constraint": False,
            },
            {
                "name": "Teacher Daily Load Limit",
                "constraint_type": "daily_limit",
                "parameters": {"max_periods_per_day": 6, "max_consecutive_periods": 3},
                "priority": 9,
                "is_hard_constraint": True,
            },
        ]

        for constraint_data in constraints_data:
            SchedulingConstraint.objects.create(**constraint_data)

    def _create_timetable_templates(self, grades):
        """Create sample timetable templates"""

        if self.verbose:
            self.stdout.write("Creating timetable templates...")

        for grade in grades[:3]:  # Create templates for first 3 grades
            template_config = {
                "subjects": [
                    {"subject": "Mathematics", "periods_per_week": 6},
                    {"subject": "English", "periods_per_week": 5},
                    {"subject": "Science", "periods_per_week": 5},
                    {"subject": "Social Studies", "periods_per_week": 4},
                    {"subject": "Physical Education", "periods_per_week": 3},
                ],
                "preferences": {
                    "core_subjects_morning": True,
                    "lab_periods_consecutive": True,
                    "max_periods_per_day": 7,
                },
            }

            TimetableTemplate.objects.create(
                name=f"{grade.name} Standard Template",
                description=f"Standard timetable template for {grade.name}",
                grade=grade,
                is_default=True,
                configuration=template_config,
            )

    def _print_summary(
        self,
        sections,
        grades,
        classes,
        subjects,
        teachers,
        time_slots,
        rooms,
        assignments,
    ):
        """Print creation summary"""

        self.stdout.write("\n" + "=" * 50)
        self.stdout.write("SAMPLE DATA CREATION SUMMARY")
        self.stdout.write("=" * 50)

        self.stdout.write(f"Sections: {len(sections)}")
        self.stdout.write(f"Grades: {len(grades)}")
        self.stdout.write(f"Classes: {len(classes)}")
        self.stdout.write(f"Subjects: {len(subjects)}")
        self.stdout.write(f"Teachers: {len(teachers)}")
        self.stdout.write(f"Time Slots: {len(time_slots)}")
        self.stdout.write(f"Rooms: {len(rooms)}")
        self.stdout.write(f"Teacher Assignments: {len(assignments)}")

        timetable_count = Timetable.objects.count()
        substitute_count = SubstituteTeacher.objects.count()

        self.stdout.write(f"Timetable Entries: {timetable_count}")
        self.stdout.write(f"Substitute Assignments: {substitute_count}")

        self.stdout.write("\n" + self.style.SUCCESS("Sample data creation completed!"))
        self.stdout.write("\nYou can now:")
        self.stdout.write("  - View timetables in the admin interface")
        self.stdout.write("  - Test the optimization algorithms")
        self.stdout.write("  - Explore the analytics features")
        self.stdout.write("  - Generate reports")

        # Login information
        self.stdout.write(f"\nSample teacher logins:")
        for i, teacher in enumerate(teachers[:3]):
            self.stdout.write(
                f"  Username: {teacher.user.username}, Password: password123"
            )

        self.stdout.write(
            "\nUse these accounts to test the system from different perspectives."
        )
