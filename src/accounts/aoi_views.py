# src/accounts/api_views.py

import logging
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_POST
from django.utils.decorators import method_decorator
from django.middleware.csrf import get_token
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status

from .services.authentication_service import UnifiedAuthenticationService
from .forms import QuickLoginForm, IdentifierValidationForm
from .utils import get_client_info, mask_identifier

logger = logging.getLogger(__name__)


@csrf_exempt
@require_POST
def api_login(request):
    """
    API endpoint for login via AJAX/mobile apps.
    Returns JSON response with authentication status and user info.
    """
    try:
        form = QuickLoginForm(request.POST)

        if form.is_valid():
            user = form.get_user()

            # Generate tokens
            tokens = UnifiedAuthenticationService.generate_tokens_for_user(user)

            # Log successful login
            client_info = get_client_info(request)

            return JsonResponse(
                {
                    "success": True,
                    "message": f"Welcome back, {user.get_display_name()}!",
                    "user": {
                        "id": user.id,
                        "username": user.username,
                        "email": user.email,
                        "full_name": user.get_full_name(),
                        "first_name": user.first_name,
                        "last_name": user.last_name,
                        "is_student": getattr(user, "is_student", False),
                        "is_teacher": getattr(user, "is_teacher", False),
                        "is_staff": user.is_staff,
                        "is_superuser": user.is_superuser,
                        "date_joined": user.date_joined.isoformat(),
                        "last_login": (
                            user.last_login.isoformat() if user.last_login else None
                        ),
                    },
                    "tokens": tokens,
                    "session_info": {
                        "session_key": request.session.session_key,
                        "csrf_token": get_token(request),
                    },
                    "login_info": {
                        "identifier_type": form._detect_identifier_type(
                            form.cleaned_data["identifier"]
                        ),
                        "ip_address": client_info.get("ip_address"),
                        "user_agent": client_info.get("browser"),
                        "device_type": (
                            "mobile" if client_info.get("is_mobile") else "desktop"
                        ),
                    },
                }
            )
        else:
            # Form validation failed
            return JsonResponse(
                {
                    "success": False,
                    "message": "Invalid login credentials",
                    "errors": form.errors,
                    "csrf_token": get_token(request),
                },
                status=400,
            )

    except Exception as e:
        logger.error(f"API login error: {str(e)}")
        return JsonResponse(
            {
                "success": False,
                "message": "Login failed due to server error",
                "error": "INTERNAL_ERROR",
            },
            status=500,
        )


@require_POST
@login_required
def api_logout(request):
    """API endpoint for logout."""
    try:
        user = request.user

        # Use authentication service for logout
        UnifiedAuthenticationService.logout_user(user, request)

        # Django logout
        logout(request)

        return JsonResponse({"success": True, "message": "Successfully logged out"})

    except Exception as e:
        logger.error(f"API logout error: {str(e)}")
        return JsonResponse(
            {"success": False, "message": "Logout failed", "error": str(e)}, status=500
        )


@require_POST
def api_validate_identifier(request):
    """
    API endpoint to validate identifier format and existence.
    """
    try:
        identifier = request.POST.get("identifier", "").strip()

        if not identifier:
            return JsonResponse(
                {
                    "valid": False,
                    "message": "Identifier is required",
                    "identifier_type": None,
                }
            )

        # Detect identifier type
        identifier_type = UnifiedAuthenticationService._get_identifier_type(identifier)

        # Check if user exists
        user = UnifiedAuthenticationService._find_user_by_identifier(identifier)

        response_data = {
            "valid": user is not None,
            "identifier_type": identifier_type,
            "masked_identifier": mask_identifier(identifier, identifier_type),
        }

        if user:
            response_data.update(
                {
                    "message": f'Account found for this {identifier_type.replace("_", " ")}',
                    "user_type": (
                        "student" if getattr(user, "is_student", False) else "staff"
                    ),
                    "account_status": "active" if user.is_active else "inactive",
                    "requires_2fa": getattr(user, "two_factor_enabled", False),
                }
            )
        else:
            response_data.update(
                {
                    "message": f'No account found with this {identifier_type.replace("_", " ")}',
                    "suggestions": _get_identifier_suggestions(
                        identifier, identifier_type
                    ),
                }
            )

        return JsonResponse(response_data)

    except Exception as e:
        logger.error(f"API validate identifier error: {str(e)}")
        return JsonResponse(
            {
                "valid": False,
                "message": "Validation failed due to server error",
                "error": "INTERNAL_ERROR",
            },
            status=500,
        )


