from django.db import models, transaction
from django.core.cache import cache
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from django.db.models import Avg, Sum, Count, Max, Min, Q, StdDev
from django.conf import settings
from decimal import Decimal
import json
import logging
from typing import Dict, Any, Optional, List, Union
from datetime import datetime, timedelta

from src.finance.models import FinancialAnalytics
from src.students.models import Student

from .models import (
    SystemSetting,
    AuditLog,
    StudentPerformanceAnalytics,
    ClassPerformanceAnalytics,
    AttendanceAnalytics,
    # FinancialAnalytics,
    TeacherPerformanceAnalytics,
    SystemHealthMetrics,
)

User = get_user_model()
logger = logging.getLogger(__name__)


class ConfigurationService:
    """Service for managing system configuration settings"""

    # Cache configuration settings for performance
    CACHE_TIMEOUT = 3600  # 1 hour
    CACHE_PREFIX = "system_setting_"

    @classmethod
    def get_setting(cls, key: str, default: Any = None, use_cache: bool = True) -> Any:
        """Get a system setting value with caching"""
        cache_key = f"{cls.CACHE_PREFIX}{key}"

        if use_cache:
            cached_value = cache.get(cache_key)
            if cached_value is not None:
                return cached_value

        try:
            setting = SystemSetting.objects.get(setting_key=key)
            value = setting.get_typed_value()

            if use_cache:
                cache.set(cache_key, value, cls.CACHE_TIMEOUT)

            return value
        except SystemSetting.DoesNotExist:
            return default

    @classmethod
    def set_setting(
        cls,
        key: str,
        value: Any,
        user: User = None,
        data_type: str = "string",
        category: str = "system",
        description: str = "",
        is_editable: bool = True,
    ) -> SystemSetting:
        """Set a system setting value"""
        setting, created = SystemSetting.objects.get_or_create(
            setting_key=key,
            defaults={
                "data_type": data_type,
                "category": category,
                "description": description,
                "is_editable": is_editable,
            },
        )

        setting.set_typed_value(value)
        setting.updated_by = user
        setting.save()

        # Clear cache
        cache_key = f"{cls.CACHE_PREFIX}{key}"
        cache.delete(cache_key)

        # Log the change
        AuditService.log_action(
            user=user,
            action="update",
            content_object=setting,
            description=f"Updated system setting: {key}",
            data_after={"key": key, "value": value},
        )

        return setting

    @classmethod
    def get_settings_by_category(cls, category: str) -> Dict[str, Any]:
        """Get all settings for a specific category"""
        settings = SystemSetting.objects.filter(category=category)
        return {setting.setting_key: setting.get_typed_value() for setting in settings}

    @classmethod
    def initialize_default_settings(cls):
        """Initialize default system settings"""
        defaults = {
            # Academic settings
            "academic.default_academic_year_start_month": (
                7,
                "integer",
                "academic",
                "Default start month for academic year (1-12)",
            ),
            "academic.terms_per_year": (
                3,
                "integer",
                "academic",
                "Number of terms per academic year",
            ),
            "academic.passing_grade_percentage": (
                40,
                "integer",
                "academic",
                "Minimum percentage for passing grade",
            ),
            "academic.max_students_per_class": (
                40,
                "integer",
                "academic",
                "Maximum students allowed per class",
            ),
            # Financial settings
            "finance.late_fee_percentage": (
                5,
                "integer",
                "financial",
                "Late fee percentage for overdue payments",
            ),
            "finance.grace_period_days": (
                7,
                "integer",
                "financial",
                "Grace period in days before late fee applies",
            ),
            "finance.currency_code": (
                "USD",
                "string",
                "financial",
                "Default currency code",
            ),
            "finance.invoice_due_days": (
                30,
                "integer",
                "financial",
                "Default invoice due period in days",
            ),
            # Communication settings
            "communication.email_notifications": (
                True,
                "boolean",
                "communication",
                "Enable email notifications",
            ),
            "communication.sms_notifications": (
                True,
                "boolean",
                "communication",
                "Enable SMS notifications",
            ),
            "communication.push_notifications": (
                True,
                "boolean",
                "communication",
                "Enable push notifications",
            ),
            # System settings
            "system.maintenance_mode": (
                False,
                "boolean",
                "system",
                "Enable maintenance mode",
            ),
            "system.max_file_upload_mb": (
                10,
                "integer",
                "system",
                "Maximum file upload size in MB",
            ),
            "system.session_timeout_minutes": (
                60,
                "integer",
                "system",
                "User session timeout in minutes",
            ),
            "system.auto_backup_enabled": (
                True,
                "boolean",
                "system",
                "Enable automatic database backups",
            ),
            # Analytics settings
            "analytics.auto_calculation_enabled": (
                True,
                "boolean",
                "analytics",
                "Enable automatic analytics calculation",
            ),
            "analytics.calculation_frequency_hours": (
                24,
                "integer",
                "analytics",
                "Analytics calculation frequency in hours",
            ),
            "analytics.retention_days": (
                365,
                "integer",
                "analytics",
                "Analytics data retention period in days",
            ),
        }

        for key, (value, data_type, category, description) in defaults.items():
            if not SystemSetting.objects.filter(setting_key=key).exists():
                cls.set_setting(
                    key, value, None, data_type, category, description, True
                )


