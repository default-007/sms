"""
School Management System - Exam Tests
File: src/exams/tests.py
"""

from datetime import date, time, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from exams.services.analytics_service import ExamAnalyticsService

from .models import (
    Exam,
    ExamQuestion,
    ExamSchedule,
    ExamType,
    GradeScale,
    GradingSystem,
    OnlineExam,
    OnlineExamQuestion,
    ReportCard,
    StudentExamResult,
    StudentOnlineExamAttempt,
)
from .services.exam_service import ExamService, OnlineExamService, ResultService

""" from .services.analytics_service import ExamAnalyticsService """
from academics.models import AcademicYear, Class, Grade, Section, Term
from students.models import Student
from subjects.models import Subject
from teachers.models import Teacher

User = get_user_model()


class ExamModelTests(TestCase):
    """Test cases for Exam models"""

    def setUp(self):
        """Set up test data"""
        # Create users
        self.admin_user = User.objects.create_user(
            username="admin", email="admin@test.com", password="testpass123"
        )

        self.teacher_user = User.objects.create_user(
            username="teacher", email="teacher@test.com", password="testpass123"
        )

        self.student_user = User.objects.create_user(
            username="student", email="student@test.com", password="testpass123"
        )

        # Create academic structure
        self.academic_year = AcademicYear.objects.create(
            name="2024-25",
            start_date=date(2024, 4, 1),
            end_date=date(2025, 3, 31),
            is_current=True,
        )

        self.term = Term.objects.create(
            academic_year=self.academic_year,
            name="First Term",
            term_number=1,
            start_date=date(2024, 4, 1),
            end_date=date(2024, 8, 31),
            is_current=True,
        )

        self.section = Section.objects.create(name="Primary")
        self.grade = Grade.objects.create(name="Grade 5", section=self.section)

        self.teacher = Teacher.objects.create(
            user=self.teacher_user, employee_id="T001", joining_date=date(2024, 1, 1)
        )

        self.class_obj = Class.objects.create(
            name="A",
            grade=self.grade,
            academic_year=self.academic_year,
            class_teacher=self.teacher,
        )

        self.student = Student.objects.create(
            user=self.student_user,
            admission_number="S001",
            current_class=self.class_obj,
        )

        self.subject = Subject.objects.create(name="Mathematics", code="MATH001")

        # Create exam type
        self.exam_type = ExamType.objects.create(
            name="Mid-term Exam",
            contribution_percentage=Decimal("30.00"),
            is_term_based=True,
        )

    def test_exam_creation(self):
        """Test exam model creation"""
        exam = Exam.objects.create(
            name="Mid-term Mathematics",
            exam_type=self.exam_type,
            academic_year=self.academic_year,
            term=self.term,
            start_date=date(2024, 6, 1),
            end_date=date(2024, 6, 10),
            created_by=self.admin_user,
        )

        self.assertEqual(exam.name, "Mid-term Mathematics")
        self.assertEqual(exam.status, "DRAFT")
        self.assertFalse(exam.is_published)
        self.assertEqual(exam.completion_rate, 0)

    def test_exam_schedule_creation(self):
        """Test exam schedule creation"""
        exam = Exam.objects.create(
            name="Test Exam",
            exam_type=self.exam_type,
            academic_year=self.academic_year,
            term=self.term,
            start_date=date(2024, 6, 1),
            end_date=date(2024, 6, 10),
            created_by=self.admin_user,
        )

        schedule = ExamSchedule.objects.create(
            exam=exam,
            class_obj=self.class_obj,
            subject=self.subject,
            date=date(2024, 6, 5),
            start_time=time(9, 0),
            end_time=time(11, 0),
            duration_minutes=120,
            total_marks=100,
            passing_marks=40,
            supervisor=self.teacher,
        )

        self.assertEqual(schedule.duration_hours, 2.0)
        self.assertEqual(schedule.passing_percentage, 40.0)
        self.assertFalse(schedule.is_completed)

    def test_student_exam_result_auto_calculation(self):
        """Test automatic calculation in student exam result"""
        exam = Exam.objects.create(
            name="Test Exam",
            exam_type=self.exam_type,
            academic_year=self.academic_year,
            term=self.term,
            start_date=date(2024, 6, 1),
            end_date=date(2024, 6, 10),
            created_by=self.admin_user,
        )

        schedule = ExamSchedule.objects.create(
            exam=exam,
            class_obj=self.class_obj,
            subject=self.subject,
            date=date(2024, 6, 5),
            start_time=time(9, 0),
            end_time=time(11, 0),
            duration_minutes=120,
            total_marks=100,
            passing_marks=40,
            supervisor=self.teacher,
        )

        result = StudentExamResult.objects.create(
            student=self.student,
            exam_schedule=schedule,
            term=self.term,
            marks_obtained=Decimal("75.5"),
            entered_by=self.teacher_user,
        )

        self.assertEqual(result.percentage, Decimal("75.50"))
        self.assertEqual(result.grade, "B+")
        self.assertTrue(result.is_pass)

    def test_report_card_creation(self):
        """Test report card model"""
        report_card = ReportCard.objects.create(
            student=self.student,
            class_obj=self.class_obj,
            academic_year=self.academic_year,
            term=self.term,
            total_marks=500,
            marks_obtained=Decimal("425.5"),
            percentage=Decimal("85.10"),
            grade="A",
            grade_point_average=Decimal("3.8"),
            class_rank=1,
            class_size=30,
            attendance_percentage=Decimal("95.5"),
            days_present=95,
            days_absent=5,
            total_days=100,
        )

        self.assertEqual(report_card.rank_suffix, "1st")
        self.assertEqual(report_card.status, "DRAFT")

    def test_exam_question_creation(self):
        """Test exam question model"""
        question = ExamQuestion.objects.create(
            subject=self.subject,
            grade=self.grade,
            question_text="What is 2 + 2?",
            question_type="MCQ",
            difficulty_level="EASY",
            marks=2,
            options=["3", "4", "5", "6"],
            correct_answer="4",
            created_by=self.teacher_user,
        )

        self.assertEqual(question.usage_count, 0)
        self.assertTrue(question.is_active)

    def test_grading_system(self):
        """Test grading system and grade scales"""
        grading_system = GradingSystem.objects.create(
            academic_year=self.academic_year, name="Standard Grading", is_default=True
        )

        grade_scale = GradeScale.objects.create(
            grading_system=grading_system,
            grade_name="A+",
            min_percentage=Decimal("90.00"),
            max_percentage=Decimal("100.00"),
            grade_point=Decimal("4.00"),
        )

        self.assertEqual(str(grade_scale), "A+ (90.00-100.00%)")


