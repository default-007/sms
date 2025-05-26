"""
Django Forms for Academics Module

This module provides Django forms for web interface interactions,
including creation and editing forms for academic entities.
"""

from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from .models import AcademicYear, Class, Department, Grade, Section, Term
from .services import AcademicYearService, ClassService, GradeService, SectionService

User = get_user_model()


class DepartmentForm(forms.ModelForm):
    """Form for creating/editing departments"""

    class Meta:
        model = Department
        fields = ["name", "description", "head", "is_active"]
        widgets = {
            "name": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Enter department name"}
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": "Enter department description",
                }
            ),
            "head": forms.Select(attrs={"class": "form-control"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter head choices to active teachers only
        try:
            from teachers.models import Teacher

            self.fields["head"].queryset = Teacher.objects.filter(status="Active")
            self.fields["head"].empty_label = "Select Department Head"
        except ImportError:
            # Teachers module not available
            self.fields["head"].widget = forms.HiddenInput()


class AcademicYearForm(forms.ModelForm):
    """Form for creating/editing academic years"""

    create_terms = forms.BooleanField(
        required=False,
        initial=True,
        label="Create default terms",
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )

    num_terms = forms.ChoiceField(
        choices=[(2, "2 Terms"), (3, "3 Terms"), (4, "4 Terms")],
        initial=3,
        required=False,
        label="Number of terms",
        widget=forms.Select(attrs={"class": "form-control"}),
    )

    class Meta:
        model = AcademicYear
        fields = ["name", "start_date", "end_date", "is_current"]
        widgets = {
            "name": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "e.g., 2024-2025"}
            ),
            "start_date": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}
            ),
            "end_date": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}
            ),
            "is_current": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def clean(self):
        """Validate form data"""
        cleaned_data = super().clean()
        start_date = cleaned_data.get("start_date")
        end_date = cleaned_data.get("end_date")

        if start_date and end_date:
            if start_date >= end_date:
                raise ValidationError("Start date must be before end date")

            # Check for overlapping academic years
            overlapping = AcademicYear.objects.filter(
                start_date__lte=end_date, end_date__gte=start_date
            )

            if self.instance.pk:
                overlapping = overlapping.exclude(pk=self.instance.pk)

            if overlapping.exists():
                raise ValidationError(
                    f"Academic year dates overlap with: {overlapping.first().name}"
                )

        return cleaned_data

    def save(self, commit=True):
        """Save academic year and optionally create terms"""
        if not commit:
            return super().save(commit=False)

        # Get the user from the form's initial data or context
        user = getattr(self, "user", None)
        if not user:
            # Fallback to first admin user
            user = User.objects.filter(is_superuser=True).first()

        create_terms = self.cleaned_data.get("create_terms", False)
        num_terms = int(self.cleaned_data.get("num_terms", 3))

        if create_terms and not self.instance.pk:
            # Creating new academic year with terms
            academic_year = AcademicYearService.setup_academic_year_with_terms(
                name=self.cleaned_data["name"],
                start_date=self.cleaned_data["start_date"],
                end_date=self.cleaned_data["end_date"],
                num_terms=num_terms,
                user=user,
                is_current=self.cleaned_data.get("is_current", False),
            )
            return academic_year
        else:
            # Regular save
            return super().save(commit=True)


class TermForm(forms.ModelForm):
    """Form for creating/editing terms"""

    class Meta:
        model = Term
        fields = [
            "academic_year",
            "name",
            "term_number",
            "start_date",
            "end_date",
            "is_current",
        ]
        widgets = {
            "academic_year": forms.Select(attrs={"class": "form-control"}),
            "name": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "e.g., First Term"}
            ),
            "term_number": forms.Select(attrs={"class": "form-control"}),
            "start_date": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}
            ),
            "end_date": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}
            ),
            "is_current": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def clean(self):
        """Validate term dates"""
        cleaned_data = super().clean()
        academic_year = cleaned_data.get("academic_year")
        start_date = cleaned_data.get("start_date")
        end_date = cleaned_data.get("end_date")
        term_number = cleaned_data.get("term_number")

        if start_date and end_date:
            if start_date >= end_date:
                raise ValidationError("Start date must be before end date")

        if academic_year and start_date and end_date:
            # Check if dates are within academic year
            if (
                start_date < academic_year.start_date
                or end_date > academic_year.end_date
            ):
                raise ValidationError("Term dates must be within academic year dates")

        if academic_year and term_number:
            # Check for duplicate term number
            existing = Term.objects.filter(
                academic_year=academic_year, term_number=term_number
            )
            if self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)

            if existing.exists():
                raise ValidationError(
                    f"Term {term_number} already exists in this academic year"
                )

        return cleaned_data


class SectionForm(forms.ModelForm):
    """Form for creating/editing sections"""

    class Meta:
        model = Section
        fields = ["name", "description", "department", "order_sequence", "is_active"]
        widgets = {
            "name": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "e.g., Lower Primary"}
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": "Enter section description",
                }
            ),
            "department": forms.Select(attrs={"class": "form-control"}),
            "order_sequence": forms.NumberInput(
                attrs={"class": "form-control", "min": "1"}
            ),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["department"].queryset = Department.objects.filter(is_active=True)
        self.fields["department"].empty_label = "Select Department (Optional)"


