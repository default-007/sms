# students/filters.py
import django_filters
from django import forms
from django.db.models import Q, Count
from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import Student, Parent, StudentParentRelation


class StudentFilter(django_filters.FilterSet):
    """Advanced filter for students"""

    search = django_filters.CharFilter(
        method="filter_search",
        label="Search",
        widget=forms.TextInput(
            attrs={
                "placeholder": "Search by name, admission number, email...",
                "class": "form-control",
            }
        ),
    )

    status = django_filters.MultipleChoiceFilter(
        choices=Student.STATUS_CHOICES,
        widget=forms.CheckboxSelectMultiple(),
        label="Status",
    )

    blood_group = django_filters.MultipleChoiceFilter(
        choices=Student.BLOOD_GROUP_CHOICES,
        widget=forms.CheckboxSelectMultiple(),
        label="Blood Group",
    )

    current_class = django_filters.ModelChoiceFilter(
        queryset=None,  # Will be set in __init__
        label="Class",
        empty_label="All Classes",
    )

    admission_year = django_filters.NumberFilter(
        field_name="admission_date__year", label="Admission Year"
    )

    age_range = django_filters.RangeFilter(
        method="filter_age_range",
        label="Age Range",
        widget=django_filters.widgets.RangeWidget(attrs={"class": "form-control"}),
    )

    has_parents = django_filters.BooleanFilter(
        method="filter_has_parents",
        label="Has Linked Parents",
        widget=forms.CheckboxInput(),
    )

    city = django_filters.CharFilter(
        lookup_expr="icontains",
        label="City",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )

    medical_conditions = django_filters.BooleanFilter(
        method="filter_medical_conditions",
        label="Has Medical Conditions",
        widget=forms.CheckboxInput(),
    )

    class Meta:
        model = Student
        fields = ["status", "blood_group", "current_class", "admission_year"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Set current class queryset
        from src.academics.models import Class

        self.filters["current_class"].queryset = Class.objects.filter(
            academic_year__is_current=True
        ).select_related("grade", "section")

    def filter_search(self, queryset, name, value):
        if not value:
            return queryset

        return queryset.filter(
            Q(admission_number__icontains=value)
            | Q(user__first_name__icontains=value)
            | Q(user__last_name__icontains=value)
            | Q(user__email__icontains=value)
            | Q(roll_number__icontains=value)
        )

    def filter_age_range(self, queryset, name, value):
        if not value or not (value.start or value.stop):
            return queryset

        from django.utils import timezone

        current_date = timezone.now().date()

        if value.start:
            max_birth_date = current_date.replace(year=current_date.year - value.start)
            queryset = queryset.filter(user__date_of_birth__lte=max_birth_date)

        if value.stop:
            min_birth_date = current_date.replace(year=current_date.year - value.stop)
            queryset = queryset.filter(user__date_of_birth__gte=min_birth_date)

        return queryset

    def filter_has_parents(self, queryset, name, value):
        if value is None:
            return queryset

        if value:
            return queryset.filter(student_parent_relations__isnull=False).distinct()
        else:
            return queryset.filter(student_parent_relations__isnull=True)

    def filter_medical_conditions(self, queryset, name, value):
        if value is None:
            return queryset

        if value:
            return queryset.exclude(medical_conditions__isnull=True).exclude(
                medical_conditions=""
            )
        else:
            return queryset.filter(
                Q(medical_conditions__isnull=True) | Q(medical_conditions="")
            )


class ParentFilter(django_filters.FilterSet):
    """Advanced filter for parents"""

    search = django_filters.CharFilter(
        method="filter_search",
        label="Search",
        widget=forms.TextInput(
            attrs={
                "placeholder": "Search by name, email, occupation...",
                "class": "form-control",
            }
        ),
    )

    relation_with_student = django_filters.MultipleChoiceFilter(
        choices=Parent.RELATION_CHOICES,
        widget=forms.CheckboxSelectMultiple(),
        label="Relation",
    )

    emergency_contact = django_filters.BooleanFilter(
        label="Emergency Contact", widget=forms.CheckboxInput()
    )

    has_multiple_children = django_filters.BooleanFilter(
        method="filter_multiple_children",
        label="Has Multiple Children",
        widget=forms.CheckboxInput(),
    )

    occupation = django_filters.CharFilter(
        lookup_expr="icontains",
        label="Occupation",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )

    class Meta:
        model = Parent
        fields = ["relation_with_student", "emergency_contact", "occupation"]

    def filter_search(self, queryset, name, value):
        if not value:
            return queryset

        return queryset.filter(
            Q(user__first_name__icontains=value)
            | Q(user__last_name__icontains=value)
            | Q(user__email__icontains=value)
            | Q(user__phone_number__icontains=value)
            | Q(occupation__icontains=value)
            | Q(workplace__icontains=value)
        )

    def filter_multiple_children(self, queryset, name, value):
        if value is None:
            return queryset

        parents_with_multiple = queryset.annotate(
            child_count=Count("parent_student_relations")
        )

        if value:
            return parents_with_multiple.filter(child_count__gt=1)
        else:
            return parents_with_multiple.filter(child_count__lte=1)


# Admin filters
class StatusFilter(admin.SimpleListFilter):
    title = _("Status")
    parameter_name = "status"

    def lookups(self, request, model_admin):
        return Student.STATUS_CHOICES

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(status=self.value())
        return queryset


class ClassFilter(admin.SimpleListFilter):
    title = _("Class")
    parameter_name = "current_class"

    def lookups(self, request, model_admin):
        from src.academics.models import Class

        classes = Class.objects.filter(academic_year__is_current=True).select_related(
            "grade", "section"
        )
        return [(str(c.id), str(c)) for c in classes]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(current_class_id=self.value())
        return queryset


class ParentCountFilter(admin.SimpleListFilter):
    title = _("Parent Count")
    parameter_name = "parent_count"

    def lookups(self, request, model_admin):
        return [
            ("0", _("No Parents")),
            ("1", _("One Parent")),
            ("2", _("Two Parents")),
            ("3+", _("Three or More Parents")),
        ]

    def queryset(self, request, queryset):
        value = self.value()
        if value == "0":
            return queryset.filter(student_parent_relations__isnull=True)
        elif value == "1":
            return queryset.annotate(
                parent_count=Count("student_parent_relations")
            ).filter(parent_count=1)
        elif value == "2":
            return queryset.annotate(
                parent_count=Count("student_parent_relations")
            ).filter(parent_count=2)
        elif value == "3+":
            return queryset.annotate(
                parent_count=Count("student_parent_relations")
            ).filter(parent_count__gte=3)
        return queryset


class AgeRangeFilter(admin.SimpleListFilter):
    title = _("Age Range")
    parameter_name = "age_range"

    def lookups(self, request, model_admin):
        return [
            ("3-5", _("3-5 years")),
            ("6-8", _("6-8 years")),
            ("9-11", _("9-11 years")),
            ("12-14", _("12-14 years")),
            ("15-17", _("15-17 years")),
            ("18+", _("18+ years")),
        ]

    def queryset(self, request, queryset):
        from django.utils import timezone

        current_date = timezone.now().date()

        value = self.value()
        if value == "3-5":
            min_date = current_date.replace(year=current_date.year - 5)
            max_date = current_date.replace(year=current_date.year - 3)
            return queryset.filter(user__date_of_birth__range=[min_date, max_date])
        elif value == "6-8":
            min_date = current_date.replace(year=current_date.year - 8)
            max_date = current_date.replace(year=current_date.year - 6)
            return queryset.filter(user__date_of_birth__range=[min_date, max_date])
        elif value == "9-11":
            min_date = current_date.replace(year=current_date.year - 11)
            max_date = current_date.replace(year=current_date.year - 9)
            return queryset.filter(user__date_of_birth__range=[min_date, max_date])
        elif value == "12-14":
            min_date = current_date.replace(year=current_date.year - 14)
            max_date = current_date.replace(year=current_date.year - 12)
            return queryset.filter(user__date_of_birth__range=[min_date, max_date])
        elif value == "15-17":
            min_date = current_date.replace(year=current_date.year - 17)
            max_date = current_date.replace(year=current_date.year - 15)
            return queryset.filter(user__date_of_birth__range=[min_date, max_date])
        elif value == "18+":
            max_date = current_date.replace(year=current_date.year - 18)
            return queryset.filter(user__date_of_birth__lte=max_date)
        return queryset


class AdmissionYearFilter(admin.SimpleListFilter):
    title = _("Admission Year")
    parameter_name = "admission_year"

    def lookups(self, request, model_admin):
        from django.utils import timezone

        current_year = timezone.now().year
        years = []

        # Get unique admission years from database
        admission_years = (
            Student.objects.values_list("admission_date__year", flat=True)
            .distinct()
            .order_by("-admission_date__year")
        )

        for year in admission_years:
            if year:
                years.append((str(year), str(year)))

        return years

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(admission_date__year=self.value())
        return queryset
