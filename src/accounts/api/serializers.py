# src/accounts/api/serializers.py

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from ..models import User, UserRole, UserRoleAssignment, UserProfile, UserAuditLog
from ..services import AuthenticationService, RoleService
from ..utils import validate_password_strength

User = get_user_model()


class UserRoleSerializer(serializers.ModelSerializer):
    """Serializer for UserRole model."""

    user_count = serializers.IntegerField(read_only=True)
    permission_count = serializers.SerializerMethodField()

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
            "user_count",
            "permission_count",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "is_system_role"]

    def get_permission_count(self, obj):
        """Get total number of permissions in this role."""
        return obj.get_permission_count()

    def validate_name(self, value):
        """Validate role name."""
        if self.instance and self.instance.is_system_role:
            if value != self.instance.name:
                raise serializers.ValidationError(
                    "Cannot change the name of a system role."
                )
        return value

    def validate_permissions(self, value):
        """Validate permissions structure."""
        is_valid, message = RoleService.validate_permissions(value)
        if not is_valid:
            raise serializers.ValidationError(message)
        return value


class UserRoleAssignmentSerializer(serializers.ModelSerializer):
    """Serializer for UserRoleAssignment model."""

    role_name = serializers.CharField(source="role.name", read_only=True)
    role_description = serializers.CharField(source="role.description", read_only=True)
    assigned_by_name = serializers.CharField(
        source="assigned_by.get_full_name", read_only=True
    )
    is_expired = serializers.SerializerMethodField()
    days_until_expiry = serializers.SerializerMethodField()

    class Meta:
        model = UserRoleAssignment
        fields = [
            "id",
            "role",
            "role_name",
            "role_description",
            "assigned_date",
            "assigned_by",
            "assigned_by_name",
            "expires_at",
            "is_active",
            "notes",
            "is_expired",
            "days_until_expiry",
        ]
        read_only_fields = ["id", "assigned_date", "assigned_by"]

    def get_is_expired(self, obj):
        """Check if assignment is expired."""
        return obj.is_expired()

    def get_days_until_expiry(self, obj):
        """Get days until expiry."""
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


class UserListSerializer(serializers.ModelSerializer):
    """Serializer for User list view."""

    full_name = serializers.CharField(source="get_full_name", read_only=True)
    initials = serializers.CharField(source="get_initials", read_only=True)
    age = serializers.IntegerField(source="get_age", read_only=True)
    roles = serializers.SerializerMethodField()
    is_locked = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "full_name",
            "initials",
            "phone_number",
            "age",
            "gender",
            "is_active",
            "is_staff",
            "date_joined",
            "last_login",
            "roles",
            "is_locked",
            "requires_password_change",
        ]

    def get_roles(self, obj):
        """Get user roles."""
        return [assignment.role.name for assignment in obj.active_role_assignments]

    def get_is_locked(self, obj):
        """Check if account is locked."""
        return obj.is_account_locked()


class UserDetailSerializer(serializers.ModelSerializer):
    """Serializer for User detail view."""

    full_name = serializers.CharField(source="get_full_name", read_only=True)
    initials = serializers.CharField(source="get_initials", read_only=True)
    age = serializers.IntegerField(source="get_age", read_only=True)
    profile = UserProfileSerializer(read_only=True)
    role_assignments = UserRoleAssignmentSerializer(many=True, read_only=True)
    permissions = serializers.SerializerMethodField()
    is_locked = serializers.SerializerMethodField()
    login_statistics = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "full_name",
            "initials",
            "phone_number",
            "address",
            "date_of_birth",
            "age",
            "gender",
            "profile_picture",
            "is_active",
            "is_staff",
            "date_joined",
            "last_login",
            "password_changed_at",
            "requires_password_change",
            "failed_login_attempts",
            "profile",
            "role_assignments",
            "permissions",
            "is_locked",
            "login_statistics",
        ]
        read_only_fields = [
            "id",
            "date_joined",
            "last_login",
            "password_changed_at",
            "failed_login_attempts",
        ]

    def get_permissions(self, obj):
        """Get user permissions."""
        return RoleService.get_user_permissions(obj)

    def get_is_locked(self, obj):
        """Check if account is locked."""
        return obj.is_account_locked()

    def get_login_statistics(self, obj):
        """Get login statistics."""
        return AuthenticationService.get_login_statistics(obj)


class UserCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating users."""

    password = serializers.CharField(write_only=True, required=False)
    password_confirm = serializers.CharField(write_only=True, required=False)
    roles = serializers.ListField(
        child=serializers.CharField(), write_only=True, required=False
    )
    send_welcome_email = serializers.BooleanField(default=True, write_only=True)

    class Meta:
        model = User
        fields = [
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
            "roles",
            "send_welcome_email",
        ]

    def validate_email(self, value):
        """Validate email uniqueness."""
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("This email is already in use.")
        return value

    def validate_username(self, value):
        """Validate username."""
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("This username is already taken.")
        if len(value) < 3:
            raise serializers.ValidationError(
                "Username must be at least 3 characters long."
            )
        return value

    def validate_phone_number(self, value):
        """Validate phone number uniqueness."""
        if value and User.objects.filter(phone_number=value).exists():
            raise serializers.ValidationError("This phone number is already in use.")
        return value

    def validate(self, attrs):
        """Validate password confirmation."""
        password = attrs.get("password")
        password_confirm = attrs.get("password_confirm")

        if password and password_confirm:
            if password != password_confirm:
                raise serializers.ValidationError("Passwords do not match.")

            # Validate password strength
            validation = validate_password_strength(password)
            if not validation["is_valid"]:
                raise serializers.ValidationError({"password": validation["feedback"]})

        return attrs

    def create(self, validated_data):
        """Create user with roles."""
        roles = validated_data.pop("roles", [])
        send_email = validated_data.pop("send_welcome_email", True)
        validated_data.pop("password_confirm", None)

        # Create user using AuthenticationService
        user = AuthenticationService.register_user(
            validated_data,
            role_names=roles,
            created_by=self.context["request"].user,
            send_email=send_email,
        )

        return user


class UserUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating users."""

    roles = serializers.ListField(
        child=serializers.CharField(), write_only=True, required=False
    )

    class Meta:
        model = User
        fields = [
            "first_name",
            "last_name",
            "email",
            "phone_number",
            "address",
            "date_of_birth",
            "gender",
            "profile_picture",
            "is_active",
            "requires_password_change",
            "roles",
        ]

    def validate_email(self, value):
        """Validate email uniqueness."""
        if User.objects.filter(email=value).exclude(pk=self.instance.pk).exists():
            raise serializers.ValidationError("This email is already in use.")
        return value

    def validate_phone_number(self, value):
        """Validate phone number uniqueness."""
        if (
            value
            and User.objects.filter(phone_number=value)
            .exclude(pk=self.instance.pk)
            .exists()
        ):
            raise serializers.ValidationError("This phone number is already in use.")
        return value

    def update(self, instance, validated_data):
        """Update user and roles."""
        roles = validated_data.pop("roles", None)

        # Update user fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # Update roles if provided and user has permission
        if roles is not None:
            request_user = self.context["request"].user
            if RoleService.check_permission(request_user, "roles", "change"):
                # Deactivate current roles
                instance.role_assignments.update(is_active=False)

                # Assign new roles
                for role_name in roles:
                    try:
                        RoleService.assign_role_to_user(
                            instance, role_name, assigned_by=request_user
                        )
                    except ValueError:
                        pass  # Skip invalid roles

        return instance


class PasswordChangeSerializer(serializers.Serializer):
    """Serializer for password change."""

    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)
    new_password_confirm = serializers.CharField(write_only=True)

    def validate(self, attrs):
        """Validate passwords."""
        old_password = attrs.get("old_password")
        new_password = attrs.get("new_password")
        new_password_confirm = attrs.get("new_password_confirm")

        # Check if new passwords match
        if new_password != new_password_confirm:
            raise serializers.ValidationError("New passwords do not match.")

        # Validate password strength
        validation = validate_password_strength(new_password)
        if not validation["is_valid"]:
            raise serializers.ValidationError({"new_password": validation["feedback"]})

        # Check old password
        user = self.context["request"].user
        if not user.check_password(old_password):
            raise serializers.ValidationError(
                {"old_password": "Current password is incorrect."}
            )

        return attrs

    def save(self):
        """Change password."""
        user = self.context["request"].user
        new_password = self.validated_data["new_password"]
        request = self.context["request"]

        success, message = AuthenticationService.change_password(
            user, self.validated_data["old_password"], new_password, request
        )

        if not success:
            raise serializers.ValidationError(message)

        return user


