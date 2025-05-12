from rest_framework import permissions


class CanManageCommunications(permissions.BasePermission):
    """
    Permission to allow users to manage communications.
    """

    def has_permission(self, request, view):
        # Admin can do anything
        if request.user.is_staff:
            return True

        # Check if the user has the appropriate permissions
        if hasattr(request.user, "teacher_profile"):
            # Teachers can send messages and view announcements
            if view.action in ["list", "retrieve", "create"]:
                return True

        return False


class IsMessageParticipant(permissions.BasePermission):
    """
    Permission to allow only participants of a message to access it.
    """

    def has_object_permission(self, request, view, obj):
        # Check if the user is a participant in the message
        return request.user == obj.sender or request.user == obj.receiver


class IsOwnNotification(permissions.BasePermission):
    """
    Permission to allow users to access only their own notifications.
    """

    def has_object_permission(self, request, view, obj):
        # Check if the notification belongs to the user
        return obj.user == request.user
