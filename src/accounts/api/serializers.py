# src/accounts/api/serializers.py

from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from ..models import UserAuditLog, UserProfile, UserRole, UserRoleAssignment
from ..utils import validate_password_strength

User = get_user_model()


class UserProfileSerializer(serializers.ModelSerializer):
    """Serializer for user profile."""

    class Meta:
        model = UserProfile
        fields = [
            "bio",
            "website",
            "location",
            "language",
            "timezone",
            "email_notifications",
            "sms_notifications",
            "linkedin_url",
            "twitter_url",
            "facebook_url",
        ]


class UserRoleSerializer(serializers.ModelSerializer):
    """Serializer for user roles."""

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
        read_only_fields = ["created_at", "updated_at", "is_system_role"]

    def get_permission_count(self, obj):
        return obj.get_permission_count()

    def validate_permissions(self, value):
        """Validate permissions structure."""
        from ..services import RoleService

        is_valid, message = RoleService.validate_permissions(value)
        if not is_valid:
            raise serializers.ValidationError(message)
        return value


class UserRoleAssignmentSerializer(serializers.ModelSerializer):
    """Serializer for user role assignments."""

    role_name = serializers.CharField(source="role.name", read_only=True)
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
            "assigned_date",
            "assigned_by",
            "assigned_by_name",
            "expires_at",
            "is_active",
            "notes",
            "is_expired",
            "days_until_expiry",
        ]
        read_only_fields = ["assigned_date", "assigned_by"]

    def get_is_expired(self, obj):
        return obj.is_expired()

    def get_days_until_expiry(self, obj):
        return obj.days_until_expiry()


class UserListSerializer(serializers.ModelSerializer):
    """Serializer for user list view."""

    full_name = serializers.CharField(source="get_full_name", read_only=True)
    initials = serializers.CharField(source="get_initials", read_only=True)
    age = serializers.IntegerField(source="get_age", read_only=True)
    roles = serializers.StringRelatedField(
        source="get_assigned_roles", many=True, read_only=True
    )
    is_account_locked = serializers.BooleanField(
        source="is_account_locked", read_only=True
    )

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
            "is_active",
            "is_staff",
            "date_joined",
            "last_login",
            "age",
            "roles",
            "failed_login_attempts",
            "requires_password_change",
            "is_account_locked",
        ]


class UserDetailSerializer(serializers.ModelSerializer):
    """Serializer for detailed user view."""

    full_name = serializers.CharField(source="get_full_name", read_only=True)
    initials = serializers.CharField(source="get_initials", read_only=True)
    age = serializers.IntegerField(source="get_age", read_only=True)
    profile = UserProfileSerializer(read_only=True)
    role_assignments = UserRoleAssignmentSerializer(many=True, read_only=True)
    is_account_locked = serializers.BooleanField(
        source="is_account_locked", read_only=True
    )

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
            "gender",
            "profile_picture",
            "is_active",
            "is_staff",
            "date_joined",
            "last_login",
            "age",
            "profile",
            "role_assignments",
            "failed_login_attempts",
            "requires_password_change",
            "password_changed_at",
            "is_account_locked",
        ]
        read_only_fields = [
            "date_joined",
            "last_login",
            "failed_login_attempts",
            "password_changed_at",
        ]


class UserCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating users."""

    password = serializers.CharField(write_only=True, required=False)
    password_confirm = serializers.CharField(write_only=True, required=False)
    roles = serializers.ListField(
        child=serializers.CharField(), write_only=True, required=False
    )
    profile = UserProfileSerializer(required=False)

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
            "is_active",
            "password",
            "password_confirm",
            "roles",
            "profile",
        ]

    def validate(self, attrs):
        """Validate password and confirmation."""
        password = attrs.get("password")
        password_confirm = attrs.get("password_confirm")

        if password or password_confirm:
            if password != password_confirm:
                raise serializers.ValidationError(
                    {"password_confirm": _("Passwords do not match.")}
                )

            if password:
                # Validate password strength
                validation = validate_password_strength(password)
                if not validation["is_valid"]:
                    raise serializers.ValidationError(
                        {"password": validation["feedback"]}
                    )

        return attrs

    def create(self, validated_data):
        """Create user with roles and profile."""
        roles = validated_data.pop("roles", [])
        profile_data = validated_data.pop("profile", {})
        password = validated_data.pop("password", None)
        validated_data.pop("password_confirm", None)

        from ..services import AuthenticationService

        if password:
            validated_data["password"] = password

        user = AuthenticationService.register_user(
            validated_data,
            role_names=roles,
            created_by=self.context["request"].user,
            send_email=True,
        )

        # Create profile if provided
        if profile_data:
            UserProfile.objects.create(user=user, **profile_data)

        return user


class UserUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating users."""

    profile = UserProfileSerializer(required=False)
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
            "profile",
            "roles",
        ]

    def update(self, instance, validated_data):
        """Update user with profile and roles."""
        profile_data = validated_data.pop("profile", {})
        roles = validated_data.pop("roles", None)

        # Update user fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # Update or create profile
        if profile_data:
            profile, created = UserProfile.objects.get_or_create(user=instance)
            for attr, value in profile_data.items():
                setattr(profile, attr, value)
            profile.save()

        # Update roles if provided and user has permission
        request = self.context.get("request")
        if (
            roles is not None
            and request
            and request.user.has_permission("roles", "change")
        ):
            from ..services import RoleService

            # Deactivate current roles
            instance.role_assignments.update(is_active=False)

            # Assign new roles
            for role_name in roles:
                try:
                    RoleService.assign_role_to_user(
                        instance, role_name, assigned_by=request.user
                    )
                except ValueError:
                    pass

        return instance


