from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.generic import (
    ListView,
    DetailView,
    CreateView,
    UpdateView,
    DeleteView,
    TemplateView,
    View,
)
from django.urls import reverse_lazy
from django.db.models import Q, Sum, Count
from django.utils import timezone
from decimal import Decimal
import json

from .models import (
    FeeCategory,
    FeeStructure,
    SpecialFee,
    Scholarship,
    StudentScholarship,
    Invoice,
    Payment,
    FeeWaiver,
    FinancialAnalytics,
)
from .forms import (
    FeeCategoryForm,
    FeeStructureForm,
    SpecialFeeForm,
    ScholarshipForm,
    StudentScholarshipForm,
    PaymentForm,
    FeeWaiverForm,
    BulkInvoiceGenerationForm,
    FinancialReportFilterForm,
)
from .services.fee_service import FeeService
from .services.invoice_service import InvoiceService
from .services.payment_service import PaymentService
from .services.scholarship_service import ScholarshipService
from .services.analytics_service import FinancialAnalyticsService

from academics.models import AcademicYear, Term, Section, Grade, Class
from students.models import Student


class FinancePermissionMixin(PermissionRequiredMixin):
    """Base mixin for finance permissions."""

    permission_required = "finance.view_invoice"  # Default permission


class DashboardView(LoginRequiredMixin, TemplateView):
    """Finance dashboard view."""

    template_name = "finance/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get current academic year and term
        try:
            current_year = AcademicYear.objects.get(is_current=True)
            current_term = Term.objects.get(is_current=True, academic_year=current_year)
        except (AcademicYear.DoesNotExist, Term.DoesNotExist):
            current_year = None
            current_term = None

        if current_year and current_term:
            # Get key metrics
            context.update(
                {
                    "current_year": current_year,
                    "current_term": current_term,
                    "total_invoices": Invoice.objects.filter(
                        academic_year=current_year, term=current_term
                    ).count(),
                    "total_collections": Payment.objects.filter(
                        invoice__academic_year=current_year,
                        invoice__term=current_term,
                        status="completed",
                    ).aggregate(total=Sum("amount"))["total"]
                    or Decimal("0.00"),
                    "pending_invoices": Invoice.objects.filter(
                        academic_year=current_year,
                        term=current_term,
                        status__in=["unpaid", "partially_paid"],
                    ).count(),
                    "overdue_invoices": Invoice.objects.filter(
                        academic_year=current_year,
                        term=current_term,
                        due_date__lt=timezone.now().date(),
                        status__in=["unpaid", "partially_paid"],
                    ).count(),
                }
            )

        return context


# Fee Category Views
class FeeCategoryListView(FinancePermissionMixin, ListView):
    """List fee categories."""

    model = FeeCategory
    template_name = "finance/fee_category_list.html"
    context_object_name = "categories"
    paginate_by = 20


class FeeCategoryCreateView(FinancePermissionMixin, CreateView):
    """Create fee category."""

    model = FeeCategory
    form_class = FeeCategoryForm
    template_name = "finance/fee_category_form.html"
    success_url = reverse_lazy("finance:fee-category-list")


class FeeCategoryDetailView(FinancePermissionMixin, DetailView):
    """Fee category detail view."""

    model = FeeCategory
    template_name = "finance/fee_category_detail.html"


class FeeCategoryUpdateView(FinancePermissionMixin, UpdateView):
    """Update fee category."""

    model = FeeCategory
    form_class = FeeCategoryForm
    template_name = "finance/fee_category_form.html"
    success_url = reverse_lazy("finance:fee-category-list")


# Fee Structure Views
class FeeStructureListView(FinancePermissionMixin, ListView):
    """List fee structures."""

    model = FeeStructure
    template_name = "finance/fee_structure_list.html"
    context_object_name = "structures"
    paginate_by = 20

    def get_queryset(self):
        queryset = (
            super()
            .get_queryset()
            .select_related("academic_year", "term", "section", "grade", "fee_category")
        )

        # Filter by query parameters
        academic_year = self.request.GET.get("academic_year")
        term = self.request.GET.get("term")

        if academic_year:
            queryset = queryset.filter(academic_year_id=academic_year)
        if term:
            queryset = queryset.filter(term_id=term)

        return queryset


class FeeStructureCreateView(FinancePermissionMixin, CreateView):
    """Create fee structure."""

    model = FeeStructure
    form_class = FeeStructureForm
    template_name = "finance/fee_structure_form.html"
    success_url = reverse_lazy("finance:fee-structure-list")


