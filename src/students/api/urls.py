# students/api/urls.py
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

app_name = "students_api"

# URL patterns for students API
urlpatterns = [
    # Student endpoints
    path(
        "students/",
        views.StudentListCreateAPIView.as_view(),
        name="student-list-create",
    ),
    path(
        "students/<uuid:pk>/",
        views.StudentRetrieveUpdateDestroyAPIView.as_view(),
        name="student-detail",
    ),
    path(
        "students/<uuid:student_id>/family-tree/",
        views.student_family_tree,
        name="student-family-tree",
    ),
    # Parent endpoints
    path(
        "parents/", views.ParentListCreateAPIView.as_view(), name="parent-list-create"
    ),
    path(
        "parents/<uuid:pk>/",
        views.ParentRetrieveUpdateDestroyAPIView.as_view(),
        name="parent-detail",
    ),
    # Relationship endpoints
    path(
        "relationships/",
        views.StudentParentRelationListCreateAPIView.as_view(),
        name="relationship-list-create",
    ),
    path(
        "relationships/<uuid:pk>/",
        views.StudentParentRelationRetrieveUpdateDestroyAPIView.as_view(),
        name="relationship-detail",
    ),
    # Bulk operations
    path(
        "students/bulk/import/", views.bulk_import_students, name="bulk-import-students"
    ),
    path("parents/bulk/import/", views.bulk_import_parents, name="bulk-import-parents"),
    path(
        "students/bulk/promote/", views.promote_students, name="bulk-promote-students"
    ),
    path(
        "students/bulk/graduate/",
        views.graduate_students,
        name="bulk-graduate-students",
    ),
    # Search and autocomplete
    path("search/advanced/", views.advanced_search, name="advanced-search"),
    path(
        "search/autocomplete/students/",
        views.student_autocomplete,
        name="student-autocomplete",
    ),
    path(
        "search/autocomplete/parents/",
        views.parent_autocomplete,
        name="parent-autocomplete",
    ),
    # Analytics
    path("analytics/", views.student_analytics, name="student-analytics"),
]
