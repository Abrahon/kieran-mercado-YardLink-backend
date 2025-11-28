from django.db import models
from django.conf import settings
from .enums import MessageStatus, MessageCategory

class ContactMessage(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='contact_messages',null=True, 
    )
    name = models.CharField(max_length=100)
    message = models.TextField()
    category = models.CharField(
        max_length=20,
        choices=MessageCategory.choices,
        default=MessageCategory.GENERAL
    )
    status = models.CharField(
        max_length=10, choices=MessageStatus.choices, default=MessageStatus.NEW
    )
    created_at = models.DateTimeField(auto_now_add=True)
    replied_at = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f"{self.name} - {self.user.email}"
