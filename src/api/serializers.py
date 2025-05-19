from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.validators import validate_email
from src.accounts.models import UserRole, UserRoleAssignment, UserProfile
from src.students.models import Student, Parent, StudentParentRelation
from src.teachers.models import Teacher, TeacherClassAssignment, TeacherEvaluation
from src.courses.models import (
    Department,
    AcademicYear,
    Grade,
    Section,
    Class,
    Subject,
    Syllabus,
    TimeSlot,
    Timetable,
    Assignment,
    AssignmentSubmission,
)
from src.core.models import SystemSetting, Document

User = get_user_model()


# User and Role Serializers

User = get_user_model()


class UserRoleSerializer(serializers.ModelSerializer):
    """Serializer for UserRole model."""

    permission_count = serializers.SerializerMethodField()
    assigned_users_count = serializers.SerializerMethodField()

    class Meta:
        model = UserRole
        fields = [
            "id",
            "name",
            "description",
            "permissions",
            "is_system_role",
            "created_at",
            "updated_at",
            "permission_count",
            "assigned_users_count",
        ]
        read_only_fields = [
            "created_at",
            "updated_at",
            "permission_count",
            "assigned_users_count",
        ]

    def get_permission_count(self, obj):
        return obj.get_permission_count()

    def get_assigned_users_count(self, obj):
        return obj.user_assignments.filter(is_active=True).count()

    def validate_permissions(self, value):
        """Validate permissions structure."""
        from ..services import RoleService

        is_valid, message = RoleService.validate_permissions(value)
        if not is_valid:
            raise serializers.ValidationError(message)
        return value


class UserRoleAssignmentSerializer(serializers.ModelSerializer):
    """Serializer for UserRoleAssignment model."""

    role_name = serializers.CharField(source="role.name", read_only=True)
    user_username = serializers.CharField(source="user.username", read_only=True)
    assigned_by_username = serializers.CharField(
        source="assigned_by.username", read_only=True
    )
    is_expired = serializers.SerializerMethodField()
    days_until_expiry = serializers.SerializerMethodField()

    class Meta:
        model = UserRoleAssignment
        fields = [
            "id",
            "user",
            "role",
            "role_name",
            "user_username",
            "assigned_date",
            "assigned_by",
            "assigned_by_username",
            "expires_at",
            "is_active",
            "notes",
            "is_expired",
            "days_until_expiry",
        ]
        read_only_fields = ["assigned_date", "is_expired", "days_until_expiry"]

    def get_is_expired(self, obj):
        return obj.is_expired()

    def get_days_until_expiry(self, obj):
        return obj.days_until_expiry()


class UserProfileSerializer(serializers.ModelSerializer):
    """Serializer for UserProfile model."""

    class Meta:
        model = UserProfile
        fields = [
            "bio",
            "website",
            "location",
            "birth_date",
            "language",
            "timezone",
            "email_notifications",
            "sms_notifications",
            "linkedin_url",
            "twitter_url",
            "facebook_url",
        ]


class UserSerializer(serializers.ModelSerializer):
    """Enhanced serializer for User model."""

    full_name = serializers.CharField(source="get_full_name", read_only=True)
    initials = serializers.CharField(source="get_initials", read_only=True)
    age = serializers.IntegerField(source="get_age", read_only=True)
    assigned_roles = serializers.StringRelatedField(
        source="get_assigned_roles", many=True, read_only=True
    )
    profile = UserProfileSerializer(read_only=True)
    role_assignments = UserRoleAssignmentSerializer(many=True, read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "phone_number",
            "address",
            "date_of_birth",
            "gender",
            "profile_picture",
            "is_active",
            "date_joined",
            "last_login",
            "full_name",
            "initials",
            "age",
            "assigned_roles",
            "profile",
            "role_assignments",
            "requires_password_change",
        ]
        read_only_fields = [
            "date_joined",
            "last_login",
            "full_name",
            "initials",
            "age",
            "assigned_roles",
            "role_assignments",
        ]
        extra_kwargs = {
            "password": {"write_only": True},
            "profile_picture": {"required": False},
        }

    def validate_email(self, value):
        """Validate email uniqueness."""
        if self.instance and self.instance.email == value:
            return value

        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def validate_username(self, value):
        """Validate username uniqueness."""
        if self.instance and self.instance.username == value:
            return value

        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError(
                "A user with this username already exists."
            )
        return value


