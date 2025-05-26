from django.test import TestCase, TransactionTestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError
from datetime import datetime, timedelta
from unittest.mock import patch, Mock
import json
import tempfile
import os

from .models import (
    Assignment,
    AssignmentSubmission,
    AssignmentRubric,
    SubmissionGrade,
    AssignmentComment,
)
from .services import (
    AssignmentService,
    SubmissionService,
    GradingService,
    PlagiarismService,
)
from .services.analytics_service import AssignmentAnalyticsService
from teachers.models import Teacher
from students.models import Student
from subjects.models import Subject
from academics.models import AcademicYear, Term, Section, Grade, Class

User = get_user_model()


class AssignmentModelTestCase(TestCase):
    """
    Test cases for Assignment model
    """

    def setUp(self):
        """Set up test data"""
        # Create academic structure
        self.academic_year = AcademicYear.objects.create(
            name="2024-2025",
            start_date="2024-04-01",
            end_date="2025-03-31",
            is_current=True,
        )

        self.term = Term.objects.create(
            academic_year=self.academic_year,
            name="First Term",
            term_number=1,
            start_date="2024-04-01",
            end_date="2024-08-31",
            is_current=True,
        )

        self.section = Section.objects.create(name="Primary")
        self.grade = Grade.objects.create(name="Grade 5", section=self.section)
        self.class_obj = Class.objects.create(
            grade=self.grade, name="A", academic_year=self.academic_year
        )

        # Create subject
        self.subject = Subject.objects.create(name="Mathematics", code="MATH101")

        # Create teacher
        self.teacher_user = User.objects.create_user(
            username="teacher1", email="teacher@test.com", password="testpass123"
        )
        self.teacher = Teacher.objects.create(
            user=self.teacher_user, employee_id="T001"
        )

        # Create student
        self.student_user = User.objects.create_user(
            username="student1", email="student@test.com", password="testpass123"
        )
        self.student = Student.objects.create(
            user=self.student_user,
            admission_number="S001",
            current_class_id=self.class_obj,
        )

    def test_assignment_creation(self):
        """Test assignment creation with valid data"""
        assignment = Assignment.objects.create(
            title="Test Assignment",
            description="Test description",
            class_id=self.class_obj,
            subject=self.subject,
            teacher=self.teacher,
            term=self.term,
            due_date=timezone.now() + timedelta(days=7),
            total_marks=100,
        )

        self.assertEqual(assignment.title, "Test Assignment")
        self.assertEqual(assignment.status, "draft")
        self.assertFalse(assignment.is_overdue)
        self.assertEqual(assignment.submission_count, 0)
        self.assertEqual(assignment.completion_rate, 0)

    def test_assignment_str_representation(self):
        """Test string representation of assignment"""
        assignment = Assignment.objects.create(
            title="Math Quiz",
            class_id=self.class_obj,
            subject=self.subject,
            teacher=self.teacher,
            term=self.term,
            due_date=timezone.now() + timedelta(days=7),
            total_marks=50,
        )

        expected_str = f"Math Quiz - {self.class_obj} ({self.subject.code})"
        self.assertEqual(str(assignment), expected_str)

    def test_assignment_overdue_property(self):
        """Test is_overdue property"""
        # Past due date
        overdue_assignment = Assignment.objects.create(
            title="Overdue Assignment",
            class_id=self.class_obj,
            subject=self.subject,
            teacher=self.teacher,
            term=self.term,
            due_date=timezone.now() - timedelta(days=1),
            total_marks=100,
            status="published",
        )
        self.assertTrue(overdue_assignment.is_overdue)

        # Future due date
        future_assignment = Assignment.objects.create(
            title="Future Assignment",
            class_id=self.class_obj,
            subject=self.subject,
            teacher=self.teacher,
            term=self.term,
            due_date=timezone.now() + timedelta(days=7),
            total_marks=100,
            status="published",
        )
        self.assertFalse(future_assignment.is_overdue)

    def test_assignment_save_validation(self):
        """Test assignment save method validation"""
        assignment = Assignment(
            title="Test Assignment",
            class_id=self.class_obj,
            subject=self.subject,
            teacher=self.teacher,
            term=self.term,
            due_date=timezone.now() + timedelta(days=7),
            total_marks=100,
            passing_marks=120,  # Invalid: exceeds total marks
        )
        assignment.save()

        # Should automatically correct passing marks
        self.assertEqual(assignment.passing_marks, 100)

    def test_assignment_published_at_setting(self):
        """Test published_at field is set when status changes to published"""
        assignment = Assignment.objects.create(
            title="Test Assignment",
            class_id=self.class_obj,
            subject=self.subject,
            teacher=self.teacher,
            term=self.term,
            due_date=timezone.now() + timedelta(days=7),
            total_marks=100,
        )

        self.assertIsNone(assignment.published_at)

        assignment.status = "published"
        assignment.save()

        self.assertIsNotNone(assignment.published_at)


