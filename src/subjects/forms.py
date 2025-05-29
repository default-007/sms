import json

from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from academics.models import AcademicYear, Class, Department, Grade, Term
from teachers.models import Teacher

from .models import Subject, SubjectAssignment, Syllabus, TopicProgress

User = get_user_model()


class SubjectForm(forms.ModelForm):
    """Form for creating and editing subjects."""

    class Meta:
        model = Subject
        fields = [
            "name",
            "code",
            "description",
            "department",
            "credit_hours",
            "is_elective",
            "grade_level",
            "is_active",
        ]
        widgets = {
            "name": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Enter subject name"}
            ),
            "code": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Enter subject code (e.g., MATH101)",
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": "Enter subject description",
                }
            ),
            "department": forms.Select(attrs={"class": "form-select"}),
            "credit_hours": forms.NumberInput(
                attrs={"class": "form-control", "min": 1, "max": 10}
            ),
            "is_elective": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "grade_level": forms.CheckboxSelectMultiple(
                attrs={"class": "form-check-input"}
            ),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, **kwargs):
        """Initialize form with dynamic grade choices."""
        super().__init__(*args, **kwargs)

        # Set grade level choices
        self.fields["grade_level"].queryset = Grade.objects.all().order_by(
            "order_sequence"
        )

        # Make fields required
        self.fields["name"].required = True
        self.fields["code"].required = True
        self.fields["department"].required = True

        # Add help text
        self.fields["grade_level"].help_text = _(
            "Select grades where this subject is applicable. Leave empty for all grades."
        )
        self.fields["credit_hours"].help_text = _("Number of credit hours (1-10)")
        self.fields["is_elective"].help_text = _("Check if this is an elective subject")

    def clean_code(self):
        """Validate subject code uniqueness."""
        code = self.cleaned_data.get("code")
        if code:
            code = code.upper()

            # Check for uniqueness
            queryset = Subject.objects.filter(code=code)
            if self.instance and self.instance.pk:
                queryset = queryset.exclude(pk=self.instance.pk)

            if queryset.exists():
                raise ValidationError(
                    _("Subject code '{}' already exists.").format(code)
                )

        return code

    def clean_grade_level(self):
        """Convert grade level to list of IDs."""
        grade_level = self.cleaned_data.get("grade_level")
        if grade_level:
            return [grade.id for grade in grade_level]
        return []

    def save(self, commit=True):
        """Save subject with proper grade level format."""
        subject = super().save(commit=False)
        subject.code = subject.code.upper()

        if commit:
            subject.save()

        return subject


