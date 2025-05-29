from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase, TransactionTestCase
from django.utils import timezone

from academics.models import AcademicYear, Class, Grade, Section, Term
from students.models import Student

from .models import (
    FeeCategory,
    FeeStructure,
    FeeWaiver,
    Invoice,
    InvoiceItem,
    Payment,
    Scholarship,
    SpecialFee,
    StudentScholarship,
)
from .services.fee_service import FeeService
from .services.invoice_service import InvoiceService
from .services.payment_service import PaymentService
from .services.scholarship_service import ScholarshipService

User = get_user_model()


class FeeServiceTestCase(TestCase):
    """Test cases for FeeService."""

    def setUp(self):
        """Set up test data."""
        # Create users
        self.admin_user = User.objects.create_user(
            username="admin", email="admin@test.com", password="testpass"
        )

        self.student_user = User.objects.create_user(
            username="student", email="student@test.com", password="testpass"
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
            end_date=date(2024, 8, 31),
            is_current=True,
        )

        self.section = Section.objects.create(name="Primary")
        self.grade = Grade.objects.create(name="Grade 5", section=self.section)
        self.class_obj = Class.objects.create(
            name="A", grade=self.grade, academic_year=self.academic_year
        )

        # Create student
        self.student = Student.objects.create(
            user=self.student_user,
            admission_number="STU001",
            current_class=self.class_obj,
        )

        # Create fee categories
        self.tuition_category = FeeCategory.objects.create(
            name="Tuition", is_mandatory=True
        )

        self.transport_category = FeeCategory.objects.create(
            name="Transport", is_mandatory=False
        )

        # Create fee structures
        self.section_fee = FeeStructure.objects.create(
            academic_year=self.academic_year,
            term=self.term,
            section=self.section,
            fee_category=self.tuition_category,
            amount=Decimal("5000.00"),
            due_date=date(2024, 5, 1),
        )

        self.grade_fee = FeeStructure.objects.create(
            academic_year=self.academic_year,
            term=self.term,
            grade=self.grade,
            fee_category=self.transport_category,
            amount=Decimal("1000.00"),
            due_date=date(2024, 5, 1),
        )

    def test_calculate_student_fees(self):
        """Test fee calculation for a student."""
        fee_breakdown = FeeService.calculate_student_fees(
            self.student, self.academic_year, self.term
        )

        self.assertEqual(len(fee_breakdown["base_fees"]), 2)
        self.assertEqual(fee_breakdown["total_amount"], Decimal("6000.00"))
        self.assertEqual(fee_breakdown["net_amount"], Decimal("6000.00"))

    def test_special_fee_calculation(self):
        """Test special fee inclusion in calculation."""
        # Create special fee for the student
        special_fee = SpecialFee.objects.create(
            name="Lab Fee",
            fee_category=self.tuition_category,
            amount=Decimal("500.00"),
            fee_type="student_specific",
            student=self.student,
            term=self.term,
            due_date=date(2024, 5, 1),
            reason="Science lab usage",
        )

        fee_breakdown = FeeService.calculate_student_fees(
            self.student, self.academic_year, self.term
        )

        self.assertEqual(len(fee_breakdown["special_fees"]), 1)
        self.assertEqual(fee_breakdown["total_amount"], Decimal("6500.00"))

    def test_scholarship_discount(self):
        """Test scholarship discount application."""
        # Create scholarship
        scholarship = Scholarship.objects.create(
            name="Merit Scholarship",
            discount_type="percentage",
            discount_value=Decimal("10.00"),
            criteria="merit",
            academic_year=self.academic_year,
        )

        # Assign to student
        StudentScholarship.objects.create(
            student=self.student,
            scholarship=scholarship,
            status="approved",
            start_date=date(2024, 4, 1),
        )

        fee_breakdown = FeeService.calculate_student_fees(
            self.student, self.academic_year, self.term
        )

        expected_discount = Decimal("6000.00") * Decimal("0.10")
        self.assertEqual(fee_breakdown["discount_amount"], expected_discount)
        self.assertEqual(
            fee_breakdown["net_amount"], Decimal("6000.00") - expected_discount
        )


