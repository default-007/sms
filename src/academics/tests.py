"""
Tests for Academics Module

This module contains comprehensive tests for the academics app,
including model tests, service tests, and API tests.
"""

from datetime import datetime, timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .models import AcademicYear, Class, Department, Grade, Section, Term
from .services import (
    AcademicYearService,
    ClassService,
    GradeService,
    SectionService,
    TermService,
)

User = get_user_model()


class AcademicsModelTestCase(TestCase):
    """Test cases for academics models"""

    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )

        self.department = Department.objects.create(
            name="Test Department", description="Test department description"
        )

        self.academic_year = AcademicYear.objects.create(
            name="2024-2025",
            start_date=datetime(2024, 4, 1).date(),
            end_date=datetime(2025, 3, 31).date(),
            is_current=True,
            created_by=self.user,
        )

        self.section = Section.objects.create(
            name="Test Section",
            description="Test section description",
            department=self.department,
            order_sequence=1,
        )

        self.grade = Grade.objects.create(
            name="Grade 1",
            section=self.section,
            order_sequence=1,
            minimum_age=6,
            maximum_age=7,
        )

    def test_department_model(self):
        """Test Department model"""
        self.assertEqual(str(self.department), "Test Department")
        self.assertTrue(self.department.is_active)
        self.assertEqual(self.department.get_teachers_count(), 0)
        self.assertEqual(self.department.get_subjects_count(), 0)

    def test_academic_year_model(self):
        """Test AcademicYear model"""
        self.assertEqual(str(self.academic_year), "2024-2025")
        self.assertTrue(self.academic_year.is_current)
        self.assertEqual(self.academic_year.created_by, self.user)

        # Test date validation
        with self.assertRaises(ValidationError):
            invalid_year = AcademicYear(
                name="Invalid Year",
                start_date=datetime(2024, 6, 1).date(),
                end_date=datetime(2024, 4, 1).date(),  # End before start
                created_by=self.user,
            )
            invalid_year.full_clean()

    def test_academic_year_current_constraint(self):
        """Test that only one academic year can be current"""
        # Create another academic year
        new_year = AcademicYear.objects.create(
            name="2025-2026",
            start_date=datetime(2025, 4, 1).date(),
            end_date=datetime(2026, 3, 31).date(),
            is_current=True,
            created_by=self.user,
        )

        # Refresh from database
        self.academic_year.refresh_from_db()

        # Original should no longer be current
        self.assertFalse(self.academic_year.is_current)
        self.assertTrue(new_year.is_current)

    def test_section_model(self):
        """Test Section model"""
        self.assertEqual(str(self.section), "Test Section")
        self.assertEqual(self.section.get_grades_count(), 1)
        self.assertEqual(self.section.department, self.department)

    def test_grade_model(self):
        """Test Grade model"""
        self.assertEqual(str(self.grade), "Test Section - Grade 1")
        self.assertEqual(self.grade.display_name, "Test Section - Grade 1")
        self.assertEqual(self.grade.section, self.section)

        # Test age validation
        with self.assertRaises(ValidationError):
            invalid_grade = Grade(
                name="Invalid Grade",
                section=self.section,
                minimum_age=10,
                maximum_age=8,  # Max less than min
            )
            invalid_grade.full_clean()

    def test_class_model(self):
        """Test Class model"""
        test_class = Class.objects.create(
            name="A", grade=self.grade, academic_year=self.academic_year, capacity=30
        )

        self.assertEqual(str(test_class), "Grade 1 A")
        self.assertEqual(test_class.display_name, "Grade 1 A")
        self.assertEqual(test_class.full_name, "Test Section - Grade 1 A")
        self.assertEqual(test_class.section, self.grade.section)  # Auto-set
        self.assertEqual(test_class.get_students_count(), 0)
        self.assertEqual(test_class.get_available_capacity(), 30)
        self.assertFalse(test_class.is_full())

    def test_term_model(self):
        """Test Term model"""
        term = Term.objects.create(
            academic_year=self.academic_year,
            name="First Term",
            term_number=1,
            start_date=datetime(2024, 4, 1).date(),
            end_date=datetime(2024, 7, 31).date(),
            is_current=True,
        )

        self.assertEqual(str(term), "2024-2025 - First Term")
        self.assertTrue(term.is_current)
        self.assertEqual(term.get_duration_days(), 122)

        # Test date validation
        with self.assertRaises(ValidationError):
            invalid_term = Term(
                academic_year=self.academic_year,
                name="Invalid Term",
                term_number=2,
                start_date=datetime(2024, 8, 1).date(),
                end_date=datetime(2024, 7, 1).date(),  # End before start
            )
            invalid_term.full_clean()


