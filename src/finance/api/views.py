from decimal import Decimal

from django.db.models import Q
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from src.api.filters import BaseFilter
from src.api.paginations import StandardPagination
from src.api.permissions import IsAdminOrReadOnly, IsOwnerOrReadOnly

from ..models import (
    FeeCategory,
    FeeStructure,
    FeeWaiver,
    FinancialAnalytics,
    FinancialSummary,
    Invoice,
    InvoiceItem,
    Payment,
    Scholarship,
    SpecialFee,
    StudentScholarship,
)
from ..services.analytics_service import FinancialAnalyticsService
from ..services.fee_service import FeeService
from ..services.invoice_service import InvoiceService
from ..services.payment_service import PaymentService
from ..services.scholarship_service import ScholarshipService
from .serializers import (
    BulkInvoiceGenerationSerializer,
    CollectionMetricsSerializer,
    DefaulterAnalysisSerializer,
    FeeCalculationSerializer,
    FeeCategorySerializer,
    FeeStructureSerializer,
    FeeWaiverSerializer,
    FinancialAnalyticsSerializer,
    FinancialSummarySerializer,
    InvoiceSerializer,
    PaymentProcessingSerializer,
    PaymentSerializer,
    PaymentTrendsSerializer,
    ScholarshipImpactSerializer,
    ScholarshipSerializer,
    SpecialFeeSerializer,
    StudentScholarshipSerializer,
)


class FeeCategoryViewSet(viewsets.ModelViewSet):
    """ViewSet for fee categories."""

    queryset = FeeCategory.objects.all()
    serializer_class = FeeCategorySerializer
    permission_classes = [IsAuthenticated, IsAdminOrReadOnly]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["is_mandatory", "is_recurring", "frequency"]
    search_fields = ["name", "description"]
    ordering_fields = ["name", "created_at"]
    ordering = ["name"]