class InvoiceServiceTestCase(TestCase):
    """Test cases for InvoiceService."""

    def setUp(self):
        """Set up test data."""
        # Reuse setup from FeeServiceTestCase
        self.fee_test_case = FeeServiceTestCase()
        self.fee_test_case.setUp()

        # Copy attributes
        for attr in [
            "admin_user",
            "student_user",
            "academic_year",
            "term",
            "section",
            "grade",
            "class_obj",
            "student",
            "tuition_category",
            "transport_category",
            "section_fee",
            "grade_fee",
        ]:
            setattr(self, attr, getattr(self.fee_test_case, attr))

    def test_generate_invoice(self):
        """Test invoice generation."""
        invoice = InvoiceService.generate_invoice(
            self.student, self.academic_year, self.term, self.admin_user
        )

        self.assertIsNotNone(invoice.invoice_number)
        self.assertEqual(invoice.student, self.student)
        self.assertEqual(invoice.total_amount, Decimal("6000.00"))
        self.assertEqual(invoice.net_amount, Decimal("6000.00"))
        self.assertEqual(invoice.status, "unpaid")

        # Check invoice items
        self.assertEqual(invoice.items.count(), 2)

    def test_duplicate_invoice_prevention(self):
        """Test that duplicate invoices are prevented."""
        # Generate first invoice
        InvoiceService.generate_invoice(
            self.student, self.academic_year, self.term, self.admin_user
        )

        # Try to generate duplicate
        with self.assertRaises(ValidationError):
            InvoiceService.generate_invoice(
                self.student, self.academic_year, self.term, self.admin_user
            )

    def test_bulk_invoice_generation(self):
        """Test bulk invoice generation."""
        # Create additional students
        student2_user = User.objects.create_user(
            username="student2", email="student2@test.com"
        )
        student2 = Student.objects.create(
            user=student2_user, admission_number="STU002", current_class=self.class_obj
        )

        students = [self.student, student2]
        results = InvoiceService.bulk_generate_invoices(
            students, self.academic_year, self.term, self.admin_user
        )

        self.assertEqual(len(results["created"]), 2)
        self.assertEqual(len(results["skipped"]), 0)
        self.assertEqual(len(results["errors"]), 0)


class PaymentServiceTestCase(TestCase):
    """Test cases for PaymentService."""

    def setUp(self):
        """Set up test data."""
        # Reuse setup from InvoiceServiceTestCase
        self.invoice_test_case = InvoiceServiceTestCase()
        self.invoice_test_case.setUp()

        # Copy attributes
        for attr in ["admin_user", "student", "academic_year", "term"]:
            setattr(self, attr, getattr(self.invoice_test_case, attr))

        # Generate invoice for testing
        self.invoice = InvoiceService.generate_invoice(
            self.student, self.academic_year, self.term, self.admin_user
        )

    def test_process_payment(self):
        """Test payment processing."""
        payment = PaymentService.process_single_payment(
            invoice_id=self.invoice.id,
            amount=Decimal("3000.00"),
            payment_method="cash",
            received_by=self.admin_user,
        )

        self.assertEqual(payment.amount, Decimal("3000.00"))
        self.assertEqual(payment.status, "completed")
        self.assertIsNotNone(payment.receipt_number)

        # Check invoice update
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.paid_amount, Decimal("3000.00"))
        self.assertEqual(self.invoice.status, "partially_paid")

    def test_full_payment(self):
        """Test full payment processing."""
        PaymentService.process_single_payment(
            invoice_id=self.invoice.id,
            amount=self.invoice.net_amount,
            payment_method="cash",
            received_by=self.admin_user,
        )

        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, "paid")
        self.assertEqual(self.invoice.outstanding_amount, Decimal("0.00"))

    def test_overpayment_handling(self):
        """Test overpayment (advance payment) handling."""
        overpayment_amount = self.invoice.net_amount + Decimal("1000.00")

        payment = PaymentService.process_single_payment(
            invoice_id=self.invoice.id,
            amount=overpayment_amount,
            payment_method="cash",
            received_by=self.admin_user,
        )

        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, "paid")
        # Outstanding should be negative (advance)
        self.assertEqual(self.invoice.outstanding_amount, -Decimal("1000.00"))