class AcademicYearServiceTestCase(TestCase):
    """Test cases for AcademicYearService"""

    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )

    def test_create_academic_year(self):
        """Test academic year creation"""
        start_date = datetime(2024, 4, 1).date()
        end_date = datetime(2025, 3, 31).date()

        academic_year = AcademicYearService.create_academic_year(
            name="2024-2025",
            start_date=start_date,
            end_date=end_date,
            user=self.user,
            is_current=True,
        )

        self.assertEqual(academic_year.name, "2024-2025")
        self.assertEqual(academic_year.start_date, start_date)
        self.assertEqual(academic_year.end_date, end_date)
        self.assertTrue(academic_year.is_current)
        self.assertEqual(academic_year.created_by, self.user)

    def test_create_academic_year_with_terms(self):
        """Test academic year creation with terms"""
        start_date = datetime(2024, 4, 1).date()
        end_date = datetime(2025, 3, 31).date()

        academic_year = AcademicYearService.setup_academic_year_with_terms(
            name="2024-2025",
            start_date=start_date,
            end_date=end_date,
            num_terms=3,
            user=self.user,
            is_current=True,
        )

        self.assertEqual(academic_year.terms.count(), 3)

        terms = academic_year.terms.order_by("term_number")
        self.assertEqual(terms[0].name, "First Term")
        self.assertEqual(terms[1].name, "Second Term")
        self.assertEqual(terms[2].name, "Third Term")

        # First term should be current
        self.assertTrue(terms[0].is_current)
        self.assertFalse(terms[1].is_current)
        self.assertFalse(terms[2].is_current)

    def test_get_current_academic_year(self):
        """Test getting current academic year"""
        # Initially no current year
        self.assertIsNone(AcademicYearService.get_current_academic_year())

        # Create current year
        academic_year = AcademicYearService.create_academic_year(
            name="2024-2025",
            start_date=datetime(2024, 4, 1).date(),
            end_date=datetime(2025, 3, 31).date(),
            user=self.user,
            is_current=True,
        )

        current = AcademicYearService.get_current_academic_year()
        self.assertEqual(current, academic_year)

    def test_academic_year_summary(self):
        """Test academic year summary"""
        academic_year = AcademicYearService.setup_academic_year_with_terms(
            name="2024-2025",
            start_date=datetime(2024, 4, 1).date(),
            end_date=datetime(2025, 3, 31).date(),
            num_terms=3,
            user=self.user,
            is_current=True,
        )

        summary = AcademicYearService.get_academic_year_summary(academic_year.id)

        self.assertEqual(summary["academic_year"]["name"], "2024-2025")
        self.assertEqual(len(summary["terms"]), 3)
        self.assertEqual(summary["statistics"]["total_terms"], 3)
        self.assertIsNotNone(summary["current_term"])


class SectionServiceTestCase(TestCase):
    """Test cases for SectionService"""

    def setUp(self):
        """Set up test data"""
        self.department = Department.objects.create(name="Test Department")

    def test_create_section(self):
        """Test section creation"""
        section = SectionService.create_section(
            name="Test Section",
            description="Test description",
            department=self.department,
            order_sequence=1,
        )

        self.assertEqual(section.name, "Test Section")
        self.assertEqual(section.description, "Test description")
        self.assertEqual(section.department, self.department)
        self.assertEqual(section.order_sequence, 1)
        self.assertTrue(section.is_active)

    def test_section_name_uniqueness(self):
        """Test section name uniqueness"""
        SectionService.create_section(name="Test Section")

        with self.assertRaises(ValidationError):
            SectionService.create_section(name="Test Section")

    def test_get_sections_summary(self):
        """Test sections summary"""
        section1 = SectionService.create_section(name="Section 1", order_sequence=1)
        section2 = SectionService.create_section(name="Section 2", order_sequence=2)

        summary = SectionService.get_sections_summary()

        self.assertEqual(len(summary["sections"]), 2)
        self.assertEqual(summary["summary"]["total_sections"], 2)


