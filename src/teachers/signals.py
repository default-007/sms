from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from src.teachers.models import Teacher
from django.contrib.auth.models import Group

User = get_user_model()


@receiver(post_save, sender=Teacher)
def assign_teacher_role(sender, instance, created, **kwargs):
    """
    Assign the Teacher role to user when a Teacher profile is created.
    """
    if created:
        teacher_group, _ = Group.objects.get_or_create(name="Teacher")
        instance.user.groups.add(teacher_group)

        # Ensure the user is active
        if not instance.user.is_active:
            instance.user.is_active = True
            instance.user.save()


@receiver(post_delete, sender=Teacher)
def handle_teacher_delete(sender, instance, **kwargs):
    """
    Handle user cleanup when a Teacher profile is deleted.
    """
    user = instance.user
    if (
        user
        and not user.is_staff
        and not hasattr(user, "student_profile")
        and not hasattr(user, "parent_profile")
    ):
        user.delete()
