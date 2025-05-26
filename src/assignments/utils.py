from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from django.utils import timezone
from django.core.files.storage import default_storage
from django.core.exceptions import ValidationError
from datetime import datetime, timedelta
import os
import hashlib
import mimetypes
import csv
import io
import zipfile
import logging
from typing import List, Dict, Tuple, Optional
import pandas as pd
from PIL import Image

logger = logging.getLogger(__name__)


class FileUtils:
    """
    Utility functions for file handling in assignments
    """

    @staticmethod
    def validate_file_upload(file, max_size_mb=10, allowed_extensions=None):
        """
        Validate uploaded file for size and type
        """
        if not file:
            return True, None

        # Check file size
        max_size_bytes = max_size_mb * 1024 * 1024
        if file.size > max_size_bytes:
            return (
                False,
                f"File size ({file.size / (1024*1024):.1f}MB) exceeds maximum allowed size ({max_size_mb}MB)",
            )

        # Check file extension
        if allowed_extensions:
            file_ext = os.path.splitext(file.name)[1][1:].lower()
            if file_ext not in [ext.lower() for ext in allowed_extensions]:
                return (
                    False,
                    f"File type '{file_ext}' not allowed. Allowed types: {', '.join(allowed_extensions)}",
                )

        # Check for malicious files
        dangerous_extensions = ["exe", "bat", "cmd", "scr", "vbs", "js", "jar"]
        file_ext = os.path.splitext(file.name)[1][1:].lower()
        if file_ext in dangerous_extensions:
            return False, f"File type '{file_ext}' is not allowed for security reasons"

        return True, None

    @staticmethod
    def get_file_icon_class(filename):
        """
        Get CSS icon class for file type
        """
        if not filename:
            return "fas fa-file"

        extension = os.path.splitext(filename)[1][1:].lower()

        icon_map = {
            "pdf": "fas fa-file-pdf",
            "doc": "fas fa-file-word",
            "docx": "fas fa-file-word",
            "xls": "fas fa-file-excel",
            "xlsx": "fas fa-file-excel",
            "ppt": "fas fa-file-powerpoint",
            "pptx": "fas fa-file-powerpoint",
            "txt": "fas fa-file-alt",
            "rtf": "fas fa-file-alt",
            "jpg": "fas fa-file-image",
            "jpeg": "fas fa-file-image",
            "png": "fas fa-file-image",
            "gif": "fas fa-file-image",
            "zip": "fas fa-file-archive",
            "rar": "fas fa-file-archive",
            "7z": "fas fa-file-archive",
            "mp4": "fas fa-file-video",
            "avi": "fas fa-file-video",
            "mov": "fas fa-file-video",
            "mp3": "fas fa-file-audio",
            "wav": "fas fa-file-audio",
            "css": "fas fa-file-code",
            "html": "fas fa-file-code",
            "js": "fas fa-file-code",
            "py": "fas fa-file-code",
            "java": "fas fa-file-code",
        }

        return icon_map.get(extension, "fas fa-file")

    @staticmethod
    def format_file_size(size_bytes):
        """
        Format file size in human readable format
        """
        if size_bytes == 0:
            return "0 B"

        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0

        return f"{size_bytes:.1f} PB"

    @staticmethod
    def generate_unique_filename(original_filename, upload_path=""):
        """
        Generate unique filename to prevent conflicts
        """
        name, ext = os.path.splitext(original_filename)
        timestamp = timezone.now().strftime("%Y%m%d_%H%M%S")
        hash_object = hashlib.md5(original_filename.encode())
        short_hash = hash_object.hexdigest()[:8]

        unique_name = f"{name}_{timestamp}_{short_hash}{ext}"
        return os.path.join(upload_path, unique_name)

    @staticmethod
    def compress_image(image_file, max_width=1200, max_height=1200, quality=85):
        """
        Compress and resize image file
        """
        try:
            from PIL import Image
            import io

            # Open image
            img = Image.open(image_file)

            # Convert to RGB if necessary
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")

            # Resize if necessary
            img.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)

            # Save compressed image
            output = io.BytesIO()
            img.save(output, format="JPEG", quality=quality, optimize=True)
            output.seek(0)

            return output
        except Exception as e:
            logger.error(f"Error compressing image: {str(e)}")
            return image_file

    @staticmethod
    def create_submission_archive(submissions, assignment_title):
        """
        Create ZIP archive of multiple submissions
        """
        try:
            zip_buffer = io.BytesIO()

            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                for submission in submissions:
                    student_name = submission.student.user.get_full_name()
                    safe_student_name = "".join(
                        c for c in student_name if c.isalnum() or c in (" ", "-", "_")
                    ).rstrip()

                    # Add text content if exists
                    if submission.content:
                        content_filename = f"{safe_student_name}_content.txt"
                        zip_file.writestr(content_filename, submission.content)

                    # Add attachment if exists
                    if submission.attachment:
                        try:
                            file_content = submission.attachment.read()
                            file_extension = os.path.splitext(
                                submission.attachment.name
                            )[1]
                            attachment_filename = (
                                f"{safe_student_name}_attachment{file_extension}"
                            )
                            zip_file.writestr(attachment_filename, file_content)
                        except Exception as e:
                            logger.error(f"Error adding attachment to zip: {str(e)}")

            zip_buffer.seek(0)
            return zip_buffer

        except Exception as e:
            logger.error(f"Error creating submission archive: {str(e)}")
            return None


