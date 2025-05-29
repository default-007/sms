# finance/management/commands/calculate_financial_analytics.py

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from academics.models import AcademicYear, Term
from finance.services.analytics_service import FinancialAnalyticsService


class Command(BaseCommand):
    """Management command to calculate financial analytics."""

    help = "Calculate and update financial analytics for specified periods"

    def add_arguments(self, parser):
        parser.add_argument(
            "--academic-year",
            type=int,
            help="Academic year ID to calculate analytics for",
        )
        parser.add_argument(
            "--term", type=int, help="Term ID to calculate analytics for (optional)"
        )
        parser.add_argument(
            "--all-years",
            action="store_true",
            help="Calculate analytics for all academic years",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Force recalculation even if analytics exist",
        )

    def handle(self, *args, **options):
        """Execute the command."""

        if options["all_years"]:
            academic_years = AcademicYear.objects.all()
        elif options["academic_year"]:
            try:
                academic_years = [AcademicYear.objects.get(id=options["academic_year"])]
            except AcademicYear.DoesNotExist:
                raise CommandError(
                    f"Academic year with ID {options['academic_year']} does not exist"
                )
        else:
            # Default to current academic year
            try:
                academic_years = [AcademicYear.objects.get(is_current=True)]
            except AcademicYear.DoesNotExist:
                raise CommandError(
                    "No current academic year found. Please specify --academic-year or --all-years"
                )

        total_calculated = 0

        for academic_year in academic_years:
            self.stdout.write(f"Processing academic year: {academic_year}")

            if options["term"]:
                try:
                    terms = [
                        Term.objects.get(
                            id=options["term"], academic_year=academic_year
                        )
                    ]
                except Term.DoesNotExist:
                    self.stdout.write(
                        self.style.WARNING(
                            f"Term with ID {options['term']} not found in {academic_year}"
                        )
                    )
                    continue
            else:
                terms = academic_year.term_set.all()

            for term in terms:
                self.stdout.write(f"  Processing term: {term}")

                try:
                    with transaction.atomic():
                        FinancialAnalyticsService.update_financial_analytics(
                            academic_year, term
                        )
                        total_calculated += 1
                        self.stdout.write(
                            self.style.SUCCESS(f"    ✓ Analytics updated for {term}")
                        )
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(
                            f"    ✗ Error updating analytics for {term}: {e}"
                        )
                    )

        self.stdout.write(
            self.style.SUCCESS(
                f"\nCompleted! Analytics calculated for {total_calculated} periods."
            )
        )


# finance/management/commands/generate_bulk_invoices.py

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from academics.models import AcademicYear, Class, Grade, Section, Term
from finance.services.invoice_service import InvoiceService
from students.models import Student


