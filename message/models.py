# from django.db import models
# from django.db import models
# from django.contrib.auth import get_user_model
# from cloudinary.models import CloudinaryField
# from django.conf import settings 


# User = get_user_model()

# class ChatThread(models.Model):
#     client = models.ForeignKey(User, on_delete=models.CASCADE, related_name="client_threads")
#     landscaper = models.ForeignKey(User, on_delete=models.CASCADE, related_name="landscaper_threads")
#     created_at = models.DateTimeField(auto_now_add=True)

#     def __str__(self):
#         return f"Thread: {self.client} ↔ {self.landscaper}"


# class Message(models.Model):
#     thread = models.ForeignKey(ChatThread, on_delete=models.CASCADE, related_name="messages")
#     sender = models.ForeignKey(User, on_delete=models.CASCADE)
#     text = models.TextField(blank=True, null=True)
#     file = CloudinaryField('file', blank=True, null=True) 
#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)
#     is_deleted = models.BooleanField(default=False)
    
#     @property
#     def message_type(self):
#         if self.file:
#             name = self.file.name.lower()
#             if name.endswith((".jpg", ".jpeg", ".png", ".gif")):
#                 return "image"
#             return "file"
#         return "text"

#     def __str__(self):
#         return f"Message from {self.sender}"

from django.db import models
from cloudinary.models import CloudinaryField

from django.conf import settings  # use settings instead of get_user_model

class ChatThread(models.Model):
    client = models.ForeignKey(
        'accounts.User',  # string reference
        on_delete=models.CASCADE,
        related_name="client_threads"
    )

    landscaper = models.ForeignKey(
        'accounts.User', on_delete=models.CASCADE, related_name="landscaper_threads"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Thread: {self.client} ↔ {self.landscaper}"


class Message(models.Model):
    thread = models.ForeignKey(ChatThread, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey('accounts.User', on_delete=models.CASCADE)
    text = models.TextField(blank=True, null=True)
    file = CloudinaryField("file", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def message_type(self):
        if self.file:
            name = self.file.name.lower()
            if name.endswith((".jpg", ".jpeg", ".png", ".gif")):
                return "image"
            return "file"
        return "text"

    def __str__(self):
        return f"Message from {self.sender}"
