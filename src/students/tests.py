# students/tests.py
import csv
import io
import tempfile
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, TransactionTestCase
from django.test.utils import override_settings
from django.urls import reverse
from django.utils import timezone

from src.courses.models import AcademicYear, Class, Department, Grade, Section

from .models import Parent, Student, StudentParentRelation
from .services.parent_service import ParentService
from .services.student_service import StudentService

User = get_user_model()


class StudentModelTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Create test user
        cls.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpassword",
            first_name="Test",
            last_name="User",
        )

        # Create test data for relationships
        cls.department = Department.objects.create(name="Test Department")
        cls.grade = Grade.objects.create(name="Test Grade", department=cls.department)
        cls.section = Section.objects.create(name="A")
        cls.academic_year = AcademicYear.objects.create(
            name="2024-2025",
            start_date="2024-04-01",
            end_date="2025-03-31",
            is_current=True,
        )
        cls.class_obj = Class.objects.create(
            grade=cls.grade, section=cls.section, academic_year=cls.academic_year
        )

        # Create test student
        cls.student = Student.objects.create(
            user=cls.user,
            admission_number="TEST-001",
            admission_date=timezone.now().date(),
            current_class=cls.class_obj,
            emergency_contact_name="Emergency Contact",
            emergency_contact_number="1234567890",
            status="Active",
        )

    def test_student_str_representation(self):
        self.assertEqual(str(self.student), "Test User (TEST-001)")

    def test_student_full_name_property(self):
        self.assertEqual(self.student.full_name, "Test User")

    def test_student_get_full_name_method(self):
        self.assertEqual(self.student.get_full_name(), "Test User")

    def test_student_is_active(self):
        self.assertTrue(self.student.is_active())

        # Test inactive status
        self.student.status = "Inactive"
        self.assertFalse(self.student.is_active())

    def test_registration_number_auto_generation(self):
        # Registration number should be auto-generated on save
        self.assertIsNotNone(self.student.registration_number)
        self.assertTrue(self.student.registration_number.startswith("STU-"))

    def test_student_age_calculation(self):
        # Set date of birth
        self.date_of_birth = timezone.now().date().replace(year=2005)
        # self.user.save() - No user for students

        # Age should be calculated correctly
        expected_age = timezone.now().year - 2005
        self.assertEqual(self.student.age, expected_age)

    def test_get_full_address(self):
        self.student.address = "123 Test Street"
        self.student.city = "Test City"
        self.student.state = "Test State"
        self.student.country = "Test Country"
        self.student.save()

        expected_address = "123 Test Street, Test City, Test State, Test Country"
        self.assertEqual(self.student.get_full_address(), expected_address)

    def test_student_promotion(self):
        # Create a new class for promotion
        new_grade = Grade.objects.create(
            name="Higher Grade", department=self.department
        )
        new_class = Class.objects.create(
            grade=new_grade, section=self.section, academic_year=self.academic_year
        )

        # Promote student
        old_class = self.student.current_class
        self.student.promote_to_next_class(new_class)

        # Check if promotion was successful
        self.student.refresh_from_db()
        self.assertEqual(self.student.current_class, new_class)

    def test_student_graduation(self):
        # Mark student as graduated
        old_status = self.student.status
        self.student.mark_as_graduated()

        # Check if graduation was successful
        self.student.refresh_from_db()
        self.assertEqual(self.student.status, "Graduated")

    def test_student_withdrawal(self):
        # Mark student as withdrawn
        reason = "Family relocation"
        self.student.mark_as_withdrawn(reason)

        # Check if withdrawal was successful
        self.student.refresh_from_db()
        self.assertEqual(self.student.status, "Withdrawn")


class ParentModelTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Create test user for parent
        cls.parent_user = User.objects.create_user(
            username="parentuser",
            email="parent@example.com",
            password="parentpassword",
            first_name="Parent",
            last_name="User",
        )

        # Create test parent
        cls.parent = Parent.objects.create(
            user=cls.parent_user,
            relation_with_student="Father",
            occupation="Engineer",
            annual_income=50000.00,
        )

    def test_parent_str_representation(self):
        self.assertEqual(str(self.parent), "Parent User (Father)")

    def test_parent_full_name_property(self):
        self.assertEqual(self.parent.full_name, "Parent User")

    def test_parent_get_full_name_method(self):
        self.assertEqual(self.parent.get_full_name(), "Parent User")


class StudentParentRelationTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Create test users
        cls.student_user = User.objects.create_user(
            username="student@example.com",
            email="student@example.com",
            first_name="Student",
            last_name="User",
        )
        cls.parent_user = User.objects.create_user(
            username="parent@example.com",
            email="parent@example.com",
            first_name="Parent",
            last_name="User",
        )

        # Create test data
        cls.department = Department.objects.create(name="Test Department")
        cls.grade = Grade.objects.create(name="Test Grade", department=cls.department)
        cls.section = Section.objects.create(name="A")
        cls.academic_year = AcademicYear.objects.create(
            name="2024-2025",
            start_date="2024-04-01",
            end_date="2025-03-31",
            is_current=True,
        )
        cls.class_obj = Class.objects.create(
            grade=cls.grade, section=cls.section, academic_year=cls.academic_year
        )

        # Create student and parent
        cls.student = Student.objects.create(
            user=cls.student_user,
            admission_number="TEST-002",
            admission_date=timezone.now().date(),
            current_class=cls.class_obj,
            emergency_contact_name="Emergency Contact",
            emergency_contact_number="1234567890",
        )
        cls.parent = Parent.objects.create(
            user=cls.parent_user,
            relation_with_student="Mother",
        )

    def test_relation_creation(self):
        relation = StudentParentRelation.objects.create(
            student=self.student,
            parent=self.parent,
            is_primary_contact=True,
        )

        self.assertEqual(relation.student, self.student)
        self.assertEqual(relation.parent, self.parent)
        self.assertTrue(relation.is_primary_contact)

    def test_primary_contact_constraint(self):
        # Create first relation as primary
        relation1 = StudentParentRelation.objects.create(
            student=self.student,
            parent=self.parent,
            is_primary_contact=True,
        )

        # Create second parent
        parent2_user = User.objects.create_user(
            username="parent2@example.com",
            email="parent2@example.com",
            first_name="Second",
            last_name="Parent",
        )
        parent2 = Parent.objects.create(
            user=parent2_user,
            relation_with_student="Father",
        )

        # Create second relation as primary - should make first one non-primary
        relation2 = StudentParentRelation.objects.create(
            student=self.student,
            parent=parent2,
            is_primary_contact=True,
        )

        # Refresh from database
        relation1.refresh_from_db()

        # First relation should no longer be primary
        self.assertFalse(relation1.is_primary_contact)
        self.assertTrue(relation2.is_primary_contact)

    def test_get_parents(self):
        # Create relation
        StudentParentRelation.objects.create(
            student=self.student,
            parent=self.parent,
        )

        # Test get_parents method
        parents = self.student.get_parents()
        self.assertIn(self.parent, parents)

    def test_get_primary_parent(self):
        # Create relation as primary
        StudentParentRelation.objects.create(
            student=self.student,
            parent=self.parent,
            is_primary_contact=True,
        )

        # Test get_primary_parent method
        primary_parent = self.student.get_primary_parent()
        self.assertEqual(primary_parent, self.parent)

    def test_get_siblings(self):
        # Create second student with same parent
        student2_user = User.objects.create_user(
            username="student2@example.com",
            email="student2@example.com",
            first_name="Second",
            last_name="Student",
        )
        student2 = Student.objects.create(
            user=student2_user,
            admission_number="TEST-003",
            admission_date=timezone.now().date(),
            emergency_contact_name="Emergency Contact",
            emergency_contact_number="1234567890",
        )

        # Create relations
        StudentParentRelation.objects.create(student=self.student, parent=self.parent)
        StudentParentRelation.objects.create(student=student2, parent=self.parent)

        # Test get_siblings
        siblings = self.student.get_siblings()
        self.assertIn(student2, siblings)


