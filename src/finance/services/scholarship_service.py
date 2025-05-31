from decimal import Decimal
from typing import Dict, List, Optional

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, F, Q, Sum
from django.utils import timezone

from src.students.models import Student, StudentParentRelation

from ..models import FeeCategory, Scholarship, StudentScholarship


class ScholarshipService:
    """Service for scholarship management and allocation."""

    @classmethod
    @transaction.atomic
    def create_scholarship(cls, data: Dict) -> Scholarship:
        """Create a new scholarship with validation."""

        # Validate discount value based on type
        if data["discount_type"] == "percentage":
            if data["discount_value"] > 100:
                raise ValidationError("Percentage discount cannot exceed 100%")
        elif data["discount_value"] <= 0:
            raise ValidationError("Discount value must be positive")

        # Create scholarship
        scholarship = Scholarship.objects.create(**data)

        # Set applicable categories if provided
        if "applicable_category_ids" in data:
            categories = FeeCategory.objects.filter(
                id__in=data["applicable_category_ids"]
            )
            scholarship.applicable_categories.set(categories)

        return scholarship

    @classmethod
    @transaction.atomic
    def assign_scholarship(
        cls, student, scholarship, start_date=None, approved_by=None, remarks=""
    ) -> StudentScholarship:
        """Assign scholarship to a student."""

        # Check if student already has this scholarship
        existing = StudentScholarship.objects.filter(
            student=student, scholarship=scholarship, status__in=["approved", "pending"]
        ).exists()

        if existing:
            raise ValidationError("Student already has this scholarship")

        # Check scholarship availability
        if not scholarship.has_available_slots:
            raise ValidationError("No available slots for this scholarship")

        # Validate academic year compatibility
        current_year = getattr(student.current_class, "academic_year", None)
        if current_year and current_year != scholarship.academic_year:
            raise ValidationError(
                "Scholarship not available for student's academic year"
            )

        # Create assignment
        student_scholarship = StudentScholarship.objects.create(
            student=student,
            scholarship=scholarship,
            start_date=start_date or timezone.now().date(),
            approved_by=approved_by,
            remarks=remarks,
            status="approved" if approved_by else "pending",
        )

        # Update scholarship recipient count
        if student_scholarship.status == "approved":
            scholarship.current_recipients = F("current_recipients") + 1
            scholarship.save()

        return student_scholarship

    @classmethod
    def bulk_assign_scholarships(
        cls, student_list: List, scholarship_id: int, approved_by=None
    ) -> Dict:
        """Assign scholarship to multiple students."""

        try:
            scholarship = Scholarship.objects.get(id=scholarship_id)
        except Scholarship.DoesNotExist:
            raise ValidationError("Scholarship not found")

        results = {"assigned": [], "skipped": [], "errors": []}

        for student in student_list:
            try:
                student_scholarship = cls.assign_scholarship(
                    student=student, scholarship=scholarship, approved_by=approved_by
                )
                results["assigned"].append(
                    {"student": student, "scholarship_assignment": student_scholarship}
                )
            except ValidationError as e:
                results["skipped"].append({"student": student, "reason": str(e)})
            except Exception as e:
                results["errors"].append({"student": student, "error": str(e)})

        return results

    @classmethod
    @transaction.atomic
    def approve_scholarship(
        cls, student_scholarship_id: int, approved_by
    ) -> StudentScholarship:
        """Approve a pending scholarship assignment."""

        try:
            student_scholarship = StudentScholarship.objects.select_for_update().get(
                id=student_scholarship_id
            )
        except StudentScholarship.DoesNotExist:
            raise ValidationError("Scholarship assignment not found")

        if student_scholarship.status != "pending":
            raise ValidationError("Only pending scholarships can be approved")

        # Check if scholarship still has available slots
        scholarship = student_scholarship.scholarship
        if not scholarship.has_available_slots:
            raise ValidationError("No available slots remaining for this scholarship")

        # Approve scholarship
        student_scholarship.status = "approved"
        student_scholarship.approved_by = approved_by
        student_scholarship.approval_date = timezone.now()
        student_scholarship.save()

        # Update scholarship recipient count
        scholarship.current_recipients = F("current_recipients") + 1
        scholarship.save()

        return student_scholarship

    @classmethod
    @transaction.atomic
    def suspend_scholarship(
        cls, student_scholarship_id: int, reason: str, suspended_by
    ) -> StudentScholarship:
        """Suspend an active scholarship."""

        try:
            student_scholarship = StudentScholarship.objects.get(
                id=student_scholarship_id
            )
        except StudentScholarship.DoesNotExist:
            raise ValidationError("Scholarship assignment not found")

        if student_scholarship.status != "approved":
            raise ValidationError("Only approved scholarships can be suspended")

        # Suspend scholarship
        student_scholarship.status = "suspended"
        student_scholarship.remarks += f"\nSuspended: {reason}"
        student_scholarship.save()

        # Update scholarship recipient count
        scholarship = student_scholarship.scholarship
        scholarship.current_recipients = F("current_recipients") - 1
        scholarship.save()

        return student_scholarship

    @classmethod
    def calculate_scholarship_impact(
        cls, scholarship_id: int, academic_year, term=None
    ) -> Dict:
        """Calculate the financial impact of a scholarship."""

        try:
            scholarship = Scholarship.objects.get(id=scholarship_id)
        except Scholarship.DoesNotExist:
            raise ValidationError("Scholarship not found")

        # Get all approved assignments
        assignments = StudentScholarship.objects.filter(
            scholarship=scholarship, status="approved"
        ).select_related("student")

        total_discount = Decimal("0.00")
        beneficiaries = assignments.count()

        # Calculate discount for each student
        for assignment in assignments:
            student = assignment.student

            # Get student's fees for the term
            from .fee_service import FeeService

            try:
                fee_breakdown = FeeService.calculate_student_fees(
                    student, academic_year, term
                )

                # Calculate discount for this student
                student_discount = cls._calculate_student_discount(
                    scholarship, fee_breakdown
                )
                total_discount += student_discount

            except Exception:
                # Skip if unable to calculate fees for this student
                continue

        return {
            "scholarship": scholarship,
            "total_beneficiaries": beneficiaries,
            "total_discount_amount": total_discount,
            "average_discount_per_student": (
                total_discount / beneficiaries if beneficiaries > 0 else Decimal("0.00")
            ),
            "remaining_slots": (
                scholarship.max_recipients - scholarship.current_recipients
                if scholarship.max_recipients
                else None
            ),
        }

    @classmethod
    def _calculate_student_discount(cls, scholarship, fee_breakdown) -> Decimal:
        """Calculate discount amount for a specific student."""

        if scholarship.discount_type == "percentage":
            discount_rate = scholarship.discount_value / 100

            if scholarship.applicable_categories.exists():
                # Apply to specific categories only
                applicable_categories = set(
                    scholarship.applicable_categories.values_list("name", flat=True)
                )

                applicable_amount = sum(
                    item["amount"]
                    for item in fee_breakdown["base_fees"]
                    + fee_breakdown["special_fees"]
                    if item.get("category") in applicable_categories
                )
                return applicable_amount * discount_rate
            else:
                # Apply to total amount
                return fee_breakdown["total_amount"] * discount_rate

        elif scholarship.discount_type == "fixed_amount":
            return scholarship.discount_value

        return Decimal("0.00")

    @classmethod
    def get_eligible_students(cls, scholarship, criteria_filters=None) -> List:
        """Get list of students eligible for a scholarship."""
        from students.models import Student

        # Base queryset - students in the scholarship's academic year
        queryset = Student.objects.filter(
            current_class__academic_year=scholarship.academic_year, status="active"
        ).select_related("user", "current_class")

        # Exclude students who already have this scholarship
        existing_recipients = StudentScholarship.objects.filter(
            scholarship=scholarship, status__in=["approved", "pending"]
        ).values_list("student_id", flat=True)

        queryset = queryset.exclude(id__in=existing_recipients)

        # Apply criteria-based filters
        if scholarship.criteria == "merit":
            # Could integrate with academic performance data
            # For now, return all eligible students
            pass
        elif scholarship.criteria == "need":
            # Could filter based on family income or other need indicators
            pass
        elif scholarship.criteria == "sibling":
            # Filter students who have siblings in the school
            queryset = queryset.filter(
                studentparentrelation__parent__studentparentrelation__student__isnull=False
            ).distinct()
        elif scholarship.criteria == "staff":
            # Filter students whose parents are staff members
            # This would need integration with staff management
            pass

        # Apply additional custom filters if provided
        if criteria_filters:
            queryset = queryset.filter(**criteria_filters)

        return list(queryset)

    @classmethod
    def generate_scholarship_report(cls, academic_year, term=None) -> Dict:
        """Generate comprehensive scholarship report."""

        # Get all scholarships for the academic year
        scholarships = Scholarship.objects.filter(
            academic_year=academic_year, is_active=True
        ).prefetch_related("applicable_categories")

        report_data = {
            "academic_year": academic_year,
            "term": term,
            "total_scholarships": scholarships.count(),
            "scholarship_details": [],
            "summary": {
                "total_beneficiaries": 0,
                "total_discount_amount": Decimal("0.00"),
                "by_criteria": {},
                "by_type": {},
            },
        }

        for scholarship in scholarships:
            # Calculate impact for each scholarship
            impact = cls.calculate_scholarship_impact(
                scholarship.id, academic_year, term
            )

            scholarship_data = {
                "name": scholarship.name,
                "criteria": scholarship.get_criteria_display(),
                "discount_type": scholarship.get_discount_type_display(),
                "discount_value": scholarship.discount_value,
                "max_recipients": scholarship.max_recipients,
                "current_recipients": scholarship.current_recipients,
                "total_discount": impact["total_discount_amount"],
                "average_discount": impact["average_discount_per_student"],
            }

            report_data["scholarship_details"].append(scholarship_data)

            # Update summary
            report_data["summary"]["total_beneficiaries"] += impact[
                "total_beneficiaries"
            ]
            report_data["summary"]["total_discount_amount"] += impact[
                "total_discount_amount"
            ]

            # Group by criteria
            criteria = scholarship.criteria
            if criteria not in report_data["summary"]["by_criteria"]:
                report_data["summary"]["by_criteria"][criteria] = {
                    "count": 0,
                    "beneficiaries": 0,
                    "total_discount": Decimal("0.00"),
                }

            report_data["summary"]["by_criteria"][criteria]["count"] += 1
            report_data["summary"]["by_criteria"][criteria]["beneficiaries"] += impact[
                "total_beneficiaries"
            ]
            report_data["summary"]["by_criteria"][criteria]["total_discount"] += impact[
                "total_discount_amount"
            ]

            # Group by discount type
            discount_type = scholarship.discount_type
            if discount_type not in report_data["summary"]["by_type"]:
                report_data["summary"]["by_type"][discount_type] = {
                    "count": 0,
                    "total_discount": Decimal("0.00"),
                }

            report_data["summary"]["by_type"][discount_type]["count"] += 1
            report_data["summary"]["by_type"][discount_type][
                "total_discount"
            ] += impact["total_discount_amount"]

        return report_data

    @classmethod
    def auto_assign_sibling_discount(cls, academic_year) -> Dict:
        """Automatically assign sibling discounts based on family relationships."""

        # Get or create sibling discount scholarship
        sibling_scholarship, created = Scholarship.objects.get_or_create(
            name="Sibling Discount",
            academic_year=academic_year,
            criteria="sibling",
            defaults={
                "description": "Automatic discount for students with siblings",
                "discount_type": "percentage",
                "discount_value": Decimal("10.00"),  # 10% discount
                "is_active": True,
            },
        )

        # Find families with multiple children
        from django.db.models import Count

        families_with_multiple_children = (
            StudentParentRelation.objects.filter(
                student__current_class__academic_year=academic_year
            )
            .values("parent")
            .annotate(child_count=Count("student"))
            .filter(child_count__gt=1)
        )

        assigned_count = 0

        for family in families_with_multiple_children:
            # Get all children in this family
            children = Student.objects.filter(
                studentparentrelation__parent_id=family["parent"],
                current_class__academic_year=academic_year,
                status="active",
            )

            # Assign scholarship to all children except the first (eldest)
            for child in children[1:]:  # Skip first child
                try:
                    cls.assign_scholarship(
                        student=child,
                        scholarship=sibling_scholarship,
                        remarks="Auto-assigned sibling discount",
                    )
                    assigned_count += 1
                except ValidationError:
                    # Skip if already assigned
                    continue

        return {
            "scholarship": sibling_scholarship,
            "families_processed": len(families_with_multiple_children),
            "students_assigned": assigned_count,
        }