class GradingUtils:
    """
    Utility functions for grading assignments
    """

    @staticmethod
    def calculate_letter_grade(percentage, grading_scale=None):
        """
        Calculate letter grade from percentage
        """
        if grading_scale is None:
            grading_scale = {
                "A+": 97,
                "A": 93,
                "A-": 90,
                "B+": 87,
                "B": 83,
                "B-": 80,
                "C+": 77,
                "C": 73,
                "C-": 70,
                "D+": 67,
                "D": 63,
                "D-": 60,
                "F": 0,
            }

        if percentage is None:
            return None

        for grade, min_percentage in grading_scale.items():
            if percentage >= min_percentage:
                return grade

        return "F"

    @staticmethod
    def calculate_gpa_points(letter_grade):
        """
        Calculate GPA points from letter grade
        """
        gpa_scale = {
            "A+": 4.0,
            "A": 4.0,
            "A-": 3.7,
            "B+": 3.3,
            "B": 3.0,
            "B-": 2.7,
            "C+": 2.3,
            "C": 2.0,
            "C-": 1.7,
            "D+": 1.3,
            "D": 1.0,
            "D-": 0.7,
            "F": 0.0,
        }

        return gpa_scale.get(letter_grade, 0.0)

    @staticmethod
    def calculate_class_statistics(submissions):
        """
        Calculate statistics for a class of submissions
        """
        if not submissions:
            return {}

        graded_submissions = [s for s in submissions if s.marks_obtained is not None]

        if not graded_submissions:
            return {}

        scores = [s.marks_obtained for s in graded_submissions]
        percentages = [
            s.percentage for s in graded_submissions if s.percentage is not None
        ]

        stats = {
            "count": len(graded_submissions),
            "mean": sum(scores) / len(scores),
            "median": sorted(scores)[len(scores) // 2],
            "min": min(scores),
            "max": max(scores),
            "range": max(scores) - min(scores),
        }

        # Calculate standard deviation
        if len(scores) > 1:
            variance = sum((x - stats["mean"]) ** 2 for x in scores) / (len(scores) - 1)
            stats["std_dev"] = variance**0.5
        else:
            stats["std_dev"] = 0

        # Grade distribution
        grade_distribution = {}
        for submission in graded_submissions:
            grade = GradingUtils.calculate_letter_grade(submission.percentage)
            grade_distribution[grade] = grade_distribution.get(grade, 0) + 1

        stats["grade_distribution"] = grade_distribution

        # Performance categories
        if percentages:
            stats["excellent"] = len([p for p in percentages if p >= 90])
            stats["good"] = len([p for p in percentages if 80 <= p < 90])
            stats["satisfactory"] = len([p for p in percentages if 70 <= p < 80])
            stats["needs_improvement"] = len([p for p in percentages if p < 70])

        return stats

    @staticmethod
    def generate_grade_report(assignment, format_type="csv"):
        """
        Generate grade report in various formats
        """
        submissions = (
            assignment.submissions.filter(status="graded")
            .select_related("student__user")
            .order_by("student__user__last_name")
        )

        if format_type == "csv":
            return GradingUtils._generate_csv_report(assignment, submissions)
        elif format_type == "excel":
            return GradingUtils._generate_excel_report(assignment, submissions)
        else:
            raise ValueError("Unsupported format type")

    @staticmethod
    def _generate_csv_report(assignment, submissions):
        """
        Generate CSV grade report
        """
        output = io.StringIO()
        writer = csv.writer(output)

        # Header
        writer.writerow(
            [
                "Student Name",
                "Admission Number",
                "Submission Date",
                "Marks Obtained",
                "Total Marks",
                "Percentage",
                "Letter Grade",
                "Status",
                "Is Late",
                "Teacher Remarks",
            ]
        )

        # Data rows
        for submission in submissions:
            writer.writerow(
                [
                    submission.student.user.get_full_name(),
                    submission.student.admission_number,
                    (
                        submission.submission_date.strftime("%Y-%m-%d %H:%M")
                        if submission.submission_date
                        else ""
                    ),
                    submission.marks_obtained or "",
                    assignment.total_marks,
                    f"{submission.percentage:.1f}%" if submission.percentage else "",
                    submission.calculate_grade(),
                    submission.status,
                    "Yes" if submission.is_late else "No",
                    submission.teacher_remarks or "",
                ]
            )

        return output.getvalue()

    @staticmethod
    def _generate_excel_report(assignment, submissions):
        """
        Generate Excel grade report
        """
        try:
            import pandas as pd

            data = []
            for submission in submissions:
                data.append(
                    {
                        "Student Name": submission.student.user.get_full_name(),
                        "Admission Number": submission.student.admission_number,
                        "Submission Date": submission.submission_date,
                        "Marks Obtained": submission.marks_obtained,
                        "Total Marks": assignment.total_marks,
                        "Percentage": submission.percentage,
                        "Letter Grade": submission.calculate_grade(),
                        "Status": submission.status,
                        "Is Late": submission.is_late,
                        "Teacher Remarks": submission.teacher_remarks or "",
                    }
                )

            df = pd.DataFrame(data)

            # Create Excel file in memory
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine="openpyxl") as writer:
                df.to_excel(writer, sheet_name="Grades", index=False)

                # Add summary sheet
                stats = GradingUtils.calculate_class_statistics(submissions)
                if stats:
                    summary_data = [
                        ["Metric", "Value"],
                        ["Total Submissions", stats["count"]],
                        ["Average Score", f"{stats['mean']:.2f}"],
                        ["Median Score", f"{stats['median']:.2f}"],
                        ["Highest Score", stats["max"]],
                        ["Lowest Score", stats["min"]],
                        ["Standard Deviation", f"{stats['std_dev']:.2f}"],
                    ]

                    summary_df = pd.DataFrame(summary_data[1:], columns=summary_data[0])
                    summary_df.to_excel(writer, sheet_name="Summary", index=False)

            output.seek(0)
            return output

        except ImportError:
            # Fallback to CSV if pandas/openpyxl not available
            return GradingUtils._generate_csv_report(assignment, submissions)


