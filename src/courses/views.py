from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import (
    ListView,
    DetailView,
    CreateView,
    UpdateView,
    DeleteView,
)
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.auth.decorators import login_required, permission_required
from django.urls import reverse_lazy
from django.contrib import messages
from django.db.models import Q, Count
from django.utils import timezone
from django.http import JsonResponse

from .models import (
    Department,
    AcademicYear,
    Grade,
    Section,
    Class,
    Subject,
    Syllabus,
    TimeSlot,
    Timetable,
    Assignment,
    AssignmentSubmission,
)
from .forms import (
    DepartmentForm,
    AcademicYearForm,
    GradeForm,
    SectionForm,
    ClassForm,
    SubjectForm,
    SyllabusForm,
    TimeSlotForm,
    TimetableForm,
    AssignmentForm,
    AssignmentSubmissionForm,
    GradeSubmissionForm,
)
from .services.class_service import ClassService
from .services.timetable_service import TimetableService
from .services.assignment_service import AssignmentService


@login_required
def courses_dashboard(request):
    """Dashboard view for the courses module."""
    context = {
        "title": "Courses Dashboard",
        "total_departments": Department.objects.count(),
        "total_subjects": Subject.objects.count(),
        "total_classes": Class.objects.filter(academic_year__is_current=True).count(),
        "total_assignments": Assignment.objects.filter(status="published").count(),
        "recent_assignments": Assignment.objects.order_by("-assigned_date")[:5],
    }

    if hasattr(request.user, "teacher_profile"):
        teacher = request.user.teacher_profile
        current_year = AcademicYear.objects.filter(is_current=True).first()

        context.update(
            {
                "teacher_classes": Class.objects.filter(
                    timetable_entries__teacher=teacher, academic_year=current_year
                ).distinct(),
                "teacher_subjects": Subject.objects.filter(
                    timetable_entries__teacher=teacher
                ).distinct(),
                "teacher_assignments": Assignment.objects.filter(
                    teacher=teacher
                ).order_by("-assigned_date")[:5],
            }
        )

    if hasattr(request.user, "student_profile"):
        student = request.user.student_profile
        context.update(
            {
                "student_class": student.current_class,
                "student_subjects": (
                    Subject.objects.filter(
                        timetable_entries__class_obj=student.current_class
                    ).distinct()
                    if student.current_class
                    else []
                ),
                "pending_assignments": AssignmentService.get_student_assignments(
                    student, status="published"
                ),
            }
        )

    return render(request, "courses/dashboard.html", context)


# Department Views
class DepartmentListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = Department
    permission_required = "courses.view_department"
    template_name = "courses/department_list.html"
    context_object_name = "departments"
    paginate_by = 10

    def get_queryset(self):
        queryset = super().get_queryset()
        search_query = self.request.GET.get("search", "")

        if search_query:
            queryset = queryset.filter(
                Q(name__icontains=search_query) | Q(description__icontains=search_query)
            )

        return queryset.annotate(
            teacher_count=Count("teachers", distinct=True),
            subject_count=Count("subjects", distinct=True),
        )


class DepartmentDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = Department
    permission_required = "courses.view_department"
    template_name = "courses/department_detail.html"
    context_object_name = "department"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        department = self.get_object()

        context.update(
            {
                "teachers": department.teachers.all(),
                "subjects": department.subjects.all(),
                "grades": department.grades.all(),
            }
        )

        return context


class DepartmentCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = Department
    permission_required = "courses.add_department"
    form_class = DepartmentForm
    template_name = "courses/department_form.html"
    success_url = reverse_lazy("courses:department-list")

    def form_valid(self, form):
        messages.success(
            self.request, f"Department '{form.instance.name}' created successfully."
        )
        return super().form_valid(form)


class DepartmentUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = Department
    permission_required = "courses.change_department"
    form_class = DepartmentForm
    template_name = "courses/department_form.html"

    def get_success_url(self):
        return reverse_lazy("courses:department-detail", kwargs={"pk": self.object.pk})

    def form_valid(self, form):
        messages.success(
            self.request, f"Department '{form.instance.name}' updated successfully."
        )
        return super().form_valid(form)


class DepartmentDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = Department
    permission_required = "courses.delete_department"
    template_name = "courses/department_confirm_delete.html"
    success_url = reverse_lazy("courses:department-list")

    def delete(self, request, *args, **kwargs):
        department = self.get_object()
        messages.success(
            request, f"Department '{department.name}' deleted successfully."
        )
        return super().delete(request, *args, **kwargs)


# Academic Year Views
class AcademicYearListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = AcademicYear
    permission_required = "courses.view_academicyear"
    template_name = "courses/academic_year_list.html"
    context_object_name = "academic_years"
    ordering = ["-is_current", "-start_date"]


class AcademicYearDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = AcademicYear
    permission_required = "courses.view_academicyear"
    template_name = "courses/academic_year_detail.html"
    context_object_name = "academic_year"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        academic_year = self.get_object()

        context.update(
            {
                "classes": academic_year.classes.all().select_related(
                    "grade", "section"
                ),
            }
        )

        return context


class AcademicYearCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = AcademicYear
    permission_required = "courses.add_academicyear"
    form_class = AcademicYearForm
    template_name = "courses/academic_year_form.html"
    success_url = reverse_lazy("courses:academic-year-list")

    def form_valid(self, form):
        messages.success(
            self.request, f"Academic year '{form.instance.name}' created successfully."
        )
        return super().form_valid(form)


class AcademicYearUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = AcademicYear
    permission_required = "courses.change_academicyear"
    form_class = AcademicYearForm
    template_name = "courses/academic_year_form.html"

    def get_success_url(self):
        return reverse_lazy(
            "courses:academic-year-detail", kwargs={"pk": self.object.pk}
        )

    def form_valid(self, form):
        messages.success(
            self.request, f"Academic year '{form.instance.name}' updated successfully."
        )
        return super().form_valid(form)


class AcademicYearDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = AcademicYear
    permission_required = "courses.delete_academicyear"
    template_name = "courses/academic_year_confirm_delete.html"
    success_url = reverse_lazy("courses:academic-year-list")

    def delete(self, request, *args, **kwargs):
        academic_year = self.get_object()
        messages.success(
            request, f"Academic year '{academic_year.name}' deleted successfully."
        )
        return super().delete(request, *args, **kwargs)


@login_required
@permission_required("courses.change_academicyear")
def set_current_academic_year(request, pk):
    """Set an academic year as the current one."""
    academic_year = get_object_or_404(AcademicYear, pk=pk)

    # Update the academic year
    academic_year.is_current = True
    academic_year.save()

    messages.success(
        request, f"'{academic_year.name}' has been set as the current academic year."
    )
    return redirect("courses:academic-year-list")


# Grade Views
class GradeListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = Grade
    permission_required = "courses.view_grade"
    template_name = "courses/grade_list.html"
    context_object_name = "grades"
    paginate_by = 10

    def get_queryset(self):
        queryset = super().get_queryset().select_related("department")
        department_id = self.request.GET.get("department", "")

        if department_id:
            queryset = queryset.filter(department_id=department_id)

        return queryset.annotate(class_count=Count("classes"))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["departments"] = Department.objects.all()
        context["selected_department"] = self.request.GET.get("department", "")
        return context


class GradeDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = Grade
    permission_required = "courses.view_grade"
    template_name = "courses/grade_detail.html"
    context_object_name = "grade"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        grade = self.get_object()
        current_year = AcademicYear.objects.filter(is_current=True).first()

        context.update(
            {
                "current_classes": grade.classes.filter(
                    academic_year=current_year
                ).select_related("section"),
                "syllabi": grade.syllabi.all().select_related(
                    "subject", "academic_year"
                ),
            }
        )

        return context


class GradeCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = Grade
    permission_required = "courses.add_grade"
    form_class = GradeForm
    template_name = "courses/grade_form.html"
    success_url = reverse_lazy("courses:grade-list")

    def form_valid(self, form):
        messages.success(
            self.request, f"Grade '{form.instance.name}' created successfully."
        )
        return super().form_valid(form)


class GradeUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = Grade
    permission_required = "courses.change_grade"
    form_class = GradeForm
    template_name = "courses/grade_form.html"

    def get_success_url(self):
        return reverse_lazy("courses:grade-detail", kwargs={"pk": self.object.pk})

    def form_valid(self, form):
        messages.success(
            self.request, f"Grade '{form.instance.name}' updated successfully."
        )
        return super().form_valid(form)


class GradeDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = Grade
    permission_required = "courses.delete_grade"
    template_name = "courses/grade_confirm_delete.html"
    success_url = reverse_lazy("courses:grade-list")

    def delete(self, request, *args, **kwargs):
        grade = self.get_object()
        messages.success(request, f"Grade '{grade.name}' deleted successfully.")
        return super().delete(request, *args, **kwargs)


# Section Views
class SectionListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = Section
    permission_required = "courses.view_section"
    template_name = "courses/section_list.html"
    context_object_name = "sections"
    paginate_by = 10


class SectionDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = Section
    permission_required = "courses.view_section"
    template_name = "courses/section_detail.html"
    context_object_name = "section"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        section = self.get_object()
        current_year = AcademicYear.objects.filter(is_current=True).first()

        context.update(
            {
                "current_classes": section.classes.filter(
                    academic_year=current_year
                ).select_related("grade"),
            }
        )

        return context


class SectionCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = Section
    permission_required = "courses.add_section"
    form_class = SectionForm
    template_name = "courses/section_form.html"
    success_url = reverse_lazy("courses:section-list")

    def form_valid(self, form):
        messages.success(
            self.request, f"Section '{form.instance.name}' created successfully."
        )
        return super().form_valid(form)


class SectionUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = Section
    permission_required = "courses.change_section"
    form_class = SectionForm
    template_name = "courses/section_form.html"

    def get_success_url(self):
        return reverse_lazy("courses:section-detail", kwargs={"pk": self.object.pk})

    def form_valid(self, form):
        messages.success(
            self.request, f"Section '{form.instance.name}' updated successfully."
        )
        return super().form_valid(form)


class SectionDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = Section
    permission_required = "courses.delete_section"
    template_name = "courses/section_confirm_delete.html"
    success_url = reverse_lazy("courses:section-list")

    def delete(self, request, *args, **kwargs):
        section = self.get_object()
        messages.success(request, f"Section '{section.name}' deleted successfully.")
        return super().delete(request, *args, **kwargs)


