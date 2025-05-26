# src/teachers/utils/data_migration_helpers.py
"""
Helper utilities for teacher data migration and transformation.
"""

import csv
import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

import pandas as pd
from django.core.exceptions import ValidationError

from src.teachers.validators import validate_evaluation_data, validate_teacher_data
from teachers.models import Teacher


class TeacherDataTransformer:
    """Transform teacher data between different formats."""

    def __init__(self):
        self.errors = []
        self.warnings = []

    def transform_csv_to_teacher_dict(self, csv_row: Dict[str, str]) -> Dict[str, Any]:
        """Transform CSV row to teacher dictionary."""
        try:
            return {
                "employee_id": self._clean_string(csv_row.get("employee_id", "")),
                "first_name": self._clean_string(csv_row.get("first_name", "")).title(),
                "last_name": self._clean_string(csv_row.get("last_name", "")).title(),
                "email": self._clean_string(csv_row.get("email", "")).lower(),
                "phone_number": self._clean_phone(csv_row.get("phone_number", "")),
                "joining_date": self._parse_date(csv_row.get("joining_date")),
                "qualification": self._clean_string(csv_row.get("qualification", "")),
                "experience_years": self._parse_decimal(
                    csv_row.get("experience_years", "0")
                ),
                "specialization": self._clean_string(
                    csv_row.get("specialization", "")
                ).title(),
                "department_name": self._clean_string(csv_row.get("department", "")),
                "position": self._clean_string(csv_row.get("position", "")),
                "salary": self._parse_decimal(csv_row.get("salary", "0")),
                "contract_type": self._normalize_contract_type(
                    csv_row.get("contract_type", "Permanent")
                ),
                "status": self._normalize_status(csv_row.get("status", "Active")),
                "bio": self._clean_text(csv_row.get("bio", "")),
                "emergency_contact": self._clean_string(
                    csv_row.get("emergency_contact", "")
                ),
                "emergency_phone": self._clean_phone(
                    csv_row.get("emergency_phone", "")
                ),
            }
        except Exception as e:
            self.errors.append(f"Error transforming row: {str(e)}")
            return None

    def _clean_string(self, value: str) -> str:
        """Clean and normalize string values."""
        if not value:
            return ""
        return str(value).strip()

    def _clean_text(self, value: str) -> str:
        """Clean longer text fields."""
        if not value:
            return ""
        # Remove extra whitespace
        return " ".join(str(value).split())

    def _clean_phone(self, value: str) -> str:
        """Clean phone number."""
        if not value:
            return ""
        # Remove common formatting characters
        cleaned = "".join(c for c in str(value) if c.isdigit() or c == "+")
        return cleaned if len(cleaned) >= 10 else ""

    def _parse_date(self, value: str) -> Optional[date]:
        """Parse date from various formats."""
        if not value:
            return None

        date_formats = ["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y"]

        for fmt in date_formats:
            try:
                return datetime.strptime(str(value).strip(), fmt).date()
            except ValueError:
                continue

        self.warnings.append(f"Could not parse date: {value}")
        return None

    def _parse_decimal(self, value: str) -> Decimal:
        """Parse decimal value."""
        if not value:
            return Decimal("0")

        try:
            # Remove commas and currency symbols
            cleaned = str(value).replace(",", "").replace("$", "").strip()
            return Decimal(cleaned)
        except:
            self.warnings.append(f"Could not parse decimal: {value}")
            return Decimal("0")

    def _normalize_contract_type(self, value: str) -> str:
        """Normalize contract type values."""
        if not value:
            return "Permanent"

        value = str(value).strip().lower()

        if value in ["permanent", "perm", "full-time"]:
            return "Permanent"
        elif value in ["temporary", "temp", "part-time"]:
            return "Temporary"
        elif value in ["contract", "contractor", "freelance"]:
            return "Contract"
        else:
            self.warnings.append(
                f"Unknown contract type: {value}, defaulting to Permanent"
            )
            return "Permanent"

    def _normalize_status(self, value: str) -> str:
        """Normalize status values."""
        if not value:
            return "Active"

        value = str(value).strip().lower()

        if value in ["active", "employed", "working"]:
            return "Active"
        elif value in ["leave", "on leave", "on_leave", "absent"]:
            return "On Leave"
        elif value in ["terminated", "fired", "resigned", "left", "inactive"]:
            return "Terminated"
        else:
            self.warnings.append(f"Unknown status: {value}, defaulting to Active")
            return "Active"


