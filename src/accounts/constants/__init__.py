# src/accounts/constants/__init__.py

from .choices import *
from .permissions import *

# Explicit imports to avoid issues
from .permissions import (
    DEFAULT_ROLES,
    PERMISSION_SCOPES,
    DEFAULT_ADMIN_PERMISSIONS,
    DEFAULT_TEACHER_PERMISSIONS,
    DEFAULT_PARENT_PERMISSIONS,
    DEFAULT_STUDENT_PERMISSIONS,
    SYSTEM_ROLE_NAMES,
    ROLE_HIERARCHY,
    DEFAULT_ROLE_MAPPINGS,
)

from .choices import (
    GENDER_CHOICES,
    ACCOUNT_STATUS_CHOICES,
    USER_STATUS,
)

__all__ = [
    # From choices
    "GENDER_CHOICES",
    "ACCOUNT_STATUS_CHOICES",
    # From permissions
    "PERMISSION_SCOPES",
    "DEFAULT_ADMIN_PERMISSIONS",
    "DEFAULT_TEACHER_PERMISSIONS",
    "DEFAULT_PARENT_PERMISSIONS",
    "DEFAULT_STUDENT_PERMISSIONS",
    "DEFAULT_ROLES",
    "SYSTEM_ROLE_NAMES",
    "ROLE_HIERARCHY",
    "DEFAULT_ROLE_MAPPINGS",
]