# Class Views
class ClassListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = Class
    permission_required = "courses.view_class"
    template_name = "courses/class_list.html"
    context_object_name = "classes"
    paginate_by = 20

    def get_queryset(self):
        queryset = (
            super()
            .get_queryset()
            .select_related("grade", "section", "academic_year", "class_teacher")
        )

        # Filter by academic year
        academic_year_id = self.request.GET.get("academic_year", "")
        if not academic_year_id:
            # Default to current academic year
            current_year = AcademicYear.objects.filter(is_current=True).first()
            if current_year:
                academic_year_id = current_year.id

        if academic_year_id:
            queryset = queryset.filter(academic_year_id=academic_year_id)

        # Filter by grade
        grade_id = self.request.GET.get("grade", "")
        if grade_id:
            queryset = queryset.filter(grade_id=grade_id)

        # Filter by section
        section_id = self.request.GET.get("section", "")
        if section_id:
            queryset = queryset.filter(section_id=section_id)

        return queryset.annotate(student_count=Count("students"))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["academic_years"] = AcademicYear.objects.all().order_by(
            "-is_current", "-start_date"
        )
        context["grades"] = Grade.objects.all()
        context["sections"] = Section.objects.all()
        context["selected_academic_year"] = self.request.GET.get("academic_year", "")
        context["selected_grade"] = self.request.GET.get("grade", "")
        context["selected_section"] = self.request.GET.get("section", "")
        return context


class ClassDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = Class
    permission_required = "courses.view_class"
    template_name = "courses/class_detail.html"
    context_object_name = "class_obj"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        class_obj = self.get_object()

        context.update(
            {
                "students": ClassService.get_class_students(class_obj),
                "timetable": ClassService.get_class_timetable(class_obj),
                "assignments": Assignment.objects.filter(
                    class_obj=class_obj
                ).select_related("subject", "teacher"),
            }
        )

        return context


class ClassCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = Class
    permission_required = "courses.add_class"
    form_class = ClassForm
    template_name = "courses/class_form.html"
    success_url = reverse_lazy("courses:class-list")

    def form_valid(self, form):
        messages.success(
            self.request,
            f"Class {form.instance.grade.name}-{form.instance.section.name} created successfully.",
        )
        return super().form_valid(form)


class ClassUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = Class
    permission_required = "courses.change_class"
    form_class = ClassForm
    template_name = "courses/class_form.html"

    def get_success_url(self):
        return reverse_lazy("courses:class-detail", kwargs={"pk": self.object.pk})

    def form_valid(self, form):
        messages.success(
            self.request,
            f"Class {form.instance.grade.name}-{form.instance.section.name} updated successfully.",
        )
        return super().form_valid(form)


class ClassDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = Class
    permission_required = "courses.delete_class"
    template_name = "courses/class_confirm_delete.html"
    success_url = reverse_lazy("courses:class-list")
    context_object_name = "class_obj"

    def delete(self, request, *args, **kwargs):
        class_obj = self.get_object()
        messages.success(
            request,
            f"Class {class_obj.grade.name}-{class_obj.section.name} deleted successfully.",
        )
        return super().delete(request, *args, **kwargs)


@login_required
@permission_required("courses.view_class")
def class_students(request, pk):
    """View students in a class."""
    class_obj = get_object_or_404(Class, pk=pk)
    students = ClassService.get_class_students(class_obj)

    return render(
        request,
        "courses/class_students.html",
        {"class_obj": class_obj, "students": students},
    )


@login_required
@permission_required("courses.view_class")
def class_timetable(request, pk):
    """View timetable for a class."""
    class_obj = get_object_or_404(Class, pk=pk)
    day = request.GET.get("day")

    if day:
        try:
            day = int(day)
        except ValueError:
            day = None

    timetable = ClassService.get_class_timetable(class_obj, day)

    return render(
        request,
        "courses/class_timetable.html",
        {"class_obj": class_obj, "timetable": timetable, "selected_day": day},
    )


# Subject Views
class SubjectListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = Subject
    permission_required = "courses.view_subject"
    template_name = "courses/subject_list.html"
    context_object_name = "subjects"
    paginate_by = 20

    def get_queryset(self):
        queryset = super().get_queryset().select_related("department")

        # Apply filters
        department_id = self.request.GET.get("department", "")
        search = self.request.GET.get("search", "")

        if department_id:
            queryset = queryset.filter(department_id=department_id)

        if search:
            queryset = queryset.filter(
                Q(name__icontains=search)
                | Q(code__icontains=search)
                | Q(description__icontains=search)
            )

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["departments"] = Department.objects.all()
        context["selected_department"] = self.request.GET.get("department", "")
        context["search_term"] = self.request.GET.get("search", "")
        return context


class SubjectDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = Subject
    permission_required = "courses.view_subject"
    template_name = "courses/subject_detail.html"
    context_object_name = "subject"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        subject = self.get_object()
        current_year = AcademicYear.objects.filter(is_current=True).first()

        syllabi = Syllabus.objects.filter(subject=subject)
        if current_year:
            current_syllabi = syllabi.filter(academic_year=current_year)
        else:
            current_syllabi = []

        context.update(
            {
                "current_syllabi": current_syllabi,
                "all_syllabi": syllabi,
                "teachers": subject.teacher_assignments.values("teacher").distinct(),
                "classes": (
                    Class.objects.filter(
                        timetable_entries__subject=subject, academic_year=current_year
                    ).distinct()
                    if current_year
                    else []
                ),
            }
        )

        return context


class SubjectCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = Subject
    permission_required = "courses.add_subject"
    form_class = SubjectForm
    template_name = "courses/subject_form.html"
    success_url = reverse_lazy("courses:subject-list")

    def form_valid(self, form):
        messages.success(
            self.request, f"Subject '{form.instance.name}' created successfully."
        )
        return super().form_valid(form)


class SubjectUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = Subject
    permission_required = "courses.change_subject"
    form_class = SubjectForm
    template_name = "courses/subject_form.html"

    def get_success_url(self):
        return reverse_lazy("courses:subject-detail", kwargs={"pk": self.object.pk})

    def form_valid(self, form):
        messages.success(
            self.request, f"Subject '{form.instance.name}' updated successfully."
        )
        return super().form_valid(form)


class SubjectDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = Subject
    permission_required = "courses.delete_subject"
    template_name = "courses/subject_confirm_delete.html"
    success_url = reverse_lazy("courses:subject-list")

    def delete(self, request, *args, **kwargs):
        subject = self.get_object()
        messages.success(request, f"Subject '{subject.name}' deleted successfully.")
        return super().delete(request, *args, **kwargs)


# Syllabus Views
class SyllabusListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = Syllabus
    permission_required = "courses.view_syllabus"
    template_name = "courses/syllabus_list.html"
    context_object_name = "syllabi"
    paginate_by = 20

    def get_queryset(self):
        queryset = (
            super()
            .get_queryset()
            .select_related(
                "subject", "grade", "academic_year", "created_by", "last_updated_by"
            )
        )

        subject_id = self.request.GET.get("subject", "")
        grade_id = self.request.GET.get("grade", "")
        academic_year_id = self.request.GET.get("academic_year", "")

        if subject_id:
            queryset = queryset.filter(subject_id=subject_id)

        if grade_id:
            queryset = queryset.filter(grade_id=grade_id)

        if academic_year_id:
            queryset = queryset.filter(academic_year_id=academic_year_id)
        elif not any([subject_id, grade_id, academic_year_id]):
            # Default to current academic year if no filters
            current_year = AcademicYear.objects.filter(is_current=True).first()
            if current_year:
                queryset = queryset.filter(academic_year=current_year)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "subjects": Subject.objects.all(),
                "grades": Grade.objects.all(),
                "academic_years": AcademicYear.objects.all().order_by(
                    "-is_current", "-start_date"
                ),
                "selected_subject": self.request.GET.get("subject", ""),
                "selected_grade": self.request.GET.get("grade", ""),
                "selected_academic_year": self.request.GET.get("academic_year", ""),
            }
        )
        return context


class SyllabusDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = Syllabus
    permission_required = "courses.view_syllabus"
    template_name = "courses/syllabus_detail.html"
    context_object_name = "syllabus"


class SyllabusCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = Syllabus
    permission_required = "courses.add_syllabus"
    form_class = SyllabusForm
    template_name = "courses/syllabus_form.html"
    success_url = reverse_lazy("courses:syllabus-list")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        messages.success(
            self.request, f"Syllabus '{form.instance.title}' created successfully."
        )
        return super().form_valid(form)


class SyllabusUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = Syllabus
    permission_required = "courses.change_syllabus"
    form_class = SyllabusForm
    template_name = "courses/syllabus_form.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def get_success_url(self):
        return reverse_lazy("courses:syllabus-detail", kwargs={"pk": self.object.pk})

    def form_valid(self, form):
        messages.success(
            self.request, f"Syllabus '{form.instance.title}' updated successfully."
        )
        return super().form_valid(form)


class SyllabusDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = Syllabus
    permission_required = "courses.delete_syllabus"
    template_name = "courses/syllabus_confirm_delete.html"
    success_url = reverse_lazy("courses:syllabus-list")

    def delete(self, request, *args, **kwargs):
        syllabus = self.get_object()
        messages.success(request, f"Syllabus '{syllabus.title}' deleted successfully.")
        return super().delete(request, *args, **kwargs)


# TimeSlot Views
class TimeSlotListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = TimeSlot
    permission_required = "courses.view_timeslot"
    template_name = "courses/timeslot_list.html"
    context_object_name = "timeslots"
    ordering = ["day_of_week", "start_time"]


class TimeSlotCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = TimeSlot
    permission_required = "courses.add_timeslot"
    form_class = TimeSlotForm
    template_name = "courses/timeslot_form.html"
    success_url = reverse_lazy("courses:timeslot-list")

    def form_valid(self, form):
        messages.success(self.request, "Time slot created successfully.")
        return super().form_valid(form)


class TimeSlotUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = TimeSlot
    permission_required = "courses.change_timeslot"
    form_class = TimeSlotForm
    template_name = "courses/timeslot_form.html"
    success_url = reverse_lazy("courses:timeslot-list")

    def form_valid(self, form):
        messages.success(self.request, "Time slot updated successfully.")
        return super().form_valid(form)


class TimeSlotDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = TimeSlot
    permission_required = "courses.delete_timeslot"
    template_name = "courses/timeslot_confirm_delete.html"
    success_url = reverse_lazy("courses:timeslot-list")

    def delete(self, request, *args, **kwargs):
        messages.success(request, "Time slot deleted successfully.")
        return super().delete(request, *args, **kwargs)


