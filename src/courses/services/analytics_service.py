from django.db.models import Avg, Count, Sum, F, Q, Case, When, Value, IntegerField
from django.utils import timezone
from datetime import datetime, timedelta

from src.courses.models import (
    Department,
    AcademicYear,
    Grade,
    Class,
    Subject,
    Assignment,
    AssignmentSubmission,
    Timetable,
)


class AnalyticsService:
    @staticmethod
    def get_department_analytics(department, academic_year=None):
        """Get comprehensive analytics for a department"""
        if not academic_year:
            academic_year = AcademicYear.objects.filter(is_current=True).first()
            if not academic_year:
                return {
                    "department": department.name,
                    "error": "No current academic year found",
                }

        # Get subjects and teachers in the department
        subjects = department.subjects.all()
        subject_count = subjects.count()

        # Get classes offering these subjects
        classes = Class.objects.filter(
            academic_year=academic_year,
            timetable_entries__subject__department=department,
        ).distinct()
        class_count = classes.count()

        # Get students studying these subjects
        from src.students.models import Student

        students = Student.objects.filter(current_class__in=classes).distinct()
        student_count = students.count()

        # Get assignment analytics
        assignments = Assignment.objects.filter(
            subject__department=department, class_obj__academic_year=academic_year
        )
        assignment_count = assignments.count()

        # Get exam performance
        from src.exams.models import StudentExamResult

        exam_results = StudentExamResult.objects.filter(
            exam_schedule__subject__department=department,
            exam_schedule__exam__academic_year=academic_year,
        )

        average_score = exam_results.aggregate(avg=Avg("marks_obtained"))["avg"] or 0
        pass_rate = (
            exam_results.filter(is_pass=True).count() / max(exam_results.count(), 1)
        ) * 100

        # Subject performance breakdown
        subject_performance = {}
        for subject in subjects:
            subject_results = exam_results.filter(exam_schedule__subject=subject)
            subject_classes = classes.filter(
                timetable_entries__subject=subject
            ).distinct()
            subject_students = students.filter(
                current_class__in=subject_classes
            ).distinct()

            if subject_results.exists():
                subject_performance[subject.name] = {
                    "subject_id": subject.id,
                    "code": subject.code,
                    "credit_hours": subject.credit_hours,
                    "average_score": subject_results.aggregate(
                        avg=Avg("marks_obtained")
                    )["avg"]
                    or 0,
                    "pass_rate": (
                        (
                            subject_results.filter(is_pass=True).count()
                            / subject_results.count()
                        )
                        * 100
                        if subject_results.count() > 0
                        else 0
                    ),
                    "class_count": subject_classes.count(),
                    "student_count": subject_students.count(),
                }
            else:
                subject_performance[subject.name] = {
                    "subject_id": subject.id,
                    "code": subject.code,
                    "credit_hours": subject.credit_hours,
                    "average_score": 0,
                    "pass_rate": 0,
                    "class_count": subject_classes.count(),
                    "student_count": subject_students.count(),
                }

        # Teacher performance
        teacher_performance = {}
        from src.teachers.models import Teacher

        teachers = Teacher.objects.filter(department=department)
        teacher_count = teachers.count()

        for teacher in teachers:
            teacher_results = exam_results.filter(
                exam_schedule__subject__timetable_entries__teacher=teacher
            ).distinct()

            teacher_classes = classes.filter(
                timetable_entries__teacher=teacher
            ).distinct()

            if teacher_results.exists():
                teacher_performance[teacher.user.get_full_name()] = {
                    "id": teacher.id,
                    "average_score": teacher_results.aggregate(
                        avg=Avg("marks_obtained")
                    )["avg"]
                    or 0,
                    "pass_rate": (
                        (
                            teacher_results.filter(is_pass=True).count()
                            / teacher_results.count()
                        )
                        * 100
                        if teacher_results.count() > 0
                        else 0
                    ),
                    "class_count": teacher_classes.count(),
                    "subject_count": teacher_classes.annotate(
                        subject_count=Count("timetable_entries__subject", distinct=True)
                    ).aggregate(total=Sum("subject_count"))["total"]
                    or 0,
                }
            else:
                teacher_performance[teacher.user.get_full_name()] = {
                    "id": teacher.id,
                    "average_score": 0,
                    "pass_rate": 0,
                    "class_count": teacher_classes.count(),
                    "subject_count": teacher_classes.annotate(
                        subject_count=Count("timetable_entries__subject", distinct=True)
                    ).aggregate(total=Sum("subject_count"))["total"]
                    or 0,
                }

        # Teacher workload analysis
        teacher_workload = {}
        for teacher in teachers:
            timetable_entries = Timetable.objects.filter(
                teacher=teacher,
                class_obj__academic_year=academic_year,
                is_active=True,
            )

            weekly_hours = (
                sum(entry.time_slot.duration_minutes for entry in timetable_entries)
                / 60
            )

            teacher_workload[teacher.user.get_full_name()] = weekly_hours

        return {
            "department": department.name,
            "academic_year": academic_year.name,
            "subject_count": subject_count,
            "class_count": class_count,
            "student_count": student_count,
            "teacher_count": teacher_count,
            "assignment_count": assignment_count,
            "average_score": average_score,
            "pass_rate": pass_rate,
            "subject_performance": subject_performance,
            "teacher_performance": teacher_performance,
            "teacher_workload": teacher_workload,
        }

    @staticmethod
    def get_class_analytics(class_obj):
        """Get comprehensive analytics for a class"""
        # Get students in class
        students = class_obj.students.all()
        student_count = students.count()

        # Get attendance data
        from src.attendance.models import Attendance

        attendances = Attendance.objects.filter(class_id=class_obj)
        total_attendance = attendances.count()

        present_count = attendances.filter(status="Present").count()
        average_attendance = (
            (present_count / total_attendance * 100) if total_attendance > 0 else 0
        )

        # Monthly attendance breakdown
        months = range(1, 13)
        monthly_attendance = {}

        for month in months:
            month_attendances = attendances.filter(date__month=month)
            if month_attendances.exists():
                present_count = month_attendances.filter(status="Present").count()
                total_count = month_attendances.count()
                monthly_attendance[month] = (
                    (present_count / total_count) * 100 if total_count > 0 else 0
                )
            else:
                monthly_attendance[month] = 0

        # Assignment completion
        assignments = Assignment.objects.filter(class_obj=class_obj)
        assignment_count = assignments.count()

        submissions = AssignmentSubmission.objects.filter(
            assignment__class_obj=class_obj
        )
        submission_count = submissions.count()
        expected_submissions = assignment_count * student_count

        completion_rate = (
            (submission_count / expected_submissions) * 100
            if expected_submissions > 0
            else 0
        )
        on_time_rate = (
            (submissions.filter(status="submitted").count() / submission_count) * 100
            if submission_count > 0
            else 0
        )
        late_rate = (
            (submissions.filter(status="late").count() / submission_count) * 100
            if submission_count > 0
            else 0
        )
        missing_rate = 100 - completion_rate

        # Exam performance
        from src.exams.models import StudentExamResult

        exam_results = StudentExamResult.objects.filter(
            student__current_class=class_obj,
            exam_schedule__exam__academic_year=class_obj.academic_year,
        )

        total_results = exam_results.count()
        pass_count = (
            exam_results.filter(is_pass=True).count() if total_results > 0 else 0
        )

        # Overall performance metrics
        average_score = exam_results.aggregate(avg=Avg("marks_obtained"))["avg"] or 0
        pass_rate = (pass_count / total_results) * 100 if total_results > 0 else 0

        # Subject performance breakdown
        subjects = Subject.objects.filter(
            timetable_entries__class_obj=class_obj
        ).distinct()
        subject_performance = {}

        for subject in subjects:
            subject_results = exam_results.filter(exam_schedule__subject=subject)
            if subject_results.exists():
                subject_performance[subject.name] = {
                    "average_score": subject_results.aggregate(
                        avg=Avg("marks_obtained")
                    )["avg"]
                    or 0,
                    "pass_rate": (
                        (
                            subject_results.filter(is_pass=True).count()
                            / subject_results.count()
                        )
                        * 100
                        if subject_results.count() > 0
                        else 0
                    ),
                    "highest_score": (
                        subject_results.aggregate(max_score=max("marks_obtained"))[
                            "max_score"
                        ]
                        if subject_results.count() > 0
                        else 0
                    ),
                    "lowest_score": (
                        subject_results.aggregate(min_score=min("marks_obtained"))[
                            "min_score"
                        ]
                        if subject_results.count() > 0
                        else 0
                    ),
                }
            else:
                subject_performance[subject.name] = {
                    "average_score": 0,
                    "pass_rate": 0,
                    "highest_score": 0,
                    "lowest_score": 0,
                }

        # Student performance
        student_performance = []
        for student in students:
            student_results = exam_results.filter(student=student)
            student_attendances = attendances.filter(student=student)
            student_submissions = submissions.filter(student=student)

            # Calculate student metrics
            student_average_score = (
                student_results.aggregate(avg=Avg("marks_obtained"))["avg"] or 0
            )
            student_attendance_rate = (
                (
                    student_attendances.filter(status="Present").count()
                    / student_attendances.count()
                )
                * 100
                if student_attendances.exists()
                else 0
            )
            student_assignment_completion = (
                (student_submissions.count() / assignment_count) * 100
                if assignment_count > 0
                else 0
            )

            student_performance.append(
                {
                    "student": student,
                    "average_score": student_average_score,
                    "attendance_rate": student_attendance_rate,
                    "assignment_completion": student_assignment_completion,
                }
            )

        # Sort student performance for top performers and struggling students
        sorted_by_score = sorted(
            student_performance, key=lambda x: x["average_score"], reverse=True
        )
        top_performers = (
            sorted_by_score[:5] if len(sorted_by_score) >= 5 else sorted_by_score
        )
        struggling_students = (
            sorted_by_score[-5:] if len(sorted_by_score) >= 5 else sorted_by_score
        )

        # Calculate assignment stats by subject
        assignment_stats = {}
        for subject in subjects:
            subject_assignments = assignments.filter(subject=subject)
            subject_submissions = submissions.filter(assignment__subject=subject)
            expected_subject_submissions = subject_assignments.count() * student_count

            assignment_stats[subject.name] = {
                "count": subject_assignments.count(),
                "completion_rate": (
                    (subject_submissions.count() / expected_subject_submissions) * 100
                    if expected_subject_submissions > 0
                    else 0
                ),
            }

        # Grade distribution data
        grade_distribution = {}
        for result in exam_results:
            grade = result.grade
            if grade in grade_distribution:
                grade_distribution[grade] += 1
            else:
                grade_distribution[grade] = 1

        return {
            "class_name": str(class_obj),
            "student_count": student_count,
            "occupancy_rate": class_obj.occupancy_rate,
            "assignment_count": assignment_count,
            "completion_rate": completion_rate,
            "on_time_rate": on_time_rate,
            "late_rate": late_rate,
            "missing_rate": missing_rate,
            "average_attendance": average_attendance,
            "monthly_attendance": monthly_attendance,
            "average_score": average_score,
            "pass_rate": pass_rate,
            "subject_performance": subject_performance,
            "student_performance": student_performance,
            "top_performers": top_performers,
            "struggling_students": struggling_students,
            "grade_distribution": grade_distribution,
            "assignment_stats": assignment_stats,
        }

    @staticmethod
    def get_subject_analytics(subject, academic_year=None):
        """Get comprehensive analytics for a subject"""
        if not academic_year:
            academic_year = AcademicYear.objects.filter(is_current=True).first()
            if not academic_year:
                return {
                    "subject_name": subject.name,
                    "error": "No current academic year found",
                }

        # Get classes studying this subject
        classes = Class.objects.filter(
            academic_year=academic_year, timetable_entries__subject=subject
        ).distinct()

        class_count = classes.count()

        # Get students studying this subject
        from src.students.models import Student

        students = Student.objects.filter(current_class__in=classes).distinct()

        student_count = students.count()

        # Get exam performance
        from src.exams.models import StudentExamResult

        exam_results = StudentExamResult.objects.filter(
            exam_schedule__subject=subject,
            exam_schedule__exam__academic_year=academic_year,
        )

        total_results = exam_results.count()

        # Overall performance
        average_score = exam_results.aggregate(avg=Avg("marks_obtained"))["avg"] or 0
        pass_rate = (
            exam_results.filter(is_pass=True).count() / max(total_results, 1)
        ) * 100

        # Grade distribution
        grade_distribution = {}
        for grade_item in exam_results.values("grade").annotate(count=Count("id")):
            grade_distribution[grade_item["grade"]] = (
                (grade_item["count"] / total_results) * 100 if total_results > 0 else 0
            )

        # Class performance breakdown
        class_performance = {}
        for class_obj in classes:
            class_results = exam_results.filter(student__current_class=class_obj)
            class_students = students.filter(current_class=class_obj)

            if class_results.exists():
                class_performance[str(class_obj)] = {
                    "average_score": class_results.aggregate(avg=Avg("marks_obtained"))[
                        "avg"
                    ]
                    or 0,
                    "pass_rate": (
                        class_results.filter(is_pass=True).count()
                        / class_results.count()
                    )
                    * 100,
                    "student_count": class_students.count(),
                }
            else:
                class_performance[str(class_obj)] = {
                    "average_score": 0,
                    "pass_rate": 0,
                    "student_count": class_students.count(),
                }

        # Assignment analytics
        assignments = Assignment.objects.filter(
            subject=subject, class_obj__academic_year=academic_year
        )

        assignment_count = assignments.count()
        submissions = AssignmentSubmission.objects.filter(assignment__in=assignments)
        submission_count = submissions.count()

        expected_submissions = (
            assignment_count * student_count if assignment_count > 0 else 0
        )
        completion_rate = (
            (submission_count / expected_submissions) * 100
            if expected_submissions > 0
            else 0
        )

        # Teacher performance
        teacher_performance = {}
        teachers = set()
        for tt in Timetable.objects.filter(
            subject=subject, class_obj__academic_year=academic_year
        ):
            teachers.add(tt.teacher)

        for teacher in teachers:
            teacher_classes = classes.filter(
                timetable_entries__teacher=teacher, timetable_entries__subject=subject
            ).distinct()

            teacher_results = exam_results.filter(
                student__current_class__in=teacher_classes
            ).distinct()

            teacher_students = students.filter(
                current_class__in=teacher_classes
            ).distinct()

            if teacher_results.exists():
                teacher_performance[teacher.user.get_full_name()] = {
                    "average_score": teacher_results.aggregate(
                        avg=Avg("marks_obtained")
                    )["avg"]
                    or 0,
                    "pass_rate": (
                        teacher_results.filter(is_pass=True).count()
                        / teacher_results.count()
                    )
                    * 100,
                    "class_count": teacher_classes.count(),
                    "student_count": teacher_students.count(),
                }
            else:
                teacher_performance[teacher.user.get_full_name()] = {
                    "average_score": 0,
                    "pass_rate": 0,
                    "class_count": teacher_classes.count(),
                    "student_count": teacher_students.count(),
                }

        # Annual performance trend
        annual_performance = {}
        past_years = AcademicYear.objects.filter(
            end_date__lt=timezone.now().date()
        ).order_by("-end_date")[
            :3
        ]  # Last 3 years

        for year in past_years:
            year_results = StudentExamResult.objects.filter(
                exam_schedule__subject=subject,
                exam_schedule__exam__academic_year=year,
            )

            if year_results.exists():
                annual_performance[year.name] = {
                    "average_score": year_results.aggregate(avg=Avg("marks_obtained"))[
                        "avg"
                    ]
                    or 0,
                    "pass_rate": (
                        year_results.filter(is_pass=True).count() / year_results.count()
                    )
                    * 100,
                }
            else:
                annual_performance[year.name] = {
                    "average_score": 0,
                    "pass_rate": 0,
                }

        return {
            "subject_name": subject.name,
            "subject_code": subject.code,
            "department": subject.department.name,
            "academic_year": academic_year.name,
            "class_count": class_count,
            "student_count": student_count,
            "teacher_count": len(teachers),
            "assignment_count": assignment_count,
            "completion_rate": completion_rate,
            "average_score": average_score,
            "pass_rate": pass_rate,
            "grade_distribution": grade_distribution,
            "class_performance": class_performance,
            "teacher_performance": teacher_performance,
            "annual_performance": annual_performance,
        }

    @staticmethod
    def get_timetable_analytics(timetable_entries):
        """Generate analytics for a set of timetable entries"""
        subject_hours = {}
        day_distribution = {}
        teacher_workload = {}
        room_utilization = {}

        # Initialize days
        for day in range(7):
            day_distribution[day] = 0

        for entry in timetable_entries:
            # Subject hours
            subject_name = entry.subject.name
            minutes = entry.time_slot.duration_minutes
            hours = minutes / 60

            if subject_name in subject_hours:
                subject_hours[subject_name] += hours
            else:
                subject_hours[subject_name] = hours

            # Day distribution
            day = entry.time_slot.day_of_week
            day_distribution[day] += hours

            # Teacher workload
            teacher_name = entry.teacher.user.get_full_name()
            if teacher_name in teacher_workload:
                teacher_workload[teacher_name] += hours
            else:
                teacher_workload[teacher_name] = hours

            # Room utilization
            if entry.room:
                if entry.room in room_utilization:
                    room_utilization[entry.room] += hours
                else:
                    room_utilization[entry.room] = hours

        return {
            "subject_hours": subject_hours,
            "day_distribution": day_distribution,
            "teacher_workload": teacher_workload,
            "room_utilization": room_utilization,
        }

    @staticmethod
    def get_assignment_analytics(assignment):
        """Generate analytics for an assignment and its submissions"""
        from src.students.models import Student

        # Get all students in the class
        students = Student.objects.filter(current_class=assignment.class_obj)
        total_students = students.count()

        # Get all submissions
        submissions = AssignmentSubmission.objects.filter(assignment=assignment)
        submission_count = submissions.count()

        # Calculate rates
        submission_rate = (
            (submission_count / total_students) * 100 if total_students > 0 else 0
        )
        pending_rate = 100 - submission_rate

        # Status breakdown
        on_time_count = submissions.filter(status="submitted").count()
        late_count = submissions.filter(status="late").count()
        graded_count = submissions.filter(status="graded").count()

        on_time_percentage = (
            (on_time_count / submission_count) * 100 if submission_count > 0 else 0
        )
        late_percentage = (
            (late_count / submission_count) * 100 if submission_count > 0 else 0
        )
        grading_rate = (
            (graded_count / submission_count) * 100 if submission_count > 0 else 0
        )

        # Grade distribution (for graded submissions)
        graded_submissions = submissions.filter(status="graded")

        # Categorize by score range
        a_count = graded_submissions.filter(
            marks_obtained__gte=0.9 * assignment.total_marks
        ).count()
        b_count = graded_submissions.filter(
            marks_obtained__lt=0.9 * assignment.total_marks,
            marks_obtained__gte=0.8 * assignment.total_marks,
        ).count()
        c_count = graded_submissions.filter(
            marks_obtained__lt=0.8 * assignment.total_marks,
            marks_obtained__gte=0.7 * assignment.total_marks,
        ).count()
        d_count = graded_submissions.filter(
            marks_obtained__lt=0.7 * assignment.total_marks,
            marks_obtained__gte=0.6 * assignment.total_marks,
        ).count()
        f_count = graded_submissions.filter(
            marks_obtained__lt=0.6 * assignment.total_marks
        ).count()

        total_graded = graded_submissions.count()

        # Calculate percentages
        grade_a_percentage = (a_count / total_graded) * 100 if total_graded > 0 else 0
        grade_b_percentage = (b_count / total_graded) * 100 if total_graded > 0 else 0
        grade_c_percentage = (c_count / total_graded) * 100 if total_graded > 0 else 0
        grade_d_percentage = (d_count / total_graded) * 100 if total_graded > 0 else 0
        grade_f_percentage = (f_count / total_graded) * 100 if total_graded > 0 else 0

        # Prepare all students data with submission status
        all_students = []
        for student in students:
            submission = submissions.filter(student=student).first()
            all_students.append(
                {
                    "id": student.id,
                    "name": student.user.get_full_name(),
                    "admission_number": student.admission_number,
                    "has_submitted": submission is not None,
                    "submission": submission,
                }
            )

        # Sort by name
        all_students.sort(key=lambda x: x["name"])

        return {
            "total_students": total_students,
            "submissions": submissions,
            "submission_count": submission_count,
            "submission_rate": submission_rate,
            "pending_rate": pending_rate,
            "on_time_count": on_time_count,
            "late_count": late_count,
            "graded_count": graded_count,
            "on_time_percentage": on_time_percentage,
            "late_percentage": late_percentage,
            "grading_rate": grading_rate,
            "grade_a_percentage": grade_a_percentage,
            "grade_b_percentage": grade_b_percentage,
            "grade_c_percentage": grade_c_percentage,
            "grade_d_percentage": grade_d_percentage,
            "grade_f_percentage": grade_f_percentage,
            "all_students": all_students,
        }