class PasswordChangeSerializer(serializers.Serializer):
    """Serializer for password change."""

    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True)
    new_password_confirm = serializers.CharField(required=True)

    def validate(self, attrs):
        """Validate passwords."""
        user = self.context["request"].user
        old_password = attrs.get("old_password")
        new_password = attrs.get("new_password")
        new_password_confirm = attrs.get("new_password_confirm")

        # Check old password
        if not user.check_password(old_password):
            raise serializers.ValidationError(
                {"old_password": _("Current password is incorrect.")}
            )

        # Check new password confirmation
        if new_password != new_password_confirm:
            raise serializers.ValidationError(
                {"new_password_confirm": _("New passwords do not match.")}
            )

        # Validate new password strength
        validation = validate_password_strength(new_password)
        if not validation["is_valid"]:
            raise serializers.ValidationError({"new_password": validation["feedback"]})

        return attrs

    def save(self):
        """Change user password."""
        from ..services import AuthenticationService

        user = self.context["request"].user
        new_password = self.validated_data["new_password"]
        old_password = self.validated_data["old_password"]

        success, message = AuthenticationService.change_password(
            user, old_password, new_password, self.context.get("request")
        )

        if not success:
            raise serializers.ValidationError({"non_field_errors": [message]})

        return user


class PasswordResetSerializer(serializers.Serializer):
    """Serializer for password reset."""

    new_password = serializers.CharField(required=False)

    def validate_new_password(self, value):
        """Validate new password strength."""
        if value:
            validation = validate_password_strength(value)
            if not validation["is_valid"]:
                raise serializers.ValidationError(validation["feedback"])
        return value

    def save(self, user):
        """Reset user password."""
        from ..services import AuthenticationService

        new_password = self.validated_data.get("new_password")
        request = self.context.get("request")
        reset_by = request.user if request and request.user.is_authenticated else None

        return AuthenticationService.reset_password(
            user, new_password, request, reset_by
        )


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Custom JWT token serializer with additional user info."""

    def validate(self, attrs):
        """Validate credentials and add user info."""
        from ..services import AuthenticationService

        username = attrs.get("username")
        password = attrs.get("password")
        request = self.context.get("request")

        user, result = AuthenticationService.authenticate_user(
            username, password, request
        )

        if not user:
            error_messages = {
                "account_locked": _(
                    "Account is locked due to multiple failed login attempts."
                ),
                "account_inactive": _("Account is inactive."),
                "invalid_credentials": _("Invalid username or password."),
                "user_not_found": _("Invalid username or password."),
            }
            raise serializers.ValidationError(
                {
                    "non_field_errors": [
                        error_messages.get(result, _("Authentication failed."))
                    ]
                }
            )

        # Generate tokens
        data = AuthenticationService.generate_tokens_for_user(user)

        # Add user info
        data["user"] = {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "full_name": user.get_full_name(),
            "roles": [role.name for role in user.get_assigned_roles()],
            "is_admin": user.is_admin(),
            "requires_password_change": user.requires_password_change,
        }

        return data


class UserAuditLogSerializer(serializers.ModelSerializer):
    """Serializer for user audit logs."""

    user_name = serializers.CharField(source="user.username", read_only=True)
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
        read_only_fields = ["timestamp"]


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
        ]
    )
    roles = serializers.ListField(child=serializers.CharField(), required=False)

    def validate(self, attrs):
        """Validate bulk action parameters."""
        action = attrs.get("action")
        roles = attrs.get("roles", [])

        if action in ["assign_roles", "remove_roles"] and not roles:
            raise serializers.ValidationError(
                {"roles": _("Roles are required for role-based actions.")}
            )

        # Validate that users exist
        user_ids = attrs.get("user_ids", [])
        existing_users = User.objects.filter(id__in=user_ids).count()
        if existing_users != len(user_ids):
            raise serializers.ValidationError(
                {"user_ids": _("Some users do not exist.")}
            )

        return attrs
