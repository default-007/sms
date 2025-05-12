from django.shortcuts import render, get_object_or_404, redirect
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
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.db.models import Q, Sum, Count, F, ExpressionWrapper, DecimalField
from django.db.models.functions import TruncMonth
from django.forms import inlineformset_factory
from django.http import HttpResponse
from django.utils import timezone
from datetime import timedelta
import csv

from src.courses.models import Grade

from .models import (
    FeeCategory,
    FeeStructure,
    Scholarship,
    StudentScholarship,
    Invoice,
    InvoiceItem,
    Payment,
    Expense,
)
from .forms import (
    FeeCategoryForm,
    FeeStructureForm,
    ScholarshipForm,
    StudentScholarshipForm,
    InvoiceForm,
    InvoiceItemForm,
    InvoiceItemFormSet,
    BulkInvoiceGenerationForm,
    PaymentForm,
    ExpenseForm,
)
from .services import FinanceService
from src.core.decorators import role_required, module_access_required


# Mixin to check finance module access
class FinanceAccessMixin(LoginRequiredMixin):
    """Mixin to ensure users have access to finance module."""

    def dispatch(self, request, *args, **kwargs):
        # Check if user has access to finance module
        if not request.user.is_authenticated:
            return self.handle_no_permission()

        # Staff members always have access
        if request.user.is_staff:
            return super().dispatch(request, *args, **kwargs)

        # Check user roles for finance permission
        has_access = False
        for role_assignment in request.user.role_assignments.all():
            role_permissions = role_assignment.role.permissions
            if "finance" in role_permissions and role_permissions["finance"]:
                has_access = True
                break

        if not has_access:
            messages.error(
                request, "You do not have permission to access the finance module."
            )
            return redirect("core:dashboard")

        return super().dispatch(request, *args, **kwargs)


# Fee Category Views
class FeeCategoryListView(FinanceAccessMixin, ListView):
    model = FeeCategory
    context_object_name = "fee_categories"
    template_name = "finance/fee_category_list.html"
    paginate_by = 20

    def get_queryset(self):
        queryset = super().get_queryset()

        # Apply search filter
        search_query = self.request.GET.get("search", "")
        if search_query:
            queryset = queryset.filter(
                Q(name__icontains=search_query) | Q(description__icontains=search_query)
            )

        return queryset


class FeeCategoryDetailView(FinanceAccessMixin, DetailView):
    model = FeeCategory
    context_object_name = "fee_category"
    template_name = "finance/fee_category_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["fee_structures"] = self.object.fee_structures.all()
        return context


class FeeCategoryCreateView(FinanceAccessMixin, CreateView):
    model = FeeCategory
    form_class = FeeCategoryForm
    template_name = "finance/fee_category_form.html"
    success_url = reverse_lazy("finance:fee-category-list")

    def form_valid(self, form):
        messages.success(self.request, "Fee category created successfully.")
        return super().form_valid(form)


class FeeCategoryUpdateView(FinanceAccessMixin, UpdateView):
    model = FeeCategory
    form_class = FeeCategoryForm
    template_name = "finance/fee_category_form.html"

    def get_success_url(self):
        return reverse_lazy(
            "finance:fee-category-detail", kwargs={"pk": self.object.pk}
        )

    def form_valid(self, form):
        messages.success(self.request, "Fee category updated successfully.")
        return super().form_valid(form)


class FeeCategoryDeleteView(FinanceAccessMixin, DeleteView):
    model = FeeCategory
    template_name = "finance/fee_category_confirm_delete.html"
    success_url = reverse_lazy("finance:fee-category-list")

    def delete(self, request, *args, **kwargs):
        messages.success(request, "Fee category deleted successfully.")
        return super().delete(request, *args, **kwargs)


# Fee Structure Views
class FeeStructureListView(FinanceAccessMixin, ListView):
    model = FeeStructure
    context_object_name = "fee_structures"
    template_name = "finance/fee_structure_list.html"
    paginate_by = 20

    def get_queryset(self):
        queryset = (
            super()
            .get_queryset()
            .select_related("academic_year", "grade", "fee_category")
        )

        # Apply filters
        academic_year = self.request.GET.get("academic_year", "")
        grade = self.request.GET.get("grade", "")
        fee_category = self.request.GET.get("fee_category", "")

        if academic_year:
            queryset = queryset.filter(academic_year_id=academic_year)

        if grade:
            queryset = queryset.filter(grade_id=grade)

        if fee_category:
            queryset = queryset.filter(fee_category_id=fee_category)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from src.courses.models import Grade, AcademicYear

        context["academic_years"] = AcademicYear.objects.all()
        context["grades"] = Grade.objects.all()
        context["fee_categories"] = FeeCategory.objects.all()

        # Get selected filters
        context["selected_academic_year"] = self.request.GET.get("academic_year", "")
        context["selected_grade"] = self.request.GET.get("grade", "")
        context["selected_fee_category"] = self.request.GET.get("fee_category", "")

        return context


