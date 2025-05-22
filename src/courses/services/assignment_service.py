from src.courses.models import Assignment, AssignmentSubmission
from django.db import transaction
from django.db.models import Avg, Count, Q, F, When, Case, Value, IntegerField
from django.utils import timezone
from datetime import datetime, timedelta


class AssignmentService:
    @staticmethod
    def get_class_assignments(class_obj, subject=None, status=None):
        """Get assignments for a specific class."""
        query = Assignment.objects.filter(class_obj=class_obj)

        if subject:
            query = query.filter(subject=subject)

        if status:
            query = query.filter(status=status)

        return query.select_related("subject", "teacher", "teacher__user").order_by(
            "-assigned_date"
        )

    @staticmethod
    def get_student_assignments(student, class_obj=None, subject=None, status=None):
        """Get assignments for a specific student."""
        # Get the student's current class if not specified
        if not class_obj and student.current_class:
            class_obj = student.current_class
        elif not class_obj and not student.current_class:
            return Assignment.objects.none()

        # Start with all assignments for the class
        assignments = AssignmentService.get_class_assignments(
            class_obj, subject, status
        )

        # Add submission status
        from django.db.models import OuterRef, Subquery, CharField
        from django.db.models.functions import Coalesce

        submission_subquery = AssignmentSubmission.objects.filter(
            assignment_id=OuterRef("pk"), student=student
        ).values("status")[:1]

        return assignments.annotate(
            submission_status=Coalesce(
                Subquery(submission_subquery),
                Value("not_submitted"),
                output_field=CharField(),
            )
        )

    @staticmethod
    def get_assignments_by_teacher(teacher, class_obj=None, subject=None, status=None):
        """Get assignments created by a specific teacher."""
        query = Assignment.objects.filter(teacher=teacher)

        if class_obj:
            query = query.filter(class_obj=class_obj)

        if subject:
            query = query.filter(subject=subject)

        if status:
            query = query.filter(status=status)

        return query.select_related(
            "class_obj", "subject", "teacher", "teacher__user"
        ).order_by("-assigned_date")

    @staticmethod
    def get_assignment_with_submissions(assignment_id):
        """Get an assignment with all its submissions."""
        assignment = (
            Assignment.objects.filter(id=assignment_id)
            .select_related("class_obj", "subject", "teacher", "teacher__user")
            .first()
        )

        if not assignment:
            return None, []

        submissions = (
            AssignmentSubmission.objects.filter(assignment=assignment)
            .select_related("student", "student__user", "graded_by")
            .order_by("student__user__last_name")
        )

        return assignment, submissions

    @staticmethod
    def get_overdue_assignments():
        """Get all assignments that are overdue but still active."""
        today = timezone.now().date()
        return Assignment.objects.filter(
            status="published", due_date__lt=today
        ).select_related("class_obj", "subject", "teacher", "teacher__user")

    @staticmethod
    @transaction.atomic
    def submit_assignment(assignment, student, content="", file=None):
        """Submit an assignment. Updates existing submission if exists."""
        # Check if already submitted
        existing = AssignmentSubmission.objects.filter(
            assignment=assignment, student=student
        ).first()

        submission_date = timezone.now()

        if existing:
            # Update existing submission
            existing.content = content
            if file:
                existing.file = file
            existing.submission_date = submission_date

            # Check if late
            if submission_date.date() > assignment.due_date:
                existing.status = "late"
            else:
                existing.status = "submitted"

            existing.save()
            return existing
        else:
            # Create new submission
            submission = AssignmentSubmission(
                assignment=assignment,
                student=student,
                content=content,
                file=file,
                submission_date=submission_date,
            )

            # Check if late
            if submission_date.date() > assignment.due_date:
                submission.status = "late"

            submission.save()
            return submission

    @staticmethod
    @transaction.atomic
    def grade_assignment(submission, marks, remarks, teacher):
        """Grade an assignment submission."""
        submission.marks_obtained = marks
        submission.remarks = remarks
        submission.status = "graded"
        submission.graded_by = teacher
        submission.graded_at = timezone.now()
        submission.save()
        return submission

    @staticmethod
    def get_submission_analytics(submission):
        """Get analytics for a specific submission."""
        # Get past submissions from the same student
        past_submissions = (
            AssignmentSubmission.objects.filter(
                student=submission.student, status="graded"
            )
            .exclude(id=submission.id)
            .select_related("assignment")
            .order_by("-submission_date")[:5]
        )

        # Get the average score for this student
        student_avg = past_submissions.aggregate(avg=Avg("marks_obtained"))["avg"] or 0

        # Get the class average for this assignment
        class_avg = (
            AssignmentSubmission.objects.filter(
                assignment=submission.assignment, status="graded"
            ).aggregate(avg=Avg("marks_obtained"))["avg"]
            or 0
        )

        # Get rank (position) among all graded submissions
        better_submissions = AssignmentSubmission.objects.filter(
            assignment=submission.assignment,
            status="graded",
            marks_obtained__gt=submission.marks_obtained,
        ).count()

        # Rank will be the number of better submissions + 1
        rank = better_submissions + 1

        # Get total graded submissions
        total_graded = AssignmentSubmission.objects.filter(
            assignment=submission.assignment, status="graded"
        ).count()

        return {
            "past_submissions": past_submissions,
            "student_average": student_avg,
            "class_average": class_avg,
            "rank": rank,
            "total_graded": total_graded,
        }

    @staticmethod
    def extend_deadline(assignment, new_due_date, notify_students=True):
        """Extend the deadline for an assignment."""
        old_due_date = assignment.due_date
        assignment.due_date = new_due_date
        assignment.save()

        if notify_students and new_due_date > old_due_date:
            # We would send notifications here
            # This is a placeholder for integrating with a notification system
            try:
                from src.communications.models import Notification

                # Get students in the class
                students = assignment.class_obj.students.all()

                # Create notifications
                notifications = []
                for student in students:
                    notification = Notification(
                        user=student.user,
                        title="Assignment Deadline Extended",
                        content=f"The deadline for '{assignment.title}' has been extended to {new_due_date}.",
                        notification_type="Assignment",
                        reference_id=assignment.id,
                        priority="Medium",
                    )
                    notifications.append(notification)

                # Bulk create notifications
                if notifications:
                    Notification.objects.bulk_create(notifications)

                return (
                    True,
                    f"Deadline extended and {len(notifications)} students notified.",
                )
            except ImportError:
                return True, "Deadline extended but could not send notifications."

        return True, "Deadline extended successfully."

    @staticmethod
    def get_assignment_submission_rates(
        teacher=None, class_obj=None, subject=None, period=None
    ):
        """Get assignment submission rates over time."""
        query = Assignment.objects.all()

        if teacher:
            query = query.filter(teacher=teacher)

        if class_obj:
            query = query.filter(class_obj=class_obj)

        if subject:
            query = query.filter(subject=subject)

        # Filter by time period
        if period:
            if period == "week":
                start_date = timezone.now().date() - timedelta(days=7)
            elif period == "month":
                start_date = timezone.now().date() - timedelta(days=30)
            elif period == "quarter":
                start_date = timezone.now().date() - timedelta(days=90)
            elif period == "year":
                start_date = timezone.now().date() - timedelta(days=365)
            else:
                start_date = None

            if start_date:
                query = query.filter(assigned_date__gte=start_date)

        # Group by assigned date
        assignments_by_date = (
            query.values("assigned_date")
            .annotate(count=Count("id"))
            .order_by("assigned_date")
        )

        # Get submission counts
        submission_data = []
        for date_group in assignments_by_date:
            assigned_date = date_group["assigned_date"]
            assignment_count = date_group["count"]

            # Get assignments for this date
            assignments = Assignment.objects.filter(assigned_date=assigned_date)

            # Count expected submissions (assignments * students per class)
            expected_submissions = 0
            for a in assignments:
                expected_submissions += a.class_obj.students.count()

            # Count actual submissions
            actual_submissions = AssignmentSubmission.objects.filter(
                assignment__in=assignments
            ).count()

            # Calculate rate
            if expected_submissions > 0:
                submission_rate = (actual_submissions / expected_submissions) * 100
            else:
                submission_rate = 0

            submission_data.append(
                {
                    "date": assigned_date,
                    "assignment_count": assignment_count,
                    "submission_rate": submission_rate,
                }
            )

        return submission_data