class ScholarshipServiceTestCase(TestCase):
    """Test cases for ScholarshipService."""

    def setUp(self):
        """Set up test data."""
        # Reuse setup from previous test cases
        self.payment_test_case = PaymentServiceTestCase()
        self.payment_test_case.setUp()

        # Copy attributes
        for attr in ["admin_user", "student", "academic_year"]:
            setattr(self, attr, getattr(self.payment_test_case, attr))

        # Create scholarship
        self.scholarship = Scholarship.objects.create(
            name="Test Scholarship",
            description="Test scholarship for unit tests",
            discount_type="percentage",
            discount_value=Decimal("15.00"),
            criteria="merit",
            academic_year=self.academic_year,
            max_recipients=10,
        )

    def test_assign_scholarship(self):
        """Test scholarship assignment."""
        student_scholarship = ScholarshipService.assign_scholarship(
            student=self.student,
            scholarship=self.scholarship,
            approved_by=self.admin_user,
        )

        self.assertEqual(student_scholarship.status, "approved")
        self.assertEqual(student_scholarship.student, self.student)
        self.assertEqual(student_scholarship.scholarship, self.scholarship)

        # Check scholarship recipient count update
        self.scholarship.refresh_from_db()
        self.assertEqual(self.scholarship.current_recipients, 1)

    def test_duplicate_scholarship_prevention(self):
        """Test prevention of duplicate scholarship assignments."""
        # Assign scholarship first time
        ScholarshipService.assign_scholarship(
            student=self.student,
            scholarship=self.scholarship,
            approved_by=self.admin_user,
        )

        # Try to assign again
        with self.assertRaises(ValidationError):
            ScholarshipService.assign_scholarship(
                student=self.student,
                scholarship=self.scholarship,
                approved_by=self.admin_user,
            )

    def test_scholarship_capacity_limit(self):
        """Test scholarship capacity limits."""
        # Set max recipients to 1
        self.scholarship.max_recipients = 1
        self.scholarship.save()

        # Assign to first student
        ScholarshipService.assign_scholarship(
            student=self.student,
            scholarship=self.scholarship,
            approved_by=self.admin_user,
        )

        # Create second student
        student2_user = User.objects.create_user(
            username="student2", email="student2@test.com"
        )
        student2 = Student.objects.create(
            user=student2_user,
            admission_number="STU002",
            current_class=self.payment_test_case.class_obj,
        )

        # Try to assign to second student (should fail)
        with self.assertRaises(ValidationError):
            ScholarshipService.assign_scholarship(
                student=student2,
                scholarship=self.scholarship,
                approved_by=self.admin_user,
            )


