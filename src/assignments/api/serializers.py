from rest_framework import serializers
from django.utils import timezone
from django.contrib.auth import get_user_model
from datetime import datetime
import os

from ..models import (
    Assignment,
    AssignmentSubmission,
    AssignmentRubric,
    SubmissionGrade,
    AssignmentComment,
)

User = get_user_model()


class TeacherBasicSerializer(serializers.ModelSerializer):
    """Basic teacher information for assignments"""

    full_name = serializers.SerializerMethodField()

    class Meta:
        model = "teachers.Teacher"
        fields = ["id", "employee_id", "full_name"]

    def get_full_name(self, obj):
        return obj.user.get_full_name()


class StudentBasicSerializer(serializers.ModelSerializer):
    """Basic student information for submissions"""

    full_name = serializers.SerializerMethodField()

    class Meta:
        model = "students.Student"
        fields = ["id", "admission_number", "full_name"]

    def get_full_name(self, obj):
        return obj.user.get_full_name()


class ClassBasicSerializer(serializers.ModelSerializer):
    """Basic class information"""

    display_name = serializers.SerializerMethodField()
    grade_name = serializers.CharField(source="grade.name", read_only=True)
    section_name = serializers.CharField(source="grade.section.name", read_only=True)

    class Meta:
        model = "academics.Class"
        fields = ["id", "name", "display_name", "grade_name", "section_name"]

    def get_display_name(self, obj):
        return f"{obj.grade.section.name} - {obj.grade.name} {obj.name}"


class SubjectBasicSerializer(serializers.ModelSerializer):
    """Basic subject information"""

    class Meta:
        model = "subjects.Subject"
        fields = ["id", "name", "code"]


class TermBasicSerializer(serializers.ModelSerializer):
    """Basic term information"""

    class Meta:
        model = "academics.Term"
        fields = ["id", "name", "term_number"]


