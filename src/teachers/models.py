from django.db import models
from django.conf import settings
from django.db.models import Avg, Count, Sum
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal


class TeacherQuerySet(models.QuerySet):
    def active(self):
        return self.filter(status="Active")

    def on_leave(self):
        return self.filter(status="On Leave")

    def by_department(self, department_id):
        return self.filter(department_id=department_id)

    def by_experience_range(self, min_years=None, max_years=None):
        queryset = self
        if min_years is not None:
            queryset = queryset.filter(experience_years__gte=min_years)
        if max_years is not None:
            queryset = queryset.filter(experience_years__lte=max_years)
        return queryset

    def with_evaluation_stats(self):
        return self.annotate(
            avg_evaluation_score=Avg("evaluations__score"),
            evaluation_count=Count("evaluations"),
            latest_evaluation_date=models.Max("evaluations__evaluation_date"),
        )

    def with_class_counts(self):
        return self.annotate(
            class_count=Count("class_assignments", distinct=True),
            subject_count=Count("class_assignments__subject", distinct=True),
        )

    def with_workload_stats(self, academic_year=None):
        queryset = self
        if academic_year:
            queryset = queryset.annotate(
                current_classes=Count(
                    "class_assignments",
                    filter=models.Q(class_assignments__academic_year=academic_year),
                    distinct=True,
                ),
                current_subjects=Count(
                    "class_assignments__subject",
                    filter=models.Q(class_assignments__academic_year=academic_year),
                    distinct=True,
                ),
            )
        return queryset


