from django.db import models
from django.conf import settings
from django.utils import timezone
from django.db.models import Count, Avg, Sum, Q, F, Max, Min, Case, When, Value
from django.core.exceptions import ValidationError
from django.core.cache import cache
from datetime import datetime, date, timedelta
import json


class Department(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    head = models.ForeignKey(
        "teachers.Teacher",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="headed_departments",
    )
    creation_date = models.DateField(auto_now_add=True)

    def __str__(self):
        return self.name

    @property
    def teacher_count(self):
        """Get the count of teachers in this department."""
        return self.teachers.count()

    @property
    def subject_count(self):
        """Get the count of subjects in this department."""
        return self.subjects.count()

    @property
    def student_count(self):
        """Get the total number of students studying subjects in this department."""
        from src.students.models import Student

        current_year = AcademicYear.objects.filter(is_current=True).first()
        if not current_year:
            return 0

        classes = Class.objects.filter(
            academic_year=current_year, timetable_entries__subject__department=self
        ).distinct()

        return Student.objects.filter(current_class__in=classes).distinct().count()

    def get_performance_statistics(self, academic_year=None):
        """Get performance statistics for subjects in this department."""
        from src.exams.models import StudentExamResult

        if not academic_year:
            academic_year = AcademicYear.objects.filter(is_current=True).first()
            if not academic_year:
                return {}

        exam_results = StudentExamResult.objects.filter(
            exam_schedule__subject__department=self,
            exam_schedule__exam__academic_year=academic_year,
        )

        return {
            "average_score": exam_results.aggregate(avg=Avg("marks_obtained"))["avg"]
            or 0,
            "pass_rate": (
                exam_results.filter(is_pass=True).count() / max(exam_results.count(), 1)
            )
            * 100,
            "subject_performance": {
                subject.name: {
                    "average": exam_results.filter(
                        exam_schedule__subject=subject
                    ).aggregate(avg=Avg("marks_obtained"))["avg"]
                    or 0,
                    "pass_rate": (
                        exam_results.filter(
                            exam_schedule__subject=subject, is_pass=True
                        ).count()
                        / max(
                            exam_results.filter(exam_schedule__subject=subject).count(),
                            1,
                        )
                    )
                    * 100,
                }
                for subject in self.subjects.all()
            },
        }


class AcademicYear(models.Model):
    name = models.CharField(max_length=50)
    start_date = models.DateField()
    end_date = models.DateField()
    is_current = models.BooleanField(default=False)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        # Ensure only one academic year is marked as current
        if self.is_current:
            AcademicYear.objects.filter(is_current=True).update(is_current=False)
        super().save(*args, **kwargs)

    @property
    def duration_days(self):
        """Get the duration of the academic year in days."""
        return (self.end_date - self.start_date).days

    @property
    def is_active(self):
        """Check if the academic year is currently active."""
        today = timezone.now().date()
        return self.start_date <= today <= self.end_date

    @property
    def progress_percentage(self):
        """Get the percentage of the academic year that has elapsed."""
        today = timezone.now().date()
        if today < self.start_date:
            return 0
        if today > self.end_date:
            return 100

        elapsed = (today - self.start_date).days
        total = self.duration_days
        return (elapsed / total) * 100 if total > 0 else 0

    @property
    def class_count(self):
        """Get the number of classes in this academic year."""
        return self.classes.count()

    @property
    def student_count(self):
        """Get the number of students enrolled in this academic year."""
        from src.students.models import Student

        return Student.objects.filter(current_class__academic_year=self).count()

    @classmethod
    def get_current(cls):
        """Get the current academic year, or None if not set."""
        return cls.objects.filter(is_current=True).first()

    def get_attendance_statistics(self):
        """Get attendance statistics for this academic year."""
        from src.attendance.models import Attendance

        attendance = Attendance.objects.filter(class_id__academic_year=self)

        total_records = attendance.count()
        if total_records == 0:
            return {"average_attendance_rate": 0, "monthly_rates": {}}

        present_count = attendance.filter(status="Present").count()

        # Monthly breakdown
        monthly_stats = {}
        for month in range(1, 13):
            month_attendance = attendance.filter(date__month=month)
            month_total = month_attendance.count()
            month_present = month_attendance.filter(status="Present").count()
            if month_total > 0:
                monthly_stats[month] = (month_present / month_total) * 100
            else:
                monthly_stats[month] = 0

        return {
            "average_attendance_rate": (present_count / total_records) * 100,
            "monthly_rates": monthly_stats,
        }

    def get_performance_statistics(self):
        """Get overall performance statistics for this academic year."""
        from src.exams.models import StudentExamResult

        results = StudentExamResult.objects.filter(
            exam_schedule__exam__academic_year=self
        )

        total_results = results.count()
        if total_results == 0:
            return {"average_score": 0, "pass_rate": 0, "grade_distribution": {}}

        pass_count = results.filter(is_pass=True).count()

        # Grade distribution
        grade_distribution = {}
        for grade in results.values("grade").annotate(count=Count("id")):
            grade_distribution[grade["grade"]] = (grade["count"] / total_results) * 100

        return {
            "average_score": results.aggregate(avg=Avg("marks_obtained"))["avg"] or 0,
            "pass_rate": (pass_count / total_results) * 100,
            "grade_distribution": grade_distribution,
        }


class Grade(models.Model):
    name = models.CharField(max_length=50)
    description = models.TextField(blank=True)
    department = models.ForeignKey(
        Department, on_delete=models.CASCADE, related_name="grades"
    )

    def __str__(self):
        return self.name

    @property
    def current_student_count(self):
        """Get the number of students currently in this grade."""
        current_year = AcademicYear.objects.filter(is_current=True).first()
        if not current_year:
            return 0

        from src.students.models import Student

        return Student.objects.filter(
            current_class__grade=self, current_class__academic_year=current_year
        ).count()

    @property
    def current_class_count(self):
        """Get the number of classes currently in this grade."""
        current_year = AcademicYear.objects.filter(is_current=True).first()
        if not current_year:
            return 0

        return self.classes.filter(academic_year=current_year).count()

    def get_gender_distribution(self, academic_year=None):
        """Get gender distribution of students in this grade."""
        from src.students.models import Student

        if not academic_year:
            academic_year = AcademicYear.objects.filter(is_current=True).first()
            if not academic_year:
                return {"M": 0, "F": 0, "O": 0}

        students = Student.objects.filter(
            current_class__grade=self, current_class__academic_year=academic_year
        )

        total = students.count()
        if total == 0:
            return {"M": 0, "F": 0, "O": 0}

        gender_counts = {
            gender: students.filter(user__gender=gender).count()
            for gender in ["M", "F", "O"]
        }

        return {
            gender: (count / total) * 100 for gender, count in gender_counts.items()
        }

    def get_performance_trend(self, years=3):
        """Get performance trend over recent academic years."""
        from src.exams.models import StudentExamResult

        current_year = AcademicYear.objects.filter(is_current=True).first()
        if not current_year:
            return {}

        # Get recent academic years
        recent_years = AcademicYear.objects.filter(
            end_date__lte=current_year.end_date
        ).order_by("-end_date")[:years]

        trend = {}
        for year in recent_years:
            results = StudentExamResult.objects.filter(
                exam_schedule__exam__academic_year=year,
                student__current_class__grade=self,
            )

            if results.exists():
                trend[year.name] = {
                    "average_score": results.aggregate(avg=Avg("marks_obtained"))["avg"]
                    or 0,
                    "pass_rate": (
                        results.filter(is_pass=True).count() / results.count()
                    )
                    * 100,
                }
            else:
                trend[year.name] = {"average_score": 0, "pass_rate": 0}

        return trend


class Section(models.Model):
    name = models.CharField(max_length=20)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name

    @property
    def current_student_count(self):
        """Get the number of students currently in this section."""
        current_year = AcademicYear.objects.filter(is_current=True).first()
        if not current_year:
            return 0

        from src.students.models import Student

        return Student.objects.filter(
            current_class__section=self, current_class__academic_year=current_year
        ).count()

    @property
    def current_class_count(self):
        """Get the number of classes currently using this section."""
        current_year = AcademicYear.objects.filter(is_current=True).first()
        if not current_year:
            return 0

        return self.classes.filter(academic_year=current_year).count()


class Class(models.Model):
    grade = models.ForeignKey(Grade, on_delete=models.CASCADE, related_name="classes")
    section = models.ForeignKey(
        Section, on_delete=models.CASCADE, related_name="classes"
    )
    academic_year = models.ForeignKey(
        AcademicYear, on_delete=models.CASCADE, related_name="classes"
    )
    room_number = models.CharField(max_length=20, blank=True)
    capacity = models.PositiveIntegerField(default=30)
    class_teacher = models.ForeignKey(
        to="teachers.Teacher",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_classes",
    )

    class Meta:
        verbose_name_plural = "Classes"
        unique_together = ("grade", "section", "academic_year")

    def __str__(self):
        return f"{self.grade.name} - {self.section.name} ({self.academic_year.name})"

    @property
    def student_count(self):
        """Get the number of students in this class."""
        return self.students.count()

    @property
    def vacancy_count(self):
        """Get the number of vacant seats in this class."""
        return max(0, self.capacity - self.student_count)

    @property
    def occupancy_rate(self):
        """Get the occupancy rate of this class."""
        if self.capacity == 0:
            return 0
        return (self.student_count / self.capacity) * 100

    @property
    def subject_count(self):
        """Get the number of subjects assigned to this class."""
        return (
            Subject.objects.filter(timetable_entries__class_obj=self).distinct().count()
        )

    @property
    def is_current(self):
        """Check if this class belongs to the current academic year."""
        return self.academic_year.is_current

    def get_gender_distribution(self):
        """Get gender distribution of students in this class."""
        total = self.students.count()
        if total == 0:
            return {"M": 0, "F": 0, "O": 0}

        gender_counts = {
            gender: self.students.filter(user__gender=gender).count()
            for gender in ["M", "F", "O"]
        }

        return {
            gender: (count / total) * 100 for gender, count in gender_counts.items()
        }

    def get_attendance_statistics(self, start_date=None, end_date=None):
        """Get attendance statistics for this class."""
        from src.attendance.models import Attendance

        query = Attendance.objects.filter(class_id=self)

        if start_date:
            query = query.filter(date__gte=start_date)
        if end_date:
            query = query.filter(date__lte=end_date)

        total_records = query.count()
        if total_records == 0:
            return {"average_attendance_rate": 0, "student_rates": {}}

        present_count = query.filter(status="Present").count()

        # Student-wise attendance
        student_stats = {}
        for student in self.students.all():
            student_attendance = query.filter(student=student)
            student_total = student_attendance.count()
            student_present = student_attendance.filter(status="Present").count()
            if student_total > 0:
                student_stats[student.id] = {
                    "name": student.get_full_name(),
                    "attendance_rate": (student_present / student_total) * 100,
                }
            else:
                student_stats[student.id] = {
                    "name": student.get_full_name(),
                    "attendance_rate": 0,
                }

        return {
            "average_attendance_rate": (present_count / total_records) * 100,
            "student_rates": student_stats,
        }

    def get_assignment_completion_rate(self):
        """Get assignment completion rates for this class."""
        assignments = Assignment.objects.filter(
            class_obj=self, status__in=["published", "closed"]
        )

        total_assignments = assignments.count()
        if total_assignments == 0:
            return {"overall_rate": 0, "student_rates": {}}

        student_stats = {}
        for student in self.students.all():
            student_submissions = AssignmentSubmission.objects.filter(
                assignment__in=assignments, student=student
            ).count()

            submission_rate = (student_submissions / total_assignments) * 100
            student_stats[student.id] = {
                "name": student.get_full_name(),
                "submission_rate": submission_rate,
            }

        total_submissions = AssignmentSubmission.objects.filter(
            assignment__in=assignments
        ).count()

        expected_submissions = total_assignments * self.students.count()
        overall_rate = (
            (total_submissions / expected_submissions) * 100
            if expected_submissions > 0
            else 0
        )

        return {"overall_rate": overall_rate, "student_rates": student_stats}

    def get_performance_statistics(self):
        """Get academic performance statistics for this class."""
        from src.exams.models import StudentExamResult

        results = StudentExamResult.objects.filter(
            student__current_class=self,
            exam_schedule__exam__academic_year=self.academic_year,
        )

        total_results = results.count()
        if total_results == 0:
            return {"average_score": 0, "pass_rate": 0, "subject_stats": {}}

        pass_count = results.filter(is_pass=True).count()

        # Subject-wise performance
        subject_stats = {}
        subjects = Subject.objects.filter(timetable_entries__class_obj=self).distinct()

        for subject in subjects:
            subject_results = results.filter(exam_schedule__subject=subject)
            if subject_results.exists():
                subject_stats[subject.name] = {
                    "average_score": subject_results.aggregate(
                        avg=Avg("marks_obtained")
                    )["avg"]
                    or 0,
                    "pass_rate": (
                        subject_results.filter(is_pass=True).count()
                        / subject_results.count()
                    )
                    * 100,
                }
            else:
                subject_stats[subject.name] = {"average_score": 0, "pass_rate": 0}

        return {
            "average_score": results.aggregate(avg=Avg("marks_obtained"))["avg"] or 0,
            "pass_rate": (pass_count / total_results) * 100,
            "subject_stats": subject_stats,
        }


class Subject(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20, unique=True)
    description = models.TextField(blank=True)
    color = models.CharField(
        max_length=20, default="#4e73df", help_text="Color for timetable display"
    )
    department = models.ForeignKey(
        Department, on_delete=models.CASCADE, related_name="subjects"
    )
    credit_hours = models.DecimalField(max_digits=3, decimal_places=1, default=1.0)
    is_elective = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.name} ({self.code})"

    @property
    def current_class_count(self):
        """Get the number of classes currently studying this subject."""
        current_year = AcademicYear.objects.filter(is_current=True).first()
        if not current_year:
            return 0

        return (
            Class.objects.filter(
                timetable_entries__subject=self, academic_year=current_year
            )
            .distinct()
            .count()
        )

    @property
    def current_student_count(self):
        """Get the number of students currently studying this subject."""
        current_year = AcademicYear.objects.filter(is_current=True).first()
        if not current_year:
            return 0

        from src.students.models import Student

        return (
            Student.objects.filter(
                current_class__timetable_entries__subject=self,
                current_class__academic_year=current_year,
            )
            .distinct()
            .count()
        )

    @property
    def current_teacher_count(self):
        """Get the number of teachers currently teaching this subject."""
        current_year = AcademicYear.objects.filter(is_current=True).first()
        if not current_year:
            return 0

        return (
            self.teacher_assignments.filter(academic_year=current_year)
            .values("teacher")
            .distinct()
            .count()
        )

    def get_performance_statistics(self, academic_year=None):
        """Get performance statistics for this subject."""
        from src.exams.models import StudentExamResult

        if not academic_year:
            academic_year = AcademicYear.objects.filter(is_current=True).first()
            if not academic_year:
                return {"average_score": 0, "pass_rate": 0, "grade_distribution": {}}

        results = StudentExamResult.objects.filter(
            exam_schedule__subject=self,
            exam_schedule__exam__academic_year=academic_year,
        )

        total_results = results.count()
        if total_results == 0:
            return {"average_score": 0, "pass_rate": 0, "grade_distribution": {}}

        pass_count = results.filter(is_pass=True).count()

        # Grade distribution
        grade_distribution = {}
        for grade in results.values("grade").annotate(count=Count("id")):
            grade_distribution[grade["grade"]] = (grade["count"] / total_results) * 100

        # Class-wise performance
        class_stats = {}
        classes = Class.objects.filter(
            timetable_entries__subject=self, academic_year=academic_year
        )

        for class_obj in classes:
            class_results = results.filter(student__current_class=class_obj)
            if class_results.exists():
                class_stats[str(class_obj)] = {
                    "average_score": class_results.aggregate(avg=Avg("marks_obtained"))[
                        "avg"
                    ]
                    or 0,
                    "pass_rate": (
                        class_results.filter(is_pass=True).count()
                        / class_results.count()
                    )
                    * 100,
                }
            else:
                class_stats[str(class_obj)] = {"average_score": 0, "pass_rate": 0}

        return {
            "average_score": results.aggregate(avg=Avg("marks_obtained"))["avg"] or 0,
            "pass_rate": (pass_count / total_results) * 100,
            "grade_distribution": grade_distribution,
            "class_stats": class_stats,
        }

    def get_annual_performance_trend(self, years=3):
        """Get annual performance trend for this subject."""
        from src.exams.models import StudentExamResult

        current_year = AcademicYear.objects.filter(is_current=True).first()
        if not current_year:
            return {}

        # Get recent academic years
        recent_years = AcademicYear.objects.filter(
            end_date__lte=current_year.end_date
        ).order_by("-end_date")[:years]

        trend = {}
        for year in recent_years:
            results = StudentExamResult.objects.filter(
                exam_schedule__subject=self, exam_schedule__exam__academic_year=year
            )

            if results.exists():
                trend[year.name] = {
                    "average_score": results.aggregate(avg=Avg("marks_obtained"))["avg"]
                    or 0,
                    "pass_rate": (
                        results.filter(is_pass=True).count() / results.count()
                    )
                    * 100,
                }
            else:
                trend[year.name] = {"average_score": 0, "pass_rate": 0}

        return trend


