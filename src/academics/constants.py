"""
Constants for Academics Module

This module contains constant values used throughout the academics app,
including choices, limits, and configuration values.
"""

# Academic Year Constants
ACADEMIC_YEAR_NAME_MAX_LENGTH = 20
ACADEMIC_YEAR_MIN_DURATION_DAYS = 180  # Minimum 6 months
ACADEMIC_YEAR_MAX_DURATION_DAYS = 450  # Maximum 15 months

# Term Constants
MIN_TERMS_PER_YEAR = 2
MAX_TERMS_PER_YEAR = 4
TERM_MIN_DURATION_DAYS = 30  # Minimum 1 month
TERM_MAX_DURATION_DAYS = 180  # Maximum 6 months

TERM_CHOICES = [
    (1, "First Term"),
    (2, "Second Term"),
    (3, "Third Term"),
    (4, "Fourth Term"),
]

DEFAULT_TERM_NAMES = ["First Term", "Second Term", "Third Term", "Fourth Term"]

# Section Constants
SECTION_ORDER_MIN = 1
SECTION_ORDER_MAX = 20

# Common section names by education level
DEFAULT_SECTION_NAMES = {
    "early_childhood": ["Pre-Nursery", "Nursery", "Pre-Primary"],
    "primary": ["Lower Primary", "Upper Primary"],
    "secondary": ["Middle School", "Lower Secondary", "Upper Secondary"],
    "senior": ["Senior Secondary", "Pre-University"],
}

# Grade Constants
GRADE_ORDER_MIN = 1
GRADE_ORDER_MAX = 50

# Age range constants
MIN_STUDENT_AGE = 2
MAX_STUDENT_AGE = 25

# Common grade names by section
DEFAULT_GRADE_NAMES = {
    "pre_primary": ["Playgroup", "Nursery", "Lower KG", "Upper KG"],
    "lower_primary": ["Grade 1", "Grade 2", "Grade 3"],
    "upper_primary": ["Grade 4", "Grade 5"],
    "middle_school": ["Grade 6", "Grade 7", "Grade 8"],
    "lower_secondary": ["Grade 9", "Grade 10"],
    "upper_secondary": ["Grade 11", "Grade 12"],
}

# Class Constants
CLASS_CAPACITY_MIN = 1
CLASS_CAPACITY_MAX = 100
CLASS_CAPACITY_DEFAULT = 30

# Class name patterns
CLASS_NAME_PATTERNS = {
    "alphabetic": ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J"],
    "directional": [
        "North",
        "South",
        "East",
        "West",
        "Northeast",
        "Southeast",
        "Northwest",
        "Southwest",
    ],
    "colors": [
        "Red",
        "Blue",
        "Green",
        "Yellow",
        "Orange",
        "Purple",
        "Pink",
        "Brown",
        "Black",
        "White",
    ],
    "precious_stones": [
        "Diamond",
        "Ruby",
        "Emerald",
        "Sapphire",
        "Pearl",
        "Topaz",
        "Amethyst",
        "Opal",
    ],
    "flowers": [
        "Rose",
        "Lily",
        "Jasmine",
        "Tulip",
        "Lotus",
        "Daisy",
        "Sunflower",
        "Orchid",
    ],
    "planets": [
        "Mercury",
        "Venus",
        "Earth",
        "Mars",
        "Jupiter",
        "Saturn",
        "Uranus",
        "Neptune",
    ],
    "elements": [
        "Hydrogen",
        "Helium",
        "Lithium",
        "Carbon",
        "Oxygen",
        "Neon",
        "Sodium",
        "Magnesium",
    ],
    "numeric": ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10"],
    "roman": ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"],
}

# Optimal class sizes by education level
OPTIMAL_CLASS_SIZES = {
    "pre_primary": 15,
    "lower_primary": 20,
    "upper_primary": 25,
    "middle_school": 28,
    "lower_secondary": 30,
    "upper_secondary": 32,
    "senior_secondary": 35,
}

# Capacity utilization thresholds
CAPACITY_THRESHOLDS = {
    "low": 60,  # Below 60% is low utilization
    "optimal": 85,  # 60-85% is optimal utilization
    "high": 95,  # 85-95% is high utilization
    "overcapacity": 100,  # Above 100% is overcapacity
}

# Department Constants
DEPARTMENT_TYPES = [
    ("academic", "Academic Department"),
    ("administrative", "Administrative Department"),
    ("support", "Support Department"),
    ("extracurricular", "Extracurricular Department"),
]