class FeeStructureDetailView(FinanceAccessMixin, DetailView):
    model = FeeStructure
    context_object_name = "fee_structure"
    template_name = "finance/fee_structure_detail.html"


class FeeStructureCreateView(FinanceAccessMixin, CreateView):
    model = FeeStructure
    form_class = FeeStructureForm
    template_name = "finance/fee_structure_form.html"
    success_url = reverse_lazy("finance:fee-structure-list")

    def form_valid(self, form):
        messages.success(self.request, "Fee structure created successfully.")
        return super().form_valid(form)


class FeeStructureUpdateView(FinanceAccessMixin, UpdateView):
    model = FeeStructure
    form_class = FeeStructureForm
    template_name = "finance/fee_structure_form.html"

    def get_success_url(self):
        return reverse_lazy(
            "finance:fee-structure-detail", kwargs={"pk": self.object.pk}
        )

    def form_valid(self, form):
        messages.success(self.request, "Fee structure updated successfully.")
        return super().form_valid(form)


class FeeStructureDeleteView(FinanceAccessMixin, DeleteView):
    model = FeeStructure
    template_name = "finance/fee_structure_confirm_delete.html"
    success_url = reverse_lazy("finance:fee-structure-list")

    def delete(self, request, *args, **kwargs):
        messages.success(request, "Fee structure deleted successfully.")
        return super().delete(request, *args, **kwargs)


# Scholarship Views
class ScholarshipListView(FinanceAccessMixin, ListView):
    model = Scholarship
    context_object_name = "scholarships"
    template_name = "finance/scholarship_list.html"
    paginate_by = 20

    def get_queryset(self):
        queryset = super().get_queryset().select_related("academic_year")

        # Apply search filter
        search_query = self.request.GET.get("search", "")
        if search_query:
            queryset = queryset.filter(
                Q(name__icontains=search_query) | Q(description__icontains=search_query)
            )

        # Apply academic year filter
        academic_year = self.request.GET.get("academic_year", "")
        if academic_year:
            queryset = queryset.filter(academic_year_id=academic_year)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from src.courses.models import AcademicYear

        context["academic_years"] = AcademicYear.objects.all()
        context["selected_academic_year"] = self.request.GET.get("academic_year", "")

        return context


class ScholarshipDetailView(FinanceAccessMixin, DetailView):
    model = Scholarship
    context_object_name = "scholarship"
    template_name = "finance/scholarship_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["student_scholarships"] = (
            self.object.student_scholarships.select_related("student__user")
        )
        return context


class ScholarshipCreateView(FinanceAccessMixin, CreateView):
    model = Scholarship
    form_class = ScholarshipForm
    template_name = "finance/scholarship_form.html"
    success_url = reverse_lazy("finance:scholarship-list")

    def form_valid(self, form):
        messages.success(self.request, "Scholarship created successfully.")
        return super().form_valid(form)


class ScholarshipUpdateView(FinanceAccessMixin, UpdateView):
    model = Scholarship
    form_class = ScholarshipForm
    template_name = "finance/scholarship_form.html"

    def get_success_url(self):
        return reverse_lazy("finance:scholarship-detail", kwargs={"pk": self.object.pk})

    def form_valid(self, form):
        messages.success(self.request, "Scholarship updated successfully.")
        return super().form_valid(form)


class ScholarshipDeleteView(FinanceAccessMixin, DeleteView):
    model = Scholarship
    template_name = "finance/scholarship_confirm_delete.html"
    success_url = reverse_lazy("finance:scholarship-list")

    def delete(self, request, *args, **kwargs):
        messages.success(request, "Scholarship deleted successfully.")
        return super().delete(request, *args, **kwargs)


