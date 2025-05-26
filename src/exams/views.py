"""
School Management System - Exam Views
File: src/exams/views.py
"""

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.core.paginator import Paginator
from django.db.models import Q, Count, Avg
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
import json
from datetime import datetime, timedelta

from .models import (
    Exam,
    ExamType,
    ExamSchedule,
    StudentExamResult,
    ReportCard,
    ExamQuestion,
    OnlineExam,
    StudentOnlineExamAttempt,
)
from .forms import (
    ExamForm,
    ExamScheduleForm,
    ResultEntryForm,
    ExamQuestionForm,
    OnlineExamConfigForm,
)
from .services.exam_service import ExamService, ResultService
from .services.analytics_service import ExamAnalyticsService
from academics.models import AcademicYear, Term, Class
from students.models import Student


@login_required
def exam_dashboard(request):
    """Main exam dashboard view"""
    current_year = AcademicYear.objects.filter(is_current=True).first()
    current_term = Term.objects.filter(is_current=True).first()

    context = {
        "current_year": current_year,
        "current_term": current_term,
        "recent_exams": Exam.objects.filter(academic_year=current_year).order_by(
            "-created_at"
        )[:5],
        "upcoming_schedules": ExamSchedule.objects.filter(
            date__gte=timezone.now().date(), is_active=True
        ).order_by("date", "start_time")[:10],
        "pending_results": ExamSchedule.objects.filter(
            date__lt=timezone.now().date(), is_completed=False, is_active=True
        ).count(),
    }

    # Add role-specific data
    if hasattr(request.user, "teacher"):
        teacher = request.user.teacher
        context["my_exams"] = ExamSchedule.objects.filter(
            supervisor=teacher, date__gte=timezone.now().date() - timedelta(days=30)
        ).order_by("-date")[:5]

    elif hasattr(request.user, "student"):
        student = request.user.student
        context["my_results"] = StudentExamResult.objects.filter(
            student=student
        ).order_by("-entry_date")[:5]
        context["upcoming_exams"] = ExamSchedule.objects.filter(
            class_obj=student.current_class,
            date__gte=timezone.now().date(),
            exam__is_published=True,
        ).order_by("date", "start_time")[:5]

    return render(request, "exams/dashboard.html", context)


@login_required
def exam_list(request):
    """List all exams with filtering"""
    exams = Exam.objects.select_related("exam_type", "academic_year", "term").order_by(
        "-start_date"
    )

    # Filtering
    academic_year_id = request.GET.get("academic_year")
    term_id = request.GET.get("term")
    exam_type_id = request.GET.get("exam_type")
    status = request.GET.get("status")
    search = request.GET.get("search")

    if academic_year_id:
        exams = exams.filter(academic_year_id=academic_year_id)
    if term_id:
        exams = exams.filter(term_id=term_id)
    if exam_type_id:
        exams = exams.filter(exam_type_id=exam_type_id)
    if status:
        exams = exams.filter(status=status)
    if search:
        exams = exams.filter(
            Q(name__icontains=search) | Q(description__icontains=search)
        )

    # Pagination
    paginator = Paginator(exams, 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "academic_years": AcademicYear.objects.all(),
        "terms": Term.objects.all(),
        "exam_types": ExamType.objects.all(),
        "current_filters": {
            "academic_year": academic_year_id,
            "term": term_id,
            "exam_type": exam_type_id,
            "status": status,
            "search": search,
        },
    }

    return render(request, "exams/exam_list.html", context)


@login_required
def exam_detail(request, exam_id):
    """Exam detail view with schedules and analytics"""
    exam = get_object_or_404(Exam, id=exam_id)

    # Get exam schedules
    schedules = exam.schedules.select_related(
        "class_obj", "subject", "supervisor"
    ).order_by("date", "start_time")

    # Get analytics if exam has results
    analytics = None
    if exam.status in ["ONGOING", "COMPLETED"]:
        try:
            analytics = ExamService.get_exam_analytics(str(exam.id))
        except Exception as e:
            messages.warning(request, f"Could not load analytics: {e}")

    context = {
        "exam": exam,
        "schedules": schedules,
        "analytics": analytics,
        "can_edit": request.user.role in ["ADMIN", "PRINCIPAL"],
        "can_publish": not exam.is_published
        and request.user.role in ["ADMIN", "PRINCIPAL"],
    }

    return render(request, "exams/exam_detail.html", context)


@login_required
def create_exam(request):
    """Create new exam"""
    if request.user.role not in ["ADMIN", "PRINCIPAL"]:
        messages.error(request, "You don't have permission to create exams.")
        return redirect("exams:exam_list")

    if request.method == "POST":
        form = ExamForm(request.POST)
        if form.is_valid():
            exam_data = form.cleaned_data
            exam_data["created_by"] = request.user

            try:
                exam = ExamService.create_exam(exam_data)
                messages.success(request, f"Exam '{exam.name}' created successfully.")
                return redirect("exams:exam_detail", exam_id=exam.id)
            except Exception as e:
                messages.error(request, f"Error creating exam: {e}")
    else:
        form = ExamForm()

    context = {"form": form, "title": "Create New Exam"}

    return render(request, "exams/exam_form.html", context)


