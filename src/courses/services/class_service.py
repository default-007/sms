from src.courses.models import Class, Timetable, TimeSlot


class ClassService:
    @staticmethod
    def get_class_by_id(class_id):
        try:
            return Class.objects.get(id=class_id)
        except Class.DoesNotExist:
            return None

    @staticmethod
    def get_class_students(class_obj):
        try:
            return class_obj.students.all()
        except (DatabaseError, ProgrammingError):
            return []

    @staticmethod
    def get_class_timetable(class_obj, day=None):
        timetable_entries = Timetable.objects.filter(
            class_obj=class_obj, is_active=True
        ).select_related("subject", "teacher", "time_slot")

        if day is not None:
            timetable_entries = timetable_entries.filter(time_slot__day_of_week=day)

        return timetable_entries.order_by(
            "time_slot__day_of_week", "time_slot__start_time"
        )

    @staticmethod
    def check_timetable_clash(class_obj, time_slot, exclude_id=None):
        """Check if there's any clash in the timetable for a given class and time slot"""
        query = Timetable.objects.filter(
            class_obj=class_obj, time_slot=time_slot, is_active=True
        )

        if exclude_id:
            query = query.exclude(id=exclude_id)

        return query.exists()
