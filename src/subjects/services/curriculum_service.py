from typing import Dict, List, Optional, Tuple, Any
from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.db.models import QuerySet, Q, Avg, Count, Sum, F, Case, When
from django.db.models.functions import Coalesce
from datetime import datetime, date
import json

from ..models import Subject, Syllabus, TopicProgress, SubjectAssignment
from academics.models import Grade, AcademicYear, Term, Class, Department
from teachers.models import Teacher


class CurriculumService:
    """
    Service class for managing curriculum operations including subject management,
    curriculum planning, analytics, and reporting.
    """

    @staticmethod
    def create_subject(
        name: str,
        code: str,
        department_id: int,
        grade_level: List[int] = None,
        credit_hours: int = 1,
        is_elective: bool = False,
        description: str = "",
        **kwargs,
    ) -> Subject:
        """
        Create a new subject with validation.

        Args:
            name: Name of the subject
            code: Unique subject code
            department_id: ID of the department
            grade_level: List of grade IDs this subject applies to
            credit_hours: Number of credit hours
            is_elective: Whether subject is elective
            description: Subject description
            **kwargs: Additional fields

        Returns:
            Created Subject instance

        Raises:
            ValidationError: If validation fails
        """
        with transaction.atomic():
            # Validate department exists
            try:
                department = Department.objects.get(id=department_id)
            except Department.DoesNotExist:
                raise ValidationError(_("Department not found"))

            # Validate grade levels if provided
            if grade_level:
                valid_grades = Grade.objects.filter(id__in=grade_level).count()
                if valid_grades != len(grade_level):
                    raise ValidationError(_("One or more invalid grade IDs provided"))

            # Check for duplicate code
            if Subject.objects.filter(code=code).exists():
                raise ValidationError(
                    _("Subject code '{}' already exists").format(code)
                )

            subject = Subject.objects.create(
                name=name,
                code=code,
                department=department,
                grade_level=grade_level or [],
                credit_hours=credit_hours,
                is_elective=is_elective,
                description=description,
                **kwargs,
            )

            return subject

    @staticmethod
    def update_subject_grade_levels(
        subject_id: int, grade_levels: List[int]
    ) -> Subject:
        """
        Update the grade levels that a subject applies to.

        Args:
            subject_id: ID of the subject
            grade_levels: New list of grade IDs

        Returns:
            Updated Subject instance
        """
        with transaction.atomic():
            subject = Subject.objects.get(id=subject_id, is_active=True)

            # Validate grade levels
            if grade_levels:
                valid_grades = Grade.objects.filter(id__in=grade_levels).count()
                if valid_grades != len(grade_levels):
                    raise ValidationError(_("One or more invalid grade IDs provided"))

            subject.grade_level = grade_levels
            subject.save()

            return subject

    @staticmethod
    def get_subjects_by_grade(
        grade_id: int,
        department_id: Optional[int] = None,
        include_electives: bool = True,
    ) -> QuerySet[Subject]:
        """
        Get all subjects applicable for a specific grade.

        Args:
            grade_id: ID of the grade
            department_id: Optional department filter
            include_electives: Whether to include elective subjects

        Returns:
            QuerySet of applicable subjects
        """
        # Base filter for subjects applicable to the grade
        q_filter = Q(Q(grade_level__contains=[grade_id]) | Q(grade_level=[])) & Q(
            is_active=True
        )

        if department_id:
            q_filter &= Q(department_id=department_id)

        if not include_electives:
            q_filter &= Q(is_elective=False)

        return Subject.objects.filter(q_filter).select_related("department")

    @staticmethod
    def get_curriculum_structure(
        academic_year_id: int,
        grade_id: Optional[int] = None,
        department_id: Optional[int] = None,
    ) -> Dict:
        """
        Get comprehensive curriculum structure for an academic year.

        Args:
            academic_year_id: ID of the academic year
            grade_id: Optional grade filter
            department_id: Optional department filter

        Returns:
            Dictionary containing curriculum structure
        """
        filters = {"academic_year_id": academic_year_id, "is_active": True}

        if grade_id:
            filters["grade_id"] = grade_id
        if department_id:
            filters["subject__department_id"] = department_id

        syllabi = (
            Syllabus.objects.filter(**filters)
            .select_related("subject", "grade", "term", "subject__department")
            .annotate(
                total_topics=Count("topic_progress"),
                completed_topics=Count(
                    "topic_progress", filter=Q(topic_progress__is_completed=True)
                ),
            )
        )

        # Group by department and grade
        structure = {}

        for syllabus in syllabi:
            dept_name = syllabus.subject.department.name
            grade_name = syllabus.grade.name

            if dept_name not in structure:
                structure[dept_name] = {}

            if grade_name not in structure[dept_name]:
                structure[dept_name][grade_name] = {
                    "subjects": [],
                    "total_subjects": 0,
                    "average_completion": 0,
                }

            subject_info = {
                "subject_id": syllabus.subject.id,
                "subject_name": syllabus.subject.name,
                "subject_code": syllabus.subject.code,
                "credit_hours": syllabus.subject.credit_hours,
                "is_elective": syllabus.subject.is_elective,
                "syllabi": [],
            }

            # Find existing subject or add new one
            existing_subject = None
            for subj in structure[dept_name][grade_name]["subjects"]:
                if subj["subject_id"] == syllabus.subject.id:
                    existing_subject = subj
                    break

            if existing_subject:
                subject_info = existing_subject
            else:
                structure[dept_name][grade_name]["subjects"].append(subject_info)

            # Add syllabus info
            syllabus_info = {
                "syllabus_id": syllabus.id,
                "title": syllabus.title,
                "term_name": syllabus.term.name,
                "completion_percentage": syllabus.completion_percentage,
                "total_topics": syllabus.total_topics,
                "completed_topics": syllabus.completed_topics,
                "learning_objectives_count": len(syllabus.learning_objectives or []),
            }
            subject_info["syllabi"].append(syllabus_info)

        # Calculate aggregates
        for dept_name in structure:
            for grade_name in structure[dept_name]:
                grade_data = structure[dept_name][grade_name]
                grade_data["total_subjects"] = len(grade_data["subjects"])

                # Calculate average completion across all syllabi
                all_syllabi = []
                for subject in grade_data["subjects"]:
                    all_syllabi.extend(subject["syllabi"])

                if all_syllabi:
                    total_completion = sum(
                        s["completion_percentage"] for s in all_syllabi
                    )
                    grade_data["average_completion"] = total_completion / len(
                        all_syllabi
                    )

        return structure

    @staticmethod
    def assign_teacher_to_subject(
        teacher_id: int,
        subject_id: int,
        class_id: int,
        academic_year_id: int,
        term_id: int,
        is_primary_teacher: bool = True,
        assigned_by_id: Optional[int] = None,
    ) -> SubjectAssignment:
        """
        Assign a teacher to teach a subject for a specific class and term.

        Args:
            teacher_id: ID of the teacher
            subject_id: ID of the subject
            class_id: ID of the class
            academic_year_id: ID of the academic year
            term_id: ID of the term
            is_primary_teacher: Whether this is the primary teacher
            assigned_by_id: ID of the user making the assignment

        Returns:
            Created SubjectAssignment instance
        """
        with transaction.atomic():
            # Validate all relationships
            try:
                teacher = Teacher.objects.get(id=teacher_id, status="Active")
                subject = Subject.objects.get(id=subject_id, is_active=True)
                class_obj = Class.objects.get(id=class_id)
                academic_year = AcademicYear.objects.get(id=academic_year_id)
                term = Term.objects.get(id=term_id, academic_year=academic_year)
            except (
                Teacher.DoesNotExist,
                Subject.DoesNotExist,
                Class.DoesNotExist,
                AcademicYear.DoesNotExist,
                Term.DoesNotExist,
            ) as e:
                raise ValidationError(_("Invalid reference: {}").format(str(e)))

            # Check if subject is applicable for the class's grade
            if not subject.is_applicable_for_grade(class_obj.grade.id):
                raise ValidationError(
                    _("Subject '{}' is not applicable for grade '{}'").format(
                        subject.name, class_obj.grade.name
                    )
                )

            # Check for existing assignment
            existing_assignment = SubjectAssignment.objects.filter(
                subject=subject,
                class_assigned=class_obj,
                academic_year=academic_year,
                term=term,
                is_active=True,
            ).first()

            if existing_assignment:
                # Update existing assignment
                existing_assignment.teacher = teacher
                existing_assignment.is_primary_teacher = is_primary_teacher
                if assigned_by_id:
                    existing_assignment.assigned_by_id = assigned_by_id
                existing_assignment.save()
                return existing_assignment
            else:
                # Create new assignment
                assignment = SubjectAssignment.objects.create(
                    subject=subject,
                    teacher=teacher,
                    class_assigned=class_obj,
                    academic_year=academic_year,
                    term=term,
                    is_primary_teacher=is_primary_teacher,
                    assigned_by_id=assigned_by_id,
                )
                return assignment

    @staticmethod
    def get_teacher_workload(
        teacher_id: int, academic_year_id: int, term_id: Optional[int] = None
    ) -> Dict:
        """
        Calculate and return teacher's workload for subjects.

        Args:
            teacher_id: ID of the teacher
            academic_year_id: ID of the academic year
            term_id: Optional specific term

        Returns:
            Dictionary containing workload information
        """
        filters = {
            "teacher_id": teacher_id,
            "academic_year_id": academic_year_id,
            "is_active": True,
        }

        if term_id:
            filters["term_id"] = term_id

        assignments = SubjectAssignment.objects.filter(**filters).select_related(
            "subject", "class_assigned", "term"
        )

        workload = {
            "teacher_id": teacher_id,
            "academic_year_id": academic_year_id,
            "term_id": term_id,
            "total_subjects": assignments.count(),
            "total_classes": assignments.values("class_assigned").distinct().count(),
            "total_credit_hours": sum(a.subject.credit_hours for a in assignments),
            "primary_assignments": assignments.filter(is_primary_teacher=True).count(),
            "secondary_assignments": assignments.filter(
                is_primary_teacher=False
            ).count(),
            "assignments_by_term": {},
            "assignments_detail": [],
        }

        # Group by term
        for assignment in assignments:
            term_name = assignment.term.name
            if term_name not in workload["assignments_by_term"]:
                workload["assignments_by_term"][term_name] = {
                    "subjects": 0,
                    "classes": set(),
                    "credit_hours": 0,
                }

            workload["assignments_by_term"][term_name]["subjects"] += 1
            workload["assignments_by_term"][term_name]["classes"].add(
                assignment.class_assigned.id
            )
            workload["assignments_by_term"][term_name][
                "credit_hours"
            ] += assignment.subject.credit_hours

            # Add assignment detail
            assignment_detail = {
                "assignment_id": assignment.id,
                "subject_name": assignment.subject.name,
                "subject_code": assignment.subject.code,
                "class_name": str(assignment.class_assigned),
                "term_name": assignment.term.name,
                "credit_hours": assignment.subject.credit_hours,
                "is_primary_teacher": assignment.is_primary_teacher,
                "is_elective": assignment.subject.is_elective,
            }
            workload["assignments_detail"].append(assignment_detail)

        # Convert sets to counts
        for term_data in workload["assignments_by_term"].values():
            term_data["classes"] = len(term_data["classes"])

        return workload

    @staticmethod
    def get_curriculum_analytics(
        academic_year_id: int,
        grade_id: Optional[int] = None,
        department_id: Optional[int] = None,
    ) -> Dict:
        """
        Get comprehensive curriculum analytics for an academic year.

        Args:
            academic_year_id: ID of the academic year
            grade_id: Optional grade filter
            department_id: Optional department filter

        Returns:
            Dictionary containing analytics data
        """
        filters = {"academic_year_id": academic_year_id, "is_active": True}

        if grade_id:
            filters["grade_id"] = grade_id
        if department_id:
            filters["subject__department_id"] = department_id

        # Get syllabi with analytics
        syllabi = (
            Syllabus.objects.filter(**filters)
            .select_related("subject", "grade", "term", "subject__department")
            .annotate(
                total_topics=Count("topic_progress"),
                completed_topics=Count(
                    "topic_progress", filter=Q(topic_progress__is_completed=True)
                ),
                total_hours_taught=Coalesce(Sum("topic_progress__hours_taught"), 0),
            )
        )

        # Calculate overall statistics
        total_syllabi = syllabi.count()
        avg_completion = (
            syllabi.aggregate(avg_completion=Avg("completion_percentage"))[
                "avg_completion"
            ]
            or 0
        )

        completed_syllabi = syllabi.filter(completion_percentage=100).count()
        in_progress_syllabi = syllabi.filter(
            completion_percentage__gt=0, completion_percentage__lt=100
        ).count()
        not_started_syllabi = syllabi.filter(completion_percentage=0).count()

        # Analytics by department
        dept_analytics = {}
        for syllabus in syllabi:
            dept_name = syllabus.subject.department.name
            if dept_name not in dept_analytics:
                dept_analytics[dept_name] = {
                    "total_subjects": 0,
                    "total_syllabi": 0,
                    "avg_completion": 0,
                    "total_topics": 0,
                    "completed_topics": 0,
                    "total_hours_taught": 0,
                    "subjects": set(),
                }

            dept_data = dept_analytics[dept_name]
            dept_data["subjects"].add(syllabus.subject.id)
            dept_data["total_syllabi"] += 1
            dept_data["total_topics"] += syllabus.total_topics
            dept_data["completed_topics"] += syllabus.completed_topics
            dept_data["total_hours_taught"] += syllabus.total_hours_taught

        # Calculate averages for departments
        for dept_data in dept_analytics.values():
            dept_data["total_subjects"] = len(dept_data["subjects"])
            dept_data["subjects"] = list(dept_data["subjects"])  # Convert set to list

            if dept_data["total_syllabi"] > 0:
                dept_syllabi = syllabi.filter(subject__department__name=dept_name)
                dept_data["avg_completion"] = (
                    dept_syllabi.aggregate(avg=Avg("completion_percentage"))["avg"] or 0
                )

        # Analytics by grade
        grade_analytics = {}
        for syllabus in syllabi:
            grade_name = syllabus.grade.name
            if grade_name not in grade_analytics:
                grade_analytics[grade_name] = {
                    "total_syllabi": 0,
                    "avg_completion": 0,
                    "total_topics": 0,
                    "completed_topics": 0,
                    "total_hours_taught": 0,
                }

            grade_data = grade_analytics[grade_name]
            grade_data["total_syllabi"] += 1
            grade_data["total_topics"] += syllabus.total_topics
            grade_data["completed_topics"] += syllabus.completed_topics
            grade_data["total_hours_taught"] += syllabus.total_hours_taught

        # Calculate averages for grades
        for grade_name, grade_data in grade_analytics.items():
            if grade_data["total_syllabi"] > 0:
                grade_syllabi = syllabi.filter(grade__name=grade_name)
                grade_data["avg_completion"] = (
                    grade_syllabi.aggregate(avg=Avg("completion_percentage"))["avg"]
                    or 0
                )

        return {
            "academic_year_id": academic_year_id,
            "grade_id": grade_id,
            "department_id": department_id,
            "overview": {
                "total_syllabi": total_syllabi,
                "average_completion": round(avg_completion, 2),
                "completed_syllabi": completed_syllabi,
                "in_progress_syllabi": in_progress_syllabi,
                "not_started_syllabi": not_started_syllabi,
                "completion_rate": (
                    round((completed_syllabi / total_syllabi * 100), 2)
                    if total_syllabi > 0
                    else 0
                ),
            },
            "by_department": dept_analytics,
            "by_grade": grade_analytics,
            "completion_distribution": {
                "completed": completed_syllabi,
                "in_progress": in_progress_syllabi,
                "not_started": not_started_syllabi,
            },
        }

    @staticmethod
    def get_subject_prerequisite_chain(subject_id: int) -> List[Dict]:
        """
        Get the prerequisite chain for a subject across terms/grades.

        Args:
            subject_id: ID of the subject

        Returns:
            List of prerequisite information
        """
        subject = Subject.objects.get(id=subject_id, is_active=True)

        # Get all syllabi for this subject across grades and terms
        syllabi = (
            Syllabus.objects.filter(subject=subject, is_active=True)
            .select_related("grade", "term", "academic_year")
            .order_by("academic_year", "term__term_number", "grade__order_sequence")
        )

        prerequisite_chain = []

        for syllabus in syllabi:
            chain_item = {
                "syllabus_id": syllabus.id,
                "grade_name": syllabus.grade.name,
                "term_name": syllabus.term.name,
                "academic_year": syllabus.academic_year.name,
                "completion_percentage": syllabus.completion_percentage,
                "prerequisites": syllabus.prerequisites or [],
                "learning_objectives": syllabus.learning_objectives or [],
                "difficulty_level": syllabus.difficulty_level,
            }
            prerequisite_chain.append(chain_item)

        return prerequisite_chain

    @staticmethod
    def bulk_import_subjects(
        subjects_data: List[Dict], department_id: int
    ) -> Tuple[List[Subject], List[str]]:
        """
        Bulk import subjects with validation and error reporting.

        Args:
            subjects_data: List of subject data dictionaries
            department_id: ID of the department for all subjects

        Returns:
            Tuple of (created subjects, error messages)
        """
        created_subjects = []
        errors = []

        with transaction.atomic():
            department = Department.objects.get(id=department_id)

            for i, subject_data in enumerate(subjects_data):
                try:
                    # Validate required fields
                    if "name" not in subject_data or "code" not in subject_data:
                        errors.append(
                            f"Row {i+1}: Missing required fields (name, code)"
                        )
                        continue

                    # Check for duplicate code
                    if Subject.objects.filter(code=subject_data["code"]).exists():
                        errors.append(
                            f"Row {i+1}: Subject code '{subject_data['code']}' already exists"
                        )
                        continue

                    subject = Subject.objects.create(
                        name=subject_data["name"],
                        code=subject_data["code"],
                        department=department,
                        description=subject_data.get("description", ""),
                        credit_hours=subject_data.get("credit_hours", 1),
                        is_elective=subject_data.get("is_elective", False),
                        grade_level=subject_data.get("grade_level", []),
                    )
                    created_subjects.append(subject)

                except Exception as e:
                    errors.append(f"Row {i+1}: {str(e)}")

        return created_subjects, errors