class AuditService:
    """Service for comprehensive audit logging"""

    @classmethod
    def log_action(
        cls,
        user: User = None,
        action: str = "view",
        content_object: models.Model = None,
        description: str = "",
        data_before: Dict = None,
        data_after: Dict = None,
        ip_address: str = None,
        user_agent: str = "",
        session_key: str = "",
        module_name: str = "",
        view_name: str = "",
        duration_ms: int = None,
    ) -> AuditLog:
        """Log an audit entry"""

        content_type = None
        object_id = None

        if content_object:
            content_type = ContentType.objects.get_for_model(content_object)
            object_id = content_object.pk

        audit_log = AuditLog.objects.create(
            user=user,
            action=action,
            content_type=content_type,
            object_id=object_id,
            data_before=data_before,
            data_after=data_after,
            ip_address=ip_address,
            user_agent=user_agent,
            session_key=session_key,
            description=description,
            module_name=module_name,
            view_name=view_name,
            duration_ms=duration_ms,
        )

        return audit_log

    @classmethod
    def log_login(
        cls,
        user: User,
        ip_address: str = None,
        user_agent: str = "",
        session_key: str = "",
    ) -> AuditLog:
        """Log user login"""
        return cls.log_action(
            user=user,
            action="login",
            description=f"User {user.username} logged in",
            ip_address=ip_address,
            user_agent=user_agent,
            session_key=session_key,
            module_name="accounts",
        )

    @classmethod
    def log_logout(
        cls,
        user: User,
        ip_address: str = None,
        user_agent: str = "",
        session_key: str = "",
    ) -> AuditLog:
        """Log user logout"""
        return cls.log_action(
            user=user,
            action="logout",
            description=f"User {user.username} logged out",
            ip_address=ip_address,
            user_agent=user_agent,
            session_key=session_key,
            module_name="accounts",
        )

    @classmethod
    def get_user_activity(cls, user: User, days: int = 30) -> models.QuerySet:
        """Get user activity for the last N days"""
        since = timezone.now() - timedelta(days=days)
        return AuditLog.objects.filter(user=user, timestamp__gte=since).order_by(
            "-timestamp"
        )

    @classmethod
    def get_object_history(cls, obj: models.Model) -> models.QuerySet:
        """Get audit history for a specific object"""
        content_type = ContentType.objects.get_for_model(obj)
        return AuditLog.objects.filter(
            content_type=content_type, object_id=obj.pk
        ).order_by("-timestamp")

    @classmethod
    def cleanup_old_logs(cls, days: int = 365):
        """Clean up audit logs older than specified days"""
        cutoff_date = timezone.now() - timedelta(days=days)
        deleted_count = AuditLog.objects.filter(timestamp__lt=cutoff_date).delete()[0]
        logger.info(f"Cleaned up {deleted_count} old audit logs")
        return deleted_count


