from django.test import TestCase, TransactionTestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from rest_framework.test import APITestCase
from rest_framework import status
from django.urls import reverse
import json

from .models import Subject, Syllabus, TopicProgress, SubjectAssignment
from .services import SyllabusService, CurriculumService, SubjectAnalyticsService
from academics.models import Grade, AcademicYear, Term, Class, Department, Section
from teachers.models import Teacher

User = get_user_model()


class SubjectModelTest(TestCase):
    """Test cases for Subject model."""

    def setUp(self):
        """Set up test data."""
        self.department = Department.objects.create(
            name="Mathematics Department",
            description="Mathematics and related subjects",
        )

        self.grade1 = Grade.objects.create(name="Grade 1", order_sequence=1)

        self.grade2 = Grade.objects.create(name="Grade 2", order_sequence=2)

    def test_subject_creation(self):
        """Test basic subject creation."""
        subject = Subject.objects.create(
            name="Mathematics",
            code="MATH101",
            department=self.department,
            credit_hours=3,
            grade_level=[self.grade1.id, self.grade2.id],
        )

        self.assertEqual(subject.name, "Mathematics")
        self.assertEqual(subject.code, "MATH101")
        self.assertEqual(subject.credit_hours, 3)
        self.assertTrue(subject.is_active)
        self.assertFalse(subject.is_elective)

    def test_subject_code_uniqueness(self):
        """Test that subject codes must be unique."""
        Subject.objects.create(
            name="Mathematics", code="MATH101", department=self.department
        )

        with self.assertRaises(IntegrityError):
            Subject.objects.create(
                name="Advanced Mathematics",
                code="MATH101",  # Duplicate code
                department=self.department,
            )

    def test_subject_grade_applicability(self):
        """Test grade level applicability checking."""
        subject = Subject.objects.create(
            name="Mathematics",
            code="MATH101",
            department=self.department,
            grade_level=[self.grade1.id],
        )

        self.assertTrue(subject.is_applicable_for_grade(self.grade1.id))
        self.assertFalse(subject.is_applicable_for_grade(self.grade2.id))

        # Test empty grade_level (applies to all grades)
        subject.grade_level = []
        subject.save()

        self.assertTrue(subject.is_applicable_for_grade(self.grade1.id))
        self.assertTrue(subject.is_applicable_for_grade(self.grade2.id))

    def test_subject_string_representation(self):
        """Test subject string representation."""
        subject = Subject.objects.create(
            name="Mathematics", code="MATH101", department=self.department
        )

        self.assertEqual(str(subject), "MATH101 - Mathematics")


