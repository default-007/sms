"""
Utility Functions for Academics Module

This module provides helper functions and utilities for the academics app,
including data processing, validation, and common operations.
"""

from django.db.models import Q, Count, Sum, Avg
from django.core.cache import cache
from django.utils import timezone
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple

from .models import AcademicYear, Term, Section, Grade, Class, Department


def get_current_academic_context() -> Dict[str, Any]:
    """
    Get current academic context (year and term)

    Returns:
        Dictionary with current academic year and term information
    """
    cache_key = "current_academic_context"
    context = cache.get(cache_key)

    if context is None:
        current_year = AcademicYear.objects.filter(is_current=True).first()
        current_term = None

        if current_year:
            current_term = current_year.terms.filter(is_current=True).first()

        context = {
            "academic_year": (
                {
                    "id": current_year.id,
                    "name": current_year.name,
                    "start_date": current_year.start_date,
                    "end_date": current_year.end_date,
                }
                if current_year
                else None
            ),
            "term": (
                {
                    "id": current_term.id,
                    "name": current_term.name,
                    "term_number": current_term.term_number,
                    "start_date": current_term.start_date,
                    "end_date": current_term.end_date,
                }
                if current_term
                else None
            ),
        }

        # Cache for 1 hour
        cache.set(cache_key, context, 3600)

    return context


def calculate_academic_year_progress(academic_year: AcademicYear) -> Dict[str, Any]:
    """
    Calculate progress of an academic year

    Args:
        academic_year: AcademicYear instance

    Returns:
        Dictionary with progress information
    """
    today = timezone.now().date()

    if today < academic_year.start_date:
        return {
            "status": "Not Started",
            "progress_percentage": 0,
            "days_until_start": (academic_year.start_date - today).days,
            "days_remaining": (academic_year.end_date - academic_year.start_date).days,
        }
    elif today > academic_year.end_date:
        return {
            "status": "Completed",
            "progress_percentage": 100,
            "days_since_end": (today - academic_year.end_date).days,
            "days_remaining": 0,
        }
    else:
        total_days = (academic_year.end_date - academic_year.start_date).days
        elapsed_days = (today - academic_year.start_date).days
        remaining_days = (academic_year.end_date - today).days
        progress_percentage = (elapsed_days / total_days * 100) if total_days > 0 else 0

        return {
            "status": "In Progress",
            "progress_percentage": round(progress_percentage, 1),
            "elapsed_days": elapsed_days,
            "days_remaining": remaining_days,
        }


def generate_class_name_suggestions(
    grade: Grade, existing_names: List[str] = None
) -> List[str]:
    """
    Generate class name suggestions based on common patterns

    Args:
        grade: Grade instance
        existing_names: List of existing class names to avoid

    Returns:
        List of suggested class names
    """
    if existing_names is None:
        existing_names = []

    existing_names = [name.upper() for name in existing_names]

    # Common naming patterns
    patterns = {
        "alphabetic": ["A", "B", "C", "D", "E", "F"],
        "directional": ["North", "South", "East", "West"],
        "colors": ["Red", "Blue", "Green", "Yellow", "Orange", "Purple"],
        "precious_stones": ["Diamond", "Ruby", "Emerald", "Sapphire", "Pearl", "Topaz"],
        "flowers": ["Rose", "Lily", "Jasmine", "Tulip", "Lotus", "Daisy"],
        "numeric": ["1", "2", "3", "4", "5", "6"],
    }

    suggestions = []

    # Determine appropriate pattern based on grade level
    section_name = grade.section.name.lower()

    if "pre" in section_name or "kg" in section_name:
        # Pre-primary: Colors or Flowers
        suggestions.extend(patterns["colors"])
        suggestions.extend(patterns["flowers"])
    elif "primary" in section_name:
        # Primary: Alphabetic or Colors
        suggestions.extend(patterns["alphabetic"])
        suggestions.extend(patterns["colors"])
    elif "secondary" in section_name:
        # Secondary: Alphabetic or Precious stones
        suggestions.extend(patterns["alphabetic"])
        suggestions.extend(patterns["precious_stones"])
    else:
        # Default: Alphabetic
        suggestions.extend(patterns["alphabetic"])

    # Filter out existing names
    suggestions = [name for name in suggestions if name.upper() not in existing_names]

    return suggestions[:6]  # Return top 6 suggestions