DEFAULT_DEPARTMENTS = [
    {
        "name": "Academic Administration",
        "description": "Overall academic management and coordination",
        "type": "administrative",
    },
    {
        "name": "Primary Education",
        "description": "Primary level education management",
        "type": "academic",
    },
    {
        "name": "Secondary Education",
        "description": "Secondary level education management",
        "type": "academic",
    },
    {
        "name": "Languages",
        "description": "Language subjects and literature",
        "type": "academic",
    },
    {
        "name": "Mathematics",
        "description": "Mathematics and related subjects",
        "type": "academic",
    },
    {
        "name": "Sciences",
        "description": "Physics, Chemistry, Biology, and General Science",
        "type": "academic",
    },
    {
        "name": "Social Studies",
        "description": "History, Geography, Civics, and Social Sciences",
        "type": "academic",
    },
    {
        "name": "Arts & Crafts",
        "description": "Creative arts, music, and craft activities",
        "type": "extracurricular",
    },
    {
        "name": "Physical Education",
        "description": "Sports, fitness, and physical activities",
        "type": "extracurricular",
    },
    {
        "name": "Technology",
        "description": "Computer science and technology education",
        "type": "academic",
    },
]

# Analytics Constants
ANALYTICS_CACHE_TIMEOUT = 3600  # 1 hour in seconds
ANALYTICS_CALCULATION_BATCH_SIZE = 100

# Performance grade thresholds
PERFORMANCE_GRADES = {
    "A+": {"min": 95, "max": 100},
    "A": {"min": 90, "max": 94},
    "B+": {"min": 85, "max": 89},
    "B": {"min": 80, "max": 84},
    "C+": {"min": 75, "max": 79},
    "C": {"min": 70, "max": 74},
    "D+": {"min": 65, "max": 69},
    "D": {"min": 60, "max": 64},
    "F": {"min": 0, "max": 59},
}

# Attendance thresholds
ATTENDANCE_THRESHOLDS = {
    "excellent": 95,  # 95% and above
    "good": 85,  # 85-94%
    "average": 75,  # 75-84%
    "poor": 60,  # 60-74%
    "critical": 0,  # Below 60%
}

# Status Constants
ACADEMIC_YEAR_STATUS = [
    ("draft", "Draft"),
    ("active", "Active"),
    ("completed", "Completed"),
    ("archived", "Archived"),
]

TERM_STATUS = [
    ("upcoming", "Upcoming"),
    ("current", "Current"),
    ("completed", "Completed"),
]

CLASS_STATUS = [
    ("active", "Active"),
    ("inactive", "Inactive"),
    ("full", "Full"),
    ("disbanded", "Disbanded"),
]

# Academic progression constants
PROGRESSION_RULES = {
    "auto_promotion": True,
    "minimum_attendance": 75,  # Minimum attendance percentage for promotion
    "minimum_grade": 60,  # Minimum grade percentage for promotion
    "grace_marks": 5,  # Grace marks for borderline cases
    "max_failed_subjects": 2,  # Maximum failed subjects allowed for promotion
}

# Validation rules
VALIDATION_RULES = {
    "academic_year": {
        "min_duration_days": ACADEMIC_YEAR_MIN_DURATION_DAYS,
        "max_duration_days": ACADEMIC_YEAR_MAX_DURATION_DAYS,
        "allow_overlap": False,
    },
    "term": {
        "min_duration_days": TERM_MIN_DURATION_DAYS,
        "max_duration_days": TERM_MAX_DURATION_DAYS,
        "allow_gap_days": 7,  # Maximum gap between terms
        "require_sequential": True,
    },
    "class": {
        "min_capacity": CLASS_CAPACITY_MIN,
        "max_capacity": CLASS_CAPACITY_MAX,
        "allow_overcapacity": False,
        "capacity_buffer": 5,  # Buffer for capacity calculations
    },
}

# Report constants
REPORT_TYPES = [
    ("academic_summary", "Academic Summary Report"),
    ("enrollment", "Enrollment Report"),
    ("capacity_utilization", "Capacity Utilization Report"),
    ("class_distribution", "Class Distribution Report"),
    ("section_analysis", "Section Analysis Report"),
    ("grade_progression", "Grade Progression Report"),
    ("department_overview", "Department Overview Report"),
]

REPORT_FORMATS = [("pdf", "PDF"), ("excel", "Excel"), ("csv", "CSV"), ("json", "JSON")]

# Notification constants
NOTIFICATION_TYPES = [
    ("capacity_warning", "Capacity Warning"),
    ("term_transition", "Term Transition"),
    ("academic_year_change", "Academic Year Change"),
    ("structure_integrity", "Structure Integrity Alert"),
    ("enrollment_alert", "Enrollment Alert"),
]

NOTIFICATION_PRIORITIES = [
    ("low", "Low"),
    ("medium", "Medium"),
    ("high", "High"),
    ("critical", "Critical"),
]

# Cache keys
CACHE_KEYS = {
    "current_academic_year": "academics:current_academic_year",
    "current_term": "academics:current_term",
    "academic_structure": "academics:structure:{academic_year_id}",
    "section_hierarchy": "academics:section_hierarchy:{section_id}",
    "section_analytics": "academics:section_analytics:{section_id}",
    "grade_details": "academics:grade_details:{grade_id}",
    "class_analytics": "academics:class_analytics:{class_id}",
    "quick_stats": "academics:quick_stats",
    "sections_summary": "academics:sections_summary",
}