class ExamServiceTests(TestCase):
    """Test cases for Exam services"""

    def setUp(self):
        """Set up test data"""
        self.admin_user = User.objects.create_user(
            username="admin", email="admin@test.com", password="testpass123"
        )

        self.academic_year = AcademicYear.objects.create(
            name="2024-25",
            start_date=date(2024, 4, 1),
            end_date=date(2025, 3, 31),
            is_current=True,
        )

        self.term = Term.objects.create(
            academic_year=self.academic_year,
            name="First Term",
            term_number=1,
            start_date=date(2024, 4, 1),
            end_date=date(2024, 8, 31),
            is_current=True,
        )

        self.exam_type = ExamType.objects.create(
            name="Unit Test", contribution_percentage=Decimal("20.00")
        )

    def test_create_exam_service(self):
        """Test exam creation service"""
        exam_data = {
            "name": "Test Exam",
            "exam_type": self.exam_type,
            "academic_year": self.academic_year,
            "term": self.term,
            "start_date": date(2024, 6, 1),
            "end_date": date(2024, 6, 10),
            "created_by": self.admin_user,
        }

        exam = ExamService.create_exam(exam_data)

        self.assertEqual(exam.name, "Test Exam")
        self.assertEqual(exam.total_students, 0)  # No students in system yet

    def test_publish_exam_service(self):
        """Test exam publishing service"""
        exam = Exam.objects.create(
            name="Test Exam",
            exam_type=self.exam_type,
            academic_year=self.academic_year,
            term=self.term,
            start_date=date(2024, 6, 1),
            end_date=date(2024, 6, 10),
            created_by=self.admin_user,
        )

        published_exam = ExamService.publish_exam(str(exam.id))

        self.assertTrue(published_exam.is_published)
        self.assertEqual(published_exam.status, "SCHEDULED")


