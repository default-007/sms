from datetime import datetime, timedelta

from django.db.models import Avg, Case, Count, F, IntegerField, Max, Q, Sum, Value, When
from django.db.models.functions import ExtractMonth, ExtractYear, TruncMonth
from django.utils import timezone

from src.academics.models import AcademicYear, Class, Department
from src.scheduling.services.timetable_service import TimetableService
from src.teachers.models import Teacher, TeacherClassAssignment, TeacherEvaluation


class TeacherService:
    """Service class for teacher-related operations."""

    @staticmethod
    def get_teacher_by_id(teacher_id):
        """Get a teacher by ID."""
        try:
            return Teacher.objects.get(id=teacher_id)
        except Teacher.DoesNotExist:
            return None

    @staticmethod
    def get_teacher_by_employee_id(employee_id):
        """Get a teacher by employee ID."""
        try:
            return Teacher.objects.get(employee_id=employee_id)
        except Teacher.DoesNotExist:
            return None

    @staticmethod
    def get_active_teachers():
        """Get all active teachers."""
        return Teacher.objects.active().select_related("user", "department")

    @staticmethod
    def get_teachers_by_department(department_id):
        """Get teachers by department."""
        return Teacher.objects.filter(department_id=department_id).select_related(
            "user", "department"
        )

    @staticmethod
    def get_class_teacher(class_id):
        """Get the class teacher for a specific class."""
        try:
            class_obj = Class.objects.get(id=class_id)
            return class_obj.class_teacher
        except Class.DoesNotExist:
            return None

    @staticmethod
    def get_teacher_timetable(teacher, academic_year=None):
        """Get the timetable for a specific teacher."""

        return TimetableService.get_teacher_timetable(
            teacher, academic_year=academic_year
        )

    @staticmethod
    def calculate_teacher_performance(teacher, year=None):
        """Calculate teacher performance based on evaluations."""
        if not year:
            year = timezone.now().year

        evaluations = TeacherEvaluation.objects.filter(
            teacher=teacher, evaluation_date__year=year
        )

        if not evaluations.exists():
            return None

        avg_score = evaluations.aggregate(Avg("score"))["score__avg"]
        return {
            "average_score": avg_score,
            "evaluation_count": evaluations.count(),
            "latest_evaluation": evaluations.order_by("-evaluation_date").first(),
            "trend": [
                {"date": e.evaluation_date, "score": float(e.score)}
                for e in evaluations.order_by("evaluation_date")
            ],
        }

    @staticmethod
    def get_top_performing_teachers(limit=10):
        """Get top performing teachers based on evaluation scores."""
        return (
            Teacher.objects.active()
            .with_evaluation_stats()
            .filter(avg_evaluation_score__isnull=False)
            .order_by("-avg_evaluation_score")[:limit]
        )

    @staticmethod
    def get_teacher_workload(academic_year=None):
        """Get teacher workload distribution."""
        if not academic_year:
            academic_year = AcademicYear.objects.filter(is_current=True).first()

        return (
            Teacher.objects.active()
            .annotate(
                class_count=Count(
                    "class_assignments",
                    filter=Q(class_assignments__academic_year=academic_year),
                    distinct=True,
                ),
                subject_count=Count(
                    "class_assignments__subject",
                    filter=Q(class_assignments__academic_year=academic_year),
                    distinct=True,
                ),
            )
            .order_by("-class_count")
        )

    @staticmethod
    def get_departmental_performance():
        """Get performance metrics by department."""
        return Department.objects.annotate(
            teacher_count=Count("teachers", filter=Q(teachers__status="Active")),
            avg_score=Avg("teachers__evaluations__score"),
            avg_experience=Avg("teachers__experience_years"),
        ).filter(teacher_count__gt=0)

    @staticmethod
    def get_performance_by_experience():
        """Get performance correlation with experience."""
        return [
            {
                "range": "0-2 years",
                "avg_score": TeacherEvaluation.objects.filter(
                    teacher__experience_years__lt=2
                ).aggregate(avg_score=Avg("score"))["avg_score"]
                or 0,
                "count": Teacher.objects.filter(experience_years__lt=2).count(),
            },
            {
                "range": "2-5 years",
                "avg_score": TeacherEvaluation.objects.filter(
                    teacher__experience_years__gte=2, teacher__experience_years__lt=5
                ).aggregate(avg_score=Avg("score"))["avg_score"]
                or 0,
                "count": Teacher.objects.filter(
                    experience_years__gte=2, experience_years__lt=5
                ).count(),
            },
            {
                "range": "5-10 years",
                "avg_score": TeacherEvaluation.objects.filter(
                    teacher__experience_years__gte=5, teacher__experience_years__lt=10
                ).aggregate(avg_score=Avg("score"))["avg_score"]
                or 0,
                "count": Teacher.objects.filter(
                    experience_years__gte=5, experience_years__lt=10
                ).count(),
            },
            {
                "range": "10+ years",
                "avg_score": TeacherEvaluation.objects.filter(
                    teacher__experience_years__gte=10
                ).aggregate(avg_score=Avg("score"))["avg_score"]
                or 0,
                "count": Teacher.objects.filter(experience_years__gte=10).count(),
            },
        ]

    @staticmethod
    def get_teacher_performance_trend(months=12):
        """Get performance trend over time."""
        start_date = timezone.now().date() - timedelta(days=30 * months)

        evaluations = (
            TeacherEvaluation.objects.filter(evaluation_date__gte=start_date)
            .annotate(month=TruncMonth("evaluation_date"))
            .values("month")
            .annotate(avg_score=Avg("score"), count=Count("id"))
            .order_by("month")
        )

        return {
            "months": [e["month"].strftime("%b %Y") for e in evaluations],
            "scores": [float(e["avg_score"]) for e in evaluations],
            "counts": [e["count"] for e in evaluations],
        }

    @staticmethod
    def get_teacher_statistics():
        """Get comprehensive teacher statistics."""
        total_teachers = Teacher.objects.count()
        active_teachers = Teacher.objects.filter(status="Active").count()
        on_leave_teachers = Teacher.objects.filter(status="On Leave").count()
        terminated_teachers = Teacher.objects.filter(status="Terminated").count()

        avg_experience = (
            Teacher.objects.aggregate(avg=Avg("experience_years"))["avg"] or 0
        )
        avg_salary = Teacher.objects.aggregate(avg=Avg("salary"))["avg"] or 0

        contract_distribution = (
            Teacher.objects.values("contract_type")
            .annotate(count=Count("id"))
            .order_by("contract_type")
        )

        recent_hires = Teacher.objects.filter(
            joining_date__gte=timezone.now().date() - timedelta(days=365)
        ).count()

        tenure_distribution = [
            {
                "range": "<1 year",
                "count": Teacher.objects.filter(
                    joining_date__gte=timezone.now().date() - timedelta(days=365)
                ).count(),
            },
            {
                "range": "1-3 years",
                "count": Teacher.objects.filter(
                    joining_date__lt=timezone.now().date() - timedelta(days=365),
                    joining_date__gte=timezone.now().date() - timedelta(days=3 * 365),
                ).count(),
            },
            {
                "range": "3-5 years",
                "count": Teacher.objects.filter(
                    joining_date__lt=timezone.now().date() - timedelta(days=3 * 365),
                    joining_date__gte=timezone.now().date() - timedelta(days=5 * 365),
                ).count(),
            },
            {
                "range": "5+ years",
                "count": Teacher.objects.filter(
                    joining_date__lt=timezone.now().date() - timedelta(days=5 * 365)
                ).count(),
            },
        ]

        return {
            "total_teachers": total_teachers,
            "active_teachers": active_teachers,
            "on_leave_teachers": on_leave_teachers,
            "terminated_teachers": terminated_teachers,
            "avg_experience": avg_experience,
            "avg_salary": avg_salary,
            "contract_distribution": contract_distribution,
            "recent_hires": recent_hires,
            "tenure_distribution": tenure_distribution,
        }

    @staticmethod
    def get_teacher_export_data(filters=None):
        """Get teacher data for export with optional filters."""
        queryset = Teacher.objects.select_related("user", "department")

        if filters:
            if "status" in filters and filters["status"]:
                queryset = queryset.filter(status=filters["status"])
            if "department" in filters and filters["department"]:
                queryset = queryset.filter(department_id=filters["department"])
            if "contract_type" in filters and filters["contract_type"]:
                queryset = queryset.filter(contract_type=filters["contract_type"])

        return queryset