class Syllabus(models.Model):
    subject = models.ForeignKey(
        Subject, on_delete=models.CASCADE, related_name="syllabi"
    )
    grade = models.ForeignKey(Grade, on_delete=models.CASCADE, related_name="syllabi")
    academic_year = models.ForeignKey(
        AcademicYear, on_delete=models.CASCADE, related_name="syllabi"
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    content = models.JSONField(default=dict)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="created_syllabi",
    )
    last_updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="updated_syllabi",
    )
    last_updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Syllabi"
        unique_together = ("subject", "grade", "academic_year")

    def __str__(self):
        return f"Syllabus for {self.subject.name} - {self.grade.name} ({self.academic_year.name})"

    @property
    def completion_percentage(self):
        """Calculate the percentage of syllabus completed."""
        try:
            total_items = len(self.content.get("units", []))
            if total_items == 0:
                return 0

            completed_items = sum(
                1
                for unit in self.content.get("units", [])
                if unit.get("status", "") == "completed"
            )

            return (completed_items / total_items) * 100
        except (AttributeError, KeyError, TypeError):
            return 0

    @property
    def is_complete(self):
        """Check if the syllabus is 100% complete."""
        return self.completion_percentage == 100

    @property
    def is_current(self):
        """Check if this syllabus belongs to the current academic year."""
        return self.academic_year.is_current

    def get_completion_timeline(self):
        """Get a timeline of syllabus completion."""
        try:
            units = self.content.get("units", [])
            timeline = []

            for unit in units:
                if "completion_date" in unit and unit.get("status", "") == "completed":
                    timeline.append(
                        {
                            "unit": unit.get("title", "Unknown Unit"),
                            "completion_date": unit["completion_date"],
                            "duration_days": unit.get("duration_days", 0),
                        }
                    )

            return sorted(timeline, key=lambda x: x["completion_date"])
        except (AttributeError, KeyError, TypeError):
            return []

    def get_topic_count(self):
        """Get the total number of topics in the syllabus."""
        try:
            topic_count = 0
            for unit in self.content.get("units", []):
                topic_count += len(unit.get("topics", []))
            return topic_count
        except (AttributeError, KeyError, TypeError):
            return 0


