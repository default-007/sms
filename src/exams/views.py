from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import (
    ListView,
    DetailView,
    CreateView,
    UpdateView,
    DeleteView,
    FormView,
    View,
    TemplateView,
)
from django.urls import reverse_lazy, reverse
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib import messages
from django.db.models import Q, Count, Sum, Avg
from django.db import transaction
from django.http import HttpResponseRedirect, Http404, JsonResponse, HttpResponse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.core.paginator import Paginator

from .models import (
    ExamType,
    Exam,
    ExamSchedule,
    Quiz,
    Question,
    StudentExamResult,
    StudentQuizAttempt,
    StudentQuizResponse,
    GradingSystem,
    ReportCard,
)
from .forms import (
    ExamTypeForm,
    ExamForm,
    ExamScheduleForm,
    QuizForm,
    QuestionForm,
    StudentExamResultForm,
    BulkResultEntryForm,
    QuizAttemptForm,
    QuizResponseForm,
    GradingSystemForm,
    ReportCardForm,
)
from .services import ExamService, ResultService, QuizService


# Exam Type Views
class ExamTypeListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = ExamType
    permission_required = "exams.view_examtype"
    template_name = "exams/exam_type_list.html"
    context_object_name = "exam_types"
    paginate_by = 10


class ExamTypeCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = ExamType
    permission_required = "exams.add_examtype"
    form_class = ExamTypeForm
    template_name = "exams/exam_type_form.html"
    success_url = reverse_lazy("exams:exam-type-list")

    def form_valid(self, form):
        messages.success(self.request, _("Exam type created successfully."))
        return super().form_valid(form)


class ExamTypeDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = ExamType
    permission_required = "exams.view_examtype"
    template_name = "exams/exam_type_detail.html"
    context_object_name = "exam_type"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["exams"] = self.object.exams.all()[:10]
        return context


class ExamTypeUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = ExamType
    permission_required = "exams.change_examtype"
    form_class = ExamTypeForm
    template_name = "exams/exam_type_form.html"

    def get_success_url(self):
        return reverse_lazy("exams:exam-type-detail", kwargs={"pk": self.object.pk})

    def form_valid(self, form):
        messages.success(self.request, _("Exam type updated successfully."))
        return super().form_valid(form)


class ExamTypeDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = ExamType
    permission_required = "exams.delete_examtype"
    template_name = "exams/exam_type_confirm_delete.html"
    success_url = reverse_lazy("exams:exam-type-list")

    def delete(self, request, *args, **kwargs):
        messages.success(request, _("Exam type deleted successfully."))
        return super().delete(request, *args, **kwargs)


# Exam Views
class ExamListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = Exam
    permission_required = "exams.view_exam"
    template_name = "exams/exam_list.html"
    context_object_name = "exams"
    paginate_by = 20

    def get_queryset(self):
        queryset = (
            super()
            .get_queryset()
            .select_related("exam_type", "academic_year", "created_by")
        )

        # Apply search filter
        search_query = self.request.GET.get("search", "")
        if search_query:
            queryset = queryset.filter(
                Q(name__icontains=search_query)
                | Q(description__icontains=search_query)
                | Q(exam_type__name__icontains=search_query)
            )

        # Apply status filter
        status_filter = self.request.GET.get("status", "")
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        # Apply academic year filter
        academic_year_filter = self.request.GET.get("academic_year", "")
        if academic_year_filter:
            queryset = queryset.filter(academic_year_id=academic_year_filter)

        return queryset.order_by("-start_date")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["status_choices"] = dict(Exam.STATUS_CHOICES)
        context["current_filters"] = {
            "search": self.request.GET.get("search", ""),
            "status": self.request.GET.get("status", ""),
            "academic_year": self.request.GET.get("academic_year", ""),
        }

        from src.courses.models import AcademicYear

        context["academic_years"] = AcademicYear.objects.all().order_by(
            "-is_current", "-start_date"
        )

        return context


class ExamDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = Exam
    permission_required = "exams.view_exam"
    template_name = "exams/exam_detail.html"
    context_object_name = "exam"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get schedules for this exam
        context["schedules"] = self.object.exam_schedules.select_related(
            "class_obj", "subject", "supervisor"
        ).order_by("date", "start_time")

        # Get result statistics
        context["results_stats"] = {
            "total_students": StudentExamResult.objects.filter(
                exam_schedule__exam=self.object
            )
            .values("student")
            .distinct()
            .count(),
            "total_results": StudentExamResult.objects.filter(
                exam_schedule__exam=self.object
            ).count(),
            "average_percentage": StudentExamResult.objects.filter(
                exam_schedule__exam=self.object
            ).aggregate(avg=Avg("percentage"))["avg"]
            or 0,
            "passing_count": StudentExamResult.objects.filter(
                exam_schedule__exam=self.object, is_pass=True
            )
            .values("student")
            .distinct()
            .count(),
        }

        # Calculate passing percentage
        if context["results_stats"]["total_students"] > 0:
            context["results_stats"]["passing_percentage"] = (
                context["results_stats"]["passing_count"]
                / context["results_stats"]["total_students"]
            ) * 100
        else:
            context["results_stats"]["passing_percentage"] = 0

        return context


class ExamCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = Exam
    permission_required = "exams.add_exam"
    form_class = ExamForm
    template_name = "exams/exam_form.html"
    success_url = reverse_lazy("exams:exam-list")

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, _("Exam created successfully."))
        return super().form_valid(form)


class ExamUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = Exam
    permission_required = "exams.change_exam"
    form_class = ExamForm
    template_name = "exams/exam_form.html"

    def get_success_url(self):
        return reverse_lazy("exams:exam-detail", kwargs={"pk": self.object.pk})

    def form_valid(self, form):
        messages.success(self.request, _("Exam updated successfully."))
        return super().form_valid(form)


class ExamDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = Exam
    permission_required = "exams.delete_exam"
    template_name = "exams/exam_confirm_delete.html"
    success_url = reverse_lazy("exams:exam-list")

    def delete(self, request, *args, **kwargs):
        messages.success(request, _("Exam deleted successfully."))
        return super().delete(request, *args, **kwargs)


class ExamUpdateStatusView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = "exams.change_exam"

    def post(self, request, pk):
        exam = get_object_or_404(Exam, pk=pk)
        status = request.POST.get("status")

        if status in dict(Exam.STATUS_CHOICES):
            exam.status = status
            exam.save(update_fields=["status"])
            messages.success(request, _("Exam status updated successfully."))
        else:
            messages.error(request, _("Invalid status value."))

        return redirect("exams:exam-detail", pk=pk)


# Exam Schedule Views
class ExamScheduleCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = ExamSchedule
    permission_required = "exams.add_examschedule"
    form_class = ExamScheduleForm
    template_name = "exams/exam_schedule_form.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["exam"] = get_object_or_404(Exam, pk=self.kwargs["exam_id"])
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["exam"] = get_object_or_404(Exam, pk=self.kwargs["exam_id"])
        return context

    def get_success_url(self):
        return reverse_lazy("exams:exam-detail", kwargs={"pk": self.kwargs["exam_id"]})

    def form_valid(self, form):
        form.instance.exam = get_object_or_404(Exam, pk=self.kwargs["exam_id"])
        messages.success(self.request, _("Exam schedule created successfully."))
        return super().form_valid(form)


class ExamScheduleDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = ExamSchedule
    permission_required = "exams.view_examschedule"
    template_name = "exams/exam_schedule_detail.html"
    context_object_name = "schedule"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get student results for this schedule
        context["results"] = self.object.student_results.select_related(
            "student", "student__user"
        ).order_by("student__user__first_name", "student__user__last_name")

        # Calculate statistics
        context["stats"] = {
            "total_students": context["results"].count(),
            "average_marks": context["results"].aggregate(avg=Avg("marks_obtained"))[
                "avg"
            ]
            or 0,
            "highest_marks": context["results"].aggregate(
                max=models.Max("marks_obtained")
            )["max"]
            or 0,
            "lowest_marks": context["results"].aggregate(
                min=models.Min("marks_obtained")
            )["min"]
            or 0,
            "pass_count": context["results"].filter(is_pass=True).count(),
        }

        # Calculate pass percentage
        if context["stats"]["total_students"] > 0:
            context["stats"]["pass_percentage"] = (
                context["stats"]["pass_count"] / context["stats"]["total_students"]
            ) * 100
        else:
            context["stats"]["pass_percentage"] = 0

        return context


class ExamScheduleUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = ExamSchedule
    permission_required = "exams.change_examschedule"
    form_class = ExamScheduleForm
    template_name = "exams/exam_schedule_form.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["exam"] = self.object.exam
        return context

    def get_success_url(self):
        return reverse_lazy("exams:schedule-detail", kwargs={"pk": self.object.pk})

    def form_valid(self, form):
        messages.success(self.request, _("Exam schedule updated successfully."))
        return super().form_valid(form)


class ExamScheduleDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = ExamSchedule
    permission_required = "exams.delete_examschedule"
    template_name = "exams/exam_schedule_confirm_delete.html"

    def get_success_url(self):
        return reverse_lazy("exams:exam-detail", kwargs={"pk": self.object.exam.pk})

    def delete(self, request, *args, **kwargs):
        messages.success(request, _("Exam schedule deleted successfully."))
        return super().delete(request, *args, **kwargs)


