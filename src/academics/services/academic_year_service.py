"""
Academic Year Service

Business logic for academic year management including:
- Academic year creation and validation
- Term management within academic years
- Current academic year tracking
- Year transition workflows
"""

from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

from ..models import AcademicYear, Term
from django.contrib.auth import get_user_model

User = get_user_model()


class AcademicYearService:
    """Service for managing academic years and related operations"""

    @staticmethod
    def create_academic_year(
        name: str,
        start_date: datetime,
        end_date: datetime,
        user: User,
        is_current: bool = False,
    ) -> AcademicYear:
        """
        Create a new academic year with validation

        Args:
            name: Academic year name (e.g., "2023-2024")
            start_date: Academic year start date
            end_date: Academic year end date
            user: User creating the academic year
            is_current: Whether this should be the current academic year

        Returns:
            Created AcademicYear instance

        Raises:
            ValidationError: If validation fails
        """
        # Validate date range
        if start_date >= end_date:
            raise ValidationError("Start date must be before end date")

        # Check for overlapping academic years
        overlapping = AcademicYear.objects.filter(
            start_date__lte=end_date, end_date__gte=start_date
        )

        if overlapping.exists():
            raise ValidationError(
                f"Academic year dates overlap with existing academic year: {overlapping.first().name}"
            )

        with transaction.atomic():
            # If setting as current, unset other current academic years
            if is_current:
                AcademicYear.objects.filter(is_current=True).update(is_current=False)

            academic_year = AcademicYear.objects.create(
                name=name,
                start_date=start_date,
                end_date=end_date,
                is_current=is_current,
                created_by=user,
            )

            return academic_year

    @staticmethod
    def setup_academic_year_with_terms(
        name: str,
        start_date: datetime,
        end_date: datetime,
        num_terms: int,
        user: User,
        is_current: bool = False,
        term_names: Optional[List[str]] = None,
    ) -> AcademicYear:
        """
        Create academic year with automatically generated terms

        Args:
            name: Academic year name
            start_date: Academic year start date
            end_date: Academic year end date
            num_terms: Number of terms to create (2-4)
            user: User creating the academic year
            is_current: Whether this should be current
            term_names: Custom term names, defaults to "First Term", "Second Term", etc.

        Returns:
            Created AcademicYear with terms
        """
        if num_terms < 2 or num_terms > 4:
            raise ValidationError("Number of terms must be between 2 and 4")

        if term_names and len(term_names) != num_terms:
            raise ValidationError(f"Must provide exactly {num_terms} term names")

        # Default term names
        if not term_names:
            term_names = ["First Term", "Second Term", "Third Term", "Fourth Term"][
                :num_terms
            ]

        with transaction.atomic():
            # Create academic year
            academic_year = AcademicYearService.create_academic_year(
                name=name,
                start_date=start_date,
                end_date=end_date,
                user=user,
                is_current=is_current,
            )

            # Calculate term dates
            total_days = (end_date - start_date).days
            days_per_term = total_days // num_terms

            for i in range(num_terms):
                term_start = start_date + timedelta(days=i * days_per_term)

                if i == num_terms - 1:  # Last term gets remaining days
                    term_end = end_date
                else:
                    term_end = start_date + timedelta(days=(i + 1) * days_per_term - 1)

                Term.objects.create(
                    academic_year=academic_year,
                    name=term_names[i],
                    term_number=i + 1,
                    start_date=term_start,
                    end_date=term_end,
                    is_current=is_current
                    and i == 0,  # First term is current if academic year is current
                )

            return academic_year

    @staticmethod
    def get_current_academic_year() -> Optional[AcademicYear]:
        """Get the current academic year"""
        return AcademicYear.objects.filter(is_current=True).first()

    @staticmethod
    def set_current_academic_year(academic_year_id: int) -> AcademicYear:
        """
        Set an academic year as current

        Args:
            academic_year_id: ID of academic year to set as current

        Returns:
            Updated AcademicYear instance
        """
        with transaction.atomic():
            # Unset current academic year
            AcademicYear.objects.filter(is_current=True).update(is_current=False)

            # Set new current academic year
            academic_year = AcademicYear.objects.get(id=academic_year_id)
            academic_year.is_current = True
            academic_year.save()

            # Set first term as current if it exists
            first_term = academic_year.terms.filter(term_number=1).first()
            if first_term:
                Term.objects.filter(
                    academic_year=academic_year, is_current=True
                ).update(is_current=False)
                first_term.is_current = True
                first_term.save()

            return academic_year

    @staticmethod
    def get_academic_year_summary(academic_year_id: int) -> Dict[str, Any]:
        """
        Get comprehensive summary of an academic year

        Args:
            academic_year_id: ID of academic year

        Returns:
            Dictionary containing academic year statistics
        """
        try:
            academic_year = AcademicYear.objects.get(id=academic_year_id)
        except AcademicYear.DoesNotExist:
            raise ValidationError("Academic year not found")

        terms = academic_year.get_terms()
        current_term = academic_year.get_current_term()

        # Get statistics
        total_classes = academic_year.classes.filter(is_active=True).count()
        total_students = sum(
            cls.get_students_count()
            for cls in academic_year.classes.filter(is_active=True)
        )

        return {
            "academic_year": {
                "id": academic_year.id,
                "name": academic_year.name,
                "start_date": academic_year.start_date,
                "end_date": academic_year.end_date,
                "is_current": academic_year.is_current,
                "is_active": academic_year.is_active,
            },
            "terms": [
                {
                    "id": term.id,
                    "name": term.name,
                    "term_number": term.term_number,
                    "start_date": term.start_date,
                    "end_date": term.end_date,
                    "is_current": term.is_current,
                    "is_active": term.is_active,
                    "duration_days": term.get_duration_days(),
                }
                for term in terms
            ],
            "current_term": (
                {
                    "id": current_term.id,
                    "name": current_term.name,
                    "term_number": current_term.term_number,
                }
                if current_term
                else None
            ),
            "statistics": {
                "total_terms": terms.count(),
                "total_classes": total_classes,
                "total_students": total_students,
            },
        }

    @staticmethod
    def transition_to_next_term(academic_year_id: int) -> Optional[Term]:
        """
        Transition to the next term in the academic year

        Args:
            academic_year_id: ID of academic year

        Returns:
            New current term or None if no next term
        """
        try:
            academic_year = AcademicYear.objects.get(id=academic_year_id)
        except AcademicYear.DoesNotExist:
            raise ValidationError("Academic year not found")

        current_term = academic_year.terms.filter(is_current=True).first()

        if not current_term:
            # No current term, set first term as current
            first_term = academic_year.terms.filter(term_number=1).first()
            if first_term:
                first_term.is_current = True
                first_term.save()
                return first_term
            return None

        # Get next term
        next_term = academic_year.terms.filter(
            term_number=current_term.term_number + 1
        ).first()

        if next_term:
            with transaction.atomic():
                current_term.is_current = False
                current_term.save()

                next_term.is_current = True
                next_term.save()

                return next_term

        return None

    @staticmethod
    def get_active_academic_years() -> List[AcademicYear]:
        """Get all academic years that are currently active (within date range)"""
        today = timezone.now().date()
        return AcademicYear.objects.filter(
            start_date__lte=today, end_date__gte=today
        ).order_by("-start_date")

    @staticmethod
    def get_upcoming_academic_years() -> List[AcademicYear]:
        """Get academic years that will start in the future"""
        today = timezone.now().date()
        return AcademicYear.objects.filter(start_date__gt=today).order_by("start_date")

    @staticmethod
    def validate_academic_year_transition(
        current_year_id: int, new_year_id: int
    ) -> Dict[str, Any]:
        """
        Validate if transition from current to new academic year is valid

        Args:
            current_year_id: Current academic year ID
            new_year_id: New academic year ID

        Returns:
            Dictionary with validation results and warnings
        """
        try:
            current_year = AcademicYear.objects.get(id=current_year_id)
            new_year = AcademicYear.objects.get(id=new_year_id)
        except AcademicYear.DoesNotExist:
            return {"is_valid": False, "error": "One or both academic years not found"}

        warnings = []
        errors = []

        # Check date continuity
        if new_year.start_date < current_year.end_date:
            if (current_year.end_date - new_year.start_date).days > 30:
                errors.append(
                    "New academic year starts significantly before current year ends"
                )
            else:
                warnings.append("New academic year overlaps with current year")

        # Check for gap
        gap_days = (new_year.start_date - current_year.end_date).days
        if gap_days > 90:
            warnings.append(f"Large gap ({gap_days} days) between academic years")

        # Check if new year has required structure
        if not new_year.terms.exists():
            warnings.append("New academic year has no terms defined")

        return {
            "is_valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "gap_days": gap_days,
            "current_year": {
                "name": current_year.name,
                "end_date": current_year.end_date,
            },
            "new_year": {"name": new_year.name, "start_date": new_year.start_date},
        }

    @staticmethod
    def archive_academic_year(academic_year_id: int, user: User) -> AcademicYear:
        """
        Archive an academic year (soft delete)

        Args:
            academic_year_id: ID of academic year to archive
            user: User performing the archival

        Returns:
            Archived AcademicYear instance
        """
        try:
            academic_year = AcademicYear.objects.get(id=academic_year_id)
        except AcademicYear.DoesNotExist:
            raise ValidationError("Academic year not found")

        if academic_year.is_current:
            raise ValidationError("Cannot archive the current academic year")

        # Check if academic year has active data
        active_classes = academic_year.classes.filter(is_active=True).count()
        if active_classes > 0:
            raise ValidationError(
                f"Cannot archive academic year with {active_classes} active classes"
            )

        # Archive the academic year (implementation depends on your archival strategy)
        # For now, we'll just mark it as inactive
        with transaction.atomic():
            academic_year.is_current = False
            academic_year.save()

            # Also mark all terms as non-current
            academic_year.terms.update(is_current=False)

        return academic_year