class SyllabusModelTest(TestCase):
    """Test cases for Syllabus model."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )

        self.department = Department.objects.create(name="Mathematics Department")

        self.grade = Grade.objects.create(name="Grade 1", order_sequence=1)

        self.academic_year = AcademicYear.objects.create(
            name="2024-2025",
            start_date="2024-04-01",
            end_date="2025-03-31",
            is_current=True,
        )

        self.term = Term.objects.create(
            academic_year=self.academic_year,
            name="Term 1",
            term_number=1,
            start_date="2024-04-01",
            end_date="2024-07-31",
        )

        self.subject = Subject.objects.create(
            name="Mathematics",
            code="MATH101",
            department=self.department,
            grade_level=[self.grade.id],
        )

    def test_syllabus_creation(self):
        """Test basic syllabus creation."""
        syllabus = Syllabus.objects.create(
            subject=self.subject,
            grade=self.grade,
            academic_year=self.academic_year,
            term=self.term,
            title="Mathematics Term 1",
            description="Basic mathematics concepts",
            created_by=self.user,
            last_updated_by=self.user,
        )

        self.assertEqual(syllabus.subject, self.subject)
        self.assertEqual(syllabus.grade, self.grade)
        self.assertEqual(syllabus.completion_percentage, 0.0)
        self.assertTrue(syllabus.is_active)

    def test_syllabus_unique_constraint(self):
        """Test unique constraint on syllabus."""
        Syllabus.objects.create(
            subject=self.subject,
            grade=self.grade,
            academic_year=self.academic_year,
            term=self.term,
            title="Mathematics Term 1",
            created_by=self.user,
            last_updated_by=self.user,
        )

        with self.assertRaises(IntegrityError):
            Syllabus.objects.create(
                subject=self.subject,
                grade=self.grade,
                academic_year=self.academic_year,
                term=self.term,  # Same combination
                title="Duplicate Syllabus",
                created_by=self.user,
                last_updated_by=self.user,
            )

    def test_syllabus_topic_management(self):
        """Test topic addition and completion tracking."""
        syllabus = Syllabus.objects.create(
            subject=self.subject,
            grade=self.grade,
            academic_year=self.academic_year,
            term=self.term,
            title="Mathematics Term 1",
            content={
                "topics": [
                    {"name": "Addition", "completed": False},
                    {"name": "Subtraction", "completed": True},
                ]
            },
            created_by=self.user,
            last_updated_by=self.user,
        )

        self.assertEqual(syllabus.get_total_topics(), 2)
        self.assertEqual(syllabus.get_completed_topics(), 1)

    def test_syllabus_progress_status(self):
        """Test progress status calculation."""
        syllabus = Syllabus.objects.create(
            subject=self.subject,
            grade=self.grade,
            academic_year=self.academic_year,
            term=self.term,
            title="Mathematics Term 1",
            completion_percentage=0.0,
            created_by=self.user,
            last_updated_by=self.user,
        )

        self.assertEqual(syllabus.progress_status, "not_started")

        syllabus.completion_percentage = 30.0
        self.assertEqual(syllabus.progress_status, "in_progress")

        syllabus.completion_percentage = 70.0
        self.assertEqual(syllabus.progress_status, "nearing_completion")

        syllabus.completion_percentage = 100.0
        self.assertEqual(syllabus.progress_status, "completed")


class SyllabusServiceTest(TestCase):
    """Test cases for SyllabusService."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )

        self.department = Department.objects.create(name="Mathematics Department")

        self.grade = Grade.objects.create(name="Grade 1", order_sequence=1)

        self.academic_year = AcademicYear.objects.create(
            name="2024-2025", start_date="2024-04-01", end_date="2025-03-31"
        )

        self.term = Term.objects.create(
            academic_year=self.academic_year,
            name="Term 1",
            term_number=1,
            start_date="2024-04-01",
            end_date="2024-07-31",
        )

        self.subject = Subject.objects.create(
            name="Mathematics",
            code="MATH101",
            department=self.department,
            grade_level=[self.grade.id],
        )

    def test_create_syllabus_service(self):
        """Test syllabus creation through service."""
        syllabus = SyllabusService.create_syllabus(
            subject_id=self.subject.id,
            grade_id=self.grade.id,
            academic_year_id=self.academic_year.id,
            term_id=self.term.id,
            title="Mathematics Term 1",
            created_by_id=self.user.id,
            description="Basic mathematics",
        )

        self.assertIsInstance(syllabus, Syllabus)
        self.assertEqual(syllabus.title, "Mathematics Term 1")
        self.assertEqual(syllabus.created_by, self.user)

    def test_create_syllabus_validation(self):
        """Test syllabus creation validation."""
        # Test with non-applicable grade
        other_grade = Grade.objects.create(name="Grade 5", order_sequence=5)

        with self.assertRaises(ValidationError):
            SyllabusService.create_syllabus(
                subject_id=self.subject.id,
                grade_id=other_grade.id,  # Not in subject's grade_level
                academic_year_id=self.academic_year.id,
                term_id=self.term.id,
                title="Invalid Syllabus",
                created_by_id=self.user.id,
            )

    def test_mark_topic_completed(self):
        """Test marking topics as completed."""
        syllabus = SyllabusService.create_syllabus(
            subject_id=self.subject.id,
            grade_id=self.grade.id,
            academic_year_id=self.academic_year.id,
            term_id=self.term.id,
            title="Mathematics Term 1",
            created_by_id=self.user.id,
            content={
                "topics": [
                    {"name": "Addition", "completed": False},
                    {"name": "Subtraction", "completed": False},
                ]
            },
        )

        # Mark first topic as completed
        topic_progress = SyllabusService.mark_topic_completed(
            syllabus.id, 0, {"hours_taught": 5, "teaching_method": "Interactive"}
        )

        self.assertTrue(topic_progress.is_completed)
        self.assertEqual(topic_progress.hours_taught, 5)

        # Check syllabus completion percentage updated
        syllabus.refresh_from_db()
        self.assertEqual(syllabus.completion_percentage, 50.0)

    def test_get_syllabus_progress(self):
        """Test getting syllabus progress data."""
        syllabus = SyllabusService.create_syllabus(
            subject_id=self.subject.id,
            grade_id=self.grade.id,
            academic_year_id=self.academic_year.id,
            term_id=self.term.id,
            title="Mathematics Term 1",
            created_by_id=self.user.id,
            content={
                "topics": [
                    {"name": "Addition", "completed": True},
                    {"name": "Subtraction", "completed": False},
                ]
            },
        )

        progress_data = SyllabusService.get_syllabus_progress(syllabus.id)

        self.assertEqual(progress_data["total_topics"], 2)
        self.assertEqual(progress_data["completed_topics"], 1)
        self.assertEqual(progress_data["remaining_topics"], 1)
        self.assertEqual(progress_data["syllabus_id"], syllabus.id)