class AnalyticsService:
    """Service for calculating and managing analytics"""

    @classmethod
    def calculate_student_performance(
        cls, academic_year=None, term=None, student=None, force_recalculate=False
    ):
        """Calculate student performance analytics"""
        from students.models import Student
        from exams.models import StudentExamResult
        from assignments.models import AssignmentSubmission
        from attendance.models import Attendance

        # Get students to calculate for
        students_query = Student.objects.filter(status="active")
        if student:
            students_query = students_query.filter(id=student.id)

        # Get current academic year/term if not specified
        if not academic_year:
            from academics.models import AcademicYear

            academic_year = AcademicYear.objects.filter(is_current=True).first()

        if not term:
            from academics.models import Term

            term = Term.objects.filter(
                academic_year=academic_year, is_current=True
            ).first()

        if not academic_year or not term:
            logger.warning(
                "No current academic year or term found for analytics calculation"
            )
            return

        for student in students_query:
            try:
                with transaction.atomic():
                    # Check if analytics already exist and not forcing recalculation
                    if not force_recalculate:
                        existing = StudentPerformanceAnalytics.objects.filter(
                            student=student,
                            academic_year=academic_year,
                            term=term,
                            subject__isnull=True,  # Overall performance
                        ).exists()
                        if existing:
                            continue

                    # Calculate exam performance
                    exam_results = StudentExamResult.objects.filter(
                        student=student, term=term
                    )

                    exam_avg = exam_results.aggregate(
                        avg_marks=Avg("marks_obtained"),
                        max_marks=Max("marks_obtained"),
                        min_marks=Min("marks_obtained"),
                    )

                    # Calculate assignment performance
                    assignments = AssignmentSubmission.objects.filter(
                        student=student, assignment__term=term, status="graded"
                    )

                    assignment_stats = assignments.aggregate(
                        total_submitted=Count("id"),
                        on_time_count=Count(
                            "id",
                            filter=Q(
                                submission_date__lte=models.F("assignment__due_date")
                            ),
                        ),
                    )

                    total_assignments = assignments.count()
                    completion_rate = (
                        (assignment_stats["total_submitted"] / total_assignments * 100)
                        if total_assignments > 0
                        else 0
                    )
                    on_time_rate = (
                        (assignment_stats["on_time_count"] / total_assignments * 100)
                        if total_assignments > 0
                        else 0
                    )

                    # Calculate attendance
                    attendance_records = Attendance.objects.filter(
                        student=student, term=term
                    )

                    attendance_stats = attendance_records.aggregate(
                        total_days=Count("id"),
                        present_days=Count("id", filter=Q(status="present")),
                    )

                    attendance_percentage = (
                        attendance_stats["present_days"]
                        / attendance_stats["total_days"]
                        * 100
                        if attendance_stats["total_days"] > 0
                        else 0
                    )

                    # Calculate rankings (simplified - would need more complex logic for actual implementation)
                    class_ranking = cls._calculate_class_ranking(student, term)
                    grade_ranking = cls._calculate_grade_ranking(student, term)

                    # Create or update analytics record
                    analytics, created = (
                        StudentPerformanceAnalytics.objects.update_or_create(
                            student=student,
                            academic_year=academic_year,
                            term=term,
                            subject=None,  # Overall performance
                            defaults={
                                "average_marks": exam_avg["avg_marks"],
                                "highest_marks": exam_avg["max_marks"],
                                "lowest_marks": exam_avg["min_marks"],
                                "attendance_percentage": Decimal(
                                    str(attendance_percentage)
                                ),
                                "assignment_completion_rate": Decimal(
                                    str(completion_rate)
                                ),
                                "assignments_submitted": assignment_stats[
                                    "total_submitted"
                                ],
                                "assignments_on_time": assignment_stats[
                                    "on_time_count"
                                ],
                                "ranking_in_class": class_ranking,
                                "ranking_in_grade": grade_ranking,
                            },
                        )
                    )

                    logger.info(
                        f"Calculated performance analytics for student {student.id}"
                    )

            except Exception as e:
                logger.error(
                    f"Error calculating analytics for student {student.id}: {str(e)}"
                )

    @classmethod
    def calculate_class_performance(
        cls, academic_year=None, term=None, class_instance=None, force_recalculate=False
    ):
        """Calculate class performance analytics"""
        from academics.models import Class
        from students.models import Student
        from exams.models import StudentExamResult

        # Get classes to calculate for
        classes_query = Class.objects.all()
        if class_instance:
            classes_query = classes_query.filter(id=class_instance.id)

        # Get current academic year/term if not specified
        if not academic_year:
            from academics.models import AcademicYear

            academic_year = AcademicYear.objects.filter(is_current=True).first()

        if not term:
            from academics.models import Term

            term = Term.objects.filter(
                academic_year=academic_year, is_current=True
            ).first()

        if not academic_year or not term:
            return

        for class_obj in classes_query:
            try:
                with transaction.atomic():
                    # Check if analytics already exist
                    if not force_recalculate:
                        existing = ClassPerformanceAnalytics.objects.filter(
                            class_instance=class_obj,
                            academic_year=academic_year,
                            term=term,
                            subject__isnull=True,
                        ).exists()
                        if existing:
                            continue

                    # Get students in class
                    students = Student.objects.filter(
                        current_class=class_obj, status="active"
                    )

                    if not students.exists():
                        continue

                    # Calculate performance metrics
                    exam_results = StudentExamResult.objects.filter(
                        student__in=students, term=term
                    )

                    performance_stats = exam_results.aggregate(
                        class_avg=Avg("marks_obtained"),
                        highest=Max("marks_obtained"),
                        lowest=Min("marks_obtained"),
                        std_dev=StdDev("marks_obtained"),
                    )

                    # Calculate pass rate (assuming 40% is passing)
                    passing_threshold = ConfigurationService.get_setting(
                        "academic.passing_grade_percentage", 40
                    )
                    pass_count = exam_results.filter(
                        marks_obtained__gte=passing_threshold
                    ).count()
                    total_results = exam_results.count()
                    pass_rate = (
                        (pass_count / total_results * 100) if total_results > 0 else 0
                    )

                    # Student distribution
                    class_avg = performance_stats["class_avg"] or 0
                    above_avg = exam_results.filter(
                        marks_obtained__gt=class_avg
                    ).count()
                    below_avg = exam_results.filter(
                        marks_obtained__lt=class_avg
                    ).count()

                    # Create or update analytics record
                    analytics, created = (
                        ClassPerformanceAnalytics.objects.update_or_create(
                            class_instance=class_obj,
                            academic_year=academic_year,
                            term=term,
                            subject=None,
                            defaults={
                                "class_average": performance_stats["class_avg"],
                                "highest_score": performance_stats["highest"],
                                "lowest_score": performance_stats["lowest"],
                                "standard_deviation": performance_stats["std_dev"],
                                "total_students": students.count(),
                                "students_above_average": above_avg,
                                "students_below_average": below_avg,
                                "pass_rate": Decimal(str(pass_rate)),
                            },
                        )
                    )

                    logger.info(
                        f"Calculated class performance analytics for class {class_obj.id}"
                    )

            except Exception as e:
                logger.error(
                    f"Error calculating class analytics for {class_obj.id}: {str(e)}"
                )

    @classmethod
    def calculate_attendance_analytics(
        cls, academic_year=None, term=None, force_recalculate=False
    ):
        """Calculate attendance analytics for all entities"""
        from attendance.models import Attendance
        from students.models import Student
        from academics.models import Class, Grade, Section

        if not academic_year:
            from academics.models import AcademicYear

            academic_year = AcademicYear.objects.filter(is_current=True).first()

        if not term:
            from academics.models import Term

            term = Term.objects.filter(
                academic_year=academic_year, is_current=True
            ).first()

        if not academic_year or not term:
            return

        # Calculate for students
        students = Student.objects.filter(status="active")
        for student in students:
            cls._calculate_entity_attendance(
                "student",
                student.id,
                str(student),
                academic_year,
                term,
                force_recalculate,
            )

        # Calculate for classes
        classes = Class.objects.filter(academic_year=academic_year)
        for class_obj in classes:
            cls._calculate_entity_attendance(
                "class",
                class_obj.id,
                str(class_obj),
                academic_year,
                term,
                force_recalculate,
            )

        # Calculate for grades
        grades = Grade.objects.all()
        for grade in grades:
            cls._calculate_entity_attendance(
                "grade", grade.id, str(grade), academic_year, term, force_recalculate
            )

        # Calculate for sections
        sections = Section.objects.all()
        for section in sections:
            cls._calculate_entity_attendance(
                "section",
                section.id,
                str(section),
                academic_year,
                term,
                force_recalculate,
            )

    @classmethod
    def _calculate_entity_attendance(
        cls, entity_type, entity_id, entity_name, academic_year, term, force_recalculate
    ):
        """Helper method to calculate attendance for a specific entity"""
        from attendance.models import Attendance

        try:
            # Check if analytics already exist
            if not force_recalculate:
                existing = AttendanceAnalytics.objects.filter(
                    entity_type=entity_type,
                    entity_id=entity_id,
                    academic_year=academic_year,
                    term=term,
                ).exists()
                if existing:
                    return

            # Build attendance query based on entity type
            attendance_query = Attendance.objects.filter(term=term)

            if entity_type == "student":
                attendance_query = attendance_query.filter(student_id=entity_id)
            elif entity_type == "class":
                attendance_query = attendance_query.filter(class_id=entity_id)
            elif entity_type == "grade":
                attendance_query = attendance_query.filter(class__grade_id=entity_id)
            elif entity_type == "section":
                attendance_query = attendance_query.filter(
                    class__grade__section_id=entity_id
                )

            # Calculate attendance statistics
            stats = attendance_query.aggregate(
                total=Count("id"),
                present=Count("id", filter=Q(status="present")),
                absent=Count("id", filter=Q(status="absent")),
                late=Count("id", filter=Q(status="late")),
                excused=Count("id", filter=Q(status="excused")),
            )

            total_days = stats["total"] or 0
            present_days = stats["present"] or 0
            attendance_percentage = (
                (present_days / total_days * 100) if total_days > 0 else 0
            )

            # Create or update analytics record
            AttendanceAnalytics.objects.update_or_create(
                entity_type=entity_type,
                entity_id=entity_id,
                academic_year=academic_year,
                term=term,
                defaults={
                    "entity_name": entity_name,
                    "total_days": total_days,
                    "present_days": present_days,
                    "absent_days": stats["absent"] or 0,
                    "late_days": stats["late"] or 0,
                    "excused_days": stats["excused"] or 0,
                    "attendance_percentage": Decimal(str(attendance_percentage)),
                },
            )

        except Exception as e:
            logger.error(
                f"Error calculating attendance for {entity_type} {entity_id}: {str(e)}"
            )

    @classmethod
    def calculate_financial_analytics(
        cls, academic_year=None, term=None, force_recalculate=False
    ):
        """Calculate financial analytics"""
        from finance.models import Invoice, Payment, FeeStructure, SpecialFee
        from academics.models import Section, Grade

        if not academic_year:
            from academics.models import AcademicYear

            academic_year = AcademicYear.objects.filter(is_current=True).first()

        if not term:
            from academics.models import Term

            term = Term.objects.filter(
                academic_year=academic_year, is_current=True
            ).first()

        if not academic_year or not term:
            return

        # Calculate overall analytics
        cls._calculate_financial_summary(academic_year, term, force_recalculate)

        # Calculate by section
        sections = Section.objects.all()
        for section in sections:
            cls._calculate_financial_summary(
                academic_year, term, force_recalculate, section=section
            )

        # Calculate by grade
        grades = Grade.objects.all()
        for grade in grades:
            cls._calculate_financial_summary(
                academic_year, term, force_recalculate, grade=grade
            )

    @classmethod
    def _calculate_financial_summary(
        cls,
        academic_year,
        term,
        force_recalculate,
        section=None,
        grade=None,
        fee_category=None,
    ):
        """Helper method to calculate financial summary for specific filters"""
        from finance.models import Invoice, Payment
        from students.models import Student

        try:
            # Check if analytics already exist
            if not force_recalculate:
                existing = FinancialAnalytics.objects.filter(
                    academic_year=academic_year,
                    term=term,
                    section=section,
                    grade=grade,
                    fee_category=fee_category,
                ).exists()
                if existing:
                    return

            # Build student query based on filters
            students_query = Student.objects.filter(status="active")
            if section:
                students_query = students_query.filter(
                    current_class__grade__section=section
                )
            elif grade:
                students_query = students_query.filter(current_class__grade=grade)

            # Get invoices for the filtered students
            invoices = Invoice.objects.filter(
                academic_year=academic_year, term=term, student__in=students_query
            )

            # Calculate financial metrics
            financial_stats = invoices.aggregate(
                total_expected=Sum("total_amount"),
                total_collected=Sum("net_amount", filter=Q(status="paid")),
                total_outstanding=Sum(
                    "net_amount", filter=Q(status__in=["unpaid", "partially_paid"])
                ),
            )

            total_expected = financial_stats["total_expected"] or 0
            total_collected = financial_stats["total_collected"] or 0
            collection_rate = (
                (total_collected / total_expected * 100) if total_expected > 0 else 0
            )

            # Student payment statistics
            total_students = students_query.count()
            students_paid_full = (
                invoices.filter(status="paid").values("student").distinct().count()
            )
            students_with_outstanding = (
                invoices.filter(status__in=["unpaid", "partially_paid"])
                .values("student")
                .distinct()
                .count()
            )

            # Create or update analytics record
            FinancialAnalytics.objects.update_or_create(
                academic_year=academic_year,
                term=term,
                section=section,
                grade=grade,
                fee_category=fee_category,
                defaults={
                    "total_expected_revenue": total_expected,
                    "total_collected_revenue": total_collected,
                    "total_outstanding": financial_stats["total_outstanding"] or 0,
                    "collection_rate": Decimal(str(collection_rate)),
                    "total_students": total_students,
                    "students_paid_full": students_paid_full,
                    "students_with_outstanding": students_with_outstanding,
                },
            )

        except Exception as e:
            logger.error(f"Error calculating financial analytics: {str(e)}")

    @classmethod
    def _calculate_class_ranking(cls, student, term):
        """Calculate student's ranking within their class"""
        # This is a simplified implementation
        # In practice, you'd want more sophisticated ranking logic
        from exams.models import StudentExamResult

        class_students = Student.objects.filter(
            current_class=student.current_class, status="active"
        )

        # Get average marks for all students in class
        student_averages = []
        for class_student in class_students:
            avg_marks = StudentExamResult.objects.filter(
                student=class_student, term=term
            ).aggregate(avg=Avg("marks_obtained"))["avg"]

            if avg_marks:
                student_averages.append((class_student.id, avg_marks))

        # Sort by average marks (descending)
        student_averages.sort(key=lambda x: x[1], reverse=True)

        # Find student's position
        for i, (student_id, _) in enumerate(student_averages):
            if student_id == student.id:
                return i + 1

        return None

    @classmethod
    def _calculate_grade_ranking(cls, student, term):
        """Calculate student's ranking within their grade"""
        # Similar to class ranking but for entire grade
        from exams.models import StudentExamResult

        grade_students = Student.objects.filter(
            current_class__grade=student.current_class.grade, status="active"
        )

        student_averages = []
        for grade_student in grade_students:
            avg_marks = StudentExamResult.objects.filter(
                student=grade_student, term=term
            ).aggregate(avg=Avg("marks_obtained"))["avg"]

            if avg_marks:
                student_averages.append((grade_student.id, avg_marks))

        student_averages.sort(key=lambda x: x[1], reverse=True)

        for i, (student_id, _) in enumerate(student_averages):
            if student_id == student.id:
                return i + 1

        return None


