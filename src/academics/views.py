"""
Web Views for Academics Module

This module provides Django views for the academics app web interface.
These views complement the API and provide server-side rendered pages.
"""

from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import (
    TemplateView,
    ListView,
    DetailView,
    CreateView,
    UpdateView,
)
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.urls import reverse_lazy
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.db.models import Q

from .models import Department, AcademicYear, Term, Section, Grade, Class
from .services import (
    AcademicYearService,
    SectionService,
    GradeService,
    ClassService,
    TermService,
)


class AcademicsHomeView(LoginRequiredMixin, TemplateView):
    """Home view for academics module"""

    template_name = "academics/home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get current academic year
        current_year = AcademicYearService.get_current_academic_year()
        context["current_academic_year"] = current_year

        if current_year:
            # Get quick statistics
            context["quick_stats"] = {
                "sections_count": Section.objects.filter(is_active=True).count(),
                "grades_count": Grade.objects.filter(is_active=True).count(),
                "classes_count": Class.objects.filter(
                    academic_year=current_year, is_active=True
                ).count(),
                "current_term": current_year.get_current_term(),
            }

        return context


class DepartmentListView(LoginRequiredMixin, ListView):
    """List view for departments"""

    model = Department
    template_name = "academics/department_list.html"
    context_object_name = "departments"
    paginate_by = 20

    def get_queryset(self):
        queryset = Department.objects.filter(is_active=True)
        search = self.request.GET.get("search")
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) | Q(description__icontains=search)
            )
        return queryset.order_by("name")


class DepartmentDetailView(LoginRequiredMixin, DetailView):
    """Detail view for department"""

    model = Department
    template_name = "academics/department_detail.html"
    context_object_name = "department"


class AcademicYearListView(LoginRequiredMixin, ListView):
    """List view for academic years"""

    model = AcademicYear
    template_name = "academics/academic_year_list.html"
    context_object_name = "academic_years"
    paginate_by = 10

    def get_queryset(self):
        return AcademicYear.objects.all().order_by("-start_date")


class AcademicYearDetailView(LoginRequiredMixin, DetailView):
    """Detail view for academic year"""

    model = AcademicYear
    template_name = "academics/academic_year_detail.html"
    context_object_name = "academic_year"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            context["summary"] = AcademicYearService.get_academic_year_summary(
                self.object.id
            )
        except Exception:
            context["summary"] = None
        return context


class AcademicYearCreateView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    """Create view for academic year"""

    template_name = "academics/academic_year_create.html"
    permission_required = "academics.add_academicyear"

    def post(self, request, *args, **kwargs):
        """Handle academic year creation"""
        try:
            name = request.POST.get("name")
            start_date = request.POST.get("start_date")
            end_date = request.POST.get("end_date")
            is_current = request.POST.get("is_current") == "on"
            num_terms = int(request.POST.get("num_terms", 3))

            # Create academic year with terms
            academic_year = AcademicYearService.setup_academic_year_with_terms(
                name=name,
                start_date=start_date,
                end_date=end_date,
                num_terms=num_terms,
                user=request.user,
                is_current=is_current,
            )

            messages.success(request, f"Academic year {name} created successfully")
            return redirect("academics:academic-year-detail", pk=academic_year.id)

        except Exception as e:
            messages.error(request, f"Error creating academic year: {str(e)}")
            return self.get(request, *args, **kwargs)


class SectionListView(LoginRequiredMixin, ListView):
    """List view for sections"""

    model = Section
    template_name = "academics/section_list.html"
    context_object_name = "sections"

    def get_queryset(self):
        return Section.objects.filter(is_active=True).order_by("order_sequence")


class SectionDetailView(LoginRequiredMixin, DetailView):
    """Detail view for section"""

    model = Section
    template_name = "academics/section_detail.html"
    context_object_name = "section"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            context["hierarchy"] = SectionService.get_section_hierarchy(self.object.id)
        except Exception:
            context["hierarchy"] = None
        return context


class SectionHierarchyView(LoginRequiredMixin, DetailView):
    """Hierarchy view for section"""

    model = Section
    template_name = "academics/section_hierarchy.html"
    context_object_name = "section"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["hierarchy"] = SectionService.get_section_hierarchy(self.object.id)
        return context


class GradeListView(LoginRequiredMixin, ListView):
    """List view for grades"""

    model = Grade
    template_name = "academics/grade_list.html"
    context_object_name = "grades"
    paginate_by = 20

    def get_queryset(self):
        queryset = Grade.objects.filter(is_active=True)
        section_id = self.request.GET.get("section")
        if section_id:
            queryset = queryset.filter(section_id=section_id)
        return queryset.select_related("section").order_by("section", "order_sequence")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["sections"] = Section.objects.filter(is_active=True)
        return context


class GradeDetailView(LoginRequiredMixin, DetailView):
    """Detail view for grade"""

    model = Grade
    template_name = "academics/grade_detail.html"
    context_object_name = "grade"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            context["details"] = GradeService.get_grade_details(self.object.id)
        except Exception:
            context["details"] = None
        return context


class ClassListView(LoginRequiredMixin, ListView):
    """List view for classes"""

    model = Class
    template_name = "academics/class_list.html"
    context_object_name = "classes"
    paginate_by = 20

    def get_queryset(self):
        queryset = Class.objects.filter(is_active=True)

        # Filter by current academic year by default
        current_year = AcademicYearService.get_current_academic_year()
        if current_year:
            queryset = queryset.filter(academic_year=current_year)

        # Additional filters
        section_id = self.request.GET.get("section")
        grade_id = self.request.GET.get("grade")

        if section_id:
            queryset = queryset.filter(section_id=section_id)
        if grade_id:
            queryset = queryset.filter(grade_id=grade_id)

        return queryset.select_related(
            "grade__section", "academic_year", "class_teacher__user"
        ).order_by("section", "grade", "name")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["sections"] = Section.objects.filter(is_active=True)
        context["current_academic_year"] = (
            AcademicYearService.get_current_academic_year()
        )
        return context


