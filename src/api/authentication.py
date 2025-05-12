from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.authentication import SessionAuthentication
from src.accounts.services.authentication_service import AuthenticationService


class CustomJWTAuthentication(JWTAuthentication):
    """Custom JWT authentication that updates last login time."""

    def authenticate(self, request):
        auth_tuple = super().authenticate(request)
        if auth_tuple:
            user, token = auth_tuple
            # Update last login timestamp
            AuthenticationService.update_last_login(user)
            return auth_tuple
        return None


class DefaultAuthentication:
    """Default authentication classes to use for API views."""

    authentication_classes = [CustomJWTAuthentication, SessionAuthentication]
