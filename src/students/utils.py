# students/utils.py
from asyncio.log import logger
import base64
import hashlib
import io
import re
import uuid
from datetime import date, datetime

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils.text import slugify
from PIL import Image

User = get_user_model()


class StudentUtils:
    """Utility functions for student-related operations"""

    @staticmethod
    def generate_username_from_admission_number(admission_number):
        """
        Generate username from admission number (direct mapping)
        For students, username = admission_number
        """
        if not admission_number:
            return ""

        # For students, username is exactly the admission number
        # Validate format first
        if not StudentUtils.validate_admission_number(admission_number):
            raise ValidationError("Invalid admission number format")

        # Check if username already exists
        if User.objects.filter(username=admission_number).exists():
            raise ValidationError("This admission number is already in use")

        return admission_number

    @staticmethod
    def generate_username_from_email(email):
        """
        This method is kept for backward compatibility but not used for students
        Students now use admission number as username
        """
        logger.warning(
            "generate_username_from_email called for student - should use admission_number"
        )

        if not email:
            return ""

        # Use email as username, ensuring uniqueness
        username = email.lower()

        if not User.objects.filter(username=username).exists():
            return username

        # If email already exists as username, add a number
        base_username = username.split("@")[0]
        counter = 1

        while User.objects.filter(username=f"{base_username}{counter}").exists():
            counter += 1

        return f"{base_username}{counter}"

    @staticmethod
    def validate_student_username(username, admission_number):
        """
        Validate that student username matches admission number
        """
        if username != admission_number:
            raise ValidationError(
                "Student username must be the same as admission number"
            )

        if not StudentUtils.validate_admission_number(admission_number):
            raise ValidationError("Invalid admission number format")

        return True

    @staticmethod
    def is_student_username(username):
        """
        Check if a username follows student admission number pattern
        """
        return StudentUtils.validate_admission_number(username)

    @staticmethod
    def generate_admission_number(prefix="STU", year=None):
        """
        Generate a unique admission number

        Args:
            prefix (str): Prefix for admission number
            year (int): Year for admission (defaults to current year)

        Returns:
            str: Generated admission number
        """
        if year is None:
            year = datetime.now().year

        # Generate a unique identifier
        unique_id = str(uuid.uuid4().hex)[:6].upper()

        # Format: STU-2024-ABC123
        admission_number = f"{prefix}-{year}-{unique_id}"

        # Ensure uniqueness
        from .models import Student

        counter = 1
        original_number = admission_number

        while Student.objects.filter(admission_number=admission_number).exists():
            admission_number = f"{original_number}-{counter:02d}"
            counter += 1

        return admission_number

    @staticmethod
    def validate_admission_number(admission_number):
        """
        Validate admission number format

        Args:
            admission_number (str): Admission number to validate

        Returns:
            bool: True if valid, False otherwise
        """
        # Pattern: STU-YYYY-XXXXXX or similar
        pattern = r"^[A-Z]{2,5}-\d{4}-[A-Z0-9]{4,8}(-\d{2})?$"
        return bool(re.match(pattern, admission_number))

    @staticmethod
    def parse_name_components(full_name):
        """
        Parse full name into first and last name components

        Args:
            full_name (str): Full name string

        Returns:
            tuple: (first_name, last_name)
        """
        name_parts = full_name.strip().split()

        if len(name_parts) == 0:
            return "", ""
        elif len(name_parts) == 1:
            return name_parts[0], ""
        else:
            return name_parts[0], " ".join(name_parts[1:])

    @staticmethod
    def format_phone_number(phone):
        """
        Format phone number to a standard format

        Args:
            phone (str): Raw phone number

        Returns:
            str: Formatted phone number
        """
        if not phone:
            return ""

        # Remove all non-digit characters except +
        cleaned = re.sub(r"[^\d+]", "", phone)

        # Handle different formats
        if cleaned.startswith("+"):
            return cleaned
        elif cleaned.startswith("0"):
            # Remove leading 0 and add country code
            return f"+91{cleaned[1:]}"  # Assuming India (+91)
        elif len(cleaned) == 10:
            return f"+91{cleaned}"
        else:
            return cleaned

    @staticmethod
    def calculate_age(date_of_birth):
        """
        Calculate age from date of birth

        Args:
            date_of_birth (date): Date of birth

        Returns:
            int: Age in years
        """
        if not date_of_birth:
            return None

        today = date.today()
        age = today.year - date_of_birth.year

        # Adjust if birthday hasn't occurred this year
        if today.month < date_of_birth.month or (
            today.month == date_of_birth.month and today.day < date_of_birth.day
        ):
            age -= 1

        return max(0, age)

    @staticmethod
    def validate_email_domain(email, allowed_domains=None):
        """
        Validate email domain against allowed list

        Args:
            email (str): Email to validate
            allowed_domains (list): List of allowed domains

        Returns:
            bool: True if valid, False otherwise
        """
        if not email or not allowed_domains:
            return True

        domain = email.split("@")[-1].lower()
        return domain in [d.lower() for d in allowed_domains]

    @staticmethod
    def generate_student_slug(student):
        """
        Generate a URL-friendly slug for a student

        Args:
            student: Student instance

        Returns:
            str: URL slug
        """
        name_slug = slugify(f"{student.user.first_name} {student.user.last_name}")
        return f"{student.admission_number}-{name_slug}".lower()

    @staticmethod
    def process_profile_image(image_file, max_size=(800, 800), quality=85):
        """
        Process uploaded profile image

        Args:
            image_file: Uploaded image file
            max_size (tuple): Maximum dimensions (width, height)
            quality (int): JPEG quality (1-100)

        Returns:
            BytesIO: Processed image data
        """
        try:
            # Open and process the image
            image = Image.open(image_file)

            # Convert to RGB if necessary
            if image.mode in ("RGBA", "LA", "P"):
                background = Image.new("RGB", image.size, (255, 255, 255))
                if image.mode == "P":
                    image = image.convert("RGBA")
                background.paste(
                    image, mask=image.split()[-1] if image.mode == "RGBA" else None
                )
                image = background

            # Resize if larger than max_size
            image.thumbnail(max_size, Image.Resampling.LANCZOS)

            # Save to BytesIO
            output = io.BytesIO()
            image.save(output, format="JPEG", quality=quality, optimize=True)
            output.seek(0)

            return output

        except Exception as e:
            raise ValidationError(f"Error processing image: {str(e)}")

    @staticmethod
    def generate_qr_code_data(student):
        """
        Generate QR code data for student

        Args:
            student: Student instance

        Returns:
            str: QR code data string
        """
        data = {
            "id": str(student.id),
            "admission_number": student.admission_number,
            "name": student.get_full_name(),
            "class": str(student.current_class) if student.current_class else "",
            "emergency_contact": student.emergency_contact_number,
        }

        # Create a formatted string
        qr_string = "\n".join([f"{k}: {v}" for k, v in data.items()])
        return qr_string

    @staticmethod
    def mask_sensitive_data(data, fields_to_mask=None):
        """
        Mask sensitive data for logging/display

        Args:
            data (dict): Data to mask
            fields_to_mask (list): List of field names to mask

        Returns:
            dict: Masked data
        """
        if fields_to_mask is None:
            fields_to_mask = [
                "phone_number",
                "emergency_contact_number",
                "work_phone",
                "email",
                "address",
            ]

        masked_data = data.copy()

        for field in fields_to_mask:
            if field in masked_data and masked_data[field]:
                value = str(masked_data[field])
                if "@" in value:  # Email
                    parts = value.split("@")
                    masked_data[field] = f"{parts[0][:2]}***@{parts[1]}"
                elif len(value) > 4:  # Phone or other
                    masked_data[field] = f"{value[:2]}***{value[-2:]}"
                else:
                    masked_data[field] = "***"

        return masked_data