class CurriculumServiceTest(TestCase):
    """Test cases for CurriculumService."""

    def setUp(self):
        """Set up test data."""
        self.department = Department.objects.create(name="Mathematics Department")

        self.grade1 = Grade.objects.create(name="Grade 1", order_sequence=1)

        self.grade2 = Grade.objects.create(name="Grade 2", order_sequence=2)

    def test_create_subject_service(self):
        """Test subject creation through service."""
        subject = CurriculumService.create_subject(
            name="Mathematics",
            code="MATH101",
            department_id=self.department.id,
            grade_level=[self.grade1.id, self.grade2.id],
            credit_hours=3,
            description="Basic mathematics",
        )

        self.assertIsInstance(subject, Subject)
        self.assertEqual(subject.name, "Mathematics")
        self.assertEqual(subject.credit_hours, 3)
        self.assertEqual(len(subject.grade_level), 2)

    def test_get_subjects_by_grade(self):
        """Test getting subjects by grade."""
        # Create subjects with different grade applicabilities
        subject1 = CurriculumService.create_subject(
            name="Mathematics",
            code="MATH101",
            department_id=self.department.id,
            grade_level=[self.grade1.id],
        )

        subject2 = CurriculumService.create_subject(
            name="Science",
            code="SCI101",
            department_id=self.department.id,
            grade_level=[self.grade1.id, self.grade2.id],
        )

        subject3 = CurriculumService.create_subject(
            name="Advanced Math",
            code="MATH201",
            department_id=self.department.id,
            grade_level=[self.grade2.id],
        )

        # Test grade 1 subjects
        grade1_subjects = CurriculumService.get_subjects_by_grade(self.grade1.id)
        self.assertEqual(grade1_subjects.count(), 2)

        # Test grade 2 subjects
        grade2_subjects = CurriculumService.get_subjects_by_grade(self.grade2.id)
        self.assertEqual(grade2_subjects.count(), 2)

    def test_bulk_import_subjects(self):
        """Test bulk import of subjects."""
        subjects_data = [
            {
                "name": "Mathematics",
                "code": "MATH101",
                "credit_hours": 3,
                "description": "Basic math",
            },
            {
                "name": "Science",
                "code": "SCI101",
                "credit_hours": 4,
                "description": "Basic science",
            },
            {
                "name": "Invalid Subject",
                "code": "MATH101",  # Duplicate code
                "credit_hours": 2,
            },
        ]

        created_subjects, errors = CurriculumService.bulk_import_subjects(
            subjects_data, self.department.id
        )

        self.assertEqual(len(created_subjects), 2)
        self.assertEqual(len(errors), 1)
        self.assertIn("already exists", errors[0])


