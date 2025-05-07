from django.urls import path
from . import views

app_name = "finance"

urlpatterns = [
    # Fee Categories
    path(
        "fee-categories/", views.FeeCategoryListView.as_view(), name="fee-category-list"
    ),
    path(
        "fee-categories/create/",
        views.FeeCategoryCreateView.as_view(),
        name="fee-category-create",
    ),
    path(
        "fee-categories/<int:pk>/",
        views.FeeCategoryDetailView.as_view(),
        name="fee-category-detail",
    ),
    path(
        "fee-categories/<int:pk>/update/",
        views.FeeCategoryUpdateView.as_view(),
        name="fee-category-update",
    ),
    path(
        "fee-categories/<int:pk>/delete/",
        views.FeeCategoryDeleteView.as_view(),
        name="fee-category-delete",
    ),
    # Fee Structures
    path(
        "fee-structures/",
        views.FeeStructureListView.as_view(),
        name="fee-structure-list",
    ),
    path(
        "fee-structures/create/",
        views.FeeStructureCreateView.as_view(),
        name="fee-structure-create",
    ),
    path(
        "fee-structures/<int:pk>/",
        views.FeeStructureDetailView.as_view(),
        name="fee-structure-detail",
    ),
    path(
        "fee-structures/<int:pk>/update/",
        views.FeeStructureUpdateView.as_view(),
        name="fee-structure-update",
    ),
    path(
        "fee-structures/<int:pk>/delete/",
        views.FeeStructureDeleteView.as_view(),
        name="fee-structure-delete",
    ),
    # Scholarships
    path("scholarships/", views.ScholarshipListView.as_view(), name="scholarship-list"),
    path(
        "scholarships/create/",
        views.ScholarshipCreateView.as_view(),
        name="scholarship-create",
    ),
    path(
        "scholarships/<int:pk>/",
        views.ScholarshipDetailView.as_view(),
        name="scholarship-detail",
    ),
    path(
        "scholarships/<int:pk>/update/",
        views.ScholarshipUpdateView.as_view(),
        name="scholarship-update",
    ),
    path(
        "scholarships/<int:pk>/delete/",
        views.ScholarshipDeleteView.as_view(),
        name="scholarship-delete",
    ),
    # Student Scholarships
    path(
        "student-scholarships/",
        views.StudentScholarshipListView.as_view(),
        name="student-scholarship-list",
    ),
    path(
        "student-scholarships/create/",
        views.StudentScholarshipCreateView.as_view(),
        name="student-scholarship-create",
    ),
    path(
        "student-scholarships/<int:pk>/",
        views.StudentScholarshipDetailView.as_view(),
        name="student-scholarship-detail",
    ),
    path(
        "student-scholarships/<int:pk>/update/",
        views.StudentScholarshipUpdateView.as_view(),
        name="student-scholarship-update",
    ),
    # Invoices
    path("invoices/", views.InvoiceListView.as_view(), name="invoice-list"),
    path("invoices/create/", views.InvoiceCreateView.as_view(), name="invoice-create"),
    path(
        "invoices/bulk-generate/",
        views.BulkInvoiceGenerationView.as_view(),
        name="invoice-bulk-generate",
    ),
    path(
        "invoices/<int:pk>/", views.InvoiceDetailView.as_view(), name="invoice-detail"
    ),
    path(
        "invoices/<int:pk>/update/",
        views.InvoiceUpdateView.as_view(),
        name="invoice-update",
    ),
    path(
        "invoices/<int:pk>/delete/",
        views.InvoiceDeleteView.as_view(),
        name="invoice-delete",
    ),
    path(
        "invoices/<int:pk>/print/",
        views.InvoicePrintView.as_view(),
        name="invoice-print",
    ),
    # Payments
    path("payments/", views.PaymentListView.as_view(), name="payment-list"),
    path("payments/create/", views.PaymentCreateView.as_view(), name="payment-create"),
    path(
        "payments/<int:invoice_id>/create/",
        views.PaymentCreateForInvoiceView.as_view(),
        name="payment-create-for-invoice",
    ),
    path(
        "payments/<int:pk>/", views.PaymentDetailView.as_view(), name="payment-detail"
    ),
    path(
        "payments/<int:pk>/receipt/",
        views.PaymentReceiptView.as_view(),
        name="payment-receipt",
    ),
    # Expenses
    path("expenses/", views.ExpenseListView.as_view(), name="expense-list"),
    path("expenses/create/", views.ExpenseCreateView.as_view(), name="expense-create"),
    path(
        "expenses/<int:pk>/", views.ExpenseDetailView.as_view(), name="expense-detail"
    ),
    path(
        "expenses/<int:pk>/update/",
        views.ExpenseUpdateView.as_view(),
        name="expense-update",
    ),
    path(
        "expenses/<int:pk>/delete/",
        views.ExpenseDeleteView.as_view(),
        name="expense-delete",
    ),
    # Reports
    path(
        "reports/financial-summary/",
        views.FinancialSummaryView.as_view(),
        name="financial-summary",
    ),
    path(
        "reports/fee-collection/",
        views.FeeCollectionReportView.as_view(),
        name="fee-collection-report",
    ),
    path(
        "reports/outstanding-fees/",
        views.OutstandingFeesReportView.as_view(),
        name="outstanding-fees-report",
    ),
    path(
        "reports/expense-report/",
        views.ExpenseReportView.as_view(),
        name="expense-report",
    ),
    # Dashboard
    path("dashboard/", views.FinanceDashboardView.as_view(), name="dashboard"),
    # Student Fee Portal
    path(
        "student-portal/", views.StudentFeePortalView.as_view(), name="student-portal"
    ),
]