class ParentUtils:
    """Utility functions for parent-related operations"""

    @staticmethod
    def determine_relation_priority(relation):
        """
        Determine priority order for parent relations

        Args:
            relation (str): Parent relation type

        Returns:
            int: Priority order (lower number = higher priority)
        """
        priority_map = {
            "Mother": 1,
            "Father": 2,
            "Guardian": 3,
            "Grandparent": 4,
            "Uncle": 5,
            "Aunt": 6,
            "Other": 7,
        }
        return priority_map.get(relation, 10)

    @staticmethod
    def suggest_emergency_priority(student, parent):
        """
        Suggest emergency contact priority for a new parent-student relationship

        Args:
            student: Student instance
            parent: Parent instance

        Returns:
            int: Suggested priority
        """
        existing_relations = student.student_parent_relations.all()

        if not existing_relations:
            return 1

        # Get the lowest priority number (highest priority) available
        existing_priorities = [r.emergency_contact_priority for r in existing_relations]
        max_priority = max(existing_priorities) if existing_priorities else 0

        # Assign based on relation type
        relation_priority = ParentUtils.determine_relation_priority(
            parent.relation_with_student
        )

        # Find appropriate slot
        for priority in range(1, max_priority + 2):
            if priority not in existing_priorities:
                return priority

        return max_priority + 1

    @staticmethod
    def validate_parent_permissions(parent, permissions):
        """
        Validate parent permissions based on relation type

        Args:
            parent: Parent instance
            permissions (dict): Requested permissions

        Returns:
            dict: Validated permissions with suggestions
        """
        suggestions = {}

        # Primary contact suggestions
        if parent.relation_with_student in ["Mother", "Father"]:
            suggestions["is_primary_contact"] = True

        # Financial responsibility suggestions
        if parent.relation_with_student in ["Mother", "Father", "Guardian"]:
            suggestions["financial_responsibility"] = True

        # Pickup permissions
        if parent.relation_with_student != "Other":
            suggestions["can_pickup"] = True

        # Access to information
        suggestions["access_to_grades"] = True
        suggestions["access_to_attendance"] = True

        # Merge with requested permissions
        validated = suggestions.copy()
        validated.update(permissions)

        return validated