@login_required
def exam_schedules(request, exam_id):
    """Manage exam schedules"""
    exam = get_object_or_404(Exam, id=exam_id)

    schedules = exam.schedules.select_related(
        "class_obj", "subject", "supervisor"
    ).order_by("date", "start_time")

    context = {
        "exam": exam,
        "schedules": schedules,
        "can_edit": request.user.role in ["ADMIN", "PRINCIPAL", "TEACHER"],
    }

    return render(request, "exams/exam_schedules.html", context)


@login_required
def create_exam_schedule(request, exam_id):
    """Create exam schedule"""
    exam = get_object_or_404(Exam, id=exam_id)

    if request.method == "POST":
        form = ExamScheduleForm(request.POST)
        if form.is_valid():
            schedule = form.save(commit=False)
            schedule.exam = exam

            # Check for conflicts
            from .utils import ExamUtils

            conflicts = ExamUtils.check_exam_conflicts(
                date=schedule.date,
                start_time=schedule.start_time,
                end_time=schedule.end_time,
                teacher_id=str(schedule.supervisor.id) if schedule.supervisor else None,
                room=schedule.room,
                class_id=str(schedule.class_obj.id),
            )

            if conflicts:
                for conflict in conflicts:
                    messages.warning(request, conflict["message"])
            else:
                schedule.save()
                form.save_m2m()
                messages.success(request, "Exam schedule created successfully.")
                return redirect("exams:exam_schedules", exam_id=exam.id)
    else:
        form = ExamScheduleForm()

    context = {"form": form, "exam": exam, "title": f"Create Schedule for {exam.name}"}

    return render(request, "exams/exam_schedule_form.html", context)


@login_required
def result_entry(request, schedule_id):
    """Bulk result entry for exam schedule"""
    schedule = get_object_or_404(ExamSchedule, id=schedule_id)

    # Check permissions
    if request.user.role == "TEACHER" and schedule.supervisor.user != request.user:
        messages.error(request, "You can only enter results for your supervised exams.")
        return redirect("exams:exam_schedules", exam_id=schedule.exam.id)

    # Get students for this class
    students = schedule.class_obj.students.filter(status="ACTIVE").order_by(
        "user__last_name", "user__first_name"
    )

    # Get existing results
    existing_results = {
        result.student.id: result
        for result in StudentExamResult.objects.filter(exam_schedule=schedule)
    }

    if request.method == "POST":
        results_data = []
        errors = []

        for student in students:
            student_id = str(student.id)
            marks_key = f"marks_{student_id}"
            absent_key = f"absent_{student_id}"
            remarks_key = f"remarks_{student_id}"

            if marks_key in request.POST or absent_key in request.POST:
                is_absent = absent_key in request.POST
                marks_obtained = 0

                if not is_absent:
                    try:
                        marks_obtained = float(request.POST.get(marks_key, 0))
                        if marks_obtained < 0 or marks_obtained > schedule.total_marks:
                            errors.append(
                                f"Invalid marks for {student.user.get_full_name()}"
                            )
                            continue
                    except ValueError:
                        errors.append(
                            f"Invalid marks format for {student.user.get_full_name()}"
                        )
                        continue

                results_data.append(
                    {
                        "student_id": student_id,
                        "marks_obtained": str(marks_obtained),
                        "is_absent": is_absent,
                        "remarks": request.POST.get(remarks_key, ""),
                    }
                )

        if not errors:
            try:
                ResultService.enter_results(schedule_id, results_data, request.user)
                messages.success(
                    request,
                    f"Results entered successfully for {len(results_data)} students.",
                )
                return redirect("exams:exam_schedules", exam_id=schedule.exam.id)
            except Exception as e:
                messages.error(request, f"Error entering results: {e}")
        else:
            for error in errors:
                messages.error(request, error)

    context = {
        "schedule": schedule,
        "students": students,
        "existing_results": existing_results,
        "total_marks": schedule.total_marks,
    }

    return render(request, "exams/result_entry.html", context)