class SyllabusForm(forms.ModelForm):
    """Form for creating and editing syllabi."""

    learning_objectives_text = forms.CharField(
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 4,
                "placeholder": "Enter each learning objective on a new line",
            }
        ),
        required=False,
        help_text=_("Enter each learning objective on a separate line"),
    )

    prerequisites_text = forms.CharField(
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 3,
                "placeholder": "Enter each prerequisite on a new line",
            }
        ),
        required=False,
        help_text=_("Enter each prerequisite on a separate line"),
    )

    assessment_methods_text = forms.CharField(
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 3,
                "placeholder": "Enter each assessment method on a new line",
            }
        ),
        required=False,
        help_text=_("Enter each assessment method on a separate line"),
    )

    class Meta:
        model = Syllabus
        fields = [
            "title",
            "description",
            "subject",
            "grade",
            "academic_year",
            "term",
            "estimated_duration_hours",
            "difficulty_level",
            "is_active",
        ]
        widgets = {
            "title": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Enter syllabus title"}
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 4,
                    "placeholder": "Enter syllabus description",
                }
            ),
            "subject": forms.Select(attrs={"class": "form-select"}),
            "grade": forms.Select(attrs={"class": "form-select"}),
            "academic_year": forms.Select(attrs={"class": "form-select"}),
            "term": forms.Select(attrs={"class": "form-select"}),
            "estimated_duration_hours": forms.NumberInput(
                attrs={"class": "form-control", "min": 0}
            ),
            "difficulty_level": forms.Select(attrs={"class": "form-select"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, **kwargs):
        """Initialize form with dynamic choices and data population."""
        super().__init__(*args, **kwargs)

        # Set querysets
        self.fields["subject"].queryset = Subject.objects.filter(is_active=True)
        self.fields["grade"].queryset = Grade.objects.all().order_by("order_sequence")
        self.fields["academic_year"].queryset = AcademicYear.objects.all().order_by(
            "-start_date"
        )
        self.fields["term"].queryset = Term.objects.all().order_by(
            "academic_year", "term_number"
        )

        # Populate text fields from JSON fields if editing
        if self.instance and self.instance.pk:
            if self.instance.learning_objectives:
                self.initial["learning_objectives_text"] = "\n".join(
                    self.instance.learning_objectives
                )

            if self.instance.prerequisites:
                self.initial["prerequisites_text"] = "\n".join(
                    self.instance.prerequisites
                )

            if self.instance.assessment_methods:
                self.initial["assessment_methods_text"] = "\n".join(
                    self.instance.assessment_methods
                )

    def clean(self):
        """Validate form data and check unique constraints."""
        cleaned_data = super().clean()

        subject = cleaned_data.get("subject")
        grade = cleaned_data.get("grade")
        academic_year = cleaned_data.get("academic_year")
        term = cleaned_data.get("term")

        # Check unique constraint
        if subject and grade and academic_year and term:
            queryset = Syllabus.objects.filter(
                subject=subject, grade=grade, academic_year=academic_year, term=term
            )

            if self.instance and self.instance.pk:
                queryset = queryset.exclude(pk=self.instance.pk)

            if queryset.exists():
                raise ValidationError(
                    _(
                        "A syllabus already exists for this subject, grade, and term combination."
                    )
                )

            # Check if subject is applicable for grade
            if not subject.is_applicable_for_grade(grade.id):
                raise ValidationError(
                    _("Subject '{}' is not applicable for grade '{}'.").format(
                        subject.name, grade.name
                    )
                )

            # Check if term belongs to academic year
            if term.academic_year != academic_year:
                raise ValidationError(
                    _("Term '{}' does not belong to academic year '{}'.").format(
                        term.name, academic_year.name
                    )
                )

        return cleaned_data

    def save(self, commit=True):
        """Save syllabus with processed JSON fields."""
        syllabus = super().save(commit=False)

        # Process text fields into JSON arrays
        learning_objectives_text = self.cleaned_data.get("learning_objectives_text", "")
        if learning_objectives_text:
            syllabus.learning_objectives = [
                obj.strip()
                for obj in learning_objectives_text.split("\n")
                if obj.strip()
            ]
        else:
            syllabus.learning_objectives = []

        prerequisites_text = self.cleaned_data.get("prerequisites_text", "")
        if prerequisites_text:
            syllabus.prerequisites = [
                req.strip() for req in prerequisites_text.split("\n") if req.strip()
            ]
        else:
            syllabus.prerequisites = []

        assessment_methods_text = self.cleaned_data.get("assessment_methods_text", "")
        if assessment_methods_text:
            syllabus.assessment_methods = [
                method.strip()
                for method in assessment_methods_text.split("\n")
                if method.strip()
            ]
        else:
            syllabus.assessment_methods = []

        if commit:
            syllabus.save()

        return syllabus


class SyllabusContentForm(forms.Form):
    """Form for managing syllabus content (topics, units, etc.)."""

    content_json = forms.CharField(
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 15,
                "placeholder": "Enter syllabus content in JSON format",
            }
        ),
        help_text=_("Enter syllabus content structure in JSON format"),
    )

    def __init__(self, *args, **kwargs):
        """Initialize with existing content if available."""
        self.syllabus = kwargs.pop("syllabus", None)
        super().__init__(*args, **kwargs)

        if self.syllabus and self.syllabus.content:
            self.initial["content_json"] = json.dumps(self.syllabus.content, indent=2)

    def clean_content_json(self):
        """Validate JSON content."""
        content_json = self.cleaned_data.get("content_json")

        if content_json:
            try:
                content = json.loads(content_json)

                # Validate content structure
                if not isinstance(content, dict):
                    raise ValidationError(_("Content must be a JSON object"))

                # Validate topics structure if present
                if "topics" in content:
                    if not isinstance(content["topics"], list):
                        raise ValidationError(_("Topics must be a list"))

                    for i, topic in enumerate(content["topics"]):
                        if not isinstance(topic, dict):
                            raise ValidationError(
                                _("Topic {} must be an object").format(i + 1)
                            )

                        if "name" not in topic:
                            raise ValidationError(
                                _("Topic {} must have a 'name' field").format(i + 1)
                            )

                return content

            except json.JSONDecodeError as e:
                raise ValidationError(_("Invalid JSON format: {}").format(str(e)))

        return {}


