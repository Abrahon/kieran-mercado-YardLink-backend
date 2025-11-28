# apps/contact/enums.py

from django.db import models

class MessageStatus(models.TextChoices):
    NEW = "New", "New"
    REPLIED = "Replied", "Replied"
    READ = "Read", "Read"



class MessageCategory(models.TextChoices):
    GENERAL = "General", "General"
    REPORT = "Report", "Report"
    SUPPORT = "Support", "Support"