class NotificationUtils:
    """
    Utility functions for sending notifications
    """

    @staticmethod
    def send_assignment_notification(
        assignment, recipient_list, template_name, context=None
    ):
        """
        Send assignment-related notification email
        """
        if not context:
            context = {}

        context.update(
            {
                "assignment": assignment,
                "site_name": getattr(settings, "SITE_NAME", "School Management System"),
            }
        )

        subject = render_to_string(
            f"assignments/emails/{template_name}_subject.txt", context
        ).strip()
        text_content = render_to_string(
            f"assignments/emails/{template_name}.txt", context
        )
        html_content = render_to_string(
            f"assignments/emails/{template_name}.html", context
        )

        msg = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=recipient_list,
        )
        msg.attach_alternative(html_content, "text/html")

        try:
            msg.send()
            return True
        except Exception as e:
            logger.error(f"Error sending notification: {str(e)}")
            return False

    @staticmethod
    def send_grade_notification(submission):
        """
        Send grade notification to student and parents
        """
        recipients = [submission.student.user.email]

        # Add parent emails
        for parent in submission.student.parents.all():
            if parent.user.email:
                recipients.append(parent.user.email)

        context = {
            "submission": submission,
            "student": submission.student,
            "assignment": submission.assignment,
        }

        return NotificationUtils.send_assignment_notification(
            submission.assignment, recipients, "grade_notification", context
        )

    @staticmethod
    def send_deadline_reminder(assignment, students):
        """
        Send deadline reminder to students
        """
        recipients = []
        for student in students:
            if student.user.email:
                recipients.append(student.user.email)

        if not recipients:
            return False

        context = {"students": students, "days_until_due": assignment.days_until_due}

        return NotificationUtils.send_assignment_notification(
            assignment, recipients, "deadline_reminder", context
        )