# Timetable Views
class TimetableListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = Timetable
    permission_required = "courses.view_timetable"
    template_name = "courses/timetable_list.html"
    context_object_name = "timetable_entries"
    paginate_by = 30

    def get_queryset(self):
        queryset = (
            super()
            .get_queryset()
            .select_related(
                "class_obj",
                "subject",
                "teacher",
                "time_slot",
                "class_obj__grade",
                "class_obj__section",
                "class_obj__academic_year",
            )
        )

        class_id = self.request.GET.get("class", "")
        subject_id = self.request.GET.get("subject", "")
        teacher_id = self.request.GET.get("teacher", "")
        day = self.request.GET.get("day", "")

        if class_id:
            queryset = queryset.filter(class_obj_id=class_id)

        if subject_id:
            queryset = queryset.filter(subject_id=subject_id)

        if teacher_id:
            queryset = queryset.filter(teacher_id=teacher_id)

        if day:
            try:
                day = int(day)
                queryset = queryset.filter(time_slot__day_of_week=day)
            except ValueError:
                pass

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get current academic year
        current_year = AcademicYear.objects.filter(is_current=True).first()

        context.update(
            {
                "classes": (
                    Class.objects.filter(academic_year=current_year)
                    if current_year
                    else Class.objects.all()
                ),
                "subjects": Subject.objects.all(),
                "teachers": getattr(
                    self.request, "teachers", []
                ),  # This would need to be set elsewhere
                "day_choices": TimeSlot.DAY_CHOICES,
                "selected_class": self.request.GET.get("class", ""),
                "selected_subject": self.request.GET.get("subject", ""),
                "selected_teacher": self.request.GET.get("teacher", ""),
                "selected_day": self.request.GET.get("day", ""),
            }
        )
        return context


class TimetableDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = Timetable
    permission_required = "courses.view_timetable"
    template_name = "courses/timetable_detail.html"
    context_object_name = "timetable_entry"


class TimetableCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = Timetable
    permission_required = "courses.add_timetable"
    form_class = TimetableForm
    template_name = "courses/timetable_form.html"
    success_url = reverse_lazy("courses:timetable-list")

    def form_valid(self, form):
        messages.success(self.request, "Timetable entry created successfully.")
        return super().form_valid(form)


class TimetableUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = Timetable
    permission_required = "courses.change_timetable"
    form_class = TimetableForm
    template_name = "courses/timetable_form.html"

    def get_success_url(self):
        return reverse_lazy("courses:timetable-detail", kwargs={"pk": self.object.pk})

    def form_valid(self, form):
        messages.success(self.request, "Timetable entry updated successfully.")
        return super().form_valid(form)


class TimetableDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = Timetable
    permission_required = "courses.delete_timetable"
    template_name = "courses/timetable_confirm_delete.html"
    success_url = reverse_lazy("courses:timetable-list")

    def delete(self, request, *args, **kwargs):
        messages.success(request, "Timetable entry deleted successfully.")
        return super().delete(request, *args, **kwargs)


@login_required
@permission_required("courses.add_timetable")
def generate_timetable(request):
    """Generate timetable automatically based on parameters."""
    if request.method == "POST":
        # Implement timetable generation logic here
        # This would be a complex algorithm to avoid clashes
        messages.info(request, "Timetable generation feature is under development.")
        return redirect("courses:timetable-list")

    # Get current academic year
    current_year = AcademicYear.objects.filter(is_current=True).first()

    return render(
        request,
        "courses/generate_timetable.html",
        {
            "classes": (
                Class.objects.filter(academic_year=current_year) if current_year else []
            ),
            "teachers": getattr(request, "teachers", []),
            "subjects": Subject.objects.all(),
        },
    )


# Assignment Views
class AssignmentListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = Assignment
    permission_required = "courses.view_assignment"
    template_name = "courses/assignment_list.html"
    context_object_name = "assignments"
    paginate_by = 20

    def get_queryset(self):
        queryset = (
            super()
            .get_queryset()
            .select_related(
                "class_obj",
                "subject",
                "teacher",
                "class_obj__grade",
                "class_obj__section",
            )
        )

        class_id = self.request.GET.get("class", "")
        subject_id = self.request.GET.get("subject", "")
        teacher_id = self.request.GET.get("teacher", "")
        status = self.request.GET.get("status", "")

        if class_id:
            queryset = queryset.filter(class_obj_id=class_id)

        if subject_id:
            queryset = queryset.filter(subject_id=subject_id)

        if teacher_id:
            queryset = queryset.filter(teacher_id=teacher_id)

        if status:
            queryset = queryset.filter(status=status)

        # If user is a teacher, show only their assignments
        if hasattr(self.request.user, "teacher_profile"):
            queryset = queryset.filter(teacher=self.request.user.teacher_profile)

        # If user is a student, show only assignments for their class
        if hasattr(self.request.user, "student_profile"):
            student = self.request.user.student_profile
            if student.current_class:
                queryset = queryset.filter(class_obj=student.current_class)

        return queryset.order_by("-assigned_date")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get current academic year
        current_year = AcademicYear.objects.filter(is_current=True).first()

        context.update(
            {
                "classes": (
                    Class.objects.filter(academic_year=current_year)
                    if current_year
                    else Class.objects.all()
                ),
                "subjects": Subject.objects.all(),
                "status_choices": Assignment.STATUS_CHOICES,
                "selected_class": self.request.GET.get("class", ""),
                "selected_subject": self.request.GET.get("subject", ""),
                "selected_status": self.request.GET.get("status", ""),
            }
        )
        return context


class AssignmentDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = Assignment
    permission_required = "courses.view_assignment"
    template_name = "courses/assignment_detail.html"
    context_object_name = "assignment"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        assignment = self.get_object()

        # Get submissions for teachers
        if hasattr(self.request.user, "teacher_profile") or self.request.user.is_staff:
            context["submissions"] = assignment.submissions.all().select_related(
                "student"
            )

        # Get personal submission for students
        if hasattr(self.request.user, "student_profile"):
            student = self.request.user.student_profile
            context["submission"] = assignment.submissions.filter(
                student=student
            ).first()

        return context


class AssignmentCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = Assignment
    permission_required = "courses.add_assignment"
    form_class = AssignmentForm
    template_name = "courses/assignment_form.html"
    success_url = reverse_lazy("courses:assignment-list")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        messages.success(
            self.request, f"Assignment '{form.instance.title}' created successfully."
        )
        return super().form_valid(form)


class AssignmentUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = Assignment
    permission_required = "courses.change_assignment"
    form_class = AssignmentForm
    template_name = "courses/assignment_form.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def get_success_url(self):
        return reverse_lazy("courses:assignment-detail", kwargs={"pk": self.object.pk})

    def form_valid(self, form):
        messages.success(
            self.request, f"Assignment '{form.instance.title}' updated successfully."
        )
        return super().form_valid(form)


class AssignmentDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = Assignment
    permission_required = "courses.delete_assignment"
    template_name = "courses/assignment_confirm_delete.html"
    success_url = reverse_lazy("courses:assignment-list")

    def delete(self, request, *args, **kwargs):
        assignment = self.get_object()
        messages.success(
            request, f"Assignment '{assignment.title}' deleted successfully."
        )
        return super().delete(request, *args, **kwargs)


@login_required
@permission_required("courses.view_assignmentsubmission")
def assignment_submissions(request, pk):
    """View all submissions for an assignment."""
    assignment = get_object_or_404(Assignment, pk=pk)
    submissions = assignment.submissions.all().select_related(
        "student", "student__user"
    )

    return render(
        request,
        "courses/assignment_submissions.html",
        {"assignment": assignment, "submissions": submissions},
    )


@login_required
def submit_assignment(request, pk):
    """Submit an assignment."""
    assignment = get_object_or_404(Assignment, pk=pk)

    # Check if the user is a student
    if not hasattr(request.user, "student_profile"):
        messages.error(request, "Only students can submit assignments.")
        return redirect("courses:assignment-detail", pk=assignment.pk)

    student = request.user.student_profile

    # Check if the student is in the correct class
    if student.current_class != assignment.class_obj:
        messages.error(
            request,
            "You cannot submit to this assignment as you are not in this class.",
        )
        return redirect("courses:assignment-list")

    # Check if assignment is open for submission
    if assignment.status == "closed":
        messages.error(request, "This assignment is closed for submissions.")
        return redirect("courses:assignment-detail", pk=assignment.pk)

    # Check if already submitted
    submission = AssignmentSubmission.objects.filter(
        assignment=assignment, student=student
    ).first()

    if request.method == "POST":
        form = AssignmentSubmissionForm(
            request.POST,
            request.FILES,
            instance=submission,
            assignment=assignment,
            student=student,
        )

        if form.is_valid():
            form.save()
            messages.success(request, "Assignment submitted successfully.")
            return redirect("courses:assignment-detail", pk=assignment.pk)
    else:
        form = AssignmentSubmissionForm(instance=submission)

    return render(
        request,
        "courses/submit_assignment.html",
        {"form": form, "assignment": assignment, "submission": submission},
    )


@login_required
@permission_required("courses.change_assignmentsubmission")
def grade_assignment(request, pk):
    """Grade an assignment submission."""
    submission = get_object_or_404(AssignmentSubmission, pk=pk)

    # Check if the user is the teacher for this assignment or an admin
    is_teacher = (
        hasattr(request.user, "teacher_profile")
        and request.user.teacher_profile == submission.assignment.teacher
    )

    if not (is_teacher or request.user.is_staff):
        messages.error(request, "You do not have permission to grade this submission.")
        return redirect("courses:assignment-detail", pk=submission.assignment.pk)

    if request.method == "POST":
        form = GradeSubmissionForm(request.POST, instance=submission)

        if form.is_valid():
            submission = form.save(commit=False)
            submission.status = "graded"
            submission.graded_by = request.user.teacher_profile if is_teacher else None
            submission.graded_at = timezone.now()
            submission.save()

            messages.success(request, "Assignment graded successfully.")
            return redirect(
                "courses:assignment-submissions", pk=submission.assignment.pk
            )
    else:
        form = GradeSubmissionForm(instance=submission)

    return render(
        request,
        "courses/grade_assignment.html",
        {
            "form": form,
            "submission": submission,
            "assignment": submission.assignment,
            "student": submission.student,
        },
    )