def calculate_optimal_class_size(grade: Grade, total_students: int) -> Dict[str, Any]:
    """
    Calculate optimal class size and number of classes for a grade

    Args:
        grade: Grade instance
        total_students: Total number of students to accommodate

    Returns:
        Dictionary with optimization suggestions
    """
    # Define optimal class sizes by grade level
    optimal_sizes = {
        "pre-primary": 20,
        "lower primary": 25,
        "upper primary": 28,
        "middle": 30,
        "secondary": 32,
        "senior secondary": 35,
    }

    section_name = grade.section.name.lower()

    # Determine optimal class size
    optimal_size = 30  # Default
    for key, size in optimal_sizes.items():
        if key in section_name:
            optimal_size = size
            break

    if total_students == 0:
        return {
            "optimal_classes": 1,
            "optimal_size_per_class": optimal_size,
            "distribution": [optimal_size],
            "efficiency_score": 100,
        }

    # Calculate number of classes needed
    optimal_classes = max(1, round(total_students / optimal_size))

    # Distribute students across classes
    base_size = total_students // optimal_classes
    remainder = total_students % optimal_classes

    distribution = []
    for i in range(optimal_classes):
        class_size = base_size + (1 if i < remainder else 0)
        distribution.append(class_size)

    # Calculate efficiency (how close to optimal size)
    efficiency_scores = []
    for size in distribution:
        if size <= optimal_size:
            efficiency_scores.append((size / optimal_size) * 100)
        else:
            # Penalty for oversized classes
            efficiency_scores.append(max(0, 100 - ((size - optimal_size) * 5)))

    efficiency_score = sum(efficiency_scores) / len(efficiency_scores)

    return {
        "optimal_classes": optimal_classes,
        "optimal_size_per_class": optimal_size,
        "distribution": distribution,
        "efficiency_score": round(efficiency_score, 1),
        "total_capacity": sum(distribution),
        "utilization_rate": (
            (total_students / sum(distribution) * 100) if sum(distribution) > 0 else 0
        ),
    }


def get_academic_hierarchy_tree() -> Dict[str, Any]:
    """
    Get complete academic hierarchy as a tree structure

    Returns:
        Nested dictionary representing the academic hierarchy
    """
    cache_key = "academic_hierarchy_tree"
    tree = cache.get(cache_key)

    if tree is None:
        current_year = AcademicYear.objects.filter(is_current=True).first()

        tree = {
            "academic_year": (
                {"id": current_year.id, "name": current_year.name}
                if current_year
                else None
            ),
            "sections": [],
        }

        sections = Section.objects.filter(is_active=True).order_by("order_sequence")

        for section in sections:
            section_data = {"id": section.id, "name": section.name, "grades": []}

            grades = section.grades.filter(is_active=True).order_by("order_sequence")

            for grade in grades:
                grade_data = {"id": grade.id, "name": grade.name, "classes": []}

                if current_year:
                    classes = grade.classes.filter(
                        academic_year=current_year, is_active=True
                    ).order_by("name")

                    for cls in classes:
                        class_data = {
                            "id": cls.id,
                            "name": cls.name,
                            "display_name": cls.display_name,
                            "capacity": cls.capacity,
                            "students_count": cls.get_students_count(),
                            "room_number": cls.room_number,
                        }
                        grade_data["classes"].append(class_data)

                section_data["grades"].append(grade_data)

            tree["sections"].append(section_data)

        # Cache for 30 minutes
        cache.set(cache_key, tree, 1800)

    return tree