class ValidationService:
    """Service for system-wide data validation"""

    @classmethod
    def validate_academic_structure(cls, section=None, grade=None, class_instance=None):
        """Validate academic structure relationships"""
        errors = []

        if grade and section:
            if grade.section != section:
                errors.append(f"Grade {grade} does not belong to section {section}")

        if class_instance and grade:
            if class_instance.grade != grade:
                errors.append(
                    f"Class {class_instance} does not belong to grade {grade}"
                )

        return errors

    @classmethod
    def validate_fee_structure(cls, fee_structure):
        """Validate fee structure configuration"""
        errors = []

        # Check for conflicting fee structures
        from finance.models import FeeStructure

        conflicting = FeeStructure.objects.filter(
            academic_year=fee_structure.academic_year,
            term=fee_structure.term,
            fee_category=fee_structure.fee_category,
            section=fee_structure.section,
            grade=fee_structure.grade,
        ).exclude(id=fee_structure.id if fee_structure.id else None)

        if conflicting.exists():
            errors.append("A fee structure with these parameters already exists")

        # Validate amount
        if fee_structure.amount <= 0:
            errors.append("Fee amount must be greater than zero")

        return errors

    @classmethod
    def validate_user_permissions(cls, user, required_permissions):
        """Validate user has required permissions"""
        if not user.is_authenticated:
            return ["User is not authenticated"]

        missing_permissions = []
        for permission in required_permissions:
            if not user.has_perm(permission):
                missing_permissions.append(permission)

        return missing_permissions