@login_required
@permission_required("courses.view_class")
def class_analytics(request, pk):
    """View analytics for a class."""
    class_obj = get_object_or_404(Class, pk=pk)

    # Get analytics data
    from src.courses.services.analytics_service import AnalyticsService

    analytics = AnalyticsService.get_class_analytics(class_obj)

    # Prepare data for charts
    subject_names = []
    subject_scores = []
    subject_pass_rates = []

    for subject_name, data in analytics.get("subject_performance", {}).items():
        subject_names.append(f"'{subject_name}'")
        subject_scores.append(data.get("average_score", 0))
        subject_pass_rates.append(data.get("pass_rate", 0))

    # Grade distribution data
    from src.exams.models import StudentExamResult

    grade_distribution = (
        StudentExamResult.objects.filter(
            student__current_class=class_obj,
            exam_schedule__exam__academic_year=class_obj.academic_year,
        )
        .values("grade")
        .annotate(count=Count("id"))
    )

    grade_labels = []
    grade_values = []

    for grade in grade_distribution:
        grade_labels.append(f"'{grade['grade']}'")
        grade_values.append(grade["count"])

    context = {
        "class_obj": class_obj,
        "analytics": analytics,
        "subject_names": ",".join(subject_names),
        "subject_scores": ",".join(map(str, subject_scores)),
        "subject_pass_rates": ",".join(map(str, subject_pass_rates)),
        "grade_distribution_labels": ",".join(grade_labels),
        "grade_distribution_values": ",".join(map(str, grade_values)),
    }

    return render(request, "courses/class_analytics.html", context)


@login_required
@permission_required("courses.view_subject")
def subject_analytics(request, pk):
    """View analytics for a subject."""
    subject = get_object_or_404(Subject, pk=pk)

    # Get academic year
    academic_year_id = request.GET.get("academic_year", "")
    if academic_year_id:
        academic_year = get_object_or_404(AcademicYear, pk=academic_year_id)
    else:
        academic_year = AcademicYear.objects.filter(is_current=True).first()

    # Get analytics data
    from src.courses.services.analytics_service import AnalyticsService

    analytics = AnalyticsService.get_subject_analytics(subject, academic_year)

    # Prepare data for charts
    class_names = []
    class_scores = []
    class_pass_rates = []

    for class_name, data in analytics.get("class_performance", {}).items():
        class_names.append(f"'{class_name}'")
        class_scores.append(data.get("average_score", 0))
        class_pass_rates.append(data.get("pass_rate", 0))

    # Grade distribution data
    grade_labels = []
    grade_values = []

    for grade, percentage in analytics.get("grade_distribution", {}).items():
        grade_labels.append(f"'{grade}'")
        grade_values.append(percentage)

    context = {
        "subject": subject,
        "academic_year": academic_year,
        "analytics": analytics,
        "academic_years": AcademicYear.objects.all().order_by("-start_date"),
        "class_names": ",".join(class_names),
        "class_scores": ",".join(map(str, class_scores)),
        "class_pass_rates": ",".join(map(str, class_pass_rates)),
        "grade_labels": ",".join(grade_labels),
        "grade_values": ",".join(map(str, grade_values)),
    }

    return render(request, "courses/subject_analytics.html", context)


@login_required
@permission_required("courses.view_department")
def department_analytics(request, pk):
    """View analytics for a department."""
    department = get_object_or_404(Department, pk=pk)

    # Get academic year
    academic_year_id = request.GET.get("academic_year", "")
    if academic_year_id:
        academic_year = get_object_or_404(AcademicYear, pk=academic_year_id)
    else:
        academic_year = AcademicYear.objects.filter(is_current=True).first()

    # Get analytics data
    from src.courses.services.analytics_service import AnalyticsService

    analytics = AnalyticsService.get_department_analytics(department, academic_year)

    # Prepare data for charts
    subject_names = []
    subject_scores = []
    subject_pass_rates = []

    for subject_name, data in analytics.get("subject_performance", {}).items():
        subject_names.append(f"'{subject_name}'")
        subject_scores.append(data.get("average_score", 0))
        subject_pass_rates.append(data.get("pass_rate", 0))

    # Teacher data
    teacher_names = []
    teacher_scores = []

    for teacher_name, data in analytics.get("teacher_performance", {}).items():
        teacher_names.append(f"'{teacher_name}'")
        teacher_scores.append(data.get("average_score", 0))

    context = {
        "department": department,
        "academic_year": academic_year,
        "analytics": analytics,
        "academic_years": AcademicYear.objects.all().order_by("-start_date"),
        "subject_names": ",".join(subject_names),
        "subject_scores": ",".join(map(str, subject_scores)),
        "subject_pass_rates": ",".join(map(str, subject_pass_rates)),
        "teacher_names": ",".join(teacher_names),
        "teacher_scores": ",".join(map(str, teacher_scores)),
    }

    return render(request, "courses/department_analytics.html", context)


@login_required
@permission_required("courses.view_timetable")
def check_timetable_clashes(request):
    """API endpoint to check timetable clashes."""
    from src.courses.services.timetable_service import TimetableService

    clashes = TimetableService.get_timetable_clashes()

    # Format clashes for the response
    formatted_clashes = []
    for clash in clashes:
        formatted_clash = {
            "time_slot": str(clash["time_slot"]),
            "teacher_clashes": [],
            "room_clashes": [],
            "class_clashes": [],
        }

        # Format teacher clashes
        for teacher_clash in clash["teacher_clashes"]:
            from src.teachers.models import Teacher

            teacher = Teacher.objects.get(id=teacher_clash["teacher"])
            formatted_clash["teacher_clashes"].append(teacher.user.get_full_name())

        # Format room clashes
        for room_clash in clash["room_clashes"]:
            if room_clash["room"]:  # Skip empty rooms
                formatted_clash["room_clashes"].append(room_clash["room"])

        # Format class clashes
        for class_clash in clash["class_clashes"]:
            class_obj = Class.objects.get(id=class_clash["class_obj"])
            formatted_clash["class_clashes"].append(str(class_obj))

        formatted_clashes.append(formatted_clash)

    return JsonResponse({"clashes": formatted_clashes})


