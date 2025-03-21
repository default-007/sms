from rest_framework import viewsets, status, generics, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import get_user_model
from django.db import models

from src.accounts.models import UserRole, UserRoleAssignment
from src.accounts.permissions import IsAdmin, CanManageUsers
from .serializers import (
    UserSerializer,
    UserCreateSerializer,
    UserRoleSerializer,
    UserRoleAssignmentSerializer,
    ChangePasswordSerializer,
)

User = get_user_model()


class UserViewSet(viewsets.ModelViewSet):
    """ViewSet for viewing and editing User instances."""

    queryset = User.objects.all()
    permission_classes = [permissions.IsAuthenticated, CanManageUsers]

    def get_serializer_class(self):
        """Return appropriate serializer class based on the action."""
        if self.action == "create":
            return UserCreateSerializer
        return UserSerializer

    def get_queryset(self):
        """Filter queryset based on query parameters."""
        queryset = super().get_queryset()

        # Apply filters if provided
        role = self.request.query_params.get("role")
        status = self.request.query_params.get("status")
        search = self.request.query_params.get("search")

        if role:
            queryset = queryset.filter(role_assignments__role__name=role)

        if status:
            queryset = queryset.filter(is_active=(status.lower() == "active"))

        if search:
            queryset = queryset.filter(
                models.Q(username__icontains=search)
                | models.Q(email__icontains=search)
                | models.Q(first_name__icontains=search)
                | models.Q(last_name__icontains=search)
            )

        return queryset

    @action(
        detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated]
    )
    def change_password(self, request, pk=None):
        """Change user password."""
        user = self.get_object()
        serializer = ChangePasswordSerializer(
            data=request.data, context={"request": request}
        )

        if serializer.is_valid():
            # Set new password
            user.set_password(serializer.validated_data["new_password"])
            user.save()
            return Response(
                {"message": "Password updated successfully"}, status=status.HTTP_200_OK
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UserRoleViewSet(viewsets.ModelViewSet):
    """ViewSet for viewing and editing UserRole instances."""

    queryset = UserRole.objects.all()
    serializer_class = UserRoleSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdmin]

    @action(detail=True, methods=["get"])
    def permissions(self, request, pk=None):
        """List permissions for a role."""
        role = self.get_object()
        return Response(role.permissions)


class LoginView(TokenObtainPairView):
    """Custom login view that returns user details along with tokens."""

    def post(self, request, *args, **kwargs):
        """Override to return additional user data."""
        response = super().post(request, *args, **kwargs)

        # Add user data to response
        user = User.objects.get(username=request.data.get("username"))
        user_serializer = UserSerializer(user)
        response.data["user"] = user_serializer.data

        return response


class LogoutView(generics.GenericAPIView):
    """View for logging out a user by blacklisting their refresh token."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        """Blacklist the refresh token to logout."""
        try:
            refresh_token = request.data.get("refresh")
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response(status=status.HTTP_205_RESET_CONTENT)
        except Exception as e:
            return Response(status=status.HTTP_400_BAD_REQUEST)