# Student Scholarship Views
class StudentScholarshipListView(FinanceAccessMixin, ListView):
    model = StudentScholarship
    context_object_name = "student_scholarships"
    template_name = "finance/student_scholarship_list.html"
    paginate_by = 20

    def get_queryset(self):
        queryset = (
            super()
            .get_queryset()
            .select_related("student__user", "scholarship", "approved_by")
        )

        # Apply search filter
        search_query = self.request.GET.get("search", "")
        if search_query:
            queryset = queryset.filter(
                Q(student__user__first_name__icontains=search_query)
                | Q(student__user__last_name__icontains=search_query)
                | Q(student__admission_number__icontains=search_query)
                | Q(scholarship__name__icontains=search_query)
            )

        # Apply status filter
        status = self.request.GET.get("status", "")
        if status:
            queryset = queryset.filter(status=status)

        # Apply scholarship filter
        scholarship = self.request.GET.get("scholarship", "")
        if scholarship:
            queryset = queryset.filter(scholarship_id=scholarship)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["scholarships"] = Scholarship.objects.all()
        context["status_choices"] = dict(StudentScholarship.STATUS_CHOICES)

        # Get selected filters
        context["selected_status"] = self.request.GET.get("status", "")
        context["selected_scholarship"] = self.request.GET.get("scholarship", "")
        context["search_query"] = self.request.GET.get("search", "")

        return context


class StudentScholarshipDetailView(FinanceAccessMixin, DetailView):
    model = StudentScholarship
    context_object_name = "student_scholarship"
    template_name = "finance/student_scholarship_detail.html"


class StudentScholarshipCreateView(FinanceAccessMixin, CreateView):
    model = StudentScholarship
    form_class = StudentScholarshipForm
    template_name = "finance/student_scholarship_form.html"
    success_url = reverse_lazy("finance:student-scholarship-list")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, "Student scholarship created successfully.")
        return super().form_valid(form)


class StudentScholarshipUpdateView(FinanceAccessMixin, UpdateView):
    model = StudentScholarship
    form_class = StudentScholarshipForm
    template_name = "finance/student_scholarship_form.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def get_success_url(self):
        return reverse_lazy(
            "finance:student-scholarship-detail", kwargs={"pk": self.object.pk}
        )

    def form_valid(self, form):
        messages.success(self.request, "Student scholarship updated successfully.")
        return super().form_valid(form)


# Invoice Views
class InvoiceListView(FinanceAccessMixin, ListView):
    model = Invoice
    context_object_name = "invoices"
    template_name = "finance/invoice_list.html"
    paginate_by = 20

    def get_queryset(self):
        queryset = (
            super()
            .get_queryset()
            .select_related("student__user", "academic_year", "created_by")
        )

        # Apply search filter
        search_query = self.request.GET.get("search", "")
        if search_query:
            queryset = queryset.filter(
                Q(invoice_number__icontains=search_query)
                | Q(student__user__first_name__icontains=search_query)
                | Q(student__user__last_name__icontains=search_query)
                | Q(student__admission_number__icontains=search_query)
            )

        # Apply date range filter
        start_date = self.request.GET.get("start_date", "")
        end_date = self.request.GET.get("end_date", "")

        if start_date:
            queryset = queryset.filter(issue_date__gte=start_date)

        if end_date:
            queryset = queryset.filter(issue_date__lte=end_date)

        # Apply status filter
        status = self.request.GET.get("status", "")
        if status:
            queryset = queryset.filter(status=status)

        # Apply class filter
        class_id = self.request.GET.get("class", "")
        if class_id:
            queryset = queryset.filter(student__current_class_id=class_id)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from src.courses.models import Class

        context["classes"] = Class.objects.select_related("grade", "section").all()
        context["status_choices"] = dict(Invoice.STATUS_CHOICES)

        # Get selected filters
        context["selected_status"] = self.request.GET.get("status", "")
        context["selected_class"] = self.request.GET.get("class", "")
        context["start_date"] = self.request.GET.get("start_date", "")
        context["end_date"] = self.request.GET.get("end_date", "")
        context["search_query"] = self.request.GET.get("search", "")

        return context


class InvoiceDetailView(FinanceAccessMixin, DetailView):
    model = Invoice
    context_object_name = "invoice"
    template_name = "finance/invoice_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["items"] = self.object.items.select_related(
            "fee_structure__fee_category"
        ).all()
        context["payments"] = self.object.payments.select_related("received_by").all()
        context["paid_amount"] = self.object.get_paid_amount()
        context["due_amount"] = self.object.get_due_amount()
        return context