class ValidationUtils:
    """Common validation utilities"""

    @staticmethod
    def validate_indian_phone(phone):
        """
        Validate Indian phone number format

        Args:
            phone (str): Phone number to validate

        Returns:
            bool: True if valid, False otherwise
        """
        if not phone:
            return False

        # Remove all non-digit characters
        digits = re.sub(r"\D", "", phone)

        # Indian mobile numbers are 10 digits
        if len(digits) == 10 and digits[0] in "6789":
            return True

        # Include country code
        if len(digits) == 12 and digits.startswith("91") and digits[2] in "6789":
            return True

        return False

    @staticmethod
    def validate_admission_date(admission_date):
        """
        Validate admission date

        Args:
            admission_date (date): Admission date to validate

        Returns:
            tuple: (is_valid, error_message)
        """
        if not admission_date:
            return False, "Admission date is required"

        today = date.today()

        # Cannot be in the future
        if admission_date > today:
            return False, "Admission date cannot be in the future"

        # Cannot be too far in the past (more than 20 years)
        if (today - admission_date).days > 20 * 365:
            return False, "Admission date seems too old"

        return True, ""

    @staticmethod
    def validate_age_for_class(age, class_name):
        """
        Validate if student age is appropriate for the class

        Args:
            age (int): Student age
            class_name (str): Class name

        Returns:
            tuple: (is_valid, warning_message)
        """
        if not age or not class_name:
            return True, ""

        # Extract grade number from class name
        grade_match = re.search(r"(\d+)", class_name)
        if not grade_match:
            return True, ""

        grade = int(grade_match.group(1))

        # Typical age ranges for grades
        expected_age_min = grade + 4  # Grade 1 = age 5-6
        expected_age_max = grade + 7

        if age < expected_age_min:
            return False, f"Student might be too young for {class_name}"
        elif age > expected_age_max:
            return False, f"Student might be too old for {class_name}"

        return True, ""


