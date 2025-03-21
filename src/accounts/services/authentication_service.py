from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db import transaction
from rest_framework_simplejwt.tokens import RefreshToken

User = get_user_model()


class AuthenticationService:
    """
    Service for handling authentication-related operations.
    """

    @staticmethod
    def generate_tokens_for_user(user):
        """Generate JWT tokens for a user."""
        refresh = RefreshToken.for_user(user)

        return {
            "refresh": str(refresh),
            "access": str(refresh.access_token),
        }

    @staticmethod
    def update_last_login(user):
        """Update the last login timestamp for a user."""
        user.last_login = timezone.now()
        user.save(update_fields=["last_login"])

    @staticmethod
    def authenticate_user(username, password):
        """
        Authenticate a user with username and password.
        Returns user object if authentication is successful, None otherwise.
        """
        try:
            user = User.objects.get(username=username)
            if user.check_password(password):
                if user.is_active:
                    AuthenticationService.update_last_login(user)
                    return user
            return None
        except User.DoesNotExist:
            return None

    @staticmethod
    @transaction.atomic
    def register_user(user_data, role_names=None):
        """
        Register a new user with optional roles.

        Args:
            user_data (dict): User data including username, email, password, etc.
            role_names (list): List of role names to assign to the user

        Returns:
            User: The created user instance
        """
        from ..models import UserRole, UserRoleAssignment

        # Create the user
        password = user_data.pop("password")
        user = User.objects.create(**user_data)
        user.set_password(password)
        user.save()

        # Assign roles if provided
        if role_names:
            roles = UserRole.objects.filter(name__in=role_names)
            for role in roles:
                UserRoleAssignment.objects.create(user=user, role=role)

        return user