def validate_academic_structure_integrity() -> Dict[str, Any]:
    """
    Validate the integrity of the academic structure

    Returns:
        Dictionary with validation results
    """
    issues = []
    warnings = []

    # Check for current academic year
    current_years = AcademicYear.objects.filter(is_current=True).count()
    if current_years == 0:
        issues.append("No current academic year is set")
    elif current_years > 1:
        issues.append(f"Multiple academic years marked as current: {current_years}")

    # Check for terms in current academic year
    current_year = AcademicYear.objects.filter(is_current=True).first()
    if current_year:
        terms_count = current_year.terms.count()
        if terms_count == 0:
            issues.append("Current academic year has no terms")
        elif terms_count == 1:
            warnings.append("Current academic year has only one term")

        current_terms = current_year.terms.filter(is_current=True).count()
        if current_terms == 0:
            warnings.append("No current term is set")
        elif current_terms > 1:
            issues.append(f"Multiple terms marked as current: {current_terms}")

    # Check for sections without grades
    sections_without_grades = Section.objects.filter(
        is_active=True, grades__isnull=True
    ).count()
    if sections_without_grades > 0:
        warnings.append(f"{sections_without_grades} active sections have no grades")

    # Check for grades without classes
    if current_year:
        grades_without_classes = Grade.objects.filter(
            is_active=True, classes__academic_year=current_year, classes__isnull=True
        ).count()
        if grades_without_classes > 0:
            warnings.append(
                f"{grades_without_classes} grades have no classes in current academic year"
            )

    # Check for overcapacity classes
    if current_year:
        overcapacity_classes = (
            Class.objects.filter(academic_year=current_year, is_active=True)
            .annotate(students_count=Count("students"))
            .filter(students_count__gt=models.F("capacity"))
            .count()
        )

        if overcapacity_classes > 0:
            warnings.append(f"{overcapacity_classes} classes are over capacity")

    # Check for classes without teachers
    if current_year:
        classes_without_teachers = Class.objects.filter(
            academic_year=current_year, is_active=True, class_teacher__isnull=True
        ).count()

        if classes_without_teachers > 0:
            warnings.append(
                f"{classes_without_teachers} classes have no assigned teacher"
            )

    return {
        "is_valid": len(issues) == 0,
        "issues": issues,
        "warnings": warnings,
        "total_issues": len(issues),
        "total_warnings": len(warnings),
    }


def generate_academic_year_name(start_year: int) -> str:
    """
    Generate academic year name based on start year

    Args:
        start_year: Starting year of the academic year

    Returns:
        Academic year name (e.g., "2024-2025")
    """
    return f"{start_year}-{start_year + 1}"


def calculate_age_from_birth_date(
    birth_date: datetime.date, reference_date: datetime.date = None
) -> int:
    """
    Calculate age from birth date

    Args:
        birth_date: Date of birth
        reference_date: Reference date for age calculation (default: today)

    Returns:
        Age in years
    """
    if reference_date is None:
        reference_date = timezone.now().date()

    age = reference_date.year - birth_date.year

    # Adjust if birthday hasn't occurred this year
    if (reference_date.month, reference_date.day) < (birth_date.month, birth_date.day):
        age -= 1

    return age


def get_grade_progression_path(grade: Grade) -> Dict[str, Any]:
    """
    Get the progression path for a grade (previous and next grades)

    Args:
        grade: Grade instance

    Returns:
        Dictionary with progression information
    """
    section = grade.section

    # Get previous grade in the same section
    previous_grade = (
        Grade.objects.filter(
            section=section, order_sequence__lt=grade.order_sequence, is_active=True
        )
        .order_by("-order_sequence")
        .first()
    )

    # Get next grade in the same section
    next_grade = (
        Grade.objects.filter(
            section=section, order_sequence__gt=grade.order_sequence, is_active=True
        )
        .order_by("order_sequence")
        .first()
    )

    # If no next grade in section, check next section's first grade
    if not next_grade:
        next_section = (
            Section.objects.filter(
                order_sequence__gt=section.order_sequence, is_active=True
            )
            .order_by("order_sequence")
            .first()
        )

        if next_section:
            next_grade = (
                next_section.grades.filter(is_active=True)
                .order_by("order_sequence")
                .first()
            )

    return {
        "current_grade": {
            "id": grade.id,
            "name": grade.name,
            "section": grade.section.name,
        },
        "previous_grade": (
            {
                "id": previous_grade.id,
                "name": previous_grade.name,
                "section": previous_grade.section.name,
            }
            if previous_grade
            else None
        ),
        "next_grade": (
            {
                "id": next_grade.id,
                "name": next_grade.name,
                "section": next_grade.section.name,
            }
            if next_grade
            else None
        ),
    }


