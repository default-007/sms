from typing import Dict, List, Optional, Tuple, Union

from django.db import transaction
from django.db.models import Avg, Count, F, Q, Sum
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from src.courses.models import AcademicYear, Class, Subject
from src.students.models import Student

from .models import (
    Exam,
    ExamSchedule,
    ExamType,
    GradingSystem,
    Question,
    Quiz,
    ReportCard,
    StudentExamResult,
    StudentQuizAttempt,
    StudentQuizResponse,
)


class ExamService:
    @staticmethod
    def create_exam(
        name: str,
        exam_type_id: int,
        academic_year_id: int,
        start_date,
        end_date,
        description: str,
        created_by_id: int,
    ) -> Exam:
        """Create a new exam."""
        exam = Exam.objects.create(
            name=name,
            exam_type_id=exam_type_id,
            academic_year_id=academic_year_id,
            start_date=start_date,
            end_date=end_date,
            description=description,
            created_by_id=created_by_id,
            status="scheduled",
        )
        return exam

    @staticmethod
    def get_exam_by_id(exam_id: int) -> Optional[Exam]:
        """Get exam by ID."""
        try:
            return Exam.objects.get(id=exam_id)
        except Exam.DoesNotExist:
            return None

    @staticmethod
    def get_exams_by_academic_year(academic_year_id: int) -> List[Exam]:
        """Get all exams for an academic year."""
        return Exam.objects.filter(academic_year_id=academic_year_id)

    @staticmethod
    def get_active_exams() -> List[Exam]:
        """Get currently active exams."""
        today = timezone.now().date()
        return Exam.objects.filter(
            start_date__lte=today, end_date__gte=today, status="ongoing"
        )

    @staticmethod
    def update_exam_status(exam_id: int, status: str) -> bool:
        """Update the status of an exam."""
        try:
            exam = Exam.objects.get(id=exam_id)
            exam.status = status
            exam.save()
            return True
        except Exam.DoesNotExist:
            return False

    @staticmethod
    def add_exam_schedule(
        exam_id: int,
        class_id: int,
        subject_id: int,
        date,
        start_time,
        end_time,
        room: str,
        supervisor_id: int,
        total_marks: int,
        passing_marks: int,
    ) -> ExamSchedule:
        """Add a schedule to an exam."""
        exam_schedule = ExamSchedule.objects.create(
            exam_id=exam_id,
            class_obj_id=class_id,
            subject_id=subject_id,
            date=date,
            start_time=start_time,
            end_time=end_time,
            room=room,
            supervisor_id=supervisor_id,
            total_marks=total_marks,
            passing_marks=passing_marks,
            status="scheduled",
        )
        return exam_schedule

    @staticmethod
    def get_class_exam_schedules(
        class_id: int, exam_id: Optional[int] = None
    ) -> List[ExamSchedule]:
        """Get exam schedules for a class."""
        query = ExamSchedule.objects.filter(class_obj_id=class_id)
        if exam_id:
            query = query.filter(exam_id=exam_id)
        return query.select_related("exam", "subject", "supervisor")


