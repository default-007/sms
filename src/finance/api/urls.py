from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    FeeCategoryViewSet,
    FeeStructureViewSet,
    SpecialFeeViewSet,
    ScholarshipViewSet,
    StudentScholarshipViewSet,
    InvoiceViewSet,
    PaymentViewSet,
    FinancialAnalyticsViewSet,
    FeeWaiverViewSet,
)

# Create router and register viewsets
router = DefaultRouter()
router.register(r"fee-categories", FeeCategoryViewSet, basename="fee-category")
router.register(r"fee-structures", FeeStructureViewSet, basename="fee-structure")
router.register(r"special-fees", SpecialFeeViewSet, basename="special-fee")
router.register(r"scholarships", ScholarshipViewSet, basename="scholarship")
router.register(
    r"student-scholarships", StudentScholarshipViewSet, basename="student-scholarship"
)
router.register(r"invoices", InvoiceViewSet, basename="invoice")
router.register(r"payments", PaymentViewSet, basename="payment")
router.register(r"analytics", FinancialAnalyticsViewSet, basename="financial-analytics")
router.register(r"fee-waivers", FeeWaiverViewSet, basename="fee-waiver")

# URL patterns
urlpatterns = [
    path("", include(router.urls)),
    # Additional custom endpoints can be added here if needed
    # For example:
    # path('reports/revenue/', RevenueReportView.as_view(), name='revenue-report'),
    # path('reports/collection/', CollectionReportView.as_view(), name='collection-report'),
]

# URL namespace for inclusion in main urls.py
app_name = "finance"
