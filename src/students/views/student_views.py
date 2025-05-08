# students/views/student_views.py
from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import (
    ListView,
    DetailView,
    CreateView,
    UpdateView,
    DeleteView,
    FormView,
)
from django.urls import reverse_lazy, reverse
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib import messages
from django.db.models import Q
from django.http import JsonResponse

from ..models import Student, Parent, StudentParentRelation
from ..forms import StudentForm, StudentPromotionForm
from ..services.student_service import StudentService


class StudentListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = Student
    permission_required = "students.view_student"
    context_object_name = "students"
    template_name = "students/student_list.html"
    paginate_by = 20

    def get_queryset(self):
        queryset = super().get_queryset().select_related("user", "current_class")

        # Apply search filter
        search_query = self.request.GET.get("search", "")
        if search_query:
            queryset = queryset.filter(
                Q(admission_number__icontains=search_query)
                | Q(user__first_name__icontains=search_query)
                | Q(user__last_name__icontains=search_query)
                | Q(user__email__icontains=search_query)
                | Q(roll_number__icontains=search_query)
            )

        # Apply class filter
        class_filter = self.request.GET.get("class", "")
        if class_filter:
            queryset = queryset.filter(current_class_id=class_filter)

        # Apply status filter
        status_filter = self.request.GET.get("status", "")
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        # Apply blood group filter
        blood_group_filter = self.request.GET.get("blood_group", "")
        if blood_group_filter:
            queryset = queryset.filter(blood_group=blood_group_filter)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        from src.courses.models import Class, AcademicYear

        # Get current academic year
        current_year = AcademicYear.objects.filter(is_current=True).first()

        # Get classes for filter, prioritizing current academic year
        if current_year:
            context["classes"] = Class.objects.filter(
                academic_year=current_year
            ).select_related("grade", "section")
        else:
            context["classes"] = Class.objects.all().select_related("grade", "section")

        context["status_choices"] = Student.STATUS_CHOICES
        context["blood_group_choices"] = Student.BLOOD_GROUP_CHOICES

        # Pass current filters to template
        context["current_filters"] = {
            "search": self.request.GET.get("search", ""),
            "class": self.request.GET.get("class", ""),
            "status": self.request.GET.get("status", ""),
            "blood_group": self.request.GET.get("blood_group", ""),
        }

        return context


class StudentDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = Student
    permission_required = "students.view_student"
    context_object_name = "student"
    template_name = "students/student_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        student = self.get_object()

        # Get parents
        context["parents"] = Parent.objects.filter(
            parent_student_relations__student=student
        ).select_related("user")

        # Get primary parent
        context["primary_parent"] = Parent.objects.filter(
            parent_student_relations__student=student,
            parent_student_relations__is_primary_contact=True,
        ).first()

        # Get siblings
        context["siblings"] = student.get_siblings()

        # Get attendance information
        try:
            from src.attendance.models import Attendance

            # Get current academic year
            from src.courses.models import AcademicYear

            current_year = AcademicYear.objects.filter(is_current=True).first()

            if current_year:
                context["attendance_percentage"] = student.get_attendance_percentage(
                    academic_year=current_year
                )

                # Get recent attendance records
                context["recent_attendance"] = Attendance.objects.filter(
                    student=student, academic_year=current_year
                ).order_by("-date")[:10]
        except:
            # Attendance module might not be installed
            pass

        # Get academic performance information
        try:
            from src.exams.models import StudentExamResult

            # Get recent exam results
            context["recent_exam_results"] = (
                StudentExamResult.objects.filter(student=student)
                .select_related("exam_schedule__exam", "exam_schedule__subject")
                .order_by("-entry_date")[:5]
            )
        except:
            # Exams module might not be installed
            pass

        # Get fee information
        try:
            from src.finance.models import Invoice

            # Get recent invoices
            context["recent_invoices"] = Invoice.objects.filter(
                student=student
            ).order_by("-issue_date")[:5]
        except:
            # Finance module might not be installed
            pass

        return context


class StudentCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = Student
    permission_required = "students.add_student"
    form_class = StudentForm
    template_name = "students/student_form.html"
    success_url = reverse_lazy("student-list")

    def form_valid(self, form):
        messages.success(self.request, "Student created successfully!")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Add New Student"
        context["button_label"] = "Create Student"
        return context


class StudentUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = Student
    permission_required = "students.change_student"
    form_class = StudentForm
    template_name = "students/student_form.html"

    def get_success_url(self):
        return reverse_lazy("student-detail", kwargs={"pk": self.object.pk})

    def form_valid(self, form):
        messages.success(self.request, "Student updated successfully!")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = f"Edit Student: {self.object.get_full_name()}"
        context["button_label"] = "Update Student"
        return context


class StudentDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = Student
    permission_required = "students.delete_student"
    template_name = "students/student_confirm_delete.html"
    success_url = reverse_lazy("student-list")
    context_object_name = "student"

    def delete(self, request, *args, **kwargs):
        student = self.get_object()
        messages.success(
            request,
            f"Student '{student.get_full_name()}' has been deleted successfully!",
        )
        return super().delete(request, *args, **kwargs)


class StudentPromotionView(LoginRequiredMixin, PermissionRequiredMixin, FormView):
    template_name = "students/student_promotion_form.html"
    form_class = StudentPromotionForm
    permission_required = "students.promote_student"
    success_url = reverse_lazy("student-list")

    def form_valid(self, form):
        students = form.cleaned_data["students"]
        target_class = form.cleaned_data["target_class"]

        # Promote students
        result = StudentService.promote_students(students, target_class)

        # Show success message
        messages.success(
            self.request,
            f"Successfully promoted {result['promoted']} students to {target_class}.",
        )

        # Show errors if any
        if result["errors"] > 0:
            messages.warning(
                self.request,
                f"Failed to promote {result['errors']} students. Please check the logs for details.",
            )

        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Student Promotion"
        return context


class StudentGraduationView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = Student
    template_name = "students/student_graduation.html"
    permission_required = "students.graduate_student"
    context_object_name = "students"

    def get_queryset(self):
        # Get students who are in final year classes
        from src.courses.models import Class, Grade, AcademicYear

        # Get current academic year
        current_year = AcademicYear.objects.filter(is_current=True).first()

        if not current_year:
            return Student.objects.none()

        # Get highest grade level
        highest_grade = Grade.objects.order_by("-name").first()

        if not highest_grade:
            return Student.objects.none()

        # Get classes of highest grade in current academic year
        final_classes = Class.objects.filter(
            grade=highest_grade, academic_year=current_year
        )

        # Get active students in these classes
        return Student.objects.filter(
            current_class__in=final_classes, status="Active"
        ).select_related("user", "current_class")

    def post(self, request, *args, **kwargs):
        student_ids = request.POST.getlist("student_ids")

        if not student_ids:
            messages.warning(request, "No students selected for graduation.")
            return redirect("student-graduation")

        # Get selected students
        students = Student.objects.filter(id__in=student_ids)

        # Graduate students
        result = StudentService.graduate_students(students)

        # Show success message
        messages.success(
            request, f"Successfully graduated {result['graduated']} students."
        )

        # Show errors if any
        if result["errors"] > 0:
            messages.warning(
                request,
                f"Failed to graduate {result['errors']} students. Please check the logs for details.",
            )

        return redirect("student-graduation")


class GenerateStudentIDCardView(
    LoginRequiredMixin, PermissionRequiredMixin, DetailView
):
    model = Student
    permission_required = "students.generate_student_id"
    template_name = "students/student_id_card.html"
    context_object_name = "student"

    def get(self, request, *args, **kwargs):
        student = self.get_object()

        # Check if AJAX request for PDF generation
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            try:
                # Generate ID card
                id_card_path = StudentService.generate_student_id_card(student)

                return JsonResponse(
                    {"success": True, "id_card_url": f"/media/{id_card_path}"}
                )
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)}, status=500)

        return super().get(request, *args, **kwargs)