class GradeServiceTestCase(TestCase):
    """Test cases for GradeService"""

    def setUp(self):
        """Set up test data"""
        self.section = Section.objects.create(name="Test Section", order_sequence=1)

    def test_create_grade(self):
        """Test grade creation"""
        grade = GradeService.create_grade(
            name="Grade 1",
            section_id=self.section.id,
            description="First grade",
            order_sequence=1,
            minimum_age=6,
            maximum_age=7,
        )

        self.assertEqual(grade.name, "Grade 1")
        self.assertEqual(grade.section, self.section)
        self.assertEqual(grade.minimum_age, 6)
        self.assertEqual(grade.maximum_age, 7)
        self.assertTrue(grade.is_active)

    def test_validate_student_age_for_grade(self):
        """Test student age validation"""
        grade = GradeService.create_grade(
            name="Grade 1", section_id=self.section.id, minimum_age=6, maximum_age=7
        )

        # Valid age
        result = GradeService.validate_student_age_for_grade(grade.id, 6)
        self.assertTrue(result["is_valid"])
        self.assertEqual(len(result["errors"]), 0)

        # Invalid age (too young)
        result = GradeService.validate_student_age_for_grade(grade.id, 5)
        self.assertFalse(result["is_valid"])
        self.assertTrue(len(result["errors"]) > 0)

        # Invalid age (too old)
        result = GradeService.validate_student_age_for_grade(grade.id, 8)
        self.assertFalse(result["is_valid"])
        self.assertTrue(len(result["errors"]) > 0)


class ClassServiceTestCase(TestCase):
    """Test cases for ClassService"""

    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )

        self.section = Section.objects.create(name="Test Section", order_sequence=1)

        self.grade = Grade.objects.create(
            name="Grade 1", section=self.section, order_sequence=1
        )

        self.academic_year = AcademicYear.objects.create(
            name="2024-2025",
            start_date=datetime(2024, 4, 1).date(),
            end_date=datetime(2025, 3, 31).date(),
            created_by=self.user,
        )

    def test_create_class(self):
        """Test class creation"""
        cls = ClassService.create_class(
            name="A",
            grade_id=self.grade.id,
            academic_year_id=self.academic_year.id,
            room_number="101",
            capacity=30,
        )

        self.assertEqual(cls.name, "A")
        self.assertEqual(cls.grade, self.grade)
        self.assertEqual(cls.section, self.section)  # Auto-set
        self.assertEqual(cls.academic_year, self.academic_year)
        self.assertEqual(cls.room_number, "101")
        self.assertEqual(cls.capacity, 30)
        self.assertTrue(cls.is_active)

    def test_bulk_create_classes(self):
        """Test bulk class creation"""
        class_configs = [
            {"name": "A", "capacity": 30, "room_number": "101"},
            {"name": "B", "capacity": 25, "room_number": "102"},
            {"name": "C", "capacity": 28, "room_number": "103"},
        ]

        classes = ClassService.bulk_create_classes(
            grade_id=self.grade.id,
            academic_year_id=self.academic_year.id,
            class_configs=class_configs,
        )

        self.assertEqual(len(classes), 3)
        self.assertEqual(classes[0].name, "A")
        self.assertEqual(classes[1].name, "B")
        self.assertEqual(classes[2].name, "C")

    def test_get_classes_by_grade(self):
        """Test getting classes by grade"""
        ClassService.create_class("A", self.grade.id, self.academic_year.id)
        ClassService.create_class("B", self.grade.id, self.academic_year.id)

        classes = ClassService.get_classes_by_grade(
            grade_id=self.grade.id, academic_year_id=self.academic_year.id
        )

        self.assertEqual(len(classes), 2)

    def test_optimize_class_distribution(self):
        """Test class distribution optimization"""
        # Create a class with some hypothetical student data
        cls = ClassService.create_class(
            "A", self.grade.id, self.academic_year.id, capacity=30
        )

        optimization = ClassService.optimize_class_distribution(
            grade_id=self.grade.id, academic_year_id=self.academic_year.id
        )

        self.assertIn("current_state", optimization)
        self.assertIn("optimization", optimization)
        self.assertIn("recommendations", optimization)


