"""
Utility functions for the subjects module.

This module contains helper functions, decorators, and utility classes
for common operations in the subjects management system.
"""

import json
import csv
import openpyxl
from io import StringIO, BytesIO
from typing import Dict, List, Optional, Tuple, Any, Union
from datetime import datetime, date, timedelta
from decimal import Decimal
import re

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.core.cache import cache
from django.db.models import Q, Count, Avg, Sum
from django.conf import settings
import logging

from .models import Subject, Syllabus, TopicProgress, SubjectAssignment
from academics.models import Grade, AcademicYear, Term, Class

logger = logging.getLogger(__name__)


class SubjectCodeGenerator:
    """
    Utility class for generating standardized subject codes.
    """

    @staticmethod
    def generate_code(
        subject_name: str, department_code: str = None, grade_level: int = None
    ) -> str:
        """
        Generate a standardized subject code.

        Args:
            subject_name: Name of the subject
            department_code: Optional department code
            grade_level: Optional grade level

        Returns:
            Generated subject code
        """
        # Clean subject name
        clean_name = re.sub(r"[^a-zA-Z\s]", "", subject_name)
        words = clean_name.split()

        # Create base code from first letters of words
        if len(words) == 1:
            base_code = words[0][:4].upper()
        else:
            base_code = "".join(word[0] for word in words[:3]).upper()

        # Add department prefix if provided
        if department_code:
            base_code = f"{department_code}{base_code}"

        # Add grade level suffix if provided
        if grade_level:
            base_code = f"{base_code}{grade_level:02d}"

        # Ensure minimum length
        if len(base_code) < 3:
            base_code = base_code.ljust(3, "0")

        return base_code[:10]  # Limit to 10 characters

    @staticmethod
    def suggest_unique_code(subject_name: str, department_code: str = None) -> str:
        """
        Suggest a unique subject code by checking existing codes.

        Args:
            subject_name: Name of the subject
            department_code: Optional department code

        Returns:
            Unique subject code
        """
        base_code = SubjectCodeGenerator.generate_code(subject_name, department_code)

        # Check if code already exists
        counter = 1
        unique_code = base_code

        while Subject.objects.filter(code=unique_code).exists():
            if len(base_code) <= 7:
                unique_code = f"{base_code}{counter:02d}"
            else:
                unique_code = f"{base_code[:-2]}{counter:02d}"
            counter += 1

            if counter > 99:  # Prevent infinite loop
                unique_code = f"{base_code[:6]}{counter:03d}"
                break

        return unique_code


