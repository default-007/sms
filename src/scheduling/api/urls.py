from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    TimeSlotViewSet,
    RoomViewSet,
    TimetableViewSet,
    SubstituteTeacherViewSet,
    TimetableGenerationViewSet,
    SchedulingAnalyticsViewSet,
    SchedulingConstraintViewSet,
    TimetableTemplateViewSet,
)

# Create router and register viewsets
router = DefaultRouter()
router.register(r"time-slots", TimeSlotViewSet, basename="time-slot")
router.register(r"rooms", RoomViewSet, basename="room")
router.register(r"timetables", TimetableViewSet, basename="timetable")
router.register(r"substitutes", SubstituteTeacherViewSet, basename="substitute")
router.register(r"generations", TimetableGenerationViewSet, basename="generation")
router.register(r"analytics", SchedulingAnalyticsViewSet, basename="analytics")
router.register(r"constraints", SchedulingConstraintViewSet, basename="constraint")
router.register(r"templates", TimetableTemplateViewSet, basename="template")

app_name = "scheduling"

urlpatterns = [
    path("", include(router.urls)),
]
