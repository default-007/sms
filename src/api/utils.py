from django.utils import timezone
from rest_framework.response import Response


def get_current_academic_year():
    """
    Get the current academic year.
    """
    from src.courses.models import AcademicYear

    try:
        return AcademicYear.objects.get(is_current=True)
    except AcademicYear.DoesNotExist:
        # Fall back to the academic year that encompasses the current date
        today = timezone.now().date()
        return AcademicYear.objects.filter(
            start_date__lte=today, end_date__gte=today
        ).first()


def api_response(data=None, message=None, status="success", status_code=200):
    """
    Standard API response format.
    """
    response_data = {"status": status, "message": message, "data": data}

    if data is None and message is None:
        # Default message based on status
        if status == "success":
            response_data["message"] = "Operation completed successfully."
        else:
            response_data["message"] = "Operation failed."

    return Response(response_data, status=status_code)