# Exam Results Views
class ResultListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = StudentExamResult
    permission_required = "exams.view_studentexamresult"
    template_name = "exams/result_list.html"
    context_object_name = "results"
    paginate_by = 50

    def get_queryset(self):
        schedule_id = self.kwargs.get("schedule_id")
        self.exam_schedule = get_object_or_404(ExamSchedule, pk=schedule_id)

        return (
            StudentExamResult.objects.filter(exam_schedule=self.exam_schedule)
            .select_related("student", "student__user")
            .order_by("student__user__first_name", "student__user__last_name")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["exam_schedule"] = self.exam_schedule

        # Calculate statistics
        context["stats"] = {
            "total_students": context["results"].count(),
            "average_marks": context["results"].aggregate(avg=Avg("marks_obtained"))[
                "avg"
            ]
            or 0,
            "highest_marks": context["results"].aggregate(
                max=models.Max("marks_obtained")
            )["max"]
            or 0,
            "lowest_marks": context["results"].aggregate(
                min=models.Min("marks_obtained")
            )["min"]
            or 0,
            "pass_count": context["results"].filter(is_pass=True).count(),
        }

        # Calculate pass percentage
        if context["stats"]["total_students"] > 0:
            context["stats"]["pass_percentage"] = (
                context["stats"]["pass_count"] / context["stats"]["total_students"]
            ) * 100
        else:
            context["stats"]["pass_percentage"] = 0

        return context


class ResultDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = StudentExamResult
    permission_required = "exams.view_studentexamresult"
    template_name = "exams/result_detail.html"
    context_object_name = "result"


class ResultUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = StudentExamResult
    permission_required = "exams.change_studentexamresult"
    form_class = StudentExamResultForm
    template_name = "exams/result_form.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["exam_schedule"] = self.object.exam_schedule
        kwargs["student"] = self.object.student
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["exam_schedule"] = self.object.exam_schedule
        context["student"] = self.object.student
        return context

    def get_success_url(self):
        return reverse_lazy("exams:result-detail", kwargs={"pk": self.object.pk})

    def form_valid(self, form):
        form.instance.entered_by = self.request.user

        # Calculate percentage and is_pass
        total_marks = self.object.exam_schedule.total_marks
        passing_marks = self.object.exam_schedule.passing_marks
        marks_obtained = form.cleaned_data.get("marks_obtained")

        form.instance.percentage = (marks_obtained / total_marks) * 100
        form.instance.is_pass = marks_obtained >= passing_marks

        # Calculate grade
        form.instance.grade = ResultService.calculate_grade(
            form.instance.percentage, self.object.exam_schedule.exam.academic_year_id
        )

        messages.success(self.request, _("Result updated successfully."))
        return super().form_valid(form)


class BulkResultEntryView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = "exams.add_studentexamresult"
    template_name = "exams/bulk_result_entry.html"

    def get(self, request, schedule_id):
        exam_schedule = get_object_or_404(ExamSchedule, pk=schedule_id)

        # Get students in the class who don't have results yet
        from src.students.models import Student

        students = (
            Student.objects.filter(current_class=exam_schedule.class_obj)
            .exclude(exam_results__exam_schedule=exam_schedule)
            .select_related("user")
            .order_by("user__first_name", "user__last_name")
        )

        # Get existing results
        existing_results = (
            StudentExamResult.objects.filter(exam_schedule=exam_schedule)
            .select_related("student", "student__user")
            .order_by("student__user__first_name", "student__user__last_name")
        )

        return render(
            request,
            self.template_name,
            {
                "exam_schedule": exam_schedule,
                "students": students,
                "existing_results": existing_results,
                "max_marks": exam_schedule.total_marks,
                "passing_marks": exam_schedule.passing_marks,
            },
        )

    def post(self, request, schedule_id):
        exam_schedule = get_object_or_404(ExamSchedule, pk=schedule_id)

        # Process form data
        student_ids = request.POST.getlist("student_id")
        marks = request.POST.getlist("marks")
        remarks = request.POST.getlist("remarks")

        success_count = 0
        error_count = 0

        for i in range(len(student_ids)):
            try:
                student_id = int(student_ids[i])
                mark = float(marks[i])
                remark = remarks[i] if i < len(remarks) else ""

                if mark > exam_schedule.total_marks:
                    error_count += 1
                    continue

                ResultService.enter_student_result(
                    student_id=student_id,
                    exam_schedule_id=schedule_id,
                    marks_obtained=mark,
                    remarks=remark,
                    entered_by_id=request.user.id,
                )
                success_count += 1

            except (ValueError, IndexError):
                error_count += 1

        if success_count > 0:
            messages.success(
                request,
                _("Successfully entered results for {} students.").format(
                    success_count
                ),
            )

        if error_count > 0:
            messages.warning(
                request,
                _(
                    "Could not process results for {} students. Please check the values."
                ).format(error_count),
            )

        return redirect("exams:result-list", schedule_id=schedule_id)


# Quiz Views
class QuizListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = Quiz
    permission_required = "exams.view_quiz"
    template_name = "exams/quiz_list.html"
    context_object_name = "quizzes"
    paginate_by = 20

    def get_queryset(self):
        queryset = (
            super()
            .get_queryset()
            .select_related("class_obj", "subject", "teacher", "teacher__user")
        )

        # Filter by teacher if not admin
        if not self.request.user.is_staff and hasattr(
            self.request.user, "teacher_profile"
        ):
            queryset = queryset.filter(teacher=self.request.user.teacher_profile)

        # Apply search filter
        search_query = self.request.GET.get("search", "")
        if search_query:
            queryset = queryset.filter(
                Q(title__icontains=search_query)
                | Q(description__icontains=search_query)
                | Q(subject__name__icontains=search_query)
            )

        # Apply status filter
        status_filter = self.request.GET.get("status", "")
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        # Apply class filter
        class_filter = self.request.GET.get("class", "")
        if class_filter:
            queryset = queryset.filter(class_obj_id=class_filter)

        return queryset.order_by("-start_datetime")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["status_choices"] = dict(Quiz.STATUS_CHOICES)
        context["current_filters"] = {
            "search": self.request.GET.get("search", ""),
            "status": self.request.GET.get("status", ""),
            "class": self.request.GET.get("class", ""),
        }

        from src.courses.models import Class

        context["classes"] = Class.objects.all().select_related(
            "grade", "section", "academic_year"
        )

        return context


class QuizDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = Quiz
    permission_required = "exams.view_quiz"
    template_name = "exams/quiz_detail.html"
    context_object_name = "quiz"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get questions for this quiz
        context["questions"] = self.object.questions.all().order_by("id")

        # Get attempt statistics
        context["stats"] = {
            "total_attempts": self.object.student_attempts.count(),
            "completed_attempts": self.object.student_attempts.filter(
                end_time__isnull=False
            ).count(),
            "avg_score": self.object.student_attempts.filter(
                end_time__isnull=False, marks_obtained__isnull=False
            ).aggregate(avg=Avg("percentage"))["avg"]
            or 0,
            "pass_count": self.object.student_attempts.filter(is_pass=True).count(),
        }

        # Get recent attempts
        context["recent_attempts"] = self.object.student_attempts.select_related(
            "student", "student__user"
        ).order_by("-start_time")[:10]

        return context


class QuizCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = Quiz
    permission_required = "exams.add_quiz"
    form_class = QuizForm
    template_name = "exams/quiz_form.html"
    success_url = reverse_lazy("exams:quiz-list")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, _("Quiz created successfully."))
        return super().form_valid(form)


class QuizUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = Quiz
    permission_required = "exams.change_quiz"
    form_class = QuizForm
    template_name = "exams/quiz_form.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def get_success_url(self):
        return reverse_lazy("exams:quiz-detail", kwargs={"pk": self.object.pk})

    def form_valid(self, form):
        messages.success(self.request, _("Quiz updated successfully."))
        return super().form_valid(form)


class QuizDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = Quiz
    permission_required = "exams.delete_quiz"
    template_name = "exams/quiz_confirm_delete.html"
    success_url = reverse_lazy("exams:quiz-list")

    def delete(self, request, *args, **kwargs):
        messages.success(request, _("Quiz deleted successfully."))
        return super().delete(request, *args, **kwargs)


class QuizUpdateStatusView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = "exams.change_quiz"

    def post(self, request, pk):
        quiz = get_object_or_404(Quiz, pk=pk)
        status = request.POST.get("status")

        if status in dict(Quiz.STATUS_CHOICES):
            quiz.status = status
            quiz.save(update_fields=["status"])
            messages.success(request, _("Quiz status updated successfully."))
        else:
            messages.error(request, _("Invalid status value."))

        return redirect("exams:quiz-detail", pk=pk)


# Question Views
class QuestionCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = Question
    permission_required = "exams.add_question"
    form_class = QuestionForm
    template_name = "exams/question_form.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["quiz"] = get_object_or_404(Quiz, pk=self.kwargs["quiz_id"])
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["quiz"] = get_object_or_404(Quiz, pk=self.kwargs["quiz_id"])
        return context

    def get_success_url(self):
        return reverse_lazy("exams:quiz-detail", kwargs={"pk": self.kwargs["quiz_id"]})

    def form_valid(self, form):
        form.instance.quiz = get_object_or_404(Quiz, pk=self.kwargs["quiz_id"])
        messages.success(self.request, _("Question created successfully."))
        return super().form_valid(form)


class QuestionDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = Question
    permission_required = "exams.view_question"
    template_name = "exams/question_detail.html"
    context_object_name = "question"


class QuestionUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = Question
    permission_required = "exams.change_question"
    form_class = QuestionForm
    template_name = "exams/question_form.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["quiz"] = self.object.quiz
        return context

    def get_success_url(self):
        return reverse_lazy("exams:quiz-detail", kwargs={"pk": self.object.quiz.pk})

    def form_valid(self, form):
        messages.success(self.request, _("Question updated successfully."))
        return super().form_valid(form)


class QuestionDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = Question
    permission_required = "exams.delete_question"
    template_name = "exams/question_confirm_delete.html"

    def get_success_url(self):
        return reverse_lazy("exams:quiz-detail", kwargs={"pk": self.object.quiz.pk})

    def delete(self, request, *args, **kwargs):
        messages.success(request, _("Question deleted successfully."))
        return super().delete(request, *args, **kwargs)


# Quiz Attempt Views
class QuizAttemptView(LoginRequiredMixin, View):
    template_name = "exams/quiz_attempt.html"

    def get(self, request, quiz_id):
        quiz = get_object_or_404(Quiz, pk=quiz_id)

        # Check if quiz is available
        now = timezone.now()
        if not (
            quiz.status == "published"
            and quiz.start_datetime <= now <= quiz.end_datetime
        ):
            messages.error(request, _("This quiz is not currently available."))
            return redirect("exams:student-quiz-list")

        # Check if user is a student
        if not hasattr(request.user, "student_profile"):
            messages.error(request, _("Only students can attempt quizzes."))
            return redirect("exams:quiz-list")

        student = request.user.student_profile

        # Check if student is in the correct class
        if student.current_class != quiz.class_obj:
            messages.error(request, _("This quiz is not available for your class."))
            return redirect("exams:student-quiz-list")

        # Check if student has remaining attempts
        attempt_count = StudentQuizAttempt.objects.filter(
            quiz=quiz, student=student
        ).count()

        if attempt_count >= quiz.attempts_allowed:
            messages.error(request, _("You have used all your attempts for this quiz."))
            return redirect("exams:student-quiz-list")

        # Show confirmation page
        return render(
            request,
            self.template_name,
            {
                "quiz": quiz,
                "attempt_count": attempt_count,
                "remaining_attempts": quiz.attempts_allowed - attempt_count,
            },
        )

    def post(self, request, quiz_id):
        quiz = get_object_or_404(Quiz, pk=quiz_id)

        # Same validations as GET
        now = timezone.now()
        if not (
            quiz.status == "published"
            and quiz.start_datetime <= now <= quiz.end_datetime
        ):
            messages.error(request, _("This quiz is not currently available."))
            return redirect("exams:student-quiz-list")

        if not hasattr(request.user, "student_profile"):
            messages.error(request, _("Only students can attempt quizzes."))
            return redirect("exams:quiz-list")

        student = request.user.student_profile

        if student.current_class != quiz.class_obj:
            messages.error(request, _("This quiz is not available for your class."))
            return redirect("exams:student-quiz-list")

        # Check if student has remaining attempts
        attempt_count = StudentQuizAttempt.objects.filter(
            quiz=quiz, student=student
        ).count()

        if attempt_count >= quiz.attempts_allowed:
            messages.error(request, _("You have used all your attempts for this quiz."))
            return redirect("exams:student-quiz-list")

        # Start the attempt
        try:
            attempt = QuizService.start_quiz_attempt(quiz.id, student.id)

            # Go to the first question
            first_question = quiz.questions.first()
            if first_question:
                return redirect(
                    "exams:attempt-question",
                    pk=attempt.id,
                    question_id=first_question.id,
                )
            else:
                # No questions, complete the attempt
                messages.warning(request, _("This quiz has no questions."))
                QuizService.complete_quiz_attempt(attempt.id)
                return redirect("exams:attempt-detail", pk=attempt.id)

        except ValueError as e:
            messages.error(request, str(e))
            return redirect("exams:student-quiz-list")