@login_required
@permission_required("courses.view_timetable")
def get_teacher_timetable(request, teacher_id):
    """View timetable for a specific teacher."""
    from src.teachers.models import Teacher

    teacher = get_object_or_404(Teacher, pk=teacher_id)

    # Get day filter
    day = request.GET.get("day")
    if day:
        try:
            day = int(day)
        except ValueError:
            day = None

    # Get academic year
    academic_year_id = request.GET.get("academic_year", "")
    if academic_year_id:
        academic_year = get_object_or_404(AcademicYear, pk=academic_year_id)
    else:
        academic_year = AcademicYear.objects.filter(is_current=True).first()

    # Get timetable
    from src.courses.services.timetable_service import TimetableService

    timetable = TimetableService.get_teacher_timetable(teacher, day, academic_year)

    # Get workload stats
    workload = TimetableService.get_teacher_workload(teacher, academic_year)

    context = {
        "teacher": teacher,
        "timetable": timetable,
        "workload": workload,
        "selected_day": day,
        "academic_year": academic_year,
        "academic_years": AcademicYear.objects.all().order_by("-start_date"),
        "day_choices": TimeSlot.DAY_CHOICES,
    }

    return render(request, "courses/teacher_timetable.html", context)


@login_required
@permission_required("courses.add_timetable")
def generate_timetable(request):
    """Generate timetable automatically based on parameters."""
    if request.method == "POST":
        # Get parameters
        class_id = request.POST.get("class")
        if not class_id:
            messages.error(request, "Please select a class.")
            return redirect("courses:generate-timetable")

        class_obj = get_object_or_404(Class, pk=class_id)

        # Get selected subjects
        subject_ids = request.POST.getlist("subjects")
        if not subject_ids:
            messages.error(request, "Please select at least one subject.")
            return redirect("courses:generate-timetable")

        subjects = Subject.objects.filter(id__in=subject_ids)

        # Generate suggestions
        from src.courses.services.timetable_service import TimetableService

        suggestions = TimetableService.generate_timetable_suggestions(
            class_obj, subjects
        )

        if not suggestions:
            messages.error(
                request,
                "Could not generate any timetable suggestions. Please check teacher and room availability.",
            )
            return redirect("courses:generate-timetable")

        # Save to session for the confirmation page
        request.session["timetable_suggestions"] = [
            {
                "class_id": class_obj.id,
                "subject_id": suggestion["subject"].id,
                "time_slot_id": suggestion["time_slot"].id,
                "available_teachers": [t.id for t in suggestion["available_teachers"]],
                "available_rooms": list(suggestion["available_rooms"]),
            }
            for suggestion in suggestions
        ]

        return redirect("courses:confirm-timetable")

    # Get current academic year
    current_year = AcademicYear.objects.filter(is_current=True).first()

    context = {
        "classes": (
            Class.objects.filter(academic_year=current_year) if current_year else []
        ),
        "subjects": Subject.objects.all(),
        "timeslots": TimeSlot.objects.all(),
    }

    return render(request, "courses/generate_timetable.html", context)


@login_required
@permission_required("courses.add_timetable")
def confirm_timetable(request):
    """Confirm and create timetable entries."""
    suggestions = request.session.get("timetable_suggestions", [])

    if not suggestions:
        messages.error(
            request, "No timetable suggestions found. Please generate timetable first."
        )
        return redirect("courses:generate-timetable")

    if request.method == "POST":
        # Create timetable entries
        created_count = 0

        for i, suggestion in enumerate(suggestions):
            teacher_id = request.POST.get(f"teacher_{i}")
            room = request.POST.get(f"room_{i}")

            if teacher_id and room:
                class_obj = get_object_or_404(Class, pk=suggestion["class_id"])
                subject = get_object_or_404(Subject, pk=suggestion["subject_id"])
                time_slot = get_object_or_404(TimeSlot, pk=suggestion["time_slot_id"])
                teacher = get_object_or_404("teachers.Teacher", pk=teacher_id)

                from src.courses.services.timetable_service import TimetableService

                entry = TimetableService.create_timetable_entry(
                    class_obj, subject, teacher, time_slot, room
                )

                if entry:
                    created_count += 1

        # Clear session
        del request.session["timetable_suggestions"]

        if created_count > 0:
            messages.success(
                request, f"Successfully created {created_count} timetable entries."
            )
        else:
            messages.warning(
                request,
                "No timetable entries were created. Please check for conflicts.",
            )

        return redirect("courses:timetable-list")

    # Prepare data for template
    formatted_suggestions = []

    for i, suggestion in enumerate(suggestions):
        class_obj = get_object_or_404(Class, pk=suggestion["class_id"])
        subject = get_object_or_404(Subject, pk=suggestion["subject_id"])
        time_slot = get_object_or_404(TimeSlot, pk=suggestion["time_slot_id"])
        available_teachers = []

        for teacher_id in suggestion["available_teachers"]:
            from src.teachers.models import Teacher

            teacher = Teacher.objects.get(pk=teacher_id)
            available_teachers.append(teacher)

        formatted_suggestions.append(
            {
                "index": i,
                "class_obj": class_obj,
                "subject": subject,
                "time_slot": time_slot,
                "available_teachers": available_teachers,
                "available_rooms": suggestion["available_rooms"],
            }
        )

    context = {"suggestions": formatted_suggestions}

    return render(request, "courses/confirm_timetable.html", context)
