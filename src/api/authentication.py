# src/api/authentication.py
"""Custom Authentication Classes"""

import logging
from datetime import datetime, timedelta

import jwt
import redis
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import BaseBackend
from django.utils import timezone
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import RefreshToken

User = get_user_model()
logger = logging.getLogger(__name__)


class CustomJWTAuthentication(JWTAuthentication):
    """Enhanced JWT Authentication with additional security features"""

    def authenticate(self, request):
        """Authenticate request with enhanced security checks"""
        header = self.get_header(request)
        if header is None:
            return None

        raw_token = self.get_raw_token(header)
        if raw_token is None:
            return None

        validated_token = self.get_validated_token(raw_token)
        user = self.get_user(validated_token)

        # Additional security checks
        if not self._is_token_valid(validated_token, user, request):
            raise AuthenticationFailed("Token is no longer valid")

        # Update last activity
        self._update_last_activity(user)

        return (user, validated_token)

    def _is_token_valid(self, token, user, request):
        """Additional token validation checks"""
        try:
            # Check if user is still active
            if not user.is_active:
                return False

            # Check token blacklist (Redis-based)
            token_id = token.get("jti")
            if token_id and self._is_token_blacklisted(token_id):
                return False

            # Check IP binding if enabled
            if getattr(settings, "JWT_BIND_TO_IP", False):
                token_ip = token.get("ip")
                current_ip = self._get_client_ip(request)
                if token_ip and token_ip != current_ip:
                    return False

            return True
        except Exception as e:
            logger.warning(f"Token validation error: {e}")
            return False

    def _is_token_blacklisted(self, token_id):
        """Check if token is blacklisted in Redis"""
        try:
            redis_client = redis.Redis.from_url(settings.REDIS_URL)
            return redis_client.exists(f"blacklist:{token_id}")
        except Exception:
            return False

    def _get_client_ip(self, request):
        """Get client IP address"""
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            ip = x_forwarded_for.split(",")[0]
        else:
            ip = request.META.get("REMOTE_ADDR")
        return ip

    def _update_last_activity(self, user):
        """Update user's last activity timestamp"""
        try:
            user.last_login = timezone.now()
            user.save(update_fields=["last_login"])
        except Exception as e:
            logger.warning(f"Failed to update last activity: {e}")


class SessionKeyAuthentication(BaseAuthentication):
    """Session-based authentication for web interface"""

    def authenticate(self, request):
        """Authenticate using Django session"""
        if not request.session.session_key:
            return None

        user = getattr(request, "user", None)
        if user and user.is_authenticated:
            return (user, None)

        return None


class APIKeyAuthentication(BaseAuthentication):
    """API Key authentication for external integrations"""

    def authenticate(self, request):
        """Authenticate using API key in header"""
        api_key = request.META.get("HTTP_X_API_KEY")
        if not api_key:
            return None

        try:
            # Validate API key format and get associated user
            user = self._validate_api_key(api_key)
            if user:
                return (user, api_key)
        except Exception as e:
            logger.warning(f"API key authentication failed: {e}")

        return None

    def _validate_api_key(self, api_key):
        """Validate API key and return associated user"""
        # Implementation depends on your API key storage strategy
        # This is a placeholder - implement based on your requirements
        try:
            from src.accounts.models import APIKey

            api_key_obj = APIKey.objects.select_related("user").get(
                key=api_key, is_active=True, expires_at__gt=timezone.now()
            )
            return api_key_obj.user
        except Exception:
            return None


class TokenManager:
    """Utility class for token management operations"""

    @staticmethod
    def blacklist_token(token):
        """Add token to blacklist"""
        try:
            token_id = token.get("jti")
            if token_id:
                redis_client = redis.Redis.from_url(settings.REDIS_URL)
                # Set expiry to token's remaining lifetime
                exp = token.get("exp", timezone.now().timestamp() + 3600)
                ttl = int(exp - timezone.now().timestamp())
                if ttl > 0:
                    redis_client.setex(f"blacklist:{token_id}", ttl, "1")
                return True
        except Exception as e:
            logger.error(f"Failed to blacklist token: {e}")
        return False

    @staticmethod
    def generate_enhanced_token(user, request=None):
        """Generate JWT token with enhanced claims"""
        refresh = RefreshToken.for_user(user)

        # Add custom claims
        refresh["user_type"] = user.get_user_type()
        refresh["permissions"] = user.get_all_permissions()

        if request and getattr(settings, "JWT_BIND_TO_IP", False):
            refresh["ip"] = CustomJWTAuthentication()._get_client_ip(request)

        return {
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "expires_in": settings.SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"].total_seconds(),
        }