class TopicProgressForm(forms.ModelForm):
    """Form for updating topic progress."""

    class Meta:
        model = TopicProgress
        fields = [
            "topic_name",
            "is_completed",
            "completion_date",
            "hours_taught",
            "teaching_method",
            "notes",
        ]
        widgets = {
            "topic_name": forms.TextInput(
                attrs={"class": "form-control", "readonly": True}
            ),
            "is_completed": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "completion_date": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}
            ),
            "hours_taught": forms.NumberInput(
                attrs={"class": "form-control", "min": 0, "step": 0.5}
            ),
            "teaching_method": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "e.g., Interactive, Lecture, Practical",
                }
            ),
            "notes": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": "Enter any notes about teaching this topic",
                }
            ),
        }

    def clean(self):
        """Validate completion data."""
        cleaned_data = super().clean()

        is_completed = cleaned_data.get("is_completed")
        completion_date = cleaned_data.get("completion_date")

        if is_completed and not completion_date:
            # Auto-set completion date to today
            from datetime import date

            cleaned_data["completion_date"] = date.today()

        return cleaned_data


class SubjectAssignmentForm(forms.ModelForm):
    """Form for creating and editing subject assignments."""

    class Meta:
        model = SubjectAssignment
        fields = [
            "subject",
            "teacher",
            "class_assigned",
            "academic_year",
            "term",
            "is_primary_teacher",
            "is_active",
        ]
        widgets = {
            "subject": forms.Select(attrs={"class": "form-select"}),
            "teacher": forms.Select(attrs={"class": "form-select"}),
            "class_assigned": forms.Select(attrs={"class": "form-select"}),
            "academic_year": forms.Select(attrs={"class": "form-select"}),
            "term": forms.Select(attrs={"class": "form-select"}),
            "is_primary_teacher": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, **kwargs):
        """Initialize form with filtered querysets."""
        super().__init__(*args, **kwargs)

        # Set querysets
        self.fields["subject"].queryset = Subject.objects.filter(is_active=True)
        self.fields["teacher"].queryset = Teacher.objects.filter(status="Active")
        self.fields["class_assigned"].queryset = Class.objects.all()
        self.fields["academic_year"].queryset = AcademicYear.objects.all().order_by(
            "-start_date"
        )
        self.fields["term"].queryset = Term.objects.all().order_by(
            "academic_year", "term_number"
        )

        # Add help text
        self.fields["is_primary_teacher"].help_text = _(
            "Check if this teacher is the primary instructor for this subject"
        )

    def clean(self):
        """Validate assignment data."""
        cleaned_data = super().clean()

        subject = cleaned_data.get("subject")
        class_assigned = cleaned_data.get("class_assigned")
        academic_year = cleaned_data.get("academic_year")
        term = cleaned_data.get("term")

        if subject and class_assigned:
            # Check if subject is applicable for the class's grade
            if not subject.is_applicable_for_grade(class_assigned.grade.id):
                raise ValidationError(
                    _("Subject '{}' is not applicable for grade '{}'.").format(
                        subject.name, class_assigned.grade.name
                    )
                )

        if term and academic_year:
            # Check if term belongs to academic year
            if term.academic_year != academic_year:
                raise ValidationError(
                    _("Term '{}' does not belong to academic year '{}'.").format(
                        term.name, academic_year.name
                    )
                )

        # Check for existing assignment (except when updating)
        if subject and class_assigned and academic_year and term:
            queryset = SubjectAssignment.objects.filter(
                subject=subject,
                class_assigned=class_assigned,
                academic_year=academic_year,
                term=term,
                is_active=True,
            )

            if self.instance and self.instance.pk:
                queryset = queryset.exclude(pk=self.instance.pk)

            if queryset.exists():
                raise ValidationError(
                    _(
                        "An assignment already exists for this subject, class, and term combination."
                    )
                )

        return cleaned_data


