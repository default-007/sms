from django.db import models


class AssignmentStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    PUBLISHED = "published", "Published"
    CLOSED = "closed", "Closed"


class SubmissionType(models.TextChoices):
    ONLINE = "online", "Online"
    PHYSICAL = "physical", "Physical"


class SubmissionStatus(models.TextChoices):
    SUBMITTED = "submitted", "Submitted"
    LATE = "late", "Late"
    GRADED = "graded", "Graded"


class DayOfWeek(models.IntegerChoices):
    MONDAY = 0, "Monday"
    TUESDAY = 1, "Tuesday"
    WEDNESDAY = 2, "Wednesday"
    THURSDAY = 3, "Thursday"
    FRIDAY = 4, "Friday"
    SATURDAY = 5, "Saturday"
    SUNDAY = 6, "Sunday"