class SyllabusContentValidator:
    """
    Utility class for validating syllabus content structure.
    """

    REQUIRED_TOPIC_FIELDS = ["name"]
    OPTIONAL_TOPIC_FIELDS = [
        "description",
        "duration",
        "objectives",
        "resources",
        "completed",
    ]

    @staticmethod
    def validate_content_structure(content: Dict) -> Tuple[bool, List[str]]:
        """
        Validate syllabus content structure.

        Args:
            content: Content dictionary to validate

        Returns:
            Tuple of (is_valid, errors_list)
        """
        errors = []

        if not isinstance(content, dict):
            errors.append(_("Content must be a dictionary"))
            return False, errors

        # Validate topics structure
        if "topics" in content:
            topics_valid, topics_errors = SyllabusContentValidator._validate_topics(
                content["topics"]
            )
            if not topics_valid:
                errors.extend(topics_errors)

        # Validate units structure
        if "units" in content:
            units_valid, units_errors = SyllabusContentValidator._validate_units(
                content["units"]
            )
            if not units_valid:
                errors.extend(units_errors)

        # Validate teaching schedule
        if "teaching_schedule" in content:
            schedule_valid, schedule_errors = (
                SyllabusContentValidator._validate_teaching_schedule(
                    content["teaching_schedule"]
                )
            )
            if not schedule_valid:
                errors.extend(schedule_errors)

        return len(errors) == 0, errors

    @staticmethod
    def _validate_topics(topics: List) -> Tuple[bool, List[str]]:
        """Validate topics structure."""
        errors = []

        if not isinstance(topics, list):
            errors.append(_("Topics must be a list"))
            return False, errors

        for i, topic in enumerate(topics):
            if not isinstance(topic, dict):
                errors.append(_(f"Topic {i+1} must be a dictionary"))
                continue

            # Check required fields
            for field in SyllabusContentValidator.REQUIRED_TOPIC_FIELDS:
                if field not in topic:
                    errors.append(_(f"Topic {i+1} missing required field: {field}"))

            # Validate field types
            if "name" in topic and not isinstance(topic["name"], str):
                errors.append(_(f"Topic {i+1} name must be a string"))

            if "completed" in topic and not isinstance(topic["completed"], bool):
                errors.append(_(f"Topic {i+1} completed must be a boolean"))

        return len(errors) == 0, errors

    @staticmethod
    def _validate_units(units: List) -> Tuple[bool, List[str]]:
        """Validate units structure."""
        errors = []

        if not isinstance(units, list):
            errors.append(_("Units must be a list"))
            return False, errors

        for i, unit in enumerate(units):
            if not isinstance(unit, dict):
                errors.append(_(f"Unit {i+1} must be a dictionary"))
                continue

            if "name" not in unit:
                errors.append(_(f"Unit {i+1} missing required field: name"))

        return len(errors) == 0, errors

    @staticmethod
    def _validate_teaching_schedule(schedule: Dict) -> Tuple[bool, List[str]]:
        """Validate teaching schedule structure."""
        errors = []

        if not isinstance(schedule, dict):
            errors.append(_("Teaching schedule must be a dictionary"))
            return False, errors

        # Add specific validation rules for teaching schedule
        # This can be customized based on requirements

        return len(errors) == 0, errors


class ProgressCalculator:
    """
    Utility class for calculating various progress metrics.
    """

    @staticmethod
    def calculate_completion_percentage(
        total_items: int, completed_items: int
    ) -> float:
        """
        Calculate completion percentage.

        Args:
            total_items: Total number of items
            completed_items: Number of completed items

        Returns:
            Completion percentage (0-100)
        """
        if total_items == 0:
            return 0.0

        percentage = (completed_items / total_items) * 100
        return round(percentage, 2)

    @staticmethod
    def calculate_progress_velocity(
        completion_percentage: float, days_elapsed: int, total_days: int
    ) -> float:
        """
        Calculate progress velocity (rate of completion).

        Args:
            completion_percentage: Current completion percentage
            days_elapsed: Days elapsed since start
            total_days: Total days available

        Returns:
            Progress velocity
        """
        if days_elapsed == 0:
            return 0.0

        expected_progress = (days_elapsed / total_days) * 100
        if expected_progress == 0:
            return 0.0

        velocity = completion_percentage / expected_progress
        return round(velocity, 2)

    @staticmethod
    def project_completion_date(
        start_date: date,
        end_date: date,
        current_progress: float,
        target_progress: float = 100.0,
    ) -> Optional[date]:
        """
        Project completion date based on current progress.

        Args:
            start_date: Start date
            end_date: Planned end date
            current_progress: Current progress percentage
            target_progress: Target progress percentage

        Returns:
            Projected completion date or None if cannot calculate
        """
        if current_progress <= 0:
            return None

        current_date = date.today()
        days_elapsed = (current_date - start_date).days

        if days_elapsed <= 0:
            return None

        # Calculate daily progress rate
        daily_rate = current_progress / days_elapsed

        if daily_rate <= 0:
            return None

        # Calculate remaining progress needed
        remaining_progress = target_progress - current_progress

        if remaining_progress <= 0:
            return current_date  # Already completed

        # Calculate days needed to complete
        days_needed = remaining_progress / daily_rate
        projected_date = current_date + timedelta(days=int(days_needed))

        return projected_date