class AssignmentSubmissionModelTestCase(TestCase):
    """
    Test cases for AssignmentSubmission model
    """

    def setUp(self):
        """Set up test data"""
        # Create test assignment and student (reusing setup logic)
        self.setUpAcademicStructure()
        self.assignment = Assignment.objects.create(
            title="Test Assignment",
            class_id=self.class_obj,
            subject=self.subject,
            teacher=self.teacher,
            term=self.term,
            due_date=timezone.now() + timedelta(days=7),
            total_marks=100,
        )

    def setUpAcademicStructure(self):
        """Helper method to set up academic structure"""
        self.academic_year = AcademicYear.objects.create(
            name="2024-2025",
            start_date="2024-04-01",
            end_date="2025-03-31",
            is_current=True,
        )

        self.term = Term.objects.create(
            academic_year=self.academic_year,
            name="First Term",
            term_number=1,
            start_date="2024-04-01",
            end_date="2024-08-31",
            is_current=True,
        )

        self.section = Section.objects.create(name="Primary")
        self.grade = Grade.objects.create(name="Grade 5", section=self.section)
        self.class_obj = Class.objects.create(
            grade=self.grade, name="A", academic_year=self.academic_year
        )

        self.subject = Subject.objects.create(name="Mathematics", code="MATH101")

        self.teacher_user = User.objects.create_user(
            username="teacher1", email="teacher@test.com", password="testpass123"
        )
        self.teacher = Teacher.objects.create(
            user=self.teacher_user, employee_id="T001"
        )

        self.student_user = User.objects.create_user(
            username="student1", email="student@test.com", password="testpass123"
        )
        self.student = Student.objects.create(
            user=self.student_user,
            admission_number="S001",
            current_class_id=self.class_obj,
        )

    def test_submission_creation(self):
        """Test submission creation"""
        submission = AssignmentSubmission.objects.create(
            assignment=self.assignment,
            student=self.student,
            content="This is my submission content",
        )

        self.assertEqual(submission.status, "submitted")
        self.assertFalse(submission.is_late)
        self.assertIsNone(submission.marks_obtained)
        self.assertIsNone(submission.percentage)

    def test_submission_late_detection(self):
        """Test automatic late submission detection"""
        # Create overdue assignment
        overdue_assignment = Assignment.objects.create(
            title="Overdue Assignment",
            class_id=self.class_obj,
            subject=self.subject,
            teacher=self.teacher,
            term=self.term,
            due_date=timezone.now() - timedelta(days=1),
            total_marks=100,
        )

        submission = AssignmentSubmission.objects.create(
            assignment=overdue_assignment,
            student=self.student,
            content="Late submission",
        )

        self.assertTrue(submission.is_late)

    def test_submission_percentage_calculation(self):
        """Test automatic percentage calculation"""
        submission = AssignmentSubmission.objects.create(
            assignment=self.assignment,
            student=self.student,
            content="Test submission",
            marks_obtained=85,
        )

        self.assertEqual(submission.percentage, 85.0)

    def test_submission_grade_calculation(self):
        """Test grade calculation method"""
        submission = AssignmentSubmission.objects.create(
            assignment=self.assignment,
            student=self.student,
            content="Test submission",
            marks_obtained=92,
        )

        grade = submission.calculate_grade()
        self.assertEqual(grade, "A+")

        submission.marks_obtained = 75
        submission.save()
        grade = submission.calculate_grade()
        self.assertEqual(grade, "B+")

    def test_submission_unique_constraint(self):
        """Test unique constraint on assignment-student pair"""
        AssignmentSubmission.objects.create(
            assignment=self.assignment, student=self.student, content="First submission"
        )

        # Attempt to create duplicate submission should raise error
        with self.assertRaises(IntegrityError):
            AssignmentSubmission.objects.create(
                assignment=self.assignment,
                student=self.student,
                content="Duplicate submission",
            )

    def test_submission_is_passed_property(self):
        """Test is_passed property"""
        self.assignment.passing_marks = 60
        self.assignment.save()

        # Passing submission
        passing_submission = AssignmentSubmission.objects.create(
            assignment=self.assignment,
            student=self.student,
            content="Passing submission",
            marks_obtained=75,
        )
        self.assertTrue(passing_submission.is_passed)

        # Failing submission
        failing_submission = AssignmentSubmission.objects.create(
            assignment=Assignment.objects.create(
                title="Another Assignment",
                class_id=self.class_obj,
                subject=self.subject,
                teacher=self.teacher,
                term=self.term,
                due_date=timezone.now() + timedelta(days=7),
                total_marks=100,
                passing_marks=60,
            ),
            student=Student.objects.create(
                user=User.objects.create_user(
                    username="student2",
                    email="student2@test.com",
                    password="testpass123",
                ),
                admission_number="S002",
                current_class_id=self.class_obj,
            ),
            content="Failing submission",
            marks_obtained=45,
        )
        self.assertFalse(failing_submission.is_passed)