class FeeStructureDetailView(FinancePermissionMixin, DetailView):
    """Fee structure detail view."""

    model = FeeStructure
    template_name = "finance/fee_structure_detail.html"


class FeeStructureUpdateView(FinancePermissionMixin, UpdateView):
    """Update fee structure."""

    model = FeeStructure
    form_class = FeeStructureForm
    template_name = "finance/fee_structure_form.html"
    success_url = reverse_lazy("finance:fee-structure-list")


# Special Fee Views
class SpecialFeeListView(FinancePermissionMixin, ListView):
    """List special fees."""

    model = SpecialFee
    template_name = "finance/special_fee_list.html"
    context_object_name = "special_fees"
    paginate_by = 20


class SpecialFeeCreateView(FinancePermissionMixin, CreateView):
    """Create special fee."""

    model = SpecialFee
    form_class = SpecialFeeForm
    template_name = "finance/special_fee_form.html"
    success_url = reverse_lazy("finance:special-fee-list")


class SpecialFeeDetailView(FinancePermissionMixin, DetailView):
    """Special fee detail view."""

    model = SpecialFee
    template_name = "finance/special_fee_detail.html"


# Scholarship Views
class ScholarshipListView(FinancePermissionMixin, ListView):
    """List scholarships."""

    model = Scholarship
    template_name = "finance/scholarship_list.html"
    context_object_name = "scholarships"
    paginate_by = 20


class ScholarshipCreateView(FinancePermissionMixin, CreateView):
    """Create scholarship."""

    model = Scholarship
    form_class = ScholarshipForm
    template_name = "finance/scholarship_form.html"
    success_url = reverse_lazy("finance:scholarship-list")


class ScholarshipDetailView(FinancePermissionMixin, DetailView):
    """Scholarship detail view."""

    model = Scholarship
    template_name = "finance/scholarship_detail.html"


class ScholarshipAssignView(FinancePermissionMixin, TemplateView):
    """Assign scholarship to students."""

    template_name = "finance/scholarship_assign.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        scholarship = get_object_or_404(Scholarship, pk=kwargs["pk"])
        context["scholarship"] = scholarship
        context["eligible_students"] = ScholarshipService.get_eligible_students(
            scholarship
        )
        return context


class StudentScholarshipListView(FinancePermissionMixin, ListView):
    """List student scholarship assignments."""

    model = StudentScholarship
    template_name = "finance/student_scholarship_list.html"
    context_object_name = "assignments"
    paginate_by = 20


class StudentScholarshipApproveView(FinancePermissionMixin, View):
    """Approve student scholarship."""

    def post(self, request, pk):
        assignment = get_object_or_404(StudentScholarship, pk=pk)

        try:
            ScholarshipService.approve_scholarship(pk, request.user)
            messages.success(request, f"Scholarship approved for {assignment.student}")
        except Exception as e:
            messages.error(request, f"Error approving scholarship: {e}")

        return redirect("finance:student-scholarship-list")


# Invoice Views
class InvoiceListView(FinancePermissionMixin, ListView):
    """List invoices."""

    model = Invoice
    template_name = "finance/invoice_list.html"
    context_object_name = "invoices"
    paginate_by = 20

    def get_queryset(self):
        queryset = (
            super().get_queryset().select_related("student", "academic_year", "term")
        )

        # Filter based on user permissions
        if hasattr(self.request.user, "parent"):
            # Parents see only their children's invoices
            parent = self.request.user.parent
            student_ids = parent.studentparentrelation_set.values_list(
                "student_id", flat=True
            )
            queryset = queryset.filter(student_id__in=student_ids)
        elif hasattr(self.request.user, "student"):
            # Students see only their own invoices
            queryset = queryset.filter(student=self.request.user.student)

        return queryset


class InvoiceDetailView(FinancePermissionMixin, DetailView):
    """Invoice detail view."""

    model = Invoice
    template_name = "finance/invoice_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        invoice = self.get_object()
        context["payments"] = invoice.payments.all().order_by("-payment_date")
        context["invoice_items"] = invoice.items.all()
        return context


class InvoiceGenerateView(FinancePermissionMixin, TemplateView):
    """Generate invoice for a student."""

    template_name = "finance/invoice_generate.html"

    def post(self, request):
        student_id = request.POST.get("student_id")
        academic_year_id = request.POST.get("academic_year_id")
        term_id = request.POST.get("term_id")

        try:
            student = Student.objects.get(id=student_id)
            academic_year = AcademicYear.objects.get(id=academic_year_id)
            term = Term.objects.get(id=term_id)

            invoice = InvoiceService.generate_invoice(
                student, academic_year, term, request.user
            )

            messages.success(
                request, f"Invoice {invoice.invoice_number} generated successfully"
            )
            return redirect("finance:invoice-detail", pk=invoice.pk)

        except Exception as e:
            messages.error(request, f"Error generating invoice: {e}")
            return redirect("finance:invoice-generate")