class TeacherAccountUtils:
    """Utility functions for managing teacher accounts."""

    @staticmethod
    def create_teacher_with_account(
        teacher_data, user_data, created_by=None, send_email=True
    ):
        """
        Create a teacher along with their user account in a single transaction.

        Args:
            teacher_data (dict): Teacher model field data
            user_data (dict): User account data
            created_by (User): User who is creating this teacher
            send_email (bool): Whether to send welcome email

        Returns:
            Teacher: The created teacher instance
        """
        try:
            with transaction.atomic():
                # Create user account using AuthenticationService
                user = AuthenticationService.register_user(
                    user_data=user_data,
                    role_names=["Teacher"],
                    created_by=created_by,
                    send_email=send_email,
                )

                # Create teacher instance
                teacher_data["user"] = user
                teacher = Teacher.objects.create(**teacher_data)

                return teacher

        except Exception as e:
            raise Exception(f"Failed to create teacher account: {str(e)}")

    @staticmethod
    def reset_teacher_password(teacher, new_password=None, send_email=True):
        """
        Reset a teacher's password.

        Args:
            teacher (Teacher): Teacher instance
            new_password (str): New password (auto-generated if None)
            send_email (bool): Whether to send password reset email

        Returns:
            str: The new password
        """
        if not teacher.user:
            raise ValueError("Teacher does not have an associated user account")

        if not new_password:
            new_password = AuthenticationService._generate_secure_password()

        teacher.user.set_password(new_password)
        teacher.user.requires_password_change = True
        teacher.user.save()

        if send_email:
            TeacherAccountUtils._send_password_reset_email(teacher, new_password)

        return new_password

    @staticmethod
    def ensure_teacher_role(teacher):
        """
        Ensure teacher has the Teacher role assigned.

        Args:
            teacher (Teacher): Teacher instance

        Returns:
            bool: True if role was assigned, False if already had it
        """
        if not teacher.user:
            raise ValueError("Teacher does not have an associated user account")

        if not teacher.user.has_role("Teacher"):
            RoleService.assign_role_to_user(teacher.user, "Teacher")
            return True
        return False

    @staticmethod
    def bulk_create_teachers_from_data(
        teachers_data, created_by=None, send_emails=True
    ):
        """
        Create multiple teachers from data in bulk.

        Args:
            teachers_data (list): List of teacher data dictionaries
            created_by (User): User creating these teachers
            send_emails (bool): Whether to send welcome emails

        Returns:
            dict: Results with created/failed counts and details
        """
        results = {
            "created": [],
            "failed": [],
            "created_count": 0,
            "failed_count": 0,
        }

        for data in teachers_data:
            try:
                teacher_fields = {
                    k: v
                    for k, v in data.items()
                    if k in [f.name for f in Teacher._meta.fields] and k != "user"
                }

                user_fields = {
                    "first_name": data.get("first_name", ""),
                    "last_name": data.get("last_name", ""),
                    "email": data.get("email"),
                    "username": data.get("email"),
                    "phone_number": data.get("phone_number", ""),
                    "is_active": True,
                }

                teacher = TeacherAccountUtils.create_teacher_with_account(
                    teacher_data=teacher_fields,
                    user_data=user_fields,
                    created_by=created_by,
                    send_email=send_emails,
                )

                results["created"].append(
                    {
                        "teacher": teacher,
                        "employee_id": teacher.employee_id,
                        "email": teacher.user.email,
                    }
                )
                results["created_count"] += 1

            except Exception as e:
                results["failed"].append(
                    {
                        "data": data,
                        "error": str(e),
                    }
                )
                results["failed_count"] += 1

        return results

    @staticmethod
    def get_teachers_without_accounts():
        """
        Get teachers that don't have proper user accounts.

        Returns:
            dict: Dictionary with different categories of problematic accounts
        """
        return {
            "no_user": Teacher.objects.filter(user__isnull=True),
            "inactive_user": Teacher.objects.filter(user__is_active=False),
            "no_password": Teacher.objects.filter(user__password__in=["", "!"]),
            "no_teacher_role": [
                t
                for t in Teacher.objects.filter(user__isnull=False)
                if not t.user.has_role("Teacher")
            ],
        }

    @staticmethod
    def _send_password_reset_email(teacher, new_password):
        """Send password reset email to teacher."""
        try:
            subject = f"Password Reset - {getattr(settings, 'SITE_NAME', 'School Management System')}"

            context = {
                "teacher": teacher,
                "user": teacher.user,
                "new_password": new_password,
                "site_name": getattr(settings, "SITE_NAME", "School Management System"),
                "login_url": getattr(settings, "LOGIN_URL", "/login/"),
            }

            # Try to use a custom template, fall back to a simple text email
            try:
                html_message = render_to_string(
                    "teachers/emails/password_reset.html", context
                )
            except:
                html_message = f"""
                <h2>Password Reset</h2>
                <p>Dear {teacher.user.get_full_name()},</p>
                <p>Your password has been reset. Here are your new login credentials:</p>
                <ul>
                    <li><strong>Username:</strong> {teacher.user.username}</li>
                    <li><strong>New Password:</strong> {new_password}</li>
                </ul>
                <p>Please log in and change your password immediately.</p>
                <p>Best regards,<br>{context['site_name']} Team</p>
                """

            send_mail(
                subject=subject,
                message=f"Your new password is: {new_password}",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[teacher.user.email],
                html_message=html_message,
                fail_silently=False,
            )

        except Exception as e:
            raise Exception(f"Failed to send password reset email: {str(e)}")

    @staticmethod
    def validate_teacher_account(teacher):
        """
        Validate that a teacher's account is properly set up.

        Args:
            teacher (Teacher): Teacher instance to validate

        Returns:
            dict: Validation results with issues found
        """
        issues = []

        if not teacher.user:
            issues.append("No user account associated")
            return {"valid": False, "issues": issues}

        user = teacher.user

        if not user.is_active:
            issues.append("User account is inactive")

        if not user.has_usable_password():
            issues.append("User account has no usable password")

        if not user.email:
            issues.append("User account has no email address")

        if not user.has_role("Teacher"):
            issues.append("User does not have Teacher role")

        if not user.first_name or not user.last_name:
            issues.append("User account is missing name information")

        return {
            "valid": len(issues) == 0,
            "issues": issues,
        }