class TimeSlot(models.Model):
    DAY_CHOICES = [
        (0, "Monday"),
        (1, "Tuesday"),
        (2, "Wednesday"),
        (3, "Thursday"),
        (4, "Friday"),
        (5, "Saturday"),
        (6, "Sunday"),
    ]

    day_of_week = models.IntegerField(choices=DAY_CHOICES)
    start_time = models.TimeField()
    end_time = models.TimeField()
    duration_minutes = models.PositiveIntegerField()

    def __str__(self):
        return f"{self.get_day_of_week_display()} {self.start_time} - {self.end_time}"

    def save(self, *args, **kwargs):
        # Calculate duration in minutes
        start_datetime = datetime.combine(date.today(), self.start_time)
        end_datetime = datetime.combine(date.today(), self.end_time)
        delta = end_datetime - start_datetime
        self.duration_minutes = delta.seconds // 60
        super().save(*args, **kwargs)

    @property
    def usage_count(self):
        """Get the number of timetable entries using this time slot."""
        return self.timetable_entries.count()

    @property
    def current_usage_count(self):
        """Get the number of current timetable entries using this time slot."""
        current_year = AcademicYear.objects.filter(is_current=True).first()
        if not current_year:
            return 0

        return self.timetable_entries.filter(
            class_obj__academic_year=current_year, is_active=True
        ).count()

    def get_subject_distribution(self):
        """Get the distribution of subjects using this time slot."""
        subject_counts = self.timetable_entries.values("subject__name").annotate(
            count=Count("id")
        )
        total = self.usage_count

        if total == 0:
            return {}

        return {
            item["subject__name"]: (item["count"] / total) * 100
            for item in subject_counts
        }

    def get_teacher_distribution(self):
        """Get the distribution of teachers using this time slot."""
        teacher_counts = self.timetable_entries.values(
            "teacher__user__first_name", "teacher__user__last_name"
        ).annotate(count=Count("id"))

        total = self.usage_count

        if total == 0:
            return {}

        return {
            f"{item['teacher__user__first_name']} {item['teacher__user__last_name']}": (
                item["count"] / total
            )
            * 100
            for item in teacher_counts
        }