class TermServiceTestCase(TestCase):
    """Test cases for TermService"""

    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )

        self.academic_year = AcademicYear.objects.create(
            name="2024-2025",
            start_date=datetime(2024, 4, 1).date(),
            end_date=datetime(2025, 3, 31).date(),
            created_by=self.user,
        )

    def test_create_term(self):
        """Test term creation"""
        term = TermService.create_term(
            academic_year_id=self.academic_year.id,
            name="First Term",
            term_number=1,
            start_date=datetime(2024, 4, 1).date(),
            end_date=datetime(2024, 7, 31).date(),
            is_current=True,
        )

        self.assertEqual(term.name, "First Term")
        self.assertEqual(term.term_number, 1)
        self.assertEqual(term.academic_year, self.academic_year)
        self.assertTrue(term.is_current)

    def test_auto_generate_terms(self):
        """Test automatic term generation"""
        terms = TermService.auto_generate_terms(
            academic_year_id=self.academic_year.id, num_terms=3
        )

        self.assertEqual(len(terms), 3)
        self.assertEqual(terms[0].term_number, 1)
        self.assertEqual(terms[1].term_number, 2)
        self.assertEqual(terms[2].term_number, 3)

        # First term should be current
        self.assertTrue(terms[0].is_current)

    def test_get_term_calendar(self):
        """Test term calendar generation"""
        TermService.auto_generate_terms(
            academic_year_id=self.academic_year.id, num_terms=3
        )

        calendar = TermService.get_term_calendar(self.academic_year.id)

        self.assertEqual(calendar["academic_year"]["name"], "2024-2025")
        self.assertEqual(len(calendar["terms"]), 3)
        self.assertIn("summary", calendar)


class AcademicsAPITestCase(APITestCase):
    """Test cases for Academics API"""

    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )
        self.client.force_authenticate(user=self.user)

        self.department = Department.objects.create(name="Test Department")

        self.academic_year = AcademicYear.objects.create(
            name="2024-2025",
            start_date=datetime(2024, 4, 1).date(),
            end_date=datetime(2025, 3, 31).date(),
            created_by=self.user,
        )

    def test_department_list_api(self):
        """Test department list API"""
        url = reverse("academics_api:department-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["name"], "Test Department")

    def test_academic_year_list_api(self):
        """Test academic year list API"""
        url = reverse("academics_api:academicyear-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)

    def test_academic_year_create_api(self):
        """Test academic year creation API"""
        url = reverse("academics_api:academicyear-list")
        data = {
            "name": "2025-2026",
            "start_date": "2025-04-01",
            "end_date": "2026-03-31",
            "is_current": False,
            "terms_data": [{"name": "Term 1"}, {"name": "Term 2"}, {"name": "Term 3"}],
        }

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["name"], "2025-2026")

    def test_section_create_api(self):
        """Test section creation API"""
        url = reverse("academics_api:section-list")
        data = {
            "name": "Test Section",
            "description": "Test description",
            "department": self.department.id,
            "order_sequence": 1,
        }

        response = self.client.post(url, data)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["name"], "Test Section")

    def test_quick_stats_api(self):
        """Test quick stats API"""
        # Create some test data
        section = Section.objects.create(name="Test Section")
        grade = Grade.objects.create(name="Grade 1", section=section)
        Class.objects.create(name="A", grade=grade, academic_year=self.academic_year)

        url = reverse("academics_api:quick-stats")
        response = self.client.get(url)

        self.assertEqual(
            response.status_code, status.HTTP_404_NOT_FOUND
        )  # No current academic year

    def test_academic_structure_api(self):
        """Test academic structure API"""
        # Set academic year as current
        self.academic_year.is_current = True
        self.academic_year.save()

        # Create structure
        section = Section.objects.create(name="Test Section")
        grade = Grade.objects.create(name="Grade 1", section=section)
        Class.objects.create(name="A", grade=grade, academic_year=self.academic_year)

        url = reverse("academics_api:academic-structure")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("academic_year", response.data)
        self.assertIn("structure", response.data)