class BulkInvoiceGenerateView(FinancePermissionMixin, TemplateView):
    """Generate invoices in bulk."""

    template_name = "finance/bulk_invoice_generate.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["form"] = BulkInvoiceGenerationForm()
        return context

    def post(self, request):
        form = BulkInvoiceGenerationForm(request.POST)

        if form.is_valid():
            # Get students based on selected criteria
            students = Student.objects.filter(status="active")

            if form.cleaned_data["section"]:
                students = students.filter(
                    current_class__grade__section=form.cleaned_data["section"]
                )
            elif form.cleaned_data["grade"]:
                students = students.filter(
                    current_class__grade=form.cleaned_data["grade"]
                )
            elif form.cleaned_data["class_obj"]:
                students = students.filter(current_class=form.cleaned_data["class_obj"])

            # Generate invoices
            results = InvoiceService.bulk_generate_invoices(
                list(students),
                form.cleaned_data["academic_year"],
                form.cleaned_data["term"],
                request.user,
            )

            messages.success(
                request,
                f"Generated {len(results['created'])} invoices. "
                f"Skipped {len(results['skipped'])}. "
                f"Errors: {len(results['errors'])}",
            )

        return redirect("finance:bulk-invoice-generate")


class InvoicePDFView(FinancePermissionMixin, View):
    """Generate PDF for invoice."""

    def get(self, request, pk):
        invoice = get_object_or_404(Invoice, pk=pk)

        # Generate PDF (placeholder - integrate with reportlab or similar)
        pdf_data = InvoiceService.generate_invoice_pdf(invoice)

        # Return JSON for now (would return PDF in real implementation)
        return JsonResponse(pdf_data)


# Payment Views
class PaymentListView(FinancePermissionMixin, ListView):
    """List payments."""

    model = Payment
    template_name = "finance/payment_list.html"
    context_object_name = "payments"
    paginate_by = 20

    def get_queryset(self):
        queryset = (
            super()
            .get_queryset()
            .select_related("invoice", "invoice__student", "received_by")
        )

        # Filter based on user permissions
        if hasattr(self.request.user, "parent"):
            parent = self.request.user.parent
            student_ids = parent.studentparentrelation_set.values_list(
                "student_id", flat=True
            )
            queryset = queryset.filter(invoice__student_id__in=student_ids)
        elif hasattr(self.request.user, "student"):
            queryset = queryset.filter(invoice__student=self.request.user.student)

        return queryset


class PaymentDetailView(FinancePermissionMixin, DetailView):
    """Payment detail view."""

    model = Payment
    template_name = "finance/payment_detail.html"


class PaymentProcessView(FinancePermissionMixin, TemplateView):
    """Process payment for invoice."""

    template_name = "finance/payment_process.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["form"] = PaymentForm()

        # Get unpaid invoices
        context["unpaid_invoices"] = Invoice.objects.filter(
            status__in=["unpaid", "partially_paid"]
        ).select_related("student")[:100]

        return context

    def post(self, request):
        form = PaymentForm(request.POST)

        if form.is_valid():
            try:
                payment = PaymentService.process_single_payment(
                    invoice_id=form.cleaned_data["invoice"].id,
                    amount=form.cleaned_data["amount"],
                    payment_method=form.cleaned_data["payment_method"],
                    received_by=request.user,
                    transaction_id=form.cleaned_data.get("transaction_id", ""),
                    reference_number=form.cleaned_data.get("reference_number", ""),
                    remarks=form.cleaned_data.get("remarks", ""),
                )

                messages.success(
                    request,
                    f"Payment of ${payment.amount} processed successfully. "
                    f"Receipt: {payment.receipt_number}",
                )
                return redirect("finance:payment-detail", pk=payment.pk)

            except Exception as e:
                messages.error(request, f"Error processing payment: {e}")

        return render(request, self.template_name, {"form": form})


class PaymentReceiptView(FinancePermissionMixin, View):
    """Generate payment receipt."""

    def get(self, request, pk):
        payment = get_object_or_404(Payment, pk=pk)
        receipt_data = PaymentService.generate_receipt_data(pk)

        # Return JSON for now (would return PDF in real implementation)
        return JsonResponse(receipt_data)