class FileProcessor:
    """
    Utility class for processing uploaded files (CSV, Excel).
    """

    @staticmethod
    def process_subjects_file(file) -> Tuple[List[Dict], List[str]]:
        """
        Process uploaded subjects file and extract data.

        Args:
            file: Uploaded file object

        Returns:
            Tuple of (data_list, errors_list)
        """
        errors = []
        data = []

        file_extension = file.name.split(".")[-1].lower()

        try:
            if file_extension == "csv":
                data, errors = FileProcessor._process_csv_file(file)
            elif file_extension in ["xlsx", "xls"]:
                data, errors = FileProcessor._process_excel_file(file)
            else:
                errors.append(_("Unsupported file format"))

        except Exception as e:
            errors.append(_("Error processing file: {}").format(str(e)))
            logger.error(f"Error processing subjects file: {str(e)}")

        return data, errors

    @staticmethod
    def _process_csv_file(file) -> Tuple[List[Dict], List[str]]:
        """Process CSV file."""
        data = []
        errors = []

        try:
            # Read file content
            content = file.read().decode("utf-8")
            csv_reader = csv.DictReader(StringIO(content))

            required_fields = ["name", "code"]

            for row_num, row in enumerate(csv_reader, start=2):
                # Clean row data
                clean_row = {k.strip().lower(): v.strip() for k, v in row.items() if k}

                # Check required fields
                missing_fields = [
                    field
                    for field in required_fields
                    if field not in clean_row or not clean_row[field]
                ]

                if missing_fields:
                    errors.append(
                        _("Row {}: Missing required fields: {}").format(
                            row_num, ", ".join(missing_fields)
                        )
                    )
                    continue

                # Convert data types
                processed_row = FileProcessor._convert_subject_data_types(
                    clean_row, row_num, errors
                )
                if processed_row:
                    data.append(processed_row)

        except Exception as e:
            errors.append(_("Error reading CSV file: {}").format(str(e)))

        return data, errors

    @staticmethod
    def _process_excel_file(file) -> Tuple[List[Dict], List[str]]:
        """Process Excel file."""
        data = []
        errors = []

        try:
            workbook = openpyxl.load_workbook(file)
            worksheet = workbook.active

            # Get headers from first row
            headers = []
            for cell in worksheet[1]:
                if cell.value:
                    headers.append(cell.value.strip().lower())
                else:
                    headers.append("")

            required_fields = ["name", "code"]

            # Process data rows
            for row_num, row in enumerate(
                worksheet.iter_rows(min_row=2, values_only=True), start=2
            ):
                if not any(row):  # Skip empty rows
                    continue

                # Create row dictionary
                row_dict = {}
                for i, value in enumerate(row):
                    if i < len(headers) and headers[i]:
                        row_dict[headers[i]] = str(value).strip() if value else ""

                # Check required fields
                missing_fields = [
                    field
                    for field in required_fields
                    if field not in row_dict or not row_dict[field]
                ]

                if missing_fields:
                    errors.append(
                        _("Row {}: Missing required fields: {}").format(
                            row_num, ", ".join(missing_fields)
                        )
                    )
                    continue

                # Convert data types
                processed_row = FileProcessor._convert_subject_data_types(
                    row_dict, row_num, errors
                )
                if processed_row:
                    data.append(processed_row)

        except Exception as e:
            errors.append(_("Error reading Excel file: {}").format(str(e)))

        return data, errors

    @staticmethod
    def _convert_subject_data_types(
        row: Dict, row_num: int, errors: List[str]
    ) -> Optional[Dict]:
        """Convert subject data to appropriate types."""
        try:
            processed = {
                "name": row.get("name", ""),
                "code": row.get("code", "").upper(),
                "description": row.get("description", ""),
                "credit_hours": 1,
                "is_elective": False,
                "grade_level": [],
            }

            # Convert credit hours
            if "credit_hours" in row and row["credit_hours"]:
                try:
                    processed["credit_hours"] = int(row["credit_hours"])
                    if processed["credit_hours"] < 1 or processed["credit_hours"] > 10:
                        errors.append(
                            _(f"Row {row_num}: Credit hours must be between 1 and 10")
                        )
                        return None
                except ValueError:
                    errors.append(_(f"Row {row_num}: Invalid credit hours value"))
                    return None

            # Convert is_elective
            if "is_elective" in row and row["is_elective"]:
                elective_value = row["is_elective"].lower()
                processed["is_elective"] = elective_value in ["true", "1", "yes", "y"]

            # Convert grade_level
            if "grade_level" in row and row["grade_level"]:
                try:
                    # Parse comma-separated grade IDs
                    grade_ids = [
                        int(x.strip())
                        for x in row["grade_level"].split(",")
                        if x.strip()
                    ]
                    processed["grade_level"] = grade_ids
                except ValueError:
                    errors.append(_(f"Row {row_num}: Invalid grade level format"))
                    return None

            return processed

        except Exception as e:
            errors.append(_(f"Row {row_num}: Error processing data: {str(e)}"))
            return None