class AssignmentServiceTestCase(TestCase):
    """
    Test cases for AssignmentService
    """

    def setUp(self):
        """Set up test data"""
        self.setUpAcademicStructure()

    def setUpAcademicStructure(self):
        """Helper method to set up academic structure"""
        self.academic_year = AcademicYear.objects.create(
            name="2024-2025",
            start_date="2024-04-01",
            end_date="2025-03-31",
            is_current=True,
        )

        self.term = Term.objects.create(
            academic_year=self.academic_year,
            name="First Term",
            term_number=1,
            start_date="2024-04-01",
            end_date="2024-08-31",
            is_current=True,
        )

        self.section = Section.objects.create(name="Primary")
        self.grade = Grade.objects.create(name="Grade 5", section=self.section)
        self.class_obj = Class.objects.create(
            grade=self.grade, name="A", academic_year=self.academic_year
        )

        self.subject = Subject.objects.create(name="Mathematics", code="MATH101")

        self.teacher_user = User.objects.create_user(
            username="teacher1", email="teacher@test.com", password="testpass123"
        )
        self.teacher = Teacher.objects.create(
            user=self.teacher_user, employee_id="T001"
        )

        self.student_user = User.objects.create_user(
            username="student1", email="student@test.com", password="testpass123"
        )
        self.student = Student.objects.create(
            user=self.student_user,
            admission_number="S001",
            current_class_id=self.class_obj,
        )

    def test_create_assignment_success(self):
        """Test successful assignment creation"""
        assignment_data = {
            "title": "Test Assignment",
            "description": "Test description",
            "class_id": self.class_obj,
            "subject": self.subject,
            "term": self.term,
            "due_date": timezone.now() + timedelta(days=7),
            "total_marks": 100,
            "passing_marks": 60,
        }

        assignment = AssignmentService.create_assignment(self.teacher, assignment_data)

        self.assertIsInstance(assignment, Assignment)
        self.assertEqual(assignment.title, "Test Assignment")
        self.assertEqual(assignment.teacher, self.teacher)
        self.assertEqual(assignment.status, "draft")

    def test_create_assignment_validation_error(self):
        """Test assignment creation with validation errors"""
        assignment_data = {
            "title": "Test Assignment",
            "class_id": self.class_obj,
            "subject": self.subject,
            "term": self.term,
            "due_date": timezone.now() - timedelta(days=1),  # Past due date
            "total_marks": 100,
        }

        with self.assertRaises(Exception):
            AssignmentService.create_assignment(self.teacher, assignment_data)

    def test_publish_assignment(self):
        """Test assignment publishing"""
        assignment = Assignment.objects.create(
            title="Test Assignment",
            class_id=self.class_obj,
            subject=self.subject,
            teacher=self.teacher,
            term=self.term,
            due_date=timezone.now() + timedelta(days=7),
            total_marks=100,
        )

        published_assignment = AssignmentService.publish_assignment(assignment.id)

        self.assertEqual(published_assignment.status, "published")
        self.assertIsNotNone(published_assignment.published_at)

    def test_get_assignment_analytics(self):
        """Test assignment analytics generation"""
        assignment = Assignment.objects.create(
            title="Test Assignment",
            class_id=self.class_obj,
            subject=self.subject,
            teacher=self.teacher,
            term=self.term,
            due_date=timezone.now() + timedelta(days=7),
            total_marks=100,
        )

        # Create some submissions
        AssignmentSubmission.objects.create(
            assignment=assignment,
            student=self.student,
            content="Test submission",
            marks_obtained=85,
            status="graded",
        )

        analytics = AssignmentService.get_assignment_analytics(assignment.id)

        self.assertIn("assignment_id", analytics)
        self.assertIn("completion_rate", analytics)
        self.assertIn("average_score", analytics)
        self.assertEqual(analytics["submission_count"], 1)
        self.assertEqual(analytics["graded_count"], 1)


