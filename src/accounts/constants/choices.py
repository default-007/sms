from django.utils.translation import gettext_lazy as _

# Gender choices
GENDER_CHOICES = (
    ("M", _("Male")),
    ("F", _("Female")),
    ("O", _("Other")),
)

# Default system roles
ADMIN_ROLE = "Admin"
TEACHER_ROLE = "Teacher"
PARENT_ROLE = "Parent"
STAFF_ROLE = "Staff"
STUDENT_ROLE = "Student"

SYSTEM_ROLES = [
    ADMIN_ROLE,
    TEACHER_ROLE,
    PARENT_ROLE,
    STAFF_ROLE,
    STUDENT_ROLE,
]

# Permission scopes
PERMISSION_SCOPES = {
    "users": ["view", "add", "change", "delete"],
    "roles": ["view", "add", "change", "delete"],
    "students": ["view", "add", "change", "delete"],
    "teachers": ["view", "add", "change", "delete"],
    "courses": ["view", "add", "change", "delete"],
    "classes": ["view", "add", "change", "delete"],
    "exams": ["view", "add", "change", "delete"],
    "grades": ["view", "add", "change", "delete"],
    "attendance": ["view", "add", "change", "delete"],
    "fees": ["view", "add", "change", "delete"],
    "library": ["view", "add", "change", "delete"],
    "transport": ["view", "add", "change", "delete"],
    "communications": ["view", "add", "change", "delete"],
    "reports": ["view", "generate"],
}

# Account status choices
ACCOUNT_STATUS_CHOICES = (
    ("active", _("Active")),
    ("inactive", _("Inactive")),
    ("pending", _("Pending")),
    ("suspended", _("Suspended")),
)
