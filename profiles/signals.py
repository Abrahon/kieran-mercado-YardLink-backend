from django.db.models.signals import post_save
from django.dispatch import receiver
from django.apps import apps
from django.conf import settings
from .models import AdminProfile
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from .models import LandscaperProfilies
User = apps.get_model(settings.AUTH_USER_MODEL)

User = get_user_model()

@receiver(post_save, sender=User)
def create_admin_profile(sender, instance, created, **kwargs):
    if created:
        AdminProfile.objects.get_or_create(user=instance)

@receiver(post_save, sender=User)
def save_admin_profile(sender, instance, **kwargs):
    # Use the correct related name from AdminProfile
    try:
        instance.admin_profile.save()
    except AdminProfile.DoesNotExist:
        pass
# profiles/signals.py



@receiver(post_save, sender=User)
def create_landscaper_profile(sender, instance, created, **kwargs):
    if created and instance.role == "landscaper":
        LandscaperProfilies.objects.get_or_create(
            user=instance
        )