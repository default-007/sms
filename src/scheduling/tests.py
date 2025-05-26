from django.test import TestCase, TransactionTestCase
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from datetime import datetime, time, date, timedelta
import json

from .models import (
    TimeSlot,
    Room,
    Timetable,
    TimetableTemplate,
    SubstituteTeacher,
    SchedulingConstraint,
    TimetableGeneration,
)
from .services.timetable_service import TimetableService, SubstituteService, RoomService
from .services.optimization_service import OptimizationService
from .services.analytics_service import SchedulingAnalyticsService
from academics.models import AcademicYear, Term, Grade, Section, Class
from subjects.models import Subject
from teachers.models import Teacher, TeacherClassAssignment
from accounts.models import User

User = get_user_model()


class BaseSchedulingTestCase(TestCase):
    """Base test case with common setup for scheduling tests"""

    def setUp(self):
        # Create users
        self.admin_user = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="testpass123",
            is_staff=True,
        )

        self.teacher_user = User.objects.create_user(
            username="teacher1", email="teacher1@example.com", password="testpass123"
        )

        # Create academic structure
        self.academic_year = AcademicYear.objects.create(
            name="2024-2025",
            start_date=date(2024, 4, 1),
            end_date=date(2025, 3, 31),
            is_current=True,
        )

        self.term = Term.objects.create(
            academic_year=self.academic_year,
            name="First Term",
            term_number=1,
            start_date=date(2024, 4, 1),
            end_date=date(2024, 7, 31),
            is_current=True,
        )

        self.section = Section.objects.create(
            name="Primary", description="Primary Section"
        )

        self.grade = Grade.objects.create(
            name="Grade 1", section=self.section, order_sequence=1
        )

        self.class_obj = Class.objects.create(
            name="A", grade=self.grade, academic_year=self.academic_year, capacity=30
        )

        # Create subject
        self.subject = Subject.objects.create(
            name="Mathematics", code="MATH001", credit_hours=5
        )

        # Create teacher
        self.teacher = Teacher.objects.create(
            user=self.teacher_user,
            employee_id="T001",
            joining_date=date(2024, 1, 1),
            status="active",
        )

        # Create teacher assignment
        self.teacher_assignment = TeacherClassAssignment.objects.create(
            teacher=self.teacher,
            class_assigned=self.class_obj,
            subject=self.subject,
            term=self.term,
            is_class_teacher=False,
        )

        # Create time slots
        self.time_slot = TimeSlot.objects.create(
            day_of_week=0,  # Monday
            start_time=time(9, 0),
            end_time=time(9, 45),
            duration_minutes=45,
            period_number=1,
            name="Period 1",
        )

        # Create room
        self.room = Room.objects.create(
            number="101",
            name="Classroom 101",
            room_type="classroom",
            capacity=35,
            is_available=True,
        )


class TimeSlotModelTest(BaseSchedulingTestCase):
    """Test TimeSlot model"""

    def test_create_time_slot(self):
        """Test creating a time slot"""
        time_slot = TimeSlot.objects.create(
            day_of_week=1,  # Tuesday
            start_time=time(10, 0),
            end_time=time(10, 45),
            duration_minutes=45,
            period_number=2,
            name="Period 2",
        )

        self.assertEqual(time_slot.get_day_of_week_display(), "Tuesday")
        self.assertEqual(str(time_slot), "Tuesday - Period 2 (10:00:00-10:45:00)")

    def test_time_slot_validation(self):
        """Test time slot validation"""
        with self.assertRaises(ValidationError):
            time_slot = TimeSlot(
                day_of_week=1,
                start_time=time(10, 45),  # Start after end
                end_time=time(10, 0),
                duration_minutes=45,
                period_number=2,
            )
            time_slot.full_clean()

    def test_duration_calculation(self):
        """Test duration calculation validation"""
        with self.assertRaises(ValidationError):
            time_slot = TimeSlot(
                day_of_week=1,
                start_time=time(10, 0),
                end_time=time(10, 45),
                duration_minutes=60,  # Wrong duration
                period_number=2,
            )
            time_slot.full_clean()


