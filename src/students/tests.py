# students/tests.py
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone

from .models import Student, Parent, StudentParentRelation
from src.courses.models import Class, Grade, Section, AcademicYear, Department

User = get_user_model()


class StudentModelTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Create user
        cls.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpassword",
            first_name="Test",
            last_name="User",
        )

        # Create student
        cls.student = Student.objects.create(
            user=cls.user,
            admission_number="TEST-001",
            admission_date=timezone.now().date(),
            emergency_contact_name="Emergency Contact",
            emergency_contact_number="1234567890",
            status="Active",
        )

    def test_string_representation(self):
        self.assertEqual(str(self.student), f"Test User (TEST-001)")

    def test_get_full_name(self):
        self.assertEqual(self.student.get_full_name(), "Test User")

    def test_is_active(self):
        self.assertTrue(self.student.is_active())

        # Change status and test again
        self.student.status = "Inactive"
        self.student.save()
        self.assertFalse(self.student.is_active())

    def test_registration_number_generation(self):
        # Registration number should be auto-generated
        self.assertIsNotNone(self.student.registration_number)
        self.assertTrue(self.student.registration_number.startswith("STU-"))


class ParentModelTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Create user
        cls.user = User.objects.create_user(
            username="parentuser",
            email="parent@example.com",
            password="testpassword",
            first_name="Parent",
            last_name="User",
        )

        # Create parent
        cls.parent = Parent.objects.create(
            user=cls.user, relation_with_student="Father", occupation="Engineer"
        )

    def test_string_representation(self):
        self.assertEqual(str(self.parent), "Parent User (Father)")

    def test_get_full_name(self):
        self.assertEqual(self.parent.get_full_name(), "Parent User")


class StudentViewsTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Create admin user
        cls.admin_user = User.objects.create_user(
            username="adminuser",
            email="admin@example.com",
            password="adminpassword",
            is_staff=True,
        )

        # Create student user
        cls.student_user = User.objects.create_user(
            username="studentuser",
            email="student@example.com",
            password="studentpassword",
            first_name="Student",
            last_name="User",
        )

        # Create test data
        cls.department = Department.objects.create(name="Test Department")
        cls.grade = Grade.objects.create(name="Test Grade", department=cls.department)
        cls.section = Section.objects.create(name="A")
        cls.academic_year = AcademicYear.objects.create(
            name="2023-2024",
            start_date="2023-09-01",
            end_date="2024-06-30",
            is_current=True,
        )
        cls.class_obj = Class.objects.create(
            grade=cls.grade, section=cls.section, academic_year=cls.academic_year
        )

        # Create student
        cls.student = Student.objects.create(
            user=cls.student_user,
            admission_number="TEST-001",
            admission_date=timezone.now().date(),
            current_class=cls.class_obj,
            emergency_contact_name="Emergency Contact",
            emergency_contact_number="1234567890",
            status="Active",
        )

    def setUp(self):
        # Login as admin user
        self.client.login(username="adminuser", password="adminpassword")

    def test_student_list_view(self):
        response = self.client.get(reverse("student-list"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "students/student_list.html")
        self.assertContains(response, "Student User")

    def test_student_detail_view(self):
        response = self.client.get(reverse("student-detail", args=[self.student.id]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "students/student_detail.html")
        self.assertContains(response, "Student User")
        self.assertContains(response, "TEST-001")

    def test_student_create_view(self):
        response = self.client.get(reverse("student-create"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "students/student_form.html")

        # Test POST request
        user_count_before = User.objects.count()
        student_count_before = Student.objects.count()

        response = self.client.post(
            reverse("student-create"),
            {
                "first_name": "New",
                "last_name": "Student",
                "email": "new.student@example.com",
                "admission_number": "TEST-002",
                "admission_date": "2023-09-01",
                "emergency_contact_name": "Contact Person",
                "emergency_contact_number": "0987654321",
                "status": "Active",
            },
        )

        # Redirects to list view on success
        self.assertRedirects(response, reverse("student-list"))

        # Check if new objects were created
        self.assertEqual(User.objects.count(), user_count_before + 1)
        self.assertEqual(Student.objects.count(), student_count_before + 1)