class SubjectAPITest(APITestCase):
    """Test cases for Subject API endpoints."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )

        self.department = Department.objects.create(name="Mathematics Department")

        self.grade = Grade.objects.create(name="Grade 1", order_sequence=1)

        self.subject = Subject.objects.create(
            name="Mathematics",
            code="MATH101",
            department=self.department,
            grade_level=[self.grade.id],
        )

    def test_subject_list_api(self):
        """Test subject list API endpoint."""
        self.client.force_authenticate(user=self.user)

        url = reverse("subjects_api:subject-list-create")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)

    def test_subject_create_api(self):
        """Test subject creation API endpoint."""
        self.client.force_authenticate(user=self.user)

        url = reverse("subjects_api:subject-list-create")
        data = {
            "name": "Science",
            "code": "SCI101",
            "department": self.department.id,
            "credit_hours": 3,
            "grade_level": [self.grade.id],
        }

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Subject.objects.count(), 2)

    def test_subject_detail_api(self):
        """Test subject detail API endpoint."""
        self.client.force_authenticate(user=self.user)

        url = reverse("subjects_api:subject-detail", kwargs={"pk": self.subject.pk})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "Mathematics")

    def test_subject_update_api(self):
        """Test subject update API endpoint."""
        self.client.force_authenticate(user=self.user)

        url = reverse("subjects_api:subject-detail", kwargs={"pk": self.subject.pk})
        data = {
            "name": "Advanced Mathematics",
            "code": "MATH101",
            "department": self.department.id,
            "credit_hours": 4,
        }

        response = self.client.put(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.subject.refresh_from_db()
        self.assertEqual(self.subject.name, "Advanced Mathematics")
        self.assertEqual(self.subject.credit_hours, 4)

    def test_subject_delete_api(self):
        """Test subject soft delete API endpoint."""
        self.client.force_authenticate(user=self.user)

        url = reverse("subjects_api:subject-detail", kwargs={"pk": self.subject.pk})
        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        self.subject.refresh_from_db()
        self.assertFalse(self.subject.is_active)


class SubjectAnalyticsServiceTest(TestCase):
    """Test cases for SubjectAnalyticsService."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )

        self.department = Department.objects.create(name="Mathematics Department")

        self.grade = Grade.objects.create(name="Grade 1", order_sequence=1)

        self.academic_year = AcademicYear.objects.create(
            name="2024-2025", start_date="2024-04-01", end_date="2025-03-31"
        )

        self.term = Term.objects.create(
            academic_year=self.academic_year,
            name="Term 1",
            term_number=1,
            start_date="2024-04-01",
            end_date="2024-07-31",
        )

        self.subject = Subject.objects.create(
            name="Mathematics",
            code="MATH101",
            department=self.department,
            grade_level=[self.grade.id],
        )

        # Create test syllabi
        self.syllabus1 = Syllabus.objects.create(
            subject=self.subject,
            grade=self.grade,
            academic_year=self.academic_year,
            term=self.term,
            title="Mathematics Term 1",
            completion_percentage=50.0,
            created_by=self.user,
            last_updated_by=self.user,
        )

    def test_department_performance_analytics(self):
        """Test department performance analytics."""
        analytics = SubjectAnalyticsService.get_department_performance_analytics(
            self.department.id, self.academic_year.id
        )

        self.assertIn("overview", analytics)
        self.assertIn("by_grade", analytics)
        self.assertIn("by_subject", analytics)
        self.assertEqual(analytics["overview"]["total_syllabi"], 1)

    def test_curriculum_analytics_with_no_data(self):
        """Test analytics when no data exists."""
        # Delete test data
        self.syllabus1.delete()

        analytics = SubjectAnalyticsService.get_department_performance_analytics(
            self.department.id, self.academic_year.id
        )

        self.assertIn("message", analytics)

    def test_completion_forecasting(self):
        """Test completion forecasting functionality."""
        forecast = SubjectAnalyticsService.get_completion_forecasting(
            self.academic_year.id
        )

        self.assertIn("forecasts", forecast)
        self.assertIn("recommendations", forecast)
        self.assertEqual(forecast["academic_year_id"], self.academic_year.id)


