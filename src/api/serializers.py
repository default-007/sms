from rest_framework import serializers
from django.contrib.auth import get_user_model
from src.accounts.models import UserRole, UserRoleAssignment
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
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = (
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
        )
        read_only_fields = ("date_joined", "last_login")
        extra_kwargs = {"password": {"write_only": True}}


class UserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True, required=True, style={"input_type": "password"}
    )
    password_confirm = serializers.CharField(
        write_only=True, required=True, style={"input_type": "password"}
    )

    class Meta:
        model = User
        fields = (
            "username",
            "email",
            "first_name",
            "last_name",
            "phone_number",
            "address",
            "date_of_birth",
            "gender",
            "profile_picture",
            "password",
            "password_confirm",
        )

    def validate(self, data):
        if data["password"] != data.pop("password_confirm"):
            raise serializers.ValidationError(
                {"password_confirm": "Passwords do not match."}
            )
        return data

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user


class UserRoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserRole
        fields = ("id", "name", "description", "permissions")


class UserRoleAssignmentSerializer(serializers.ModelSerializer):
    role_name = serializers.CharField(source="role.name", read_only=True)

    class Meta:
        model = UserRoleAssignment
        fields = ("id", "user", "role", "role_name", "assigned_date", "assigned_by")
        read_only_fields = ("assigned_date",)


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
