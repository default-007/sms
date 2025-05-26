# students/services/search_service.py
import logging
from datetime import datetime, timedelta

from django.core.cache import cache
from django.db.models import Avg, Case, Count, IntegerField, Q, When
from django.utils import timezone

from ..models import Parent, Student, StudentParentRelation

logger = logging.getLogger(__name__)


class StudentSearchService:
    """Advanced search service for students with filtering, sorting, and optimization"""

    @staticmethod
    def search_students(filters):
        """Basic search with common filters"""
        try:
            queryset = Student.objects.with_related().with_parents()

            # Apply basic filters
            if filters.get("search"):
                queryset = queryset.search(filters["search"])

            if filters.get("status"):
                queryset = queryset.filter(status=filters["status"])

            if filters.get("class_id"):
                queryset = queryset.filter(current_class_id=filters["class_id"])

            if filters.get("blood_group"):
                queryset = queryset.filter(blood_group=filters["blood_group"])

            if filters.get("admission_year"):
                queryset = queryset.filter(
                    admission_date__year=filters["admission_year"]
                )

            if filters.get("section_id"):
                queryset = queryset.filter(
                    current_class__section_id=filters["section_id"]
                )

            if filters.get("grade_id"):
                queryset = queryset.filter(current_class__grade_id=filters["grade_id"])

            return queryset.distinct()

        except Exception as e:
            logger.error(f"Error in student search: {str(e)}")
            return Student.objects.none()

    @staticmethod
    def advanced_search(params):
        """Advanced search with complex filtering and analytics"""
        try:
            queryset = Student.objects.with_related().with_parents()

            # Text search across multiple fields
            if params.get("search"):
                search_query = params["search"]
                queryset = queryset.filter(
                    Q(admission_number__icontains=search_query)
                    | Q(user__first_name__icontains=search_query)
                    | Q(user__last_name__icontains=search_query)
                    | Q(user__email__icontains=search_query)
                    | Q(roll_number__icontains=search_query)
                    | Q(current_class__name__icontains=search_query)
                    | Q(
                        student_parent_relations__parent__user__first_name__icontains=search_query
                    )
                    | Q(
                        student_parent_relations__parent__user__last_name__icontains=search_query
                    )
                )

            # Status filters (multiple)
            if params.get("status"):
                status_list = (
                    params["status"]
                    if isinstance(params["status"], list)
                    else [params["status"]]
                )
                queryset = queryset.filter(status__in=status_list)

            # Blood group filters (multiple)
            if params.get("blood_group"):
                blood_groups = (
                    params["blood_group"]
                    if isinstance(params["blood_group"], list)
                    else [params["blood_group"]]
                )
                queryset = queryset.filter(blood_group__in=blood_groups)

            # Academic filters
            if params.get("class_id"):
                queryset = queryset.filter(current_class_id=params["class_id"])

            if params.get("section_id"):
                queryset = queryset.filter(
                    current_class__section_id=params["section_id"]
                )

            if params.get("grade_id"):
                queryset = queryset.filter(current_class__grade_id=params["grade_id"])

            # Age range filters
            if params.get("age_min") or params.get("age_max"):
                queryset = StudentSearchService._apply_age_filters(queryset, params)

            # Admission date range
            if params.get("admission_year_start") or params.get("admission_year_end"):
                queryset = StudentSearchService._apply_admission_date_filters(
                    queryset, params
                )

            # Family-related filters
            if params.get("has_siblings"):
                queryset = StudentSearchService._filter_by_siblings(queryset)

            if params.get("parent_relation"):
                queryset = queryset.filter(
                    student_parent_relations__parent__relation_with_student=params[
                        "parent_relation"
                    ]
                )

            # Attendance-based filters
            if params.get("attendance_min") or params.get("attendance_max"):
                queryset = StudentSearchService._apply_attendance_filters(
                    queryset, params
                )

            # Geographic filters
            if params.get("city"):
                queryset = queryset.filter(city__icontains=params["city"])

            if params.get("state"):
                queryset = queryset.filter(state__icontains=params["state"])

            # Medical condition filters
            if params.get("has_medical_conditions"):
                queryset = queryset.exclude(medical_conditions__isnull=True).exclude(
                    medical_conditions=""
                )

            # Profile completion filters
            if params.get("incomplete_profiles"):
                queryset = StudentSearchService._filter_incomplete_profiles(queryset)

            return queryset.distinct()

        except Exception as e:
            logger.error(f"Error in advanced search: {str(e)}")
            return Student.objects.none()

    @staticmethod
    def _apply_age_filters(queryset, params):
        """Apply age range filters"""
        try:
            current_date = timezone.now().date()

            if params.get("age_min"):
                min_birth_date = current_date.replace(
                    year=current_date.year - int(params["age_min"])
                )
                queryset = queryset.filter(user__date_of_birth__lte=min_birth_date)

            if params.get("age_max"):
                max_birth_date = current_date.replace(
                    year=current_date.year - int(params["age_max"])
                )
                queryset = queryset.filter(user__date_of_birth__gte=max_birth_date)

            return queryset
        except Exception as e:
            logger.error(f"Error applying age filters: {str(e)}")
            return queryset

    @staticmethod
    def _apply_admission_date_filters(queryset, params):
        """Apply admission date range filters"""
        try:
            if params.get("admission_year_start"):
                start_date = datetime(int(params["admission_year_start"]), 1, 1).date()
                queryset = queryset.filter(admission_date__gte=start_date)

            if params.get("admission_year_end"):
                end_date = datetime(int(params["admission_year_end"]), 12, 31).date()
                queryset = queryset.filter(admission_date__lte=end_date)

            return queryset
        except Exception as e:
            logger.error(f"Error applying admission date filters: {str(e)}")
            return queryset

    @staticmethod
    def _filter_by_siblings(queryset):
        """Filter students who have siblings"""
        try:
            # Get students who share parents with other students
            students_with_siblings = []

            for student in queryset:
                if student.get_siblings().exists():
                    students_with_siblings.append(student.id)

            return queryset.filter(id__in=students_with_siblings)
        except Exception as e:
            logger.error(f"Error filtering by siblings: {str(e)}")
            return queryset

    @staticmethod
    def _apply_attendance_filters(queryset, params):
        """Apply attendance percentage filters"""
        try:
            # This would need integration with attendance module
            # For now, filter based on cached attendance data
            filtered_students = []

            for student in queryset:
                attendance_pct = student.get_attendance_percentage()

                if params.get("attendance_min") and attendance_pct < float(
                    params["attendance_min"]
                ):
                    continue

                if params.get("attendance_max") and attendance_pct > float(
                    params["attendance_max"]
                ):
                    continue

                filtered_students.append(student.id)

            return queryset.filter(id__in=filtered_students)
        except Exception as e:
            logger.error(f"Error applying attendance filters: {str(e)}")
            return queryset

    @staticmethod
    def _filter_incomplete_profiles(queryset):
        """Filter students with incomplete profiles"""
        try:
            return queryset.filter(
                Q(user__first_name="")
                | Q(user__last_name="")
                | Q(user__email="")
                | Q(emergency_contact_name="")
                | Q(emergency_contact_number="")
                | Q(current_class__isnull=True)
            )
        except Exception as e:
            logger.error(f"Error filtering incomplete profiles: {str(e)}")
            return queryset

    @staticmethod
    def search_with_analytics(filters):
        """Search with additional analytics data"""
        try:
            queryset = StudentSearchService.search_students(filters)

            # Add analytics annotations
            queryset = queryset.annotate(
                parent_count=Count("student_parent_relations"),
                sibling_count=Count(
                    "student_parent_relations__parent__parent_student_relations"
                )
                - 1,
                primary_contact_exists=Count(
                    Case(
                        When(student_parent_relations__is_primary_contact=True, then=1)
                    )
                ),
            )

            return queryset
        except Exception as e:
            logger.error(f"Error in search with analytics: {str(e)}")
            return Student.objects.none()

    @staticmethod
    def get_search_suggestions(query, limit=10):
        """Get search suggestions based on partial query"""
        try:
            if len(query) < 2:
                return []

            cache_key = f"search_suggestions_{query.lower()}_{limit}"
            suggestions = cache.get(cache_key)

            if suggestions is None:
                suggestions = []

                # Student name suggestions
                students = Student.objects.filter(
                    Q(user__first_name__icontains=query)
                    | Q(user__last_name__icontains=query)
                    | Q(admission_number__icontains=query)
                ).select_related("user", "current_class")[:limit]

                for student in students:
                    suggestions.append(
                        {
                            "type": "student",
                            "id": str(student.id),
                            "text": f"{student.get_full_name()} ({student.admission_number})",
                            "category": "Students",
                            "class": (
                                str(student.current_class)
                                if student.current_class
                                else None
                            ),
                        }
                    )

                # Class suggestions
                from src.academics.models import Class

                classes = Class.objects.filter(
                    Q(name__icontains=query)
                    | Q(grade__name__icontains=query)
                    | Q(section__name__icontains=query)
                ).select_related("grade", "section")[:5]

                for class_obj in classes:
                    suggestions.append(
                        {
                            "type": "class",
                            "id": str(class_obj.id),
                            "text": str(class_obj),
                            "category": "Classes",
                        }
                    )

                # Parent suggestions
                parents = Parent.objects.filter(
                    Q(user__first_name__icontains=query)
                    | Q(user__last_name__icontains=query)
                    | Q(user__email__icontains=query)
                ).select_related("user")[:5]

                for parent in parents:
                    suggestions.append(
                        {
                            "type": "parent",
                            "id": str(parent.id),
                            "text": f"{parent.get_full_name()} ({parent.relation_with_student})",
                            "category": "Parents",
                        }
                    )

                cache.set(cache_key, suggestions, 300)  # Cache for 5 minutes

            return suggestions[:limit]

        except Exception as e:
            logger.error(f"Error getting search suggestions: {str(e)}")
            return []

    @staticmethod
    def search_parents(filters):
        """Search parents with filters"""
        try:
            queryset = Parent.objects.with_related().with_students()

            # Basic search
            if filters.get("search"):
                search_query = filters["search"]
                queryset = queryset.filter(
                    Q(user__first_name__icontains=search_query)
                    | Q(user__last_name__icontains=search_query)
                    | Q(user__email__icontains=search_query)
                    | Q(user__phone_number__icontains=search_query)
                    | Q(occupation__icontains=search_query)
                    | Q(workplace__icontains=search_query)
                )

            # Relation filter
            if filters.get("relation"):
                queryset = queryset.filter(relation_with_student=filters["relation"])

            # Emergency contact filter
            if filters.get("emergency_contact") is not None:
                queryset = queryset.filter(
                    emergency_contact=filters["emergency_contact"]
                )

            # Has multiple children filter
            if filters.get("has_multiple_children"):
                queryset = queryset.annotate(
                    child_count=Count("parent_student_relations")
                ).filter(child_count__gt=1)

            # Occupation filter
            if filters.get("occupation"):
                queryset = queryset.filter(occupation__icontains=filters["occupation"])

            return queryset.distinct()

        except Exception as e:
            logger.error(f"Error in parent search: {str(e)}")
            return Parent.objects.none()

    @staticmethod
    def search_relationships(filters):
        """Search student-parent relationships"""
        try:
            queryset = StudentParentRelation.objects.select_related(
                "student__user", "parent__user"
            )

            # Student search
            if filters.get("student_search"):
                search_query = filters["student_search"]
                queryset = queryset.filter(
                    Q(student__admission_number__icontains=search_query)
                    | Q(student__user__first_name__icontains=search_query)
                    | Q(student__user__last_name__icontains=search_query)
                )

            # Parent search
            if filters.get("parent_search"):
                search_query = filters["parent_search"]
                queryset = queryset.filter(
                    Q(parent__user__first_name__icontains=search_query)
                    | Q(parent__user__last_name__icontains=search_query)
                    | Q(parent__user__email__icontains=search_query)
                )

            # Relationship type filters
            if filters.get("is_primary_contact") is not None:
                queryset = queryset.filter(
                    is_primary_contact=filters["is_primary_contact"]
                )

            if filters.get("can_pickup") is not None:
                queryset = queryset.filter(can_pickup=filters["can_pickup"])

            if filters.get("financial_responsibility") is not None:
                queryset = queryset.filter(
                    financial_responsibility=filters["financial_responsibility"]
                )

            # Permission filters
            if filters.get("access_to_grades") is not None:
                queryset = queryset.filter(access_to_grades=filters["access_to_grades"])

            if filters.get("access_to_attendance") is not None:
                queryset = queryset.filter(
                    access_to_attendance=filters["access_to_attendance"]
                )

            # Emergency priority filter
            if filters.get("emergency_priority"):
                queryset = queryset.filter(
                    emergency_contact_priority=filters["emergency_priority"]
                )

            return queryset.distinct()

        except Exception as e:
            logger.error(f"Error in relationship search: {str(e)}")
            return StudentParentRelation.objects.none()

    @staticmethod
    def get_filter_options():
        """Get available filter options for UI"""
        try:
            cache_key = "student_filter_options"
            options = cache.get(cache_key)

            if options is None:
                options = {
                    "status_choices": Student.STATUS_CHOICES,
                    "blood_group_choices": Student.BLOOD_GROUP_CHOICES,
                    "relation_choices": Parent.RELATION_CHOICES,
                    "available_classes": StudentSearchService._get_available_classes(),
                    "available_sections": StudentSearchService._get_available_sections(),
                    "available_grades": StudentSearchService._get_available_grades(),
                    "admission_years": StudentSearchService._get_admission_years(),
                    "cities": StudentSearchService._get_cities(),
                    "states": StudentSearchService._get_states(),
                }

                cache.set(cache_key, options, 3600)  # Cache for 1 hour

            return options

        except Exception as e:
            logger.error(f"Error getting filter options: {str(e)}")
            return {}

    @staticmethod
    def _get_available_classes():
        """Get available classes for filtering"""
        try:
            from src.academics.models import Class

            return list(
                Class.objects.filter(academic_year__is_current=True)
                .select_related("grade", "section")
                .values("id", "name", "grade__name", "section__name")
            )
        except Exception as e:
            logger.error(f"Error getting available classes: {str(e)}")
            return []

    @staticmethod
    def _get_available_sections():
        """Get available sections for filtering"""
        try:
            from src.academics.models import Section

            return list(Section.objects.values("id", "name"))
        except Exception as e:
            logger.error(f"Error getting available sections: {str(e)}")
            return []

    @staticmethod
    def _get_available_grades():
        """Get available grades for filtering"""
        try:
            from src.academics.models import Grade

            return list(Grade.objects.values("id", "name"))
        except Exception as e:
            logger.error(f"Error getting available grades: {str(e)}")
            return []

    @staticmethod
    def _get_admission_years():
        """Get available admission years"""
        try:
            years = (
                Student.objects.values_list("admission_date__year", flat=True)
                .distinct()
                .order_by("-admission_date__year")
            )
            return [year for year in years if year]
        except Exception as e:
            logger.error(f"Error getting admission years: {str(e)}")
            return []

    @staticmethod
    def _get_cities():
        """Get available cities"""
        try:
            cities = (
                Student.objects.exclude(city__isnull=True)
                .exclude(city="")
                .values_list("city", flat=True)
                .distinct()
                .order_by("city")
            )
            return list(cities)[:50]  # Limit to top 50
        except Exception as e:
            logger.error(f"Error getting cities: {str(e)}")
            return []

    @staticmethod
    def _get_states():
        """Get available states"""
        try:
            states = (
                Student.objects.exclude(state__isnull=True)
                .exclude(state="")
                .values_list("state", flat=True)
                .distinct()
                .order_by("state")
            )
            return list(states)
        except Exception as e:
            logger.error(f"Error getting states: {str(e)}")
            return []

    @staticmethod
    def export_search_results(queryset, format="csv"):
        """Export search results in various formats"""
        try:
            if format == "csv":
                from ..services.student_service import StudentService

                return StudentService.export_students_to_csv(queryset)
            elif format == "json":
                return StudentSearchService._export_as_json(queryset)
            elif format == "excel":
                return StudentSearchService._export_as_excel(queryset)
            else:
                raise ValueError(f"Unsupported export format: {format}")

        except Exception as e:
            logger.error(f"Error exporting search results: {str(e)}")
            raise

    @staticmethod
    def _export_as_json(queryset):
        """Export queryset as JSON"""
        import json

        data = []
        for student in queryset.select_related("user", "current_class"):
            data.append(
                {
                    "id": str(student.id),
                    "admission_number": student.admission_number,
                    "name": student.get_full_name(),
                    "email": student.user.email,
                    "status": student.status,
                    "class": (
                        str(student.current_class) if student.current_class else None
                    ),
                    "blood_group": student.blood_group,
                    "admission_date": student.admission_date.isoformat(),
                }
            )

        return json.dumps(data, indent=2)

    @staticmethod
    def _export_as_excel(queryset):
        """Export queryset as Excel file"""
        # This would require openpyxl or xlsxwriter
        # For now, return CSV format
        from ..services.student_service import StudentService

        return StudentService.export_students_to_csv(queryset)

    @staticmethod
    def get_search_analytics(filters):
        """Get analytics for search results"""
        try:
            queryset = StudentSearchService.search_students(filters)

            analytics = {
                "total_results": queryset.count(),
                "status_breakdown": dict(
                    queryset.values("status").annotate(count=Count("id"))
                ),
                "class_breakdown": dict(
                    queryset.filter(current_class__isnull=False)
                    .values("current_class__name")
                    .annotate(count=Count("id"))
                ),
                "blood_group_breakdown": dict(
                    queryset.values("blood_group").annotate(count=Count("id"))
                ),
                "age_statistics": StudentSearchService._get_age_statistics(queryset),
                "geographic_distribution": StudentSearchService._get_geographic_distribution(
                    queryset
                ),
            }

            return analytics

        except Exception as e:
            logger.error(f"Error getting search analytics: {str(e)}")
            return {}

    @staticmethod
    def _get_age_statistics(queryset):
        """Get age statistics for queryset"""
        try:
            ages = [student.age for student in queryset if student.age]

            if not ages:
                return {}

            return {
                "average_age": round(sum(ages) / len(ages), 1),
                "min_age": min(ages),
                "max_age": max(ages),
                "age_distribution": StudentSearchService._create_age_distribution(ages),
            }
        except Exception as e:
            logger.error(f"Error getting age statistics: {str(e)}")
            return {}

    @staticmethod
    def _create_age_distribution(ages):
        """Create age distribution from list of ages"""
        distribution = {}
        for age in ages:
            distribution[age] = distribution.get(age, 0) + 1
        return distribution

    @staticmethod
    def _get_geographic_distribution(queryset):
        """Get geographic distribution for queryset"""
        try:
            distribution = {}

            cities = (
                queryset.exclude(city__isnull=True)
                .exclude(city="")
                .values_list("city", flat=True)
            )
            for city in cities:
                distribution[city] = distribution.get(city, 0) + 1

            # Sort by count and take top 10
            sorted_cities = sorted(
                distribution.items(), key=lambda x: x[1], reverse=True
            )[:10]
            return dict(sorted_cities)

        except Exception as e:
            logger.error(f"Error getting geographic distribution: {str(e)}")
            return {}

    @staticmethod
    def save_search(user, name, filters):
        """Save search for future use"""
        try:
            # This would save to a SavedSearch model
            saved_search = {
                "name": name,
                "filters": filters,
                "created_by": user.id,
                "created_at": timezone.now(),
            }

            # Store in cache for now (in real implementation, save to database)
            cache_key = f"saved_search_{user.id}_{name}"
            cache.set(cache_key, saved_search, 86400 * 30)  # 30 days

            return True

        except Exception as e:
            logger.error(f"Error saving search: {str(e)}")
            return False

    @staticmethod
    def get_saved_searches(user):
        """Get user's saved searches"""
        try:
            # This would retrieve from SavedSearch model
            # For now, return from cache
            searches = []

            # In real implementation, query database
            # searches = SavedSearch.objects.filter(created_by=user)

            return searches

        except Exception as e:
            logger.error(f"Error getting saved searches: {str(e)}")
            return []
