# src/teachers/tests/test_integration.py
"""
Integration tests for the teachers module.
Tests the interaction between different components of the teacher system.
"""

import json
from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from src.communications.models import Notification
from src.courses.models import (
    AcademicYear,
    Class,
    Department,
    Grade,
    Section,
    Subject,
    Term,
)
from src.teachers.models import Teacher, TeacherClassAssignment, TeacherEvaluation
from src.teachers.services import EvaluationService, TeacherService
from src.teachers.services.analytics_service import TeacherAnalyticsService
from src.teachers.tasks import (
    calculate_daily_teacher_analytics,
    process_bulk_teacher_assignments,
    send_evaluation_reminders,
)

User = get_user_model()


class TeacherWorkflowIntegrationTest(TestCase):
    """Test complete teacher management workflows."""

    def setUp(self):
        """Set up test data."""
        # Create departments
        self.department = Department.objects.create(
            name="Mathematics", description="Math Department"
        )

        # Create academic year and term
        self.academic_year = AcademicYear.objects.create(
            name="2024-2025",
            start_date=date(2024, 9, 1),
            end_date=date(2025, 6, 30),
            is_current=True,
        )

        self.term = Term.objects.create(
            academic_year=self.academic_year,
            name="First Term",
            term_number=1,
            start_date=date(2024, 9, 1),
            end_date=date(2024, 12, 20),
            is_current=True,
        )

        # Create subject
        self.subject = Subject.objects.create(
            name="Mathematics", code="MATH001", department=self.department
        )

        # Create grade and section
        self.section = Section.objects.create(
            name="Primary", description="Primary Section"
        )

        self.grade = Grade.objects.create(
            name="Grade 5", section=self.section, order_sequence=5
        )

        # Create class
        self.class_instance = Class.objects.create(
            name="A",
            grade=self.grade,
            academic_year=self.academic_year,
            room_number="101",
            capacity=30,
        )

        # Create users
        self.admin_user = User.objects.create_user(
            username="admin@school.edu",
            email="admin@school.edu",
            password="testpass123",
            first_name="Admin",
            last_name="User",
            is_staff=True,
            is_superuser=True,
        )

        self.teacher_user = User.objects.create_user(
            username="teacher@school.edu",
            email="teacher@school.edu",
            password="testpass123",
            first_name="John",
            last_name="Doe",
        )

        self.evaluator_user = User.objects.create_user(
            username="evaluator@school.edu",
            email="evaluator@school.edu",
            password="testpass123",
            first_name="Jane",
            last_name="Smith",
        )

        # Create groups and permissions
        self.admin_group = Group.objects.create(name="Admin")
        self.teacher_group = Group.objects.create(name="Teacher")
        self.principal_group = Group.objects.create(name="Principal")

        # Add users to groups
        self.admin_user.groups.add(self.admin_group)
        self.teacher_user.groups.add(self.teacher_group)
        self.evaluator_user.groups.add(self.principal_group)

    def test_complete_teacher_onboarding_workflow(self):
        """Test the complete teacher onboarding process."""
        # Step 1: Create teacher profile
        teacher = Teacher.objects.create(
            user=self.teacher_user,
            employee_id="T123456",
            joining_date=date.today(),
            qualification="Master of Education",
            experience_years=Decimal("5.5"),
            specialization="Mathematics",
            department=self.department,
            position="Senior Teacher",
            salary=Decimal("45000.00"),
            contract_type="Permanent",
            status="Active",
        )

        # Verify teacher was created with correct relationships
        self.assertEqual(teacher.user.email, "teacher@school.edu")
        self.assertEqual(teacher.department, self.department)
        self.assertTrue(teacher.is_active())

        # Step 2: Assign teacher to class and subject
        assignment = TeacherClassAssignment.objects.create(
            teacher=teacher,
            class_instance=self.class_instance,
            subject=self.subject,
            academic_year=self.academic_year,
            is_class_teacher=True,
        )

        # Verify assignment
        self.assertTrue(assignment.is_class_teacher)
        self.assertEqual(teacher.get_assigned_classes()[0], self.class_instance)

        # Step 3: Create initial evaluation
        evaluation_criteria = TeacherEvaluation.get_default_criteria()
        for criterion in evaluation_criteria:
            evaluation_criteria[criterion]["score"] = 8

        evaluation = TeacherEvaluation.objects.create(
            teacher=teacher,
            evaluator=self.evaluator_user,
            evaluation_date=date.today(),
            criteria=evaluation_criteria,
            score=Decimal("80.0"),
            remarks="Good performance in first evaluation",
            status="submitted",
        )

        # Verify evaluation
        self.assertEqual(evaluation.get_performance_level(), "Good")
        self.assertEqual(teacher.get_average_evaluation_score(), 80.0)

        # Step 4: Verify notifications were created
        notifications = Notification.objects.filter(user=teacher.user)
        self.assertTrue(notifications.exists())

    def test_teacher_performance_tracking_workflow(self):
        """Test teacher performance tracking over time."""
        # Create teacher
        teacher = Teacher.objects.create(
            user=self.teacher_user,
            employee_id="T123456",
            joining_date=date.today() - timedelta(days=365),
            qualification="Bachelor of Education",
            experience_years=Decimal("3.0"),
            specialization="Mathematics",
            department=self.department,
            position="Teacher",
            salary=Decimal("35000.00"),
            contract_type="Permanent",
            status="Active",
        )

        # Create multiple evaluations over time
        evaluation_dates = [
            date.today() - timedelta(days=300),
            date.today() - timedelta(days=180),
            date.today() - timedelta(days=60),
        ]

        scores = [65, 75, 85]  # Improving performance

        for i, (eval_date, score) in enumerate(zip(evaluation_dates, scores)):
            evaluation_criteria = TeacherEvaluation.get_default_criteria()
            for criterion in evaluation_criteria:
                evaluation_criteria[criterion]["score"] = score / 10

            TeacherEvaluation.objects.create(
                teacher=teacher,
                evaluator=self.evaluator_user,
                evaluation_date=eval_date,
                criteria=evaluation_criteria,
                score=Decimal(str(score)),
                remarks=f"Evaluation {i+1}",
                status="reviewed",
            )

        # Test performance analysis
        performance_data = TeacherService.calculate_teacher_performance(teacher)

        self.assertIsNotNone(performance_data)
        self.assertEqual(performance_data["evaluation_count"], 3)
        self.assertEqual(performance_data["average_score"], 75.0)

        # Test analytics service
        growth_analysis = TeacherAnalyticsService.get_teacher_growth_analysis(
            teacher.id, months=12
        )

        self.assertIsNotNone(growth_analysis)
        self.assertEqual(
            growth_analysis["growth_metrics"]["improvement_trend"], "Improving"
        )

    def test_bulk_assignment_workflow(self):
        """Test bulk teacher assignment process."""
        # Create multiple teachers
        teachers = []
        for i in range(3):
            user = User.objects.create_user(
                username=f"teacher{i}@school.edu",
                email=f"teacher{i}@school.edu",
                password="testpass123",
                first_name=f"Teacher",
                last_name=f"{i}",
            )

            teacher = Teacher.objects.create(
                user=user,
                employee_id=f"T12345{i}",
                joining_date=date.today(),
                qualification="Bachelor of Education",
                experience_years=Decimal("2.0"),
                specialization="Mathematics",
                department=self.department,
                position="Teacher",
                salary=Decimal("30000.00"),
                contract_type="Permanent",
                status="Active",
            )
            teachers.append(teacher)

        # Create multiple classes
        classes = []
        for i in range(3):
            class_obj = Class.objects.create(
                name=chr(ord("A") + i),
                grade=self.grade,
                academic_year=self.academic_year,
                room_number=f"10{i}",
                capacity=25,
            )
            classes.append(class_obj)

        # Prepare bulk assignment data
        assignments_data = []
        for i, (teacher, class_obj) in enumerate(zip(teachers, classes)):
            assignments_data.append(
                {
                    "teacher_id": teacher.id,
                    "class_instance_id": class_obj.id,
                    "subject_id": self.subject.id,
                    "academic_year_id": self.academic_year.id,
                    "is_class_teacher": i == 0,  # First teacher is class teacher
                    "notes": f"Assignment {i+1}",
                }
            )

        # Process bulk assignments
        result = process_bulk_teacher_assignments.apply(
            args=[assignments_data, self.admin_user.id]
        ).result

        # Verify results
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["created_count"], 3)
        self.assertEqual(result["error_count"], 0)

        # Verify assignments were created
        self.assertEqual(TeacherClassAssignment.objects.count(), 3)

        # Verify class teacher assignment
        class_teacher_assignment = TeacherClassAssignment.objects.get(
            is_class_teacher=True
        )
        self.assertEqual(class_teacher_assignment.teacher, teachers[0])

    def test_evaluation_reminder_workflow(self):
        """Test evaluation reminder system."""
        # Create teacher who needs evaluation
        teacher = Teacher.objects.create(
            user=self.teacher_user,
            employee_id="T123456",
            joining_date=date.today() - timedelta(days=200),
            qualification="Bachelor of Education",
            experience_years=Decimal("2.0"),
            specialization="Mathematics",
            department=self.department,
            position="Teacher",
            salary=Decimal("30000.00"),
            contract_type="Permanent",
            status="Active",
        )

        # Set department head
        dept_head_user = User.objects.create_user(
            username="head@school.edu",
            email="head@school.edu",
            password="testpass123",
            first_name="Department",
            last_name="Head",
        )

        dept_head = Teacher.objects.create(
            user=dept_head_user,
            employee_id="T999999",
            joining_date=date.today() - timedelta(days=1000),
            qualification="PhD in Education",
            experience_years=Decimal("15.0"),
            specialization="Mathematics",
            department=self.department,
            position="Department Head",
            salary=Decimal("60000.00"),
            contract_type="Permanent",
            status="Active",
        )

        self.department.head = dept_head
        self.department.save()

        # Run evaluation reminder task
        result = send_evaluation_reminders.apply().result

        # Verify notifications were created
        notifications = Notification.objects.filter(
            user=dept_head.user, title__icontains="evaluation"
        )
        self.assertTrue(notifications.exists())

        # Verify result
        self.assertEqual(result["status"], "success")
        self.assertGreater(result["notifications_sent"], 0)

    def test_analytics_calculation_workflow(self):
        """Test analytics calculation workflow."""
        # Create teachers with various performance levels
        teachers_data = [
            ("Excellent", 95, "T100001"),
            ("Good", 82, "T100002"),
            ("Average", 75, "T100003"),
            ("Poor", 55, "T100004"),
        ]

        for name, score, emp_id in teachers_data:
            user = User.objects.create_user(
                username=f"{name.lower()}@school.edu",
                email=f"{name.lower()}@school.edu",
                password="testpass123",
                first_name=name,
                last_name="Teacher",
            )

            teacher = Teacher.objects.create(
                user=user,
                employee_id=emp_id,
                joining_date=date.today() - timedelta(days=100),
                qualification="Bachelor of Education",
                experience_years=Decimal("3.0"),
                specialization="Mathematics",
                department=self.department,
                position="Teacher",
                salary=Decimal("35000.00"),
                contract_type="Permanent",
                status="Active",
            )

            # Create evaluation
            evaluation_criteria = TeacherEvaluation.get_default_criteria()
            for criterion in evaluation_criteria:
                evaluation_criteria[criterion]["score"] = score / 10

            TeacherEvaluation.objects.create(
                teacher=teacher,
                evaluator=self.evaluator_user,
                evaluation_date=date.today() - timedelta(days=30),
                criteria=evaluation_criteria,
                score=Decimal(str(score)),
                remarks=f"{name} performance",
                status="reviewed",
            )

        # Run analytics calculation
        result = calculate_daily_teacher_analytics.apply(
            args=[self.academic_year.id]
        ).result

        # Verify analytics were calculated
        self.assertEqual(result["status"], "success")
        self.assertIn("metrics", result)

        # Test analytics service results
        overview = TeacherAnalyticsService.get_performance_overview(
            academic_year=self.academic_year, department_id=self.department.id
        )

        self.assertEqual(overview["base_stats"]["total_teachers"], 4)
        self.assertGreater(overview["base_stats"]["avg_evaluation_score"], 0)

        # Test performance distribution
        distribution = overview["performance_distribution"]
        excellent_count = next(
            (item["count"] for item in distribution if "Excellent" in item["range"]), 0
        )
        self.assertEqual(excellent_count, 1)


