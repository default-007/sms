from rest_framework import permissions


class HasFinancePermission(permissions.BasePermission):
    """Permission to check if user has finance module permissions."""

    def has_permission(self, request, view):
        # User must be authenticated
        if not request.user.is_authenticated:
            return False

        # Staff members have all permissions
        if request.user.is_staff:
            return True

        # Check if the user's roles include finance permissions
        for role_assignment in request.user.role_assignments.all():
            role_permissions = role_assignment.role.permissions

            # Check if there's any finance permission
            if "finance" in role_permissions and role_permissions["finance"]:
                return True

        return False


class CanViewFinances(permissions.BasePermission):
    """Permission to allow users to view finance data."""

    def has_permission(self, request, view):
        # GET requests require view permission
        if request.method in permissions.SAFE_METHODS:
            return self._check_finance_permission(request.user, "view")
        return True

    def _check_finance_permission(self, user, action):
        # Staff members have all permissions
        if user.is_staff:
            return True

        # Check for specific permission
        for role_assignment in user.role_assignments.all():
            role_permissions = role_assignment.role.permissions

            if "finance" in role_permissions and action in role_permissions["finance"]:
                return True

        return False


class CanManageInvoices(permissions.BasePermission):
    """Permission to allow users to manage invoices."""

    def has_permission(self, request, view):
        # Check for proper permission based on HTTP method
        if request.method in permissions.SAFE_METHODS:
            return self._check_invoice_permission(request.user, "view")
        elif request.method == "POST":
            return self._check_invoice_permission(request.user, "add")
        elif request.method in ["PUT", "PATCH"]:
            return self._check_invoice_permission(request.user, "change")
        elif request.method == "DELETE":
            return self._check_invoice_permission(request.user, "delete")
        return False

    def _check_invoice_permission(self, user, action):
        # Staff members have all permissions
        if user.is_staff:
            return True

        # Check for specific permission
        for role_assignment in user.role_assignments.all():
            role_permissions = role_assignment.role.permissions

            if (
                "invoices" in role_permissions
                and action in role_permissions["invoices"]
            ):
                return True

        return False


class CanManagePayments(permissions.BasePermission):
    """Permission to allow users to manage payments."""

    def has_permission(self, request, view):
        # Check for proper permission based on HTTP method
        if request.method in permissions.SAFE_METHODS:
            return self._check_payment_permission(request.user, "view")
        elif request.method == "POST":
            return self._check_payment_permission(request.user, "add")
        elif request.method in ["PUT", "PATCH"]:
            return self._check_payment_permission(request.user, "change")
        elif request.method == "DELETE":
            return self._check_payment_permission(request.user, "delete")
        return False

    def _check_payment_permission(self, user, action):
        # Staff members have all permissions
        if user.is_staff:
            return True

        # Check for specific permission
        for role_assignment in user.role_assignments.all():
            role_permissions = role_assignment.role.permissions

            if (
                "payments" in role_permissions
                and action in role_permissions["payments"]
            ):
                return True

        return False


class StudentCanViewOwnInvoices(permissions.BasePermission):
    """Permission to allow students to view their own invoices."""

    def has_object_permission(self, request, view, obj):
        # Only allow safe methods
        if not request.method in permissions.SAFE_METHODS:
            return False

        # Check if user is the student
        if hasattr(request.user, "student_profile"):
            return obj.student.id == request.user.student_profile.id

        # Check if user is a parent of the student
        if hasattr(request.user, "parent_profile"):
            parent = request.user.parent_profile
            student_ids = parent.parent_student_relations.values_list(
                "student_id", flat=True
            )
            return obj.student.id in student_ids

        return False
