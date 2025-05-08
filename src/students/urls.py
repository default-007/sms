# students/urls.py
from django.urls import path
from . import views

urlpatterns = [
    # Student URLs
    path("", views.StudentListView.as_view(), name="student-list"),
    path("<int:pk>/", views.StudentDetailView.as_view(), name="student-detail"),
    path("create/", views.StudentCreateView.as_view(), name="student-create"),
    path("<int:pk>/update/", views.StudentUpdateView.as_view(), name="student-update"),
    path("<int:pk>/delete/", views.StudentDeleteView.as_view(), name="student-delete"),
    path("promotion/", views.StudentPromotionView.as_view(), name="student-promotion"),
    path(
        "graduation/", views.StudentGraduationView.as_view(), name="student-graduation"
    ),
    path(
        "<int:pk>/id-card/",
        views.GenerateStudentIDCardView.as_view(),
        name="student-id-card",
    ),
    # Import/Export URLs
    path("import/", views.StudentBulkImportView.as_view(), name="student-import"),
    path("export/", views.ExportStudentsView.as_view(), name="student-export"),
    # Parent URLs
    path("parents/", views.ParentListView.as_view(), name="parent-list"),
    path("parents/<int:pk>/", views.ParentDetailView.as_view(), name="parent-detail"),
    path("parents/create/", views.ParentCreateView.as_view(), name="parent-create"),
    path(
        "parents/<int:pk>/update/",
        views.ParentUpdateView.as_view(),
        name="parent-update",
    ),
    path(
        "parents/<int:pk>/delete/",
        views.ParentDeleteView.as_view(),
        name="parent-delete",
    ),
    path("parents/import/", views.ParentBulkImportView.as_view(), name="parent-import"),
    path("parents/export/", views.ExportParentsView.as_view(), name="parent-export"),
    # Relation URLs
    path(
        "relation/create/",
        views.StudentParentRelationCreateView.as_view(),
        name="relation-create",
    ),
    path(
        "relation/<int:pk>/update/",
        views.StudentParentRelationUpdateView.as_view(),
        name="relation-update",
    ),
    path(
        "relation/<int:pk>/delete/",
        views.StudentParentRelationDeleteView.as_view(),
        name="relation-delete",
    ),
    path(
        "relation/student/<int:student_id>/create/",
        views.StudentParentRelationCreateView.as_view(),
        name="relation-create-for-student",
    ),
    path(
        "relation/parent/<int:parent_id>/create/",
        views.StudentParentRelationCreateView.as_view(),
        name="relation-create-for-parent",
    ),
    path(
        "relation/quick-link/",
        views.QuickLinkParentToStudentView.as_view(),
        name="relation-quick-link",
    ),
]
