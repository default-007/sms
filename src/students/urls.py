# students/urls.py
from django.contrib.auth.decorators import login_required
from django.urls import include, path

# Import standard student views
from .views import (
    BulkStudentImportView,
    GenerateStudentIDCardView,
    QuickStudentCreateView,
    StudentCreateView,
    StudentDeleteView,
    StudentDetailView,
    StudentListView,
    StudentPromotionView,
    StudentStatusUpdateView,
    StudentUpdateView,
    export_students_csv,
    student_analytics_view,
    student_search_ajax,
    toggle_student_status,
    bulk_student_action,
)

# Import parent-related views
from .views.parent_views import (
    ParentCreateView,
    ParentDeleteView,
    ParentDetailView,
    ParentListView,
    ParentUpdateView,
    # StudentParentRelationCreateView,
    # StudentParentRelationDeleteView,
    # StudentParentRelationUpdateView,
)

# Import new import/export views
from .views.import_export_views import (
    StudentImportView,
    StudentExportView,
    download_import_template,
    validate_import_file,
)

app_name = "students"

urlpatterns = [
    # ================================
    # STUDENT MANAGEMENT URLS
    # ================================
    # Basic CRUD operations
    path("", login_required(StudentListView.as_view()), name="student-list"),
    path("create/", login_required(StudentCreateView.as_view()), name="student-create"),
    path(
        "quick-create/",
        login_required(QuickStudentCreateView.as_view()),
        name="quick-student-create",
    ),
    path(
        "<uuid:pk>/", login_required(StudentDetailView.as_view()), name="student-detail"
    ),
    path(
        "<uuid:pk>/edit/",
        login_required(StudentUpdateView.as_view()),
        name="student-update",
    ),
    path(
        "<uuid:pk>/delete/",
        login_required(StudentDeleteView.as_view()),
        name="student-delete",
    ),
    path(
        "<uuid:pk>/status/",
        login_required(StudentStatusUpdateView.as_view()),
        name="student-status-update",
    ),
    # Student actions
    path(
        "<uuid:pk>/generate-id/",
        login_required(GenerateStudentIDCardView.as_view()),
        name="generate-id-card",
    ),
    path("<uuid:pk>/analytics/", student_analytics_view, name="student-analytics"),
    # ================================
    # IMPORT/EXPORT FUNCTIONALITY
    # ================================
    # Import operations
    path("import/", login_required(StudentImportView.as_view()), name="student-import"),
    path("import/template/", download_import_template, name="download-import-template"),
    path("import/validate/", validate_import_file, name="validate-import-file"),
    # Export operations
    path("export/", login_required(StudentExportView.as_view()), name="student-export"),
    path("export/csv/", export_students_csv, name="export-csv"),
    # Legacy export (redirect to new export)
    path(
        "bulk-import/", login_required(StudentImportView.as_view()), name="bulk-import"
    ),  # Backwards compatibility
    path("bulk-action/", bulk_student_action, name="bulk-action"),
    # ================================
    # BULK OPERATIONS
    # ================================
    # Bulk student operations
    path(
        "promotion/", login_required(StudentPromotionView.as_view()), name="promotion"
    ),
    # ================================
    # AJAX ENDPOINTS
    # ================================
    # AJAX operations
    path("ajax/search/", student_search_ajax, name="search-ajax"),
    path("ajax/toggle-status/<uuid:pk>/", toggle_student_status, name="toggle-status"),
    # ================================
    # PARENT MANAGEMENT URLS
    # ================================
    # Parent CRUD operations
    path("parents/", login_required(ParentListView.as_view()), name="parent-list"),
    path(
        "parents/create/",
        login_required(ParentCreateView.as_view()),
        name="parent-create",
    ),
    path(
        "parents/<uuid:pk>/",
        login_required(ParentDetailView.as_view()),
        name="parent-detail",
    ),
    path(
        "parents/<uuid:pk>/edit/",
        login_required(ParentUpdateView.as_view()),
        name="parent-update",
    ),
    path(
        "parents/<uuid:pk>/delete/",
        login_required(ParentDeleteView.as_view()),
        name="parent-delete",
    ),
    # ================================
    # STUDENT-PARENT RELATIONSHIPS
    # ================================
    # Student-Parent relationship management
]
