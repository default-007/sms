# src/api/throttling.py
"""API Rate Limiting and Throttling"""

import time

from django.conf import settings
from django.core.cache import cache
from rest_framework.throttling import (
    AnonRateThrottle,
    ScopedRateThrottle,
    UserRateThrottle,
)


class CustomUserRateThrottle(UserRateThrottle):
    """Enhanced user-based rate limiting"""

    scope = "user"

    def get_cache_key(self, request, view):
        """Custom cache key with user role consideration"""
        if request.user.is_authenticated:
            ident = request.user.pk
            # Different rates for different user types
            user_type = getattr(request.user, "user_type", "standard")
            return self.cache_format % {
                "scope": f"{self.scope}_{user_type}",
                "ident": ident,
            }
        return None

    def allow_request(self, request, view):
        """Enhanced allow request with role-based rates"""
        # Admin users get higher rate limits
        if request.user.is_authenticated and request.user.is_admin:
            self.rate = getattr(settings, "ADMIN_THROTTLE_RATE", "1000/hour")
        elif request.user.is_authenticated and request.user.is_teacher:
            self.rate = getattr(settings, "TEACHER_THROTTLE_RATE", "500/hour")
        elif request.user.is_authenticated:
            self.rate = getattr(settings, "USER_THROTTLE_RATE", "200/hour")

        return super().allow_request(request, view)


class CustomAnonRateThrottle(AnonRateThrottle):
    """Enhanced anonymous user rate limiting"""

    scope = "anon"

    def get_cache_key(self, request, view):
        """Custom cache key for anonymous users"""
        return self.cache_format % {
            "scope": self.scope,
            "ident": self.get_ident(request),
        }


class LoginRateThrottle(UserRateThrottle):
    """Specific throttling for login attempts"""

    scope = "login"

    def get_cache_key(self, request, view):
        """Cache key based on IP for login attempts"""
        ident = self.get_ident(request)
        return self.cache_format % {"scope": self.scope, "ident": ident}


class APIKeyRateThrottle(UserRateThrottle):
    """Rate limiting for API key usage"""

    scope = "api_key"

    def get_cache_key(self, request, view):
        """Cache key based on API key"""
        api_key = request.META.get("HTTP_X_API_KEY")
        if api_key:
            return self.cache_format % {"scope": self.scope, "ident": api_key}
        return None


class BurstRateThrottle(UserRateThrottle):
    """Burst protection for rapid requests"""

    scope = "burst"
    rate = "60/min"

    def get_cache_key(self, request, view):
        """Cache key for burst protection"""
        if request.user.is_authenticated:
            ident = request.user.pk
        else:
            ident = self.get_ident(request)

        return self.cache_format % {"scope": self.scope, "ident": ident}


class OperationThrottle(ScopedRateThrottle):
    """Throttling for specific operations"""

    def get_cache_key(self, request, view):
        """Cache key based on operation type"""
        scope = getattr(view, "throttle_scope", self.scope)
        if request.user.is_authenticated:
            ident = request.user.pk
        else:
            ident = self.get_ident(request)

        return self.cache_format % {"scope": scope, "ident": ident}
