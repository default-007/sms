from django.urls import path
from . import views

urlpatterns = [
    # Student URLs
    path("", views.StudentListView.as_view(), name="student-list"),
    path("<int:pk>/", views.StudentDetailView.as_view(), name="student-detail"),
    path("create/", views.StudentCreateView.as_view(), name="student-create"),
    path("<int:pk>/update/", views.StudentUpdateView.as_view(), name="student-update"),
    path("<int:pk>/delete/", views.StudentDeleteView.as_view(), name="student-delete"),
    # Parent URLs
    path("parents/", views.ParentListView.as_view(), name="parent-list"),
    path("parents/<int:pk>/", views.ParentDetailView.as_view(), name="parent-detail"),
    path("parents/create/", views.ParentCreateView.as_view(), name="parent-create"),
    path(
        "parents/<int:pk>/update/",
        views.ParentUpdateView.as_view(),
        name="parent-update",
    ),
    # Relation URLs
    path(
        "relation/create/",
        views.StudentParentRelationCreateView.as_view(),
        name="relation-create",
    ),
]
