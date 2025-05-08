from django.utils.translation import gettext_lazy as _

# Permission scopes for user roles
PERMISSION_SCOPES = {
    "users": {
        "view": _("View user information"),
        "add": _("Add new users"),
        "change": _("Edit user information"),
        "delete": _("Delete users"),
    },
    "roles": {
        "view": _("View roles"),
        "add": _("Add new roles"),
        "change": _("Edit roles"),
        "delete": _("Delete roles"),
    },
    "students": {
        "view": _("View student information"),
        "add": _("Add new students"),
        "change": _("Edit student information"),
        "delete": _("Delete students"),
        "view_details": _("View detailed student information"),
        "export": _("Export student data"),
    },
    "teachers": {
        "view": _("View teacher information"),
        "add": _("Add new teachers"),
        "change": _("Edit teacher information"),
        "delete": _("Delete teachers"),
        "view_details": _("View detailed teacher information"),
        "assign_classes": _("Assign classes to teachers"),
        "evaluate": _("Evaluate teachers"),
    },
    "courses": {
        "view": _("View courses"),
        "add": _("Add new courses"),
        "change": _("Edit courses"),
        "delete": _("Delete courses"),
        "manage_syllabus": _("Manage course syllabus"),
    },
    "classes": {
        "view": _("View classes"),
        "add": _("Add new classes"),
        "change": _("Edit classes"),
        "delete": _("Delete classes"),
        "manage_timetable": _("Manage class timetable"),
    },
    "assignments": {
        "view": _("View assignments"),
        "add": _("Add new assignments"),
        "change": _("Edit assignments"),
        "delete": _("Delete assignments"),
        "grade": _("Grade assignments"),
    },
    "exams": {
        "view": _("View exams"),
        "add": _("Add new exams"),
        "change": _("Edit exams"),
        "delete": _("Delete exams"),
        "schedule": _("Schedule exams"),
        "enter_results": _("Enter exam results"),
    },
    "attendance": {
        "view": _("View attendance"),
        "mark": _("Mark attendance"),
        "edit": _("Edit attendance"),
        "report": _("Generate attendance reports"),
    },
    "finance": {
        "view": _("View financial information"),
        "add_invoice": _("Create invoices"),
        "record_payment": _("Record payments"),
        "manage_fees": _("Manage fee structures"),
        "view_reports": _("View financial reports"),
    },
    "library": {
        "view": _("View library resources"),
        "add_book": _("Add new books"),
        "issue_book": _("Issue books"),
        "return_book": _("Process book returns"),
        "manage": _("Manage library operations"),
    },
    "transport": {
        "view": _("View transport information"),
        "manage_routes": _("Manage transport routes"),
        "manage_vehicles": _("Manage vehicles"),
        "assign_transport": _("Assign transport to students"),
    },
    "communications": {
        "view": _("View communications"),
        "send_message": _("Send messages"),
        "send_email": _("Send emails"),
        "send_sms": _("Send SMS"),
        "make_announcement": _("Make announcements"),
    },
    "reports": {
        "view": _("View reports"),
        "generate": _("Generate custom reports"),
        "export": _("Export reports"),
    },
    "system": {
        "view_settings": _("View system settings"),
        "change_settings": _("Change system settings"),
        "manage_backups": _("Manage system backups"),
        "view_logs": _("View system logs"),
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

# User statuses
USER_STATUS = (
    ("active", _("Active")),
    ("inactive", _("Inactive")),
    ("suspended", _("Suspended")),
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
]