class SecurityService:
    """Service for security-related operations"""

    @classmethod
    def check_rate_limit(
        cls,
        user_identifier: str,
        action: str,
        max_attempts: int = 5,
        window_minutes: int = 15,
    ) -> bool:
        """Check if action is rate limited"""
        cache_key = f"rate_limit:{action}:{user_identifier}"
        current_time = timezone.now()

        # Get current attempts from cache
        attempts = cache.get(cache_key, [])

        # Remove attempts outside the window
        window_start = current_time - timedelta(minutes=window_minutes)
        attempts = [attempt for attempt in attempts if attempt > window_start]

        # Check if under limit
        if len(attempts) >= max_attempts:
            return False

        # Add current attempt
        attempts.append(current_time)
        cache.set(cache_key, attempts, timeout=window_minutes * 60)

        return True

    @classmethod
    def log_security_event(
        cls,
        event_type: str,
        user: User = None,
        ip_address: str = None,
        details: Dict = None,
    ):
        """Log security-related events"""
        AuditService.log_action(
            user=user,
            action="system_action",
            description=f"Security event: {event_type}",
            data_after={"event_type": event_type, "details": details},
            ip_address=ip_address,
            module_name="security",
        )

    @classmethod
    def validate_file_upload(cls, file, allowed_extensions=None, max_size_mb=None):
        """Validate file uploads for security"""
        errors = []

        if not file:
            return ["No file provided"]

        # Check file size
        max_size = max_size_mb or ConfigurationService.get_setting(
            "system.max_file_upload_mb", 10
        )
        if file.size > max_size * 1024 * 1024:
            errors.append(f"File size exceeds maximum allowed size of {max_size}MB")

        # Check file extension
        if allowed_extensions:
            file_extension = file.name.split(".")[-1].lower()
            if file_extension not in [ext.lower() for ext in allowed_extensions]:
                errors.append(f"File extension '{file_extension}' is not allowed")

        return errors


