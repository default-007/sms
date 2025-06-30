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


class StudentService:
    @staticmethod
    def create_student(student_data, user_data=None, created_by=None):
        """
        Create a new student with associated user account
        Username will be set to admission_number
        """
        with transaction.atomic():
            try:
                # Get admission number for username
                admission_number = student_data.get("admission_number")
                if not admission_number:
                    raise ValueError("Admission number is required")

                # Create or get user account
                if user_data:
                    # Use admission number as username
                    username = admission_number
                    email = user_data.get("email", "")

                    if User.objects.filter(username=username).exists():
                        user = User.objects.get(username=username)
                        # Update existing user
                        for key, value in user_data.items():
                            if key not in ["password", "username"]:
                                setattr(user, key, value)
                    else:
                        # Create new user with admission number as username
                        password = user_data.pop("password", None)
                        user_data["username"] = username
                        user = User.objects.create(**user_data)
                        if password:
                            user.set_password(password)
                        else:
                            user.set_password(User.objects.make_random_password())
                        user.save()
                else:
                    user = student_data.get("user")

                # Create student profile
                student_data = {k: v for k, v in student_data.items() if k != "user"}
                student_data["user"] = user
                student_data["created_by"] = created_by

                student = Student.objects.create(**student_data)

                # Assign student role
                from src.accounts.services import RoleService

                RoleService.assign_role_to_user(user, "Student")

                logger.info(f"Created student: {student.admission_number}")
                return student

            except Exception as e:
                logger.error(f"Error creating student: {str(e)}")
                raise

    @staticmethod
    def bulk_import_students(
        csv_file,
        target_class=None,
        academic_year=None,
        auto_assign_class=False,
        send_notifications=False,
        update_existing=False,
        created_by=None,
    ):
        """
        Enhanced import students from a CSV file with improved UX

        Args:
            csv_file: CSV file with student data
            target_class: Optional Class instance to assign all students
            academic_year: Academic year for the import
            auto_assign_class: Whether to auto-assign students to target_class
            send_notifications: Send email notifications (only if email exists)
            update_existing: Update existing students
            created_by: User who initiated the import
        """
        created_count = 0
        updated_count = 0
        error_count = 0
        errors = []
        warnings = []
        success_emails = []

        try:
            decoded_file = csv_file.read().decode("utf-8")
            io_string = io.StringIO(decoded_file)
            reader = csv.DictReader(io_string)

            # Validate target class if provided
            if target_class and academic_year:
                if target_class.academic_year != academic_year:
                    raise ValidationError(
                        "Target class must belong to the selected academic year"
                    )

            for row_num, row in enumerate(reader, start=2):
                try:
                    with transaction.atomic():
                        # Validate required fields
                        required_fields = [
                            "first_name",
                            "last_name",
                            "admission_number",
                        ]
                        missing_fields = [
                            field
                            for field in required_fields
                            if not row.get(field, "").strip()
                        ]

                        if missing_fields:
                            raise ValueError(
                                f"Missing required fields: {', '.join(missing_fields)}"
                            )

                        admission_number = row.get("admission_number").strip()

                        # Check for existing student
                        existing_user = User.objects.filter(
                            username=admission_number
                        ).first()
                        existing_student = None

                        if existing_user and hasattr(existing_user, "student_profile"):
                            existing_student = existing_user.student_profile

                        if existing_student and not update_existing:
                            warnings.append(
                                f"Row {row_num}: Student with admission number {admission_number} already exists (skipped)"
                            )
                            continue

                        # Prepare user data
                        user_data = {
                            "username": admission_number,
                            "first_name": row.get("first_name", "").strip(),
                            "last_name": row.get("last_name", "").strip(),
                            "email": row.get("email", "").strip(),
                            "phone_number": row.get("phone_number", "").strip(),
                        }

                        # Handle class assignment logic
                        student_class = None

                        # Priority 1: Use class_id from CSV if provided
                        class_id = (
                            row.get("class_id", "").strip()
                            or row.get("current_class_id", "").strip()
                        )
                        if class_id:
                            try:
                                from academics.models import Class

                                student_class = Class.objects.get(
                                    id=int(class_id), is_active=True
                                )
                            except (Class.DoesNotExist, ValueError):
                                if auto_assign_class and target_class:
                                    student_class = target_class
                                    warnings.append(
                                        f"Row {row_num}: Invalid class_id {class_id}, assigned to target class {target_class.display_name}"
                                    )
                                else:
                                    warnings.append(
                                        f"Row {row_num}: Invalid class_id {class_id}, student will not be assigned to any class"
                                    )

                        # Priority 2: Use target class if auto_assign is enabled
                        elif auto_assign_class and target_class:
                            student_class = target_class

                        # Prepare student data
                        student_data = {
                            "admission_number": admission_number,
                            "admission_date": timezone.now().date(),
                            "current_class": student_class,
                            "emergency_contact_name": row.get(
                                "emergency_contact_name", ""
                            ).strip(),
                            "emergency_contact_number": row.get(
                                "emergency_contact_number", ""
                            ).strip(),
                            "blood_group": row.get("blood_group", "Unknown").strip(),
                            "status": row.get("status", "Active").strip(),
                        }

                        # Optional fields
                        optional_fields = [
                            "roll_number",
                            "nationality",
                            "religion",
                            "city",
                            "state",
                            "country",
                            "medical_conditions",
                            "date_of_birth",
                        ]
                        for field in optional_fields:
                            if row.get(field, "").strip():
                                student_data[field] = row.get(field).strip()

                        # Handle date fields
                        if row.get("admission_date", "").strip():
                            try:
                                from datetime import datetime

                                admission_date = datetime.strptime(
                                    row.get("admission_date").strip(), "%Y-%m-%d"
                                ).date()
                                student_data["admission_date"] = admission_date
                            except ValueError:
                                warnings.append(
                                    f"Row {row_num}: Invalid date format for admission_date, using current date"
                                )

                        if existing_student:
                            # Update existing student
                            existing_user.first_name = user_data["first_name"]
                            existing_user.last_name = user_data["last_name"]

                            # Only update email if provided and not empty
                            if user_data["email"]:
                                existing_user.email = user_data["email"]

                            # Only update phone if provided and not empty
                            if user_data["phone_number"]:
                                existing_user.phone_number = user_data["phone_number"]

                            existing_user.save()

                            # Update student profile
                            for key, value in student_data.items():
                                if (
                                    key != "admission_number" and value
                                ):  # Don't update with empty values
                                    setattr(existing_student, key, value)

                            existing_student.save()
                            updated_count += 1

                            logger.info(f"Updated student: {admission_number}")

                        else:
                            # Create new user
                            user = User.objects.create_user(
                                username=user_data["username"],
                                email=user_data["email"],
                                first_name=user_data["first_name"],
                                last_name=user_data["last_name"],
                                phone_number=user_data["phone_number"],
                            )

                            # Create student profile
                            student_data["user"] = user
                            student_data["created_by"] = created_by

                            from students.models import Student

                            student = Student.objects.create(**student_data)

                            # Assign student role
                            from accounts.services import RoleService

                            RoleService.assign_role_to_user(user, "Student")

                            created_count += 1
                            logger.info(f"Created student: {admission_number}")

                        # Collect email for notifications if email exists
                        if send_notifications and user_data["email"]:
                            success_emails.append(user_data["email"])

                except Exception as e:
                    error_count += 1
                    error_msg = f"Row {row_num}: {str(e)}"
                    errors.append(error_msg)
                    logger.error(f"Error processing row {row_num}: {str(e)}")
                    continue

            # Send notifications if requested
            if send_notifications and success_emails:
                try:
                    StudentService._send_bulk_welcome_emails(success_emails, created_by)
                except Exception as e:
                    warnings.append(f"Notifications sent with some errors: {str(e)}")

            # Prepare results summary
            result = {
                "success": True,
                "created_count": created_count,
                "updated_count": updated_count,
                "error_count": error_count,
                "errors": errors,
                "warnings": warnings,
                "total_processed": created_count + updated_count + error_count,
            }

            if target_class:
                result["target_class"] = {
                    "id": target_class.id,
                    "name": target_class.display_name,
                    "assigned_count": (
                        created_count + updated_count if auto_assign_class else 0
                    ),
                }

            return result

        except Exception as e:
            logger.error(f"Bulk import failed: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "created_count": created_count,
                "updated_count": updated_count,
                "error_count": error_count,
            }

    @staticmethod
    def update_student(student, student_data, user_data=None, updated_by=None):
        """
        Update a student and associated user account

        Args:
            student (Student): Student instance to update
            student_data (dict): Student model fields
            user_data (dict): User model fields (optional)
            updated_by (User): User updating the student

        Returns:
            Student: The updated student instance
        """
        with transaction.atomic():
            try:
                # Update user data if provided
                if user_data and student.user:
                    for key, value in user_data.items():
                        if key == "password" and value:
                            student.user.set_password(value)
                        elif key != "password":
                            setattr(student.user, key, value)
                    student.user.save()

                # Update student data
                for key, value in student_data.items():
                    if key != "user":
                        setattr(student, key, value)

                student.save()

                # Clear related cache
                cache_keys = [
                    f"student_attendance_percentage_{student.id}",
                    f"student_siblings_{student.id}",
                    f"student_parents_{student.id}",
                ]
                cache.delete_many(cache_keys)

                logger.info(f"Updated student: {student.admission_number}")
                return student

            except Exception as e:
                logger.error(
                    f"Error updating student {student.admission_number}: {str(e)}"
                )
                raise

    @staticmethod
    def _send_bulk_welcome_emails(email_list, created_by=None):
        """Send welcome emails to successfully imported students"""
        # Implementation depends on your email service
        # This is a placeholder for the actual email sending logic
        from django.core.mail import send_mass_mail

        messages = []
        for email in email_list:
            message = (
                "Welcome to Our School",
                "Welcome! Your student account has been created successfully.",
                "noreply@school.com",
                [email],
            )
            messages.append(message)

        if messages:
            send_mass_mail(messages, fail_silently=True)

    @staticmethod
    def generate_student_id_card(student):
        """
        Generate an enhanced PDF ID card for a student

        Args:
            student (Student): Student instance

        Returns:
            str: Path to the generated PDF file
        """
        try:
            # Create file path
            filename = (
                f"student_id_{student.admission_number}_{uuid.uuid4().hex[:8]}.pdf"
            )
            filepath = os.path.join(settings.MEDIA_ROOT, "id_cards", filename)
            os.makedirs(os.path.dirname(filepath), exist_ok=True)

            # Create PDF document
            doc = SimpleDocTemplate(
                filepath,
                pagesize=letter,
                rightMargin=30,
                leftMargin=30,
                topMargin=30,
                bottomMargin=30,
            )

            # Prepare content
            styles = getSampleStyleSheet()
            content = []

            # School header
            school_name = getattr(settings, "SCHOOL_NAME", "School Management System")
            header_style = ParagraphStyle(
                "CustomHeader",
                parent=styles["Heading1"],
                fontSize=18,
                textColor=colors.darkblue,
                alignment=1,  # Center alignment
                spaceAfter=10,
            )
            content.append(Paragraph(school_name, header_style))
            content.append(Paragraph("STUDENT IDENTIFICATION CARD", styles["Heading2"]))
            content.append(Spacer(1, 20))

            # Student information table
            data = [
                ["Name:", student.get_full_name()],
                ["Admission No:", student.admission_number],
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

            # Add parent information
            primary_parent = student.get_primary_parent()
            if primary_parent:
                data.extend(
                    [
                        ["Parent/Guardian:", primary_parent.get_full_name()],
                        [
                            "Parent Phone:",
                            primary_parent.user.phone_number or "Not provided",
                        ],
                    ]
                )

            # Create table
            table = Table(data, colWidths=[2 * 72, 4 * 72])
            table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (0, -1), colors.lightgrey),
                        ("TEXTCOLOR", (0, 0), (-1, -1), colors.black),
                        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                        ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
                        ("FONTSIZE", (0, 0), (-1, -1), 10),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                        ("TOPPADDING", (0, 0), (-1, -1), 8),
                        ("GRID", (0, 0), (-1, -1), 1, colors.black),
                    ]
                )
            )

            content.append(table)
            content.append(Spacer(1, 30))

            # Generate QR code with student information
            qr_data = f"Student:{student.admission_number}|Name:{student.get_full_name()}|Class:{student.current_class}"
            qr = qrcode.QRCode(version=1, box_size=4, border=1)
            qr.add_data(qr_data)
            qr.make(fit=True)

            qr_img = qr.make_image(fill_color="black", back_color="white")
            qr_path = os.path.join(
                settings.MEDIA_ROOT, "temp", f"qr_{student.admission_number}.png"
            )
            os.makedirs(os.path.dirname(qr_path), exist_ok=True)
            qr_img.save(qr_path)

            # Add QR code to PDF
            from reportlab.platypus import Image

            qr_image = Image(qr_path, width=1 * 72, height=1 * 72)
            content.append(qr_image)

            # Add validity information
            content.append(Spacer(1, 20))
            issue_date = timezone.now().date()
            expiry_date = issue_date.replace(year=issue_date.year + 1)

            validity_style = ParagraphStyle(
                "Validity",
                parent=styles["Normal"],
                fontSize=9,
                alignment=1,
            )

            content.append(
                Paragraph(f"Issued: {issue_date.strftime('%d/%m/%Y')}", validity_style)
            )
            content.append(
                Paragraph(
                    f"Valid Until: {expiry_date.strftime('%d/%m/%Y')}", validity_style
                )
            )

            # Add footer
            content.append(Spacer(1, 30))
            footer_style = ParagraphStyle(
                "Footer",
                parent=styles["Normal"],
                fontSize=8,
                alignment=1,
                textColor=colors.grey,
            )
            content.append(
                Paragraph(
                    "This card is the property of the school. If found, please return to the school office.",
                    footer_style,
                )
            )

            # Build PDF
            doc.build(content)

            # Clean up QR code temp file
            if os.path.exists(qr_path):
                os.remove(qr_path)

            # Return relative path
            relative_path = os.path.join("id_cards", filename)
            logger.info(f"Generated ID card for student: {student.admission_number}")
            return relative_path

        except Exception as e:
            logger.error(
                f"Error generating ID card for {student.admission_number}: {str(e)}"
            )
            raise

    @staticmethod
    def promote_students(students, new_class, send_notifications=False):
        """
        Promote multiple students to a new class

        Args:
            students (QuerySet): Student instances
            new_class (Class): The new class
            send_notifications (bool): Send notification emails

        Returns:
            dict: Promotion statistics
        """
        promoted_count = 0
        errors = []
        promoted_students = []

        with transaction.atomic():
            for student in students:
                try:
                    old_class = student.current_class
                    student.promote_to_next_class(new_class)
                    promoted_count += 1
                    promoted_students.append(
                        {
                            "student": student,
                            "old_class": old_class,
                            "new_class": new_class,
                        }
                    )
                except Exception as e:
                    errors.append(
                        {"student": student.admission_number, "error": str(e)}
                    )
                    logger.error(
                        f"Error promoting student {student.admission_number}: {str(e)}"
                    )

        # Send notification emails
        if send_notifications and promoted_students:
            StudentService._send_promotion_notifications(promoted_students)

        logger.info(f"Promoted {promoted_count} students to {new_class}")
        return {
            "promoted": promoted_count,
            "errors": len(errors),
            "error_details": errors,
        }

    @staticmethod
    def _send_promotion_notifications(promoted_students):
        """Send promotion notification emails"""
        try:
            for item in promoted_students:
                student = item["student"]
                try:
                    # Send to student
                    send_mail(
                        subject="Class Promotion Notification",
                        message=render_to_string(
                            "emails/student_promotion.txt",
                            {
                                "student": student,
                                "old_class": item["old_class"],
                                "new_class": item["new_class"],
                            },
                        ),
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[student.user.email],
                        fail_silently=True,
                    )

                    # Send to parents
                    for parent in student.get_parents():
                        send_mail(
                            subject=f"Class Promotion - {student.get_full_name()}",
                            message=render_to_string(
                                "emails/parent_promotion_notification.txt",
                                {
                                    "student": student,
                                    "parent": parent,
                                    "old_class": item["old_class"],
                                    "new_class": item["new_class"],
                                },
                            ),
                            from_email=settings.DEFAULT_FROM_EMAIL,
                            recipient_list=[parent.user.email],
                            fail_silently=True,
                        )
                except Exception as e:
                    logger.error(
                        f"Failed to send promotion notification for {student.admission_number}: {str(e)}"
                    )
        except Exception as e:
            logger.error(f"Error in promotion notifications: {str(e)}")

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
