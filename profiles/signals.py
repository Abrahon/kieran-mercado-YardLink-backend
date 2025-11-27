from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
from .models import AdminProfile

User = settings.AUTH_USER_MODEL

@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_admin_profile(sender, instance, created, **kwargs):
    if created:
        AdminProfile.objects.create(user=instance)

@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def save_admin_profile(sender, instance, **kwargs):
    if hasattr(instance, 'profile'):
        instance.profile.save()

