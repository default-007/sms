from django.db import transaction
from django.db.models import Q, Count, Avg
from django.utils import timezone
from django.core.exceptions import ValidationError, PermissionDenied
from django.contrib.auth import get_user_model
from typing import Dict, List, Optional, Tuple
import difflib
import hashlib

from ..models import Assignment, AssignmentSubmission, StudentAssignmentProgress
from students.models import Student
from teachers.models import Teacher
from communications.services.notification_service import NotificationService

User = get_user_model()


class SubmissionService:
    """Service class for assignment submission management"""

    @staticmethod
    def create_submission(
        assignment: Assignment, student: Student, data: Dict
    ) -> AssignmentSubmission:
        """Create a new assignment submission"""
        with transaction.atomic():
            # Check if student can submit
            can_submit, message = assignment.can_submit(student)
            if not can_submit:
                raise ValidationError(message)

            # Determine attempt number
            existing_submissions = AssignmentSubmission.objects.filter(
                assignment=assignment, student=student
            )
            attempt_number = existing_submissions.count() + 1

            # Check if submission is late
            is_late = timezone.now() > assignment.due_date
            if is_late and not assignment.late_submission_allowed:
                raise ValidationError(
                    "Late submissions are not allowed for this assignment"
                )

            # Create submission
            submission = AssignmentSubmission.objects.create(
                assignment=assignment,
                student=student,
                content=data.get("content", ""),
                attachment=data.get("attachment"),
                attempt_number=attempt_number,
                is_late=is_late,
                status="late" if is_late else "submitted",
            )

            # Update progress tracking
            SubmissionService._update_student_progress(
                student, assignment, completed=True
            )

            # Run plagiarism check if content provided
            if submission.content:
                SubmissionService._check_plagiarism(submission)

            # Notify teacher
            SubmissionService._notify_submission_received(submission)

            return submission

    @staticmethod
    def update_submission(
        submission: AssignmentSubmission, data: Dict, user: User
    ) -> AssignmentSubmission:
        """Update an existing submission"""
        with transaction.atomic():
            # Check permissions
            if submission.status == "graded":
                raise ValidationError("Cannot update graded submission")

            # Only student or teacher can update
            if user != submission.student.user and not hasattr(user, "teacher"):
                raise PermissionDenied("Not authorized to update this submission")

            # Update fields
            if "content" in data:
                submission.content = data["content"]
                # Re-run plagiarism check if content changed
                SubmissionService._check_plagiarism(submission)

            if "attachment" in data:
                submission.attachment = data["attachment"]

            submission.save()

            return submission

    @staticmethod
    def delete_submission(submission: AssignmentSubmission, user: User) -> bool:
        """Delete a submission (only if not graded)"""
        with transaction.atomic():
            # Check permissions
            if submission.status == "graded":
                raise ValidationError("Cannot delete graded submission")

            # Only student can delete their own submission
            if user != submission.student.user:
                raise PermissionDenied("Not authorized to delete this submission")

            # Check if within allowed time (e.g., 1 hour after submission)
            time_limit = submission.created_at + timezone.timedelta(hours=1)
            if timezone.now() > time_limit:
                raise ValidationError("Deletion time limit exceeded")

            submission.delete()

            # Update progress tracking
            SubmissionService._update_student_progress(
                submission.student, submission.assignment, completed=False
            )

            return True

    @staticmethod
    def get_submissions_for_assignment(
        assignment: Assignment, filters: Dict = None
    ) -> List[AssignmentSubmission]:
        """Get all submissions for an assignment with optional filters"""
        queryset = AssignmentSubmission.objects.filter(assignment=assignment)

        if filters:
            if filters.get("status"):
                queryset = queryset.filter(status=filters["status"])

            if filters.get("graded"):
                if filters["graded"]:
                    queryset = queryset.filter(status="graded")
                else:
                    queryset = queryset.exclude(status="graded")

            if filters.get("late_only"):
                queryset = queryset.filter(is_late=True)

            if filters.get("student_id"):
                queryset = queryset.filter(student_id=filters["student_id"])

        return queryset.select_related("student", "student__user").order_by(
            "-submission_date"
        )

    @staticmethod
    def get_submissions_for_student(
        student: Student, filters: Dict = None
    ) -> List[AssignmentSubmission]:
        """Get all submissions for a student with optional filters"""
        queryset = AssignmentSubmission.objects.filter(student=student)

        if filters:
            if filters.get("assignment_id"):
                queryset = queryset.filter(assignment_id=filters["assignment_id"])

            if filters.get("subject_id"):
                queryset = queryset.filter(assignment__subject_id=filters["subject_id"])

            if filters.get("status"):
                queryset = queryset.filter(status=filters["status"])

            if filters.get("term_id"):
                queryset = queryset.filter(assignment__term_id=filters["term_id"])

        return queryset.select_related("assignment", "assignment__subject").order_by(
            "-submission_date"
        )

    @staticmethod
    def get_late_submissions(
        teacher: Optional[Teacher] = None, days_overdue: int = None
    ) -> List[AssignmentSubmission]:
        """Get late submissions with optional filters"""
        queryset = AssignmentSubmission.objects.filter(is_late=True)

        if teacher:
            queryset = queryset.filter(assignment__teacher=teacher)

        if days_overdue:
            cutoff_date = timezone.now() - timezone.timedelta(days=days_overdue)
            queryset = queryset.filter(submission_date__lte=cutoff_date)

        return queryset.select_related(
            "assignment", "student", "student__user"
        ).order_by("-submission_date")

    @staticmethod
    def get_submission_statistics(assignment: Assignment) -> Dict:
        """Get submission statistics for an assignment"""
        total_students = Student.objects.filter(
            current_class=assignment.class_field
        ).count()
        submissions = AssignmentSubmission.objects.filter(assignment=assignment)

        submitted_count = submissions.count()
        on_time_count = submissions.filter(is_late=False).count()
        late_count = submissions.filter(is_late=True).count()
        graded_count = submissions.filter(status="graded").count()

        # Average submission time (days before due date)
        on_time_submissions = submissions.filter(is_late=False)
        submission_times = []
        for sub in on_time_submissions:
            days_early = (assignment.due_date - sub.submission_date).days
            submission_times.append(days_early)

        avg_days_early = (
            sum(submission_times) / len(submission_times) if submission_times else 0
        )

        return {
            "total_students": total_students,
            "submitted_count": submitted_count,
            "pending_count": total_students - submitted_count,
            "on_time_count": on_time_count,
            "late_count": late_count,
            "graded_count": graded_count,
            "pending_grading": submitted_count - graded_count,
            "submission_rate": (
                (submitted_count / total_students * 100) if total_students > 0 else 0
            ),
            "on_time_rate": (
                (on_time_count / submitted_count * 100) if submitted_count > 0 else 0
            ),
            "avg_days_early": round(avg_days_early, 1),
        }

    @staticmethod
    def get_student_submission_history(
        student: Student, limit: int = 10
    ) -> List[AssignmentSubmission]:
        """Get recent submission history for a student"""
        return (
            AssignmentSubmission.objects.filter(student=student)
            .select_related("assignment", "assignment__subject")
            .order_by("-submission_date")[:limit]
        )

    @staticmethod
    def track_student_progress(
        student: Student, assignment: Assignment, activity_data: Dict
    ):
        """Track student progress on an assignment"""
        progress, created = StudentAssignmentProgress.objects.get_or_create(
            student=student,
            assignment=assignment,
            defaults={"viewed_at": timezone.now()},
        )

        # Update activity tracking
        if activity_data.get("started") and not progress.started_at:
            progress.started_at = timezone.now()

        if "time_spent" in activity_data:
            progress.time_spent_minutes += activity_data["time_spent"]

        if "progress_percentage" in activity_data:
            progress.progress_percentage = max(
                progress.progress_percentage, activity_data["progress_percentage"]
            )

        progress.last_activity_at = timezone.now()
        progress.save()

        return progress

    @staticmethod
    def _update_student_progress(
        student: Student, assignment: Assignment, completed: bool
    ):
        """Update student progress when submission is made or deleted"""
        progress, created = StudentAssignmentProgress.objects.get_or_create(
            student=student,
            assignment=assignment,
            defaults={"viewed_at": timezone.now()},
        )

        if completed:
            progress.progress_percentage = 100
        else:
            progress.progress_percentage = 0

        progress.save()

    @staticmethod
    def _check_plagiarism(submission: AssignmentSubmission):
        """Basic plagiarism detection (simplified implementation)"""
        if not submission.content or len(submission.content.strip()) < 50:
            return

        # Compare with other submissions for the same assignment
        other_submissions = (
            AssignmentSubmission.objects.filter(assignment=submission.assignment)
            .exclude(id=submission.id)
            .exclude(content="")
        )

        max_similarity = 0
        similar_submissions = []

        for other_sub in other_submissions:
            similarity = SubmissionService._calculate_text_similarity(
                submission.content, other_sub.content
            )

            if similarity > 0.7:  # 70% similarity threshold
                similar_submissions.append(
                    {
                        "submission_id": str(other_sub.id),
                        "student_name": other_sub.student.user.get_full_name(),
                        "similarity_percentage": round(similarity * 100, 2),
                    }
                )
                max_similarity = max(max_similarity, similarity)

        # Store results
        submission.plagiarism_score = round(max_similarity * 100, 2)
        submission.plagiarism_report = {
            "similar_submissions": similar_submissions,
            "check_date": timezone.now().isoformat(),
            "threshold_exceeded": max_similarity > 0.7,
        }
        submission.save()

        # Notify teacher if high similarity detected
        if max_similarity > 0.7:
            SubmissionService._notify_plagiarism_detected(submission)

    @staticmethod
    def _calculate_text_similarity(text1: str, text2: str) -> float:
        """Calculate similarity between two texts using difflib"""
        # Clean and normalize texts
        text1_clean = " ".join(text1.lower().split())
        text2_clean = " ".join(text2.lower().split())

        # Use difflib to calculate similarity
        similarity = difflib.SequenceMatcher(None, text1_clean, text2_clean).ratio()
        return similarity

    @staticmethod
    def _notify_submission_received(submission: AssignmentSubmission):
        """Notify teacher when submission is received"""
        NotificationService.send_notification(
            user=submission.assignment.teacher.user,
            title=f"New Submission: {submission.assignment.title}",
            content=f"Submission received from {submission.student.user.get_full_name()}",
            notification_type="submission",
            reference_id=str(submission.id),
            reference_type="submission",
        )

    @staticmethod
    def _notify_plagiarism_detected(submission: AssignmentSubmission):
        """Notify teacher when potential plagiarism is detected"""
        NotificationService.send_notification(
            user=submission.assignment.teacher.user,
            title=f"Potential Plagiarism Detected",
            content=f"High similarity detected in submission from {submission.student.user.get_full_name()} for {submission.assignment.title}",
            notification_type="plagiarism_alert",
            reference_id=str(submission.id),
            reference_type="submission",
            priority="high",
        )

    @staticmethod
    def bulk_download_submissions(
        assignment: Assignment, format_type: str = "zip"
    ) -> str:
        """Prepare submissions for bulk download"""
        # This would typically create a zip file with all submissions
        # Implementation would depend on file storage backend
        submissions = AssignmentSubmission.objects.filter(assignment=assignment)

        # Create manifest with submission details
        manifest = {
            "assignment": {
                "title": assignment.title,
                "due_date": assignment.due_date.isoformat(),
                "total_marks": str(assignment.total_marks),
            },
            "submissions": [],
        }

        for submission in submissions:
            manifest["submissions"].append(
                {
                    "student_name": submission.student.user.get_full_name(),
                    "student_id": submission.student.admission_number,
                    "submission_date": submission.submission_date.isoformat(),
                    "is_late": submission.is_late,
                    "status": submission.status,
                    "marks_obtained": (
                        str(submission.marks_obtained)
                        if submission.marks_obtained
                        else None
                    ),
                    "attachment": (
                        submission.attachment.name if submission.attachment else None
                    ),
                }
            )

        # In a real implementation, this would:
        # 1. Create a temporary directory
        # 2. Copy all submission files
        # 3. Create the manifest.json
        # 4. Zip everything
        # 5. Return the download URL

        return f"/api/assignments/{assignment.id}/download/"

    @staticmethod
    def resubmit_assignment(
        original_submission: AssignmentSubmission, data: Dict
    ) -> AssignmentSubmission:
        """Handle assignment resubmission"""
        assignment = original_submission.assignment
        student = original_submission.student

        # Check if resubmission is allowed
        if not assignment.allow_resubmission:
            raise ValidationError("Resubmission not allowed for this assignment")

        # Check attempt limits
        existing_attempts = AssignmentSubmission.objects.filter(
            assignment=assignment, student=student
        ).count()

        if existing_attempts >= assignment.max_attempts:
            raise ValidationError("Maximum attempts reached")

        # Create new submission
        return SubmissionService.create_submission(assignment, student, data)

    @staticmethod
    def get_submission_analytics_for_teacher(
        teacher: Teacher, term_id: Optional[int] = None
    ) -> Dict:
        """Get submission analytics for a teacher"""
        queryset = AssignmentSubmission.objects.filter(assignment__teacher=teacher)

        if term_id:
            queryset = queryset.filter(assignment__term_id=term_id)

        total_submissions = queryset.count()
        late_submissions = queryset.filter(is_late=True).count()
        graded_submissions = queryset.filter(status="graded").count()

        # Average grading time
        graded_with_times = queryset.filter(status="graded", graded_at__isnull=False)

        grading_times = []
        for submission in graded_with_times:
            grading_time = submission.graded_at - submission.submission_date
            grading_times.append(
                grading_time.total_seconds() / 3600
            )  # Convert to hours

        avg_grading_time = (
            sum(grading_times) / len(grading_times) if grading_times else 0
        )

        return {
            "total_submissions": total_submissions,
            "late_submissions": late_submissions,
            "late_submission_rate": (
                (late_submissions / total_submissions * 100)
                if total_submissions > 0
                else 0
            ),
            "graded_submissions": graded_submissions,
            "pending_grading": total_submissions - graded_submissions,
            "grading_completion_rate": (
                (graded_submissions / total_submissions * 100)
                if total_submissions > 0
                else 0
            ),
            "avg_grading_time_hours": round(avg_grading_time, 2),
        }