class QuizQuestionView(LoginRequiredMixin, View):
    template_name = "exams/quiz_question.html"

    def get(self, request, pk, question_id):
        attempt = get_object_or_404(StudentQuizAttempt, pk=pk)
        question = get_object_or_404(Question, pk=question_id)

        # Check if user is the student who started this attempt
        if (
            not hasattr(request.user, "student_profile")
            or request.user.student_profile != attempt.student
        ):
            messages.error(request, _("Access denied."))
            return redirect("exams:student-quiz-list")

        # Check if attempt is still ongoing
        if attempt.end_time:
            messages.error(request, _("This attempt has already been completed."))
            return redirect("exams:attempt-detail", pk=pk)

        # Check if question belongs to the quiz
        if question.quiz != attempt.quiz:
            messages.error(request, _("Invalid question."))
            return redirect("exams:attempt-detail", pk=pk)

        # Get existing response if any
        try:
            response = StudentQuizResponse.objects.get(
                student_quiz_attempt=attempt, question=question
            )
            initial = {
                "answer": (
                    response.selected_option
                    if question.question_type == "mcq"
                    else response.answer_text
                )
            }
        except StudentQuizResponse.DoesNotExist:
            initial = {}

        form = QuizResponseForm(question=question, initial=initial)

        # Get next and previous questions
        questions = list(attempt.quiz.questions.order_by("id"))
        current_index = questions.index(question)

        prev_question = questions[current_index - 1] if current_index > 0 else None
        next_question = (
            questions[current_index + 1] if current_index < len(questions) - 1 else None
        )

        return render(
            request,
            self.template_name,
            {
                "attempt": attempt,
                "question": question,
                "form": form,
                "question_number": current_index + 1,
                "total_questions": len(questions),
                "prev_question": prev_question,
                "next_question": next_question,
            },
        )

    def post(self, request, pk, question_id):
        attempt = get_object_or_404(StudentQuizAttempt, pk=pk)
        question = get_object_or_404(Question, pk=question_id)

        # Check if user is the student who started this attempt
        if (
            not hasattr(request.user, "student_profile")
            or request.user.student_profile != attempt.student
        ):
            messages.error(request, _("Access denied."))
            return redirect("exams:student-quiz-list")

        # Check if attempt is still ongoing
        if attempt.end_time:
            messages.error(request, _("This attempt has already been completed."))
            return redirect("exams:attempt-detail", pk=pk)

        # Check if question belongs to the quiz
        if question.quiz != attempt.quiz:
            messages.error(request, _("Invalid question."))
            return redirect("exams:attempt-detail", pk=pk)

        form = QuizResponseForm(request.POST, question=question)

        if form.is_valid():
            answer = form.cleaned_data.get("answer")

            if question.question_type == "mcq":
                try:
                    selected_option = int(answer)
                    answer_text = ""
                except (ValueError, TypeError):
                    selected_option = None
                    answer_text = str(answer)
            else:
                selected_option = None
                answer_text = str(answer)

            # Save the response
            QuizService.submit_response(
                attempt_id=attempt.id,
                question_id=question.id,
                selected_option=selected_option,
                answer_text=answer_text,
            )

            # Redirect based on the action
            if "save_next" in request.POST and request.POST.get("next_question"):
                next_id = request.POST.get("next_question")
                return redirect("exams:attempt-question", pk=pk, question_id=next_id)
            elif "save_prev" in request.POST and request.POST.get("prev_question"):
                prev_id = request.POST.get("prev_question")
                return redirect("exams:attempt-question", pk=pk, question_id=prev_id)
            elif "finish" in request.POST:
                return redirect("exams:attempt-complete", pk=pk)
            else:
                # Stay on the same question
                return redirect(
                    "exams:attempt-question", pk=pk, question_id=question_id
                )

        # Form is invalid, show the form again
        questions = list(attempt.quiz.questions.order_by("id"))
        current_index = questions.index(question)

        prev_question = questions[current_index - 1] if current_index > 0 else None
        next_question = (
            questions[current_index + 1] if current_index < len(questions) - 1 else None
        )

        return render(
            request,
            self.template_name,
            {
                "attempt": attempt,
                "question": question,
                "form": form,
                "question_number": current_index + 1,
                "total_questions": len(questions),
                "prev_question": prev_question,
                "next_question": next_question,
            },
        )


class QuizAttemptCompleteView(LoginRequiredMixin, View):
    template_name = "exams/quiz_attempt_confirm_complete.html"

    def get(self, request, pk):
        attempt = get_object_or_404(StudentQuizAttempt, pk=pk)

        # Check if user is the student who started this attempt
        if (
            not hasattr(request.user, "student_profile")
            or request.user.student_profile != attempt.student
        ):
            messages.error(request, _("Access denied."))
            return redirect("exams:student-quiz-list")

        # Check if attempt is still ongoing
        if attempt.end_time:
            messages.error(request, _("This attempt has already been completed."))
            return redirect("exams:attempt-detail", pk=pk)

        # Get questions with responses
        questions = attempt.quiz.questions.order_by("id")

        responses = StudentQuizResponse.objects.filter(
            student_quiz_attempt=attempt
        ).values_list("question_id", flat=True)

        answered_count = len(responses)
        total_count = questions.count()

        unanswered = [q for q in questions if q.id not in responses]

        return render(
            request,
            self.template_name,
            {
                "attempt": attempt,
                "answered_count": answered_count,
                "total_count": total_count,
                "unanswered": unanswered,
            },
        )

    def post(self, request, pk):
        attempt = get_object_or_404(StudentQuizAttempt, pk=pk)

        # Check if user is the student who started this attempt
        if (
            not hasattr(request.user, "student_profile")
            or request.user.student_profile != attempt.student
        ):
            messages.error(request, _("Access denied."))
            return redirect("exams:student-quiz-list")

        # Check if attempt is still ongoing
        if attempt.end_time:
            messages.error(request, _("This attempt has already been completed."))
            return redirect("exams:attempt-detail", pk=pk)

        # Complete the attempt
        attempt = QuizService.complete_quiz_attempt(attempt.id)

        messages.success(request, _("Quiz completed successfully."))
        return redirect("exams:attempt-detail", pk=pk)