class TeacherDataValidator:
    """Validate teacher data during migration."""

    def __init__(self):
        self.validation_results = []

    def validate_batch(self, teacher_data_list: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Validate a batch of teacher data."""
        valid_records = []
        invalid_records = []

        for i, data in enumerate(teacher_data_list):
            try:
                validated_data = validate_teacher_data(data)
                valid_records.append({"index": i, "data": validated_data, "errors": []})
            except ValidationError as e:
                invalid_records.append(
                    {
                        "index": i,
                        "data": data,
                        "errors": (
                            e.message_dict if hasattr(e, "message_dict") else [str(e)]
                        ),
                    }
                )

        return {
            "valid_count": len(valid_records),
            "invalid_count": len(invalid_records),
            "valid_records": valid_records,
            "invalid_records": invalid_records,
            "success_rate": (
                len(valid_records) / len(teacher_data_list) * 100
                if teacher_data_list
                else 0
            ),
        }


class TeacherBackupManager:
    """Manage teacher data backups."""

    def create_backup(
        self, teachers_queryset, include_relations=True
    ) -> Dict[str, Any]:
        """Create a comprehensive backup of teacher data."""
        backup_data = {
            "metadata": {
                "created_at": datetime.now().isoformat(),
                "total_teachers": teachers_queryset.count(),
                "include_relations": include_relations,
                "version": "1.0",
            },
            "teachers": [],
        }

        for teacher in teachers_queryset.select_related("user", "department"):
            teacher_data = {
                "employee_id": teacher.employee_id,
                "user": {
                    "first_name": teacher.user.first_name,
                    "last_name": teacher.user.last_name,
                    "email": teacher.user.email,
                    "phone_number": getattr(teacher.user, "phone_number", ""),
                    "date_joined": teacher.user.date_joined.isoformat(),
                },
                "profile": {
                    "joining_date": (
                        teacher.joining_date.isoformat()
                        if teacher.joining_date
                        else None
                    ),
                    "qualification": teacher.qualification,
                    "experience_years": str(teacher.experience_years),
                    "specialization": teacher.specialization,
                    "department": (
                        teacher.department.name if teacher.department else None
                    ),
                    "position": teacher.position,
                    "salary": str(teacher.salary),
                    "contract_type": teacher.contract_type,
                    "status": teacher.status,
                    "bio": teacher.bio,
                    "emergency_contact": teacher.emergency_contact,
                    "emergency_phone": teacher.emergency_phone,
                    "created_at": teacher.created_at.isoformat(),
                    "updated_at": teacher.updated_at.isoformat(),
                },
            }

            if include_relations:
                # Include evaluations
                teacher_data["evaluations"] = [
                    {
                        "evaluation_date": eval.evaluation_date.isoformat(),
                        "score": float(eval.score),
                        "criteria": eval.criteria,
                        "remarks": eval.remarks,
                        "followup_actions": eval.followup_actions,
                        "status": eval.status,
                        "followup_date": (
                            eval.followup_date.isoformat()
                            if eval.followup_date
                            else None
                        ),
                        "evaluator_email": eval.evaluator.email,
                    }
                    for eval in teacher.evaluations.select_related("evaluator")
                ]

                # Include assignments
                teacher_data["assignments"] = [
                    {
                        "class_name": str(assignment.class_instance),
                        "subject_name": assignment.subject.name,
                        "subject_code": assignment.subject.code,
                        "academic_year": assignment.academic_year.name,
                        "is_class_teacher": assignment.is_class_teacher,
                        "notes": assignment.notes,
                        "created_at": assignment.created_at.isoformat(),
                    }
                    for assignment in teacher.class_assignments.select_related(
                        "class_instance", "subject", "academic_year"
                    )
                ]

            backup_data["teachers"].append(teacher_data)

        return backup_data

    def restore_from_backup(
        self, backup_data: Dict[str, Any], overwrite_existing=False
    ) -> Dict[str, Any]:
        """Restore teacher data from backup."""
        results = {
            "restored_count": 0,
            "skipped_count": 0,
            "error_count": 0,
            "errors": [],
        }

        for teacher_data in backup_data.get("teachers", []):
            try:
                # This would implement the actual restoration logic
                # For now, just track what would be restored
                employee_id = teacher_data.get("employee_id")

                if Teacher.objects.filter(employee_id=employee_id).exists():
                    if overwrite_existing:
                        results["restored_count"] += 1
                    else:
                        results["skipped_count"] += 1
                else:
                    results["restored_count"] += 1

            except Exception as e:
                results["error_count"] += 1
                results["errors"].append(
                    f"Error restoring {teacher_data.get('employee_id')}: {str(e)}"
                )

        return results
