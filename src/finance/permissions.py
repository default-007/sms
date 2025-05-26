from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from rest_framework.permissions import BasePermission


class FinanceManagerPermission(BasePermission):
    """Permission for finance managers."""

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False

        # Superusers have all permissions
        if request.user.is_superuser:
            return True

        # Check if user has finance manager role
        return request.user.groups.filter(name="Finance Manager").exists()


class CanManageFeesPermission(BasePermission):
    """Permission to manage fee structures."""

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False

        if request.user.is_superuser:
            return True

        # Check specific permissions
        return (
            request.user.has_perm("finance.add_feestructure")
            or request.user.has_perm("finance.change_feestructure")
            or request.user.has_perm("finance.delete_feestructure")
        )


class CanProcessPaymentsPermission(BasePermission):
    """Permission to process payments."""

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False

        if request.user.is_superuser:
            return True

        return (
            request.user.has_perm("finance.add_payment")
            or request.user.groups.filter(
                name__in=["Finance Manager", "Cashier"]
            ).exists()
        )


class CanApproveWaiversPermission(BasePermission):
    """Permission to approve fee waivers."""

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False

        if request.user.is_superuser:
            return True

        return (
            request.user.has_perm("finance.change_feewaiver")
            or request.user.groups.filter(
                name__in=["Finance Manager", "Principal"]
            ).exists()
        )


class CanManageScholarshipsPermission(BasePermission):
    """Permission to manage scholarships."""

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False

        if request.user.is_superuser:
            return True

        return (
            request.user.has_perm("finance.add_scholarship")
            or request.user.has_perm("finance.change_scholarship")
            or request.user.groups.filter(
                name__in=["Finance Manager", "Academic Director"]
            ).exists()
        )


class CanViewFinancialReportsPermission(BasePermission):
    """Permission to view financial reports."""

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False

        if request.user.is_superuser:
            return True

        return (
            request.user.has_perm("finance.view_financialanalytics")
            or request.user.groups.filter(
                name__in=["Finance Manager", "Principal", "Accountant"]
            ).exists()
        )


class ParentStudentPermission(BasePermission):
    """Permission for parents to view their children's financial data."""

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False

        # Staff and superusers can access all data
        if request.user.is_staff or request.user.is_superuser:
            return True

        # Parents and students can access limited data
        return hasattr(request.user, "parent") or hasattr(request.user, "student")

    def has_object_permission(self, request, view, obj):
        # Staff and superusers can access all objects
        if request.user.is_staff or request.user.is_superuser:
            return True

        # Parents can only access their children's data
        if hasattr(request.user, "parent"):
            parent = request.user.parent
            student_ids = parent.studentparentrelation_set.values_list(
                "student_id", flat=True
            )

            # Check based on object type
            if hasattr(obj, "student"):
                return obj.student.id in student_ids
            elif hasattr(obj, "invoice") and hasattr(obj.invoice, "student"):
                return obj.invoice.student.id in student_ids

        # Students can only access their own data
        if hasattr(request.user, "student"):
            student = request.user.student

            if hasattr(obj, "student"):
                return obj.student == student
            elif hasattr(obj, "invoice") and hasattr(obj.invoice, "student"):
                return obj.invoice.student == student

        return False


class CanGenerateInvoicesPermission(BasePermission):
    """Permission to generate invoices."""

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False

        if request.user.is_superuser:
            return True

        return (
            request.user.has_perm("finance.add_invoice")
            or request.user.groups.filter(
                name__in=["Finance Manager", "Accountant"]
            ).exists()
        )


# Custom permission groups and permissions setup
def create_finance_permissions():
    """Create custom finance permissions."""

    # Get content types
    from .models import (
        FeeStructure,
        FeeWaiver,
        FinancialAnalytics,
        Invoice,
        Payment,
        Scholarship,
        SpecialFee,
    )

    # Custom permissions beyond the default add/change/delete/view
    custom_permissions = [
        # Fee management
        ("can_approve_fee_structures", "Can approve fee structures"),
        ("can_bulk_create_fees", "Can create fees in bulk"),
        ("can_modify_active_fees", "Can modify active fee structures"),
        # Payment processing
        ("can_process_cash_payments", "Can process cash payments"),
        ("can_process_card_payments", "Can process card payments"),
        ("can_process_bank_transfers", "Can process bank transfers"),
        ("can_refund_payments", "Can process payment refunds"),
        ("can_void_payments", "Can void payments"),
        # Invoice management
        ("can_generate_bulk_invoices", "Can generate invoices in bulk"),
        ("can_modify_invoices", "Can modify existing invoices"),
        ("can_cancel_invoices", "Can cancel invoices"),
        ("can_send_invoice_reminders", "Can send payment reminders"),
        # Scholarship management
        ("can_approve_scholarships", "Can approve scholarship assignments"),
        ("can_suspend_scholarships", "Can suspend scholarships"),
        ("can_create_automatic_scholarships", "Can create automatic scholarships"),
        # Waiver management
        ("can_request_waivers", "Can request fee waivers"),
        ("can_approve_waivers", "Can approve fee waivers"),
        ("can_reject_waivers", "Can reject fee waivers"),
        # Financial reporting
        ("can_view_all_financial_data", "Can view all financial data"),
        ("can_export_financial_data", "Can export financial data"),
        ("can_view_defaulter_reports", "Can view defaulter reports"),
        ("can_view_collection_reports", "Can view collection reports"),
        ("can_generate_financial_summaries", "Can generate financial summaries"),
        # Administrative
        ("can_configure_finance_settings", "Can configure finance settings"),
        ("can_manage_payment_methods", "Can manage payment methods"),
        ("can_access_finance_analytics", "Can access finance analytics"),
    ]

    # Create permissions
    created_permissions = []

    for codename, name in custom_permissions:
        # Use Invoice content type as a base (could be any model)
        content_type = ContentType.objects.get_for_model(Invoice)

        permission, created = Permission.objects.get_or_create(
            codename=codename, name=name, content_type=content_type
        )

        if created:
            created_permissions.append(permission)

    return created_permissions


