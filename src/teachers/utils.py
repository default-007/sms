# src/teachers/utils.py
import csv
import io
import json
import logging
import re
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Union

import xlsxwriter
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db.models import Avg, Count, Q, Sum
from django.http import HttpResponse, JsonResponse
from django.utils import timezone

from src.courses.models import AcademicYear, Class, Department, Subject
from src.teachers.models import Teacher, TeacherClassAssignment, TeacherEvaluation

User = get_user_model()
logger = logging.getLogger(__name__)


class TeacherExportMixin:
    """Mixin for exporting teacher data in various formats."""

    def export_teachers_csv(self, queryset, filename=None):
        """Export teachers to CSV format."""
        if not filename:
            filename = f"teachers_export_{timezone.now().strftime('%Y%m%d_%H%M%S')}.csv"

        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'

        writer = csv.writer(response)

        # Header row
        headers = [
            "Employee ID",
            "First Name",
            "Last Name",
            "Email",
            "Phone",
            "Department",
            "Position",
            "Status",
            "Contract Type",
            "Experience (Years)",
            "Joining Date",
            "Salary",
            "Qualification",
            "Specialization",
            "Average Evaluation Score",
            "Total Evaluations",
        ]
        writer.writerow(headers)

        # Data rows
        for teacher in queryset.select_related("user", "department"):
            avg_score = teacher.get_average_evaluation_score()
            eval_count = teacher.evaluations.count()

            row = [
                teacher.employee_id,
                teacher.user.first_name,
                teacher.user.last_name,
                teacher.user.email,
                getattr(teacher.user, "phone_number", ""),
                teacher.department.name if teacher.department else "",
                teacher.position,
                teacher.status,
                teacher.contract_type,
                teacher.experience_years,
                teacher.joining_date.strftime("%Y-%m-%d"),
                teacher.salary,
                teacher.qualification,
                teacher.specialization,
                f"{avg_score:.1f}" if avg_score else "",
                eval_count,
            ]
            writer.writerow(row)

        return response

    def export_teachers_excel(self, queryset, filename=None):
        """Export teachers to Excel format."""
        if not filename:
            filename = (
                f"teachers_export_{timezone.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            )

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {"in_memory": True})

        # Create worksheets
        main_sheet = workbook.add_worksheet("Teachers")
        summary_sheet = workbook.add_worksheet("Summary")

        # Define formats
        header_format = workbook.add_format(
            {"bold": True, "bg_color": "#4472C4", "font_color": "white", "border": 1}
        )

        data_format = workbook.add_format({"border": 1, "align": "left"})

        number_format = workbook.add_format({"border": 1, "num_format": "#,##0.00"})

        # Main sheet headers
        headers = [
            "Employee ID",
            "Name",
            "Email",
            "Department",
            "Position",
            "Status",
            "Contract Type",
            "Experience",
            "Joining Date",
            "Salary",
            "Qualification",
            "Avg Score",
            "Evaluations",
        ]

        for col, header in enumerate(headers):
            main_sheet.write(0, col, header, header_format)

        # Main sheet data
        for row, teacher in enumerate(queryset.select_related("user", "department"), 1):
            avg_score = teacher.get_average_evaluation_score()
            eval_count = teacher.evaluations.count()

            main_sheet.write(row, 0, teacher.employee_id, data_format)
            main_sheet.write(row, 1, teacher.get_full_name(), data_format)
            main_sheet.write(row, 2, teacher.user.email, data_format)
            main_sheet.write(
                row,
                3,
                teacher.department.name if teacher.department else "",
                data_format,
            )
            main_sheet.write(row, 4, teacher.position, data_format)
            main_sheet.write(row, 5, teacher.status, data_format)
            main_sheet.write(row, 6, teacher.contract_type, data_format)
            main_sheet.write(row, 7, float(teacher.experience_years), number_format)
            main_sheet.write(
                row, 8, teacher.joining_date.strftime("%Y-%m-%d"), data_format
            )
            main_sheet.write(row, 9, float(teacher.salary), number_format)
            main_sheet.write(row, 10, teacher.qualification, data_format)
            main_sheet.write(
                row, 11, float(avg_score) if avg_score else 0, number_format
            )
            main_sheet.write(row, 12, eval_count, data_format)

        # Summary sheet
        summary_data = self._generate_teacher_summary(queryset)

        summary_sheet.write(0, 0, "Teacher Summary Report", header_format)
        summary_sheet.write(
            1, 0, f'Generated: {timezone.now().strftime("%Y-%m-%d %H:%M")}', data_format
        )

        row = 3
        for key, value in summary_data.items():
            summary_sheet.write(row, 0, key, data_format)
            summary_sheet.write(row, 1, value, data_format)
            row += 1

        # Auto-adjust column widths
        for sheet in [main_sheet, summary_sheet]:
            for col in range(len(headers)):
                sheet.set_column(col, col, 15)

        workbook.close()
        output.seek(0)

        response = HttpResponse(
            output.read(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = f'attachment; filename="{filename}"'

        return response

    def _generate_teacher_summary(self, queryset):
        """Generate summary statistics for teachers."""
        total_teachers = queryset.count()

        summary = {
            "Total Teachers": total_teachers,
            "Active Teachers": queryset.filter(status="Active").count(),
            "On Leave": queryset.filter(status="On Leave").count(),
            "Terminated": queryset.filter(status="Terminated").count(),
            "Permanent Staff": queryset.filter(contract_type="Permanent").count(),
            "Temporary Staff": queryset.filter(contract_type="Temporary").count(),
            "Contract Staff": queryset.filter(contract_type="Contract").count(),
        }

        # Add averages
        aggregates = queryset.aggregate(
            avg_experience=Avg("experience_years"),
            avg_salary=Avg("salary"),
            avg_evaluation_score=Avg("evaluations__score"),
        )

        summary.update(
            {
                "Average Experience (Years)": (
                    f"{aggregates['avg_experience']:.1f}"
                    if aggregates["avg_experience"]
                    else "N/A"
                ),
                "Average Salary": (
                    f"{aggregates['avg_salary']:,.2f}"
                    if aggregates["avg_salary"]
                    else "N/A"
                ),
                "Average Evaluation Score": (
                    f"{aggregates['avg_evaluation_score']:.1f}%"
                    if aggregates["avg_evaluation_score"]
                    else "N/A"
                ),
            }
        )

        return summary


class TeacherValidationMixin:
    """Mixin for common teacher validation logic."""

    def validate_employee_id(self, employee_id, teacher_id=None):
        """Validate employee ID uniqueness and format."""
        # Check format (assuming T followed by 6 digits)
        if not re.match(r"^T\d{6}$", employee_id):
            raise ValidationError("Employee ID must be in format T######")

        # Check uniqueness
        existing = Teacher.objects.filter(employee_id=employee_id)
        if teacher_id:
            existing = existing.exclude(id=teacher_id)

        if existing.exists():
            raise ValidationError("Employee ID already exists")

        return employee_id

    def validate_teacher_email(self, email, user_id=None):
        """Validate teacher email uniqueness."""
        existing = User.objects.filter(email=email)
        if user_id:
            existing = existing.exclude(id=user_id)

        if existing.exists():
            raise ValidationError("Email already exists")

        return email

    def validate_evaluation_criteria(self, criteria):
        """Validate evaluation criteria structure."""
        if not isinstance(criteria, dict):
            raise ValidationError("Criteria must be a dictionary")

        required_categories = [
            "teaching_methodology",
            "subject_knowledge",
            "classroom_management",
            "student_engagement",
            "professional_conduct",
        ]

        for category in required_categories:
            if category not in criteria:
                raise ValidationError(f"Missing required criterion: {category}")

            criterion_data = criteria[category]
            if not isinstance(criterion_data, dict):
                raise ValidationError(f"Invalid data for criterion: {category}")

            if "score" not in criterion_data or "max_score" not in criterion_data:
                raise ValidationError(
                    f"Criterion {category} must have 'score' and 'max_score'"
                )

            try:
                score = float(criterion_data["score"])
                max_score = float(criterion_data["max_score"])

                if score < 0 or score > max_score:
                    raise ValidationError(
                        f"Score for {category} must be between 0 and {max_score}"
                    )
            except (ValueError, TypeError):
                raise ValidationError(f"Invalid score values for criterion: {category}")

        return criteria

    def validate_assignment_constraints(
        self, teacher, class_instance, subject, academic_year, assignment_id=None
    ):
        """Validate teacher class assignment constraints."""
        # Check if assignment already exists
        existing = TeacherClassAssignment.objects.filter(
            teacher=teacher,
            class_instance=class_instance,
            subject=subject,
            academic_year=academic_year,
        )

        if assignment_id:
            existing = existing.exclude(id=assignment_id)

        if existing.exists():
            raise ValidationError(
                "Teacher is already assigned to this class and subject"
            )

        # Check teacher workload (example: max 8 classes per teacher)
        current_assignments = TeacherClassAssignment.objects.filter(
            teacher=teacher, academic_year=academic_year
        ).count()

        if assignment_id is None and current_assignments >= 8:
            raise ValidationError(
                "Teacher already has maximum number of class assignments (8)"
            )

        # Check if teacher is qualified for the subject
        if not self._is_teacher_qualified_for_subject(teacher, subject):
            raise ValidationError(f"Teacher is not qualified to teach {subject.name}")

        return True

    def _is_teacher_qualified_for_subject(self, teacher, subject):
        """Check if teacher is qualified to teach a specific subject."""
        # Simple qualification check based on specialization
        teacher_specialization = teacher.specialization.lower()
        subject_name = subject.name.lower()

        # Basic matching logic (this could be more sophisticated)
        qualification_map = {
            "mathematics": ["math", "mathematics", "algebra", "geometry", "calculus"],
            "science": ["science", "physics", "chemistry", "biology"],
            "english": ["english", "language", "literature"],
            "history": ["history", "social studies", "civics"],
            "geography": ["geography", "social studies"],
            "computer science": ["computer", "programming", "technology", "it"],
            "art": ["art", "drawing", "painting", "visual arts"],
            "music": ["music", "singing", "instruments"],
            "physical education": ["physical education", "sports", "pe", "fitness"],
        }

        for subject_area, keywords in qualification_map.items():
            if any(keyword in subject_name for keyword in keywords):
                if any(keyword in teacher_specialization for keyword in keywords):
                    return True

        # Default to True for flexibility (can be made stricter)
        return True


class TeacherReportMixin:
    """Mixin for generating teacher reports."""

    def generate_teacher_performance_report(
        self, queryset, academic_year=None, department=None
    ):
        """Generate comprehensive teacher performance report."""
        report_data = {
            "generation_date": timezone.now(),
            "academic_year": academic_year.name if academic_year else "All Years",
            "department": department.name if department else "All Departments",
            "total_teachers": queryset.count(),
            "teachers": [],
        }

        for teacher in queryset.select_related("user", "department"):
            # Get evaluations
            evaluations = teacher.evaluations.all()
            if academic_year:
                evaluations = evaluations.filter(
                    evaluation_date__year=academic_year.start_date.year
                )

            # Calculate metrics
            avg_score = evaluations.aggregate(avg=Avg("score"))["avg"]
            latest_evaluation = evaluations.order_by("-evaluation_date").first()

            # Get assignments
            assignments = teacher.class_assignments.all()
            if academic_year:
                assignments = assignments.filter(academic_year=academic_year)

            teacher_data = {
                "id": teacher.id,
                "employee_id": teacher.employee_id,
                "name": teacher.get_full_name(),
                "department": teacher.department.name if teacher.department else "N/A",
                "position": teacher.position,
                "experience_years": float(teacher.experience_years),
                "avg_evaluation_score": float(avg_score) if avg_score else None,
                "total_evaluations": evaluations.count(),
                "latest_evaluation_date": (
                    latest_evaluation.evaluation_date if latest_evaluation else None
                ),
                "latest_evaluation_score": (
                    float(latest_evaluation.score) if latest_evaluation else None
                ),
                "total_assignments": assignments.count(),
                "is_class_teacher": assignments.filter(is_class_teacher=True).exists(),
                "performance_level": (
                    self._get_performance_level(avg_score)
                    if avg_score
                    else "Not Evaluated"
                ),
            }

            report_data["teachers"].append(teacher_data)

        # Add summary statistics
        report_data["summary"] = self._calculate_performance_summary(
            report_data["teachers"]
        )

        return report_data

    def _get_performance_level(self, score):
        """Get performance level based on score."""
        if score >= 90:
            return "Excellent"
        elif score >= 80:
            return "Good"
        elif score >= 70:
            return "Satisfactory"
        elif score >= 60:
            return "Needs Improvement"
        else:
            return "Poor"

    def _calculate_performance_summary(self, teachers_data):
        """Calculate summary statistics for performance report."""
        if not teachers_data:
            return {}

        evaluated_teachers = [
            t for t in teachers_data if t["avg_evaluation_score"] is not None
        ]

        if not evaluated_teachers:
            return {"message": "No teachers have been evaluated"}

        scores = [t["avg_evaluation_score"] for t in evaluated_teachers]

        # Performance distribution
        excellent = len(
            [t for t in evaluated_teachers if t["avg_evaluation_score"] >= 90]
        )
        good = len(
            [t for t in evaluated_teachers if 80 <= t["avg_evaluation_score"] < 90]
        )
        satisfactory = len(
            [t for t in evaluated_teachers if 70 <= t["avg_evaluation_score"] < 80]
        )
        needs_improvement = len(
            [t for t in evaluated_teachers if 60 <= t["avg_evaluation_score"] < 70]
        )
        poor = len([t for t in evaluated_teachers if t["avg_evaluation_score"] < 60])

        return {
            "total_evaluated": len(evaluated_teachers),
            "average_score": sum(scores) / len(scores),
            "highest_score": max(scores),
            "lowest_score": min(scores),
            "performance_distribution": {
                "excellent": excellent,
                "good": good,
                "satisfactory": satisfactory,
                "needs_improvement": needs_improvement,
                "poor": poor,
            },
            "class_teachers": len([t for t in teachers_data if t["is_class_teacher"]]),
        }


class TeacherAnalyticsMixin:
    """Mixin for teacher analytics functionality."""

    def get_teacher_metrics(self, teacher_id, months=12):
        """Get comprehensive metrics for a specific teacher."""
        try:
            teacher = Teacher.objects.get(id=teacher_id)
        except Teacher.DoesNotExist:
            return None

        start_date = timezone.now().date() - timedelta(days=30 * months)

        # Get evaluations
        evaluations = teacher.evaluations.filter(evaluation_date__gte=start_date)

        # Get assignments
        current_year = AcademicYear.objects.filter(is_current=True).first()
        assignments = (
            teacher.class_assignments.filter(academic_year=current_year)
            if current_year
            else []
        )

        metrics = {
            "teacher_info": {
                "id": teacher.id,
                "name": teacher.get_full_name(),
                "employee_id": teacher.employee_id,
                "department": teacher.department.name if teacher.department else None,
                "experience_years": float(teacher.experience_years),
                "joining_date": teacher.joining_date,
                "years_of_service": teacher.get_years_of_service(),
            },
            "evaluation_metrics": {
                "total_evaluations": evaluations.count(),
                "average_score": evaluations.aggregate(avg=Avg("score"))["avg"],
                "latest_score": (
                    evaluations.order_by("-evaluation_date").first().score
                    if evaluations.exists()
                    else None
                ),
                "score_trend": self._calculate_score_trend(evaluations),
                "performance_consistency": self._calculate_consistency(evaluations),
            },
            "workload_metrics": {
                "total_assignments": assignments.count() if assignments else 0,
                "unique_subjects": (
                    assignments.values("subject").distinct().count()
                    if assignments
                    else 0
                ),
                "unique_classes": (
                    assignments.values("class_instance").distinct().count()
                    if assignments
                    else 0
                ),
                "is_class_teacher": (
                    assignments.filter(is_class_teacher=True).exists()
                    if assignments
                    else False
                ),
            },
        }

        return metrics

    def _calculate_score_trend(self, evaluations):
        """Calculate score trend (improving, stable, declining)."""
        if evaluations.count() < 2:
            return "Insufficient Data"

        scores = list(
            evaluations.order_by("evaluation_date").values_list("score", flat=True)
        )

        # Simple linear trend calculation
        if len(scores) >= 3:
            recent_avg = sum(scores[-2:]) / 2
            older_avg = sum(scores[:-2]) / len(scores[:-2])

            if recent_avg > older_avg + 5:
                return "Improving"
            elif recent_avg < older_avg - 5:
                return "Declining"
            else:
                return "Stable"
        else:
            if scores[-1] > scores[0]:
                return "Improving"
            elif scores[-1] < scores[0]:
                return "Declining"
            else:
                return "Stable"

    def _calculate_consistency(self, evaluations):
        """Calculate performance consistency score."""
        if evaluations.count() < 2:
            return None

        scores = list(evaluations.values_list("score", flat=True))
        avg_score = sum(scores) / len(scores)
        variance = sum((score - avg_score) ** 2 for score in scores) / len(scores)
        std_deviation = variance**0.5

        # Consistency score (0-100, higher is more consistent)
        consistency = max(0, 100 - (std_deviation * 2))
        return round(consistency, 2)


# Utility functions


def get_teacher_by_user(user):
    """Get teacher instance for a user."""
    try:
        return user.teacher_profile
    except AttributeError:
        return None


def is_teacher(user):
    """Check if user is a teacher."""
    return hasattr(user, "teacher_profile")


def get_teachers_by_department(department_id):
    """Get all teachers in a specific department."""
    return Teacher.objects.filter(
        department_id=department_id, status="Active"
    ).select_related("user", "department")


def get_teachers_by_subject(subject_id, academic_year=None):
    """Get teachers who teach a specific subject."""
    if not academic_year:
        academic_year = AcademicYear.objects.filter(is_current=True).first()

    if not academic_year:
        return Teacher.objects.none()

    return (
        Teacher.objects.filter(
            class_assignments__subject_id=subject_id,
            class_assignments__academic_year=academic_year,
            status="Active",
        )
        .distinct()
        .select_related("user", "department")
    )


def calculate_teacher_workload_score(teacher, academic_year=None):
    """Calculate workload score for a teacher (0-100)."""
    if not academic_year:
        academic_year = AcademicYear.objects.filter(is_current=True).first()

    if not academic_year:
        return 0

    assignments = teacher.class_assignments.filter(academic_year=academic_year)

    # Calculate workload factors
    class_count = assignments.values("class_instance").distinct().count()
    subject_count = assignments.values("subject").distinct().count()
    is_class_teacher = assignments.filter(is_class_teacher=True).exists()

    # Simple scoring algorithm (can be refined)
    score = min(
        100, (class_count * 10) + (subject_count * 5) + (20 if is_class_teacher else 0)
    )

    return score


def get_teacher_availability(teacher, date_obj=None):
    """Check teacher availability for a specific date."""
    if not date_obj:
        date_obj = timezone.now().date()

    # Check if teacher is on leave (this would require a leave model)
    # For now, just check if teacher is active
    if teacher.status != "Active":
        return False

    # Check timetable availability (this would require timetable integration)
    # For now, return True for active teachers
    return True


def format_teacher_name(teacher, format_type="full"):
    """Format teacher name in various ways."""
    if format_type == "full":
        return teacher.get_full_name()
    elif format_type == "short":
        return teacher.get_short_name()
    elif format_type == "formal":
        return f"Mr./Ms. {teacher.user.last_name}"
    elif format_type == "with_title":
        title = "Dr." if "phd" in teacher.qualification.lower() else "Mr./Ms."
        return f"{title} {teacher.get_full_name()}"
    else:
        return teacher.get_full_name()


def send_teacher_notification(
    teacher, title, message, notification_type="General", priority="Medium"
):
    """Send notification to a teacher."""
    from src.communications.models import Notification

    try:
        notification = Notification.objects.create(
            user=teacher.user,
            title=title,
            content=message,
            notification_type=notification_type,
            priority=priority,
        )
        return notification
    except Exception as e:
        logger.error(f"Failed to send notification to teacher {teacher.id}: {str(e)}")
        return None


def bulk_update_teachers(teacher_updates, updated_by):
    """Bulk update multiple teachers."""
    from src.core.models import AuditLog

    updated_count = 0
    errors = []

    for update_data in teacher_updates:
        try:
            teacher_id = update_data.pop("id")
            teacher = Teacher.objects.get(id=teacher_id)

            # Store old data for audit
            old_data = {
                "status": teacher.status,
                "position": teacher.position,
                "salary": teacher.salary,
            }

            # Update teacher
            for field, value in update_data.items():
                if hasattr(teacher, field):
                    setattr(teacher, field, value)

            teacher.save()
            updated_count += 1

            # Create audit log
            AuditLog.objects.create(
                user=updated_by,
                action="BULK_UPDATE",
                entity_type="Teacher",
                entity_id=teacher.id,
                data_before=old_data,
                data_after=update_data,
            )

        except Exception as e:
            errors.append({"teacher_id": update_data.get("id"), "error": str(e)})

    return {"updated_count": updated_count, "errors": errors}


class TeacherSearchHelper:
    """Helper class for advanced teacher search functionality."""

    @staticmethod
    def search_teachers(query, filters=None):
        """Advanced teacher search with multiple criteria."""
        queryset = Teacher.objects.select_related("user", "department")

        # Text search
        if query:
            queryset = queryset.filter(
                Q(user__first_name__icontains=query)
                | Q(user__last_name__icontains=query)
                | Q(employee_id__icontains=query)
                | Q(user__email__icontains=query)
                | Q(specialization__icontains=query)
                | Q(qualification__icontains=query)
                | Q(position__icontains=query)
            )

        # Apply filters
        if filters:
            if "department" in filters:
                queryset = queryset.filter(department_id=filters["department"])

            if "status" in filters:
                queryset = queryset.filter(status=filters["status"])

            if "contract_type" in filters:
                queryset = queryset.filter(contract_type=filters["contract_type"])

            if "experience_min" in filters:
                queryset = queryset.filter(
                    experience_years__gte=filters["experience_min"]
                )

            if "experience_max" in filters:
                queryset = queryset.filter(
                    experience_years__lte=filters["experience_max"]
                )

        return queryset.distinct()

    @staticmethod
    def get_search_suggestions(query, limit=10):
        """Get search suggestions based on partial query."""
        suggestions = []

        if len(query) >= 2:
            # Name suggestions
            names = Teacher.objects.filter(
                Q(user__first_name__icontains=query)
                | Q(user__last_name__icontains=query)
            ).values_list("user__first_name", "user__last_name")[: limit // 2]

            suggestions.extend([f"{first} {last}" for first, last in names])

            # Employee ID suggestions
            employee_ids = Teacher.objects.filter(
                employee_id__icontains=query
            ).values_list("employee_id", flat=True)[: limit // 2]

            suggestions.extend(employee_ids)

        return suggestions[:limit]