# Fee Waiver Views
class FeeWaiverListView(FinancePermissionMixin, ListView):
    """List fee waivers."""

    model = FeeWaiver
    template_name = "finance/fee_waiver_list.html"
    context_object_name = "waivers"
    paginate_by = 20


class FeeWaiverCreateView(FinancePermissionMixin, CreateView):
    """Create fee waiver request."""

    model = FeeWaiver
    form_class = FeeWaiverForm
    template_name = "finance/fee_waiver_form.html"
    success_url = reverse_lazy("finance:fee-waiver-list")

    def form_valid(self, form):
        form.instance.requested_by = self.request.user
        return super().form_valid(form)


class FeeWaiverDetailView(FinancePermissionMixin, DetailView):
    """Fee waiver detail view."""

    model = FeeWaiver
    template_name = "finance/fee_waiver_detail.html"


class FeeWaiverApproveView(FinancePermissionMixin, View):
    """Approve fee waiver."""

    def post(self, request, pk):
        waiver = get_object_or_404(FeeWaiver, pk=pk)

        try:
            InvoiceService.approve_fee_waiver(waiver, request.user)
            messages.success(request, f"Fee waiver approved for {waiver.student}")
        except Exception as e:
            messages.error(request, f"Error approving waiver: {e}")

        return redirect("finance:fee-waiver-detail", pk=pk)


# Reports and Analytics Views
class ReportsView(FinancePermissionMixin, TemplateView):
    """Reports dashboard."""

    template_name = "finance/reports.html"


class CollectionReportView(FinancePermissionMixin, TemplateView):
    """Collection report view."""

    template_name = "finance/collection_report.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["form"] = FinancialReportFilterForm()

        # Get current academic year metrics if available
        try:
            current_year = AcademicYear.objects.get(is_current=True)
            current_term = Term.objects.get(is_current=True, academic_year=current_year)

            context["metrics"] = FinancialAnalyticsService.calculate_collection_metrics(
                current_year, current_term
            )
        except (AcademicYear.DoesNotExist, Term.DoesNotExist):
            context["metrics"] = None

        return context


class DefaultersReportView(FinancePermissionMixin, TemplateView):
    """Defaulters report view."""

    template_name = "finance/defaulters_report.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        try:
            current_year = AcademicYear.objects.get(is_current=True)
            context["defaulters"] = InvoiceService.get_defaulter_report(current_year)
        except AcademicYear.DoesNotExist:
            context["defaulters"] = []

        return context


class ScholarshipReportView(FinancePermissionMixin, TemplateView):
    """Scholarship report view."""

    template_name = "finance/scholarship_report.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        try:
            current_year = AcademicYear.objects.get(is_current=True)
            context["report"] = ScholarshipService.generate_scholarship_report(
                current_year
            )
        except AcademicYear.DoesNotExist:
            context["report"] = None

        return context


class FinancialSummaryReportView(FinancePermissionMixin, TemplateView):
    """Financial summary report view."""

    template_name = "finance/financial_summary_report.html"


class AnalyticsView(FinancePermissionMixin, TemplateView):
    """Analytics dashboard."""

    template_name = "finance/analytics.html"


class CollectionMetricsView(FinancePermissionMixin, View):
    """Collection metrics API view."""

    def get(self, request):
        academic_year_id = request.GET.get("academic_year")
        term_id = request.GET.get("term")

        if not academic_year_id:
            return JsonResponse({"error": "Academic year is required"}, status=400)

        try:
            academic_year = AcademicYear.objects.get(id=academic_year_id)
            term = Term.objects.get(id=term_id) if term_id else None

            metrics = FinancialAnalyticsService.calculate_collection_metrics(
                academic_year, term
            )
            return JsonResponse(metrics)

        except Exception as e:
            return JsonResponse({"error": str(e)}, status=400)


class PaymentTrendsView(FinancePermissionMixin, View):
    """Payment trends API view."""

    def get(self, request):
        academic_year_id = request.GET.get("academic_year")
        days = int(request.GET.get("days", 30))

        if not academic_year_id:
            return JsonResponse({"error": "Academic year is required"}, status=400)

        try:
            academic_year = AcademicYear.objects.get(id=academic_year_id)

            trends = FinancialAnalyticsService.generate_payment_trends(
                academic_year, days
            )
            return JsonResponse(trends)

        except Exception as e:
            return JsonResponse({"error": str(e)}, status=400)


