from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.authentication import SessionAuthentication


class CustomJWTAuthentication(JWTAuthentication):
    """
    Custom JWT authentication class with additional features.
    """

    def authenticate(self, request):
        """
        Authenticate the request and return a two-tuple of (user, token).
        """
        result = super().authenticate(request)
        if result is not None:
            user, token = result
            # We could add additional checks or logging here
            return user, token
        return None


class CsrfExemptSessionAuthentication(SessionAuthentication):
    """
    Session authentication that skips CSRF validation.
    Only use in contexts where CSRF protection is handled elsewhere or not needed.
    """

    def enforce_csrf(self, request):
        """
        Do not enforce CSRF validation.
        """
        return