class GradeForm(forms.ModelForm):
    """Form for creating/editing grades"""

    class Meta:
        model = Grade
        fields = [
            "section",
            "name",
            "description",
            "department",
            "order_sequence",
            "minimum_age",
            "maximum_age",
            "is_active",
        ]
        widgets = {
            "section": forms.Select(attrs={"class": "form-control"}),
            "name": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "e.g., Grade 1"}
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 2,
                    "placeholder": "Enter grade description",
                }
            ),
            "department": forms.Select(attrs={"class": "form-control"}),
            "order_sequence": forms.NumberInput(
                attrs={"class": "form-control", "min": "1"}
            ),
            "minimum_age": forms.NumberInput(
                attrs={"class": "form-control", "min": "3", "max": "25"}
            ),
            "maximum_age": forms.NumberInput(
                attrs={"class": "form-control", "min": "3", "max": "25"}
            ),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["section"].queryset = Section.objects.filter(is_active=True)
        self.fields["department"].queryset = Department.objects.filter(is_active=True)
        self.fields["department"].empty_label = "Select Department (Optional)"

    def clean(self):
        """Validate grade data"""
        cleaned_data = super().clean()
        minimum_age = cleaned_data.get("minimum_age")
        maximum_age = cleaned_data.get("maximum_age")
        section = cleaned_data.get("section")
        name = cleaned_data.get("name")

        if minimum_age and maximum_age:
            if minimum_age >= maximum_age:
                raise ValidationError("Minimum age must be less than maximum age")

        if section and name:
            # Check for duplicate grade name in section
            existing = Grade.objects.filter(section=section, name=name)
            if self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)

            if existing.exists():
                raise ValidationError(
                    f"Grade '{name}' already exists in {section.name}"
                )

        return cleaned_data


class ClassForm(forms.ModelForm):
    """Form for creating/editing classes"""

    class Meta:
        model = Class
        fields = [
            "grade",
            "name",
            "academic_year",
            "room_number",
            "capacity",
            "class_teacher",
            "is_active",
        ]
        widgets = {
            "grade": forms.Select(attrs={"class": "form-control"}),
            "name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "e.g., A, B, North, Blue",
                }
            ),
            "academic_year": forms.Select(attrs={"class": "form-control"}),
            "room_number": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "e.g., 101, A-12"}
            ),
            "capacity": forms.NumberInput(
                attrs={"class": "form-control", "min": "1", "max": "100", "value": "30"}
            ),
            "class_teacher": forms.Select(attrs={"class": "form-control"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["grade"].queryset = Grade.objects.filter(
            is_active=True
        ).select_related("section")
        self.fields["academic_year"].queryset = AcademicYear.objects.all().order_by(
            "-start_date"
        )

        # Filter teachers
        try:
            from teachers.models import Teacher

            self.fields["class_teacher"].queryset = Teacher.objects.filter(
                status="Active"
            )
            self.fields["class_teacher"].empty_label = "Select Class Teacher (Optional)"
        except ImportError:
            self.fields["class_teacher"].widget = forms.HiddenInput()

    def clean(self):
        """Validate class data"""
        cleaned_data = super().clean()
        grade = cleaned_data.get("grade")
        name = cleaned_data.get("name")
        academic_year = cleaned_data.get("academic_year")
        class_teacher = cleaned_data.get("class_teacher")
        capacity = cleaned_data.get("capacity")

        if grade and name and academic_year:
            # Check for duplicate class name in grade and academic year
            existing = Class.objects.filter(
                grade=grade, name=name, academic_year=academic_year
            )
            if self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)

            if existing.exists():
                raise ValidationError(
                    f"Class '{name}' already exists in {grade.name} for {academic_year.name}"
                )

        if class_teacher and academic_year:
            # Check if teacher is already assigned as class teacher
            existing_assignment = Class.objects.filter(
                class_teacher=class_teacher, academic_year=academic_year, is_active=True
            )
            if self.instance.pk:
                existing_assignment = existing_assignment.exclude(pk=self.instance.pk)

            if existing_assignment.exists():
                raise ValidationError(
                    f"Teacher is already assigned as class teacher for another class in {academic_year.name}"
                )

        if capacity and capacity < 1:
            raise ValidationError("Capacity must be at least 1")

        return cleaned_data


class BulkClassCreateForm(forms.Form):
    """Form for creating multiple classes at once"""

    grade = forms.ModelChoiceField(
        queryset=Grade.objects.filter(is_active=True),
        widget=forms.Select(attrs={"class": "form-control"}),
        empty_label="Select Grade",
    )

    academic_year = forms.ModelChoiceField(
        queryset=AcademicYear.objects.all().order_by("-start_date"),
        widget=forms.Select(attrs={"class": "form-control"}),
        empty_label="Select Academic Year",
    )

    class_names = forms.CharField(
        max_length=200,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "e.g., A, B, C or North, South, East",
            }
        ),
        help_text="Enter class names separated by commas",
    )

    default_capacity = forms.IntegerField(
        min_value=1,
        max_value=100,
        initial=30,
        widget=forms.NumberInput(attrs={"class": "form-control"}),
    )

    room_prefix = forms.CharField(
        max_length=10,
        required=False,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "e.g., 1, A-"}
        ),
        help_text="Optional prefix for room numbers",
    )

    def clean_class_names(self):
        """Validate and parse class names"""
        class_names = self.cleaned_data["class_names"]
        names = [name.strip() for name in class_names.split(",") if name.strip()]

        if not names:
            raise ValidationError("At least one class name is required")

        if len(names) > 10:
            raise ValidationError("Maximum 10 classes can be created at once")

        # Check for duplicates
        if len(names) != len(set(names)):
            raise ValidationError("Duplicate class names are not allowed")

        return names

    def clean(self):
        """Validate form data"""
        cleaned_data = super().clean()
        grade = cleaned_data.get("grade")
        academic_year = cleaned_data.get("academic_year")
        class_names = cleaned_data.get("class_names", [])

        if grade and academic_year and class_names:
            # Check for existing classes
            existing = Class.objects.filter(
                grade=grade, academic_year=academic_year, name__in=class_names
            ).values_list("name", flat=True)

            if existing:
                raise ValidationError(f"Classes already exist: {', '.join(existing)}")

        return cleaned_data