class Timetable(models.Model):
    class_obj = models.ForeignKey(
        Class, on_delete=models.CASCADE, related_name="timetable_entries"
    )
    subject = models.ForeignKey(
        Subject, on_delete=models.CASCADE, related_name="timetable_entries"
    )
    teacher = models.ForeignKey(
        "teachers.Teacher", on_delete=models.CASCADE, related_name="timetable_entries"
    )
    time_slot = models.ForeignKey(
        TimeSlot, on_delete=models.CASCADE, related_name="timetable_entries"
    )
    room = models.CharField(max_length=20, blank=True)
    effective_from_date = models.DateField()
    effective_to_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.class_obj} - {self.subject} - {self.time_slot}"

    @property
    def is_current(self):
        """Check if this timetable entry is for the current academic year."""
        return self.class_obj.academic_year.is_current

    @property
    def duration_days(self):
        """Get the duration of this timetable entry in days."""
        if not self.effective_to_date:
            today = timezone.now().date()
            return (today - self.effective_from_date).days

        return (self.effective_to_date - self.effective_from_date).days

    @classmethod
    def get_teacher_schedule(cls, teacher, day=None, academic_year=None):
        """Get the schedule for a specific teacher."""
        query = cls.objects.filter(teacher=teacher, is_active=True)

        if day is not None:
            query = query.filter(time_slot__day_of_week=day)

        if academic_year:
            query = query.filter(class_obj__academic_year=academic_year)
        else:
            # Default to current academic year
            current_year = AcademicYear.objects.filter(is_current=True).first()
            if current_year:
                query = query.filter(class_obj__academic_year=current_year)

        return query.select_related(
            "class_obj",
            "subject",
            "time_slot",
            "class_obj__grade",
            "class_obj__section",
        ).order_by("time_slot__day_of_week", "time_slot__start_time")

    @classmethod
    def get_class_schedule(cls, class_obj, day=None):
        """Get the schedule for a specific class."""
        query = cls.objects.filter(class_obj=class_obj, is_active=True)

        if day is not None:
            query = query.filter(time_slot__day_of_week=day)

        return query.select_related(
            "subject", "teacher", "time_slot", "teacher__user"
        ).order_by("time_slot__day_of_week", "time_slot__start_time")

    @classmethod
    def get_room_schedule(cls, room, day=None, academic_year=None):
        """Get the schedule for a specific room."""
        query = cls.objects.filter(room=room, is_active=True)

        if day is not None:
            query = query.filter(time_slot__day_of_week=day)

        if academic_year:
            query = query.filter(class_obj__academic_year=academic_year)
        else:
            # Default to current academic year
            current_year = AcademicYear.objects.filter(is_current=True).first()
            if current_year:
                query = query.filter(class_obj__academic_year=current_year)

        return query.select_related(
            "class_obj",
            "subject",
            "teacher",
            "time_slot",
            "teacher__user",
            "class_obj__grade",
            "class_obj__section",
        ).order_by("time_slot__day_of_week", "time_slot__start_time")

    @classmethod
    def get_subject_schedule(cls, subject, academic_year=None):
        """Get the schedule for a specific subject."""
        query = cls.objects.filter(subject=subject, is_active=True)

        if academic_year:
            query = query.filter(class_obj__academic_year=academic_year)
        else:
            # Default to current academic year
            current_year = AcademicYear.objects.filter(is_current=True).first()
            if current_year:
                query = query.filter(class_obj__academic_year=current_year)

        return query.select_related(
            "class_obj",
            "teacher",
            "time_slot",
            "teacher__user",
            "class_obj__grade",
            "class_obj__section",
        ).order_by("time_slot__day_of_week", "time_slot__start_time")


