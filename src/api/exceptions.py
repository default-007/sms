from rest_framework.views import exception_handler
from rest_framework.exceptions import APIException
from rest_framework import status


class ServiceError(APIException):
    """
    Exception raised when a service operation fails.
    """

    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Service operation failed."
    default_code = "service_error"


def custom_exception_handler(exc, context):
    """
    Custom exception handler for API views.
    """
    response = exception_handler(exc, context)

    if response is not None:
        # Format the response to match our standard format
        response.data = {
            "status": "error",
            "message": str(exc),
            "errors": response.data if hasattr(response, "data") else {},
        }

        # Add error code if available
        if hasattr(exc, "default_code"):
            response.data["code"] = exc.default_code

    return response
