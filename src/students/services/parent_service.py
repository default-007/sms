# students/services/parent_service.py
import csv
import io
import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.mail import send_mail
from django.db import transaction
from django.template.loader import render_to_string
from django.utils import timezone

from ..models import Parent, Student, StudentParentRelation

User = get_user_model()
logger = logging.getLogger(__name__)


class ParentService:
    @staticmethod
    def create_parent(parent_data, user_data=None, created_by=None):
        """
        Create a new parent with associated user account

        Args:
            parent_data (dict): Parent model fields
            user_data (dict): User model fields (optional)
            created_by (User): User creating the parent

        Returns:
            Parent: The created parent instance
        """
        with transaction.atomic():
            try:
                # Create or get user account
                if user_data:
                    email = user_data.get("email")
                    if email and User.objects.filter(email=email).exists():
                        user = User.objects.get(email=email)
                        # Update existing user
                        for key, value in user_data.items():
                            if key != "password":
                                setattr(user, key, value)
                    else:
                        # Create new user
                        password = user_data.pop("password", None)
                        user = User.objects.create(**user_data)
                        if password:
                            user.set_password(password)
                        else:
                            user.set_password(User.objects.make_random_password())
                        user.save()
                else:
                    user = parent_data.get("user")

                # Create parent profile
                parent_data = {k: v for k, v in parent_data.items() if k != "user"}
                parent_data["user"] = user
                parent_data["created_by"] = created_by

                parent = Parent.objects.create(**parent_data)

                # Assign parent role
                from src.accounts.services import RoleService

                RoleService.assign_role_to_user(user, "Parent")

                logger.info(f"Created parent: {parent.get_full_name()}")
                return parent

            except Exception as e:
                logger.error(f"Error creating parent: {str(e)}")
                raise

    @staticmethod
    def update_parent(parent, parent_data, user_data=None, updated_by=None):
        """
        Update a parent and associated user account

        Args:
            parent (Parent): Parent instance to update
            parent_data (dict): Parent model fields
            user_data (dict): User model fields (optional)
            updated_by (User): User updating the parent

        Returns:
            Parent: The updated parent instance
        """
        with transaction.atomic():
            try:
                # Update user data if provided
                if user_data and parent.user:
                    for key, value in user_data.items():
                        if key == "password" and value:
                            parent.user.set_password(value)
                        elif key != "password":
                            setattr(parent.user, key, value)
                    parent.user.save()

                # Update parent data
                for key, value in parent_data.items():
                    if key != "user":
                        setattr(parent, key, value)

                parent.save()

                logger.info(f"Updated parent: {parent.get_full_name()}")
                return parent

            except Exception as e:
                logger.error(
                    f"Error updating parent {parent.get_full_name()}: {str(e)}"
                )
                raise

    @staticmethod
    def link_parent_to_student(
        parent, student, is_primary_contact=False, created_by=None, **kwargs
    ):
        """
        Create a relationship between a parent and a student

        Args:
            parent (Parent): Parent instance
            student (Student): Student instance
            is_primary_contact (bool): Whether this parent is the primary contact
            created_by (User): User creating the relationship
            **kwargs: Additional relationship attributes

        Returns:
            StudentParentRelation: The created relationship
        """
        try:
            # Check if relationship already exists
            existing_relation = StudentParentRelation.objects.filter(
                parent=parent, student=student
            ).first()

            if existing_relation:
                # Update existing relationship
                if is_primary_contact and not existing_relation.is_primary_contact:
                    existing_relation.is_primary_contact = True
                    existing_relation.save()

                for key, value in kwargs.items():
                    if hasattr(existing_relation, key):
                        setattr(existing_relation, key, value)

                existing_relation.save()
                return existing_relation

            # Create new relationship
            relation_data = {
                "parent": parent,
                "student": student,
                "is_primary_contact": is_primary_contact,
                "created_by": created_by,
                **kwargs,
            }

            relation = StudentParentRelation.objects.create(**relation_data)

            # Clear related cache
            cache.delete_many(
                [
                    f"student_parents_{student.id}",
                    f"student_siblings_{student.id}",
                ]
            )

            logger.info(
                f"Linked parent {parent.get_full_name()} to student {student.admission_number}"
            )
            return relation

        except Exception as e:
            logger.error(f"Error linking parent to student: {str(e)}")
            raise

    @staticmethod
    def bulk_import_parents(
        csv_file, send_notifications=False, update_existing=False, created_by=None
    ):
        """
        Import parents from a CSV file

        Args:
            csv_file: CSV file with parent data
            send_notifications (bool): Send email notifications
            update_existing (bool): Update existing parents
            created_by (User): User performing the import

        Returns:
            dict: Detailed import statistics
        """
        created_count = 0
        updated_count = 0
        error_count = 0
        errors = []
        linked_count = 0

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
                            "email",
                            "relation_with_student",
                        ]
                        missing_fields = [
                            field for field in required_fields if not row.get(field)
                        ]

                        if missing_fields:
                            raise ValueError(
                                f"Missing required fields: {', '.join(missing_fields)}"
                            )

                        # Prepare user data
                        user_data = {
                            "username": row.get("email"),
                            "email": row.get("email"),
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

                        # Prepare parent data
                        parent_data = {
                            "relation_with_student": row.get("relation_with_student"),
                            "occupation": row.get("occupation", ""),
                            "workplace": row.get("workplace", ""),
                            "work_address": row.get("work_address", ""),
                            "work_phone": row.get("work_phone", ""),
                            "education": row.get("education", ""),
                            "emergency_contact": row.get(
                                "emergency_contact", ""
                            ).lower()
                            in ("true", "yes", "1"),
                            "annual_income": None,
                        }

                        # Parse annual income
                        if row.get("annual_income"):
                            try:
                                parent_data["annual_income"] = float(
                                    row["annual_income"]
                                )
                            except ValueError:
                                pass

                        # Check if parent exists
                        existing_parent = Parent.objects.filter(
                            user__email=user_data["email"]
                        ).first()

                        if existing_parent:
                            if update_existing:
                                ParentService.update_parent(
                                    existing_parent, parent_data, user_data, created_by
                                )
                                updated_count += 1
                                parent = existing_parent
                            else:
                                raise ValueError(
                                    "Parent with this email already exists"
                                )
                        else:
                            parent = ParentService.create_parent(
                                parent_data, user_data, created_by
                            )
                            created_count += 1

                        # Link to student if student admission number provided
                        student_admission_number = row.get("student_admission_number")
                        if student_admission_number:
                            try:
                                student = Student.objects.get(
                                    admission_number=student_admission_number
                                )

                                # Parse relationship attributes
                                is_primary = row.get(
                                    "is_primary_contact", ""
                                ).lower() in ("true", "yes", "1")
                                can_pickup = row.get("can_pickup", "").lower() in (
                                    "true",
                                    "yes",
                                    "1",
                                )
                                financial_responsibility = row.get(
                                    "financial_responsibility", ""
                                ).lower() in ("true", "yes", "1")

                                # Create relationship
                                ParentService.link_parent_to_student(
                                    parent=parent,
                                    student=student,
                                    is_primary_contact=is_primary,
                                    can_pickup=can_pickup,
                                    financial_responsibility=financial_responsibility,
                                    created_by=created_by,
                                )
                                linked_count += 1

                            except Student.DoesNotExist:
                                logger.warning(
                                    f"Student {student_admission_number} not found for parent {parent.get_full_name()}"
                                )

                except Exception as e:
                    error_count += 1
                    errors.append({"row": row_num, "data": dict(row), "error": str(e)})
                    logger.error(f"Error processing parent row {row_num}: {str(e)}")

            # Send welcome emails if enabled
            if send_notifications and created_count > 0:
                ParentService._send_bulk_welcome_emails(
                    Parent.objects.filter(created_by=created_by)
                )

        except Exception as e:
            logger.error(f"Critical error during parent bulk import: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "created": 0,
                "updated": 0,
                "linked": 0,
                "errors": 0,
                "error_details": [],
            }

        return {
            "success": True,
            "created": created_count,
            "updated": updated_count,
            "linked": linked_count,
            "errors": error_count,
            "error_details": errors,
            "total_processed": created_count + updated_count + error_count,
        }

    @staticmethod
    def _send_bulk_welcome_emails(parents):
        """Send welcome emails to newly created parents"""
        try:
            for parent in parents:
                try:
                    send_mail(
                        subject=f'Parent Account Created - {getattr(settings, "SCHOOL_NAME", "School")}',
                        message=render_to_string(
                            "emails/parent_welcome.txt",
                            {
                                "parent": parent,
                                "school_name": getattr(
                                    settings, "SCHOOL_NAME", "School"
                                ),
                            },
                        ),
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[parent.user.email],
                        fail_silently=False,
                    )
                except Exception as e:
                    logger.error(
                        f"Failed to send welcome email to {parent.user.email}: {str(e)}"
                    )
        except Exception as e:
            logger.error(f"Error in bulk email sending: {str(e)}")

    @staticmethod
    def export_parents_to_csv(queryset):
        """
        Export parents to CSV with enhanced data

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
            "date_of_birth",
            "relation_with_student",
            "occupation",
            "education",
            "workplace",
            "work_address",
            "work_phone",
            "annual_income",
            "emergency_contact",
            "students",
            "primary_students",
            "created_at",
        ]

        csv_buffer = io.StringIO()
        writer = csv.DictWriter(csv_buffer, fieldnames=fieldnames)
        writer.writeheader()

        for parent in queryset.prefetch_related("parent_student_relations__student"):
            # Get related students
            all_students = [
                rel.student for rel in parent.parent_student_relations.all()
            ]
            primary_students = [
                rel.student
                for rel in parent.parent_student_relations.filter(
                    is_primary_contact=True
                )
            ]

            all_students_list = ", ".join(
                [student.admission_number for student in all_students]
            )
            primary_students_list = ", ".join(
                [student.admission_number for student in primary_students]
            )

            writer.writerow(
                {
                    "first_name": parent.user.first_name,
                    "last_name": parent.user.last_name,
                    "email": parent.user.email,
                    "phone_number": parent.user.phone_number or "",
                    "date_of_birth": parent.user.date_of_birth or "",
                    "relation_with_student": parent.relation_with_student,
                    "occupation": parent.occupation or "",
                    "education": parent.education or "",
                    "workplace": parent.workplace or "",
                    "work_address": parent.work_address or "",
                    "work_phone": parent.work_phone or "",
                    "annual_income": parent.annual_income or "",
                    "emergency_contact": "Yes" if parent.emergency_contact else "No",
                    "students": all_students_list,
                    "primary_students": primary_students_list,
                    "created_at": parent.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                }
            )

        return csv_buffer.getvalue()

    @staticmethod
    def get_parent_statistics():
        """Get comprehensive parent statistics"""
        total_parents = Parent.objects.count()

        stats = {
            "total_parents": total_parents,
            "fathers": Parent.objects.filter(relation_with_student="Father").count(),
            "mothers": Parent.objects.filter(relation_with_student="Mother").count(),
            "guardians": Parent.objects.filter(
                relation_with_student="Guardian"
            ).count(),
            "emergency_contacts": Parent.objects.filter(emergency_contact=True).count(),
            "parents_with_photos": Parent.objects.exclude(photo__isnull=True)
            .exclude(photo="")
            .count(),
            "parents_with_multiple_children": Parent.objects.annotate(
                child_count=Count("parent_student_relations")
            )
            .filter(child_count__gt=1)
            .count(),
            "parents_with_work_info": Parent.objects.exclude(workplace__isnull=True)
            .exclude(workplace="")
            .count(),
        }

        # Calculate percentages
        if total_parents > 0:
            stats["emergency_percentage"] = round(
                (stats["emergency_contacts"] / total_parents) * 100, 1
            )
            stats["completion_percentage"] = round(
                (stats["parents_with_photos"] / total_parents) * 100, 1
            )
        else:
            stats["emergency_percentage"] = 0
            stats["completion_percentage"] = 0

        return stats

    @staticmethod
    def get_family_overview(parent):
        """Get comprehensive family overview for a parent"""
        relations = parent.parent_student_relations.select_related(
            "student__user", "student__current_class"
        ).prefetch_related("student__student_parent_relations__parent__user")

        family_overview = {
            "parent": parent,
            "children": [],
            "total_children": relations.count(),
            "primary_contacts": relations.filter(is_primary_contact=True).count(),
            "financial_responsibility": relations.filter(
                financial_responsibility=True
            ).count(),
        }

        for relation in relations:
            student = relation.student

            # Get all parents for this student
            other_parents = []
            for other_relation in student.student_parent_relations.exclude(
                parent=parent
            ):
                other_parents.append(
                    {
                        "parent": other_relation.parent,
                        "relation": other_relation.parent.relation_with_student,
                        "is_primary": other_relation.is_primary_contact,
                    }
                )

            family_overview["children"].append(
                {
                    "student": student,
                    "relation": relation,
                    "other_parents": other_parents,
                    "is_primary": relation.is_primary_contact,
                    "permissions": {
                        "can_pickup": relation.can_pickup,
                        "financial_responsibility": relation.financial_responsibility,
                        "access_to_grades": relation.access_to_grades,
                        "access_to_attendance": relation.access_to_attendance,
                        "access_to_financial_info": relation.access_to_financial_info,
                    },
                }
            )

        return family_overview

    @staticmethod
    def update_communication_preferences(parent, preferences):
        """Update communication preferences for all relationships of a parent"""
        try:
            relations = parent.parent_student_relations.all()

            for relation in relations:
                for key, value in preferences.items():
                    if hasattr(relation, key):
                        setattr(relation, key, value)
                relation.save()

            logger.info(
                f"Updated communication preferences for parent {parent.get_full_name()}"
            )
            return True

        except Exception as e:
            logger.error(f"Error updating communication preferences: {str(e)}")
            raise

    @staticmethod
    def search_parents(query, filters=None):
        """
        Advanced parent search with filters

        Args:
            query (str): Search query
            filters (dict): Additional filters

        Returns:
            QuerySet: Filtered parents
        """
        parents = Parent.objects.with_related()

        if query:
            parents = parents.search(query)

        if filters:
            if filters.get("relation"):
                parents = parents.filter(relation_with_student=filters["relation"])

            if filters.get("emergency_contact") is not None:
                parents = parents.filter(emergency_contact=filters["emergency_contact"])

            if filters.get("has_multiple_children"):
                from django.db.models import Count

                parents = parents.annotate(
                    child_count=Count("parent_student_relations")
                ).filter(child_count__gt=1)

        return parents.order_by("user__first_name", "user__last_name")

    @staticmethod
    def generate_parent_report(parent):
        """Generate a comprehensive report for a parent"""
        family_overview = ParentService.get_family_overview(parent)

        report_data = {
            "parent_info": {
                "name": parent.get_full_name(),
                "email": parent.user.email,
                "phone": parent.user.phone_number,
                "relation": parent.relation_with_student,
                "occupation": parent.occupation,
                "workplace": parent.workplace,
            },
            "family_overview": family_overview,
            "communication_summary": {
                "total_relationships": family_overview["total_children"],
                "primary_contacts": family_overview["primary_contacts"],
                "emergency_priority": (
                    min(
                        [
                            rel.emergency_contact_priority
                            for rel in parent.parent_student_relations.all()
                        ]
                    )
                    if parent.parent_student_relations.exists()
                    else None
                ),
            },
            "permissions_summary": {
                "can_pickup_count": parent.parent_student_relations.filter(
                    can_pickup=True
                ).count(),
                "financial_responsibility_count": parent.parent_student_relations.filter(
                    financial_responsibility=True
                ).count(),
                "grade_access_count": parent.parent_student_relations.filter(
                    access_to_grades=True
                ).count(),
                "attendance_access_count": parent.parent_student_relations.filter(
                    access_to_attendance=True
                ).count(),
            },
        }

        return report_data

    @staticmethod
    def merge_parent_accounts(primary_parent, duplicate_parent):
        """Merge two parent accounts, keeping the primary and removing the duplicate"""
        try:
            with transaction.atomic():
                # Transfer all relationships to primary parent
                duplicate_relations = duplicate_parent.parent_student_relations.all()

                for relation in duplicate_relations:
                    # Check if primary parent already has relationship with this student
                    existing_relation = StudentParentRelation.objects.filter(
                        parent=primary_parent, student=relation.student
                    ).first()

                    if existing_relation:
                        # Update existing relation with duplicate's information if needed
                        if (
                            relation.is_primary_contact
                            and not existing_relation.is_primary_contact
                        ):
                            existing_relation.is_primary_contact = True
                            existing_relation.save()
                        # Delete duplicate relation
                        relation.delete()
                    else:
                        # Transfer relation to primary parent
                        relation.parent = primary_parent
                        relation.save()

                # Delete duplicate parent and user
                duplicate_user = duplicate_parent.user
                duplicate_parent.delete()
                duplicate_user.delete()

                logger.info(
                    f"Merged parent {duplicate_parent.get_full_name()} into {primary_parent.get_full_name()}"
                )
                return True

        except Exception as e:
            logger.error(f"Error merging parent accounts: {str(e)}")
            raise