class Assignment(models.Model):
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("published", "Published"),
        ("closed", "Closed"),
    ]

    SUBMISSION_CHOICES = [
        ("online", "Online"),
        ("physical", "Physical"),
    ]

    title = models.CharField(max_length=200)
    description = models.TextField()
    class_obj = models.ForeignKey(
        Class, on_delete=models.CASCADE, related_name="assignments"
    )
    subject = models.ForeignKey(
        Subject, on_delete=models.CASCADE, related_name="assignments"
    )
    teacher = models.ForeignKey(
        "teachers.Teacher", on_delete=models.CASCADE, related_name="assignments"
    )
    assigned_date = models.DateField(auto_now_add=True)
    due_date = models.DateField()
    total_marks = models.PositiveIntegerField()
    attachment = models.FileField(upload_to="assignments/", null=True, blank=True)
    submission_type = models.CharField(
        max_length=10, choices=SUBMISSION_CHOICES, default="online"
    )
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="draft")

    def __str__(self):
        return self.title

    @property
    def is_overdue(self):
        """Check if the assignment is past its due date."""
        return timezone.now().date() > self.due_date

    @property
    def days_remaining(self):
        """Get the number of days remaining until the due date."""
        today = timezone.now().date()
        if today > self.due_date:
            return 0
        return (self.due_date - today).days

    @property
    def submission_count(self):
        """Get the number of submissions for this assignment."""
        return self.submissions.count()

    @property
    def submission_rate(self):
        """Get the submission rate for this assignment."""
        student_count = self.class_obj.students.count()
        if student_count == 0:
            return 0
        return (self.submission_count / student_count) * 100

    @property
    def graded_count(self):
        """Get the number of graded submissions for this assignment."""
        return self.submissions.filter(status="graded").count()

    @property
    def grading_completion_rate(self):
        """Get the grading completion rate for this assignment."""
        if self.submission_count == 0:
            return 0
        return (self.graded_count / self.submission_count) * 100

    def get_grade_distribution(self):
        """Get the grade distribution for this assignment."""
        graded_submissions = self.submissions.filter(status="graded")
        total_graded = graded_submissions.count()

        if total_graded == 0:
            return {"average_score": 0, "score_ranges": {}}

        # Calculate average score
        average_score = (
            graded_submissions.aggregate(avg=Avg("marks_obtained"))["avg"] or 0
        )

        # Create score ranges
        ranges = {
            "91-100": 0,
            "81-90": 0,
            "71-80": 0,
            "61-70": 0,
            "51-60": 0,
            "41-50": 0,
            "31-40": 0,
            "21-30": 0,
            "11-20": 0,
            "0-10": 0,
        }

        # Calculate percentage for each submission
        for submission in graded_submissions:
            if submission.marks_obtained is not None:
                percentage = (submission.marks_obtained / self.total_marks) * 100

                # Assign to appropriate range
                if percentage > 90:
                    ranges["91-100"] += 1
                elif percentage > 80:
                    ranges["81-90"] += 1
                elif percentage > 70:
                    ranges["71-80"] += 1
                elif percentage > 60:
                    ranges["61-70"] += 1
                elif percentage > 50:
                    ranges["51-60"] += 1
                elif percentage > 40:
                    ranges["41-50"] += 1
                elif percentage > 30:
                    ranges["31-40"] += 1
                elif percentage > 20:
                    ranges["21-30"] += 1
                elif percentage > 10:
                    ranges["11-20"] += 1
                else:
                    ranges["0-10"] += 1

        # Convert counts to percentages
        score_ranges = {
            range_name: (count / total_graded) * 100
            for range_name, count in ranges.items()
        }

        return {"average_score": average_score, "score_ranges": score_ranges}

    @classmethod
    def get_assignment_statistics(
        cls, teacher=None, class_obj=None, subject=None, academic_year=None
    ):
        """Get statistics about assignments."""
        query = cls.objects

        if teacher:
            query = query.filter(teacher=teacher)

        if class_obj:
            query = query.filter(class_obj=class_obj)

        if subject:
            query = query.filter(subject=subject)

        if academic_year:
            query = query.filter(class_obj__academic_year=academic_year)
        else:
            # Default to current academic year
            current_year = AcademicYear.objects.filter(is_current=True).first()
            if current_year:
                query = query.filter(class_obj__academic_year=current_year)

        total_assignments = query.count()
        if total_assignments == 0:
            return {
                "total_assignments": 0,
                "published_count": 0,
                "average_submission_rate": 0,
                "average_grading_rate": 0,
            }

        published_count = query.filter(status__in=["published", "closed"]).count()

        # Calculate average submission and grading rates
        submission_rates = []
        grading_rates = []

        for assignment in query.filter(status__in=["published", "closed"]):
            submission_rates.append(assignment.submission_rate)
            grading_rates.append(assignment.grading_completion_rate)

        avg_submission_rate = (
            sum(submission_rates) / len(submission_rates) if submission_rates else 0
        )
        avg_grading_rate = (
            sum(grading_rates) / len(grading_rates) if grading_rates else 0
        )

        return {
            "total_assignments": total_assignments,
            "published_count": published_count,
            "average_submission_rate": avg_submission_rate,
            "average_grading_rate": avg_grading_rate,
        }