class RoomModelTest(BaseSchedulingTestCase):
    """Test Room model"""

    def test_create_room(self):
        """Test creating a room"""
        room = Room.objects.create(
            number="LAB1",
            name="Physics Laboratory",
            room_type="laboratory",
            capacity=25,
            equipment=["laboratory_equipment", "projector"],
        )

        self.assertEqual(str(room), "LAB1 - Physics Laboratory")
        self.assertIn("laboratory_equipment", room.equipment)

    def test_unique_room_number(self):
        """Test room number uniqueness"""
        with self.assertRaises(Exception):  # IntegrityError
            Room.objects.create(
                number="101",  # Same as existing room
                name="Another Room",
                room_type="classroom",
                capacity=30,
            )


class TimetableModelTest(BaseSchedulingTestCase):
    """Test Timetable model"""

    def test_create_timetable(self):
        """Test creating a timetable entry"""
        timetable = Timetable.objects.create(
            class_assigned=self.class_obj,
            subject=self.subject,
            teacher=self.teacher,
            time_slot=self.time_slot,
            room=self.room,
            term=self.term,
            effective_from_date=self.term.start_date,
            effective_to_date=self.term.end_date,
        )

        self.assertEqual(
            str(timetable), f"{self.class_obj} - {self.subject} - {self.time_slot}"
        )
        self.assertTrue(timetable.is_active)

    def test_timetable_conflict_detection(self):
        """Test conflict detection in timetable"""
        # Create first timetable
        timetable1 = Timetable.objects.create(
            class_assigned=self.class_obj,
            subject=self.subject,
            teacher=self.teacher,
            time_slot=self.time_slot,
            room=self.room,
            term=self.term,
            effective_from_date=self.term.start_date,
            effective_to_date=self.term.end_date,
        )

        # Try to create conflicting timetable (same teacher, same time)
        with self.assertRaises(ValidationError):
            timetable2 = Timetable(
                class_assigned=self.class_obj,
                subject=self.subject,
                teacher=self.teacher,  # Same teacher
                time_slot=self.time_slot,  # Same time slot
                term=self.term,
                effective_from_date=self.term.start_date,
                effective_to_date=self.term.end_date,
            )
            timetable2.full_clean()


class TimetableServiceTest(BaseSchedulingTestCase):
    """Test TimetableService"""

    def test_create_timetable_entry(self):
        """Test creating timetable entry via service"""
        timetable = TimetableService.create_timetable_entry(
            class_assigned=self.class_obj,
            subject=self.subject,
            teacher=self.teacher,
            time_slot=self.time_slot,
            term=self.term,
            room=self.room,
        )

        self.assertIsNotNone(timetable.id)
        self.assertEqual(timetable.class_assigned, self.class_obj)
        self.assertEqual(timetable.teacher, self.teacher)

    def test_get_class_timetable(self):
        """Test getting class timetable"""
        # Create timetable entry
        TimetableService.create_timetable_entry(
            class_assigned=self.class_obj,
            subject=self.subject,
            teacher=self.teacher,
            time_slot=self.time_slot,
            term=self.term,
            room=self.room,
        )

        timetable_data = TimetableService.get_class_timetable(self.class_obj, self.term)

        self.assertIn("Monday", timetable_data)
        self.assertEqual(len(timetable_data["Monday"]), 1)

    def test_conflict_checking(self):
        """Test conflict checking service"""
        # Create existing timetable
        TimetableService.create_timetable_entry(
            class_assigned=self.class_obj,
            subject=self.subject,
            teacher=self.teacher,
            time_slot=self.time_slot,
            term=self.term,
            room=self.room,
        )

        # Check for teacher conflict
        conflicts = TimetableService.check_conflicts(
            teacher=self.teacher,
            time_slot=self.time_slot,
            date_range=(self.term.start_date, self.term.end_date),
        )

        self.assertTrue(len(conflicts) > 0)
        self.assertEqual(conflicts[0]["type"], "teacher")

    def test_get_available_teachers(self):
        """Test getting available teachers"""
        available_teachers = TimetableService.get_available_teachers(
            time_slot=self.time_slot,
            subject=self.subject,
            date=self.term.start_date,
            class_obj=self.class_obj,
        )

        self.assertIn(self.teacher, available_teachers)

        # Create timetable and check again
        TimetableService.create_timetable_entry(
            class_assigned=self.class_obj,
            subject=self.subject,
            teacher=self.teacher,
            time_slot=self.time_slot,
            term=self.term,
            room=self.room,
        )

        available_teachers = TimetableService.get_available_teachers(
            time_slot=self.time_slot,
            subject=self.subject,
            date=self.term.start_date,
            class_obj=self.class_obj,
        )

        self.assertNotIn(self.teacher, available_teachers)

    def test_teacher_workload_calculation(self):
        """Test teacher workload calculation"""
        # Create multiple timetable entries
        for i in range(3):
            time_slot = TimeSlot.objects.create(
                day_of_week=0,
                start_time=time(9 + i, 0),
                end_time=time(9 + i, 45),
                duration_minutes=45,
                period_number=i + 1,
                name=f"Period {i + 1}",
            )

            TimetableService.create_timetable_entry(
                class_assigned=self.class_obj,
                subject=self.subject,
                teacher=self.teacher,
                time_slot=time_slot,
                term=self.term,
                room=self.room,
            )

        workload = TimetableService.get_teacher_workload(self.teacher, self.term)

        self.assertEqual(workload["total_periods"], 3)
        self.assertEqual(workload["classes_taught"], 1)
        self.assertEqual(workload["subjects_taught"], 1)