class InvoiceCreateView(FinanceAccessMixin, CreateView):
    model = Invoice
    form_class = InvoiceForm
    template_name = "finance/invoice_form.html"
    success_url = reverse_lazy("finance:invoice-list")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        if self.request.POST:
            context["items_formset"] = InvoiceItemFormSet(
                self.request.POST, instance=self.object
            )
        else:
            context["items_formset"] = InvoiceItemFormSet(instance=self.object)

        return context

    def form_valid(self, form):
        context = self.get_context_data()
        items_formset = context["items_formset"]

        if items_formset.is_valid():
            with transaction.atomic():
                self.object = form.save()

                # Save invoice items
                items_formset.instance = self.object
                items_formset.save()

                # Calculate totals
                total_amount = sum(item.amount for item in self.object.items.all())
                net_amount = sum(item.net_amount for item in self.object.items.all())
                discount_amount = total_amount - net_amount

                # Update invoice with calculated totals
                self.object.total_amount = total_amount
                self.object.discount_amount = discount_amount
                self.object.net_amount = net_amount
                self.object.save()

                messages.success(self.request, "Invoice created successfully.")
                return redirect(self.get_success_url())
        else:
            return self.render_to_response(self.get_context_data(form=form))


class InvoiceUpdateView(FinanceAccessMixin, UpdateView):
    model = Invoice
    form_class = InvoiceForm
    template_name = "finance/invoice_form.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        if self.request.POST:
            context["items_formset"] = InvoiceItemFormSet(
                self.request.POST, instance=self.object
            )
        else:
            context["items_formset"] = InvoiceItemFormSet(instance=self.object)

        return context

    def form_valid(self, form):
        context = self.get_context_data()
        items_formset = context["items_formset"]

        if items_formset.is_valid():
            with transaction.atomic():
                self.object = form.save()

                # Save invoice items
                items_formset.instance = self.object
                items_formset.save()

                # The signal handler will update the totals

                messages.success(self.request, "Invoice updated successfully.")
                return redirect(self.get_success_url())
        else:
            return self.render_to_response(self.get_context_data(form=form))

    def get_success_url(self):
        return reverse_lazy("finance:invoice-detail", kwargs={"pk": self.object.pk})


class InvoiceDeleteView(FinanceAccessMixin, DeleteView):
    model = Invoice
    template_name = "finance/invoice_confirm_delete.html"
    success_url = reverse_lazy("finance:invoice-list")

    def delete(self, request, *args, **kwargs):
        messages.success(request, "Invoice deleted successfully.")
        return super().delete(request, *args, **kwargs)


class InvoicePrintView(FinanceAccessMixin, DetailView):
    model = Invoice
    template_name = "finance/invoice_print.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["items"] = self.object.items.select_related(
            "fee_structure__fee_category"
        ).all()
        context["school_info"] = {
            "name": "School Management System",  # You would get this from settings
            "address": "123 Education St, Knowledge City",
            "phone": "+1 (555) 123-4567",
            "email": "info@school.example.com",
        }
        return context


class BulkInvoiceGenerationView(FinanceAccessMixin, View):
    template_name = "finance/bulk_invoice_form.html"

    def get(self, request):
        form = BulkInvoiceGenerationForm()
        return render(request, self.template_name, {"form": form})

    def post(self, request):
        form = BulkInvoiceGenerationForm(request.POST)

        if form.is_valid():
            academic_year = form.cleaned_data["academic_year"]
            grade = form.cleaned_data["grade"]
            fee_category = form.cleaned_data["fee_category"]
            issue_date = form.cleaned_data["issue_date"]
            due_date = form.cleaned_data["due_date"]

            # Generate invoices
            invoices = FinanceService.generate_bulk_invoices(
                academic_year=academic_year,
                fee_category=fee_category,
                grade=grade,
                issue_date=issue_date,
                due_date=due_date,
                created_by=request.user,
            )

            messages.success(
                request, f"{len(invoices)} invoice(s) generated successfully."
            )
            return redirect("finance:invoice-list")

        return render(request, self.template_name, {"form": form})