class Command(BaseCommand):
    """Management command to generate invoices in bulk."""

    help = "Generate invoices for students in bulk"

    def add_arguments(self, parser):
        parser.add_argument(
            "--academic-year",
            type=int,
            required=True,
            help="Academic year ID to generate invoices for",
        )
        parser.add_argument(
            "--term", type=int, required=True, help="Term ID to generate invoices for"
        )
        parser.add_argument(
            "--section", type=int, help="Section ID to filter students (optional)"
        )
        parser.add_argument(
            "--grade", type=int, help="Grade ID to filter students (optional)"
        )
        parser.add_argument(
            "--class", type=int, help="Class ID to filter students (optional)"
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be done without actually creating invoices",
        )

    def handle(self, *args, **options):
        """Execute the command."""

        try:
            academic_year = AcademicYear.objects.get(id=options["academic_year"])
            term = Term.objects.get(id=options["term"])
        except (AcademicYear.DoesNotExist, Term.DoesNotExist) as e:
            raise CommandError(f"Invalid academic year or term: {e}")

        # Build student queryset based on filters
        students = Student.objects.filter(
            status="active", current_class__academic_year=academic_year
        ).select_related("user", "current_class")

        if options["class"]:
            try:
                class_obj = Class.objects.get(id=options["class"])
                students = students.filter(current_class=class_obj)
            except Class.DoesNotExist:
                raise CommandError(f"Class with ID {options['class']} does not exist")

        elif options["grade"]:
            try:
                grade = Grade.objects.get(id=options["grade"])
                students = students.filter(current_class__grade=grade)
            except Grade.DoesNotExist:
                raise CommandError(f"Grade with ID {options['grade']} does not exist")

        elif options["section"]:
            try:
                section = Section.objects.get(id=options["section"])
                students = students.filter(current_class__grade__section=section)
            except Section.DoesNotExist:
                raise CommandError(
                    f"Section with ID {options['section']} does not exist"
                )

        student_count = students.count()

        if student_count == 0:
            self.stdout.write(
                self.style.WARNING("No students found matching the criteria")
            )
            return

        self.stdout.write(f"Found {student_count} students for invoice generation")

        if options["dry_run"]:
            self.stdout.write(
                self.style.WARNING("DRY RUN - No invoices will be created")
            )
            for student in students[:10]:  # Show first 10
                self.stdout.write(
                    f"  - {student.user.get_full_name()} ({student.current_class})"
                )
            if student_count > 10:
                self.stdout.write(f"  ... and {student_count - 10} more students")
            return

        # Confirm before proceeding
        confirm = input(f"Generate invoices for {student_count} students? [y/N]: ")
        if confirm.lower() != "y":
            self.stdout.write("Operation cancelled")
            return

        # Generate invoices
        self.stdout.write("Generating invoices...")

        try:
            with transaction.atomic():
                results = InvoiceService.bulk_generate_invoices(
                    list(students), academic_year, term
                )

                self.stdout.write(
                    self.style.SUCCESS(f"✓ Created {len(results['created'])} invoices")
                )

                if results["skipped"]:
                    self.stdout.write(
                        self.style.WARNING(
                            f"⚠ Skipped {len(results['skipped'])} students (already have invoices)"
                        )
                    )

                if results["errors"]:
                    self.stdout.write(
                        self.style.ERROR(
                            f"✗ Errors for {len(results['errors'])} students"
                        )
                    )
                    for error in results["errors"][:5]:  # Show first 5 errors
                        self.stdout.write(f"  - {error['student']}: {error['error']}")

        except Exception as e:
            raise CommandError(f"Error during bulk invoice generation: {e}")


# finance/management/commands/send_payment_reminders.py

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from finance.models import Invoice
from finance.services.invoice_service import InvoiceService


class Command(BaseCommand):
    """Management command to send payment reminders."""

    help = "Send payment reminders for overdue invoices"

    def add_arguments(self, parser):
        parser.add_argument(
            "--days-overdue",
            type=int,
            default=7,
            help="Send reminders for invoices overdue by this many days",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what reminders would be sent without actually sending them",
        )
        parser.add_argument(
            "--limit", type=int, default=100, help="Maximum number of reminders to send"
        )

    def handle(self, *args, **options):
        """Execute the command."""

        days_overdue = options["days_overdue"]
        cutoff_date = timezone.now().date() - timedelta(days=days_overdue)

        # Get overdue invoices
        overdue_invoices = Invoice.objects.filter(
            due_date__lt=cutoff_date, status__in=["unpaid", "partially_paid"]
        ).select_related("student", "student__user")[: options["limit"]]

        reminder_count = 0

        self.stdout.write(f"Found {overdue_invoices.count()} overdue invoices")

        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("DRY RUN - No reminders will be sent"))

        for invoice in overdue_invoices:
            days_overdue_count = (timezone.now().date() - invoice.due_date).days

            self.stdout.write(
                f"Invoice {invoice.invoice_number} - {invoice.student.user.get_full_name()} "
                f"(${invoice.outstanding_amount}, {days_overdue_count} days overdue)"
            )

            if not options["dry_run"]:
                try:
                    reminder_data = InvoiceService.send_payment_reminder(invoice)
                    self.stdout.write(
                        f"  ✓ Reminder sent to {reminder_data['recipient']}"
                    )
                    reminder_count += 1
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f"  ✗ Failed to send reminder: {e}")
                    )

        if not options["dry_run"]:
            self.stdout.write(
                self.style.SUCCESS(f"Sent {reminder_count} payment reminders")
            )


# finance/management/commands/process_sibling_discounts.py

from django.core.management.base import BaseCommand, CommandError

