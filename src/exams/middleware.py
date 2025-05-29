"""
School Management System - Exam Middleware
File: src/exams/middleware.py
"""

from django.http import JsonResponse
from django.utils import timezone
from django.utils.deprecation import MiddlewareMixin

from .models import StudentOnlineExamAttempt


class OnlineExamSecurityMiddleware(MiddlewareMixin):
    """Middleware for online exam security measures"""

    def process_request(self, request):
        # Check if this is an online exam session
        if (
            request.path.startswith("/api/exams/online-")
            and request.user.is_authenticated
        ):

            # Check for active exam attempts
            active_attempts = StudentOnlineExamAttempt.objects.filter(
                student__user=request.user, status="IN_PROGRESS"
            )

            for attempt in active_attempts:
                online_exam = attempt.online_exam

                # Check if time limit exceeded
                if online_exam.time_limit_minutes:
                    time_limit_seconds = online_exam.time_limit_minutes * 60
                    elapsed_time = (timezone.now() - attempt.start_time).total_seconds()

                    if elapsed_time > time_limit_seconds:
                        # Auto-submit the exam
                        attempt.status = "TIMED_OUT"
                        attempt.submit_time = timezone.now()
                        attempt.save()

                        return JsonResponse(
                            {
                                "error": "Exam time limit exceeded. Your exam has been automatically submitted.",
                                "code": "TIME_LIMIT_EXCEEDED",
                            },
                            status=408,
                        )

                # Add attempt ID to request for tracking
                request.current_exam_attempt = attempt

        return None