class SubstituteServiceTest(BaseSchedulingTestCase):
    """Test SubstituteService"""

    def setUp(self):
        super().setUp()

        # Create timetable for substitution
        self.timetable = TimetableService.create_timetable_entry(
            class_assigned=self.class_obj,
            subject=self.subject,
            teacher=self.teacher,
            time_slot=self.time_slot,
            term=self.term,
            room=self.room,
        )

        # Create substitute teacher
        self.substitute_user = User.objects.create_user(
            username="substitute1",
            email="substitute1@example.com",
            password="testpass123",
        )

        self.substitute_teacher = Teacher.objects.create(
            user=self.substitute_user,
            employee_id="S001",
            joining_date=date(2024, 1, 1),
            status="active",
        )

    def test_create_substitute_assignment(self):
        """Test creating substitute assignment"""
        substitute = SubstituteService.create_substitute_assignment(
            original_timetable=self.timetable,
            substitute_teacher=self.substitute_teacher,
            date=date.today(),
            reason="Sick leave",
        )

        self.assertIsNotNone(substitute.id)
        self.assertEqual(substitute.substitute_teacher, self.substitute_teacher)
        self.assertEqual(substitute.reason, "Sick leave")

    def test_substitute_suggestions(self):
        """Test getting substitute suggestions"""
        suggestions = SubstituteService.get_substitute_suggestions(
            self.timetable, date.today()
        )

        # Should include the substitute teacher we created
        teacher_ids = [s["teacher"].id for s in suggestions]
        self.assertIn(self.substitute_teacher.id, teacher_ids)


class RoomServiceTest(BaseSchedulingTestCase):
    """Test RoomService"""

    def test_room_utilization(self):
        """Test room utilization calculation"""
        # Create timetable entry
        TimetableService.create_timetable_entry(
            class_assigned=self.class_obj,
            subject=self.subject,
            teacher=self.teacher,
            time_slot=self.time_slot,
            term=self.term,
            room=self.room,
        )

        utilization = RoomService.get_room_utilization(self.room, self.term)

        self.assertIn("total_available_periods", utilization)
        self.assertIn("used_periods", utilization)
        self.assertIn("utilization_rate", utilization)
        self.assertEqual(utilization["used_periods"], 1)

    def test_room_booking_calendar(self):
        """Test room booking calendar"""
        # Create timetable entry
        TimetableService.create_timetable_entry(
            class_assigned=self.class_obj,
            subject=self.subject,
            teacher=self.teacher,
            time_slot=self.time_slot,
            term=self.term,
            room=self.room,
        )

        calendar = RoomService.get_room_booking_calendar(self.room, self.term)

        self.assertIn("Monday", calendar)
        self.assertEqual(len(calendar["Monday"]), 1)


