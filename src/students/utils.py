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
    """Utility functions for student-related operations (no user account management)"""

    @staticmethod
    def validate_admission_number(admission_number):
        """
        Validate admission number format

        Args:
            admission_number (str): Admission number to validate

        Returns:
            bool: True if valid, False otherwise
        """
        if not admission_number:
            return False

        # Remove whitespace and convert to uppercase
        admission_number = admission_number.strip().upper()

        # Pattern: STU-YYYY-XXXXXX or similar variations
        patterns = [
            r"^[A-Z]{2,5}-\d{4}-[A-Z0-9]{4,8}(-\d{2})?$",  # STU-2024-ABC123-01
            r"^[A-Z]{2,5}\d{4}[A-Z0-9]{4,8}$",  # STU2024ABC123
            r"^\d{4}[A-Z0-9]{4,8}$",  # 2024ABC123
            r"^\d{7,12}$",  # 202400001
            r"^[A-Z]{2,5}/\d{4}/\d{3,6}$",  # STU/2024/001
        ]

        return any(re.match(pattern, admission_number) for pattern in patterns)

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
    def generate_registration_number(admission_year, prefix="REG"):
        """
        Generate a unique registration number

        Args:
            admission_year (int): Year of admission
            prefix (str): Prefix for registration number

        Returns:
            str: Generated registration number
        """
        # Generate unique ID
        unique_id = str(uuid.uuid4().hex)[:8].upper()

        # Format: REG-2024-ABCD1234
        registration_number = f"{prefix}-{admission_year}-{unique_id}"

        return registration_number

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
            # First part is first name, rest is last name
            first_name = name_parts[0]
            last_name = " ".join(name_parts[1:])
            return first_name, last_name

    @staticmethod
    def format_phone_number(phone_number, country_code="+1"):
        """
        Format phone number to standard format

        Args:
            phone_number (str): Phone number to format
            country_code (str): Default country code

        Returns:
            str: Formatted phone number
        """
        if not phone_number:
            return ""

        # Remove all non-digit characters
        digits_only = re.sub(r"\D", "", phone_number)

        # If no country code, add default
        if not digits_only.startswith(country_code.replace("+", "")):
            if len(digits_only) == 10:  # US format
                digits_only = country_code.replace("+", "") + digits_only

        # Format as +1-234-567-8900
        if len(digits_only) == 11 and digits_only.startswith("1"):
            return f"+{digits_only[0]}-{digits_only[1:4]}-{digits_only[4:7]}-{digits_only[7:]}"
        elif len(digits_only) == 10:
            return f"+1-{digits_only[:3]}-{digits_only[3:6]}-{digits_only[6:]}"
        else:
            return f"+{digits_only}"

    @staticmethod
    def validate_email_format(email):
        """
        Validate email format

        Args:
            email (str): Email to validate

        Returns:
            bool: True if valid format
        """
        if not email:
            return True  # Email is optional for students

        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        return bool(re.match(pattern, email))

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

        return age

    @staticmethod
    def validate_age(date_of_birth, min_age=3, max_age=25):
        """
        Validate if age is within acceptable range for students

        Args:
            date_of_birth (date): Date of birth
            min_age (int): Minimum acceptable age
            max_age (int): Maximum acceptable age

        Returns:
            bool: True if age is valid
        """
        if not date_of_birth:
            return True  # Date of birth is optional

        age = StudentUtils.calculate_age(date_of_birth)
        return min_age <= age <= max_age

    @staticmethod
    def generate_student_email(
        first_name, last_name, admission_number, domain="student.school.edu"
    ):
        """
        Generate a suggested email address for student

        Args:
            first_name (str): Student's first name
            last_name (str): Student's last name
            admission_number (str): Student's admission number
            domain (str): Email domain

        Returns:
            str: Suggested email address
        """
        # Create email from name and admission number
        name_part = f"{first_name.lower()}.{last_name.lower()}"
        name_part = re.sub(r"[^a-z.]", "", name_part)  # Remove non-alphabetic chars

        # Extract year from admission number
        year_match = re.search(r"\d{4}", admission_number)
        year = year_match.group() if year_match else ""

        return f"{name_part}.{year}@{domain}"

    @staticmethod
    def process_profile_picture(image_file, max_size=(300, 300), quality=85):
        """
        Process and optimize student profile picture

        Args:
            image_file: Image file object
            max_size (tuple): Maximum dimensions (width, height)
            quality (int): JPEG quality (1-100)

        Returns:
            io.BytesIO: Processed image buffer
        """
        try:
            # Open and process image
            image = Image.open(image_file)

            # Convert to RGB if necessary
            if image.mode in ("RGBA", "LA", "P"):
                image = image.convert("RGB")

            # Resize image while maintaining aspect ratio
            image.thumbnail(max_size, Image.Resampling.LANCZOS)

            # Save to buffer
            output = io.BytesIO()
            image.save(output, format="JPEG", quality=quality, optimize=True)
            output.seek(0)

            return output

        except Exception as e:
            raise ValidationError(f"Error processing image: {str(e)}")

    @staticmethod
    def validate_emergency_contact(contact_name, contact_number):
        """
        Validate emergency contact information

        Args:
            contact_name (str): Emergency contact name
            contact_number (str): Emergency contact phone number

        Returns:
            bool: True if valid
        """
        if not contact_name or not contact_name.strip():
            return False

        if not contact_number or not contact_number.strip():
            return False

        # Validate phone number format
        phone_pattern = r"^\+?[\d\s\-\(\)]{10,15}$"
        return bool(re.match(phone_pattern, contact_number))

    @staticmethod
    def format_student_display_name(first_name, last_name, admission_number):
        """
        Format student name for display purposes

        Args:
            first_name (str): First name
            last_name (str): Last name
            admission_number (str): Admission number

        Returns:
            str: Formatted display name
        """
        full_name = f"{first_name} {last_name}".strip()
        if not full_name:
            return admission_number
        return f"{full_name} ({admission_number})"

    @staticmethod
    def sanitize_student_data(data):
        """
        Sanitize student data input

        Args:
            data (dict): Student data dictionary

        Returns:
            dict: Sanitized data
        """
        sanitized = {}

        # Text fields that need stripping and title case
        text_fields = [
            "first_name",
            "last_name",
            "emergency_contact_name",
            "emergency_contact_relationship",
        ]
        for field in text_fields:
            if field in data and data[field]:
                sanitized[field] = data[field].strip().title()

        # Fields that need stripping only
        strip_fields = [
            "email",
            "phone_number",
            "admission_number",
            "roll_number",
            "previous_school",
        ]
        for field in strip_fields:
            if field in data and data[field]:
                sanitized[field] = data[field].strip()

        # Email to lowercase
        if "email" in sanitized and sanitized["email"]:
            sanitized["email"] = sanitized["email"].lower()

        # Admission number to uppercase
        if "admission_number" in sanitized and sanitized["admission_number"]:
            sanitized["admission_number"] = sanitized["admission_number"].upper()

        # Text areas that need stripping
        textarea_fields = ["address", "medical_conditions"]
        for field in textarea_fields:
            if field in data and data[field]:
                sanitized[field] = data[field].strip()

        # Copy other fields as-is
        for field, value in data.items():
            if field not in sanitized:
                sanitized[field] = value

        return sanitized

    @staticmethod
    def validate_student_data_completeness(data, required_fields=None):
        """
        Validate that required student data is complete

        Args:
            data (dict): Student data dictionary
            required_fields (list): List of required fields

        Returns:
            tuple: (is_valid, missing_fields)
        """
        if required_fields is None:
            required_fields = [
                "first_name",
                "last_name",
                "admission_number",
                "emergency_contact_name",
                "emergency_contact_number",
            ]

        missing_fields = []

        for field in required_fields:
            if field not in data or not data[field] or not str(data[field]).strip():
                missing_fields.append(field)

        return len(missing_fields) == 0, missing_fields

    @staticmethod
    def generate_csv_header():
        """
        Generate CSV header for student data export

        Returns:
            list: List of CSV column headers
        """
        return [
            "admission_number",
            "first_name",
            "last_name",
            "email",
            "phone_number",
            "date_of_birth",
            "gender",
            "address",
            "current_class",
            "roll_number",
            "blood_group",
            "status",
            "admission_date",
            "emergency_contact_name",
            "emergency_contact_number",
            "emergency_contact_relationship",
            "previous_school",
            "medical_conditions",
        ]

    @staticmethod
    def student_to_csv_row(student):
        """
        Convert student object to CSV row

        Args:
            student: Student model instance

        Returns:
            list: List of values for CSV row
        """
        return [
            student.admission_number,
            student.first_name,
            student.last_name,
            student.email or "",
            student.phone_number or "",
            student.date_of_birth.strftime("%Y-%m-%d") if student.date_of_birth else "",
            student.get_gender_display() if student.gender else "",
            student.address or "",
            str(student.current_class) if student.current_class else "",
            student.roll_number or "",
            student.blood_group,
            student.status,
            student.admission_date.strftime("%Y-%m-%d"),
            student.emergency_contact_name,
            student.emergency_contact_number,
            student.emergency_contact_relationship or "",
            student.previous_school or "",
            student.medical_conditions or "",
        ]

    @staticmethod
    def is_valid_blood_group(blood_group):
        """
        Validate blood group

        Args:
            blood_group (str): Blood group to validate

        Returns:
            bool: True if valid
        """
        valid_groups = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-", "Unknown"]
        return blood_group in valid_groups

    @staticmethod
    def normalize_blood_group(blood_group):
        """
        Normalize blood group format

        Args:
            blood_group (str): Blood group to normalize

        Returns:
            str: Normalized blood group
        """
        if not blood_group:
            return "Unknown"

        # Remove spaces and convert to uppercase
        normalized = blood_group.replace(" ", "").upper()

        # Map common variations
        blood_group_map = {
            "A+": "A+",
            "A-": "A-",
            "B+": "B+",
            "B-": "B-",
            "AB+": "AB+",
            "AB-": "AB-",
            "O+": "O+",
            "O-": "O-",
            "APOSITIVE": "A+",
            "ANEGATIVE": "A-",
            "BPOSITIVE": "B+",
            "BNEGATIVE": "B-",
            "ABPOSITIVE": "AB+",
            "ABNEGATIVE": "AB-",
            "OPOSITIVE": "O+",
            "ONEGATIVE": "O-",
        }

        return blood_group_map.get(normalized, "Unknown")

    @staticmethod
    def generate_qr_code_data(student):
        """
        Generate QR code data for student

        Args:
            student: Student model instance

        Returns:
            dict: Data to encode in QR code
        """
        return {
            "type": "student",
            "admission_number": student.admission_number,
            "name": student.full_name,
            "class": str(student.current_class) if student.current_class else "",
            "emergency_contact": student.emergency_contact_number,
            "blood_group": student.blood_group,
        }


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