class QuizAttemptDetailView(LoginRequiredMixin, DetailView):
    model = StudentQuizAttempt
    template_name = "exams/quiz_attempt_detail.html"
    context_object_name = "attempt"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get responses for this attempt
        context["responses"] = self.object.responses.select_related(
            "question"
        ).order_by("question__id")

        # Calculate statistics
        if self.object.is_completed():
            context["stats"] = {
                "total_questions": self.object.quiz.questions.count(),
                "answered_questions": context["responses"].count(),
                "correct_answers": context["responses"].filter(is_correct=True).count(),
                "marks_obtained": self.object.marks_obtained,
                "percentage": self.object.percentage,
                "is_pass": self.object.is_pass,
                "duration_minutes": None,
            }

            # Calculate duration if end_time exists
            if self.object.start_time and self.object.end_time:
                duration = self.object.end_time - self.object.start_time
                context["stats"]["duration_minutes"] = round(
                    duration.total_seconds() / 60, 1
                )

        return context


# Grading System Views
class GradingSystemListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = GradingSystem
    permission_required = "exams.view_gradingsystem"
    template_name = "exams/grading_system_list.html"
    context_object_name = "grading_systems"
    paginate_by = 10

    def get_queryset(self):
        queryset = super().get_queryset().select_related("academic_year")

        # Filter by academic year
        academic_year_id = self.request.GET.get("academic_year", "")
        if academic_year_id:
            queryset = queryset.filter(academic_year_id=academic_year_id)

        return queryset.order_by("academic_year", "-grade_point")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        from src.courses.models import AcademicYear

        context["academic_years"] = AcademicYear.objects.all().order_by(
            "-is_current", "-start_date"
        )
        context["current_academic_year"] = self.request.GET.get("academic_year", "")

        return context


class GradingSystemCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = GradingSystem
    permission_required = "exams.add_gradingsystem"
    form_class = GradingSystemForm
    template_name = "exams/grading_system_form.html"
    success_url = reverse_lazy("exams:grading-system-list")

    def form_valid(self, form):
        messages.success(self.request, _("Grading system created successfully."))
        return super().form_valid(form)


class GradingSystemDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = GradingSystem
    permission_required = "exams.view_gradingsystem"
    template_name = "exams/grading_system_detail.html"
    context_object_name = "grading_system"


class GradingSystemUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = GradingSystem
    permission_required = "exams.change_gradingsystem"
    form_class = GradingSystemForm
    template_name = "exams/grading_system_form.html"

    def get_success_url(self):
        return reverse_lazy(
            "exams:grading-system-detail", kwargs={"pk": self.object.pk}
        )

    def form_valid(self, form):
        messages.success(self.request, _("Grading system updated successfully."))
        return super().form_valid(form)


class GradingSystemDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = GradingSystem
    permission_required = "exams.delete_gradingsystem"
    template_name = "exams/grading_system_confirm_delete.html"
    success_url = reverse_lazy("exams:grading-system-list")

    def delete(self, request, *args, **kwargs):
        messages.success(request, _("Grading system deleted successfully."))
        return super().delete(request, *args, **kwargs)


