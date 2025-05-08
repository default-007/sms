# students/services/student_service.py
from django.db import transaction
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone
import csv
import io
import uuid
import os
from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors

from ..models import Student, Parent, StudentParentRelation

User = get_user_model()


class StudentService:
    @staticmethod
    def create_student(student_data, user_data=None):
        """
        Create a new student with associated user account

        Args:
            student_data (dict): Student model fields
            user_data (dict): User model fields (optional)

        Returns:
            Student: The created student instance
        """
        with transaction.atomic():
            # Create or get user account
            if user_data:
                # Check if user already exists
                if (
                    "email" in user_data
                    and User.objects.filter(email=user_data["email"]).exists()
                ):
                    user = User.objects.get(email=user_data["email"])
                else:
                    # Create new user
                    password = user_data.pop("password", None)
                    user = User.objects.create(**user_data)
                    if password:
                        user.set_password(password)
                        user.save()
            else:
                # Use existing user if provided in student_data
                user = student_data.get("user")

            # Create student profile
            if "user" in student_data:
                del student_data["user"]

            student = Student.objects.create(user=user, **student_data)

            # Ensure user has student role
            from src.accounts.services import RoleService

            RoleService.assign_role_to_user(user, "Student")

            return student

    @staticmethod
    def update_student(student, student_data, user_data=None):
        """
        Update a student and associated user account

        Args:
            student (Student): Student instance to update
            student_data (dict): Student model fields
            user_data (dict): User model fields (optional)

        Returns:
            Student: The updated student instance
        """
        with transaction.atomic():
            # Update user data if provided
            if user_data and student.user:
                for key, value in user_data.items():
                    if key != "password":
                        setattr(student.user, key, value)

                if "password" in user_data and user_data["password"]:
                    student.user.set_password(user_data["password"])

                student.user.save()

            # Update student data
            for key, value in student_data.items():
                if key != "user":
                    setattr(student, key, value)

            student.save()
            return student

    @staticmethod
    def bulk_import_students(csv_file):
        """
        Import students from a CSV file

        Args:
            csv_file: CSV file with student data

        Returns:
            dict: Import statistics
        """
        created_count = 0
        updated_count = 0
        error_count = 0
        errors = []

        try:
            decoded_file = csv_file.read().decode("utf-8")
            io_string = io.StringIO(decoded_file)
            reader = csv.DictReader(io_string)

            for row in reader:
                try:
                    with transaction.atomic():
                        # Extract and prepare user data
                        user_data = {
                            "username": row.get("email", ""),
                            "email": row.get("email", ""),
                            "first_name": row.get("first_name", ""),
                            "last_name": row.get("last_name", ""),
                            "password": row.get(
                                "password", User.objects.make_random_password()
                            ),
                        }

                        # Extract and prepare student data
                        student_data = {
                            "admission_number": row.get("admission_number", ""),
                            "admission_date": row.get(
                                "admission_date", timezone.now().date()
                            ),
                            "blood_group": row.get("blood_group", "Unknown"),
                            "emergency_contact_name": row.get(
                                "emergency_contact_name", ""
                            ),
                            "emergency_contact_number": row.get(
                                "emergency_contact_number", ""
                            ),
                            "status": row.get("status", "Active"),
                        }

                        # Handle current class if provided
                        class_id = row.get("current_class_id")
                        if class_id:
                            from src.courses.models import Class

                            try:
                                student_data["current_class"] = Class.objects.get(
                                    id=class_id
                                )
                            except Class.DoesNotExist:
                                pass

                        # Check if student already exists by admission number
                        if Student.objects.filter(
                            admission_number=student_data["admission_number"]
                        ).exists():
                            # Update existing student
                            student = Student.objects.get(
                                admission_number=student_data["admission_number"]
                            )
                            StudentService.update_student(
                                student, student_data, user_data
                            )
                            updated_count += 1
                        else:
                            # Create new student
                            StudentService.create_student(student_data, user_data)
                            created_count += 1

                except Exception as e:
                    error_count += 1
                    errors.append({"row": row, "error": str(e)})

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "created": 0,
                "updated": 0,
                "errors": 0,
            }

        return {
            "success": True,
            "created": created_count,
            "updated": updated_count,
            "errors": error_count,
            "error_details": errors,
        }

    @staticmethod
    def generate_student_id_card(student):
        """
        Generate a PDF ID card for a student

        Args:
            student (Student): Student instance

        Returns:
            str: Path to the generated PDF file
        """
        # Create a file to save the ID card
        filename = f"student_id_{student.admission_number}_{uuid.uuid4()}.pdf"
        filepath = os.path.join(settings.MEDIA_ROOT, "id_cards", filename)

        # Ensure directory exists
        os.makedirs(os.path.dirname(filepath), exist_ok=True)

        # Create PDF
        c = canvas.Canvas(filepath, pagesize=A4)
        width, height = A4

        # Draw school logo
        logo_path = os.path.join(settings.STATIC_ROOT, "images/school_logo.png")
        if os.path.exists(logo_path):
            c.drawImage(logo_path, 50, height - 100, width=100, height=80)

        # Draw school name
        c.setFont("Helvetica-Bold", 18)
        school_name = (
            settings.SCHOOL_NAME
            if hasattr(settings, "SCHOOL_NAME")
            else "School Management System"
        )
        c.drawCentredString(width / 2, height - 70, school_name)

        # Draw ID card title
        c.setFont("Helvetica-Bold", 14)
        c.drawCentredString(width / 2, height - 90, "STUDENT IDENTIFICATION CARD")

        # Draw line separator
        c.line(50, height - 100, width - 50, height - 100)

        # Draw student photo if available
        if student.photo:
            photo_path = student.photo.path
            if os.path.exists(photo_path):
                c.drawImage(
                    photo_path, width / 2 - 50, height - 220, width=100, height=100
                )
        else:
            # Draw placeholder photo box
            c.rect(width / 2 - 50, height - 220, 100, 100)
            c.setFont("Helvetica", 10)
            c.drawCentredString(width / 2, height - 170, "Photo")

        # Draw student details
        c.setFont("Helvetica-Bold", 12)
        c.drawString(50, height - 250, f"Name: {student.get_full_name()}")
        c.drawString(50, height - 270, f"Admission No: {student.admission_number}")
        c.drawString(50, height - 290, f"Class: {student.current_class}")
        c.drawString(50, height - 310, f"Blood Group: {student.blood_group}")

        # Draw parent contact (if available)
        primary_parent = student.get_primary_parent()
        if primary_parent:
            c.drawString(
                50, height - 330, f"Emergency Contact: {primary_parent.get_full_name()}"
            )
            c.drawString(
                50, height - 350, f"Contact No: {primary_parent.user.phone_number}"
            )

        # Draw address
        address = student.get_full_address()
        if len(address) > 40:
            # Split address into multiple lines
            address_parts = [address[i : i + 40] for i in range(0, len(address), 40)]
            for i, part in enumerate(address_parts):
                c.drawString(50, height - 370 - (i * 20), part)
        else:
            c.drawString(50, height - 370, f"Address: {address}")

        # Draw barcode or QR code
        # (implementation depends on available libraries)

        # Draw validity period
        from datetime import datetime, timedelta

        issue_date = datetime.now()
        expiry_date = issue_date + timedelta(days=365)  # Valid for 1 year

        c.setFont("Helvetica", 10)
        c.drawString(50, height - 430, f"Issue Date: {issue_date.strftime('%d-%m-%Y')}")
        c.drawString(
            50, height - 450, f"Valid Until: {expiry_date.strftime('%d-%m-%Y')}"
        )

        # Draw signature boxes
        c.line(50, height - 500, 200, height - 500)
        c.drawCentredString(125, height - 510, "Student's Signature")

        c.line(width - 200, height - 500, width - 50, height - 500)
        c.drawCentredString(width - 125, height - 510, "Principal's Signature")

        # Draw footer
        c.setFont("Helvetica-Italic", 8)
        c.drawCentredString(
            width / 2,
            30,
            "This card is the property of the school. If found, please return to the school office.",
        )

        # Save the PDF
        c.save()

        # Return the relative path to the generated file
        relative_path = os.path.join("id_cards", filename)
        return relative_path

    @staticmethod
    def promote_students(students, new_class):
        """
        Promote multiple students to a new class

        Args:
            students (list): List of Student instances
            new_class (Class): The new class

        Returns:
            dict: Promotion statistics
        """
        promoted_count = 0
        errors = []

        with transaction.atomic():
            for student in students:
                try:
                    student.promote_to_next_class(new_class)
                    promoted_count += 1
                except Exception as e:
                    errors.append(
                        {"student": student.admission_number, "error": str(e)}
                    )

        return {
            "promoted": promoted_count,
            "errors": len(errors),
            "error_details": errors,
        }

    @staticmethod
    def graduate_students(students):
        """
        Mark multiple students as graduated

        Args:
            students (list): List of Student instances

        Returns:
            dict: Graduation statistics
        """
        graduated_count = 0
        errors = []

        with transaction.atomic():
            for student in students:
                try:
                    student.mark_as_graduated()
                    graduated_count += 1
                except Exception as e:
                    errors.append(
                        {"student": student.admission_number, "error": str(e)}
                    )

        return {
            "graduated": graduated_count,
            "errors": len(errors),
            "error_details": errors,
        }

    @staticmethod
    def export_students_to_csv(queryset):
        """
        Export students to CSV

        Args:
            queryset: QuerySet of Student objects

        Returns:
            str: CSV content as string
        """
        fieldnames = [
            "admission_number",
            "first_name",
            "last_name",
            "email",
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
        ]

        csv_buffer = io.StringIO()
        writer = csv.DictWriter(csv_buffer, fieldnames=fieldnames)
        writer.writeheader()

        for student in queryset:
            writer.writerow(
                {
                    "admission_number": student.admission_number,
                    "first_name": student.user.first_name,
                    "last_name": student.user.last_name,
                    "email": student.user.email,
                    "status": student.status,
                    "current_class": (
                        student.current_class.id if student.current_class else ""
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
                }
            )

        return csv_buffer.getvalue()