class SchedulingAnalyticsServiceTest(BaseSchedulingTestCase):
    """Test SchedulingAnalyticsService"""

    def test_teacher_workload_analytics(self):
        """Test teacher workload analytics"""
        # Create some timetable entries
        for i in range(2):
            time_slot = TimeSlot.objects.create(
                day_of_week=0,
                start_time=time(9 + i, 0),
                end_time=time(9 + i, 45),
                duration_minutes=45,
                period_number=i + 1,
                name=f"Period {i + 1}",
            )

            TimetableService.create_timetable_entry(
                class_assigned=self.class_obj,
                subject=self.subject,
                teacher=self.teacher,
                time_slot=time_slot,
                term=self.term,
                room=self.room,
            )

        analytics = SchedulingAnalyticsService.get_teacher_workload_analytics(self.term)

        self.assertIn("teacher_workloads", analytics)
        self.assertIn("summary", analytics)
        self.assertEqual(len(analytics["teacher_workloads"]), 1)

    def test_room_utilization_analytics(self):
        """Test room utilization analytics"""
        # Create timetable entry
        TimetableService.create_timetable_entry(
            class_assigned=self.class_obj,
            subject=self.subject,
            teacher=self.teacher,
            time_slot=self.time_slot,
            term=self.term,
            room=self.room,
        )

        analytics = SchedulingAnalyticsService.get_room_utilization_analytics(self.term)

        self.assertIn("room_utilization", analytics)
        self.assertIn("summary", analytics)
        self.assertEqual(len(analytics["room_utilization"]), 1)

    def test_optimization_score(self):
        """Test optimization score calculation"""
        # Create some timetable entries
        TimetableService.create_timetable_entry(
            class_assigned=self.class_obj,
            subject=self.subject,
            teacher=self.teacher,
            time_slot=self.time_slot,
            term=self.term,
            room=self.room,
        )

        score_data = SchedulingAnalyticsService.get_timetable_optimization_score(
            self.term
        )

        self.assertIn("overall_score", score_data)
        self.assertIn("breakdown", score_data)
        self.assertIn("recommendations", score_data)
        self.assertGreaterEqual(score_data["overall_score"], 0)
        self.assertLessEqual(score_data["overall_score"], 100)


