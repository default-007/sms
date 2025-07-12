# src/accounts/constants/choices.py

from django.utils.translation import gettext_lazy as _

# Gender choices
GENDER_CHOICES = (
    ("M", _("Male")),
    ("F", _("Female")),
    ("O", _("Other")),
    ("P", _("Prefer not to say")),
)

# Account status choices
ACCOUNT_STATUS_CHOICES = (
    ("active", _("Active")),
    ("inactive", _("Inactive")),
    ("pending", _("Pending")),
    ("suspended", _("Suspended")),
)

# User statuses
USER_STATUS = (
    ("active", _("Active")),
    ("inactive", _("Inactive")),
    ("suspended", _("Suspended")),
)
