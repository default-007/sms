from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.utils.translation import gettext_lazy as _

from src.accounts.models import UserRole, UserRoleAssignment

User = get_user_model()


# User serializers
class UserRoleSerializer(serializers.ModelSerializer):
    """Serializer for the UserRole model."""

    class Meta:
        model = UserRole
        fields = ["id", "name", "description", "permissions"]


class UserRoleAssignmentSerializer(serializers.ModelSerializer):
    """Serializer for the UserRoleAssignment model."""

    role_name = serializers.ReadOnlyField(source="role.name")

    class Meta:
        model = UserRoleAssignment
        fields = ["id", "role", "role_name", "assigned_date", "assigned_by"]
        read_only_fields = ["assigned_date", "assigned_by"]


class UserSerializer(serializers.ModelSerializer):
    """Serializer for the User model."""

    roles = UserRoleAssignmentSerializer(
        source="role_assignments", many=True, read_only=True
    )
    role_ids = serializers.PrimaryKeyRelatedField(
        source="role_assignments",
        queryset=UserRole.objects.all(),
        many=True,
        required=False,
        write_only=True,
    )

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
            "roles",
            "role_ids",
        ]
        read_only_fields = ["date_joined", "last_login"]
        extra_kwargs = {"password": {"write_only": True}}

    def create(self, validated_data):
        """Handle role assignments and create user."""
        role_ids = validated_data.pop("role_assignments", [])
        user = User.objects.create_user(**validated_data)

        # Assign roles
        for role in role_ids:
            UserRoleAssignment.objects.create(
                user=user,
                role=role,
                assigned_by=(
                    self.context["request"].user if "request" in self.context else None
                ),
            )

        return user

    def update(self, instance, validated_data):
        """Handle role assignments and update user."""
        role_ids = validated_data.pop("role_assignments", [])

        # Update user fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # Update roles if provided
        if role_ids:
            # Clear existing roles
            instance.role_assignments.all().delete()

            # Assign new roles
            for role in role_ids:
                UserRoleAssignment.objects.create(
                    user=instance,
                    role=role,
                    assigned_by=(
                        self.context["request"].user
                        if "request" in self.context
                        else None
                    ),
                )

        return instance


class UserCreateSerializer(UserSerializer):
    """Serializer for creating users with password."""

    password = serializers.CharField(
        write_only=True, required=True, validators=[validate_password]
    )
    password_confirm = serializers.CharField(write_only=True, required=True)

    class Meta(UserSerializer.Meta):
        fields = UserSerializer.Meta.fields + ["password", "password_confirm"]

    def validate(self, attrs):
        """Validate that the passwords match."""
        if attrs.get("password") != attrs.get("password_confirm"):
            raise serializers.ValidationError(
                {"password": _("Password fields didn't match.")}
            )
        return attrs

    def create(self, validated_data):
        """Create user with password."""
        validated_data.pop("password_confirm")
        return super().create(validated_data)


class ChangePasswordSerializer(serializers.Serializer):
    """Serializer for changing user password."""

    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, validators=[validate_password])
    confirm_password = serializers.CharField(required=True)

    def validate(self, attrs):
        """Validate old password and that new passwords match."""
        if attrs.get("new_password") != attrs.get("confirm_password"):
            raise serializers.ValidationError(
                {"new_password": _("Password fields didn't match.")}
            )
        return attrs

    def validate_old_password(self, value):
        """Validate that the old password is correct."""
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError(_("Old password is not correct"))
        return value


class UserLoginSerializer(serializers.Serializer):
    """Serializer for user login."""

    username = serializers.CharField(required=True)
    password = serializers.CharField(required=True, style={"input_type": "password"})
