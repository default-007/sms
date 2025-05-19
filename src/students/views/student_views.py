# students/views/student_views.py
from django.shortcuts import get_object_or_404, redirect
from django.views.generic import (
    ListView,
    DetailView,
    CreateView,
    UpdateView,
    DeleteView,
    FormView,
)
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib import messages
from django.db.models import Q, Prefetch
from django.http import JsonResponse, HttpResponse
from django.core.cache import cache
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page

from ..models import Student, Parent, StudentParentRelation
from ..forms import StudentForm, StudentPromotionForm, QuickStudentAddForm
from ..services.student_service import StudentService


class StudentListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = Student
    permission_required = "students.view_student"
    context_object_name = "students"
    template_name = "students/student_list.html"
    paginate_by = 25

    def get_queryset(self):
        queryset = Student.objects.with_related().with_parents()

        # Apply filters
        filters = self.get_filters()
        if filters:
            queryset = StudentService.search_students(
                query=filters.get("search", ""), filters=filters
            )
        else:
            # Apply search only
            search_query = self.request.GET.get("search", "")
            if search_query:
                queryset = queryset.search(search_query)

        return queryset.order_by("admission_number")

    def get_filters(self):
        """Extract filters from request"""
        return {
            "search": self.request.GET.get("search", ""),
            "class_id": self.request.GET.get("class", ""),
            "status": self.request.GET.get("status", ""),
            "blood_group": self.request.GET.get("blood_group", ""),
            "admission_year": self.request.GET.get("admission_year", ""),
        }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get filter options
        from src.courses.models import Class, AcademicYear

        current_year = AcademicYear.objects.filter(is_current=True).first()

        if current_year:
            context["classes"] = Class.objects.filter(
                academic_year=current_year
            ).select_related("grade", "section")
        else:
            context["classes"] = Class.objects.all().select_related("grade", "section")

        context["status_choices"] = Student.STATUS_CHOICES
        context["blood_group_choices"] = Student.BLOOD_GROUP_CHOICES
        context["current_filters"] = self.get_filters()

        # Add statistics
        context["statistics"] = StudentService.get_student_statistics()

        return context


@method_decorator(cache_page(300), name="get")  # Cache for 5 minutes
class StudentDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = Student
    permission_required = "students.view_student"
    context_object_name = "student"
    template_name = "students/student_detail.html"

    def get_queryset(self):
        return Student.objects.select_related(
            "user", "current_class__grade", "current_class__section"
        ).prefetch_related(
            Prefetch(
                "student_parent_relations",
                queryset=StudentParentRelation.objects.select_related("parent__user"),
            )
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        student = self.get_object()

        # Get related data
        context["parents"] = student.get_parents()
        context["primary_parent"] = student.get_primary_parent()
        context["siblings"] = student.get_siblings()

        # Attendance data
        try:
            from src.attendance.models import Attendance
            from src.courses.models import AcademicYear

            current_year = AcademicYear.objects.filter(is_current=True).first()
            if current_year:
                # Cache attendance percentage
                cache_key = f"student_attendance_{student.id}_{current_year.id}"
                attendance_percentage = cache.get(cache_key)

                if attendance_percentage is None:
                    attendance_percentage = student.get_attendance_percentage(
                        current_year
                    )
                    cache.set(cache_key, attendance_percentage, 1800)  # 30 minutes

                context["attendance_percentage"] = attendance_percentage

                # Recent attendance
                context["recent_attendance"] = Attendance.objects.filter(
                    student=student, academic_year=current_year
                ).order_by("-date")[:10]
        except:
            pass

        # Academic performance
        try:
            from src.exams.models import StudentExamResult

            context["recent_exam_results"] = (
                StudentExamResult.objects.filter(student=student)
                .select_related("exam_schedule__exam", "exam_schedule__subject")
                .order_by("-entry_date")[:5]
            )
        except:
            pass

        # Financial information
        try:
            from src.finance.models import Invoice

            context["recent_invoices"] = Invoice.objects.filter(
                student=student
            ).order_by("-issue_date")[:5]
        except:
            pass

        return context


class StudentCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = Student
    permission_required = "students.add_student"
    form_class = StudentForm
    template_name = "students/student_form.html"
    success_url = reverse_lazy("students:student-list")

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
        return reverse_lazy("students:student-detail", kwargs={"pk": self.object.pk})

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
    success_url = reverse_lazy("students:student-list")
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
    success_url = reverse_lazy("students:student-list")

    def form_valid(self, form):
        students = form.cleaned_data["students"]
        target_class = form.cleaned_data["target_class"]
        send_notifications = form.cleaned_data.get("send_notifications", False)

        # Promote students
        result = StudentService.promote_students(
            students, target_class, send_notifications
        )

        messages.success(
            self.request,
            f"Successfully promoted {result['promoted']} students to {target_class}.",
        )

        if result["errors"] > 0:
            messages.warning(
                self.request,
                f"Failed to promote {result['errors']} students. Please check the logs.",
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
        """Get students eligible for graduation"""
        from src.courses.models import Class, Grade, AcademicYear

        current_year = AcademicYear.objects.filter(is_current=True).first()
        if not current_year:
            return Student.objects.none()

        # Get highest grade
        highest_grade = Grade.objects.order_by("-id").first()
        if not highest_grade:
            return Student.objects.none()

        # Get final year classes
        final_classes = Class.objects.filter(
            grade=highest_grade, academic_year=current_year
        )

        return Student.objects.filter(
            current_class__in=final_classes, status="Active"
        ).with_related()

    def post(self, request, *args, **kwargs):
        student_ids = request.POST.getlist("student_ids")
        send_notifications = request.POST.get("send_notifications") == "on"

        if not student_ids:
            messages.warning(request, "No students selected for graduation.")
            return redirect("students:student-graduation")

        students = Student.objects.filter(id__in=student_ids)
        result = StudentService.graduate_students(students, send_notifications)

        messages.success(
            request, f"Successfully graduated {result['graduated']} students."
        )

        if result["errors"] > 0:
            messages.warning(
                request, f"Failed to graduate {result['errors']} students."
            )

        return redirect("students:student-graduation")


class GenerateStudentIDCardView(
    LoginRequiredMixin, PermissionRequiredMixin, DetailView
):
    model = Student
    permission_required = "students.generate_student_id"
    template_name = "students/student_id_card.html"
    context_object_name = "student"

    def get(self, request, *args, **kwargs):
        student = self.get_object()

        # Check for AJAX request
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            try:
                id_card_path = StudentService.generate_student_id_card(student)
                return JsonResponse(
                    {"success": True, "id_card_url": f"/media/{id_card_path}"}
                )
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)}, status=500)

        return super().get(request, *args, **kwargs)


