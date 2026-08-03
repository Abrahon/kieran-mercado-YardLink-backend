
from django.db import models
from django.contrib.auth import get_user_model
from cloudinary.models import CloudinaryField
from django.utils.translation import gettext_lazy as _
from django.db import models
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.contrib.postgres.fields import ArrayField, JSONField  # PostgreSQL
User = get_user_model()
from django.core.exceptions import ValidationError

from django.core.exceptions import ValidationError



# Landscaper Profile (business info)
class BusinessProfile(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="landscaper_profile")


    # Business info
    business_name = models.CharField(max_length=150)
    business_email = models.EmailField()
    business_phone = models.CharField(max_length=20)

    # Optional tagline / slogan
    tagline = models.CharField(
        max_length=250,
        blank=True,
        null=True,
        help_text="Short description or tagline about the business"
    )

    # Optional business description
    description = models.TextField(
        max_length=500,
        blank=True,
        null=True
    )

    # Location
    latitude = models.DecimalField(
        max_digits=17,      # 2 before + 15 after
        decimal_places=15,
        null=True,
        blank=True
    )

    longitude = models.DecimalField(
        max_digits=18,      # 3 before + 15 after
        decimal_places=15,
        null=True,
        blank=True
    )
    
    # Service Area
    service_radius_km = models.PositiveIntegerField(
        default=20,
        help_text="How far the landscaper is willing to travel"
    )
    # Profile image (Pro only — validated via subscription app)
    profile_image = CloudinaryField(
        "pro_landscaper",
        blank=True,
        null=True
    )

    # QuickBooks integration (Pro only — validated via subscription app)
    quickbooks_connected = models.BooleanField(default=False)

    # Either Insurance or License document
    insurance_doc = CloudinaryField(
        "insurance_doc",
        blank=True,
        null=True,
        help_text="Upload business insurance document if required"
    )
    license_doc = CloudinaryField(
        "license_doc",
        blank=True,
        null=True,
        help_text="Upload business license document if required"
    )

    # Profile complete flag
    is_profile_completed = models.BooleanField(default=False)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        # Validation: only one of insurance_doc or license_doc can be uploaded
        if self.insurance_doc and self.license_doc:
            raise ValidationError("You can upload either insurance OR license document, not both.")
        
    def save(self, *args, **kwargs):
        # AUTO PROFILE COMPLETION LOGIC
        self.is_profile_completed = all([
            self.business_name,
            self.business_email,
            self.business_phone,
            self.latitude,
            self.longitude,
        ])

        super().save(*args, **kwargs)

    def __str__(self):
        return self.business_name


# standard service
# models.py

class Service(models.Model):

    class PricingType(models.TextChoices):
        FIXED = "fixed", "Fixed Price"
        REQUEST = "request", "Priced Upon Request"

    business = models.ForeignKey(
        BusinessProfile,
        on_delete=models.CASCADE,
        related_name="services"
    )

    name = models.CharField(max_length=150)

    description = models.TextField(
        blank=True,
        null=True
    )

    # Pricing
    base_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        blank=True,
        null=True
    )

    pricing_type = models.CharField(
        max_length=10,
        choices=PricingType.choices,
        default=PricingType.FIXED
    )

    min_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        blank=True,
        null=True
    )

    # Status
    is_active = models.BooleanField(default=True)

    is_pinned = models.BooleanField(default=False)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

        indexes = [
            models.Index(fields=["business", "is_active"]),
            models.Index(fields=["pricing_type"]),
            models.Index(fields=["is_pinned"]),
        ]

        constraints = [
            models.UniqueConstraint(
                fields=["business", "name"],
                name="unique_service_per_business"
            )
        ]

    def clean(self):

        # FIXED pricing
        if self.pricing_type == self.PricingType.FIXED:

            if self.base_price is None:
                raise ValidationError(
                    "Fixed pricing requires base_price."
                )

            # optional cleanup
            self.min_price = None

        # REQUEST pricing
        if self.pricing_type == self.PricingType.REQUEST:

            if self.base_price is not None:
                raise ValidationError(
                    "Request pricing should not have base_price."
                )

            if self.min_price is None:
                raise ValidationError(
                    "Request pricing requires min_price."
                )

    def __str__(self):
        return f"{self.name} ({self.business.business_name})"



# qute model

