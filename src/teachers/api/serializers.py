# src/teachers/api/serializers.py
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db.models import Avg, Count
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from src.accounts.api.serializers import UserBasicSerializer
from src.courses.models import AcademicYear, Class, Department, Subject
from src.teachers.models import Teacher, TeacherClassAssignment, TeacherEvaluation

User = get_user_model()


class DepartmentSerializer(serializers.ModelSerializer):
    """Lightweight department serializer for teacher context."""

    class Meta:
        model = Department
        fields = ["id", "name", "description"]


class TeacherListSerializer(serializers.ModelSerializer):
    """Serializer for teacher list view with essential information."""

    full_name = serializers.SerializerMethodField()
    department_name = serializers.CharField(source="department.name", read_only=True)
    email = serializers.CharField(source="user.email", read_only=True)
    phone_number = serializers.CharField(source="user.phone_number", read_only=True)
    years_of_service = serializers.SerializerMethodField()
    average_evaluation_score = serializers.SerializerMethodField()
    total_evaluations = serializers.SerializerMethodField()

    class Meta:
        model = Teacher
        fields = [
            "id",
            "employee_id",
            "full_name",
            "email",
            "phone_number",
            "department_name",
            "position",
            "status",
            "contract_type",
            "experience_years",
            "joining_date",
            "years_of_service",
            "average_evaluation_score",
            "total_evaluations",
        ]

    def get_full_name(self, obj):
        return obj.get_full_name()

    def get_years_of_service(self, obj):
        return obj.get_years_of_service()

    def get_average_evaluation_score(self, obj):
        avg_score = obj.get_average_evaluation_score()
        return float(avg_score) if avg_score else None

    def get_total_evaluations(self, obj):
        return obj.evaluations.count()


class TeacherDetailSerializer(serializers.ModelSerializer):
    """Detailed teacher serializer with all information."""

    user = UserBasicSerializer(read_only=True)
    department = DepartmentSerializer(read_only=True)
    full_name = serializers.SerializerMethodField()
    years_of_service = serializers.SerializerMethodField()
    performance_metrics = serializers.SerializerMethodField()
    current_assignments = serializers.SerializerMethodField()
    recent_evaluations = serializers.SerializerMethodField()

    class Meta:
        model = Teacher
        fields = [
            "id",
            "user",
            "employee_id",
            "joining_date",
            "qualification",
            "experience_years",
            "specialization",
            "department",
            "position",
            "salary",
            "contract_type",
            "status",
            "bio",
            "emergency_contact",
            "emergency_phone",
            "created_at",
            "updated_at",
            "full_name",
            "years_of_service",
            "performance_metrics",
            "current_assignments",
            "recent_evaluations",
        ]

    def get_full_name(self, obj):
        return obj.get_full_name()

    def get_years_of_service(self, obj):
        return obj.get_years_of_service()

    def get_performance_metrics(self, obj):
        from src.teachers.services.analytics_service import TeacherAnalyticsService

        return TeacherAnalyticsService.get_teacher_growth_analysis(obj.id, months=12)

    def get_current_assignments(self, obj):
        current_year = AcademicYear.objects.filter(is_current=True).first()
        if current_year:
            assignments = TeacherClassAssignment.objects.filter(
                teacher=obj, academic_year=current_year
            ).select_related("class_instance", "subject")
            return TeacherClassAssignmentSerializer(assignments, many=True).data
        return []

    def get_recent_evaluations(self, obj):
        recent_evaluations = obj.evaluations.order_by("-evaluation_date")[:5]
        return TeacherEvaluationListSerializer(recent_evaluations, many=True).data


class TeacherCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating and updating teachers."""

    # User related fields
    first_name = serializers.CharField(max_length=100)
    last_name = serializers.CharField(max_length=100)
    email = serializers.EmailField()
    phone_number = serializers.CharField(
        max_length=20, required=False, allow_blank=True
    )

    class Meta:
        model = Teacher
        fields = [
            "employee_id",
            "first_name",
            "last_name",
            "email",
            "phone_number",
            "joining_date",
            "qualification",
            "experience_years",
            "specialization",
            "department",
            "position",
            "salary",
            "contract_type",
            "status",
            "bio",
            "emergency_contact",
            "emergency_phone",
        ]

    def validate_email(self, value):
        """Validate email uniqueness."""
        instance_id = self.instance.user.id if self.instance else None
        if User.objects.filter(email=value).exclude(id=instance_id).exists():
            raise ValidationError("This email is already in use.")
        return value

    def validate_employee_id(self, value):
        """Validate employee ID uniqueness."""
        instance_id = self.instance.id if self.instance else None
        if Teacher.objects.filter(employee_id=value).exclude(id=instance_id).exists():
            raise ValidationError("This employee ID is already in use.")
        return value

    def validate(self, attrs):
        """Cross-field validation."""
        # Validate joining date is not in the future
        if attrs.get("joining_date") and attrs["joining_date"] > timezone.now().date():
            raise ValidationError(
                {"joining_date": "Joining date cannot be in the future."}
            )

        # Validate experience years
        experience = attrs.get("experience_years", 0)
        if experience < 0:
            raise ValidationError(
                {"experience_years": "Experience years cannot be negative."}
            )

        # Validate salary
        salary = attrs.get("salary", 0)
        if salary < 0:
            raise ValidationError({"salary": "Salary cannot be negative."})

        return attrs

    def create(self, validated_data):
        """Create teacher with associated user."""
        # Extract user data
        user_data = {
            "first_name": validated_data.pop("first_name"),
            "last_name": validated_data.pop("last_name"),
            "email": validated_data.pop("email"),
            "username": validated_data["email"],
            "is_active": True,
        }

        phone_number = validated_data.pop("phone_number", "")
        if phone_number:
            user_data["phone_number"] = phone_number

        # Create user
        user = User.objects.create(**user_data)

        # Create teacher
        teacher = Teacher.objects.create(user=user, **validated_data)

        return teacher

    def update(self, instance, validated_data):
        """Update teacher and associated user."""
        # Extract user data
        user_data = {}
        if "first_name" in validated_data:
            user_data["first_name"] = validated_data.pop("first_name")
        if "last_name" in validated_data:
            user_data["last_name"] = validated_data.pop("last_name")
        if "email" in validated_data:
            user_data["email"] = validated_data.pop("email")
            user_data["username"] = user_data["email"]
        if "phone_number" in validated_data:
            user_data["phone_number"] = validated_data.pop("phone_number")

        # Update user
        if user_data:
            for attr, value in user_data.items():
                setattr(instance.user, attr, value)
            instance.user.save()

        # Update teacher
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        return instance


class SubjectBasicSerializer(serializers.ModelSerializer):
    """Basic subject serializer for assignments."""

    class Meta:
        model = Subject
        fields = ["id", "name", "code"]


class ClassBasicSerializer(serializers.ModelSerializer):
    """Basic class serializer for assignments."""

    class_name = serializers.SerializerMethodField()

    class Meta:
        model = Class
        fields = ["id", "class_name", "room_number", "capacity"]

    def get_class_name(self, obj):
        return str(obj)


class TeacherClassAssignmentSerializer(serializers.ModelSerializer):
    """Serializer for teacher class assignments."""

    teacher_name = serializers.CharField(source="teacher.get_full_name", read_only=True)
    class_instance = ClassBasicSerializer(read_only=True)
    subject = SubjectBasicSerializer(read_only=True)
    academic_year_name = serializers.CharField(
        source="academic_year.name", read_only=True
    )

    class Meta:
        model = TeacherClassAssignment
        fields = [
            "id",
            "teacher",
            "teacher_name",
            "class_instance",
            "subject",
            "academic_year",
            "academic_year_name",
            "is_class_teacher",
            "notes",
            "created_at",
            "updated_at",
        ]


class TeacherClassAssignmentCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating teacher class assignments."""

    class Meta:
        model = TeacherClassAssignment
        fields = [
            "teacher",
            "class_instance",
            "subject",
            "academic_year",
            "is_class_teacher",
            "notes",
        ]

    def validate(self, attrs):
        """Validate assignment constraints."""
        teacher = attrs["teacher"]
        class_instance = attrs["class_instance"]
        subject = attrs["subject"]
        academic_year = attrs["academic_year"]
        is_class_teacher = attrs.get("is_class_teacher", False)

        # Check if assignment already exists
        existing = TeacherClassAssignment.objects.filter(
            teacher=teacher,
            class_instance=class_instance,
            subject=subject,
            academic_year=academic_year,
        )

        if self.instance:
            existing = existing.exclude(id=self.instance.id)

        if existing.exists():
            raise ValidationError(
                "This teacher is already assigned to this class and subject."
            )

        # Check if another teacher is already the class teacher
        if is_class_teacher:
            existing_class_teacher = TeacherClassAssignment.objects.filter(
                class_instance=class_instance,
                academic_year=academic_year,
                is_class_teacher=True,
            )

            if self.instance:
                existing_class_teacher = existing_class_teacher.exclude(
                    id=self.instance.id
                )

            if existing_class_teacher.exists():
                existing_teacher = existing_class_teacher.first().teacher
                raise ValidationError(
                    {
                        "is_class_teacher": f"{existing_teacher.get_full_name()} is already the class teacher."
                    }
                )

        return attrs