class FileUtils:
    """File handling utilities"""

    @staticmethod
    def validate_csv_structure(csv_file, required_columns, max_size_mb=5):
        """
        Validate CSV file structure

        Args:
            csv_file: Uploaded CSV file
            required_columns (list): List of required column names
            max_size_mb (int): Maximum file size in MB

        Returns:
            tuple: (is_valid, error_message, column_mapping)
        """
        try:
            # Check file size
            if csv_file.size > max_size_mb * 1024 * 1024:
                return False, f"File size exceeds {max_size_mb}MB limit", None

            # Check file extension
            if not csv_file.name.lower().endswith(".csv"):
                return False, "File must be a CSV file", None

            # Read and parse CSV headers
            csv_file.seek(0)
            first_line = csv_file.readline().decode("utf-8").strip()
            headers = [h.strip().lower() for h in first_line.split(",")]

            # Check for required columns
            missing_columns = []
            column_mapping = {}

            for req_col in required_columns:
                req_col_lower = req_col.lower()
                if req_col_lower not in headers:
                    # Try to find similar column names
                    for header in headers:
                        if req_col_lower in header or header in req_col_lower:
                            column_mapping[req_col] = header
                            break
                    else:
                        missing_columns.append(req_col)
                else:
                    column_mapping[req_col] = req_col_lower

            if missing_columns:
                return (
                    False,
                    f"Missing required columns: {', '.join(missing_columns)}",
                    None,
                )

            csv_file.seek(0)  # Reset file pointer
            return True, "", column_mapping

        except Exception as e:
            return False, f"Error reading CSV file: {str(e)}", None

    @staticmethod
    def generate_csv_template(fields, sample_data=None):
        """
        Generate CSV template with headers and sample data

        Args:
            fields (list): List of field names
            sample_data (list): List of sample rows (optional)

        Returns:
            str: CSV content
        """
        import csv
        import io

        output = io.StringIO()
        writer = csv.writer(output)

        # Write headers
        writer.writerow(fields)

        # Write sample data if provided
        if sample_data:
            for row in sample_data:
                writer.writerow(row)

        return output.getvalue()

    @staticmethod
    def sanitize_filename(filename):
        """
        Sanitize filename for safe storage

        Args:
            filename (str): Original filename

        Returns:
            str: Sanitized filename
        """
        # Remove or replace invalid characters
        filename = re.sub(r"[^\w\s-.]", "", filename)
        filename = re.sub(r"[-\s]+", "-", filename)

        # Ensure it doesn't start with a dot
        if filename.startswith("."):
            filename = "file" + filename

        # Limit length
        name, ext = filename.rsplit(".", 1) if "." in filename else (filename, "")
        if len(name) > 50:
            name = name[:50]

        return f"{name}.{ext}" if ext else name


class SecurityUtils:
    """Security-related utilities"""

    @staticmethod
    def hash_sensitive_data(data):
        """
        Create a hash of sensitive data for comparison

        Args:
            data (str): Data to hash

        Returns:
            str: Hashed data
        """
        return hashlib.sha256(data.encode()).hexdigest()

    @staticmethod
    def generate_secure_token(length=32):
        """
        Generate a secure random token

        Args:
            length (int): Token length

        Returns:
            str: Secure token
        """
        return base64.urlsafe_b64encode(uuid.uuid4().bytes).decode()[:length]

    @staticmethod
    def validate_file_type(file, allowed_types):
        """
        Validate uploaded file type

        Args:
            file: Uploaded file
            allowed_types (list): List of allowed MIME types

        Returns:
            bool: True if valid, False otherwise
        """
        if not file:
            return False

        file_type = getattr(file, "content_type", "")
        return file_type in allowed_types

    @staticmethod
    def check_suspicious_patterns(text):
        """
        Check for suspicious patterns in text input

        Args:
            text (str): Text to check

        Returns:
            list: List of suspicious patterns found
        """
        suspicious_patterns = [
            r"<script.*?>.*?</script>",  # Script tags
            r"javascript:",  # JavaScript URLs
            r"on\w+\s*=",  # Event handlers
            r"<iframe.*?>",  # Iframes
            r"eval\s*\(",  # Eval function
        ]

        found_patterns = []
        for pattern in suspicious_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                found_patterns.append(pattern)

        return found_patterns


# Convenience function exports
def generate_admission_number(*args, **kwargs):
    return StudentUtils.generate_admission_number(*args, **kwargs)


def validate_phone_number(phone):
    return ValidationUtils.validate_indian_phone(phone)


def process_profile_image(*args, **kwargs):
    return StudentUtils.process_profile_image(*args, **kwargs)


def mask_sensitive_data(*args, **kwargs):
    return StudentUtils.mask_sensitive_data(*args, **kwargs)
