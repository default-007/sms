from django.urls import path

from . import views

app_name = "courses"

urlpatterns = [
    # Department URLs
    path("departments/", views.DepartmentListView.as_view(), name="department-list"),
    path(
        "departments/create/",
        views.DepartmentCreateView.as_view(),
        name="department-create",
    ),
    path(
        "departments/<int:pk>/",
        views.DepartmentDetailView.as_view(),
        name="department-detail",
    ),
    path(
        "departments/<int:pk>/update/",
        views.DepartmentUpdateView.as_view(),
        name="department-update",
    ),
    path(
        "departments/<int:pk>/delete/",
        views.DepartmentDeleteView.as_view(),
        name="department-delete",
    ),
    # Academic Year URLs
    path(
        "academic-years/",
        views.AcademicYearListView.as_view(),
        name="academic-year-list",
    ),
    path(
        "academic-years/create/",
        views.AcademicYearCreateView.as_view(),
        name="academic-year-create",
    ),
    path(
        "academic-years/<int:pk>/",
        views.AcademicYearDetailView.as_view(),
        name="academic-year-detail",
    ),
    path(
        "academic-years/<int:pk>/update/",
        views.AcademicYearUpdateView.as_view(),
        name="academic-year-update",
    ),
    path(
        "academic-years/<int:pk>/delete/",
        views.AcademicYearDeleteView.as_view(),
        name="academic-year-delete",
    ),
    path(
        "academic-years/<int:pk>/set-current/",
        views.set_current_academic_year,
        name="set-current-academic-year",
    ),
    # Grade URLs
    path("grades/", views.GradeListView.as_view(), name="grade-list"),
    path("grades/create/", views.GradeCreateView.as_view(), name="grade-create"),
    path("grades/<int:pk>/", views.GradeDetailView.as_view(), name="grade-detail"),
    path(
        "grades/<int:pk>/update/", views.GradeUpdateView.as_view(), name="grade-update"
    ),
    path(
        "grades/<int:pk>/delete/", views.GradeDeleteView.as_view(), name="grade-delete"
    ),
    # Section URLs
    path("sections/", views.SectionListView.as_view(), name="section-list"),
    path("sections/create/", views.SectionCreateView.as_view(), name="section-create"),
    path(
        "sections/<int:pk>/", views.SectionDetailView.as_view(), name="section-detail"
    ),
    path(
        "sections/<int:pk>/update/",
        views.SectionUpdateView.as_view(),
        name="section-update",
    ),
    path(
        "sections/<int:pk>/delete/",
        views.SectionDeleteView.as_view(),
        name="section-delete",
    ),
    # Class URLs
    path("classes/", views.ClassListView.as_view(), name="class-list"),
    path("classes/create/", views.ClassCreateView.as_view(), name="class-create"),
    path("classes/<int:pk>/", views.ClassDetailView.as_view(), name="class-detail"),
    path(
        "classes/<int:pk>/update/", views.ClassUpdateView.as_view(), name="class-update"
    ),
    path(
        "classes/<int:pk>/delete/", views.ClassDeleteView.as_view(), name="class-delete"
    ),
    path("classes/<int:pk>/students/", views.class_students, name="class-students"),
    path("classes/<int:pk>/timetable/", views.class_timetable, name="class-timetable"),
    # Subject URLs
    path("subjects/", views.SubjectListView.as_view(), name="subject-list"),
    path("subjects/create/", views.SubjectCreateView.as_view(), name="subject-create"),
    path(
        "subjects/<int:pk>/", views.SubjectDetailView.as_view(), name="subject-detail"
    ),
    path(
        "subjects/<int:pk>/update/",
        views.SubjectUpdateView.as_view(),
        name="subject-update",
    ),
    path(
        "subjects/<int:pk>/delete/",
        views.SubjectDeleteView.as_view(),
        name="subject-delete",
    ),
    # Syllabus URLs
    path("syllabus/", views.SyllabusListView.as_view(), name="syllabus-list"),
    path(
        "syllabus/create/", views.SyllabusCreateView.as_view(), name="syllabus-create"
    ),
    path(
        "syllabus/<int:pk>/", views.SyllabusDetailView.as_view(), name="syllabus-detail"
    ),
    path(
        "syllabus/<int:pk>/update/",
        views.SyllabusUpdateView.as_view(),
        name="syllabus-update",
    ),
    path(
        "syllabus/<int:pk>/delete/",
        views.SyllabusDeleteView.as_view(),
        name="syllabus-delete",
    ),
    # Timetable URLs
    path("timetable/", views.TimetableListView.as_view(), name="timetable-list"),
    path(
        "timetable/create/",
        views.TimetableCreateView.as_view(),
        name="timetable-create",
    ),
    path(
        "timetable/<int:pk>/",
        views.TimetableDetailView.as_view(),
        name="timetable-detail",
    ),
    path(
        "timetable/<int:pk>/update/",
        views.TimetableUpdateView.as_view(),
        name="timetable-update",
    ),
    path(
        "timetable/<int:pk>/delete/",
        views.TimetableDeleteView.as_view(),
        name="timetable-delete",
    ),
    path("timetable/generate/", views.generate_timetable, name="generate-timetable"),
    # TimeSlot URLs
    path("timeslots/", views.TimeSlotListView.as_view(), name="timeslot-list"),
    path(
        "timeslots/create/", views.TimeSlotCreateView.as_view(), name="timeslot-create"
    ),
    path(
        "timeslots/<int:pk>/update/",
        views.TimeSlotUpdateView.as_view(),
        name="timeslot-update",
    ),
    path(
        "timeslots/<int:pk>/delete/",
        views.TimeSlotDeleteView.as_view(),
        name="timeslot-delete",
    ),
    # Assignment URLs
    path("assignments/", views.AssignmentListView.as_view(), name="assignment-list"),
    path(
        "assignments/create/",
        views.AssignmentCreateView.as_view(),
        name="assignment-create",
    ),
    path(
        "assignments/<int:pk>/",
        views.AssignmentDetailView.as_view(),
        name="assignment-detail",
    ),
    path(
        "assignments/<int:pk>/update/",
        views.AssignmentUpdateView.as_view(),
        name="assignment-update",
    ),
    path(
        "assignments/<int:pk>/delete/",
        views.AssignmentDeleteView.as_view(),
        name="assignment-delete",
    ),
    path(
        "assignments/<int:pk>/submissions/",
        views.assignment_submissions,
        name="assignment-submissions",
    ),
    path(
        "assignments/<int:pk>/submit/",
        views.submit_assignment,
        name="submit-assignment",
    ),
    path(
        "assignment-submissions/<int:pk>/grade/",
        views.grade_assignment,
        name="grade-assignment",
    ),
    # Dashboard
    path("dashboard/", views.courses_dashboard, name="dashboard"),
    # Class Analytics
    path("classes/<int:pk>/analytics/", views.class_analytics, name="class-analytics"),
    # Subject Analytics
    path(
        "subjects/<int:pk>/analytics/",
        views.subject_analytics,
        name="subject-analytics",
    ),
    # Department Analytics
    path(
        "departments/<int:pk>/analytics/",
        views.department_analytics,
        name="department-analytics",
    ),
    # Timetable API
    path(
        "timetable/check-clashes/",
        views.check_timetable_clashes,
        name="check-timetable-clashes",
    ),
    path(
        "timetable/teacher/<int:teacher_id>/",
        views.get_teacher_timetable,
        name="teacher-timetable",
    ),
    path("timetable/confirm/", views.confirm_timetable, name="confirm-timetable"),
]