# Payment Views
class PaymentListView(FinanceAccessMixin, ListView):
    model = Payment
    context_object_name = "payments"
    template_name = "finance/payment_list.html"
    paginate_by = 20

    def get_queryset(self):
        queryset = (
            super()
            .get_queryset()
            .select_related("invoice__student__user", "received_by")
        )

        # Apply search filter
        search_query = self.request.GET.get("search", "")
        if search_query:
            queryset = queryset.filter(
                Q(receipt_number__icontains=search_query)
                | Q(invoice__invoice_number__icontains=search_query)
                | Q(invoice__student__user__first_name__icontains=search_query)
                | Q(invoice__student__user__last_name__icontains=search_query)
                | Q(invoice__student__admission_number__icontains=search_query)
            )

        # Apply date range filter
        start_date = self.request.GET.get("start_date", "")
        end_date = self.request.GET.get("end_date", "")

        if start_date:
            queryset = queryset.filter(payment_date__gte=start_date)

        if end_date:
            queryset = queryset.filter(payment_date__lte=end_date)

        # Apply payment method filter
        payment_method = self.request.GET.get("payment_method", "")
        if payment_method:
            queryset = queryset.filter(payment_method=payment_method)

        # Apply status filter
        status = self.request.GET.get("status", "")
        if status:
            queryset = queryset.filter(status=status)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["payment_method_choices"] = dict(Payment.PAYMENT_METHOD_CHOICES)
        context["status_choices"] = dict(Payment.STATUS_CHOICES)

        # Get selected filters
        context["selected_payment_method"] = self.request.GET.get("payment_method", "")
        context["selected_status"] = self.request.GET.get("status", "")
        context["start_date"] = self.request.GET.get("start_date", "")
        context["end_date"] = self.request.GET.get("end_date", "")
        context["search_query"] = self.request.GET.get("search", "")

        return context


class PaymentDetailView(FinanceAccessMixin, DetailView):
    model = Payment
    context_object_name = "payment"
    template_name = "finance/payment_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["invoice"] = self.object.invoice
        context["student"] = self.object.invoice.student
        return context


class PaymentCreateView(FinanceAccessMixin, CreateView):
    model = Payment
    form_class = PaymentForm
    template_name = "finance/payment_form.html"
    success_url = reverse_lazy("finance:payment-list")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, "Payment recorded successfully.")
        return super().form_valid(form)


class PaymentCreateForInvoiceView(FinanceAccessMixin, CreateView):
    model = Payment
    form_class = PaymentForm
    template_name = "finance/payment_form.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        kwargs["invoice_id"] = self.kwargs.get("invoice_id")
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        invoice_id = self.kwargs.get("invoice_id")
        context["invoice"] = get_object_or_404(Invoice, id=invoice_id)
        return context

    def get_success_url(self):
        return reverse_lazy(
            "finance:invoice-detail", kwargs={"pk": self.kwargs.get("invoice_id")}
        )

    def form_valid(self, form):
        messages.success(self.request, "Payment recorded successfully.")
        return super().form_valid(form)


class PaymentReceiptView(FinanceAccessMixin, DetailView):
    model = Payment
    template_name = "finance/payment_receipt.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["invoice"] = self.object.invoice
        context["student"] = self.object.invoice.student
        context["school_info"] = {
            "name": "School Management System",  # You would get this from settings
            "address": "123 Education St, Knowledge City",
            "phone": "+1 (555) 123-4567",
            "email": "info@school.example.com",
        }
        return context


# Expense Views
class ExpenseListView(FinanceAccessMixin, ListView):
    model = Expense
    context_object_name = "expenses"
    template_name = "finance/expense_list.html"
    paginate_by = 20

    def get_queryset(self):
        queryset = super().get_queryset().select_related("approved_by")

        # Apply search filter
        search_query = self.request.GET.get("search", "")
        if search_query:
            queryset = queryset.filter(
                Q(description__icontains=search_query)
                | Q(paid_to__icontains=search_query)
            )

        # Apply date range filter
        start_date = self.request.GET.get("start_date", "")
        end_date = self.request.GET.get("end_date", "")

        if start_date:
            queryset = queryset.filter(expense_date__gte=start_date)

        if end_date:
            queryset = queryset.filter(expense_date__lte=end_date)

        # Apply category filter
        category = self.request.GET.get("category", "")
        if category:
            queryset = queryset.filter(expense_category=category)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["category_choices"] = dict(Expense.EXPENSE_CATEGORY_CHOICES)

        # Get selected filters
        context["selected_category"] = self.request.GET.get("category", "")
        context["start_date"] = self.request.GET.get("start_date", "")
        context["end_date"] = self.request.GET.get("end_date", "")
        context["search_query"] = self.request.GET.get("search", "")

        return context


class ExpenseDetailView(FinanceAccessMixin, DetailView):
    model = Expense
    context_object_name = "expense"
    template_name = "finance/expense_detail.html"


