"""
Section Service

Business logic for academic section management including:
- Section creation and organization
- Grade assignment to sections
- Section analytics and reporting
- Section hierarchy management
"""

from django.db import transaction, models
from django.core.exceptions import ValidationError
from django.db.models import Count, Q
from typing import List, Dict, Any, Optional

from ..models import Section, Grade, Class, Department
from django.contrib.auth import get_user_model

User = get_user_model()


class SectionService:
    """Service for managing academic sections"""

    @staticmethod
    def create_section(
        name: str,
        description: str = "",
        department: Optional[Department] = None,
        order_sequence: int = 1,
    ) -> Section:
        """
        Create a new academic section

        Args:
            name: Section name (e.g., "Lower Primary", "Upper Primary")
            description: Optional description
            department: Associated department (optional)
            order_sequence: Display order sequence

        Returns:
            Created Section instance

        Raises:
            ValidationError: If validation fails
        """
        # Validate name uniqueness
        if Section.objects.filter(name__iexact=name).exists():
            raise ValidationError(f"Section with name '{name}' already exists")

        # Auto-assign order sequence if not provided
        if order_sequence == 1:
            max_order = (
                Section.objects.aggregate(max_order=models.Max("order_sequence"))[
                    "max_order"
                ]
                or 0
            )
            order_sequence = max_order + 1

        section = Section.objects.create(
            name=name,
            description=description,
            department=department,
            order_sequence=order_sequence,
        )

        return section

    @staticmethod
    def update_section(
        section_id: int,
        name: Optional[str] = None,
        description: Optional[str] = None,
        department: Optional[Department] = None,
        order_sequence: Optional[int] = None,
        is_active: Optional[bool] = None,
    ) -> Section:
        """
        Update an existing section

        Args:
            section_id: ID of section to update
            name: New name (optional)
            description: New description (optional)
            department: New department (optional)
            order_sequence: New order sequence (optional)
            is_active: New active status (optional)

        Returns:
            Updated Section instance
        """
        try:
            section = Section.objects.get(id=section_id)
        except Section.DoesNotExist:
            raise ValidationError("Section not found")

        # Validate name uniqueness if changing name
        if name and name != section.name:
            if (
                Section.objects.filter(name__iexact=name)
                .exclude(id=section_id)
                .exists()
            ):
                raise ValidationError(f"Section with name '{name}' already exists")
            section.name = name

        if description is not None:
            section.description = description

        if department is not None:
            section.department = department

        if order_sequence is not None:
            section.order_sequence = order_sequence

        if is_active is not None:
            # Check if can be deactivated
            if not is_active and section.is_active:
                SectionService._validate_section_deactivation(section)
            section.is_active = is_active

        section.save()
        return section

    @staticmethod
    def _validate_section_deactivation(section: Section) -> None:
        """
        Validate if a section can be deactivated

        Args:
            section: Section to validate

        Raises:
            ValidationError: If section cannot be deactivated
        """
        # Check for active grades
        active_grades = section.grades.filter(is_active=True).count()
        if active_grades > 0:
            raise ValidationError(
                f"Cannot deactivate section with {active_grades} active grades"
            )

        # Check for active classes in current academic year
        from .academic_year_service import AcademicYearService

        current_year = AcademicYearService.get_current_academic_year()

        if current_year:
            active_classes = section.classes.filter(
                academic_year=current_year, is_active=True
            ).count()

            if active_classes > 0:
                raise ValidationError(
                    f"Cannot deactivate section with {active_classes} active classes in current academic year"
                )

    @staticmethod
    def get_section_hierarchy(section_id: int) -> Dict[str, Any]:
        """
        Get complete hierarchy for a section (grades and classes)

        Args:
            section_id: ID of section

        Returns:
            Dictionary containing section hierarchy with statistics
        """
        try:
            section = Section.objects.get(id=section_id)
        except Section.DoesNotExist:
            raise ValidationError("Section not found")

        from .academic_year_service import AcademicYearService

        current_year = AcademicYearService.get_current_academic_year()

        grades = []
        total_students = 0
        total_classes = 0

        for grade in section.get_grades():
            grade_classes = []
            grade_students = 0

            classes_qs = (
                grade.get_classes(current_year) if current_year else grade.get_classes()
            )

            for cls in classes_qs:
                student_count = cls.get_students_count()
                grade_students += student_count

                grade_classes.append(
                    {
                        "id": cls.id,
                        "name": cls.name,
                        "display_name": cls.display_name,
                        "room_number": cls.room_number,
                        "capacity": cls.capacity,
                        "students_count": student_count,
                        "available_capacity": cls.get_available_capacity(),
                        "is_full": cls.is_full(),
                        "class_teacher": (
                            {
                                "id": cls.class_teacher.id,
                                "name": f"{cls.class_teacher.user.first_name} {cls.class_teacher.user.last_name}",
                            }
                            if cls.class_teacher
                            else None
                        ),
                    }
                )

            total_students += grade_students
            total_classes += len(grade_classes)

            grades.append(
                {
                    "id": grade.id,
                    "name": grade.name,
                    "description": grade.description,
                    "order_sequence": grade.order_sequence,
                    "minimum_age": grade.minimum_age,
                    "maximum_age": grade.maximum_age,
                    "classes_count": len(grade_classes),
                    "students_count": grade_students,
                    "classes": grade_classes,
                }
            )

        return {
            "section": {
                "id": section.id,
                "name": section.name,
                "description": section.description,
                "order_sequence": section.order_sequence,
                "is_active": section.is_active,
                "department": (
                    {"id": section.department.id, "name": section.department.name}
                    if section.department
                    else None
                ),
            },
            "grades": grades,
            "statistics": {
                "total_grades": len(grades),
                "total_classes": total_classes,
                "total_students": total_students,
                "current_academic_year": current_year.name if current_year else None,
            },
        }

    @staticmethod
    def get_section_analytics(
        section_id: int, academic_year_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Get analytics for a section

        Args:
            section_id: ID of section
            academic_year_id: Optional academic year ID for filtering

        Returns:
            Dictionary containing section analytics
        """
        try:
            section = Section.objects.get(id=section_id)
        except Section.DoesNotExist:
            raise ValidationError("Section not found")

        from .academic_year_service import AcademicYearService

        if academic_year_id:
            try:
                from ..models import AcademicYear

                academic_year = AcademicYear.objects.get(id=academic_year_id)
            except AcademicYear.DoesNotExist:
                raise ValidationError("Academic year not found")
        else:
            academic_year = AcademicYearService.get_current_academic_year()

        if not academic_year:
            return {
                "section": section.name,
                "error": "No academic year available for analytics",
            }

        # Get classes for this section and academic year
        classes = Class.objects.filter(
            section=section, academic_year=academic_year, is_active=True
        ).select_related("grade")

        # Calculate statistics
        grade_stats = {}
        total_capacity = 0
        total_students = 0
        total_available = 0

        for cls in classes:
            grade_name = cls.grade.name
            if grade_name not in grade_stats:
                grade_stats[grade_name] = {
                    "classes_count": 0,
                    "total_capacity": 0,
                    "total_students": 0,
                    "utilization_rate": 0,
                }

            student_count = cls.get_students_count()

            grade_stats[grade_name]["classes_count"] += 1
            grade_stats[grade_name]["total_capacity"] += cls.capacity
            grade_stats[grade_name]["total_students"] += student_count

            total_capacity += cls.capacity
            total_students += student_count

        # Calculate utilization rates
        for grade_name in grade_stats:
            if grade_stats[grade_name]["total_capacity"] > 0:
                grade_stats[grade_name]["utilization_rate"] = (
                    grade_stats[grade_name]["total_students"]
                    / grade_stats[grade_name]["total_capacity"]
                    * 100
                )

        total_available = total_capacity - total_students
        overall_utilization = (
            (total_students / total_capacity * 100) if total_capacity > 0 else 0
        )

        return {
            "section": {"id": section.id, "name": section.name},
            "academic_year": {"id": academic_year.id, "name": academic_year.name},
            "overall_statistics": {
                "total_classes": classes.count(),
                "total_capacity": total_capacity,
                "total_students": total_students,
                "available_capacity": total_available,
                "utilization_rate": round(overall_utilization, 2),
                "grades_count": len(grade_stats),
            },
            "grade_statistics": grade_stats,
            "capacity_analysis": {
                "is_over_capacity": total_students > total_capacity,
                "capacity_shortage": max(0, total_students - total_capacity),
                "utilization_status": SectionService._get_utilization_status(
                    overall_utilization
                ),
            },
        }

    @staticmethod
    def _get_utilization_status(utilization_rate: float) -> str:
        """Get utilization status based on rate"""
        if utilization_rate >= 95:
            return "Over Capacity"
        elif utilization_rate >= 85:
            return "High Utilization"
        elif utilization_rate >= 70:
            return "Good Utilization"
        elif utilization_rate >= 50:
            return "Moderate Utilization"
        else:
            return "Low Utilization"

    @staticmethod
    def reorder_sections(section_orders: List[Dict[str, int]]) -> List[Section]:
        """
        Reorder sections based on provided order sequence

        Args:
            section_orders: List of dicts with 'id' and 'order_sequence'

        Returns:
            List of updated Section instances
        """
        updated_sections = []

        with transaction.atomic():
            for order_data in section_orders:
                try:
                    section = Section.objects.get(id=order_data["id"])
                    section.order_sequence = order_data["order_sequence"]
                    section.save()
                    updated_sections.append(section)
                except Section.DoesNotExist:
                    raise ValidationError(
                        f"Section with ID {order_data['id']} not found"
                    )

        return updated_sections

    @staticmethod
    def get_sections_summary() -> Dict[str, Any]:
        """
        Get summary of all sections with key metrics

        Returns:
            Dictionary containing sections summary
        """
        from .academic_year_service import AcademicYearService

        current_year = AcademicYearService.get_current_academic_year()

        sections = Section.objects.filter(is_active=True).order_by("order_sequence")

        sections_data = []
        total_students = 0
        total_classes = 0
        total_grades = 0

        for section in sections:
            section_students = 0
            section_classes = 0
            grades_count = section.get_grades_count()

            if current_year:
                classes = section.classes.filter(
                    academic_year=current_year, is_active=True
                )
                section_classes = classes.count()
                section_students = sum(cls.get_students_count() for cls in classes)

            total_students += section_students
            total_classes += section_classes
            total_grades += grades_count

            sections_data.append(
                {
                    "id": section.id,
                    "name": section.name,
                    "description": section.description,
                    "grades_count": grades_count,
                    "classes_count": section_classes,
                    "students_count": section_students,
                    "order_sequence": section.order_sequence,
                    "department": (
                        {"id": section.department.id, "name": section.department.name}
                        if section.department
                        else None
                    ),
                }
            )

        return {
            "sections": sections_data,
            "summary": {
                "total_sections": len(sections_data),
                "total_grades": total_grades,
                "total_classes": total_classes,
                "total_students": total_students,
                "current_academic_year": current_year.name if current_year else None,
            },
        }

    @staticmethod
    def duplicate_section_structure(
        source_section_id: int,
        new_section_name: str,
        academic_year_id: int,
        include_classes: bool = True,
    ) -> Section:
        """
        Duplicate a section's structure (grades and optionally classes) for a new academic year

        Args:
            source_section_id: ID of section to duplicate
            new_section_name: Name for the new section
            academic_year_id: Target academic year ID
            include_classes: Whether to also duplicate classes

        Returns:
            New Section instance with duplicated structure
        """
        try:
            source_section = Section.objects.get(id=source_section_id)
        except Section.DoesNotExist:
            raise ValidationError("Source section not found")

        try:
            from ..models import AcademicYear

            academic_year = AcademicYear.objects.get(id=academic_year_id)
        except AcademicYear.DoesNotExist:
            raise ValidationError("Academic year not found")

        with transaction.atomic():
            # Create new section
            new_section = SectionService.create_section(
                name=new_section_name,
                description=source_section.description,
                department=source_section.department,
                order_sequence=source_section.order_sequence,
            )

            # Duplicate grades
            for source_grade in source_section.get_grades():
                new_grade = Grade.objects.create(
                    name=source_grade.name,
                    description=source_grade.description,
                    section=new_section,
                    department=source_grade.department,
                    order_sequence=source_grade.order_sequence,
                    minimum_age=source_grade.minimum_age,
                    maximum_age=source_grade.maximum_age,
                )

                # Duplicate classes if requested
                if include_classes:
                    source_classes = source_grade.classes.filter(is_active=True)
                    for source_class in source_classes:
                        Class.objects.create(
                            name=source_class.name,
                            grade=new_grade,
                            section=new_section,
                            academic_year=academic_year,
                            room_number=source_class.room_number,
                            capacity=source_class.capacity,
                            # Note: class_teacher is not copied as it should be assigned manually
                        )

            return new_section
