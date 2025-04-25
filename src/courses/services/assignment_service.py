from src.courses.models import Assignment, AssignmentSubmission
from django.utils import timezone


class AssignmentService:
    @staticmethod
    def get_class_assignments(class_obj, subject=None, status=None):
        """Get assignments for a specific class"""
        query = Assignment.objects.filter(class_obj=class_obj)

        if subject:
            query = query.filter(subject=subject)

        if status:
            query = query.filter(status=status)

        return query.select_related("subject", "teacher")

    @staticmethod
    def get_student_assignments(student, class_obj=None, subject=None, status=None):
        """Get assignments for a specific student"""
        # Get the student's current class if not specified
        if not class_obj:
            class_obj = student.current_class

        if not class_obj:
            return Assignment.objects.none()

        # Get all assignments for the class
        assignments = AssignmentService.get_class_assignments(
            class_obj, subject, status
        )

        # Annotate with submission status
        from django.db.models import OuterRef, Subquery, F, Value, CharField
        from django.db.models.functions import Coalesce

        submission_subquery = AssignmentSubmission.objects.filter(
            assignment=OuterRef("pk"), student=student
        ).values("status")[:1]

        return assignments.annotate(
            submission_status=Coalesce(
                Subquery(submission_subquery),
                Value("not_submitted"),
                output_field=CharField(),
            )
        )

    @staticmethod
    def submit_assignment(assignment, student, content="", file=None):
        """Submit an assignment"""
        # Check if already submitted
        existing = AssignmentSubmission.objects.filter(
            assignment=assignment, student=student
        ).first()

        if existing:
            # Update existing submission
            existing.content = content
            if file:
                existing.file = file
            existing.submission_date = timezone.now()

            # Check if late
            if existing.submission_date.date() > assignment.due_date:
                existing.status = "late"
            else:
                existing.status = "submitted"

            existing.save()
            return existing
        else:
            # Create new submission
            submission = AssignmentSubmission(
                assignment=assignment, student=student, content=content, file=file
            )

            # Check if late
            if submission.submission_date.date() > assignment.due_date:
                submission.status = "late"

            submission.save()
            return submission

    @staticmethod
    def grade_assignment(submission, marks, remarks, teacher):
        """Grade an assignment submission"""
        submission.marks_obtained = marks
        submission.remarks = remarks
        submission.status = "graded"
        submission.graded_by = teacher
        submission.graded_at = timezone.now()
        submission.save()
        return submission
