# students/services/analytics_service.py
import logging
from datetime import datetime, timedelta

from django.core.cache import cache
from django.db.models import Avg, Count, F, Max, Min, Q
from django.utils import timezone

from ..exceptions import AnalyticsError
from ..models import Parent, Student, StudentParentRelation

logger = logging.getLogger(__name__)


class StudentAnalyticsService:
    """Comprehensive analytics service for student data"""

    @staticmethod
    def get_comprehensive_dashboard_data():
        """Get complete dashboard analytics data"""
        try:
            cache_key = "student_dashboard_analytics"
            data = cache.get(cache_key)

            if data is None:
                data = {
                    "student_statistics": StudentAnalyticsService.get_student_statistics(),
                    "parent_statistics": StudentAnalyticsService.get_parent_statistics(),
                    "enrollment_trends": StudentAnalyticsService.get_enrollment_trends(),
                    "demographics": StudentAnalyticsService.get_demographics_analysis(),
                    "performance_metrics": StudentAnalyticsService.get_performance_metrics(),
                    "class_distribution": StudentAnalyticsService.get_class_distribution(),
                    "geographic_analysis": StudentAnalyticsService.get_geographic_analysis(),
                    "communication_stats": StudentAnalyticsService.get_communication_statistics(),
                    "generated_at": timezone.now(),
                }
                cache.set(cache_key, data, 1800)  # Cache for 30 minutes

            return data
        except Exception as e:
            logger.error(f"Error generating dashboard data: {str(e)}")
            raise AnalyticsError(f"Failed to generate dashboard data: {str(e)}")

    @staticmethod
    def get_student_statistics():
        """Get comprehensive student statistics"""
        try:
            total_students = Student.objects.count()

            stats = {
                "total_students": total_students,
                "active_students": Student.objects.filter(status="Active").count(),
                "inactive_students": Student.objects.filter(status="Inactive").count(),
                "graduated_students": Student.objects.filter(
                    status="Graduated"
                ).count(),
                "suspended_students": Student.objects.filter(
                    status="Suspended"
                ).count(),
                "withdrawn_students": Student.objects.filter(
                    status="Withdrawn"
                ).count(),
                "status_breakdown": dict(
                    Student.objects.values("status")
                    .annotate(count=Count("id"))
                    .values_list("status", "count")
                ),
                "blood_group_distribution": dict(
                    Student.objects.values("blood_group")
                    .annotate(count=Count("id"))
                    .values_list("blood_group", "count")
                ),
                "students_with_photos": Student.objects.exclude(photo="").count(),
                "students_without_parents": Student.objects.filter(
                    student_parent_relations__isnull=True
                ).count(),
                "students_with_medical_conditions": Student.objects.exclude(
                    medical_conditions__isnull=True
                )
                .exclude(medical_conditions="")
                .count(),
                "recent_admissions": Student.objects.filter(
                    admission_date__gte=timezone.now().date() - timedelta(days=30)
                ).count(),
                "completion_percentage": StudentAnalyticsService._calculate_overall_completion_percentage(),
            }

            # Calculate percentages
            if total_students > 0:
                stats["active_percentage"] = round(
                    (stats["active_students"] / total_students) * 100, 2
                )
                stats["photo_completion_percentage"] = round(
                    (stats["students_with_photos"] / total_students) * 100, 2
                )
                stats["parent_linkage_percentage"] = round(
                    (
                        (total_students - stats["students_without_parents"])
                        / total_students
                    )
                    * 100,
                    2,
                )
            else:
                stats.update(
                    {
                        "active_percentage": 0,
                        "photo_completion_percentage": 0,
                        "parent_linkage_percentage": 0,
                    }
                )

            return stats
        except Exception as e:
            logger.error(f"Error getting student statistics: {str(e)}")
            raise AnalyticsError(f"Failed to get student statistics: {str(e)}")

    @staticmethod
    def get_parent_statistics():
        """Get comprehensive parent statistics"""
        try:
            total_parents = Parent.objects.count()

            stats = {
                "total_parents": total_parents,
                "fathers": Parent.objects.filter(
                    relation_with_student="Father"
                ).count(),
                "mothers": Parent.objects.filter(
                    relation_with_student="Mother"
                ).count(),
                "guardians": Parent.objects.filter(
                    relation_with_student="Guardian"
                ).count(),
                "emergency_contacts": Parent.objects.filter(
                    emergency_contact=True
                ).count(),
                "relation_breakdown": dict(
                    Parent.objects.values("relation_with_student")
                    .annotate(count=Count("id"))
                    .values_list("relation_with_student", "count")
                ),
                "parents_with_multiple_children": Parent.objects.annotate(
                    child_count=Count("parent_student_relations")
                )
                .filter(child_count__gt=1)
                .count(),
                "parents_with_workplace_info": Parent.objects.exclude(
                    workplace__isnull=True
                )
                .exclude(workplace="")
                .count(),
                "primary_contacts": StudentParentRelation.objects.filter(
                    is_primary_contact=True
                ).count(),
                "financial_responsible_parents": StudentParentRelation.objects.filter(
                    financial_responsibility=True
                ).count(),
            }

            # Calculate percentages
            if total_parents > 0:
                stats["emergency_percentage"] = round(
                    (stats["emergency_contacts"] / total_parents) * 100, 2
                )
                stats["workplace_completion_percentage"] = round(
                    (stats["parents_with_workplace_info"] / total_parents) * 100, 2
                )
            else:
                stats.update(
                    {"emergency_percentage": 0, "workplace_completion_percentage": 0}
                )

            return stats
        except Exception as e:
            logger.error(f"Error getting parent statistics: {str(e)}")
            raise AnalyticsError(f"Failed to get parent statistics: {str(e)}")

    @staticmethod
    def get_enrollment_trends():
        """Get enrollment trends over time"""
        try:
            # Get enrollment by year
            yearly_enrollments = (
                Student.objects.extra(
                    select={"year": "EXTRACT(year FROM admission_date)"}
                )
                .values("year")
                .annotate(count=Count("id"))
                .order_by("year")
            )

            # Get enrollment by month for current year
            current_year = timezone.now().year
            monthly_enrollments = (
                Student.objects.filter(admission_date__year=current_year)
                .extra(select={"month": "EXTRACT(month FROM admission_date)"})
                .values("month")
                .annotate(count=Count("id"))
                .order_by("month")
            )

            # Get class-wise enrollment
            class_enrollments = (
                Student.objects.filter(status="Active", current_class__isnull=False)
                .values("current_class__grade__name", "current_class__section__name")
                .annotate(count=Count("id"))
                .order_by("current_class__grade__name")
            )

            return {
                "yearly_trends": list(yearly_enrollments),
                "monthly_trends_current_year": list(monthly_enrollments),
                "class_wise_enrollment": list(class_enrollments),
                "total_current_year": Student.objects.filter(
                    admission_date__year=current_year
                ).count(),
                "growth_rate": StudentAnalyticsService._calculate_enrollment_growth_rate(),
            }
        except Exception as e:
            logger.error(f"Error getting enrollment trends: {str(e)}")
            raise AnalyticsError(f"Failed to get enrollment trends: {str(e)}")

    @staticmethod
    def get_demographics_analysis():
        """Get demographic analysis"""
        try:
            # Age distribution
            age_stats = StudentAnalyticsService._get_age_statistics()

            # Geographic distribution
            city_distribution = dict(
                Student.objects.exclude(city__isnull=True)
                .exclude(city="")
                .values("city")
                .annotate(count=Count("id"))
                .order_by("-count")[:10]
                .values_list("city", "count")
            )

            state_distribution = dict(
                Student.objects.exclude(state__isnull=True)
                .exclude(state="")
                .values("state")
                .annotate(count=Count("id"))
                .order_by("-count")
                .values_list("state", "count")
            )

            # Nationality distribution
            nationality_distribution = dict(
                Student.objects.exclude(nationality__isnull=True)
                .exclude(nationality="")
                .values("nationality")
                .annotate(count=Count("id"))
                .order_by("-count")
                .values_list("nationality", "count")
            )

            # Religion distribution
            religion_distribution = dict(
                Student.objects.exclude(religion__isnull=True)
                .exclude(religion="")
                .values("religion")
                .annotate(count=Count("id"))
                .order_by("-count")
                .values_list("religion", "count")
            )

            return {
                "age_statistics": age_stats,
                "geographic_distribution": {
                    "cities": city_distribution,
                    "states": state_distribution,
                },
                "nationality_distribution": nationality_distribution,
                "religion_distribution": religion_distribution,
                "diversity_index": StudentAnalyticsService._calculate_diversity_index(),
            }
        except Exception as e:
            logger.error(f"Error getting demographics analysis: {str(e)}")
            raise AnalyticsError(f"Failed to get demographics analysis: {str(e)}")

    @staticmethod
    def get_performance_metrics():
        """Get performance-related metrics"""
        try:
            # Attendance-based metrics (would integrate with attendance module)
            attendance_stats = {
                "students_with_good_attendance": 0,  # >= 90%
                "students_with_poor_attendance": 0,  # < 75%
                "average_attendance": 0,
            }

            # Try to calculate if attendance data available
            try:
                attendance_data = []
                for student in Student.objects.filter(status="Active"):
                    percentage = student.get_attendance_percentage()
                    attendance_data.append(percentage)

                if attendance_data:
                    attendance_stats = {
                        "students_with_good_attendance": len(
                            [p for p in attendance_data if p >= 90]
                        ),
                        "students_with_poor_attendance": len(
                            [p for p in attendance_data if p < 75]
                        ),
                        "average_attendance": round(
                            sum(attendance_data) / len(attendance_data), 2
                        ),
                    }
            except:
                pass  # Attendance module might not be available

            # Family structure analysis
            family_stats = {
                "students_with_both_parents": StudentParentRelation.objects.filter(
                    parent__relation_with_student__in=["Father", "Mother"]
                )
                .values("student")
                .annotate(parent_count=Count("parent"))
                .filter(parent_count=2)
                .count(),
                "students_with_single_parent": Student.objects.annotate(
                    parent_count=Count("student_parent_relations")
                )
                .filter(parent_count=1)
                .count(),
                "students_with_guardians": Student.objects.filter(
                    student_parent_relations__parent__relation_with_student="Guardian"
                )
                .distinct()
                .count(),
            }

            return {
                "attendance_metrics": attendance_stats,
                "family_structure": family_stats,
                "completion_rates": {
                    "profile_completion": StudentAnalyticsService._calculate_overall_completion_percentage(),
                    "document_completion": StudentAnalyticsService._calculate_document_completion(),
                    "parent_linkage": StudentAnalyticsService._calculate_parent_linkage_completion(),
                },
            }
        except Exception as e:
            logger.error(f"Error getting performance metrics: {str(e)}")
            raise AnalyticsError(f"Failed to get performance metrics: {str(e)}")

    @staticmethod
    def get_class_distribution():
        """Get class-wise distribution analysis"""
        try:
            # Get class distribution
            class_data = (
                Student.objects.filter(status="Active", current_class__isnull=False)
                .values(
                    "current_class__grade__name",
                    "current_class__section__name",
                    "current_class__id",
                )
                .annotate(student_count=Count("id"))
                .order_by("current_class__grade__name", "current_class__section__name")
            )

            # Calculate capacity utilization if available
            capacity_analysis = []
            for class_info in class_data:
                try:
                    from src.academics.models import Class

                    class_obj = Class.objects.get(id=class_info["current_class__id"])
                    if class_obj.capacity:
                        utilization = (
                            class_info["student_count"] / class_obj.capacity
                        ) * 100
                        capacity_analysis.append(
                            {
                                "class_name": f"{class_info['current_class__grade__name']} {class_info['current_class__section__name']}",
                                "student_count": class_info["student_count"],
                                "capacity": class_obj.capacity,
                                "utilization_percentage": round(utilization, 2),
                            }
                        )
                except:
                    pass

            return {
                "class_wise_distribution": list(class_data),
                "capacity_analysis": capacity_analysis,
                "total_classes": len(class_data),
                "average_class_size": (
                    round(
                        sum(item["student_count"] for item in class_data)
                        / len(class_data)
                    )
                    if class_data
                    else 0
                ),
            }
        except Exception as e:
            logger.error(f"Error getting class distribution: {str(e)}")
            raise AnalyticsError(f"Failed to get class distribution: {str(e)}")

    @staticmethod
    def get_geographic_analysis():
        """Get detailed geographic analysis"""
        try:
            # City-wise analysis
            city_analysis = (
                Student.objects.exclude(city__isnull=True)
                .exclude(city="")
                .values("city", "state")
                .annotate(count=Count("id"))
                .order_by("-count")
            )

            # State-wise summary
            state_summary = {}
            for item in city_analysis:
                state = item["state"] or "Unknown"
                if state not in state_summary:
                    state_summary[state] = {"cities": 0, "students": 0}
                state_summary[state]["cities"] += 1
                state_summary[state]["students"] += item["count"]

            return {
                "city_analysis": list(city_analysis),
                "state_summary": state_summary,
                "coverage_area": {
                    "total_cities": len(set(item["city"] for item in city_analysis)),
                    "total_states": len(state_summary),
                    "students_with_address": Student.objects.exclude(city__isnull=True)
                    .exclude(city="")
                    .count(),
                },
            }
        except Exception as e:
            logger.error(f"Error getting geographic analysis: {str(e)}")
            raise AnalyticsError(f"Failed to get geographic analysis: {str(e)}")

    @staticmethod
    def get_communication_statistics():
        """Get communication and engagement statistics"""
        try:
            relations = StudentParentRelation.objects.all()

            stats = {
                "total_relationships": relations.count(),
                "email_enabled": relations.filter(receive_email=True).count(),
                "sms_enabled": relations.filter(receive_sms=True).count(),
                "push_enabled": relations.filter(
                    receive_push_notifications=True
                ).count(),
                "grade_access": relations.filter(access_to_grades=True).count(),
                "attendance_access": relations.filter(
                    access_to_attendance=True
                ).count(),
                "financial_access": relations.filter(
                    access_to_financial_info=True
                ).count(),
                "pickup_authorized": relations.filter(can_pickup=True).count(),
                "primary_contacts": relations.filter(is_primary_contact=True).count(),
            }

            # Calculate engagement percentages
            total = stats["total_relationships"]
            if total > 0:
                stats["engagement_percentages"] = {
                    "email_engagement": round(
                        (stats["email_enabled"] / total) * 100, 2
                    ),
                    "sms_engagement": round((stats["sms_enabled"] / total) * 100, 2),
                    "push_engagement": round((stats["push_enabled"] / total) * 100, 2),
                }
            else:
                stats["engagement_percentages"] = {
                    "email_engagement": 0,
                    "sms_engagement": 0,
                    "push_engagement": 0,
                }

            return stats
        except Exception as e:
            logger.error(f"Error getting communication statistics: {str(e)}")
            raise AnalyticsError(f"Failed to get communication statistics: {str(e)}")

    @staticmethod
    def _get_age_statistics():
        """Calculate age-related statistics"""
        ages = []
        for student in Student.objects.exclude(user__date_of_birth__isnull=True):
            age = student.age
            if age:
                ages.append(age)

        if not ages:
            return {"no_data": True}

        age_distribution = {}
        for age in ages:
            age_group = f"{(age//3)*3}-{(age//3)*3+2}"  # Group by 3-year ranges
            age_distribution[age_group] = age_distribution.get(age_group, 0) + 1

        return {
            "average_age": round(sum(ages) / len(ages), 1),
            "min_age": min(ages),
            "max_age": max(ages),
            "age_distribution": age_distribution,
            "total_with_age_data": len(ages),
        }

    @staticmethod
    def _calculate_overall_completion_percentage():
        """Calculate overall profile completion percentage"""
        try:
            total_students = Student.objects.count()
            if total_students == 0:
                return 0

            completion_scores = []
            for student in Student.objects.select_related("user"):
                score = 0
                total_fields = 10

                if student.first_name:
                    score += 1
                if student.last_name:
                    score += 1
                if student.email:
                    score += 1
                if student.date_of_birth:
                    score += 1
                if student.emergency_contact_name:
                    score += 1
                if student.emergency_contact_number:
                    score += 1
                if student.photo:
                    score += 1
                if student.address:
                    score += 1
                if student.current_class:
                    score += 1
                if student.student_parent_relations.exists():
                    score += 1

                completion_scores.append((score / total_fields) * 100)

            return round(sum(completion_scores) / len(completion_scores), 2)
        except Exception as e:
            logger.error(f"Error calculating completion percentage: {str(e)}")
            return 0

    @staticmethod
    def _calculate_document_completion():
        """Calculate document completion percentage"""
        total_students = Student.objects.count()
        if total_students == 0:
            return 0

        students_with_photos = Student.objects.exclude(photo="").count()
        return round((students_with_photos / total_students) * 100, 2)

    @staticmethod
    def _calculate_parent_linkage_completion():
        """Calculate parent linkage completion percentage"""
        total_students = Student.objects.count()
        if total_students == 0:
            return 0

        students_with_parents = (
            Student.objects.filter(student_parent_relations__isnull=False)
            .distinct()
            .count()
        )

        return round((students_with_parents / total_students) * 100, 2)

    @staticmethod
    def _calculate_enrollment_growth_rate():
        """Calculate enrollment growth rate"""
        try:
            current_year = timezone.now().year
            current_year_enrollments = Student.objects.filter(
                admission_date__year=current_year
            ).count()

            previous_year_enrollments = Student.objects.filter(
                admission_date__year=current_year - 1
            ).count()

            if previous_year_enrollments == 0:
                return 0

            growth_rate = (
                (current_year_enrollments - previous_year_enrollments)
                / previous_year_enrollments
            ) * 100
            return round(growth_rate, 2)
        except Exception as e:
            logger.error(f"Error calculating growth rate: {str(e)}")
            return 0

    @staticmethod
    def _calculate_diversity_index():
        """Calculate diversity index based on geographic and demographic spread"""
        try:
            total_students = Student.objects.count()
            if total_students == 0:
                return 0

            # Calculate based on city diversity
            city_counts = (
                Student.objects.exclude(city__isnull=True)
                .exclude(city="")
                .values("city")
                .annotate(count=Count("id"))
                .values_list("count", flat=True)
            )

            if not city_counts:
                return 0

            # Simple diversity index: 1 - sum((count/total)^2)
            diversity_score = 1 - sum(
                (count / total_students) ** 2 for count in city_counts
            )
            return round(diversity_score * 100, 2)
        except Exception as e:
            logger.error(f"Error calculating diversity index: {str(e)}")
            return 0

    @staticmethod
    def clear_analytics_cache():
        """Clear all analytics-related cache"""
        try:
            cache_keys = [
                "student_dashboard_analytics",
                "student_analytics_dashboard",
                "student_statistics",
                "parent_statistics",
                "enrollment_trends",
                "demographics_analysis",
            ]
            cache.delete_many(cache_keys)
            logger.info("Analytics cache cleared successfully")
        except Exception as e:
            logger.error(f"Error clearing analytics cache: {str(e)}")
            raise AnalyticsError(f"Failed to clear analytics cache: {str(e)}")

    @staticmethod
    def get_real_time_metrics():
        """Get real-time metrics for dashboard"""
        try:
            today = timezone.now().date()

            metrics = {
                "students_added_today": Student.objects.filter(
                    created_at__date=today
                ).count(),
                "parents_added_today": Parent.objects.filter(
                    created_at__date=today
                ).count(),
                "relationships_created_today": StudentParentRelation.objects.filter(
                    created_at__date=today
                ).count(),
                "active_students_online": 0,  # Would require session tracking
                "last_updated": timezone.now(),
            }

            return metrics
        except Exception as e:
            logger.error(f"Error getting real-time metrics: {str(e)}")
            raise AnalyticsError(f"Failed to get real-time metrics: {str(e)}")