class QuickStudentAddView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    """AJAX view for quick student creation"""

    permission_required = "students.add_student"
    form_class = QuickStudentAddForm
    http_method_names = ["post"]

    def post(self, request, *args, **kwargs):
        form = self.get_form()

        if form.is_valid():
            try:
                student = form.save()
                return JsonResponse(
                    {
                        "success": True,
                        "student_id": str(student.id),
                        "student_name": student.get_full_name(),
                        "admission_number": student.admission_number,
                        "redirect_url": reverse_lazy(
                            "students:student-detail", args=[student.id]
                        ),
                    }
                )
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)}, status=500)
        else:
            return JsonResponse({"success": False, "errors": form.errors}, status=400)


class StudentAutocompleteView(LoginRequiredMixin, ListView):
    """AJAX autocomplete for students"""

    def get(self, request, *args, **kwargs):
        query = request.GET.get("q", "")
        students = Student.objects.filter(
            Q(user__first_name__icontains=query)
            | Q(user__last_name__icontains=query)
            | Q(admission_number__icontains=query)
        ).with_related()[:10]

        results = [
            {
                "id": str(student.id),
                "text": f"{student.get_full_name()} ({student.admission_number})",
                "admission_number": student.admission_number,
                "class": str(student.current_class) if student.current_class else None,
            }
            for student in students
        ]

        return JsonResponse({"results": results})


class StudentStatusUpdateView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    """AJAX view for updating student status"""

    model = Student
    permission_required = "students.change_student"
    http_method_names = ["post"]

    def post(self, request, *args, **kwargs):
        student = self.get_object()
        new_status = request.POST.get("status")

        if new_status not in dict(Student.STATUS_CHOICES):
            return JsonResponse(
                {"success": False, "error": "Invalid status"}, status=400
            )

        try:
            old_status = student.status

            if new_status == "Graduated":
                student.mark_as_graduated()
            elif new_status == "Withdrawn":
                reason = request.POST.get("reason", "")
                student.mark_as_withdrawn(reason)
            else:
                student.status = new_status
                student.save()

            # Clear cache
            cache.delete_many(
                [
                    f"student_attendance_{student.id}",
                    f"student_siblings_{student.id}",
                ]
            )

            return JsonResponse(
                {
                    "success": True,
                    "old_status": old_status,
                    "new_status": student.status,
                    "message": f"Student status updated to {student.status}",
                }
            )

        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)}, status=500)