class ClassDetailView(LoginRequiredMixin, DetailView):
    """Detail view for class"""

    model = Class
    template_name = "academics/class_detail.html"
    context_object_name = "class"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            context["details"] = ClassService.get_class_details(self.object.id)
            context["analytics"] = ClassService.get_class_analytics(self.object.id)
        except Exception:
            context["details"] = None
            context["analytics"] = None
        return context


class ClassCreateView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    """Create view for class"""

    template_name = "academics/class_create.html"
    permission_required = "academics.add_class"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["grades"] = Grade.objects.filter(is_active=True).select_related(
            "section"
        )
        context["academic_years"] = AcademicYear.objects.all().order_by("-start_date")
        return context

    def post(self, request, *args, **kwargs):
        """Handle class creation"""
        try:
            name = request.POST.get("name")
            grade_id = request.POST.get("grade")
            academic_year_id = request.POST.get("academic_year")
            room_number = request.POST.get("room_number", "")
            capacity = int(request.POST.get("capacity", 30))

            cls = ClassService.create_class(
                name=name,
                grade_id=int(grade_id),
                academic_year_id=int(academic_year_id),
                room_number=room_number,
                capacity=capacity,
            )

            messages.success(request, f"Class {cls.display_name} created successfully")
            return redirect("academics:class-detail", pk=cls.id)

        except Exception as e:
            messages.error(request, f"Error creating class: {str(e)}")
            return self.get(request, *args, **kwargs)


class TermListView(LoginRequiredMixin, ListView):
    """List view for terms"""

    model = Term
    template_name = "academics/term_list.html"
    context_object_name = "terms"

    def get_queryset(self):
        queryset = Term.objects.all()
        academic_year_id = self.request.GET.get("academic_year")
        if academic_year_id:
            queryset = queryset.filter(academic_year_id=academic_year_id)
        return queryset.select_related("academic_year").order_by(
            "academic_year", "term_number"
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["academic_years"] = AcademicYear.objects.all().order_by("-start_date")
        return context


class TermDetailView(LoginRequiredMixin, DetailView):
    """Detail view for term"""

    model = Term
    template_name = "academics/term_detail.html"
    context_object_name = "term"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            context["summary"] = TermService.get_term_summary(self.object.id)
        except Exception:
            context["summary"] = None
        return context


class AcademicsAnalyticsView(LoginRequiredMixin, TemplateView):
    """Analytics view for academics"""

    template_name = "academics/analytics.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        current_year = AcademicYearService.get_current_academic_year()
        if current_year:
            # Section analytics
            sections_summary = SectionService.get_sections_summary()
            context["sections_summary"] = sections_summary

            # Academic year summary
            year_summary = AcademicYearService.get_academic_year_summary(
                current_year.id
            )
            context["year_summary"] = year_summary

        return context


class AcademicsReportsView(LoginRequiredMixin, TemplateView):
    """Reports view for academics"""

    template_name = "academics/reports.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["academic_years"] = AcademicYear.objects.all().order_by("-start_date")
        return context


class AcademicStructureView(LoginRequiredMixin, TemplateView):
    """Academic structure view"""

    template_name = "academics/structure.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get current academic year
        current_year = AcademicYearService.get_current_academic_year()
        context["current_academic_year"] = current_year

        if current_year:
            # Build structure data
            sections = Section.objects.filter(is_active=True).order_by("order_sequence")
            structure_data = []

            for section in sections:
                section_data = {"section": section, "grades": []}

                grades = section.get_grades()
                for grade in grades:
                    grade_data = {
                        "grade": grade,
                        "classes": grade.get_classes(current_year),
                    }
                    section_data["grades"].append(grade_data)

                structure_data.append(section_data)

            context["structure_data"] = structure_data

        return context


class AcademicCalendarView(LoginRequiredMixin, TemplateView):
    """Academic calendar view"""

    template_name = "academics/calendar.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        academic_year_id = self.request.GET.get("academic_year_id")
        if not academic_year_id:
            current_year = AcademicYearService.get_current_academic_year()
            if current_year:
                academic_year_id = current_year.id

        if academic_year_id:
            try:
                calendar_data = TermService.get_term_calendar(int(academic_year_id))
                context["calendar_data"] = calendar_data
            except Exception:
                context["calendar_data"] = None

        context["academic_years"] = AcademicYear.objects.all().order_by("-start_date")
        return context


# AJAX Views for dynamic content


@login_required
def get_grades_by_section(request):
    """AJAX view to get grades by section"""
    section_id = request.GET.get("section_id")
    if not section_id:
        return JsonResponse({"error": "Section ID required"}, status=400)

    try:
        grades = GradeService.get_grades_by_section(int(section_id))
        return JsonResponse({"grades": grades})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)


@login_required
def get_classes_by_grade(request):
    """AJAX view to get classes by grade"""
    grade_id = request.GET.get("grade_id")
    academic_year_id = request.GET.get("academic_year_id")

    if not grade_id:
        return JsonResponse({"error": "Grade ID required"}, status=400)

    try:
        classes = ClassService.get_classes_by_grade(
            int(grade_id),
            academic_year_id=int(academic_year_id) if academic_year_id else None,
        )
        return JsonResponse({"classes": classes})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)
