# src/teachers/services/evaluation_service.py
from datetime import datetime, timedelta

from django.db.models import Avg, Count, F, Max, Min, Q, StdDev
from django.db.models.functions import TruncMonth, TruncYear
from django.utils import timezone

from src.teachers.models import Teacher, TeacherEvaluation


class EvaluationService:
    """Service class for teacher evaluation operations."""

    @staticmethod
    def create_evaluation(
        teacher,
        evaluator,
        evaluation_date,
        criteria,
        remarks,
        followup_actions=None,
        status="submitted",
        followup_date=None,
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
            status=status,
            followup_date=followup_date,
        )

        return evaluation

    @staticmethod
    def get_evaluations_by_teacher(teacher, year=None, status=None):
        """Get evaluations for a specific teacher."""
        evaluations = TeacherEvaluation.objects.filter(teacher=teacher)

        if year:
            evaluations = evaluations.filter(evaluation_date__year=year)

        if status:
            evaluations = evaluations.filter(status=status)

        return evaluations.order_by("-evaluation_date")

    @staticmethod
    def get_evaluation_by_id(evaluation_id):
        """Get an evaluation by ID."""
        try:
            return TeacherEvaluation.objects.get(id=evaluation_id)
        except TeacherEvaluation.DoesNotExist:
            return None

    @staticmethod
    def update_evaluation_status(evaluation_id, status, followup_date=None):
        """Update evaluation status."""
        try:
            evaluation = TeacherEvaluation.objects.get(id=evaluation_id)
            evaluation.status = status
            if followup_date:
                evaluation.followup_date = followup_date
            evaluation.save()
            return evaluation
        except TeacherEvaluation.DoesNotExist:
            return None

    @staticmethod
    def get_evaluations_requiring_followup():
        """Get evaluations that require followup."""
        return TeacherEvaluation.objects.filter(
            Q(score__lt=70)
            & ~Q(status="closed")
            & (
                Q(followup_date__isnull=True)
                | Q(followup_date__lte=timezone.now().date())
            )
        ).select_related("teacher", "teacher__user", "evaluator")

    @staticmethod
    def get_evaluation_summary_by_criteria(department_id=None, year=None):
        """Get summary of evaluations by criteria."""
        evaluations = TeacherEvaluation.objects.all()

        if department_id:
            evaluations = evaluations.filter(teacher__department_id=department_id)

        if year:
            evaluations = evaluations.filter(evaluation_date__year=year)

        results = {}
        for eval in evaluations:
            for criterion, data in eval.criteria.items():
                if criterion not in results:
                    results[criterion] = {
                        "scores": [],
                        "max_scores": [],
                        "comments": [],
                    }

                if isinstance(data, dict):
                    if "score" in data:
                        results[criterion]["scores"].append(data["score"])
                    if "max_score" in data:
                        results[criterion]["max_scores"].append(data["max_score"])
                    if "comments" in data and data["comments"]:
                        results[criterion]["comments"].append(data["comments"])

        # Calculate averages
        for criterion, data in results.items():
            avg_score = (
                sum(data["scores"]) / len(data["scores"]) if data["scores"] else 0
            )
            avg_max = (
                sum(data["max_scores"]) / len(data["max_scores"])
                if data["max_scores"]
                else 0
            )
            percentage = (avg_score / avg_max * 100) if avg_max > 0 else 0

            results[criterion]["avg_score"] = avg_score
            results[criterion]["avg_max"] = avg_max
            results[criterion]["percentage"] = percentage
            results[criterion]["comment_count"] = len(data["comments"])

        return results

    @staticmethod
    def get_evaluation_trend(months=12):
        """Get evaluation trends over time."""
        start_date = timezone.now().date() - timedelta(days=30 * months)

        monthly_data = (
            TeacherEvaluation.objects.filter(evaluation_date__gte=start_date)
            .annotate(month=TruncMonth("evaluation_date"))
            .values("month")
            .annotate(
                avg_score=Avg("score"),
                count=Count("id"),
                min_score=Min("score"),
                max_score=Max("score"),
            )
            .order_by("month")
        )

        return {
            "labels": [d["month"].strftime("%b %Y") for d in monthly_data],
            "avg_scores": [float(d["avg_score"]) for d in monthly_data],
            "counts": [d["count"] for d in monthly_data],
            "min_scores": [float(d["min_score"]) for d in monthly_data],
            "max_scores": [float(d["max_score"]) for d in monthly_data],
        }