class ExpenseCreateView(FinanceAccessMixin, CreateView):
    model = Expense
    form_class = ExpenseForm
    template_name = "finance/expense_form.html"
    success_url = reverse_lazy("finance:expense-list")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, "Expense recorded successfully.")
        return super().form_valid(form)


class ExpenseUpdateView(FinanceAccessMixin, UpdateView):
    model = Expense
    form_class = ExpenseForm
    template_name = "finance/expense_form.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def get_success_url(self):
        return reverse_lazy("finance:expense-detail", kwargs={"pk": self.object.pk})

    def form_valid(self, form):
        messages.success(self.request, "Expense updated successfully.")
        return super().form_valid(form)


class ExpenseDeleteView(FinanceAccessMixin, DeleteView):
    model = Expense
    template_name = "finance/expense_confirm_delete.html"
    success_url = reverse_lazy("finance:expense-list")

    def delete(self, request, *args, **kwargs):
        messages.success(request, "Expense deleted successfully.")
        return super().delete(request, *args, **kwargs)


# Report Views
class FinancialSummaryView(FinanceAccessMixin, TemplateView):
    template_name = "finance/financial_summary.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get date range
        start_date = self.request.GET.get("start_date", "")
        end_date = self.request.GET.get("end_date", "")

        # Get summary data
        summary = FinanceService.get_financial_summary(
            start_date=start_date or None, end_date=end_date or None
        )

        context.update(summary)

        # For CSV export
        if "export" in self.request.GET:
            return self.export_csv(summary)

        return context

    def export_csv(self, summary):
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="financial_summary.csv"'

        writer = csv.writer(response)
        writer.writerow(["Financial Summary Report"])
        writer.writerow(
            [
                f'Period: {summary["period"]["start_date"]} to {summary["period"]["end_date"]}'
            ]
        )
        writer.writerow([])

        writer.writerow(["Summary"])
        writer.writerow(["Total Income", summary["summary"]["total_income"]])
        writer.writerow(["Total Expenses", summary["summary"]["total_expenses"]])
        writer.writerow(["Net Profit/Loss", summary["summary"]["net_profit"]])
        writer.writerow(["Total Outstanding", summary["summary"]["total_outstanding"]])
        writer.writerow([])

        writer.writerow(["Income Breakdown"])
        writer.writerow(["Category", "Amount"])
        for item in summary["income_breakdown"]:
            writer.writerow([item["category"], item["total"]])
        writer.writerow([])

        writer.writerow(["Expense Breakdown"])
        writer.writerow(["Category", "Amount"])
        for item in summary["expense_breakdown"]:
            writer.writerow([item["expense_category"], item["total"]])

        return response


class FeeCollectionReportView(FinanceAccessMixin, TemplateView):
    template_name = "finance/fee_collection_report.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get date range
        start_date = self.request.GET.get("start_date", "")
        end_date = self.request.GET.get("end_date", "")

        # Default to current month if not provided
        if not start_date:
            today = timezone.now().date()
            start_date = today.replace(day=1)
        else:
            start_date = timezone.datetime.strptime(start_date, "%Y-%m-%d").date()

        if not end_date:
            import calendar

            today = timezone.now().date()
            _, last_day = calendar.monthrange(today.year, today.month)
            end_date = today.replace(day=last_day)
        else:
            end_date = timezone.datetime.strptime(end_date, "%Y-%m-%d").date()

        # Get selected filters
        fee_category = self.request.GET.get("fee_category", "")
        grade = self.request.GET.get("grade", "")

        # Build query
        payments = Payment.objects.filter(
            payment_date__gte=start_date, payment_date__lte=end_date, status="completed"
        ).select_related(
            "invoice__student__user",
            "invoice__student__current_class__grade",
            "received_by",
        )

        if fee_category:
            payments = payments.filter(
                invoice__items__fee_structure__fee_category_id=fee_category
            )

        if grade:
            payments = payments.filter(invoice__student__current_class__grade_id=grade)

        # Group by date
        payments_by_date = (
            payments.annotate(payment_month=TruncMonth("payment_date"))
            .values("payment_month")
            .annotate(total=Sum("amount"), count=Count("id"))
            .order_by("payment_month")
        )

        # Group by fee category
        payments_by_category = []
        if not fee_category:  # Only if not already filtered by category
            from django.db.models import Subquery, OuterRef

            # This is a simplification - in a real system, you'd need a more
            # sophisticated approach to attribute payments to specific fee categories
            categories = FeeCategory.objects.all()
            for category in categories:
                category_payments = payments.filter(
                    invoice__items__fee_structure__fee_category=category
                )
                if category_payments.exists():
                    payments_by_category.append(
                        {
                            "category": category.name,
                            "total": category_payments.aggregate(Sum("amount"))[
                                "amount__sum"
                            ],
                        }
                    )

        context.update(
            {
                "payments": payments,
                "total_collected": payments.aggregate(Sum("amount"))["amount__sum"]
                or 0,
                "payment_count": payments.count(),
                "payments_by_date": payments_by_date,
                "payments_by_category": payments_by_category,
                "start_date": start_date,
                "end_date": end_date,
                "selected_fee_category": fee_category,
                "selected_grade": grade,
                "fee_categories": FeeCategory.objects.all(),
                "grades": Grade.objects.all(),
            }
        )

        return context