class PasswordResetSerializer(serializers.Serializer):
    """Serializer for password reset by admin."""

    new_password = serializers.CharField(write_only=True, required=False)
    generate_password = serializers.BooleanField(default=True, write_only=True)

    def validate(self, attrs):
        """Validate password if provided."""
        new_password = attrs.get("new_password")
        generate_password = attrs.get("generate_password", True)

        if not generate_password and not new_password:
            raise serializers.ValidationError(
                "Either provide a new password or enable password generation."
            )

        if new_password:
            validation = validate_password_strength(new_password)
            if not validation["is_valid"]:
                raise serializers.ValidationError(
                    {"new_password": validation["feedback"]}
                )

        return attrs

    def save(self, user):
        """Reset password."""
        new_password = self.validated_data.get("new_password")
        request = self.context.get("request")
        reset_by = request.user if request else None

        return AuthenticationService.reset_password(
            user, new_password, request, reset_by
        )


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Custom token serializer that supports email/phone login."""

    username_field = "identifier"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["identifier"] = serializers.CharField()
        del self.fields["username"]

    def validate(self, attrs):
        """Validate credentials using email, phone, or username."""
        identifier = attrs.get("identifier")
        password = attrs.get("password")

        if identifier and password:
            # Use our custom authentication service
            user, result = AuthenticationService.authenticate_user(
                identifier, password, self.context.get("request")
            )

            if result == "success" and user:
                # Generate tokens
                refresh = self.get_token(user)
                data = {
                    "refresh": str(refresh),
                    "access": str(refresh.access_token),
                    "user": UserDetailSerializer(user).data,
                }

                return data
            else:
                # Handle different authentication results
                error_messages = {
                    "user_not_found": "No account found with this identifier.",
                    "account_locked": "Account is locked due to multiple failed attempts.",
                    "account_inactive": "Account is inactive.",
                    "invalid_credentials": "Invalid credentials.",
                }

                raise serializers.ValidationError(
                    error_messages.get(result, "Authentication failed.")
                )

        raise serializers.ValidationError("Must include identifier and password.")


class UserAuditLogSerializer(serializers.ModelSerializer):
    """Serializer for UserAuditLog model."""

    user_name = serializers.CharField(source="user.get_full_name", read_only=True)
    performed_by_name = serializers.CharField(
        source="performed_by.get_full_name", read_only=True
    )
    action_display = serializers.CharField(source="get_action_display", read_only=True)

    class Meta:
        model = UserAuditLog
        fields = [
            "id",
            "user",
            "user_name",
            "action",
            "action_display",
            "description",
            "ip_address",
            "user_agent",
            "performed_by",
            "performed_by_name",
            "timestamp",
            "extra_data",
        ]


class BulkUserActionSerializer(serializers.Serializer):
    """Serializer for bulk user actions."""

    user_ids = serializers.ListField(child=serializers.IntegerField(), min_length=1)
    action = serializers.ChoiceField(
        choices=[
            ("activate", "Activate"),
            ("deactivate", "Deactivate"),
            ("require_password_change", "Require Password Change"),
            ("assign_roles", "Assign Roles"),
            ("remove_roles", "Remove Roles"),
            ("unlock_accounts", "Unlock Accounts"),
        ]
    )
    roles = serializers.ListField(child=serializers.CharField(), required=False)

    def validate(self, attrs):
        """Validate bulk action data."""
        action = attrs.get("action")
        roles = attrs.get("roles", [])

        if action in ["assign_roles", "remove_roles"] and not roles:
            raise serializers.ValidationError(
                f"Roles must be provided for action '{action}'"
            )

        # Validate that roles exist
        if roles:
            existing_roles = UserRole.objects.filter(name__in=roles).values_list(
                "name", flat=True
            )
            invalid_roles = set(roles) - set(existing_roles)
            if invalid_roles:
                raise serializers.ValidationError(
                    f"Invalid roles: {', '.join(invalid_roles)}"
                )

        return attrs


class UserStatsSerializer(serializers.Serializer):
    """Serializer for user statistics."""

    total_users = serializers.IntegerField()
    active_users = serializers.IntegerField()
    inactive_users = serializers.IntegerField()
    locked_users = serializers.IntegerField()
    recent_registrations = serializers.IntegerField()
    users_requiring_password_change = serializers.IntegerField()
    role_distribution = serializers.DictField()
    login_statistics = serializers.DictField()


class OTPSerializer(serializers.Serializer):
    """Serializer for OTP operations."""

    otp = serializers.CharField(max_length=6, min_length=6)
    purpose = serializers.CharField(default="verification")

    def validate_otp(self, value):
        """Validate OTP format."""
        if not value.isdigit():
            raise serializers.ValidationError("OTP must contain only digits.")
        return value