# Utility Views
class CalculateFeesView(FinancePermissionMixin, View):
    """Calculate fees for a student."""

    def post(self, request):
        student_id = request.POST.get("student_id")
        academic_year_id = request.POST.get("academic_year_id")
        term_id = request.POST.get("term_id")

        try:
            student = Student.objects.get(id=student_id)
            academic_year = AcademicYear.objects.get(id=academic_year_id)
            term = Term.objects.get(id=term_id)

            fee_breakdown = FeeService.calculate_student_fees(
                student, academic_year, term
            )
            return JsonResponse(fee_breakdown)

        except Exception as e:
            return JsonResponse({"error": str(e)}, status=400)


class StudentSearchView(FinancePermissionMixin, View):
    """Search students for forms."""

    def get(self, request):
        query = request.GET.get("q", "")

        if len(query) < 2:
            return JsonResponse({"students": []})

        students = Student.objects.filter(
            Q(user__first_name__icontains=query)
            | Q(user__last_name__icontains=query)
            | Q(admission_number__icontains=query)
        ).select_related("user", "current_class")[:20]

        student_data = [
            {
                "id": student.id,
                "name": student.user.get_full_name(),
                "admission_number": student.admission_number,
                "class": str(student.current_class) if student.current_class else "N/A",
            }
            for student in students
        ]

        return JsonResponse({"students": student_data})


class InvoiceSearchView(FinancePermissionMixin, View):
    """Search invoices."""

    def get(self, request):
        query = request.GET.get("q", "")

        if len(query) < 2:
            return JsonResponse({"invoices": []})

        invoices = Invoice.objects.filter(
            Q(invoice_number__icontains=query)
            | Q(student__user__first_name__icontains=query)
            | Q(student__user__last_name__icontains=query)
            | Q(student__admission_number__icontains=query)
        ).select_related("student", "academic_year", "term")[:20]

        invoice_data = [
            {
                "id": invoice.id,
                "invoice_number": invoice.invoice_number,
                "student_name": invoice.student.user.get_full_name(),
                "net_amount": str(invoice.net_amount),
                "outstanding_amount": str(invoice.outstanding_amount),
                "status": invoice.status,
            }
            for invoice in invoices
        ]

        return JsonResponse({"invoices": invoice_data})


# AJAX Views for Dynamic Forms
class GradesBySectionView(View):
    """Get grades by section (AJAX)."""

    def get(self, request):
        section_id = request.GET.get("section_id")

        if section_id:
            grades = Grade.objects.filter(section_id=section_id).values("id", "name")
            return JsonResponse({"grades": list(grades)})

        return JsonResponse({"grades": []})


class ClassesByGradeView(View):
    """Get classes by grade (AJAX)."""

    def get(self, request):
        grade_id = request.GET.get("grade_id")
        academic_year_id = request.GET.get("academic_year_id")

        if grade_id:
            classes = Class.objects.filter(grade_id=grade_id)
            if academic_year_id:
                classes = classes.filter(academic_year_id=academic_year_id)

            class_data = classes.values("id", "name")
            return JsonResponse({"classes": list(class_data)})

        return JsonResponse({"classes": []})


class StudentsByClassView(View):
    """Get students by class (AJAX)."""

    def get(self, request):
        class_id = request.GET.get("class_id")

        if class_id:
            students = (
                Student.objects.filter(current_class_id=class_id, status="active")
                .select_related("user")
                .values("id", "user__first_name", "user__last_name", "admission_number")
            )

            student_data = [
                {
                    "id": student["id"],
                    "name": f"{student['user__first_name']} {student['user__last_name']}",
                    "admission_number": student["admission_number"],
                }
                for student in students
            ]

            return JsonResponse({"students": student_data})

        return JsonResponse({"students": []})


class InvoiceDetailsView(View):
    """Get invoice details (AJAX)."""

    def get(self, request):
        invoice_id = request.GET.get("invoice_id")

        if invoice_id:
            try:
                invoice = Invoice.objects.select_related("student").get(id=invoice_id)

                data = {
                    "student_name": invoice.student.user.get_full_name(),
                    "net_amount": str(invoice.net_amount),
                    "paid_amount": str(invoice.paid_amount),
                    "outstanding_amount": str(invoice.outstanding_amount),
                    "status": invoice.status,
                    "due_date": (
                        invoice.due_date.isoformat() if invoice.due_date else None
                    ),
                }

                return JsonResponse(data)

            except Invoice.DoesNotExist:
                return JsonResponse({"error": "Invoice not found"}, status=404)

        return JsonResponse({"error": "Invoice ID required"}, status=400)
