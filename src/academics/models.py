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
