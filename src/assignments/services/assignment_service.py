from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Avg, Count, Max, Min, Q
from django.utils import timezone

from src.communications.services import NotificationService
from src.academics.models import Class, Term
from src.students.models import Student
from src.subjects.models import Subject
from src.teachers.models import Teacher

from ..models import (
    Assignment,
    # AssignmentAnalytics,
    AssignmentSubmission,
    # StudentAssignmentProgress,
)

User = get_user_model()


class AssignmentService:
    """Service class for assignment management operations"""

    @staticmethod
    def create_assignment(data: Dict, created_by: User) -> Assignment:
        """Create a new assignment with validation"""
        with transaction.atomic():
            # Validate due date
            if data.get("due_date") and data["due_date"] <= timezone.now():
                raise ValidationError("Due date must be in the future")

            # Validate passing marks
            if data.get("passing_marks") and data.get("total_marks"):
                if data["passing_marks"] > data["total_marks"]:
                    raise ValidationError("Passing marks cannot exceed total marks")

            # Create assignment
            assignment = Assignment.objects.create(
                **data, created_by=created_by, updated_by=created_by
            )

            # Create analytics record
            # AssignmentAnalytics.objects.create(assignment=assignment)

            # Initialize progress tracking for all students in the class
            students = Student.objects.filter(current_class=assignment.class_field)

            return assignment

    @staticmethod
    def update_assignment(
        assignment: Assignment, data: Dict, updated_by: User
    ) -> Assignment:
        """Update assignment with validation"""
        with transaction.atomic():
            # Check if assignment can be updated
            if assignment.status == "closed":
                raise ValidationError("Cannot update closed assignment")

            # If changing due date and assignment is published, validate
            if assignment.status == "published" and "due_date" in data:
                if data["due_date"] <= timezone.now():
                    raise ValidationError(
                        "Cannot set due date to past when assignment is published"
                    )

                # Notify students of due date change
                if data["due_date"] != assignment.due_date:
                    AssignmentService._notify_due_date_change(
                        assignment, data["due_date"]
                    )

            # Update fields
            for field, value in data.items():
                setattr(assignment, field, value)

            assignment.updated_by = updated_by
            assignment.save()

            return assignment

    @staticmethod
    def publish_assignment(assignment: Assignment, published_by: User) -> Assignment:
        """Publish assignment and notify students"""
        with transaction.atomic():
            if assignment.status != "draft":
                raise ValidationError("Only draft assignments can be published")

            assignment.status = "published"
            assignment.updated_by = published_by
            assignment.save()

            # Notify students and parents
            AssignmentService._notify_assignment_published(assignment)

            return assignment

    @staticmethod
    def close_assignment(assignment: Assignment, closed_by: User) -> Assignment:
        """Close assignment for submissions"""
        with transaction.atomic():
            if assignment.status not in ["published"]:
                raise ValidationError("Only published assignments can be closed")

            assignment.status = "closed"
            assignment.updated_by = closed_by
            assignment.save()

            # Calculate final analytics
            AssignmentService.calculate_analytics(assignment)

            return assignment

    @staticmethod
    def get_assignments_for_teacher(
        teacher: Teacher, filters: Dict = None
    ) -> List[Assignment]:
        """Get assignments for a specific teacher with filters"""
        queryset = Assignment.objects.filter(teacher=teacher)

        if filters:
            if filters.get("status"):
                queryset = queryset.filter(status=filters["status"])

            if filters.get("subject_id"):
                queryset = queryset.filter(subject_id=filters["subject_id"])

            if filters.get("class_id"):
                queryset = queryset.filter(class_field_id=filters["class_id"])

            if filters.get("term_id"):
                queryset = queryset.filter(term_id=filters["term_id"])

            if filters.get("due_date_from"):
                queryset = queryset.filter(due_date__gte=filters["due_date_from"])

            if filters.get("due_date_to"):
                queryset = queryset.filter(due_date__lte=filters["due_date_to"])

        return queryset.select_related("class_field", "subject", "term").order_by(
            "-assigned_date"
        )

    @staticmethod
    def get_assignments_for_student(
        student: Student, filters: Dict = None
    ) -> List[Assignment]:
        """Get assignments for a specific student"""
        queryset = Assignment.objects.filter(
            class_field=student.current_class, status__in=["published", "closed"]
        )

        if filters:
            if filters.get("subject_id"):
                queryset = queryset.filter(subject_id=filters["subject_id"])

            if filters.get("status"):
                if filters["status"] == "pending":
                    # Assignments without submissions
                    submitted_assignments = AssignmentSubmission.objects.filter(
                        student=student
                    ).values_list("assignment_id", flat=True)
                    queryset = queryset.exclude(id__in=submitted_assignments)
                elif filters["status"] == "submitted":
                    # Assignments with submissions
                    submitted_assignments = AssignmentSubmission.objects.filter(
                        student=student
                    ).values_list("assignment_id", flat=True)
                    queryset = queryset.filter(id__in=submitted_assignments)

            if filters.get("overdue_only"):
                queryset = queryset.filter(due_date__lt=timezone.now())

        return queryset.select_related("subject", "teacher").order_by("due_date")

    @staticmethod
    def get_overdue_assignments(
        class_id: Optional[int] = None, teacher_id: Optional[int] = None
    ) -> List[Assignment]:
        """Get overdue assignments"""
        queryset = Assignment.objects.filter(
            status="published", due_date__lt=timezone.now()
        )

        if class_id:
            queryset = queryset.filter(class_field_id=class_id)

        if teacher_id:
            queryset = queryset.filter(teacher_id=teacher_id)

        return queryset.select_related("class_field", "subject", "teacher")

    @staticmethod
    def get_pending_grading(teacher: Teacher) -> List[AssignmentSubmission]:
        """Get submissions pending grading for a teacher"""
        return (
            AssignmentSubmission.objects.filter(
                assignment__teacher=teacher,
                status__in=["submitted", "late"],
                marks_obtained__isnull=True,
            )
            .select_related("assignment", "student")
            .order_by("submission_date")
        )

    """ @staticmethod
    def calculate_analytics(assignment: Assignment) -> AssignmentAnalytics:
        #Calculate analytics for an assignment
        analytics, created = AssignmentAnalytics.objects.get_or_create(
            assignment=assignment
        )

        # Get all students in the class
        total_students = Student.objects.filter(
            current_class=assignment.class_field
        ).count()

        # Get submission statistics
        submissions = AssignmentSubmission.objects.filter(assignment=assignment)

        # Basic counts
        analytics.total_students = total_students
        analytics.submissions_count = submissions.count()
        analytics.on_time_submissions = submissions.filter(is_late=False).count()
        analytics.late_submissions = submissions.filter(is_late=True).count()

        # Performance statistics (only graded submissions)
        graded_submissions = submissions.filter(
            status="graded", marks_obtained__isnull=False
        )

        if graded_submissions.exists():
            scores = graded_submissions.values_list("marks_obtained", flat=True)
            analytics.average_score = sum(scores) / len(scores)
            analytics.highest_score = max(scores)
            analytics.lowest_score = min(scores)
            analytics.median_score = sorted(scores)[len(scores) // 2]

            # Pass rate calculation
            if assignment.passing_marks:
                passed_count = graded_submissions.filter(
                    marks_obtained__gte=assignment.passing_marks
                ).count()
                analytics.pass_rate = (passed_count / graded_submissions.count()) * 100

        # Grade distribution
        grade_dist = {}
        for submission in graded_submissions:
            grade = submission.grade or "Ungraded"
            grade_dist[grade] = grade_dist.get(grade, 0) + 1
        analytics.grade_distribution = grade_dist

        # Time analytics
        time_deltas = []
        for submission in submissions:
            progress = StudentAssignmentProgress.objects.filter(
                student=submission.student, assignment=assignment
            ).first()
            if progress and progress.time_spent_minutes:
                time_deltas.append(progress.time_spent_minutes / 60)  # Convert to hours

        if time_deltas:
            analytics.average_submission_time_hours = Decimal(
                str(sum(time_deltas) / len(time_deltas))
            )

        analytics.save()
        return analytics
 """

    @staticmethod
    def get_assignment_progress_summary(assignment: Assignment) -> Dict:
        """Get progress summary for an assignment"""
        total_students = Student.objects.filter(
            current_class=assignment.class_field
        ).count()
        submissions = AssignmentSubmission.objects.filter(assignment=assignment)

        submitted_count = submissions.count()
        graded_count = submissions.filter(status="graded").count()
        pending_count = total_students - submitted_count

        return {
            "total_students": total_students,
            "submitted_count": submitted_count,
            "graded_count": graded_count,
            "pending_count": pending_count,
            "submission_rate": (
                (submitted_count / total_students * 100) if total_students > 0 else 0
            ),
            "grading_rate": (
                (graded_count / submitted_count * 100) if submitted_count > 0 else 0
            ),
        }

    @staticmethod
    def bulk_close_overdue_assignments() -> int:
        """Bulk close overdue assignments (for scheduled task)"""
        overdue_assignments = Assignment.objects.filter(
            status="published",
            due_date__lt=timezone.now()
            - timezone.timedelta(days=1),  # 1 day grace period
            late_submission_allowed=False,
        )

        count = 0
        for assignment in overdue_assignments:
            assignment.status = "closed"
            assignment.save()

            # Calculate final analytics
            AssignmentService.calculate_analytics(assignment)
            count += 1

        return count

    @staticmethod
    def _notify_assignment_published(assignment: Assignment):
        """Send notifications when assignment is published"""
        # Get all students in the class
        students = Student.objects.filter(current_class=assignment.class_field)

        for student in students:
            # Notify student
            NotificationService.send_notification(
                user=student.user,
                title=f"New Assignment: {assignment.title}",
                content=f"New assignment in {assignment.subject.name}. Due: {assignment.due_date.strftime('%Y-%m-%d %H:%M')}",
                notification_type="assignment",
                reference_id=str(assignment.id),
                reference_type="assignment",
            )

            # Notify parents
            for parent_relation in student.parent_relations.all():
                NotificationService.send_notification(
                    user=parent_relation.parent.user,
                    title=f"New Assignment for {student.user.get_full_name()}",
                    content=f"Assignment '{assignment.title}' in {assignment.subject.name}. Due: {assignment.due_date.strftime('%Y-%m-%d %H:%M')}",
                    notification_type="assignment",
                    reference_id=str(assignment.id),
                    reference_type="assignment",
                )

    @staticmethod
    def _notify_due_date_change(assignment: Assignment, new_due_date):
        """Notify students and parents of due date changes"""
        students = Student.objects.filter(current_class=assignment.class_field)

        for student in students:
            # Notify student
            NotificationService.send_notification(
                user=student.user,
                title=f"Due Date Changed: {assignment.title}",
                content=f"Due date changed to: {new_due_date.strftime('%Y-%m-%d %H:%M')}",
                notification_type="assignment",
                reference_id=str(assignment.id),
                reference_type="assignment",
            )

            # Notify parents
            for parent_relation in student.parent_relations.all():
                NotificationService.send_notification(
                    user=parent_relation.parent.user,
                    title=f"Assignment Due Date Changed",
                    content=f"Due date for '{assignment.title}' changed to: {new_due_date.strftime('%Y-%m-%d %H:%M')}",
                    notification_type="assignment",
                    reference_id=str(assignment.id),
                    reference_type="assignment",
                )

    @staticmethod
    def send_due_date_reminders():
        """Send reminders for assignments due soon (for scheduled task)"""
        tomorrow = timezone.now() + timezone.timedelta(days=1)

        # Assignments due tomorrow
        upcoming_assignments = Assignment.objects.filter(
            status="published", due_date__date=tomorrow.date()
        )

        for assignment in upcoming_assignments:
            students = Student.objects.filter(current_class=assignment.class_field)

            # Only remind students who haven't submitted
            submitted_students = AssignmentSubmission.objects.filter(
                assignment=assignment
            ).values_list("student_id", flat=True)

            pending_students = students.exclude(id__in=submitted_students)

            for student in pending_students:
                NotificationService.send_notification(
                    user=student.user,
                    title=f"Assignment Due Tomorrow: {assignment.title}",
                    content=f"Don't forget to submit your assignment for {assignment.subject.name}",
                    notification_type="assignment_reminder",
                    reference_id=str(assignment.id),
                    reference_type="assignment",
                )

    @staticmethod
    def get_teacher_assignment_statistics(
        teacher: Teacher, term: Optional[Term] = None
    ) -> Dict:
        """Get assignment statistics for a teacher"""
        queryset = Assignment.objects.filter(teacher=teacher)

        if term:
            queryset = queryset.filter(term=term)

        total_assignments = queryset.count()
        published_assignments = queryset.filter(status="published").count()
        closed_assignments = queryset.filter(status="closed").count()

        # Get submission statistics
        total_submissions = AssignmentSubmission.objects.filter(
            assignment__teacher=teacher
        )
        if term:
            total_submissions = total_submissions.filter(assignment__term=term)

        pending_grading = total_submissions.filter(
            status__in=["submitted", "late"], marks_obtained__isnull=True
        ).count()

        return {
            "total_assignments": total_assignments,
            "published_assignments": published_assignments,
            "closed_assignments": closed_assignments,
            "pending_grading": pending_grading,
            "average_submissions_per_assignment": (
                total_submissions.count() / total_assignments
                if total_assignments > 0
                else 0
            ),
        }