class SubmissionServiceTestCase(TestCase):
    """
    Test cases for SubmissionService
    """

    def setUp(self):
        """Set up test data"""
        self.setUpAcademicStructure()
        self.assignment = Assignment.objects.create(
            title="Test Assignment",
            class_id=self.class_obj,
            subject=self.subject,
            teacher=self.teacher,
            term=self.term,
            due_date=timezone.now() + timedelta(days=7),
            total_marks=100,
            status="published",
        )

    def setUpAcademicStructure(self):
        """Helper method to set up academic structure"""
        self.academic_year = AcademicYear.objects.create(
            name="2024-2025",
            start_date="2024-04-01",
            end_date="2025-03-31",
            is_current=True,
        )

        self.term = Term.objects.create(
            academic_year=self.academic_year,
            name="First Term",
            term_number=1,
            start_date="2024-04-01",
            end_date="2024-08-31",
            is_current=True,
        )

        self.section = Section.objects.create(name="Primary")
        self.grade = Grade.objects.create(name="Grade 5", section=self.section)
        self.class_obj = Class.objects.create(
            grade=self.grade, name="A", academic_year=self.academic_year
        )

        self.subject = Subject.objects.create(name="Mathematics", code="MATH101")

        self.teacher_user = User.objects.create_user(
            username="teacher1", email="teacher@test.com", password="testpass123"
        )
        self.teacher = Teacher.objects.create(
            user=self.teacher_user, employee_id="T001"
        )

        self.student_user = User.objects.create_user(
            username="student1", email="student@test.com", password="testpass123"
        )
        self.student = Student.objects.create(
            user=self.student_user,
            admission_number="S001",
            current_class_id=self.class_obj,
        )

    def test_create_submission_success(self):
        """Test successful submission creation"""
        submission_data = {
            "content": "This is my submission",
            "submission_method": "online",
        }

        submission = SubmissionService.create_submission(
            self.student, self.assignment.id, submission_data
        )

        self.assertIsInstance(submission, AssignmentSubmission)
        self.assertEqual(submission.student, self.student)
        self.assertEqual(submission.assignment, self.assignment)
        self.assertEqual(submission.status, "submitted")

    def test_create_submission_for_unpublished_assignment(self):
        """Test submission creation for unpublished assignment"""
        unpublished_assignment = Assignment.objects.create(
            title="Unpublished Assignment",
            class_id=self.class_obj,
            subject=self.subject,
            teacher=self.teacher,
            term=self.term,
            due_date=timezone.now() + timedelta(days=7),
            total_marks=100,
            status="draft",  # Not published
        )

        submission_data = {
            "content": "This is my submission",
            "submission_method": "online",
        }

        with self.assertRaises(Exception):
            SubmissionService.create_submission(
                self.student, unpublished_assignment.id, submission_data
            )

    def test_get_student_submissions(self):
        """Test getting student submissions"""
        # Create submission
        AssignmentSubmission.objects.create(
            assignment=self.assignment, student=self.student, content="Test submission"
        )

        submissions_data = SubmissionService.get_student_submissions(self.student)

        self.assertEqual(submissions_data["total_count"], 1)
        self.assertEqual(submissions_data["pending_count"], 1)
        self.assertEqual(submissions_data["graded_count"], 0)