class BulkSubjectImportForm(forms.Form):
    """Form for bulk importing subjects from file."""

    department = forms.ModelChoiceField(
        queryset=Department.objects.all(),
        widget=forms.Select(attrs={"class": "form-select"}),
        help_text=_("Select the department for all imported subjects"),
    )

    subjects_file = forms.FileField(
        widget=forms.FileInput(
            attrs={"class": "form-control", "accept": ".csv,.xlsx,.xls"}
        ),
        help_text=_("Upload CSV or Excel file with subject data"),
    )

    overwrite_existing = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
        help_text=_("Check to overwrite existing subjects with the same code"),
    )

    def clean_subjects_file(self):
        """Validate uploaded file."""
        file = self.cleaned_data.get("subjects_file")

        if file:
            # Check file size (limit to 5MB)
            if file.size > 5 * 1024 * 1024:
                raise ValidationError(_("File size cannot exceed 5MB"))

            # Check file extension
            allowed_extensions = [".csv", ".xlsx", ".xls"]
            file_extension = "." + file.name.split(".")[-1].lower()

            if file_extension not in allowed_extensions:
                raise ValidationError(_("Only CSV and Excel files are allowed"))

        return file


class SyllabusFilterForm(forms.Form):
    """Form for filtering syllabi in list views."""

    subject = forms.ModelChoiceField(
        queryset=Subject.objects.filter(is_active=True),
        required=False,
        empty_label="All Subjects",
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    grade = forms.ModelChoiceField(
        queryset=Grade.objects.all().order_by("order_sequence"),
        required=False,
        empty_label="All Grades",
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    academic_year = forms.ModelChoiceField(
        queryset=AcademicYear.objects.all().order_by("-start_date"),
        required=False,
        empty_label="All Academic Years",
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    term = forms.ModelChoiceField(
        queryset=Term.objects.all().order_by("academic_year", "term_number"),
        required=False,
        empty_label="All Terms",
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    completion_status = forms.ChoiceField(
        choices=[
            ("", "All Status"),
            ("not_started", "Not Started"),
            ("in_progress", "In Progress"),
            ("nearing_completion", "Nearing Completion"),
            ("completed", "Completed"),
        ],
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    difficulty_level = forms.ChoiceField(
        choices=[
            ("", "All Levels"),
            ("beginner", "Beginner"),
            ("intermediate", "Intermediate"),
            ("advanced", "Advanced"),
            ("expert", "Expert"),
        ],
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )


class AnalyticsFilterForm(forms.Form):
    """Form for filtering analytics data."""

    academic_year = forms.ModelChoiceField(
        queryset=AcademicYear.objects.all().order_by("-start_date"),
        widget=forms.Select(attrs={"class": "form-select"}),
        help_text=_("Select academic year for analysis"),
    )

    department = forms.ModelChoiceField(
        queryset=Department.objects.all(),
        required=False,
        empty_label="All Departments",
        widget=forms.Select(attrs={"class": "form-select"}),
        help_text=_("Optional: Filter by specific department"),
    )

    grade = forms.ModelChoiceField(
        queryset=Grade.objects.all().order_by("order_sequence"),
        required=False,
        empty_label="All Grades",
        widget=forms.Select(attrs={"class": "form-select"}),
        help_text=_("Optional: Filter by specific grade"),
    )

    term = forms.ModelChoiceField(
        queryset=Term.objects.all().order_by("academic_year", "term_number"),
        required=False,
        empty_label="All Terms",
        widget=forms.Select(attrs={"class": "form-select"}),
        help_text=_("Optional: Filter by specific term"),
    )

    analysis_type = forms.ChoiceField(
        choices=[
            ("overview", "Overview Analytics"),
            ("department", "Department Performance"),
            ("teacher", "Teacher Performance"),
            ("trends", "Curriculum Trends"),
            ("forecast", "Completion Forecasting"),
        ],
        widget=forms.Select(attrs={"class": "form-select"}),
        help_text=_("Select type of analysis to perform"),
    )

    def __init__(self, *args, **kwargs):
        """Initialize with current academic year as default."""
        super().__init__(*args, **kwargs)

        # Set current academic year as default
        current_year = AcademicYear.objects.filter(is_current=True).first()
        if current_year:
            self.initial["academic_year"] = current_year


class QuickTopicAddForm(forms.Form):
    """Quick form for adding topics to syllabus content."""

    topic_name = forms.CharField(
        max_length=300,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Enter topic name"}
        ),
    )

    topic_description = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 2,
                "placeholder": "Optional: Enter topic description",
            }
        ),
    )

    estimated_hours = forms.DecimalField(
        required=False,
        max_digits=5,
        decimal_places=2,
        widget=forms.NumberInput(
            attrs={
                "class": "form-control",
                "min": 0,
                "step": 0.5,
                "placeholder": "Estimated hours",
            }
        ),
    )


class BulkTopicCompletionForm(forms.Form):
    """Form for marking multiple topics as completed."""

    topics = forms.CharField(
        widget=forms.HiddenInput(),
        help_text=_("JSON array of topic indices to mark as completed"),
    )

    completion_date = forms.DateField(
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
        help_text=_("Date when topics were completed"),
    )

    hours_taught = forms.DecimalField(
        required=False,
        max_digits=5,
        decimal_places=2,
        widget=forms.NumberInput(
            attrs={
                "class": "form-control",
                "min": 0,
                "step": 0.5,
                "placeholder": "Total hours taught",
            }
        ),
        help_text=_("Total hours taught for all selected topics"),
    )

    teaching_method = forms.CharField(
        required=False,
        max_length=100,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "e.g., Interactive, Lecture, Practical",
            }
        ),
        help_text=_("Teaching method used for these topics"),
    )

    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 3,
                "placeholder": "Enter any notes about teaching these topics",
            }
        ),
        help_text=_("Additional notes about the completion"),
    )

    def clean_topics(self):
        """Validate topics JSON."""
        topics_json = self.cleaned_data.get("topics")

        try:
            topics = json.loads(topics_json)

            if not isinstance(topics, list):
                raise ValidationError(_("Topics must be a list"))

            if not topics:
                raise ValidationError(_("At least one topic must be selected"))

            # Validate all items are integers
            for topic in topics:
                if not isinstance(topic, int) or topic < 0:
                    raise ValidationError(_("Invalid topic index"))

            return topics

        except json.JSONDecodeError:
            raise ValidationError(_("Invalid topics data"))

    def __init__(self, *args, **kwargs):
        """Initialize with current date as default."""
        super().__init__(*args, **kwargs)

        from datetime import date

        self.initial["completion_date"] = date.today()
