from django.utils.translation import gettext_lazy as _

# Constants for use in the exams module

QUESTION_CHOICES = [
    ("mcq", _("Multiple Choice")),
    ("true_false", _("True/False")),
    ("short_answer", _("Short Answer")),
    ("essay", _("Essay")),
]

DIFFICULTY_LEVELS = [
    ("easy", _("Easy")),
    ("medium", _("Medium")),
    ("hard", _("Hard")),
]

EXAM_STATUSES = [
    ("scheduled", _("Scheduled")),
    ("ongoing", _("Ongoing")),
    ("completed", _("Completed")),
    ("cancelled", _("Cancelled")),
]

QUIZ_STATUSES = [
    ("draft", _("Draft")),
    ("published", _("Published")),
    ("closed", _("Closed")),
]

REPORT_TERMS = [
    ("first", _("First")),
    ("second", _("Second")),
    ("final", _("Final")),
]

REPORT_STATUSES = [
    ("draft", _("Draft")),
    ("published", _("Published")),
    ("archived", _("Archived")),
]