from academics.models import AcademicYear
from finance.services.scholarship_service import ScholarshipService


class Command(BaseCommand):
    """Management command to automatically process sibling discounts."""

    help = "Automatically assign sibling discounts based on family relationships"

    def add_arguments(self, parser):
        parser.add_argument(
            "--academic-year",
            type=int,
            help="Academic year ID to process sibling discounts for",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be done without actually assigning scholarships",
        )

    def handle(self, *args, **options):
        """Execute the command."""

        if options["academic_year"]:
            try:
                academic_year = AcademicYear.objects.get(id=options["academic_year"])
            except AcademicYear.DoesNotExist:
                raise CommandError(
                    f"Academic year with ID {options['academic_year']} does not exist"
                )
        else:
            # Default to current academic year
            try:
                academic_year = AcademicYear.objects.get(is_current=True)
            except AcademicYear.DoesNotExist:
                raise CommandError(
                    "No current academic year found. Please specify --academic-year"
                )

        self.stdout.write(f"Processing sibling discounts for {academic_year}")

        if options["dry_run"]:
            self.stdout.write(
                self.style.WARNING("DRY RUN - No scholarships will be assigned")
            )

        try:
            results = ScholarshipService.auto_assign_sibling_discount(academic_year)

            self.stdout.write(f"Scholarship: {results['scholarship'].name}")
            self.stdout.write(f"Families processed: {results['families_processed']}")

            if not options["dry_run"]:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Students assigned sibling discount: {results['students_assigned']}"
                    )
                )
            else:
                self.stdout.write(
                    f"Students that would be assigned: {results['students_assigned']}"
                )

        except Exception as e:
            raise CommandError(f"Error processing sibling discounts: {e}")


# finance/management/commands/reconcile_payments.py

from datetime import datetime
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone

from finance.services.payment_service import PaymentService


class Command(BaseCommand):
    """Management command to reconcile payments for a specific date."""

    help = "Reconcile payments for a specific date"

    def add_arguments(self, parser):
        parser.add_argument(
            "--date",
            type=str,
            help="Date to reconcile (YYYY-MM-DD format). Defaults to today",
        )
        parser.add_argument(
            "--expected-cash",
            type=float,
            help="Expected cash amount for reconciliation",
        )

    def handle(self, *args, **options):
        """Execute the command."""

        if options["date"]:
            try:
                reconcile_date = datetime.strptime(options["date"], "%Y-%m-%d").date()
            except ValueError:
                self.stdout.write(
                    self.style.ERROR("Invalid date format. Use YYYY-MM-DD")
                )
                return
        else:
            reconcile_date = timezone.now().date()

        expected_cash = (
            Decimal(str(options["expected_cash"])) if options["expected_cash"] else None
        )

        self.stdout.write(f"Reconciling payments for {reconcile_date}")

        try:
            reconciliation = PaymentService.reconcile_payments(
                reconcile_date, expected_cash
            )

            self.stdout.write("\n" + "=" * 50)
            self.stdout.write(f"PAYMENT RECONCILIATION - {reconciliation['date']}")
            self.stdout.write("=" * 50)

            self.stdout.write(
                f"Total Collections: ${reconciliation['total_collections']}"
            )
            self.stdout.write(f"Total Payments: {reconciliation['total_payments']}")

            self.stdout.write("\nBreakdown by Payment Method:")
            for method in reconciliation["method_breakdown"]:
                self.stdout.write(
                    f"  {method['payment_method'].title()}: ${method['total']} ({method['count']} payments)"
                )

            self.stdout.write(f"\nCash Collected: ${reconciliation['cash_collected']}")
            if reconciliation["cash_expected"] is not None:
                self.stdout.write(f"Cash Expected: ${reconciliation['cash_expected']}")
                variance = reconciliation["cash_variance"]
                if variance == 0:
                    self.stdout.write(self.style.SUCCESS("✓ Cash reconciled perfectly"))
                elif variance > 0:
                    self.stdout.write(
                        self.style.WARNING(f"⚠ Cash surplus: ${variance}")
                    )
                else:
                    self.stdout.write(
                        self.style.ERROR(f"✗ Cash shortage: ${abs(variance)}")
                    )

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error during reconciliation: {e}"))