# Report Card Views
class ReportCardListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = ReportCard
    permission_required = "exams.view_reportcard"
    template_name = "exams/report_card_list.html"
    context_object_name = "report_cards"
    paginate_by = 20

    def get_queryset(self):
        queryset = (
            super()
            .get_queryset()
            .select_related("student", "student__user", "class_obj", "academic_year")
        )

        # Apply filters
        class_id = self.request.GET.get("class", "")
        if class_id:
            queryset = queryset.filter(class_obj_id=class_id)

        academic_year_id = self.request.GET.get("academic_year", "")
        if academic_year_id:
            queryset = queryset.filter(academic_year_id=academic_year_id)

        term = self.request.GET.get("term", "")
        if term:
            queryset = queryset.filter(term=term)

        status = self.request.GET.get("status", "")
        if status:
            queryset = queryset.filter(status=status)

        search = self.request.GET.get("search", "")
        if search:
            queryset = queryset.filter(
                Q(student__user__first_name__icontains=search)
                | Q(student__user__last_name__icontains=search)
                | Q(student__admission_number__icontains=search)
            )

        return queryset.order_by(
            "student__user__first_name", "student__user__last_name"
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        from src.courses.models import Class, AcademicYear

        context["classes"] = Class.objects.all().select_related(
            "grade", "section", "academic_year"
        )
        context["academic_years"] = AcademicYear.objects.all().order_by(
            "-is_current", "-start_date"
        )
        context["terms"] = dict(ReportCard.TERM_CHOICES)
        context["statuses"] = dict(ReportCard.STATUS_CHOICES)

        context["current_filters"] = {
            "class": self.request.GET.get("class", ""),
            "academic_year": self.request.GET.get("academic_year", ""),
            "term": self.request.GET.get("term", ""),
            "status": self.request.GET.get("status", ""),
            "search": self.request.GET.get("search", ""),
        }

        return context


class ReportCardGenerateView(LoginRequiredMixin, PermissionRequiredMixin, FormView):
    permission_required = "exams.add_reportcard"
    template_name = "exams/report_card_generate.html"
    form_class = ReportCardForm
    success_url = reverse_lazy("exams:report-card-list")

    def get_form(self, form_class=None):
        form = super().get_form(form_class)

        # Simplify the form to only include necessary fields
        form.fields.pop("student", None)
        form.fields.pop("remarks", None)
        form.fields.pop("class_teacher_remarks", None)
        form.fields.pop("principal_remarks", None)
        form.fields.pop("status", None)

        return form

    def form_valid(self, form):
        class_id = form.cleaned_data.get("class_obj").id
        academic_year_id = form.cleaned_data.get("academic_year").id
        term = form.cleaned_data.get("term")

        success_count, error_count = ResultService.generate_report_cards(
            class_id=class_id,
            academic_year_id=academic_year_id,
            term=term,
            created_by_id=self.request.user.id,
        )

        if success_count > 0:
            messages.success(
                self.request,
                _("Successfully generated report cards for {} students.").format(
                    success_count
                ),
            )

        if error_count > 0:
            messages.warning(
                self.request,
                _(
                    "Could not generate report cards for {} students due to missing or incomplete data."
                ).format(error_count),
            )

        return super().form_valid(form)


class ReportCardDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = ReportCard
    permission_required = "exams.view_reportcard"
    template_name = "exams/report_card_detail.html"
    context_object_name = "report_card"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get all exam results for this student in this term
        context["exam_results"] = (
            StudentExamResult.objects.filter(
                student=self.object.student,
                exam_schedule__class_obj=self.object.class_obj,
                exam_schedule__exam__academic_year=self.object.academic_year,
            )
            .select_related(
                "exam_schedule", "exam_schedule__subject", "exam_schedule__exam"
            )
            .order_by("exam_schedule__subject__name")
        )

        # Group results by subject
        subjects = {}
        for result in context["exam_results"]:
            subject_name = result.exam_schedule.subject.name

            if subject_name not in subjects:
                subjects[subject_name] = {
                    "name": subject_name,
                    "results": [],
                    "total_marks": 0,
                    "obtained_marks": 0,
                }

            subjects[subject_name]["results"].append(result)
            subjects[subject_name]["total_marks"] += result.exam_schedule.total_marks
            subjects[subject_name]["obtained_marks"] += result.marks_obtained

        # Calculate percentages and grades for each subject
        for subject in subjects.values():
            if subject["total_marks"] > 0:
                subject["percentage"] = (
                    subject["obtained_marks"] / subject["total_marks"]
                ) * 100
                subject["grade"] = ResultService.calculate_grade(
                    subject["percentage"], self.object.academic_year_id
                )
            else:
                subject["percentage"] = 0
                subject["grade"] = "N/A"

        context["subjects"] = list(subjects.values())

        return context


class ReportCardUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = ReportCard
    permission_required = "exams.change_reportcard"
    form_class = ReportCardForm
    template_name = "exams/report_card_form.html"

    def get_form(self, form_class=None):
        form = super().get_form(form_class)

        # Make certain fields readonly
        readonly_fields = [
            "student",
            "class_obj",
            "academic_year",
            "term",
        ]

        for field in readonly_fields:
            form.fields[field].widget.attrs["readonly"] = True

        return form

    def get_success_url(self):
        return reverse_lazy("exams:report-card-detail", kwargs={"pk": self.object.pk})

    def form_valid(self, form):
        # Ensure readonly fields are not changed
        if self.object.student_id != form.cleaned_data["student"].id:
            form.cleaned_data["student"] = self.object.student

        if self.object.class_obj_id != form.cleaned_data["class_obj"].id:
            form.cleaned_data["class_obj"] = self.object.class_obj

        if self.object.academic_year_id != form.cleaned_data["academic_year"].id:
            form.cleaned_data["academic_year"] = self.object.academic_year

        if self.object.term != form.cleaned_data["term"]:
            form.cleaned_data["term"] = self.object.term

        messages.success(self.request, _("Report card updated successfully."))
        return super().form_valid(form)


class ReportCardPublishView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = "exams.change_reportcard"

    def post(self, request, pk):
        report_card = get_object_or_404(ReportCard, pk=pk)

        if report_card.status != "published":
            report_card.status = "published"
            report_card.save(update_fields=["status"])

            messages.success(request, _("Report card published successfully."))

            # Notify student and parents if available
            try:
                from src.communications.models import Notification

                # Notify student
                Notification.objects.create(
                    user=report_card.student.user,
                    title=_("Report Card Published"),
                    content=_(
                        "Your report card for {} - {} term has been published."
                    ).format(
                        report_card.academic_year.name, report_card.get_term_display()
                    ),
                    notification_type="Report",
                    reference_id=report_card.id,
                    priority="High",
                )

                # Notify parents
                for relation in report_card.student.student_parent_relations.all():
                    Notification.objects.create(
                        user=relation.parent.user,
                        title=_("Report Card Published"),
                        content=_(
                            "{}'s report card for {} - {} term has been published."
                        ).format(
                            report_card.student.get_full_name(),
                            report_card.academic_year.name,
                            report_card.get_term_display(),
                        ),
                        notification_type="Report",
                        reference_id=report_card.id,
                        priority="High",
                    )
            except Exception:
                pass

        return redirect("exams:report-card-detail", pk=pk)


class ReportCardPrintView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = ReportCard
    permission_required = "exams.view_reportcard"
    template_name = "exams/report_card_print.html"
    context_object_name = "report_card"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get all exam results for this student in this term
        context["exam_results"] = (
            StudentExamResult.objects.filter(
                student=self.object.student,
                exam_schedule__class_obj=self.object.class_obj,
                exam_schedule__exam__academic_year=self.object.academic_year,
            )
            .select_related(
                "exam_schedule", "exam_schedule__subject", "exam_schedule__exam"
            )
            .order_by("exam_schedule__subject__name")
        )

        # Group results by subject
        subjects = {}
        for result in context["exam_results"]:
            subject_name = result.exam_schedule.subject.name

            if subject_name not in subjects:
                subjects[subject_name] = {
                    "name": subject_name,
                    "results": [],
                    "total_marks": 0,
                    "obtained_marks": 0,
                }

            subjects[subject_name]["results"].append(result)
            subjects[subject_name]["total_marks"] += result.exam_schedule.total_marks
            subjects[subject_name]["obtained_marks"] += result.marks_obtained

        # Calculate percentages and grades for each subject
        for subject in subjects.values():
            if subject["total_marks"] > 0:
                subject["percentage"] = (
                    subject["obtained_marks"] / subject["total_marks"]
                ) * 100
                subject["grade"] = ResultService.calculate_grade(
                    subject["percentage"], self.object.academic_year_id
                )
            else:
                subject["percentage"] = 0
                subject["grade"] = "N/A"

        context["subjects"] = list(subjects.values())

        # Get grading system for reference
        context["grading_systems"] = GradingSystem.objects.filter(
            academic_year=self.object.academic_year
        ).order_by("-grade_point")

        # Get school info
        try:
            from src.core.utils import get_system_setting

            context["school_name"] = get_system_setting(
                "site_name", "School Management System"
            )
            context["school_address"] = get_system_setting("school_address", "")
            context["school_phone"] = get_system_setting("school_phone", "")
            context["school_email"] = get_system_setting("school_email", "")
        except Exception:
            context["school_name"] = "School Management System"

        return context


# Student Portal Views
class StudentExamListView(LoginRequiredMixin, ListView):
    template_name = "exams/student/exam_list.html"
    context_object_name = "exams"
    paginate_by = 10

    def get_queryset(self):
        if not hasattr(self.request.user, "student_profile"):
            return []

        student = self.request.user.student_profile

        if not student.current_class:
            return []

        # Get exams for student's class
        return (
            Exam.objects.filter(exam_schedules__class_obj=student.current_class)
            .distinct()
            .select_related("exam_type", "academic_year")
            .order_by("-start_date")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        if hasattr(self.request.user, "student_profile"):
            student = self.request.user.student_profile

            # Get upcoming exams
            today = timezone.now().date()
            context["upcoming_exams"] = (
                Exam.objects.filter(
                    exam_schedules__class_obj=student.current_class,
                    start_date__gte=today,
                )
                .distinct()
                .order_by("start_date")[:5]
            )

            # Get recent exam schedules
            context["recent_schedules"] = (
                ExamSchedule.objects.filter(class_obj=student.current_class)
                .select_related("exam", "subject")
                .order_by("-date")[:10]
            )

        return context


class StudentResultListView(LoginRequiredMixin, ListView):
    template_name = "exams/student/result_list.html"
    context_object_name = "results"
    paginate_by = 20

    def get_queryset(self):
        if not hasattr(self.request.user, "student_profile"):
            return []

        student = self.request.user.student_profile

        # Get all results for the student
        queryset = StudentExamResult.objects.filter(student=student).select_related(
            "exam_schedule", "exam_schedule__exam", "exam_schedule__subject"
        )

        # Apply filters
        exam_id = self.request.GET.get("exam", "")
        if exam_id:
            queryset = queryset.filter(exam_schedule__exam_id=exam_id)

        subject_id = self.request.GET.get("subject", "")
        if subject_id:
            queryset = queryset.filter(exam_schedule__subject_id=subject_id)

        return queryset.order_by("-exam_schedule__date")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        if hasattr(self.request.user, "student_profile"):
            student = self.request.user.student_profile

            # Get exams for filter
            context["exams"] = (
                Exam.objects.filter(exam_schedules__student_results__student=student)
                .distinct()
                .order_by("-start_date")
            )

            # Get subjects for filter
            context["subjects"] = (
                Subject.objects.filter(exam_schedules__student_results__student=student)
                .distinct()
                .order_by("name")
            )

            # Current filters
            context["current_filters"] = {
                "exam": self.request.GET.get("exam", ""),
                "subject": self.request.GET.get("subject", ""),
            }

        return context


class StudentQuizListView(LoginRequiredMixin, ListView):
    template_name = "exams/student/quiz_list.html"
    context_object_name = "quizzes"
    paginate_by = 10

    def get_queryset(self):
        if not hasattr(self.request.user, "student_profile"):
            return []

        student = self.request.user.student_profile

        if not student.current_class:
            return []

        # Get quizzes for student's class
        queryset = Quiz.objects.filter(class_obj=student.current_class).select_related(
            "subject", "teacher", "teacher__user"
        )

        # Apply status filter
        status = self.request.GET.get("status", "")
        if status:
            queryset = queryset.filter(status=status)

        # Apply subject filter
        subject_id = self.request.GET.get("subject", "")
        if subject_id:
            queryset = queryset.filter(subject_id=subject_id)

        return queryset.order_by("-start_datetime")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        if hasattr(self.request.user, "student_profile"):
            student = self.request.user.student_profile

            # Get active quizzes
            now = timezone.now()
            context["active_quizzes"] = QuizService.get_active_quizzes_for_student(
                student.id
            )

            # Get recent attempts
            context["recent_attempts"] = (
                StudentQuizAttempt.objects.filter(student=student)
                .select_related("quiz")
                .order_by("-start_time")[:5]
            )

            # Get subjects for filter
            context["subjects"] = (
                Subject.objects.filter(quizzes__class_obj=student.current_class)
                .distinct()
                .order_by("name")
            )

            # Current filters
            context["current_filters"] = {
                "status": self.request.GET.get("status", ""),
                "subject": self.request.GET.get("subject", ""),
            }

            context["status_choices"] = dict(Quiz.STATUS_CHOICES)

        return context


class StudentReportCardListView(LoginRequiredMixin, ListView):
    template_name = "exams/student/report_card_list.html"
    context_object_name = "report_cards"

    def get_queryset(self):
        if not hasattr(self.request.user, "student_profile"):
            return []

        student = self.request.user.student_profile

        # Get published report cards for the student
        return (
            ReportCard.objects.filter(student=student, status="published")
            .select_related("class_obj", "academic_year")
            .order_by("-academic_year__start_date", "term")
        )