class CacheManager:
    """
    Utility class for managing cache operations related to subjects.
    """

    CACHE_TIMEOUT = getattr(settings, "SUBJECTS_CACHE_TIMEOUT", 3600)  # 1 hour default

    @staticmethod
    def get_cache_key(prefix: str, *args) -> str:
        """
        Generate cache key with consistent format.

        Args:
            prefix: Cache key prefix
            *args: Additional arguments for key

        Returns:
            Formatted cache key
        """
        key_parts = [prefix] + [str(arg) for arg in args]
        return "subjects:" + ":".join(key_parts)

    @staticmethod
    def cache_syllabus_progress(syllabus_id: int, progress_data: Dict) -> None:
        """Cache syllabus progress data."""
        cache_key = CacheManager.get_cache_key("progress", syllabus_id)
        cache.set(cache_key, progress_data, CacheManager.CACHE_TIMEOUT)

    @staticmethod
    def get_cached_syllabus_progress(syllabus_id: int) -> Optional[Dict]:
        """Get cached syllabus progress data."""
        cache_key = CacheManager.get_cache_key("progress", syllabus_id)
        return cache.get(cache_key)

    @staticmethod
    def cache_curriculum_analytics(
        academic_year_id: int, department_id: Optional[int], data: Dict
    ) -> None:
        """Cache curriculum analytics data."""
        cache_key = CacheManager.get_cache_key(
            "analytics", academic_year_id, department_id or "all"
        )
        cache.set(cache_key, data, CacheManager.CACHE_TIMEOUT)

    @staticmethod
    def get_cached_curriculum_analytics(
        academic_year_id: int, department_id: Optional[int]
    ) -> Optional[Dict]:
        """Get cached curriculum analytics data."""
        cache_key = CacheManager.get_cache_key(
            "analytics", academic_year_id, department_id or "all"
        )
        return cache.get(cache_key)

    @staticmethod
    def clear_related_caches(syllabus: "Syllabus") -> None:
        """Clear all caches related to a syllabus."""
        keys_to_clear = [
            CacheManager.get_cache_key("progress", syllabus.id),
            CacheManager.get_cache_key(
                "analytics", syllabus.academic_year.id, syllabus.subject.department.id
            ),
            CacheManager.get_cache_key(
                "grade_overview", syllabus.grade.id, syllabus.academic_year.id
            ),
            CacheManager.get_cache_key(
                "curriculum_structure", syllabus.academic_year.id
            ),
        ]

        cache.delete_many(keys_to_clear)