@login_required
def student_results(request, student_id=None):
    """View student exam results"""
    if student_id:
        student = get_object_or_404(Student, id=student_id)
        # Check permissions
        if (request.user.role == "STUDENT" and request.user.student != student) or (
            request.user.role == "PARENT"
            and student not in request.user.parent.students.all()
        ):
            messages.error(request, "You don't have permission to view these results.")
            return redirect("exams:dashboard")
    else:
        if request.user.role == "STUDENT":
            student = request.user.student
        else:
            messages.error(request, "Student ID required.")
            return redirect("exams:dashboard")

    # Get results
    results = (
        StudentExamResult.objects.filter(student=student)
        .select_related("exam_schedule__exam", "exam_schedule__subject", "term")
        .order_by("-exam_schedule__exam__start_date")
    )

    # Get report cards
    report_cards = ReportCard.objects.filter(student=student).order_by(
        "-academic_year__start_date", "-term__term_number"
    )

    # Get progress analytics
    current_year = AcademicYear.objects.filter(is_current=True).first()
    progress_data = None
    if current_year:
        try:
            progress_data = ExamAnalyticsService.get_student_progress_report(
                str(student.id), str(current_year.id)
            )
        except Exception as e:
            messages.warning(request, f"Could not load progress data: {e}")

    context = {
        "student": student,
        "results": results,
        "report_cards": report_cards,
        "progress_data": progress_data,
    }

    return render(request, "exams/student_results.html", context)


@login_required
def report_card_detail(request, report_card_id):
    """View detailed report card"""
    report_card = get_object_or_404(ReportCard, id=report_card_id)

    # Check permissions
    if request.user.role == "STUDENT" and request.user.student != report_card.student:
        messages.error(request, "You don't have permission to view this report card.")
        return redirect("exams:dashboard")
    elif (
        request.user.role == "PARENT"
        and report_card.student not in request.user.parent.students.all()
    ):
        messages.error(request, "You don't have permission to view this report card.")
        return redirect("exams:dashboard")

    # Get subject-wise results
    subject_results = (
        StudentExamResult.objects.filter(
            student=report_card.student, term=report_card.term
        )
        .select_related("exam_schedule__subject")
        .order_by("exam_schedule__subject__name")
    )

    context = {"report_card": report_card, "subject_results": subject_results}

    return render(request, "exams/report_card_detail.html", context)


@login_required
def question_bank(request):
    """Manage question bank"""
    if request.user.role not in ["ADMIN", "TEACHER", "PRINCIPAL"]:
        messages.error(
            request, "You don't have permission to access the question bank."
        )
        return redirect("exams:dashboard")

    questions = ExamQuestion.objects.select_related(
        "subject", "grade", "created_by"
    ).order_by("-created_at")

    # Filtering
    subject_id = request.GET.get("subject")
    grade_id = request.GET.get("grade")
    question_type = request.GET.get("question_type")
    difficulty = request.GET.get("difficulty")
    search = request.GET.get("search")

    if subject_id:
        questions = questions.filter(subject_id=subject_id)
    if grade_id:
        questions = questions.filter(grade_id=grade_id)
    if question_type:
        questions = questions.filter(question_type=question_type)
    if difficulty:
        questions = questions.filter(difficulty_level=difficulty)
    if search:
        questions = questions.filter(
            Q(question_text__icontains=search) | Q(topic__icontains=search)
        )

    # Teacher can only see their own questions
    if request.user.role == "TEACHER":
        questions = questions.filter(created_by=request.user)

    # Pagination
    paginator = Paginator(questions, 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "current_filters": {
            "subject": subject_id,
            "grade": grade_id,
            "question_type": question_type,
            "difficulty": difficulty,
            "search": search,
        },
    }

    return render(request, "exams/question_bank.html", context)


@login_required
def create_question(request):
    """Create exam question"""
    if request.user.role not in ["ADMIN", "TEACHER", "PRINCIPAL"]:
        messages.error(request, "You don't have permission to create questions.")
        return redirect("exams:question_bank")

    if request.method == "POST":
        form = ExamQuestionForm(request.POST)
        if form.is_valid():
            question = form.save(commit=False)
            question.created_by = request.user
            question.save()
            messages.success(request, "Question created successfully.")
            return redirect("exams:question_bank")
    else:
        form = ExamQuestionForm()

    context = {"form": form, "title": "Create New Question"}

    return render(request, "exams/question_form.html", context)


@login_required
def exam_analytics_view(request, exam_id):
    """View exam analytics"""
    exam = get_object_or_404(Exam, id=exam_id)

    try:
        analytics = ExamService.get_exam_analytics(str(exam.id))
    except Exception as e:
        messages.error(request, f"Could not load analytics: {e}")
        analytics = {}

    context = {"exam": exam, "analytics": analytics}

    return render(request, "exams/exam_analytics.html", context)


@require_http_methods(["POST"])
@login_required
def publish_exam(request, exam_id):
    """Publish exam (AJAX)"""
    if request.user.role not in ["ADMIN", "PRINCIPAL"]:
        return JsonResponse({"error": "Permission denied"}, status=403)

    try:
        exam = ExamService.publish_exam(exam_id)
        return JsonResponse(
            {
                "success": True,
                "message": f"Exam '{exam.name}' published successfully.",
                "status": exam.status,
                "is_published": exam.is_published,
            }
        )
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)


@require_http_methods(["GET"])
@login_required
def get_exam_statistics(request, exam_id):
    """Get exam statistics (AJAX)"""
    try:
        analytics = ExamService.get_exam_analytics(exam_id)
        return JsonResponse(analytics)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)
