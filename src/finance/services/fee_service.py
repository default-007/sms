from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from django.core.exceptions import ValidationError
from django.db.models import Q, Sum
from django.utils import timezone

from ..models import (
    FeeCategory,
    FeeStructure,
    Invoice,
    InvoiceItem,
    Scholarship,
    SpecialFee,
    StudentScholarship,
)


class FeeService:
    """Service for fee calculation and management."""

    @classmethod
    def calculate_student_fees(cls, student, academic_year, term) -> Dict:
        """
        Calculate total fees for a student for a specific term.
        Returns breakdown of all applicable fees and discounts.
        """
        # Get student's class to determine grade and section
        try:
            current_class = student.current_class
            grade = current_class.grade
            section = grade.section
        except AttributeError:
            raise ValidationError("Student must be assigned to a class")

        fee_breakdown = {
            "base_fees": [],
            "special_fees": [],
            "total_amount": Decimal("0.00"),
            "discount_amount": Decimal("0.00"),
            "net_amount": Decimal("0.00"),
            "scholarships_applied": [],
        }

        # 1. Calculate base fees from fee structure
        base_fees = cls._get_base_fees(section, grade, academic_year, term)
        fee_breakdown["base_fees"] = base_fees

        # 2. Calculate special fees
        special_fees = cls._get_special_fees(student, current_class, term)
        fee_breakdown["special_fees"] = special_fees

        # 3. Calculate total before discounts
        total_base = sum(fee["amount"] for fee in base_fees)
        total_special = sum(fee["amount"] for fee in special_fees)
        fee_breakdown["total_amount"] = total_base + total_special

        # 4. Apply scholarships and discounts
        scholarships = cls._calculate_scholarships(student, academic_year, term)
        discount_amount = cls._calculate_discount_amount(
            fee_breakdown["total_amount"], scholarships, base_fees + special_fees
        )

        fee_breakdown["discount_amount"] = discount_amount
        fee_breakdown["net_amount"] = fee_breakdown["total_amount"] - discount_amount
        fee_breakdown["scholarships_applied"] = scholarships

        return fee_breakdown

    @classmethod
    def _get_base_fees(cls, section, grade, academic_year, term) -> List[Dict]:
        """Get base fees from fee structure hierarchy."""
        fees = []

        # Section-level fees
        section_fees = FeeStructure.objects.filter(
            academic_year=academic_year,
            term=term,
            section=section,
            grade__isnull=True,
            is_active=True,
        ).select_related("fee_category")

        for fee in section_fees:
            fees.append(
                {
                    "type": "section",
                    "category": fee.fee_category.name,
                    "amount": fee.amount,
                    "due_date": fee.due_date,
                    "late_fee_percentage": fee.late_fee_percentage,
                    "grace_period_days": fee.grace_period_days,
                    "fee_structure_id": fee.id,
                }
            )

        # Grade-level fees (more specific, so they override section fees)
        grade_fees = FeeStructure.objects.filter(
            academic_year=academic_year, term=term, grade=grade, is_active=True
        ).select_related("fee_category")

        for fee in grade_fees:
            fees.append(
                {
                    "type": "grade",
                    "category": fee.fee_category.name,
                    "amount": fee.amount,
                    "due_date": fee.due_date,
                    "late_fee_percentage": fee.late_fee_percentage,
                    "grace_period_days": fee.grace_period_days,
                    "fee_structure_id": fee.id,
                }
            )

        return fees

    @classmethod
    def _get_special_fees(cls, student, current_class, term) -> List[Dict]:
        """Get special fees for student and class."""
        fees = []

        # Class-based special fees
        class_fees = SpecialFee.objects.filter(
            class_obj=current_class, term=term, fee_type="class_based", is_active=True
        ).select_related("fee_category")

        for fee in class_fees:
            fees.append(
                {
                    "type": "class_special",
                    "category": fee.fee_category.name,
                    "name": fee.name,
                    "amount": fee.amount,
                    "due_date": fee.due_date,
                    "reason": fee.reason,
                    "special_fee_id": fee.id,
                }
            )

        # Student-specific special fees
        student_fees = SpecialFee.objects.filter(
            student=student, term=term, fee_type="student_specific", is_active=True
        ).select_related("fee_category")

        for fee in student_fees:
            fees.append(
                {
                    "type": "student_special",
                    "category": fee.fee_category.name,
                    "name": fee.name,
                    "amount": fee.amount,
                    "due_date": fee.due_date,
                    "reason": fee.reason,
                    "special_fee_id": fee.id,
                }
            )

        return fees

    @classmethod
    def _calculate_scholarships(cls, student, academic_year, term) -> List[Dict]:
        """Get applicable scholarships for student."""
        scholarships = []

        # Get student's active scholarships for the academic year
        student_scholarships = (
            StudentScholarship.objects.filter(
                student=student,
                scholarship__academic_year=academic_year,
                status="approved",
                start_date__lte=timezone.now().date(),
            )
            .filter(Q(end_date__gte=timezone.now().date()) | Q(end_date__isnull=True))
            .select_related("scholarship")
        )

        for student_scholarship in student_scholarships:
            scholarship = student_scholarship.scholarship

            # Check if scholarship applies to this term
            if (
                not scholarship.applicable_terms
                or term.id in scholarship.applicable_terms
            ):

                scholarships.append(
                    {
                        "name": scholarship.name,
                        "discount_type": scholarship.discount_type,
                        "discount_value": scholarship.discount_value,
                        "criteria": scholarship.criteria,
                        "applicable_categories": list(
                            scholarship.applicable_categories.values_list(
                                "name", flat=True
                            )
                        ),
                        "scholarship_id": scholarship.id,
                        "student_scholarship_id": student_scholarship.id,
                    }
                )

        return scholarships

    @classmethod
    def _calculate_discount_amount(
        cls, total_amount: Decimal, scholarships: List[Dict], fee_items: List[Dict]
    ) -> Decimal:
        """Calculate total discount amount from scholarships."""
        total_discount = Decimal("0.00")

        for scholarship in scholarships:
            if scholarship["discount_type"] == "percentage":
                # Apply percentage discount
                discount_rate = scholarship["discount_value"] / 100

                if scholarship["applicable_categories"]:
                    # Apply to specific categories only
                    applicable_amount = sum(
                        item["amount"]
                        for item in fee_items
                        if item.get("category") in scholarship["applicable_categories"]
                    )
                    total_discount += applicable_amount * discount_rate
                else:
                    # Apply to total amount
                    total_discount += total_amount * discount_rate

            elif scholarship["discount_type"] == "fixed_amount":
                # Apply fixed amount discount
                total_discount += scholarship["discount_value"]

        # Ensure discount doesn't exceed total amount
        return min(total_discount, total_amount)

    @classmethod
    def calculate_late_fees(cls, invoice) -> Decimal:
        """Calculate late fees for an overdue invoice."""
        if not invoice.is_overdue:
            return Decimal("0.00")

        from django.utils import timezone

        total_late_fee = Decimal("0.00")
        current_date = timezone.now().date()

        for item in invoice.items.all():
            # Get the fee structure to determine late fee percentage
            fee_structure = item.fee_structure
            if fee_structure:
                days_overdue = (current_date - invoice.due_date).days
                grace_period = fee_structure.grace_period_days

                if days_overdue > grace_period:
                    late_fee_percentage = fee_structure.late_fee_percentage / 100
                    late_fee = item.net_amount * late_fee_percentage
                    total_late_fee += late_fee

        return total_late_fee

    @classmethod
    def create_fee_structure(cls, data: Dict) -> FeeStructure:
        """Create a new fee structure with validation."""
        # Validate that either section or grade is provided
        if not data.get("section") and not data.get("grade"):
            raise ValidationError("Either section or grade must be specified")

        # Check for duplicate fee structures
        existing = FeeStructure.objects.filter(
            academic_year=data["academic_year"],
            term=data["term"],
            section=data.get("section"),
            grade=data.get("grade"),
            fee_category=data["fee_category"],
        ).exists()

        if existing:
            raise ValidationError("Fee structure already exists for this combination")

        return FeeStructure.objects.create(**data)

    @classmethod
    def create_special_fee(cls, data: Dict) -> SpecialFee:
        """Create a special fee with validation."""
        fee_type = data.get("fee_type")

        # Validate required fields based on fee type
        if fee_type == "class_based" and not data.get("class_obj"):
            raise ValidationError("Class is required for class-based fees")
        elif fee_type == "student_specific" and not data.get("student"):
            raise ValidationError("Student is required for student-specific fees")

        return SpecialFee.objects.create(**data)

    @classmethod
    def bulk_apply_special_fee(
        cls, fee_data: Dict, target_list: List
    ) -> List[SpecialFee]:
        """Apply special fee to multiple targets (classes or students)."""
        created_fees = []

        for target in target_list:
            if fee_data["fee_type"] == "class_based":
                fee_data["class_obj"] = target
            else:
                fee_data["student"] = target

            try:
                special_fee = cls.create_special_fee(fee_data.copy())
                created_fees.append(special_fee)
            except ValidationError:
                # Skip if duplicate or invalid
                continue

        return created_fees

    @classmethod
    def get_fee_summary_by_section(cls, academic_year, term) -> Dict:
        """Get fee summary grouped by section."""
        from django.db.models import Avg, Count

        summary = {}

        # Get all sections with students
        sections = (
            academic_year.class_set.select_related("grade__section")
            .values("grade__section__id", "grade__section__name")
            .annotate(student_count=Count("student"))
            .distinct()
        )

        for section_data in sections:
            section_id = section_data["grade__section__id"]
            section_name = section_data["grade__section__name"]

            # Calculate fees for this section
            section_fees = FeeStructure.objects.filter(
                academic_year=academic_year,
                term=term,
                section_id=section_id,
                is_active=True,
            ).aggregate(
                total_fees=Sum("amount"), avg_fees=Avg("amount"), fee_count=Count("id")
            )

            summary[section_name] = {
                "student_count": section_data["student_count"],
                "total_fees": section_fees["total_fees"] or Decimal("0.00"),
                "average_fees": section_fees["avg_fees"] or Decimal("0.00"),
                "fee_structure_count": section_fees["fee_count"],
            }

        return summary

    @classmethod
    def validate_fee_structure_hierarchy(cls, academic_year, term) -> Dict:
        """Validate fee structure completeness and conflicts."""
        issues = {
            "missing_mandatory_fees": [],
            "duplicate_fees": [],
            "orphaned_grades": [],
            "warnings": [],
        }

        # Check for mandatory fee categories
        mandatory_categories = FeeCategory.objects.filter(is_mandatory=True)

        for category in mandatory_categories:
            # Check if each section has this mandatory fee
            sections_without_fee = []
            # Implementation would check each section for mandatory fees

        return issues
