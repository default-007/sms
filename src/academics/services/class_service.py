"""
Class Service

Business logic for class management including:
- Class creation within grades
- Student enrollment and capacity management
- Class teacher assignment
- Class analytics and optimization
"""

from typing import Any, Dict, List, Optional

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Avg, Count, Q, Sum

from ..models import AcademicYear, Class, Grade, Section

User = get_user_model()


class ClassService:
    """Service for managing academic classes"""

    @staticmethod
    def create_class(
        name: str,
        grade_id: int,
        academic_year_id: int,
        room_number: str = "",
        capacity: int = 30,
        class_teacher_id: Optional[int] = None,
    ) -> Class:
        """
        Create a new class within a grade

        Args:
            name: Class name (e.g., "North", "Blue", "Alpha")
            grade_id: ID of parent grade
            academic_year_id: Academic year ID
            room_number: Room/classroom number
            capacity: Maximum student capacity
            class_teacher_id: Optional class teacher ID

        Returns:
            Created Class instance

        Raises:
            ValidationError: If validation fails
        """
        try:
            grade = Grade.objects.get(id=grade_id)
        except Grade.DoesNotExist:
            raise ValidationError("Grade not found")

        if not grade.is_active:
            raise ValidationError("Cannot create class in inactive grade")

        try:
            academic_year = AcademicYear.objects.get(id=academic_year_id)
        except AcademicYear.DoesNotExist:
            raise ValidationError("Academic year not found")

        # Validate name uniqueness within grade and academic year
        if Class.objects.filter(
            grade=grade, academic_year=academic_year, name__iexact=name
        ).exists():
            raise ValidationError(
                f"Class '{name}' already exists in {grade.name} for {academic_year.name}"
            )

        # Validate capacity
        if capacity < 1 or capacity > 100:
            raise ValidationError("Class capacity must be between 1 and 100")

        # Validate and get class teacher
        class_teacher = None
        if class_teacher_id:
            try:
                from teachers.models import Teacher

                class_teacher = Teacher.objects.get(id=class_teacher_id)

                # Check if teacher is already assigned as class teacher in same academic year
                existing_assignment = Class.objects.filter(
                    class_teacher=class_teacher,
                    academic_year=academic_year,
                    is_active=True,
                ).exists()

                if existing_assignment:
                    raise ValidationError(
                        f"Teacher is already assigned as class teacher for another class in {academic_year.name}"
                    )

            except Teacher.DoesNotExist:
                raise ValidationError("Teacher not found")

        cls = Class.objects.create(
            name=name,
            grade=grade,
            section=grade.section,  # Auto-set from grade
            academic_year=academic_year,
            room_number=room_number,
            capacity=capacity,
            class_teacher=class_teacher,
        )

        return cls

    @staticmethod
    def update_class(
        class_id: int,
        name: Optional[str] = None,
        room_number: Optional[str] = None,
        capacity: Optional[int] = None,
        class_teacher_id: Optional[int] = None,
        is_active: Optional[bool] = None,
    ) -> Class:
        """
        Update an existing class

        Args:
            class_id: ID of class to update
            name: New name (optional)
            room_number: New room number (optional)
            capacity: New capacity (optional)
            class_teacher_id: New class teacher ID (optional, None to remove)
            is_active: New active status (optional)

        Returns:
            Updated Class instance
        """
        try:
            cls = Class.objects.get(id=class_id)
        except Class.DoesNotExist:
            raise ValidationError("Class not found")

        # Validate name uniqueness if changing name
        if name and name != cls.name:
            if (
                Class.objects.filter(
                    grade=cls.grade, academic_year=cls.academic_year, name__iexact=name
                )
                .exclude(id=class_id)
                .exists()
            ):
                raise ValidationError(
                    f"Class '{name}' already exists in {cls.grade.name} for {cls.academic_year.name}"
                )
            cls.name = name

        if room_number is not None:
            cls.room_number = room_number

        if capacity is not None:
            if capacity < 1 or capacity > 100:
                raise ValidationError("Class capacity must be between 1 and 100")

            # Check if new capacity is less than current enrollment
            current_students = cls.get_students_count()
            if capacity < current_students:
                raise ValidationError(
                    f"Cannot reduce capacity to {capacity}. Current enrollment is {current_students} students"
                )

            cls.capacity = capacity

        if class_teacher_id is not None:
            if class_teacher_id:
                try:
                    from teachers.models import Teacher

                    class_teacher = Teacher.objects.get(id=class_teacher_id)

                    # Check if teacher is already assigned elsewhere
                    existing_assignment = (
                        Class.objects.filter(
                            class_teacher=class_teacher,
                            academic_year=cls.academic_year,
                            is_active=True,
                        )
                        .exclude(id=class_id)
                        .exists()
                    )

                    if existing_assignment:
                        raise ValidationError(
                            f"Teacher is already assigned as class teacher for another class in {cls.academic_year.name}"
                        )

                    cls.class_teacher = class_teacher
                except Teacher.DoesNotExist:
                    raise ValidationError("Teacher not found")
            else:
                cls.class_teacher = None

        if is_active is not None:
            if not is_active and cls.is_active:
                ClassService._validate_class_deactivation(cls)
            cls.is_active = is_active

        cls.save()
        return cls

    @staticmethod
    def _validate_class_deactivation(cls: Class) -> None:
        """
        Validate if a class can be deactivated

        Args:
            cls: Class to validate

        Raises:
            ValidationError: If class cannot be deactivated
        """
        current_students = cls.get_students_count()
        if current_students > 0:
            raise ValidationError(
                f"Cannot deactivate class with {current_students} enrolled students"
            )

    @staticmethod
    def get_class_details(class_id: int) -> Dict[str, Any]:
        """
        Get detailed information about a class

        Args:
            class_id: ID of class

        Returns:
            Dictionary containing class details and statistics
        """
        try:
            cls = Class.objects.get(id=class_id)
        except Class.DoesNotExist:
            raise ValidationError("Class not found")

        students = cls.get_students()
        students_data = []

        for student in students:
            students_data.append(
                {
                    "id": student.id,
                    "admission_number": student.admission_number,
                    "user": {
                        "id": student.user.id,
                        "first_name": student.user.first_name,
                        "last_name": student.user.last_name,
                        "email": student.user.email,
                    },
                    "roll_number": student.roll_number,
                    "admission_date": student.admission_date,
                    "status": student.status,
                }
            )

        # Get subjects taught in this class
        subjects = cls.get_subjects()
        subjects_data = []

        if subjects:
            from subjects.models import Subject

            subject_objects = Subject.objects.filter(id__in=subjects)
            subjects_data = [
                {"id": subject.id, "name": subject.name, "code": subject.code}
                for subject in subject_objects
            ]

        # Get timetable information
        timetable = cls.get_timetable()
        timetable_data = [
            {
                "id": entry.id,
                "subject": (
                    {"id": entry.subject.id, "name": entry.subject.name}
                    if entry.subject
                    else None
                ),
                "teacher": (
                    {
                        "id": entry.teacher.id,
                        "name": f"{entry.teacher.user.first_name} {entry.teacher.user.last_name}",
                    }
                    if entry.teacher
                    else None
                ),
                "time_slot": {
                    "id": entry.time_slot.id,
                    "day_of_week": entry.time_slot.day_of_week,
                    "start_time": entry.time_slot.start_time,
                    "end_time": entry.time_slot.end_time,
                    "period_number": entry.time_slot.period_number,
                },
                "room": entry.room,
            }
            for entry in timetable
        ]

        return {
            "class": {
                "id": cls.id,
                "name": cls.name,
                "display_name": cls.display_name,
                "full_name": cls.full_name,
                "room_number": cls.room_number,
                "capacity": cls.capacity,
                "is_active": cls.is_active,
                "grade": {
                    "id": cls.grade.id,
                    "name": cls.grade.name,
                    "section": {"id": cls.section.id, "name": cls.section.name},
                },
                "academic_year": {
                    "id": cls.academic_year.id,
                    "name": cls.academic_year.name,
                },
                "class_teacher": (
                    {
                        "id": cls.class_teacher.id,
                        "name": f"{cls.class_teacher.user.first_name} {cls.class_teacher.user.last_name}",
                        "employee_id": cls.class_teacher.employee_id,
                    }
                    if cls.class_teacher
                    else None
                ),
            },
            "students": students_data,
            "subjects": subjects_data,
            "timetable": timetable_data,
            "statistics": {
                "total_students": len(students_data),
                "available_capacity": cls.get_available_capacity(),
                "utilization_rate": (
                    (len(students_data) / cls.capacity * 100) if cls.capacity > 0 else 0
                ),
                "is_full": cls.is_full(),
                "subjects_count": len(subjects_data),
                "timetable_periods": len(timetable_data),
            },
        }

    @staticmethod
    def get_class_analytics(class_id: int) -> Dict[str, Any]:
        """
        Get analytics for a specific class

        Args:
            class_id: ID of class

        Returns:
            Dictionary containing class analytics
        """
        try:
            cls = Class.objects.get(id=class_id)
        except Class.DoesNotExist:
            raise ValidationError("Class not found")

        students = cls.get_students()

        # Gender distribution
        gender_stats = {
            "male": students.filter(user__gender="Male").count(),
            "female": students.filter(user__gender="Female").count(),
            "other": students.filter(user__gender__in=["Other", ""]).count(),
        }

        # Age distribution
        from datetime import datetime

        from django.utils import timezone

        current_date = timezone.now().date()

        age_groups = {
            "under_5": 0,
            "5_to_7": 0,
            "8_to_10": 0,
            "11_to_13": 0,
            "14_to_16": 0,
            "over_16": 0,
        }

        for student in students:
            if student.user.date_of_birth:
                age = (current_date - student.user.date_of_birth).days // 365
                if age < 5:
                    age_groups["under_5"] += 1
                elif 5 <= age <= 7:
                    age_groups["5_to_7"] += 1
                elif 8 <= age <= 10:
                    age_groups["8_to_10"] += 1
                elif 11 <= age <= 13:
                    age_groups["11_to_13"] += 1
                elif 14 <= age <= 16:
                    age_groups["14_to_16"] += 1
                else:
                    age_groups["over_16"] += 1

        # Performance analytics (if available)
        performance_stats = {}

        try:
            from analytics.models import StudentPerformanceAnalytics

            performance_data = StudentPerformanceAnalytics.objects.filter(
                student__in=students, academic_year=cls.academic_year
            ).aggregate(
                avg_marks=Avg("average_marks"),
                highest_marks=models.Max("highest_marks"),
                lowest_marks=models.Min("lowest_marks"),
            )

            performance_stats = {
                "class_average": round(performance_data["avg_marks"] or 0, 2),
                "highest_score": performance_data["highest_marks"] or 0,
                "lowest_score": performance_data["lowest_marks"] or 0,
                "has_data": performance_data["avg_marks"] is not None,
            }
        except ImportError:
            performance_stats = {"has_data": False}

        # Attendance analytics (if available)
        attendance_stats = {}

        try:
            from attendance.models import Attendance

            attendance_data = Attendance.objects.filter(
                student__in=students, class_id=cls, academic_year=cls.academic_year
            ).aggregate(
                total_days=Count("id"),
                present_days=Count("id", filter=Q(status="Present")),
                absent_days=Count("id", filter=Q(status="Absent")),
            )

            if attendance_data["total_days"] > 0:
                attendance_stats = {
                    "total_days": attendance_data["total_days"],
                    "present_days": attendance_data["present_days"],
                    "absent_days": attendance_data["absent_days"],
                    "attendance_rate": round(
                        (
                            attendance_data["present_days"]
                            / attendance_data["total_days"]
                        )
                        * 100,
                        2,
                    ),
                    "has_data": True,
                }
            else:
                attendance_stats = {"has_data": False}
        except ImportError:
            attendance_stats = {"has_data": False}

        return {
            "class": {"id": cls.id, "name": cls.name, "display_name": cls.display_name},
            "enrollment": {
                "total_students": students.count(),
                "capacity": cls.capacity,
                "utilization_rate": (
                    (students.count() / cls.capacity * 100) if cls.capacity > 0 else 0
                ),
                "available_spots": cls.get_available_capacity(),
            },
            "demographics": {
                "gender_distribution": gender_stats,
                "age_distribution": age_groups,
            },
            "performance": performance_stats,
            "attendance": attendance_stats,
            "recommendations": ClassService._generate_class_recommendations(
                cls, students.count()
            ),
        }

    @staticmethod
    def _generate_class_recommendations(cls: Class, student_count: int) -> List[str]:
        """Generate recommendations for class management"""
        recommendations = []

        utilization_rate = (
            (student_count / cls.capacity * 100) if cls.capacity > 0 else 0
        )

        # Capacity recommendations
        if utilization_rate > 95:
            recommendations.append(
                "Class is at near-full capacity - consider increasing capacity or creating additional sections"
            )
        elif utilization_rate < 50:
            recommendations.append(
                "Class utilization is low - consider consolidating with other classes or reducing capacity"
            )

        # Teacher assignment
        if not cls.class_teacher:
            recommendations.append(
                "No class teacher assigned - assign a primary teacher for better class management"
            )

        # Room assignment
        if not cls.room_number:
            recommendations.append(
                "No room assigned - assign a dedicated classroom for better organization"
            )

        return recommendations

    @staticmethod
    def bulk_create_classes(
        grade_id: int, academic_year_id: int, class_configs: List[Dict[str, Any]]
    ) -> List[Class]:
        """
        Create multiple classes at once

        Args:
            grade_id: ID of parent grade
            academic_year_id: Academic year ID
            class_configs: List of class configuration dictionaries
                          Each dict should contain: name, capacity, room_number (optional)

        Returns:
            List of created Class instances
        """
        try:
            grade = Grade.objects.get(id=grade_id)
        except Grade.DoesNotExist:
            raise ValidationError("Grade not found")

        try:
            academic_year = AcademicYear.objects.get(id=academic_year_id)
        except AcademicYear.DoesNotExist:
            raise ValidationError("Academic year not found")

        created_classes = []

        with transaction.atomic():
            for config in class_configs:
                if "name" not in config:
                    raise ValidationError("Class name is required for each class")

                cls = ClassService.create_class(
                    name=config["name"],
                    grade_id=grade_id,
                    academic_year_id=academic_year_id,
                    room_number=config.get("room_number", ""),
                    capacity=config.get("capacity", 30),
                    class_teacher_id=config.get("class_teacher_id"),
                )
                created_classes.append(cls)

        return created_classes

    @staticmethod
    def get_classes_by_grade(
        grade_id: int,
        academic_year_id: Optional[int] = None,
        include_inactive: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Get all classes in a grade

        Args:
            grade_id: ID of grade
            academic_year_id: Optional academic year ID for filtering
            include_inactive: Whether to include inactive classes

        Returns:
            List of class dictionaries with basic information
        """
        try:
            grade = Grade.objects.get(id=grade_id)
        except Grade.DoesNotExist:
            raise ValidationError("Grade not found")

        classes_qs = grade.classes.all()

        if academic_year_id:
            classes_qs = classes_qs.filter(academic_year_id=academic_year_id)

        if not include_inactive:
            classes_qs = classes_qs.filter(is_active=True)

        classes_qs = classes_qs.order_by("name")

        classes_data = []
        for cls in classes_qs:
            student_count = cls.get_students_count()

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
                    "is_active": cls.is_active,
                    "class_teacher": (
                        {
                            "id": cls.class_teacher.id,
                            "name": f"{cls.class_teacher.user.first_name} {cls.class_teacher.user.last_name}",
                        }
                        if cls.class_teacher
                        else None
                    ),
                    "academic_year": {
                        "id": cls.academic_year.id,
                        "name": cls.academic_year.name,
                    },
                }
            )

        return classes_data

    @staticmethod
    def optimize_class_distribution(
        grade_id: int, academic_year_id: int
    ) -> Dict[str, Any]:
        """
        Analyze and suggest optimal class distribution for a grade

        Args:
            grade_id: ID of grade
            academic_year_id: Academic year ID

        Returns:
            Dictionary containing optimization suggestions
        """
        try:
            grade = Grade.objects.get(id=grade_id)
        except Grade.DoesNotExist:
            raise ValidationError("Grade not found")

        classes = grade.get_classes(academic_year_id)
        total_students = sum(cls.get_students_count() for cls in classes)
        total_capacity = sum(cls.capacity for cls in classes)

        if not classes:
            return {
                "current_state": "No classes found",
                "recommendations": ["Create classes for this grade"],
            }

        current_distribution = []
        for cls in classes:
            student_count = cls.get_students_count()
            current_distribution.append(
                {
                    "class_name": cls.display_name,
                    "students": student_count,
                    "capacity": cls.capacity,
                    "utilization": (
                        (student_count / cls.capacity * 100) if cls.capacity > 0 else 0
                    ),
                }
            )

        # Calculate optimal distribution
        if total_students > 0:
            optimal_class_size = 25  # Configurable optimal class size
            suggested_classes = max(1, total_students // optimal_class_size)
            if total_students % optimal_class_size > optimal_class_size * 0.7:
                suggested_classes += 1

            students_per_class = total_students // suggested_classes
            remainder = total_students % suggested_classes

            suggested_distribution = []
            for i in range(suggested_classes):
                class_size = students_per_class + (1 if i < remainder else 0)
                suggested_distribution.append(
                    {
                        "class_number": i + 1,
                        "suggested_students": class_size,
                        "suggested_capacity": max(
                            class_size + 5, optimal_class_size
                        ),  # 5-student buffer
                    }
                )
        else:
            suggested_distribution = []

        recommendations = []

        # Generate recommendations
        if len(classes) != suggested_classes:
            if len(classes) < suggested_classes:
                recommendations.append(
                    f"Consider creating {suggested_classes - len(classes)} additional class(es)"
                )
            else:
                recommendations.append(
                    f"Consider consolidating into {suggested_classes} class(es)"
                )

        # Check utilization rates
        over_capacity = [
            cls for cls in current_distribution if cls["utilization"] > 100
        ]
        under_utilized = [
            cls for cls in current_distribution if cls["utilization"] < 60
        ]

        if over_capacity:
            recommendations.append(f"{len(over_capacity)} class(es) are over capacity")

        if under_utilized:
            recommendations.append(
                f"{len(under_utilized)} class(es) are under-utilized"
            )

        return {
            "grade": {"id": grade.id, "name": grade.name},
            "current_state": {
                "total_classes": len(classes),
                "total_students": total_students,
                "total_capacity": total_capacity,
                "overall_utilization": (
                    (total_students / total_capacity * 100) if total_capacity > 0 else 0
                ),
                "distribution": current_distribution,
            },
            "optimization": {
                "suggested_classes": suggested_classes,
                "suggested_distribution": suggested_distribution,
                "efficiency_gain": abs(len(classes) - suggested_classes),
            },
            "recommendations": recommendations,
        }

    @staticmethod
    def transfer_student_between_classes(
        student_id: int, from_class_id: int, to_class_id: int, reason: str = ""
    ) -> Dict[str, Any]:
        """
        Transfer a student from one class to another

        Args:
            student_id: ID of student to transfer
            from_class_id: Source class ID
            to_class_id: Destination class ID
            reason: Reason for transfer

        Returns:
            Dictionary containing transfer results
        """
        try:
            from students.models import Student

            student = Student.objects.get(id=student_id)
        except Student.DoesNotExist:
            raise ValidationError("Student not found")

        try:
            from_class = Class.objects.get(id=from_class_id)
            to_class = Class.objects.get(id=to_class_id)
        except Class.DoesNotExist:
            raise ValidationError("One or both classes not found")

        # Validate transfer
        if from_class.academic_year != to_class.academic_year:
            raise ValidationError("Cannot transfer between different academic years")

        if student.current_class_id != from_class_id:
            raise ValidationError(
                "Student is not currently in the specified source class"
            )

        if to_class.is_full():
            raise ValidationError("Destination class is at full capacity")

        if not to_class.is_active:
            raise ValidationError("Cannot transfer to inactive class")

        with transaction.atomic():
            # Update student's class
            student.current_class_id = to_class_id
            student.save()

            # Log the transfer (if audit system exists)
            try:
                from core.models import AuditLog

                AuditLog.objects.create(
                    user=student.user,
                    action="Class Transfer",
                    entity_type="Student",
                    entity_id=student.id,
                    data_before={
                        "class_id": from_class_id,
                        "class_name": from_class.display_name,
                    },
                    data_after={
                        "class_id": to_class_id,
                        "class_name": to_class.display_name,
                    },
                    metadata={"reason": reason},
                )
            except ImportError:
                pass  # Audit system not available

        return {
            "success": True,
            "student": {
                "id": student.id,
                "name": f"{student.user.first_name} {student.user.last_name}",
                "admission_number": student.admission_number,
            },
            "transfer": {
                "from_class": {"id": from_class.id, "name": from_class.display_name},
                "to_class": {"id": to_class.id, "name": to_class.display_name},
                "reason": reason,
            },
            "new_class_stats": {
                "students_count": to_class.get_students_count(),
                "available_capacity": to_class.get_available_capacity(),
            },
        }