def bulk_update_class_capacities(grade_id: int, new_capacity: int) -> Dict[str, Any]:
    """
    Bulk update capacities for all classes in a grade

    Args:
        grade_id: Grade ID
        new_capacity: New capacity for all classes

    Returns:
        Dictionary with update results
    """
    try:
        grade = Grade.objects.get(id=grade_id)
    except Grade.DoesNotExist:
        return {"success": False, "error": "Grade not found"}

    current_year = AcademicYear.objects.filter(is_current=True).first()
    if not current_year:
        return {"success": False, "error": "No current academic year"}

    classes = grade.classes.filter(academic_year=current_year, is_active=True)

    # Check if any class has more students than new capacity
    problematic_classes = []
    for cls in classes:
        student_count = cls.get_students_count()
        if student_count > new_capacity:
            problematic_classes.append(
                {
                    "class_name": cls.display_name,
                    "current_students": student_count,
                    "new_capacity": new_capacity,
                }
            )

    if problematic_classes:
        return {
            "success": False,
            "error": "Some classes have more students than the new capacity",
            "problematic_classes": problematic_classes,
        }

    # Update capacities
    updated_count = classes.update(capacity=new_capacity)

    return {
        "success": True,
        "updated_classes": updated_count,
        "new_capacity": new_capacity,
    }


def get_department_statistics() -> Dict[str, Any]:
    """
    Get statistics for all departments

    Returns:
        Dictionary with department statistics
    """
    departments = Department.objects.filter(is_active=True)

    stats = []
    for dept in departments:
        # Get sections in this department
        sections_count = dept.sections.filter(is_active=True).count()

        # Get grades in this department
        grades_count = dept.grades.filter(is_active=True).count()

        # Get teachers in this department
        teachers_count = dept.get_teachers_count()

        # Get subjects in this department
        subjects_count = dept.get_subjects_count()

        stats.append(
            {
                "id": dept.id,
                "name": dept.name,
                "sections_count": sections_count,
                "grades_count": grades_count,
                "teachers_count": teachers_count,
                "subjects_count": subjects_count,
                "head": (
                    {
                        "id": dept.head.id,
                        "name": f"{dept.head.user.first_name} {dept.head.user.last_name}",
                    }
                    if dept.head
                    else None
                ),
            }
        )

    return {
        "departments": stats,
        "total_departments": len(stats),
        "total_sections": sum(d["sections_count"] for d in stats),
        "total_grades": sum(d["grades_count"] for d in stats),
        "total_teachers": sum(d["teachers_count"] for d in stats),
        "total_subjects": sum(d["subjects_count"] for d in stats),
    }


def export_academic_structure_data(format_type: str = "dict") -> Any:
    """
    Export academic structure data in various formats

    Args:
        format_type: Export format ('dict', 'json', 'csv')

    Returns:
        Academic structure data in requested format
    """
    data = get_academic_hierarchy_tree()

    if format_type == "dict":
        return data
    elif format_type == "json":
        import json

        return json.dumps(data, indent=2, default=str)
    elif format_type == "csv":
        import csv
        import io

        output = io.StringIO()
        writer = csv.writer(output)

        # Write headers
        writer.writerow(["Section", "Grade", "Class", "Capacity", "Students", "Room"])

        # Write data
        for section in data["sections"]:
            for grade in section["grades"]:
                for cls in grade["classes"]:
                    writer.writerow(
                        [
                            section["name"],
                            grade["name"],
                            cls["name"],
                            cls["capacity"],
                            cls["students_count"],
                            cls["room_number"],
                        ]
                    )

        return output.getvalue()
    else:
        raise ValueError(f"Unsupported format: {format_type}")


def clear_academics_cache():
    """Clear all academics-related cache entries"""
    cache_keys = [
        "current_academic_context",
        "academic_hierarchy_tree",
        "sections_summary",
        "current_academic_year",
    ]

    cache.delete_many(cache_keys)

    # Clear pattern-based cache keys
    from django.core.cache.utils import make_key

    for key_pattern in [
        "section_hierarchy_*",
        "section_analytics_*",
        "grade_details_*",
    ]:
        # This would need custom implementation based on cache backend
        pass