def create_finance_groups():
    """Create default finance user groups with appropriate permissions."""

    from django.contrib.auth.models import Group

    # Define groups and their permissions
    group_permissions = {
        "Finance Manager": [
            # Full access to all finance operations
            "add_feestructure",
            "change_feestructure",
            "delete_feestructure",
            "view_feestructure",
            "add_specialfee",
            "change_specialfee",
            "delete_specialfee",
            "view_specialfee",
            "add_scholarship",
            "change_scholarship",
            "delete_scholarship",
            "view_scholarship",
            "add_invoice",
            "change_invoice",
            "delete_invoice",
            "view_invoice",
            "add_payment",
            "change_payment",
            "delete_payment",
            "view_payment",
            "add_feewaiver",
            "change_feewaiver",
            "delete_feewaiver",
            "view_feewaiver",
            "view_financialanalytics",
            # Custom permissions
            "can_approve_fee_structures",
            "can_bulk_create_fees",
            "can_process_cash_payments",
            "can_process_card_payments",
            "can_generate_bulk_invoices",
            "can_modify_invoices",
            "can_approve_scholarships",
            "can_approve_waivers",
            "can_view_all_financial_data",
            "can_export_financial_data",
            "can_configure_finance_settings",
        ],
        "Accountant": [
            # View and limited edit access
            "view_feestructure",
            "view_specialfee",
            "view_scholarship",
            "add_invoice",
            "change_invoice",
            "view_invoice",
            "view_payment",
            "view_feewaiver",
            "view_financialanalytics",
            # Limited custom permissions
            "can_generate_bulk_invoices",
            "can_view_collection_reports",
            "can_export_financial_data",
        ],
        "Cashier": [
            # Payment processing focus
            "view_invoice",
            "add_payment",
            "view_payment",
            "view_feewaiver",
            # Payment-specific permissions
            "can_process_cash_payments",
            "can_process_card_payments",
            "can_process_bank_transfers",
        ],
        "Finance Clerk": [
            # Basic data entry
            "add_specialfee",
            "view_specialfee",
            "view_invoice",
            "view_payment",
            "add_feewaiver",
            "view_feewaiver",
            # Limited permissions
            "can_request_waivers",
        ],
        "Principal": [
            # Oversight and approval focus
            "view_feestructure",
            "view_specialfee",
            "view_scholarship",
            "view_invoice",
            "view_payment",
            "view_feewaiver",
            "view_financialanalytics",
            # Approval permissions
            "can_approve_scholarships",
            "can_approve_waivers",
            "can_view_all_financial_data",
            "can_view_defaulter_reports",
        ],
    }

    created_groups = []

    for group_name, permission_codenames in group_permissions.items():
        group, created = Group.objects.get_or_create(name=group_name)

        if created:
            created_groups.append(group)

        # Add permissions to group
        permissions = Permission.objects.filter(codename__in=permission_codenames)
        group.permissions.set(permissions)

    return created_groups


def assign_user_to_finance_group(user, group_name):
    """Assign user to a finance group."""

    try:
        from django.contrib.auth.models import Group

        group = Group.objects.get(name=group_name)
        user.groups.add(group)
        return True
    except Group.DoesNotExist:
        return False


def check_finance_permission(user, permission_codename):
    """Check if user has specific finance permission."""

    if user.is_superuser:
        return True

    return user.has_perm(f"finance.{permission_codename}")


def get_user_finance_permissions(user):
    """Get all finance permissions for a user."""

    if user.is_superuser:
        return Permission.objects.filter(content_type__app_label="finance").values_list(
            "codename", flat=True
        )

    # Get permissions from groups and direct user permissions
    permissions = set()

    # Group permissions
    for group in user.groups.all():
        group_perms = group.permissions.filter(
            content_type__app_label="finance"
        ).values_list("codename", flat=True)
        permissions.update(group_perms)

    # User-specific permissions
    user_perms = user.user_permissions.filter(
        content_type__app_label="finance"
    ).values_list("codename", flat=True)
    permissions.update(user_perms)

    return list(permissions)


# Role-based permission checker decorators
def finance_manager_required(view_func):
    """Decorator to require finance manager role."""

    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            from django.contrib.auth.views import redirect_to_login

            return redirect_to_login(request.get_full_path())

        if not (
            request.user.is_superuser
            or request.user.groups.filter(name="Finance Manager").exists()
        ):
            from django.core.exceptions import PermissionDenied

            raise PermissionDenied("Finance Manager role required")

        return view_func(request, *args, **kwargs)

    return wrapper


def can_process_payments_required(view_func):
    """Decorator to require payment processing permission."""

    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            from django.contrib.auth.views import redirect_to_login

            return redirect_to_login(request.get_full_path())

        if not (
            request.user.is_superuser
            or request.user.has_perm("finance.add_payment")
            or request.user.groups.filter(
                name__in=["Finance Manager", "Cashier"]
            ).exists()
        ):
            from django.core.exceptions import PermissionDenied

            raise PermissionDenied("Payment processing permission required")

        return view_func(request, *args, **kwargs)

    return wrapper
