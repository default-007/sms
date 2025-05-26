"""
School Management System - Exam Serializers
File: src/exams/api/serializers.py
"""

from django.contrib.auth import get_user_model
from rest_framework import serializers

from ..models import (
    Exam,
    ExamQuestion,
    ExamSchedule,
    ExamType,
    GradeScale,
    GradingSystem,
    OnlineExam,
    OnlineExamQuestion,
    ReportCard,
    StudentExamResult,
    StudentOnlineExamAttempt,
)

User = get_user_model()


class ExamTypeSerializer(serializers.ModelSerializer):
    """Serializer for ExamType model"""

    class Meta:
        model = ExamType
        fields = [
            "id",
            "name",
            "description",
            "contribution_percentage",
            "is_term_based",
            "frequency",
            "max_attempts",
            "is_online",
            "duration_minutes",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class ExamListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for exam listings"""

    exam_type_name = serializers.CharField(source="exam_type.name", read_only=True)
    academic_year_name = serializers.CharField(
        source="academic_year.name", read_only=True
    )
    term_name = serializers.CharField(source="term.name", read_only=True)
    completion_rate = serializers.ReadOnlyField()
    schedules_count = serializers.SerializerMethodField()

    class Meta:
        model = Exam
        fields = [
            "id",
            "name",
            "exam_type_name",
            "academic_year_name",
            "term_name",
            "start_date",
            "end_date",
            "status",
            "is_published",
            "completion_rate",
            "total_students",
            "completed_count",
            "schedules_count",
        ]

    def get_schedules_count(self, obj):
        return obj.schedules.count()


class ExamDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for exam CRUD operations"""

    exam_type_details = ExamTypeSerializer(source="exam_type", read_only=True)
    created_by_name = serializers.CharField(
        source="created_by.get_full_name", read_only=True
    )
    completion_rate = serializers.ReadOnlyField()
    is_active = serializers.ReadOnlyField()

    class Meta:
        model = Exam
        fields = [
            "id",
            "name",
            "exam_type",
            "exam_type_details",
            "academic_year",
            "term",
            "start_date",
            "end_date",
            "description",
            "instructions",
            "grading_system",
            "passing_percentage",
            "status",
            "is_published",
            "publish_results",
            "total_students",
            "completed_count",
            "completion_rate",
            "is_active",
            "created_by",
            "created_by_name",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "total_students",
            "completed_count",
            "completion_rate",
            "is_active",
            "created_at",
            "updated_at",
        ]

    def validate(self, data):
        if data.get("start_date") and data.get("end_date"):
            if data["start_date"] > data["end_date"]:
                raise serializers.ValidationError("Start date cannot be after end date")
        return data


class ExamScheduleListSerializer(serializers.ModelSerializer):
    """Serializer for exam schedule listings"""

    exam_name = serializers.CharField(source="exam.name", read_only=True)
    class_name = serializers.CharField(
        source="class_obj.get_display_name", read_only=True
    )
    subject_name = serializers.CharField(source="subject.name", read_only=True)
    supervisor_name = serializers.CharField(
        source="supervisor.user.get_full_name", read_only=True
    )
    duration_hours = serializers.ReadOnlyField()
    passing_percentage = serializers.ReadOnlyField()

    class Meta:
        model = ExamSchedule
        fields = [
            "id",
            "exam_name",
            "class_name",
            "subject_name",
            "date",
            "start_time",
            "end_time",
            "duration_minutes",
            "duration_hours",
            "room",
            "supervisor_name",
            "total_marks",
            "passing_marks",
            "passing_percentage",
            "is_completed",
            "is_active",
        ]


class ExamScheduleDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for exam schedule operations"""

    additional_supervisors_details = serializers.SerializerMethodField()
    results_count = serializers.SerializerMethodField()

    class Meta:
        model = ExamSchedule
        fields = [
            "id",
            "exam",
            "class_obj",
            "subject",
            "date",
            "start_time",
            "end_time",
            "duration_minutes",
            "room",
            "supervisor",
            "additional_supervisors",
            "additional_supervisors_details",
            "total_marks",
            "passing_marks",
            "special_instructions",
            "materials_allowed",
            "is_active",
            "is_completed",
            "results_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "results_count", "created_at", "updated_at"]

    def get_additional_supervisors_details(self, obj):
        return [
            {
                "id": teacher.id,
                "name": teacher.user.get_full_name(),
                "employee_id": teacher.employee_id,
            }
            for teacher in obj.additional_supervisors.all()
        ]

    def get_results_count(self, obj):
        return obj.student_results.count()

    def validate(self, data):
        if data.get("start_time") and data.get("end_time"):
            if data["start_time"] >= data["end_time"]:
                raise serializers.ValidationError("Start time must be before end time")

        if data.get("passing_marks") and data.get("total_marks"):
            if data["passing_marks"] > data["total_marks"]:
                raise serializers.ValidationError(
                    "Passing marks cannot exceed total marks"
                )

        return data


class StudentExamResultSerializer(serializers.ModelSerializer):
    """Serializer for student exam results"""

    student_name = serializers.CharField(
        source="student.user.get_full_name", read_only=True
    )
    student_admission_number = serializers.CharField(
        source="student.admission_number", read_only=True
    )
    subject_name = serializers.CharField(
        source="exam_schedule.subject.name", read_only=True
    )
    total_marks = serializers.CharField(
        source="exam_schedule.total_marks", read_only=True
    )
    entered_by_name = serializers.CharField(
        source="entered_by.get_full_name", read_only=True
    )

    class Meta:
        model = StudentExamResult
        fields = [
            "id",
            "student",
            "student_name",
            "student_admission_number",
            "exam_schedule",
            "subject_name",
            "term",
            "marks_obtained",
            "total_marks",
            "percentage",
            "grade",
            "grade_point",
            "is_pass",
            "is_absent",
            "is_exempted",
            "remarks",
            "teacher_comments",
            "class_rank",
            "grade_rank",
            "entered_by",
            "entered_by_name",
            "entry_date",
        ]
        read_only_fields = [
            "id",
            "percentage",
            "grade",
            "is_pass",
            "class_rank",
            "grade_rank",
            "entry_date",
        ]


class BulkResultEntrySerializer(serializers.Serializer):
    """Serializer for bulk result entry"""

    exam_schedule = serializers.UUIDField()
    results = serializers.ListField(
        child=serializers.DictField(child=serializers.CharField())
    )

    def validate_results(self, value):
        required_fields = ["student_id", "marks_obtained"]
        for result in value:
            for field in required_fields:
                if field not in result:
                    raise serializers.ValidationError(
                        f"Missing required field: {field}"
                    )
        return value


class ReportCardSerializer(serializers.ModelSerializer):
    """Serializer for student report cards"""

    student_name = serializers.CharField(
        source="student.user.get_full_name", read_only=True
    )
    student_admission_number = serializers.CharField(
        source="student.admission_number", read_only=True
    )
    class_name = serializers.CharField(
        source="class_obj.get_display_name", read_only=True
    )
    academic_year_name = serializers.CharField(
        source="academic_year.name", read_only=True
    )
    term_name = serializers.CharField(source="term.name", read_only=True)
    rank_suffix = serializers.ReadOnlyField()
    subject_results = serializers.SerializerMethodField()

    class Meta:
        model = ReportCard
        fields = [
            "id",
            "student",
            "student_name",
            "student_admission_number",
            "class_obj",
            "class_name",
            "academic_year",
            "academic_year_name",
            "term",
            "term_name",
            "total_marks",
            "marks_obtained",
            "percentage",
            "grade",
            "grade_point_average",
            "class_rank",
            "class_size",
            "grade_rank",
            "grade_size",
            "rank_suffix",
            "attendance_percentage",
            "days_present",
            "days_absent",
            "total_days",
            "class_teacher_remarks",
            "principal_remarks",
            "achievements",
            "areas_for_improvement",
            "generation_date",
            "status",
            "subject_results",
        ]
        read_only_fields = ["id", "generation_date", "rank_suffix", "subject_results"]

    def get_subject_results(self, obj):
        results = StudentExamResult.objects.filter(
            student=obj.student, term=obj.term
        ).select_related("exam_schedule__subject")

        return [
            {
                "subject": result.exam_schedule.subject.name,
                "marks_obtained": result.marks_obtained,
                "total_marks": result.exam_schedule.total_marks,
                "percentage": result.percentage,
                "grade": result.grade,
                "remarks": result.remarks,
            }
            for result in results
        ]


class GradingSystemSerializer(serializers.ModelSerializer):
    """Serializer for grading systems"""

    grade_scales = serializers.SerializerMethodField()

    class Meta:
        model = GradingSystem
        fields = [
            "id",
            "academic_year",
            "name",
            "description",
            "is_default",
            "is_active",
            "grade_scales",
            "created_at",
        ]
        read_only_fields = ["id", "grade_scales", "created_at"]

    def get_grade_scales(self, obj):
        return GradeScaleSerializer(obj.grade_scales.all(), many=True).data


class GradeScaleSerializer(serializers.ModelSerializer):
    """Serializer for grade scales"""

    class Meta:
        model = GradeScale
        fields = [
            "id",
            "grading_system",
            "grade_name",
            "min_percentage",
            "max_percentage",
            "grade_point",
            "description",
            "color_code",
        ]
        read_only_fields = ["id"]


class ExamQuestionSerializer(serializers.ModelSerializer):
    """Serializer for exam questions"""

    subject_name = serializers.CharField(source="subject.name", read_only=True)
    grade_name = serializers.CharField(source="grade.name", read_only=True)
    created_by_name = serializers.CharField(
        source="created_by.get_full_name", read_only=True
    )

    class Meta:
        model = ExamQuestion
        fields = [
            "id",
            "subject",
            "subject_name",
            "grade",
            "grade_name",
            "question_text",
            "question_type",
            "difficulty_level",
            "marks",
            "options",
            "correct_answer",
            "explanation",
            "topic",
            "learning_objective",
            "created_by",
            "created_by_name",
            "is_active",
            "usage_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "usage_count", "created_at", "updated_at"]


class OnlineExamSerializer(serializers.ModelSerializer):
    """Serializer for online exams"""

    exam_schedule_details = ExamScheduleListSerializer(
        source="exam_schedule", read_only=True
    )
    questions_count = serializers.SerializerMethodField()
    total_marks = serializers.SerializerMethodField()

    class Meta:
        model = OnlineExam
        fields = [
            "id",
            "exam_schedule",
            "exam_schedule_details",
            "time_limit_minutes",
            "max_attempts",
            "shuffle_questions",
            "shuffle_options",
            "show_results_immediately",
            "enable_proctoring",
            "webcam_required",
            "fullscreen_required",
            "access_code",
            "ip_restrictions",
            "questions_count",
            "total_marks",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "questions_count",
            "total_marks",
            "created_at",
            "updated_at",
        ]

    def get_questions_count(self, obj):
        return obj.questions.count()

    def get_total_marks(self, obj):
        return sum(q.marks for q in obj.onlineexamquestion_set.all())


class OnlineExamQuestionSerializer(serializers.ModelSerializer):
    """Serializer for online exam questions"""

    question_details = ExamQuestionSerializer(source="question", read_only=True)

    class Meta:
        model = OnlineExamQuestion
        fields = ["id", "online_exam", "question", "question_details", "order", "marks"]


class StudentOnlineExamAttemptSerializer(serializers.ModelSerializer):
    """Serializer for student online exam attempts"""

    student_name = serializers.CharField(
        source="student.user.get_full_name", read_only=True
    )
    exam_details = OnlineExamSerializer(source="online_exam", read_only=True)
    percentage = serializers.SerializerMethodField()
    time_taken = serializers.SerializerMethodField()

    class Meta:
        model = StudentOnlineExamAttempt
        fields = [
            "id",
            "student",
            "student_name",
            "online_exam",
            "exam_details",
            "attempt_number",
            "start_time",
            "submit_time",
            "time_remaining_seconds",
            "responses",
            "total_marks",
            "marks_obtained",
            "auto_graded_marks",
            "manual_graded_marks",
            "percentage",
            "time_taken",
            "status",
            "is_graded",
            "violation_count",
        ]
        read_only_fields = ["id", "start_time", "percentage", "time_taken"]

    def get_percentage(self, obj):
        if obj.total_marks > 0:
            return round((obj.marks_obtained / obj.total_marks) * 100, 2)
        return 0

    def get_time_taken(self, obj):
        if obj.submit_time and obj.start_time:
            delta = obj.submit_time - obj.start_time
            return int(delta.total_seconds() / 60)  # minutes
        return None


class ExamAnalyticsSerializer(serializers.Serializer):
    """Serializer for exam analytics data"""

    exam_info = serializers.DictField()
    performance_summary = serializers.DictField()
    subject_wise_analysis = serializers.ListField()
    grade_distribution = serializers.DictField()
    class_comparison = serializers.ListField()
    top_performers = serializers.ListField()
    improvement_areas = serializers.ListField()


class QuestionBankFilterSerializer(serializers.Serializer):
    """Serializer for question bank filtering"""

    subject = serializers.UUIDField(required=False)
    grade = serializers.UUIDField(required=False)
    question_type = serializers.ChoiceField(
        choices=ExamQuestion.QUESTION_TYPES, required=False
    )
    difficulty_level = serializers.ChoiceField(
        choices=ExamQuestion.DIFFICULTY_LEVELS, required=False
    )
    topic = serializers.CharField(required=False)
    marks = serializers.IntegerField(required=False)


class AutoQuestionSelectionSerializer(serializers.Serializer):
    """Serializer for automatic question selection"""

    total_questions = serializers.IntegerField(required=False)
    total_marks = serializers.IntegerField(required=False)
    difficulty_distribution = serializers.DictField(required=False)
    topic_distribution = serializers.DictField(required=False)
    question_types = serializers.ListField(
        child=serializers.ChoiceField(choices=ExamQuestion.QUESTION_TYPES),
        required=False,
    )
