from django.utils.translation import gettext_lazy as _

# Gender choices
GENDER_CHOICES = (
    ("M", _("Male")),
    ("F", _("Female")),
    ("O", _("Other")),
)

# Default system roles
DEFAULT_ROLES = [
    {
        "name": "Admin",
        "description": _("Full administrative access to the system"),
        "permissions": DEFAULT_ADMIN_PERMISSIONS,
    },
    {
        "name": "Teacher",
        "description": _("Access to teaching and student management functions"),
        "permissions": DEFAULT_TEACHER_PERMISSIONS,
    },
    {
        "name": "Parent",
        "description": _(
            "Access to view child information and communicate with teachers"
        ),
        "permissions": DEFAULT_PARENT_PERMISSIONS,
    },
    {
        "name": "Student",
        "description": _("Access to view course information and assignments"),
        "permissions": DEFAULT_STUDENT_PERMISSIONS,
    },
    {
        "name": "Staff",
        "description": _("Administrative staff with access to operational features"),
        "permissions": {
            "students": ["view", "add", "change"],
            "teachers": ["view"],
            "courses": ["view", "add", "change"],
            "classes": ["view", "add", "change"],
            "attendance": ["view", "mark", "edit"],
            "finance": ["view", "add_invoice", "record_payment"],
            "library": ["view", "add_book", "issue_book", "return_book"],
            "transport": ["view", "manage_routes", "assign_transport"],
            "communications": ["view", "send_message", "make_announcement"],
            "reports": ["view", "generate"],
        },
    },
    {
        "name": "Principal",
        "description": _("School principal with elevated administrative access"),
        "permissions": {
            "users": ["view", "add", "change"],
            "students": ["view", "add", "change", "delete", "view_details", "export"],
            "teachers": ["view", "add", "change", "delete", "view_details", "evaluate"],
            "courses": ["view", "add", "change", "delete", "manage_syllabus"],
            "classes": ["view", "add", "change", "delete", "manage_timetable"],
            "assignments": ["view", "add", "change", "delete", "grade"],
            "exams": ["view", "add", "change", "delete", "schedule", "enter_results"],
            "attendance": ["view", "mark", "edit", "report"],
            "finance": [
                "view",
                "add_invoice",
                "record_payment",
                "manage_fees",
                "view_reports",
            ],
            "library": ["view", "add_book", "issue_book", "return_book", "manage"],
            "transport": [
                "view",
                "manage_routes",
                "manage_vehicles",
                "assign_transport",
            ],
            "communications": [
                "view",
                "send_message",
                "send_email",
                "send_sms",
                "make_announcement",
            ],
            "reports": ["view", "generate", "export"],
        },
    },
    {
        "name": "Librarian",
        "description": _("Library management access"),
        "permissions": {
            "students": ["view"],
            "teachers": ["view"],
            "library": ["view", "add_book", "issue_book", "return_book", "manage"],
            "reports": ["view"],
        },
    },
    {
        "name": "Accountant",
        "description": _("Financial management access"),
        "permissions": {
            "students": ["view"],
            "finance": [
                "view",
                "add_invoice",
                "record_payment",
                "manage_fees",
                "view_reports",
            ],
            "reports": ["view", "generate"],
        },
    },
]

# System role names (cannot be deleted)
SYSTEM_ROLE_NAMES = [role["name"] for role in DEFAULT_ROLES]

# Role hierarchy for permission inheritance
ROLE_HIERARCHY = {
    "Admin": [],  # No parent roles
    "Principal": [],
    "Teacher": [],
    "Staff": [],
    "Accountant": [],
    "Librarian": [],
    "Parent": [],
    "Student": [],
}

# Default role assignments for new users based on email domain
DEFAULT_ROLE_MAPPINGS = {
    "teacher": ["Teacher"],
    "admin": ["Admin"],
    "staff": ["Staff"],
    "principal": ["Principal"],
    "librarian": ["Librarian"],
    "accountant": ["Accountant"],
}

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