class OutstandingFeesReportView(FinanceAccessMixin, ListView):
    model = Invoice
    template_name = "finance/outstanding_fees_report.html"
    context_object_name = "invoices"
    paginate_by = 50

    def get_queryset(self):
        queryset = Invoice.objects.filter(
            status__in=["unpaid", "partially_paid", "overdue"]
        ).select_related(
            "student__user", "student__current_class__grade", "academic_year"
        )

        # Apply grade filter
        grade = self.request.GET.get("grade", "")
        if grade:
            queryset = queryset.filter(student__current_class__grade_id=grade)

        # Apply class filter
        class_id = self.request.GET.get("class", "")
        if class_id:
            queryset = queryset.filter(student__current_class_id=class_id)

        # Calculate due amount for each invoice
        for invoice in queryset:
            invoice.due_amount = invoice.get_due_amount()
            invoice.days_overdue = (
                (timezone.now().date() - invoice.due_date).days
                if timezone.now().date() > invoice.due_date
                else 0
            )

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from src.courses.models import Grade, Class

        context["grades"] = Grade.objects.all()
        context["classes"] = Class.objects.select_related("grade", "section").all()

        # Get selected filters
        context["selected_grade"] = self.request.GET.get("grade", "")
        context["selected_class"] = self.request.GET.get("class", "")

        # Calculate totals
        invoices = context["invoices"]
        context["total_outstanding"] = sum(
            invoice.get_due_amount() for invoice in invoices
        )
        context["total_invoice_count"] = len(invoices)

        # Overdue statistics
        context["overdue_30_days"] = sum(
            1 for invoice in invoices if invoice.days_overdue > 30
        )
        context["overdue_60_days"] = sum(
            1 for invoice in invoices if invoice.days_overdue > 60
        )
        context["overdue_90_days"] = sum(
            1 for invoice in invoices if invoice.days_overdue > 90
        )

        return context


class ExpenseReportView(FinanceAccessMixin, TemplateView):
    template_name = "finance/expense_report.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get date range
        start_date = self.request.GET.get("start_date", "")
        end_date = self.request.GET.get("end_date", "")

        # Default to current month if not provided
        if not start_date:
            today = timezone.now().date()
            start_date = today.replace(day=1)
        else:
            start_date = timezone.datetime.strptime(start_date, "%Y-%m-%d").date()

        if not end_date:
            import calendar

            today = timezone.now().date()
            _, last_day = calendar.monthrange(today.year, today.month)
            end_date = today.replace(day=last_day)
        else:
            end_date = timezone.datetime.strptime(end_date, "%Y-%m-%d").date()

        # Get selected filters
        category = self.request.GET.get("category", "")

        # Build query
        expenses = Expense.objects.filter(
            expense_date__gte=start_date, expense_date__lte=end_date
        ).select_related("approved_by")

        if category:
            expenses = expenses.filter(expense_category=category)

        # Group by category
        expenses_by_category = (
            expenses.values("expense_category")
            .annotate(total=Sum("amount"), count=Count("id"))
            .order_by("-total")
        )

        # Group by month
        expenses_by_month = (
            expenses.annotate(expense_month=TruncMonth("expense_date"))
            .values("expense_month")
            .annotate(total=Sum("amount"), count=Count("id"))
            .order_by("expense_month")
        )

        context.update(
            {
                "expenses": expenses,
                "total_expenses": expenses.aggregate(Sum("amount"))["amount__sum"] or 0,
                "expense_count": expenses.count(),
                "expenses_by_category": expenses_by_category,
                "expenses_by_month": expenses_by_month,
                "start_date": start_date,
                "end_date": end_date,
                "selected_category": category,
                "category_choices": dict(Expense.EXPENSE_CATEGORY_CHOICES),
            }
        )

        return context


