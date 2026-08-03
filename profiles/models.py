from django.db import models
from django.contrib.auth import get_user_model
from cloudinary.models import CloudinaryField
# from landscapers .models import BusinessProfile
#  from landscapers.models import BusinessProfile
from invitations .models import TeamInvitation
from accounts.models import User
from subscriptions.models import Plan
from landscapers.models import BusinessProfile

User = get_user_model()

class AdminProfile(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="admin_profile"
    )

    phone = models.CharField(max_length=15, blank=True, null=True)
    image = CloudinaryField("admin_profile", blank=True, null=True)

    def __str__(self):
        return f"{self.user.name}"


# profiles/models.py
class WorkerProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    pro_landscaper = models.ForeignKey(
        "landscapers.BusinessProfile",
        on_delete=models.CASCADE,  # 🔹 required
        null=True,
        blank=True
    )
    
    name = models.CharField(max_length=255, default="Worker")
    phone = models.CharField(max_length=20, blank=True, default="")
    image = CloudinaryField("worker_profile", blank=True, null=True)
    is_blocked = models.BooleanField(default=False)

    def __str__(self):
        return self.name

        


# profiles/models.py
class LandscaperProfilies(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="landscaperprofilies"
    )
    name = models.CharField(max_length=255, default="Landscaper")
    phone = models.CharField(max_length=20, blank=True, default="")
    image = CloudinaryField("landscaper_profile", blank=True, null=True)
    stripe_account_id = models.CharField(max_length=255, blank=True, null=True)
    plan = models.ForeignKey(Plan, on_delete=models.SET_NULL, null=True, blank=True)
    calendar_sync = models.BooleanField(default=False)
    job_reminder= models.BooleanField(default=False)


# client
class ClientProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=255, default="Client")
    phone = models.CharField(max_length=20, blank=True, default="")
    image = CloudinaryField("client_profile", blank=True, null=True)
    calendar_sync = models.BooleanField(default=False)

    service_reminder = models.BooleanField(default=False)

    def __str__(self):
        return self.name




from django.db import models
from django.conf import settings
from landscapers.models import BusinessProfile


class ExternalClient(models.Model):
    landscaper = models.ForeignKey(
        BusinessProfile,
        on_delete=models.CASCADE,
        related_name="external_clients"
    )

    name = models.CharField(max_length=255)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=30, blank=True, null=True)
    company_name = models.CharField(max_length=255, blank=True, null=True)

    address = models.TextField(blank=True, null=True)
    notes = models.TextField(blank=True, null=True)

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["landscaper", "email", "phone"],
                name="unique_external_client_per_landscaper_email_phone"
            )
        ]

    def __str__(self):
        return self.name



