"""
School Management System - Generate Sample Exam Data
File: src/exams/management/commands/generate_sample_exam_data.py
"""

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from decimal import Decimal
import random
from datetime import date, time, timedelta

from exams.models import (
    ExamType,
    Exam,
    ExamSchedule,
    StudentExamResult,
    ExamQuestion,
    GradingSystem,
    GradeScale,
)
from academics.models import AcademicYear, Term, Class, Grade
from subjects.models import Subject
from students.models import Student
from teachers.models import Teacher

User = get_user_model()


class Command(BaseCommand):
    help = "Generate sample exam data for testing and demonstration"

    def add_arguments(self, parser):
        parser.add_argument(
            "--academic-year", type=str, help="Academic year ID to create data for"
        )
        parser.add_argument(
            "--num-exams", type=int, default=5, help="Number of exams to create"
        )
        parser.add_argument(
            "--num-questions",
            type=int,
            default=50,
            help="Number of questions to create per subject",
        )
        parser.add_argument(
            "--create-results", action="store_true", help="Create sample exam results"
        )
        parser.add_argument(
            "--clear-existing",
            action="store_true",
            help="Clear existing exam data before creating new",
        )

    def handle(self, *args, **options):
        if options["clear_existing"]:
            self._clear_existing_data()

        academic_year_id = options["academic_year"]
        if not academic_year_id:
            academic_year = AcademicYear.objects.filter(is_current=True).first()
        else:
            academic_year = AcademicYear.objects.get(id=academic_year_id)

        if not academic_year:
            self.stdout.write(self.style.ERROR("No academic year found"))
            return

        self.stdout.write(f"Creating sample data for: {academic_year.name}")

        # Create exam types
        exam_types = self._create_exam_types()
        self.stdout.write(f"Created {len(exam_types)} exam types")

        # Create grading system
        grading_system = self._create_grading_system(academic_year)
        self.stdout.write(f"Created grading system: {grading_system.name}")

        # Create sample questions
        questions_created = self._create_sample_questions(options["num_questions"])
        self.stdout.write(f"Created {questions_created} sample questions")

        # Create exams
        exams = self._create_sample_exams(
            academic_year, exam_types, options["num_exams"]
        )
        self.stdout.write(f"Created {len(exams)} exams")

        # Create exam schedules
        schedules_created = self._create_exam_schedules(exams)
        self.stdout.write(f"Created {schedules_created} exam schedules")

        # Create results if requested
        if options["create_results"]:
            results_created = self._create_sample_results()
            self.stdout.write(f"Created {results_created} exam results")

        self.stdout.write(self.style.SUCCESS("Sample exam data created successfully!"))

    def _clear_existing_data(self):
        """Clear existing exam data"""
        self.stdout.write("Clearing existing exam data...")

        StudentExamResult.objects.all().delete()
        ExamSchedule.objects.all().delete()
        Exam.objects.all().delete()
        ExamQuestion.objects.all().delete()
        GradeScale.objects.all().delete()
        GradingSystem.objects.all().delete()
        ExamType.objects.all().delete()

        self.stdout.write("Existing data cleared")

    def _create_exam_types(self):
        """Create sample exam types"""
        exam_types_data = [
            {
                "name": "Unit Test",
                "contribution_percentage": Decimal("15.00"),
                "frequency": "MONTHLY",
                "is_term_based": True,
            },
            {
                "name": "Mid-term Exam",
                "contribution_percentage": Decimal("30.00"),
                "frequency": "TERMLY",
                "is_term_based": True,
            },
            {
                "name": "Final Exam",
                "contribution_percentage": Decimal("40.00"),
                "frequency": "TERMLY",
                "is_term_based": True,
            },
            {
                "name": "Assignment",
                "contribution_percentage": Decimal("10.00"),
                "frequency": "WEEKLY",
                "is_term_based": False,
            },
            {
                "name": "Class Test",
                "contribution_percentage": Decimal("5.00"),
                "frequency": "WEEKLY",
                "is_term_based": False,
            },
        ]

        exam_types = []
        for data in exam_types_data:
            exam_type, created = ExamType.objects.get_or_create(
                name=data["name"], defaults=data
            )
            exam_types.append(exam_type)

        return exam_types

    def _create_grading_system(self, academic_year):
        """Create sample grading system"""
        grading_system, created = GradingSystem.objects.get_or_create(
            academic_year=academic_year,
            name="Standard Grading System",
            defaults={
                "description": "Standard A-F grading system",
                "is_default": True,
                "is_active": True,
            },
        )

        if created:
            # Create grade scales
            grade_scales_data = [
                {
                    "grade_name": "A+",
                    "min_percentage": 90,
                    "max_percentage": 100,
                    "grade_point": 4.0,
                },
                {
                    "grade_name": "A",
                    "min_percentage": 80,
                    "max_percentage": 89,
                    "grade_point": 3.7,
                },
                {
                    "grade_name": "B+",
                    "min_percentage": 70,
                    "max_percentage": 79,
                    "grade_point": 3.3,
                },
                {
                    "grade_name": "B",
                    "min_percentage": 60,
                    "max_percentage": 69,
                    "grade_point": 3.0,
                },
                {
                    "grade_name": "C+",
                    "min_percentage": 50,
                    "max_percentage": 59,
                    "grade_point": 2.7,
                },
                {
                    "grade_name": "C",
                    "min_percentage": 40,
                    "max_percentage": 49,
                    "grade_point": 2.3,
                },
                {
                    "grade_name": "D",
                    "min_percentage": 30,
                    "max_percentage": 39,
                    "grade_point": 2.0,
                },
                {
                    "grade_name": "F",
                    "min_percentage": 0,
                    "max_percentage": 29,
                    "grade_point": 0.0,
                },
            ]

            for scale_data in grade_scales_data:
                GradeScale.objects.create(grading_system=grading_system, **scale_data)

        return grading_system

    def _create_sample_questions(self, num_questions_per_subject):
        """Create sample exam questions"""
        subjects = Subject.objects.all()[:5]  # Limit to first 5 subjects
        grades = Grade.objects.all()[:3]  # Limit to first 3 grades

        if not subjects.exists() or not grades.exists():
            self.stdout.write(
                self.style.WARNING(
                    "No subjects or grades found. Skipping question creation."
                )
            )
            return 0

        teacher_user = User.objects.filter(role="TEACHER").first()
        if not teacher_user:
            teacher_user = User.objects.filter(role="ADMIN").first()

        question_types = ["MCQ", "TF", "SA", "LA"]
        difficulties = ["EASY", "MEDIUM", "HARD"]

        questions_created = 0

        for subject in subjects:
            for grade in grades:
                for i in range(num_questions_per_subject // len(grades)):
                    question_type = random.choice(question_types)
                    difficulty = random.choice(difficulties)

                    question_data = {
                        "subject": subject,
                        "grade": grade,
                        "question_text": f"Sample {question_type} question {i+1} for {subject.name} - {grade.name}",
                        "question_type": question_type,
                        "difficulty_level": difficulty,
                        "marks": random.choice([1, 2, 3, 5]),
                        "topic": f"Topic {random.randint(1, 10)}",
                        "learning_objective": f"Learning objective for {subject.name}",
                        "created_by": teacher_user,
                    }

                    if question_type == "MCQ":
                        question_data.update(
                            {
                                "options": [
                                    "Option A",
                                    "Option B",
                                    "Option C",
                                    "Option D",
                                ],
                                "correct_answer": "Option A",
                            }
                        )
                    elif question_type == "TF":
                        question_data.update(
                            {"options": ["True", "False"], "correct_answer": "True"}
                        )
                    else:
                        question_data["correct_answer"] = "Sample answer text"

                    ExamQuestion.objects.create(**question_data)
                    questions_created += 1

        return questions_created

    def _create_sample_exams(self, academic_year, exam_types, num_exams):
        """Create sample exams"""
        terms = academic_year.terms.all()
        admin_user = User.objects.filter(role="ADMIN").first()

        if not terms.exists():
            self.stdout.write(self.style.WARNING("No terms found for academic year"))
            return []

        exams = []
        current_date = academic_year.start_date

        for i in range(num_exams):
            term = random.choice(terms)
            exam_type = random.choice(exam_types)

            exam_data = {
                "name": f"{exam_type.name} - {term.name} - Exam {i+1}",
                "exam_type": exam_type,
                "academic_year": academic_year,
                "term": term,
                "start_date": current_date,
                "end_date": current_date + timedelta(days=7),
                "description": f"Sample {exam_type.name} for {term.name}",
                "created_by": admin_user,
                "status": random.choice(["DRAFT", "SCHEDULED", "ONGOING", "COMPLETED"]),
            }

            exam = Exam.objects.create(**exam_data)
            exams.append(exam)

            current_date += timedelta(days=14)  # Space exams 2 weeks apart

        return exams

    def _create_exam_schedules(self, exams):
        """Create exam schedules for the exams"""
        classes = Class.objects.all()[:5]  # Limit to first 5 classes
        subjects = Subject.objects.all()[:3]  # Limit to first 3 subjects
        teachers = Teacher.objects.filter(status="ACTIVE")[:5]

        if not classes.exists() or not subjects.exists() or not teachers.exists():
            self.stdout.write(
                self.style.WARNING("Insufficient data for creating schedules")
            )
            return 0

        schedules_created = 0

        for exam in exams:
            # Create 1-3 schedules per exam
            num_schedules = random.randint(1, min(3, len(classes)))
            selected_classes = random.sample(list(classes), num_schedules)

            for i, class_obj in enumerate(selected_classes):
                subject = random.choice(subjects)
                teacher = random.choice(teachers)

                schedule_date = exam.start_date + timedelta(days=i)
                start_time = time(9 + i, 0)  # 9 AM, 10 AM, 11 AM
                end_time = time(start_time.hour + 2, start_time.minute)  # 2-hour exams

                ExamSchedule.objects.create(
                    exam=exam,
                    class_obj=class_obj,
                    subject=subject,
                    date=schedule_date,
                    start_time=start_time,
                    end_time=end_time,
                    duration_minutes=120,
                    room=f"Room {random.randint(101, 105)}",
                    supervisor=teacher,
                    total_marks=100,
                    passing_marks=40,
                    is_completed=exam.status == "COMPLETED",
                )

                schedules_created += 1

        return schedules_created

    def _create_sample_results(self):
        """Create sample exam results"""
        schedules = ExamSchedule.objects.filter(is_completed=True)
        students = Student.objects.filter(status="ACTIVE")

        if not schedules.exists() or not students.exists():
            self.stdout.write(
                self.style.WARNING("No completed schedules or active students found")
            )
            return 0

        admin_user = User.objects.filter(role="ADMIN").first()
        results_created = 0

        for schedule in schedules:
            # Get students from the class
            class_students = students.filter(current_class=schedule.class_obj)

            for student in class_students:
                # Generate realistic marks (bell curve distribution)
                marks = max(0, min(100, random.gauss(65, 20)))  # Mean 65, std dev 20
                is_absent = random.random() < 0.05  # 5% absence rate

                if is_absent:
                    marks = 0

                StudentExamResult.objects.create(
                    student=student,
                    exam_schedule=schedule,
                    term=schedule.exam.term,
                    marks_obtained=Decimal(str(round(marks, 2))),
                    is_absent=is_absent,
                    remarks=f"Sample result for {student.user.get_full_name()}",
                    entered_by=admin_user,
                )

                results_created += 1

        return results_created
