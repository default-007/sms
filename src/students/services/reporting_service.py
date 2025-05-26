# students/services/reporting_service.py
import csv
import io
import json
import logging
import os
from datetime import datetime, timedelta

from django.conf import settings
from django.db.models import Avg, Count, F, Q
from django.template.loader import render_to_string
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from ..exceptions import ExportError, ReportingError
from ..models import Parent, Student, StudentParentRelation
from .analytics_service import StudentAnalyticsService

logger = logging.getLogger(__name__)


class StudentReportingService:
    """Comprehensive reporting service for student data"""

    @staticmethod
    def generate_student_profile_report(
        student, format="pdf", include_family=True, include_academic=True
    ):
        """Generate comprehensive student profile report"""
        try:
            context = StudentReportingService._prepare_student_context(
                student, include_family, include_academic
            )

            if format.lower() == "pdf":
                return StudentReportingService._generate_student_pdf_report(
                    student, context
                )
            elif format.lower() == "html":
                return render_to_string("reports/student_profile.html", context)
            elif format.lower() == "json":
                return json.dumps(context, indent=2, default=str)
            else:
                raise ExportError(f"Unsupported format: {format}")

        except Exception as e:
            logger.error(f"Error generating student profile report: {str(e)}")
            raise ExportError(f"Failed to generate student report: {str(e)}")

    @staticmethod
    def generate_class_roster_report(class_obj, format="pdf", include_parents=True):
        """Generate class roster with student details"""
        try:
            students = (
                Student.objects.filter(current_class=class_obj, status="Active")
                .select_related("user")
                .prefetch_related("student_parent_relations__parent__user")
            )

            context = {
                "class": class_obj,
                "students": students,
                "total_students": students.count(),
                "generated_date": timezone.now(),
                "include_parents": include_parents,
                "school_name": getattr(settings, "SCHOOL_NAME", "School"),
            }

            if format.lower() == "pdf":
                return StudentReportingService._generate_class_roster_pdf(context)
            elif format.lower() == "csv":
                return StudentReportingService._generate_class_roster_csv(context)
            elif format.lower() == "html":
                return render_to_string("reports/class_roster.html", context)
            else:
                raise ExportError(f"Unsupported format: {format}")

        except Exception as e:
            logger.error(f"Error generating class roster: {str(e)}")
            raise ExportError(f"Failed to generate class roster: {str(e)}")

    @staticmethod
    def generate_attendance_summary_report(
        class_obj=None, academic_year=None, format="pdf"
    ):
        """Generate attendance summary report"""
        try:
            queryset = Student.objects.filter(status="Active")

            if class_obj:
                queryset = queryset.filter(current_class=class_obj)

            attendance_data = []
            for student in queryset:
                percentage = student.get_attendance_percentage(academic_year)
                attendance_data.append(
                    {
                        "student": student,
                        "percentage": percentage,
                        "status": StudentReportingService._get_attendance_status(
                            percentage
                        ),
                    }
                )

            # Sort by attendance percentage (lowest first for attention)
            attendance_data.sort(key=lambda x: x["percentage"])

            context = {
                "attendance_data": attendance_data,
                "class": class_obj,
                "academic_year": academic_year,
                "generated_date": timezone.now(),
                "summary_stats": StudentReportingService._calculate_attendance_stats(
                    attendance_data
                ),
                "school_name": getattr(settings, "SCHOOL_NAME", "School"),
            }

            if format.lower() == "pdf":
                return StudentReportingService._generate_attendance_pdf(context)
            elif format.lower() == "csv":
                return StudentReportingService._generate_attendance_csv(context)
            else:
                raise ExportError(f"Unsupported format: {format}")

        except Exception as e:
            logger.error(f"Error generating attendance report: {str(e)}")
            raise ExportError(f"Failed to generate attendance report: {str(e)}")

    @staticmethod
    def generate_parent_contact_list(
        class_obj=None, format="pdf", include_emergency_only=False
    ):
        """Generate parent contact list"""
        try:
            queryset = (
                Parent.objects.all()
                .select_related("user")
                .prefetch_related("parent_student_relations__student")
            )

            if class_obj:
                queryset = queryset.filter(
                    parent_student_relations__student__current_class=class_obj
                )

            if include_emergency_only:
                queryset = queryset.filter(emergency_contact=True)

            context = {
                "parents": queryset.distinct(),
                "class": class_obj,
                "emergency_only": include_emergency_only,
                "generated_date": timezone.now(),
                "school_name": getattr(settings, "SCHOOL_NAME", "School"),
            }

            if format.lower() == "pdf":
                return StudentReportingService._generate_parent_contact_pdf(context)
            elif format.lower() == "csv":
                return StudentReportingService._generate_parent_contact_csv(context)
            else:
                raise ExportError(f"Unsupported format: {format}")

        except Exception as e:
            logger.error(f"Error generating parent contact list: {str(e)}")
            raise ExportError(f"Failed to generate parent contact list: {str(e)}")

    @staticmethod
    def generate_analytics_dashboard_report(format="pdf"):
        """Generate comprehensive analytics dashboard report"""
        try:
            dashboard_data = StudentAnalyticsService.get_comprehensive_dashboard_data()

            context = {
                "dashboard_data": dashboard_data,
                "generated_date": timezone.now(),
                "school_name": getattr(settings, "SCHOOL_NAME", "School"),
            }

            if format.lower() == "pdf":
                return StudentReportingService._generate_analytics_pdf(context)
            elif format.lower() == "json":
                return json.dumps(dashboard_data, indent=2, default=str)
            else:
                raise ExportError(f"Unsupported format: {format}")

        except Exception as e:
            logger.error(f"Error generating analytics report: {str(e)}")
            raise ExportError(f"Failed to generate analytics report: {str(e)}")

    @staticmethod
    def generate_missing_information_report(format="csv"):
        """Generate report of students with missing information"""
        try:
            missing_data = []

            for student in Student.objects.select_related("user").prefetch_related(
                "student_parent_relations"
            ):
                issues = []

                # Check missing basic info
                if not student.user.date_of_birth:
                    issues.append("Date of Birth")
                if not student.user.phone_number:
                    issues.append("Phone Number")
                if not student.photo:
                    issues.append("Photo")
                if not student.address:
                    issues.append("Address")
                if not student.emergency_contact_name:
                    issues.append("Emergency Contact")
                if student.blood_group == "Unknown":
                    issues.append("Blood Group")

                # Check missing parents
                if not student.student_parent_relations.exists():
                    issues.append("Parent Information")
                elif not student.student_parent_relations.filter(
                    is_primary_contact=True
                ).exists():
                    issues.append("Primary Contact")

                if issues:
                    missing_data.append(
                        {
                            "student": student,
                            "missing_fields": issues,
                            "missing_count": len(issues),
                        }
                    )

            # Sort by most issues first
            missing_data.sort(key=lambda x: x["missing_count"], reverse=True)

            context = {
                "missing_data": missing_data,
                "total_students_with_issues": len(missing_data),
                "generated_date": timezone.now(),
            }

            if format.lower() == "csv":
                return StudentReportingService._generate_missing_info_csv(context)
            elif format.lower() == "pdf":
                return StudentReportingService._generate_missing_info_pdf(context)
            else:
                raise ExportError(f"Unsupported format: {format}")

        except Exception as e:
            logger.error(f"Error generating missing information report: {str(e)}")
            raise ExportError(
                f"Failed to generate missing information report: {str(e)}"
            )

    @staticmethod
    def _prepare_student_context(student, include_family, include_academic):
        """Prepare context data for student reports"""
        context = {
            "student": student,
            "generated_date": timezone.now(),
            "school_name": getattr(settings, "SCHOOL_NAME", "School"),
            "profile_completion": StudentReportingService._calculate_profile_completion(
                student
            ),
        }

        if include_family:
            context.update(
                {
                    "parents": student.get_parents(),
                    "primary_parent": student.get_primary_parent(),
                    "siblings": student.get_siblings(),
                }
            )

        if include_academic:
            context.update(
                {
                    "current_class": student.current_class,
                    "attendance_percentage": student.get_attendance_percentage(),
                    "academic_history": [],  # Would integrate with academic records
                }
            )

        return context

    @staticmethod
    def _generate_student_pdf_report(student, context):
        """Generate PDF report for individual student"""
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        styles = getSampleStyleSheet()
        content = []

        # Title
        title_style = ParagraphStyle(
            "CustomTitle",
            parent=styles["Heading1"],
            fontSize=18,
            textColor=colors.darkblue,
            alignment=1,
        )
        content.append(Paragraph(f"Student Profile Report", title_style))
        content.append(Spacer(1, 20))

        # Student basic info
        student_info = [
            ["Name:", student.get_full_name()],
            ["Admission Number:", student.admission_number],
            [
                "Class:",
                str(student.current_class) if student.current_class else "Not Assigned",
            ],
            ["Status:", student.status],
            ["Blood Group:", student.blood_group],
            ["Date of Birth:", student.user.date_of_birth or "Not provided"],
            ["Age:", f"{student.age} years" if student.age else "Not calculated"],
        ]

        info_table = Table(student_info, colWidths=[2 * inch, 4 * inch])
        info_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (0, -1), colors.lightgrey),
                    ("TEXTCOLOR", (0, 0), (-1, -1), colors.black),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 10),
                    ("GRID", (0, 0), (-1, -1), 1, colors.black),
                ]
            )
        )

        content.append(info_table)
        content.append(Spacer(1, 20))

        # Contact information
        if student.emergency_contact_name:
            content.append(
                Paragraph("Emergency Contact Information", styles["Heading2"])
            )
            emergency_info = [
                ["Contact Name:", student.emergency_contact_name],
                ["Contact Number:", student.emergency_contact_number],
                ["Address:", student.get_full_address() or "Not provided"],
            ]

            emergency_table = Table(emergency_info, colWidths=[2 * inch, 4 * inch])
            emergency_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (0, -1), colors.lightgrey),
                        ("GRID", (0, 0), (-1, -1), 1, colors.black),
                        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                    ]
                )
            )
            content.append(emergency_table)
            content.append(Spacer(1, 20))

        # Family information
        if "parents" in context and context["parents"]:
            content.append(Paragraph("Family Information", styles["Heading2"]))
            for parent in context["parents"]:
                relation = student.student_parent_relations.filter(
                    parent=parent
                ).first()
                parent_info = [
                    ["Name:", parent.get_full_name()],
                    ["Relation:", parent.relation_with_student],
                    ["Email:", parent.user.email],
                    ["Phone:", parent.user.phone_number or "Not provided"],
                    ["Occupation:", parent.occupation or "Not provided"],
                    [
                        "Primary Contact:",
                        "Yes" if relation and relation.is_primary_contact else "No",
                    ],
                ]

                parent_table = Table(parent_info, colWidths=[2 * inch, 4 * inch])
                parent_table.setStyle(
                    TableStyle(
                        [
                            ("BACKGROUND", (0, 0), (0, -1), colors.lightblue),
                            ("GRID", (0, 0), (-1, -1), 1, colors.black),
                            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                        ]
                    )
                )
                content.append(parent_table)
                content.append(Spacer(1, 10))

        doc.build(content)
        buffer.seek(0)
        return buffer.getvalue()

    @staticmethod
    def _generate_class_roster_pdf(context):
        """Generate PDF class roster"""
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        styles = getSampleStyleSheet()
        content = []

        # Title
        content.append(
            Paragraph(f"Class Roster - {context['class']}", styles["Heading1"])
        )
        content.append(
            Paragraph(
                f"Generated on: {context['generated_date'].strftime('%B %d, %Y')}",
                styles["Normal"],
            )
        )
        content.append(Spacer(1, 20))

        # Student table
        table_data = [["#", "Admission No.", "Name", "Blood Group", "Contact"]]

        for i, student in enumerate(context["students"], 1):
            primary_parent = student.get_primary_parent()
            contact = primary_parent.user.phone_number if primary_parent else "N/A"

            table_data.append(
                [
                    str(i),
                    student.admission_number,
                    student.get_full_name(),
                    student.blood_group,
                    contact,
                ]
            )

        roster_table = Table(
            table_data,
            colWidths=[0.5 * inch, 1.5 * inch, 2.5 * inch, 1 * inch, 1.5 * inch],
        )
        roster_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 12),
                    ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                    ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
                    ("GRID", (0, 0), (-1, -1), 1, colors.black),
                ]
            )
        )

        content.append(roster_table)
        content.append(Spacer(1, 20))

        # Summary
        content.append(
            Paragraph(
                f"Total Students: {context['total_students']}", styles["Heading3"]
            )
        )

        doc.build(content)
        buffer.seek(0)
        return buffer.getvalue()

    @staticmethod
    def _generate_class_roster_csv(context):
        """Generate CSV class roster"""
        output = io.StringIO()
        writer = csv.writer(output)

        # Header
        writer.writerow(["Class Roster", str(context["class"])])
        writer.writerow(
            ["Generated", context["generated_date"].strftime("%Y-%m-%d %H:%M:%S")]
        )
        writer.writerow([])  # Empty row

        # Column headers
        headers = ["Sr.No", "Admission Number", "Name", "Blood Group", "Email", "Phone"]
        if context["include_parents"]:
            headers.extend(["Primary Parent", "Parent Phone", "Parent Email"])
        writer.writerow(headers)

        # Student data
        for i, student in enumerate(context["students"], 1):
            row = [
                i,
                student.admission_number,
                student.get_full_name(),
                student.blood_group,
                student.user.email,
                student.user.phone_number or "",
            ]

            if context["include_parents"]:
                primary_parent = student.get_primary_parent()
                if primary_parent:
                    row.extend(
                        [
                            primary_parent.get_full_name(),
                            primary_parent.user.phone_number or "",
                            primary_parent.user.email,
                        ]
                    )
                else:
                    row.extend(["", "", ""])

            writer.writerow(row)

        return output.getvalue()

    @staticmethod
    def _calculate_profile_completion(student):
        """Calculate profile completion percentage"""
        total_fields = 12
        completed = 0

        if student.user.first_name:
            completed += 1
        if student.user.last_name:
            completed += 1
        if student.user.email:
            completed += 1
        if student.user.date_of_birth:
            completed += 1
        if student.emergency_contact_name:
            completed += 1
        if student.emergency_contact_number:
            completed += 1
        if student.photo:
            completed += 1
        if student.address:
            completed += 1
        if student.current_class:
            completed += 1
        if student.blood_group != "Unknown":
            completed += 1
        if student.city:
            completed += 1
        if student.student_parent_relations.exists():
            completed += 1

        return round((completed / total_fields) * 100)

    @staticmethod
    def _get_attendance_status(percentage):
        """Get attendance status based on percentage"""
        if percentage >= 95:
            return "Excellent"
        elif percentage >= 85:
            return "Good"
        elif percentage >= 75:
            return "Average"
        elif percentage >= 60:
            return "Poor"
        else:
            return "Critical"

    @staticmethod
    def _calculate_attendance_stats(attendance_data):
        """Calculate attendance statistics"""
        if not attendance_data:
            return {}

        percentages = [item["percentage"] for item in attendance_data]
        return {
            "average": round(sum(percentages) / len(percentages), 2),
            "highest": max(percentages),
            "lowest": min(percentages),
            "excellent_count": len([p for p in percentages if p >= 95]),
            "critical_count": len([p for p in percentages if p < 60]),
        }

    # Additional helper methods for other PDF/CSV generations would go here...
    # _generate_attendance_pdf, _generate_attendance_csv, etc.
