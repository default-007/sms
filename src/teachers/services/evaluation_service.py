# src/teachers/services/evaluation_service.py

from src.teachers.models import TeacherEvaluation
from django.utils import timezone


class EvaluationService:
    """Service class for teacher evaluation operations."""

    @staticmethod
    def create_evaluation(
        teacher, evaluator, evaluation_date, criteria, remarks, followup_actions=None
    ):
        """Create a teacher evaluation."""
        # Calculate total score from criteria
        total_score = 0
        max_score = 0

        for category, data in criteria.items():
            if isinstance(data, dict) and "score" in data and "max_score" in data:
                total_score += data["score"]
                max_score += data["max_score"]

        # Convert to percentage
        percentage_score = (total_score / max_score * 100) if max_score > 0 else 0

        evaluation = TeacherEvaluation.objects.create(
            teacher=teacher,
            evaluator=evaluator,
            evaluation_date=evaluation_date,
            criteria=criteria,
            score=percentage_score,
            remarks=remarks,
            followup_actions=followup_actions,
        )

        return evaluation

    @staticmethod
    def get_evaluations_by_teacher(teacher, year=None):
        """Get evaluations for a specific teacher."""
        evaluations = TeacherEvaluation.objects.filter(teacher=teacher)

        if year:
            evaluations = evaluations.filter(evaluation_date__year=year)

        return evaluations.order_by("-evaluation_date")

    @staticmethod
    def get_evaluation_by_id(evaluation_id):
        """Get an evaluation by ID."""
        try:
            return TeacherEvaluation.objects.get(id=evaluation_id)
        except TeacherEvaluation.DoesNotExist:
            return None