class AcademicsIntegrationTestCase(TransactionTestCase):
    """Integration tests for academics module"""

    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )

    def test_complete_academic_setup_workflow(self):
        """Test complete academic setup workflow"""
        # 1. Create departments
        dept1 = Department.objects.create(name="Primary Education")
        dept2 = Department.objects.create(name="Secondary Education")

        # 2. Create academic year with terms
        academic_year = AcademicYearService.setup_academic_year_with_terms(
            name="2024-2025",
            start_date=datetime(2024, 4, 1).date(),
            end_date=datetime(2025, 3, 31).date(),
            num_terms=3,
            user=self.user,
            is_current=True,
        )

        # 3. Create sections
        primary_section = SectionService.create_section(
            name="Primary", department=dept1, order_sequence=1
        )

        secondary_section = SectionService.create_section(
            name="Secondary", department=dept2, order_sequence=2
        )

        # 4. Create grades
        grade1 = GradeService.create_grade(
            name="Grade 1",
            section_id=primary_section.id,
            order_sequence=1,
            minimum_age=6,
            maximum_age=7,
        )

        grade9 = GradeService.create_grade(
            name="Grade 9",
            section_id=secondary_section.id,
            order_sequence=1,
            minimum_age=14,
            maximum_age=15,
        )

        # 5. Create classes
        class1a = ClassService.create_class(
            name="A", grade_id=grade1.id, academic_year_id=academic_year.id, capacity=25
        )

        class9a = ClassService.create_class(
            name="A", grade_id=grade9.id, academic_year_id=academic_year.id, capacity=30
        )

        # 6. Verify complete structure
        self.assertEqual(AcademicYear.objects.count(), 1)
        self.assertEqual(Term.objects.count(), 3)
        self.assertEqual(Section.objects.count(), 2)
        self.assertEqual(Grade.objects.count(), 2)
        self.assertEqual(Class.objects.count(), 2)

        # 7. Test hierarchy
        hierarchy = SectionService.get_section_hierarchy(primary_section.id)
        self.assertEqual(len(hierarchy["grades"]), 1)
        self.assertEqual(len(hierarchy["grades"][0]["classes"]), 1)

        # 8. Test analytics
        analytics = SectionService.get_section_analytics(primary_section.id)
        self.assertEqual(analytics["overall_statistics"]["total_classes"], 1)

        # 9. Test academic year summary
        summary = AcademicYearService.get_academic_year_summary(academic_year.id)
        self.assertEqual(summary["statistics"]["total_classes"], 2)

    def test_academic_year_transition(self):
        """Test academic year transition workflow"""
        # Create first academic year
        year1 = AcademicYearService.setup_academic_year_with_terms(
            name="2024-2025",
            start_date=datetime(2024, 4, 1).date(),
            end_date=datetime(2025, 3, 31).date(),
            num_terms=3,
            user=self.user,
            is_current=True,
        )

        # Create second academic year
        year2 = AcademicYearService.create_academic_year(
            name="2025-2026",
            start_date=datetime(2025, 4, 1).date(),
            end_date=datetime(2026, 3, 31).date(),
            user=self.user,
            is_current=False,
        )

        # Validate transition
        validation = AcademicYearService.validate_academic_year_transition(
            year1.id, year2.id
        )
        self.assertTrue(validation["is_valid"])

        # Perform transition
        AcademicYearService.set_current_academic_year(year2.id)

        # Verify transition
        year1.refresh_from_db()
        year2.refresh_from_db()

        self.assertFalse(year1.is_current)
        self.assertTrue(year2.is_current)