@login_required
def api_user_info(request):
    """API endpoint to get current user information."""
    try:
        user = request.user

        # Get user roles
        roles = []
        if hasattr(user, "role_assignments"):
            roles = [
                {
                    "name": assignment.role.name,
                    "description": assignment.role.description,
                    "is_active": assignment.is_active,
                }
                for assignment in user.role_assignments.filter(is_active=True)
            ]

        # Get student info if applicable
        student_info = None
        if getattr(user, "is_student", False):
            try:
                from src.students.models import Student

                student = Student.objects.get(user=user)
                student_info = {
                    "admission_number": student.admission_number,
                    "current_class": (
                        str(student.current_class) if student.current_class else None
                    ),
                    "roll_number": student.roll_number,
                    "status": student.status,
                    "admission_date": student.admission_date.isoformat(),
                }
            except (Student.DoesNotExist, ImportError):
                pass

        return JsonResponse(
            {
                "success": True,
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "phone_number": user.phone_number,
                    "full_name": user.get_full_name(),
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "is_active": user.is_active,
                    "is_student": getattr(user, "is_student", False),
                    "is_teacher": getattr(user, "is_teacher", False),
                    "is_staff": user.is_staff,
                    "is_superuser": user.is_superuser,
                    "date_joined": user.date_joined.isoformat(),
                    "last_login": (
                        user.last_login.isoformat() if user.last_login else None
                    ),
                    "email_verified": getattr(user, "email_verified", False),
                    "phone_verified": getattr(user, "phone_verified", False),
                    "two_factor_enabled": getattr(user, "two_factor_enabled", False),
                },
                "roles": roles,
                "student_info": student_info,
                "permissions": _get_user_permissions(user),
            }
        )

    except Exception as e:
        logger.error(f"API user info error: {str(e)}")
        return JsonResponse(
            {
                "success": False,
                "message": "Failed to retrieve user information",
                "error": "INTERNAL_ERROR",
            },
            status=500,
        )


@login_required
def api_user_profile(request):
    """API endpoint for user profile management."""
    if request.method == "GET":
        return api_user_info(request)

    elif request.method == "POST":
        try:
            user = request.user

            # Update allowed fields
            allowed_fields = ["first_name", "last_name", "email", "phone_number"]
            updated_fields = []

            for field in allowed_fields:
                if field in request.POST:
                    new_value = request.POST[field].strip()
                    if new_value != getattr(user, field, ""):
                        setattr(user, field, new_value)
                        updated_fields.append(field)

            if updated_fields:
                user.save(update_fields=updated_fields)

                # Log profile update
                from .models import UserAuditLog

                UserAuditLog.objects.create(
                    user=user,
                    action="profile_update",
                    description=f'Profile updated: {", ".join(updated_fields)}',
                    ip_address=get_client_info(request).get("ip_address"),
                    extra_data={"updated_fields": updated_fields},
                )

            return JsonResponse(
                {
                    "success": True,
                    "message": (
                        "Profile updated successfully"
                        if updated_fields
                        else "No changes made"
                    ),
                    "updated_fields": updated_fields,
                }
            )

        except Exception as e:
            logger.error(f"API user profile update error: {str(e)}")
            return JsonResponse(
                {
                    "success": False,
                    "message": "Failed to update profile",
                    "error": str(e),
                },
                status=500,
            )


def api_auth_status(request):
    """API endpoint to check authentication status."""
    return JsonResponse(
        {
            "authenticated": request.user.is_authenticated,
            "user_id": request.user.id if request.user.is_authenticated else None,
            "username": (
                request.user.username if request.user.is_authenticated else None
            ),
            "csrf_token": get_token(request),
            "session_key": request.session.session_key,
        }
    )


# Utility functions for API views


def _get_identifier_suggestions(identifier, identifier_type):
    """Get helpful suggestions for invalid identifiers."""
    suggestions = []

    if identifier_type == "email":
        if "@" not in identifier:
            suggestions.append("Make sure to include @ symbol")
        elif "." not in identifier.split("@")[-1]:
            suggestions.append("Include domain extension (.com, .edu, etc.)")
        else:
            suggestions.append("Check for typos in email address")

    elif identifier_type == "phone":
        if (
            len(
                identifier.replace(" ", "")
                .replace("-", "")
                .replace("(", "")
                .replace(")", "")
            )
            < 10
        ):
            suggestions.append("Phone number should have at least 10 digits")
        else:
            suggestions.append("Try with or without country code")

    elif identifier_type == "admission_number":
        suggestions.extend(
            [
                "Check with school administration for correct format",
                "Admission numbers are usually provided during enrollment",
                "Try uppercase letters if applicable",
            ]
        )

    elif identifier_type == "username":
        suggestions.extend(
            [
                "Check for typos in username",
                "Username might be case-sensitive",
                "Try your email address instead",
            ]
        )

    return suggestions


def _get_user_permissions(user):
    """Get user permissions for API response."""
    permissions = {
        "can_view_users": False,
        "can_edit_users": False,
        "can_delete_users": False,
        "can_view_reports": False,
        "can_manage_roles": False,
    }

    # Check user permissions
    if hasattr(user, "has_permission"):
        permissions.update(
            {
                "can_view_users": user.has_permission("users", "view"),
                "can_edit_users": user.has_permission("users", "change"),
                "can_delete_users": user.has_permission("users", "delete"),
                "can_view_reports": user.has_permission("reports", "view"),
                "can_manage_roles": user.has_permission("roles", "change"),
            }
        )
    elif user.is_staff or user.is_superuser:
        # Default permissions for staff/admin
        permissions.update(
            {
                "can_view_users": True,
                "can_edit_users": True,
                "can_delete_users": user.is_superuser,
                "can_view_reports": True,
                "can_manage_roles": user.is_superuser,
            }
        )

    return permissions


# Legacy imports for backward compatibility
validate_identifier = api_validate_identifier