class GradingServiceTestCase(TestCase):
    """
    Test cases for GradingService
    """

    def setUp(self):
        """Set up test data"""
        self.setUpAcademicStructure()
        self.assignment = Assignment.objects.create(
            title="Test Assignment",
            class_id=self.class_obj,
            subject=self.subject,
            teacher=self.teacher,
            term=self.term,
            due_date=timezone.now() + timedelta(days=7),
            total_marks=100,
            status="published",
        )

        self.submission = AssignmentSubmission.objects.create(
            assignment=self.assignment, student=self.student, content="Test submission"
        )

    def setUpAcademicStructure(self):
        """Helper method to set up academic structure"""
        self.academic_year = AcademicYear.objects.create(
            name="2024-2025",
            start_date="2024-04-01",
            end_date="2025-03-31",
            is_current=True,
        )

        self.term = Term.objects.create(
            academic_year=self.academic_year,
            name="First Term",
            term_number=1,
            start_date="2024-04-01",
            end_date="2024-08-31",
            is_current=True,
        )

        self.section = Section.objects.create(name="Primary")
        self.grade = Grade.objects.create(name="Grade 5", section=self.section)
        self.class_obj = Class.objects.create(
            grade=self.grade, name="A", academic_year=self.academic_year
        )

        self.subject = Subject.objects.create(name="Mathematics", code="MATH101")

        self.teacher_user = User.objects.create_user(
            username="teacher1", email="teacher@test.com", password="testpass123"
        )
        self.teacher = Teacher.objects.create(
            user=self.teacher_user, employee_id="T001"
        )

        self.student_user = User.objects.create_user(
            username="student1", email="student@test.com", password="testpass123"
        )
        self.student = Student.objects.create(
            user=self.student_user,
            admission_number="S001",
            current_class_id=self.class_obj,
        )

    def test_grade_submission_success(self):
        """Test successful submission grading"""
        grading_data = {
            "marks_obtained": 85,
            "teacher_remarks": "Excellent work!",
            "strengths": "Good understanding of concepts",
            "improvements": "Work on presentation",
        }

        graded_submission = GradingService.grade_submission(
            self.submission.id, self.teacher, grading_data
        )

        self.assertEqual(graded_submission.marks_obtained, 85)
        self.assertEqual(graded_submission.status, "graded")
        self.assertEqual(graded_submission.graded_by, self.teacher)
        self.assertEqual(graded_submission.percentage, 85.0)
        self.assertIsNotNone(graded_submission.graded_at)

    def test_grade_submission_invalid_marks(self):
        """Test grading with invalid marks"""
        grading_data = {
            "marks_obtained": 150,  # Exceeds total marks
            "teacher_remarks": "Test remarks",
        }

        with self.assertRaises(Exception):
            GradingService.grade_submission(
                self.submission.id, self.teacher, grading_data
            )

    def test_get_grading_analytics(self):
        """Test grading analytics generation"""
        # Grade the submission first
        grading_data = {"marks_obtained": 75, "teacher_remarks": "Good work"}

        GradingService.grade_submission(self.submission.id, self.teacher, grading_data)

        analytics = GradingService.get_grading_analytics(self.teacher)

        self.assertIn("total_submissions", analytics)
        self.assertIn("graded_submissions", analytics)
        self.assertIn("grading_rate", analytics)
        self.assertEqual(analytics["graded_submissions"], 1)