class ModelTestCase(TestCase):
    """Test cases for model methods and properties."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(username="testuser", email="test@test.com")

        self.academic_year = AcademicYear.objects.create(
            name="2024-2025", start_date=date(2024, 4, 1), end_date=date(2025, 3, 31)
        )

        self.term = Term.objects.create(
            academic_year=self.academic_year,
            name="First Term",
            term_number=1,
            start_date=date(2024, 4, 1),
            end_date=date(2024, 8, 31),
        )

        self.section = Section.objects.create(name="Primary")
        self.grade = Grade.objects.create(name="Grade 1", section=self.section)
        self.class_obj = Class.objects.create(
            name="A", grade=self.grade, academic_year=self.academic_year
        )

        self.student = Student.objects.create(
            user=self.user, admission_number="STU001", current_class=self.class_obj
        )

    def test_invoice_number_generation(self):
        """Test automatic invoice number generation."""
        invoice = Invoice.objects.create(
            student=self.student,
            academic_year=self.academic_year,
            term=self.term,
            total_amount=Decimal("1000.00"),
            net_amount=Decimal("1000.00"),
            due_date=date.today(),
        )

        self.assertIsNotNone(invoice.invoice_number)
        self.assertTrue(invoice.invoice_number.startswith("INV"))

    def test_payment_receipt_generation(self):
        """Test automatic receipt number generation."""
        invoice = Invoice.objects.create(
            student=self.student,
            academic_year=self.academic_year,
            term=self.term,
            total_amount=Decimal("1000.00"),
            net_amount=Decimal("1000.00"),
            due_date=date.today(),
        )

        payment = Payment.objects.create(
            invoice=invoice, amount=Decimal("1000.00"), payment_method="cash"
        )

        self.assertIsNotNone(payment.receipt_number)
        self.assertTrue(payment.receipt_number.startswith("RCP"))

    def test_invoice_overdue_property(self):
        """Test invoice overdue property."""
        # Create overdue invoice
        overdue_date = date.today() - timedelta(days=5)
        invoice = Invoice.objects.create(
            student=self.student,
            academic_year=self.academic_year,
            term=self.term,
            total_amount=Decimal("1000.00"),
            net_amount=Decimal("1000.00"),
            due_date=overdue_date,
        )

        self.assertTrue(invoice.is_overdue)

        # Create future due date invoice
        future_date = date.today() + timedelta(days=5)
        invoice2 = Invoice.objects.create(
            student=self.student,
            academic_year=self.academic_year,
            term=self.term,
            total_amount=Decimal("1000.00"),
            net_amount=Decimal("1000.00"),
            due_date=future_date,
        )

        self.assertFalse(invoice2.is_overdue)

    def test_scholarship_available_slots(self):
        """Test scholarship available slots property."""
        scholarship = Scholarship.objects.create(
            name="Test Scholarship",
            discount_type="percentage",
            discount_value=Decimal("10.00"),
            criteria="merit",
            academic_year=self.academic_year,
            max_recipients=5,
            current_recipients=3,
        )

        self.assertTrue(scholarship.has_available_slots)

        # Fill up the scholarship
        scholarship.current_recipients = 5
        scholarship.save()

        self.assertFalse(scholarship.has_available_slots)

        # Test unlimited scholarship
        unlimited_scholarship = Scholarship.objects.create(
            name="Unlimited Scholarship",
            discount_type="percentage",
            discount_value=Decimal("10.00"),
            criteria="merit",
            academic_year=self.academic_year,
            max_recipients=None,
            current_recipients=100,
        )

        self.assertTrue(unlimited_scholarship.has_available_slots)


class APITestCase(TestCase):
    """Test cases for API endpoints."""

    def setUp(self):
        """Set up test data."""
        self.admin_user = User.objects.create_user(
            username="admin", email="admin@test.com", is_staff=True, is_superuser=True
        )

        self.client.force_login(self.admin_user)

        # Create basic data
        self.fee_category = FeeCategory.objects.create(
            name="Tuition", is_mandatory=True
        )

    def test_fee_category_creation(self):
        """Test fee category creation via API."""
        data = {
            "name": "Transport Fee",
            "description": "Transportation charges",
            "is_mandatory": False,
            "frequency": "monthly",
        }

        response = self.client.post("/api/finance/fee-categories/", data)
        self.assertEqual(response.status_code, 201)

        # Check if category was created
        self.assertTrue(FeeCategory.objects.filter(name="Transport Fee").exists())

    def test_fee_category_list(self):
        """Test fee category listing via API."""
        response = self.client.get("/api/finance/fee-categories/")
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertIn("results", data)
        self.assertEqual(len(data["results"]), 1)
        self.assertEqual(data["results"][0]["name"], "Tuition")


class TransactionTestCase(TransactionTestCase):
    """Test cases that require database transactions."""

    def test_payment_signal_handling(self):
        """Test that payment signals update invoice correctly."""
        # This test requires TransactionTestCase because signals
        # might not work properly with regular TestCase

        # Create test data
        user = User.objects.create_user(username="test", email="test@test.com")
        academic_year = AcademicYear.objects.create(
            name="2024", start_date=date.today(), end_date=date.today()
        )
        term = Term.objects.create(
            academic_year=academic_year,
            name="Term 1",
            term_number=1,
            start_date=date.today(),
            end_date=date.today(),
        )
        section = Section.objects.create(name="Primary")
        grade = Grade.objects.create(name="Grade 1", section=section)
        class_obj = Class.objects.create(
            name="A", grade=grade, academic_year=academic_year
        )
        student = Student.objects.create(
            user=user, admission_number="STU001", current_class=class_obj
        )

        invoice = Invoice.objects.create(
            student=student,
            academic_year=academic_year,
            term=term,
            total_amount=Decimal("1000.00"),
            net_amount=Decimal("1000.00"),
            due_date=date.today(),
        )

        # Create payment - this should trigger signals
        payment = Payment.objects.create(
            invoice=invoice,
            amount=Decimal("500.00"),
            payment_method="cash",
            status="completed",
        )

        # Refresh invoice and check if it was updated
        invoice.refresh_from_db()
        self.assertEqual(invoice.paid_amount, Decimal("500.00"))
        self.assertEqual(invoice.status, "partially_paid")