class AcademicYearTransitionForm(forms.Form):
    """Form for academic year transition"""

    current_academic_year = forms.ModelChoiceField(
        queryset=AcademicYear.objects.filter(is_current=True),
        widget=forms.Select(attrs={"class": "form-control"}),
        empty_label="Select Current Academic Year",
    )

    new_academic_year = forms.ModelChoiceField(
        queryset=AcademicYear.objects.filter(is_current=False),
        widget=forms.Select(attrs={"class": "form-control"}),
        empty_label="Select New Academic Year",
    )

    confirm_transition = forms.BooleanField(
        required=True,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
        label="I confirm that I want to transition to the new academic year",
    )

    def clean(self):
        """Validate transition"""
        cleaned_data = super().clean()
        current_year = cleaned_data.get("current_academic_year")
        new_year = cleaned_data.get("new_academic_year")

        if current_year and new_year:
            if current_year == new_year:
                raise ValidationError(
                    "Current and new academic years cannot be the same"
                )

            # Validate transition using service
            validation = AcademicYearService.validate_academic_year_transition(
                current_year.id, new_year.id
            )

            if not validation["is_valid"]:
                raise ValidationError(
                    f"Invalid transition: {'; '.join(validation['errors'])}"
                )

            if validation["warnings"]:
                # Add warnings to form (could be displayed in template)
                self.warnings = validation["warnings"]

        return cleaned_data


class StudentAgeValidationForm(forms.Form):
    """Form for validating student age for grade"""

    grade = forms.ModelChoiceField(
        queryset=Grade.objects.filter(is_active=True),
        widget=forms.Select(attrs={"class": "form-control"}),
        empty_label="Select Grade",
    )

    student_age = forms.IntegerField(
        min_value=3,
        max_value=25,
        widget=forms.NumberInput(
            attrs={"class": "form-control", "placeholder": "Enter student age in years"}
        ),
    )

    def validate_age(self):
        """Validate age for selected grade"""
        if self.is_valid():
            grade = self.cleaned_data["grade"]
            age = self.cleaned_data["student_age"]

            return GradeService.validate_student_age_for_grade(grade.id, age)

        return None


# Custom widgets for enhanced functionality


class AjaxModelChoiceWidget(forms.Select):
    """Widget for AJAX-enabled model choices"""

    def __init__(self, url_name, *args, **kwargs):
        self.url_name = url_name
        super().__init__(*args, **kwargs)

    def render(self, name, value, attrs=None, renderer=None):
        attrs = attrs or {}
        attrs["data-ajax-url"] = self.url_name
        attrs["data-ajax-enabled"] = "true"
        return super().render(name, value, attrs, renderer)


class GradeChoiceField(forms.ModelChoiceField):
    """Custom field for grade selection with section grouping"""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault(
            "queryset", Grade.objects.filter(is_active=True).select_related("section")
        )
        super().__init__(*args, **kwargs)

    def label_from_instance(self, obj):
        return f"{obj.section.name} - {obj.name}"


class ClassChoiceField(forms.ModelChoiceField):
    """Custom field for class selection with full hierarchy"""

    def __init__(self, academic_year=None, *args, **kwargs):
        queryset = Class.objects.filter(is_active=True).select_related(
            "grade__section", "academic_year"
        )

        if academic_year:
            queryset = queryset.filter(academic_year=academic_year)

        kwargs.setdefault("queryset", queryset)
        super().__init__(*args, **kwargs)

    def label_from_instance(self, obj):
        return f"{obj.full_name} ({obj.academic_year.name})"