class AssignmentViewTestCase(TestCase):
    """
    Test cases for Assignment views
    """

    def setUp(self):
        """Set up test data"""
        self.client = Client()
        self.setUpAcademicStructure()

    def setUpAcademicStructure(self):
        """Helper method to set up academic structure"""
        self.academic_year = AcademicYear.objects.create(
            name="2024-2025",
            start_date="2024-04-01",
            end_date="2025-03-31",
            is_current=True,
        )

        self.term = Term.objects.create(
            academic_year=self.academic_year,
            name="First Term",
            term_number=1,
            start_date="2024-04-01",
            end_date="2024-08-31",
            is_current=True,
        )

        self.section = Section.objects.create(name="Primary")
        self.grade = Grade.objects.create(name="Grade 5", section=self.section)
        self.class_obj = Class.objects.create(
            grade=self.grade, name="A", academic_year=self.academic_year
        )

        self.subject = Subject.objects.create(name="Mathematics", code="MATH101")

        self.teacher_user = User.objects.create_user(
            username="teacher1", email="teacher@test.com", password="testpass123"
        )
        self.teacher = Teacher.objects.create(
            user=self.teacher_user, employee_id="T001"
        )

        self.student_user = User.objects.create_user(
            username="student1", email="student@test.com", password="testpass123"
        )
        self.student = Student.objects.create(
            user=self.student_user,
            admission_number="S001",
            current_class_id=self.class_obj,
        )

    def test_assignment_list_view_teacher(self):
        """Test assignment list view for teachers"""
        self.client.login(username="teacher1", password="testpass123")

        # Create assignment
        Assignment.objects.create(
            title="Test Assignment",
            class_id=self.class_obj,
            subject=self.subject,
            teacher=self.teacher,
            term=self.term,
            due_date=timezone.now() + timedelta(days=7),
            total_marks=100,
        )

        response = self.client.get(reverse("assignments:assignment_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test Assignment")

    def test_assignment_list_view_student(self):
        """Test assignment list view for students"""
        self.client.login(username="student1", password="testpass123")

        # Create published assignment
        Assignment.objects.create(
            title="Published Assignment",
            class_id=self.class_obj,
            subject=self.subject,
            teacher=self.teacher,
            term=self.term,
            due_date=timezone.now() + timedelta(days=7),
            total_marks=100,
            status="published",
        )

        response = self.client.get(reverse("assignments:assignment_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Published Assignment")

    def test_assignment_create_view_teacher(self):
        """Test assignment creation view for teachers"""
        self.client.login(username="teacher1", password="testpass123")

        response = self.client.get(reverse("assignments:assignment_create"))
        self.assertEqual(response.status_code, 200)

        # Test form submission
        form_data = {
            "title": "New Assignment",
            "description": "Test description",
            "class_id": self.class_obj.id,
            "subject": self.subject.id,
            "term": self.term.id,
            "due_date": (timezone.now() + timedelta(days=7)).strftime("%Y-%m-%dT%H:%M"),
            "total_marks": 100,
            "submission_type": "online",
            "difficulty_level": "medium",
        }

        response = self.client.post(reverse("assignments:assignment_create"), form_data)
        self.assertEqual(
            response.status_code, 302
        )  # Redirect after successful creation

        # Check if assignment was created
        self.assertTrue(Assignment.objects.filter(title="New Assignment").exists())

    def test_assignment_create_view_student_forbidden(self):
        """Test that students cannot access assignment creation"""
        self.client.login(username="student1", password="testpass123")

        response = self.client.get(reverse("assignments:assignment_create"))
        self.assertEqual(response.status_code, 403)  # Forbidden

    def test_assignment_detail_view(self):
        """Test assignment detail view"""
        assignment = Assignment.objects.create(
            title="Detail Test Assignment",
            class_id=self.class_obj,
            subject=self.subject,
            teacher=self.teacher,
            term=self.term,
            due_date=timezone.now() + timedelta(days=7),
            total_marks=100,
            status="published",
        )

        # Test teacher view
        self.client.login(username="teacher1", password="testpass123")
        response = self.client.get(
            reverse("assignments:assignment_detail", kwargs={"pk": assignment.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Detail Test Assignment")

        # Test student view
        self.client.login(username="student1", password="testpass123")
        response = self.client.get(
            reverse("assignments:assignment_detail", kwargs={"pk": assignment.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Detail Test Assignment")


class AssignmentAPITestCase(TestCase):
    """
    Test cases for Assignment API endpoints
    """

    def setUp(self):
        """Set up test data"""
        self.client = Client()
        self.setUpAcademicStructure()

    def setUpAcademicStructure(self):
        """Helper method to set up academic structure"""
        self.academic_year = AcademicYear.objects.create(
            name="2024-2025",
            start_date="2024-04-01",
            end_date="2025-03-31",
            is_current=True,
        )

        self.term = Term.objects.create(
            academic_year=self.academic_year,
            name="First Term",
            term_number=1,
            start_date="2024-04-01",
            end_date="2024-08-31",
            is_current=True,
        )

        self.section = Section.objects.create(name="Primary")
        self.grade = Grade.objects.create(name="Grade 5", section=self.section)
        self.class_obj = Class.objects.create(
            grade=self.grade, name="A", academic_year=self.academic_year
        )

        self.subject = Subject.objects.create(name="Mathematics", code="MATH101")

        self.teacher_user = User.objects.create_user(
            username="teacher1", email="teacher@test.com", password="testpass123"
        )
        self.teacher = Teacher.objects.create(
            user=self.teacher_user, employee_id="T001"
        )

        self.student_user = User.objects.create_user(
            username="student1", email="student@test.com", password="testpass123"
        )
        self.student = Student.objects.create(
            user=self.student_user,
            admission_number="S001",
            current_class_id=self.class_obj,
        )

    def test_assignment_api_list(self):
        """Test assignment API list endpoint"""
        self.client.login(username="teacher1", password="testpass123")

        # Create assignment
        Assignment.objects.create(
            title="API Test Assignment",
            class_id=self.class_obj,
            subject=self.subject,
            teacher=self.teacher,
            term=self.term,
            due_date=timezone.now() + timedelta(days=7),
            total_marks=100,
        )

        response = self.client.get("/assignments/api/assignments/")
        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertIn("results", data)
        self.assertEqual(len(data["results"]), 1)
        self.assertEqual(data["results"][0]["title"], "API Test Assignment")

    def test_assignment_api_create(self):
        """Test assignment API creation endpoint"""
        self.client.login(username="teacher1", password="testpass123")

        assignment_data = {
            "title": "API Created Assignment",
            "description": "Created via API",
            "class_id": self.class_obj.id,
            "subject": self.subject.id,
            "term": self.term.id,
            "due_date": (timezone.now() + timedelta(days=7)).isoformat(),
            "total_marks": 100,
            "submission_type": "online",
            "difficulty_level": "medium",
        }

        response = self.client.post(
            "/assignments/api/assignments/",
            json.dumps(assignment_data),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(
            Assignment.objects.filter(title="API Created Assignment").exists()
        )

    def test_assignment_api_unauthorized(self):
        """Test API access without authentication"""
        response = self.client.get("/assignments/api/assignments/")
        self.assertEqual(response.status_code, 401)  # Unauthorized


class PlagiarismServiceTestCase(TestCase):
    """
    Test cases for PlagiarismService
    """

    def setUp(self):
        """Set up test data"""
        self.setUpAcademicStructure()
        self.assignment = Assignment.objects.create(
            title="Plagiarism Test Assignment",
            class_id=self.class_obj,
            subject=self.subject,
            teacher=self.teacher,
            term=self.term,
            due_date=timezone.now() + timedelta(days=7),
            total_marks=100,
        )

    def setUpAcademicStructure(self):
        """Helper method to set up academic structure"""
        self.academic_year = AcademicYear.objects.create(
            name="2024-2025",
            start_date="2024-04-01",
            end_date="2025-03-31",
            is_current=True,
        )

        self.term = Term.objects.create(
            academic_year=self.academic_year,
            name="First Term",
            term_number=1,
            start_date="2024-04-01",
            end_date="2024-08-31",
            is_current=True,
        )

        self.section = Section.objects.create(name="Primary")
        self.grade = Grade.objects.create(name="Grade 5", section=self.section)
        self.class_obj = Class.objects.create(
            grade=self.grade, name="A", academic_year=self.academic_year
        )

        self.subject = Subject.objects.create(name="Mathematics", code="MATH101")

        self.teacher_user = User.objects.create_user(
            username="teacher1", email="teacher@test.com", password="testpass123"
        )
        self.teacher = Teacher.objects.create(
            user=self.teacher_user, employee_id="T001"
        )

        self.student_user = User.objects.create_user(
            username="student1", email="student@test.com", password="testpass123"
        )
        self.student = Student.objects.create(
            user=self.student_user,
            admission_number="S001",
            current_class_id=self.class_obj,
        )

        self.student_user2 = User.objects.create_user(
            username="student2", email="student2@test.com", password="testpass123"
        )
        self.student2 = Student.objects.create(
            user=self.student_user2,
            admission_number="S002",
            current_class_id=self.class_obj,
        )

    def test_plagiarism_check_identical_content(self):
        """Test plagiarism detection with identical content"""
        # Create first submission
        submission1 = AssignmentSubmission.objects.create(
            assignment=self.assignment,
            student=self.student,
            content="This is the exact same content for both submissions.",
        )

        # Create second submission with identical content
        submission2 = AssignmentSubmission.objects.create(
            assignment=self.assignment,
            student=self.student2,
            content="This is the exact same content for both submissions.",
        )

        # Check plagiarism for second submission
        result = PlagiarismService.check_submission_plagiarism(submission2.id)

        self.assertIn("plagiarism_score", result)
        self.assertIn("is_suspicious", result)
        self.assertTrue(result["plagiarism_score"] > 50)  # Should be high similarity

    def test_plagiarism_check_unique_content(self):
        """Test plagiarism detection with unique content"""
        # Create submission with unique content
        submission = AssignmentSubmission.objects.create(
            assignment=self.assignment,
            student=self.student,
            content="This is completely unique content that should not match anything else.",
        )

        result = PlagiarismService.check_submission_plagiarism(submission.id)

        self.assertIn("plagiarism_score", result)
        self.assertIn("is_suspicious", result)
        self.assertFalse(result["is_suspicious"])
        self.assertEqual(
            result["plagiarism_score"], 0
        )  # No other submissions to compare against

    def test_batch_plagiarism_check(self):
        """Test batch plagiarism checking"""
        # Create multiple submissions
        AssignmentSubmission.objects.create(
            assignment=self.assignment,
            student=self.student,
            content="First submission content",
        )

        AssignmentSubmission.objects.create(
            assignment=self.assignment,
            student=self.student2,
            content="Second submission content",
        )

        result = PlagiarismService.batch_plagiarism_check(self.assignment.id)

        self.assertIn("checked", result)
        self.assertIn("total", result)
        self.assertEqual(result["total"], 2)


class AssignmentAnalyticsTestCase(TestCase):
    """
    Test cases for Assignment Analytics
    """

    def setUp(self):
        """Set up test data"""
        self.setUpAcademicStructure()

    def setUpAcademicStructure(self):
        """Helper method to set up academic structure"""
        self.academic_year = AcademicYear.objects.create(
            name="2024-2025",
            start_date="2024-04-01",
            end_date="2025-03-31",
            is_current=True,
        )

        self.term = Term.objects.create(
            academic_year=self.academic_year,
            name="First Term",
            term_number=1,
            start_date="2024-04-01",
            end_date="2024-08-31",
            is_current=True,
        )

        self.section = Section.objects.create(name="Primary")
        self.grade = Grade.objects.create(name="Grade 5", section=self.section)
        self.class_obj = Class.objects.create(
            grade=self.grade, name="A", academic_year=self.academic_year
        )

        self.subject = Subject.objects.create(name="Mathematics", code="MATH101")

        self.teacher_user = User.objects.create_user(
            username="teacher1", email="teacher@test.com", password="testpass123"
        )
        self.teacher = Teacher.objects.create(
            user=self.teacher_user, employee_id="T001"
        )

        self.student_user = User.objects.create_user(
            username="student1", email="student@test.com", password="testpass123"
        )
        self.student = Student.objects.create(
            user=self.student_user,
            admission_number="S001",
            current_class_id=self.class_obj,
        )

    def test_student_performance_analytics(self):
        """Test student performance analytics generation"""
        # Create assignment and submission
        assignment = Assignment.objects.create(
            title="Analytics Test Assignment",
            class_id=self.class_obj,
            subject=self.subject,
            teacher=self.teacher,
            term=self.term,
            due_date=timezone.now() + timedelta(days=7),
            total_marks=100,
        )

        submission = AssignmentSubmission.objects.create(
            assignment=assignment,
            student=self.student,
            content="Test submission",
            marks_obtained=85,
            status="graded",
        )

        analytics = AssignmentAnalyticsService.get_student_performance_analytics(
            self.student.id
        )

        self.assertIn("student_info", analytics)
        self.assertIn("basic_stats", analytics)
        self.assertIn("performance_stats", analytics)
        self.assertEqual(analytics["basic_stats"]["total_assignments"], 1)
        self.assertEqual(analytics["basic_stats"]["graded_assignments"], 1)
        self.assertEqual(analytics["performance_stats"]["average_score"], 85)

    def test_teacher_analytics(self):
        """Test teacher analytics generation"""
        # Create assignment
        assignment = Assignment.objects.create(
            title="Teacher Analytics Test",
            class_id=self.class_obj,
            subject=self.subject,
            teacher=self.teacher,
            term=self.term,
            due_date=timezone.now() + timedelta(days=7),
            total_marks=100,
        )

        analytics = AssignmentAnalyticsService.get_teacher_analytics(self.teacher.id)

        self.assertIn("teacher_info", analytics)
        self.assertIn("assignment_stats", analytics)
        self.assertIn("grading_stats", analytics)
        self.assertEqual(analytics["assignment_stats"]["total_assignments"], 1)

    def test_class_analytics(self):
        """Test class analytics generation"""
        # Create assignment
        assignment = Assignment.objects.create(
            title="Class Analytics Test",
            class_id=self.class_obj,
            subject=self.subject,
            teacher=self.teacher,
            term=self.term,
            due_date=timezone.now() + timedelta(days=7),
            total_marks=100,
        )

        analytics = AssignmentAnalyticsService.get_class_analytics(self.class_obj.id)

        self.assertIn("class_info", analytics)
        self.assertIn("assignment_overview", analytics)
        self.assertEqual(analytics["assignment_overview"]["total_assignments"], 1)