# Permission constants
ACADEMIC_PERMISSIONS = [
    "view_academicyear",
    "add_academicyear",
    "change_academicyear",
    "delete_academicyear",
    "view_term",
    "add_term",
    "change_term",
    "delete_term",
    "view_section",
    "add_section",
    "change_section",
    "delete_section",
    "view_grade",
    "add_grade",
    "change_grade",
    "delete_grade",
    "view_class",
    "add_class",
    "change_class",
    "delete_class",
    "view_department",
    "add_department",
    "change_department",
    "delete_department",
    "view_analytics",
    "manage_structure",
    "transition_academic_year",
]

# Role-based access patterns
ROLE_PERMISSIONS = {
    "Academic Admin": [
        "view_*",
        "add_*",
        "change_*",
        "delete_*",
        "view_analytics",
        "manage_structure",
        "transition_academic_year",
    ],
    "Principal": [
        "view_*",
        "add_*",
        "change_*",
        "view_analytics",
        "manage_structure",
        "transition_academic_year",
    ],
    "Academic Coordinator": [
        "view_*",
        "add_class",
        "change_class",
        "view_analytics",
        "manage_structure",
    ],
    "Department Head": ["view_*", "change_class", "view_analytics"],
    "Teacher": [
        "view_academicyear",
        "view_term",
        "view_section",
        "view_grade",
        "view_class",
        "view_department",
    ],
    "Parent": [
        "view_academicyear",
        "view_term",
        "view_section",
        "view_grade",
        "view_class",
    ],
    "Student": ["view_academicyear", "view_term", "view_class"],
}

# API constants
API_VERSION = "v1"
API_RATE_LIMITS = {
    "default": "1000/hour",
    "analytics": "100/hour",
    "bulk_operations": "50/hour",
}

MAX_BULK_OPERATIONS = {"classes": 20, "grades": 10, "sections": 5}

# File upload constants
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB
ALLOWED_FILE_EXTENSIONS = [".pdf", ".doc", ".docx", ".xls", ".xlsx", ".csv"]

# Internationalization
SUPPORTED_LANGUAGES = [
    ("en", "English"),
    ("es", "Spanish"),
    ("fr", "French"),
    ("de", "German"),
    ("hi", "Hindi"),
    ("ar", "Arabic"),
    ("zh", "Chinese"),
    ("ja", "Japanese"),
]

DEFAULT_LANGUAGE = "en"

# Academic calendar constants
ACADEMIC_CALENDAR_TYPES = [
    ("semester", "Semester System"),
    ("trimester", "Trimester System"),
    ("quarter", "Quarter System"),
    ("annual", "Annual System"),
]

HOLIDAY_TYPES = [
    ("national", "National Holiday"),
    ("religious", "Religious Holiday"),
    ("school", "School Holiday"),
    ("exam", "Examination Period"),
    ("vacation", "Vacation Period"),
]

# Export/Import constants
EXPORT_BATCH_SIZE = 1000
IMPORT_BATCH_SIZE = 500
MAX_EXPORT_RECORDS = 10000

# Error messages
ERROR_MESSAGES = {
    "academic_year_overlap": "Academic year dates overlap with existing academic year",
    "term_overlap": "Term dates overlap with existing term",
    "multiple_current_years": "Multiple academic years marked as current",
    "multiple_current_terms": "Multiple terms marked as current",
    "class_over_capacity": "Class enrollment exceeds capacity",
    "invalid_age_range": "Invalid age range for grade",
    "duplicate_class_name": "Class name already exists in grade",
    "no_current_academic_year": "No current academic year is set",
    "no_current_term": "No current term is set",
    "structure_integrity_error": "Academic structure integrity check failed",
}

# Success messages
SUCCESS_MESSAGES = {
    "academic_year_created": "Academic year created successfully",
    "term_created": "Term created successfully",
    "section_created": "Section created successfully",
    "grade_created": "Grade created successfully",
    "class_created": "Class created successfully",
    "structure_validated": "Academic structure validation passed",
    "analytics_updated": "Analytics updated successfully",
    "transition_completed": "Academic year transition completed",
}

# Default configuration
DEFAULT_CONFIG = {
    "auto_create_terms": True,
    "default_terms_count": 3,
    "enable_analytics": True,
    "enable_caching": True,
    "cache_timeout": ANALYTICS_CACHE_TIMEOUT,
    "enable_notifications": True,
    "auto_transition_terms": True,
    "validate_structure_integrity": True,
    "enable_capacity_warnings": True,
    "capacity_warning_threshold": 95,
}

# Module metadata
MODULE_VERSION = "1.0.0"
MODULE_NAME = "Academics"
MODULE_DESCRIPTION = "Comprehensive academic structure management"
MODULE_AUTHOR = "School Management System Team"

# Feature flags
FEATURES = {
    "multi_academic_years": True,
    "flexible_terms": True,
    "section_hierarchy": True,
    "age_requirements": True,
    "class_capacity_limits": True,
    "teacher_assignments": True,
    "analytics_integration": True,
    "background_tasks": True,
    "api_endpoints": True,
    "permission_system": True,
    "cache_support": True,
    "internationalization": True,
    "bulk_operations": True,
    "data_validation": True,
    "audit_logging": True,
}