class TeacherAPIIntegrationTest(APITestCase):
    """Test teacher API integration with permissions and workflows."""

    def setUp(self):
        """Set up test data for API tests."""
        self.client = APIClient()

        # Create department
        self.department = Department.objects.create(
            name="Science", description="Science Department"
        )

        # Create users with different roles
        self.admin_user = User.objects.create_user(
            username="admin@school.edu",
            email="admin@school.edu",
            password="testpass123",
            is_staff=True,
            is_superuser=True,
        )

        self.teacher_user = User.objects.create_user(
            username="teacher@school.edu",
            email="teacher@school.edu",
            password="testpass123",
            first_name="Jane",
            last_name="Smith",
        )

        # Create teacher profile
        self.teacher = Teacher.objects.create(
            user=self.teacher_user,
            employee_id="T123456",
            joining_date=date.today(),
            qualification="Master of Science",
            experience_years=Decimal("5.0"),
            specialization="Physics",
            department=self.department,
            position="Senior Teacher",
            salary=Decimal("45000.00"),
            contract_type="Permanent",
            status="Active",
        )

        # Create groups
        self.admin_group = Group.objects.create(name="Admin")
        self.teacher_group = Group.objects.create(name="Teacher")

        self.admin_user.groups.add(self.admin_group)
        self.teacher_user.groups.add(self.teacher_group)

    def test_teacher_crud_api_workflow(self):
        """Test complete CRUD operations via API."""
        # Test authentication required
        response = self.client.get("/api/teachers/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

        # Login as admin
        self.client.force_authenticate(user=self.admin_user)

        # Test list teachers
        response = self.client.get("/api/teachers/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)

        # Test create teacher
        new_teacher_data = {
            "employee_id": "T789012",
            "first_name": "John",
            "last_name": "Doe",
            "email": "john.doe@school.edu",
            "phone_number": "+1234567890",
            "joining_date": date.today().isoformat(),
            "qualification": "Bachelor of Science",
            "experience_years": "3.0",
            "specialization": "Chemistry",
            "department": self.department.id,
            "position": "Teacher",
            "salary": "35000.00",
            "contract_type": "Permanent",
            "status": "Active",
        }

        response = self.client.post("/api/teachers/", new_teacher_data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Verify teacher was created
        created_teacher = Teacher.objects.get(employee_id="T789012")
        self.assertEqual(created_teacher.user.email, "john.doe@school.edu")

        # Test retrieve teacher
        response = self.client.get(f"/api/teachers/{created_teacher.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["employee_id"], "T789012")

        # Test update teacher
        update_data = {"position": "Senior Teacher", "salary": "40000.00"}
        response = self.client.patch(
            f"/api/teachers/{created_teacher.id}/", update_data
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify update
        created_teacher.refresh_from_db()
        self.assertEqual(created_teacher.position, "Senior Teacher")
        self.assertEqual(created_teacher.salary, Decimal("40000.00"))

        # Test delete teacher
        response = self.client.delete(f"/api/teachers/{created_teacher.id}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # Verify deletion
        self.assertFalse(Teacher.objects.filter(id=created_teacher.id).exists())

    def test_teacher_evaluation_api_workflow(self):
        """Test evaluation creation and management via API."""
        self.client.force_authenticate(user=self.admin_user)

        # Test create evaluation
        evaluation_data = {
            "teacher": self.teacher.id,
            "evaluation_date": date.today().isoformat(),
            "criteria": TeacherEvaluation.get_default_criteria(),
            "remarks": "Good performance overall",
            "status": "submitted",
        }

        # Set scores in criteria
        for criterion in evaluation_data["criteria"]:
            evaluation_data["criteria"][criterion]["score"] = 8

        response = self.client.post("/api/teachers/evaluations/", evaluation_data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Verify evaluation was created
        evaluation = TeacherEvaluation.objects.get(teacher=self.teacher)
        self.assertEqual(evaluation.score, 80.0)

        # Test list evaluations
        response = self.client.get("/api/teachers/evaluations/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)

        # Test teacher-specific evaluations
        response = self.client.get(f"/api/teachers/{self.teacher.id}/evaluations/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)

        # Test evaluation detail
        response = self.client.get(f"/api/teachers/evaluations/{evaluation.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("criteria_summary", response.data)

    def test_teacher_analytics_api_workflow(self):
        """Test analytics API endpoints."""
        self.client.force_authenticate(user=self.admin_user)

        # Create some test data first
        TeacherEvaluation.objects.create(
            teacher=self.teacher,
            evaluator=self.admin_user,
            evaluation_date=date.today(),
            criteria=TeacherEvaluation.get_default_criteria(),
            score=Decimal("85.0"),
            remarks="Good performance",
            status="reviewed",
        )

        # Test analytics overview
        response = self.client.get("/api/teachers/analytics/overview/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("performance_overview", response.data)

        # Test teacher performance analysis
        response = self.client.get(
            f"/api/teachers/analytics/performance/{self.teacher.id}/"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("growth_metrics", response.data)

        # Test dashboard metrics
        response = self.client.get("/api/teachers/analytics/dashboard/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("current_metrics", response.data)

    def test_teacher_permissions_workflow(self):
        """Test permission-based access control."""
        # Test teacher accessing their own profile
        self.client.force_authenticate(user=self.teacher_user)

        response = self.client.get("/api/teachers/profile/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["employee_id"], self.teacher.employee_id)

        # Test teacher updating their own profile (limited fields)
        update_data = {
            "bio": "Updated bio",
            "emergency_contact": "John Doe",
            "emergency_phone": "+1234567890",
        }

        response = self.client.patch("/api/teachers/profile/update/", update_data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify update
        self.teacher.refresh_from_db()
        self.assertEqual(self.teacher.bio, "Updated bio")

        # Test teacher cannot access other teachers' detailed info
        other_user = User.objects.create_user(
            username="other@school.edu",
            email="other@school.edu",
            password="testpass123",
        )

        other_teacher = Teacher.objects.create(
            user=other_user,
            employee_id="T999999",
            joining_date=date.today(),
            qualification="Bachelor of Arts",
            experience_years=Decimal("2.0"),
            specialization="English",
            department=self.department,
            position="Teacher",
            salary=Decimal("30000.00"),
            contract_type="Temporary",
            status="Active",
        )

        response = self.client.get(f"/api/teachers/{other_teacher.id}/")
        # Should allow viewing basic info but not sensitive data
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn("salary", response.data)

    def test_bulk_operations_api_workflow(self):
        """Test bulk operations via API."""
        self.client.force_authenticate(user=self.admin_user)

        # Create additional test data
        academic_year = AcademicYear.objects.create(
            name="2024-2025",
            start_date=date(2024, 9, 1),
            end_date=date(2025, 6, 30),
            is_current=True,
        )

        subject = Subject.objects.create(
            name="Physics", code="PHY001", department=self.department
        )

        section = Section.objects.create(name="Secondary")
        grade = Grade.objects.create(
            name="Grade 10", section=section, order_sequence=10
        )
        class_obj = Class.objects.create(
            name="A",
            grade=grade,
            academic_year=academic_year,
            room_number="201",
            capacity=30,
        )

        # Test bulk assignment creation
        assignments_data = {
            "assignments": [
                {
                    "teacher_id": self.teacher.id,
                    "class_instance_id": class_obj.id,
                    "subject_id": subject.id,
                    "academic_year_id": academic_year.id,
                    "is_class_teacher": True,
                    "notes": "Physics teacher for Grade 10A",
                }
            ]
        }

        response = self.client.post("/api/teachers/bulk-assign/", assignments_data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["success_count"], 1)
        self.assertEqual(response.data["error_count"], 0)

        # Verify assignment was created
        assignment = TeacherClassAssignment.objects.get(teacher=self.teacher)
        self.assertTrue(assignment.is_class_teacher)
        self.assertEqual(assignment.subject, subject)


class TeacherCacheIntegrationTest(TestCase):
    """Test caching integration in teacher module."""

    def setUp(self):
        """Set up test data."""
        cache.clear()

        self.department = Department.objects.create(
            name="Mathematics", description="Math Department"
        )

        self.user = User.objects.create_user(
            username="teacher@school.edu",
            email="teacher@school.edu",
            password="testpass123",
            first_name="John",
            last_name="Doe",
        )

        self.teacher = Teacher.objects.create(
            user=self.user,
            employee_id="T123456",
            joining_date=date.today(),
            qualification="Master of Education",
            experience_years=Decimal("5.0"),
            specialization="Mathematics",
            department=self.department,
            position="Teacher",
            salary=Decimal("40000.00"),
            contract_type="Permanent",
            status="Active",
        )

    def test_performance_metrics_caching(self):
        """Test that performance metrics are properly cached."""
        from src.teachers.middleware import TeacherPerformanceMiddleware

        # Create some evaluations
        for i in range(3):
            TeacherEvaluation.objects.create(
                teacher=self.teacher,
                evaluator=self.user,
                evaluation_date=date.today() - timedelta(days=i * 30),
                criteria=TeacherEvaluation.get_default_criteria(),
                score=Decimal(str(80 + i * 5)),
                remarks=f"Evaluation {i+1}",
                status="reviewed",
            )

        # Test analytics service caching
        analytics_data_1 = TeacherAnalyticsService.get_performance_overview(
            department_id=self.department.id
        )

        # Call again - should use cached data
        analytics_data_2 = TeacherAnalyticsService.get_performance_overview(
            department_id=self.department.id
        )

        # Results should be identical
        self.assertEqual(
            analytics_data_1["base_stats"]["total_teachers"],
            analytics_data_2["base_stats"]["total_teachers"],
        )

    def test_cache_invalidation_on_updates(self):
        """Test that cache is properly invalidated when data changes."""
        # Get initial analytics
        initial_data = TeacherAnalyticsService.get_performance_overview()
        initial_count = initial_data["base_stats"]["total_teachers"]

        # Create new teacher
        new_user = User.objects.create_user(
            username="new@school.edu", email="new@school.edu", password="testpass123"
        )

        Teacher.objects.create(
            user=new_user,
            employee_id="T789012",
            joining_date=date.today(),
            qualification="Bachelor of Education",
            experience_years=Decimal("2.0"),
            specialization="Science",
            department=self.department,
            position="Teacher",
            salary=Decimal("35000.00"),
            contract_type="Temporary",
            status="Active",
        )

        # Get updated analytics
        updated_data = TeacherAnalyticsService.get_performance_overview()
        updated_count = updated_data["base_stats"]["total_teachers"]

        # Count should be incremented
        self.assertEqual(updated_count, initial_count + 1)


class TeacherSignalIntegrationTest(TestCase):
    """Test Django signals integration in teacher module."""

    def setUp(self):
        """Set up test data."""
        self.department = Department.objects.create(
            name="Science", description="Science Department"
        )

        self.user = User.objects.create_user(
            username="teacher@school.edu",
            email="teacher@school.edu",
            password="testpass123",
            first_name="Jane",
            last_name="Smith",
        )

        self.evaluator = User.objects.create_user(
            username="evaluator@school.edu",
            email="evaluator@school.edu",
            password="testpass123",
            first_name="Principal",
            last_name="Wilson",
        )

    def test_teacher_creation_signals(self):
        """Test signals triggered on teacher creation."""
        # Create teacher group
        teacher_group = Group.objects.create(name="Teacher")

        # Create teacher
        teacher = Teacher.objects.create(
            user=self.user,
            employee_id="T123456",
            joining_date=date.today(),
            qualification="PhD in Physics",
            experience_years=Decimal("8.0"),
            specialization="Physics",
            department=self.department,
            position="Senior Teacher",
            salary=Decimal("50000.00"),
            contract_type="Permanent",
            status="Active",
        )

        # Verify user was added to teacher group
        self.assertTrue(self.user.groups.filter(name="Teacher").exists())

        # Verify audit log was created
        from src.core.models import AuditLog

        audit_logs = AuditLog.objects.filter(
            entity_type="Teacher", entity_id=teacher.id, action="CREATE"
        )
        self.assertTrue(audit_logs.exists())

    def test_evaluation_creation_signals(self):
        """Test signals triggered on evaluation creation."""
        # Create teacher
        teacher = Teacher.objects.create(
            user=self.user,
            employee_id="T123456",
            joining_date=date.today(),
            qualification="Master of Science",
            experience_years=Decimal("5.0"),
            specialization="Chemistry",
            department=self.department,
            position="Teacher",
            salary=Decimal("40000.00"),
            contract_type="Permanent",
            status="Active",
        )

        # Create evaluation with low score
        evaluation = TeacherEvaluation.objects.create(
            teacher=teacher,
            evaluator=self.evaluator,
            evaluation_date=date.today(),
            criteria=TeacherEvaluation.get_default_criteria(),
            score=Decimal("65.0"),
            remarks="Needs improvement in classroom management",
            status="submitted",
        )

        # Verify followup date was set automatically
        self.assertIsNotNone(evaluation.followup_date)
        self.assertEqual(
            evaluation.followup_date, evaluation.evaluation_date + timedelta(days=30)
        )

        # Verify notification was created for teacher
        notifications = Notification.objects.filter(
            user=teacher.user, notification_type="Evaluation"
        )
        self.assertTrue(notifications.exists())

        # Verify audit log was created
        from src.core.models import AuditLog

        audit_logs = AuditLog.objects.filter(
            entity_type="TeacherEvaluation", entity_id=evaluation.id, action="CREATE"
        )
        self.assertTrue(audit_logs.exists())


class TeacherTaskIntegrationTest(TransactionTestCase):
    """Test Celery task integration."""

    def setUp(self):
        """Set up test data."""
        self.department = Department.objects.create(
            name="Mathematics", description="Math Department"
        )

        self.academic_year = AcademicYear.objects.create(
            name="2024-2025",
            start_date=date(2024, 9, 1),
            end_date=date(2025, 6, 30),
            is_current=True,
        )

        # Create users and teachers
        self.users = []
        self.teachers = []

        for i in range(3):
            user = User.objects.create_user(
                username=f"teacher{i}@school.edu",
                email=f"teacher{i}@school.edu",
                password="testpass123",
                first_name=f"Teacher",
                last_name=f"{i}",
            )

            teacher = Teacher.objects.create(
                user=user,
                employee_id=f"T12345{i}",
                joining_date=date.today() - timedelta(days=200),
                qualification="Bachelor of Education",
                experience_years=Decimal("3.0"),
                specialization="Mathematics",
                department=self.department,
                position="Teacher",
                salary=Decimal("35000.00"),
                contract_type="Permanent",
                status="Active",
            )

            self.users.append(user)
            self.teachers.append(teacher)

    @patch("src.teachers.tasks.TeacherAnalyticsService")
    def test_analytics_calculation_task(self, mock_analytics):
        """Test analytics calculation task."""
        # Mock analytics service
        mock_analytics.get_performance_overview.return_value = {
            "base_stats": {"total_teachers": 3}
        }

        # Run task
        result = calculate_daily_teacher_analytics.apply(
            args=[self.academic_year.id]
        ).result

        # Verify task completed successfully
        self.assertEqual(result["status"], "success")
        self.assertIn("metrics", result)

        # Verify analytics service was called
        mock_analytics.get_performance_overview.assert_called()

    @patch("src.teachers.tasks.send_mail")
    def test_evaluation_reminder_task(self, mock_send_mail):
        """Test evaluation reminder task."""
        # Create department head
        head_user = User.objects.create_user(
            username="head@school.edu", email="head@school.edu", password="testpass123"
        )

        head_teacher = Teacher.objects.create(
            user=head_user,
            employee_id="T999999",
            joining_date=date.today() - timedelta(days=1000),
            qualification="PhD in Education",
            experience_years=Decimal("15.0"),
            specialization="Mathematics",
            department=self.department,
            position="Department Head",
            salary=Decimal("60000.00"),
            contract_type="Permanent",
            status="Active",
        )

        self.department.head = head_teacher
        self.department.save()

        # Run task
        result = send_evaluation_reminders.apply().result

        # Verify task completed
        self.assertEqual(result["status"], "success")
        self.assertGreater(result["teachers_needing_evaluation"], 0)

    def test_performance_update_task(self):
        """Test performance metrics update task."""
        from src.teachers.tasks import update_teacher_performance_metrics

        # Create some evaluations
        evaluator = User.objects.create_user(
            username="evaluator@school.edu",
            email="evaluator@school.edu",
            password="testpass123",
        )

        for teacher in self.teachers:
            TeacherEvaluation.objects.create(
                teacher=teacher,
                evaluator=evaluator,
                evaluation_date=date.today() - timedelta(days=30),
                criteria=TeacherEvaluation.get_default_criteria(),
                score=Decimal("75.0"),
                remarks="Good performance",
                status="reviewed",
            )

        # Run task
        result = update_teacher_performance_metrics.apply().result

        # Verify task completed
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["updated_count"], 3)
