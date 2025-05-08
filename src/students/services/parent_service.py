# students/services/parent_service.py
from django.db import transaction
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone
import csv
import io

from ..models import Parent, StudentParentRelation, Student

User = get_user_model()


class ParentService:
    @staticmethod
    def create_parent(parent_data, user_data=None):
        """
        Create a new parent with associated user account

        Args:
            parent_data (dict): Parent model fields
            user_data (dict): User model fields (optional)

        Returns:
            Parent: The created parent instance
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
                # Use existing user if provided in parent_data
                user = parent_data.get("user")

            # Create parent profile
            if "user" in parent_data:
                del parent_data["user"]

            parent = Parent.objects.create(user=user, **parent_data)

            # Ensure user has parent role
            from src.accounts.services import RoleService

            RoleService.assign_role_to_user(user, "Parent")

            return parent

    @staticmethod
    def update_parent(parent, parent_data, user_data=None):
        """
        Update a parent and associated user account

        Args:
            parent (Parent): Parent instance to update
            parent_data (dict): Parent model fields
            user_data (dict): User model fields (optional)

        Returns:
            Parent: The updated parent instance
        """
        with transaction.atomic():
            # Update user data if provided
            if user_data and parent.user:
                for key, value in user_data.items():
                    if key != "password":
                        setattr(parent.user, key, value)

                if "password" in user_data and user_data["password"]:
                    parent.user.set_password(user_data["password"])

                parent.user.save()

            # Update parent data
            for key, value in parent_data.items():
                if key != "user":
                    setattr(parent, key, value)

            parent.save()
            return parent

    @staticmethod
    def link_parent_to_student(parent, student, is_primary_contact=False, **kwargs):
        """
        Create a relationship between a parent and a student

        Args:
            parent (Parent): Parent instance
            student (Student): Student instance
            is_primary_contact (bool): Whether this parent is the primary contact
            **kwargs: Additional relationship attributes

        Returns:
            StudentParentRelation: The created relationship
        """
        # Check if relationship already exists
        relation, created = StudentParentRelation.objects.get_or_create(
            parent=parent,
            student=student,
            defaults={"is_primary_contact": is_primary_contact, **kwargs},
        )

        if not created and is_primary_contact and not relation.is_primary_contact:
            # Update existing relationship to make this parent the primary contact
            relation.is_primary_contact = True
            relation.save()

        return relation

    @staticmethod
    def bulk_import_parents(csv_file):
        """
        Import parents from a CSV file

        Args:
            csv_file: CSV file with parent data

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
                            "phone_number": row.get("phone_number", ""),
                            "password": row.get(
                                "password", User.objects.make_random_password()
                            ),
                        }

                        # Extract and prepare parent data
                        parent_data = {
                            "occupation": row.get("occupation", ""),
                            "relation_with_student": row.get(
                                "relation_with_student", "Guardian"
                            ),
                            "workplace": row.get("workplace", ""),
                            "work_address": row.get("work_address", ""),
                            "work_phone": row.get("work_phone", ""),
                        }

                        # Check if parent already exists by email
                        existing_user = User.objects.filter(
                            email=user_data["email"]
                        ).first()
                        if existing_user and hasattr(existing_user, "parent_profile"):
                            # Update existing parent
                            parent = existing_user.parent_profile
                            ParentService.update_parent(parent, parent_data, user_data)
                            updated_count += 1
                        else:
                            # Create new parent
                            ParentService.create_parent(parent_data, user_data)
                            created_count += 1

                        # Link to student if student admission number provided
                        student_admission_number = row.get("student_admission_number")
                        if student_admission_number:
                            try:
                                student = Student.objects.get(
                                    admission_number=student_admission_number
                                )
                                parent = Parent.objects.get(
                                    user__email=user_data["email"]
                                )

                                is_primary = row.get(
                                    "is_primary_contact", ""
                                ).lower() in ("true", "yes", "1")
                                ParentService.link_parent_to_student(
                                    parent,
                                    student,
                                    is_primary_contact=is_primary,
                                    can_pickup=row.get("can_pickup", "").lower()
                                    in ("true", "yes", "1"),
                                    financial_responsibility=row.get(
                                        "financial_responsibility", ""
                                    ).lower()
                                    in ("true", "yes", "1"),
                                )
                            except Student.DoesNotExist:
                                pass

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
    def export_parents_to_csv(queryset):
        """
        Export parents to CSV

        Args:
            queryset: QuerySet of Parent objects

        Returns:
            str: CSV content as string
        """
        fieldnames = [
            "first_name",
            "last_name",
            "email",
            "phone_number",
            "relation_with_student",
            "occupation",
            "workplace",
            "work_address",
            "work_phone",
            "emergency_contact",
            "students",
        ]

        csv_buffer = io.StringIO()
        writer = csv.DictWriter(csv_buffer, fieldnames=fieldnames)
        writer.writeheader()

        for parent in queryset:
            # Get related students
            students = parent.get_students()
            student_list = ", ".join([student.admission_number for student in students])

            writer.writerow(
                {
                    "first_name": parent.user.first_name,
                    "last_name": parent.user.last_name,
                    "email": parent.user.email,
                    "phone_number": parent.user.phone_number or "",
                    "relation_with_student": parent.relation_with_student,
                    "occupation": parent.occupation or "",
                    "workplace": parent.workplace or "",
                    "work_address": parent.work_address or "",
                    "work_phone": parent.work_phone or "",
                    "emergency_contact": "Yes" if parent.emergency_contact else "No",
                    "students": student_list,
                }
            )

        return csv_buffer.getvalue()
