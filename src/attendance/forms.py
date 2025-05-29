from django import forms
from django.forms import formset_factory

from .models import AttendanceRecord, StudentAttendance


class AttendanceRecordForm(forms.ModelForm):
    """Form for creating an attendance record"""

    class Meta:
        model = AttendanceRecord
        fields = ["class_obj", "date", "remarks"]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
            "remarks": forms.Textarea(attrs={"rows": 3}),
        }


class StudentAttendanceForm(forms.Form):
    """Form for recording a single student's attendance"""

    student_id = forms.IntegerField(widget=forms.HiddenInput())
    student_name = forms.CharField(
        widget=forms.TextInput(attrs={"readonly": "readonly"})
    )
    status = forms.ChoiceField(
        choices=StudentAttendance.STATUS_CHOICES,
        widget=forms.RadioSelect(attrs={"class": "inline-radio"}),
    )
    remarks = forms.CharField(required=False, widget=forms.TextInput())


# Create a formset for multiple student attendance records
StudentAttendanceFormSet = formset_factory(StudentAttendanceForm, extra=0)


class AttendanceFilterForm(forms.Form):
    """Form for filtering attendance records"""

    start_date = forms.DateField(
        required=False, widget=forms.DateInput(attrs={"type": "date"})
    )
    end_date = forms.DateField(
        required=False, widget=forms.DateInput(attrs={"type": "date"})
    )
    status = forms.ChoiceField(
        required=False, choices=[("", "All")] + list(StudentAttendance.STATUS_CHOICES)
    )
