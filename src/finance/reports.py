"""
Finance report generation utilities.
"""

import io
import csv
from datetime import datetime, timedelta
from decimal import Decimal
from django.db.models import Sum, Count, Q, Avg
from django.utils import timezone
from django.http import HttpResponse
from typing import Dict, List, Optional, Union

from .models import (
    Invoice,
    Payment,
    FeeStructure,
    SpecialFee,
    Scholarship,
    StudentScholarship,
    FeeWaiver,
    FinancialAnalytics,
)
from .services.analytics_service import FinancialAnalyticsService
from academics.models import AcademicYear, Term, Section, Grade
from students.models import Student


class FinanceReportGenerator:
    """Generate various financial reports."""

    @staticmethod
    def collection_summary_report(
        academic_year, term=None, section=None, date_from=None, date_to=None
    ) -> Dict:
        """Generate collection summary report."""

        # Base query
        invoices = Invoice.objects.filter(academic_year=academic_year)
        payments = Payment.objects.filter(
            invoice__academic_year=academic_year, status="completed"
        )

        # Apply filters
        if term:
            invoices = invoices.filter(term=term)
            payments = payments.filter(invoice__term=term)

        if section:
            invoices = invoices.filter(student__current_class__grade__section=section)
            payments = payments.filter(
                invoice__student__current_class__grade__section=section
            )

        if date_from:
            payments = payments.filter(payment_date__date__gte=date_from)

        if date_to:
            payments = payments.filter(payment_date__date__lte=date_to)

        # Calculate metrics
        total_invoices = invoices.count()
        total_due = invoices.aggregate(total=Sum("net_amount"))["total"] or Decimal(
            "0.00"
        )
        total_collected = payments.aggregate(total=Sum("amount"))["total"] or Decimal(
            "0.00"
        )

        # Status breakdown
        status_breakdown = (
            invoices.values("status")
            .annotate(count=Count("id"), amount=Sum("net_amount"))
            .order_by("status")
        )

        # Payment method breakdown
        method_breakdown = (
            payments.values("payment_method")
            .annotate(count=Count("id"), amount=Sum("amount"))
            .order_by("-amount")
        )

        # Collection rate
        collection_rate = (total_collected / total_due * 100) if total_due > 0 else 0

        return {
            "report_type": "Collection Summary",
            "period": {
                "academic_year": str(academic_year),
                "term": str(term) if term else "All Terms",
                "section": str(section) if section else "All Sections",
                "date_from": date_from,
                "date_to": date_to,
            },
            "summary": {
                "total_invoices": total_invoices,
                "total_amount_due": total_due,
                "total_collected": total_collected,
                "outstanding_amount": total_due - total_collected,
                "collection_rate": round(collection_rate, 2),
            },
            "status_breakdown": list(status_breakdown),
            "payment_methods": list(method_breakdown),
            "generated_at": timezone.now(),
        }

    @staticmethod
    def defaulter_report(
        academic_year, term=None, days_overdue=30, amount_threshold=None
    ) -> Dict:
        """Generate defaulter report."""

        cutoff_date = timezone.now().date() - timedelta(days=days_overdue)

        # Get overdue invoices
        overdue_invoices = Invoice.objects.filter(
            academic_year=academic_year,
            due_date__lt=cutoff_date,
            status__in=["unpaid", "partially_paid"],
        ).select_related("student", "student__user", "student__current_class")

        if term:
            overdue_invoices = overdue_invoices.filter(term=term)

        # Calculate defaulter details
        defaulters = []
        total_overdue_amount = Decimal("0.00")

        for invoice in overdue_invoices:
            outstanding = invoice.outstanding_amount

            # Apply amount threshold filter
            if amount_threshold and outstanding < amount_threshold:
                continue

            days_overdue_count = (timezone.now().date() - invoice.due_date).days

            # Get student's contact information
            student = invoice.student
            parents = student.studentparentrelation_set.filter(
                is_primary_contact=True
            ).first()

            defaulter_info = {
                "student_id": student.id,
                "student_name": student.user.get_full_name(),
                "admission_number": student.admission_number,
                "class": str(student.current_class),
                "invoice_number": invoice.invoice_number,
                "net_amount": invoice.net_amount,
                "paid_amount": invoice.paid_amount,
                "outstanding_amount": outstanding,
                "due_date": invoice.due_date,
                "days_overdue": days_overdue_count,
                "contact_email": student.user.email,
                "contact_phone": student.user.phone_number,
                "parent_contact": (
                    {
                        "name": parents.parent.user.get_full_name() if parents else "",
                        "email": parents.parent.user.email if parents else "",
                        "phone": parents.parent.user.phone_number if parents else "",
                    }
                    if parents
                    else None
                ),
            }

            defaulters.append(defaulter_info)
            total_overdue_amount += outstanding

        # Sort by days overdue (descending)
        defaulters.sort(key=lambda x: x["days_overdue"], reverse=True)

        # Risk categorization
        high_risk = [d for d in defaulters if d["days_overdue"] > 60]
        medium_risk = [d for d in defaulters if 30 <= d["days_overdue"] <= 60]
        low_risk = [d for d in defaulters if d["days_overdue"] < 30]

        return {
            "report_type": "Defaulter Report",
            "period": {
                "academic_year": str(academic_year),
                "term": str(term) if term else "All Terms",
                "days_overdue_threshold": days_overdue,
                "amount_threshold": amount_threshold,
            },
            "summary": {
                "total_defaulters": len(defaulters),
                "total_overdue_amount": total_overdue_amount,
                "high_risk_count": len(high_risk),
                "medium_risk_count": len(medium_risk),
                "low_risk_count": len(low_risk),
            },
            "risk_analysis": {
                "high_risk": high_risk[:20],  # Top 20
                "medium_risk": medium_risk[:20],
                "low_risk": low_risk[:20],
            },
            "all_defaulters": defaulters,
            "generated_at": timezone.now(),
        }

    @staticmethod
    def scholarship_report(academic_year, term=None) -> Dict:
        """Generate scholarship utilization report."""

        # Get scholarships for the academic year
        scholarships = Scholarship.objects.filter(
            academic_year=academic_year, is_active=True
        ).prefetch_related("applicable_categories")

        # Get scholarship assignments
        assignments = StudentScholarship.objects.filter(
            scholarship__academic_year=academic_year, status="approved"
        ).select_related("scholarship", "student")

        if term:
            # Filter by term if scholarship applies to specific terms
            assignments = assignments.filter(
                Q(scholarship__applicable_terms__isnull=True)
                | Q(scholarship__applicable_terms__contains=[term.id])
            )

        # Calculate scholarship details
        scholarship_details = []
        total_discount_amount = Decimal("0.00")
        total_beneficiaries = 0

        for scholarship in scholarships:
            # Get assignments for this scholarship
            scholarship_assignments = assignments.filter(scholarship=scholarship)
            beneficiary_count = scholarship_assignments.count()

            # Calculate total discount
            discount_amount = Decimal("0.00")
            for assignment in scholarship_assignments:
                try:
                    # Get student's fees
                    from .services.fee_service import FeeService

                    fee_breakdown = FeeService.calculate_student_fees(
                        assignment.student, academic_year, term
                    )

                    # Calculate discount for this student
                    if scholarship.discount_type == "percentage":
                        student_discount = fee_breakdown["total_amount"] * (
                            scholarship.discount_value / 100
                        )
                    else:
                        student_discount = scholarship.discount_value

                    discount_amount += student_discount
                except Exception:
                    continue

            scholarship_info = {
                "name": scholarship.name,
                "criteria": scholarship.get_criteria_display(),
                "discount_type": scholarship.get_discount_type_display(),
                "discount_value": scholarship.discount_value,
                "max_recipients": scholarship.max_recipients,
                "current_beneficiaries": beneficiary_count,
                "total_discount_amount": discount_amount,
                "average_discount_per_student": (
                    discount_amount / beneficiary_count
                    if beneficiary_count > 0
                    else Decimal("0.00")
                ),
                "utilization_rate": (
                    beneficiary_count / scholarship.max_recipients * 100
                    if scholarship.max_recipients
                    else 100
                ),
                "beneficiaries": [
                    {
                        "student_name": assignment.student.user.get_full_name(),
                        "admission_number": assignment.student.admission_number,
                        "class": str(assignment.student.current_class),
                        "approved_date": assignment.approval_date,
                    }
                    for assignment in scholarship_assignments[
                        :10
                    ]  # Limit to 10 for summary
                ],
            }

            scholarship_details.append(scholarship_info)
            total_discount_amount += discount_amount
            total_beneficiaries += beneficiary_count

        # Criteria-wise breakdown
        criteria_breakdown = (
            assignments.values("scholarship__criteria")
            .annotate(
                beneficiary_count=Count("id"),
                scholarship_count=Count("scholarship", distinct=True),
            )
            .order_by("-beneficiary_count")
        )

        return {
            "report_type": "Scholarship Report",
            "period": {
                "academic_year": str(academic_year),
                "term": str(term) if term else "All Terms",
            },
            "summary": {
                "total_scholarships": scholarships.count(),
                "total_beneficiaries": total_beneficiaries,
                "total_discount_amount": total_discount_amount,
                "average_discount_per_student": (
                    total_discount_amount / total_beneficiaries
                    if total_beneficiaries > 0
                    else Decimal("0.00")
                ),
            },
            "scholarship_details": scholarship_details,
            "criteria_breakdown": list(criteria_breakdown),
            "generated_at": timezone.now(),
        }

    @staticmethod
    def fee_structure_report(academic_year, term=None) -> Dict:
        """Generate fee structure analysis report."""

        # Get fee structures
        fee_structures = FeeStructure.objects.filter(
            academic_year=academic_year, is_active=True
        ).select_related("fee_category", "section", "grade")

        if term:
            fee_structures = fee_structures.filter(term=term)

        # Organize by hierarchy
        section_analysis = {}
        total_fees = Decimal("0.00")

        for structure in fee_structures:
            level = structure.section or structure.grade
            level_name = str(level)

            if level_name not in section_analysis:
                section_analysis[level_name] = {
                    "level": level_name,
                    "level_type": "section" if structure.section else "grade",
                    "fee_categories": {},
                    "total_fees": Decimal("0.00"),
                    "fee_count": 0,
                }

            category_name = structure.fee_category.name
            section_analysis[level_name]["fee_categories"][category_name] = {
                "amount": structure.amount,
                "due_date": structure.due_date,
                "late_fee_percentage": structure.late_fee_percentage,
                "grace_period_days": structure.grace_period_days,
            }

            section_analysis[level_name]["total_fees"] += structure.amount
            section_analysis[level_name]["fee_count"] += 1
            total_fees += structure.amount

        # Category-wise analysis
        category_analysis = (
            fee_structures.values("fee_category__name")
            .annotate(
                total_amount=Sum("amount"),
                structure_count=Count("id"),
                avg_amount=Avg("amount"),
                min_amount=models.Min("amount"),
                max_amount=models.Max("amount"),
            )
            .order_by("-total_amount")
        )

        # Special fees analysis
        special_fees = SpecialFee.objects.filter(
            term__academic_year=academic_year, is_active=True
        )

        if term:
            special_fees = special_fees.filter(term=term)

        special_fee_analysis = (
            special_fees.values("fee_type", "fee_category__name")
            .annotate(
                count=Count("id"),
                total_amount=Sum("amount"),
                avg_amount=Avg("amount"),
            )
            .order_by("fee_type", "-total_amount")
        )

        return {
            "report_type": "Fee Structure Report",
            "period": {
                "academic_year": str(academic_year),
                "term": str(term) if term else "All Terms",
            },
            "summary": {
                "total_fee_structures": fee_structures.count(),
                "total_fees_defined": total_fees,
                "special_fees_count": special_fees.count(),
                "categories_used": category_analysis.count(),
            },
            "level_analysis": list(section_analysis.values()),
            "category_analysis": list(category_analysis),
            "special_fee_analysis": list(special_fee_analysis),
            "generated_at": timezone.now(),
        }

    @staticmethod
    def payment_analysis_report(
        academic_year, term=None, date_from=None, date_to=None
    ) -> Dict:
        """Generate payment analysis report."""

        # Base query
        payments = Payment.objects.filter(
            invoice__academic_year=academic_year, status="completed"
        )

        # Apply filters
        if term:
            payments = payments.filter(invoice__term=term)

        if date_from:
            payments = payments.filter(payment_date__date__gte=date_from)

        if date_to:
            payments = payments.filter(payment_date__date__lte=date_to)

        # Payment method analysis
        method_analysis = (
            payments.values("payment_method")
            .annotate(
                count=Count("id"),
                total_amount=Sum("amount"),
                avg_amount=Avg("amount"),
                min_amount=models.Min("amount"),
                max_amount=models.Max("amount"),
            )
            .order_by("-total_amount")
        )

        # Daily trends
        daily_trends = (
            payments.extra(select={"day": "date(payment_date)"})
            .values("day")
            .annotate(
                daily_count=Count("id"),
                daily_amount=Sum("amount"),
            )
            .order_by("day")
        )

        # Peak analysis
        peak_hours = (
            payments.extra(select={"hour": "extract(hour from payment_date)"})
            .values("hour")
            .annotate(
                hourly_count=Count("id"),
                hourly_amount=Sum("amount"),
            )
            .order_by("-hourly_count")
        )

        peak_days = (
            payments.extra(select={"day_of_week": "extract(dow from payment_date)"})
            .values("day_of_week")
            .annotate(
                daily_count=Count("id"),
                daily_amount=Sum("amount"),
            )
            .order_by("-daily_count")
        )

        # Amount distribution
        amount_ranges = {
            "0-100": payments.filter(amount__lt=100).count(),
            "100-500": payments.filter(amount__range=(100, 500)).count(),
            "500-1000": payments.filter(amount__range=(500, 1000)).count(),
            "1000-5000": payments.filter(amount__range=(1000, 5000)).count(),
            "5000+": payments.filter(amount__gt=5000).count(),
        }

        return {
            "report_type": "Payment Analysis",
            "period": {
                "academic_year": str(academic_year),
                "term": str(term) if term else "All Terms",
                "date_from": date_from,
                "date_to": date_to,
            },
            "summary": {
                "total_payments": payments.count(),
                "total_amount": payments.aggregate(Sum("amount"))["amount__sum"]
                or Decimal("0.00"),
                "average_payment": payments.aggregate(Avg("amount"))["amount__avg"]
                or Decimal("0.00"),
                "largest_payment": payments.aggregate(models.Max("amount"))[
                    "amount__max"
                ]
                or Decimal("0.00"),
            },
            "method_analysis": list(method_analysis),
            "daily_trends": list(daily_trends),
            "peak_analysis": {
                "peak_hours": list(peak_hours[:5]),  # Top 5 hours
                "peak_days": list(peak_days),
            },
            "amount_distribution": amount_ranges,
            "generated_at": timezone.now(),
        }


