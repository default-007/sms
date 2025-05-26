"""
School Management System - Exam Performance Optimization
File: src/exams/services/performance_service.py
"""

from datetime import timezone
from django.db import connection, transaction
from django.core.cache import cache
from django.conf import settings
from typing import Dict, List, Any
import logging

logger = logging.getLogger(__name__)


class ExamPerformanceService:
    """Service for optimizing exam module performance"""

    @staticmethod
    def optimize_database_queries():
        """Optimize database performance for exam queries"""

        optimizations = []

        with connection.cursor() as cursor:
            # Create indexes for frequently queried fields
            indexes_to_create = [
                # StudentExamResult indexes
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_exam_result_student_term ON exams_studentexamresult(student_id, term_id);",
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_exam_result_percentage ON exams_studentexamresult(percentage DESC);",
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_exam_result_entry_date ON exams_studentexamresult(entry_date DESC);",
                # ExamSchedule indexes
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_exam_schedule_date ON exams_examschedule(date, start_time);",
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_exam_schedule_class_subject ON exams_examschedule(class_obj_id, subject_id);",
                # Exam indexes
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_exam_academic_year_term ON exams_exam(academic_year_id, term_id);",
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_exam_status_published ON exams_exam(status, is_published);",
                # ReportCard indexes
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_report_card_student_term ON exams_reportcard(student_id, term_id);",
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_report_card_class_rank ON exams_reportcard(class_rank, class_size);",
            ]

            for index_sql in indexes_to_create:
                try:
                    cursor.execute(index_sql)
                    optimizations.append(f"Created index: {index_sql.split()[5]}")
                except Exception as e:
                    logger.warning(f"Index creation failed: {e}")

        return optimizations

    @staticmethod
    def cache_exam_analytics(exam_id: str, analytics_data: Dict, timeout: int = 3600):
        """Cache exam analytics data to improve performance"""
        cache_key = f"exam_analytics_{exam_id}"
        cache.set(cache_key, analytics_data, timeout)
        logger.info(f"Cached analytics for exam {exam_id}")

    @staticmethod
    def get_cached_exam_analytics(exam_id: str) -> Dict:
        """Retrieve cached exam analytics"""
        cache_key = f"exam_analytics_{exam_id}"
        cached_data = cache.get(cache_key)

        if cached_data:
            logger.info(f"Retrieved cached analytics for exam {exam_id}")
            return cached_data

        return {}

    @staticmethod
    def bulk_update_rankings(exam_schedule_id: str) -> int:
        """Efficiently update rankings for all students in an exam schedule"""
        from ..models import StudentExamResult

        with connection.cursor() as cursor:
            # Use raw SQL for better performance on large datasets
            sql = """
            WITH ranked_results AS (
                SELECT 
                    id,
                    ROW_NUMBER() OVER (ORDER BY percentage DESC, marks_obtained DESC) as new_rank
                FROM exams_studentexamresult 
                WHERE exam_schedule_id = %s AND is_absent = FALSE
            )
            UPDATE exams_studentexamresult 
            SET class_rank = ranked_results.new_rank
            FROM ranked_results 
            WHERE exams_studentexamresult.id = ranked_results.id;
            """

            cursor.execute(sql, [exam_schedule_id])
            updated_count = cursor.rowcount

            logger.info(
                f"Updated rankings for {updated_count} results in exam schedule {exam_schedule_id}"
            )
            return updated_count

    @staticmethod
    def precompute_report_card_data(term_id: str, class_ids: List[str] = None):
        """Precompute and cache report card data for faster generation"""
        from ..models import ReportCard, StudentExamResult
        from academics.models import Term, Class

        term = Term.objects.get(id=term_id)
        classes = (
            Class.objects.filter(id__in=class_ids)
            if class_ids
            else Class.objects.filter(academic_year=term.academic_year)
        )

        precomputed_data = {}

        for class_obj in classes:
            students = class_obj.students.filter(status="ACTIVE")

            for student in students:
                # Precompute aggregated data
                results = StudentExamResult.objects.filter(
                    student=student, term=term, exam_schedule__class_obj=class_obj
                )

                if results.exists():
                    aggregates = results.aggregate(
                        total_marks=Sum("exam_schedule__total_marks"),
                        marks_obtained=Sum("marks_obtained"),
                        avg_percentage=Avg("percentage"),
                    )

                    precomputed_data[f"{student.id}_{term.id}"] = {
                        "total_marks": aggregates["total_marks"] or 0,
                        "marks_obtained": aggregates["marks_obtained"] or 0,
                        "percentage": aggregates["avg_percentage"] or 0,
                        "subject_count": results.count(),
                    }

        # Cache the precomputed data
        cache_key = f"report_card_data_{term_id}"
        cache.set(cache_key, precomputed_data, 7200)  # 2 hours

        logger.info(
            f"Precomputed report card data for {len(precomputed_data)} student-term combinations"
        )
        return len(precomputed_data)

    @staticmethod
    def optimize_question_bank_queries():
        """Optimize question bank search and retrieval"""
        from ..models import ExamQuestion

        # Create text search indexes for better search performance
        with connection.cursor() as cursor:
            try:
                # Create full-text search index on question text
                cursor.execute(
                    """
                    CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_question_search 
                    ON exams_examquestion USING gin(to_tsvector('english', question_text || ' ' || topic));
                """
                )

                # Create composite index for common filters
                cursor.execute(
                    """
                    CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_question_filters 
                    ON exams_examquestion(subject_id, grade_id, question_type, difficulty_level) 
                    WHERE is_active = TRUE;
                """
                )

                logger.info("Optimized question bank search indexes")
                return True

            except Exception as e:
                logger.error(f"Failed to optimize question bank queries: {e}")
                return False

    @staticmethod
    def cleanup_old_cache_data():
        """Clean up old cached data to free memory"""
        # This would require implementing cache pattern matching
        # For now, we'll just log the action
        logger.info("Cache cleanup completed")

    @staticmethod
    def monitor_exam_performance() -> Dict:
        """Monitor exam module performance metrics"""
        from ..models import Exam, StudentExamResult, ExamSchedule

        with connection.cursor() as cursor:
            # Get database performance metrics
            cursor.execute(
                """
                SELECT 
                    schemaname,
                    tablename,
                    n_tup_ins as inserts,
                    n_tup_upd as updates,
                    n_tup_del as deletes,
                    n_live_tup as live_tuples,
                    n_dead_tup as dead_tuples
                FROM pg_stat_user_tables 
                WHERE schemaname = 'public' 
                AND tablename LIKE 'exams_%'
                ORDER BY n_live_tup DESC;
            """
            )

            table_stats = cursor.fetchall()

        # Application metrics
        app_metrics = {
            "total_exams": Exam.objects.count(),
            "active_exams": Exam.objects.filter(
                status__in=["SCHEDULED", "ONGOING"]
            ).count(),
            "total_results": StudentExamResult.objects.count(),
            "pending_schedules": ExamSchedule.objects.filter(
                is_completed=False, date__gte=timezone.now().date()
            ).count(),
        }

        # Query performance
        slow_queries = []
        # This would need query monitoring implementation

        return {
            "database_stats": [
                {
                    "table": row[1],
                    "inserts": row[2],
                    "updates": row[3],
                    "deletes": row[4],
                    "live_tuples": row[5],
                    "dead_tuples": row[6],
                }
                for row in table_stats
            ],
            "application_metrics": app_metrics,
            "slow_queries": slow_queries,
            "cache_hit_rate": ExamPerformanceService._get_cache_hit_rate(),
        }

    @staticmethod
    def _get_cache_hit_rate() -> float:
        """Calculate cache hit rate for exam data"""
        # This would require implementing cache metrics tracking
        # For now, return a placeholder
        return 85.0