class ResultService:
    @staticmethod
    def enter_student_result(
        student_id: int,
        exam_schedule_id: int,
        marks_obtained: float,
        remarks: str,
        entered_by_id: int,
    ) -> StudentExamResult:
        """Enter or update a student's exam result."""
        # Get exam schedule for total and passing marks
        exam_schedule = ExamSchedule.objects.get(id=exam_schedule_id)

        # Calculate percentage and is_pass
        percentage = (marks_obtained / exam_schedule.total_marks) * 100
        is_pass = marks_obtained >= exam_schedule.passing_marks

        # Get grade based on percentage
        grade = ResultService.calculate_grade(
            percentage, exam_schedule.exam.academic_year_id
        )

        # Create or update result
        result, created = StudentExamResult.objects.update_or_create(
            student_id=student_id,
            exam_schedule_id=exam_schedule_id,
            defaults={
                "marks_obtained": marks_obtained,
                "percentage": percentage,
                "grade": grade,
                "remarks": remarks,
                "is_pass": is_pass,
                "entered_by_id": entered_by_id,
            },
        )

        return result

    @staticmethod
    def calculate_grade(percentage: float, academic_year_id: int) -> str:
        """Calculate grade based on percentage and grading system."""
        grading_systems = GradingSystem.objects.filter(
            academic_year_id=academic_year_id,
            min_percentage__lte=percentage,
            max_percentage__gte=percentage,
        )

        if grading_systems.exists():
            return grading_systems.first().grade_name

        return "N/A"

    @staticmethod
    def get_student_results(
        student_id: int, exam_id: Optional[int] = None
    ) -> List[StudentExamResult]:
        """Get all results for a student, optionally filtered by exam."""
        query = StudentExamResult.objects.filter(student_id=student_id)

        if exam_id:
            query = query.filter(exam_schedule__exam_id=exam_id)

        return query.select_related(
            "exam_schedule", "exam_schedule__exam", "exam_schedule__subject"
        )

    @staticmethod
    def get_class_results(class_id: int, exam_id: int) -> Dict:
        """Get all results for a class in a specific exam."""
        results = StudentExamResult.objects.filter(
            exam_schedule__class_obj_id=class_id, exam_schedule__exam_id=exam_id
        ).select_related(
            "student", "student__user", "exam_schedule", "exam_schedule__subject"
        )

        # Group by student
        student_results = {}
        for result in results:
            student_id = result.student_id
            if student_id not in student_results:
                student_results[student_id] = {
                    "student": result.student,
                    "subjects": {},
                    "total_marks": 0,
                    "total_obtained": 0,
                    "percentage": 0,
                    "grade": "",
                    "is_pass": True,
                }

            subject_name = result.exam_schedule.subject.name
            student_results[student_id]["subjects"][subject_name] = {
                "marks_obtained": result.marks_obtained,
                "total_marks": result.exam_schedule.total_marks,
                "percentage": result.percentage,
                "grade": result.grade,
                "is_pass": result.is_pass,
            }

            student_results[student_id][
                "total_marks"
            ] += result.exam_schedule.total_marks
            student_results[student_id]["total_obtained"] += result.marks_obtained
            if not result.is_pass:
                student_results[student_id]["is_pass"] = False

        # Calculate overall percentage and grade for each student
        for student_id, data in student_results.items():
            if data["total_marks"] > 0:
                data["percentage"] = (
                    data["total_obtained"] / data["total_marks"]
                ) * 100
                data["grade"] = ResultService.calculate_grade(
                    data["percentage"], Exam.objects.get(id=exam_id).academic_year_id
                )

        return student_results

    @staticmethod
    @transaction.atomic
    def generate_report_cards(
        class_id: int, academic_year_id: int, term: str, created_by_id: int
    ) -> Tuple[int, int]:
        """Generate report cards for all students in a class.

        Returns:
            Tuple of (success_count, error_count)
        """
        class_obj = Class.objects.get(id=class_id)
        academic_year = AcademicYear.objects.get(id=academic_year_id)

        # Get all students in the class
        students = Student.objects.filter(current_class_id=class_id)

        # Get all relevant exams for this term and academic year
        exams = Exam.objects.filter(
            academic_year_id=academic_year_id, status="completed"
        )

        success_count = 0
        error_count = 0

        for student in students:
            try:
                # Get all results for this student across relevant exams
                results = StudentExamResult.objects.filter(
                    student_id=student.id,
                    exam_schedule__exam__in=exams,
                    exam_schedule__class_obj_id=class_id,
                ).select_related("exam_schedule")

                if not results.exists():
                    error_count += 1
                    continue

                # Calculate totals
                total_marks = (
                    results.aggregate(total=Sum("exam_schedule__total_marks"))["total"]
                    or 0
                )

                marks_obtained = (
                    results.aggregate(total=Sum("marks_obtained"))["total"] or 0
                )

                if total_marks == 0:
                    error_count += 1
                    continue

                percentage = (marks_obtained / total_marks) * 100
                grade = ResultService.calculate_grade(percentage, academic_year_id)

                # Calculate GPA
                grade_points = GradingSystem.objects.filter(
                    academic_year_id=academic_year_id, grade_name=grade
                ).first()

                grade_point_average = grade_points.grade_point if grade_points else 0

                # Get attendance data if available
                attendance_percentage = None
                try:
                    from src.attendance.models import Attendance

                    attendance_data = Attendance.objects.filter(
                        student_id=student.id, class_obj_id=class_id
                    ).aggregate(
                        total=Count("id"),
                        present=Count("id", filter=Q(status="Present")),
                    )

                    if attendance_data["total"] > 0:
                        attendance_percentage = (
                            attendance_data["present"] / attendance_data["total"]
                        ) * 100
                except (ImportError, AttributeError):
                    pass

                # Create or update report card
                report_card, created = ReportCard.objects.update_or_create(
                    student_id=student.id,
                    class_obj_id=class_id,
                    academic_year_id=academic_year_id,
                    term=term,
                    defaults={
                        "total_marks": total_marks,
                        "marks_obtained": marks_obtained,
                        "percentage": percentage,
                        "grade": grade,
                        "grade_point_average": grade_point_average,
                        "attendance_percentage": attendance_percentage,
                        "created_by_id": created_by_id,
                        "status": "draft",
                    },
                )

                success_count += 1

            except Exception as e:
                error_count += 1
                continue

        return (success_count, error_count)

    @staticmethod
    @transaction.atomic
    def publish_report_cards(report_card_ids: List[int]) -> int:
        """Publish multiple report cards.

        Returns:
            Number of successfully published report cards
        """
        count = ReportCard.objects.filter(id__in=report_card_ids).update(
            status="published"
        )
        return count


