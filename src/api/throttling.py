from rest_framework.throttling import UserRateThrottle, AnonRateThrottle


class StandardUserRateThrottle(UserRateThrottle):
    """
    Throttle rate for standard authenticated users.
    """

    scope = "standard_user"
    rate = "60/minute"


class StandardAnonRateThrottle(AnonRateThrottle):
    """
    Throttle rate for anonymous users.
    """

    scope = "anon"
    rate = "20/minute"


class AdminUserRateThrottle(UserRateThrottle):
    """
    Throttle rate for admin users.
    """

    scope = "admin_user"
    rate = "120/minute"

    def get_cache_key(self, request, view):
        if request.user and (request.user.is_staff or request.user.has_role("Admin")):
            return self.cache_format % {
                "scope": self.scope,
                "ident": self.get_ident(request),
            }
        return None  # Allow non-admin users to be throttled by other throttle classes
