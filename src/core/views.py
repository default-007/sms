from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.views.generic import ListView, DetailView, UpdateView
from django.utils.decorators import method_decorator
from django.contrib import messages
from django.db.models import Q
from django.apps import apps

from .models import SystemSetting, AuditLog, Document
from .decorators import role_required, audit_log
from .utils import get_system_setting


@login_required
def dashboard(request):
    """Main dashboard view."""
    context = {
        "title": "Dashboard",
    }

    # Get relevant statistics based on user role
    if request.user.is_staff:
        # Admin dashboard
        Student = apps.get_model("students", "Student")
        Teacher = apps.get_model("teachers", "Teacher")

        context.update(
            {
                "total_students": Student.objects.count(),
                "total_teachers": Teacher.objects.count(),
                "recent_activities": AuditLog.objects.order_by("-timestamp")[:10],
            }
        )
    elif hasattr(request.user, "teacher"):
        # Teacher dashboard
        Teacher = apps.get_model("teachers", "Teacher")
        Class = apps.get_model("courses", "Class")
        Assignment = apps.get_model("courses", "Assignment")

        teacher = request.user.teacher

        context.update(
            {
                "teacher": teacher,
                "assigned_classes": Class.objects.filter(
                    teacherclassassignment__teacher=teacher
                ).distinct(),
                "pending_assignments": Assignment.objects.filter(
                    teacher=teacher, status__in=["draft", "published"]
                ).count(),
            }
        )
    elif hasattr(request.user, "parent"):
        # Parent dashboard
        Parent = apps.get_model("students", "Parent")
        Student = apps.get_model("students", "Student")

        parent = request.user.parent
        children = Student.objects.filter(studentparentrelation__parent=parent)

        context.update(
            {
                "parent": parent,
                "children": children,
            }
        )

    return render(request, "core/dashboard.html", context)


@method_decorator(login_required, name="dispatch")
class DocumentListView(ListView):
    model = Document
    template_name = "core/document_list.html"
    context_object_name = "documents"
    paginate_by = 20

    def get_queryset(self):
        queryset = super().get_queryset()

        # Filter by public documents or user's own documents
        if not self.request.user.is_staff:
            queryset = queryset.filter(
                Q(is_public=True) | Q(uploaded_by=self.request.user)
            )

        # Apply search if provided
        search_query = self.request.GET.get("q")
        if search_query:
            queryset = queryset.filter(
                Q(title__icontains=search_query)
                | Q(description__icontains=search_query)
                | Q(category__icontains=search_query)
            )

        # Filter by category if provided
        category = self.request.GET.get("category")
        if category:
            queryset = queryset.filter(category=category)

        return queryset.order_by("-upload_date")
