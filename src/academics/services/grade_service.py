"""
Grade Service

Business logic for grade management including:
- Grade creation within sections
- Age requirement management
- Grade progression logic
- Class assignment within grades
"""

from typing import Any, Dict, List, Optional

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Avg, Count, Q

from ..models import Class, Department, Grade, Section

User = get_user_model()


class GradeService:
    """Service for managing academic grades"""

    @staticmethod
    def create_grade(
        name: str,
        section_id: int,
        description: str = "",
        department_id: Optional[int] = None,
        order_sequence: Optional[int] = None,
        minimum_age: Optional[int] = None,
        maximum_age: Optional[int] = None,
    ) -> Grade:
        """
        Create a new grade within a section

        Args:
            name: Grade name (e.g., "Grade 1", "Grade 2")
            section_id: ID of parent section
            description: Optional description
            department_id: Optional department ID
            order_sequence: Display order within section
            minimum_age: Minimum age for admission
            maximum_age: Maximum age for admission

        Returns:
            Created Grade instance

        Raises:
            ValidationError: If validation fails
        """
        try:
            section = Section.objects.get(id=section_id)
        except Section.DoesNotExist:
            raise ValidationError("Section not found")

        if not section.is_active:
            raise ValidationError("Cannot create grade in inactive section")

        # Validate name uniqueness within section
        if Grade.objects.filter(section=section, name__iexact=name).exists():
            raise ValidationError(
                f"Grade '{name}' already exists in section '{section.name}'"
            )

        # Validate age requirements
        if minimum_age and maximum_age and minimum_age >= maximum_age:
            raise ValidationError("Minimum age must be less than maximum age")

        # Get department if provided
        department = None
        if department_id:
            try:
                department = Department.objects.get(id=department_id)
            except Department.DoesNotExist:
                raise ValidationError("Department not found")

        # Auto-assign order sequence if not provided
        if order_sequence is None:
            max_order = (
                Grade.objects.filter(section=section).aggregate(
                    max_order=models.Max("order_sequence")
                )["max_order"]
                or 0
            )
            order_sequence = max_order + 1

        grade = Grade.objects.create(
            name=name,
            section=section,
            description=description,
            department=department,
            order_sequence=order_sequence,
            minimum_age=minimum_age,
            maximum_age=maximum_age,
        )

        return grade

    @staticmethod
    def update_grade(
        grade_id: int,
        name: Optional[str] = None,
        description: Optional[str] = None,
        department_id: Optional[int] = None,
        order_sequence: Optional[int] = None,
        minimum_age: Optional[int] = None,
        maximum_age: Optional[int] = None,
        is_active: Optional[bool] = None,
    ) -> Grade:
        """
        Update an existing grade

        Args:
            grade_id: ID of grade to update
            name: New name (optional)
            description: New description (optional)
            department_id: New department ID (optional)
            order_sequence: New order sequence (optional)
            minimum_age: New minimum age (optional)
            maximum_age: New maximum age (optional)
            is_active: New active status (optional)

        Returns:
            Updated Grade instance
        """
        try:
            grade = Grade.objects.get(id=grade_id)
        except Grade.DoesNotExist:
            raise ValidationError("Grade not found")

        # Validate name uniqueness if changing name
        if name and name != grade.name:
            if (
                Grade.objects.filter(section=grade.section, name__iexact=name)
                .exclude(id=grade_id)
                .exists()
            ):
                raise ValidationError(
                    f"Grade '{name}' already exists in section '{grade.section.name}'"
                )
            grade.name = name

        if description is not None:
            grade.description = description

        if department_id is not None:
            if department_id:
                try:
                    department = Department.objects.get(id=department_id)
                    grade.department = department
                except Department.DoesNotExist:
                    raise ValidationError("Department not found")
            else:
                grade.department = None

        if order_sequence is not None:
            grade.order_sequence = order_sequence

        if minimum_age is not None:
            grade.minimum_age = minimum_age

        if maximum_age is not None:
            grade.maximum_age = maximum_age

        # Validate age requirements after updates
        if (
            grade.minimum_age
            and grade.maximum_age
            and grade.minimum_age >= grade.maximum_age
        ):
            raise ValidationError("Minimum age must be less than maximum age")

        if is_active is not None:
            # Check if can be deactivated
            if not is_active and grade.is_active:
                GradeService._validate_grade_deactivation(grade)
            grade.is_active = is_active

        grade.save()
        return grade

    @staticmethod
    def _validate_grade_deactivation(grade: Grade) -> None:
        """
        Validate if a grade can be deactivated

        Args:
            grade: Grade to validate

        Raises:
            ValidationError: If grade cannot be deactivated
        """
        from .academic_year_service import AcademicYearService

        current_year = AcademicYearService.get_current_academic_year()

        if current_year:
            # Check for active classes in current academic year
            active_classes = grade.classes.filter(
                academic_year=current_year, is_active=True
            ).count()

            if active_classes > 0:
                raise ValidationError(
                    f"Cannot deactivate grade with {active_classes} active classes in current academic year"
                )

            # Check for enrolled students
            total_students = sum(
                cls.get_students_count()
                for cls in grade.classes.filter(academic_year=current_year)
            )

            if total_students > 0:
                raise ValidationError(
                    f"Cannot deactivate grade with {total_students} enrolled students"
                )

    @staticmethod
    def get_grade_details(
        grade_id: int, academic_year_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Get detailed information about a grade

        Args:
            grade_id: ID of grade
            academic_year_id: Optional academic year for filtering classes

        Returns:
            Dictionary containing grade details and statistics
        """
        try:
            grade = Grade.objects.get(id=grade_id)
        except Grade.DoesNotExist:
            raise ValidationError("Grade not found")

        from .academic_year_service import AcademicYearService

        if academic_year_id:
            try:
                from ..models import AcademicYear

                academic_year = AcademicYear.objects.get(id=academic_year_id)
            except AcademicYear.DoesNotExist:
                raise ValidationError("Academic year not found")
        else:
            academic_year = AcademicYearService.get_current_academic_year()

        # Get classes for this grade
        classes_qs = (
            grade.get_classes(academic_year) if academic_year else grade.get_classes()
        )

        classes_data = []
        total_students = 0
        total_capacity = 0

        for cls in classes_qs:
            student_count = cls.get_students_count()
            total_students += student_count
            total_capacity += cls.capacity

            classes_data.append(
                {
                    "id": cls.id,
                    "name": cls.name,
                    "display_name": cls.display_name,
                    "room_number": cls.room_number,
                    "capacity": cls.capacity,
                    "students_count": student_count,
                    "available_capacity": cls.get_available_capacity(),
                    "utilization_rate": (
                        (student_count / cls.capacity * 100) if cls.capacity > 0 else 0
                    ),
                    "is_full": cls.is_full(),
                    "class_teacher": (
                        {
                            "id": cls.class_teacher.id,
                            "name": f"{cls.class_teacher.user.first_name} {cls.class_teacher.user.last_name}",
                            "employee_id": cls.class_teacher.employee_id,
                        }
                        if cls.class_teacher
                        else None
                    ),
                }
            )

        return {
            "grade": {
                "id": grade.id,
                "name": grade.name,
                "display_name": grade.display_name,
                "description": grade.description,
                "order_sequence": grade.order_sequence,
                "minimum_age": grade.minimum_age,
                "maximum_age": grade.maximum_age,
                "is_active": grade.is_active,
                "section": {"id": grade.section.id, "name": grade.section.name},
                "department": (
                    {"id": grade.department.id, "name": grade.department.name}
                    if grade.department
                    else None
                ),
            },
            "classes": classes_data,
            "statistics": {
                "total_classes": len(classes_data),
                "total_students": total_students,
                "total_capacity": total_capacity,
                "available_capacity": total_capacity - total_students,
                "average_class_size": (
                    total_students / len(classes_data) if classes_data else 0
                ),
                "utilization_rate": (
                    (total_students / total_capacity * 100) if total_capacity > 0 else 0
                ),
                "academic_year": academic_year.name if academic_year else None,
            },
        }

    @staticmethod
    def get_grade_progression_analysis(grade_id: int) -> Dict[str, Any]:
        """
        Analyze grade progression patterns and requirements

        Args:
            grade_id: ID of grade to analyze

        Returns:
            Dictionary containing progression analysis
        """
        try:
            grade = Grade.objects.get(id=grade_id)
        except Grade.DoesNotExist:
            raise ValidationError("Grade not found")

        section = grade.section

        # Find previous and next grades in sequence
        previous_grade = (
            Grade.objects.filter(
                section=section, order_sequence__lt=grade.order_sequence, is_active=True
            )
            .order_by("-order_sequence")
            .first()
        )

        next_grade = (
            Grade.objects.filter(
                section=section, order_sequence__gt=grade.order_sequence, is_active=True
            )
            .order_by("order_sequence")
            .first()
        )

        # Get current academic year stats
        from .academic_year_service import AcademicYearService

        current_year = AcademicYearService.get_current_academic_year()

        current_stats = {
            "total_students": 0,
            "total_classes": 0,
            "average_class_size": 0,
        }

        if current_year:
            classes = grade.get_classes(current_year)
            current_stats["total_classes"] = classes.count()
            current_stats["total_students"] = sum(
                cls.get_students_count() for cls in classes
            )
            current_stats["average_class_size"] = (
                current_stats["total_students"] / current_stats["total_classes"]
                if current_stats["total_classes"] > 0
                else 0
            )

        # Age progression analysis
        age_analysis = {}
        if grade.minimum_age and grade.maximum_age:
            age_analysis = {
                "current_age_range": f"{grade.minimum_age}-{grade.maximum_age} years",
                "previous_grade_compatibility": None,
                "next_grade_compatibility": None,
            }

            if previous_grade and previous_grade.maximum_age:
                age_gap = grade.minimum_age - previous_grade.maximum_age
                age_analysis["previous_grade_compatibility"] = {
                    "has_gap": age_gap > 1,
                    "gap_years": age_gap,
                    "status": (
                        "Normal progression" if age_gap <= 1 else f"{age_gap} year gap"
                    ),
                }

            if next_grade and next_grade.minimum_age:
                age_gap = next_grade.minimum_age - grade.maximum_age
                age_analysis["next_grade_compatibility"] = {
                    "has_gap": age_gap > 1,
                    "gap_years": age_gap,
                    "status": (
                        "Normal progression" if age_gap <= 1 else f"{age_gap} year gap"
                    ),
                }

        return {
            "grade": {
                "id": grade.id,
                "name": grade.name,
                "order_sequence": grade.order_sequence,
            },
            "progression": {
                "previous_grade": (
                    {
                        "id": previous_grade.id,
                        "name": previous_grade.name,
                        "order_sequence": previous_grade.order_sequence,
                    }
                    if previous_grade
                    else None
                ),
                "next_grade": (
                    {
                        "id": next_grade.id,
                        "name": next_grade.name,
                        "order_sequence": next_grade.order_sequence,
                    }
                    if next_grade
                    else None
                ),
            },
            "current_statistics": current_stats,
            "age_analysis": age_analysis,
            "recommendations": GradeService._generate_grade_recommendations(
                grade, current_stats
            ),
        }

    @staticmethod
    def _generate_grade_recommendations(
        grade: Grade, current_stats: Dict[str, Any]
    ) -> List[str]:
        """Generate recommendations for grade management"""
        recommendations = []

        # Class size recommendations
        if current_stats["average_class_size"] > 35:
            recommendations.append(
                "Consider adding more classes - average class size is high"
            )
        elif (
            current_stats["average_class_size"] < 15
            and current_stats["total_classes"] > 1
        ):
            recommendations.append(
                "Consider consolidating classes - average class size is low"
            )

        # Age requirement recommendations
        if not grade.minimum_age or not grade.maximum_age:
            recommendations.append(
                "Consider setting age requirements for better admission management"
            )

        # Department assignment
        if not grade.department:
            recommendations.append(
                "Consider assigning a department for better academic management"
            )

        return recommendations

    @staticmethod
    def reorder_grades_in_section(
        section_id: int, grade_orders: List[Dict[str, int]]
    ) -> List[Grade]:
        """
        Reorder grades within a section

        Args:
            section_id: ID of section
            grade_orders: List of dicts with 'id' and 'order_sequence'

        Returns:
            List of updated Grade instances
        """
        try:
            section = Section.objects.get(id=section_id)
        except Section.DoesNotExist:
            raise ValidationError("Section not found")

        updated_grades = []

        with transaction.atomic():
            for order_data in grade_orders:
                try:
                    grade = Grade.objects.get(id=order_data["id"], section=section)
                    grade.order_sequence = order_data["order_sequence"]
                    grade.save()
                    updated_grades.append(grade)
                except Grade.DoesNotExist:
                    raise ValidationError(
                        f"Grade with ID {order_data['id']} not found in section"
                    )

        return updated_grades

    @staticmethod
    def get_grades_by_section(
        section_id: int, include_inactive: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Get all grades in a section with basic information

        Args:
            section_id: ID of section
            include_inactive: Whether to include inactive grades

        Returns:
            List of grade dictionaries
        """
        try:
            section = Section.objects.get(id=section_id)
        except Section.DoesNotExist:
            raise ValidationError("Section not found")

        grades_qs = section.grades.all()
        if not include_inactive:
            grades_qs = grades_qs.filter(is_active=True)

        grades_qs = grades_qs.order_by("order_sequence")

        from .academic_year_service import AcademicYearService

        current_year = AcademicYearService.get_current_academic_year()

        grades_data = []
        for grade in grades_qs:
            classes_count = 0
            students_count = 0

            if current_year:
                classes = grade.get_classes(current_year)
                classes_count = classes.count()
                students_count = sum(cls.get_students_count() for cls in classes)

            grades_data.append(
                {
                    "id": grade.id,
                    "name": grade.name,
                    "description": grade.description,
                    "order_sequence": grade.order_sequence,
                    "minimum_age": grade.minimum_age,
                    "maximum_age": grade.maximum_age,
                    "is_active": grade.is_active,
                    "classes_count": classes_count,
                    "students_count": students_count,
                    "department": (
                        {"id": grade.department.id, "name": grade.department.name}
                        if grade.department
                        else None
                    ),
                }
            )

        return grades_data

    @staticmethod
    def validate_student_age_for_grade(
        grade_id: int, student_age: int
    ) -> Dict[str, Any]:
        """
        Validate if a student's age is appropriate for a grade

        Args:
            grade_id: ID of grade
            student_age: Student's age in years

        Returns:
            Dictionary containing validation results
        """
        try:
            grade = Grade.objects.get(id=grade_id)
        except Grade.DoesNotExist:
            raise ValidationError("Grade not found")

        is_valid = True
        warnings = []
        errors = []

        if grade.minimum_age and student_age < grade.minimum_age:
            is_valid = False
            errors.append(
                f"Student age ({student_age}) is below minimum age ({grade.minimum_age}) for {grade.name}"
            )
        elif grade.minimum_age and student_age == grade.minimum_age:
            warnings.append(f"Student is at minimum age for {grade.name}")

        if grade.maximum_age and student_age > grade.maximum_age:
            is_valid = False
            errors.append(
                f"Student age ({student_age}) exceeds maximum age ({grade.maximum_age}) for {grade.name}"
            )
        elif grade.maximum_age and student_age == grade.maximum_age:
            warnings.append(f"Student is at maximum age for {grade.name}")

        if not grade.minimum_age and not grade.maximum_age:
            warnings.append("No age requirements set for this grade")

        return {
            "is_valid": is_valid,
            "student_age": student_age,
            "grade": {
                "id": grade.id,
                "name": grade.name,
                "minimum_age": grade.minimum_age,
                "maximum_age": grade.maximum_age,
            },
            "errors": errors,
            "warnings": warnings,
        }
