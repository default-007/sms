from django.db import DatabaseError, transaction
from django.db.utils import ProgrammingError
from django.utils import timezone
from django.db.models import Count, Q, F, Sum, Avg
from datetime import datetime, date, timedelta

from src.courses.models import (
    Class,
    Timetable,
    TimeSlot,
    Assignment,
    AssignmentSubmission,
)


class ClassService:
    @staticmethod
    def get_class_by_id(class_id):
        """Get a class by ID."""
        try:
            return Class.objects.get(id=class_id)
        except (Class.DoesNotExist, ValueError):
            return None

    @staticmethod
    def get_class_students(class_obj):
        """Get all students in a class."""
        try:
            return class_obj.students.all().select_related("user")
        except (DatabaseError, ProgrammingError, AttributeError):
            return []

    @staticmethod
    def get_class_timetable(class_obj, day=None):
        """Get the timetable for a class, optionally filtered by day."""
        try:
            timetable_entries = Timetable.objects.filter(
                class_obj=class_obj, is_active=True
            ).select_related("subject", "teacher", "time_slot", "teacher__user")

            if day is not None:
                timetable_entries = timetable_entries.filter(time_slot__day_of_week=day)

            return timetable_entries.order_by(
                "time_slot__day_of_week", "time_slot__start_time"
            )
        except (DatabaseError, ProgrammingError, AttributeError):
            return []

    @staticmethod
    def check_timetable_clash(class_obj, time_slot, exclude_id=None):
        """Check if there's any clash in the timetable for a given class and time slot."""
        query = Timetable.objects.filter(
            class_obj=class_obj, time_slot=time_slot, is_active=True
        )

        if exclude_id:
            query = query.exclude(id=exclude_id)

        return query.exists()

    @staticmethod
    def get_class_subjects(class_obj):
        """Get all subjects taught in a class."""
        try:
            return (
                Timetable.objects.filter(class_obj=class_obj, is_active=True)
                .values_list("subject", flat=True)
                .distinct()
            )
        except (DatabaseError, ProgrammingError, AttributeError):
            return []

    @staticmethod
    def get_class_teachers(class_obj):
        """Get all teachers teaching in a class."""
        try:
            return (
                Timetable.objects.filter(class_obj=class_obj, is_active=True)
                .values_list("teacher", flat=True)
                .distinct()
            )
        except (DatabaseError, ProgrammingError, AttributeError):
            return []

    @staticmethod
    def get_class_timetable_matrix(class_obj, day=None):
        """Get the timetable for a class in matrix format."""
        # Get all time slots
        time_slots = TimeSlot.objects.all().order_by("start_time")

        # Get days (0-6 for Monday-Sunday)
        days = range(7)
        if day is not None:
            days = [day]

        # Get all timetable entries for this class
        timetable_entries = Timetable.objects.filter(
            class_obj=class_obj, is_active=True
        ).select_related("subject", "teacher", "time_slot", "teacher__user")

        if day is not None:
            timetable_entries = timetable_entries.filter(time_slot__day_of_week=day)

        # Create a matrix of days and time slots
        timetable_matrix = {}

        for day_num in days:
            timetable_matrix[day_num] = {}

        # Fill the matrix with timetable entries
        for entry in timetable_entries:
            day = entry.time_slot.day_of_week
            time_slot_id = entry.time_slot.id

            timetable_matrix[day][time_slot_id] = entry

        return timetable_matrix, list(time_slots), list(days)

    @staticmethod
    def get_class_statistics(class_obj):
        """Get various statistics for a class."""
        try:
            students = class_obj.students.all()
            student_count = students.count()

            # Gender distribution
            male_count = students.filter(user__gender="M").count()
            female_count = students.filter(user__gender="F").count()
            other_count = students.filter(
                Q(user__gender="O") | Q(user__gender="")
            ).count()

            gender_distribution = {
                "M": (male_count / student_count * 100) if student_count > 0 else 0,
                "F": (female_count / student_count * 100) if student_count > 0 else 0,
                "O": (other_count / student_count * 100) if student_count > 0 else 0,
            }

            # Attendance statistics
            from src.attendance.models import Attendance

            attendances = Attendance.objects.filter(class_id=class_obj)
            present_count = attendances.filter(status="Present").count()
            total_attendance = attendances.count()

            attendance_stats = {
                "average_attendance_rate": (
                    (present_count / total_attendance * 100)
                    if total_attendance > 0
                    else 0
                ),
            }

            # Assignment statistics
            assignments = Assignment.objects.filter(class_obj=class_obj)
            submissions = AssignmentSubmission.objects.filter(
                assignment__class_obj=class_obj
            )

            submitted_assignments = submissions.values("assignment").distinct().count()
            total_assignments = assignments.count()

            assignment_stats = {
                "completion_rate": (
                    (submitted_assignments / total_assignments * 100)
                    if total_assignments > 0
                    else 0
                ),
            }

            # Exam results
            from src.exams.models import StudentExamResult

            exam_results = StudentExamResult.objects.filter(
                student__current_class=class_obj,
                exam_schedule__exam__academic_year=class_obj.academic_year,
            )

            average_score = (
                exam_results.aggregate(Avg("marks_obtained"))["marks_obtained__avg"]
                or 0
            )
            pass_count = exam_results.filter(is_pass=True).count()
            exam_count = exam_results.count()

            exam_stats = {
                "average_score": average_score,
                "pass_rate": (pass_count / exam_count * 100) if exam_count > 0 else 0,
            }

            return {
                "student_count": student_count,
                "gender_distribution": gender_distribution,
                "attendance_stats": attendance_stats,
                "assignment_stats": assignment_stats,
                "exam_stats": exam_stats,
            }
        except Exception as e:
            return {"error": str(e)}

    @staticmethod
    @transaction.atomic
    def add_students_to_class(class_obj, students):
        """Add multiple students to a class."""
        try:
            # Get current students in class
            current_students = set(
                class_obj.students.all().values_list("id", flat=True)
            )

            # Get students to add
            students_to_add = [s for s in students if s.id not in current_students]

            # Update students' current_class
            for student in students_to_add:
                student.current_class = class_obj
                student.save()

            return True, f"Added {len(students_to_add)} students to class."
        except Exception as e:
            return False, str(e)

    @staticmethod
    @transaction.atomic
    def remove_students_from_class(class_obj, students):
        """Remove multiple students from a class."""
        try:
            # Get students to remove
            students_to_remove = [s for s in students if s.current_class == class_obj]

            # Update students' current_class
            for student in students_to_remove:
                student.current_class = None
                student.save()

            return True, f"Removed {len(students_to_remove)} students from class."
        except Exception as e:
            return False, str(e)

    @staticmethod
    @transaction.atomic
    def promote_students(from_class, to_class, students=None):
        """Promote students from one class to another."""
        try:
            # Get students to promote
            if students is None:
                students = from_class.students.all()

            # Promote students
            for student in students:
                student.current_class = to_class
                student.save()

            return True, f"Promoted {len(students)} students to {to_class}."
        except Exception as e:
            return False, str(e)

    @staticmethod
    @transaction.atomic
    def create_class_from_template(template_class, new_academic_year, new_grade=None):
        """Create a new class based on an existing class template."""
        try:
            # Create new class
            new_class = Class(
                grade=new_grade or template_class.grade,
                section=template_class.section,
                academic_year=new_academic_year,
                room_number=template_class.room_number,
                capacity=template_class.capacity,
                class_teacher=template_class.class_teacher,
            )
            new_class.save()

            return new_class
        except Exception as e:
            raise e

    @staticmethod
    def get_class_attendance_report(class_obj, start_date=None, end_date=None):
        """Generate attendance report for a class."""
        from src.attendance.models import Attendance

        query = Attendance.objects.filter(class_id=class_obj)

        if start_date:
            query = query.filter(date__gte=start_date)

        if end_date:
            query = query.filter(date__lte=end_date)

        # Group by date
        attendance_by_date = {}
        dates = query.values_list("date", flat=True).distinct().order_by("date")

        for attendance_date in dates:
            date_attendances = query.filter(date=attendance_date)
            present_count = date_attendances.filter(status="Present").count()
            absent_count = date_attendances.filter(status="Absent").count()
            late_count = date_attendances.filter(status="Late").count()
            excused_count = date_attendances.filter(status="Excused").count()

            total_count = present_count + absent_count + late_count + excused_count

            attendance_by_date[attendance_date] = {
                "present": present_count,
                "absent": absent_count,
                "late": late_count,
                "excused": excused_count,
                "total": total_count,
                "attendance_rate": (
                    (present_count / total_count * 100) if total_count > 0 else 0
                ),
            }

        # Group by student
        attendance_by_student = {}
        students = class_obj.students.all()

        for student in students:
            student_attendances = query.filter(student=student)
            present_count = student_attendances.filter(status="Present").count()
            absent_count = student_attendances.filter(status="Absent").count()
            late_count = student_attendances.filter(status="Late").count()
            excused_count = student_attendances.filter(status="Excused").count()

            total_count = present_count + absent_count + late_count + excused_count

            attendance_by_student[student.id] = {
                "student": student,
                "present": present_count,
                "absent": absent_count,
                "late": late_count,
                "excused": excused_count,
                "total": total_count,
                "attendance_rate": (
                    (present_count / total_count * 100) if total_count > 0 else 0
                ),
            }

        # Calculate overall statistics
        total_records = query.count()
        present_count = query.filter(status="Present").count()
        absent_count = query.filter(status="Absent").count()
        late_count = query.filter(status="Late").count()
        excused_count = query.filter(status="Excused").count()

        overall_stats = {
            "total_days": len(dates),
            "total_records": total_records,
            "present_count": present_count,
            "absent_count": absent_count,
            "late_count": late_count,
            "excused_count": excused_count,
            "attendance_rate": (
                (present_count / total_records * 100) if total_records > 0 else 0
            ),
        }

        return {
            "overall": overall_stats,
            "by_date": attendance_by_date,
            "by_student": attendance_by_student,
        }

    @staticmethod
    def get_students_with_low_attendance(class_obj, threshold=75, period_days=30):
        """Get students with attendance below a threshold."""
        from src.attendance.models import Attendance

        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=period_days)

        students = class_obj.students.all()
        low_attendance_students = []

        for student in students:
            student_attendances = Attendance.objects.filter(
                class_id=class_obj,
                student=student,
                date__gte=start_date,
                date__lte=end_date,
            )

            total_count = student_attendances.count()

            if total_count > 0:
                present_count = student_attendances.filter(status="Present").count()
                attendance_rate = (present_count / total_count) * 100

                if attendance_rate < threshold:
                    low_attendance_students.append(
                        {
                            "student": student,
                            "attendance_rate": attendance_rate,
                            "present_days": present_count,
                            "total_days": total_count,
                            "absence_count": total_count - present_count,
                        }
                    )

        return low_attendance_students

    @staticmethod
    def get_top_performing_students(class_obj, count=5):
        """Get top performing students based on exam results."""
        from src.exams.models import StudentExamResult

        students = class_obj.students.all()
        performance_data = []

        for student in students:
            exam_results = StudentExamResult.objects.filter(
                student=student,
                exam_schedule__exam__academic_year=class_obj.academic_year,
            )

            if exam_results.exists():
                avg_score = (
                    exam_results.aggregate(Avg("marks_obtained"))["marks_obtained__avg"]
                    or 0
                )
                performance_data.append(
                    {
                        "student": student,
                        "average_score": avg_score,
                        "exams_count": exam_results.count(),
                        "pass_count": exam_results.filter(is_pass=True).count(),
                    }
                )

        # Sort by average score in descending order
        performance_data.sort(key=lambda x: x["average_score"], reverse=True)

        return performance_data[:count]

    @staticmethod
    def get_assignment_completion_by_subject(class_obj):
        """Get assignment completion rates by subject."""
        subjects = ClassService.get_class_subjects(class_obj)
        completion_by_subject = {}

        for subject_id in subjects:
            from src.courses.models import Subject

            subject = Subject.objects.get(id=subject_id)

            assignments = Assignment.objects.filter(
                class_obj=class_obj, subject=subject, status__in=["published", "closed"]
            )

            total_assignments = assignments.count()

            if total_assignments > 0:
                expected_submissions = total_assignments * class_obj.students.count()
                actual_submissions = AssignmentSubmission.objects.filter(
                    assignment__in=assignments
                ).count()

                completion_rate = (actual_submissions / expected_submissions) * 100

                completion_by_subject[subject.name] = {
                    "subject": subject,
                    "total_assignments": total_assignments,
                    "expected_submissions": expected_submissions,
                    "actual_submissions": actual_submissions,
                    "completion_rate": completion_rate,
                }

        return completion_by_subject