class Teacher(models.Model):
    STATUS_CHOICES = (
        ("Active", "Active"),
        ("On Leave", "On Leave"),
        ("Terminated", "Terminated"),
    )

    CONTRACT_TYPE_CHOICES = (
        ("Permanent", "Permanent"),
        ("Temporary", "Temporary"),
        ("Contract", "Contract"),
    )

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="teacher_profile",
    )
    employee_id = models.CharField(max_length=20, unique=True, db_index=True)
    joining_date = models.DateField(db_index=True)
    qualification = models.CharField(max_length=500)
    experience_years = models.DecimalField(
        max_digits=4,
        decimal_places=1,
        default=0,
        db_index=True,
        validators=[MinValueValidator(Decimal("0"))],
    )
    specialization = models.CharField(max_length=500)
    department = models.ForeignKey(
        "academics.Department",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="teachers",
        db_index=True,
    )
    position = models.CharField(max_length=100)
    salary = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0"))]
    )
    contract_type = models.CharField(
        max_length=20, choices=CONTRACT_TYPE_CHOICES, db_index=True
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="Active", db_index=True
    )

    # Additional fields
    bio = models.TextField(blank=True)
    emergency_contact = models.CharField(max_length=100, blank=True)
    emergency_phone = models.CharField(max_length=20, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = TeacherQuerySet.as_manager()

    class Meta:
        ordering = ["employee_id"]
        permissions = [
            ("view_teacher_details", "Can view detailed teacher information"),
            ("assign_classes", "Can assign classes to teachers"),
            ("view_teacher_analytics", "Can view teacher analytics"),
            ("export_teacher_data", "Can export teacher data"),
            ("evaluate_teacher", "Can evaluate teacher performance"),
        ]
        indexes = [
            models.Index(fields=["joining_date"]),
            models.Index(fields=["department", "status"]),
            models.Index(fields=["contract_type", "status"]),
            models.Index(fields=["experience_years"]),
            models.Index(fields=["status", "created_at"]),
        ]

    def __str__(self):
        return f"{self.user.first_name} {self.user.last_name} ({self.employee_id})"

    def save(self, *args, **kwargs):
        # Auto-generate employee ID if not provided
        if not self.employee_id:
            self.employee_id = self._generate_employee_id()
        super().save(*args, **kwargs)

    def _generate_employee_id(self):
        """Generate unique employee ID"""
        current_year = timezone.now().year
        prefix = f"TCH{current_year}"

        # Get the last teacher for this year
        last_teacher = (
            Teacher.objects.filter(employee_id__startswith=prefix)
            .order_by("employee_id")
            .last()
        )

        if last_teacher:
            try:
                last_number = int(last_teacher.employee_id.replace(prefix, ""))
                new_number = last_number + 1
            except ValueError:
                new_number = 1
        else:
            new_number = 1

        return f"{prefix}{new_number:04d}"

    def is_active(self):
        return self.status == "Active"

    def get_full_name(self):
        return f"{self.user.first_name} {self.user.last_name}"

    def get_short_name(self):
        return (
            f"{self.user.first_name} {self.user.last_name[0]}."
            if self.user.last_name
            else self.user.first_name
        )

    def get_display_name(self):
        """Get display name with title"""
        name = self.get_full_name()
        if self.position:
            return f"{self.position} {name}"
        return name

    def get_assigned_classes(self, academic_year=None):
        """Get classes assigned to this teacher"""
        assignments = self.class_assignments.select_related("class_instance")
        if academic_year:
            assignments = assignments.filter(academic_year=academic_year)
        return [assignment.class_instance for assignment in assignments.distinct()]

    def get_assigned_subjects(self, academic_year=None):
        """Get subjects assigned to this teacher"""
        assignments = self.class_assignments.select_related("subject")
        if academic_year:
            assignments = assignments.filter(academic_year=academic_year)
        return list(set([assignment.subject for assignment in assignments]))

    def get_class_teacher_classes(self, academic_year=None):
        """Get classes where this teacher is the class teacher"""
        assignments = self.class_assignments.filter(is_class_teacher=True)
        if academic_year:
            assignments = assignments.filter(academic_year=academic_year)
        return [assignment.class_instance for assignment in assignments]

    def get_average_evaluation_score(self, year=None):
        """Get average evaluation score"""
        evaluations = self.evaluations.all()
        if year:
            evaluations = evaluations.filter(evaluation_date__year=year)
        return evaluations.aggregate(avg_score=Avg("score"))["avg_score"]

    def get_latest_evaluation(self):
        """Get latest evaluation"""
        return self.evaluations.order_by("-evaluation_date").first()

    def get_years_of_service(self):
        """Calculate years of service"""
        if not self.joining_date:
            return 0
        today = timezone.now().date()
        return (today - self.joining_date).days / 365.25

    def get_performance_trend(self, months=6):
        """Get performance trend over the last X months"""
        start_date = timezone.now().date() - timezone.timedelta(days=30 * months)
        evaluations = self.evaluations.filter(evaluation_date__gte=start_date).order_by(
            "evaluation_date"
        )

        return {
            "dates": [eval.evaluation_date for eval in evaluations],
            "scores": [float(eval.score) for eval in evaluations],
            "count": evaluations.count(),
        }

    def get_current_workload(self):
        """Get current academic year workload"""
        from src.academics.models import AcademicYear

        current_year = AcademicYear.objects.filter(is_current=True).first()
        if not current_year:
            return {"classes": 0, "subjects": 0, "assignments": []}

        assignments = self.class_assignments.filter(
            academic_year=current_year
        ).select_related("class_instance", "subject")

        return {
            "classes": assignments.values("class_instance").distinct().count(),
            "subjects": assignments.values("subject").distinct().count(),
            "assignments": list(assignments),
        }

    def can_be_assigned_to_class(self, class_instance, subject):
        """Check if teacher can be assigned to a class for a subject"""
        # Add business logic here
        # For example, check if teacher's specialization matches subject
        return True

    def get_evaluation_summary(self, year=None):
        """Get evaluation summary"""
        evaluations = self.evaluations.all()
        if year:
            evaluations = evaluations.filter(evaluation_date__year=year)

        if not evaluations.exists():
            return None

        return {
            "count": evaluations.count(),
            "average_score": evaluations.aggregate(avg=Avg("score"))["avg"],
            "highest_score": evaluations.aggregate(max=models.Max("score"))["max"],
            "lowest_score": evaluations.aggregate(min=models.Min("score"))["min"],
            "latest": evaluations.order_by("-evaluation_date").first(),
            "needs_followup": evaluations.filter(
                score__lt=70, status__in=["submitted", "reviewed"]
            ).count(),
        }


class TeacherClassAssignment(models.Model):
    teacher = models.ForeignKey(
        Teacher, on_delete=models.CASCADE, related_name="class_assignments"
    )
    class_instance = models.ForeignKey(
        "academics.Class", on_delete=models.CASCADE, related_name="teacher_assignments"
    )
    subject = models.ForeignKey(
        "subjects.Subject", on_delete=models.CASCADE, related_name="teacher_assignments"
    )
    academic_year = models.ForeignKey(
        "academics.AcademicYear",
        on_delete=models.CASCADE,
        related_name="teacher_assignments",
    )
    term = models.ForeignKey(
        "academics.Term",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="teacher_assignments",
    )
    is_class_teacher = models.BooleanField(default=False)

    # Additional fields
    notes = models.TextField(blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [
            ["teacher", "class_instance", "subject", "academic_year"],
        ]
        indexes = [
            models.Index(fields=["teacher", "academic_year"]),
            models.Index(fields=["class_instance", "academic_year"]),
            models.Index(fields=["subject", "academic_year"]),
            models.Index(fields=["is_class_teacher"]),
            models.Index(fields=["is_active", "academic_year"]),
        ]
        constraints = [
            # Only one class teacher per class per academic year
            models.UniqueConstraint(
                fields=["class_instance", "academic_year"],
                condition=models.Q(is_class_teacher=True),
                name="unique_class_teacher_per_class_year",
            )
        ]

    def __str__(self):
        return f"{self.teacher} - {self.class_instance} - {self.subject}"

    def clean(self):
        from django.core.exceptions import ValidationError

        # Validate date ranges
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValidationError("Start date cannot be after end date")

        # Validate academic year alignment
        if self.start_date and self.academic_year:
            if self.start_date < self.academic_year.start_date:
                raise ValidationError(
                    "Assignment start date cannot be before academic year start"
                )

        if self.end_date and self.academic_year:
            if self.end_date > self.academic_year.end_date:
                raise ValidationError(
                    "Assignment end date cannot be after academic year end"
                )

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def get_duration_days(self):
        """Get assignment duration in days"""
        if not self.start_date or not self.end_date:
            return None
        return (self.end_date - self.start_date).days

    def is_current(self):
        """Check if assignment is currently active"""
        if not self.is_active:
            return False

        today = timezone.now().date()

        if self.start_date and today < self.start_date:
            return False

        if self.end_date and today > self.end_date:
            return False

        return True


class TeacherEvaluation(models.Model):
    EVALUATION_STATUS_CHOICES = [
        ("draft", "Draft"),
        ("submitted", "Submitted"),
        ("reviewed", "Reviewed"),
        ("approved", "Approved"),
        ("closed", "Closed"),
    ]

    EVALUATION_CATEGORIES = {
        "teaching_methodology": {
            "name": "Teaching Methodology",
            "weight": 0.25,
            "description": "Effectiveness of teaching methods and techniques",
        },
        "subject_knowledge": {
            "name": "Subject Knowledge",
            "weight": 0.20,
            "description": "Depth and accuracy of subject matter expertise",
        },
        "classroom_management": {
            "name": "Classroom Management",
            "weight": 0.20,
            "description": "Ability to maintain discipline and create learning environment",
        },
        "student_engagement": {
            "name": "Student Engagement",
            "weight": 0.20,
            "description": "Ability to involve and motivate students",
        },
        "professional_conduct": {
            "name": "Professional Conduct",
            "weight": 0.15,
            "description": "Professional behavior and ethics",
        },
    }

    teacher = models.ForeignKey(
        Teacher, on_delete=models.CASCADE, related_name="evaluations"
    )
    evaluator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="teacher_evaluations",
    )
    academic_year = models.ForeignKey(
        "academics.AcademicYear",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="teacher_evaluations",
    )
    term = models.ForeignKey(
        "academics.Term",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="teacher_evaluations",
    )
    evaluation_date = models.DateField(db_index=True)
    evaluation_period_start = models.DateField(null=True, blank=True)
    evaluation_period_end = models.DateField(null=True, blank=True)

    # Scoring
    criteria = models.JSONField(default=dict)  # Stores evaluation parameters and scores
    score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        db_index=True,
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("100"))],
    )
    weighted_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Score calculated using category weights",
    )

    # Feedback
    remarks = models.TextField()
    strengths = models.TextField(blank=True)
    areas_for_improvement = models.TextField(blank=True)
    followup_actions = models.TextField(blank=True)

    # Status and follow-up
    status = models.CharField(
        max_length=20,
        choices=EVALUATION_STATUS_CHOICES,
        default="submitted",
        db_index=True,
    )
    followup_date = models.DateField(null=True, blank=True)
    followup_completed = models.BooleanField(default=False)
    followup_notes = models.TextField(blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-evaluation_date"]
        indexes = [
            models.Index(fields=["teacher", "evaluation_date"]),
            models.Index(fields=["teacher", "score"]),
            models.Index(fields=["evaluator", "evaluation_date"]),
            models.Index(fields=["status", "evaluation_date"]),
            models.Index(fields=["academic_year", "term"]),
        ]

    def __str__(self):
        return f"Evaluation of {self.teacher} on {self.evaluation_date}"

    def save(self, *args, **kwargs):
        # Calculate weighted score if criteria is provided
        if self.criteria:
            self.weighted_score = self.calculate_weighted_score()

        # Set follow-up date for low scores
        if self.score < 70 and not self.followup_date and self.status != "closed":
            self.followup_date = self.evaluation_date + timezone.timedelta(days=30)

        super().save(*args, **kwargs)

    def calculate_weighted_score(self):
        """Calculate weighted score based on category weights"""
        if not self.criteria:
            return self.score

        total_weighted_score = 0
        total_weight = 0

        for category, data in self.criteria.items():
            if category in self.EVALUATION_CATEGORIES and isinstance(data, dict):
                score = data.get("score", 0)
                max_score = data.get("max_score", 10)
                weight = self.EVALUATION_CATEGORIES[category]["weight"]

                category_percentage = (score / max_score * 100) if max_score > 0 else 0
                weighted_contribution = category_percentage * weight

                total_weighted_score += weighted_contribution
                total_weight += weight

        return total_weighted_score if total_weight > 0 else self.score

    def get_performance_level(self):
        """Get performance level based on score"""
        score = float(self.weighted_score or self.score)
        if score >= 90:
            return {"level": "Excellent", "color": "success", "icon": "fas fa-star"}
        elif score >= 80:
            return {"level": "Good", "color": "info", "icon": "fas fa-thumbs-up"}
        elif score >= 70:
            return {"level": "Satisfactory", "color": "primary", "icon": "fas fa-check"}
        elif score >= 60:
            return {
                "level": "Needs Improvement",
                "color": "warning",
                "icon": "fas fa-exclamation-triangle",
            }
        else:
            return {"level": "Poor", "color": "danger", "icon": "fas fa-times"}

    def is_followup_required(self):
        """Check if follow-up is required"""
        return (
            float(self.score) < 70
            and self.status not in ["closed"]
            and not self.followup_completed
        )

    def is_followup_overdue(self):
        """Check if follow-up is overdue"""
        if not self.followup_date or self.followup_completed:
            return False
        return self.followup_date < timezone.now().date()

    def get_category_scores(self):
        """Get scores by category with metadata"""
        category_scores = []

        for category, metadata in self.EVALUATION_CATEGORIES.items():
            category_data = self.criteria.get(category, {})
            score = category_data.get("score", 0)
            max_score = category_data.get("max_score", 10)
            percentage = (score / max_score * 100) if max_score > 0 else 0

            category_scores.append(
                {
                    "category": category,
                    "name": metadata["name"],
                    "description": metadata["description"],
                    "weight": metadata["weight"],
                    "score": score,
                    "max_score": max_score,
                    "percentage": percentage,
                    "comments": category_data.get("comments", ""),
                }
            )

        return category_scores

    @staticmethod
    def get_default_criteria():
        """Get default criteria structure"""
        return {
            category: {
                "score": 0,
                "max_score": 10,
                "comments": "",
            }
            for category in TeacherEvaluation.EVALUATION_CATEGORIES.keys()
        }

    def get_improvement_areas(self):
        """Get areas that scored below 70%"""
        improvements = []

        for category_data in self.get_category_scores():
            if category_data["percentage"] < 70:
                improvements.append(
                    {
                        "category": category_data["name"],
                        "score": category_data["percentage"],
                        "comments": category_data["comments"],
                    }
                )

        return improvements

    def get_strengths(self):
        """Get areas that scored above 80%"""
        strengths = []

        for category_data in self.get_category_scores():
            if category_data["percentage"] >= 80:
                strengths.append(
                    {
                        "category": category_data["name"],
                        "score": category_data["percentage"],
                        "comments": category_data["comments"],
                    }
                )

        return strengths
