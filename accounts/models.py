# accounts/models.py
from datetime import timedelta
from django.db import models
from django.utils import timezone
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from .enums import RoleChoices


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, role=None, **extra_fields):
        """
        Create and save a regular user. Role is required (no default).
        """
        if not email:
            raise ValueError("Users must have an email address")
        if role is None:
            raise ValueError("A role must be provided when creating a user")

        email = self.normalize_email(email)
        user = self.model(email=email, role=role, **extra_fields)
        user.set_password(password)
        # ensure staff/superuser flags are consistent with role
        if role == RoleChoices.ADMIN:
            user.is_staff = True
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        """
        Create and save a superuser. Force admin role + flags.
        """
        extra_fields.setdefault('role', RoleChoices.ADMIN)
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)

    # NEW FIELDS
    phone = models.CharField(max_length=20, blank=True, null=True)
    address = models.CharField(max_length=255, blank=True, null=True)
    latitude = models.DecimalField(max_digits=10, decimal_places=7, blank=True, null=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, blank=True, null=True)

    # NOTE: no default role. Must be provided.
    role = models.CharField(max_length=20, choices=RoleChoices.choices)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)   # set True for admins
    is_superuser = models.BooleanField(default=False)
    date_joined = models.DateTimeField(auto_now_add=True)

    groups = models.ManyToManyField(
        'auth.Group',
        related_name='accounts_user_set',
        blank=True
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        related_name='accounts_user_permissions_set',
        blank=True
    )

    objects = UserManager()

    USERNAME_FIELD = 'email'
    # include 'role' in REQUIRED_FIELDS so createsuperuser prompts for it if needed
    REQUIRED_FIELDS = ['name', 'role']

    def __str__(self):
        return self.email

    def clean(self):
        # optional: ensure role is one of choices
        super().clean()
        if self.role not in RoleChoices.values:
            raise ValueError("Invalid role for user")


class OTP(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)

    def is_expired(self):
        from django.utils import timezone
        from datetime import timedelta
        return timezone.now() > self.created_at + timedelta(minutes=5)

    def __str__(self):
        if self.user:
            return f"{self.code} ({self.user.email})"
        return f"{self.code} ({self.email})"   # ❌ FIXED: removed extra dot