class QuizService:
    @staticmethod
    def create_quiz(
        title: str,
        description: str,
        class_id: int,
        subject_id: int,
        teacher_id: int,
        start_datetime,
        end_datetime,
        duration_minutes: int,
        total_marks: int,
        passing_marks: int,
        attempts_allowed: int = 1,
    ) -> Quiz:
        """Create a new quiz."""
        quiz = Quiz.objects.create(
            title=title,
            description=description,
            class_obj_id=class_id,
            subject_id=subject_id,
            teacher_id=teacher_id,
            start_datetime=start_datetime,
            end_datetime=end_datetime,
            duration_minutes=duration_minutes,
            total_marks=total_marks,
            passing_marks=passing_marks,
            attempts_allowed=attempts_allowed,
            status="draft",
        )
        return quiz

    @staticmethod
    def add_question(
        quiz_id: int,
        question_text: str,
        question_type: str,
        options: List[str],
        correct_answer: str,
        explanation: str,
        marks: int,
        difficulty_level: str = "medium",
    ) -> Question:
        """Add a question to a quiz."""
        question = Question.objects.create(
            quiz_id=quiz_id,
            question_text=question_text,
            question_type=question_type,
            options=options,
            correct_answer=correct_answer,
            explanation=explanation,
            marks=marks,
            difficulty_level=difficulty_level,
        )
        return question

    @staticmethod
    def get_active_quizzes_for_student(student_id: int) -> List[Quiz]:
        """Get all currently active quizzes for a student."""
        student = Student.objects.get(id=student_id)
        now = timezone.now()

        return Quiz.objects.filter(
            class_obj=student.current_class,
            start_datetime__lte=now,
            end_datetime__gte=now,
            status="published",
        ).exclude(
            student_attempts__student_id=student_id,
            student_attempts__attempt_number__gte=F("attempts_allowed"),
        )

    @staticmethod
    @transaction.atomic
    def start_quiz_attempt(quiz_id: int, student_id: int) -> StudentQuizAttempt:
        """Start a new attempt for a quiz."""
        quiz = Quiz.objects.get(id=quiz_id)

        # Check if student has remaining attempts
        attempt_count = StudentQuizAttempt.objects.filter(
            quiz_id=quiz_id, student_id=student_id
        ).count()

        if attempt_count >= quiz.attempts_allowed:
            raise ValueError(_("No remaining attempts for this quiz"))

        # Create new attempt
        attempt = StudentQuizAttempt.objects.create(
            student_id=student_id,
            quiz_id=quiz_id,
            start_time=timezone.now(),
            attempt_number=attempt_count + 1,
        )

        return attempt

    @staticmethod
    def submit_response(
        attempt_id: int,
        question_id: int,
        selected_option: Optional[int] = None,
        answer_text: str = "",
    ) -> StudentQuizResponse:
        """Submit a response to a question."""
        attempt = StudentQuizAttempt.objects.get(id=attempt_id)
        question = Question.objects.get(id=question_id)

        # Check if attempt is still ongoing
        if attempt.end_time:
            raise ValueError(_("This attempt has already been completed"))

        # Create or update response
        response, created = StudentQuizResponse.objects.update_or_create(
            student_quiz_attempt_id=attempt_id,
            question_id=question_id,
            defaults={"selected_option": selected_option, "answer_text": answer_text},
        )

        # Auto-evaluate for MCQ and true/false
        if question.question_type in ["mcq", "true_false"]:
            response.evaluate()

        return response

    @staticmethod
    @transaction.atomic
    def complete_quiz_attempt(attempt_id: int) -> StudentQuizAttempt:
        """Complete a quiz attempt and calculate results."""
        attempt = StudentQuizAttempt.objects.get(id=attempt_id)

        # Set end time
        attempt.end_time = timezone.now()
        attempt.save()

        # Calculate results
        attempt.calculate_results()

        return attempt

    @staticmethod
    def get_student_quiz_attempts(
        student_id: int, quiz_id: Optional[int] = None
    ) -> List[StudentQuizAttempt]:
        """Get all quiz attempts for a student."""
        query = StudentQuizAttempt.objects.filter(student_id=student_id)

        if quiz_id:
            query = query.filter(quiz_id=quiz_id)

        return query.select_related("quiz").order_by("-start_time")
