import logging
from typing import Optional, Tuple
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from .services import AuthenticationService

logger = logging.getLogger(__name__)
User = get_user_model()


class UnifiedAuthenticationBackend(ModelBackend):
    """
    Unified authentication backend supporting email, phone, username, and admission number.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        """
        Authenticate user using identifier and password.
        """
        if not username or not password:
            return None

        try:
            # Use the AuthenticationService to find and authenticate the user
            user, result = AuthenticationService.authenticate_user(
                username, password, request
            )

            if result == "success" and user:
                return user
            else:
                logger.debug(f"Authentication failed: {result}")
                return None

        except Exception as e:
            logger.error(f"Authentication error: {str(e)}")
            return None

    def get_user(self, user_id):
        """Get user by ID."""
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
