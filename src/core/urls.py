from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = "core"

urlpatterns = [
    # Web views
    path("", views.dashboard, name="dashboard"),
    path("documents/", views.DocumentListView.as_view(), name="document_list"),
    # API endpoints
    path("api/", include("src.api.urls")),
]