class ServiceQuote(models.Model):

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        COUNTERED = "countered", "Countered"
        ACCEPTED = "accepted", "Accepted"
        REJECTED = "rejected", "Rejected"
        CONVERTED = "converted", "Converted"

    service = models.ForeignKey(
        "landscapers.Service",
        on_delete=models.CASCADE,
        related_name="quotes"
    )

    client = models.ForeignKey(
        "profiles.ClientProfile",
        on_delete=models.CASCADE,
        related_name="service_quotes"
    )

    landscaper = models.ForeignKey(
        "landscapers.BusinessProfile",
        on_delete=models.CASCADE,
        related_name="service_quotes"
    )

    property = models.ForeignKey(
        "property.Property",
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    message = models.TextField(blank=True, null=True)


    # LANDSCAPER confirmed schedule
    scheduled_date = models.DateField(null=True, blank=True)
    scheduled_time = models.TimeField(null=True, blank=True)

    # PRICE (only landscaper controls)
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    

    



class ClientCustomService(models.Model):

    class RecurringType(models.TextChoices):
        WEEKLY = "weekly", "Weekly"
        BIWEEKLY = "biweekly", "Biweekly"

    client = models.ForeignKey("profiles.ClientProfile", on_delete=models.CASCADE)
    # landscaper = models.ForeignKey(BusinessProfile, on_delete=models.CASCADE)
    landscaper = models.ForeignKey(
        BusinessProfile,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    property = models.ForeignKey(
        "property.Property",
        on_delete=models.CASCADE,
        related_name="custom_services"
    )

    booking = models.OneToOneField(
        "bookings.BookingRequest",
        null=True,
        blank=True,
        on_delete=models.SET_NULL
    )

    name = models.CharField(max_length=150)
    description = models.TextField(blank=True, null=True)
    note = models.TextField(blank=True, null=True)

    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )

    is_active = models.BooleanField(default=True)

    # -------------------------
    # DATE & TIME
    # -------------------------
    preferred_date = models.DateField(null=True, blank=True)
    preferred_time = models.TimeField(null=True, blank=True)

    # -------------------------
    # RECURRING
    # -------------------------
    recurring_type = models.CharField(
        max_length=10,
        choices=RecurringType.choices,
        null=True,
        blank=True,
        help_text="Set only for recurring services"
    )

    recurring_day_of_week = models.CharField(
        max_length=10,
        choices=[
            ("MONDAY", "Monday"),
            ("TUESDAY", "Tuesday"),
            ("WEDNESDAY", "Wednesday"),
            ("THURSDAY", "Thursday"),
            ("FRIDAY", "Friday"),
            ("SATURDAY", "Saturday"),
            ("SUNDAY", "Sunday"),
        ],
        null=True,
        blank=True
    )

    # -------------------------
    # STATUS
    # -------------------------
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("accepted", "Accepted"),
        ("confirmed", "Confirmed"),
        ("declined", "Declined"),
        ("completed", "Completed"),
    ]

    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default="pending"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # -------------------------
    # VALIDATION LOGIC
    # -------------------------
    def clean(self):

        # =========================
        # ONE-TIME SERVICE
        # =========================
        if not self.recurring_type:

            # Must have BOTH date and time
            if not self.preferred_date or not self.preferred_time:
                raise ValidationError(
                    "One-time service requires both date and time."
                )

            # Ensure no recurring day is stored
            self.recurring_day_of_week = None

        # =========================
        # RECURRING SERVICE
        # =========================
        else:

            # Must have a valid weekday
            if not self.recurring_day_of_week:
                raise ValidationError(
                    "Recurring service must have a day of week."
                )

            # Must have start date
            if not self.preferred_date:
                raise ValidationError(
                    "Recurring service must have a start date."
                )


# add on
class Addon(models.Model):
    business = models.ForeignKey(
        BusinessProfile,
        on_delete=models.CASCADE,
        related_name="addons"
    )

    name = models.CharField(max_length=150)

    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )

    applicable_services = models.ManyToManyField(
        Service,
        related_name="addons",
        blank=True
    )
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["business", "name"],
                name="unique_addon_per_business"
            )
        ]
    def clean(self):

        for service in self.applicable_services.all():
            if service.business != self.business:
                raise ValidationError(
                    "Addon can only be attached to services of the same business."
                )

    def __str__(self):
        return f"{self.name} ({self.business.business_name})"





from django.db import models
from django.core.exceptions import ValidationError


DAYS_OF_WEEK = [
    ('SUNDAY', 'Sunday'),
    ('MONDAY', 'Monday'),
    ('TUESDAY', 'Tuesday'),
    ('WEDNESDAY', 'Wednesday'),
    ('THURSDAY', 'Thursday'),
    ('FRIDAY', 'Friday'),
    ('SATURDAY', 'Saturday'),
]


class WorkingHours(models.Model):
    landscaper = models.ForeignKey(
        "landscapers.BusinessProfile",
        on_delete=models.CASCADE,
        related_name="working_hours"
    )

    day = models.CharField(
        max_length=10,
        choices=DAYS_OF_WEEK
    )

    start_time = models.TimeField()
    end_time = models.TimeField()

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["day", "start_time"]

        indexes = [
            models.Index(fields=["landscaper", "day"]),
        ]

    def clean(self):

        # End must be greater
        if self.start_time >= self.end_time:
            raise ValidationError(
                "End time must be greater than start time."
            )

        # Prevent overlapping shifts
        overlapping = WorkingHours.objects.filter(
            landscaper=self.landscaper,
            day=self.day,
            is_active=True,
            start_time__lt=self.end_time,
            end_time__gt=self.start_time
        )

        # exclude current instance during update
        if self.pk:
            overlapping = overlapping.exclude(pk=self.pk)

        if overlapping.exists():
            raise ValidationError(
                "This time range overlaps with another shift."
            )

    def __str__(self):
        return (
            f"{self.landscaper.business_name} - "
            f"{self.day} "
            f"({self.start_time} - {self.end_time})"
        )