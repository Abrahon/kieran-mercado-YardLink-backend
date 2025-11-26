# 
# admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, OTP

class UserAdmin(BaseUserAdmin):
    model = User
    list_display = ("id", "email", "name", "role", "is_active", "is_staff", "is_superuser")
    search_fields = ("email", "name")
    ordering = ("id",)

    # Disable logging to django_admin_log
    def log_addition(self, request, object, message):
        pass

    def log_change(self, request, object, message):
        pass

    def log_deletion(self, request, object, message):
        pass

# Register
admin.site.register(User, UserAdmin)
admin.site.register(OTP)