class StudentServiceTest(TestCase):
    def setUp(self):
        self.department = Department.objects.create(name="Test Department")
        self.grade = Grade.objects.create(name="Test Grade", department=self.department)
        self.section = Section.objects.create(name="A")
        self.academic_year = AcademicYear.objects.create(
            name="2024-2025",
            start_date="2024-04-01",
            end_date="2025-03-31",
            is_current=True,
        )
        self.class_obj = Class.objects.create(
            grade=self.grade, section=self.section, academic_year=self.academic_year
        )

    def test_create_student_service(self):
        user_data = {
            "username": "newstudent@example.com",
            "email": "newstudent@example.com",
            "first_name": "New",
            "last_name": "Student",
        }

        student_data = {
            "admission_number": "NEW-001",
            "admission_date": timezone.now().date(),
            "current_class": self.class_obj,
            "emergency_contact_name": "Emergency Contact",
            "emergency_contact_number": "+1234567890",
        }

        student = StudentService.create_student(student_data, user_data)

        self.assertIsInstance(student, Student)
        self.assertEqual(student.admission_number, "NEW-001")
        self.assertEqual(student.first_name, "New")
        self.assertEqual(student.last_name, "Student")

    @patch("students.services.student_service.send_mail")
    def test_bulk_import_students(self, mock_send_mail):
        # Create CSV content
        csv_content = """first_name,last_name,email,admission_number,emergency_contact_name,emergency_contact_number
John,Doe,john@example.com,IMP-001,Jane Doe,+1234567890
Alice,Smith,alice@example.com,IMP-002,Bob Smith,+1234567891"""

        # Create file-like object
        csv_file = io.StringIO(csv_content)
        csv_file.name = "test_students.csv"

        # Convert to uploaded file
        uploaded_file = SimpleUploadedFile(
            "test_students.csv", csv_content.encode("utf-8"), content_type="text/csv"
        )

        # Test import
        result = StudentService.bulk_import_students(uploaded_file)

        self.assertTrue(result["success"])
        self.assertEqual(result["created"], 2)
        self.assertEqual(result["errors"], 0)

        # Verify students were created
        self.assertTrue(Student.objects.filter(admission_number="IMP-001").exists())
        self.assertTrue(Student.objects.filter(admission_number="IMP-002").exists())

    def test_export_students_to_csv(self):
        # Create test student
        user = User.objects.create_user(
            username="export@example.com",
            email="export@example.com",
            first_name="Export",
            last_name="Student",
        )
        Student.objects.create(
            user=user,
            admission_number="EXP-001",
            admission_date=timezone.now().date(),
            emergency_contact_name="Emergency Contact",
            emergency_contact_number="+1234567890",
        )

        # Test export
        queryset = Student.objects.all()
        csv_content = StudentService.export_students_to_csv(queryset)

        # Parse CSV to verify content
        csv_reader = csv.DictReader(io.StringIO(csv_content))
        rows = list(csv_reader)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["admission_number"], "EXP-001")
        self.assertEqual(rows[0]["first_name"], "Export")
        self.assertEqual(rows[0]["last_name"], "Student")