class UserCreateSerializer(UserSerializer):
    """Serializer for creating users with password."""

    password = serializers.CharField(write_only=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True)
    roles = serializers.ListField(
        child=serializers.CharField(),
        write_only=True,
        required=False,
        help_text="List of role names to assign to the user",
    )

    class Meta(UserSerializer.Meta):
        fields = UserSerializer.Meta.fields + ["password", "password_confirm", "roles"]

    def validate(self, attrs):
        """Validate password confirmation and roles."""
        if attrs.get("password") != attrs.get("password_confirm"):
            raise serializers.ValidationError("Passwords don't match.")

        # Validate roles exist
        if "roles" in attrs:
            role_names = attrs["roles"]
            existing_roles = UserRole.objects.filter(name__in=role_names).values_list(
                "name", flat=True
            )
            invalid_roles = set(role_names) - set(existing_roles)
            if invalid_roles:
                raise serializers.ValidationError(
                    f"Invalid roles: {', '.join(invalid_roles)}"
                )

        return attrs

    def create(self, validated_data):
        """Create user with password and roles."""
        from ..services import RoleService

        password = validated_data.pop("password")
        validated_data.pop("password_confirm")
        roles = validated_data.pop("roles", [])

        user = User.objects.create(**validated_data)
        user.set_password(password)
        user.save()

        # Assign roles
        for role_name in roles:
            RoleService.assign_role_to_user(user, role_name)

        return user


class UserUpdateSerializer(UserSerializer):
    """Serializer for updating users."""

    roles = serializers.ListField(
        child=serializers.CharField(),
        write_only=True,
        required=False,
        help_text="List of role names to assign to the user",
    )

    class Meta(UserSerializer.Meta):
        fields = UserSerializer.Meta.fields + ["roles"]

    def validate(self, attrs):
        """Validate roles if provided."""
        if "roles" in attrs:
            role_names = attrs["roles"]
            existing_roles = UserRole.objects.filter(name__in=role_names).values_list(
                "name", flat=True
            )
            invalid_roles = set(role_names) - set(existing_roles)
            if invalid_roles:
                raise serializers.ValidationError(
                    f"Invalid roles: {', '.join(invalid_roles)}"
                )

        return attrs

    def update(self, instance, validated_data):
        """Update user and roles."""
        from ..services import RoleService

        roles = validated_data.pop("roles", None)

        # Update user fields
        user = super().update(instance, validated_data)

        # Update roles if provided
        if roles is not None:
            # Remove all current role assignments
            instance.role_assignments.all().delete()

            # Assign new roles
            for role_name in roles:
                RoleService.assign_role_to_user(instance, role_name)

        return user


class PasswordChangeSerializer(serializers.Serializer):
    """Serializer for password change."""

    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(
        write_only=True, validators=[validate_password]
    )
    new_password_confirm = serializers.CharField(write_only=True)

    def validate_current_password(self, value):
        """Validate current password."""
        if not self.context["request"].user.check_password(value):
            raise serializers.ValidationError("Current password is incorrect.")
        return value

    def validate(self, attrs):
        """Validate password confirmation."""
        if attrs["new_password"] != attrs["new_password_confirm"]:
            raise serializers.ValidationError("New passwords don't match.")
        return attrs

    def save(self):
        """Update user password."""
        user = self.context["request"].user
        user.set_password(self.validated_data["new_password"])
        user.password_changed_at = timezone.now()
        user.requires_password_change = False
        user.save()
        return user


class UserStatsSerializer(serializers.Serializer):
    """Serializer for user statistics."""

    total_users = serializers.IntegerField()
    active_users = serializers.IntegerField()
    inactive_users = serializers.IntegerField()
    users_by_role = serializers.DictField()
    recent_registrations = serializers.IntegerField()
    users_requiring_password_change = serializers.IntegerField()


class UserBulkActionSerializer(serializers.Serializer):
    """Serializer for bulk user actions."""

    ACTION_CHOICES = [
        ("activate", "Activate"),
        ("deactivate", "Deactivate"),
        ("assign_roles", "Assign Roles"),
        ("remove_roles", "Remove Roles"),
        ("require_password_change", "Require Password Change"),
    ]

    user_ids = serializers.ListField(
        child=serializers.IntegerField(),
        min_length=1,
        help_text="List of user IDs to perform action on",
    )
    action = serializers.ChoiceField(choices=ACTION_CHOICES)
    roles = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        help_text="List of role names (required for role-related actions)",
    )

    def validate(self, attrs):
        """Validate action and required fields."""
        action = attrs["action"]

        if action in ["assign_roles", "remove_roles"] and not attrs.get("roles"):
            raise serializers.ValidationError(
                "Roles are required for role-related actions."
            )

        # Validate user IDs exist
        user_ids = attrs["user_ids"]
        existing_users = User.objects.filter(id__in=user_ids).count()
        if existing_users != len(user_ids):
            raise serializers.ValidationError("Some user IDs are invalid.")

        # Validate roles if provided
        if attrs.get("roles"):
            role_names = attrs["roles"]
            existing_roles = UserRole.objects.filter(name__in=role_names).count()
            if existing_roles != len(role_names):
                raise serializers.ValidationError("Some role names are invalid.")

        return attrs


