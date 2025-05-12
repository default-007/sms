from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from . import views

# Create a router and register our viewsets with it
router = DefaultRouter()
router.register(r"users", views.UserViewSet)
router.register(r"roles", views.UserRoleViewSet)
router.register(r"students", views.StudentViewSet)
router.register(r"parents", views.ParentViewSet)
router.register(r"student-parent-relations", views.StudentParentRelationViewSet)
router.register(r"teachers", views.TeacherViewSet)
router.register(r"teacher-class-assignments", views.TeacherClassAssignmentViewSet)
router.register(r"teacher-evaluations", views.TeacherEvaluationViewSet)
router.register(r"departments", views.DepartmentViewSet)
router.register(r"academic-years", views.AcademicYearViewSet)
router.register(r"grades", views.GradeViewSet)
router.register(r"sections", views.SectionViewSet)
router.register(r"classes", views.ClassViewSet)
router.register(r"subjects", views.SubjectViewSet)
router.register(r"syllabi", views.SyllabusViewSet)
router.register(r"time-slots", views.TimeSlotViewSet)
router.register(r"timetables", views.TimetableViewSet)
router.register(r"assignments", views.AssignmentViewSet)
router.register(r"assignment-submissions", views.AssignmentSubmissionViewSet)
router.register(r"system-settings", views.SystemSettingViewSet)
router.register(r"documents", views.DocumentViewSet)

# Authentication endpoints
auth_urlpatterns = [
    path("token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
]

urlpatterns = [
    # API endpoints
    path("", include(router.urls)),
    # Authentication endpoints
    path("auth/", include(auth_urlpatterns)),
    # API Documentation (if using DRF's browsable API)
    path("auth/", include("rest_framework.urls", namespace="rest_framework")),
]