class AssignmentSubmission(models.Model):
    STATUS_CHOICES = [
        ("submitted", "Submitted"),
        ("late", "Late"),
        ("graded", "Graded"),
    ]

    assignment = models.ForeignKey(
        Assignment, on_delete=models.CASCADE, related_name="submissions"
    )
    student = models.ForeignKey(
        "students.Student",
        on_delete=models.CASCADE,
        related_name="assignment_submissions",
    )
    submission_date = models.DateTimeField(auto_now_add=True)
    content = models.TextField(blank=True)
    file = models.FileField(upload_to="assignment_submissions/", null=True, blank=True)
    remarks = models.TextField(blank=True)
    marks_obtained = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    status = models.CharField(
        max_length=10, choices=STATUS_CHOICES, default="submitted"
    )
    graded_by = models.ForeignKey(
        "teachers.Teacher",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="graded_submissions",
    )
    graded_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.assignment.title} - {self.student}"

    def save(self, *args, **kwargs):
        # Check if submission is late
        if self.submission_date.date() > self.assignment.due_date:
            self.status = "late"
        super().save(*args, **kwargs)

    @property
    def days_late(self):
        """Get the number of days the submission is late."""
        if self.submission_date.date() <= self.assignment.due_date:
            return 0
        return (self.submission_date.date() - self.assignment.due_date).days

    @property
    def score_percentage(self):
        """Get the score as a percentage of total marks."""
        if self.marks_obtained is None or self.assignment.total_marks == 0:
            return 0
        return (self.marks_obtained / self.assignment.total_marks) * 100

    @property
    def is_graded(self):
        """Check if the submission has been graded."""
        return self.status == "graded"

    @property
    def grade_letter(self):
        """Get the grade letter based on the score percentage."""
        percentage = self.score_percentage

        if percentage >= 90:
            return "A+"
        elif percentage >= 80:
            return "A"
        elif percentage >= 70:
            return "B+"
        elif percentage >= 60:
            return "B"
        elif percentage >= 50:
            return "C+"
        elif percentage >= 40:
            return "C"
        elif percentage >= 33:
            return "D"
        else:
            return "F"

    @classmethod
    def get_student_submission_statistics(cls, student, academic_year=None):
        """Get submission statistics for a specific student."""
        if not academic_year:
            academic_year = AcademicYear.objects.filter(is_current=True).first()
            if not academic_year:
                return {
                    "submission_count": 0,
                    "total_assignments": 0,
                    "submission_rate": 0,
                    "on_time_rate": 0,
                    "average_score": 0,
                }

        # Get all assignments for the student's class
        assignments = Assignment.objects.filter(
            class_obj=student.current_class,
            class_obj__academic_year=academic_year,
            status__in=["published", "closed"],
        )

        total_assignments = assignments.count()
        if total_assignments == 0:
            return {
                "submission_count": 0,
                "total_assignments": 0,
                "submission_rate": 0,
                "on_time_rate": 0,
                "average_score": 0,
            }

        # Get student's submissions
        submissions = cls.objects.filter(assignment__in=assignments, student=student)

        submission_count = submissions.count()
        on_time_count = submissions.filter(status="submitted").count()
        graded_submissions = submissions.filter(status="graded")

        average_score = (
            graded_submissions.aggregate(avg=Avg("marks_obtained"))["avg"] or 0
            if graded_submissions.exists()
            else 0
        )

        return {
            "submission_count": submission_count,
            "total_assignments": total_assignments,
            "submission_rate": (submission_count / total_assignments) * 100,
            "on_time_rate": (
                (on_time_count / submission_count) * 100 if submission_count > 0 else 0
            ),
            "average_score": average_score,
        }

    @classmethod
    def get_grading_statistics(cls, teacher, academic_year=None):
        """Get grading statistics for a specific teacher."""
        if not academic_year:
            academic_year = AcademicYear.objects.filter(is_current=True).first()
            if not academic_year:
                return {
                    "total_submissions": 0,
                    "graded_count": 0,
                    "grading_rate": 0,
                    "average_score": 0,
                    "average_grading_time": 0,
                }

        # Get all assignments created by the teacher
        assignments = Assignment.objects.filter(
            teacher=teacher, class_obj__academic_year=academic_year
        )

        # Get all submissions for these assignments
        submissions = cls.objects.filter(assignment__in=assignments)

        total_submissions = submissions.count()
        if total_submissions == 0:
            return {
                "total_submissions": 0,
                "graded_count": 0,
                "grading_rate": 0,
                "average_score": 0,
                "average_grading_time": 0,
            }

        graded_submissions = submissions.filter(status="graded")
        graded_count = graded_submissions.count()

        average_score = (
            graded_submissions.aggregate(avg=Avg("marks_obtained"))["avg"] or 0
            if graded_submissions.exists()
            else 0
        )

        # Calculate average grading time (time between submission and grading)
        grading_times = []
        for submission in graded_submissions:
            if submission.graded_at:
                grading_time = submission.graded_at - submission.submission_date
                grading_times.append(
                    grading_time.total_seconds() / 3600
                )  # Convert to hours

        average_grading_time = (
            sum(grading_times) / len(grading_times) if grading_times else 0
        )

        return {
            "total_submissions": total_submissions,
            "graded_count": graded_count,
            "grading_rate": (graded_count / total_submissions) * 100,
            "average_score": average_score,
            "average_grading_time": average_grading_time,
        }