# Student Serializers
class StudentSerializer(serializers.ModelSerializer):
    user_details = UserSerializer(source="user", read_only=True)
    current_class_name = serializers.CharField(
        source="current_class.__str__", read_only=True
    )

    class Meta:
        model = Student
        fields = (
            "id",
            "user",
            "user_details",
            "admission_number",
            "admission_date",
            "current_class",
            "current_class_name",
            "roll_number",
            "blood_group",
            "medical_conditions",
            "emergency_contact_name",
            "emergency_contact_number",
            "previous_school",
            "status",
        )


class ParentSerializer(serializers.ModelSerializer):
    user_details = UserSerializer(source="user", read_only=True)

    class Meta:
        model = Parent
        fields = (
            "id",
            "user",
            "user_details",
            "occupation",
            "annual_income",
            "education",
            "relation_with_student",
        )


class StudentParentRelationSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.__str__", read_only=True)
    parent_name = serializers.CharField(source="parent.__str__", read_only=True)

    class Meta:
        model = StudentParentRelation
        fields = (
            "id",
            "student",
            "student_name",
            "parent",
            "parent_name",
            "is_primary_contact",
        )


# Teacher Serializers
class TeacherSerializer(serializers.ModelSerializer):
    user_details = UserSerializer(source="user", read_only=True)
    department_name = serializers.CharField(source="department.name", read_only=True)

    class Meta:
        model = Teacher
        fields = (
            "id",
            "user",
            "user_details",
            "employee_id",
            "joining_date",
            "qualification",
            "experience_years",
            "specialization",
            "department",
            "department_name",
            "position",
            "salary",
            "contract_type",
            "status",
        )


class TeacherClassAssignmentSerializer(serializers.ModelSerializer):
    teacher_name = serializers.CharField(source="teacher.__str__", read_only=True)
    class_name = serializers.CharField(source="class_instance.__str__", read_only=True)
    subject_name = serializers.CharField(source="subject.name", read_only=True)
    academic_year_name = serializers.CharField(
        source="academic_year.name", read_only=True
    )

    class Meta:
        model = TeacherClassAssignment
        fields = (
            "id",
            "teacher",
            "teacher_name",
            "class_instance",
            "class_name",
            "subject",
            "subject_name",
            "academic_year",
            "academic_year_name",
            "is_class_teacher",
        )


class TeacherEvaluationSerializer(serializers.ModelSerializer):
    teacher_name = serializers.CharField(source="teacher.__str__", read_only=True)
    evaluator_name = serializers.CharField(source="evaluator.__str__", read_only=True)

    class Meta:
        model = TeacherEvaluation
        fields = (
            "id",
            "teacher",
            "teacher_name",
            "evaluator",
            "evaluator_name",
            "evaluation_date",
            "criteria",
            "score",
            "remarks",
            "followup_actions",
        )


# Course Serializers
class DepartmentSerializer(serializers.ModelSerializer):
    head_name = serializers.CharField(source="head.__str__", read_only=True)

    class Meta:
        model = Department
        fields = ("id", "name", "description", "head", "head_name", "creation_date")
        read_only_fields = ("creation_date",)


class AcademicYearSerializer(serializers.ModelSerializer):
    class Meta:
        model = AcademicYear
        fields = ("id", "name", "start_date", "end_date", "is_current")


class GradeSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source="department.name", read_only=True)

    class Meta:
        model = Grade
        fields = ("id", "name", "description", "department", "department_name")


class SectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Section
        fields = ("id", "name", "description")


class ClassSerializer(serializers.ModelSerializer):
    grade_name = serializers.CharField(source="grade.name", read_only=True)
    section_name = serializers.CharField(source="section.name", read_only=True)
    academic_year_name = serializers.CharField(
        source="academic_year.name", read_only=True
    )
    class_teacher_name = serializers.CharField(
        source="class_teacher.__str__", read_only=True
    )

    class Meta:
        model = Class
        fields = (
            "id",
            "grade",
            "grade_name",
            "section",
            "section_name",
            "academic_year",
            "academic_year_name",
            "room_number",
            "capacity",
            "class_teacher",
            "class_teacher_name",
        )


class SubjectSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source="department.name", read_only=True)

    class Meta:
        model = Subject
        fields = (
            "id",
            "name",
            "code",
            "description",
            "department",
            "department_name",
            "credit_hours",
            "is_elective",
        )


class SyllabusSerializer(serializers.ModelSerializer):
    subject_name = serializers.CharField(source="subject.name", read_only=True)
    grade_name = serializers.CharField(source="grade.name", read_only=True)
    academic_year_name = serializers.CharField(
        source="academic_year.name", read_only=True
    )
    created_by_name = serializers.CharField(source="created_by.__str__", read_only=True)
    last_updated_by_name = serializers.CharField(
        source="last_updated_by.__str__", read_only=True
    )

    class Meta:
        model = Syllabus
        fields = (
            "id",
            "subject",
            "subject_name",
            "grade",
            "grade_name",
            "academic_year",
            "academic_year_name",
            "title",
            "description",
            "content",
            "created_by",
            "created_by_name",
            "last_updated_by",
            "last_updated_by_name",
            "last_updated_at",
        )
        read_only_fields = ("last_updated_at",)


class TimeSlotSerializer(serializers.ModelSerializer):
    day_display = serializers.CharField(
        source="get_day_of_week_display", read_only=True
    )

    class Meta:
        model = TimeSlot
        fields = (
            "id",
            "day_of_week",
            "day_display",
            "start_time",
            "end_time",
            "duration_minutes",
        )
        read_only_fields = ("duration_minutes",)


class TimetableSerializer(serializers.ModelSerializer):
    class_name = serializers.CharField(source="class_obj.__str__", read_only=True)
    subject_name = serializers.CharField(source="subject.name", read_only=True)
    teacher_name = serializers.CharField(source="teacher.__str__", read_only=True)
    time_slot_display = serializers.CharField(
        source="time_slot.__str__", read_only=True
    )

    class Meta:
        model = Timetable
        fields = (
            "id",
            "class_obj",
            "class_name",
            "subject",
            "subject_name",
            "teacher",
            "teacher_name",
            "time_slot",
            "time_slot_display",
            "room",
            "effective_from_date",
            "effective_to_date",
            "is_active",
        )


class AssignmentSerializer(serializers.ModelSerializer):
    class_name = serializers.CharField(source="class_obj.__str__", read_only=True)
    subject_name = serializers.CharField(source="subject.name", read_only=True)
    teacher_name = serializers.CharField(source="teacher.__str__", read_only=True)

    class Meta:
        model = Assignment
        fields = (
            "id",
            "title",
            "description",
            "class_obj",
            "class_name",
            "subject",
            "subject_name",
            "teacher",
            "teacher_name",
            "assigned_date",
            "due_date",
            "total_marks",
            "attachment",
            "submission_type",
            "status",
        )
        read_only_fields = ("assigned_date",)


class AssignmentSubmissionSerializer(serializers.ModelSerializer):
    assignment_title = serializers.CharField(source="assignment.title", read_only=True)
    student_name = serializers.CharField(source="student.__str__", read_only=True)
    graded_by_name = serializers.CharField(source="graded_by.__str__", read_only=True)

    class Meta:
        model = AssignmentSubmission
        fields = (
            "id",
            "assignment",
            "assignment_title",
            "student",
            "student_name",
            "submission_date",
            "content",
            "file",
            "remarks",
            "marks_obtained",
            "status",
            "graded_by",
            "graded_by_name",
            "graded_at",
        )
        read_only_fields = ("submission_date", "graded_at")


# Core Serializers
class SystemSettingSerializer(serializers.ModelSerializer):
    class Meta:
        model = SystemSetting
        fields = (
            "id",
            "setting_key",
            "setting_value",
            "data_type",
            "description",
            "is_editable",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("created_at", "updated_at")


class DocumentSerializer(serializers.ModelSerializer):
    uploaded_by_name = serializers.CharField(
        source="uploaded_by.__str__", read_only=True
    )

    class Meta:
        model = Document
        fields = (
            "id",
            "title",
            "description",
            "file_path",
            "file_type",
            "upload_date",
            "uploaded_by",
            "uploaded_by_name",
            "category",
            "related_to_id",
            "related_to_type",
            "is_public",
        )
        read_only_fields = ("upload_date", "file_type")
