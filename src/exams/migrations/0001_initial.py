"""
School Management System - Exam Initial Migration
File: src/exams/migrations/0001_initial.py
"""

# Generated migration file for the exams app

import uuid

import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("academics", "0001_initial"),
        ("subjects", "0001_initial"),
        ("students", "0001_initial"),
        ("teachers", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ExamType",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("name", models.CharField(max_length=100, unique=True)),
                ("description", models.TextField(blank=True)),
                (
                    "contribution_percentage",
                    models.DecimalField(
                        decimal_places=2,
                        help_text="Percentage contribution to final grade",
                        max_digits=5,
                        validators=[
                            django.core.validators.MinValueValidator(0),
                            django.core.validators.MaxValueValidator(100),
                        ],
                    ),
                ),
                ("is_term_based", models.BooleanField(default=True)),
                (
                    "frequency",
                    models.CharField(
                        choices=[
                            ("DAILY", "Daily"),
                            ("WEEKLY", "Weekly"),
                            ("MONTHLY", "Monthly"),
                            ("TERMLY", "Termly"),
                            ("YEARLY", "Yearly"),
                        ],
                        default="TERMLY",
                        max_length=20,
                    ),
                ),
                ("max_attempts", models.PositiveIntegerField(default=1)),
                ("is_online", models.BooleanField(default=False)),
                (
                    "duration_minutes",
                    models.PositiveIntegerField(blank=True, null=True),
                ),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "exam_types",
                "ordering": ["contribution_percentage", "name"],
            },
        ),
        migrations.CreateModel(
            name="GradingSystem",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("name", models.CharField(max_length=100)),
                ("description", models.TextField(blank=True)),
                ("is_default", models.BooleanField(default=False)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "academic_year",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="grading_systems",
                        to="academics.academicyear",
                    ),
                ),
            ],
            options={
                "db_table": "grading_systems",
            },
        ),
        migrations.CreateModel(
            name="Exam",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("name", models.CharField(max_length=200)),
                ("start_date", models.DateField()),
                ("end_date", models.DateField()),
                ("description", models.TextField(blank=True)),
                (
                    "instructions",
                    models.TextField(
                        blank=True, help_text="General instructions for students"
                    ),
                ),
                (
                    "passing_percentage",
                    models.DecimalField(
                        decimal_places=2,
                        default=40.00,
                        max_digits=5,
                        validators=[
                            django.core.validators.MinValueValidator(0),
                            django.core.validators.MaxValueValidator(100),
                        ],
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("DRAFT", "Draft"),
                            ("SCHEDULED", "Scheduled"),
                            ("ONGOING", "Ongoing"),
                            ("COMPLETED", "Completed"),
                            ("CANCELLED", "Cancelled"),
                            ("POSTPONED", "Postponed"),
                        ],
                        default="DRAFT",
                        max_length=20,
                    ),
                ),
                ("is_published", models.BooleanField(default=False)),
                ("publish_results", models.BooleanField(default=False)),
                ("total_students", models.PositiveIntegerField(default=0)),
                ("completed_count", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "academic_year",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="exams",
                        to="academics.academicyear",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="created_exams",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "exam_type",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="exams",
                        to="exams.examtype",
                    ),
                ),
                (
                    "grading_system",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to="exams.gradingsystem",
                    ),
                ),
                (
                    "term",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="exams",
                        to="academics.term",
                    ),
                ),
            ],
            options={
                "db_table": "exams",
                "ordering": ["-start_date", "name"],
            },
        ),
        migrations.CreateModel(
            name="ExamSchedule",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("date", models.DateField()),
                ("start_time", models.TimeField()),
                ("end_time", models.TimeField()),
                ("duration_minutes", models.PositiveIntegerField()),
                ("room", models.CharField(blank=True, max_length=100)),
                ("total_marks", models.PositiveIntegerField()),
                ("passing_marks", models.PositiveIntegerField()),
                ("special_instructions", models.TextField(blank=True)),
                (
                    "materials_allowed",
                    models.TextField(
                        blank=True, help_text="Calculator, formula sheet, etc."
                    ),
                ),
                ("is_active", models.BooleanField(default=True)),
                ("is_completed", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "additional_supervisors",
                    models.ManyToManyField(
                        blank=True,
                        related_name="additional_supervised_exams",
                        to="teachers.teacher",
                    ),
                ),
                (
                    "class_obj",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="exam_schedules",
                        to="academics.class",
                    ),
                ),
                (
                    "exam",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="schedules",
                        to="exams.exam",
                    ),
                ),
                (
                    "subject",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="exam_schedules",
                        to="subjects.subject",
                    ),
                ),
                (
                    "supervisor",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="supervised_exams",
                        to="teachers.teacher",
                    ),
                ),
            ],
            options={
                "db_table": "exam_schedules",
                "ordering": ["date", "start_time"],
            },
        ),
        migrations.CreateModel(
            name="StudentExamResult",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "marks_obtained",
                    models.DecimalField(
                        decimal_places=2,
                        max_digits=6,
                        validators=[django.core.validators.MinValueValidator(0)],
                    ),
                ),
                (
                    "percentage",
                    models.DecimalField(
                        decimal_places=2,
                        max_digits=5,
                        validators=[
                            django.core.validators.MinValueValidator(0),
                            django.core.validators.MaxValueValidator(100),
                        ],
                    ),
                ),
                (
                    "grade",
                    models.CharField(
                        choices=[
                            ("A+", "A+ (90-100)"),
                            ("A", "A (80-89)"),
                            ("B+", "B+ (70-79)"),
                            ("B", "B (60-69)"),
                            ("C+", "C+ (50-59)"),
                            ("C", "C (40-49)"),
                            ("D", "D (30-39)"),
                            ("F", "F (0-29)"),
                        ],
                        max_length=2,
                    ),
                ),
                (
                    "grade_point",
                    models.DecimalField(
                        blank=True, decimal_places=2, max_digits=3, null=True
                    ),
                ),
                ("is_pass", models.BooleanField()),
                ("is_absent", models.BooleanField(default=False)),
                ("is_exempted", models.BooleanField(default=False)),
                ("remarks", models.TextField(blank=True)),
                ("teacher_comments", models.TextField(blank=True)),
                ("class_rank", models.PositiveIntegerField(blank=True, null=True)),
                ("grade_rank", models.PositiveIntegerField(blank=True, null=True)),
                ("entry_date", models.DateTimeField(auto_now_add=True)),
                ("last_modified_at", models.DateTimeField(auto_now=True)),
                (
                    "entered_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="entered_results",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "exam_schedule",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="student_results",
                        to="exams.examschedule",
                    ),
                ),
                (
                    "last_modified_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="modified_results",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "student",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="exam_results",
                        to="students.student",
                    ),
                ),
                (
                    "term",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="exam_results",
                        to="academics.term",
                    ),
                ),
            ],
            options={
                "db_table": "student_exam_results",
                "ordering": ["-percentage", "student__user__last_name"],
            },
        ),
        migrations.CreateModel(
            name="ReportCard",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("total_marks", models.PositiveIntegerField()),
                ("marks_obtained", models.DecimalField(decimal_places=2, max_digits=8)),
                ("percentage", models.DecimalField(decimal_places=2, max_digits=5)),
                ("grade", models.CharField(max_length=2)),
                (
                    "grade_point_average",
                    models.DecimalField(decimal_places=2, max_digits=4),
                ),
                ("class_rank", models.PositiveIntegerField()),
                ("class_size", models.PositiveIntegerField()),
                ("grade_rank", models.PositiveIntegerField(blank=True, null=True)),
                ("grade_size", models.PositiveIntegerField(blank=True, null=True)),
                (
                    "attendance_percentage",
                    models.DecimalField(decimal_places=2, max_digits=5),
                ),
                ("days_present", models.PositiveIntegerField()),
                ("days_absent", models.PositiveIntegerField()),
                ("total_days", models.PositiveIntegerField()),
                ("class_teacher_remarks", models.TextField(blank=True)),
                ("principal_remarks", models.TextField(blank=True)),
                ("achievements", models.TextField(blank=True)),
                ("areas_for_improvement", models.TextField(blank=True)),
                ("generation_date", models.DateTimeField(auto_now_add=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("DRAFT", "Draft"),
                            ("PUBLISHED", "Published"),
                            ("ARCHIVED", "Archived"),
                        ],
                        default="DRAFT",
                        max_length=20,
                    ),
                ),
                ("published_date", models.DateTimeField(blank=True, null=True)),
                (
                    "academic_year",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="report_cards",
                        to="academics.academicyear",
                    ),
                ),
                (
                    "class_obj",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="report_cards",
                        to="academics.class",
                    ),
                ),
                (
                    "student",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="report_cards",
                        to="students.student",
                    ),
                ),
                (
                    "term",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="report_cards",
                        to="academics.term",
                    ),
                ),
            ],
            options={
                "db_table": "report_cards",
                "ordering": [
                    "-academic_year__start_date",
                    "-term__term_number",
                    "class_rank",
                ],
            },
        ),
        migrations.CreateModel(
            name="ExamQuestion",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("question_text", models.TextField()),
                (
                    "question_type",
                    models.CharField(
                        choices=[
                            ("MCQ", "Multiple Choice"),
                            ("TF", "True/False"),
                            ("SA", "Short Answer"),
                            ("LA", "Long Answer"),
                            ("FB", "Fill in the Blanks"),
                            ("ESSAY", "Essay"),
                        ],
                        max_length=10,
                    ),
                ),
                (
                    "difficulty_level",
                    models.CharField(
                        choices=[
                            ("EASY", "Easy"),
                            ("MEDIUM", "Medium"),
                            ("HARD", "Hard"),
                        ],
                        max_length=10,
                    ),
                ),
                ("marks", models.PositiveIntegerField(default=1)),
                (
                    "options",
                    models.JSONField(
                        blank=True, help_text="Array of options for MCQ", null=True
                    ),
                ),
                (
                    "correct_answer",
                    models.TextField(help_text="Correct answer or answer key"),
                ),
                ("explanation", models.TextField(blank=True)),
                ("topic", models.CharField(blank=True, max_length=200)),
                ("learning_objective", models.CharField(blank=True, max_length=200)),
                ("is_active", models.BooleanField(default=True)),
                ("usage_count", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="created_questions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "grade",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="exam_questions",
                        to="academics.grade",
                    ),
                ),
                (
                    "subject",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="exam_questions",
                        to="subjects.subject",
                    ),
                ),
            ],
            options={
                "db_table": "exam_questions",
                "ordering": ["subject", "difficulty_level", "topic"],
            },
        ),
        migrations.CreateModel(
            name="OnlineExam",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("time_limit_minutes", models.PositiveIntegerField()),
                ("max_attempts", models.PositiveIntegerField(default=1)),
                ("shuffle_questions", models.BooleanField(default=True)),
                ("shuffle_options", models.BooleanField(default=True)),
                ("show_results_immediately", models.BooleanField(default=False)),
                ("enable_proctoring", models.BooleanField(default=False)),
                ("webcam_required", models.BooleanField(default=False)),
                ("fullscreen_required", models.BooleanField(default=True)),
                ("access_code", models.CharField(blank=True, max_length=20)),
                (
                    "ip_restrictions",
                    models.TextField(
                        blank=True, help_text="Comma-separated IP addresses"
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "exam_schedule",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="online_exam",
                        to="exams.examschedule",
                    ),
                ),
            ],
            options={
                "db_table": "online_exams",
            },
        ),
        migrations.CreateModel(
            name="OnlineExamQuestion",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("order", models.PositiveIntegerField()),
                ("marks", models.PositiveIntegerField()),
                (
                    "online_exam",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="exams.onlineexam",
                    ),
                ),
                (
                    "question",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="exams.examquestion",
                    ),
                ),
            ],
            options={
                "db_table": "online_exam_questions",
                "ordering": ["order"],
            },
        ),
        migrations.CreateModel(
            name="StudentOnlineExamAttempt",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("attempt_number", models.PositiveIntegerField()),
                ("start_time", models.DateTimeField(auto_now_add=True)),
                ("submit_time", models.DateTimeField(blank=True, null=True)),
                (
                    "time_remaining_seconds",
                    models.PositiveIntegerField(blank=True, null=True),
                ),
                (
                    "responses",
                    models.JSONField(
                        default=dict, help_text="Question ID to answer mapping"
                    ),
                ),
                ("total_marks", models.PositiveIntegerField(default=0)),
                (
                    "marks_obtained",
                    models.DecimalField(decimal_places=2, default=0, max_digits=6),
                ),
                (
                    "auto_graded_marks",
                    models.DecimalField(decimal_places=2, default=0, max_digits=6),
                ),
                (
                    "manual_graded_marks",
                    models.DecimalField(decimal_places=2, default=0, max_digits=6),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("STARTED", "Started"),
                            ("IN_PROGRESS", "In Progress"),
                            ("SUBMITTED", "Submitted"),
                            ("TIMED_OUT", "Timed Out"),
                            ("CANCELLED", "Cancelled"),
                        ],
                        default="STARTED",
                        max_length=20,
                    ),
                ),
                ("is_graded", models.BooleanField(default=False)),
                ("proctoring_data", models.JSONField(blank=True, null=True)),
                ("violation_count", models.PositiveIntegerField(default=0)),
                (
                    "online_exam",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="student_attempts",
                        to="exams.onlineexam",
                    ),
                ),
                (
                    "student",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="online_exam_attempts",
                        to="students.student",
                    ),
                ),
            ],
            options={
                "db_table": "student_online_exam_attempts",
                "ordering": ["-start_time"],
            },
        ),
        migrations.CreateModel(
            name="GradeScale",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("grade_name", models.CharField(max_length=5)),
                (
                    "min_percentage",
                    models.DecimalField(
                        decimal_places=2,
                        max_digits=5,
                        validators=[
                            django.core.validators.MinValueValidator(0),
                            django.core.validators.MaxValueValidator(100),
                        ],
                    ),
                ),
                (
                    "max_percentage",
                    models.DecimalField(
                        decimal_places=2,
                        max_digits=5,
                        validators=[
                            django.core.validators.MinValueValidator(0),
                            django.core.validators.MaxValueValidator(100),
                        ],
                    ),
                ),
                ("grade_point", models.DecimalField(decimal_places=2, max_digits=3)),
                ("description", models.CharField(blank=True, max_length=100)),
                (
                    "color_code",
                    models.CharField(
                        blank=True, help_text="Hex color code for UI", max_length=7
                    ),
                ),
                (
                    "grading_system",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="grade_scales",
                        to="exams.gradingsystem",
                    ),
                ),
            ],
            options={
                "db_table": "grade_scales",
                "ordering": ["-min_percentage"],
            },
        ),
        # Add unique constraints
        migrations.AddConstraint(
            model_name="exam",
            constraint=models.UniqueConstraint(
                fields=["name", "academic_year", "term"], name="unique_exam_per_term"
            ),
        ),
        migrations.AddConstraint(
            model_name="examschedule",
            constraint=models.UniqueConstraint(
                fields=["exam", "class_obj", "subject"], name="unique_exam_schedule"
            ),
        ),
        migrations.AddConstraint(
            model_name="studentexamresult",
            constraint=models.UniqueConstraint(
                fields=["student", "exam_schedule"], name="unique_student_result"
            ),
        ),
        migrations.AddConstraint(
            model_name="reportcard",
            constraint=models.UniqueConstraint(
                fields=["student", "academic_year", "term"], name="unique_report_card"
            ),
        ),
        migrations.AddConstraint(
            model_name="gradingsystem",
            constraint=models.UniqueConstraint(
                fields=["academic_year", "name"], name="unique_grading_system"
            ),
        ),
        migrations.AddConstraint(
            model_name="gradescale",
            constraint=models.UniqueConstraint(
                fields=["grading_system", "grade_name"], name="unique_grade_scale"
            ),
        ),
        migrations.AddConstraint(
            model_name="onlineexamquestion",
            constraint=models.UniqueConstraint(
                fields=["online_exam", "question"], name="unique_online_exam_question"
            ),
        ),
        migrations.AddConstraint(
            model_name="studentonlineexamattempt",
            constraint=models.UniqueConstraint(
                fields=["student", "online_exam", "attempt_number"],
                name="unique_exam_attempt",
            ),
        ),
    ]
