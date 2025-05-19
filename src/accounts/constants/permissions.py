# src/accounts/constants/permissions.py

from django.utils.translation import gettext_lazy as _

# Permission scopes for user roles
PERMISSION_SCOPES = {
    "users": {
        "view": "View users",
        "add": "Add users",
        "change": "Edit users",
        "delete": "Delete users",
    },
    "roles": {
        "view": "View roles",
        "add": "Add roles",
        "change": "Edit roles",
        "delete": "Delete roles",
    },
    "students": {
        "view": "View students",
        "add": "Add students",
        "change": "Edit students",
        "delete": "Delete students",
    },
    "teachers": {
        "view": "View teachers",
        "add": "Add teachers",
        "change": "Edit teachers",
        "delete": "Delete teachers",
    },
    "courses": {
        "view": "View courses",
        "add": "Add courses",
        "change": "Edit courses",
        "delete": "Delete courses",
    },
    "classes": {
        "view": "View classes",
        "add": "Add classes",
        "change": "Edit classes",
        "delete": "Delete classes",
    },
    "exams": {
        "view": "View exams",
        "add": "Add exams",
        "change": "Edit exams",
        "delete": "Delete exams",
    },
    "grades": {
        "view": "View grades",
        "add": "Add grades",
        "change": "Edit grades",
        "delete": "Delete grades",
    },
    "attendance": {
        "view": "View attendance",
        "add": "Add attendance",
        "change": "Edit attendance",
        "delete": "Delete attendance",
    },
    "fees": {
        "view": "View fees",
        "add": "Add fees",
        "change": "Edit fees",
        "delete": "Delete fees",
    },
    "library": {
        "view": "View library",
        "add": "Add library items",
        "change": "Edit library items",
        "delete": "Delete library items",
    },
    "transport": {
        "view": "View transport",
        "add": "Add transport",
        "change": "Edit transport",
        "delete": "Delete transport",
    },
    "communications": {
        "view": "View communications",
        "add": "Add communications",
        "change": "Edit communications",
        "delete": "Delete communications",
    },
    "reports": {
        "view": "View reports",
        "generate": "Generate reports",
    },
}

# Default role permissions
DEFAULT_ADMIN_PERMISSIONS = {
    # Grant all permissions for all resources to Admin role
    resource: list(actions.keys())
    for resource, actions in PERMISSION_SCOPES.items()
}

DEFAULT_TEACHER_PERMISSIONS = {
    "students": ["view", "view_details"],
    "courses": ["view"],
    "classes": ["view"],
    "assignments": ["view", "add", "change", "grade"],
    "exams": ["view", "add", "enter_results"],
    "attendance": ["view", "mark"],
    "communications": ["view", "send_message"],
    "reports": ["view"],
}

DEFAULT_PARENT_PERMISSIONS = {
    "students": ["view"],  # Only their own children
    "teachers": ["view"],
    "courses": ["view"],
    "classes": ["view"],
    "assignments": ["view"],
    "exams": ["view"],
    "attendance": ["view"],
    "communications": ["view", "send_message"],
    "finance": ["view"],  # Only their own invoices
}

DEFAULT_STUDENT_PERMISSIONS = {
    "courses": ["view"],
    "classes": ["view"],
    "assignments": ["view"],
    "exams": ["view"],
    "attendance": ["view"],  # Only their own
    "library": ["view"],
    "communications": ["view", "send_message"],
}

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