class IntegrationTest(TransactionTestCase):
    """Integration tests for the entire subjects module."""

    def setUp(self):
        """Set up comprehensive test data."""
        # Create users
        self.admin_user = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="adminpass123",
            is_staff=True,
        )

        self.teacher_user = User.objects.create_user(
            username="teacher", email="teacher@example.com", password="teacherpass123"
        )

        # Create academic structure
        self.department = Department.objects.create(name="Mathematics Department")

        self.section = Section.objects.create(name="Primary Section")

        self.grade = Grade.objects.create(
            name="Grade 1", section=self.section, order_sequence=1
        )

        self.academic_year = AcademicYear.objects.create(
            name="2024-2025",
            start_date="2024-04-01",
            end_date="2025-03-31",
            is_current=True,
        )

        self.term = Term.objects.create(
            academic_year=self.academic_year,
            name="Term 1",
            term_number=1,
            start_date="2024-04-01",
            end_date="2024-07-31",
            is_current=True,
        )

        self.class_obj = Class.objects.create(
            name="North",
            grade=self.grade,
            academic_year=self.academic_year,
            capacity=30,
        )

        # Create teacher
        self.teacher = Teacher.objects.create(
            user=self.teacher_user,
            employee_id="T001",
            department=self.department,
            joining_date="2024-01-01",
        )

    def test_complete_workflow(self):
        """Test complete workflow from subject creation to analytics."""
        # 1. Create subject
        subject = CurriculumService.create_subject(
            name="Mathematics",
            code="MATH101",
            department_id=self.department.id,
            grade_level=[self.grade.id],
            credit_hours=3,
        )

        # 2. Create syllabus
        syllabus = SyllabusService.create_syllabus(
            subject_id=subject.id,
            grade_id=self.grade.id,
            academic_year_id=self.academic_year.id,
            term_id=self.term.id,
            title="Mathematics Term 1",
            created_by_id=self.admin_user.id,
            content={
                "topics": [
                    {"name": "Addition", "completed": False},
                    {"name": "Subtraction", "completed": False},
                    {"name": "Multiplication", "completed": False},
                ]
            },
        )

        # 3. Create subject assignment
        assignment = CurriculumService.assign_teacher_to_subject(
            teacher_id=self.teacher.id,
            subject_id=subject.id,
            class_id=self.class_obj.id,
            academic_year_id=self.academic_year.id,
            term_id=self.term.id,
            assigned_by_id=self.admin_user.id,
        )

        # 4. Mark some topics as completed
        SyllabusService.mark_topic_completed(syllabus.id, 0, {"hours_taught": 3})
        SyllabusService.mark_topic_completed(syllabus.id, 1, {"hours_taught": 4})

        # 5. Get progress analytics
        progress = SyllabusService.get_syllabus_progress(syllabus.id)

        # 6. Get teacher workload
        workload = CurriculumService.get_teacher_workload(
            self.teacher.id, self.academic_year.id
        )

        # 7. Get curriculum analytics
        analytics = CurriculumService.get_curriculum_analytics(self.academic_year.id)

        # Assertions
        self.assertEqual(subject.name, "Mathematics")
        self.assertEqual(syllabus.completion_percentage, 66.67)  # 2/3 topics completed
        self.assertIsInstance(assignment, SubjectAssignment)

        self.assertEqual(progress["completed_topics"], 2)
        self.assertEqual(progress["total_topics"], 3)

        self.assertEqual(workload["total_subjects"], 1)
        self.assertEqual(workload["total_classes"], 1)

        self.assertGreater(analytics["overview"]["total_syllabi"], 0)
        self.assertGreater(analytics["overview"]["average_completion"], 0)

    def test_error_handling(self):
        """Test error handling in various scenarios."""
        # Test creating syllabus with invalid data
        with self.assertRaises(ValidationError):
            SyllabusService.create_syllabus(
                subject_id=999,  # Non-existent subject
                grade_id=self.grade.id,
                academic_year_id=self.academic_year.id,
                term_id=self.term.id,
                title="Invalid Syllabus",
                created_by_id=self.admin_user.id,
            )

        # Test analytics with non-existent academic year
        analytics = CurriculumService.get_curriculum_analytics(999)
        self.assertEqual(analytics["overview"]["total_syllabi"], 0)

    def test_performance_with_large_dataset(self):
        """Test performance with larger dataset."""
        # Create multiple subjects and syllabi
        subjects = []
        for i in range(10):
            subject = Subject.objects.create(
                name=f"Subject {i}",
                code=f"SUB{i:03d}",
                department=self.department,
                grade_level=[self.grade.id],
            )
            subjects.append(subject)

        # Create syllabi for each subject
        for subject in subjects:
            Syllabus.objects.create(
                subject=subject,
                grade=self.grade,
                academic_year=self.academic_year,
                term=self.term,
                title=f"{subject.name} Syllabus",
                completion_percentage=50.0,
                created_by=self.admin_user,
                last_updated_by=self.admin_user,
            )

        # Test analytics performance
        analytics = CurriculumService.get_curriculum_analytics(self.academic_year.id)

        self.assertEqual(analytics["overview"]["total_syllabi"], 10)
        self.assertEqual(analytics["overview"]["average_completion"], 50.0)