class AssignmentValidationUtils:
    """
    Utility functions for validating assignment data
    """

    @staticmethod
    def validate_assignment_dates(start_date, due_date, term_start=None, term_end=None):
        """
        Validate assignment date constraints
        """
        errors = []

        # Due date must be in the future
        if due_date <= timezone.now():
            errors.append("Due date must be in the future")

        # Due date must be after start date
        if start_date and due_date <= start_date:
            errors.append("Due date must be after start date")

        # Dates must be within term period
        if term_start and start_date and start_date < term_start:
            errors.append("Start date must be within the term period")

        if term_end and due_date and due_date > term_end:
            errors.append("Due date must be within the term period")

        return errors

    @staticmethod
    def validate_grading_constraints(marks_obtained, total_marks, passing_marks=None):
        """
        Validate grading constraints
        """
        errors = []

        if marks_obtained < 0:
            errors.append("Marks cannot be negative")

        if marks_obtained > total_marks:
            errors.append(f"Marks cannot exceed total marks ({total_marks})")

        if passing_marks and passing_marks > total_marks:
            errors.append(f"Passing marks cannot exceed total marks ({total_marks})")

        return errors

    @staticmethod
    def validate_rubric_weights(rubric_items):
        """
        Validate that rubric weights sum to 100%
        """
        total_weight = sum(item.get("weight_percentage", 0) for item in rubric_items)

        if abs(total_weight - 100) > 0.01:  # Allow for small floating point errors
            return [f"Rubric weights must sum to 100% (current total: {total_weight}%)"]

        return []


class ReportUtils:
    """
    Utility functions for generating reports
    """

    @staticmethod
    def generate_assignment_summary_report(assignments, format_type="html"):
        """
        Generate summary report for multiple assignments
        """
        context = {
            "assignments": assignments,
            "total_assignments": len(assignments),
            "published_count": len([a for a in assignments if a.status == "published"]),
            "draft_count": len([a for a in assignments if a.status == "draft"]),
            "overdue_count": len([a for a in assignments if a.is_overdue]),
            "report_date": timezone.now(),
        }

        if format_type == "html":
            return render_to_string(
                "assignments/reports/assignment_summary.html", context
            )
        elif format_type == "csv":
            return ReportUtils._generate_assignment_csv(assignments)
        else:
            raise ValueError("Unsupported format type")

    @staticmethod
    def _generate_assignment_csv(assignments):
        """
        Generate CSV report for assignments
        """
        output = io.StringIO()
        writer = csv.writer(output)

        # Header
        writer.writerow(
            [
                "Title",
                "Subject",
                "Teacher",
                "Class",
                "Status",
                "Due Date",
                "Total Marks",
                "Submissions",
                "Completion Rate",
            ]
        )

        # Data rows
        for assignment in assignments:
            writer.writerow(
                [
                    assignment.title,
                    assignment.subject.name,
                    assignment.teacher.user.get_full_name(),
                    str(assignment.class_id),
                    assignment.get_status_display(),
                    assignment.due_date.strftime("%Y-%m-%d %H:%M"),
                    assignment.total_marks,
                    assignment.submission_count,
                    f"{assignment.completion_rate:.1f}%",
                ]
            )

        return output.getvalue()

    @staticmethod
    def generate_student_performance_report(student, assignments):
        """
        Generate performance report for a student
        """
        submissions = []
        for assignment in assignments:
            submission = assignment.get_student_submission(student)
            if submission:
                submissions.append(submission)

        if not submissions:
            return None

        # Calculate statistics
        graded_submissions = [s for s in submissions if s.marks_obtained is not None]

        stats = {
            "total_assignments": len(assignments),
            "submitted_count": len(submissions),
            "graded_count": len(graded_submissions),
            "submission_rate": (
                (len(submissions) / len(assignments)) * 100 if assignments else 0
            ),
            "late_count": len([s for s in submissions if s.is_late]),
        }

        if graded_submissions:
            percentages = [
                s.percentage for s in graded_submissions if s.percentage is not None
            ]
            stats.update(
                {
                    "average_percentage": (
                        sum(percentages) / len(percentages) if percentages else 0
                    ),
                    "highest_percentage": max(percentages) if percentages else 0,
                    "lowest_percentage": min(percentages) if percentages else 0,
                }
            )

        context = {
            "student": student,
            "assignments": assignments,
            "submissions": submissions,
            "statistics": stats,
            "report_date": timezone.now(),
        }

        return render_to_string("assignments/reports/student_performance.html", context)


