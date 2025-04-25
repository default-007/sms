from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from src.students.models import Student, Parent, StudentParentRelation
from django.contrib.auth.models import Group

User = get_user_model()


@receiver(post_save, sender=Student)
def assign_student_role(sender, instance, created, **kwargs):
    """
    Assign the Student role to user when a Student profile is created.
    """
    if created:
        student_group, _ = Group.objects.get_or_create(name="Student")
        instance.user.groups.add(student_group)

        # Ensure the user is active
        if not instance.user.is_active:
            instance.user.is_active = True
            instance.user.save()


@receiver(post_save, sender=Parent)
def assign_parent_role(sender, instance, created, **kwargs):
    """
    Assign the Parent role to user when a Parent profile is created.
    """
    if created:
        parent_group, _ = Group.objects.get_or_create(name="Parent")
        instance.user.groups.add(parent_group)

        # Ensure the user is active
        if not instance.user.is_active:
            instance.user.is_active = True
            instance.user.save()


@receiver(post_delete, sender=Student)
def handle_student_delete(sender, instance, **kwargs):
    """
    Handle user cleanup when a Student profile is deleted.
    """
    # This is a simple implementation. In production, you might want to:
    # 1. Archive the user instead of deleting
    # 2. Check if the user has other roles before deletion
    user = instance.user
    if (
        user
        and not user.is_staff
        and not hasattr(user, "teacher_profile")
        and not hasattr(user, "parent_profile")
    ):
        user.delete()


@receiver(post_delete, sender=Parent)
def handle_parent_delete(sender, instance, **kwargs):
    """
    Handle user cleanup when a Parent profile is deleted.
    """
    user = instance.user
    if (
        user
        and not user.is_staff
        and not hasattr(user, "teacher_profile")
        and not hasattr(user, "student_profile")
    ):
        user.delete()
