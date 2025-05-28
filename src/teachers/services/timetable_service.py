# src/teachers/services/timetable_service.py
import io
from datetime import datetime

from django.core.exceptions import ObjectDoesNotExist
from django.http import HttpResponse
from django.template.loader import get_template
from xhtml2pdf import pisa

from src.academics.models import AcademicYear
from src.scheduling.models import Timetable


class TimetableService:
    """Service for timetable operations, including PDF generation."""

    @staticmethod
    def generate_timetable_pdf(teacher, academic_year=None, template_name=None):
        """Generate a PDF of a teacher's timetable."""
        from src.teachers.services import TeacherService

        # Get timetable data for the teacher
        timetable = TeacherService.get_teacher_timetable(teacher, academic_year)

        # Template path
        template_path = template_name or "teachers/teacher_timetable_pdf.html"

        # Context data
        context = {
            "teacher": teacher,
            "timetable": timetable,
            "academic_year": academic_year,
            "current_date": datetime.now().strftime("%d %b, %Y"),
        }

        # Render template
        template = get_template(template_path)
        html = template.render(context)

        # Create a file-like buffer to receive PDF data
        buffer = io.BytesIO()

        # Create the PDF object using the buffer as its "file"
        pdf = pisa.pisaDocument(io.BytesIO(html.encode("UTF-8")), buffer)

        # Get the value of the BytesIO buffer
        pdf_data = buffer.getvalue()
        buffer.close()

        # Return the response with appropriate headers
        response = HttpResponse(content_type="application/pdf")
        response["Content-Disposition"] = (
            f'attachment; filename="Timetable_{teacher.employee_id}.pdf"'
        )
        response.write(pdf_data)

        return response

    @staticmethod
    def get_teacher_availability(teacher, date=None):
        """Get teacher availability for a specific date or current day."""

        if date is None:
            date = datetime.now().date()

        day_of_week = date.strftime("%A")

        try:
            current_academic_year = AcademicYear.objects.get(is_current=True)
            teacher_timetable = (
                Timetable.objects.filter(
                    teacher=teacher,
                    time_slot__day_of_week=day_of_week,
                    is_active=True,
                    effective_from_date__lte=date,
                    effective_to_date__gte=date,
                    academic_year=current_academic_year,
                )
                .select_related("time_slot", "subject", "class_instance")
                .order_by("time_slot__start_time")
            )

            timeslots = []
            for tt in teacher_timetable:
                timeslots.append(
                    {
                        "time_slot": tt.time_slot,
                        "subject": tt.subject,
                        "class_instance": tt.class_instance,
                        "room": tt.room,
                    }
                )

            return {"date": date, "day_of_week": day_of_week, "timeslots": timeslots}

        except ObjectDoesNotExist:
            return {"date": date, "day_of_week": day_of_week, "timeslots": []}