class AssignmentRubricSerializer(serializers.ModelSerializer):
    """Serializer for assignment rubrics"""

    class Meta:
        model = AssignmentRubric
        fields = [
            "id",
            "criteria_name",
            "description",
            "max_points",
            "weight_percentage",
            "excellent_description",
            "good_description",
            "satisfactory_description",
            "needs_improvement_description",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def validate_weight_percentage(self, value):
        """Validate weight percentage is between 1 and 100"""
        if value < 1 or value > 100:
            raise serializers.ValidationError(
                "Weight percentage must be between 1 and 100"
            )
        return value


class SubmissionGradeSerializer(serializers.ModelSerializer):
    """Serializer for rubric-based grades"""

    rubric_name = serializers.CharField(source="rubric.criteria_name", read_only=True)
    max_points = serializers.IntegerField(source="rubric.max_points", read_only=True)
    percentage = serializers.SerializerMethodField()

    class Meta:
        model = SubmissionGrade
        fields = [
            "id",
            "rubric",
            "rubric_name",
            "points_earned",
            "max_points",
            "percentage",
            "feedback",
        ]
        read_only_fields = ["id", "rubric_name", "max_points", "percentage"]

    def get_percentage(self, obj):
        if obj.rubric.max_points > 0:
            return round((obj.points_earned / obj.rubric.max_points) * 100, 2)
        return 0

    def validate_points_earned(self, value):
        """Validate points earned don't exceed max points"""
        if hasattr(self, "initial_data") and "rubric" in self.initial_data:
            try:
                rubric = AssignmentRubric.objects.get(id=self.initial_data["rubric"])
                if value > rubric.max_points:
                    raise serializers.ValidationError(
                        f"Points cannot exceed {rubric.max_points}"
                    )
            except AssignmentRubric.DoesNotExist:
                raise serializers.ValidationError("Invalid rubric")
        return value


class AssignmentCommentSerializer(serializers.ModelSerializer):
    """Serializer for assignment comments"""

    user_name = serializers.CharField(source="user.get_full_name", read_only=True)
    replies_count = serializers.SerializerMethodField()

    class Meta:
        model = AssignmentComment
        fields = [
            "id",
            "user",
            "user_name",
            "parent_comment",
            "content",
            "is_private",
            "replies_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "user",
            "user_name",
            "replies_count",
            "created_at",
            "updated_at",
        ]

    def get_replies_count(self, obj):
        return obj.replies.count()


class AssignmentSubmissionListSerializer(serializers.ModelSerializer):
    """Serializer for listing assignment submissions"""

    student = StudentBasicSerializer(read_only=True)
    assignment_title = serializers.CharField(source="assignment.title", read_only=True)
    subject_name = serializers.CharField(
        source="assignment.subject.name", read_only=True
    )
    graded_by_name = serializers.SerializerMethodField()
    is_passed = serializers.ReadOnlyField()
    days_late = serializers.ReadOnlyField()
    file_size_mb = serializers.ReadOnlyField()

    class Meta:
        model = AssignmentSubmission
        fields = [
            "id",
            "assignment",
            "assignment_title",
            "subject_name",
            "student",
            "submission_date",
            "submission_method",
            "status",
            "marks_obtained",
            "percentage",
            "grade",
            "is_late",
            "days_late",
            "is_passed",
            "graded_by_name",
            "graded_at",
            "file_size_mb",
            "plagiarism_score",
        ]

    def get_graded_by_name(self, obj):
        return obj.graded_by.user.get_full_name() if obj.graded_by else None


class AssignmentSubmissionDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for assignment submissions"""

    student = StudentBasicSerializer(read_only=True)
    assignment_title = serializers.CharField(source="assignment.title", read_only=True)
    assignment_total_marks = serializers.IntegerField(
        source="assignment.total_marks", read_only=True
    )
    assignment_passing_marks = serializers.IntegerField(
        source="assignment.passing_marks", read_only=True
    )
    graded_by = TeacherBasicSerializer(read_only=True)
    rubric_grades = SubmissionGradeSerializer(many=True, read_only=True)
    is_passed = serializers.ReadOnlyField()
    days_late = serializers.ReadOnlyField()
    file_size_mb = serializers.ReadOnlyField()

    class Meta:
        model = AssignmentSubmission
        fields = [
            "id",
            "assignment",
            "assignment_title",
            "assignment_total_marks",
            "assignment_passing_marks",
            "student",
            "content",
            "attachment",
            "submission_date",
            "submission_method",
            "student_remarks",
            "marks_obtained",
            "percentage",
            "grade",
            "teacher_remarks",
            "strengths",
            "improvements",
            "graded_by",
            "graded_at",
            "status",
            "is_late",
            "days_late",
            "is_passed",
            "late_penalty_applied",
            "original_marks",
            "plagiarism_score",
            "plagiarism_checked",
            "file_size_mb",
            "revision_count",
            "rubric_grades",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "assignment_title",
            "assignment_total_marks",
            "assignment_passing_marks",
            "student",
            "submission_date",
            "percentage",
            "grade",
            "graded_by",
            "graded_at",
            "is_late",
            "days_late",
            "is_passed",
            "late_penalty_applied",
            "original_marks",
            "plagiarism_score",
            "plagiarism_checked",
            "file_size_mb",
            "revision_count",
            "rubric_grades",
            "created_at",
            "updated_at",
        ]


class AssignmentSubmissionCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating assignment submissions"""

    class Meta:
        model = AssignmentSubmission
        fields = ["content", "attachment", "submission_method", "student_remarks"]

    def validate_attachment(self, value):
        """Validate attachment file"""
        if value:
            # Get assignment from context
            assignment = self.context.get("assignment")
            if assignment:
                # Check file size
                max_size_bytes = assignment.max_file_size_mb * 1024 * 1024
                if value.size > max_size_bytes:
                    raise serializers.ValidationError(
                        f"File size exceeds {assignment.max_file_size_mb}MB limit"
                    )

                # Check file type
                allowed_types = [
                    ext.strip().lower()
                    for ext in assignment.allowed_file_types.split(",")
                ]
                file_ext = os.path.splitext(value.name)[1][1:].lower()

                if file_ext not in allowed_types:
                    raise serializers.ValidationError(
                        f"File type '{file_ext}' not allowed. Allowed types: {', '.join(allowed_types)}"
                    )

        return value


class AssignmentSubmissionGradeSerializer(serializers.ModelSerializer):
    """Serializer for grading submissions"""

    rubric_grades = SubmissionGradeSerializer(many=True, required=False)

    class Meta:
        model = AssignmentSubmission
        fields = [
            "marks_obtained",
            "teacher_remarks",
            "strengths",
            "improvements",
            "rubric_grades",
        ]

    def validate_marks_obtained(self, value):
        """Validate marks are within valid range"""
        if value is not None:
            assignment = self.instance.assignment if self.instance else None
            if assignment and (value < 0 or value > assignment.total_marks):
                raise serializers.ValidationError(
                    f"Marks must be between 0 and {assignment.total_marks}"
                )
        return value

    def update(self, instance, validated_data):
        """Update submission with grading data"""
        rubric_grades_data = validated_data.pop("rubric_grades", [])

        # Update main submission fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        # Set grading metadata
        instance.graded_by = self.context["request"].user.teacher
        instance.graded_at = timezone.now()
        instance.status = "graded"
        instance.grade = instance.calculate_grade()
        instance.save()

        # Update rubric grades
        for grade_data in rubric_grades_data:
            rubric_id = grade_data.get("rubric")
            if rubric_id:
                SubmissionGrade.objects.update_or_create(
                    submission=instance,
                    rubric_id=rubric_id,
                    defaults={
                        "points_earned": grade_data.get("points_earned", 0),
                        "feedback": grade_data.get("feedback", ""),
                    },
                )

        return instance


class AssignmentListSerializer(serializers.ModelSerializer):
    """Serializer for listing assignments"""

    class_info = ClassBasicSerializer(source="class_id", read_only=True)
    subject = SubjectBasicSerializer(read_only=True)
    teacher = TeacherBasicSerializer(read_only=True)
    term = TermBasicSerializer(read_only=True)

    # Computed fields
    submission_count = serializers.ReadOnlyField()
    graded_submission_count = serializers.ReadOnlyField()
    completion_rate = serializers.ReadOnlyField()
    average_score = serializers.ReadOnlyField()
    is_overdue = serializers.ReadOnlyField()
    days_until_due = serializers.ReadOnlyField()

    # Student-specific fields (populated based on context)
    student_submission_status = serializers.SerializerMethodField()
    student_marks = serializers.SerializerMethodField()

    class Meta:
        model = Assignment
        fields = [
            "id",
            "title",
            "description",
            "class_info",
            "subject",
            "teacher",
            "term",
            "assigned_date",
            "due_date",
            "total_marks",
            "passing_marks",
            "submission_type",
            "status",
            "difficulty_level",
            "allow_late_submission",
            "submission_count",
            "graded_submission_count",
            "completion_rate",
            "average_score",
            "is_overdue",
            "days_until_due",
            "student_submission_status",
            "student_marks",
            "created_at",
        ]

    def get_student_submission_status(self, obj):
        """Get submission status for current student"""
        student = self.context.get("student")
        if student:
            submission = obj.get_student_submission(student)
            return submission.status if submission else None
        return None

    def get_student_marks(self, obj):
        """Get marks for current student"""
        student = self.context.get("student")
        if student:
            submission = obj.get_student_submission(student)
            if submission and submission.marks_obtained is not None:
                return {
                    "marks_obtained": submission.marks_obtained,
                    "percentage": submission.percentage,
                    "grade": submission.grade,
                }
        return None


class AssignmentDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for assignments"""

    class_info = ClassBasicSerializer(source="class_id", read_only=True)
    subject = SubjectBasicSerializer(read_only=True)
    teacher = TeacherBasicSerializer(read_only=True)
    term = TermBasicSerializer(read_only=True)
    rubrics = AssignmentRubricSerializer(many=True, read_only=True)
    comments = AssignmentCommentSerializer(many=True, read_only=True)

    # Analytics fields
    submission_count = serializers.ReadOnlyField()
    graded_submission_count = serializers.ReadOnlyField()
    completion_rate = serializers.ReadOnlyField()
    average_score = serializers.ReadOnlyField()
    is_overdue = serializers.ReadOnlyField()
    days_until_due = serializers.ReadOnlyField()

    # Student-specific fields
    student_submission = serializers.SerializerMethodField()

    class Meta:
        model = Assignment
        fields = [
            "id",
            "title",
            "description",
            "instructions",
            "class_info",
            "subject",
            "teacher",
            "term",
            "assigned_date",
            "due_date",
            "total_marks",
            "passing_marks",
            "attachment",
            "submission_type",
            "status",
            "difficulty_level",
            "allow_late_submission",
            "late_penalty_percentage",
            "max_file_size_mb",
            "allowed_file_types",
            "estimated_duration_hours",
            "learning_objectives",
            "auto_grade",
            "peer_review",
            "submission_count",
            "graded_submission_count",
            "completion_rate",
            "average_score",
            "is_overdue",
            "days_until_due",
            "student_submission",
            "rubrics",
            "comments",
            "created_at",
            "updated_at",
            "published_at",
        ]

    def get_student_submission(self, obj):
        """Get detailed submission for current student"""
        student = self.context.get("student")
        if student:
            submission = obj.get_student_submission(student)
            if submission:
                return AssignmentSubmissionDetailSerializer(submission).data
        return None


class AssignmentCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating assignments"""

    rubrics = AssignmentRubricSerializer(many=True, required=False)

    class Meta:
        model = Assignment
        fields = [
            "title",
            "description",
            "instructions",
            "class_id",
            "subject",
            "term",
            "due_date",
            "total_marks",
            "passing_marks",
            "attachment",
            "submission_type",
            "difficulty_level",
            "allow_late_submission",
            "late_penalty_percentage",
            "max_file_size_mb",
            "allowed_file_types",
            "estimated_duration_hours",
            "learning_objectives",
            "auto_grade",
            "peer_review",
            "rubrics",
        ]

    def validate_due_date(self, value):
        """Validate due date is in the future"""
        if value <= timezone.now():
            raise serializers.ValidationError("Due date must be in the future")
        return value

    def validate_passing_marks(self, value):
        """Validate passing marks don't exceed total marks"""
        total_marks = self.initial_data.get("total_marks")
        if value and total_marks and value > total_marks:
            raise serializers.ValidationError("Passing marks cannot exceed total marks")
        return value

    def validate_rubrics(self, value):
        """Validate rubric weight percentages sum to 100"""
        if value:
            total_weight = sum(rubric["weight_percentage"] for rubric in value)
            if total_weight != 100:
                raise serializers.ValidationError(
                    "Total rubric weight percentage must equal 100"
                )
        return value

    def create(self, validated_data):
        """Create assignment with rubrics"""
        rubrics_data = validated_data.pop("rubrics", [])

        # Set teacher from request context
        validated_data["teacher"] = self.context["request"].user.teacher

        assignment = Assignment.objects.create(**validated_data)

        # Create rubrics
        for rubric_data in rubrics_data:
            AssignmentRubric.objects.create(assignment=assignment, **rubric_data)

        return assignment


class AssignmentUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating assignments"""

    class Meta:
        model = Assignment
        fields = [
            "title",
            "description",
            "instructions",
            "due_date",
            "total_marks",
            "passing_marks",
            "attachment",
            "submission_type",
            "difficulty_level",
            "allow_late_submission",
            "late_penalty_percentage",
            "max_file_size_mb",
            "allowed_file_types",
            "estimated_duration_hours",
            "learning_objectives",
            "auto_grade",
            "peer_review",
            "status",
        ]

    def validate_due_date(self, value):
        """Validate due date for published assignments"""
        if self.instance and self.instance.status == "published":
            if value <= timezone.now():
                raise serializers.ValidationError(
                    "Due date must be in the future for published assignments"
                )
        return value

    def validate_total_marks(self, value):
        """Prevent changing total marks if submissions exist"""
        if self.instance and self.instance.submissions.exists():
            if value != self.instance.total_marks:
                raise serializers.ValidationError(
                    "Cannot change total marks after submissions exist"
                )
        return value


class AssignmentAnalyticsSerializer(serializers.Serializer):
    """Serializer for assignment analytics data"""

    assignment_id = serializers.IntegerField()
    title = serializers.CharField()
    total_students = serializers.IntegerField()
    submission_count = serializers.IntegerField()
    graded_count = serializers.IntegerField()
    completion_rate = serializers.FloatField()
    grading_rate = serializers.FloatField()
    late_submissions = serializers.IntegerField()
    on_time_submissions = serializers.IntegerField()
    average_score = serializers.FloatField(allow_null=True)
    highest_score = serializers.IntegerField(allow_null=True)
    lowest_score = serializers.IntegerField(allow_null=True)
    pass_rate = serializers.FloatField()
    grade_distribution = serializers.DictField()


class PlagiarismResultSerializer(serializers.Serializer):
    """Serializer for plagiarism check results"""

    submission_id = serializers.IntegerField()
    plagiarism_score = serializers.FloatField()
    is_suspicious = serializers.BooleanField()
    detailed_report = serializers.DictField()


class DeadlineReminderSerializer(serializers.Serializer):
    """Serializer for deadline reminders"""

    assignment_id = serializers.IntegerField()
    title = serializers.CharField()
    subject = serializers.CharField()
    due_date = serializers.DateTimeField()
    days_until_due = serializers.IntegerField()
    is_submitted = serializers.BooleanField(required=False)
    submission_status = serializers.CharField(required=False, allow_null=True)
    submission_count = serializers.IntegerField(required=False)
    graded_count = serializers.IntegerField(required=False)
