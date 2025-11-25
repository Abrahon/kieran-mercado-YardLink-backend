from django.db.models import TextChoices

class RoleChoices(TextChoices):
    ADMIN = 'admin', 'Admin'
    CLIENT = 'client', 'Client'
    LANDSCAPER = 'landscaper', 'Landscaper'