class ExamAPITests(APITestCase):
    """Test cases for Exam API endpoints"""

    def setUp(self):
        """Set up test data"""
        self.admin_user = User.objects.create_user(
            username="admin",
            email="admin@test.com",
            password="testpass123",
            role="ADMIN",
        )

        self.teacher_user = User.objects.create_user(
            username="teacher",
            email="teacher@test.com",
            password="testpass123",
            role="TEACHER",
        )

        self.academic_year = AcademicYear.objects.create(
            name="2024-25",
            start_date=date(2024, 4, 1),
            end_date=date(2025, 3, 31),
            is_current=True,
        )

        self.term = Term.objects.create(
            academic_year=self.academic_year,
            name="First Term",
            term_number=1,
            start_date=date(2024, 4, 1),
            end_date=date(2024, 8, 31),
            is_current=True,
        )

        self.exam_type = ExamType.objects.create(
            name="Unit Test", contribution_percentage=Decimal("20.00")
        )

    def test_exam_type_list_api(self):
        """Test exam type list API"""
        self.client.force_authenticate(user=self.admin_user)

        url = reverse("exams:examtype-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)

    def test_exam_creation_api(self):
        """Test exam creation via API"""
        self.client.force_authenticate(user=self.admin_user)

        data = {
            "name": "API Test Exam",
            "exam_type": str(self.exam_type.id),
            "academic_year": str(self.academic_year.id),
            "term": str(self.term.id),
            "start_date": "2024-06-01",
            "end_date": "2024-06-10",
            "description": "Test exam created via API",
        }

        url = reverse("exams:exam-list")
        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["name"], "API Test Exam")

    def test_exam_publish_api(self):
        """Test exam publish API"""
        self.client.force_authenticate(user=self.admin_user)

        exam = Exam.objects.create(
            name="Test Exam",
            exam_type=self.exam_type,
            academic_year=self.academic_year,
            term=self.term,
            start_date=date(2024, 6, 1),
            end_date=date(2024, 6, 10),
            created_by=self.admin_user,
        )

        url = reverse("exams:exam-publish", kwargs={"pk": exam.id})
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["is_published"])

    def test_unauthorized_access(self):
        """Test unauthorized access to exam APIs"""
        url = reverse("exams:exam-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_teacher_access_permissions(self):
        """Test teacher access to exam APIs"""
        self.client.force_authenticate(user=self.teacher_user)

        url = reverse("exams:exam-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)


class ExamAnalyticsTests(TestCase):
    """Test cases for Exam analytics"""

    def setUp(self):
        """Set up test data with results"""
        # Create basic setup
        self.admin_user = User.objects.create_user(
            username="admin", email="admin@test.com", password="testpass123"
        )

        self.academic_year = AcademicYear.objects.create(
            name="2024-25",
            start_date=date(2024, 4, 1),
            end_date=date(2025, 3, 31),
            is_current=True,
        )

        self.term = Term.objects.create(
            academic_year=self.academic_year,
            name="First Term",
            term_number=1,
            start_date=date(2024, 4, 1),
            end_date=date(2024, 8, 31),
            is_current=True,
        )

        # Create students and results for analytics
        self.create_test_data()

    def create_test_data(self):
        """Create comprehensive test data"""
        # Create exam setup
        self.exam_type = ExamType.objects.create(
            name="Unit Test", contribution_percentage=Decimal("20.00")
        )

        self.exam = Exam.objects.create(
            name="Mathematics Unit Test",
            exam_type=self.exam_type,
            academic_year=self.academic_year,
            term=self.term,
            start_date=date(2024, 6, 1),
            end_date=date(2024, 6, 10),
            created_by=self.admin_user,
        )

        # Create multiple students and results
        self.results = []
        for i in range(10):
            user = User.objects.create_user(
                username=f"student{i}",
                email=f"student{i}@test.com",
                password="testpass123",
            )

            # Create minimal academic structure
            if i == 0:  # Create once
                self.section = Section.objects.create(name="Primary")
                self.grade = Grade.objects.create(name="Grade 5", section=self.section)

                teacher_user = User.objects.create_user(
                    username="teacher", email="teacher@test.com", password="testpass123"
                )

                self.teacher = Teacher.objects.create(
                    user=teacher_user, employee_id="T001", joining_date=date(2024, 1, 1)
                )

                self.class_obj = Class.objects.create(
                    name="A",
                    grade=self.grade,
                    academic_year=self.academic_year,
                    class_teacher=self.teacher,
                )

                self.subject = Subject.objects.create(
                    name="Mathematics", code="MATH001"
                )

                self.schedule = ExamSchedule.objects.create(
                    exam=self.exam,
                    class_obj=self.class_obj,
                    subject=self.subject,
                    date=date(2024, 6, 5),
                    start_time=time(9, 0),
                    end_time=time(11, 0),
                    duration_minutes=120,
                    total_marks=100,
                    passing_marks=40,
                    supervisor=self.teacher,
                )

            student = Student.objects.create(
                user=user, admission_number=f"S00{i}", current_class=self.class_obj
            )

            # Create varied results for analytics
            marks = 50 + (i * 5)  # Scores from 50 to 95
            result = StudentExamResult.objects.create(
                student=student,
                exam_schedule=self.schedule,
                term=self.term,
                marks_obtained=Decimal(str(marks)),
                entered_by=self.admin_user,
            )

            self.results.append(result)

    def test_exam_analytics_service(self):
        """Test exam analytics generation"""
        analytics = ExamService.get_exam_analytics(str(self.exam.id))

        self.assertIn("exam_info", analytics)
        self.assertIn("performance_summary", analytics)
        self.assertIn("subject_wise_analysis", analytics)
        self.assertIn("grade_distribution", analytics)

        # Check exam info
        exam_info = analytics["exam_info"]
        self.assertEqual(exam_info["name"], "Mathematics Unit Test")
        self.assertEqual(exam_info["total_students"], 0)  # Auto-calculated

    def test_academic_performance_dashboard(self):
        """Test academic performance dashboard"""
        dashboard = ExamAnalyticsService.get_academic_performance_dashboard(
            str(self.academic_year.id), str(self.term.id)
        )

        self.assertIn("overview", dashboard)
        self.assertIn("subject_analysis", dashboard)
        self.assertIn("class_comparison", dashboard)

        # Check overview data
        overview = dashboard["overview"]
        self.assertIn("avg_percentage", overview)
        self.assertIn("pass_rate", overview)
        self.assertIn("total_students", overview)

    def test_student_progress_report(self):
        """Test individual student progress report"""
        student = self.results[0].student

        progress_report = ExamAnalyticsService.get_student_progress_report(
            str(student.id), str(self.academic_year.id)
        )

        self.assertIn("overall_average", progress_report)
        self.assertIn("total_exams", progress_report)
        self.assertIn("pass_rate", progress_report)
        self.assertIn("subject_performance", progress_report)


class OnlineExamTests(TestCase):
    """Test cases for Online Exam functionality"""

    def setUp(self):
        """Set up test data for online exams"""
        self.admin_user = User.objects.create_user(
            username="admin", email="admin@test.com", password="testpass123"
        )

        self.student_user = User.objects.create_user(
            username="student", email="student@test.com", password="testpass123"
        )

        # Create minimal academic structure
        self.academic_year = AcademicYear.objects.create(
            name="2024-25",
            start_date=date(2024, 4, 1),
            end_date=date(2025, 3, 31),
            is_current=True,
        )

        self.term = Term.objects.create(
            academic_year=self.academic_year,
            name="First Term",
            term_number=1,
            start_date=date(2024, 4, 1),
            end_date=date(2024, 8, 31),
            is_current=True,
        )

        self.section = Section.objects.create(name="Primary")
        self.grade = Grade.objects.create(name="Grade 5", section=self.section)

        teacher_user = User.objects.create_user(
            username="teacher", email="teacher@test.com", password="testpass123"
        )

        self.teacher = Teacher.objects.create(
            user=teacher_user, employee_id="T001", joining_date=date(2024, 1, 1)
        )

        self.class_obj = Class.objects.create(
            name="A",
            grade=self.grade,
            academic_year=self.academic_year,
            class_teacher=self.teacher,
        )

        self.student = Student.objects.create(
            user=self.student_user,
            admission_number="S001",
            current_class=self.class_obj,
        )

        self.subject = Subject.objects.create(name="Mathematics", code="MATH001")

    def test_online_exam_creation(self):
        """Test online exam creation"""
        exam_type = ExamType.objects.create(
            name="Online Quiz", contribution_percentage=Decimal("10.00"), is_online=True
        )

        exam = Exam.objects.create(
            name="Online Math Quiz",
            exam_type=exam_type,
            academic_year=self.academic_year,
            term=self.term,
            start_date=date(2024, 6, 1),
            end_date=date(2024, 6, 10),
            created_by=self.admin_user,
        )

        schedule = ExamSchedule.objects.create(
            exam=exam,
            class_obj=self.class_obj,
            subject=self.subject,
            date=date(2024, 6, 5),
            start_time=time(9, 0),
            end_time=time(10, 0),
            duration_minutes=60,
            total_marks=50,
            passing_marks=20,
            supervisor=self.teacher,
        )

        online_exam = OnlineExam.objects.create(
            exam_schedule=schedule,
            time_limit_minutes=45,
            max_attempts=2,
            shuffle_questions=True,
            enable_proctoring=True,
        )

        self.assertEqual(online_exam.time_limit_minutes, 45)
        self.assertTrue(online_exam.shuffle_questions)
        self.assertTrue(online_exam.enable_proctoring)

    def test_student_online_exam_attempt(self):
        """Test student online exam attempt"""
        # Create online exam setup
        exam_type = ExamType.objects.create(
            name="Online Quiz", contribution_percentage=Decimal("10.00"), is_online=True
        )

        exam = Exam.objects.create(
            name="Online Math Quiz",
            exam_type=exam_type,
            academic_year=self.academic_year,
            term=self.term,
            start_date=date(2024, 6, 1),
            end_date=date(2024, 6, 10),
            created_by=self.admin_user,
        )

        schedule = ExamSchedule.objects.create(
            exam=exam,
            class_obj=self.class_obj,
            subject=self.subject,
            date=date(2024, 6, 5),
            start_time=time(9, 0),
            end_time=time(10, 0),
            duration_minutes=60,
            total_marks=50,
            passing_marks=20,
            supervisor=self.teacher,
        )

        online_exam = OnlineExam.objects.create(
            exam_schedule=schedule, time_limit_minutes=45, max_attempts=2
        )

        # Create student attempt
        attempt = StudentOnlineExamAttempt.objects.create(
            student=self.student,
            online_exam=online_exam,
            attempt_number=1,
            total_marks=50,
            responses={"q1": "answer1", "q2": "answer2"},
        )

        self.assertEqual(attempt.status, "STARTED")
        self.assertEqual(attempt.attempt_number, 1)
        self.assertIsNone(attempt.submit_time)


class ExamIntegrationTests(TestCase):
    """Integration tests for exam workflow"""

    def setUp(self):
        """Set up comprehensive test environment"""
        # Create users
        self.admin_user = User.objects.create_user(
            username="admin",
            email="admin@test.com",
            password="testpass123",
            role="ADMIN",
        )

        self.teacher_user = User.objects.create_user(
            username="teacher",
            email="teacher@test.com",
            password="testpass123",
            role="TEACHER",
        )

        # Create academic structure
        self.academic_year = AcademicYear.objects.create(
            name="2024-25",
            start_date=date(2024, 4, 1),
            end_date=date(2025, 3, 31),
            is_current=True,
        )

        self.term = Term.objects.create(
            academic_year=self.academic_year,
            name="First Term",
            term_number=1,
            start_date=date(2024, 4, 1),
            end_date=date(2024, 8, 31),
            is_current=True,
        )

        self.section = Section.objects.create(name="Primary")
        self.grade = Grade.objects.create(name="Grade 5", section=self.section)

        self.teacher = Teacher.objects.create(
            user=self.teacher_user, employee_id="T001", joining_date=date(2024, 1, 1)
        )

        self.class_obj = Class.objects.create(
            name="A",
            grade=self.grade,
            academic_year=self.academic_year,
            class_teacher=self.teacher,
        )

        self.subject = Subject.objects.create(name="Mathematics", code="MATH001")

        # Create students
        self.students = []
        for i in range(5):
            user = User.objects.create_user(
                username=f"student{i}",
                email=f"student{i}@test.com",
                password="testpass123",
            )

            student = Student.objects.create(
                user=user, admission_number=f"S00{i}", current_class=self.class_obj
            )

            self.students.append(student)

    def test_complete_exam_workflow(self):
        """Test complete exam workflow from creation to report cards"""
        # 1. Create exam type
        exam_type = ExamType.objects.create(
            name="Final Exam",
            contribution_percentage=Decimal("40.00"),
            is_term_based=True,
        )

        # 2. Create exam
        exam_data = {
            "name": "Mathematics Final Exam",
            "exam_type": exam_type,
            "academic_year": self.academic_year,
            "term": self.term,
            "start_date": date(2024, 6, 1),
            "end_date": date(2024, 6, 10),
            "created_by": self.admin_user,
        }

        exam = ExamService.create_exam(exam_data)
        self.assertEqual(exam.status, "DRAFT")

        # 3. Create exam schedule
        schedule = ExamSchedule.objects.create(
            exam=exam,
            class_obj=self.class_obj,
            subject=self.subject,
            date=date(2024, 6, 5),
            start_time=time(9, 0),
            end_time=time(12, 0),
            duration_minutes=180,
            total_marks=100,
            passing_marks=40,
            supervisor=self.teacher,
        )

        # 4. Publish exam
        published_exam = ExamService.publish_exam(str(exam.id))
        self.assertTrue(published_exam.is_published)

        # 5. Enter results for all students
        results_data = []
        for i, student in enumerate(self.students):
            marks = 40 + (i * 10)  # Scores: 40, 50, 60, 70, 80
            results_data.append(
                {
                    "student_id": str(student.id),
                    "marks_obtained": str(marks),
                    "is_absent": False,
                    "remarks": f"Good performance by {student.user.get_full_name()}",
                }
            )

        results = ResultService.enter_results(
            str(schedule.id), results_data, self.teacher_user
        )

        self.assertEqual(len(results), 5)

        # 6. Verify rankings were calculated
        for result in results:
            self.assertIsNotNone(result.class_rank)
            self.assertIn(result.grade, ["F", "D", "C", "B", "A"])

        # 7. Generate report cards
        report_cards = ResultService.generate_report_cards(
            str(self.term.id), [str(self.class_obj.id)]
        )

        self.assertEqual(len(report_cards), 5)

        # 8. Verify report card data
        for report_card in report_cards:
            self.assertIsNotNone(report_card.percentage)
            self.assertIsNotNone(report_card.class_rank)
            self.assertEqual(report_card.class_size, 5)

        # 9. Get exam analytics
        analytics = ExamService.get_exam_analytics(str(exam.id))

        self.assertIn("performance_summary", analytics)
        self.assertIn("subject_wise_analysis", analytics)

        performance_summary = analytics["performance_summary"]
        self.assertEqual(performance_summary["total_count"], 5)
        self.assertGreater(performance_summary["avg_percentage"], 0)