class DataExportUtils:
    """
    Utility functions for data export
    """

    @staticmethod
    def export_assignment_data(
        assignment, include_submissions=True, format_type="json"
    ):
        """
        Export assignment data in various formats
        """
        data = {
            "assignment": {
                "id": assignment.id,
                "title": assignment.title,
                "description": assignment.description,
                "subject": assignment.subject.name,
                "teacher": assignment.teacher.user.get_full_name(),
                "class": str(assignment.class_id),
                "term": assignment.term.name,
                "due_date": assignment.due_date.isoformat(),
                "total_marks": assignment.total_marks,
                "status": assignment.status,
                "created_at": assignment.created_at.isoformat(),
            }
        }

        if include_submissions:
            submissions_data = []
            for submission in assignment.submissions.all():
                submissions_data.append(
                    {
                        "student": submission.student.user.get_full_name(),
                        "admission_number": submission.student.admission_number,
                        "submission_date": (
                            submission.submission_date.isoformat()
                            if submission.submission_date
                            else None
                        ),
                        "marks_obtained": submission.marks_obtained,
                        "percentage": (
                            float(submission.percentage)
                            if submission.percentage
                            else None
                        ),
                        "grade": submission.calculate_grade(),
                        "status": submission.status,
                        "is_late": submission.is_late,
                    }
                )

            data["submissions"] = submissions_data

        if format_type == "json":
            import json

            return json.dumps(data, indent=2)
        elif format_type == "csv":
            # Return CSV for submissions only
            if include_submissions and data["submissions"]:
                output = io.StringIO()
                writer = csv.DictWriter(
                    output, fieldnames=data["submissions"][0].keys()
                )
                writer.writeheader()
                writer.writerows(data["submissions"])
                return output.getvalue()
            else:
                return "No submission data available"
        else:
            raise ValueError("Unsupported format type")


class SearchUtils:
    """
    Utility functions for search functionality
    """

    @staticmethod
    def search_assignments(query, user, filters=None):
        """
        Search assignments with various criteria
        """
        from django.db.models import Q
        from .models import Assignment

        # Base queryset based on user permissions
        queryset = Assignment.objects.all()

        if hasattr(user, "teacher"):
            queryset = queryset.filter(teacher=user.teacher)
        elif hasattr(user, "student"):
            queryset = queryset.filter(
                class_id=user.student.current_class_id, status="published"
            )
        elif not user.is_staff:
            queryset = queryset.none()

        # Apply search query
        if query:
            queryset = queryset.filter(
                Q(title__icontains=query)
                | Q(description__icontains=query)
                | Q(instructions__icontains=query)
                | Q(subject__name__icontains=query)
                | Q(teacher__user__first_name__icontains=query)
                | Q(teacher__user__last_name__icontains=query)
            )

        # Apply additional filters
        if filters:
            if filters.get("status"):
                queryset = queryset.filter(status__in=filters["status"])

            if filters.get("subject"):
                queryset = queryset.filter(subject=filters["subject"])

            if filters.get("difficulty"):
                queryset = queryset.filter(difficulty_level=filters["difficulty"])

            if filters.get("due_from"):
                queryset = queryset.filter(due_date__gte=filters["due_from"])

            if filters.get("due_to"):
                queryset = queryset.filter(due_date__lte=filters["due_to"])

        return queryset.select_related(
            "subject", "teacher__user", "class_id__grade__section"
        ).order_by("-created_at")


# Cache utilities
class CacheUtils:
    """
    Utility functions for caching
    """

    @staticmethod
    def get_cache_key(prefix, *args):
        """
        Generate cache key from prefix and arguments
        """
        return f"{prefix}_{'_'.join(str(arg) for arg in args)}"

    @staticmethod
    def invalidate_assignment_cache(assignment_id):
        """
        Invalidate all cache entries related to an assignment
        """
        from django.core.cache import cache

        cache_keys = [
            f"assignment_{assignment_id}",
            f"assignment_analytics_{assignment_id}",
            f"assignment_submissions_{assignment_id}",
        ]

        cache.delete_many(cache_keys)

    @staticmethod
    def invalidate_user_cache(user):
        """
        Invalidate cache entries for a user
        """
        from django.core.cache import cache

        cache_keys = [f"user_assignments_{user.id}"]

        if hasattr(user, "teacher"):
            cache_keys.extend(
                [
                    f"teacher_assignments_{user.teacher.id}",
                    f"teacher_analytics_{user.teacher.id}",
                    f"pending_grading_{user.teacher.id}",
                ]
            )

        if hasattr(user, "student"):
            cache_keys.extend(
                [
                    f"student_assignments_{user.student.id}",
                    f"student_performance_{user.student.id}",
                    f"upcoming_deadlines_{user.student.id}",
                ]
            )

        cache.delete_many(cache_keys)
