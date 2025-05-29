"""
REST API Serializers for Academics Module

This module provides serializers for converting model instances to/from JSON
for the REST API endpoints. Includes nested serializers for hierarchical data.
"""

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from ..models import AcademicYear, Class, Department, Grade, Section, Term


class DepartmentSerializer(serializers.ModelSerializer):
    """Serializer for Department model"""

    head_name = serializers.SerializerMethodField()
    teachers_count = serializers.SerializerMethodField()
    subjects_count = serializers.SerializerMethodField()

    class Meta:
        model = Department
        fields = [
            "id",
            "name",
            "description",
            "head",
            "head_name",
            "teachers_count",
            "subjects_count",
            "is_active",
            "creation_date",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["creation_date", "created_at", "updated_at"]

    def get_head_name(self, obj):
        """Get department head full name"""
        if obj.head:
            return f"{obj.head.user.first_name} {obj.head.user.last_name}"
        return None

    def get_teachers_count(self, obj):
        """Get count of teachers in department"""
        return obj.get_teachers_count()

    def get_subjects_count(self, obj):
        """Get count of subjects in department"""
        return obj.get_subjects_count()


class DepartmentSummarySerializer(serializers.ModelSerializer):
    """Lightweight serializer for Department references"""

    class Meta:
        model = Department
        fields = ["id", "name"]


class TermSerializer(serializers.ModelSerializer):
    """Serializer for Term model"""

    duration_days = serializers.SerializerMethodField()
    is_active = serializers.SerializerMethodField()
    progress = serializers.SerializerMethodField()

    class Meta:
        model = Term
        fields = [
            "id",
            "academic_year",
            "name",
            "term_number",
            "start_date",
            "end_date",
            "is_current",
            "duration_days",
            "is_active",
            "progress",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

    def get_duration_days(self, obj):
        """Get term duration in days"""
        return obj.get_duration_days()

    def get_is_active(self, obj):
        """Check if term is currently active"""
        return obj.is_active

    def get_progress(self, obj):
        """Get term progress information"""
        from ..services import TermService

        return TermService._calculate_term_progress(obj)

    def validate(self, data):
        """Validate term data"""
        if data.get("start_date") and data.get("end_date"):
            if data["start_date"] >= data["end_date"]:
                raise serializers.ValidationError("Start date must be before end date")

        return data


class TermSummarySerializer(serializers.ModelSerializer):
    """Lightweight serializer for Term references"""

    class Meta:
        model = Term
        fields = ["id", "name", "term_number", "is_current"]


class AcademicYearSerializer(serializers.ModelSerializer):
    """Serializer for AcademicYear model"""

    terms = TermSerializer(many=True, read_only=True)
    terms_count = serializers.SerializerMethodField()
    classes_count = serializers.SerializerMethodField()
    is_active = serializers.SerializerMethodField()
    current_term = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = AcademicYear
        fields = [
            "id",
            "name",
            "start_date",
            "end_date",
            "is_current",
            "terms",
            "terms_count",
            "classes_count",
            "is_active",
            "current_term",
            "created_by",
            "created_by_name",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

    def get_terms_count(self, obj):
        """Get count of terms in academic year"""
        return obj.terms.count()

    def get_classes_count(self, obj):
        """Get count of active classes in academic year"""
        return obj.classes.filter(is_active=True).count()

    def get_is_active(self, obj):
        """Check if academic year is currently active"""
        return obj.is_active

    def get_current_term(self, obj):
        """Get current term information"""
        current_term = obj.get_current_term()
        if current_term:
            return TermSummarySerializer(current_term).data
        return None

    def get_created_by_name(self, obj):
        """Get creator full name"""
        if obj.created_by:
            return f"{obj.created_by.first_name} {obj.created_by.last_name}"
        return None

    def validate(self, data):
        """Validate academic year data"""
        if data.get("start_date") and data.get("end_date"):
            if data["start_date"] >= data["end_date"]:
                raise serializers.ValidationError("Start date must be before end date")

        return data


class AcademicYearSummarySerializer(serializers.ModelSerializer):
    """Lightweight serializer for AcademicYear references"""

    class Meta:
        model = AcademicYear
        fields = ["id", "name", "is_current"]


class GradeSerializer(serializers.ModelSerializer):
    """Serializer for Grade model"""

    section_name = serializers.CharField(source="section.name", read_only=True)
    department_name = serializers.CharField(source="department.name", read_only=True)
    display_name = serializers.SerializerMethodField()
    classes_count = serializers.SerializerMethodField()
    students_count = serializers.SerializerMethodField()

    class Meta:
        model = Grade
        fields = [
            "id",
            "name",
            "description",
            "section",
            "section_name",
            "department",
            "department_name",
            "order_sequence",
            "minimum_age",
            "maximum_age",
            "is_active",
            "display_name",
            "classes_count",
            "students_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

    def get_display_name(self, obj):
        """Get grade display name"""
        return obj.display_name

    def get_classes_count(self, obj):
        """Get count of classes for current academic year"""
        from ..services import AcademicYearService

        current_year = AcademicYearService.get_current_academic_year()
        return obj.get_classes_count(current_year) if current_year else 0

    def get_students_count(self, obj):
        """Get count of students for current academic year"""
        from ..services import AcademicYearService

        current_year = AcademicYearService.get_current_academic_year()
        return obj.get_total_students(current_year) if current_year else 0

    def validate(self, data):
        """Validate grade data"""
        minimum_age = data.get("minimum_age")
        maximum_age = data.get("maximum_age")

        if minimum_age and maximum_age and minimum_age >= maximum_age:
            raise serializers.ValidationError(
                "Minimum age must be less than maximum age"
            )

        return data


class GradeSummarySerializer(serializers.ModelSerializer):
    """Lightweight serializer for Grade references"""

    section_name = serializers.CharField(source="section.name", read_only=True)

    class Meta:
        model = Grade
        fields = ["id", "name", "section", "section_name", "order_sequence"]


class ClassSerializer(serializers.ModelSerializer):
    """Serializer for Class model"""

    grade_name = serializers.CharField(source="grade.name", read_only=True)
    section_name = serializers.CharField(source="section.name", read_only=True)
    academic_year_name = serializers.CharField(
        source="academic_year.name", read_only=True
    )
    display_name = serializers.SerializerMethodField()
    full_name = serializers.SerializerMethodField()
    students_count = serializers.SerializerMethodField()
    available_capacity = serializers.SerializerMethodField()
    utilization_rate = serializers.SerializerMethodField()
    is_full = serializers.SerializerMethodField()
    class_teacher_name = serializers.SerializerMethodField()

    class Meta:
        model = Class
        fields = [
            "id",
            "name",
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
            "is_active",
            "display_name",
            "full_name",
            "students_count",
            "available_capacity",
            "utilization_rate",
            "is_full",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["section", "created_at", "updated_at"]

    def get_display_name(self, obj):
        """Get class display name"""
        return obj.display_name

    def get_full_name(self, obj):
        """Get class full name"""
        return obj.full_name

    def get_students_count(self, obj):
        """Get current student count"""
        return obj.get_students_count()

    def get_available_capacity(self, obj):
        """Get available capacity"""
        return obj.get_available_capacity()

    def get_utilization_rate(self, obj):
        """Get utilization rate percentage"""
        students = obj.get_students_count()
        return (students / obj.capacity * 100) if obj.capacity > 0 else 0

    def get_is_full(self, obj):
        """Check if class is at capacity"""
        return obj.is_full()

    def get_class_teacher_name(self, obj):
        """Get class teacher full name"""
        if obj.class_teacher:
            return f"{obj.class_teacher.user.first_name} {obj.class_teacher.user.last_name}"
        return None

    def validate_capacity(self, value):
        """Validate class capacity"""
        if value < 1 or value > 100:
            raise serializers.ValidationError("Capacity must be between 1 and 100")
        return value


class ClassSummarySerializer(serializers.ModelSerializer):
    """Lightweight serializer for Class references"""

    display_name = serializers.SerializerMethodField()
    students_count = serializers.SerializerMethodField()

    class Meta:
        model = Class
        fields = ["id", "name", "display_name", "capacity", "students_count"]

    def get_display_name(self, obj):
        return obj.display_name

    def get_students_count(self, obj):
        return obj.get_students_count()


class SectionSerializer(serializers.ModelSerializer):
    """Serializer for Section model"""

    department_name = serializers.CharField(source="department.name", read_only=True)
    grades = GradeSummarySerializer(many=True, read_only=True)
    grades_count = serializers.SerializerMethodField()
    total_students = serializers.SerializerMethodField()
    total_classes = serializers.SerializerMethodField()

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
            "grades",
            "grades_count",
            "total_students",
            "total_classes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

    def get_grades_count(self, obj):
        """Get count of active grades in section"""
        return obj.get_grades_count()

    def get_total_students(self, obj):
        """Get total students across all grades in section"""
        return obj.get_total_students()

    def get_total_classes(self, obj):
        """Get total classes in section for current academic year"""
        from ..services import AcademicYearService

        current_year = AcademicYearService.get_current_academic_year()

        if current_year:
            return obj.classes.filter(
                academic_year=current_year, is_active=True
            ).count()
        return 0


class SectionHierarchySerializer(serializers.ModelSerializer):
    """Detailed serializer for Section with full hierarchy"""

    department = DepartmentSummarySerializer(read_only=True)
    grades = serializers.SerializerMethodField()
    statistics = serializers.SerializerMethodField()

    class Meta:
        model = Section
        fields = [
            "id",
            "name",
            "description",
            "department",
            "order_sequence",
            "is_active",
            "grades",
            "statistics",
        ]

    def get_grades(self, obj):
        """Get grades with their classes"""
        from ..services import AcademicYearService

        current_year = AcademicYearService.get_current_academic_year()

        grades_data = []
        for grade in obj.get_grades():
            classes_qs = (
                grade.get_classes(current_year) if current_year else grade.get_classes()
            )

            grade_data = {
                "id": grade.id,
                "name": grade.name,
                "order_sequence": grade.order_sequence,
                "minimum_age": grade.minimum_age,
                "maximum_age": grade.maximum_age,
                "classes": ClassSummarySerializer(classes_qs, many=True).data,
            }
            grades_data.append(grade_data)

        return grades_data

    def get_statistics(self, obj):
        """Get section statistics"""
        from ..services import AcademicYearService

        current_year = AcademicYearService.get_current_academic_year()

        total_classes = 0
        total_students = 0

        if current_year:
            classes = obj.classes.filter(academic_year=current_year, is_active=True)
            total_classes = classes.count()
            total_students = sum(cls.get_students_count() for cls in classes)

        return {
            "total_grades": obj.get_grades_count(),
            "total_classes": total_classes,
            "total_students": total_students,
            "current_academic_year": current_year.name if current_year else None,
        }


# Create/Update serializers with validation


class AcademicYearCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating academic years"""

    terms_data = serializers.ListField(
        child=serializers.DictField(),
        write_only=True,
        required=False,
        help_text="Optional terms data to create with academic year",
    )

    class Meta:
        model = AcademicYear
        fields = ["name", "start_date", "end_date", "is_current", "terms_data"]

    def create(self, validated_data):
        """Create academic year with optional terms"""
        from ..services import AcademicYearService

        terms_data = validated_data.pop("terms_data", None)
        user = self.context["request"].user

        if terms_data:
            # Create with terms
            term_names = [term.get("name") for term in terms_data]
            academic_year = AcademicYearService.setup_academic_year_with_terms(
                name=validated_data["name"],
                start_date=validated_data["start_date"],
                end_date=validated_data["end_date"],
                num_terms=len(terms_data),
                user=user,
                is_current=validated_data.get("is_current", False),
                term_names=term_names,
            )
        else:
            # Create without terms
            academic_year = AcademicYearService.create_academic_year(
                name=validated_data["name"],
                start_date=validated_data["start_date"],
                end_date=validated_data["end_date"],
                user=user,
                is_current=validated_data.get("is_current", False),
            )

        return academic_year


class ClassCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating classes"""

    class Meta:
        model = Class
        fields = [
            "name",
            "grade",
            "academic_year",
            "room_number",
            "capacity",
            "class_teacher",
        ]

    def create(self, validated_data):
        """Create class using service"""
        from ..services import ClassService

        return ClassService.create_class(
            name=validated_data["name"],
            grade_id=validated_data["grade"].id,
            academic_year_id=validated_data["academic_year"].id,
            room_number=validated_data.get("room_number", ""),
            capacity=validated_data.get("capacity", 30),
            class_teacher_id=(
                validated_data.get("class_teacher").id
                if validated_data.get("class_teacher")
                else None
            ),
        )


class BulkClassCreateSerializer(serializers.Serializer):
    """Serializer for bulk class creation"""

    grade = serializers.PrimaryKeyRelatedField(queryset=Grade.objects.all())
    academic_year = serializers.PrimaryKeyRelatedField(
        queryset=AcademicYear.objects.all()
    )
    classes = serializers.ListField(
        child=serializers.DictField(), min_length=1, max_length=20
    )

    def validate_classes(self, value):
        """Validate class configurations"""
        for class_config in value:
            if "name" not in class_config:
                raise serializers.ValidationError("Each class must have a name")

            capacity = class_config.get("capacity", 30)
            if not isinstance(capacity, int) or capacity < 1 or capacity > 100:
                raise serializers.ValidationError("Capacity must be between 1 and 100")

        return value

    def create(self, validated_data):
        """Create multiple classes"""
        from ..services import ClassService

        return ClassService.bulk_create_classes(
            grade_id=validated_data["grade"].id,
            academic_year_id=validated_data["academic_year"].id,
            class_configs=validated_data["classes"],
        )