class DataExporter:
    """
    Utility class for exporting subjects data to various formats.
    """

    @staticmethod
    def export_subjects_to_csv(subjects_queryset) -> str:
        """
        Export subjects data to CSV format.

        Args:
            subjects_queryset: QuerySet of subjects to export

        Returns:
            CSV content as string
        """
        output = StringIO()
        writer = csv.writer(output)

        # Write headers
        headers = [
            "Name",
            "Code",
            "Department",
            "Credit Hours",
            "Is Elective",
            "Grade Levels",
            "Description",
            "Created At",
        ]
        writer.writerow(headers)

        # Write data
        for subject in subjects_queryset:
            grade_names = []
            if subject.grade_level:
                grades = Grade.objects.filter(id__in=subject.grade_level)
                grade_names = [grade.name for grade in grades]

            row = [
                subject.name,
                subject.code,
                subject.department.name,
                subject.credit_hours,
                "Yes" if subject.is_elective else "No",
                ", ".join(grade_names) if grade_names else "All Grades",
                subject.description,
                subject.created_at.strftime("%Y-%m-%d"),
            ]
            writer.writerow(row)

        return output.getvalue()

    @staticmethod
    def export_syllabi_to_csv(syllabi_queryset) -> str:
        """
        Export syllabi data to CSV format.

        Args:
            syllabi_queryset: QuerySet of syllabi to export

        Returns:
            CSV content as string
        """
        output = StringIO()
        writer = csv.writer(output)

        # Write headers
        headers = [
            "Title",
            "Subject",
            "Grade",
            "Academic Year",
            "Term",
            "Completion %",
            "Total Topics",
            "Completed Topics",
            "Difficulty Level",
            "Created By",
            "Created At",
        ]
        writer.writerow(headers)

        # Write data
        for syllabus in syllabi_queryset:
            row = [
                syllabus.title,
                syllabus.subject.name,
                syllabus.grade.name,
                syllabus.academic_year.name,
                syllabus.term.name,
                f"{syllabus.completion_percentage:.2f}%",
                syllabus.get_total_topics(),
                syllabus.get_completed_topics(),
                syllabus.get_difficulty_level_display(),
                syllabus.created_by.get_full_name() if syllabus.created_by else "",
                syllabus.created_at.strftime("%Y-%m-%d"),
            ]
            writer.writerow(row)

        return output.getvalue()

    @staticmethod
    def export_analytics_to_json(analytics_data: Dict) -> str:
        """
        Export analytics data to JSON format.

        Args:
            analytics_data: Analytics data dictionary

        Returns:
            JSON content as string
        """

        # Convert any datetime objects to strings
        def json_serializer(obj):
            if isinstance(obj, (date, datetime)):
                return obj.isoformat()
            elif isinstance(obj, Decimal):
                return float(obj)
            raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

        return json.dumps(analytics_data, indent=2, default=json_serializer)


class ValidationHelpers:
    """
    Utility class for common validation operations.
    """

    @staticmethod
    def validate_academic_hierarchy(
        subject_id: int, grade_id: int, academic_year_id: int, term_id: int
    ) -> List[str]:
        """
        Validate academic hierarchy relationships.

        Args:
            subject_id: Subject ID
            grade_id: Grade ID
            academic_year_id: Academic year ID
            term_id: Term ID

        Returns:
            List of validation errors
        """
        errors = []

        try:
            # Validate subject-grade relationship
            subject = Subject.objects.get(id=subject_id)
            if not subject.is_applicable_for_grade(grade_id):
                errors.append(
                    _("Subject '{}' is not applicable for the selected grade").format(
                        subject.name
                    )
                )

            # Validate term-academic year relationship
            term = Term.objects.get(id=term_id)
            if term.academic_year_id != academic_year_id:
                errors.append(
                    _("Term '{}' does not belong to the selected academic year").format(
                        term.name
                    )
                )

        except (Subject.DoesNotExist, Term.DoesNotExist) as e:
            errors.append(_("Invalid reference: {}").format(str(e)))

        return errors

    @staticmethod
    def validate_date_range(
        start_date: date, end_date: date, field_name: str = "Date range"
    ) -> List[str]:
        """
        Validate date range.

        Args:
            start_date: Start date
            end_date: End date
            field_name: Field name for error messages

        Returns:
            List of validation errors
        """
        errors = []

        if start_date and end_date:
            if start_date > end_date:
                errors.append(_(f"{field_name}: Start date cannot be after end date"))

            # Check if dates are reasonable (not too far in past/future)
            current_year = date.today().year
            if start_date.year < current_year - 10:
                errors.append(_(f"{field_name}: Start date seems too far in the past"))

            if end_date.year > current_year + 10:
                errors.append(_(f"{field_name}: End date seems too far in the future"))

        return errors