class SchedulingAPITest(APITestCase):
    """Test Scheduling API endpoints"""

    def setUp(self):
        self.client = APIClient()

        # Create test data (reuse from base test case)
        self.base_setup()

        # Authenticate
        self.client.force_authenticate(user=self.admin_user)

    def base_setup(self):
        """Setup base test data"""
        self.admin_user = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="testpass123",
            is_staff=True,
        )

        self.academic_year = AcademicYear.objects.create(
            name="2024-2025",
            start_date=date(2024, 4, 1),
            end_date=date(2025, 3, 31),
            is_current=True,
        )

        self.term = Term.objects.create(
            academic_year=self.academic_year,
            name="First Term",
            term_number=1,
            start_date=date(2024, 4, 1),
            end_date=date(2024, 7, 31),
            is_current=True,
        )

        self.time_slot = TimeSlot.objects.create(
            day_of_week=0,
            start_time=time(9, 0),
            end_time=time(9, 45),
            duration_minutes=45,
            period_number=1,
            name="Period 1",
        )

        self.room = Room.objects.create(
            number="101",
            name="Classroom 101",
            room_type="classroom",
            capacity=35,
            is_available=True,
        )

    def test_time_slot_list_api(self):
        """Test time slot list API"""
        url = reverse("scheduling:time-slot-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)

    def test_time_slot_create_api(self):
        """Test time slot creation API"""
        url = reverse("scheduling:time-slot-list")
        data = {
            "day_of_week": 1,
            "start_time": "10:00",
            "end_time": "10:45",
            "duration_minutes": 45,
            "period_number": 2,
            "name": "Period 2",
        }

        response = self.client.post(url, data)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(TimeSlot.objects.count(), 2)

    def test_room_list_api(self):
        """Test room list API"""
        url = reverse("scheduling:room-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)

    def test_room_create_api(self):
        """Test room creation API"""
        url = reverse("scheduling:room-list")
        data = {
            "number": "102",
            "name": "Classroom 102",
            "room_type": "classroom",
            "capacity": 30,
            "is_available": True,
        }

        response = self.client.post(url, data)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Room.objects.count(), 2)

    def test_analytics_api(self):
        """Test analytics API endpoints"""
        # Test teacher workload analytics
        url = reverse("scheduling:analytics-teacher-workload")
        response = self.client.get(url, {"term_id": str(self.term.id)})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("teacher_workloads", response.data)

        # Test room utilization analytics
        url = reverse("scheduling:analytics-room-utilization")
        response = self.client.get(url, {"term_id": str(self.term.id)})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("room_utilization", response.data)


class OptimizationServiceTest(BaseSchedulingTestCase):
    """Test optimization service"""

    def setUp(self):
        super().setUp()

        # Create additional test data for optimization
        self.time_slot_2 = TimeSlot.objects.create(
            day_of_week=0,
            start_time=time(10, 0),
            end_time=time(10, 45),
            duration_minutes=45,
            period_number=2,
            name="Period 2",
        )

        self.subject_2 = Subject.objects.create(
            name="English", code="ENG001", credit_hours=4
        )

        # Create teacher assignment for second subject
        TeacherClassAssignment.objects.create(
            teacher=self.teacher,
            class_assigned=self.class_obj,
            subject=self.subject_2,
            term=self.term,
            is_class_teacher=False,
        )

    def test_optimization_service_initialization(self):
        """Test optimization service initialization"""
        optimizer = OptimizationService(self.term)

        self.assertEqual(optimizer.term, self.term)
        self.assertIsNotNone(optimizer.time_slots)
        self.assertIsNotNone(optimizer.rooms)

    def test_required_slots_generation(self):
        """Test generation of required scheduling slots"""
        optimizer = OptimizationService(self.term)
        required_slots = optimizer._get_required_slots([self.grade])

        # Should have slots for both subjects
        self.assertGreater(len(required_slots), 0)

        # Check subjects are included
        subjects_in_slots = set(slot.subject for slot in required_slots)
        self.assertIn(self.subject, subjects_in_slots)
        self.assertIn(self.subject_2, subjects_in_slots)


class TimetableIntegrationTest(TransactionTestCase):
    """Integration tests for timetable functionality"""

    def setUp(self):
        # Create comprehensive test data
        self.admin_user = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="testpass123",
            is_staff=True,
        )

        # Create academic structure
        self.academic_year = AcademicYear.objects.create(
            name="2024-2025",
            start_date=date(2024, 4, 1),
            end_date=date(2025, 3, 31),
            is_current=True,
        )

        self.term = Term.objects.create(
            academic_year=self.academic_year,
            name="First Term",
            term_number=1,
            start_date=date(2024, 4, 1),
            end_date=date(2024, 7, 31),
            is_current=True,
        )

        # Create multiple time slots
        self.time_slots = []
        for i in range(6):  # 6 periods
            time_slot = TimeSlot.objects.create(
                day_of_week=0,  # Monday
                start_time=time(9 + i, 0),
                end_time=time(9 + i, 45),
                duration_minutes=45,
                period_number=i + 1,
                name=f"Period {i + 1}",
            )
            self.time_slots.append(time_slot)

        # Create rooms
        self.rooms = []
        for i in range(3):
            room = Room.objects.create(
                number=f"10{i + 1}",
                name=f"Classroom 10{i + 1}",
                room_type="classroom",
                capacity=30,
                is_available=True,
            )
            self.rooms.append(room)

        # Create subjects
        self.subjects = []
        subject_names = ["Mathematics", "English", "Science"]
        for i, name in enumerate(subject_names):
            subject = Subject.objects.create(
                name=name, code=f"{name[:3].upper()}00{i + 1}", credit_hours=5
            )
            self.subjects.append(subject)

        # Create teachers
        self.teachers = []
        for i in range(3):
            user = User.objects.create_user(
                username=f"teacher{i + 1}",
                email=f"teacher{i + 1}@example.com",
                password="testpass123",
            )
            teacher = Teacher.objects.create(
                user=user,
                employee_id=f"T00{i + 1}",
                joining_date=date(2024, 1, 1),
                status="active",
            )
            self.teachers.append(teacher)

        # Create academic structure
        self.section = Section.objects.create(
            name="Primary", description="Primary Section"
        )

        self.grade = Grade.objects.create(
            name="Grade 1", section=self.section, order_sequence=1
        )

        self.class_obj = Class.objects.create(
            name="A", grade=self.grade, academic_year=self.academic_year, capacity=30
        )

        # Create teacher assignments
        for i, (teacher, subject) in enumerate(zip(self.teachers, self.subjects)):
            TeacherClassAssignment.objects.create(
                teacher=teacher,
                class_assigned=self.class_obj,
                subject=subject,
                term=self.term,
                is_class_teacher=(i == 0),  # First teacher is class teacher
            )

    def test_complete_timetable_workflow(self):
        """Test complete timetable creation workflow"""
        # Step 1: Create individual timetable entries
        created_timetables = []

        for i in range(3):  # Create 3 timetable entries
            timetable = TimetableService.create_timetable_entry(
                class_assigned=self.class_obj,
                subject=self.subjects[i],
                teacher=self.teachers[i],
                time_slot=self.time_slots[i],
                term=self.term,
                room=self.rooms[i],
            )
            created_timetables.append(timetable)

        # Verify creation
        self.assertEqual(len(created_timetables), 3)
        self.assertEqual(Timetable.objects.filter(term=self.term).count(), 3)

        # Step 2: Test class timetable retrieval
        class_timetable = TimetableService.get_class_timetable(
            self.class_obj, self.term
        )
        self.assertIn("Monday", class_timetable)
        self.assertEqual(len(class_timetable["Monday"]), 3)

        # Step 3: Test teacher workload calculation
        for teacher in self.teachers:
            workload = TimetableService.get_teacher_workload(teacher, self.term)
            self.assertEqual(workload["total_periods"], 1)
            self.assertEqual(workload["classes_taught"], 1)

        # Step 4: Test analytics
        analytics = SchedulingAnalyticsService.get_teacher_workload_analytics(self.term)
        self.assertEqual(len(analytics["teacher_workloads"]), 3)

        room_analytics = SchedulingAnalyticsService.get_room_utilization_analytics(
            self.term
        )
        self.assertEqual(len(room_analytics["room_utilization"]), 3)

        # Step 5: Test optimization score
        score = SchedulingAnalyticsService.get_timetable_optimization_score(self.term)
        self.assertGreaterEqual(score["overall_score"], 0)
        self.assertLessEqual(score["overall_score"], 100)

    def test_conflict_resolution_workflow(self):
        """Test conflict detection and resolution"""
        # Create conflicting timetables
        timetable1 = TimetableService.create_timetable_entry(
            class_assigned=self.class_obj,
            subject=self.subjects[0],
            teacher=self.teachers[0],
            time_slot=self.time_slots[0],
            term=self.term,
            room=self.rooms[0],
        )

        # Check conflicts for same teacher, same time
        conflicts = TimetableService.check_conflicts(
            teacher=self.teachers[0],
            time_slot=self.time_slots[0],
            date_range=(self.term.start_date, self.term.end_date),
        )

        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0]["type"], "teacher")

        # Test conflict resolution by changing time slot
        timetable2 = TimetableService.create_timetable_entry(
            class_assigned=self.class_obj,
            subject=self.subjects[1],
            teacher=self.teachers[0],
            time_slot=self.time_slots[1],  # Different time slot
            term=self.term,
            room=self.rooms[1],
        )

        # Should not have conflicts now
        conflicts = TimetableService.check_conflicts(
            teacher=self.teachers[0],
            time_slot=self.time_slots[1],
            date_range=(self.term.start_date, self.term.end_date),
            exclude_timetable=timetable2,
        )

        self.assertEqual(len(conflicts), 0)

    def test_bulk_operations(self):
        """Test bulk timetable operations"""
        # Test bulk update
        updates = []
        for i in range(3):
            updates.append(
                {
                    "class_assigned": self.class_obj,
                    "subject": self.subjects[i],
                    "teacher": self.teachers[i],
                    "time_slot": self.time_slots[i],
                    "room": self.rooms[i],
                    "effective_from_date": self.term.start_date,
                    "effective_to_date": self.term.end_date,
                }
            )

        result = TimetableService.bulk_update_timetable(
            self.term, updates, self.admin_user
        )

        self.assertEqual(result["created"], 3)
        self.assertEqual(result["updated"], 0)
        self.assertEqual(len(result["errors"]), 0)

        # Verify bulk creation
        self.assertEqual(Timetable.objects.filter(term=self.term).count(), 3)