class TeacherEvaluationListSerializer(serializers.ModelSerializer):
    """Serializer for evaluation list view."""

    teacher_name = serializers.CharField(source="teacher.get_full_name", read_only=True)
    evaluator_name = serializers.CharField(
        source="evaluator.get_full_name", read_only=True
    )
    performance_level = serializers.SerializerMethodField()

    class Meta:
        model = TeacherEvaluation
        fields = [
            "id",
            "teacher",
            "teacher_name",
            "evaluator",
            "evaluator_name",
            "evaluation_date",
            "score",
            "performance_level",
            "status",
            "followup_date",
            "created_at",
        ]

    def get_performance_level(self, obj):
        return obj.get_performance_level()


class TeacherEvaluationDetailSerializer(serializers.ModelSerializer):
    """Detailed evaluation serializer."""

    teacher = TeacherListSerializer(read_only=True)
    evaluator = UserBasicSerializer(read_only=True)
    performance_level = serializers.SerializerMethodField()
    is_followup_required = serializers.SerializerMethodField()
    is_followup_overdue = serializers.SerializerMethodField()
    criteria_summary = serializers.SerializerMethodField()

    class Meta:
        model = TeacherEvaluation
        fields = [
            "id",
            "teacher",
            "evaluator",
            "evaluation_date",
            "criteria",
            "score",
            "performance_level",
            "remarks",
            "followup_actions",
            "status",
            "followup_date",
            "is_followup_required",
            "is_followup_overdue",
            "criteria_summary",
            "created_at",
            "updated_at",
        ]

    def get_performance_level(self, obj):
        return obj.get_performance_level()

    def get_is_followup_required(self, obj):
        return obj.is_followup_required()

    def get_is_followup_overdue(self, obj):
        return obj.is_followup_overdue()

    def get_criteria_summary(self, obj):
        """Get formatted criteria summary."""
        summary = {}
        total_score = 0
        max_total = 0

        for criterion, data in obj.criteria.items():
            if isinstance(data, dict) and "score" in data:
                score = data["score"]
                max_score = data.get("max_score", 10)
                percentage = (score / max_score * 100) if max_score > 0 else 0

                summary[criterion] = {
                    "score": score,
                    "max_score": max_score,
                    "percentage": round(percentage, 1),
                    "comments": data.get("comments", ""),
                }

                total_score += score
                max_total += max_score

        summary["overall"] = {
            "total_score": total_score,
            "max_total": max_total,
            "percentage": round(
                (total_score / max_total * 100) if max_total > 0 else 0, 1
            ),
        }

        return summary


class TeacherEvaluationCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating evaluations."""

    class Meta:
        model = TeacherEvaluation
        fields = [
            "teacher",
            "evaluation_date",
            "criteria",
            "remarks",
            "followup_actions",
            "status",
            "followup_date",
        ]

    def validate_criteria(self, value):
        """Validate criteria structure."""
        if not isinstance(value, dict):
            raise ValidationError("Criteria must be a valid JSON object.")

        required_criteria = TeacherEvaluation.EVALUATION_CATEGORIES

        for criterion in required_criteria:
            if criterion not in value:
                raise ValidationError(f"Missing required criterion: {criterion}")

            criterion_data = value[criterion]
            if not isinstance(criterion_data, dict):
                raise ValidationError(f"Invalid data for criterion: {criterion}")

            if "score" not in criterion_data or "max_score" not in criterion_data:
                raise ValidationError(
                    f"Criterion {criterion} must have 'score' and 'max_score' fields."
                )

            try:
                score = float(criterion_data["score"])
                max_score = float(criterion_data["max_score"])

                if score < 0 or score > max_score:
                    raise ValidationError(
                        f"Score for {criterion} must be between 0 and {max_score}."
                    )

            except (ValueError, TypeError):
                raise ValidationError(
                    f"Invalid score values for criterion: {criterion}"
                )

        return value

    def validate(self, attrs):
        """Cross-field validation."""
        evaluation_date = attrs.get("evaluation_date")
        score = attrs.get("score")
        followup_actions = attrs.get("followup_actions")
        followup_date = attrs.get("followup_date")

        # Validate evaluation date
        if evaluation_date and evaluation_date > timezone.now().date():
            raise ValidationError(
                {"evaluation_date": "Evaluation date cannot be in the future."}
            )

        # Calculate score from criteria if not provided
        if not score and "criteria" in attrs:
            total_score = 0
            max_total = 0

            for criterion_data in attrs["criteria"].values():
                if isinstance(criterion_data, dict):
                    total_score += criterion_data.get("score", 0)
                    max_total += criterion_data.get("max_score", 10)

            attrs["score"] = (total_score / max_total * 100) if max_total > 0 else 0

        # Validate followup requirements for low scores
        if attrs["score"] < 70:
            if not followup_actions:
                raise ValidationError(
                    {
                        "followup_actions": "Follow-up actions are required for low performance evaluations."
                    }
                )

            if not followup_date:
                # Auto-set followup date to 30 days from evaluation
                attrs["followup_date"] = evaluation_date + timezone.timedelta(days=30)

        return attrs

    def create(self, validated_data):
        """Create evaluation with auto-calculated score."""
        # Set evaluator from request user
        request = self.context.get("request")
        if request and request.user:
            validated_data["evaluator"] = request.user

        return super().create(validated_data)


class TeacherAnalyticsSerializer(serializers.Serializer):
    """Serializer for teacher analytics data."""

    # Performance metrics
    total_teachers = serializers.IntegerField()
    active_teachers = serializers.IntegerField()
    avg_experience = serializers.DecimalField(max_digits=4, decimal_places=1)
    avg_evaluation_score = serializers.DecimalField(max_digits=5, decimal_places=2)

    # Performance distribution
    performance_distribution = serializers.ListField()

    # Department comparison
    departmental_performance = serializers.ListField()

    # Workload analysis
    workload_distribution = serializers.ListField()

    # Trends
    evaluation_trends = serializers.ListField()


class TeacherPerformanceSerializer(serializers.Serializer):
    """Serializer for individual teacher performance data."""

    teacher_id = serializers.IntegerField()
    teacher_name = serializers.CharField()
    average_score = serializers.DecimalField(max_digits=5, decimal_places=2)
    evaluation_count = serializers.IntegerField()
    latest_evaluation_date = serializers.DateField()
    growth_rate = serializers.DecimalField(max_digits=5, decimal_places=2)
    improvement_trend = serializers.CharField()
    criteria_analysis = serializers.DictField()


class TeacherWorkloadSerializer(serializers.Serializer):
    """Serializer for teacher workload data."""

    teacher_id = serializers.IntegerField()
    teacher_name = serializers.CharField()
    department = serializers.CharField()
    total_classes = serializers.IntegerField()
    total_subjects = serializers.IntegerField()
    total_students = serializers.IntegerField()
    class_teacher_count = serializers.IntegerField()
    workload_level = serializers.SerializerMethodField()

    def get_workload_level(self, obj):
        """Determine workload level based on class count."""
        classes = obj.get("total_classes", 0)
        if classes >= 8:
            return "Overloaded"
        elif classes >= 4:
            return "Balanced"
        else:
            return "Underutilized"
