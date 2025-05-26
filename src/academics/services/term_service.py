"""
Term Service

Business logic for term management including:
- Term creation and validation within academic years
- Current term tracking and transitions
- Term-based data filtering and analytics
- Term scheduling and date management
"""

from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db.models import Q, Count, Sum
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from ..models import Term, AcademicYear
from django.contrib.auth import get_user_model

User = get_user_model()


class TermService:
    """Service for managing academic terms"""

    @staticmethod
    def create_term(
        academic_year_id: int,
        name: str,
        term_number: int,
        start_date: datetime,
        end_date: datetime,
        is_current: bool = False,
    ) -> Term:
        """
        Create a new term within an academic year

        Args:
            academic_year_id: ID of parent academic year
            name: Term name (e.g., "First Term", "Fall Semester")
            term_number: Term sequence number (1-4)
            start_date: Term start date
            end_date: Term end date
            is_current: Whether this should be the current term

        Returns:
            Created Term instance

        Raises:
            ValidationError: If validation fails
        """
        try:
            academic_year = AcademicYear.objects.get(id=academic_year_id)
        except AcademicYear.DoesNotExist:
            raise ValidationError("Academic year not found")

        # Validate term number
        if term_number < 1 or term_number > 4:
            raise ValidationError("Term number must be between 1 and 4")

        # Check for duplicate term number in same academic year
        if Term.objects.filter(
            academic_year=academic_year, term_number=term_number
        ).exists():
            raise ValidationError(
                f"Term {term_number} already exists in {academic_year.name}"
            )

        # Validate date range
        if start_date >= end_date:
            raise ValidationError("Start date must be before end date")

        # Ensure term dates are within academic year
        if start_date < academic_year.start_date or end_date > academic_year.end_date:
            raise ValidationError("Term dates must be within academic year dates")

        # Check for overlapping terms in the same academic year
        overlapping = Term.objects.filter(
            academic_year=academic_year,
            start_date__lte=end_date,
            end_date__gte=start_date,
        )

        if overlapping.exists():
            raise ValidationError(
                f"Term dates overlap with existing term: {overlapping.first().name}"
            )

        with transaction.atomic():
            # If setting as current, unset other current terms in same academic year
            if is_current:
                Term.objects.filter(
                    academic_year=academic_year, is_current=True
                ).update(is_current=False)

            term = Term.objects.create(
                academic_year=academic_year,
                name=name,
                term_number=term_number,
                start_date=start_date,
                end_date=end_date,
                is_current=is_current,
            )

            return term

    @staticmethod
    def update_term(
        term_id: int,
        name: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        is_current: Optional[bool] = None,
    ) -> Term:
        """
        Update an existing term

        Args:
            term_id: ID of term to update
            name: New name (optional)
            start_date: New start date (optional)
            end_date: New end date (optional)
            is_current: New current status (optional)

        Returns:
            Updated Term instance
        """
        try:
            term = Term.objects.get(id=term_id)
        except Term.DoesNotExist:
            raise ValidationError("Term not found")

        # Store original values for validation
        original_start = term.start_date
        original_end = term.end_date

        if name is not None:
            term.name = name

        if start_date is not None:
            term.start_date = start_date

        if end_date is not None:
            term.end_date = end_date

        # Validate updated date range
        if term.start_date >= term.end_date:
            raise ValidationError("Start date must be before end date")

        # Ensure term dates are within academic year
        if (
            term.start_date < term.academic_year.start_date
            or term.end_date > term.academic_year.end_date
        ):
            raise ValidationError("Term dates must be within academic year dates")

        # Check for overlapping terms if dates changed
        if start_date is not None or end_date is not None:
            overlapping = Term.objects.filter(
                academic_year=term.academic_year,
                start_date__lte=term.end_date,
                end_date__gte=term.start_date,
            ).exclude(id=term_id)

            if overlapping.exists():
                raise ValidationError(
                    f"Updated term dates overlap with existing term: {overlapping.first().name}"
                )

        # Validate if term has active data and dates are being changed significantly
        if start_date is not None or end_date is not None:
            TermService._validate_term_date_changes(term, original_start, original_end)

        with transaction.atomic():
            if is_current is not None and is_current:
                # Unset other current terms in same academic year
                Term.objects.filter(
                    academic_year=term.academic_year, is_current=True
                ).exclude(id=term_id).update(is_current=False)
                term.is_current = True
            elif is_current is not None:
                term.is_current = is_current

            term.save()

            return term

    @staticmethod
    def _validate_term_date_changes(
        term: Term, original_start: datetime, original_end: datetime
    ) -> None:
        """
        Validate if term date changes are allowed based on existing data

        Args:
            term: Term being updated
            original_start: Original start date
            original_end: Original end date

        Raises:
            ValidationError: If date changes would affect existing data
        """
        warnings = []

        # Check for attendance records
        try:
            from attendance.models import Attendance

            attendance_count = Attendance.objects.filter(term=term).count()
            if attendance_count > 0:
                warnings.append(
                    f"{attendance_count} attendance records exist for this term"
                )
        except ImportError:
            pass

        # Check for exam schedules
        try:
            from exams.models import ExamSchedule

            exam_count = ExamSchedule.objects.filter(exam__term=term).count()
            if exam_count > 0:
                warnings.append(f"{exam_count} exam schedules exist for this term")
        except ImportError:
            pass

        # Check for fee structures
        try:
            from finance.models import FeeStructure

            fee_count = FeeStructure.objects.filter(term=term).count()
            if fee_count > 0:
                warnings.append(f"{fee_count} fee structures exist for this term")
        except ImportError:
            pass

        if warnings:
            # For now, just log warnings. In a real implementation, you might
            # want to prevent changes or require admin confirmation
            pass

    @staticmethod
    def get_current_term(academic_year_id: Optional[int] = None) -> Optional[Term]:
        """
        Get the current term

        Args:
            academic_year_id: Optional academic year ID to filter by

        Returns:
            Current Term instance or None
        """
        terms_qs = Term.objects.filter(is_current=True)

        if academic_year_id:
            terms_qs = terms_qs.filter(academic_year_id=academic_year_id)

        return terms_qs.first()

    @staticmethod
    def set_current_term(term_id: int) -> Term:
        """
        Set a term as current

        Args:
            term_id: ID of term to set as current

        Returns:
            Updated Term instance
        """
        try:
            term = Term.objects.get(id=term_id)
        except Term.DoesNotExist:
            raise ValidationError("Term not found")

        with transaction.atomic():
            # Unset current term in same academic year
            Term.objects.filter(
                academic_year=term.academic_year, is_current=True
            ).update(is_current=False)

            # Set new current term
            term.is_current = True
            term.save()

            return term

    @staticmethod
    def get_term_summary(term_id: int) -> Dict[str, Any]:
        """
        Get comprehensive summary of a term

        Args:
            term_id: ID of term

        Returns:
            Dictionary containing term statistics and information
        """
        try:
            term = Term.objects.get(id=term_id)
        except Term.DoesNotExist:
            raise ValidationError("Term not found")

        # Basic term information
        term_info = {
            "id": term.id,
            "name": term.name,
            "term_number": term.term_number,
            "start_date": term.start_date,
            "end_date": term.end_date,
            "is_current": term.is_current,
            "is_active": term.is_active,
            "duration_days": term.get_duration_days(),
            "academic_year": {
                "id": term.academic_year.id,
                "name": term.academic_year.name,
            },
        }

        # Get classes for this term
        classes_count = 0
        students_count = 0

        try:
            from ..models import Class

            classes = Class.objects.filter(
                academic_year=term.academic_year, is_active=True
            )
            classes_count = classes.count()
            students_count = sum(cls.get_students_count() for cls in classes)
        except Exception:
            pass

        # Get statistics from various modules
        statistics = {
            "classes_count": classes_count,
            "students_count": students_count,
            "attendance_records": 0,
            "exam_schedules": 0,
            "assignments": 0,
            "fee_invoices": 0,
        }

        # Attendance statistics
        try:
            from attendance.models import Attendance

            statistics["attendance_records"] = Attendance.objects.filter(
                term=term
            ).count()
        except ImportError:
            pass

        # Exam statistics
        try:
            from exams.models import ExamSchedule

            statistics["exam_schedules"] = ExamSchedule.objects.filter(
                exam__term=term
            ).count()
        except ImportError:
            pass

        # Assignment statistics
        try:
            from assignments.models import Assignment

            statistics["assignments"] = Assignment.objects.filter(term=term).count()
        except ImportError:
            pass

        # Finance statistics
        try:
            from finance.models import Invoice

            statistics["fee_invoices"] = Invoice.objects.filter(term=term).count()
        except ImportError:
            pass

        return {
            "term": term_info,
            "statistics": statistics,
            "progress": TermService._calculate_term_progress(term),
        }

    @staticmethod
    def _calculate_term_progress(term: Term) -> Dict[str, Any]:
        """Calculate term progress based on current date"""
        today = timezone.now().date()

        if today < term.start_date:
            return {
                "status": "Not Started",
                "progress_percentage": 0,
                "days_until_start": (term.start_date - today).days,
                "days_remaining": term.get_duration_days(),
            }
        elif today > term.end_date:
            return {
                "status": "Completed",
                "progress_percentage": 100,
                "days_since_end": (today - term.end_date).days,
                "days_remaining": 0,
            }
        else:
            total_days = term.get_duration_days()
            elapsed_days = (today - term.start_date).days
            remaining_days = (term.end_date - today).days
            progress_percentage = (
                (elapsed_days / total_days * 100) if total_days > 0 else 0
            )

            return {
                "status": "In Progress",
                "progress_percentage": round(progress_percentage, 1),
                "elapsed_days": elapsed_days,
                "days_remaining": remaining_days,
            }

    @staticmethod
    def get_terms_by_academic_year(academic_year_id: int) -> List[Dict[str, Any]]:
        """
        Get all terms for an academic year

        Args:
            academic_year_id: ID of academic year

        Returns:
            List of term dictionaries with basic information
        """
        try:
            academic_year = AcademicYear.objects.get(id=academic_year_id)
        except AcademicYear.DoesNotExist:
            raise ValidationError("Academic year not found")

        terms = Term.objects.filter(academic_year=academic_year).order_by("term_number")

        terms_data = []
        for term in terms:
            progress = TermService._calculate_term_progress(term)

            terms_data.append(
                {
                    "id": term.id,
                    "name": term.name,
                    "term_number": term.term_number,
                    "start_date": term.start_date,
                    "end_date": term.end_date,
                    "is_current": term.is_current,
                    "duration_days": term.get_duration_days(),
                    "status": progress["status"],
                    "progress_percentage": progress["progress_percentage"],
                }
            )

        return terms_data

    @staticmethod
    def transition_to_next_term(current_term_id: int) -> Optional[Term]:
        """
        Transition from current term to next term

        Args:
            current_term_id: ID of current term

        Returns:
            New current term or None if no next term
        """
        try:
            current_term = Term.objects.get(id=current_term_id)
        except Term.DoesNotExist:
            raise ValidationError("Current term not found")

        if not current_term.is_current:
            raise ValidationError("Specified term is not the current term")

        # Find next term in sequence
        next_term = Term.objects.filter(
            academic_year=current_term.academic_year,
            term_number=current_term.term_number + 1,
        ).first()

        if next_term:
            with transaction.atomic():
                current_term.is_current = False
                current_term.save()

                next_term.is_current = True
                next_term.save()

                # Log the transition
                try:
                    from core.models import AuditLog

                    AuditLog.objects.create(
                        action="Term Transition",
                        entity_type="Term",
                        entity_id=next_term.id,
                        data_before={"current_term": current_term.name},
                        data_after={"current_term": next_term.name},
                    )
                except ImportError:
                    pass

                return next_term

        return None

    @staticmethod
    def auto_generate_terms(
        academic_year_id: int, num_terms: int, term_names: Optional[List[str]] = None
    ) -> List[Term]:
        """
        Automatically generate terms for an academic year

        Args:
            academic_year_id: ID of academic year
            num_terms: Number of terms to create (2-4)
            term_names: Optional custom term names

        Returns:
            List of created Term instances
        """
        try:
            academic_year = AcademicYear.objects.get(id=academic_year_id)
        except AcademicYear.DoesNotExist:
            raise ValidationError("Academic year not found")

        if num_terms < 2 or num_terms > 4:
            raise ValidationError("Number of terms must be between 2 and 4")

        # Check if terms already exist
        existing_terms = Term.objects.filter(academic_year=academic_year).count()
        if existing_terms > 0:
            raise ValidationError(f"Academic year already has {existing_terms} terms")

        # Default term names
        if not term_names:
            term_names = ["First Term", "Second Term", "Third Term", "Fourth Term"][
                :num_terms
            ]
        elif len(term_names) != num_terms:
            raise ValidationError(f"Must provide exactly {num_terms} term names")

        # Calculate term dates
        total_days = (academic_year.end_date - academic_year.start_date).days
        days_per_term = total_days // num_terms

        created_terms = []

        with transaction.atomic():
            for i in range(num_terms):
                term_start = academic_year.start_date + timedelta(
                    days=i * days_per_term
                )

                if i == num_terms - 1:  # Last term gets remaining days
                    term_end = academic_year.end_date
                else:
                    term_end = academic_year.start_date + timedelta(
                        days=(i + 1) * days_per_term - 1
                    )

                term = Term.objects.create(
                    academic_year=academic_year,
                    name=term_names[i],
                    term_number=i + 1,
                    start_date=term_start,
                    end_date=term_end,
                    is_current=i == 0,  # First term is current by default
                )

                created_terms.append(term)

        return created_terms

    @staticmethod
    def get_term_calendar(academic_year_id: int) -> Dict[str, Any]:
        """
        Get calendar view of all terms in an academic year

        Args:
            academic_year_id: ID of academic year

        Returns:
            Dictionary containing calendar information
        """
        try:
            academic_year = AcademicYear.objects.get(id=academic_year_id)
        except AcademicYear.DoesNotExist:
            raise ValidationError("Academic year not found")

        terms = Term.objects.filter(academic_year=academic_year).order_by("term_number")

        calendar_data = {
            "academic_year": {
                "id": academic_year.id,
                "name": academic_year.name,
                "start_date": academic_year.start_date,
                "end_date": academic_year.end_date,
            },
            "terms": [],
            "gaps": [],
            "summary": {
                "total_terms": terms.count(),
                "total_academic_days": 0,
                "total_gap_days": 0,
            },
        }

        previous_end = academic_year.start_date

        for term in terms:
            # Check for gap between terms
            if term.start_date > previous_end:
                gap_days = (term.start_date - previous_end).days
                calendar_data["gaps"].append(
                    {
                        "start_date": previous_end,
                        "end_date": term.start_date,
                        "duration_days": gap_days,
                        "description": f"Break between {previous_end.strftime('%b %d')} and {term.start_date.strftime('%b %d')}",
                    }
                )
                calendar_data["summary"]["total_gap_days"] += gap_days

            term_data = {
                "id": term.id,
                "name": term.name,
                "term_number": term.term_number,
                "start_date": term.start_date,
                "end_date": term.end_date,
                "duration_days": term.get_duration_days(),
                "is_current": term.is_current,
                "progress": TermService._calculate_term_progress(term),
            }

            calendar_data["terms"].append(term_data)
            calendar_data["summary"]["total_academic_days"] += term.get_duration_days()
            previous_end = term.end_date + timedelta(days=1)

        return calendar_data

    @staticmethod
    def validate_term_structure(academic_year_id: int) -> Dict[str, Any]:
        """
        Validate the term structure for an academic year

        Args:
            academic_year_id: ID of academic year

        Returns:
            Dictionary containing validation results
        """
        try:
            academic_year = AcademicYear.objects.get(id=academic_year_id)
        except AcademicYear.DoesNotExist:
            raise ValidationError("Academic year not found")

        terms = Term.objects.filter(academic_year=academic_year).order_by("term_number")

        validation_results = {
            "is_valid": True,
            "errors": [],
            "warnings": [],
            "recommendations": [],
        }

        # Check if terms exist
        if not terms.exists():
            validation_results["errors"].append(
                "No terms defined for this academic year"
            )
            validation_results["is_valid"] = False
            return validation_results

        # Check term sequence
        expected_numbers = list(range(1, terms.count() + 1))
        actual_numbers = list(terms.values_list("term_number", flat=True))

        if actual_numbers != expected_numbers:
            validation_results["errors"].append("Term numbers are not sequential")
            validation_results["is_valid"] = False

        # Check for gaps and overlaps
        previous_term = None
        for term in terms:
            if previous_term:
                gap_days = (term.start_date - previous_term.end_date).days - 1

                if gap_days < 0:
                    validation_results["errors"].append(
                        f"Terms overlap: {previous_term.name} and {term.name}"
                    )
                    validation_results["is_valid"] = False
                elif gap_days > 30:
                    validation_results["warnings"].append(
                        f"Large gap ({gap_days} days) between {previous_term.name} and {term.name}"
                    )

            previous_term = term

        # Check current term status
        current_terms = terms.filter(is_current=True)
        if current_terms.count() == 0:
            validation_results["warnings"].append("No current term set")
        elif current_terms.count() > 1:
            validation_results["errors"].append("Multiple terms marked as current")
            validation_results["is_valid"] = False

        # Check term durations
        total_academic_days = sum(term.get_duration_days() for term in terms)
        academic_year_days = (academic_year.end_date - academic_year.start_date).days

        if total_academic_days < academic_year_days * 0.8:
            validation_results["recommendations"].append(
                "Terms cover less than 80% of academic year - consider extending term dates"
            )

        return validation_results