def get_current_academic_context() -> Dict:
    """
    Get current academic context (year and term).

    Returns:
        Dictionary with current academic year and term
    """
    try:
        current_year = AcademicYear.objects.filter(is_current=True).first()
        current_term = None

        if current_year:
            current_term = Term.objects.filter(
                academic_year=current_year, is_current=True
            ).first()

        return {
            "academic_year": current_year,
            "term": current_term,
            "academic_year_id": current_year.id if current_year else None,
            "term_id": current_term.id if current_term else None,
        }

    except Exception as e:
        logger.error(f"Error getting academic context: {str(e)}")
        return {
            "academic_year": None,
            "term": None,
            "academic_year_id": None,
            "term_id": None,
        }


def format_progress_percentage(percentage: float) -> str:
    """
    Format progress percentage for display.

    Args:
        percentage: Progress percentage (0-100)

    Returns:
        Formatted percentage string
    """
    if percentage == 0:
        return "0%"
    elif percentage == 100:
        return "100%"
    else:
        return f"{percentage:.1f}%"


def get_progress_status_color(percentage: float) -> str:
    """
    Get color code for progress status.

    Args:
        percentage: Progress percentage (0-100)

    Returns:
        Color code (Bootstrap classes)
    """
    if percentage == 0:
        return "secondary"
    elif percentage < 30:
        return "danger"
    elif percentage < 70:
        return "warning"
    elif percentage < 100:
        return "info"
    else:
        return "success"


def calculate_risk_assessment(syllabus: "Syllabus") -> Dict:
    """
    Calculate risk assessment for syllabus completion.

    Args:
        syllabus: Syllabus instance

    Returns:
        Risk assessment data
    """
    current_date = date.today()
    term = syllabus.term

    # Calculate time progress
    if term.start_date <= current_date <= term.end_date:
        total_days = (term.end_date - term.start_date).days
        elapsed_days = (current_date - term.start_date).days
        remaining_days = (term.end_date - current_date).days
        time_progress = (elapsed_days / total_days) * 100 if total_days > 0 else 0
    else:
        # Term not active
        return {
            "risk_level": "unknown",
            "message": "Term not currently active",
            "recommendations": [],
        }

    # Calculate completion vs time progress
    completion_progress = syllabus.completion_percentage
    progress_difference = time_progress - completion_progress

    # Determine risk level
    risk_level = "low"
    message = "On track"
    recommendations = []

    if progress_difference > 30:
        risk_level = "high"
        message = "Significantly behind schedule"
        recommendations = [
            "Immediate action required",
            "Consider additional teaching hours",
            "Review teaching methodology",
            "Prioritize essential topics",
        ]
    elif progress_difference > 15:
        risk_level = "medium"
        message = "Behind schedule"
        recommendations = [
            "Monitor progress closely",
            "Consider accelerating pace",
            "Focus on key topics",
        ]
    elif progress_difference < -15:
        risk_level = "low"
        message = "Ahead of schedule"
        recommendations = [
            "Maintain current pace",
            "Consider enrichment activities",
            "Review additional topics",
        ]

    return {
        "risk_level": risk_level,
        "message": message,
        "recommendations": recommendations,
        "time_progress": round(time_progress, 1),
        "completion_progress": round(completion_progress, 1),
        "progress_difference": round(progress_difference, 1),
        "remaining_days": remaining_days,
    }
