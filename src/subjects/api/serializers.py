from rest_framework import serializers
from django.db import models
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from ..models import Subject, Syllabus, TopicProgress, SubjectAssignment
from academics.models import Grade, AcademicYear, Term, Class, Department
from teachers.models import Teacher

User = get_user_model()


class SubjectListSerializer(serializers.ModelSerializer):
    """Serializer for listing subjects with basic information."""

    department_name = serializers.CharField(source="department.name", read_only=True)
    applicable_grades = serializers.SerializerMethodField()
    total_syllabi = serializers.SerializerMethodField()

    class Meta:
        model = Subject
        fields = [
            "id",
            "name",
            "code",
            "department_name",
            "credit_hours",
            "is_elective",
            "is_active",
            "applicable_grades",
            "total_syllabi",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def get_applicable_grades(self, obj):
        """Get list of grade names this subject applies to."""
        if not obj.grade_level:
            return "All Grades"
        grades = Grade.objects.filter(id__in=obj.grade_level)
        return [grade.name for grade in grades]

    def get_total_syllabi(self, obj):
        """Get total number of syllabi for this subject."""
        return obj.syllabi.filter(is_active=True).count()


class SubjectDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for subject with all information."""

    department_name = serializers.CharField(source="department.name", read_only=True)
    department_id = serializers.IntegerField(source="department.id", read_only=True)
    applicable_grades_detail = serializers.SerializerMethodField()
    syllabi_summary = serializers.SerializerMethodField()
    completion_stats = serializers.SerializerMethodField()

    class Meta:
        model = Subject
        fields = [
            "id",
            "name",
            "code",
            "description",
            "department_id",
            "department_name",
            "credit_hours",
            "is_elective",
            "grade_level",
            "is_active",
            "applicable_grades_detail",
            "syllabi_summary",
            "completion_stats",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_applicable_grades_detail(self, obj):
        """Get detailed information about applicable grades."""
        if not obj.grade_level:
            return Grade.objects.all().values("id", "name", "order_sequence")
        grades = Grade.objects.filter(id__in=obj.grade_level)
        return grades.values("id", "name", "order_sequence")

    def get_syllabi_summary(self, obj):
        """Get summary of syllabi for this subject."""
        syllabi = obj.syllabi.filter(is_active=True)
        return {
            "total_count": syllabi.count(),
            "by_academic_year": list(
                syllabi.values("academic_year__name")
                .annotate(count=models.Count("id"))
                .order_by("academic_year__name")
            ),
        }

    def get_completion_stats(self, obj):
        """Get completion statistics for this subject."""
        syllabi = obj.syllabi.filter(is_active=True)
        if not syllabi.exists():
            return None

        from django.db import models

        return {
            "average_completion": syllabi.aggregate(
                avg=models.Avg("completion_percentage")
            )["avg"]
            or 0,
            "completed_count": syllabi.filter(completion_percentage=100).count(),
            "in_progress_count": syllabi.filter(
                completion_percentage__gt=0, completion_percentage__lt=100
            ).count(),
            "not_started_count": syllabi.filter(completion_percentage=0).count(),
        }


class SubjectCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating and updating subjects."""

    class Meta:
        model = Subject
        fields = [
            "name",
            "code",
            "description",
            "department",
            "credit_hours",
            "is_elective",
            "grade_level",
            "is_active",
        ]

    def validate_code(self, value):
        """Validate subject code uniqueness."""
        if self.instance:
            # Update case - exclude current instance
            if Subject.objects.exclude(id=self.instance.id).filter(code=value).exists():
                raise serializers.ValidationError(_("Subject code already exists"))
        else:
            # Create case
            if Subject.objects.filter(code=value).exists():
                raise serializers.ValidationError(_("Subject code already exists"))
        return value

    def validate_grade_level(self, value):
        """Validate grade level IDs."""
        if value:
            valid_grades = Grade.objects.filter(id__in=value).count()
            if valid_grades != len(value):
                raise serializers.ValidationError(_("One or more invalid grade IDs"))
        return value


class SyllabusListSerializer(serializers.ModelSerializer):
    """Serializer for listing syllabi with essential information."""

    subject_name = serializers.CharField(source="subject.name", read_only=True)
    subject_code = serializers.CharField(source="subject.code", read_only=True)
    grade_name = serializers.CharField(source="grade.name", read_only=True)
    term_name = serializers.CharField(source="term.name", read_only=True)
    academic_year_name = serializers.CharField(
        source="academic_year.name", read_only=True
    )
    created_by_name = serializers.CharField(
        source="created_by.get_full_name", read_only=True
    )
    progress_status = serializers.CharField(read_only=True)
    total_topics = serializers.SerializerMethodField()
    completed_topics = serializers.SerializerMethodField()

    class Meta:
        model = Syllabus
        fields = [
            "id",
            "title",
            "subject_name",
            "subject_code",
            "grade_name",
            "term_name",
            "academic_year_name",
            "completion_percentage",
            "progress_status",
            "total_topics",
            "completed_topics",
            "difficulty_level",
            "estimated_duration_hours",
            "created_by_name",
            "created_at",
            "last_updated_at",
            "is_active",
        ]
        read_only_fields = ["id", "created_at", "last_updated_at"]

    def get_total_topics(self, obj):
        """Get total number of topics."""
        return obj.get_total_topics()

    def get_completed_topics(self, obj):
        """Get number of completed topics."""
        return obj.get_completed_topics()


class SyllabusDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for syllabus with full content."""

    subject_detail = SubjectListSerializer(source="subject", read_only=True)
    grade_name = serializers.CharField(source="grade.name", read_only=True)
    term_name = serializers.CharField(source="term.name", read_only=True)
    academic_year_name = serializers.CharField(
        source="academic_year.name", read_only=True
    )
    created_by_name = serializers.CharField(
        source="created_by.get_full_name", read_only=True
    )
    last_updated_by_name = serializers.CharField(
        source="last_updated_by.get_full_name", read_only=True
    )
    progress_status = serializers.CharField(read_only=True)
    topic_progress_details = serializers.SerializerMethodField()
    content_statistics = serializers.SerializerMethodField()

    class Meta:
        model = Syllabus
        fields = [
            "id",
            "title",
            "description",
            "subject_detail",
            "grade_name",
            "term_name",
            "academic_year_name",
            "content",
            "learning_objectives",
            "completion_percentage",
            "progress_status",
            "estimated_duration_hours",
            "difficulty_level",
            "prerequisites",
            "assessment_methods",
            "resources",
            "topic_progress_details",
            "content_statistics",
            "created_by_name",
            "last_updated_by_name",
            "created_at",
            "last_updated_at",
            "is_active",
        ]
        read_only_fields = ["id", "created_at", "last_updated_at"]

    def get_topic_progress_details(self, obj):
        """Get detailed topic progress information."""
        progress_items = obj.topic_progress.all().order_by("topic_index")
        return TopicProgressSerializer(progress_items, many=True).data

    def get_content_statistics(self, obj):
        """Get content-related statistics."""
        return {
            "total_topics": obj.get_total_topics(),
            "completed_topics": obj.get_completed_topics(),
            "learning_objectives_count": len(obj.learning_objectives or []),
            "prerequisites_count": len(obj.prerequisites or []),
            "assessment_methods_count": len(obj.assessment_methods or []),
        }


class SyllabusCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating and updating syllabi."""

    class Meta:
        model = Syllabus
        fields = [
            "subject",
            "grade",
            "academic_year",
            "term",
            "title",
            "description",
            "content",
            "learning_objectives",
            "estimated_duration_hours",
            "difficulty_level",
            "prerequisites",
            "assessment_methods",
            "resources",
        ]

    def validate(self, data):
        """Validate syllabus data."""
        # Check unique constraint
        if self.instance:
            # Update case
            existing = Syllabus.objects.exclude(id=self.instance.id).filter(
                subject=data.get("subject", self.instance.subject),
                grade=data.get("grade", self.instance.grade),
                academic_year=data.get("academic_year", self.instance.academic_year),
                term=data.get("term", self.instance.term),
            )
        else:
            # Create case
            existing = Syllabus.objects.filter(
                subject=data["subject"],
                grade=data["grade"],
                academic_year=data["academic_year"],
                term=data["term"],
            )

        if existing.exists():
            raise serializers.ValidationError(
                _("Syllabus already exists for this subject, grade, and term")
            )

        # Validate subject is applicable for grade
        subject = data.get("subject", getattr(self.instance, "subject", None))
        grade = data.get("grade", getattr(self.instance, "grade", None))

        if subject and grade and not subject.is_applicable_for_grade(grade.id):
            raise serializers.ValidationError(
                _("Subject '{}' is not applicable for grade '{}'").format(
                    subject.name, grade.name
                )
            )

        # Validate term belongs to academic year
        term = data.get("term", getattr(self.instance, "term", None))
        academic_year = data.get(
            "academic_year", getattr(self.instance, "academic_year", None)
        )

        if term and academic_year and term.academic_year != academic_year:
            raise serializers.ValidationError(
                _("Term '{}' does not belong to academic year '{}'").format(
                    term.name, academic_year.name
                )
            )

        return data


class TopicProgressSerializer(serializers.ModelSerializer):
    """Serializer for topic progress tracking."""

    syllabus_title = serializers.CharField(source="syllabus.title", read_only=True)

    class Meta:
        model = TopicProgress
        fields = [
            "id",
            "syllabus",
            "syllabus_title",
            "topic_name",
            "topic_index",
            "is_completed",
            "completion_date",
            "hours_taught",
            "teaching_method",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate(self, data):
        """Validate topic progress data."""
        # Ensure topic_index is unique within syllabus
        syllabus = data.get("syllabus")
        topic_index = data.get("topic_index")

        if self.instance:
            existing = TopicProgress.objects.exclude(id=self.instance.id).filter(
                syllabus=syllabus or self.instance.syllabus,
                topic_index=topic_index or self.instance.topic_index,
            )
        else:
            existing = TopicProgress.objects.filter(
                syllabus=syllabus, topic_index=topic_index
            )

        if existing.exists():
            raise serializers.ValidationError(
                _("Topic progress already exists for this syllabus and topic index")
            )

        return data


class SubjectAssignmentSerializer(serializers.ModelSerializer):
    """Serializer for subject assignments to teachers."""

    subject_name = serializers.CharField(source="subject.name", read_only=True)
    subject_code = serializers.CharField(source="subject.code", read_only=True)
    teacher_name = serializers.CharField(
        source="teacher.user.get_full_name", read_only=True
    )
    class_name = serializers.CharField(source="class_assigned.__str__", read_only=True)
    term_name = serializers.CharField(source="term.name", read_only=True)
    academic_year_name = serializers.CharField(
        source="academic_year.name", read_only=True
    )
    assigned_by_name = serializers.CharField(
        source="assigned_by.get_full_name", read_only=True
    )

    class Meta:
        model = SubjectAssignment
        fields = [
            "id",
            "subject",
            "subject_name",
            "subject_code",
            "teacher",
            "teacher_name",
            "class_assigned",
            "class_name",
            "academic_year",
            "academic_year_name",
            "term",
            "term_name",
            "is_primary_teacher",
            "assigned_date",
            "assigned_by",
            "assigned_by_name",
            "is_active",
        ]
        read_only_fields = ["id", "assigned_date"]

    def validate(self, data):
        """Validate assignment data."""
        # Check if subject is applicable for the class's grade
        subject = data.get("subject")
        class_assigned = data.get("class_assigned")

        if subject and class_assigned:
            if not subject.is_applicable_for_grade(class_assigned.grade.id):
                raise serializers.ValidationError(
                    _("Subject '{}' is not applicable for grade '{}'").format(
                        subject.name, class_assigned.grade.name
                    )
                )

        # Check for existing assignment (allow updates)
        if not self.instance:
            existing = SubjectAssignment.objects.filter(
                subject=subject,
                class_assigned=class_assigned,
                academic_year=data.get("academic_year"),
                term=data.get("term"),
                is_active=True,
            )
            if existing.exists():
                raise serializers.ValidationError(
                    _("Assignment already exists for this subject, class, and term")
                )

        return data


class BulkSubjectCreateSerializer(serializers.Serializer):
    """Serializer for bulk subject creation."""

    department = serializers.PrimaryKeyRelatedField(queryset=Department.objects.all())
    subjects_data = serializers.ListField(
        child=serializers.DictField(), min_length=1, max_length=100
    )

    def validate_subjects_data(self, value):
        """Validate subjects data structure."""
        required_fields = ["name", "code"]

        for i, subject_data in enumerate(value):
            for field in required_fields:
                if field not in subject_data:
                    raise serializers.ValidationError(
                        _("Row {}: Missing required field '{}'").format(i + 1, field)
                    )

            # Validate optional fields
            if "credit_hours" in subject_data:
                try:
                    credit_hours = int(subject_data["credit_hours"])
                    if credit_hours < 1 or credit_hours > 10:
                        raise serializers.ValidationError(
                            _("Row {}: Credit hours must be between 1 and 10").format(
                                i + 1
                            )
                        )
                except (ValueError, TypeError):
                    raise serializers.ValidationError(
                        _("Row {}: Invalid credit hours value").format(i + 1)
                    )

        return value


class SyllabusProgressUpdateSerializer(serializers.Serializer):
    """Serializer for updating syllabus progress."""

    topic_index = serializers.IntegerField(min_value=0)
    completion_data = serializers.DictField(required=False)

    def validate_topic_index(self, value):
        """Validate topic index exists in syllabus."""
        syllabus = self.context.get("syllabus")
        if syllabus:
            total_topics = syllabus.get_total_topics()
            if value >= total_topics:
                raise serializers.ValidationError(
                    _("Topic index {} does not exist in syllabus").format(value)
                )
        return value


class CurriculumAnalyticsSerializer(serializers.Serializer):
    """Serializer for curriculum analytics data."""

    academic_year_id = serializers.IntegerField()
    grade_id = serializers.IntegerField(required=False)
    department_id = serializers.IntegerField(required=False)
    overview = serializers.DictField(read_only=True)
    by_department = serializers.DictField(read_only=True)
    by_grade = serializers.DictField(read_only=True)
    completion_distribution = serializers.DictField(read_only=True)


class TeacherWorkloadSerializer(serializers.Serializer):
    """Serializer for teacher workload information."""

    teacher_id = serializers.IntegerField()
    academic_year_id = serializers.IntegerField()
    term_id = serializers.IntegerField(required=False)
    total_subjects = serializers.IntegerField(read_only=True)
    total_classes = serializers.IntegerField(read_only=True)
    total_credit_hours = serializers.IntegerField(read_only=True)
    primary_assignments = serializers.IntegerField(read_only=True)
    secondary_assignments = serializers.IntegerField(read_only=True)
    assignments_by_term = serializers.DictField(read_only=True)
    assignments_detail = serializers.ListField(read_only=True)