class FeeStructureViewSet(viewsets.ModelViewSet):
    """ViewSet for fee structures."""

    queryset = FeeStructure.objects.select_related(
        "academic_year", "term", "section", "grade", "fee_category", "created_by"
    ).all()
    serializer_class = FeeStructureSerializer
    permission_classes = [IsAuthenticated, IsAdminOrReadOnly]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = [
        "academic_year",
        "term",
        "section",
        "grade",
        "fee_category",
        "is_active",
    ]
    search_fields = ["fee_category__name"]
    ordering_fields = ["amount", "due_date", "created_at"]
    ordering = ["-created_at"]

    @action(detail=False, methods=["post"])
    def bulk_create(self, request):
        """Bulk create fee structures."""
        data_list = request.data if isinstance(request.data, list) else [request.data]
        created_structures = []
        errors = []

        for data in data_list:
            serializer = self.get_serializer(data=data)
            if serializer.is_valid():
                try:
                    structure = serializer.save()
                    created_structures.append(structure)
                except Exception as e:
                    errors.append({"data": data, "error": str(e)})
            else:
                errors.append({"data": data, "errors": serializer.errors})

        return Response(
            {
                "created_count": len(created_structures),
                "error_count": len(errors),
                "created_structures": self.get_serializer(
                    created_structures, many=True
                ).data,
                "errors": errors,
            }
        )

    @action(detail=False, methods=["get"])
    def hierarchy_summary(self, request):
        """Get fee structure summary by hierarchy."""
        academic_year_id = request.query_params.get("academic_year")
        term_id = request.query_params.get("term")

        if not academic_year_id or not term_id:
            return Response(
                {"error": "academic_year and term parameters are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            from academics.models import AcademicYear, Term

            academic_year = AcademicYear.objects.get(id=academic_year_id)
            term = Term.objects.get(id=term_id)

            summary = FeeService.get_fee_summary_by_section(academic_year, term)
            return Response(summary)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class SpecialFeeViewSet(viewsets.ModelViewSet):
    """ViewSet for special fees."""

    queryset = SpecialFee.objects.select_related(
        "fee_category", "class_obj", "student", "term", "created_by"
    ).all()
    serializer_class = SpecialFeeSerializer
    permission_classes = [IsAuthenticated, IsAdminOrReadOnly]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = [
        "fee_type",
        "fee_category",
        "term",
        "is_active",
        "class_obj",
        "student",
    ]
    search_fields = ["name", "description", "reason"]
    ordering_fields = ["amount", "due_date", "created_at"]
    ordering = ["-created_at"]

    @action(detail=False, methods=["post"])
    def bulk_apply(self, request):
        """Apply special fee to multiple targets."""
        fee_data = request.data.get("fee_data", {})
        target_ids = request.data.get("target_ids", [])

        if not fee_data or not target_ids:
            return Response(
                {"error": "fee_data and target_ids are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            # Get targets based on fee type
            if fee_data["fee_type"] == "class_based":
                from academics.models import Class

                targets = Class.objects.filter(id__in=target_ids)
            else:
                from students.models import Student

                targets = Student.objects.filter(id__in=target_ids)

            created_fees = FeeService.bulk_apply_special_fee(fee_data, list(targets))

            return Response(
                {
                    "created_count": len(created_fees),
                    "created_fees": self.get_serializer(created_fees, many=True).data,
                }
            )

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class ScholarshipViewSet(viewsets.ModelViewSet):
    """ViewSet for scholarships."""

    queryset = Scholarship.objects.prefetch_related("applicable_categories").all()
    serializer_class = ScholarshipSerializer
    permission_classes = [IsAuthenticated, IsAdminOrReadOnly]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["academic_year", "criteria", "discount_type", "is_active"]
    search_fields = ["name", "description"]
    ordering_fields = ["name", "discount_value", "created_at"]
    ordering = ["-created_at"]

    @action(detail=True, methods=["get"])
    def eligible_students(self, request, pk=None):
        """Get students eligible for this scholarship."""
        scholarship = self.get_object()

        try:
            eligible_students = ScholarshipService.get_eligible_students(scholarship)

            # Serialize student data
            from students.api.serializers import StudentSerializer

            serializer = StudentSerializer(eligible_students, many=True)

            return Response(
                {
                    "scholarship": scholarship.name,
                    "eligible_count": len(eligible_students),
                    "students": serializer.data,
                }
            )

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"])
    def assign_to_students(self, request, pk=None):
        """Assign scholarship to multiple students."""
        scholarship = self.get_object()
        student_ids = request.data.get("student_ids", [])

        if not student_ids:
            return Response(
                {"error": "student_ids are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            from students.models import Student

            students = Student.objects.filter(id__in=student_ids)

            results = ScholarshipService.bulk_assign_scholarships(
                list(students), scholarship.id, request.user
            )

            return Response(results)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["get"])
    def impact_analysis(self, request, pk=None):
        """Get impact analysis for this scholarship."""
        scholarship = self.get_object()
        academic_year_id = request.query_params.get("academic_year")
        term_id = request.query_params.get("term")

        try:
            from academics.models import AcademicYear, Term

            academic_year = (
                AcademicYear.objects.get(id=academic_year_id)
                if academic_year_id
                else scholarship.academic_year
            )
            term = Term.objects.get(id=term_id) if term_id else None

            impact = ScholarshipService.calculate_scholarship_impact(
                scholarship.id, academic_year, term
            )

            return Response(impact)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class StudentScholarshipViewSet(viewsets.ModelViewSet):
    """ViewSet for student scholarship assignments."""

    queryset = StudentScholarship.objects.select_related(
        "student", "scholarship", "approved_by"
    ).all()
    serializer_class = StudentScholarshipSerializer
    permission_classes = [IsAuthenticated, IsAdminOrReadOnly]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = [
        "student",
        "scholarship",
        "status",
        "scholarship__academic_year",
    ]
    search_fields = [
        "student__user__first_name",
        "student__user__last_name",
        "scholarship__name",
    ]
    ordering_fields = ["approval_date", "created_at"]
    ordering = ["-created_at"]

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        """Approve a pending scholarship assignment."""
        student_scholarship = self.get_object()

        try:
            approved_scholarship = ScholarshipService.approve_scholarship(
                student_scholarship.id, request.user
            )

            serializer = self.get_serializer(approved_scholarship)
            return Response(serializer.data)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"])
    def suspend(self, request, pk=None):
        """Suspend an active scholarship."""
        student_scholarship = self.get_object()
        reason = request.data.get("reason", "")

        if not reason:
            return Response(
                {"error": "Reason is required for suspension"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            suspended_scholarship = ScholarshipService.suspend_scholarship(
                student_scholarship.id, reason, request.user
            )

            serializer = self.get_serializer(suspended_scholarship)
            return Response(serializer.data)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class InvoiceViewSet(viewsets.ModelViewSet):
    """ViewSet for invoices."""

    queryset = (
        Invoice.objects.select_related("student", "academic_year", "term", "created_by")
        .prefetch_related("items", "payments")
        .all()
    )
    serializer_class = InvoiceSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["student", "academic_year", "term", "status"]
    search_fields = [
        "invoice_number",
        "student__user__first_name",
        "student__user__last_name",
    ]
    ordering_fields = ["issue_date", "due_date", "net_amount", "created_at"]
    ordering = ["-created_at"]

    def get_queryset(self):
        """Filter queryset based on user permissions."""
        queryset = super().get_queryset()

        # If user is a parent, only show their children's invoices
        if hasattr(self.request.user, "parent"):
            parent = self.request.user.parent
            student_ids = parent.studentparentrelation_set.values_list(
                "student_id", flat=True
            )
            queryset = queryset.filter(student_id__in=student_ids)

        # If user is a student, only show their own invoices
        elif hasattr(self.request.user, "student"):
            queryset = queryset.filter(student=self.request.user.student)

        return queryset

    @action(detail=False, methods=["post"])
    def calculate_fees(self, request):
        """Calculate fees for a student without creating invoice."""
        serializer = FeeCalculationSerializer(data=request.data)
        if serializer.is_valid():
            try:
                from academics.models import AcademicYear, Term
                from students.models import Student

                student = Student.objects.get(
                    id=serializer.validated_data["student_id"]
                )
                academic_year = AcademicYear.objects.get(
                    id=serializer.validated_data["academic_year_id"]
                )
                term = Term.objects.get(id=serializer.validated_data["term_id"])

                fee_breakdown = FeeService.calculate_student_fees(
                    student, academic_year, term
                )
                return Response(fee_breakdown)

            except Exception as e:
                return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=["post"])
    def bulk_generate(self, request):
        """Generate invoices for multiple students."""
        serializer = BulkInvoiceGenerationSerializer(data=request.data)
        if serializer.is_valid():
            try:
                from academics.models import AcademicYear, Term
                from students.models import Student

                students = Student.objects.filter(
                    id__in=serializer.validated_data["student_ids"]
                )
                academic_year = AcademicYear.objects.get(
                    id=serializer.validated_data["academic_year_id"]
                )
                term = Term.objects.get(id=serializer.validated_data["term_id"])

                results = InvoiceService.bulk_generate_invoices(
                    list(students), academic_year, term, request.user
                )

                return Response(results)

            except Exception as e:
                return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=["get"])
    def overdue(self, request):
        """Get overdue invoices."""
        days_overdue = request.query_params.get("days", 30)

        try:
            overdue_invoices = InvoiceService.get_overdue_invoices(int(days_overdue))
            serializer = self.get_serializer(overdue_invoices, many=True)
            return Response(serializer.data)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["get"])
    def generate_pdf(self, request, pk=None):
        """Generate PDF for invoice."""
        invoice = self.get_object()

        try:
            pdf_data = InvoiceService.generate_invoice_pdf(invoice)
            return Response(pdf_data)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class PaymentViewSet(viewsets.ModelViewSet):
    """ViewSet for payments."""

    queryset = Payment.objects.select_related(
        "invoice", "invoice__student", "received_by"
    ).all()
    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["invoice", "payment_method", "status", "invoice__student"]
    search_fields = ["receipt_number", "transaction_id", "invoice__invoice_number"]
    ordering_fields = ["payment_date", "amount", "created_at"]
    ordering = ["-payment_date"]

    def get_queryset(self):
        """Filter queryset based on user permissions."""
        queryset = super().get_queryset()

        # If user is a parent, only show their children's payments
        if hasattr(self.request.user, "parent"):
            parent = self.request.user.parent
            student_ids = parent.studentparentrelation_set.values_list(
                "student_id", flat=True
            )
            queryset = queryset.filter(invoice__student_id__in=student_ids)

        # If user is a student, only show their own payments
        elif hasattr(self.request.user, "student"):
            queryset = queryset.filter(invoice__student=self.request.user.student)

        return queryset

    @action(detail=False, methods=["post"])
    def process_payment(self, request):
        """Process a new payment."""
        serializer = PaymentProcessingSerializer(data=request.data)
        if serializer.is_valid():
            try:
                payment = PaymentService.process_single_payment(
                    invoice_id=serializer.validated_data["invoice_id"],
                    amount=serializer.validated_data["amount"],
                    payment_method=serializer.validated_data["payment_method"],
                    received_by=request.user,
                    transaction_id=serializer.validated_data.get("transaction_id", ""),
                    reference_number=serializer.validated_data.get(
                        "reference_number", ""
                    ),
                    remarks=serializer.validated_data.get("remarks", ""),
                )

                payment_serializer = self.get_serializer(payment)
                return Response(payment_serializer.data, status=status.HTTP_201_CREATED)

            except Exception as e:
                return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["get"])
    def generate_receipt(self, request, pk=None):
        """Generate receipt data for payment."""
        payment = self.get_object()

        try:
            receipt_data = PaymentService.generate_receipt_data(payment.id)
            return Response(receipt_data)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=["get"])
    def collection_summary(self, request):
        """Get collection summary for date range."""
        date_from = request.query_params.get("date_from")
        date_to = request.query_params.get("date_to")
        group_by = request.query_params.get("group_by", "day")

        if not date_from or not date_to:
            return Response(
                {"error": "date_from and date_to parameters are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            from datetime import datetime

            start_date = datetime.strptime(date_from, "%Y-%m-%d").date()
            end_date = datetime.strptime(date_to, "%Y-%m-%d").date()

            summary = PaymentService.get_collection_summary(
                start_date, end_date, group_by
            )
            return Response(summary)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class FinancialAnalyticsViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for financial analytics (read-only)."""

    queryset = FinancialAnalytics.objects.select_related(
        "academic_year", "term", "section", "grade", "fee_category"
    ).all()
    serializer_class = FinancialAnalyticsSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["academic_year", "term", "section", "grade", "fee_category"]
    ordering_fields = ["calculated_at", "collection_rate", "total_expected_revenue"]
    ordering = ["-calculated_at"]

    @action(detail=False, methods=["get"])
    def collection_metrics(self, request):
        """Get comprehensive collection metrics."""
        academic_year_id = request.query_params.get("academic_year")
        term_id = request.query_params.get("term")
        section_id = request.query_params.get("section")
        grade_id = request.query_params.get("grade")

        if not academic_year_id:
            return Response(
                {"error": "academic_year parameter is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            from academics.models import AcademicYear, Grade, Section, Term

            academic_year = AcademicYear.objects.get(id=academic_year_id)
            term = Term.objects.get(id=term_id) if term_id else None
            section = Section.objects.get(id=section_id) if section_id else None
            grade = Grade.objects.get(id=grade_id) if grade_id else None

            metrics = FinancialAnalyticsService.calculate_collection_metrics(
                academic_year, term, section, grade
            )

            serializer = CollectionMetricsSerializer(data=metrics)
            serializer.is_valid(raise_exception=True)
            return Response(serializer.data)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=["get"])
    def payment_trends(self, request):
        """Get payment trends analysis."""
        academic_year_id = request.query_params.get("academic_year")
        days = int(request.query_params.get("days", 30))

        if not academic_year_id:
            return Response(
                {"error": "academic_year parameter is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            from academics.models import AcademicYear

            academic_year = AcademicYear.objects.get(id=academic_year_id)

            trends = FinancialAnalyticsService.generate_payment_trends(
                academic_year, days
            )

            serializer = PaymentTrendsSerializer(data=trends)
            serializer.is_valid(raise_exception=True)
            return Response(serializer.data)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=["get"])
    def defaulter_analysis(self, request):
        """Get defaulter analysis."""
        academic_year_id = request.query_params.get("academic_year")
        term_id = request.query_params.get("term")
        days_overdue = int(request.query_params.get("days_overdue", 30))

        if not academic_year_id:
            return Response(
                {"error": "academic_year parameter is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            from academics.models import AcademicYear, Term

            academic_year = AcademicYear.objects.get(id=academic_year_id)
            term = Term.objects.get(id=term_id) if term_id else None

            analysis = FinancialAnalyticsService.analyze_defaulters(
                academic_year, term, days_overdue
            )

            serializer = DefaulterAnalysisSerializer(data=analysis)
            serializer.is_valid(raise_exception=True)
            return Response(serializer.data)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=["get"])
    def scholarship_impact(self, request):
        """Get scholarship impact analysis."""
        academic_year_id = request.query_params.get("academic_year")
        term_id = request.query_params.get("term")

        if not academic_year_id:
            return Response(
                {"error": "academic_year parameter is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            from academics.models import AcademicYear, Term

            academic_year = AcademicYear.objects.get(id=academic_year_id)
            term = Term.objects.get(id=term_id) if term_id else None

            impact = FinancialAnalyticsService.calculate_scholarship_impact(
                academic_year, term
            )

            serializer = ScholarshipImpactSerializer(data=impact)
            serializer.is_valid(raise_exception=True)
            return Response(serializer.data)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class FeeWaiverViewSet(viewsets.ModelViewSet):
    """ViewSet for fee waivers."""

    queryset = FeeWaiver.objects.select_related(
        "student", "invoice", "requested_by", "approved_by"
    ).all()
    serializer_class = FeeWaiverSerializer
    permission_classes = [IsAuthenticated, IsAdminOrReadOnly]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["student", "status", "waiver_type"]
    search_fields = ["student__user__first_name", "student__user__last_name", "reason"]
    ordering_fields = ["created_at", "amount"]
    ordering = ["-created_at"]

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        """Approve a fee waiver."""
        waiver = self.get_object()

        try:
            payment = InvoiceService.approve_fee_waiver(waiver, request.user)

            # Return updated waiver data
            waiver.refresh_from_db()
            serializer = self.get_serializer(waiver)
            return Response(serializer.data)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        """Reject a fee waiver."""
        waiver = self.get_object()
        reason = request.data.get("reason", "")

        if waiver.status != "pending":
            return Response(
                {"error": "Only pending waivers can be rejected"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        waiver.status = "rejected"
        waiver.remarks += f"\nRejected: {reason}"
        waiver.save()

        serializer = self.get_serializer(waiver)
        return Response(serializer.data)
