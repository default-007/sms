"""
API Serializers for Academics Module
"""

from rest_framework import serializers
from ..models import AcademicYear, Section, Grade, Class, Term, Department


class DepartmentSerializer(serializers.ModelSerializer):
    """Serializer for Department model"""

    class Meta:
        model = Department
        fields = [
            "id",
            "name",
            "description",
            "head",
            "creation_date",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "creation_date", "created_at", "updated_at"]


class AcademicYearSerializer(serializers.ModelSerializer):
    """Serializer for AcademicYear model"""

    class Meta:
        model = AcademicYear
        fields = [
            "id",
            "name",
            "start_date",
            "end_date",
            "is_current",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate(self, data):
        """Validate academic year dates"""
        if data.get("start_date") and data.get("end_date"):
            if data["start_date"] >= data["end_date"]:
                raise serializers.ValidationError("Start date must be before end date")
        return data


class SectionSerializer(serializers.ModelSerializer):
    """Serializer for Section model"""

    department_name = serializers.CharField(source="department.name", read_only=True)

    class Meta:
        model = Section
        fields = [
            "id",
            "name",
            "description",
            "department",
            "department_name",
            "order_sequence",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "department_name"]

    def validate_name(self, value):
        """Validate section name uniqueness"""
        instance = self.instance
        if (
            Section.objects.filter(name__iexact=value)
            .exclude(pk=instance.pk if instance else None)
            .exists()
        ):
            raise serializers.ValidationError(
                f"Section with name '{value}' already exists"
            )
        return value


class GradeSerializer(serializers.ModelSerializer):
    """Serializer for Grade model"""

    section_name = serializers.CharField(source="section.name", read_only=True)

    class Meta:
        model = Grade
        fields = [
            "id",
            "name",
            "description",
            "section",
            "section_name",
            "order_sequence",
            "minimum_age",
            "maximum_age",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "section_name"]

    def validate_name(self, value):
        """Validate grade name uniqueness within section"""
        instance = self.instance
        section = self.initial_data.get("section") or (
            instance.section if instance else None
        )

        if (
            section
            and Grade.objects.filter(name__iexact=value, section=section)
            .exclude(pk=instance.pk if instance else None)
            .exists()
        ):
            raise serializers.ValidationError(
                f"Grade with name '{value}' already exists in this section"
            )
        return value

    def validate(self, data):
        """Validate age constraints"""
        minimum_age = data.get("minimum_age")
        maximum_age = data.get("maximum_age")

        if min_age is not None and max_age is not None:
            if min_age >= max_age:
                raise serializers.ValidationError(
                    "Minimum age must be less than maximum age"
                )

        return data


class GradeCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating grades with validation
    """

    class Meta:
        model = Grade
        fields = [
            "name",
            "description",
            "section",
            "department",
            "order_sequence",
            "minimum_age",  # Use correct field names
            "maximum_age",  # Use correct field names
            "is_active",
        ]

    def create(self, validated_data):
        """
        Create grade using GradeService
        """
        from ..services.grade_service import GradeService

        return GradeService.create_grade(
            name=validated_data["name"],
            section_id=validated_data["section"].id,
            description=validated_data.get("description", ""),
            department_id=(
                validated_data.get("department").id
                if validated_data.get("department")
                else None
            ),
            order_sequence=validated_data.get("order_sequence"),
            minimum_age=validated_data.get("minimum_age"),  # Correct field name
            maximum_age=validated_data.get("maximum_age"),  # Correct field name
        )


class ClassSerializer(serializers.ModelSerializer):
    """Serializer for Class model"""

    grade_name = serializers.CharField(source="grade.name", read_only=True)
    section_name = serializers.CharField(source="grade.section.name", read_only=True)
    academic_year_name = serializers.CharField(
        source="academic_year.name", read_only=True
    )
    class_teacher_name = serializers.CharField(
        source="class_teacher.user.get_full_name", read_only=True
    )
    display_name = serializers.CharField(read_only=True)

    class Meta:
        model = Class
        fields = [
            "id",
            "name",
            "display_name",
            "grade",
            "grade_name",
            "section_name",
            "academic_year",
            "academic_year_name",
            "class_teacher",
            "class_teacher_name",
            "room_number",
            "capacity",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "display_name",
            "grade_name",
            "section_name",
            "academic_year_name",
            "class_teacher_name",
            "created_at",
            "updated_at",
        ]

    def validate(self, data):
        """Validate class name uniqueness within grade and academic year"""
        instance = self.instance
        name = data.get("name")
        grade = data.get("grade")
        academic_year = data.get("academic_year")

        if name and grade and academic_year:
            if (
                Class.objects.filter(
                    name__iexact=name, grade=grade, academic_year=academic_year
                )
                .exclude(pk=instance.pk if instance else None)
                .exists()
            ):
                raise serializers.ValidationError(
                    f"Class with name '{name}' already exists for this grade in the academic year"
                )

        # Validate capacity
        capacity = data.get("capacity")
        if capacity is not None and capacity < 1:
            raise serializers.ValidationError("Capacity must be at least 1")

        return data


class TermSerializer(serializers.ModelSerializer):
    """Serializer for Term model"""

    academic_year_name = serializers.CharField(
        source="academic_year.name", read_only=True
    )

    class Meta:
        model = Term
        fields = [
            "id",
            "name",
            "academic_year",
            "academic_year_name",
            "term_number",
            "start_date",
            "end_date",
            "is_current",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "academic_year_name", "created_at", "updated_at"]

    def validate(self, data):
        """Validate term dates and term number"""
        start_date = data.get("start_date")
        end_date = data.get("end_date")
        academic_year = data.get("academic_year")
        term_number = data.get("term_number")
        instance = self.instance

        # Validate date range
        if start_date and end_date:
            if start_date >= end_date:
                raise serializers.ValidationError("Start date must be before end date")

        # Validate dates are within academic year
        if academic_year and start_date and end_date:
            if (
                start_date < academic_year.start_date
                or end_date > academic_year.end_date
            ):
                raise serializers.ValidationError(
                    "Term dates must be within academic year dates"
                )

        # Validate term number uniqueness
        if academic_year and term_number:
            if (
                Term.objects.filter(
                    academic_year=academic_year, term_number=term_number
                )
                .exclude(pk=instance.pk if instance else None)
                .exists()
            ):
                raise serializers.ValidationError(
                    f"Term {term_number} already exists in this academic year"
                )

        return data


# Summary serializers for quick responses


class SectionSummarySerializer(serializers.ModelSerializer):
    """Summary serializer for sections"""

    class Meta:
        model = Section
        fields = ["id", "name", "order_sequence", "is_active"]


class GradeSummarySerializer(serializers.ModelSerializer):
    """Summary serializer for grades"""

    section_name = serializers.CharField(source="section.name", read_only=True)

    class Meta:
        model = Grade
        fields = [
            "id",
            "name",
            "section",
            "section_name",
            "order_sequence",
            "is_active",
        ]


class ClassSummarySerializer(serializers.ModelSerializer):
    """Summary serializer for classes"""

    grade_name = serializers.CharField(source="grade.name", read_only=True)
    display_name = serializers.CharField(read_only=True)

    class Meta:
        model = Class
        fields = [
            "id",
            "name",
            "display_name",
            "grade",
            "grade_name",
            "capacity",
            "is_active",
        ]
