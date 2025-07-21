# students/services/student_service.py
import csv
import io
import logging
import os
import uuid

import qrcode
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.mail import send_mail
from django.db import transaction
from django.template.loader import render_to_string
from django.utils import timezone
from PIL import Image
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from ..models import Parent, Student, StudentParentRelation

User = get_user_model()
logger = logging.getLogger(__name__)


class InvalidStudentDataError(Exception):
    """Exception raised when student data is invalid"""

    pass


class StudentService:

    @staticmethod
    def create_student(student_data, created_by=None):
        """
        Create a new student with direct fields (no user account)

        Args:
            student_data (dict): Student information
            created_by (User): User who created the student

        Returns:
            Student: Created student instance
        """
        with transaction.atomic():
            try:
                # Validate required fields
                required_fields = [
                    "first_name",
                    "last_name",
                    "admission_number",
                    "emergency_contact_name",
                    "emergency_contact_number",
                ]

                for field in required_fields:
                    if not student_data.get(field):
                        raise InvalidStudentDataError(f"{field} is required")

                # Set defaults
                if "admission_date" not in student_data:
                    student_data["admission_date"] = timezone.now().date()

                if "status" not in student_data:
                    student_data["status"] = "Active"

                if "is_active" not in student_data:
                    student_data["is_active"] = True

                # Add created_by if provided
                if created_by:
                    student_data["created_by"] = created_by

                # Create student
                student = Student.objects.create(**student_data)

                logger.info(f"Student created successfully: {student.admission_number}")

                # Send welcome email if email is provided
                if student.email and getattr(
                    settings, "ENABLE_EMAIL_NOTIFICATIONS", True
                ):
                    try:
                        StudentService.send_welcome_email(student)
                    except Exception as e:
                        logger.error(f"Failed to send welcome email: {str(e)}")

                return student

            except Exception as e:
                logger.error(f"Error creating student: {str(e)}")
                raise InvalidStudentDataError(f"Failed to create student: {str(e)}")

        """
        Import students from a CSV file with admission_number as username
        """
        created_count = 0
        updated_count = 0
        error_count = 0
        errors = []
        success_emails = []

        try:
            decoded_file = csv_file.read().decode("utf-8")
            io_string = io.StringIO(decoded_file)
            reader = csv.DictReader(io_string)

            for row_num, row in enumerate(reader, start=2):
                try:
                    with transaction.atomic():
                        # Validate required fields
                        required_fields = [
                            "first_name",
                            "last_name",
                            "admission_number",  # Email no longer required
                        ]
                        missing_fields = [
                            field for field in required_fields if not row.get(field)
                        ]

                        if missing_fields:
                            raise ValueError(
                                f"Missing required fields: {', '.join(missing_fields)}"
                            )

                        admission_number = row.get("admission_number")

                        # Prepare user data with admission_number as username
                        user_data = {
                            "username": admission_number,
                            "email": row.get("email", ""),  # Email is now optional
                            "first_name": row.get("first_name"),
                            "last_name": row.get("last_name"),
                            "phone_number": row.get("phone_number", ""),
                        }

                        # Parse date of birth
                        if row.get("date_of_birth"):
                            try:
                                user_data["date_of_birth"] = timezone.datetime.strptime(
                                    row["date_of_birth"], "%Y-%m-%d"
                                ).date()
                            except ValueError:
                                pass

                        # Prepare student data
                        student_data = {
                            "admission_number": admission_number,
                            "admission_date": timezone.datetime.strptime(
                                row.get(
                                    "admission_date",
                                    timezone.now().strftime("%Y-%m-%d"),
                                ),
                                "%Y-%m-%d",
                            ).date(),
                            "blood_group": row.get("blood_group", "Unknown"),
                            "emergency_contact_name": row.get(
                                "emergency_contact_name", ""
                            ),
                            "emergency_contact_number": row.get(
                                "emergency_contact_number", ""
                            ),
                            "status": row.get("status", "Active"),
                            "nationality": row.get("nationality", ""),
                            "religion": row.get("religion", ""),
                            "city": row.get("city", ""),
                            "state": row.get("state", ""),
                            "country": row.get("country", "India"),
                        }

                        # Handle current class
                        class_id = row.get("current_class_id")
                        if class_id:
                            from src.academics.models import Class

                            try:
                                student_data["current_class"] = Class.objects.get(
                                    id=class_id
                                )
                            except Class.DoesNotExist:
                                pass

                        # Check if student exists
                        existing_student = Student.objects.filter(
                            admission_number=student_data["admission_number"]
                        ).first()

                        if existing_student:
                            if update_existing:
                                StudentService.update_student(
                                    existing_student,
                                    student_data,
                                    user_data,
                                    created_by,
                                )
                                updated_count += 1
                            else:
                                raise ValueError(
                                    "Student with this admission number already exists"
                                )
                        else:
                            student = StudentService.create_student(
                                student_data, user_data, created_by
                            )
                            created_count += 1

                            # Only add to success emails if email is provided
                            if user_data.get("email") and send_notifications:
                                success_emails.append(student.user.email)

                except Exception as e:
                    error_count += 1
                    errors.append({"row": row_num, "data": dict(row), "error": str(e)})
                    logger.error(f"Error processing row {row_num}: {str(e)}")

            # Send notification emails only to students with email addresses
            if send_notifications and success_emails:
                StudentService._send_bulk_welcome_emails(success_emails)

        except Exception as e:
            logger.error(f"Critical error during bulk import: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "created": 0,
                "updated": 0,
                "errors": 0,
                "error_details": [],
            }

        return {
            "success": True,
            "created": created_count,
            "updated": updated_count,
            "errors": error_count,
            "error_details": errors,
            "total_processed": created_count + updated_count + error_count,
        }

    @staticmethod
    def update_student(student, student_data, updated_by=None):
        """
        Update student information

        Args:
            student (Student): Student instance to update
            student_data (dict): Updated student data
            updated_by (User): User who updated the student

        Returns:
            Student: Updated student instance
        """
        with transaction.atomic():
            try:
                # Update fields
                for field, value in student_data.items():
                    if hasattr(student, field):
                        setattr(student, field, value)

                student.save()

                logger.info(f"Student updated successfully: {student.admission_number}")
                return student

            except Exception as e:
                logger.error(f"Error updating student: {str(e)}")
                raise InvalidStudentDataError(f"Failed to update student: {str(e)}")

    def send_welcome_email(student):
        """
        Send welcome email to student (if email provided)

        Args:
            student (Student): Student instance
        """
        if not student.email:
            logger.info(f"No email address for student {student.admission_number}")
            return

        try:
            subject = f'Welcome to {getattr(settings, "SCHOOL_NAME", "School")}'

            context = {
                "student": student,
                "school_name": getattr(settings, "SCHOOL_NAME", "School"),
                "admission_number": student.admission_number,
                "contact_email": getattr(settings, "SCHOOL_CONTACT_EMAIL", ""),
                "current_year": timezone.now().year,
            }

            # Try to render HTML template, fallback to plain text
            try:
                message = render_to_string("emails/student_welcome.html", context)
                html_message = message
                message = render_to_string("emails/student_welcome.txt", context)
            except:
                message = f"""
    Welcome to {context['school_name']}!

    Dear {student.first_name} {student.last_name},

    We are pleased to welcome you to our school. Your admission number is: {student.admission_number}

    Please contact us if you have any questions.

    Best regards,
    {context['school_name']} Administration
                    """.strip()
                html_message = None

            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[student.email],
                html_message=html_message,
                fail_silently=False,
            )

            logger.info(f"Welcome email sent to {student.email}")

        except Exception as e:
            logger.error(f"Failed to send welcome email to {student.email}: {str(e)}")
            raise

    @staticmethod
    def promote_students(students, target_class, send_notifications=True):
        """
        Promote multiple students to a new class

        Args:
            students (QuerySet): Students to promote
            target_class (Class): Target class
            send_notifications (bool): Whether to send notifications

        Returns:
            dict: Results summary
        """
        promoted_count = 0
        failed_count = 0
        errors = []

        with transaction.atomic():
            for student in students:
                try:
                    old_class = student.current_class
                    student.current_class = target_class
                    student.save()

                    promoted_count += 1

                    # Send notification email if enabled and email exists
                    if (
                        send_notifications
                        and student.email
                        and getattr(settings, "ENABLE_EMAIL_NOTIFICATIONS", True)
                    ):
                        try:
                            StudentService.send_promotion_email(
                                student, old_class, target_class
                            )
                        except Exception as e:
                            logger.error(f"Failed to send promotion email: {str(e)}")

                except Exception as e:
                    failed_count += 1
                    errors.append(f"{student.admission_number}: {str(e)}")
                    logger.error(
                        f"Failed to promote student {student.admission_number}: {str(e)}"
                    )

        return {
            "promoted": promoted_count,
            "failed": failed_count,
            "errors": errors,
        }

    def send_promotion_email(student, old_class, new_class):
        """
        Send promotion notification email to student

        Args:
            student (Student): Student instance
            old_class (Class): Previous class
            new_class (Class): New class
        """
        if not student.email:
            return

        try:
            subject = f"Class Promotion - {getattr(settings, 'SCHOOL_NAME', 'School')}"

            context = {
                "student": student,
                "old_class": old_class,
                "new_class": new_class,
                "school_name": getattr(settings, "SCHOOL_NAME", "School"),
            }

            message = f"""
Dear {student.first_name} {student.last_name},

Congratulations! You have been promoted from {old_class} to {new_class}.

Your admission number: {student.admission_number}

Best regards,
{context['school_name']} Administration
            """.strip()

            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[student.email],
                fail_silently=False,
            )

        except Exception as e:
            logger.error(f"Failed to send promotion email: {str(e)}")
            raise

    @staticmethod
    def generate_student_id_card(student):
        """
        Generate student ID card PDF

        Args:
            student (Student): Student instance

        Returns:
            str: Path to generated PDF file
        """
        try:
            # Create directory if it doesn't exist
            id_cards_dir = os.path.join(settings.MEDIA_ROOT, "id_cards")
            os.makedirs(id_cards_dir, exist_ok=True)

            # Generate filename
            filename = f"id_card_{student.admission_number}_{timezone.now().strftime('%Y%m%d')}.pdf"
            file_path = os.path.join(id_cards_dir, filename)

            # Create PDF
            doc = SimpleDocTemplate(file_path, pagesize=A4)
            styles = getSampleStyleSheet()
            story = []

            # Title
            title_style = ParagraphStyle(
                "CustomTitle",
                parent=styles["Title"],
                fontSize=16,
                spaceAfter=20,
                textColor=colors.darkblue,
            )

            story.append(
                Paragraph(
                    f"{getattr(settings, 'SCHOOL_NAME', 'School')} - Student ID Card",
                    title_style,
                )
            )
            story.append(Spacer(1, 12))

            # Student information table
            data = [
                ["Admission Number:", student.admission_number],
                ["Name:", student.full_name],
                [
                    "Class:",
                    (
                        str(student.current_class)
                        if student.current_class
                        else "Not Assigned"
                    ),
                ],
                ["Blood Group:", student.blood_group],
                ["Emergency Contact:", student.emergency_contact_name],
                ["Contact Number:", student.emergency_contact_number],
            ]

            if student.date_of_birth:
                data.append(
                    ["Date of Birth:", student.date_of_birth.strftime("%d/%m/%Y")]
                )

            table = Table(data, colWidths=[2 * 72, 3 * 72])
            table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("FONTSIZE", (0, 0), (-1, 0), 12),
                        ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                        ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
                        ("GRID", (0, 0), (-1, -1), 1, colors.black),
                    ]
                )
            )

            story.append(table)
            story.append(Spacer(1, 20))

            # QR Code with admission number
            qr = qrcode.QRCode(version=1, box_size=10, border=5)
            qr.add_data(student.admission_number)
            qr.make(fit=True)

            qr_img = qr.make_image(fill_color="black", back_color="white")
            qr_path = os.path.join(id_cards_dir, f"qr_{student.admission_number}.png")
            qr_img.save(qr_path)

            story.append(
                Paragraph("Scan QR Code for quick identification:", styles["Normal"])
            )

            # Build PDF
            doc.build(story)

            logger.info(f"ID card generated for student {student.admission_number}")
            return file_path

        except Exception as e:
            logger.error(f"Error generating ID card: {str(e)}")
            raise

    @staticmethod
    def bulk_import_students(
        csv_file, default_class=None, send_welcome_emails=True, created_by=None
    ):
        """
        Import students from CSV file

        Args:
            csv_file: CSV file object
            default_class (Class): Default class for students
            send_welcome_emails (bool): Whether to send welcome emails
            created_by (User): User who imported the students

        Returns:
            dict: Import results
        """
        created_count = 0
        failed_count = 0
        errors = []

        try:
            # Read CSV
            csv_content = csv_file.read().decode("utf-8")
            csv_reader = csv.DictReader(io.StringIO(csv_content))

            with transaction.atomic():
                for row_num, row in enumerate(csv_reader, start=2):
                    try:
                        # Extract student data from CSV row
                        student_data = {
                            "first_name": row.get("first_name", "").strip(),
                            "last_name": row.get("last_name", "").strip(),
                            "email": row.get("email", "").strip() or None,
                            "phone_number": row.get("phone_number", "").strip() or None,
                            "admission_number": row.get("admission_number", "").strip(),
                            "emergency_contact_name": row.get(
                                "emergency_contact_name", ""
                            ).strip(),
                            "emergency_contact_number": row.get(
                                "emergency_contact_number", ""
                            ).strip(),
                            "blood_group": row.get("blood_group", "Unknown"),
                            "gender": row.get("gender", "").strip()[:1].upper() or "",
                        }

                        # Set class
                        class_name = row.get("class_name", "").strip()
                        if class_name:
                            from src.academics.models import Class

                            try:
                                student_data["current_class"] = Class.objects.get(
                                    name=class_name
                                )
                            except Class.DoesNotExist:
                                if default_class:
                                    student_data["current_class"] = default_class
                        elif default_class:
                            student_data["current_class"] = default_class

                        # Create student
                        student = StudentService.create_student(
                            student_data, created_by
                        )
                        created_count += 1

                        # Send welcome email if enabled
                        if (
                            send_welcome_emails
                            and student.email
                            and getattr(settings, "ENABLE_EMAIL_NOTIFICATIONS", True)
                        ):
                            try:
                                StudentService.send_welcome_email(student)
                            except Exception as e:
                                logger.error(f"Failed to send welcome email: {str(e)}")

                    except Exception as e:
                        failed_count += 1
                        error_msg = f"Row {row_num}: {str(e)}"
                        errors.append(error_msg)
                        logger.error(f"Failed to import student from {error_msg}")

        except Exception as e:
            logger.error(f"Error during bulk import: {str(e)}")
            raise InvalidStudentDataError(f"Import failed: {str(e)}")

        return {
            "created": created_count,
            "failed": failed_count,
            "errors": errors,
        }

    @staticmethod
    def get_student_analytics(student):
        """
        Get analytics data for a student

        Args:
            student (Student): Student instance

        Returns:
            dict: Analytics data
        """
        cache_key = f"student_analytics_{student.id}"
        analytics = cache.get(cache_key)

        if analytics is None:
            try:
                analytics = {
                    "attendance_percentage": student.get_attendance_percentage(),
                    "siblings_count": len(student.get_siblings()),
                    "parents_count": student.get_parents().count(),
                    "age": student.age,
                    "days_since_admission": (
                        (timezone.now().date() - student.admission_date).days
                        if student.admission_date
                        else 0
                    ),
                }

                # Cache for 30 minutes
                cache.set(cache_key, analytics, 1800)

            except Exception as e:
                logger.error(f"Error calculating student analytics: {str(e)}")
                analytics = {}

        return analytics

    @staticmethod
    def graduate_students(students, send_notifications=False):
        """
        Mark multiple students as graduated

        Args:
            students (QuerySet): Student instances
            send_notifications (bool): Send notification emails

        Returns:
            dict: Graduation statistics
        """
        graduated_count = 0
        errors = []
        graduated_students = []

        with transaction.atomic():
            for student in students:
                try:
                    student.mark_as_graduated()
                    graduated_count += 1
                    graduated_students.append(student)
                except Exception as e:
                    errors.append(
                        {"student": student.admission_number, "error": str(e)}
                    )
                    logger.error(
                        f"Error graduating student {student.admission_number}: {str(e)}"
                    )

        # Send notification emails and generate certificates
        if send_notifications and graduated_students:
            StudentService._send_graduation_notifications(graduated_students)

        logger.info(f"Graduated {graduated_count} students")
        return {
            "graduated": graduated_count,
            "errors": len(errors),
            "error_details": errors,
        }

    @staticmethod
    def _send_graduation_notifications(graduated_students):
        """Send graduation notification emails"""
        try:
            for student in graduated_students:
                try:
                    # Send to student
                    send_mail(
                        subject="Graduation Confirmation",
                        message=render_to_string(
                            "emails/student_graduation.txt",
                            {
                                "student": student,
                                "school_name": getattr(
                                    settings, "SCHOOL_NAME", "School"
                                ),
                            },
                        ),
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[student.user.email],
                        fail_silently=True,
                    )

                    # Send to parents
                    for parent in student.get_parents():
                        send_mail(
                            subject=f"Graduation - {student.get_full_name()}",
                            message=render_to_string(
                                "emails/parent_graduation_notification.txt",
                                {
                                    "student": student,
                                    "parent": parent,
                                    "school_name": getattr(
                                        settings, "SCHOOL_NAME", "School"
                                    ),
                                },
                            ),
                            from_email=settings.DEFAULT_FROM_EMAIL,
                            recipient_list=[parent.user.email],
                            fail_silently=True,
                        )
                except Exception as e:
                    logger.error(
                        f"Failed to send graduation notification for {student.admission_number}: {str(e)}"
                    )
        except Exception as e:
            logger.error(f"Error in graduation notifications: {str(e)}")

    @staticmethod
    def export_students_to_csv(queryset):
        """
        Export students to CSV with enhanced data

        Args:
            queryset: QuerySet of Student objects

        Returns:
            str: CSV content as string
        """
        fieldnames = [
            "admission_number",
            "registration_number",
            "first_name",
            "last_name",
            "email",
            "phone_number",
            "date_of_birth",
            "gender",
            "status",
            "current_class",
            "roll_number",
            "blood_group",
            "nationality",
            "religion",
            "address",
            "city",
            "state",
            "postal_code",
            "country",
            "emergency_contact_name",
            "emergency_contact_number",
            "medical_conditions",
            "admission_date",
            "previous_school",
            "primary_parent_name",
            "primary_parent_phone",
            "created_at",
        ]

        csv_buffer = io.StringIO()
        writer = csv.DictWriter(csv_buffer, fieldnames=fieldnames)
        writer.writeheader()

        for student in queryset.select_related(
            "user", "current_class"
        ).prefetch_related("student_parent_relations__parent__user"):
            primary_parent = student.get_primary_parent()

            writer.writerow(
                {
                    "admission_number": student.admission_number,
                    "registration_number": student.registration_number or "",
                    "first_name": student.user.first_name,
                    "last_name": student.user.last_name,
                    "email": student.user.email,
                    "phone_number": student.user.phone_number or "",
                    "date_of_birth": student.user.date_of_birth or "",
                    "gender": getattr(student.user, "gender", ""),
                    "status": student.status,
                    "current_class": (
                        str(student.current_class) if student.current_class else ""
                    ),
                    "roll_number": student.roll_number or "",
                    "blood_group": student.blood_group,
                    "nationality": student.nationality or "",
                    "religion": student.religion or "",
                    "address": student.address or "",
                    "city": student.city or "",
                    "state": student.state or "",
                    "postal_code": student.postal_code or "",
                    "country": student.country or "",
                    "emergency_contact_name": student.emergency_contact_name,
                    "emergency_contact_number": student.emergency_contact_number,
                    "medical_conditions": student.medical_conditions or "",
                    "admission_date": student.admission_date,
                    "previous_school": student.previous_school or "",
                    "primary_parent_name": (
                        primary_parent.get_full_name() if primary_parent else ""
                    ),
                    "primary_parent_phone": (
                        primary_parent.user.phone_number if primary_parent else ""
                    ),
                    "created_at": student.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                }
            )

        return csv_buffer.getvalue()

    @staticmethod
    def get_student_statistics():
        """Get comprehensive student statistics"""
        total_students = Student.objects.count()
        active_students = Student.objects.filter(status="Active").count()

        stats = {
            "total_students": total_students,
            "active_students": active_students,
            "inactive_students": Student.objects.filter(status="Inactive").count(),
            "graduated_students": Student.objects.filter(status="Graduated").count(),
            "suspended_students": Student.objects.filter(status="Suspended").count(),
            "withdrawn_students": Student.objects.filter(status="Withdrawn").count(),
            "students_with_photos": Student.objects.exclude(photo__isnull=True)
            .exclude(photo="")
            .count(),
            "students_without_parents": Student.objects.filter(
                student_parent_relations__isnull=True
            ).count(),
        }

        # Calculate percentages
        if total_students > 0:
            stats["active_percentage"] = round(
                (active_students / total_students) * 100, 1
            )
            stats["completion_percentage"] = round(
                (stats["students_with_photos"] / total_students) * 100, 1
            )
        else:
            stats["active_percentage"] = 0
            stats["completion_percentage"] = 0

        return stats

    @staticmethod
    def search_students(query, filters=None):
        """
        Advanced student search with filters

        Args:
            query (str): Search query
            filters (dict): Additional filters

        Returns:
            QuerySet: Filtered students
        """
        students = Student.objects.with_related()

        if query:
            students = students.search(query)

        if filters:
            if filters.get("status"):
                students = students.filter(status=filters["status"])

            if filters.get("class_id"):
                students = students.filter(current_class_id=filters["class_id"])

            if filters.get("blood_group"):
                students = students.filter(blood_group=filters["blood_group"])

            if filters.get("admission_year"):
                students = students.filter(
                    admission_date__year=filters["admission_year"]
                )

        return students.order_by("admission_number")
