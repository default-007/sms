import json
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Avg, Count, Q, QuerySet, Sum
from django.utils.translation import gettext_lazy as _

from src.academics.models import AcademicYear, Class, Grade, Term
from src.teachers.models import Teacher

from ..models import Subject, SubjectAssignment, Syllabus, TopicProgress


class SyllabusService:
    """
    Service class for managing syllabus operations including creation,
    content management, progress tracking, and analytics.
    """

    @staticmethod
    def create_syllabus(
        subject_id: int,
        grade_id: int,
        academic_year_id: int,
        term_id: int,
        title: str,
        created_by_id: int,
        description: str = "",
        content: Dict = None,
        learning_objectives: List = None,
        **kwargs,
    ) -> Syllabus:
        """
        Create a new syllabus with validation and initial setup.

        Args:
            subject_id: ID of the subject
            grade_id: ID of the grade
            academic_year_id: ID of the academic year
            term_id: ID of the term
            title: Title for the syllabus
            created_by_id: ID of the user creating the syllabus
            description: Optional description
            content: Structured content data
            learning_objectives: List of learning objectives
            **kwargs: Additional fields

        Returns:
            Created Syllabus instance

        Raises:
            ValidationError: If validation fails
        """
        with transaction.atomic():
            # Validate relationships
            try:
                subject = Subject.objects.get(id=subject_id, is_active=True)
                grade = Grade.objects.get(id=grade_id)
                academic_year = AcademicYear.objects.get(id=academic_year_id)
                term = Term.objects.get(id=term_id, academic_year=academic_year)
            except (
                Subject.DoesNotExist,
                Grade.DoesNotExist,
                AcademicYear.DoesNotExist,
                Term.DoesNotExist,
            ) as e:
                raise ValidationError(_("Invalid reference: {}").format(str(e)))

            # Check if subject is applicable for grade
            if not subject.is_applicable_for_grade(grade_id):
                raise ValidationError(
                    _("Subject '{}' is not applicable for grade '{}'").format(
                        subject.name, grade.name
                    )
                )

            # Check for existing syllabus
            if Syllabus.objects.filter(
                subject=subject, grade=grade, academic_year=academic_year, term=term
            ).exists():
                raise ValidationError(
                    _("Syllabus already exists for this subject, grade, and term")
                )

            # Prepare content structure
            if content is None:
                content = {
                    "topics": [],
                    "units": [],
                    "teaching_schedule": {},
                    "assessment_plan": {},
                }

            # Create syllabus
            syllabus = Syllabus.objects.create(
                subject=subject,
                grade=grade,
                academic_year=academic_year,
                term=term,
                title=title,
                description=description,
                content=content,
                learning_objectives=learning_objectives or [],
                created_by_id=created_by_id,
                last_updated_by_id=created_by_id,
                **kwargs,
            )

            # Initialize topic progress if topics are provided
            if content.get("topics"):
                SyllabusService._initialize_topic_progress(syllabus)

            return syllabus

    @staticmethod
    def update_syllabus_content(
        syllabus_id: int, content_updates: Dict, updated_by_id: int
    ) -> Syllabus:
        """
        Update syllabus content with proper validation and progress tracking.

        Args:
            syllabus_id: ID of the syllabus to update
            content_updates: Dictionary of content updates
            updated_by_id: ID of the user making updates

        Returns:
            Updated Syllabus instance
        """
        with transaction.atomic():
            syllabus = Syllabus.objects.select_for_update().get(
                id=syllabus_id, is_active=True
            )

            # Merge content updates
            current_content = syllabus.content or {}
            current_content.update(content_updates)
            syllabus.content = current_content
            syllabus.last_updated_by_id = updated_by_id
            syllabus.save()

            # Update topic progress if topics changed
            if "topics" in content_updates:
                SyllabusService._sync_topic_progress(syllabus)

            # Recalculate completion percentage
            syllabus.update_completion_percentage()

            return syllabus

    @staticmethod
    def add_topic_to_syllabus(
        syllabus_id: int, topic_data: Dict, updated_by_id: int
    ) -> Tuple[Syllabus, int]:
        """
        Add a new topic to the syllabus and create corresponding progress tracking.

        Args:
            syllabus_id: ID of the syllabus
            topic_data: Topic information dictionary
            updated_by_id: ID of the user making updates

        Returns:
            Tuple of (updated syllabus, topic index)
        """
        with transaction.atomic():
            syllabus = Syllabus.objects.select_for_update().get(
                id=syllabus_id, is_active=True
            )

            # Ensure content structure exists
            if not isinstance(syllabus.content, dict):
                syllabus.content = {}
            if "topics" not in syllabus.content:
                syllabus.content["topics"] = []

            # Add topic with metadata
            topic_index = len(syllabus.content["topics"])
            topic_with_metadata = {
                **topic_data,
                "index": topic_index,
                "completed": False,
                "created_at": datetime.now().isoformat(),
                "created_by": updated_by_id,
            }

            syllabus.content["topics"].append(topic_with_metadata)
            syllabus.last_updated_by_id = updated_by_id
            syllabus.save()

            # Create topic progress tracking
            TopicProgress.objects.create(
                syllabus=syllabus,
                topic_name=topic_data.get("name", f"Topic {topic_index + 1}"),
                topic_index=topic_index,
                is_completed=False,
            )

            return syllabus, topic_index

    @staticmethod
    def mark_topic_completed(
        syllabus_id: int, topic_index: int, completion_data: Dict = None
    ) -> TopicProgress:
        """
        Mark a specific topic as completed and update progress tracking.

        Args:
            syllabus_id: ID of the syllabus
            topic_index: Index of the topic to mark as completed
            completion_data: Additional completion information

        Returns:
            Updated TopicProgress instance
        """
        with transaction.atomic():
            syllabus = Syllabus.objects.get(id=syllabus_id, is_active=True)

            # Update topic in content
            if (
                isinstance(syllabus.content, dict)
                and "topics" in syllabus.content
                and 0 <= topic_index < len(syllabus.content["topics"])
            ):

                syllabus.content["topics"][topic_index]["completed"] = True
                syllabus.content["topics"][topic_index][
                    "completion_date"
                ] = datetime.now().isoformat()

                if completion_data:
                    syllabus.content["topics"][topic_index].update(completion_data)

                syllabus.save()

            # Update topic progress
            topic_progress, created = TopicProgress.objects.get_or_create(
                syllabus=syllabus,
                topic_index=topic_index,
                defaults={
                    "topic_name": syllabus.content["topics"][topic_index].get(
                        "name", f"Topic {topic_index + 1}"
                    ),
                    "is_completed": True,
                    "completion_date": date.today(),
                },
            )

            if not created:
                topic_progress.mark_completed()
                if completion_data:
                    for field in ["hours_taught", "teaching_method", "notes"]:
                        if field in completion_data:
                            setattr(topic_progress, field, completion_data[field])
                    topic_progress.save()

            # Update syllabus completion percentage
            syllabus.update_completion_percentage()

            return topic_progress

    @staticmethod
    def get_syllabus_progress(syllabus_id: int) -> Dict:
        """
        Get detailed progress information for a syllabus.

        Args:
            syllabus_id: ID of the syllabus

        Returns:
            Dictionary containing progress information
        """
        try:
            syllabus = Syllabus.objects.get(id=syllabus_id, is_active=True)
        except Syllabus.DoesNotExist:
            raise ValidationError(_("Syllabus not found"))

        total_topics = syllabus.get_total_topics()
        completed_topics = syllabus.get_completed_topics()

        topic_progress = TopicProgress.objects.filter(syllabus=syllabus)
        total_hours_taught = (
            topic_progress.aggregate(total_hours=Sum("hours_taught"))["total_hours"]
            or 0
        )

        return {
            "syllabus_id": syllabus_id,
            "title": syllabus.title,
            "completion_percentage": syllabus.completion_percentage,
            "progress_status": syllabus.progress_status,
            "total_topics": total_topics,
            "completed_topics": completed_topics,
            "remaining_topics": total_topics - completed_topics,
            "total_hours_taught": total_hours_taught,
            "estimated_duration": syllabus.estimated_duration_hours,
            "learning_objectives_count": len(syllabus.learning_objectives or []),
            "last_updated": syllabus.last_updated_at,
            "topics_detail": [
                {
                    "index": i,
                    "name": topic.get("name", f"Topic {i + 1}"),
                    "completed": topic.get("completed", False),
                    "completion_date": topic.get("completion_date"),
                    "hours_taught": SyllabusService._get_topic_hours(syllabus, i),
                }
                for i, topic in enumerate(syllabus.content.get("topics", []))
            ],
        }

    @staticmethod
    def get_grade_syllabus_overview(
        grade_id: int, academic_year_id: int, term_id: Optional[int] = None
    ) -> Dict:
        """
        Get overview of all syllabi for a specific grade in an academic year/term.

        Args:
            grade_id: ID of the grade
            academic_year_id: ID of the academic year
            term_id: Optional ID of specific term

        Returns:
            Dictionary containing grade syllabus overview
        """
        filters = {
            "grade_id": grade_id,
            "academic_year_id": academic_year_id,
            "is_active": True,
        }

        if term_id:
            filters["term_id"] = term_id

        syllabi = Syllabus.objects.filter(**filters).select_related("subject", "term")

        overview = {
            "grade_id": grade_id,
            "academic_year_id": academic_year_id,
            "term_id": term_id,
            "total_subjects": syllabi.count(),
            "average_completion": syllabi.aggregate(
                avg_completion=Avg("completion_percentage")
            )["avg_completion"]
            or 0,
            "subjects_overview": [],
        }

        for syllabus in syllabi:
            subject_info = {
                "subject_id": syllabus.subject.id,
                "subject_name": syllabus.subject.name,
                "subject_code": syllabus.subject.code,
                "term_name": syllabus.term.name,
                "completion_percentage": syllabus.completion_percentage,
                "progress_status": syllabus.progress_status,
                "total_topics": syllabus.get_total_topics(),
                "completed_topics": syllabus.get_completed_topics(),
                "last_updated": syllabus.last_updated_at,
            }
            overview["subjects_overview"].append(subject_info)

        return overview

    @staticmethod
    def get_teacher_syllabus_assignments(
        teacher_id: int, academic_year_id: int, term_id: Optional[int] = None
    ) -> List[Dict]:
        """
        Get all syllabus assignments for a specific teacher.

        Args:
            teacher_id: ID of the teacher
            academic_year_id: ID of the academic year
            term_id: Optional ID of specific term

        Returns:
            List of syllabus assignment information
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

        assignment_list = []
        for assignment in assignments:
            try:
                syllabus = Syllabus.objects.get(
                    subject=assignment.subject,
                    grade=assignment.class_assigned.grade,
                    academic_year=assignment.academic_year,
                    term=assignment.term,
                    is_active=True,
                )

                assignment_info = {
                    "assignment_id": assignment.id,
                    "subject_name": assignment.subject.name,
                    "subject_code": assignment.subject.code,
                    "class_name": str(assignment.class_assigned),
                    "term_name": assignment.term.name,
                    "is_primary_teacher": assignment.is_primary_teacher,
                    "syllabus": {
                        "id": syllabus.id,
                        "title": syllabus.title,
                        "completion_percentage": syllabus.completion_percentage,
                        "progress_status": syllabus.progress_status,
                        "total_topics": syllabus.get_total_topics(),
                        "completed_topics": syllabus.get_completed_topics(),
                    },
                }
                assignment_list.append(assignment_info)

            except Syllabus.DoesNotExist:
                # Handle case where syllabus doesn't exist yet
                assignment_info = {
                    "assignment_id": assignment.id,
                    "subject_name": assignment.subject.name,
                    "subject_code": assignment.subject.code,
                    "class_name": str(assignment.class_assigned),
                    "term_name": assignment.term.name,
                    "is_primary_teacher": assignment.is_primary_teacher,
                    "syllabus": None,
                }
                assignment_list.append(assignment_info)

        return assignment_list

    @staticmethod
    def bulk_create_syllabi_for_term(
        term_id: int, template_data: Dict, created_by_id: int
    ) -> List[Syllabus]:
        """
        Bulk create syllabi for all subjects and grades in a term.

        Args:
            term_id: ID of the term
            template_data: Template data for syllabus creation
            created_by_id: ID of the user creating syllabi

        Returns:
            List of created Syllabus instances
        """
        with transaction.atomic():
            term = Term.objects.get(id=term_id)

            # Get all subject assignments for this term
            assignments = (
                SubjectAssignment.objects.filter(term=term, is_active=True)
                .select_related("subject", "class_assigned__grade")
                .distinct("subject", "class_assigned__grade")
            )

            created_syllabi = []

            for assignment in assignments:
                # Check if syllabus already exists
                if not Syllabus.objects.filter(
                    subject=assignment.subject,
                    grade=assignment.class_assigned.grade,
                    academic_year=term.academic_year,
                    term=term,
                ).exists():

                    # Create syllabus using template
                    syllabus_data = {
                        **template_data,
                        "title": f"{assignment.subject.name} - {assignment.class_assigned.grade.name} - {term.name}",
                    }

                    syllabus = SyllabusService.create_syllabus(
                        subject_id=assignment.subject.id,
                        grade_id=assignment.class_assigned.grade.id,
                        academic_year_id=term.academic_year.id,
                        term_id=term.id,
                        created_by_id=created_by_id,
                        **syllabus_data,
                    )
                    created_syllabi.append(syllabus)

            return created_syllabi

    @staticmethod
    def _initialize_topic_progress(syllabus: Syllabus) -> None:
        """Initialize topic progress entries for a syllabus."""
        topics = syllabus.content.get("topics", [])
        for i, topic in enumerate(topics):
            TopicProgress.objects.get_or_create(
                syllabus=syllabus,
                topic_index=i,
                defaults={
                    "topic_name": topic.get("name", f"Topic {i + 1}"),
                    "is_completed": topic.get("completed", False),
                },
            )

    @staticmethod
    def _sync_topic_progress(syllabus: Syllabus) -> None:
        """Sync topic progress with syllabus content."""
        topics = syllabus.content.get("topics", [])

        # Remove progress entries for deleted topics
        TopicProgress.objects.filter(
            syllabus=syllabus, topic_index__gte=len(topics)
        ).delete()

        # Update or create progress entries
        for i, topic in enumerate(topics):
            TopicProgress.objects.update_or_create(
                syllabus=syllabus,
                topic_index=i,
                defaults={
                    "topic_name": topic.get("name", f"Topic {i + 1}"),
                    "is_completed": topic.get("completed", False),
                },
            )

    @staticmethod
    def _get_topic_hours(syllabus: Syllabus, topic_index: int) -> float:
        """Get hours taught for a specific topic."""
        try:
            progress = TopicProgress.objects.get(
                syllabus=syllabus, topic_index=topic_index
            )
            return progress.hours_taught
        except TopicProgress.DoesNotExist:
            return 0.0