class UtilityService:
    """Service for common utility functions"""

    @classmethod
    def generate_unique_code(
        cls, model_class, field_name: str, prefix: str = "", length: int = 8
    ) -> str:
        """Generate a unique code for a model field"""
        import random
        import string

        while True:
            code = prefix + "".join(
                random.choices(string.ascii_uppercase + string.digits, k=length)
            )
            if not model_class.objects.filter(**{field_name: code}).exists():
                return code

    @classmethod
    def calculate_age(cls, birth_date: datetime) -> int:
        """Calculate age from birth date"""
        today = timezone.now().date()
        return (
            today.year
            - birth_date.year
            - ((today.month, today.day) < (birth_date.month, birth_date.day))
        )

    @classmethod
    def format_currency(cls, amount: Decimal, currency_code: str = None) -> str:
        """Format amount as currency"""
        if currency_code is None:
            currency_code = ConfigurationService.get_setting(
                "finance.currency_code", "USD"
            )

        # Simple formatting - in production you'd use proper locale formatting
        currency_symbols = {
            "USD": "$",
            "EUR": "€",
            "GBP": "£",
            "INR": "₹",
        }

        symbol = currency_symbols.get(currency_code, currency_code)
        return f"{symbol}{amount:,.2f}"

    @classmethod
    def sanitize_filename(cls, filename: str) -> str:
        """Sanitize filename for safe storage"""
        import re

        # Remove or replace unsafe characters
        filename = re.sub(r'[<>:"/\\|?*]', "_", filename)
        filename = filename.strip(". ")

        # Limit length
        if len(filename) > 255:
            name, ext = filename.rsplit(".", 1) if "." in filename else (filename, "")
            filename = name[: 255 - len(ext) - 1] + "." + ext if ext else name[:255]

        return filename

    @classmethod
    def calculate_working_days(
        cls, start_date: datetime, end_date: datetime, exclude_weekends: bool = True
    ) -> int:
        """Calculate working days between two dates"""
        from datetime import timedelta

        if start_date > end_date:
            return 0

        total_days = (end_date - start_date).days + 1

        if not exclude_weekends:
            return total_days

        # Count weekends
        weekends = 0
        current_date = start_date
        while current_date <= end_date:
            if current_date.weekday() >= 5:  # Saturday = 5, Sunday = 6
                weekends += 1
            current_date += timedelta(days=1)

        return total_days - weekends