class FinanceDashboardView(FinanceAccessMixin, TemplateView):
    template_name = "finance/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get date range for overview
        today = timezone.now().date()
        start_of_month = today.replace(day=1)
        start_of_year = today.replace(month=1, day=1)

        # Recent activity
        recent_invoices = Invoice.objects.order_by("-created_at")[:5]
        recent_payments = Payment.objects.order_by("-created_at")[:5]
        recent_expenses = Expense.objects.order_by("-created_at")[:5]

        # Monthly overview
        monthly_payments = Payment.objects.filter(
            payment_date__gte=start_of_month, status="completed"
        )
        monthly_income = monthly_payments.aggregate(Sum("amount"))["amount__sum"] or 0

        monthly_expenses = Expense.objects.filter(expense_date__gte=start_of_month)
        monthly_expense_total = (
            monthly_expenses.aggregate(Sum("amount"))["amount__sum"] or 0
        )

        # Outstanding fees
        outstanding_invoices = Invoice.objects.filter(
            status__in=["unpaid", "partially_paid", "overdue"]
        )
        total_outstanding = sum(
            invoice.get_due_amount() for invoice in outstanding_invoices
        )
        overdue_invoices = Invoice.objects.filter(status="overdue")
        total_overdue = sum(invoice.get_due_amount() for invoice in overdue_invoices)

        # Monthly breakdown
        last_6_months = []
        for i in range(5, -1, -1):
            month_date = today.replace(day=1) - timedelta(days=i * 30)
            month_name = month_date.strftime("%B %Y")

            month_payments = Payment.objects.filter(
                payment_date__year=month_date.year,
                payment_date__month=month_date.month,
                status="completed",
            )
            month_income = month_payments.aggregate(Sum("amount"))["amount__sum"] or 0

            month_expenses = Expense.objects.filter(
                expense_date__year=month_date.year, expense_date__month=month_date.month
            )
            month_expense_total = (
                month_expenses.aggregate(Sum("amount"))["amount__sum"] or 0
            )

            last_6_months.append(
                {
                    "month": month_name,
                    "income": month_income,
                    "expenses": month_expense_total,
                    "profit": month_income - month_expense_total,
                }
            )

        context.update(
            {
                "recent_invoices": recent_invoices,
                "recent_payments": recent_payments,
                "recent_expenses": recent_expenses,
                "monthly_income": monthly_income,
                "monthly_expense_total": monthly_expense_total,
                "monthly_profit": monthly_income - monthly_expense_total,
                "total_outstanding": total_outstanding,
                "total_overdue": total_overdue,
                "outstanding_count": outstanding_invoices.count(),
                "overdue_count": overdue_invoices.count(),
                "last_6_months": last_6_months,
            }
        )

        return context


class StudentFeePortalView(LoginRequiredMixin, TemplateView):
    template_name = "finance/student_fee_portal.html"

    def dispatch(self, request, *args, **kwargs):
        # Ensure user is either a student or parent
        if not request.user.is_authenticated:
            return self.handle_no_permission()

        is_student = hasattr(request.user, "student_profile")
        is_parent = hasattr(request.user, "parent_profile")

        if not (is_student or is_parent):
            messages.error(
                request, "Only students and parents can access the fee portal."
            )
            return redirect("core:dashboard")

        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get student info
        if hasattr(self.request.user, "student_profile"):
            # User is a student
            students = [self.request.user.student_profile]
        else:
            # User is a parent
            parent = self.request.user.parent_profile
            students = [
                relation.student
                for relation in parent.parent_student_relations.select_related(
                    "student"
                )
            ]

        student_data = []
        for student in students:
            # Get invoices for this student
            invoices = Invoice.objects.filter(student=student).order_by("-issue_date")

            # Get outstanding amount
            outstanding_amount = sum(
                invoice.get_due_amount()
                for invoice in invoices
                if invoice.status in ["unpaid", "partially_paid", "overdue"]
            )

            # Get payment history
            payments = Payment.objects.filter(invoice__student=student).order_by(
                "-payment_date"
            )

            # Get scholarships
            scholarships = StudentScholarship.objects.filter(
                student=student, status="approved"
            ).select_related("scholarship")

            student_data.append(
                {
                    "student": student,
                    "invoices": invoices,
                    "outstanding_amount": outstanding_amount,
                    "payments": payments,
                    "scholarships": scholarships,
                }
            )

        context["student_data"] = student_data

        return context
