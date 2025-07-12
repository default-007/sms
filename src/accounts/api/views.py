# src/accounts/api/views.py

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Count, Prefetch, Q
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import generics, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from ..models import UserAuditLog, UserRole, UserRoleAssignment
from ..permissions import CanManageUsers, IsAdmin
from ..services import AuthenticationService, RoleService
from .serializers import (
    BulkUserActionSerializer,
    CustomTokenObtainPairSerializer,
    PasswordChangeSerializer,
    PasswordResetSerializer,
    UserAuditLogSerializer,
    UserCreateSerializer,
    UserDetailSerializer,
    UserListSerializer,
    UserRoleAssignmentSerializer,
    UserRoleSerializer,
    UserUpdateSerializer,
)

User = get_user_model()


class CustomTokenObtainPairView(TokenObtainPairView):
    """Custom JWT token view with enhanced authentication."""

    serializer_class = CustomTokenObtainPairSerializer


class UserListCreateView(generics.ListCreateAPIView):
    """List and create users."""

    permission_classes = [CanManageUsers]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ["username", "email", "first_name", "last_name"]
    filterset_fields = ["is_active", "is_staff", "role_assignments__role__name"]
    ordering_fields = ["username", "email", "date_joined", "last_login"]
    ordering = ["-date_joined"]

    def get_queryset(self):
        """Optimized queryset with prefetches."""
        return User.objects.select_related("profile").prefetch_related(
            Prefetch(
                "role_assignments",
                queryset=UserRoleAssignment.objects.select_related("role").filter(
                    is_active=True
                ),
                to_attr="active_role_assignments",
            )
        )

    def get_serializer_class(self):
        if self.request.method == "POST":
            return UserCreateSerializer
        return UserListSerializer

    def perform_create(self, serializer):
        """Set created_by for audit trail."""
        serializer.save()


class UserDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update, and delete users."""

    queryset = User.objects.select_related("profile").prefetch_related(
        "role_assignments__role", "audit_logs"
    )
    permission_classes = [CanManageUsers]

    def get_serializer_class(self):
        if self.request.method in ["PUT", "PATCH"]:
            return UserUpdateSerializer
        return UserDetailSerializer

    def destroy(self, request, *args, **kwargs):
        """Soft delete user instead of hard delete."""
        user = self.get_object()
        user.is_active = False
        user.save()

        # Deactivate role assignments
        user.role_assignments.update(is_active=False)

        # Create audit log
        from ..utils import get_client_info

        client_info = get_client_info(request)
        UserAuditLog.objects.create(
            user=user,
            action="delete",
            description=f"User deactivated by {request.user.username}",
            performed_by=request.user,
            ip_address=client_info["ip_address"],
            user_agent=client_info["user_agent"],
        )

        return Response(status=status.HTTP_204_NO_CONTENT)


class UserProfileView(generics.RetrieveUpdateAPIView):
    """User profile management."""

    serializer_class = UserDetailSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


class PasswordChangeView(APIView):
    """Change user password."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = PasswordChangeSerializer(
            data=request.data, context={"request": request}
        )
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Password changed successfully"})
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PasswordResetView(APIView):
    """Reset user password (admin only)."""

    permission_classes = [IsAdmin]

    def post(self, request, user_id):
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response(
                {"error": "User not found"}, status=status.HTTP_404_NOT_FOUND
            )

        serializer = PasswordResetSerializer(
            data=request.data, context={"request": request}
        )
        if serializer.is_valid():
            new_password = serializer.save(user)
            return Response(
                {"message": "Password reset successfully", "new_password": new_password}
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UserRoleListCreateView(generics.ListCreateAPIView):
    """List and create user roles."""

    queryset = UserRole.objects.annotate(
        user_count=Count("user_assignments", filter=Q(user_assignments__is_active=True))
    ).order_by("name")
    serializer_class = UserRoleSerializer
    permission_classes = [IsAdmin]
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ["name", "description"]
    ordering_fields = ["name", "created_at", "user_count"]


class UserRoleDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update, and delete user roles."""

    queryset = UserRole.objects.all()
    serializer_class = UserRoleSerializer
    permission_classes = [IsAdmin]

    def destroy(self, request, *args, **kwargs):
        """Prevent deletion of system roles."""
        role = self.get_object()
        if role.is_system_role:
            return Response(
                {"error": "System roles cannot be deleted"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().destroy(request, *args, **kwargs)


class UserRoleAssignmentView(APIView):
    """Manage user role assignments."""

    permission_classes = [IsAdmin]

    def post(self, request, user_id):
        """Assign role to user."""
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response(
                {"error": "User not found"}, status=status.HTTP_404_NOT_FOUND
            )

        role_name = request.data.get("role_name")
        expires_at = request.data.get("expires_at")
        notes = request.data.get("notes", "")

        if not role_name:
            return Response(
                {"error": "Role name is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            assignment, created = RoleService.assign_role_to_user(
                user,
                role_name,
                assigned_by=request.user,
                expires_at=expires_at,
                notes=notes,
            )

            if created:
                serializer = UserRoleAssignmentSerializer(assignment)
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            else:
                return Response({"message": "Role already assigned"})

        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, user_id, role_id):
        """Remove role from user."""
        try:
            user = User.objects.get(id=user_id)
            role = UserRole.objects.get(id=role_id)
        except (User.DoesNotExist, UserRole.DoesNotExist):
            return Response(
                {"error": "User or role not found"}, status=status.HTTP_404_NOT_FOUND
            )

        removed = RoleService.remove_role_from_user(
            user, role.name, removed_by=request.user
        )

        if removed:
            return Response({"message": "Role removed successfully"})
        else:
            return Response(
                {"error": "Role assignment not found"}, status=status.HTTP_404_NOT_FOUND
            )


class BulkUserActionView(APIView):
    """Handle bulk user actions."""

    permission_classes = [IsAdmin]

    @transaction.atomic
    def post(self, request):
        serializer = BulkUserActionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        user_ids = serializer.validated_data["user_ids"]
        action = serializer.validated_data["action"]
        roles = serializer.validated_data.get("roles", [])

        users = User.objects.filter(id__in=user_ids)
        affected_count = 0

        if action == "activate":
            affected_count = users.update(is_active=True)
        elif action == "deactivate":
            affected_count = users.update(is_active=False)
        elif action == "require_password_change":
            affected_count = users.update(requires_password_change=True)
        elif action == "assign_roles":
            affected_count = RoleService.bulk_assign_roles(
                users, roles, assigned_by=request.user
            )
        elif action == "remove_roles":
            for user in users:
                for role_name in roles:
                    RoleService.remove_role_from_user(
                        user, role_name, removed_by=request.user
                    )
            affected_count = users.count()

        # Create audit logs
        from ..utils import get_client_info

        client_info = get_client_info(request)

        for user in users:
            UserAuditLog.objects.create(
                user=user,
                action=action,
                description=f"Bulk action: {action} by {request.user.username}",
                performed_by=request.user,
                ip_address=client_info["ip_address"],
                user_agent=client_info["user_agent"],
                extra_data={"action": action, "roles": roles},
            )

        return Response(
            {
                "message": f'{action.replace("_", " ").title()} applied to {affected_count} users'
            }
        )


class UserAuditLogView(generics.ListAPIView):
    """List user audit logs."""

    serializer_class = UserAuditLogSerializer
    permission_classes = [IsAdmin]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["action", "user__username"]
    search_fields = ["description", "user__username"]
    ordering = ["-timestamp"]

    def get_queryset(self):
        user_id = self.kwargs.get("user_id")
        queryset = UserAuditLog.objects.select_related("user", "performed_by")

        if user_id:
            queryset = queryset.filter(user_id=user_id)

        return queryset


class UserStatisticsView(APIView):
    """Get user statistics."""

    permission_classes = [IsAdmin]

    def get(self, request):
        stats = User.objects.get_statistics()
        role_stats = RoleService.get_role_statistics()

        return Response({"user_statistics": stats, "role_statistics": role_stats})


class UserToggleStatusView(APIView):
    """Toggle user active status."""

    permission_classes = [CanManageUsers]

    def post(self, request, user_id):
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response(
                {"error": "User not found"}, status=status.HTTP_404_NOT_FOUND
            )

        activate = request.data.get("activate", False)
        user.is_active = activate
        user.save()

        # Create audit log
        from ..utils import get_client_info

        client_info = get_client_info(request)
        action = "account_unlock" if activate else "account_lock"
        description = f'User {"activated" if activate else "deactivated"} by {request.user.username}'

        UserAuditLog.objects.create(
            user=user,
            action=action,
            description=description,
            performed_by=request.user,
            ip_address=client_info["ip_address"],
            user_agent=client_info["user_agent"],
        )

        return Response(
            {
                "message": f'User {"activated" if activate else "deactivated"} successfully'
            }
        )


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def logout_view(request):
    """Logout user and invalidate tokens."""
    AuthenticationService.logout_user(request.user, request)

    # Invalidate JWT tokens if using JWT
    try:
        AuthenticationService.invalidate_user_tokens(request.user)
    except Exception:
        pass

    return Response({"message": "Logged out successfully"})


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def user_permissions_view(request):
    """Get current user's permissions."""
    permissions = request.user.get_permissions()
    return Response({"permissions": permissions})


@api_view(["POST"])
@permission_classes([IsAdmin])
def unlock_account_view(request, user_id):
    """Unlock a locked user account."""
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

    AuthenticationService.unlock_account(user, unlocked_by=request.user)

    return Response({"message": "Account unlocked successfully"})


@api_view(["GET"])
@permission_classes([IsAdmin])
def login_statistics_view(request, user_id):
    """Get login statistics for a user."""
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

    days = int(request.GET.get("days", 30))
    stats = AuthenticationService.get_login_statistics(user, days)

    return Response(stats)


@api_view(["GET"])
@permission_classes([IsAdmin])
def suspicious_activity_view(request, user_id):
    """Check for suspicious activity for a user."""
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

    hours = int(request.GET.get("hours", 24))
    activity = AuthenticationService.check_suspicious_activity(user, hours)

    return Response(activity)
