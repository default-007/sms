from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    AssignmentViewSet,
    AssignmentSubmissionViewSet,
    AssignmentRubricViewSet,
    AssignmentCommentViewSet,
    TeacherAnalyticsView,
    StudentAnalyticsView,
)

app_name = "assignments_api"

# Create router and register viewsets
router = DefaultRouter()
router.register(r"assignments", AssignmentViewSet, basename="assignment")
router.register(r"submissions", AssignmentSubmissionViewSet, basename="submission")
router.register(r"rubrics", AssignmentRubricViewSet, basename="rubric")
router.register(r"comments", AssignmentCommentViewSet, basename="comment")
router.register(
    r"teacher-analytics", TeacherAnalyticsView, basename="teacher-analytics"
)
router.register(
    r"student-analytics", StudentAnalyticsView, basename="student-analytics"
)

urlpatterns = [
    # Include router URLs
    path("", include(router.urls)),
    # Additional custom endpoints can be added here if needed
    # Example: path('custom-endpoint/', CustomView.as_view(), name='custom-endpoint'),
]

"""
API Endpoints Summary:

Assignment Management:
- GET    /api/assignments/                           - List assignments
- POST   /api/assignments/                           - Create assignment
- GET    /api/assignments/{id}/                      - Get assignment details
- PUT    /api/assignments/{id}/                      - Update assignment
- PATCH  /api/assignments/{id}/                      - Partial update assignment
- DELETE /api/assignments/{id}/                      - Delete assignment
- POST   /api/assignments/{id}/publish/              - Publish assignment
- GET    /api/assignments/{id}/analytics/            - Get assignment analytics
- GET    /api/assignments/{id}/submissions/          - Get assignment submissions
- GET    /api/assignments/{id}/export_submissions/   - Export submissions to CSV
- GET    /api/assignments/upcoming_deadlines/        - Get upcoming deadlines
- GET    /api/assignments/overdue/                   - Get overdue assignments

Submission Management:
- GET    /api/submissions/                           - List submissions
- POST   /api/submissions/                           - Create/update submission
- GET    /api/submissions/{id}/                      - Get submission details
- PUT    /api/submissions/{id}/                      - Update submission
- PATCH  /api/submissions/{id}/                      - Partial update submission
- DELETE /api/submissions/{id}/                      - Delete submission
- POST   /api/submissions/{id}/grade/                - Grade submission
- POST   /api/submissions/{id}/check_plagiarism/     - Check plagiarism
- GET    /api/submissions/{id}/download/             - Download submission file
- POST   /api/submissions/bulk_grade/                - Bulk grade submissions

Rubric Management:
- GET    /api/rubrics/                               - List rubrics
- POST   /api/rubrics/                               - Create rubric
- GET    /api/rubrics/{id}/                          - Get rubric details
- PUT    /api/rubrics/{id}/                          - Update rubric
- PATCH  /api/rubrics/{id}/                          - Partial update rubric
- DELETE /api/rubrics/{id}/                          - Delete rubric
- POST   /api/rubrics/create_rubric/                 - Create complete rubric set

Comment Management:
- GET    /api/comments/                              - List comments
- POST   /api/comments/                              - Create comment
- GET    /api/comments/{id}/                         - Get comment details
- PUT    /api/comments/{id}/                         - Update comment
- PATCH  /api/comments/{id}/                         - Partial update comment
- DELETE /api/comments/{id}/                         - Delete comment

Analytics:
- GET    /api/teacher-analytics/                     - Teacher analytics dashboard
- GET    /api/teacher-analytics/assignment_performance/ - Assignment performance data
- GET    /api/student-analytics/                     - Student analytics dashboard

Query Parameters:
- ?status=draft|published|closed                    - Filter by assignment status
- ?subject={subject_id}                             - Filter by subject
- ?class_id={class_id}                              - Filter by class
- ?term={term_id}                                   - Filter by term
- ?difficulty=easy|medium|hard                      - Filter by difficulty
- ?overdue_only=true                                - Show only overdue assignments
- ?graded_only=true                                 - Show only graded submissions
- ?ungraded_only=true                               - Show only ungraded submissions
- ?late_only=true                                   - Show only late submissions
- ?days=7                                           - Days ahead for deadlines (default: 7)
- ?page=1                                           - Pagination page number
- ?page_size=20                                     - Number of items per page

Response Formats:
All endpoints return JSON responses with the following structure:

Success Response:
{
    "count": 100,                    // Total count (for paginated lists)
    "next": "url_to_next_page",      // Next page URL (for pagination)
    "previous": "url_to_prev_page",  // Previous page URL (for pagination)
    "results": [...],                // Data array (for lists) or object (for details)
}

Error Response:
{
    "error": "Error message",
    "details": {                     // Optional detailed error info
        "field_name": ["Field error message"]
    }
}

Authentication:
- All endpoints require authentication
- Include JWT token in Authorization header: "Bearer <token>"
- Role-based access control is enforced

Permissions:
- Teachers: Full access to their assignments and submissions
- Students: Read access to class assignments, full access to own submissions
- Parents: Read access to children's assignments and submissions
- Admins: Full access to all data

File Uploads:
- Use multipart/form-data for file uploads
- Maximum file size and allowed types are defined per assignment
- Files are automatically validated against assignment constraints

Filtering and Search:
- Django-filter integration for advanced filtering
- Search across title, description, student names, etc.
- Date range filtering for deadlines and submission dates

Pagination:
- Default page size: 20 items
- Configurable via page_size parameter
- Links to next/previous pages provided in response

Export Features:
- CSV export for assignment submissions
- Includes all relevant data for analysis
- Proper filename and content-disposition headers

Bulk Operations:
- Bulk grading of multiple submissions
- Batch plagiarism checking
- Bulk status updates for assignments

Real-time Features:
- Assignment publication triggers notifications
- Deadline reminders sent automatically
- Grade notifications to students and parents
"""
