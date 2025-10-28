# students/api/serializers.py
from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import serializers

from ..exceptions import AdmissionNumberExistsError, RelationshipExistsError
from ..models import Parent, Student, StudentParentRelation
from ..validators import validate_parent_data, validate_student_data

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    """Serializer for User model in student context"""

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "phone_number",
            "date_of_birth",
            "is_active",
            "date_joined",
        ]
        read_only_fields = ["id", "username", "date_joined"]

    def validate_email(self, value):
        instance = getattr(self, "instance", None)
        if instance and instance.pk:
            if User.objects.filter(email=value).exclude(pk=instance.pk).exists():
                raise serializers.ValidationError("Email already exists")
        elif User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Email already exists")
        return value


class StudentListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for student lists"""

    full_name = serializers.CharField(source="get_full_name", read_only=True)
    age = serializers.IntegerField(read_only=True)
    class_name = serializers.CharField(source="current_class", read_only=True)
    parent_count = serializers.SerializerMethodField()

    class Meta:
        model = Student
        fields = [
            "id",
            "admission_number",
            "full_name",
            "age",
            "status",
            "class_name",
            "blood_group",
            "photo",
            "parent_count",
        ]

    def get_parent_count(self, obj):
        return obj.student_parent_relations.count()


class StudentDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for student CRUD operations (students have direct fields, no user)"""

    full_name = serializers.CharField(source="full_name", read_only=True)
    age = serializers.IntegerField(read_only=True)
    attendance_percentage = serializers.SerializerMethodField()
    siblings = serializers.SerializerMethodField()
    parents = serializers.SerializerMethodField()

    class Meta:
        model = Student
        fields = [
            "id",
            "first_name",
            "last_name",
            "email",
            "phone_number",
            "date_of_birth",
            "gender",
            "address",
            "profile_picture",
            "admission_number",
            "registration_number",
            "admission_date",
            "current_class",
            "roll_number",
            "blood_group",
            "medical_conditions",
            "emergency_contact_name",
            "emergency_contact_number",
            "emergency_contact_relationship",
            "previous_school",
            "transfer_certificate_number",
            "status",
            "is_active",
            "full_name",
            "age",
            "attendance_percentage",
            "siblings",
            "parents",
            "date_joined",
            "last_updated",
        ]
        read_only_fields = ["id", "registration_number", "date_joined", "last_updated"]

    def get_attendance_percentage(self, obj):
        try:
            return obj.get_attendance_percentage()
        except:
            return 0

    def get_siblings(self, obj):
        siblings = obj.get_siblings()
        return StudentListSerializer(siblings, many=True).data

    def get_parents(self, obj):
        relations = obj.student_parent_relations.select_related("parent__user")
        return [
            {
                "id": str(relation.parent.id),
                "name": relation.parent.get_full_name(),
                "relation": relation.parent.relation_with_student,
                "is_primary": relation.is_primary_contact,
                "phone": relation.parent.user.phone_number,
                "email": relation.parent.user.email,
            }
            for relation in relations
        ]

    def validate_admission_number(self, value):
        instance = getattr(self, "instance", None)
        if instance and instance.pk:
            if (
                Student.objects.filter(admission_number=value)
                .exclude(pk=instance.pk)
                .exists()
            ):
                raise AdmissionNumberExistsError("Admission number already exists")
        elif Student.objects.filter(admission_number=value).exists():
            raise AdmissionNumberExistsError("Admission number already exists")
        return value

    def validate(self, attrs):
        # Custom validation using validators
        errors = validate_student_data(attrs, {})
        if errors:
            raise serializers.ValidationError({"validation_errors": errors})

        return attrs

    @transaction.atomic
    def create(self, validated_data):
        # Create student directly with all fields
        student = Student.objects.create(**validated_data)
        return student

    @transaction.atomic
    def update(self, instance, validated_data):
        # Update student fields directly
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        return instance


class ParentListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for parent lists"""

    full_name = serializers.CharField(source="get_full_name", read_only=True)
    student_count = serializers.SerializerMethodField()

    class Meta:
        model = Parent
        fields = [
            "id",
            "full_name",
            "relation_with_student",
            "occupation",
            "emergency_contact",
            "student_count",
        ]

    def get_student_count(self, obj):
        return obj.parent_student_relations.count()


class ParentDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for parent CRUD operations"""

    user = UserSerializer()
    full_name = serializers.CharField(source="get_full_name", read_only=True)
    students = serializers.SerializerMethodField()

    class Meta:
        model = Parent
        fields = [
            "id",
            "user",
            "occupation",
            "annual_income",
            "education",
            "relation_with_student",
            "workplace",
            "work_address",
            "work_phone",
            "emergency_contact",
            "photo",
            "full_name",
            "students",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_students(self, obj):
        relations = obj.parent_student_relations.select_related("student")
        return [
            {
                "id": str(relation.student.id),
                "name": relation.student.full_name,
                "admission_number": relation.student.admission_number,
                "class": (
                    str(relation.student.current_class)
                    if relation.student.current_class
                    else None
                ),
                "is_primary": relation.is_primary_contact,
            }
            for relation in relations
        ]

    def validate(self, attrs):
        # Custom validation using validators
        user_data = attrs.get("user", {})
        parent_data = {k: v for k, v in attrs.items() if k != "user"}

        errors = validate_parent_data(parent_data, user_data)
        if errors:
            raise serializers.ValidationError({"validation_errors": errors})

        return attrs

    @transaction.atomic
    def create(self, validated_data):
        user_data = validated_data.pop("user")

        # Create user
        user = User.objects.create(**user_data)
        user.set_password(User.objects.make_random_password())
        user.save()

        # Create parent
        parent = Parent.objects.create(user=user, **validated_data)

        # Assign parent role
        from src.accounts.services import RoleService

        RoleService.assign_role_to_user(user, "Parent")

        return parent

    @transaction.atomic
    def update(self, instance, validated_data):
        user_data = validated_data.pop("user", {})

        # Update user
        for attr, value in user_data.items():
            setattr(instance.user, attr, value)
        instance.user.save()

        # Update parent
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        return instance


class StudentParentRelationSerializer(serializers.ModelSerializer):
    """Serializer for student-parent relationships"""

    student_name = serializers.CharField(source="student.get_full_name", read_only=True)
    parent_name = serializers.CharField(source="parent.get_full_name", read_only=True)
    parent_relation = serializers.CharField(
        source="parent.relation_with_student", read_only=True
    )

    class Meta:
        model = StudentParentRelation
        fields = [
            "id",
            "student",
            "parent",
            "student_name",
            "parent_name",
            "parent_relation",
            "is_primary_contact",
            "can_pickup",
            "emergency_contact_priority",
            "financial_responsibility",
            "access_to_grades",
            "access_to_attendance",
            "access_to_financial_info",
            "receive_sms",
            "receive_email",
            "receive_push_notifications",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate(self, attrs):
        student = attrs.get("student")
        parent = attrs.get("parent")

        # Check if relationship already exists
        if self.instance is None:  # Creating new relationship
            if StudentParentRelation.objects.filter(
                student=student, parent=parent
            ).exists():
                raise RelationshipExistsError("Relationship already exists")

        return attrs


class BulkImportResultSerializer(serializers.Serializer):
    """Serializer for bulk import results"""

    success = serializers.BooleanField()
    created = serializers.IntegerField()
    updated = serializers.IntegerField()
    errors = serializers.IntegerField()
    error_details = serializers.ListField(child=serializers.DictField(), required=False)
    total_processed = serializers.IntegerField()


class StudentAnalyticsSerializer(serializers.Serializer):
    """Serializer for student analytics data"""

    total_students = serializers.IntegerField()
    active_students = serializers.IntegerField()
    status_breakdown = serializers.DictField()
    class_breakdown = serializers.DictField()
    blood_group_breakdown = serializers.DictField()
    age_statistics = serializers.DictField()
    attendance_summary = serializers.DictField()
    geographic_distribution = serializers.DictField()


class SearchResultSerializer(serializers.Serializer):
    """Serializer for search results"""

    results = StudentListSerializer(many=True)
    total_count = serializers.IntegerField()
    page_count = serializers.IntegerField()
    current_page = serializers.IntegerField()
    analytics = StudentAnalyticsSerializer(required=False)


class AutocompleteSerializer(serializers.Serializer):
    """Serializer for autocomplete results"""

    id = serializers.CharField()
    text = serializers.CharField()
    category = serializers.CharField(required=False)
    additional_info = serializers.DictField(required=False)
