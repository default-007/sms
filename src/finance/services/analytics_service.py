from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional

from django.db.models import Avg, Case, Count, F, Q, Sum, When
from django.utils import timezone

from ..models import (
    FeeStructure,
    FinancialAnalytics,
    FinancialSummary,
    Invoice,
    Payment,
    Scholarship,
    StudentScholarship,
)


class FinancialAnalyticsService:
    """Service for financial analytics and reporting."""

    @classmethod
    def calculate_collection_metrics(
        cls, academic_year, term=None, section=None, grade=None
    ) -> Dict:
        """Calculate comprehensive collection metrics."""

        # Base queryset
        invoices = Invoice.objects.filter(academic_year=academic_year)

        if term:
            invoices = invoices.filter(term=term)
        if section:
            invoices = invoices.filter(student__current_class__grade__section=section)
        elif grade:
            invoices = invoices.filter(student__current_class__grade=grade)

        # Basic metrics
        metrics = invoices.aggregate(
            total_invoices=Count("id"),
            total_amount_due=Sum("net_amount"),
            total_collected=Sum("paid_amount"),
            average_invoice_amount=Avg("net_amount"),
        )

        # Calculate derived metrics
        total_due = metrics["total_amount_due"] or Decimal("0.00")
        total_collected = metrics["total_collected"] or Decimal("0.00")
        outstanding = total_due - total_collected

        collection_rate = (total_collected / total_due * 100) if total_due > 0 else 0

        # Status breakdown
        status_breakdown = (
            invoices.values("status")
            .annotate(count=Count("id"), amount=Sum("net_amount"))
            .order_by("status")
        )

        # Overdue analysis
        overdue_invoices = invoices.filter(
            due_date__lt=timezone.now().date(), status__in=["unpaid", "partially_paid"]
        )

        overdue_metrics = overdue_invoices.aggregate(
            overdue_count=Count("id"),
            overdue_amount=Sum("net_amount") - Sum("paid_amount"),
        )

        return {
            "period": {
                "academic_year": str(academic_year),
                "term": str(term) if term else "All Terms",
                "level": str(grade or section or "All Levels"),
            },
            "collection_summary": {
                "total_invoices": metrics["total_invoices"] or 0,
                "total_amount_due": total_due,
                "total_collected": total_collected,
                "total_outstanding": outstanding,
                "collection_rate": round(collection_rate, 2),
                "average_invoice_amount": metrics["average_invoice_amount"]
                or Decimal("0.00"),
            },
            "status_breakdown": list(status_breakdown),
            "overdue_analysis": {
                "overdue_invoices": overdue_metrics["overdue_count"] or 0,
                "overdue_amount": overdue_metrics["overdue_amount"] or Decimal("0.00"),
                "overdue_rate": (
                    overdue_metrics["overdue_count"] / metrics["total_invoices"] * 100
                    if metrics["total_invoices"] > 0
                    else 0
                ),
            },
        }

    @classmethod
    def generate_payment_trends(cls, academic_year, days=30) -> Dict:
        """Generate payment trends over specified period."""

        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)

        # Daily payment trends
        daily_payments = (
            Payment.objects.filter(
                invoice__academic_year=academic_year,
                payment_date__date__range=[start_date, end_date],
                status="completed",
            )
            .extra(select={"day": "date(payment_date)"})
            .values("day")
            .annotate(daily_amount=Sum("amount"), daily_count=Count("id"))
            .order_by("day")
        )

        # Payment method analysis
        method_analysis = (
            Payment.objects.filter(
                invoice__academic_year=academic_year,
                payment_date__date__range=[start_date, end_date],
                status="completed",
            )
            .values("payment_method")
            .annotate(
                total_amount=Sum("amount"),
                transaction_count=Count("id"),
                avg_amount=Avg("amount"),
            )
            .order_by("-total_amount")
        )

        # Peak payment analysis
        peak_analysis = (
            Payment.objects.filter(
                invoice__academic_year=academic_year,
                payment_date__date__range=[start_date, end_date],
                status="completed",
            )
            .extra(
                select={
                    "hour": "extract(hour from payment_date)",
                    "day_of_week": "extract(dow from payment_date)",
                }
            )
            .values("hour", "day_of_week")
            .annotate(payment_count=Count("id"), total_amount=Sum("amount"))
        )

        return {
            "period": f"{start_date} to {end_date}",
            "daily_trends": list(daily_payments),
            "payment_methods": list(method_analysis),
            "peak_times": list(peak_analysis),
            "summary": {
                "total_days_analyzed": days,
                "days_with_payments": len(daily_payments),
                "average_daily_collection": (
                    sum(day["daily_amount"] for day in daily_payments)
                    / len(daily_payments)
                    if daily_payments
                    else Decimal("0.00")
                ),
            },
        }

    @classmethod
    def analyze_defaulters(cls, academic_year, term=None, days_overdue=30) -> Dict:
        """Analyze defaulter patterns and risk factors."""

        cutoff_date = timezone.now().date() - timedelta(days=days_overdue)

        # Base defaulter query
        defaulter_invoices = Invoice.objects.filter(
            academic_year=academic_year,
            due_date__lt=cutoff_date,
            status__in=["unpaid", "partially_paid"],
        ).select_related("student", "student__current_class__grade__section")

        if term:
            defaulter_invoices = defaulter_invoices.filter(term=term)

        # Risk analysis by section/grade
        risk_by_level = (
            defaulter_invoices.values(
                "student__current_class__grade__section__name",
                "student__current_class__grade__name",
            )
            .annotate(
                defaulter_count=Count("student", distinct=True),
                total_overdue=Sum("net_amount") - Sum("paid_amount"),
                avg_overdue_per_student=Avg("net_amount") - Avg("paid_amount"),
            )
            .order_by("-defaulter_count")
        )

        # Defaulter distribution by amount ranges
        amount_ranges = defaulter_invoices.aggregate(
            range_0_1k=Count(Case(When(net_amount__lt=1000, then=1))),
            range_1k_5k=Count(Case(When(net_amount__range=(1000, 5000), then=1))),
            range_5k_plus=Count(Case(When(net_amount__gt=5000, then=1))),
        )

        # Chronic defaulters (multiple overdue invoices)
        chronic_defaulters = (
            defaulter_invoices.values("student")
            .annotate(
                overdue_invoice_count=Count("id"),
                total_overdue_amount=Sum("net_amount") - Sum("paid_amount"),
            )
            .filter(overdue_invoice_count__gt=1)
            .order_by("-overdue_invoice_count")
        )

        return {
            "analysis_period": f"Overdue by {days_overdue}+ days",
            "total_defaulters": defaulter_invoices.values("student").distinct().count(),
            "total_overdue_amount": defaulter_invoices.aggregate(
                total=Sum("net_amount") - Sum("paid_amount")
            )["total"]
            or Decimal("0.00"),
            "risk_by_level": list(risk_by_level),
            "amount_distribution": amount_ranges,
            "chronic_defaulters": list(chronic_defaulters[:20]),  # Top 20
            "recommendations": cls._generate_defaulter_recommendations(
                defaulter_invoices
            ),
        }

    @classmethod
    def _generate_defaulter_recommendations(cls, defaulter_invoices) -> List[str]:
        """Generate recommendations based on defaulter analysis."""
        recommendations = []

        defaulter_count = defaulter_invoices.count()
        total_students = defaulter_invoices.values("student").distinct().count()

        if defaulter_count > 50:
            recommendations.append(
                "High number of overdue invoices - consider payment plan options"
            )

        if total_students > 20:
            recommendations.append(
                "Multiple defaulters identified - implement early warning system"
            )

        # Section-wise analysis for recommendations
        section_analysis = (
            defaulter_invoices.values("student__current_class__grade__section__name")
            .annotate(section_defaulters=Count("student", distinct=True))
            .order_by("-section_defaulters")
        )

        if section_analysis:
            top_section = section_analysis[0]
            if top_section["section_defaulters"] > 10:
                recommendations.append(
                    f"Focus collection efforts on {top_section['student__current_class__grade__section__name']} section"
                )

        return recommendations

    @classmethod
    def calculate_scholarship_impact(cls, academic_year, term=None) -> Dict:
        """Calculate overall impact of scholarships on revenue."""

        # Active scholarships
        scholarships = Scholarship.objects.filter(
            academic_year=academic_year, is_active=True
        )

        # Scholarship assignments
        assignments = StudentScholarship.objects.filter(
            scholarship__academic_year=academic_year, status="approved"
        ).select_related("scholarship", "student")

        total_discount = Decimal("0.00")
        beneficiary_count = assignments.count()

        # Calculate discount by type
        discount_by_type = {
            "percentage": Decimal("0.00"),
            "fixed_amount": Decimal("0.00"),
        }

        for assignment in assignments:
            scholarship = assignment.scholarship

            # Get student's fee breakdown
            try:
                from .fee_service import FeeService

                fee_breakdown = FeeService.calculate_student_fees(
                    assignment.student, academic_year, term
                )

                # Calculate discount for this student
                if scholarship.discount_type == "percentage":
                    discount = fee_breakdown["total_amount"] * (
                        scholarship.discount_value / 100
                    )
                    discount_by_type["percentage"] += discount
                else:
                    discount = scholarship.discount_value
                    discount_by_type["fixed_amount"] += discount

                total_discount += discount

            except Exception:
                continue

        # Scholarship distribution by criteria
        criteria_distribution = (
            assignments.values("scholarship__criteria")
            .annotate(
                count=Count("id"), total_discount=Sum("scholarship__discount_value")
            )
            .order_by("-count")
        )

        return {
            "academic_year": str(academic_year),
            "term": str(term) if term else "All Terms",
            "total_scholarships": scholarships.count(),
            "total_beneficiaries": beneficiary_count,
            "total_discount_amount": total_discount,
            "discount_by_type": discount_by_type,
            "criteria_distribution": list(criteria_distribution),
            "average_discount_per_student": (
                total_discount / beneficiary_count
                if beneficiary_count > 0
                else Decimal("0.00")
            ),
        }

    @classmethod
    def generate_revenue_forecast(cls, academic_year, months_ahead=6) -> Dict:
        """Generate revenue forecast based on historical data."""

        # Historical collection patterns
        historical_data = (
            Payment.objects.filter(
                invoice__academic_year=academic_year, status="completed"
            )
            .extra(select={"month": "extract(month from payment_date)"})
            .values("month")
            .annotate(monthly_total=Sum("amount"), payment_count=Count("id"))
            .order_by("month")
        )

        # Calculate average monthly collection
        if historical_data:
            avg_monthly_collection = sum(
                month["monthly_total"] for month in historical_data
            ) / len(historical_data)
        else:
            avg_monthly_collection = Decimal("0.00")

        # Outstanding amounts that could be collected
        outstanding_invoices = Invoice.objects.filter(
            academic_year=academic_year, status__in=["unpaid", "partially_paid"]
        ).aggregate(total_outstanding=Sum("net_amount") - Sum("paid_amount"))[
            "total_outstanding"
        ] or Decimal(
            "0.00"
        )

        # Generate forecast
        forecast_months = []
        current_date = timezone.now().date()

        for i in range(months_ahead):
            forecast_date = current_date + timedelta(days=30 * i)

            # Basic forecast based on historical average
            base_forecast = avg_monthly_collection

            # Adjust for outstanding amounts
            if outstanding_invoices > 0 and i < 3:  # Higher collection in next 3 months
                adjustment_factor = 1.2 if i == 0 else 1.1
                base_forecast *= adjustment_factor

            forecast_months.append(
                {
                    "month": forecast_date.strftime("%Y-%m"),
                    "forecasted_amount": base_forecast,
                    "confidence_level": "high" if i < 3 else "medium",
                }
            )

        return {
            "forecast_period": f"{months_ahead} months ahead",
            "historical_monthly_average": avg_monthly_collection,
            "total_outstanding": outstanding_invoices,
            "monthly_forecasts": forecast_months,
            "total_forecasted": sum(
                month["forecasted_amount"] for month in forecast_months
            ),
        }

    @classmethod
    def calculate_fee_structure_efficiency(cls, academic_year, term) -> Dict:
        """Analyze efficiency of current fee structure."""

        # Collection rates by fee category
        from django.db.models import OuterRef, Subquery

        fee_structures = FeeStructure.objects.filter(
            academic_year=academic_year, term=term, is_active=True
        ).select_related("fee_category")

        category_performance = {}

        for fee_structure in fee_structures:
            category = fee_structure.fee_category.name

            if category not in category_performance:
                category_performance[category] = {
                    "total_expected": Decimal("0.00"),
                    "total_collected": Decimal("0.00"),
                    "invoice_count": 0,
                }

            # Get invoices with this fee structure
            related_invoices = Invoice.objects.filter(
                academic_year=academic_year,
                term=term,
                items__fee_structure=fee_structure,
            )

            category_stats = related_invoices.aggregate(
                expected=Sum("items__amount"), collected=Sum("paid_amount")
            )

            category_performance[category]["total_expected"] += category_stats[
                "expected"
            ] or Decimal("0.00")
            category_performance[category]["total_collected"] += category_stats[
                "collected"
            ] or Decimal("0.00")
            category_performance[category]["invoice_count"] += related_invoices.count()

        # Calculate efficiency metrics
        for category, data in category_performance.items():
            if data["total_expected"] > 0:
                data["collection_rate"] = (
                    data["total_collected"] / data["total_expected"] * 100
                )
                data["efficiency_score"] = min(100, data["collection_rate"])
            else:
                data["collection_rate"] = 0
                data["efficiency_score"] = 0

        return {
            "academic_year": str(academic_year),
            "term": str(term),
            "category_performance": category_performance,
            "recommendations": cls._generate_fee_structure_recommendations(
                category_performance
            ),
        }

    @classmethod
    def _generate_fee_structure_recommendations(cls, category_performance) -> List[str]:
        """Generate recommendations for fee structure optimization."""
        recommendations = []

        for category, data in category_performance.items():
            collection_rate = data["collection_rate"]

            if collection_rate < 60:
                recommendations.append(
                    f"Low collection rate for {category} ({collection_rate:.1f}%) - review pricing or payment terms"
                )
            elif collection_rate > 95:
                recommendations.append(
                    f"Excellent collection for {category} ({collection_rate:.1f}%) - consider as model for other categories"
                )

        return recommendations

    @classmethod
    def update_financial_analytics(cls, academic_year, term=None):
        """Update financial analytics tables with latest data."""

        # Clear existing analytics for the period
        FinancialAnalytics.objects.filter(
            academic_year=academic_year, term=term
        ).delete()

        # Calculate analytics by section
        sections = academic_year.class_set.values("grade__section").distinct()

        for section_data in sections:
            section_id = section_data["grade__section"]

            metrics = cls.calculate_collection_metrics(
                academic_year, term, section_id=section_id
            )

            FinancialAnalytics.objects.create(
                academic_year=academic_year,
                term=term,
                section_id=section_id,
                total_expected_revenue=metrics["collection_summary"][
                    "total_amount_due"
                ],
                total_collected_revenue=metrics["collection_summary"][
                    "total_collected"
                ],
                collection_rate=metrics["collection_summary"]["collection_rate"],
                total_outstanding=metrics["collection_summary"]["total_outstanding"],
                number_of_defaulters=metrics["overdue_analysis"]["overdue_invoices"],
            )