class StudentViewsTest(TransactionTestCase):
    def setUp(self):
        # Create admin user
        self.admin_user = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="adminpass",
            is_staff=True,
            is_superuser=True,
        )

        # Create test data
        self.department = Department.objects.create(name="Test Department")
        self.grade = Grade.objects.create(name="Test Grade", department=self.department)
        self.section = Section.objects.create(name="A")
        self.academic_year = AcademicYear.objects.create(
            name="2024-2025",
            start_date="2024-04-01",
            end_date="2025-03-31",
            is_current=True,
        )
        self.class_obj = Class.objects.create(
            grade=self.grade, section=self.section, academic_year=self.academic_year
        )

        # Create test student
        self.student_user = User.objects.create_user(
            username="student@example.com",
            email="student@example.com",
            first_name="Test",
            last_name="Student",
        )
        self.student = Student.objects.create(
            user=self.student_user,
            admission_number="VIEW-001",
            admission_date=timezone.now().date(),
            current_class=self.class_obj,
            emergency_contact_name="Emergency Contact",
            emergency_contact_number="+1234567890",
        )

        # Login as admin
        self.client.login(username="admin", password="adminpass")

    def test_student_list_view(self):
        response = self.client.get(reverse("students:student-list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test Student")
        self.assertContains(response, "VIEW-001")

    def test_student_detail_view(self):
        response = self.client.get(
            reverse("students:student-detail", args=[self.student.id])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test Student")
        self.assertContains(response, "VIEW-001")

    def test_student_create_view_get(self):
        response = self.client.get(reverse("students:student-create"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Add New Student")

    def test_student_create_view_post(self):
        user_count_before = User.objects.count()
        student_count_before = Student.objects.count()

        response = self.client.post(
            reverse("students:student-create"),
            {
                "first_name": "New",
                "last_name": "Student",
                "email": "new@example.com",
                "admission_number": "NEW-001",
                "admission_date": "2024-01-01",
                "emergency_contact_name": "Contact Person",
                "emergency_contact_number": "+1234567890",
                "status": "Active",
            },
        )

        # Should redirect on success
        self.assertEqual(response.status_code, 302)

        # Check if objects were created
        self.assertEqual(User.objects.count(), user_count_before + 1)
        self.assertEqual(Student.objects.count(), student_count_before + 1)

        # Verify the student was created correctly
        new_student = Student.objects.get(admission_number="NEW-001")
        self.assertEqual(new_student.first_name, "New")
        self.assertEqual(new_student.last_name, "Student")

    def test_student_update_view(self):
        response = self.client.get(
            reverse("students:student-update", args=[self.student.id])
        )
        self.assertEqual(response.status_code, 200)

        # Test updating
        response = self.client.post(
            reverse("students:student-update", args=[self.student.id]),
            {
                "first_name": "Updated",
                "last_name": "Student",
                "email": self.student.email,
                "admission_number": self.student.admission_number,
                "admission_date": self.student.admission_date,
                "emergency_contact_name": "Updated Contact",
                "emergency_contact_number": "+1234567890",
                "status": "Active",
            },
        )

        # Should redirect on success
        self.assertEqual(response.status_code, 302)

        # Verify the update
        self.student.refresh_from_db()
        self.assertEqual(self.student.first_name, "Updated")
        self.assertEqual(self.student.emergency_contact_name, "Updated Contact")

    def test_student_delete_view(self):
        response = self.client.get(
            reverse("students:student-delete", args=[self.student.id])
        )
        self.assertEqual(response.status_code, 200)

        # Test deletion
        response = self.client.post(
            reverse("students:student-delete", args=[self.student.id])
        )

        # Should redirect on success
        self.assertEqual(response.status_code, 302)

        # Verify the student was deleted
        self.assertFalse(Student.objects.filter(id=self.student.id).exists())

    def test_student_search(self):
        # Test search functionality
        response = self.client.get(reverse("students:student-list") + "?search=Test")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test Student")

        # Test search with admission number
        response = self.client.get(
            reverse("students:student-list") + "?search=VIEW-001"
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test Student")

    def test_student_filter_by_status(self):
        response = self.client.get(reverse("students:student-list") + "?status=Active")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test Student")

        # Test with non-matching status
        response = self.client.get(
            reverse("students:student-list") + "?status=Graduated"
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Test Student")


class CacheTest(TestCase):
    def setUp(self):
        cache.clear()

        # Create test data
        self.user = User.objects.create_user(
            username="cachetest@example.com",
            email="cachetest@example.com",
            first_name="Cache",
            last_name="Test",
        )
        self.student = Student.objects.create(
            user=self.user,
            admission_number="CACHE-001",
            admission_date=timezone.now().date(),
            emergency_contact_name="Emergency Contact",
            emergency_contact_number="+1234567890",
        )

    def test_cache_invalidation_on_student_save(self):
        # Set cache
        cache_key = f"student_attendance_percentage_{self.student.id}"
        cache.set(cache_key, 95.5)

        # Verify cache is set
        self.assertEqual(cache.get(cache_key), 95.5)

        # Update student (should clear cache)
        self.student.status = "Inactive"
        self.student.save()

        # Cache should be cleared
        self.assertIsNone(cache.get(cache_key))

    def test_cache_clearing_on_relation_creation(self):
        # Create parent
        parent_user = User.objects.create_user(
            username="cacheparent@example.com",
            email="cacheparent@example.com",
        )
        parent = Parent.objects.create(
            user=parent_user,
            relation_with_student="Father",
        )

        # Set cache
        cache_key = f"student_parents_{self.student.id}"
        cache.set(cache_key, [])

        # Create relation (should clear cache)
        StudentParentRelation.objects.create(
            student=self.student,
            parent=parent,
        )

        # Cache should be cleared
        self.assertIsNone(cache.get(cache_key))


@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
class IntegrationTest(TransactionTestCase):
    """Integration tests for complete workflows"""

    def setUp(self):
        # Create admin user
        self.admin_user = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="adminpass",
            is_staff=True,
            is_superuser=True,
        )

        # Create test data
        self.department = Department.objects.create(name="Science")
        self.grade = Grade.objects.create(name="Grade 10", department=self.department)
        self.section = Section.objects.create(name="A")
        self.academic_year = AcademicYear.objects.create(
            name="2024-2025",
            start_date="2024-04-01",
            end_date="2025-03-31",
            is_current=True,
        )
        self.class_obj = Class.objects.create(
            grade=self.grade, section=self.section, academic_year=self.academic_year
        )

        self.client.login(username="admin", password="adminpass")

    def test_complete_student_lifecycle(self):
        """Test complete student lifecycle from creation to graduation"""

        # 1. Create student
        response = self.client.post(
            reverse("students:student-create"),
            {
                "first_name": "John",
                "last_name": "Doe",
                "email": "john.doe@example.com",
                "admission_number": "LIFE-001",
                "admission_date": "2024-04-01",
                "current_class": self.class_obj.id,
                "emergency_contact_name": "Jane Doe",
                "emergency_contact_number": "+1234567890",
                "status": "Active",
                "blood_group": "O+",
            },
        )
        self.assertEqual(response.status_code, 302)

        student = Student.objects.get(admission_number="LIFE-001")
        self.assertEqual(student.status, "Active")

        # 2. Create parent
        response = self.client.post(
            reverse("students:parent-create"),
            {
                "first_name": "Jane",
                "last_name": "Doe",
                "email": "jane.doe@example.com",
                "phone_number": "+1234567890",
                "relation_with_student": "Mother",
                "occupation": "Teacher",
            },
        )
        self.assertEqual(response.status_code, 302)

        parent = Parent.objects.get(user__email="jane.doe@example.com")

        # 3. Link parent to student
        response = self.client.post(
            reverse("students:relation-create"),
            {
                "student": student.id,
                "parent": parent.id,
                "is_primary_contact": True,
                "can_pickup": True,
                "emergency_contact_priority": 1,
                "financial_responsibility": True,
                "access_to_grades": True,
                "access_to_attendance": True,
            },
        )
        self.assertEqual(response.status_code, 302)

        # Verify relationship
        relation = StudentParentRelation.objects.get(student=student, parent=parent)
        self.assertTrue(relation.is_primary_contact)

        # 4. Update student status to graduated
        student.mark_as_graduated()
        student.refresh_from_db()
        self.assertEqual(student.status, "Graduated")

        # 5. Verify parent can see graduated student
        primary_parent = student.get_primary_parent()
        self.assertEqual(primary_parent, parent)

        students_of_parent = parent.get_students()
        self.assertIn(student, students_of_parent)

    def test_bulk_import_and_relationship_creation(self):
        """Test bulk import of students and automatic relationship creation"""

        # Create CSV with student data
        csv_content = """first_name,last_name,email,admission_number,emergency_contact_name,emergency_contact_number,current_class_id
Alice,Smith,alice@example.com,BULK-001,Bob Smith,+1111111111,{class_id}
Charlie,Brown,charlie@example.com,BULK-002,Diana Brown,+2222222222,{class_id}""".format(
            class_id=self.class_obj.id
        )

        uploaded_file = SimpleUploadedFile(
            "bulk_students.csv", csv_content.encode("utf-8"), content_type="text/csv"
        )

        # Test bulk import
        response = self.client.post(
            reverse("students:student-import"),
            {
                "csv_file": uploaded_file,
                "send_email_notifications": False,
                "update_existing": False,
            },
        )
        self.assertEqual(response.status_code, 302)

        # Verify students were created
        alice = Student.objects.get(admission_number="BULK-001")
        charlie = Student.objects.get(admission_number="BULK-002")

        self.assertEqual(alice.user.first_name, "Alice")
        self.assertEqual(charlie.user.first_name, "Charlie")
        self.assertEqual(alice.current_class, self.class_obj)
        self.assertEqual(charlie.current_class, self.class_obj)

        # Test export
        response = self.client.get(reverse("students:student-export"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv")

    @patch("students.services.student_service.send_mail")
    def test_promotion_workflow(self, mock_send_mail):
        """Test student promotion workflow"""

        # Create students in current class
        students = []
        for i in range(3):
            user = User.objects.create_user(
                username=f"student{i}@example.com",
                email=f"student{i}@example.com",
                first_name=f"Student{i}",
                last_name="Test",
            )
            student = Student.objects.create(
                user=user,
                admission_number=f"PROMO-00{i+1}",
                admission_date=timezone.now().date(),
                current_class=self.class_obj,
                emergency_contact_name="Emergency Contact",
                emergency_contact_number="+1234567890",
                status="Active",
            )
            students.append(student)

        # Create next year and class
        next_year = AcademicYear.objects.create(
            name="2025-2026",
            start_date="2025-04-01",
            end_date="2026-03-31",
            is_current=False,
        )
        next_grade = Grade.objects.create(name="Grade 11", department=self.department)
        next_class = Class.objects.create(
            grade=next_grade, section=self.section, academic_year=next_year
        )

        # Test promotion
        response = self.client.post(
            reverse("students:student-promotion"),
            {
                "source_class": self.class_obj.id,
                "target_class": next_class.id,
                "students": [str(s.id) for s in students],
                "send_notifications": False,
            },
        )
        self.assertEqual(response.status_code, 302)

        # Verify promotions
        for student in students:
            student.refresh_from_db()
            self.assertEqual(student.current_class, next_class)

    def tearDown(self):
        # Clear cache after each test
        cache.clear()
