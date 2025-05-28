from django.core.management.base import BaseCommand
from core.utils import generate_unique_id
from students.models import Student

class Command(BaseCommand):
    help = 'Generate registration numbers for students who don\'t have them'

    def handle(self, *args, **options):
        students_without_reg = Student.objects.filter(
            registration_number__isnull=True
        ).or_(
            Student.objects.filter(registration_number='')
        )
        
        updated_count = 0
        for student in students_without_reg:
            if student.admission_date:
                admission_year = student.admission_date.year
                # Generate unique registration number
                while True:
                    reg_number = f"STU-{admission_year}-{generate_unique_id(6)}"
                    if not Student.objects.filter(registration_number=reg_number).exists():
                        student.registration_number = reg_number
                        student.save()
                        updated_count += 1
                        break
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully generated registration numbers for {updated_count} students'
            ))