class ReportExporter:
    """Export reports in various formats."""

    @staticmethod
    def export_to_csv(report_data: Dict, filename: str = None) -> HttpResponse:
        """Export report data to CSV format."""

        if not filename:
            timestamp = timezone.now().strftime("%Y%m%d_%H%M%S")
            filename = f"financial_report_{timestamp}.csv"

        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'

        writer = csv.writer(response)

        # Write header information
        writer.writerow(["Financial Report"])
        writer.writerow(["Report Type:", report_data.get("report_type", "Unknown")])
        writer.writerow(
            ["Generated At:", report_data.get("generated_at", timezone.now())]
        )
        writer.writerow([])  # Empty row

        # Write period information
        if "period" in report_data:
            writer.writerow(["Period Information:"])
            for key, value in report_data["period"].items():
                writer.writerow([key.replace("_", " ").title() + ":", value])
            writer.writerow([])  # Empty row

        # Write summary
        if "summary" in report_data:
            writer.writerow(["Summary:"])
            for key, value in report_data["summary"].items():
                writer.writerow([key.replace("_", " ").title() + ":", value])
            writer.writerow([])  # Empty row

        # Write detailed data based on report type
        report_type = report_data.get("report_type", "")

        if "Collection Summary" in report_type:
            ReportExporter._write_collection_summary_csv(writer, report_data)
        elif "Defaulter Report" in report_type:
            ReportExporter._write_defaulter_report_csv(writer, report_data)
        elif "Scholarship Report" in report_type:
            ReportExporter._write_scholarship_report_csv(writer, report_data)
        elif "Payment Analysis" in report_type:
            ReportExporter._write_payment_analysis_csv(writer, report_data)

        return response

    @staticmethod
    def _write_collection_summary_csv(writer, report_data):
        """Write collection summary specific data to CSV."""

        # Status breakdown
        if "status_breakdown" in report_data:
            writer.writerow(["Invoice Status Breakdown:"])
            writer.writerow(["Status", "Count", "Amount"])
            for item in report_data["status_breakdown"]:
                writer.writerow([item["status"], item["count"], item["amount"]])
            writer.writerow([])

        # Payment methods
        if "payment_methods" in report_data:
            writer.writerow(["Payment Methods:"])
            writer.writerow(["Method", "Count", "Amount"])
            for item in report_data["payment_methods"]:
                writer.writerow([item["payment_method"], item["count"], item["amount"]])

    @staticmethod
    def _write_defaulter_report_csv(writer, report_data):
        """Write defaulter report specific data to CSV."""

        writer.writerow(["Defaulter Details:"])
        writer.writerow(
            [
                "Student Name",
                "Admission Number",
                "Class",
                "Invoice Number",
                "Net Amount",
                "Outstanding Amount",
                "Due Date",
                "Days Overdue",
                "Contact Email",
                "Contact Phone",
            ]
        )

        for defaulter in report_data.get("all_defaulters", []):
            writer.writerow(
                [
                    defaulter["student_name"],
                    defaulter["admission_number"],
                    defaulter["class"],
                    defaulter["invoice_number"],
                    defaulter["net_amount"],
                    defaulter["outstanding_amount"],
                    defaulter["due_date"],
                    defaulter["days_overdue"],
                    defaulter["contact_email"],
                    defaulter["contact_phone"],
                ]
            )

    @staticmethod
    def _write_scholarship_report_csv(writer, report_data):
        """Write scholarship report specific data to CSV."""

        writer.writerow(["Scholarship Details:"])
        writer.writerow(
            [
                "Scholarship Name",
                "Criteria",
                "Discount Type",
                "Discount Value",
                "Current Beneficiaries",
                "Total Discount Amount",
                "Utilization Rate",
            ]
        )

        for scholarship in report_data.get("scholarship_details", []):
            writer.writerow(
                [
                    scholarship["name"],
                    scholarship["criteria"],
                    scholarship["discount_type"],
                    scholarship["discount_value"],
                    scholarship["current_beneficiaries"],
                    scholarship["total_discount_amount"],
                    f"{scholarship['utilization_rate']:.1f}%",
                ]
            )

    @staticmethod
    def _write_payment_analysis_csv(writer, report_data):
        """Write payment analysis specific data to CSV."""

        # Method analysis
        if "method_analysis" in report_data:
            writer.writerow(["Payment Method Analysis:"])
            writer.writerow(["Method", "Count", "Total Amount", "Average Amount"])
            for item in report_data["method_analysis"]:
                writer.writerow(
                    [
                        item["payment_method"],
                        item["count"],
                        item["total_amount"],
                        item["avg_amount"],
                    ]
                )
            writer.writerow([])

        # Daily trends
        if "daily_trends" in report_data:
            writer.writerow(["Daily Trends:"])
            writer.writerow(["Date", "Payment Count", "Total Amount"])
            for item in report_data["daily_trends"]:
                writer.writerow(
                    [
                        item["day"],
                        item["daily_count"],
                        item["daily_amount"],
                    ]
                )

    @staticmethod
    def export_to_excel(report_data: Dict, filename: str = None) -> HttpResponse:
        """Export report data to Excel format."""

        try:
            import openpyxl
            from openpyxl.styles import Font, PatternFill
        except ImportError:
            # Fallback to CSV if openpyxl is not available
            return ReportExporter.export_to_csv(report_data, filename)

        if not filename:
            timestamp = timezone.now().strftime("%Y%m%d_%H%M%S")
            filename = f"financial_report_{timestamp}.xlsx"

        # Create workbook and worksheet
        workbook = openpyxl.Workbook()
        worksheet = workbook.active
        worksheet.title = "Financial Report"

        # Styling
        header_font = Font(bold=True, size=14)
        subheader_font = Font(bold=True, size=12)

        row = 1

        # Write header information
        worksheet[f"A{row}"] = report_data.get("report_type", "Financial Report")
        worksheet[f"A{row}"].font = header_font
        row += 2

        worksheet[f"A{row}"] = (
            f"Generated: {report_data.get('generated_at', timezone.now())}"
        )
        row += 2

        # Write summary if available
        if "summary" in report_data:
            worksheet[f"A{row}"] = "Summary"
            worksheet[f"A{row}"].font = subheader_font
            row += 1

            for key, value in report_data["summary"].items():
                worksheet[f"A{row}"] = key.replace("_", " ").title()
                worksheet[f"B{row}"] = value
                row += 1
            row += 1

        # Save to response
        output = io.BytesIO()
        workbook.save(output)
        output.seek(0)

        response = HttpResponse(
            output.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = f'attachment; filename="{filename}"'

        return response


# Utility functions for quick report generation
def generate_monthly_collection_report(year: int, month: int) -> Dict:
    """Generate monthly collection report for a specific year and month."""

    date_from = datetime(year, month, 1).date()
    if month == 12:
        date_to = datetime(year + 1, 1, 1).date() - timedelta(days=1)
    else:
        date_to = datetime(year, month + 1, 1).date() - timedelta(days=1)

    try:
        academic_year = AcademicYear.objects.filter(
            start_date__lte=date_from, end_date__gte=date_to
        ).first()

        if not academic_year:
            academic_year = AcademicYear.objects.filter(is_current=True).first()

        return FinanceReportGenerator.collection_summary_report(
            academic_year=academic_year, date_from=date_from, date_to=date_to
        )
    except Exception as e:
        return {"error": str(e)}


def generate_term_financial_summary(academic_year_id: int, term_id: int) -> Dict:
    """Generate comprehensive financial summary for a term."""

    try:
        academic_year = AcademicYear.objects.get(id=academic_year_id)
        term = Term.objects.get(id=term_id)

        # Generate multiple reports
        collection_report = FinanceReportGenerator.collection_summary_report(
            academic_year, term
        )
        scholarship_report = FinanceReportGenerator.scholarship_report(
            academic_year, term
        )
        payment_analysis = FinanceReportGenerator.payment_analysis_report(
            academic_year, term
        )

        return {
            "term_summary": {
                "academic_year": str(academic_year),
                "term": str(term),
                "generated_at": timezone.now(),
            },
            "collection_summary": collection_report,
            "scholarship_analysis": scholarship_report,
            "payment_analysis": payment_analysis,
        }
    except Exception as e:
        return {"error": str(e)}
