# src/accounts/api/views.py

import csv
from io import StringIO
from typing import Any, Dict

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Count, Q
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet
from rest_framework_simplejwt.views import TokenObtainPairView

from ..models import User, UserRole, UserRoleAssignment, UserAuditLog
from ..permissions import IsAdmin, CanManageUsers
from ..services import AuthenticationService, RoleService
from .serializers import (
    BulkUserActionSerializer,
    CustomTokenObtainPairSerializer,
    OTPSerializer,
    PasswordChangeSerializer,
    PasswordResetSerializer,
    UserAuditLogSerializer,
    UserCreateSerializer,
    UserDetailSerializer,
    UserListSerializer,
    UserRoleSerializer,
    UserStatsSerializer,
    UserUpdateSerializer,
)

User = get_user_model()


class CustomTokenObtainPairView(TokenObtainPairView):
    """Custom token view that supports email/phone login."""

    serializer_class = CustomTokenObtainPairSerializer


class UserViewSet(ModelViewSet):
    """ViewSet for managing users."""

    queryset = (
        User.objects.select_related("profile")
        .prefetch_related("role_assignments__role")
        .order_by("-date_joined")
    )
    permission_classes = [permissions.IsAuthenticated, CanManageUsers]

    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == "list":
            return UserListSerializer
        elif self.action == "create":
            return UserCreateSerializer
        elif self.action in ["update", "partial_update"]:
            return UserUpdateSerializer
        return UserDetailSerializer

    def get_queryset(self):
        """Filter queryset based on permissions and query parameters."""
        queryset = super().get_queryset()

        # Filter by search query
        search = self.request.query_params.get("search", "").strip()
        if search:
            queryset = queryset.filter(
                Q(username__icontains=search)
                | Q(email__icontains=search)
                | Q(first_name__icontains=search)
                | Q(last_name__icontains=search)
            )

        # Filter by role
        role = self.request.query_params.get("role", "").strip()
        if role:
            queryset = queryset.filter(
                role_assignments__role__name=role, role_assignments__is_active=True
            ).distinct()

        # Filter by status
        status_filter = self.request.query_params.get("status", "").strip()
        if status_filter == "active":
            queryset = queryset.filter(is_active=True)
        elif status_filter == "inactive":
            queryset = queryset.filter(is_active=False)
        elif status_filter == "locked":
            queryset = queryset.filter(failed_login_attempts__gte=5)
        elif status_filter == "password_change":
            queryset = queryset.filter(requires_password_change=True)

        return queryset

    @action(detail=True, methods=["post"])
    def change_password(self, request, pk=None):
        """Change user password."""
        user = self.get_object()

        # Only allow users to change their own password or admins
        if user != request.user and not request.user.has_role("Admin"):
            return Response(
                {"error": "Permission denied"}, status=status.HTTP_403_FORBIDDEN
            )

        serializer = PasswordChangeSerializer(
            data=request.data, context={"request": request}
        )

        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Password changed successfully"})

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"], permission_classes=[IsAdmin])
    def reset_password(self, request, pk=None):
        """Reset user password (admin only)."""
        user = self.get_object()
        serializer = PasswordResetSerializer(
            data=request.data, context={"request": request}
        )

        if serializer.is_valid():
            new_password = serializer.save(user)
            return Response(
                {
                    "message": "Password reset successfully",
                    "temporary_password": new_password,
                }
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"], permission_classes=[IsAdmin])
    def toggle_status(self, request, pk=None):
        """Toggle user active status."""
        user = self.get_object()
        user.is_active = not user.is_active
        user.save()

        return Response(
            {
                "message": f'User {"activated" if user.is_active else "deactivated"} successfully',
                "is_active": user.is_active,
            }
        )

    @action(detail=True, methods=["post"], permission_classes=[IsAdmin])
    def unlock_account(self, request, pk=None):
        """Unlock user account."""
        user = self.get_object()
        AuthenticationService.unlock_account(user, request.user)

        return Response({"message": "Account unlocked successfully"})

    @action(detail=True, methods=["get"])
    def audit_logs(self, request, pk=None):
        """Get user audit logs."""
        user = self.get_object()
        logs = user.audit_logs.order_by("-timestamp")[:50]  # Last 50 logs
        serializer = UserAuditLogSerializer(logs, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def login_statistics(self, request, pk=None):
        """Get user login statistics."""
        user = self.get_object()
        days = int(request.query_params.get("days", 30))
        stats = AuthenticationService.get_login_statistics(user, days)
        return Response(stats)

    @action(detail=True, methods=["get"])
    def suspicious_activity(self, request, pk=None):
        """Check for suspicious activity."""
        user = self.get_object()
        hours = int(request.query_params.get("hours", 24))
        activity = AuthenticationService.check_suspicious_activity(user, hours)
        return Response(activity)

    @action(detail=False, methods=["post"], permission_classes=[IsAdmin])
    def bulk_action(self, request):
        """Perform bulk actions on users."""
        serializer = BulkUserActionSerializer(data=request.data)

        if serializer.is_valid():
            user_ids = serializer.validated_data["user_ids"]
            action_type = serializer.validated_data["action"]
            roles = serializer.validated_data.get("roles", [])

            users = User.objects.filter(id__in=user_ids)
            affected_count = 0

            with transaction.atomic():
                if action_type == "activate":
                    affected_count = users.update(is_active=True)
                elif action_type == "deactivate":
                    affected_count = users.update(is_active=False)
                elif action_type == "require_password_change":
                    affected_count = users.update(requires_password_change=True)
                elif action_type == "unlock_accounts":
                    affected_count = users.update(
                        failed_login_attempts=0, last_failed_login=None
                    )
                elif action_type == "assign_roles":
                    affected_count = RoleService.bulk_assign_roles(
                        users, roles, request.user
                    )
                elif action_type == "remove_roles":
                    for user in users:
                        for role_name in roles:
                            RoleService.remove_role_from_user(
                                user, role_name, request.user
                            )
                    affected_count = users.count()

            return Response(
                {
                    "message": f'{action_type.replace("_", " ").title()} applied to {affected_count} users'
                }
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(
        detail=False, methods=["get"], permission_classes=[permissions.IsAuthenticated]
    )
    def export(self, request):
        """Export users to CSV."""
        if not RoleService.check_permission(request.user, "users", "view"):
            return Response(
                {"error": "Permission denied"}, status=status.HTTP_403_FORBIDDEN
            )

        # Get filtered queryset
        queryset = self.filter_queryset(self.get_queryset())

        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = (
            f'attachment; filename="users_{timezone.now().date()}.csv"'
        )

        writer = csv.writer(response)
        writer.writerow(
            [
                "Username",
                "Email",
                "First Name",
                "Last Name",
                "Phone",
                "Status",
                "Roles",
                "Date Joined",
                "Last Login",
            ]
        )

        for user in queryset:
            roles = ", ".join(
                [
                    assignment.role.name
                    for assignment in user.role_assignments.filter(is_active=True)
                ]
            )
            writer.writerow(
                [
                    user.username,
                    user.email,
                    user.first_name,
                    user.last_name,
                    user.phone_number,
                    "Active" if user.is_active else "Inactive",
                    roles,
                    user.date_joined.strftime("%Y-%m-%d"),
                    (
                        user.last_login.strftime("%Y-%m-%d %H:%M")
                        if user.last_login
                        else "Never"
                    ),
                ]
            )

        return response


class UserRoleViewSet(ModelViewSet):
    """ViewSet for managing user roles."""

    queryset = UserRole.objects.annotate(
        user_count=Count("user_assignments", filter=Q(user_assignments__is_active=True))
    ).order_by("name")
    serializer_class = UserRoleSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdmin]

    def get_queryset(self):
        """Filter by custom roles if requested."""
        queryset = super().get_queryset()

        show_system = (
            self.request.query_params.get("include_system", "false").lower() == "true"
        )
        if not show_system:
            queryset = queryset.filter(is_system_role=False)

        return queryset

    def destroy(self, request, *args, **kwargs):
        """Prevent deletion of system roles."""
        role = self.get_object()

        if role.is_system_role:
            return Response(
                {"error": "System roles cannot be deleted"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=["get"])
    def users(self, request, pk=None):
        """Get users assigned to this role."""
        role = self.get_object()
        users = RoleService.get_users_with_role(role.name)
        serializer = UserListSerializer(users, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def statistics(self, request):
        """Get role statistics."""
        stats = RoleService.get_role_statistics()
        return Response(stats)


class UserStatsView(APIView):
    """View for user statistics."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """Get comprehensive user statistics."""
        if not RoleService.check_permission(request.user, "users", "view"):
            return Response(
                {"error": "Permission denied"}, status=status.HTTP_403_FORBIDDEN
            )

        # Basic stats
        total_users = User.objects.count()
        active_users = User.objects.filter(is_active=True).count()
        inactive_users = User.objects.filter(is_active=False).count()
        locked_users = User.objects.filter(failed_login_attempts__gte=5).count()

        # Recent registrations (last 30 days)
        thirty_days_ago = timezone.now() - timezone.timedelta(days=30)
        recent_registrations = User.objects.filter(
            date_joined__gte=thirty_days_ago
        ).count()

        # Users requiring password change
        users_requiring_password_change = User.objects.filter(
            requires_password_change=True
        ).count()

        # Role distribution
        role_distribution = {}
        for role in UserRole.objects.all():
            count = (
                User.objects.filter(
                    role_assignments__role=role, role_assignments__is_active=True
                )
                .distinct()
                .count()
            )
            role_distribution[role.name] = count

        # Login statistics (last 30 days)
        login_stats = UserAuditLog.objects.filter(
            action="login", timestamp__gte=thirty_days_ago
        )

        total_logins = login_stats.count()
        successful_logins = login_stats.filter(
            description__contains="Successful"
        ).count()
        failed_logins = total_logins - successful_logins

        login_statistics = {
            "total_attempts": total_logins,
            "successful_logins": successful_logins,
            "failed_logins": failed_logins,
            "success_rate": (
                (successful_logins / total_logins * 100) if total_logins > 0 else 0
            ),
        }

        stats = {
            "total_users": total_users,
            "active_users": active_users,
            "inactive_users": inactive_users,
            "locked_users": locked_users,
            "recent_registrations": recent_registrations,
            "users_requiring_password_change": users_requiring_password_change,
            "role_distribution": role_distribution,
            "login_statistics": login_statistics,
        }

        serializer = UserStatsSerializer(stats)
        return Response(serializer.data)


class ProfileView(generics.RetrieveUpdateAPIView):
    """View for user profile management."""

    serializer_class = UserDetailSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        """Return the current user."""
        return self.request.user


class SendOTPView(APIView):
    """View for sending OTP to user."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        """Send OTP to current user."""
        purpose = request.data.get("purpose", "verification")
        otp = AuthenticationService.send_otp(request.user, purpose)

        return Response(
            {
                "message": "OTP sent successfully",
                "otp": (
                    otp if request.user.is_staff else None
                ),  # Only show OTP for staff in dev
            }
        )


class VerifyOTPView(APIView):
    """View for verifying OTP."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        """Verify OTP for current user."""
        serializer = OTPSerializer(data=request.data)

        if serializer.is_valid():
            otp = serializer.validated_data["otp"]
            purpose = serializer.validated_data["purpose"]

            is_valid = AuthenticationService.verify_otp(request.user, otp, purpose)

            if is_valid:
                return Response({"message": "OTP verified successfully"})
            else:
                return Response(
                    {"error": "Invalid or expired OTP"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class BulkUserImportView(APIView):
    """View for bulk user import via CSV."""

    permission_classes = [permissions.IsAuthenticated, IsAdmin]
    parser_classes = [MultiPartParser]

    def post(self, request):
        """Import users from CSV file."""
        csv_file = request.FILES.get("csv_file")
        default_password = request.data.get("default_password", "changeme123")
        default_roles = request.data.getlist("default_roles")
        send_emails = request.data.get("send_welcome_emails", "true").lower() == "true"

        if not csv_file:
            return Response(
                {"error": "CSV file is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Read CSV content
            csv_content = csv_file.read().decode("utf-8")
            csv_file_obj = StringIO(csv_content)
            reader = csv.DictReader(csv_file_obj)

            required_fields = ["username", "email", "first_name", "last_name"]
            if not all(field in reader.fieldnames for field in required_fields):
                return Response(
                    {
                        "error": f'CSV must contain columns: {", ".join(required_fields)}'
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            created_count = 0
            errors = []

            with transaction.atomic():
                for row_num, row in enumerate(reader, start=2):
                    try:
                        # Check for existing user
                        if User.objects.filter(
                            Q(username=row["username"]) | Q(email=row["email"])
                        ).exists():
                            errors.append(f"Row {row_num}: User already exists")
                            continue

                        # Create user
                        user_data = {
                            "username": row["username"],
                            "email": row["email"],
                            "first_name": row["first_name"],
                            "last_name": row["last_name"],
                            "phone_number": row.get("phone_number", ""),
                            "password": default_password,
                        }

                        user = AuthenticationService.register_user(
                            user_data,
                            role_names=default_roles,
                            created_by=request.user,
                            send_email=send_emails,
                        )

                        created_count += 1

                    except Exception as e:
                        errors.append(f"Row {row_num}: {str(e)}")

            return Response(
                {
                    "message": f"Successfully imported {created_count} users",
                    "created_count": created_count,
                    "error_count": len(errors),
                    "errors": errors[:10],  # Show first 10 errors
                }
            )

        except Exception as e:
            return Response(
                {"error": f"Error processing CSV: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )


class AuditLogListView(generics.ListAPIView):
    """View for listing audit logs."""

    queryset = UserAuditLog.objects.select_related("user", "performed_by").order_by(
        "-timestamp"
    )
    serializer_class = UserAuditLogSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdmin]

    def get_queryset(self):
        """Filter audit logs based on query parameters."""
        queryset = super().get_queryset()

        # Filter by user
        user_id = self.request.query_params.get("user_id")
        if user_id:
            queryset = queryset.filter(user_id=user_id)

        # Filter by action
        action = self.request.query_params.get("action")
        if action:
            queryset = queryset.filter(action=action)

        # Filter by date range
        from_date = self.request.query_params.get("from_date")
        to_date = self.request.query_params.get("to_date")

        if from_date:
            queryset = queryset.filter(timestamp__date__gte=from_date)
        if to_date:
            queryset = queryset.filter(timestamp__date__lte=to_date)

        return queryset


class SystemHealthView(APIView):
    """View for system health check."""

    permission_classes = [permissions.IsAuthenticated, IsAdmin]

    def get(self, request):
        """Get system health information."""
        # Check database connectivity
        try:
            User.objects.count()
            db_status = "healthy"
        except Exception as e:
            db_status = f"error: {str(e)}"

        # Check cache connectivity
        try:
            from django.core.cache import cache

            cache.set("health_check", "ok", 10)
            cache_status = "healthy" if cache.get("health_check") == "ok" else "error"
        except Exception as e:
            cache_status = f"error: {str(e)}"

        # Check for expired role assignments
        expired_assignments = UserRoleAssignment.objects.filter(
            expires_at__lt=timezone.now(), is_active=True
        ).count()

        # Check for locked accounts
        locked_accounts = User.objects.filter(failed_login_attempts__gte=5).count()

        health_data = {
            "timestamp": timezone.now(),
            "database": db_status,
            "cache": cache_status,
            "expired_role_assignments": expired_assignments,
            "locked_accounts": locked_accounts,
            "status": (
                "healthy"
                if db_status == "healthy" and cache_status == "healthy"
                else "warning"
            ),
        }

        return Response(health_data)
