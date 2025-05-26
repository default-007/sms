from django.urls import include, path

from . import views

app_name = "students"

# Student URLs
student_patterns = [
    path("", views.StudentListView.as_view(), name="student-list"),
    path("<uuid:pk>/", views.StudentDetailView.as_view(), name="student-detail"),
    path("create/", views.StudentCreateView.as_view(), name="student-create"),
    path("quick-add/", views.QuickStudentAddView.as_view(), name="student-quick-add"),
    path("<uuid:pk>/update/", views.StudentUpdateView.as_view(), name="student-update"),
    path("<uuid:pk>/delete/", views.StudentDeleteView.as_view(), name="student-delete"),
    path(
        "<uuid:pk>/status/",
        views.StudentStatusUpdateView.as_view(),
        name="student-status-update",
    ),
    path(
        "<uuid:pk>/id-card/",
        views.GenerateStudentIDCardView.as_view(),
        name="student-id-card",
    ),
    path(
        "<uuid:pk>/family-tree/",
        views.StudentFamilyTreeView.as_view(),
        name="student-family-tree",
    ),
    path(
        "autocomplete/",
        views.StudentAutocompleteView.as_view(),
        name="student-autocomplete",
    ),
    path("promotion/", views.StudentPromotionView.as_view(), name="student-promotion"),
    path(
        "graduation/", views.StudentGraduationView.as_view(), name="student-graduation"
    ),
]

# Parent URLs
parent_patterns = [
    path("", views.ParentListView.as_view(), name="parent-list"),
    path("<uuid:pk>/", views.ParentDetailView.as_view(), name="parent-detail"),
    path("create/", views.ParentCreateView.as_view(), name="parent-create"),
    path("<uuid:pk>/update/", views.ParentUpdateView.as_view(), name="parent-update"),
    path("<uuid:pk>/delete/", views.ParentDeleteView.as_view(), name="parent-delete"),
    path(
        "<uuid:pk>/students/",
        views.ParentStudentsView.as_view(),
        name="parent-students",
    ),
    path(
        "autocomplete/",
        views.ParentAutocompleteView.as_view(),
        name="parent-autocomplete",
    ),
]

# Relationship URLs
relationship_patterns = [
    path(
        "create/",
        views.StudentParentRelationCreateView.as_view(),
        name="relation-create",
    ),
    path(
        "<uuid:pk>/update/",
        views.StudentParentRelationUpdateView.as_view(),
        name="relation-update",
    ),
    path(
        "<uuid:pk>/delete/",
        views.StudentParentRelationDeleteView.as_view(),
        name="relation-delete",
    ),
    path(
        "<uuid:pk>/permissions/",
        views.RelationshipPermissionsUpdateView.as_view(),
        name="relation-permissions",
    ),
    path(
        "student/<uuid:student_id>/create/",
        views.StudentParentRelationCreateView.as_view(),
        name="relation-create-for-student",
    ),
    path(
        "parent/<uuid:parent_id>/create/",
        views.StudentParentRelationCreateView.as_view(),
        name="relation-create-for-parent",
    ),
    path(
        "quick-link/",
        views.QuickLinkParentToStudentView.as_view(),
        name="relation-quick-link",
    ),
    path(
        "bulk-manage/",
        views.BulkRelationshipManagementView.as_view(),
        name="relation-bulk-manage",
    ),
]

# Import/Export URLs
import_export_patterns = [
    # Import URLs
    path("import/", views.StudentBulkImportView.as_view(), name="student-import"),
    path("import/status/", views.ImportStatusView.as_view(), name="import-status"),
    # Export URLs
    path("export/", views.ExportStudentsView.as_view(), name="student-export"),
    path("export/bulk/", views.BulkExportView.as_view(), name="bulk-export"),
    # Template Downloads
    path(
        "templates/<str:template_type>/",
        views.DownloadCSVTemplateView.as_view(),
        name="download-template",
    ),
]

# Parent specific import/export
parent_import_export_patterns = [
    path("import/", views.ParentBulkImportView.as_view(), name="parent-import"),
    path("export/", views.ExportParentsView.as_view(), name="parent-export"),
]

# Main URL patterns
urlpatterns = [
    # Dashboard/Home
    path("", views.StudentListView.as_view(), name="dashboard"),
    # Student patterns
    path("students/", include(student_patterns)),
    # Parent patterns
    path("parents/", include(parent_patterns)),
    path("parents/", include(parent_import_export_patterns)),
    # Relationship patterns
    path("relationships/", include(relationship_patterns)),
    # Import/Export patterns
    path("", include(import_export_patterns)),
    path("api/", include("students.api.urls")),
]
